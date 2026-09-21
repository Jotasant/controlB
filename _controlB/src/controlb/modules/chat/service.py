"""Casos de uso do Chat. Provedores só são conhecidos através do contrato."""

from __future__ import annotations

import asyncio
import secrets
import uuid
from dataclasses import asdict, replace

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from controlb.config import get_settings
from controlb.modules.chat import repository as repo
from controlb.modules.chat import schemas
from controlb.modules.chat.connectors.base import ConnectorError, ConnectorMedia
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
    ChatReactionRequest,
    ChatTeam,
    ChatWebhookEvent,
    utcnow,
)
from controlb.modules.documents.models import BusinessDocument
from controlb.modules.documents.security import can_view_document_type
from controlb.modules.identity.models import Contact, ContactOrigin, User
from controlb.modules.identity.security import get_user_permissions
from controlb.modules.sales.models import Customer


def permissions(user):
    return set(get_user_permissions(user))


def require(user, code):
    if not {code, "*:*"}.intersection(permissions(user)):
        raise HTTPException(403, f"Permissão necessária: {code}.")


def connection(db, user, connection_id, *, active=False, allow_unassigned=False):
    obj = repo.get_connection(db, user.organization_id, connection_id)
    if obj is None:
        raise HTTPException(404, "Conexão não encontrada.")
    if not (allow_unassigned and repo.is_unassigned(db, obj)) and not repo.is_member(
        db, user.organization_id, user.id, obj.team_id
    ):
        raise HTTPException(404, "Conexão não encontrada ou fora da sua equipe.")
    if active and not obj.is_active:
        raise HTTPException(409, "Conexão desativada.")
    return obj


def conversation(db, user, conversation_id):
    require(user, "chat:view")
    obj = repo.get_conversation(
        db, user.organization_id, conversation_id, permissions(user), user.id
    )
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


def _instance_members(db, user, member_ids):
    identifiers = set(member_ids)
    if user.id not in identifiers:
        raise HTTPException(
            422, "Mantenha seu usuário entre os participantes para administrar a instância."
        )
    members = list(
        db.scalars(
            select(User).where(
                User.organization_id == user.organization_id,
                User.is_active.is_(True),
                User.id.in_(identifiers),
            )
        )
    )
    if len(members) != len(identifiers):
        raise HTTPException(422, "Selecione somente usuários ativos da sua organização.")
    return members


def create_connection(db, user, data):
    members = _instance_members(db, user, data.member_ids)
    if data.provider not in available_providers():
        raise HTTPException(422, "Provedor não suportado.")
    _validate_destination(data.base_url)
    values = data.model_dump(exclude={"api_key", "webhook_secret", "member_ids"})
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
        sync_checkpoint_at=utcnow(),
    )
    try:
        with db.begin_nested():
            obj.team = ChatTeam(
                organization_id=user.organization_id, name=data.name, members=members
            )
            db.add(obj)
            db.flush()
    except IntegrityError:
        raise HTTPException(409, "Esta instância já está cadastrada na organização.") from None
    return obj


async def update_connection(db, user, connection_id, data):
    repo.lock_connection(db, connection_id)
    obj = connection(db, user, connection_id, allow_unassigned=True)
    if data.member_ids is None and not repo.is_member(
        db, user.organization_id, user.id, obj.team_id
    ):
        raise HTTPException(404, "Configure os participantes antes de alterar esta instância.")
    values = data.model_dump(
        exclude_unset=True, exclude={"api_key", "webhook_secret", "member_ids"}
    )
    members = None
    if "member_ids" in data.model_fields_set:
        if data.member_ids is None:
            raise HTTPException(422, "Informe os usuários que podem acessar esta instância.")
        members = _instance_members(db, user, data.member_ids)
    if any(value is None for value in values.values()):
        raise HTTPException(422, "Os campos de configuração não podem ser nulos.")
    if "base_url" in values:
        _validate_destination(values["base_url"])
    routing_changed = any(
        key in values and values[key] != getattr(obj, key)
        for key in ("base_url", "external_instance_id")
    )
    active_changed = "is_active" in values and values["is_active"] != obj.is_active
    has_history = (
        db.scalar(
            select(ChatConversation.id).where(ChatConversation.connection_id == obj.id).limit(1)
        )
        is not None
    )
    if routing_changed and has_history and not obj.instance_phone:
        raise HTTPException(
            409, "Confirme o número da conexão atual antes de substituir a instância."
        )
    verify_replacement = bool(obj.instance_phone and (routing_changed or data.api_key))
    try:
        with db.begin_nested():
            for key, value in values.items():
                setattr(obj, key, value)
            if members is not None:
                if obj.team is None:
                    obj.team = ChatTeam(
                        organization_id=user.organization_id, name=obj.name, members=members
                    )
                else:
                    obj.team.members = members
            if obj.team:
                obj.team.name = obj.name
            if members is not None and not obj.sync_checkpoint_at:
                obj.sync_checkpoint_at = utcnow()
            if data.api_key or data.webhook_secret:
                credentials = _credentials(obj)
                for key in ("api_key", "webhook_secret"):
                    value = getattr(data, key)
                    if value:
                        credentials[key] = value.get_secret_value()
                obj.credentials_ciphertext = encrypt_credentials(credentials)
            if routing_changed or data.api_key or active_changed:
                obj.status = "DISCONNECTED"
            if verify_replacement:
                # O cadastro e os chats permanecem; somente a sessão técnica muda.
                adapter = connector_for(obj, network=True)
                try:
                    details = await adapter.get_instance_details()
                    if details.state != "CONNECTED":
                        raise HTTPException(
                            409,
                            "Pareie a nova instância com o mesmo número antes de salvar a substituição.",
                        )
                    _bind_instance_identity(db, obj, details)
                    base = get_settings().chat_public_base_url
                    if not base:
                        raise HTTPException(
                            503, "Configure CHAT_PUBLIC_BASE_URL antes de substituir a instância."
                        )
                    credentials = _credentials(obj)
                    credentials["webhook_secret"] = secrets.token_urlsafe(32)
                    await adapter.configure_webhook(
                        f"{schemas.validate_url(base)}/chat/webhooks/{obj.id}",
                        credentials["webhook_secret"],
                    )
                    obj.credentials_ciphertext = encrypt_credentials(credentials)
                    obj.status, obj.last_error = "CONNECTED", None
                    obj.last_synced_at = utcnow()
                    # Não avançar o checkpoint: mensagens da queda ainda precisam ser recuperadas.
                    obj.recovery_pending = True
                    obj.sync_started_at, obj.sync_page = None, 1
                except ConnectorError:
                    raise HTTPException(
                        502,
                        "Não foi possível validar a nova instância e configurar seu webhook. A conexão anterior foi preservada.",
                    ) from None
                finally:
                    await adapter.aclose()
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
        if result.state == "CONNECTED":
            _bind_instance_identity(db, obj, await adapter.get_instance_details())
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


