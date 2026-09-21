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
    ChatTeam,
    chat_team_member,
)
from controlb.modules.documents.models import BusinessDocument
from controlb.modules.documents.security import DOCUMENT_VIEW_PERMISSIONS
from controlb.modules.identity.models import User


def member_teams(org_id, user_id):
    return (
        select(ChatTeam.id)
        .join(chat_team_member, chat_team_member.c.team_id == ChatTeam.id)
        .join(User, User.id == chat_team_member.c.user_id)
        .where(
            ChatTeam.organization_id == org_id,
            ChatTeam.is_active.is_(True),
            User.organization_id == org_id,
            User.is_active.is_(True),
            User.id == user_id,
        )
    )


def team_is_active(db, org_id, team_id):
    return bool(
        db.scalar(
            select(ChatTeam.id).where(
                ChatTeam.id == team_id,
                ChatTeam.organization_id == org_id,
                ChatTeam.is_active.is_(True),
            )
        )
    )


def is_member(db, org_id, user_id, team_id):
    return bool(db.scalar(member_teams(org_id, user_id).where(ChatTeam.id == team_id)))


def configured_teams():
    return (
        select(chat_team_member.c.team_id)
        .join(User, User.id == chat_team_member.c.user_id)
        .where(User.is_active.is_(True))
    )


def is_unassigned(db, connection):
    return connection.team_id is None or not db.scalar(
        select(chat_team_member.c.team_id)
        .join(User, User.id == chat_team_member.c.user_id)
        .where(chat_team_member.c.team_id == connection.team_id, User.is_active.is_(True))
        .limit(1)
    )


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


def conversations_query(org_id, permissions: set[str], user_id):
    query = select(ChatConversation).where(
        ChatConversation.deleted_at.is_(None),
        ChatConversation.organization_id == org_id,
        ChatConversation.team_id.in_(member_teams(org_id, user_id)),
        ChatConversation.connection_id.in_(
            select(ChatConnection.id).where(
                ChatConnection.organization_id == org_id,
                ChatConnection.team_id == ChatConversation.team_id,
            )
        ),
    )
    if "*:*" in permissions:
        return query
    link = ChatConversationLink
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
    # Atendimento sem documento também é permitido aos membros da equipe.
    return query.where(~denied)


def get_conversation(db, org_id, conversation_id, permissions, user_id):
    return db.scalar(
        conversations_query(org_id, permissions, user_id)
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
