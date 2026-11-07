"""Convites de pós-venda, formulário público e painel de avaliações."""
import hashlib
import hmac
import os
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from bson import ObjectId
from bson.errors import InvalidId
from flask import Blueprint, abort, current_app, jsonify, request, send_file, send_from_directory
from gridfs import GridFSBucket
from gridfs.errors import NoFile
from psycopg2 import Error as PsycopgError
from pymongo.errors import DuplicateKeyError, PyMongoError
from werkzeug.utils import secure_filename

from backend.banco import (
    avaliacoes_collection,
    convites_avaliacao_collection,
    db,
    itens_orcamento_collection,
    orcamentos_collection,
    produtos_collection,
    clientes_collection,
)
from backend.warehouse import WarehouseNotConfigured, consultar

avaliacoes_bp = Blueprint("avaliacoes", __name__)
PASTA_PAGINA = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "avaliacoes")
)
ARQUIVOS_PUBLICOS = {
    "avaliacoes.css",
    "avaliacoes-comum.js",
    "avaliacoes.js",
    "dashboard-avaliacoes/dashboard-avaliacoes.js",
    "avaliar/avaliar.css",
    "avaliar/avaliar.js",
}
CAMPOS_EDITAVEIS = {"atendeu", "respondeu", "resolvido", "motivo", "resolucao"}
TAMANHO_MAXIMO_FOTO = 5 * 1024 * 1024
PROBLEMAS_VALIDOS = {
    "Tempo de resposta",
    "Tom inadequado",
    "Qualidade dos materiais",
    "Quebrado",
    "Rasgado",
    "Danificado",
    "Quantidade incorreta",
    "Tempo de entrega",
    "Estado da embalagem",
}
UFS_VALIDAS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}
BUCKET_FOTOS = GridFSBucket(db, bucket_name="fotos_avaliacoes")


def _agora():
    return datetime.now(timezone.utc)


def _hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _convite_expirado(convite):
    expiracao = convite.get("expira_em")
    if not expiracao:
        return True
    if expiracao.tzinfo is None:
        expiracao = expiracao.replace(tzinfo=timezone.utc)
    return expiracao <= _agora()


def _buscar_convite(token):
    convite = convites_avaliacao_collection.find_one(
        {"token_hash": _hash_token(token)}
    )
    if not convite:
        return None, (jsonify({"erro": "Convite inválido."}), 404)
    if convite.get("usado"):
        return None, (jsonify({"erro": "Este pedido já foi avaliado."}), 409)
    if _convite_expirado(convite):
        return None, (jsonify({"erro": "Este convite expirou."}), 410)
    return convite, None


def _serializar_avaliacao(documento):
    data = documento.get("criado_em")
    if isinstance(data, datetime):
        data = data.date().isoformat()
    elif not isinstance(data, str):
        data = _agora().date().isoformat()

    return {
        "id": documento.get("numero_pedido", documento.get("pedidoId", "")),
        "avaliacaoId": str(documento["_id"]),
        "pedidoId": documento.get("pedidoId", ""),
        "cliente": documento.get("cliente", "Cliente"),
        "categoria": documento.get("categoria", "Produto"),
        "uf": documento.get("uf", ""),
        "nota": documento["nota"],
        "comentario": documento.get("comentario", ""),
        "recomendacao": documento.get("recomendacao", ""),
        "problemas": documento.get("problemas", []),
        "quantidade_correta": documento.get("quantidade_correta"),
        "fotos": [
            {"id": str(foto["id"]), "nome": foto.get("nome", "Foto")}
            for foto in documento.get("fotos", [])
        ],
        "data": data[:10],
        "atendeu": documento.get("atendeu"),
        "respondeu": documento.get("respondeu"),
        "resolvido": documento.get("resolvido"),
        "motivo": documento.get("motivo"),
        "resolucao": documento.get("resolucao"),
        "origem": "real",
    }


