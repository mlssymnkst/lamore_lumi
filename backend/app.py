import os

from dotenv import load_dotenv
from flask import Flask, send_from_directory
from flask_cors import CORS

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from routes import insumos_bp, orcamentos_bp
from bot_routes import bot_bp 
from routes.clientes import clientes_bp
from routes.produtos import produtos_bp
from routes.tipos_produto import tipos_produto_bp
from routes.itens_orcamento import itens_orcamento_bp
from routes.modelos_personalizados import modelos_personalizados_bp
from dashboard_routes import dashboard_bp
from avaliacoes_routes import avaliacoes_bp
from faturamento_routes import faturamento_bp

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024
PASTA_IMAGENS = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "images")
)
CORS(app)

app.register_blueprint(clientes_bp)
app.register_blueprint(insumos_bp)
app.register_blueprint(orcamentos_bp)
app.register_blueprint(bot_bp)       
app.register_blueprint(produtos_bp)
app.register_blueprint(tipos_produto_bp)
app.register_blueprint(itens_orcamento_bp)
app.register_blueprint(modelos_personalizados_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(avaliacoes_bp)
app.register_blueprint(faturamento_bp)


@app.get("/images/<path:arquivo>")
def imagens(arquivo):
    return send_from_directory(PASTA_IMAGENS, arquivo)

@app.route("/")
def home():
    return {"msg": "API rodando com sucesso"}


if __name__ == "__main__":
    app.run(debug=True)