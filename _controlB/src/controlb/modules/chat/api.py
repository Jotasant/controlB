"""API do Chat e entrada autenticada dos webhooks dos conectores."""

import asyncio
import json
import uuid
from types import SimpleNamespace
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import AwareDatetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from controlb.db import get_db
from controlb.modules.chat import repository as repo
from controlb.modules.chat import schemas, service
from controlb.modules.chat.connectors.registry import available_providers
from controlb.modules.chat.models import ChatConnection, ChatTeam
from controlb.modules.identity.models import User
from controlb.modules.identity.security import require_permission

router = APIRouter(prefix="/chat", tags=["Chat"])
DB = Annotated[Session, Depends(get_db)]
Viewer = Annotated[User, Depends(require_permission("chat:view"))]
Manager = Annotated[User, Depends(require_permission("chat:manage_connectors"))]
Page = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


@router.get("/messages/{message_id}/media")
def download_media(message_id: uuid.UUID, db: DB, user: Viewer):
    from controlb.modules.chat import media

    result = asyncio.run(media.download(db, user, message_id))
    disposition = "inline" if result.mime_type in media.INLINE else "attachment"
    return Response(
        content=result.content,
        media_type=result.mime_type,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox; default-src 'none'",
            "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(result.filename or 'anexo', safe='')}",
        },
    )


@router.get("/conversations/{conversation_id}/media", response_model=schemas.MessagePage)
def gallery(
    conversation_id: uuid.UUID,
    db: DB,
    user: Viewer,
    page: Page = 1,
    page_size: PageSize = 24,
    search: Annotated[str | None, Query(max_length=255)] = None,
    kind: Annotated[str | None, Query(pattern="^(IMAGE|VIDEO|AUDIO|DOCUMENT|STICKER)$")] = None,
):
    from controlb.modules.chat import media

    return media.gallery(
        db, user, conversation_id, page=page, page_size=page_size, search=search, kind=kind
    )


@router.post("/conversations/{conversation_id}/media", response_model=schemas.ChatMessageResponse)
async def send_media(
    conversation_id: uuid.UUID,
    request: Request,
    db: DB,
    user: Viewer,
    client_request_id: uuid.UUID,
    filename: Annotated[str, Query(max_length=180)],
    caption: Annotated[str, Query(max_length=4096)] = "",
):
    from controlb.modules.chat import media

    service.require(user, "chat:send")
    await run_in_threadpool(lambda: service.conversation(db, user, conversation_id))
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > media.MAX_BYTES:
            raise HTTPException(413, "Anexo excede o limite de 20 MiB.")
    upload = media.attachment(bytes(body), filename, request.headers.get("content-type"))
    return await run_in_threadpool(
        lambda: asyncio.run(
            service.send_text(
                db,
                user,
                conversation_id,
                SimpleNamespace(client_request_id=client_request_id, text=caption.strip()),
                attachment=upload,
            )
        )
    )


@router.delete("/messages/{message_id}")
def delete_local_message(message_id: uuid.UUID, db: DB, user: Viewer):
    from controlb.modules.chat import media

    return asyncio.run(media.delete_message(db, user, message_id))


@router.post("/messages/{message_id}/delete-for-everyone")
def delete_for_everyone(message_id: uuid.UUID, db: DB, user: Viewer):
    from controlb.modules.chat import media

    return asyncio.run(media.delete_message(db, user, message_id, everyone=True))


@router.delete("/conversations/{conversation_id}")
def delete_local_channel(conversation_id: uuid.UUID, db: DB, user: Viewer):
    from controlb.modules.chat import media

    return media.delete_channel(db, user, conversation_id)


@router.get("/notifications")
def notifications(
    db: DB,
    user: Viewer,
    response: Response,
    since: AwareDatetime | None = None,
    until: AwareDatetime | None = None,
    page: Page = 1,
):
    response.headers["Cache-Control"] = "no-store"
    return service.notifications(db, user, since=since, until=until, page=page)


@router.post("/connections/{connection_id}/groups")
def configure_groups(connection_id: uuid.UUID, db: DB, user: Manager):
    return asyncio.run(service.configure_groups(db, user, connection_id))


@router.get("/audio/runtime")
def audio_runtime(user: Manager):
    from controlb.config import get_settings
    from controlb.modules.chat.audio import transcription_ready

    return {
        "configured": transcription_ready(),
        "worker_enabled": get_settings().chat_audio_worker_enabled,
    }


@router.get("/messages/{message_id}/audio")
def message_audio(message_id: uuid.UUID, db: DB, user: Viewer):
    from controlb.modules.chat.audio import download

    media = asyncio.run(download(db, user, message_id))
    return Response(
        content=media.content,
        media_type=media.mime_type,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": 'inline; filename="audio"',
        },
    )


@router.get("/messages/{message_id}/transcription", response_model=schemas.ChatMessageResponse)
def message_transcription(message_id: uuid.UUID, db: DB, user: Viewer):
    from controlb.modules.chat.audio import authorized_message

    message, _, _ = authorized_message(db, user, message_id)
    return message