def _serializar_avaliacao_historica(documento):
    data = (
        documento.get("data_avaliacao")
        or documento.get("data_entrega")
        or documento.get("data_pedido")
    )
    if isinstance(data, datetime):
        data = data.date()
    nota = int(documento["nota"])
    pedido = str(documento["num_pedido"])
    return {
        "id": pedido,
        "avaliacaoId": f"historico-{pedido}",
        "pedidoId": pedido,
        "cliente": f"Cliente {pedido}",
        "categoria": documento.get("categoria") or "Produto",
        "uf": documento.get("uf") or "",
        "nota": nota,
        "comentario": "Avaliação histórica importada.",
        "recomendacao": "",
        "problemas": [],
        "quantidade_correta": None,
        "fotos": [],
        "data": data.isoformat() if data else "",
        "atendeu": None,
        "respondeu": None,
        "resolvido": None,
        "motivo": None,
        "resolucao": None,
        "origem": "historico",
    }


def carregar_avaliacoes():
    """Combina respostas do MongoDB e notas históricas do data warehouse."""
    documentos = avaliacoes_collection.find().sort("criado_em", -1)
    avaliacoes = [_serializar_avaliacao(documento) for documento in documentos]
    historico = consultar(
        """
        SELECT num_pedido, categoria, uf, nota, data_avaliacao, data_entrega, data_pedido
        FROM pedidos_historicos
        WHERE nota IS NOT NULL
        ORDER BY COALESCE(data_avaliacao, data_entrega, data_pedido) DESC
        """
    )
    avaliacoes.extend(_serializar_avaliacao_historica(item) for item in historico)
    return sorted(avaliacoes, key=lambda item: item["data"], reverse=True)


def salvar_acompanhamento(id_avaliacao, campos):
    """Atualiza o acompanhamento de uma reclamação existente."""
    try:
        oid = ObjectId(id_avaliacao)
    except (InvalidId, TypeError):
        return None

    resultado = avaliacoes_collection.update_one(
        {"_id": oid},
        {"$set": campos},
    )
    if resultado.matched_count == 0:
        return None
    atualizado = avaliacoes_collection.find_one({"_id": oid})
    return _serializar_avaliacao(atualizado) if atualizado else None


def _configuracao_email():
    host = os.getenv("SMTP_HOST", "").strip()
    remetente = os.getenv("SMTP_FROM", os.getenv("SMTP_USERNAME", "")).strip()
    base_url = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if not host or not remetente or not base_url:
        raise ValueError(
            "Configure SMTP_HOST, SMTP_FROM e PUBLIC_BASE_URL para enviar convites."
        )
    try:
        porta = int(os.getenv("SMTP_PORT", "587"))
    except ValueError as exc:
        raise ValueError("SMTP_PORT deve ser um número.") from exc
    if not 1 <= porta <= 65535:
        raise ValueError("SMTP_PORT deve estar entre 1 e 65535.")
    return host, porta, remetente, base_url


def _remover_foto(foto_id):
    try:
        BUCKET_FOTOS.delete(foto_id)
    except PyMongoError:
        current_app.logger.exception("Falha ao remover foto após erro ao salvar.")


def _enviar_email(destinatario, assunto, texto):
    host, porta, remetente, _ = _configuracao_email()
    mensagem = EmailMessage()
    mensagem["Subject"] = assunto
    mensagem["From"] = remetente
    mensagem["To"] = destinatario
    mensagem.set_content(texto)

    with smtplib.SMTP(host, porta, timeout=20) as servidor:
        servidor.ehlo()
        servidor.starttls(context=ssl.create_default_context())
        servidor.ehlo()
        usuario = os.getenv("SMTP_USERNAME", "").strip()
        senha = os.getenv("SMTP_PASSWORD", "")
        if usuario:
            servidor.login(usuario, senha)
        servidor.send_message(mensagem)


