"""LUMI — previsão por COMPONENTE e simulação de estoque (28 dias).

Base: dataset_lamore.csv, somente pedidos aprovados.
Um pedido "Convite Premium + Lenço" contribui para a demanda de ambos.
Assunção didática: 1 unidade de cada componente por unidade do kit.
Não deduz consumo físico real nem atualiza estoque automaticamente.

Saídas:
  backend/lumi_estoque_componentes.csv  (editável: estoque, mínimo e prazo)
  backend/lumi_snapshot.json           (usado pela API existente)

Da raiz do projeto, execute: python -m backend.lumi_forecast
"""
from pathlib import Path
from datetime import datetime, timezone
import json

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

RAIZ = Path(__file__).resolve().parents[1]
BACKEND = Path(__file__).resolve().parent
ARQUIVO_DADOS = RAIZ / "dataset_lamore.csv"
ARQUIVO_ESTOQUE = BACKEND / "lumi_estoque_componentes.csv"
ARQUIVO_SNAPSHOT = BACKEND / "lumi_snapshot.json"
HORIZONTE = 28                         # mesmo horizonte de 4 semanas do notebook
MAX_COMPONENTES = 21                   # todos os 21 componentes desta base
JANELA_HISTORICO = 28
SEMENTE = 42


def carregar_dados():
    """Um registro aprovado pode gerar N linhas: uma por componente do kit."""
    df = pd.read_csv(
        ARQUIVO_DADOS,
        usecols=["nome_produto", "status_orcamento", "data_pedido", "unidades"],
        encoding="utf-8-sig",
    )
    df["data_pedido"] = pd.to_datetime(df["data_pedido"], errors="coerce").dt.normalize()
    df["unidades"] = pd.to_numeric(df["unidades"], errors="coerce")
    df = df[df["status_orcamento"].astype(str).str.strip().str.casefold() == "aprovado"]
    df = df.dropna(subset=["data_pedido", "nome_produto", "unidades"])
    df = df[df["unidades"] > 0].copy()
    df["produto_vendido"] = df["nome_produto"].astype(str).str.strip()
    df = df[df["produto_vendido"] != ""]
    df["nome_produto"] = df["produto_vendido"].str.split("+", regex=False)
    df = df.explode("nome_produto")
    df["nome_produto"] = df["nome_produto"].astype(str).str.strip()
    df = df[df["nome_produto"] != ""].copy()
    if df.empty:
        raise ValueError("Não foram encontrados pedidos aprovados com componentes válidos.")
    return df


def preparar_series(df):
    componentes = (df.groupby("nome_produto")["unidades"].sum()
                   .sort_values(ascending=False).head(MAX_COMPONENTES).index.tolist())
    ultima_data = df["data_pedido"].max().normalize()
    calendario = pd.date_range(df["data_pedido"].min().normalize(), ultima_data, freq="D")
    series = {}
    for componente in componentes:
        serie = (df.loc[df["nome_produto"] == componente]
                 .groupby("data_pedido")["unidades"].sum()
                 .reindex(calendario, fill_value=0).astype(float))
        series[componente] = serie
    return series, ultima_data


def obter_origens(df, componentes):
    """Informações para explicar por quais itens/combos um insumo foi consumido."""
    saida = {}
    for nome in componentes:
        registros = df.loc[df["nome_produto"] == nome].copy()
        kit = registros["produto_vendido"].str.contains("+", regex=False)
        ranking = (registros.groupby("produto_vendido")["unidades"]
                   .sum().sort_values(ascending=False))
        saida[nome] = {
            "venda_individual_historica": float(registros.loc[~kit, "unidades"].sum()),
            "consumo_em_kits_historico": float(registros.loc[kit, "unidades"].sum()),
            "produtos_que_utilizam": [
                {"nome": origem, "unidades_atribuidas": int(qtd)}
                for origem, qtd in ranking.head(7).items()
            ],
        }
    return saida


def atributos(historico, data, indice, escala):
    h = np.asarray(historico, dtype=float)
    dia_semana, dia_ano = data.dayofweek, data.dayofyear
    return [
        h[-1] / escala, h[-7] / escala, h[-14] / escala, h[-28] / escala,
        h[-7:].mean() / escala, h[-14:].mean() / escala,
        h[-28:].mean() / escala, h[-7:].std() / escala,
        np.sin(2 * np.pi * dia_semana / 7), np.cos(2 * np.pi * dia_semana / 7),
        np.sin(2 * np.pi * dia_ano / 365.25), np.cos(2 * np.pi * dia_ano / 365.25),
        indice,
    ]


