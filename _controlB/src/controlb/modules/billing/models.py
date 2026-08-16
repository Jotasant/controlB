"""
modules/billing/models.py - Modelos ORM do Módulo de Faturamento & Documentos Fiscais (Billing Domain)
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


class Invoice(Base):
    """
    Tabela 'invoice' - Faturas Comerciais emitidas a partir de Pedidos de Venda ou Vendas do PDV.
    """
    __tablename__ = "invoice"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    sales_order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sales_order.id", ondelete="SET NULL"), nullable=True)
    
    invoice_number: Mapped[str] = mapped_column(String(50), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_document: Mapped[str | None] = mapped_column(String(30), nullable=True)
    
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    net_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    status: Mapped[str] = mapped_column(String(50), default="ISSUED", index=True)  # DRAFT, ISSUED, CANCELLED
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamento 1:N com Parcelas
    installments: Mapped[list["InvoiceInstallment"]] = relationship(back_populates="invoice", cascade="all, delete-orphan", lazy="selectin")


class InvoiceInstallment(Base):
    """
    Tabela 'invoice_installment' - Parcelas Comerciais e Fiscais da Fatura.
    """
    __tablename__ = "invoice_installment"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoice.id", ondelete="CASCADE"), nullable=False)
    
    installment_number: Mapped[int] = mapped_column(Integer, nullable=False)
    total_installments: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING")  # PENDING, PAID, OVERDUE

    # Relacionamentos
    invoice: Mapped["Invoice"] = relationship(back_populates="installments")