def _bind_instance_identity(db, conn, details):
    if not details.phone:
        raise HTTPException(409, "O provedor ainda não informou o telefone pareado.")
    if conn.instance_phone and conn.instance_phone != details.phone:
        raise HTTPException(
            409, "Número diferente do canal original. Cadastre outra conexão para outro número."
        )
    # Serializa a confirmação do mesmo telefone sem depender do ID de sessão do provedor.
    repo.lock_connection(db, uuid.uuid5(conn.organization_id, f"chat-phone:{details.phone}"))
    if db.scalar(
        select(ChatConnection.id)
        .where(
            ChatConnection.organization_id == conn.organization_id,
            ChatConnection.instance_phone == details.phone,
            ChatConnection.id != conn.id,
        )
        .limit(1)
    ):
        raise HTTPException(
            409,
            "Este número já possui uma conexão no ControlB. Substitua a instância técnica no cadastro original para manter os chats e a equipe; não crie outro cadastro.",
        )
    conn.instance_phone = details.phone
    conn.provider_instance_id = details.instance_id
    db.flush()


async def _ensure_identity(db, conn):
    if not repo.team_is_active(db, conn.organization_id, conn.team_id):
        raise HTTPException(
            409, "Configure os participantes da instância antes de receber mensagens."
        )
    if conn.instance_phone:
        return
    adapter = connector_for(conn, network=True)
    try:
        _bind_instance_identity(db, conn, await adapter.get_instance_details())
    except ConnectorError:
        raise HTTPException(503, "Não foi possível confirmar a identidade do canal.") from None
    finally:
        await adapter.aclose()


def _apply_provider_state(obj, state, *, fallback="CONNECTING"):
    obj.status = state or fallback
    obj.last_error = None
    obj.last_synced_at = utcnow()


async def provision_instance(db, user, connection_id):
    repo.lock_connection(db, connection_id)
    obj = connection(db, user, connection_id, active=True)
    adapter = connector_for(obj, network=True)
    try:
        result = await adapter.create_instance()
    except ConnectorError:
        obj.status, obj.last_error = "ERROR", "Falha ao criar a instância no provedor."
        obj.last_synced_at = utcnow()
        db.flush()
        raise HTTPException(502, "Falha ao criar a instância no provedor.") from None
    finally:
        await adapter.aclose()
    _apply_provider_state(obj, result.state)
    db.flush()
    return schemas.ChatInstanceProvisionResponse(
        created=result.created,
        already_existed=result.already_existed,
        qr_code_base64=result.qr_code_base64,
        pairing_code=result.pairing_code,
        connection=obj,
    )


async def get_pairing(db, user, connection_id):
    repo.lock_connection(db, connection_id)
    obj = connection(db, user, connection_id, active=True)
    adapter = connector_for(obj, network=True)
    try:
        state = await adapter.get_connection_state()
        if state.state == "CONNECTED":
            _apply_provider_state(obj, state.state)
            db.flush()
            return schemas.ChatPairingResponse(
                qr_code_base64=None,
                pairing_code=None,
                state=obj.status,
                connection=obj,
            )
        session = await adapter.get_pairing_session()
    except ConnectorError:
        obj.status, obj.last_error = "ERROR", "Falha ao obter o pareamento no provedor."
        obj.last_synced_at = utcnow()
        db.flush()
        raise HTTPException(502, "Falha ao obter o pareamento no provedor.") from None
    finally:
        await adapter.aclose()
    _apply_provider_state(obj, session.state)
    db.flush()
    return schemas.ChatPairingResponse(
        qr_code_base64=session.qr_code_base64,
        pairing_code=session.pairing_code,
        state=obj.status,
        connection=obj,
    )


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


async def instance_details(db, user, connection_id):
    require(user, "chat:manage_connectors")
    conn = connection(db, user, connection_id, active=True)
    adapter = connector_for(conn, network=True)
    try:
        details = await adapter.get_instance_details()
    except ConnectorError:
        raise HTTPException(502, "Não foi possível consultar os dados da instância.") from None
    finally:
        await adapter.aclose()
    conversations = select(ChatConversation.id).where(
        ChatConversation.connection_id == conn.id,
        ChatConversation.organization_id == user.organization_id,
    )
    return {
        **asdict(details),
        "local_conversation_count": db.scalar(
            select(func.count()).select_from(conversations.subquery())
        ),
        "local_message_count": db.scalar(
            select(func.count(ChatMessage.id)).where(
                ChatMessage.organization_id == user.organization_id,
                ChatMessage.conversation_id.in_(conversations),
            )
        ),
        "last_webhook_at": db.scalar(
            select(func.max(ChatWebhookEvent.created_at)).where(
                ChatWebhookEvent.connection_id == conn.id,
                ChatWebhookEvent.event_type != "HISTORY_MESSAGE",
            )
        ),
    }


