"""API do Chat e entrada autenticada dos webhooks dos conectores."""

import asyncio
import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from controlb.db import get_db
from controlb.modules.chat import schemas, service
from controlb.modules.chat.connectors.registry import available_providers
from controlb.modules.chat.models import ChatConnection
from controlb.modules.identity.models import User
from controlb.modules.identity.security import require_permission

router = APIRouter(prefix="/chat", tags=["Chat"])
DB = Annotated[Session, Depends(get_db)]
Viewer = Annotated[User, Depends(require_permission("chat:view"))]
Manager = Annotated[User, Depends(require_permission("chat:manage_connectors"))]
Page = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


@router.get("/providers")
def providers(user: Manager):
    return [
        {"code": code, "name": "Evolution API" if code == "EVOLUTION" else code}
        for code in available_providers()
    ]


@router.get("/channels")
def channels(db: DB, user: Viewer):
    rows = db.execute(
        select(
            ChatConnection.id, ChatConnection.name, ChatConnection.provider, ChatConnection.status
        )
        .where(
            ChatConnection.organization_id == user.organization_id,
            ChatConnection.is_active.is_(True),
        )
        .order_by(ChatConnection.name)
    )
    return [dict(row._mapping) for row in rows]


@router.get("/connections", response_model=list[schemas.ChatConnectionResponse])
def connections(db: DB, user: Manager, page: Page = 1, page_size: PageSize = 50):
    return list(
        db.scalars(
            select(ChatConnection)
            .where(ChatConnection.organization_id == user.organization_id)
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
    return service.connection(db, user, connection_id)


@router.patch("/connections/{connection_id}", response_model=schemas.ChatConnectionResponse)
def update_connection(
    connection_id: uuid.UUID, data: schemas.ChatConnectionUpdate, db: DB, user: Manager
):
    return service.update_connection(db, user, connection_id, data)


# Sessão SQLAlchemy síncrona e locks ficam no threadpool do FastAPI. O adaptador
# tem seu próprio loop por operação, sem bloquear o loop HTTP durante locks SQL.
@router.post("/connections/{connection_id}/check", response_model=schemas.ChatConnectionResponse)
def check_connection(connection_id: uuid.UUID, db: DB, user: Manager):
    return asyncio.run(service.check_connection(db, user, connection_id))


@router.post("/connections/{connection_id}/webhook")
def configure_webhook(connection_id: uuid.UUID, db: DB, user: Manager):
    return asyncio.run(service.configure_webhook(db, user, connection_id))


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
    status: Annotated[str | None, Query(pattern="^(OPEN|CLOSED|ARCHIVED)$")] = None,
    unlinked: bool = False,
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


@router.post(
    "/conversations/{conversation_id}/read", response_model=schemas.ChatConversationResponse
)
def mark_read(conversation_id: uuid.UUID, db: DB, user: Viewer):
    """Zera os não lidos da caixa compartilhada local; não envia recibo ao WhatsApp."""
    return service.mark_read(db, user, conversation_id)


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