def preparar_treinamento(series):
    X, y, datas, escalas = [], [], [], {}
    for indice, (nome, serie) in enumerate(series.items()):
        valores = serie.to_numpy(dtype=float)
        escala = max(float(valores.mean()), 1.0)
        escalas[nome] = escala
        for posicao in range(JANELA_HISTORICO, len(serie)):
            X.append(atributos(valores[posicao-JANELA_HISTORICO:posicao],
                               serie.index[posicao], indice, escala))
            y.append(valores[posicao] / escala)
            datas.append(serie.index[posicao])
    return np.asarray(X, dtype=float), np.asarray(y, dtype=float), pd.DatetimeIndex(datas), escalas


def treinar_mlp(X, y, datas):
    """Validação temporal e comparação com uma referência de previsão simples."""
    corte = datas.max() - pd.Timedelta(days=60)
    treino, teste = datas <= corte, datas > corte
    if treino.sum() < 100 or teste.sum() < 10:
        raise ValueError("Histórico insuficiente para treinamento e validação.")

    def construir():
        return make_pipeline(StandardScaler(), MLPRegressor(
            hidden_layer_sizes=(32, 16), activation="relu", solver="adam",
            alpha=0.1, learning_rate_init=0.001, max_iter=180,
            early_stopping=True, n_iter_no_change=12, random_state=SEMENTE,
        ))

    validacao = construir()
    validacao.fit(X[treino], y[treino])
    estimado = np.maximum(validacao.predict(X[teste]), 0)
    mae = float(mean_absolute_error(y[teste], estimado))
    # Referência: últimos 7 dias, normalizada (feature 5 do vetor de entrada).
    baseline = float(mean_absolute_error(y[teste], X[teste, 4]))

    modelo = construir()
    modelo.fit(X, y)
    return modelo, mae, baseline


def prever_demanda(modelo, series, escalas, ultima_data):
    resultados = {}
    for indice, (nome, serie) in enumerate(series.items()):
        historico = serie.to_numpy(dtype=float).tolist()
        previsoes = []
        for passo in range(1, HORIZONTE + 1):
            data = ultima_data + pd.Timedelta(days=passo)
            entrada = np.asarray([atributos(historico[-JANELA_HISTORICO:],
                                            data, indice, escalas[nome])])
            demanda = max(0, float(modelo.predict(entrada)[0]) * escalas[nome])
            previsoes.append({"data": data.strftime("%Y-%m-%d"),
                              "unidades": round(demanda, 2)})
            historico.append(demanda)
        resultados[nome] = previsoes
    return resultados


def preparar_estoque(series):
    """Arquivo de CENÁRIOS de componentes. Não substitui o CSV antigo de kits."""
    registros = []
    for nome, serie in series.items():
        media = max(float(serie.tail(90).mean()), 0.1)
        registros.append({
            "nome_produto": nome,
            "estoque_atual": int(np.ceil(media * 28)),
            "estoque_minimo": int(np.ceil(media * 7)),
            "prazo_reposicao_dias": 7,
        })
    padrao = pd.DataFrame(registros).set_index("nome_produto")
    if ARQUIVO_ESTOQUE.exists():
        existente = pd.read_csv(ARQUIVO_ESTOQUE, encoding="utf-8-sig")
        colunas = ["nome_produto", "estoque_atual", "estoque_minimo", "prazo_reposicao_dias"]
        if all(coluna in existente.columns for coluna in colunas):
            existente = existente.drop_duplicates("nome_produto").set_index("nome_produto")
            for coluna in colunas[1:]:
                valores = pd.to_numeric(existente[coluna], errors="coerce")
                padrao[coluna] = valores.reindex(padrao.index).combine_first(padrao[coluna])
    for coluna in ["estoque_atual", "estoque_minimo", "prazo_reposicao_dias"]:
        padrao[coluna] = pd.to_numeric(padrao[coluna], errors="coerce").fillna(0).clip(lower=0).round().astype(int)
    padrao.reset_index().to_csv(ARQUIVO_ESTOQUE, index=False, encoding="utf-8-sig")
    return padrao


def dia_limite(curva, limite):
    """Primeiro dia (0..HORIZONTE) em que o estoque é <= limite."""
    for dia, saldo in enumerate(curva):
        if saldo <= limite:
            return dia
    return None


def data_calendario(ultima_data, dia):
    """Dia 0 = último dia do histórico; Dia 1 = primeiro dia projetado.

    Aceita None quando não há alerta/ruptura durante o horizonte analisado.
    """
    if dia is None:
        return None
    return (ultima_data + pd.Timedelta(days=int(dia))).strftime("%Y-%m-%d")