async def sync_history(db, user, connection_id, data):
    require(user, "chat:manage_connectors")
    require(user, "chat:view")
    require(user, "chat:link")
    conn = connection(db, user, connection_id, active=True)
    routing = (conn.base_url, conn.external_instance_id, conn.team_id, conn.instance_phone)
    snapshot_at = data.snapshot_at or utcnow()
    if snapshot_at > utcnow():
        raise HTTPException(422, "O limite do histórico não pode estar no futuro.")
    adapter = connector_for(conn, network=True)
    try:
        batch = await adapter.fetch_history(data.page, data.page_size, snapshot_at)
    except ConnectorError:
        raise HTTPException(
            502, "Falha ao consultar o histórico. A página pode ser tentada novamente."
        ) from None
    finally:
        await adapter.aclose()
    # A consulta remota não prende o lock usado por envios e callbacks.
    events = await _enrich_contact_names(conn, batch.events)
    repo.lock_connection(db, connection_id)
    conn = connection(db, user, connection_id, active=True)
    if routing != (conn.base_url, conn.external_instance_id, conn.team_id, conn.instance_phone):
        raise HTTPException(409, "A instância mudou durante a sincronização. Consulte novamente.")
    await _ensure_identity(db, conn)
    counts = _process_events(db, conn, events, history=True)
    return {
        "imported": counts["imported"],
        "existing": counts["existing"],
        "skipped": counts["skipped"],
        "scanned": len(batch.events),
        "total": batch.total,
        "next_page": data.page + 1 if batch.has_more else None,
        "snapshot_at": snapshot_at,
    }


async def create_conversation(db, user, data, *, from_group_participant=False):
    require(user, "chat:view")
    if data.business_document_id:
        require(user, "chat:link")
        document(db, user, data.business_document_id)
    else:
        require(user, "chat:send")
        if not data.contact_id and not from_group_participant:
            raise HTTPException(422, "Selecione um contato para iniciar o atendimento.")
    _validate_parties(db, user.organization_id, data.model_dump())
    repo.lock_connection(db, data.connection_id)
    conn = connection(db, user, data.connection_id, active=True)
    await _ensure_identity(db, conn)
    if data.contact_id:
        contact = db.get(Contact, data.contact_id)
        from controlb.modules.identity.contact_identity import find_contact, lock_contacts
        lock_contacts(db, user.organization_id)
        matched = find_contact(db, user.organization_id, {("PHONE", data.remote_phone): data.remote_phone})
        if not matched or matched.id != contact.id:
            raise HTTPException(422, "O telefone não corresponde ao contato selecionado.")
        data.display_name = contact.name
        db.flush()
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
        if data.contact_id:
            if obj.contact_id and obj.contact_id != data.contact_id:
                raise HTTPException(409, "Este número já está vinculado a outro contato.")
            obj.contact_id = data.contact_id
            obj.display_name = data.display_name
            db.flush()
    else:
        obj = ChatConversation(
            organization_id=user.organization_id,
            connection_id=conn.id,
            team_id=conn.team_id,
            instance_phone=conn.instance_phone,
            external_chat_id=external_id,
            remote_phone=data.remote_phone,
            display_name=data.display_name,
            contact_id=data.contact_id,
            customer_id=data.customer_id,
        )
        db.add(obj)
        db.flush()
    if data.business_document_id:
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


async def open_participant_conversation(db, user, group_id, message_id):
    """Open a direct thread from a trusted stored group sender, without creating a contact."""
    require(user, "chat:send")
    group = conversation(db, user, group_id)
    if not group.is_group:
        raise HTTPException(422, "A conversa de origem não é um grupo.")
    message = db.scalar(select(ChatMessage).where(
        ChatMessage.id == message_id, ChatMessage.conversation_id == group.id,
        ChatMessage.organization_id == user.organization_id,
        ChatMessage.direction == "INBOUND", ChatMessage.deleted_at.is_(None),
    ))
    if message is None:
        raise HTTPException(404, "Participante não encontrado neste grupo.")
    if not message.sender_phone:
        raise HTTPException(422, "WhatsApp não informou o telefone deste participante (somente ID interno).")
    from controlb.modules.identity.contact_identity import find_contact
    contact = find_contact(db, user.organization_id, {("PHONE", message.sender_phone): message.sender_phone})
    data = schemas.ChatConversationCreate(
        connection_id=group.connection_id,
        remote_phone=message.sender_phone,
        display_name=contact.name if contact else message.sender_name or message.sender_phone,
        contact_id=contact.id if contact else None,
    )
    return await create_conversation(db, user, data, from_group_participant=True)


async def start_conversation(db, user, data):
    require(user, "chat:send")
    connection(db, user, data.connection_id, active=True)
    contact = db.scalar(
        select(Contact).where(
            Contact.id == data.contact_id,
            Contact.organization_id == user.organization_id,
            Contact.is_active.is_(True),
        )
    )
    if contact is None:
        raise HTTPException(404, "Contato ativo não encontrado nesta organização.")
    try:
        payload = schemas.ChatConversationCreate(
            connection_id=data.connection_id,
            contact_id=contact.id,
            remote_phone=contact.normalized_phone or contact.phone or contact.mobile or "",
            display_name=contact.name,
        )
    except ValueError:
        raise HTTPException(422, "Cadastre um telefone válido com DDI e DDD no contato.") from None
    # Reutiliza o canal existente; não reabre nem desarquiva sem ação explícita.
    return await create_conversation(db, user, payload)


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
    require(user, "chat:send")
    obj = conversation(db, user, conversation_id)
    repo.lock_connection(db, obj.connection_id)
    obj = conversation(db, user, conversation_id)
    values = data.model_dump(exclude_unset=True)
    if {"contact_id", "customer_id"}.intersection(values):
        require(user, "chat:link")
    if "is_archived" in values and values["is_archived"] is None:
        raise HTTPException(422, "Informe se a conversa está arquivada.")
    if values.get("assigned_user_id") and not repo.is_member(
        db, user.organization_id, values["assigned_user_id"], obj.team_id
    ):
        raise HTTPException(422, "Responsável precisa pertencer à equipe do canal.")
    if values.get("status") == "CLOSED" and obj.status != "CLOSED":
        obj.closed_at, obj.closed_by_id = utcnow(), user.id
    elif values.get("status") == "OPEN":
        obj.closed_at, obj.closed_by_id = None, None
    if "status" in values and values["status"] is None:
        raise HTTPException(422, "Informe o estado da conversa.")
    # Fechar/arquivar não depende de um cadastro associado continuar ativo.
    _validate_parties(db, user.organization_id, values)
    if {"contact_id", "customer_id"}.intersection(values):
        customer_id = values.get("customer_id", obj.customer_id)
        contact_id = values.get("contact_id", obj.contact_id)
        if customer_id and contact_id:
            customer = db.get(Customer, customer_id)
            if customer.contact_id and customer.contact_id != contact_id:
                raise HTTPException(422, "O contato não corresponde ao cliente informado.")
    for key, value in values.items():
        setattr(obj, key, value)
    db.flush()
    if "assigned_user_id" in values:
        db.expire(obj, ["assignee"])
    return obj


