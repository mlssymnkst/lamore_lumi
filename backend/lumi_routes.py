import json
from pathlib import Path

from flask import Blueprint, jsonify, current_app

lumi_bp = Blueprint("lumi", __name__)

SNAPSHOT = (
    Path(__file__).resolve().parents[1]
    / "faturamento"
    / "lumi_snapshot.json"
)


@lumi_bp.get("/api/lumi/previsoes")
def api_lumi_previsoes():

    if not SNAPSHOT.is_file():
        return jsonify({
            "erro": "Previsão não gerada."
        }), 503

    try:
        with SNAPSHOT.open("r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)

        return jsonify(dados)

    except (OSError, ValueError):
        current_app.logger.exception(
            "Erro ao carregar previsão LUMI."
        )

        return jsonify({
            "erro": "Não foi possível carregar a previsão."
        }), 503