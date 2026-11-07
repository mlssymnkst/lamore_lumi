import unittest
import csv
import io
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

from flask import Flask

from backend import avaliacoes_routes, dashboard_routes, faturamento_routes
from backend.importar_dataset import CAMPOS, carregar_csv, converter_linha


class WarehouseImportTests(unittest.TestCase):
    def test_carregar_csv_remove_bom_sem_corromper_texto_cp1252(self):
        conteudo = io.StringIO()
        escritor = csv.DictWriter(conteudo, fieldnames=CAMPOS)
        escritor.writeheader()
        escritor.writerow({
            "num_pedido": "PED000001",
            "nome_produto": "Convite Premium + Lenço",
            "categoria": "Convites + Complementos",
            "nota": "Não Avaliado",
        })
        dados = conteudo.getvalue().encode("cp1252").replace(
            "Não Avaliado".encode("cp1252"),
            "Não Avaliado".encode("utf-8"),
        )

        with tempfile.TemporaryDirectory() as diretorio:
            caminho = Path(diretorio) / "dataset.csv"
            caminho.write_bytes(b"\xef\xbb\xbf" + dados)

            registros = carregar_csv(caminho)

        self.assertEqual(len(registros), 1)
        self.assertEqual(registros[0]["num_pedido"], "PED000001")
        self.assertEqual(registros[0]["nome_produto"], "Convite Premium + Lenço")
        self.assertEqual(registros[0]["categoria"], "Convites + Complementos")
        self.assertIsNone(registros[0]["nota"])

    def test_converter_importa_apenas_campos_analiticos(self):
        linha = {
            "num_pedido": "PED000001",
            "uf": "SP",
            "categoria": "Convites",
            "nota": "Não Avaliado",
            "data_pedido": "2021-01-02",
            "unidades": "19",
            "nome": "Nome que não deve ser importado",
            "email": "nao-importar@example.com",
            "celular": "11999999999",
            "endereco": "Endereço que não deve ser importado",
        }

        registro = converter_linha(linha)

        self.assertEqual(registro["num_pedido"], "PED000001")
        self.assertEqual(registro["nota"], None)
        self.assertEqual(registro["data_pedido"], date(2021, 1, 2))
        self.assertEqual(registro["unidades"], 19)
        self.assertEqual(set(registro), set(CAMPOS))
        self.assertNotIn("nome", registro)
        self.assertNotIn("email", registro)
        self.assertNotIn("celular", registro)
        self.assertNotIn("endereco", registro)


class WarehouseApiTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.register_blueprint(faturamento_routes.faturamento_bp)
        self.app.register_blueprint(dashboard_routes.dashboard_bp)
        self.app.register_blueprint(avaliacoes_routes.avaliacoes_bp)
        self.client = self.app.test_client()

    @patch.object(faturamento_routes, "consultar")
    def test_faturamento_usa_pedidos_do_warehouse(self, consultar):
        consultar.return_value = [
            {
                "pedido": "PED000001",
                "cliente": "Cliente PED000001",
                "categoria": "Convites",
                "valor": 266.0,
                "data": date(2026, 1, 2),
                "status": "Aprovado",
                "uf": "SP",
                "atrasado": False,
            }
        ]

        resposta = self.client.get("/api/faturamento?ano=2026")

        self.assertEqual(resposta.status_code, 200)
        dados = resposta.get_json()
        self.assertEqual(dados["cards"]["total_pedidos"], 1)
        self.assertEqual(dados["cards"]["faturamento_total"], 266.0)
        self.assertEqual(dados["pedidos"][0]["pedido"], "PED000001")

    @patch.object(dashboard_routes, "consultar")
    def test_dashboard_filtra_todos_os_agregados_pelo_ano(self, consultar):
        consultar.return_value = [
            {
                "status_orcamento": "Aprovado",
                "data_pedido": date(2026, 1, 2),
                "valor_orcado": 188.55,
                "valor_total_pedido": 266.0,
                "uf": "PR",
                "nome_produto": "Convite Premium",
                "categoria": "Convites",
                "unidades": 19,
            },
            {
                "status_orcamento": "Em negociação",
                "data_pedido": date(2026, 2, 2),
                "valor_orcado": 100.0,
                "valor_total_pedido": 120.0,
                "uf": "SP",
                "nome_produto": "Lenço",
                "categoria": "Complementos",
                "unidades": 2,
            },
            {
                "status_orcamento": "Aprovado",
                "data_pedido": date(2025, 1, 2),
                "valor_orcado": 88.0,
                "valor_total_pedido": 100.0,
                "uf": "SP",
                "nome_produto": "Lenço",
                "categoria": "Complementos",
                "unidades": 1,
            },
        ]

        resposta = self.client.get("/api/dashboard?ano=2026")

        self.assertEqual(resposta.status_code, 200)
        dados = resposta.get_json()
        consultar.assert_called_once()
        self.assertIn("WHERE data_pedido >= %s AND data_pedido < %s", consultar.call_args.args[0])
        self.assertEqual(consultar.call_args.args[1], (date(2026, 1, 1), date(2027, 1, 1)))
        self.assertEqual(dados["indicadores"]["orcamentos_fechados"], 1)
        self.assertEqual(dados["indicadores"]["pedidos_negociacao"], 1)
        self.assertEqual(dados["indicadores"]["media_desperdicio"], 5.2)
        serie = {item["periodo"]: item for item in dados["mensal"]}
        self.assertEqual(len(serie), 2)
        self.assertEqual(serie["2026-01"]["fechados"], 1)
        self.assertEqual(serie["2026-02"]["negociacao"], 1)
        self.assertEqual(dados["produtos"][0]["nome"], "Convite Premium")
        self.assertEqual([produto["nome"] for produto in dados["produtos"]], ["Convite Premium", "Lenço"])
        self.assertEqual([categoria["nome"] for categoria in dados["categorias"]], ["Convites", "Complementos"])
        self.assertEqual(
            {regiao["nome"] for regiao in dados["regioes"]},
            {"PR", "SP"},
        )

    @patch.object(dashboard_routes, "consultar")
    def test_dashboard_rejeita_ano_fora_do_intervalo(self, consultar):
        resposta = self.client.get("/api/dashboard?ano=2020")

        self.assertEqual(resposta.status_code, 400)
        consultar.assert_not_called()

    @patch.object(dashboard_routes, "consultar", return_value=[])
    def test_dashboard_retorna_media_desperdicio_por_ano(self, consultar):
        percentuais = {
            2021: 4.8,
            2022: 5.3,
            2023: 5.7,
            2024: 10.0,
            2025: 6.3,
            2026: 5.2,
        }

        for ano, percentual in percentuais.items():
            with self.subTest(ano=ano):
                resposta = self.client.get(f"/api/dashboard?ano={ano}")

                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(
                    resposta.get_json()["indicadores"]["media_desperdicio"],
                    percentual,
                )

        self.assertEqual(consultar.call_count, len(percentuais))

    @patch.object(avaliacoes_routes, "consultar")
    @patch.object(avaliacoes_routes.avaliacoes_collection, "find")
    def test_avaliacoes_combina_historico_sem_dados_pessoais(self, encontrar, consultar):
        cursor = Mock()
        cursor.sort.return_value = []
        encontrar.return_value = cursor
        consultar.return_value = [
            {
                "num_pedido": "PED000002",
                "categoria": "Convites",
                "uf": "SP",
                "nota": 4,
                "data_avaliacao": None,
                "data_entrega": date(2021, 1, 15),
                "data_pedido": date(2021, 1, 2),
            }
        ]

        historico = avaliacoes_routes.carregar_avaliacoes()[0]

        self.assertEqual(historico["origem"], "historico")
        self.assertEqual(historico["nota"], 4)
        self.assertEqual(historico["data"], "2021-01-15")
        self.assertEqual(historico["cliente"], "Cliente PED000002")
        self.assertNotIn("email", historico)
        self.assertNotIn("celular", historico)


if __name__ == "__main__":
    unittest.main()
