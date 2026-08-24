"""
modules/crm/models.py - Modelos de Dados ORM do Módulo CRM (ControlB)
Mapeamento canônico das entidades Lead, Opportunity e CustomerInteraction.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    String, Text, Numeric, Integer, Date, DateTime, ForeignKey, Index,
    CheckConstraint, Boolean, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from controlb.db import Base
import controlb.modules.identity.models  # noqa: F401
import controlb.modules.sales.models     # noqa: F401

if TYPE_CHECKING:
    from controlb.modules.identity.models import Organization, User, Contact
    from controlb.modules.sales.models import Customer, SalesQuote, SalesOrder


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ==============================================================================
# 0. ETAPAS DINÂMICAS DO FUNIL DE CRM (Pipeline Stages)
# ==============================================================================

class CRMStage(Base):
    """
    Tabela 'crm_stage' - Etapas configuráveis do funil de vendas (Kanban).
    Permite criação de etapas customizadas por organização.
    """
    __tablename__ = "crm_stage"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_crm_stage_org_code"),
        Index("ix_crm_stage_org_order", "organization_id", "order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str] = mapped_column(String(20), default="#10b981", nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    is_won: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_lost: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


# ==============================================================================
# 1. LEADS / PROSPECTS
# ==============================================================================

class Lead(Base):
    """
    Tabela 'lead' - Contatos e prospects em fase inicial de qualificação.
    Conectado diretamente à base de clientes centralizada de Vendas (Customer).
    """
    __tablename__ = "lead"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("customer.id", ondelete="SET NULL"), index=True, nullable=True
    )
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source: Mapped[str] = mapped_column(String(100), default="Indicação", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="NEW", index=True, nullable=False)  # NEW, CONTACTED, QUALIFIED, CONVERTED, DISQUALIFIED
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relacionamentos
    customer: Mapped["Customer | None"] = relationship(foreign_keys=[customer_id], lazy="select")
    assigned_to: Mapped["User | None"] = relationship(foreign_keys=[assigned_to_id], lazy="select")
    opportunities: Mapped[list["Opportunity"]] = relationship(back_populates="lead", lazy="select")
    interactions: Mapped[list["CustomerInteraction"]] = relationship(back_populates="lead", cascade="all, delete-orphan", lazy="select")


# ==============================================================================
# 2. OPORTUNIDADES & FUNIL DE VENDAS (Pipeline)
# ==============================================================================

class Opportunity(Base):
    """
    Tabela 'opportunity' - Negócios em andamento no Funil de Vendas.
    Integrado à base de clientes centralizada (Customer) e cotações (SalesQuote).
    """
    __tablename__ = "opportunity"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("lead.id", ondelete="SET NULL"), nullable=True
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("customer.id", ondelete="SET NULL"), index=True, nullable=True
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contact.id", ondelete="SET NULL"), nullable=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    estimated_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    probability_percent: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    expected_closing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    stage: Mapped[str] = mapped_column(String(50), default="PROSPECTING", index=True, nullable=False)  # PROSPECTING, QUALIFICATION, PROPOSAL, NEGOTIATION, WON, LOST
    loss_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relacionamentos
    lead: Mapped["Lead | None"] = relationship(back_populates="opportunities", lazy="select")
    customer: Mapped["Customer | None"] = relationship(back_populates="opportunities", lazy="select")
    assigned_to: Mapped["User | None"] = relationship(foreign_keys=[assigned_to_id], lazy="select")
    interactions: Mapped[list["CustomerInteraction"]] = relationship(back_populates="opportunity", cascade="all, delete-orphan", lazy="select")
    quotes: Mapped[list["SalesQuote"]] = relationship(back_populates="opportunity", cascade="all, delete-orphan", lazy="select")


# ==============================================================================
# 3. INTERAÇÕES COM CLIENTES / REGISTRO DE ATIVIDADES
# ==============================================================================

class CustomerInteraction(Base):
    """
    Tabela 'customer_interaction' - Registro de histórico de interações (Reuniões, Ligações, E-mails, WhatsApp).
    """
    __tablename__ = "customer_interaction"
    __table_args__ = (
        CheckConstraint(
            "(interaction_type = 'NOTE' AND status IS NULL) OR "
            "(interaction_type <> 'NOTE' AND status IN "
            "('SCHEDULED', 'COMPLETED', 'CANCELLED'))",
            name="ck_customer_interaction_lifecycle",
        ),
        Index("ix_customer_interaction_org_status", "organization_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("lead.id", ondelete="SET NULL"), nullable=True
    )
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("opportunity.id", ondelete="SET NULL"), nullable=True
    )
    
    interaction_type: Mapped[str] = mapped_column(String(50), nullable=False)  # CALL, MEETING, EMAIL, WHATSAPP, NOTE
    summary: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    interaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    status: Mapped[str | None] = mapped_column(String(20), nullable=True)

    responsible_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    # Relacionamentos
    lead: Mapped["Lead | None"] = relationship(back_populates="interactions", lazy="select")
    opportunity: Mapped["Opportunity | None"] = relationship(back_populates="interactions", lazy="select")
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_id], lazy="select")
    updated_by: Mapped["User | None"] = relationship(foreign_keys=[updated_by_id], lazy="select")
    responsible: Mapped["User | None"] = relationship(foreign_keys=[responsible_id], lazy="select")
