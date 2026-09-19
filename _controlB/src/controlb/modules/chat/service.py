"""Casos de uso do Chat. Provedores só são conhecidos através do contrato."""

from __future__ import annotations

import secrets
from dataclasses import asdict

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from controlb.config import get_settings
from controlb.modules.chat import repository as repo
from controlb.modules.chat import schemas
from controlb.modules.chat.connectors.base import ConnectorError
from controlb.modules.chat.connectors.registry import available_providers, create_connector
from controlb.modules.chat.crypto import (
    CredentialDecryptionError,
    decrypt_credentials,
    encrypt_credentials,
)
from controlb.modules.chat.models import (
    ChatConnection,
    ChatConversation,
    ChatConversationLink,
    ChatMessage,
    ChatWebhookEvent,
    utcnow,
)
from controlb.modules.documents.models import BusinessDocument
from controlb.modules.documents.security import can_view_document_type
from controlb.modules.identity.models import Contact, User
from controlb.modules.identity.security import get_user_permissions
from controlb.modules.sales.models import Customer


def permissions(user):
    return set(get_user_permissions(user))


def require(user, code):
    if not {code, "*:*"}.intersection(permissions(user)):
        raise HTTPException(403, f"Permissão necessária: {code}.")


def connection(db, user, connection_id, *, active=False):
    obj = repo.get_connection(db, user.organization_id, connection_id)
    if obj is None:
        raise HTTPException(404, "Conexão não encontrada.")
    if active and not obj.is_active:
        raise HTTPException(409, "Conexão desativada.")
    return obj


def conversation(db, user, conversation_id):
    require(user, "chat:view")
    obj = repo.get_conversation(db, user.organization_id, conversation_id, permissions(user))
    if obj is None:
        raise HTTPException(404, "Conversa não encontrada ou sem acesso aos documentos vinculados.")
    return obj


def document(db, user, document_id):
    obj = db.scalar(
        select(BusinessDocument).where(
            BusinessDocument.id == document_id,
            BusinessDocument.organization_id == user.organization_id,
        )
    )
    if obj is None:
        raise HTTPException(404, "Documento não encontrado.")
    if not can_view_document_type(obj.document_type, permissions(user)):
        raise HTTPException(403, "Sem acesso ao documento de origem.")
    return obj


def _validate_parties(db, org_id, values):
    for key, model in (
        ("contact_id", Contact),
        ("customer_id", Customer),
        ("assigned_user_id", User),
    ):
        identifier = values.get(key)
        if identifier and not db.scalar(
            select(model.id).where(
                model.id == identifier, model.organization_id == org_id, model.is_active.is_(True)
            )
        ):
            raise HTTPException(422, "Contato, cliente ou responsável inválido para a organização.")
    if values.get("customer_id") and values.get("contact_id"):
        customer = db.get(Customer, values["customer_id"])
        if customer.contact_id and customer.contact_id != values["contact_id"]:
            raise HTTPException(422, "O contato não corresponde ao cliente informado.")


def _validate_destination(base_url):
    allowed = {url.rstrip("/") for url in get_settings().chat_allowed_base_urls}
    if base_url not in allowed:
        raise HTTPException(422, "URL não habilitada em CHAT_ALLOWED_BASE_URLS no servidor.")


def _credentials(obj):
    try:
        return decrypt_credentials(obj.credentials_ciphertext)
    except CredentialDecryptionError:
        raise HTTPException(
            503, "Credenciais indisponíveis. Verifique a chave do servidor."
        ) from None


def connector_for(obj, *, network=False):
    if network:
        _validate_destination(obj.base_url)
    return create_connector(
        obj.provider,
        configuration={
            **obj.configuration,
            "base_url": obj.base_url,
            "instance_name": obj.external_instance_id,
        },
        credentials=_credentials(obj),
    )