def mark_read(db, user, conversation_id):
    obj = conversation(db, user, conversation_id)
    repo.lock_connection(db, obj.connection_id)
    obj = conversation(db, user, conversation_id)
    obj.unread_count = 0
    db.flush()
    return obj


def conversation_contact(db, user, conversation_id):
    obj = conversation(db, user, conversation_id)
    contact = db.scalar(
        select(Contact).where(
            Contact.id == obj.contact_id, Contact.organization_id == user.organization_id
        )
    )
    if contact is None:
        raise HTTPException(404, "Esta conversa ainda não possui um contato vinculado.")
    origin = db.scalar(
        select(ContactOrigin).where(
            ContactOrigin.id == contact.contact_origin_id,
            ContactOrigin.organization_id == user.organization_id,
        )
    )
    return {
        "id": contact.id,
        "name": contact.name,
        "phone": contact.phone,
        "origin_id": origin.id if origin else None,
        "origin_name": origin.name if origin else None,
    }


def update_contact_origin(db, user, conversation_id, data):
    require(user, "chat:send")
    obj = conversation(db, user, conversation_id)
    repo.lock_connection(db, obj.connection_id)
    contact_data = conversation_contact(db, user, conversation_id)
    if not data.model_fields_set or (data.name is not None and data.origin_id is not None):
        raise HTTPException(422, "Selecione uma origem existente ou informe um novo nome.")
    # Mesma ordem de locks do webhook: conexão -> contatos -> origens.
    repo.lock_connection(db, uuid.uuid5(user.organization_id, "whatsapp-contacts"))
    contact = db.get(Contact, contact_data["id"])
    if data.name is not None:
        from controlb.modules.identity.messaging import get_or_create_origin

        origin = get_or_create_origin(db, user.organization_id, data.name)
    elif data.origin_id is not None:
        origin = db.scalar(
            select(ContactOrigin).where(
                ContactOrigin.id == data.origin_id,
                ContactOrigin.organization_id == user.organization_id,
            )
        )
        if origin is None:
            raise HTTPException(422, "Origem inválida para esta organização.")
    else:
        origin = None
    contact.contact_origin_id = origin.id if origin else None
    db.flush()
    return conversation_contact(db, user, conversation_id)


def list_conversations(
    db,
    user,
    *,
    page,
    page_size,
    search=None,
    document_id=None,
    status=None,
    unlinked=False,
    archived=False,
    mine=False,
    assigned_user_id=None,
):
    query = repo.conversations_query(user.organization_id, permissions(user), user.id).where(
        ChatConversation.is_archived.is_(archived)
    )
    if mine:
        query = query.where(ChatConversation.assigned_user_id == user.id)
    elif assigned_user_id:
        query = query.where(ChatConversation.assigned_user_id == assigned_user_id)
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


def notifications(db, user, *, since=None, until=None, page=1):
    """Feed de mensagens novas, sem histórico importado e com a mesma policy do chat."""
    visible = repo.conversations_query(user.organization_id, permissions(user), user.id).where(
        ChatConversation.is_archived.is_(False),
        ChatConversation.connection_id.in_(
            select(ChatConnection.id).where(ChatConnection.is_active.is_(True))
        ),
    )
    visible_ids = visible.with_only_columns(ChatConversation.id)
    unread = db.scalar(
        select(func.coalesce(func.sum(ChatConversation.unread_count), 0)).where(
            ChatConversation.id.in_(visible_ids)
        )
    )
    cutoff = min(until or utcnow(), utcnow())
    if since is None:
        return {"items": [], "unread_count": unread, "until": cutoff, "next_page": None}
    query = (
        select(ChatMessage, ChatConversation)
        .join(ChatConversation, ChatConversation.id == ChatMessage.conversation_id)
        .where(
            ChatMessage.organization_id == user.organization_id,
            ChatMessage.conversation_id.in_(visible_ids),
            ChatMessage.direction == "INBOUND",
            ChatMessage.notify_at >= since,
            ChatMessage.deleted_at.is_(None),
            ChatMessage.notify_at <= cutoff,
        )
        .order_by(ChatMessage.notify_at, ChatMessage.id)
    )
    rows = db.execute(query.offset((page - 1) * 100).limit(101)).all()
    return {
        "items": [
            {
                "id": message.id,
                "conversation_id": conv.id,
                "title": conv.display_name or conv.remote_phone,
                "sender_name": message.sender_name,
                "received_at": message.notify_at,
            }
            for message, conv in rows[:100]
        ],
        "unread_count": unread,
        "until": cutoff,
        "next_page": page + 1 if len(rows) > 100 else None,
    }