def _dados_pedido(pedido_id):
    try:
        pedido_oid = ObjectId(pedido_id)
        pedido = orcamentos_collection.find_one({"_id": pedido_oid})
    except (InvalidId, TypeError):
        return None, "pedidoId inválido"

    if not pedido:
        return None, "Pedido/orçamento não encontrado"

    try:
        cliente_id = ObjectId(str(pedido.get("clienteId", "")))
    except (InvalidId, TypeError):
        return None, "O pedido não possui um cliente válido"
    cliente = clientes_collection.find_one({"_id": cliente_id})
    if not cliente:
        return None, "Cliente do pedido não encontrado"
    email = str(cliente.get("email", "")).strip()
    if not email or "@" not in email:
        return None, "O cliente do pedido não possui um e-mail válido"

    categoria = str(pedido.get("categoria") or "Produto")
    nomes_produtos = []
    for item in pedido.get("itens", []):
        if not isinstance(item, dict):
            continue
        nome = (
            item.get("produto")
            or item.get("nomeProduto")
            or item.get("nome_produto")
        )
        if nome:
            nomes_produtos.append(str(nome))

    for item in itens_orcamento_collection.find({"orcamentoId": str(pedido_oid)}):
        nome = item.get("nomeProduto") or item.get("nome_produto")
        if not nome and item.get("produtoId"):
            try:
                produto = produtos_collection.find_one(
                    {"_id": ObjectId(str(item["produtoId"]))}
                )
            except (InvalidId, TypeError):
                produto = None
            if produto:
                nome = produto.get("nome") or produto.get("descricao")
        if nome:
            nomes_produtos.append(str(nome))

    uf = str(cliente.get("uf") or cliente.get("estado") or pedido.get("uf") or "").strip().upper()
    if uf not in UFS_VALIDAS:
        uf = ""

    numero_pedido = str(
        pedido.get("numeroPedido")
        or pedido.get("numero_pedido")
        or str(pedido_oid)[-6:]
    )
    produto = ", ".join(dict.fromkeys(nomes_produtos))
    if not produto:
        produto = f"Pedido #{numero_pedido}"

    return {
        "pedidoId": str(pedido_oid),
        "numero_pedido": numero_pedido,
        "cliente": str(cliente.get("nome") or pedido.get("clienteNome") or "Cliente"),
        "email": email,
        "produto": produto,
        "categoria": categoria,
        "uf": uf,
    }, None


@avaliacoes_bp.get("/avaliacoes")
def pagina_avaliacoes():
    return send_from_directory(PASTA_PAGINA, "avaliacoes.html")


@avaliacoes_bp.get("/dashboard-avaliacoes", strict_slashes=False)
def pagina_dashboard_avaliacoes():
    return send_from_directory(
        os.path.join(PASTA_PAGINA, "dashboard-avaliacoes"),
        "dashboard-avaliacoes.html",
    )


@avaliacoes_bp.get("/avaliacoes/<path:arquivo>")
def arquivos_avaliacoes(arquivo):
    if arquivo not in ARQUIVOS_PUBLICOS:
        abort(404)
    return send_from_directory(PASTA_PAGINA, arquivo)


@avaliacoes_bp.get("/avaliar/<token>")
def pagina_avaliar_pedido(token):
    if not token.strip():
        abort(404)
    return send_from_directory(
        os.path.join(PASTA_PAGINA, "avaliar"),
        "avaliar.html",
    )


@avaliacoes_bp.get("/api/avaliacoes")
def api_avaliacoes():
    try:
        return jsonify(carregar_avaliacoes())
    except PyMongoError:
        current_app.logger.exception("Falha ao carregar avaliações do MongoDB.")
        return jsonify({"erro": "Não foi possível carregar as avaliações."}), 503
    except WarehouseNotConfigured as erro:
        return jsonify({"erro": str(erro)}), 503
    except PsycopgError:
        current_app.logger.exception("Falha ao carregar avaliações históricas.")
        return jsonify({"erro": "Não foi possível carregar as avaliações."}), 503


