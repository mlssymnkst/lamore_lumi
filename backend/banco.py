import os
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).with_name(".env"))

client = MongoClient(
    os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
)
db = client["SOA"]

clientes_collection = db["clientes"]
produtos_collection = db["produtos"]
insumos_collection = db["insumos"]
orcamentos_collection = db["orcamentos"]
tipos_produto_collection = db["tipos_produto"]
itens_orcamento_collection = db["itens_orcamento"]
modelos_personalizados_collection = db["modelos_personalizados"]
avaliacoes_collection = db["avaliacoes"]
convites_avaliacao_collection = db["convites_avaliacao"]