def create_connection(db, user, data):
    if data.provider not in available_providers():
        raise HTTPException(422, "Provedor não suportado.")
    _validate_destination(data.base_url)
    values = data.model_dump(exclude={"api_key", "webhook_secret"})
    obj = ChatConnection(
        **values,
        organization_id=user.organization_id,
        created_by_id=user.id,
        credentials_ciphertext=encrypt_credentials(
            {
                "api_key": data.api_key.get_secret_value(),
                "webhook_secret": data.webhook_secret.get_secret_value()
                if data.webhook_secret
                else secrets.token_urlsafe(32),
            }
        ),
        credentials_hint="Configurada",
    )
    try:
        with db.begin_nested():
            db.add(obj)
            db.flush()
    except IntegrityError:
        raise HTTPException(409, "Esta instância já está cadastrada na organização.") from None
    return obj


def update_connection(db, user, connection_id, data):
    repo.lock_connection(db, connection_id)
    obj = connection(db, user, connection_id)
    values = data.model_dump(exclude_unset=True, exclude={"api_key", "webhook_secret"})
    if any(value is None for value in values.values()):
        raise HTTPException(422, "Os campos de configuração não podem ser nulos.")
    if "base_url" in values:
        _validate_destination(values["base_url"])
    identity_changed = any(
        key in values and values[key] != getattr(obj, key)
        for key in ("base_url", "external_instance_id")
    )
    if identity_changed and db.scalar(
        select(ChatConversation.id).where(ChatConversation.connection_id == obj.id).limit(1)
    ):
        raise HTTPException(
            409, "A conexão tem histórico. Cadastre uma nova conexão para outra instância."
        )
    try:
        with db.begin_nested():
            for key, value in values.items():
                setattr(obj, key, value)
            if data.api_key or data.webhook_secret:
                credentials = _credentials(obj)
                for key in ("api_key", "webhook_secret"):
                    value = getattr(data, key)
                    if value:
                        credentials[key] = value.get_secret_value()
                obj.credentials_ciphertext = encrypt_credentials(credentials)
            if {"base_url", "external_instance_id", "api_key", "is_active"}.intersection(
                data.model_fields_set
            ):
                obj.status = "DISCONNECTED"
            db.flush()
    except IntegrityError:
        raise HTTPException(409, "Esta instância já está cadastrada.") from None
    return obj


async def check_connection(db, user, connection_id):
    repo.lock_connection(db, connection_id)
    obj = connection(db, user, connection_id, active=True)
    adapter = connector_for(obj, network=True)
    try:
        result = await adapter.get_connection_state()
        obj.status, obj.last_error = result.state, None
    except ConnectorError:
        obj.status, obj.last_error = (
            "ERROR",
            "Falha ao consultar o provedor. Verifique a configuração.",
        )
    finally:
        await adapter.aclose()
    obj.last_synced_at = utcnow()
    db.flush()
    return obj


async def configure_webhook(db, user, connection_id):
    repo.lock_connection(db, connection_id)
    obj = connection(db, user, connection_id, active=True)
    base = get_settings().chat_public_base_url
    if not base:
        raise HTTPException(503, "Configure CHAT_PUBLIC_BASE_URL com a URL pública da API.")
    url = f"{schemas.validate_url(base)}/chat/webhooks/{obj.id}"
    adapter = connector_for(obj, network=True)
    try:
        await adapter.configure_webhook(url, _credentials(obj)["webhook_secret"])
    except ConnectorError:
        raise HTTPException(502, "Falha ao configurar o webhook no provedor.") from None
    finally:
        await adapter.aclose()
    return {"configured": True, "url": url}


async def create_conversation(db, user, data):
    require(user, "chat:link")
    require(user, "chat:view")
    document(db, user, data.business_document_id)
    _validate_parties(db, user.organization_id, data.model_dump())
    repo.lock_connection(db, data.connection_id)
    conn = connection(db, user, data.connection_id, active=True)
    adapter = connector_for(conn)
    try:
        external_id = adapter.chat_id_for_phone(data.remote_phone)
    finally:
        await adapter.aclose()
    obj = db.scalar(
        select(ChatConversation).where(
            ChatConversation.organization_id == user.organization_id,
            ChatConversation.connection_id == conn.id,
            ChatConversation.external_chat_id == external_id,
        )
    )
    if obj:
        obj = conversation(db, user, obj.id)
    else:
        obj = ChatConversation(
            organization_id=user.organization_id,
            connection_id=conn.id,
            external_chat_id=external_id,
            remote_phone=data.remote_phone,
            display_name=data.display_name,
            contact_id=data.contact_id,
            customer_id=data.customer_id,
        )
        db.add(obj)
        db.flush()
    link_conversation(
        db,
        user,
        obj.id,
        schemas.ChatConversationLinkCreate(
            business_document_id=data.business_document_id,
            link_type="ORIGIN" if not obj.document_links else "RELATED",
            is_primary=not obj.document_links,
        ),
        obj=obj,
    )
    return obj


