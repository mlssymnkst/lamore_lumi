"""Tela de Faturamento (Flask): serve a página HTML e a API JSON.

Rotas:
    GET /faturamento                  -> página (faturamento/faturamento.html)
    GET /faturamento/<css|js>         -> arquivos da página
    GET /api/faturamento?ano=&status=&uf=&q=   -> dados já filtrados e somados

Sem pandas: só biblioteca padrão, para o deploy ficar leve.
"""
import os
import random
import unicodedata
from datetime import date, timedelta

from flask import Blueprint, abort, jsonify, request, send_from_directory

faturamento_bp = Blueprint("faturamento", __name__)

PASTA_PAGINA = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "faturamento"))
# Só estes arquivos saem da pasta (impede baixar código-fonte por engano)
ARQUIVOS_PUBLICOS = {"faturamento.css", "faturamento.js"}

TODOS = "Todos"
ESTADOS_BR = ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT",
              "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO",
              "RR", "SC", "SP", "SE", "TO"]


# ---------------------------------------------------------------------------
# DADOS (fictícios). Para usar dados reais, troque SOMENTE carregar_pedidos():
# ela deve devolver uma lista de dicts com as chaves
# pedido, cliente, categoria, valor (float), data (datetime.date), status, uf
# ---------------------------------------------------------------------------
_PEDIDOS_BASE = [
    (1, "Cliente 1", "Categoria 1", 200.00, "2026-01-01", "Pago", "SP"),
    (2, "Cliente 2", "Categoria 2", 470.00, "2026-01-15", "Pendente", "RJ"),
    (3, "Cliente 3", "Categoria 3", 9200.00, "2026-02-05", "Cancelado", "MG"),
    (4, "Cliente 4", "Categoria 4", 10.00, "2026-02-20", "Pago", "SP"),
    (5, "Cliente 5", "Categoria 5", 1000.00, "2026-03-01", "Pendente", "PR"),
]


def _gerar_pedidos_ficticios(qtd=100, primeiro_numero=6, ano=2026, semente=42):
    """Pedidos de exemplo. A semente fixa mantém os mesmos dados a cada execução."""
    rng = random.Random(semente)
    categorias = ["Convites", "Save the date", "Cardápios", "Marcadores de mesa",
                  "Tags e lacres", "Caixas personalizadas", "Papelaria de cerimônia"]
    status = ["Pago", "Pendente", "Cancelado", "Atrasado"]
    pesos_status = [55, 20, 10, 15]
    pesos_uf = {"SP": 10, "RJ": 7, "MG": 7, "PR": 5, "RS": 5, "SC": 4, "BA": 4}
    pesos = [pesos_uf.get(uf, 1.5) for uf in ESTADOS_BR]
    pedidos = []
    for i in range(qtd):
        # os 27 primeiros percorrem todos os estados: o mapa tem número em cada um
        uf = ESTADOS_BR[i] if i < len(ESTADOS_BR) else rng.choices(ESTADOS_BR, weights=pesos)[0]
        n = primeiro_numero + i
        pedidos.append({
            "pedido": n, "cliente": f"Cliente {n}", "categoria": rng.choice(categorias),
            "valor": round(min(max(rng.lognormvariate(6.3, 0.8), 60), 9500), 2),
            "data": date(ano, 1, 1) + timedelta(days=rng.randrange(365)),
            "status": rng.choices(status, weights=pesos_status)[0], "uf": uf,
        })
    return pedidos


_cache = {}


def carregar_pedidos():
    """PONTO DE TROCA: aqui entra a consulta ao banco quando houver dados reais."""
    if "pedidos" not in _cache:
        base = [{"pedido": n, "cliente": c, "categoria": cat, "valor": v,
                 "data": date.fromisoformat(d), "status": s, "uf": uf}
                for (n, c, cat, v, d, s, uf) in _PEDIDOS_BASE]
        _cache["pedidos"] = base + _gerar_pedidos_ficticios(100)
    return _cache["pedidos"]


# ---------------------------------------------------------------------------
# FUNÇÕES AUXILIARES
# ---------------------------------------------------------------------------
def formatar_moeda(valor):
    texto = f"{float(valor):,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def normalizar(texto):
    """Minúsculas e sem acento: 'ceri' acha 'cerimônia'."""
    sem_acento = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return sem_acento.lower()