def _upsert_group(db, conn, group_id, name=None):
    obj = db.scalar(
        select(ChatConversation).where(
            ChatConversation.organization_id == conn.organization_id,
            ChatConversation.connection_id == conn.id,
            ChatConversation.external_chat_id == group_id,
        )
    )
    if obj is None:
        obj = ChatConversation(
            organization_id=conn.organization_id,
            connection_id=conn.id,
            team_id=conn.team_id,
            instance_phone=conn.instance_phone,
            external_chat_id=group_id,
            remote_phone="",
            is_group=True,
            display_name=(name or f"Grupo {group_id}")[:255],
        )
        db.add(obj)
    elif name and name != f"Grupo {group_id}":
        obj.display_name = name[:255]
    db.flush()
    return obj


async def configure_groups(db, user, connection_id):
    require(user, "chat:manage_connectors")
    base = get_settings().chat_public_base_url
    if not base:
        raise HTTPException(503, "Configure CHAT_PUBLIC_BASE_URL com a URL pública da API.")
    url = f"{schemas.validate_url(base)}/chat/webhooks/{connection_id}"
    repo.lock_connection(db, connection_id)
    conn = connection(db, user, connection_id, active=True)
    await _ensure_identity(db, conn)
    adapter = connector_for(conn, network=True)
    try:
        await adapter.configure_groups(conn.groups_enabled)
        await adapter.configure_webhook(url, _credentials(conn)["webhook_secret"])
        groups = await adapter.fetch_groups() if conn.groups_enabled else []
        for group in groups:
            _upsert_group(db, conn, group["id"], group["name"])
        return {"groups_enabled": conn.groups_enabled, "synced": len(groups)}
    except ConnectorError:
        raise HTTPException(
            502,
            "Não foi possível configurar os grupos no provedor. Confira a conexão e tente novamente.",
        ) from None
    finally:
        await adapter.aclose()


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
        kind_label = {
            "IMAGE": "[Foto]",
            "STICKER": "[Figurinha]",
            "AUDIO": "[Áudio]",
            "VIDEO": "[Vídeo]",
            "DOCUMENT": "[Documento]",
        }.get(message.message_type, f"[{message.message_type}]")
        obj.last_message_preview = (message.content or kind_label)[:500]


