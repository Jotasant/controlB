"""Consultas do Chat sempre delimitadas pela organização autenticada."""

import hashlib
import uuid

from sqlalchemy import exists, func, or_, select, text
from sqlalchemy.orm import Session

from controlb.modules.chat.models import (
    ChatConnection,
    ChatConversation,
    ChatConversationLink,
    ChatMessage,
)
from controlb.modules.documents.models import BusinessDocument
from controlb.modules.documents.security import DOCUMENT_VIEW_PERMISSIONS


def lock_connection(db: Session, connection_id: uuid.UUID) -> None:
    # O webhook e a confirmação de envio compartilham este lock transacional.
    key = int.from_bytes(hashlib.sha256(connection_id.bytes).digest()[:8], signed=True)
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


def get_connection(db, org_id, connection_id):
    return db.scalar(
        select(ChatConnection)
        .where(ChatConnection.id == connection_id, ChatConnection.organization_id == org_id)
        .execution_options(populate_existing=True)
    )


def conversations_query(org_id, permissions: set[str]):
    query = select(ChatConversation).where(ChatConversation.organization_id == org_id)
    if "*:*" in permissions:
        return query
    link = ChatConversationLink
    linked = exists(
        select(link.id).where(
            link.conversation_id == ChatConversation.id, link.organization_id == org_id
        )
    )
    allowed_types = [key for key, perm in DOCUMENT_VIEW_PERMISSIONS.items() if perm in permissions]
    allowed = BusinessDocument.document_type.in_(allowed_types)
    if "documents:view" in permissions:
        allowed = or_(allowed, BusinessDocument.document_type.not_in(DOCUMENT_VIEW_PERMISSIONS))
    denied = exists(
        select(link.id)
        .join(BusinessDocument, BusinessDocument.id == link.business_document_id)
        .where(
            link.conversation_id == ChatConversation.id, link.organization_id == org_id, ~allowed
        )
    )
    # Entradas não classificadas são visíveis apenas a quem pode vinculá-las.
    return query.where(~denied) if "chat:link" in permissions else query.where(linked, ~denied)


def get_conversation(db, org_id, conversation_id, permissions):
    return db.scalar(
        conversations_query(org_id, permissions)
        .where(ChatConversation.id == conversation_id)
        .execution_options(populate_existing=True)
    )


def page(db, query, page_number, page_size):
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    items = list(db.scalars(query.offset((page_number - 1) * page_size).limit(page_size)))
    return {"items": items, "total": total, "page": page_number, "page_size": page_size}


def get_external_message(db, org_id, conversation_id, external_id):
    return db.scalar(
        select(ChatMessage).where(
            ChatMessage.organization_id == org_id,
            ChatMessage.conversation_id == conversation_id,
            ChatMessage.external_message_id == external_id,
        )
    )