@avaliacoes_bp.patch("/api/avaliacoes/<id_avaliacao>")
def api_atualizar_avaliacao(id_avaliacao):
    dados = request.get_json(silent=True) or {}
    campos = {chave: valor for chave, valor in dados.items()
              if chave in CAMPOS_EDITAVEIS}
    if not campos:
        return jsonify({"erro": "Nenhum campo válido para atualizar."}), 400
    try:
        atualizada = salvar_acompanhamento(id_avaliacao, campos)
    except PyMongoError:
        current_app.logger.exception("Falha ao atualizar acompanhamento.")
        return jsonify({"erro": "Não foi possível salvar o acompanhamento."}), 503
    if atualizada is None:
        return jsonify({"erro": "Avaliação não encontrada."}), 404
    return jsonify(atualizada)


@avaliacoes_bp.post("/api/avaliacoes/convites")
def api_criar_convite():
    segredo_configurado = os.getenv("AVALIACOES_WEBHOOK_TOKEN", "")
    segredo_recebido = request.headers.get("X-Webhook-Token", "")
    if not segredo_configurado:
        return jsonify({"erro": "O webhook de avaliações não está configurado."}), 503
    if not hmac.compare_digest(segredo_recebido, segredo_configurado):
        return jsonify({"erro": "Não autorizado."}), 401

    dados = request.get_json(silent=True) or {}
    if str(dados.get("statusEntrega", "")).strip().casefold() != "entregue":
        return jsonify({
            "erro": "Convite só pode ser enviado após a confirmação da entrega."
        }), 409

    pedido_id = str(dados.get("pedidoId", "")).strip()
    if not pedido_id:
        return jsonify({"erro": "Campo obrigatório: pedidoId"}), 400

    try:
        config_email = _configuracao_email()
        pedido, erro = _dados_pedido(pedido_id)
    except PyMongoError:
        current_app.logger.exception("Falha ao consultar os dados do pedido.")
        return jsonify({"erro": "Não foi possível consultar o pedido no MongoDB."}), 503
    except ValueError as exc:
        return jsonify({"erro": str(exc)}), 503
    if erro:
        return jsonify({"erro": erro}), 400

    token = secrets.token_urlsafe(32)
    convite = {
        **pedido,
        "token_hash": _hash_token(token),
        "criado_em": _agora(),
        "expira_em": _agora() + timedelta(days=30),
        "usado": False,
    }
    try:
        convites_avaliacao_collection.create_index("pedidoId", unique=True)
        if convites_avaliacao_collection.find_one({"pedidoId": pedido["pedidoId"]}):
            return jsonify({"erro": "Já existe um convite para este pedido."}), 409
        convites_avaliacao_collection.insert_one(convite)
    except DuplicateKeyError:
        return jsonify({"erro": "Já existe um convite para este pedido."}), 409
    except PyMongoError:
        current_app.logger.exception("Falha ao registrar convite de avaliação.")
        return jsonify({"erro": "Não foi possível registrar o convite."}), 503

    link = f"{config_email[3]}/avaliar/{token}"
    texto = (
        f"Olá, {pedido['cliente']}!\n\n"
        f"Esperamos que tenha gostado de {pedido['produto']}, do pedido "
        f"#{pedido['numero_pedido']}.\n"
        "Conte para nós como foi sua experiência. Leva só alguns minutos:\n\n"
        f"{link}\n\n"
        "Este link é pessoal e expira em 30 dias."
    )
    try:
        _enviar_email(
            pedido["email"],
            f"Avalie seu pedido #{pedido['numero_pedido']} - L'amore",
            texto,
        )
    except (OSError, smtplib.SMTPException, ValueError):
        current_app.logger.exception("Falha ao enviar convite de avaliação.")
        try:
            convites_avaliacao_collection.delete_one(
                {"token_hash": convite["token_hash"]}
            )
        except PyMongoError:
            current_app.logger.exception(
                "Falha ao remover convite após erro no envio do e-mail."
            )
        return jsonify({"erro": "Não foi possível enviar o e-mail de avaliação."}), 502

    return jsonify({
        "msg": "Convite de avaliação enviado.",
        "pedidoId": pedido["pedidoId"],
    }), 201


