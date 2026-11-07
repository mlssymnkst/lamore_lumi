"""Importa a base analítica CSV para a tabela pedidos_historicos do PostgreSQL."""
import argparse
import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from backend.warehouse import conectar

PASTA_PROJETO = Path(__file__).resolve().parents[1]
ARQUIVO_PADRAO = PASTA_PROJETO / "dataset_lamore.csv"

CAMPOS_TEXTO = (
    "num_pedido", "uf", "regiao", "nome_produto", "categoria",
    "conclusao", "recomendacao", "problema", "situacao_aval",
    "tipo_pagamento", "transportadora", "servico_frete", "status_orcamento",
)
CAMPOS_INTEIROS = (
    "prazo_estimado_dias", "unidades", "dias_para_entrega", "dias_atraso_frete",
)
CAMPOS_DECIMAIS = (
    "valor_orcado", "valor_unit", "valor_total_pedido", "valor_frete", "nota",
)
CAMPOS_DATAS = (
    "data_pedido", "data_previsao", "data_entrega", "data_casamento",
    "data_avaliacao", "data_retorno",
)
CAMPOS = CAMPOS_TEXTO + CAMPOS_INTEIROS + CAMPOS_DECIMAIS + CAMPOS_DATAS
SENTINELAS = {"", "não avaliado", "nao avaliado", "n/a", "null"}

DEFINICOES = {
    **{campo: "TEXT" for campo in CAMPOS_TEXTO},
    **{campo: "INTEGER" for campo in CAMPOS_INTEIROS},
    **{campo: "NUMERIC(14, 2)" for campo in CAMPOS_DECIMAIS},
    **{campo: "DATE" for campo in CAMPOS_DATAS},
}


def _vazio(valor):
    return str(valor or "").strip().casefold() in SENTINELAS


def _normalizar_texto(valor):
    try:
        return valor.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return valor


def _converter_valor(campo, valor):
    if isinstance(valor, str):
        valor = _normalizar_texto(valor)
    if _vazio(valor):
        return None
    valor = str(valor).strip()
    if campo in CAMPOS_INTEIROS:
        return int(Decimal(valor))
    if campo in CAMPOS_DECIMAIS:
        try:
            return Decimal(valor)
        except InvalidOperation as exc:
            raise ValueError(f"Valor numérico inválido no campo {campo}: {valor}") from exc
    if campo in CAMPOS_DATAS:
        return date.fromisoformat(valor[:10])
    return valor


def converter_linha(linha):
    """Seleciona campos analíticos e descarta nome, e-mail, telefone e endereço."""
    registro = {campo: _converter_valor(campo, linha.get(campo)) for campo in CAMPOS}
    if not registro["num_pedido"]:
        raise ValueError("A linha do CSV não contém num_pedido.")
    return registro


def carregar_csv(caminho):
    with Path(caminho).open("r", encoding="cp1252", newline="") as arquivo:
        leitor = csv.DictReader(arquivo)
        leitor.fieldnames = [
            _normalizar_texto(campo).removeprefix("\ufeff")
            for campo in leitor.fieldnames or []
        ]
        ausentes = set(CAMPOS) - set(leitor.fieldnames or [])
        if ausentes:
            raise ValueError(
                "O CSV não contém as colunas obrigatórias: "
                + ", ".join(sorted(ausentes))
            )
        return [converter_linha(linha) for linha in leitor]


def importar(caminho=ARQUIVO_PADRAO):
    registros = carregar_csv(caminho)
    colunas = ", ".join(CAMPOS)
    placeholders = ", ".join(["%s"] * len(CAMPOS))
    atualizacoes = ", ".join(
        f"{campo} = EXCLUDED.{campo}" for campo in CAMPOS if campo != "num_pedido"
    )
    comando = (
        f"INSERT INTO pedidos_historicos ({colunas}) VALUES ({placeholders}) "
        f"ON CONFLICT (num_pedido) DO UPDATE SET {atualizacoes}"
    )
    conexao = conectar()
    try:
        with conexao:
            with conexao.cursor() as cursor:
                cursor.execute(
                    "CREATE TABLE IF NOT EXISTS pedidos_historicos ("
                    + ", ".join(
                        f"{campo} {DEFINICOES[campo]}"
                        + (" PRIMARY KEY" if campo == "num_pedido" else "")
                        for campo in CAMPOS
                    )
                    + ")"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_pedidos_historicos_data "
                    "ON pedidos_historicos (data_pedido)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_pedidos_historicos_uf "
                    "ON pedidos_historicos (uf)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_pedidos_historicos_nota "
                    "ON pedidos_historicos (nota)"
                )
                cursor.executemany(
                    comando,
                    [tuple(registro[campo] for campo in CAMPOS) for registro in registros],
                )
        return len(registros)
    finally:
        conexao.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=ARQUIVO_PADRAO)
    argumentos = parser.parse_args()
    quantidade = importar(argumentos.csv)
    print(f"{quantidade} pedidos importados/atualizados em pedidos_historicos.")


if __name__ == "__main__":
    main()
