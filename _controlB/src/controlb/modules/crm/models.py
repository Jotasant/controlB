"""
modules/crm/models.py - Modelos ORM do Módulo de CRM & Gestão de Relacionamento (CRM Domain)
"""

import uuid
from datetime import datetime, timezone, date
from decimal import Decimal
from sqlalchemy import String, Text, Boolean, DateTime, Date, Numeric, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from controlb.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Lead(Base):
    """
    Tabela 'lead' - Contatos e prospects potenciais antes de virarem clientes ativos.
    """
    __tablename__ = "lead"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    source: Mapped[str] = mapped_column(String(100), default="Indicação")  # Site, Indicação, Feira, Prospecção Ativa
    status: Mapped[str] = mapped_column(String(50), default="NEW", index=True)  # NEW, CONTACTED, QUALIFIED, DISQUALIFIED, CONVERTED
    
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamentos
    opportunities: Mapped[list["Opportunity"]] = relationship(back_populates="lead", cascade="all, delete-orphan")
    interactions: Mapped[list["CustomerInteraction"]] = relationship(back_populates="lead", cascade="all, delete-orphan")


class Opportunity(Base):
    """
    Tabela 'opportunity' - Oportunidades de Negócio no Funil de Vendas (Pipeline).
    Estágios: PROSPECTING, QUALIFICATION, PROPOSAL, NEGOTIATION, WON, LOST.
    """
    __tablename__ = "opportunity"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lead.id", ondelete="SET NULL"), nullable=True)
    
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    estimated_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    probability_percent: Mapped[int] = mapped_column(Integer, default=50)  # 0 a 100%
    expected_closing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    stage: Mapped[str] = mapped_column(String(50), default="PROSPECTING", index=True)
    # PROSPECTING, QUALIFICATION, PROPOSAL, NEGOTIATION, WON, LOST
    
    loss_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamentos
    lead: Mapped["Lead | None"] = relationship(back_populates="opportunities", lazy="selectin")
    interactions: Mapped[list["CustomerInteraction"]] = relationship(back_populates="opportunity", cascade="all, delete-orphan")


class CustomerInteraction(Base):
    """
    Tabela 'customer_interaction' - Histórico de Ligações, Reuniões, E-mails e Visitas.
    """
    __tablename__ = "customer_interaction"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lead.id", ondelete="SET NULL"), nullable=True)
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("opportunity.id", ondelete="SET NULL"), nullable=True)
    
    interaction_type: Mapped[str] = mapped_column(String(50), default="CALL")  # CALL, MEETING, EMAIL, WHATSAPP, NOTE
    summary: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    interaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relacionamentos
    lead: Mapped["Lead | None"] = relationship(back_populates="interactions", lazy="selectin")
    opportunity: Mapped["Opportunity | None"] = relationship(back_populates="interactions", lazy="selectin")