@avaliacoes_bp.get("/api/avaliacoes/convites/<token>")
def api_detalhes_convite(token):
    try:
        convite = convites_avaliacao_collection.find_one(
            {"token_hash": _hash_token(token)}
        )
    except PyMongoError:
        current_app.logger.exception("Falha ao consultar convite de avaliação.")
        return jsonify({"erro": "Não foi possível consultar o convite."}), 503
    if not convite:
        return jsonify({"erro": "Convite inválido."}), 404
    if convite.get("usado"):
        return jsonify({"erro": "Este pedido já foi avaliado."}), 409
    if _convite_expirado(convite):
        return jsonify({"erro": "Este convite expirou."}), 410
    produto = convite.get("produto")
    if not produto or produto == convite.get("categoria") or produto == "Produto":
        try:
            pedido, erro = _dados_pedido(convite["pedidoId"])
        except PyMongoError:
            current_app.logger.exception(
                "Falha ao atualizar o produto do convite de avaliação."
            )
            return jsonify({"erro": "Não foi possível consultar os itens do pedido."}), 503
        if pedido:
            produto = pedido["produto"]
    if not produto or produto == convite.get("categoria"):
        produto = f"Pedido #{convite['numero_pedido']}"
    return jsonify({
        "pedidoId": convite["pedidoId"],
        "numeroPedido": convite["numero_pedido"],
        "cliente": convite["cliente"],
        "produto": produto,
        "categoria": convite["categoria"],
        "uf": convite.get("uf", ""),
    })