@router.post(
    "/messages/{message_id}/transcribe", response_model=schemas.ChatMessageResponse, status_code=202
)
def transcribe_message(message_id: uuid.UUID, db: DB, user: Viewer):
    from controlb.modules.chat.audio import queue_transcription

    return queue_transcription(db, user, message_id)


@router.get("/providers")
def providers(user: Manager):
    return [
        {"code": code, "name": "Evolution API" if code == "EVOLUTION" else code}
        for code in available_providers()
    ]


@router.get("/teams")
def teams(db: DB, user: Manager):
    return [
        dict(row._mapping)
        for row in db.execute(
            select(ChatTeam.id, ChatTeam.name)
            .where(ChatTeam.id.in_(repo.member_teams(user.organization_id, user.id)))
            .order_by(ChatTeam.name)
        )
    ]


@router.get("/eligible-users")
def eligible_users(db: DB, user: Manager):
    return [
        dict(row._mapping)
        for row in db.execute(
            select(User.id, User.full_name)
            .where(User.organization_id == user.organization_id, User.is_active.is_(True))
            .order_by(User.full_name)
        )
    ]


@router.get("/channels")
def channels(db: DB, user: Viewer):
    rows = db.execute(
        select(
            ChatConnection.id,
            ChatConnection.name,
            ChatConnection.provider,
            ChatConnection.status,
            ChatConnection.team_id,
            ChatConnection.instance_phone,
        )
        .where(
            ChatConnection.organization_id == user.organization_id,
            ChatConnection.is_active.is_(True),
            ChatConnection.team_id.in_(repo.member_teams(user.organization_id, user.id)),
        )
        .order_by(ChatConnection.name)
    )
    return [dict(row._mapping) for row in rows]


