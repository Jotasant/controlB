"""Modelos persistentes do gateway de comunicação multiconector."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from controlb.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class ChatConnection(Base):
    """Configuração de uma instância externa pertencente a uma organização."""

    __tablename__ = "chat_connection"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_chat_connection_id_org"),
        UniqueConstraint(
            "organization_id",
            "provider",
            "external_instance_id",
            name="uq_chat_connection_org_provider_instance",
        ),
        CheckConstraint(
            "status IN ('DISCONNECTED', 'CONNECTING', 'CONNECTED', 'ERROR')",
            name="ck_chat_connection_status",
        ),
        Index("ix_chat_connection_org_active", "organization_id", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    external_instance_id: Mapped[str] = mapped_column(String(200), nullable=False)
    credentials_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    credentials_hint: Mapped[str | None] = mapped_column(String(50), nullable=True)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="DISCONNECTED", nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    conversations: Mapped[list[ChatConversation]] = relationship(
        back_populates="connection", cascade="all, delete-orphan", lazy="noload"
    )
    webhook_events: Mapped[list[ChatWebhookEvent]] = relationship(
        back_populates="connection", cascade="all, delete-orphan", lazy="noload"
    )


class ChatConversation(Base):
    """Conversa persistida independentemente do formato do provedor externo."""

    __tablename__ = "chat_conversation"
    __table_args__ = (
        ForeignKeyConstraint(
            ["connection_id", "organization_id"],
            ["chat_connection.id", "chat_connection.organization_id"],
            ondelete="CASCADE",
            name="fk_chat_conversation_connection_org",
        ),
        UniqueConstraint("id", "organization_id", name="uq_chat_conversation_id_org"),
        UniqueConstraint("connection_id", "external_chat_id", name="uq_chat_conversation_external"),
        CheckConstraint(
            "status IN ('OPEN', 'CLOSED', 'ARCHIVED')",
            name="ck_chat_conversation_status",
        ),
        CheckConstraint("unread_count >= 0", name="ck_chat_conversation_unread"),
        Index(
            "ix_chat_conversation_org_status_last",
            "organization_id",
            "status",
            "last_message_at",
        ),
        Index("ix_chat_conversation_org_phone", "organization_id", "remote_phone"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    external_chat_id: Mapped[str] = mapped_column(String(255), nullable=False)
    remote_phone: Mapped[str] = mapped_column(String(40), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contact.id", ondelete="SET NULL"), nullable=True
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("customer.id", ondelete="SET NULL"), nullable=True
    )
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="OPEN", nullable=False)
    unread_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_message_preview: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    connection: Mapped[ChatConnection] = relationship(back_populates="conversations")
    messages: Mapped[list[ChatMessage]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        lazy="noload",
        foreign_keys="ChatMessage.conversation_id",
    )
    document_links: Mapped[list[ChatConversationLink]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", lazy="selectin"
    )


class ChatConversationLink(Base):
    """Vínculo extensível da conversa com um documento de qualquer módulo."""

    __tablename__ = "chat_conversation_link"
    __table_args__ = (
        ForeignKeyConstraint(
            ["conversation_id", "organization_id"],
            ["chat_conversation.id", "chat_conversation.organization_id"],
            ondelete="CASCADE",
            name="fk_chat_link_conversation_org",
        ),
        ForeignKeyConstraint(
            ["business_document_id", "organization_id"],
            ["business_document.id", "business_document.organization_id"],
            ondelete="CASCADE",
            name="fk_chat_link_document_org",
        ),
        UniqueConstraint(
            "conversation_id", "business_document_id", name="uq_chat_link_conversation_document"
        ),
        CheckConstraint("link_type IN ('ORIGIN', 'RELATED')", name="ck_chat_link_type"),
        Index("ix_chat_link_document", "business_document_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    business_document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    link_type: Mapped[str] = mapped_column(String(20), default="RELATED", nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    conversation: Mapped[ChatConversation] = relationship(back_populates="document_links")


class ChatMessage(Base):
    """Mensagem normalizada, recebida ou enviada por qualquer conector."""

    __tablename__ = "chat_message"
    __table_args__ = (
        ForeignKeyConstraint(
            ["conversation_id", "organization_id"],
            ["chat_conversation.id", "chat_conversation.organization_id"],
            ondelete="CASCADE",
            name="fk_chat_message_conversation_org",
        ),
        UniqueConstraint("conversation_id", "external_message_id", name="uq_chat_message_external"),
        UniqueConstraint("organization_id", "client_request_id", name="uq_chat_message_request"),
        CheckConstraint("direction IN ('INBOUND', 'OUTBOUND')", name="ck_chat_message_direction"),
        CheckConstraint(
            "status IN ('RECEIVED', 'PENDING', 'SENT', 'DELIVERED', 'READ', 'FAILED')",
            name="ck_chat_message_status",
        ),
        Index("ix_chat_message_conversation_time", "conversation_id", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    external_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_request_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    message_type: Mapped[str] = mapped_column(String(30), default="TEXT", nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    media_mime_type: Mapped[str | None] = mapped_column(String(150), nullable=True)
    media_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    sender_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sender_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reply_to_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chat_message.id", ondelete="SET NULL"), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    conversation: Mapped[ChatConversation] = relationship(
        back_populates="messages", foreign_keys=[conversation_id]
    )


class ChatWebhookEvent(Base):
    """Caixa de entrada idempotente dos eventos recebidos dos provedores."""

    __tablename__ = "chat_webhook_event"
    __table_args__ = (
        ForeignKeyConstraint(
            ["connection_id", "organization_id"],
            ["chat_connection.id", "chat_connection.organization_id"],
            ondelete="CASCADE",
            name="fk_chat_webhook_connection_org",
        ),
        UniqueConstraint("connection_id", "event_key", name="uq_chat_webhook_event_key"),
        CheckConstraint(
            "status IN ('PENDING', 'PROCESSED', 'IGNORED', 'FAILED')",
            name="ck_chat_webhook_status",
        ),
        Index("ix_chat_webhook_status_created", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    event_key: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    connection: Mapped[ChatConnection] = relationship(back_populates="webhook_events")