async def send_text(db, user, conversation_id, data, *, attachment=None):
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
        if existing.deleted_at:
            raise HTTPException(409, "Esta intenção de envio foi excluída. Não será reenviada.")
        if (
            existing.conversation_id != obj.id
            or existing.content != data.text
            or existing.media_sha256 != (attachment.digest if attachment else None)
        ):
            raise HTTPException(409, "Identificador de envio já usado em outra mensagem.")
        return existing
    if obj.status != "OPEN" or obj.is_archived:
        raise HTTPException(409, "Reabra a conversa antes de enviar.")
    conn = connection(db, user, obj.connection_id, active=True)
    if obj.is_group and not conn.groups_enabled:
        raise HTTPException(409, "Grupos estão desabilitados nesta instância.")
    await _ensure_identity(db, conn)
    if obj.contact_id:
        contact = db.scalar(
            select(Contact).where(
                Contact.id == obj.contact_id, Contact.organization_id == user.organization_id
            )
        )
        if contact:
            obj.display_name = contact.name
            db.flush()
    adapter = connector_for(conn, network=True)

    reply_to = None
    reply_snapshot = None
    quoted = None
    reply_to_id = getattr(data, "reply_to_message_id", None)
    if reply_to_id:
        reply_to = db.scalar(
            select(ChatMessage).where(
                ChatMessage.id == reply_to_id,
                ChatMessage.conversation_id == obj.id,
                ChatMessage.organization_id == user.organization_id,
                ChatMessage.deleted_at.is_(None),
            )
        )
        if reply_to:
            sender_title = reply_to.sender_name or reply_to.author_name or ("Você" if reply_to.direction == "OUTBOUND" else "Contato")
            reply_text = reply_to.content or (
                "[Foto]" if reply_to.message_type == "IMAGE"
                else "[Figurinha]" if reply_to.message_type == "STICKER"
                else f"[{reply_to.message_type}]"
            )
            reply_snapshot = {
                "id": str(reply_to.id),
                "external_message_id": reply_to.external_message_id,
                "text": reply_text[:500],
                "sender_name": sender_title,
                "message_type": reply_to.message_type,
            }
            if reply_to.external_message_id:
                quoted = {
                    "key": {
                        "id": reply_to.external_message_id,
                        "remoteJid": obj.external_chat_id,
                        "fromMe": reply_to.direction == "OUTBOUND",
                    },
                    "message": {
                        "conversation": reply_snapshot["text"],
                    },
                }
                if obj.is_group and reply_to.sender_external_id:
                    quoted["key"]["participant"] = reply_to.sender_external_id

    message = ChatMessage(
        organization_id=user.organization_id,
        conversation_id=obj.id,
        team_id=obj.team_id,
        instance_phone=obj.instance_phone,
        client_request_id=data.client_request_id,
        reply_to_message_id=reply_to.id if reply_to else None,
        reply_snapshot=reply_snapshot,
        direction="OUTBOUND",
        content=data.text,
        message_type=attachment.message_type if attachment else "TEXT",
        media_blob=attachment.content if attachment else None,
        media_sha256=attachment.digest if attachment else None,
        media_filename=attachment.filename if attachment else None,
        media_mime_type=attachment.mime_type if attachment else None,
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
        if obj.status != "OPEN" or obj.is_archived or (obj.is_group and not conn.groups_enabled):
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
            result = (
                await adapter.send_media(
                    obj.external_chat_id if obj.is_group else obj.remote_phone,
                    attachment.content,
                    attachment.mime_type,
                    attachment.filename,
                    data.text,
                    attachment.message_type,
                    quoted=quoted,
                )
                if attachment
                else (
                    await adapter.send_group_text(obj.external_chat_id, data.text, quoted=quoted)
                    if obj.is_group
                    else await adapter.send_text(obj.remote_phone, data.text, quoted=quoted)
                )
            )
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
                if attachment and not echo.deleted_at:
                    echo.media_blob, echo.media_sha256 = attachment.content, attachment.digest
                    echo.media_filename, echo.media_mime_type = (
                        attachment.filename,
                        attachment.mime_type,
                    )
                db.expire(echo, ["author"])
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


async def get_conversation_avatar(db, user, conversation_id):
    require(user, "chat:view")
    obj = conversation(db, user, conversation_id)
    if obj.avatar_blob is not None:
        return ConnectorMedia(obj.avatar_blob, obj.avatar_mime or "image/jpeg")
    if obj.avatar_checked_at and (utcnow() - obj.avatar_checked_at).total_seconds() < 21600:
        return None
    conn = connection(db, user, obj.connection_id, active=True)
    adapter = connector_for(conn, network=True)
    media = None
    try:
        target = obj.external_chat_id if obj.is_group else obj.remote_phone
        media = await adapter.fetch_avatar(target)
    except ConnectorError:
        media = None
    finally:
        await adapter.aclose()
    repo.lock_connection(db, conn.id)
    obj = conversation(db, user, conversation_id)
    obj.avatar_checked_at = utcnow()
    if media:
        obj.avatar_blob = media.content
        obj.avatar_mime = media.mime_type
        obj.avatar_url = f"/api/v1/chat/conversations/{obj.id}/avatar"
    else:
        obj.avatar_blob = None
        obj.avatar_url = None
    db.flush()
    return media


async def send_reaction(db, user, message_id, data):
    require(user, "chat:send")
    message = db.scalar(
        select(ChatMessage).where(
            ChatMessage.id == message_id,
            ChatMessage.organization_id == user.organization_id,
            ChatMessage.deleted_at.is_(None),
        )
    )
    if message is None or not message.external_message_id:
        raise HTTPException(404, "Mensagem não encontrada ou sem identificador no provedor.")
    obj = conversation(db, user, message.conversation_id)
    if obj.status != "OPEN" or obj.is_archived:
        raise HTTPException(409, "Reabra a conversa antes de reagir.")
    conn = connection(db, user, obj.connection_id, active=True)
    existing_req = db.scalar(
        select(ChatReactionRequest).where(
            ChatReactionRequest.id == data.client_request_id,
            ChatReactionRequest.organization_id == user.organization_id,
        )
    )
    if existing_req:
        return message

    repo.lock_connection(db, conn.id)
    obj = conversation(db, user, message.conversation_id)
    if obj.status != "OPEN" or obj.is_archived:
        raise HTTPException(409, "Reabra a conversa antes de reagir.")
    req = ChatReactionRequest(
        id=data.client_request_id,
        organization_id=user.organization_id,
        message_id=message.id,
        user_id=user.id,
        emoji=data.emoji,
        status="PENDING",
    )
    try:
        with db.begin_nested():
            db.add(req)
            db.flush()
    except IntegrityError:
        raise HTTPException(409, "Identificador de requisição já utilizado.") from None
    db.commit()

    repo.lock_connection(db, conn.id)
    conn = connection(db, user, conn.id, active=True)
    message = db.scalar(
        select(ChatMessage).where(
            ChatMessage.id == message_id,
            ChatMessage.organization_id == user.organization_id,
        )
    )
    obj = conversation(db, user, message.conversation_id)
    adapter = connector_for(conn, network=True)
    key = {
        "id": message.external_message_id,
        "remoteJid": obj.external_chat_id,
        "fromMe": message.direction == "OUTBOUND",
    }
    if obj.is_group and message.sender_external_id:
        key["participant"] = message.sender_external_id
    try:
        await adapter.send_reaction(key, data.emoji)
        req.status = "SENT"
    except ConnectorError as exc:
        req.status = "FAILED"
        if exc.status_code and 400 <= exc.status_code < 500 and exc.status_code != 408:
            raise HTTPException(400, "O provedor recusou a reação.")
        raise HTTPException(502, "Não foi possível enviar a reação ao provedor.")
    finally:
        await adapter.aclose()

    reactions = dict(message.reaction_data or {})
    sender_key = f"user:{user.id}"
    if data.emoji:
        reactions[sender_key] = {
            "emoji": data.emoji,
            "user_id": str(user.id),
            "user_name": user.full_name,
            "from_me": True,
        }
    else:
        reactions.pop(sender_key, None)
    message.reaction_data = reactions
    db.flush()
    return message


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


def reconcile_local_metadata(db, conn):
    """Manutenção local idempotente: jamais envia, baixa ou importa mensagens."""
    repo.lock_connection(db, conn.id)
    messages = list(
        db.scalars(
            select(ChatMessage)
            .join(ChatConversation, ChatConversation.id == ChatMessage.conversation_id)
            .where(
                ChatConversation.connection_id == conn.id,
                ChatMessage.organization_id == conn.organization_id,
                ChatMessage.direction == "OUTBOUND",
                ChatMessage.status == "PENDING",
                ChatMessage.external_message_id.is_not(None),
                ChatMessage.client_request_id.is_not(None),
                ChatMessage.created_by_id.is_not(None),
                ChatMessage.error_message.is_(None),
            )
        )
    )
    for message in messages:
        _apply_status(message, "SENT")
    renamed = 0
    for conv in db.scalars(
        select(ChatConversation).where(
            ChatConversation.connection_id == conn.id,
            ChatConversation.organization_id == conn.organization_id,
        )
    ):
        name = db.scalar(
            select(ChatMessage.sender_name)
            .where(
                ChatMessage.organization_id == conn.organization_id,
                ChatMessage.conversation_id == conv.id,
                ChatMessage.direction == "INBOUND",
                ChatMessage.sender_name.is_not(None),
                ChatMessage.sender_name != "",
                ChatMessage.sender_name != conv.remote_phone,
            )
            .order_by(ChatMessage.occurred_at.desc())
            .limit(1)
        )
        if name:
            previous = conv.display_name
            _update_instance_contact(db, conn, conv.remote_phone, name)
            renamed += int(previous != conv.display_name)
    db.flush()
    return {"accepted_messages": len(messages), "renamed_conversations": renamed}


def _update_instance_contact(db, conn, phone, name, *, force=False):
    from controlb.modules.identity.messaging import update_whatsapp_name

    repo.lock_connection(db, uuid.uuid5(conn.organization_id, "whatsapp-contacts"))
    conversations = list(
        db.scalars(
            select(ChatConversation).where(
                ChatConversation.organization_id == conn.organization_id,
                ChatConversation.connection_id == conn.id,
                ChatConversation.remote_phone == phone,
            )
        )
    )
    for conv in conversations:
        contact = db.scalar(
            select(Contact).where(
                Contact.id == conv.contact_id, Contact.organization_id == conn.organization_id
            )
        )
        if contact:
            update_whatsapp_name(contact, phone, name, force=force)
            conv.display_name = contact.name
            if force:
                # A atualização explícita muda o nome exibido, mas mantém a proteção manual.
                contact.name_manually_set = True
    db.flush()


async def refresh_contact(db, user, conversation_id, *, replace_manual=False):
    require(user, "chat:send")
    obj = conversation(db, user, conversation_id)
    conn = connection(db, user, obj.connection_id, active=True)
    routing = (conn.base_url, conn.external_instance_id, conn.team_id, conn.instance_phone)
    if obj.is_group:
        adapter = connector_for(conn, network=True)
        try:
            name = await asyncio.wait_for(adapter.fetch_group_name(obj.external_chat_id), timeout=8)
        except (ConnectorError, TimeoutError):
            raise HTTPException(
                502, "Nome do grupo indisponível no provedor. Tente atualizar novamente."
            ) from None
        finally:
            await adapter.aclose()
    else:
        _, name = await _lookup_contact_name(conn, obj.remote_phone)
    repo.lock_connection(db, conn.id)
    conn = connection(db, user, conn.id, active=True)
    obj = conversation(db, user, conversation_id)
    if routing != (conn.base_url, conn.external_instance_id, conn.team_id, conn.instance_phone):
        raise HTTPException(409, "A instância mudou. Consulte novamente.")
    if obj.is_group:
        if name:
            obj.display_name = name
            db.flush()
        return obj
    if not name:
        name = db.scalar(
            select(ChatMessage.sender_name)
            .where(
                ChatMessage.organization_id == user.organization_id,
                ChatMessage.conversation_id == obj.id,
                ChatMessage.direction == "INBOUND",
                ChatMessage.sender_name.is_not(None),
                ChatMessage.sender_name != "",
            )
            .order_by(ChatMessage.occurred_at.desc())
            .limit(1)
        )
    if name:
        _update_instance_contact(db, conn, obj.remote_phone, name, force=replace_manual)
    return obj


async def _lookup_contact_name(conn, phone):
    try:
        adapter = connector_for(conn, network=True)
    except HTTPException:
        # A agenda é acessória: indisponibilidade/configuração não descarta o webhook.
        return False, None
    try:
        return True, await asyncio.wait_for(adapter.fetch_contact_name(phone), timeout=3)
    except (ConnectorError, TimeoutError):
        # Falha opcional de agenda nunca deve impedir recebimento/envio.
        return False, None
    finally:
        await adapter.aclose()


async def _enrich_contact_names(conn, events):
    if any(event.external_instance_id != conn.external_instance_id for event in events):
        raise HTTPException(403, "Instância do webhook não corresponde à conexão.")
    semaphore = asyncio.Semaphore(5)

    async def lookup(phone):
        async with semaphore:
            return phone, await _lookup_contact_name(conn, phone)

    names = dict(
        await asyncio.gather(
            *(
                lookup(phone)
                for phone in {
                    event.message.remote_phone
                    for event in events
                    if event.message and not event.message.is_group
                }
            )
        )
    )
    return [
        replace(
            event,
            message=replace(
                event.message,
                contact_lookup_done=names[event.message.remote_phone][0],
                contact_name=names[event.message.remote_phone][1],
            ),
        )
        if event.message and not event.message.is_group
        else event
        for event in events
    ]


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
    await _ensure_identity(db, conn)
    # O nome recebido no payload é imediato; agenda é consultada apenas na sincronização explícita.
    return _process_events(db, conn, events)


def _process_events(db, conn, events, *, history=False):
    if any(event.external_instance_id != conn.external_instance_id for event in events):
        raise HTTPException(403, "Instância do webhook não corresponde à conexão.")
    processed = 0
    imported = skipped = existing = 0
    for event in events:
        inbox = db.scalar(
            select(ChatWebhookEvent).where(
                ChatWebhookEvent.connection_id == conn.id,
                ChatWebhookEvent.event_key == event.event_key,
            )
        )
        replay = inbox is not None and inbox.status != "IGNORED"
        if replay and not event.message:
            if history:
                skipped += 1
            continue
        # Guardar só dados normalizados; callbacks Evolution incluem apikey no corpo.
        normalized = asdict(event)
        normalized.pop("raw_payload", None)
        if normalized["message"]:
            normalized["message"]["occurred_at"] = event.message.occurred_at.isoformat()
        if inbox is None:
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
        else:
            inbox.payload = normalized
            inbox.attempts += 1
        if event.connection_state:
            conn.status, conn.last_synced_at = event.connection_state, utcnow()
            conn.recovery_pending = True
            inbox.status = "PROCESSED"
        if event.contact_phone and event.contact_name:
            _update_instance_contact(db, conn, event.contact_phone, event.contact_name)
            inbox.status = "PROCESSED"
        if event.group_id and conn.groups_enabled:
            _upsert_group(db, conn, event.group_id, event.group_name)
            inbox.status = "PROCESSED"
        if event.reaction:
            target_id = event.reaction.get("target_message_id")
            if target_id:
                query = (
                    select(ChatMessage)
                    .join(ChatConversation, ChatConversation.id == ChatMessage.conversation_id)
                    .where(
                        ChatMessage.organization_id == conn.organization_id,
                        ChatConversation.connection_id == conn.id,
                        ChatMessage.external_message_id == target_id,
                    )
                )
                if event.reaction.get("target_chat_id"):
                    query = query.where(ChatConversation.external_chat_id == event.reaction["target_chat_id"])
                target_msg = db.scalar(query)
                if target_msg:
                    reactions = dict(target_msg.reaction_data or {})
                    sender_key = str(event.reaction.get("sender_external_id") or event.reaction.get("sender_phone") or "remote")
                    emoji = event.reaction.get("emoji")
                    if emoji:
                        reactions[sender_key] = {
                            "emoji": emoji,
                            "sender": sender_key,
                            "from_me": event.reaction.get("from_me", False),
                        }
                    else:
                        reactions.pop(sender_key, None)
                    target_msg.reaction_data = reactions
                    inbox.status = "PROCESSED"
                else:
                    inbox.status = "PENDING"
        if event.message:
            incoming = event.message
            from controlb.modules.chat.audio import initial_status
            from controlb.modules.identity.messaging import upsert_whatsapp_contact

            if incoming.is_group and not conn.groups_enabled:
                inbox.status = "IGNORED"
                skipped += 1
                db.flush()
                continue
            contact = None
            if not incoming.is_group:
                if incoming.direction == "INBOUND":
                    contact = upsert_whatsapp_contact(db, conn, incoming)
                else:
                    from controlb.modules.identity.contact_identity import find_contact
                    contact = find_contact(db, conn.organization_id,
                                           {("PHONE", incoming.remote_phone): incoming.remote_phone})
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
                    team_id=conn.team_id,
                    instance_phone=conn.instance_phone,
                    external_chat_id=incoming.external_chat_id,
                    remote_phone=incoming.remote_phone,
                    is_group=incoming.is_group,
                    display_name=(incoming.group_name or f"Grupo {incoming.external_chat_id}")[:255]
                    if incoming.is_group
                    else (contact.name if contact else incoming.contact_name or incoming.remote_phone),
                    contact_id=contact.id if contact else None,
                )
                db.add(obj)
                db.flush()
            if contact:
                obj.contact_id = contact.id
                obj.display_name = contact.name
            elif incoming.group_name:
                obj.display_name = incoming.group_name[:255]
            message = repo.get_external_message(
                db, conn.organization_id, obj.id, incoming.external_message_id
            )
            if (
                (message and message.deleted_at)
                or (obj.cleared_before and incoming.occurred_at <= obj.cleared_before)
                or (obj.deleted_at and history)
            ):
                inbox.payload = {
                    "external_message_id": incoming.external_message_id,
                    "external_chat_id": incoming.external_chat_id,
                    "locally_deleted": True,
                }
                inbox.status = "PROCESSED"
                skipped += 1
                db.flush()
                continue
            if obj.deleted_at and not history:
                obj.deleted_at = None
            if message is None:
                imported += 1
                reply_to_id = None
                reply_snapshot = None
                if incoming.reply and incoming.reply.get("external_message_id"):
                    ref_ext_id = incoming.reply["external_message_id"]
                    ref_msg = repo.get_external_message(db, conn.organization_id, obj.id, ref_ext_id)
                    if ref_msg:
                        reply_to_id = ref_msg.id
                        reply_snapshot = {
                            "id": str(ref_msg.id),
                            "external_message_id": ref_msg.external_message_id,
                            "text": (ref_msg.content or (
                                "[Foto]" if ref_msg.message_type == "IMAGE"
                                else "[Figurinha]" if ref_msg.message_type == "STICKER"
                                else f"[{ref_msg.message_type}]"
                            ))[:500],
                            "sender_name": ref_msg.sender_name or ref_msg.author_name or ("Você" if ref_msg.direction == "OUTBOUND" else "Contato"),
                            "message_type": ref_msg.message_type,
                        }
                    else:
                        reply_snapshot = {
                            "id": None,
                            "external_message_id": ref_ext_id,
                            "text": incoming.reply.get("text"),
                            "sender_name": incoming.reply.get("participant") or "Contato",
                            "message_type": "TEXT",
                        }

                message = ChatMessage(
                    organization_id=conn.organization_id,
                    conversation_id=obj.id,
                    team_id=conn.team_id,
                    instance_phone=conn.instance_phone,
                    external_message_id=incoming.external_message_id,
                    reply_to_message_id=reply_to_id,
                    reply_snapshot=reply_snapshot,
                    direction=incoming.direction,
                    content=incoming.content,
                    message_type=incoming.message_type,
                    media_mime_type=incoming.media_mime_type,
                    media_filename=incoming.media_filename,
                    occurred_at=incoming.occurred_at,
                    sender_name=incoming.sender_name,
                    sender_phone=incoming.sender_phone
                    or (incoming.remote_phone if not incoming.is_group else None),
                    sender_external_id=incoming.sender_external_id,
                    notify_at=utcnow() if incoming.direction == "INBOUND" and not history else None,
                    status="RECEIVED" if incoming.direction == "INBOUND" else "SENT",
                    transcription_status=initial_status(conn.transcription_enabled)
                    if incoming.message_type == "AUDIO"
                    else "NOT_REQUESTED",
                )
                db.add(message)
                if incoming.direction == "INBOUND" and not history:
                    obj.unread_count += 1
                _preview(obj, message)
                db.flush()
                _apply_pending_statuses(db, conn, message)
            else:
                existing += 1
                if incoming.direction == "OUTBOUND":
                    _apply_status(message, "SENT")
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
        if not event.message and history:
            skipped += 1
        db.flush()
        processed += int(not replay)
    return {
        "accepted": True,
        "events": processed,
        "imported": imported,
        "existing": existing,
        "skipped": skipped,
    }