def link_conversation(db, user, conversation_id, data, *, obj=None):
    require(user, "chat:link")
    obj = obj or conversation(db, user, conversation_id)
    repo.lock_connection(db, obj.connection_id)
    obj = conversation(db, user, conversation_id)
    document(db, user, data.business_document_id)
    link = next(
        (
            link
            for link in obj.document_links
            if link.business_document_id == data.business_document_id
        ),
        None,
    )
    if data.is_primary:
        for existing in obj.document_links:
            existing.is_primary = False
    if link is None:
        link = ChatConversationLink(
            organization_id=user.organization_id,
            conversation_id=obj.id,
            business_document_id=data.business_document_id,
            link_type=data.link_type,
            is_primary=data.is_primary or not obj.document_links,
            created_by_id=user.id,
        )
        db.add(link)
    else:
        link.is_primary = data.is_primary or link.is_primary
    db.flush()
    db.expire(obj, ["document_links"])
    return link


def update_conversation(db, user, conversation_id, data):
    require(user, "chat:link")
    obj = conversation(db, user, conversation_id)
    repo.lock_connection(db, obj.connection_id)
    obj = conversation(db, user, conversation_id)
    values = data.model_dump(exclude_unset=True)
    if "status" in values and values["status"] is None:
        raise HTTPException(422, "Informe o estado da conversa.")
    _validate_parties(
        db,
        user.organization_id,
        {
            "contact_id": values.get("contact_id", obj.contact_id),
            "customer_id": values.get("customer_id", obj.customer_id),
            "assigned_user_id": values.get("assigned_user_id", obj.assigned_user_id),
        },
    )
    for key, value in values.items():
        setattr(obj, key, value)
    db.flush()
    return obj


def mark_read(db, user, conversation_id):
    obj = conversation(db, user, conversation_id)
    repo.lock_connection(db, obj.connection_id)
    obj = conversation(db, user, conversation_id)
    obj.unread_count = 0
    db.flush()
    return obj


def list_conversations(
    db, user, *, page, page_size, search=None, document_id=None, status=None, unlinked=False
):
    query = repo.conversations_query(user.organization_id, permissions(user))
    if document_id:
        document(db, user, document_id)
        query = query.where(ChatConversation.document_links.any(business_document_id=document_id))
    if unlinked:
        require(user, "chat:link")
        query = query.where(~ChatConversation.document_links.any())
    if status:
        query = query.where(ChatConversation.status == status)
    if search:
        query = query.where(
            or_(
                ChatConversation.display_name.icontains(search, autoescape=True),
                ChatConversation.remote_phone.icontains(search, autoescape=True),
            )
        )
    return repo.page(
        db,
        query.order_by(ChatConversation.last_message_at.desc().nullslast(), ChatConversation.id),
        page,
        page_size,
    )


def list_messages(db, user, conversation_id, *, page, page_size):
    obj = conversation(db, user, conversation_id)
    query = (
        select(ChatMessage)
        .where(
            ChatMessage.organization_id == user.organization_id,
            ChatMessage.conversation_id == obj.id,
        )
        .order_by(ChatMessage.occurred_at.desc(), ChatMessage.id.desc())
    )
    return repo.page(db, query, page, page_size)


def _apply_status(message, status):
    ranks = {"FAILED": -1, "PENDING": 0, "SENT": 1, "DELIVERED": 2, "READ": 3}
    if message.direction != "OUTBOUND" or status not in ranks:
        return
    if status == "FAILED" and message.status == "PENDING":
        message.status = status
    elif ranks[status] > ranks.get(message.status, -1):
        message.status = status
        message.error_message = None
    if message.status in {"DELIVERED", "READ"}:
        message.delivered_at = message.delivered_at or utcnow()
    if message.status == "READ":
        message.read_at = message.read_at or utcnow()


