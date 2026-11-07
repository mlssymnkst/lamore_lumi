import os
import unittest
from datetime import datetime, timedelta, timezone
from io import BytesIO
from unittest.mock import Mock, patch

from bson import ObjectId
from flask import Flask

from backend import avaliacoes_routes as routes


class Cursor(list):
    def sort(self, field, direction):
        return Cursor(sorted(self, key=lambda item: item.get(field), reverse=direction < 0))


class MemoryCollection:
    def __init__(self):
        self.documents = []

    @staticmethod
    def _matches(document, query):
        for field, expected in query.items():
            actual = document.get(field)
            if isinstance(expected, dict) and "$gt" in expected:
                if actual is None or actual <= expected["$gt"]:
                    return False
            elif actual != expected:
                return False
        return True

    def create_index(self, *_args, **_kwargs):
        return None

    def find_one(self, query):
        return next(
            (doc for doc in self.documents if self._matches(doc, query)),
            None,
        )

    def find(self, query=None):
        query = query or {}
        return Cursor(
            doc for doc in self.documents if self._matches(doc, query)
        )

    def insert_one(self, document):
        document.setdefault("_id", ObjectId())
        self.documents.append(document)
        return type("InsertResult", (), {"inserted_id": document["_id"]})()

    def update_one(self, query, update):
        document = self.find_one(query)
        if not document:
            return type("UpdateResult", (), {"matched_count": 0, "modified_count": 0})()
        changed = any(document.get(key) != value for key, value in update["$set"].items())
        document.update(update["$set"])
        return type(
            "UpdateResult",
            (),
            {"matched_count": 1, "modified_count": int(changed)},
        )()

    def delete_one(self, query):
        document = self.find_one(query)
        if document:
            self.documents.remove(document)
        return type("DeleteResult", (), {"deleted_count": int(document is not None)})()


class MemoryPhotos:
    def __init__(self):
        self.files = {}

    def upload_from_stream(self, filename, content, metadata=None):
        file_id = ObjectId()
        self.files[file_id] = (filename, content, metadata)
        return file_id

    def delete(self, file_id):
        self.files.pop(file_id, None)


class AvaliacoesRoutesTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.register_blueprint(routes.avaliacoes_bp)
        self.client = self.app.test_client()
        self.convites = MemoryCollection()
        self.avaliacoes = MemoryCollection()
        self.fotos = MemoryPhotos()
        self.originals = {
            "convites_avaliacao_collection": routes.convites_avaliacao_collection,
            "avaliacoes_collection": routes.avaliacoes_collection,
            "bucket": routes.BUCKET_FOTOS,
        }
        routes.convites_avaliacao_collection = self.convites
        routes.avaliacoes_collection = self.avaliacoes
        routes.BUCKET_FOTOS = self.fotos

    def tearDown(self):
        routes.convites_avaliacao_collection = self.originals["convites_avaliacao_collection"]
        routes.avaliacoes_collection = self.originals["avaliacoes_collection"]
        routes.BUCKET_FOTOS = self.originals["bucket"]

    @classmethod
    def tearDownClass(cls):
        routes.db.client.close()
        super().tearDownClass()

    def _convite(self, token="token-de-teste", usado=False):
        convite = {
            "_id": ObjectId(),
            "pedidoId": "pedido-123",
            "numero_pedido": "84712",
            "cliente": "Ana",
            "produto": "Convite personalizado",
            "categoria": "Convites",
            "uf": "SP",
            "token_hash": routes._hash_token(token),
            "criado_em": datetime.now(timezone.utc),
            "expira_em": datetime.now(timezone.utc) + timedelta(days=1),
            "usado": usado,
        }
        self.convites.insert_one(convite)
        return convite

    def test_invitation_endpoint_is_protected(self):
        with patch.dict(os.environ, {"AVALIACOES_WEBHOOK_TOKEN": "segredo"}):
            response = self.client.post(
                "/api/avaliacoes/convites",
                json={
                    "pedidoId": "pedido-123",
                    "statusEntrega": "entregue",
                },
            )
        self.assertEqual(response.status_code, 401)

    def test_invitation_requires_delivery_confirmation(self):
        environment = {
            "AVALIACOES_WEBHOOK_TOKEN": "segredo",
            "SMTP_HOST": "smtp.example.test",
            "SMTP_FROM": "loja@example.test",
            "PUBLIC_BASE_URL": "https://lumi.example.test",
        }
        with (
            patch.dict(os.environ, environment),
            patch.object(routes, "_dados_pedido") as get_order,
            patch.object(routes, "_enviar_email") as send_email,
        ):
            for payload in (
                {"pedidoId": "pedido-123"},
                {"pedidoId": "pedido-123", "statusEntrega": "em_transporte"},
                {"pedidoId": "pedido-123", "statusEntrega": "orcamento_aprovado"},
            ):
                with self.subTest(payload=payload):
                    response = self.client.post(
                        "/api/avaliacoes/convites",
                        headers={"X-Webhook-Token": "segredo"},
                        json=payload,
                    )
                    self.assertEqual(response.status_code, 409)

        get_order.assert_not_called()
        send_email.assert_not_called()

    def test_customer_form_and_script_are_served(self):
        page = self.client.get("/avaliar/token-de-teste")
        script = self.client.get("/avaliacoes/avaliar/avaliar.js")
        stylesheet = self.client.get("/avaliacoes/avaliar/avaliar.css")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Como foi sua experi", page.data)
        self.assertEqual(script.status_code, 200)
        self.assertEqual(stylesheet.status_code, 200)
        page.close()
        script.close()
        stylesheet.close()

    def test_dashboard_avaliacoes_files_are_served_from_its_folder(self):
        page = self.client.get("/dashboard-avaliacoes/")
        shared_script = self.client.get("/avaliacoes/avaliacoes-comum.js")
        script = self.client.get(
            "/avaliacoes/dashboard-avaliacoes/dashboard-avaliacoes.js"
        )
        self.assertEqual(page.status_code, 200)
        self.assertIn(
            b"/avaliacoes/avaliacoes-comum.js",
            page.data,
        )
        self.assertIn(
            b"/avaliacoes/dashboard-avaliacoes/dashboard-avaliacoes.js",
            page.data,
        )
        self.assertEqual(shared_script.status_code, 200)
        self.assertEqual(script.status_code, 200)
        page.close()
        shared_script.close()
        script.close()

    def test_reviews_page_loads_its_shared_script(self):
        page = self.client.get("/avaliacoes")
        script = self.client.get("/avaliacoes/avaliacoes-comum.js")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"/avaliacoes/avaliacoes-comum.js", page.data)
        self.assertEqual(script.status_code, 200)
        page.close()
        script.close()

    def test_customer_form_uses_official_logo(self):
        page = self.client.get("/avaliar/token-de-teste")
        self.assertIn(b'/images/logo%20redondo.png', page.data)
        self.assertIn(b'alt="L\'amore Est\xc3\xbadio"', page.data)
        page.close()

    def test_order_product_falls_back_to_order_number(self):
        pedido_id = ObjectId()
        cliente_id = ObjectId()
        pedido = {"_id": pedido_id, "clienteId": str(cliente_id), "numeroPedido": "84712"}
        cliente = {"_id": cliente_id, "email": "ana@example.test"}
        with (
            patch.object(routes, "orcamentos_collection", Mock(find_one=Mock(return_value=pedido))),
            patch.object(routes, "clientes_collection", Mock(find_one=Mock(return_value=cliente))),
            patch.object(routes, "itens_orcamento_collection", Mock(find=Mock(return_value=[]))),
        ):
            result, error = routes._dados_pedido(str(pedido_id))

        self.assertIsNone(error)
        self.assertEqual(result["produto"], "Pedido #84712")

    def test_order_product_uses_embedded_purchased_items(self):
        pedido_id = ObjectId()
        cliente_id = ObjectId()
        pedido = {
            "_id": pedido_id,
            "clienteId": str(cliente_id),
            "numeroPedido": "84712",
            "itens": [
                {"produto": "Convite Casamento Premium"},
                {"produto": "Envelope Personalizado"},
            ],
        }
        cliente = {"_id": cliente_id, "email": "ana@example.test"}
        with (
            patch.object(routes, "orcamentos_collection", Mock(find_one=Mock(return_value=pedido))),
            patch.object(routes, "clientes_collection", Mock(find_one=Mock(return_value=cliente))),
            patch.object(routes, "itens_orcamento_collection", Mock(find=Mock(return_value=[]))),
        ):
            result, error = routes._dados_pedido(str(pedido_id))

        self.assertIsNone(error)
        self.assertEqual(
            result["produto"],
            "Convite Casamento Premium, Envelope Personalizado",
        )

    def test_existing_invitation_replaces_category_with_order_number(self):
        convite = self._convite()
        convite["produto"] = convite["categoria"]

        response = self.client.get("/api/avaliacoes/convites/token-de-teste")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["produto"], "Pedido #84712")

    def test_existing_generic_invitation_loads_real_purchased_product(self):
        convite = self._convite()
        convite["produto"] = convite["categoria"] = "Produto"
        pedido = {"produto": "Convite Casamento Premium"}
        with patch.object(routes, "_dados_pedido", return_value=(pedido, None)):
            response = self.client.get("/api/avaliacoes/convites/token-de-teste")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["produto"], "Convite Casamento Premium")

    def test_delivered_order_sends_one_time_email_invitation(self):
        environment = {
            "AVALIACOES_WEBHOOK_TOKEN": "segredo",
            "SMTP_HOST": "smtp.example.test",
            "SMTP_FROM": "loja@example.test",
            "PUBLIC_BASE_URL": "https://lumi.example.test",
        }
        pedido = {
            "pedidoId": "pedido-123",
            "numero_pedido": "84712",
            "cliente": "Ana",
            "email": "ana@example.test",
            "produto": "Convite personalizado",
            "categoria": "Convites",
            "uf": "SP",
        }
        with (
            patch.dict(os.environ, environment),
            patch.object(routes, "_dados_pedido", return_value=(pedido, None)),
            patch.object(routes, "_enviar_email") as send_email,
        ):
            response = self.client.post(
                "/api/avaliacoes/convites",
                headers={"X-Webhook-Token": "segredo"},
                json={
                    "pedidoId": "pedido-123",
                    "statusEntrega": "entregue",
                },
            )

        self.assertEqual(response.status_code, 201)
        send_email.assert_called_once()
        link = next(
            line for line in send_email.call_args.args[2].splitlines()
            if line.startswith("https://lumi.example.test/avaliar/")
        )
        self.assertTrue(link.startswith("https://lumi.example.test/avaliar/"))
        token = link.rsplit("/", 1)[1]
        self.assertEqual(
            self.client.get(f"/api/avaliacoes/convites/{token}").status_code,
            200,
        )

    def test_five_star_review_is_saved_and_appears_in_admin_api(self):
        self._convite()
        response = self.client.post(
            "/api/avaliacoes/convites/token-de-teste/avaliar",
            data={"nota": "5", "comentario": "Ficou lindo!", "uf": "SP"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.avaliacoes.documents[0]["nota"], 5)
        self.assertEqual(self.avaliacoes.documents[0]["comentario"], "Ficou lindo!")
        self.assertEqual(self.avaliacoes.documents[0]["uf"], "SP")
        self.assertEqual(self.convites.documents[0]["usado"], True)

        with patch.object(routes, "consultar", return_value=[]):
            admin_response = self.client.get("/api/avaliacoes")
        self.assertEqual(admin_response.status_code, 200)
        self.assertEqual(admin_response.json[0]["id"], "84712")
        self.assertEqual(admin_response.json[0]["cliente"], "Ana")

    def test_low_rating_requires_comment_and_photo_and_stores_photo(self):
        self._convite()
        missing_state = self.client.post(
            "/api/avaliacoes/convites/token-de-teste/avaliar",
            data={"nota": "4", "comentario": "Chegou danificado."},
        )
        self.assertEqual(missing_state.status_code, 400)
        self.assertIn("estado", missing_state.json["erro"])

        missing_comment = self.client.post(
            "/api/avaliacoes/convites/token-de-teste/avaliar",
            data={"nota": "4", "uf": "SP"},
        )
        self.assertEqual(missing_comment.status_code, 400)
        self.assertIn("Descreva", missing_comment.json["erro"])

        missing_photo = self.client.post(
            "/api/avaliacoes/convites/token-de-teste/avaliar",
            data={"nota": "4", "comentario": "Chegou danificado.", "uf": "SP"},
        )
        self.assertEqual(missing_photo.status_code, 400)
        self.assertFalse(self.convites.documents[0]["usado"])

        saved = self.client.post(
            "/api/avaliacoes/convites/token-de-teste/avaliar",
            data={
                "nota": "4",
                "comentario": "Chegou danificado.",
                "uf": "SP",
                "problemas": ["Danificado"],
                "foto": (BytesIO(b"\x89PNG\r\n\x1a\nconteudo"), "problema.png", "image/png"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(saved.status_code, 201)
        self.assertEqual(self.avaliacoes.documents[0]["problemas"], ["Danificado"])
        self.assertEqual(len(self.avaliacoes.documents[0]["fotos"]), 1)
        self.assertEqual(len(self.fotos.files), 1)

    def test_failed_email_removes_unsent_invitation(self):
        environment = {
            "AVALIACOES_WEBHOOK_TOKEN": "segredo",
            "SMTP_HOST": "smtp.example.test",
            "SMTP_FROM": "loja@example.test",
            "PUBLIC_BASE_URL": "https://lumi.example.test",
        }
        pedido = {
            "pedidoId": "pedido-123",
            "numero_pedido": "84712",
            "cliente": "Ana",
            "email": "ana@example.test",
            "produto": "Convite personalizado",
            "categoria": "Convites",
            "uf": "SP",
        }
        with (
            patch.dict(os.environ, environment),
            patch.object(routes, "_dados_pedido", return_value=(pedido, None)),
            patch.object(routes, "_enviar_email", side_effect=OSError("SMTP indisponível")),
        ):
            with self.assertLogs(self.app.logger, level="ERROR"):
                response = self.client.post(
                    "/api/avaliacoes/convites",
                    headers={"X-Webhook-Token": "segredo"},
                    json={
                        "pedidoId": "pedido-123",
                        "statusEntrega": "entregue",
                    },
                )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(self.convites.documents, [])

    def test_used_invitation_cannot_submit_twice(self):
        self._convite(usado=True)
        response = self.client.post(
            "/api/avaliacoes/convites/token-de-teste/avaliar",
            data={"nota": "5"},
        )
        self.assertEqual(response.status_code, 409)


if __name__ == "__main__":
    unittest.main()