@router.get("/connections", response_model=list[schemas.ChatConnectionResponse])
def connections(db: DB, user: Manager, page: Page = 1, page_size: PageSize = 50):
    return list(
        db.scalars(
            select(ChatConnection)
            .where(
                ChatConnection.organization_id == user.organization_id,
                (ChatConnection.team_id.in_(repo.member_teams(user.organization_id, user.id)))
                | ChatConnection.team_id.is_(None)
                | ChatConnection.team_id.not_in(repo.configured_teams()),
            )
            .order_by(ChatConnection.name, ChatConnection.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )


@router.post("/connections", response_model=schemas.ChatConnectionResponse, status_code=201)
def create_connection(data: schemas.ChatConnectionCreate, db: DB, user: Manager):
    return service.create_connection(db, user, data)


@router.get("/connections/{connection_id}", response_model=schemas.ChatConnectionResponse)
def get_connection(connection_id: uuid.UUID, db: DB, user: Manager):
    return service.connection(db, user, connection_id, allow_unassigned=True)


@router.patch("/connections/{connection_id}", response_model=schemas.ChatConnectionResponse)
def update_connection(
    connection_id: uuid.UUID, data: schemas.ChatConnectionUpdate, db: DB, user: Manager
):
    return asyncio.run(service.update_connection(db, user, connection_id, data))


# Sessão SQLAlchemy síncrona e locks ficam no threadpool do FastAPI. O adaptador
# tem seu próprio loop por operação, sem bloquear o loop HTTP durante locks SQL.
@router.post("/connections/{connection_id}/check", response_model=schemas.ChatConnectionResponse)
def check_connection(connection_id: uuid.UUID, db: DB, user: Manager):
    return asyncio.run(service.check_connection(db, user, connection_id))


@router.post(
    "/connections/{connection_id}/instance", response_model=schemas.ChatInstanceProvisionResponse
)
def provision_instance(connection_id: uuid.UUID, db: DB, user: Manager, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return asyncio.run(service.provision_instance(db, user, connection_id))


@router.post("/connections/{connection_id}/pairing", response_model=schemas.ChatPairingResponse)
def pairing(connection_id: uuid.UUID, db: DB, user: Manager, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return asyncio.run(service.get_pairing(db, user, connection_id))


@router.post("/connections/{connection_id}/webhook")
def configure_webhook(connection_id: uuid.UUID, db: DB, user: Manager):
    return asyncio.run(service.configure_webhook(db, user, connection_id))


@router.get(
    "/connections/{connection_id}/details", response_model=schemas.ChatInstanceDetailsResponse
)
def instance_details(connection_id: uuid.UUID, db: DB, user: Manager, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return asyncio.run(service.instance_details(db, user, connection_id))


@router.post("/connections/{connection_id}/sync", response_model=schemas.ChatHistoryResponse)
def sync_history(connection_id: uuid.UUID, data: schemas.ChatHistoryRequest, db: DB, user: Manager):
    return asyncio.run(service.sync_history(db, user, connection_id, data))


@router.post(
    "/conversations/start", response_model=schemas.ChatConversationResponse, status_code=201
)
def start_conversation(data: schemas.ChatConversationStart, db: DB, user: Viewer):
    return asyncio.run(service.start_conversation(db, user, data))


@router.post("/conversations/{conversation_id}/participants/{message_id}/direct",
             response_model=schemas.ChatConversationResponse)
def open_participant(conversation_id: uuid.UUID, message_id: uuid.UUID, db: DB, user: Viewer):
    return asyncio.run(service.open_participant_conversation(db, user, conversation_id, message_id))


@router.post("/conversations", response_model=schemas.ChatConversationResponse, status_code=201)
def create_conversation(data: schemas.ChatConversationCreate, db: DB, user: Viewer):
    return asyncio.run(service.create_conversation(db, user, data))


@router.get("/conversations", response_model=schemas.ConversationPage)
def conversations(
    db: DB,
    user: Viewer,
    page: Page = 1,
    page_size: PageSize = 30,
    search: Annotated[str | None, Query(max_length=255)] = None,
    document_id: uuid.UUID | None = None,
    status: Annotated[str | None, Query(pattern="^(OPEN|CLOSED)$")] = None,
    unlinked: bool = False,
    archived: bool = False,
    mine: bool = False,
    assigned_user_id: uuid.UUID | None = None,
):
    return service.list_conversations(
        db,
        user,
        page=page,
        page_size=page_size,
        search=search,
        document_id=document_id,
        status=status,
        unlinked=unlinked,
        archived=archived,
        mine=mine,
        assigned_user_id=assigned_user_id,
    )


@router.get("/conversations/{conversation_id}", response_model=schemas.ChatConversationResponse)
def get_conversation(conversation_id: uuid.UUID, db: DB, user: Viewer):
    return service.conversation(db, user, conversation_id)


@router.patch("/conversations/{conversation_id}", response_model=schemas.ChatConversationResponse)
def update_conversation(
    conversation_id: uuid.UUID, data: schemas.ChatConversationUpdate, db: DB, user: Viewer
):
    return service.update_conversation(db, user, conversation_id, data)


@router.post("/conversations/{conversation_id}/links", response_model=schemas.ChatLinkResponse)
def link_conversation(
    conversation_id: uuid.UUID, data: schemas.ChatConversationLinkCreate, db: DB, user: Viewer
):
    return service.link_conversation(db, user, conversation_id, data)


@router.get("/conversations/{conversation_id}/contact")
def conversation_contact(conversation_id: uuid.UUID, db: DB, user: Viewer):
    return service.conversation_contact(db, user, conversation_id)


@router.post(
    "/conversations/{conversation_id}/refresh-contact",
    response_model=schemas.ChatConversationResponse,
)
def refresh_contact(conversation_id: uuid.UUID, db: DB, user: Viewer, replace_manual: bool = False):
    return asyncio.run(
        service.refresh_contact(db, user, conversation_id, replace_manual=replace_manual)
    )


@router.patch("/conversations/{conversation_id}/contact-origin")
def update_contact_origin(
    conversation_id: uuid.UUID, data: schemas.ChatContactOriginUpdate, db: DB, user: Viewer
):
    return service.update_contact_origin(db, user, conversation_id, data)


@router.post(
    "/conversations/{conversation_id}/read", response_model=schemas.ChatConversationResponse
)
def mark_read(conversation_id: uuid.UUID, db: DB, user: Viewer):
    """Zera os não lidos da caixa compartilhada local; não envia recibo ao WhatsApp."""
    return service.mark_read(db, user, conversation_id)


@router.get("/conversations/{conversation_id}/avatar")
def conversation_avatar(conversation_id: uuid.UUID, db: DB, user: Viewer):
    media = asyncio.run(service.get_conversation_avatar(db, user, conversation_id))
    if not media or not media.content:
        raise HTTPException(404, "Avatar não disponível para esta conversa.")
    return Response(
        content=media.content,
        media_type=media.mime_type or "image/jpeg",
        headers={
            "Cache-Control": "public, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/conversations/{conversation_id}/messages", response_model=schemas.MessagePage)
def messages(
    conversation_id: uuid.UUID, db: DB, user: Viewer, page: Page = 1, page_size: PageSize = 50
):
    return service.list_messages(db, user, conversation_id, page=page, page_size=page_size)


@router.post(
    "/conversations/{conversation_id}/messages", response_model=schemas.ChatMessageResponse
)
def send_message(
    conversation_id: uuid.UUID, data: schemas.SendTextMessageRequest, db: DB, user: Viewer
):
    return asyncio.run(service.send_text(db, user, conversation_id, data))


@router.post("/messages/{message_id}/reactions", response_model=schemas.ChatMessageResponse)
def send_reaction(
    message_id: uuid.UUID,
    data: schemas.ChatReactionRequest,
    db: DB,
    user: Viewer,
):
    return asyncio.run(service.send_reaction(db, user, message_id, data))


@router.post("/webhooks/{connection_id}", include_in_schema=False)
async def webhook(connection_id: uuid.UUID, request: Request, db: DB):
    token = request.headers.get("X-ControlB-Webhook-Token", "")
    if not token or len(token) > 4096:
        raise HTTPException(401, "Webhook não autorizado.")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 1_048_576:
            raise HTTPException(413, "Evento excede o limite de 1 MB.")
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(400, "JSON inválido.") from None
    if not isinstance(payload, dict):
        raise HTTPException(422, "Evento inválido.")
    return await run_in_threadpool(
        lambda: asyncio.run(service.receive_webhook(db, connection_id, token, payload))
    )
