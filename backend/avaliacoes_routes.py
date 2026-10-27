"""Telas de Avaliações (Flask): páginas HTML + API JSON.

Rotas:
    GET   /avaliacoes                  -> Controle de Reclamações
    GET   /dashboard-avaliacoes        -> Dashboard de Avaliações
    GET   /avaliacoes/<css|js>         -> arquivos das páginas
    GET   /api/avaliacoes              -> lista de avaliações
    PATCH /api/avaliacoes/<id>         -> atualiza o acompanhamento da reclamação

Mesmo padrão do faturamento_routes.py: dados fictícios em memória, e UM ponto
de troca (carregar_avaliacoes / salvar_acompanhamento) para ligar ao banco real.
"""
import os
import random
from datetime import date, timedelta

from flask import Blueprint, abort, jsonify, request, send_from_directory

avaliacoes_bp = Blueprint("avaliacoes", __name__)

PASTA_PAGINA = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "avaliacoes"))
ARQUIVOS_PUBLICOS = {"avaliacoes.css", "avaliacoes-comum.js",
                     "avaliacoes.js", "dashboard-avaliacoes.js"}
CAMPOS_EDITAVEIS = {"atendeu", "respondeu", "resolvido", "motivo", "resolucao"}


# ---------------------------------------------------------------------------
# DADOS (fictícios). Para usar dados reais, troque SOMENTE as duas funções
# abaixo. Cada avaliação é um dict com as chaves:
#   id, cliente, categoria, uf, nota (1-5), comentario, data ("AAAA-MM-DD"),
#   atendeu, respondeu, resolvido (True/False/None), motivo, resolucao
# ---------------------------------------------------------------------------
def _gerar_avaliacoes_ficticias(qtd=80, semente=7):
    rng = random.Random(semente)
    categorias = ["Convites", "Save the date", "Cardápios", "Marcadores de mesa",
                  "Tags e lacres", "Caixas personalizadas", "Papelaria de cerimônia"]
    ufs = ["SP", "SP", "SP", "RJ", "RJ", "MG", "MG", "PR", "RS", "SC", "BA", "PE", "GO", "DF"]
    positivos = ["Adorei! Qualidade excelente.", "Atendimento muito atencioso.",
                 "Tudo impecável, recomendo!", "Ficou lindo, entrega rápida.",
                 "Bom custo-benefício."]
    negativos = ["Produto chegou danificado.", "Entrega atrasou alguns dias.",
                 "Quantidade errada no pedido.", "A cor ficou diferente do combinado.",
                 "Não consegui retorno do atendimento."]
    motivos = ["Cliente não aceitou a resolução", "Cliente não respondeu"]
    resolucoes = ["Mandar produto faltante", "Desconto no pagamento",
                  "Devolução de pagamento", "Contato com transportadora",
                  "Reenvio do pedido", "Outro"]
    lista = []
    for i in range(qtd):
        nota = rng.choices([1, 2, 3, 4, 5], weights=[8, 10, 12, 25, 45])[0]
        a = {"id": 84000 + i, "cliente": f"Cliente {i + 1}",
             "categoria": rng.choice(categorias), "uf": rng.choice(ufs), "nota": nota,
             "comentario": rng.choice(positivos if nota >= 4 else negativos),
             "data": (date(2026, 1, 1) + timedelta(days=rng.randrange(300))).isoformat(),
             "atendeu": None, "respondeu": None, "resolvido": None,
             "motivo": None, "resolucao": None}
        if nota <= 3 and rng.random() < 0.75:
            a["atendeu"] = rng.random() < 0.85
            if a["atendeu"]:
                a["respondeu"] = rng.choice([True, True, False, None])
                a["resolvido"] = rng.choice([True, False, None])
                if a["resolvido"] is False:
                    a["motivo"] = rng.choice(motivos)
                if a["resolvido"] is not None:
                    a["resolucao"] = rng.choice(resolucoes)
        lista.append(a)
    return lista


_cache = {}

"""
PONTO DE TROCA 1: aqui entra a consulta ao banco com dados reais.
"""
def carregar_avaliacoes():
    if "lista" not in _cache:
        _cache["lista"] = _gerar_avaliacoes_ficticias()
    return _cache["lista"]

"""
PONTO DE TROCA 2: aqui entra o UPDATE no banco. Devolve a avaliação
atualizada, ou None se o id não existir.
"""
def salvar_acompanhamento(id_avaliacao, campos):
    for a in carregar_avaliacoes():
        if a["id"] == id_avaliacao:
            a.update(campos)
            return a
    return None


# ---------------------------------------------------------------------------
# ROTAS
# ---------------------------------------------------------------------------
@avaliacoes_bp.route("/avaliacoes")
def pagina_avaliacoes():
    return send_from_directory(PASTA_PAGINA, "avaliacoes.html")


@avaliacoes_bp.route("/dashboard-avaliacoes")
def pagina_dashboard_avaliacoes():
    return send_from_directory(PASTA_PAGINA, "dashboard-avaliacoes.html")


@avaliacoes_bp.route("/avaliacoes/<path:arquivo>")
def arquivos_avaliacoes(arquivo):
    if arquivo not in ARQUIVOS_PUBLICOS:
        abort(404)
    return send_from_directory(PASTA_PAGINA, arquivo)


@avaliacoes_bp.route("/api/avaliacoes")
def api_avaliacoes():
    return jsonify(carregar_avaliacoes())


@avaliacoes_bp.route("/api/avaliacoes/<int:id_avaliacao>", methods=["PATCH"])
def api_atualizar_avaliacao(id_avaliacao):
    dados = request.get_json(silent=True) or {}
    campos = {k: v for k, v in dados.items() if k in CAMPOS_EDITAVEIS}
    if not campos:
        return jsonify({"erro": "Nenhum campo válido para atualizar."}), 400
    atualizada = salvar_acompanhamento(id_avaliacao, campos)
    if atualizada is None:
        return jsonify({"erro": "Avaliação não encontrada."}), 404
    return jsonify(atualizada)
