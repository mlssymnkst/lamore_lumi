from flask import Flask
from flask_cors import CORS
from routes import insumos_bp, orcamentos_bp
from bot_routes import bot_bp 
from routes.clientes import clientes_bp
from routes.produtos import produtos_bp
from routes.tipos_produto import tipos_produto_bp
from routes.itens_orcamento import itens_orcamento_bp
from routes.modelos_personalizados import modelos_personalizados_bp
from dashboard_routes import dashboard_bp

app = Flask(__name__)
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

@app.route("/")
def home():
    return {"msg": "API rodando com sucesso"}


if __name__ == "__main__":
    app.run(debug=True)