def _preview(obj, message):
    if obj.last_message_at is None or message.occurred_at >= obj.last_message_at:
        obj.last_message_at = message.occurred_at
        obj.last_message_preview = (message.content or f"[{message.message_type}]")[:500]


async def send_text(db, user, conversation_id, data):
    require(user, "chat:send")
    obj = conversation(db, user, conversation_id)
    repo.lock_connection(db, obj.connection_id)
    obj = conversation(db, user, conversation_id)
    existing = db.scalar(
        select(ChatMessage).where(
            ChatMessage.organization_id == user.organization_id,
            ChatMessage.client_request_id == data.client_request_id,
        )
    )
    if existing:
        if existing.conversation_id != obj.id or existing.content != data.text:
            raise HTTPException(409, "Identificador de envio já usado em outra mensagem.")
        return existing
    if not obj.document_links:
        raise HTTPException(409, "Vincule a conversa ao registro de origem antes de enviar.")
    if obj.status != "OPEN":
        raise HTTPException(409, "Reabra a conversa antes de enviar.")
    conn = connection(db, user, obj.connection_id, active=True)
    adapter = connector_for(conn, network=True)
    message = ChatMessage(
        organization_id=user.organization_id,
        conversation_id=obj.id,
        client_request_id=data.client_request_id,
        direction="OUTBOUND",
        content=data.text,
        message_type="TEXT",
        status="PENDING",
        created_by_id=user.id,
    )
    try:
        try:
            with db.begin_nested():
                db.add(message)
                db.flush()
        except IntegrityError:
            raise HTTPException(409, "Identificador de envio já utilizado.") from None
        # Fronteira intencional: guardar a intenção ANTES do efeito externo.
        # Uma repetição HTTP retorna este registro e nunca reenvia automaticamente.
        db.commit()
        repo.lock_connection(db, conn.id)
        conn = connection(db, user, conn.id, active=True)
        obj = conversation(db, user, obj.id)
        if obj.status != "OPEN" or not obj.document_links:
            message.status = "FAILED"
            message.error_message = (
                "Conversa indisponível para envio. Reabra ou verifique o vínculo."
            )
            db.flush()
            return message
        # Credenciais podem ter sido rotacionadas durante a fronteira de commit.
        await adapter.aclose()
        adapter = connector_for(conn, network=True)
        try:
            result = await adapter.send_text(obj.remote_phone, data.text)
            echo = repo.get_external_message(
                db, user.organization_id, obj.id, result.external_message_id
            )
            if echo and echo.id != message.id:
                # Preservar o histórico já recebido pelo callback e reconciliar
                # a intenção local com ele, sem duplicar a mensagem.
                db.delete(message)
                db.flush()
                echo.client_request_id = data.client_request_id
                echo.created_by_id = user.id
                message = echo
            message.external_message_id = result.external_message_id
            _apply_status(message, result.status)
            _apply_pending_statuses(db, conn, message)
        except ConnectorError as exc:
            # Timeouts/5xx podem ocorrer depois de o provedor aceitar a mensagem.
            if exc.status_code and 400 <= exc.status_code < 500 and exc.status_code != 408:
                message.status = "FAILED"
                message.error_message = "O provedor recusou o envio. Verifique a conexão."
            else:
                message.error_message = (
                    "Envio sem confirmação. Verifique no provedor antes de reenviar."
                )
        _preview(obj, message)
        db.flush()
        return message
    finally:
        await adapter.aclose()


def _apply_pending_statuses(db, conn, message):
    events = db.scalars(
        select(ChatWebhookEvent).where(
            ChatWebhookEvent.connection_id == conn.id,
            ChatWebhookEvent.organization_id == conn.organization_id,
            ChatWebhookEvent.status == "PENDING",
            ChatWebhookEvent.payload["external_message_id"].as_string()
            == message.external_message_id,
        )
    )
    conv = db.get(ChatConversation, message.conversation_id)
    for event in events:
        if event.payload.get("external_chat_id") not in {None, conv.external_chat_id}:
            continue
        _apply_status(message, event.payload.get("delivery_status"))
        event.status, event.processed_at = "PROCESSED", utcnow()


