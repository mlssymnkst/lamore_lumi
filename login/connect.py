#arrrumar o nome do usuario, conexões entre a tela e banconosql

from flask import Flask, request, redirect, send_from_directory, session, jsonify
from pymongo import MongoClient
from bson import ObjectId
import psycopg2, os
import sys
from flask_cors import CORS

#da linha 6 ate a 23 são ccomandos para rodar o bot, Faturamento e dashboard

app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

sys.path.append(BASE_DIR)

from backend.bot_routes import bot_bp
app.secret_key = 'segredo123'
app.register_blueprint(bot_bp)

from backend.faturamento_routes import faturamento_bp
app.register_blueprint(faturamento_bp)

from backend.dashboard_routes import dashboard_bp
app.register_blueprint(dashboard_bp)

# conexão com PostgreSQL
conn = psycopg2.connect(
    "postgresql://neondb_owner:npg_i7CL3QSUDstA@ep-lively-field-aqff4e2r-pooler.c-8.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"#senha do seu postgree 1234
)

# conexão com o mongodb
# conexão MongoDB
mongo_client = MongoClient("mongodb://localhost:27017/")

mongo_db = mongo_client["SOA"]

colecao_insumos = mongo_db["insumos"]


@app.route('/')
def login_page():
    base = os.path.dirname(os.path.abspath(__file__))
    caminho = os.path.join(base, '..', 'login')
    return send_from_directory(caminho, 'html_login.html') # TROCAR O "."

#INSUMOS
@app.route('/insumos')
def insumos():
    base = os.path.dirname(os.path.abspath(__file__))
    caminho = os.path.join(base, '..', 'insumos')

    usuario = session.get('usuario')

    admins = ["haruka", "marly", "admin"]

    if usuario and usuario.lower() in admins:
        role = "admin"
    else:
        role = "user"

    html = open(os.path.join(caminho, 'insumos.html'), encoding='utf-8').read()

    html = html.replace('Usuário 1', usuario if usuario else 'Visitante')

    # INJETA ROLE ANTES DO JS (para puxar o nome do usuario)
    html = html.replace(
        '<script src="/insumos/insumos.js"></script>',
        f"""
        <script>
            const USER_ROLE = "{role}";
        </script>
        <script src="/insumos/insumos.js"></script>
        """
    )

    return html




#CSS
@app.route('/login/<path:arquivo>')
def arquivos_login(arquivo):
    base = os.path.dirname(os.path.abspath(__file__))
    caminho = os.path.join(base, '..', 'login')
    return send_from_directory(caminho, arquivo)

# css bot 
@app.route('/bot/static/<path:arquivo>') #arrumando o endereço da paginas
def arquivos_bot(arquivo):
    caminho = os.path.join(BASE_DIR, 'bot') #arrumando caminho para achar o arquivo
    return send_from_directory(caminho, arquivo)

#imagem 
@app.route('/images/<path:arquivo>')
def imagens(arquivo):
    base = os.path.dirname(os.path.abspath(__file__))
    caminho = os.path.join(base, '..', 'images')
    return send_from_directory(caminho, arquivo)

#chatbot
@app.route('/chatbot')
def chatbot():
    return send_from_directory(
        os.path.join(BASE_DIR, 'bot'), #CAMINHO PARA ACHAR O BOT
        'chatbot.html'
    )


#para aparecer o nome em insumos
@app.route('/login_session', methods=['POST'])
def login_session():
    from flask import session

    usuario = request.form['login']
    senha = request.form['senha']

    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM entrada WHERE usuario = %s AND senha = %s",
        (usuario, senha)
    )
    result = cursor.fetchone()

    if result:
        session['usuario'] = usuario  #  AQUI salva 
        return redirect('/insumos')
    else:
        return "Login inválido"




#css insumos
@app.route('/insumos/<path:arquivo>')
def arquivos_insumos(arquivo):
    base = os.path.dirname(os.path.abspath(__file__))
    caminho = os.path.join(base, '..', 'insumos')
    return send_from_directory(caminho, arquivo)

#adicionar produto
@app.route('/api/adicionar_insumo', methods=['POST'])
def adicionar_insumo():

    if not usuario_admin():
        return jsonify({
            "erro": "Sem permissão"
        }), 403

    dados = request.json

    # ID visual para não puxar do mongodb
    ultimo = colecao_insumos.count_documents({}) + 1

    novo_produto = {

        "id_visual": ultimo,

        "modelo": dados.get("nome"),

        "estoque_disponivel": int(dados.get("qtd")),

        "preco_venda": float(dados.get("valor")),

        # CAMPOS EXTRAS que não aparece no forms
        "modelo_detalhado": dados.get("modelo"),

        "peso": dados.get("peso"),

        "altura": dados.get("altura"),

        "largura": dados.get("largura"),

        "unidade_medida": dados.get("unidade_medida")
    }

    colecao_insumos.insert_one(novo_produto)

    return jsonify({
        "mensagem": "Produto adicionado com sucesso!"
    })

#mongodb dos produtos da tela de insumos
@app.route('/api/insumos')
def api_insumos():

    produtos = []

    contador = 1

    for item in colecao_insumos.find():

        # cria id_visual automaticamente se não existir
        if "id_visual" not in item:

            colecao_insumos.update_one(
                {"_id": item["_id"]},
                {
                    "$set": {
                        "id_visual": contador
                    }
                }
            )

            item["id_visual"] = contador

        produtos.append({

            "id": str(item["_id"]),

            "id_visual": item.get("id_visual"),

            "nome": item.get("modelo"),

            "qtd": item.get("estoque_disponivel"),

            "valor": item.get("preco_venda")
        })

        contador += 1

    return jsonify(produtos)



#RESTRIÇÃO DE PRODUTOS
def usuario_admin():

    usuario = session.get('usuario')

    admins = ["haruka", "marly", "admin"]

    return usuario and usuario.lower() in admins

#excluir produto com restrição

@app.route('/api/excluir_insumo/<id>', methods=['DELETE'])
def excluir_insumo(id):

    if not usuario_admin():
        return jsonify({
            "erro": "Sem permissão"
        }), 403

    colecao_insumos.delete_one({
        "_id": ObjectId(id)
    })

    return jsonify({
        "mensagem": "Produto excluído!"
    })


    #editar insumos
@app.route('/api/editar_insumos', methods=['POST'])
def editar_insumos():

    if not usuario_admin():
        return jsonify({
            "erro": "Sem permissão"
        }), 403

    dados = request.json

    for produto in dados:

        colecao_insumos.update_one(
            {
                "_id": ObjectId(produto["id"])
            },
            {
                "$set": {
                    "modelo": produto["nome"],
                    "estoque_disponivel": produto["qtd"],
                    "preco_venda": produto["valor"]
                }
            }
        )

    return jsonify({
        "mensagem": "Produtos atualizados!"
    })


# MUDAR A PORTA DO CONNECT PARA NAO DAR ERRO DO LOCALHOST

if __name__ == "__main__":
    app.run()