def simular_ruptura(previsoes, estoque, origens, ultima_data):
    produtos = []
    for nome, previsao_diaria in previsoes.items():
        cfg = estoque.loc[nome]
        atual = int(cfg["estoque_atual"])
        minimo = int(cfg["estoque_minimo"])
        prazo = int(cfg["prazo_reposicao_dias"])
        demanda_total = sum(float(d["unidades"]) for d in previsao_diaria)
        media_diaria = demanda_total / HORIZONTE
        ponto = int(np.ceil(media_diaria * prazo + minimo))
        trajetoria = [float(atual)]
        saldo = float(atual)
        for dia in previsao_diaria:
            saldo = max(0.0, saldo - float(dia["unidades"]))
            trajetoria.append(round(saldo, 2))
        ruptura = dia_limite(trajetoria, 0)
        alerta = dia_limite(trajetoria, ponto)
        dia_minimo = dia_limite(trajetoria, minimo)
        if ruptura is not None and ruptura <= prazo:
            risco = "critico"
        elif ruptura is not None:
            risco = "alto"
        elif alerta is not None:
            risco = "moderado"
        else:
            risco = "baixo"
        reposicao = max(0, int(np.ceil(demanda_total + minimo - atual)))
        produtos.append({
            "nome_produto": nome,
            "demanda_prevista_total": round(demanda_total, 2),
            "demanda_media_diaria": round(media_diaria, 2),
            "risco": risco,
            # Guarda os offsets para os cálculos e as datas para o dashboard.
            "dia_ruptura": ruptura,
            "dia_alerta_reposicao": alerta,
            "dia_estoque_minimo": dia_minimo,
            "data_ruptura": data_calendario(ultima_data, ruptura),
            "data_alerta_reposicao": data_calendario(ultima_data, alerta),
            "data_estoque_minimo": data_calendario(ultima_data, dia_minimo),
            "datas_grafico": [
                data_calendario(ultima_data, dia)
                for dia in range(len(trajetoria))
            ],
            "dias_cobertura": round(atual / media_diaria, 1) if media_diaria else None,
            "reposicao_sugerida": reposicao,
            "ponto_reposicao": ponto,
            "previsao_diaria": previsao_diaria,
            "origens": origens.get(nome, {}),
            "estoque": {
                "atual": atual,
                "estoque_minimo": minimo,
                "prazo_reposicao_dias": prazo,
                "trajetoria_sem_reposicao": trajetoria[1:],
            },
        })
    ordem = {"critico": 0, "alto": 1, "moderado": 2, "baixo": 3}
    produtos.sort(key=lambda p: (ordem[p["risco"]], -p["demanda_prevista_total"]))
    return produtos


def main():
    print("[1/5] Lendo pedidos aprovados e separando componentes dos kits...", flush=True)
    df = carregar_dados()
    series, ultima_data = preparar_series(df)
    origens = obter_origens(df, series.keys())
    print(f"      {len(series)} componentes · {len(df)} atribuições de unidades", flush=True)
    print("[2/5] Criando atributos e treinando MLP...", flush=True)
    X, y, datas, escalas = preparar_treinamento(series)
    modelo, mae, baseline = treinar_mlp(X, y, datas)
    print(f"      MAE MLP normalizado={mae:.4f}; referência={baseline:.4f}", flush=True)
    print("[3/5] Gerando previsão de 28 dias...", flush=True)
    previsoes = prever_demanda(modelo, series, escalas, ultima_data)
    print("[4/5] Simulando estoque, ponto de reposição e alertas...", flush=True)
    estoque = preparar_estoque(series)
    produtos = simular_ruptura(previsoes, estoque, origens, ultima_data)
    print("[5/5] Salvando JSON do dashboard...", flush=True)
    resumo = {
        "total_produtos": len(produtos),
        "produtos_em_risco": sum(p["risco"] in ("critico", "alto") for p in produtos),
        "produtos_criticos": sum(p["risco"] == "critico" for p in produtos),
        "reposicao_total_sugerida": sum(p["reposicao_sugerida"] for p in produtos),
    }
    snapshot = {
        "modelo": "MLPRegressor", "tipo_estoque": "simulado",
        "horizonte_dias": HORIZONTE,
        "ultima_data_historico": ultima_data.strftime("%Y-%m-%d"),
        "data_inicio_previsao": data_calendario(ultima_data, 1),
        "data_fim_previsao": data_calendario(ultima_data, HORIZONTE),
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "criterio_demanda": "Pedidos aprovados; componentes extraídos de kits separados por '+'",
        "aviso_composicao": "Hipótese: uma unidade de cada componente por unidade de kit; validar a ficha técnica real.",
        "aviso_previsao": "Simulação histórica, não acompanha novas vendas em tempo real.",
        "metrica_validacao": {
            "mae_demanda_normalizada": round(mae, 4),
            "mae_referencia_normalizada": round(baseline, 4),
            "observacao": "MAE normalizado; a MLP não deve orientar compras automáticas sem validação.",
        },
        "resumo": resumo, "produtos": produtos,
    }
    ARQUIVO_SNAPSHOT.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Snapshot salvo:", ARQUIVO_SNAPSHOT, flush=True)
    print("Cenário editável:", ARQUIVO_ESTOQUE, flush=True)
    print("Resumo:", resumo, flush=True)


if __name__ == "__main__":
    main()
