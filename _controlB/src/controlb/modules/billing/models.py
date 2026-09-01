"""
modules/billing/models.py - Modelos ORM do Módulo de Faturamento & Documentos Fiscais (Billing Domain)
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from controlb.db import Base
from controlb.modules.documents.models import BusinessDocument


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Invoice(Base):
    """
    Tabela 'invoice' - Faturas Comerciais emitidas a partir de Pedidos de Venda ou Vendas do PDV.
    """
    __tablename__ = "invoice"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["business_document.id", "business_document.organization_id"],
            name="fk_invoice_document_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["sales_order_id", "organization_id"],
            ["sales_order.id", "sales_order.organization_id"],
            name="fk_invoice_sales_order_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["fiscal_document_id", "organization_id"],
            ["fiscal_document.id", "fiscal_document.organization_id"],
            name="fk_invoice_fiscal_document_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("document_id", name="uq_invoice_document"),
        UniqueConstraint("id", "organization_id", name="uq_invoice_id_org"),
        UniqueConstraint("organization_id", "invoice_number", name="uq_invoice_org_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    sales_order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    fiscal_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    
    invoice_number: Mapped[str] = mapped_column(String(50), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_document: Mapped[str | None] = mapped_column(String(30), nullable=True)
    
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    net_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    status: Mapped[str] = mapped_column(String(50), default="ISSUED", index=True)  # ISSUED, PARTIALLY_RECEIVED, OVERDUE, PAID, CANCELLED
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamento 1:N com Parcelas
    document: Mapped["BusinessDocument"] = relationship(lazy="select")
    installments: Mapped[list["InvoiceInstallment"]] = relationship(back_populates="invoice", cascade="all, delete-orphan", lazy="selectin")
    items: Mapped[list["InvoiceItem"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="InvoiceItem.created_at",
    )


class InvoiceItem(Base):
    """Snapshot dos itens efetivamente faturados, inclusive em emissões parciais."""

    __tablename__ = "invoice_item"
    __table_args__ = (
        ForeignKeyConstraint(
            ["invoice_id", "organization_id"],
            ["invoice.id", "invoice.organization_id"],
            name="fk_invoice_item_invoice_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["product_id", "organization_id"],
            ["product.id", "product.organization_id"],
            name="fk_invoice_item_product_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "invoice_id", "sales_order_item_id", name="uq_invoice_item_order_item"
        ),
        CheckConstraint("quantity > 0", name="ck_invoice_item_quantity_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    sales_order_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sales_order_item.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    product_sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    invoice: Mapped["Invoice"] = relationship(back_populates="items")


class InvoiceInstallment(Base):
    """
    Tabela 'invoice_installment' - Parcelas Comerciais e Fiscais da Fatura.
    """
    __tablename__ = "invoice_installment"
    __table_args__ = (
        UniqueConstraint(
            "invoice_id", "installment_number", name="uq_invoice_installment_number"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoice.id", ondelete="CASCADE"), nullable=False)
    
    installment_number: Mapped[int] = mapped_column(Integer, nullable=False)
    total_installments: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING")  # PENDING, PAID, OVERDUE

    # Relacionamentos
    invoice: Mapped["Invoice"] = relationship(back_populates="installments")
