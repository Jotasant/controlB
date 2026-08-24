"""Modelos globais para identidade, relações e eventos de documentos de negócio."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
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


class BusinessDocument(Base):
    """Identidade transversal e persistência central de um documento transacional do sistema."""

    __tablename__ = "business_document"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "document_type",
            "native_id",
            name="uq_business_document_native",
        ),
        UniqueConstraint(
            "organization_id",
            "document_type",
            "document_number",
            name="uq_business_document_number",
        ),
        UniqueConstraint("id", "organization_id", name="uq_business_document_id_org"),
        Index("ix_business_document_org_type", "organization_id", "document_type"),
        Index("ix_business_document_org_cat", "organization_id", "category"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(100), default="generic", index=True, nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    native_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    document_number: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    current_status: Mapped[str] = mapped_column(String(50), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="MEDIUM", nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    origin_module: Mapped[str] = mapped_column(String(50), default="DOCUMENTS", nullable=False)
    responsible_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    outgoing_relations: Mapped[list[DocumentRelation]] = relationship(
        back_populates="parent_document",
        foreign_keys="DocumentRelation.parent_document_id",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    incoming_relations: Mapped[list[DocumentRelation]] = relationship(
        back_populates="child_document",
        foreign_keys="DocumentRelation.child_document_id",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    events: Mapped[list[DocumentEvent]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="DocumentEvent.created_at",
    )


# Alias semântico
Document = BusinessDocument


class DocumentSequence(Base):
    """Controle atômico de sequências de numeração por organização e categoria de documento."""

    __tablename__ = "document_sequence"
    __table_args__ = (
        UniqueConstraint("organization_id", "category", "year", name="uq_document_sequence_org_cat_year"),
        Index("ix_document_sequence_lookup", "organization_id", "category", "year"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    current_value: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    prefix: Mapped[str] = mapped_column(String(20), default="DOC", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class DocumentRelation(Base):
    """Aresta imutável entre dois documentos de negócio."""

    __tablename__ = "document_relation"
    __table_args__ = (
        ForeignKeyConstraint(
            ["parent_document_id", "organization_id"],
            ["business_document.id", "business_document.organization_id"],
            ondelete="RESTRICT",
            name="fk_document_relation_parent_org",
        ),
        ForeignKeyConstraint(
            ["child_document_id", "organization_id"],
            ["business_document.id", "business_document.organization_id"],
            ondelete="RESTRICT",
            name="fk_document_relation_child_org",
        ),
        UniqueConstraint(
            "parent_document_id",
            "child_document_id",
            "relation_type",
            name="uq_document_relation_edge",
        ),
        CheckConstraint(
            "parent_document_id <> child_document_id",
            name="ck_document_relation_not_self",
        ),
        Index("ix_document_relation_org", "organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    parent_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    child_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    relation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    relation_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    parent_document: Mapped[BusinessDocument] = relationship(
        back_populates="outgoing_relations", foreign_keys=[parent_document_id]
    )
    child_document: Mapped[BusinessDocument] = relationship(
        back_populates="incoming_relations", foreign_keys=[child_document_id]
    )


class DocumentEvent(Base):
    """Evento append-only que explica a evolução de um documento."""

    __tablename__ = "document_event"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["business_document.id", "business_document.organization_id"],
            ondelete="RESTRICT",
            name="fk_document_event_document_org",
        ),
        UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_document_event_idempotency"
        ),
        Index("ix_document_event_document_created", "document_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    event_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    document: Mapped[BusinessDocument] = relationship(back_populates="events")
