"""Modelos persistentes do gateway de comunicação multiconector."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from controlb.db import Base

if TYPE_CHECKING:
    from controlb.modules.identity.models import User


def utcnow() -> datetime:
    return datetime.now(UTC)


chat_team_member = Table(
    "chat_team_member",
    Base.metadata,
    Column("team_id", ForeignKey("chat_team.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", ForeignKey("user.id", ondelete="CASCADE"), primary_key=True),
)


class ChatTeam(Base):
    """Grupo de acesso próprio de uma instância, independente das equipes comerciais."""

    __tablename__ = "chat_team"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    members: Mapped[list[User]] = relationship(secondary=chat_team_member, lazy="selectin")


class ChatConnection(Base):
    """Configuração de uma instância externa pertencente a uma organização."""

    __tablename__ = "chat_connection"
    __table_args__ = (
        UniqueConstraint("team_id", name="uq_chat_connection_own_team"),
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
    groups_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chat_team.id", ondelete="RESTRICT"), index=True
    )
    instance_phone: Mapped[str | None] = mapped_column(String(40))
    provider_instance_id: Mapped[str | None] = mapped_column(String(255))
    transcription_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    sync_checkpoint_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sync_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sync_page: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    recovery_pending: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
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
    team: Mapped[ChatTeam | None] = relationship(lazy="selectin")

    @property
    def member_ids(self) -> list[uuid.UUID]:
        return [member.id for member in self.team.members if member.is_active] if self.team else []

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
            "status IN ('OPEN', 'CLOSED')",
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
    is_group: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cleared_before: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chat_team.id", ondelete="RESTRICT"), index=True
    )
    instance_phone: Mapped[str | None] = mapped_column(String(40))
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL")
    )
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    avatar_blob: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    avatar_mime: Mapped[str | None] = mapped_column(String(100))
    avatar_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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
    assignee: Mapped[User | None] = relationship(
        "User",
        foreign_keys=[assigned_user_id],
        lazy="selectin",
        viewonly=True,
        primaryjoin="and_(ChatConversation.assigned_user_id == User.id, ChatConversation.organization_id == User.organization_id)",
    )

    @property
    def assigned_user_name(self) -> str | None:
        return self.assignee.full_name if self.assignee else None

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
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chat_team.id", ondelete="RESTRICT"), index=True
    )
    instance_phone: Mapped[str | None] = mapped_column(String(40))
    transcription: Mapped[str | None] = mapped_column(Text)
    transcription_status: Mapped[str] = mapped_column(
        String(30), default="NOT_REQUESTED", server_default="NOT_REQUESTED"
    )
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    message_type: Mapped[str] = mapped_column(String(30), default="TEXT", nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    media_mime_type: Mapped[str | None] = mapped_column(String(150), nullable=True)
    media_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    media_blob: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    media_sha256: Mapped[str | None] = mapped_column(String(64))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL")
    )
    revoke_status: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    sender_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sender_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    sender_external_id: Mapped[str | None] = mapped_column(String(255))
    notify_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    reply_to_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chat_message.id", ondelete="SET NULL"), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    reply_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    reaction_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, server_default="{}")

    @property
    def reactions(self) -> list[dict[str, Any]]:
        return [value for value in (self.reaction_data or {}).values() if value.get("emoji")]

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
    author: Mapped[User | None] = relationship(
        "User",
        foreign_keys=[created_by_id],
        lazy="selectin",
        viewonly=True,
        primaryjoin="and_(ChatMessage.created_by_id == User.id, ChatMessage.organization_id == User.organization_id)",
    )

    @property
    def author_name(self) -> str | None:
        return self.author.full_name if self.author else None


class ChatReactionRequest(Base):
    """Intenção durável: reações incertas nunca são reenviadas automaticamente."""

    __tablename__ = "chat_reaction_request"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"))
    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_message.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"))
    emoji: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


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