async def receive_webhook(db, connection_id, token, payload):
    # A conexão da URL é a única fonte de organização. Nunca aceitar org do callback.
    conn = db.scalar(select(ChatConnection).where(ChatConnection.id == connection_id))
    if conn is None or not conn.is_active or not token:
        raise HTTPException(401, "Webhook não autorizado.")
    if not secrets.compare_digest(token.encode(), _credentials(conn)["webhook_secret"].encode()):
        raise HTTPException(401, "Webhook não autorizado.")
    repo.lock_connection(db, conn.id)
    db.refresh(conn)
    if not conn.is_active or not secrets.compare_digest(
        token.encode(), _credentials(conn)["webhook_secret"].encode()
    ):
        raise HTTPException(401, "Webhook não autorizado.")
    adapter = connector_for(conn)
    try:
        events = adapter.parse_webhooks(payload)
    except (ValueError, TypeError, OverflowError):
        raise HTTPException(422, "Evento inválido.") from None
    finally:
        await adapter.aclose()
    if any(event.external_instance_id != conn.external_instance_id for event in events):
        raise HTTPException(403, "Instância do webhook não corresponde à conexão.")
    processed = 0
    for event in events:
        if db.scalar(
            select(ChatWebhookEvent.id).where(
                ChatWebhookEvent.connection_id == conn.id,
                ChatWebhookEvent.event_key == event.event_key,
            )
        ):
            continue
        # Guardar só dados normalizados; callbacks Evolution incluem apikey no corpo.
        normalized = asdict(event)
        normalized.pop("raw_payload", None)
        if normalized["message"]:
            normalized["message"]["occurred_at"] = event.message.occurred_at.isoformat()
        inbox = ChatWebhookEvent(
            organization_id=conn.organization_id,
            connection_id=conn.id,
            event_key=event.event_key,
            event_type=event.event_type,
            payload=normalized,
            status="IGNORED",
            attempts=1,
        )
        db.add(inbox)
        if event.connection_state:
            conn.status, conn.last_synced_at = event.connection_state, utcnow()
            inbox.status = "PROCESSED"
        if event.message:
            incoming = event.message
            obj = db.scalar(
                select(ChatConversation).where(
                    ChatConversation.organization_id == conn.organization_id,
                    ChatConversation.connection_id == conn.id,
                    ChatConversation.external_chat_id == incoming.external_chat_id,
                )
            )
            if obj is None:
                obj = ChatConversation(
                    organization_id=conn.organization_id,
                    connection_id=conn.id,
                    external_chat_id=incoming.external_chat_id,
                    remote_phone=incoming.remote_phone,
                    display_name=incoming.sender_name,
                )
                db.add(obj)
                db.flush()
            message = repo.get_external_message(
                db, conn.organization_id, obj.id, incoming.external_message_id
            )
            if message is None:
                message = ChatMessage(
                    organization_id=conn.organization_id,
                    conversation_id=obj.id,
                    external_message_id=incoming.external_message_id,
                    direction=incoming.direction,
                    content=incoming.content,
                    message_type=incoming.message_type,
                    occurred_at=incoming.occurred_at,
                    sender_name=incoming.sender_name,
                    sender_phone=incoming.remote_phone,
                    status="RECEIVED" if incoming.direction == "INBOUND" else "SENT",
                )
                db.add(message)
                if incoming.direction == "INBOUND":
                    obj.unread_count += 1
                _preview(obj, message)
                db.flush()
                _apply_pending_statuses(db, conn, message)
            inbox.status = "PROCESSED"
        if event.delivery_status and event.external_message_id:
            query = (
                select(ChatMessage)
                .join(ChatConversation, ChatConversation.id == ChatMessage.conversation_id)
                .where(
                    ChatMessage.organization_id == conn.organization_id,
                    ChatConversation.connection_id == conn.id,
                    ChatMessage.external_message_id == event.external_message_id,
                )
            )
            if event.external_chat_id:
                query = query.where(ChatConversation.external_chat_id == event.external_chat_id)
            message = db.scalar(query)
            if message:
                _apply_status(message, event.delivery_status)
                inbox.status = "PROCESSED"
            else:
                inbox.status = "PENDING"
        if inbox.status != "PENDING":
            inbox.processed_at = utcnow()
        db.flush()
        processed += 1
    return {"accepted": True, "events": processed}