@avaliacoes_bp.post("/api/avaliacoes/convites/<token>/avaliar")
def api_enviar_avaliacao(token):
    try:
        convite, erro_resposta = _buscar_convite(token)
    except PyMongoError:
        current_app.logger.exception("Falha ao consultar convite de avaliação.")
        return jsonify({"erro": "Não foi possível consultar o convite."}), 503
    if erro_resposta:
        return erro_resposta

    try:
        nota = int(request.form.get("nota", ""))
    except ValueError:
        return jsonify({"erro": "Selecione uma nota de 1 a 5."}), 400
    if nota not in range(1, 6):
        return jsonify({"erro": "Selecione uma nota de 1 a 5."}), 400
    uf = request.form.get("uf", "").strip().upper()
    if uf not in UFS_VALIDAS:
        return jsonify({"erro": "Selecione o estado onde o pedido foi entregue."}), 400

    comentario = request.form.get("comentario", "").strip()
    recomendacao = request.form.get("recomendacao", "").strip()
    if len(comentario) > 500 or len(recomendacao) > 500:
        return jsonify({"erro": "Os comentários podem ter no máximo 500 caracteres."}), 400
    if nota < 5 and not comentario:
        return jsonify({"erro": "Descreva o problema para notas abaixo de 5."}), 400

    problemas = request.form.getlist("problemas")
    if any(problema not in PROBLEMAS_VALIDOS for problema in problemas):
        return jsonify({"erro": "Há um motivo de avaliação inválido."}), 400
    quantidade_correta = request.form.get("quantidade_correta") or None
    if quantidade_correta not in (None, "sim", "nao"):
        return jsonify({"erro": "Resposta inválida para a quantidade do pedido."}), 400

    foto = request.files.get("foto")
    if nota < 5 and (not foto or not foto.filename):
        return jsonify({"erro": "Envie ao menos uma foto do problema."}), 400

    foto_bytes = None
    if foto and foto.filename:
        foto_bytes = foto.stream.read(TAMANHO_MAXIMO_FOTO + 1)
        if len(foto_bytes) > TAMANHO_MAXIMO_FOTO:
            return jsonify({"erro": "A foto deve ter no máximo 5 MB."}), 413
        tipo_real = (
            "image/png" if foto_bytes.startswith(b"\x89PNG\r\n\x1a\n")
            else "image/jpeg" if foto_bytes.startswith(b"\xff\xd8\xff")
            else "image/webp" if foto_bytes.startswith(b"RIFF")
            and foto_bytes[8:12] == b"WEBP"
            else None
        )
        if not tipo_real or foto.mimetype != tipo_real:
            return jsonify({"erro": "Envie uma imagem PNG, JPG ou WebP válida."}), 400

    try:
        avaliacoes_collection.create_index("pedidoId", unique=True)
        if avaliacoes_collection.find_one({"pedidoId": convite["pedidoId"]}):
            return jsonify({"erro": "Este pedido já possui uma avaliação."}), 409
        resultado_convite = convites_avaliacao_collection.update_one(
            {
                "_id": convite["_id"],
                "usado": False,
                "expira_em": {"$gt": _agora()},
            },
            {"$set": {"usado": True}},
        )
        if resultado_convite.modified_count != 1:
            return jsonify({"erro": "Este convite já foi utilizado."}), 409

        fotos = []
        if foto_bytes is not None and foto is not None:
            foto_id = BUCKET_FOTOS.upload_from_stream(
                secure_filename(foto.filename) or "foto",
                foto_bytes,
                metadata={"content_type": tipo_real},
            )
            fotos.append({
                "id": foto_id,
                "nome": secure_filename(foto.filename) or "foto",
            })

        documento = {
            "pedidoId": convite["pedidoId"],
            "numero_pedido": convite["numero_pedido"],
            "cliente": convite["cliente"],
            "categoria": convite["categoria"],
            "uf": uf,
            "nota": nota,
            "comentario": comentario,
            "recomendacao": recomendacao,
            "problemas": problemas,
            "quantidade_correta": quantidade_correta,
            "fotos": fotos,
            "criado_em": _agora(),
            "atendeu": None,
            "respondeu": None,
            "resolvido": None,
            "motivo": None,
            "resolucao": None,
        }
        avaliacoes_collection.insert_one(documento)
    except DuplicateKeyError:
        convites_avaliacao_collection.update_one(
            {"_id": convite["_id"]}, {"$set": {"usado": True}}
        )
        if "foto_id" in locals():
            _remover_foto(foto_id)
        return jsonify({"erro": "Este pedido já possui uma avaliação."}), 409
    except PyMongoError:
        current_app.logger.exception("Falha ao salvar avaliação.")
        convites_avaliacao_collection.update_one(
            {"_id": convite["_id"]}, {"$set": {"usado": False}}
        )
        if "foto_id" in locals():
            _remover_foto(foto_id)
        return jsonify({"erro": "Não foi possível salvar sua avaliação."}), 503

    return jsonify({"msg": "A avaliação foi enviada com sucesso."}), 201


@avaliacoes_bp.get("/api/avaliacoes/fotos/<foto_id>")
def api_foto_avaliacao(foto_id):
    try:
        arquivo = BUCKET_FOTOS.open_download_stream(ObjectId(foto_id))
    except (InvalidId, TypeError, NoFile):
        return jsonify({"erro": "Foto não encontrada."}), 404
    except PyMongoError:
        current_app.logger.exception("Falha ao carregar foto de avaliação.")
        return jsonify({"erro": "Não foi possível carregar a foto."}), 503
    resposta = send_file(
        arquivo,
        mimetype=(arquivo.metadata or {}).get("content_type", "application/octet-stream"),
        download_name=arquivo.filename,
    )
    resposta.headers["X-Content-Type-Options"] = "nosniff"
    return resposta