def filtrar_por_busca(pedidos, termo):
    """Mantém os pedidos em que TODAS as palavras digitadas aparecem em algum campo
    (nº do pedido, cliente, categoria, valor, data, status ou UF)."""
    palavras = normalizar(termo).split()
    if not palavras:
        return pedidos
    achados = []
    for p in pedidos:
        texto = normalizar(" ".join([
            str(p["pedido"]), p["cliente"], p["categoria"], p["status"], p["uf"],
            p["data"].strftime("%d/%m/%Y"), formatar_moeda(p["valor"]),
        ]))
        if all(palavra in texto for palavra in palavras):
            achados.append(p)
    return achados


# ---------------------------------------------------------------------------
# ROTAS
# ---------------------------------------------------------------------------
@faturamento_bp.route("/faturamento")
def pagina_faturamento():
    return send_from_directory(PASTA_PAGINA, "faturamento.html")


@faturamento_bp.route("/faturamento/<path:arquivo>")
def arquivos_faturamento(arquivo):
    if arquivo not in ARQUIVOS_PUBLICOS:
        abort(404)
    return send_from_directory(PASTA_PAGINA, arquivo)


@faturamento_bp.route("/api/faturamento")
def api_faturamento():
    pedidos = [{**p, "status": str(p["status"]).strip().title(),
                "uf": str(p["uf"]).strip().upper()} for p in carregar_pedidos()]

    anos = sorted({p["data"].year for p in pedidos}, reverse=True)
    ano = request.args.get("ano", type=int)
    if ano not in anos:
        ano = anos[0] if anos else date.today().year
    status = request.args.get("status", TODOS)
    uf = request.args.get("uf", TODOS)
    termo = request.args.get("q", "")

    # 1) pesquisa  2) ano  3) status/UF. O mapa ignora o filtro de UF
    #    (senão sobraria um estado só).
    buscados = filtrar_por_busca(pedidos, termo)
    do_ano = [p for p in buscados if p["data"].year == ano]
    base_mapa = [p for p in do_ano if status in (TODOS, p["status"])]
    filtrados = [p for p in base_mapa if uf in (TODOS, p["uf"])]

    # --- cards (somam TODOS os status) ---
    por_uf = {}
    for p in filtrados:
        por_uf[p["uf"]] = por_uf.get(p["uf"], 0) + p["valor"]
    cards = {
        "total_pedidos": len(filtrados),
        "atrasados": sum(1 for p in filtrados if p["status"] == "Atrasado"),
        "pendentes": sum(1 for p in filtrados if p["status"] == "Pendente"),
        "faturamento_total": round(sum(p["valor"] for p in filtrados), 2),
        "estado_maior": max(por_uf, key=por_uf.get) if por_uf else "—",
    }

    # --- gráfico: 12 meses, mesmo os sem vendas (R$ 0) ---
    mensal = [0.0] * 12
    pedidos_mes = [0] * 12
    for p in filtrados:
        mensal[p["data"].month - 1] += p["valor"]
        pedidos_mes[p["data"].month - 1] += 1

    # --- mapa: faturamento de todos os 27 estados ---
    estados = {sigla: 0.0 for sigla in ESTADOS_BR}
    for p in base_mapa:
        if p["uf"] in estados:
            estados[p["uf"]] += p["valor"]

    tabela = [{
        "pedido": p["pedido"], "cliente": p["cliente"], "categoria": p["categoria"],
        "valor": p["valor"], "data": p["data"].strftime("%d/%m/%Y"),
        "status": p["status"], "uf": p["uf"],
    } for p in sorted(filtrados, key=lambda x: x["pedido"])]

    return jsonify({
        "ano": ano,
        "opcoes": {
            "anos": anos,
            "status": sorted({p["status"] for p in pedidos}),
            "ufs": sorted({p["uf"] for p in pedidos if p["uf"]}),
        },
        "cards": cards,
        "mensal": [round(v, 2) for v in mensal],
        "pedidos_mes": pedidos_mes,
        "estados": {k: round(v, 2) for k, v in estados.items()},
        "pedidos": tabela,
    })