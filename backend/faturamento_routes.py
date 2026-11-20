"""Tela de Faturamento (Flask): serve a página HTML e a API JSON.

Rotas:
    GET /faturamento                  -> página (faturamento/faturamento.html)
    GET /faturamento/<css|js>         -> arquivos da página
    GET /api/faturamento?ano=&status=&uf=&q=   -> dados já filtrados e somados

Sem pandas: só biblioteca padrão, para o deploy ficar leve.
"""
import os
import unicodedata
from datetime import date

from flask import Blueprint, abort, current_app, jsonify, request, send_from_directory
from psycopg2 import Error as PsycopgError

from backend.warehouse import WarehouseNotConfigured, consultar

faturamento_bp = Blueprint("faturamento", __name__)

PASTA_PAGINA = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "faturamento"))
# Só estes arquivos saem da pasta (impede baixar código-fonte por engano)
ARQUIVOS_PUBLICOS = {
    "faturamento.css",
    "faturamento.js",
    "ruptura-estoque.css",
    "ruptura-estoque.js"
}

TODOS = "Todos"
ESTADOS_BR = ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT",
              "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO",
              "RR", "SC", "SP", "SE", "TO"]


def carregar_pedidos():
    """Carrega pedidos históricos do data warehouse, sem dados de identificação pessoal."""
    registros = consultar(
        """
        SELECT num_pedido AS pedido,
               'Cliente ' || num_pedido AS cliente,
               COALESCE(categoria, 'Outros') AS categoria,
               COALESCE(valor_total_pedido, valor_orcado, 0)::float AS valor,
               data_pedido AS data,
               COALESCE(status_orcamento, 'Não informado') AS status,
               COALESCE(uf, '') AS uf,
               COALESCE(dias_atraso_frete, 0) > 0 AS atrasado
        FROM pedidos_historicos
        WHERE data_pedido IS NOT NULL
        """
    )
    return [
        {
            **registro,
            "data": registro["data"],
            "status": str(registro["status"]).strip().title(),
            "uf": str(registro["uf"]).strip().upper(),
            "valor": float(registro["valor"] or 0),
        }
        for registro in registros
    ]


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
    try:
        pedidos = carregar_pedidos()
    except WarehouseNotConfigured as erro:
        return jsonify({"erro": str(erro)}), 503
    except PsycopgError:
        current_app.logger.exception("Falha ao consultar o faturamento no PostgreSQL.")
        return jsonify({"erro": "Não foi possível consultar os pedidos históricos."}), 503

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
        "atrasados": sum(1 for p in filtrados if p["atrasado"]),
        "pendentes": sum(1 for p in filtrados if normalizar(p["status"]) == "em negociacao"),
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