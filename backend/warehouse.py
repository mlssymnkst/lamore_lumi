"""Conexão e consultas ao data warehouse PostgreSQL."""
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

load_dotenv(Path(__file__).with_name(".env"))


class WarehouseNotConfigured(RuntimeError):
    """Raised when the PostgreSQL connection string is missing."""


def conectar():
    url = os.getenv("DATABASE_URL") or os.getenv("NEON_DATABASE_URL")
    if not url:
        raise WarehouseNotConfigured(
            "Configure DATABASE_URL no backend/.env para conectar ao PostgreSQL."
        )
    return psycopg2.connect(url, connect_timeout=8, sslmode="require")


def consultar(sql, parametros=None):
    """Executa uma consulta somente de leitura e retorna linhas como dicionários."""
    conexao = conectar()
    try:
        with conexao.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, parametros or ())
            return [dict(linha) for linha in cursor.fetchall()]
    finally:
        conexao.close()
