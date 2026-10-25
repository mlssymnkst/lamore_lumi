"""Página e indicadores do dashboard de orçamentos."""
import os
import unicodedata
from collections import defaultdict
from datetime import date, datetime

from flask import Blueprint, jsonify, send_from_directory
from pymongo.errors import PyMongoError

from backend.banco import (
    itens_orcamento_collection,
    orcamentos_collection,
    produtos_collection,
)

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


def _valor(documento, *campos):
    for campo in campos:
        valor = documento.get(campo)
        if valor is not None:
            return valor
    return None


def _data(documento):
    valor = _valor(
        documento, "data_orcamento", "data_criacao", "dataOrcamento", "criado_em"
    )
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        try:
            return date.fromisoformat(valor[:10])
        except ValueError:
            try:
                return datetime.strptime(valor, "%d/%m/%Y").date()
            except ValueError:
                return None
    return None


def _classificar(documento):
    status = _normalizar(_valor(documento, "status", "situacao", "estado_orcamento"))
    if status in STATUS_FECHADOS:
        return "fechado"
    if status in STATUS_NEGOCIACAO or not status:
        return "negociacao"
    return "outro"


def _numero(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return 0.0


def _nome_produto(item, produtos_por_id):
    nome = _valor(item, "nomeProduto", "nome_produto", "produto")
    if isinstance(nome, dict):
        nome = _valor(nome, "nome", "descricao")
    if nome:
        return str(nome)
    produto_id = item.get("produtoId")
    if produto_id is not None:
        produto = produtos_por_id.get(str(produto_id))
        if produto:
            return str(_valor(produto, "nome", "descricao") or "Produto")
    return "Produto sem nome"


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
    try:
        orcamentos = list(orcamentos_collection.find({}, {
            "data_orcamento": 1, "data_criacao": 1, "dataOrcamento": 1,
            "criado_em": 1, "itens": 1,
            "status": 1, "situacao": 1, "estado_orcamento": 1,
            "valor_final": 1, "valor_total": 1, "valor_potencial": 1,
            "categoria": 1, "estado": 1, "uf": 1, "regiao": 1,
            "percentual_desperdicio": 1, "desperdicio_percentual": 1,
            "desperdicio": 1, "orcamentoId": 1, "clienteId": 1,
        }))
        itens = list(itens_orcamento_collection.find({}, {
            "produtoId": 1, "orcamentoId": 1, "produto": 1,
            "nomeProduto": 1, "nome_produto": 1, "quantidade": 1,
            "subtotal": 1, "categoria": 1,
        }))
        produtos = list(produtos_collection.find({}, {"nome": 1, "descricao": 1}))
    except PyMongoError:
        return jsonify({
            "erro": "Não foi possível consultar os dados do dashboard no MongoDB."
        }), 503

    total_fechados = 0
    total_negociacao = 0
    valor_potencial = 0.0
    valores_desperdicio = []
    mensal_fechados = [0] * 12
    mensal_negociacao = [0] * 12
    por_categoria = defaultdict(int)
    por_regiao = defaultdict(lambda: {"orcamentos": 0, "valor": 0.0})
    orcamentos_por_id = {}

    for orcamento in orcamentos:
        identificador = orcamento.get("_id")
        if identificador is not None:
            orcamentos_por_id[str(identificador)] = orcamento

        situacao = _classificar(orcamento)
        valor = _numero(_valor(
            orcamento, "valor_final", "valor_total", "valor_potencial"
        ))
        quando = _data(orcamento)
        if situacao == "fechado":
            total_fechados += 1
            if quando:
                mensal_fechados[quando.month - 1] += 1
            desperdicio = _valor(
                orcamento, "percentual_desperdicio",
                "desperdicio_percentual", "desperdicio",
            )
            if desperdicio is not None:
                valores_desperdicio.append(_numero(desperdicio))
            else:
                capacidade_total = 0
                unidades_nao_utilizadas = 0
                for item in orcamento.get("itens", []):
                    aproveitamento = _numero(item.get("aproveitamento"))
                    folhas = _numero(item.get("qtde_folhas"))
                    quantidade = _numero(item.get("quantidade"))
                    capacidade = aproveitamento * folhas
                    if capacidade > 0:
                        capacidade_total += capacidade
                        unidades_nao_utilizadas += max(0, capacidade - quantidade)
                if capacidade_total:
                    valores_desperdicio.append(
                        100 * unidades_nao_utilizadas / capacidade_total
                    )
        elif situacao == "negociacao":
            total_negociacao += 1
            valor_potencial += valor
            if quando:
                mensal_negociacao[quando.month - 1] += 1

        uf = _sigla_estado(_valor(orcamento, "uf", "estado", "regiao"))
        if uf:
            agregado = por_regiao[uf]
            agregado["orcamentos"] += 1
            agregado["valor"] += valor

    produtos_por_id = {str(produto["_id"]): produto for produto in produtos}
    por_produto = defaultdict(int)
    itens_dashboard = list(itens)
    for orcamento in orcamentos:
        for item in orcamento.get("itens", []):
            itens_dashboard.append({
                **item,
                "orcamentoId": str(orcamento.get("_id", "")),
                "categoria": item.get("categoria") or orcamento.get("categoria"),
            })
    for item in itens_dashboard:
        nome = _nome_produto(item, produtos_por_id)
        quantidade = item.get("quantidade")
        quantidade = int(_numero(quantidade)) if quantidade is not None else 1
        por_produto[nome] += quantidade
        categoria = item.get("categoria")
        if not categoria:
            orcamento = orcamentos_por_id.get(str(item.get("orcamentoId")))
            categoria_orcamento = _valor(orcamento or {}, "categoria")
            categoria = categoria_orcamento or item.get("produto")
        if categoria:
            por_categoria[str(categoria)] += quantidade

    return jsonify({
        "indicadores": {
            "orcamentos_fechados": total_fechados,
            "media_desperdicio": (
                sum(valores_desperdicio) / len(valores_desperdicio)
                if valores_desperdicio else None
            ),
            "pedidos_negociacao": total_negociacao,
            "valor_negociacao": round(valor_potencial, 2),
        },
        "mensal": {
            "fechados": mensal_fechados,
            "negociacao": mensal_negociacao,
        },
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
