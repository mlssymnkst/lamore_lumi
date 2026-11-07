"""Página e indicadores do dashboard de orçamentos."""
import os
import unicodedata
from collections import defaultdict
from datetime import date

from flask import Blueprint, current_app, jsonify, request, send_from_directory
from psycopg2 import Error as PsycopgError

from backend.warehouse import WarehouseNotConfigured, consultar

dashboard_bp = Blueprint("dashboard", __name__)
PASTA_DASHBOARD = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "dashboard")
)
ARQUIVOS_PUBLICOS = {
    "dashboard.css", "dashboard.js", "dashboard-bg.png", "brazil-states.geojson",
}
UF_POR_CODAREA = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA",
    "16": "AP", "17": "TO", "21": "MA", "22": "PI", "23": "CE",
    "24": "RN", "25": "PB", "26": "PE", "27": "AL", "28": "SE",
    "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP",
    "41": "PR", "42": "SC", "43": "RS", "50": "MS", "51": "MT",
    "52": "GO", "53": "DF",
}
UF_POR_NOME = {
    "rondonia": "RO", "acre": "AC", "amazonas": "AM",
    "roraima": "RR", "para": "PA", "amapa": "AP", "tocantins": "TO",
    "maranhao": "MA", "piaui": "PI", "ceara": "CE",
    "rio grande do norte": "RN", "paraiba": "PB", "pernambuco": "PE",
    "alagoas": "AL", "sergipe": "SE", "bahia": "BA",
    "minas gerais": "MG", "espirito santo": "ES", "rio de janeiro": "RJ",
    "sao paulo": "SP", "parana": "PR", "santa catarina": "SC",
    "rio grande do sul": "RS", "mato grosso do sul": "MS",
    "mato grosso": "MT", "goias": "GO", "distrito federal": "DF",
}

STATUS_FECHADOS = {
    "aprovado", "aprovada", "concluido", "concluida", "fechado", "fechada",
    "finalizado", "finalizada", "pago", "paga",
}
STATUS_NEGOCIACAO = {
    "aberto", "aberta", "aguardando", "em andamento", "em negociacao",
    "negociacao", "orcamento", "pendente",
}
MEDIA_DESPERDICIO_POR_ANO = {
    2021: 4.8,
    2022: 5.3,
    2023: 5.7,
    2024: 10.0,
    2025: 6.3,
    2026: 5.2,
}


def _normalizar(valor):
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    return "".join(char for char in texto if not unicodedata.combining(char)).strip().lower()


def _sigla_estado(valor):
    estado = _normalizar(valor)
    if estado in UF_POR_CODAREA:
        return UF_POR_CODAREA[estado]
    if len(estado) == 2 and estado.upper() in UF_POR_CODAREA.values():
        return estado.upper()
    return UF_POR_NOME.get(estado)


def _numero(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return 0.0


@dashboard_bp.get("/dashboard")
def pagina_dashboard():
    return send_from_directory(PASTA_DASHBOARD, "dashboard.html")


@dashboard_bp.get("/dashboard/assets/<path:arquivo>")
def arquivos_dashboard(arquivo):
    if arquivo not in ARQUIVOS_PUBLICOS:
        return jsonify({"erro": "Arquivo não encontrado"}), 404
    return send_from_directory(PASTA_DASHBOARD, arquivo)


@dashboard_bp.get("/api/dashboard")
def dados_dashboard():
    ano_texto = request.args.get("ano", "2026")
    try:
        ano = int(ano_texto)
    except ValueError:
        return jsonify({"erro": "Ano inválido. Selecione um ano entre 2021 e 2026."}), 400
    if ano < 2021 or ano > 2026:
        return jsonify({"erro": "Ano inválido. Selecione um ano entre 2021 e 2026."}), 400

    try:
        pedidos = consultar(
            """
            SELECT status_orcamento, data_pedido, valor_orcado,
                   valor_total_pedido, uf, nome_produto, categoria, unidades
            FROM pedidos_historicos
            WHERE data_pedido >= %s AND data_pedido < %s
            """,
            (date(ano, 1, 1), date(ano + 1, 1, 1)),
        )
    except WarehouseNotConfigured as erro:
        return jsonify({"erro": str(erro)}), 503
    except PsycopgError:
        current_app.logger.exception("Falha ao consultar o dashboard no PostgreSQL.")
        return jsonify({
            "erro": "Não foi possível consultar os dados analíticos no PostgreSQL."
        }), 503

    pedidos = [
        pedido for pedido in pedidos
        if pedido.get("data_pedido") and pedido["data_pedido"].year == ano
    ]

    total_fechados = 0
    total_negociacao = 0
    valor_potencial = 0.0
    mensal_por_periodo = defaultdict(lambda: {"fechados": 0, "negociacao": 0})
    por_produto = defaultdict(int)
    por_categoria = defaultdict(int)
    por_regiao = defaultdict(lambda: {"orcamentos": 0, "valor": 0.0})

    for pedido in pedidos:
        status = _normalizar(pedido.get("status_orcamento"))
        valor = _numero(pedido.get("valor_total_pedido") or pedido.get("valor_orcado"))
        quando = pedido.get("data_pedido")
        quantidade = int(_numero(pedido.get("unidades")) or 1)
        categoria = pedido.get("categoria")
        nome_produto = pedido.get("nome_produto")

        if nome_produto:
            por_produto[str(nome_produto)] += quantidade
        if categoria:
            por_categoria[str(categoria)] += quantidade

        uf = _sigla_estado(pedido.get("uf"))
        if uf:
            agregado = por_regiao[uf]
            agregado["orcamentos"] += 1
            agregado["valor"] += valor

        if status in STATUS_FECHADOS:
            total_fechados += 1
            if quando:
                mensal_por_periodo[(quando.year, quando.month)]["fechados"] += 1
        elif status in STATUS_NEGOCIACAO:
            total_negociacao += 1
            valor_potencial += _numero(pedido.get("valor_orcado"))
            if quando:
                mensal_por_periodo[(quando.year, quando.month)]["negociacao"] += 1

    serie_mensal = []
    if mensal_por_periodo:
        ano, mes = min(mensal_por_periodo)
        ultimo_ano, ultimo_mes = max(mensal_por_periodo)
        while (ano, mes) <= (ultimo_ano, ultimo_mes):
            dados_mes = mensal_por_periodo[(ano, mes)]
            serie_mensal.append({
                "periodo": f"{ano:04d}-{mes:02d}",
                **dados_mes,
            })
            mes += 1
            if mes == 13:
                ano += 1
                mes = 1

    return jsonify({
        "indicadores": {
            "orcamentos_fechados": total_fechados,
            "media_desperdicio": MEDIA_DESPERDICIO_POR_ANO[ano],
            "pedidos_negociacao": total_negociacao,
            "valor_negociacao": round(valor_potencial, 2),
        },
        "mensal": serie_mensal,
        "produtos": [
            {"nome": nome, "quantidade": quantidade}
            for nome, quantidade in sorted(
                por_produto.items(), key=lambda item: item[1], reverse=True
            )[:6]
        ],
        "categorias": [
            {"nome": nome, "quantidade": quantidade}
            for nome, quantidade in sorted(
                por_categoria.items(), key=lambda item: item[1], reverse=True
            )[:6]
        ],
        "regioes": [
            {"nome": nome, **dados}
            for nome, dados in sorted(
                por_regiao.items(), key=lambda item: item[1]["valor"], reverse=True
            )
        ],
    })
