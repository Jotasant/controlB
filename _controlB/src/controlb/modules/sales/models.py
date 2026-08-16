"""
modules/sales/models.py - Modelos ORM do Módulo de Vendas & PDV (Sales & POS Domain)
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


class SalesQuote(Base):
    """
    Tabela 'sales_quote' - Orçamentos Comerciais.
    """
    __tablename__ = "sales_quote"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    
    quote_number: Mapped[str] = mapped_column(String(50), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_document: Mapped[str | None] = mapped_column(String(30), nullable=True)
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    net_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    
    valid_until: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="DRAFT", index=True)  # DRAFT, SENT, APPROVED, REJECTED, EXPIRED
    
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamento 1:N com Itens
    items: Mapped[list["SalesQuoteItem"]] = relationship(back_populates="quote", cascade="all, delete-orphan", lazy="selectin")


class SalesQuoteItem(Base):
    """
    Tabela 'sales_quote_item' - Itens do Orçamento Comercial.
    """
    __tablename__ = "sales_quote_item"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quote_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sales_quote.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product.id", ondelete="RESTRICT"), nullable=False)
    
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.00"))
    total_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relacionamentos
    quote: Mapped["SalesQuote"] = relationship(back_populates="items")


class SalesOrder(Base):
    """
    Tabela 'sales_order' - Pedidos de Venda Oficiais.
    """
    __tablename__ = "sales_order"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    
    order_number: Mapped[str] = mapped_column(String(50), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_document: Mapped[str | None] = mapped_column(String(30), nullable=True)
    
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    net_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    
    payment_terms: Mapped[str | None] = mapped_column(String(100), nullable=True)  # ex: "30/60 dias", "À Vista"
    delivery_status: Mapped[str] = mapped_column(String(50), default="PENDING")  # PENDING, DISPATCHED, DELIVERED
    billing_status: Mapped[str] = mapped_column(String(50), default="PENDING", index=True)  # PENDING, INVOICED
    status: Mapped[str] = mapped_column(String(50), default="CONFIRMED", index=True)  # DRAFT, CONFIRMED, COMPLETED, CANCELLED
    
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamento 1:N com Itens
    items: Mapped[list["SalesOrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan", lazy="selectin")


class SalesOrderItem(Base):
    """
    Tabela 'sales_order_item' - Itens do Pedido de Venda.
    """
    __tablename__ = "sales_order_item"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sales_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sales_order.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product.id", ondelete="RESTRICT"), nullable=False)
    
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.00"))
    total_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relacionamentos
    order: Mapped["SalesOrder"] = relationship(back_populates="items")


# ==============================================================================
# FRENTE DE CAIXA (PDV BALCÃO ÁGIL)
# ==============================================================================

class POSSession(Base):
    """
    Tabela 'pos_session' - Turno / Caixa aberto do PDV.
    """
    __tablename__ = "pos_session"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    
    pos_terminal: Mapped[str] = mapped_column(String(50), default="Caixa 01")
    opened_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    opening_cash: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    closing_cash: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    
    status: Mapped[str] = mapped_column(String(50), default="OPEN", index=True)  # OPEN, CLOSED
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relacionamentos
    sales: Mapped[list["POSSale"]] = relationship(back_populates="session", cascade="all, delete-orphan", lazy="selectin")


class POSSale(Base):
    """
    Tabela 'pos_sale' - Venda instantânea realizada no PDV Balcão.
    """
    __tablename__ = "pos_sale"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    pos_session_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("pos_session.id", ondelete="SET NULL"), nullable=True)
    
    customer_name: Mapped[str] = mapped_column(String(255), default="Consumidor Final")
    customer_document: Mapped[str | None] = mapped_column(String(30), nullable=True)  # CPF na nota
    
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    net_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    
    payment_method: Mapped[str] = mapped_column(String(50), default="DINHEIRO")  # DINHEIRO, PIX, DEBITO, CREDITO, MULTIPLO
    status: Mapped[str] = mapped_column(String(50), default="COMPLETED")  # COMPLETED, CANCELLED
    
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relacionamentos
    session: Mapped["POSSession | None"] = relationship(back_populates="sales")
    items: Mapped[list["POSSaleItem"]] = relationship(back_populates="sale", cascade="all, delete-orphan", lazy="selectin")


class POSSaleItem(Base):
    """
    Tabela 'pos_sale_item' - Itens da Venda do PDV.
    """
    __tablename__ = "pos_sale_item"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pos_sale_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pos_sale.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product.id", ondelete="RESTRICT"), nullable=False)
    
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    # Relacionamento
    sale: Mapped["POSSale"] = relationship(back_populates="items")
