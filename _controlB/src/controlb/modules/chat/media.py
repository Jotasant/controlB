"""Mídias autenticadas e exclusão local, sem URLs fornecidas pelo cliente."""

import hashlib
import re
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import or_, select, update

from controlb.modules.chat import repository as repo
from controlb.modules.chat import service
from controlb.modules.chat.connectors.base import ConnectorError, ConnectorMedia
from controlb.modules.chat.models import ChatMessage, ChatWebhookEvent, utcnow

MAX_BYTES = 20 * 1024 * 1024
MEDIA_TYPES = {"IMAGE", "VIDEO", "DOCUMENT", "AUDIO", "STICKER"}
INLINE = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "video/mp4",
    "video/webm",
    "audio/ogg",
    "audio/mpeg",
    "audio/mp4",
    "audio/wav",
    "audio/webm",
    "audio/aac",
}


def safe_filename(value):
    return re.sub(r'[\x00-\x1f\x7f/\\:"<>|?*]', "_", value or "anexo")[:180].strip() or "anexo"


def verified_mime(content, declared):
    """Somente formatos passivos reconhecidos podem ser exibidos inline."""
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content[:6] in {b"GIF87a", b"GIF89a"}:
        return "image/gif"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    if content[:4] == b"RIFF" and content[8:12] == b"WAVE":
        return "audio/wav"
    if len(content) >= 12 and content[4:8] == b"ftyp":
        return "audio/mp4" if declared == "audio/mp4" else "video/mp4"
    if content.startswith(b"\x1aE\xdf\xa3"):
        return "audio/webm" if declared == "audio/webm" else "video/webm"
    if content.startswith(b"OggS"):
        return "audio/ogg"
    if content.startswith(b"ID3") or content[:2] in {b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"}:
        return "audio/mpeg"
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    if (declared or "").startswith("audio/"):
        return declared.split(";")[0].strip().lower()
    return "application/octet-stream"


@dataclass(frozen=True)
class Attachment:
    content: bytes
    filename: str
    mime_type: str
    message_type: str
    digest: str


def attachment(content, filename, declared):
    if not content or len(content) > MAX_BYTES:
        raise HTTPException(413, "Envie um arquivo não vazio de até 20 MiB.")
    filename = safe_filename(filename)
    mime = verified_mime(content, (declared or "").split(";")[0].lower())
    kind = (
        "IMAGE"
        if mime.startswith("image/")
        else "VIDEO"
        if mime.startswith("video/")
        else "AUDIO"
        if mime.startswith("audio/")
        else "DOCUMENT"
    )
    digest = hashlib.sha256(content + b"\0" + filename.encode() + b"\0" + mime.encode()).hexdigest()
    return Attachment(content, filename, mime, kind, digest)


def authorized(db, user, message_id, *, include_deleted=False):
    service.require(user, "chat:view")
    message = db.scalar(
        select(ChatMessage)
        .where(ChatMessage.id == message_id, ChatMessage.organization_id == user.organization_id)
        .execution_options(populate_existing=True)
    )
    if message is None or (message.deleted_at and not include_deleted):
        raise HTTPException(404, "Mensagem não encontrada.")
    conv = service.conversation(db, user, message.conversation_id)
    conn = service.connection(db, user, conv.connection_id, active=True)
    return message, conv, conn


async def download(db, user, message_id):
    message, conv, conn = authorized(db, user, message_id)
    if message.message_type not in MEDIA_TYPES:
        raise HTTPException(422, "Esta mensagem não contém mídia.")
    routing = (conn.base_url, conn.external_instance_id, conn.instance_phone)
    if message.media_blob is not None:
        return ConnectorMedia(
            message.media_blob,
            verified_mime(message.media_blob, message.media_mime_type),
            safe_filename(message.media_filename),
        )
    if not message.external_message_id:
        raise HTTPException(404, "Mídia sem identificador do provedor.")
    adapter = service.connector_for(conn, network=True)
    try:
        result = await adapter.fetch_media(
            message.external_message_id,
            conv.external_chat_id,
            from_me=message.direction == "OUTBOUND",
            participant=message.sender_external_id if conv.is_group else None,
        )
    except ConnectorError:
        raise HTTPException(
            502, "Mídia indisponível no WhatsApp ou acima de 20 MiB. O arquivo pode ter expirado."
        ) from None
    finally:
        await adapter.aclose()
    repo.lock_connection(db, conn.id)
    message, conv, conn = authorized(db, user, message_id)
    if routing != (conn.base_url, conn.external_instance_id, conn.instance_phone):
        raise HTTPException(409, "A instância mudou durante a consulta.")
    if not result.content or len(result.content) > MAX_BYTES:
        raise HTTPException(413, "Arquivo excede 20 MiB.")
    mime = verified_mime(result.content, result.mime_type)
    message.media_blob = result.content
    message.media_mime_type = mime
    message.media_filename = safe_filename(
        message.media_filename or result.filename or f"{message.message_type.lower()}-{message.id}"
    )
    db.flush()
    return ConnectorMedia(result.content, mime, message.media_filename)


def gallery(db, user, conversation_id, *, page, page_size, search=None, kind=None):
    conv = service.conversation(db, user, conversation_id)
    query = select(ChatMessage).where(
        ChatMessage.organization_id == user.organization_id,
        ChatMessage.conversation_id == conv.id,
        ChatMessage.deleted_at.is_(None),
        ChatMessage.message_type.in_(MEDIA_TYPES),
    )
    if kind:
        query = query.where(ChatMessage.message_type == kind)
    if search:
        query = query.where(
            or_(
                ChatMessage.content.icontains(search, autoescape=True),
                ChatMessage.media_filename.icontains(search, autoescape=True),
                ChatMessage.sender_name.icontains(search, autoescape=True),
            )
        )
    return repo.page(
        db, query.order_by(ChatMessage.occurred_at.desc(), ChatMessage.id.desc()), page, page_size
    )


def _clear(message, user):
    message.deleted_at = utcnow()
    message.deleted_by_id = user.id
    message.content = message.media_blob = message.media_url = message.media_filename = (
        message.media_mime_type
    ) = None
    message.transcription = message.error_message = message.notify_at = None
    message.transcription_status = "NOT_REQUESTED"
    message.provider_payload = {}


def _scrub_events(db, conv, external_id=None):
    query = select(ChatWebhookEvent).where(
        ChatWebhookEvent.organization_id == conv.organization_id,
        ChatWebhookEvent.connection_id == conv.connection_id,
        ChatWebhookEvent.payload["external_chat_id"].as_string() == conv.external_chat_id,
    )
    if external_id:
        query = query.where(
            ChatWebhookEvent.payload["external_message_id"].as_string() == external_id
        )
    for event in db.scalars(query):
        event.payload = {"locally_deleted": True}


async def delete_message(db, user, message_id, *, everyone=False):
    service.require(user, "chat:send")
    message, conv, conn = authorized(db, user, message_id, include_deleted=True)
    repo.lock_connection(db, conn.id)
    message, conv, conn = authorized(db, user, message_id, include_deleted=True)
    if everyone:
        if message.revoke_status == "CONFIRMED":
            return {"deleted": True, "scope": "WHATSAPP"}
        if message.direction != "OUTBOUND" or not message.external_message_id or message.deleted_at:
            raise HTTPException(
                409,
                "Somente mensagens enviadas e ainda disponíveis podem ser apagadas no WhatsApp.",
            )
        if message.created_by_id != user.id:
            service.require(user, "chat:manage_connectors")
        if message.revoke_status == "PENDING":
            raise HTTPException(
                409, "Exclusão sem confirmação. Confira no WhatsApp antes de tentar novamente."
            )
        message.revoke_status = "PENDING"
        db.commit()
        repo.lock_connection(db, conn.id)
        message, conv, conn = authorized(db, user, message_id)
        adapter = service.connector_for(conn, network=True)
        try:
            await adapter.delete_for_everyone(
                message.external_message_id,
                conv.external_chat_id,
                participant=message.sender_external_id if conv.is_group else None,
            )
        except ConnectorError as exc:
            message.revoke_status = (
                "FAILED"
                if exc.status_code and 400 <= exc.status_code < 500 and exc.status_code != 408
                else "PENDING"
            )
            db.flush()
            return {
                "deleted": False,
                "scope": "WHATSAPP",
                "error": "O provedor não confirmou a exclusão. Prazo/permissões do WhatsApp podem impedir a operação.",
                "status": message.revoke_status,
            }
        finally:
            await adapter.aclose()
        message.revoke_status = "CONFIRMED"
    if not message.deleted_at:
        _clear(message, user)
        _scrub_events(db, conv, message.external_message_id)
        db.flush()
        latest = db.scalar(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conv.id, ChatMessage.deleted_at.is_(None))
            .order_by(ChatMessage.occurred_at.desc(), ChatMessage.id.desc())
            .limit(1)
        )
        conv.last_message_at = latest.occurred_at if latest else None
        conv.last_message_preview = (
            (latest.content or f"[{latest.message_type}]")[:500] if latest else None
        )
    return {"deleted": True, "scope": "WHATSAPP" if everyone else "LOCAL"}


def delete_channel(db, user, conversation_id):
    service.require(user, "chat:send")
    conv = service.conversation(db, user, conversation_id)
    repo.lock_connection(db, conv.connection_id)
    conv = service.conversation(db, user, conversation_id)
    now = utcnow()
    db.execute(
        update(ChatMessage)
        .where(
            ChatMessage.conversation_id == conv.id,
            ChatMessage.organization_id == user.organization_id,
        )
        .values(
            deleted_at=now,
            deleted_by_id=user.id,
            content=None,
            media_blob=None,
            media_url=None,
            media_filename=None,
            media_mime_type=None,
            transcription=None,
            transcription_status="NOT_REQUESTED",
            provider_payload={},
            error_message=None,
            notify_at=None,
        )
    )
    _scrub_events(db, conv)
    conv.deleted_at = conv.cleared_before = now
    conv.last_message_preview = conv.last_message_at = None
    conv.unread_count = 0
    db.flush()
    return {"deleted": True, "scope": "LOCAL"}
