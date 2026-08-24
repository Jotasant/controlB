"""
modules/sales/models.py - Modelos ORM do Módulo de Vendas & PDV (Sales & POS Domain)
"""

import uuid
from datetime import datetime, timezone, date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    String, Text, Boolean, CheckConstraint, DateTime, Date, Numeric, ForeignKey,
    ForeignKeyConstraint, Integer, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from controlb.db import Base
from controlb.modules.documents.models import BusinessDocument
import controlb.modules.crm.models  # noqa: F401

if TYPE_CHECKING:
    from controlb.modules.crm.models import Opportunity


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ==============================================================================
# 1. CADASTRO CENTRALIZADO DE CLIENTES (Customer)
# ==============================================================================

class Customer(Base):
    """
    Tabela 'customer' - Cadastro Central de Clientes (Pessoa Jurídica ou Física).
    Compartilhado e acessível por todos os módulos do ERP (Vendas, PDV, Faturamento, CRM).
    """
    __tablename__ = "customer"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contact.id", ondelete="SET NULL"), nullable=True)

    person_type: Mapped[str] = mapped_column(String(10), default="PJ", index=True)  # "PJ" (CNPJ) ou "PF" (CPF)
    document: Mapped[str] = mapped_column(String(30), nullable=False, index=True)   # CNPJ ou CPF
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)      # Razão Social ou Nome Completo
    trade_name: Mapped[str | None] = mapped_column(String(255), nullable=True)     # Nome Fantasia
    state_registration: Mapped[str | None] = mapped_column(String(50), nullable=True) # Inscrição Estadual (IE)

    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # Endereço
    address_street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address_neighborhood: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address_state: Mapped[str | None] = mapped_column(String(10), nullable=True)
    address_zip_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    credit_limit: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    origin_module: Mapped[str] = mapped_column(String(50), default="SALES", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamentos
    quotes: Mapped[list["SalesQuote"]] = relationship(back_populates="customer", cascade="all, delete-orphan")
    orders: Mapped[list["SalesOrder"]] = relationship(back_populates="customer", cascade="all, delete-orphan")
    opportunities: Mapped[list["Opportunity"]] = relationship(back_populates="customer")


# ==============================================================================
# 2. ORÇAMENTOS E PROPOSTAS COMERCIAIS (Sales Quote)
# ==============================================================================

class SalesQuote(Base):
    """
    Tabela 'sales_quote' - Orçamentos Comerciais com fluxo de aprovação e conversão.
    """
    __tablename__ = "sales_quote"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["business_document.id", "business_document.organization_id"],
            ondelete="RESTRICT",
            name="fk_sales_quote_document_org",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customer.id", ondelete="SET NULL"), nullable=True)
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("opportunity.id", ondelete="SET NULL"), nullable=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True
    )
    
    quote_number: Mapped[str] = mapped_column(String(50), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_document: Mapped[str | None] = mapped_column(String(30), nullable=True)
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    net_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    
    payment_terms: Mapped[str | None] = mapped_column(String(100), nullable=True)
    valid_until: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="DRAFT", index=True)  # DRAFT, SENT, APPROVED, REJECTED, CONVERTED, EXPIRED, CANCELLED
    commercial_approval_status: Mapped[str] = mapped_column(
        String(30), default="NOT_REQUIRED", nullable=False, index=True
    )  # NOT_REQUIRED, APPROVED, PENDING, REJECTED
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamentos
    customer: Mapped["Customer | None"] = relationship(back_populates="quotes")
    opportunity: Mapped["Opportunity | None"] = relationship(
        back_populates="quotes", lazy="selectin"
    )
    document: Mapped["BusinessDocument"] = relationship(lazy="select")
    items: Mapped[list["SalesQuoteItem"]] = relationship(back_populates="quote", cascade="all, delete-orphan", lazy="selectin")
    commercial_approvals: Mapped[list["CommercialApprovalRequest"]] = relationship(
        back_populates="quote", cascade="all, delete-orphan", lazy="selectin"
    )


class SalesQuoteItem(Base):
    """
    Tabela 'sales_quote_item' - Itens do Orçamento Comercial.
    """
    __tablename__ = "sales_quote_item"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quote_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sales_quote.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product.id", ondelete="CASCADE"), nullable=False)
    
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.00"))
    total_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relacionamentos
    quote: Mapped["SalesQuote"] = relationship(back_populates="items")


# ==============================================================================
# 3. PEDIDOS DE VENDA FORMALIZADOS (Sales Order)
# ==============================================================================

class SalesOrder(Base):
    """
    Tabela 'sales_order' - Pedidos de Venda Oficiais.
    """
    __tablename__ = "sales_order"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["business_document.id", "business_document.organization_id"],
            ondelete="RESTRICT",
            name="fk_sales_order_document_org",
        ),
        UniqueConstraint("sales_quote_id", name="uq_sales_order_sales_quote"),
        UniqueConstraint("id", "organization_id", name="uq_sales_order_id_org"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customer.id", ondelete="SET NULL"), nullable=True)
    sales_quote_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sales_quote.id", ondelete="SET NULL"), nullable=True)
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("opportunity.id", ondelete="SET NULL"), nullable=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True
    )
    
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
    credit_status: Mapped[str] = mapped_column(
        String(30), default="NOT_REQUIRED", nullable=False, index=True
    )  # NOT_REQUIRED, APPROVED, PENDING, REJECTED
    credit_limit_snapshot: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    credit_exposure_snapshot: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    credit_excess_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    commercial_approval_status: Mapped[str] = mapped_column(
        String(30), default="NOT_REQUIRED", nullable=False, index=True
    )  # NOT_REQUIRED, APPROVED, PENDING, REJECTED
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamentos
    customer: Mapped["Customer | None"] = relationship(back_populates="orders")
    opportunity: Mapped["Opportunity | None"] = relationship(lazy="selectin")
    document: Mapped["BusinessDocument"] = relationship(lazy="select")
    items: Mapped[list["SalesOrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan", lazy="selectin")
    credit_approval: Mapped["CreditApprovalRequest | None"] = relationship(
        back_populates="order", cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )
    commercial_approvals: Mapped[list["CommercialApprovalRequest"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )


class SalesOrderItem(Base):
    """
    Tabela 'sales_order_item' - Itens do Pedido de Venda.
    """
    __tablename__ = "sales_order_item"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sales_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sales_order.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product.id", ondelete="CASCADE"), nullable=False)
    
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.00"))
    total_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relacionamentos
    order: Mapped["SalesOrder"] = relationship(back_populates="items")


class CreditApprovalRequest(Base):
    """Solicitação auditável para liberar um pedido acima do limite de crédito."""
    __tablename__ = "credit_approval_request"
    __table_args__ = (
        UniqueConstraint("sales_order_id", name="uq_credit_approval_sales_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sales_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sales_order.id", ondelete="CASCADE"), nullable=False
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customer.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    status: Mapped[str] = mapped_column(
        String(30), default="PENDING", nullable=False, index=True
    )  # PENDING, APPROVED, REJECTED, CANCELLED
    request_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    credit_limit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    exposure_before_order: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    order_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    excess_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    requested_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    decided_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    order: Mapped["SalesOrder"] = relationship(back_populates="credit_approval")


class CommercialApprovalRequest(Base):
    """Alçada comercial para desconto, margem ou prazo fora da política automática."""
    __tablename__ = "commercial_approval_request"
    __table_args__ = (
        CheckConstraint(
            "(sales_quote_id IS NOT NULL AND sales_order_id IS NULL) OR "
            "(sales_quote_id IS NULL AND sales_order_id IS NOT NULL)",
            name="ck_commercial_approval_single_document",
        ),
        UniqueConstraint(
            "sales_quote_id", "approval_type", name="uq_commercial_approval_quote_type"
        ),
        UniqueConstraint(
            "sales_order_id", "approval_type", name="uq_commercial_approval_order_type"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sales_quote_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sales_quote.id", ondelete="CASCADE"), nullable=True, index=True
    )
    sales_order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sales_order.id", ondelete="CASCADE"), nullable=True, index=True
    )
    approval_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(30), default="PENDING", nullable=False, index=True
    )
    metric_value: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    request_reason: Mapped[str] = mapped_column(Text, nullable=False)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    decided_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    quote: Mapped["SalesQuote | None"] = relationship(back_populates="commercial_approvals")
    order: Mapped["SalesOrder | None"] = relationship(back_populates="commercial_approvals")


# ==============================================================================
# 4. FRENTE DE CAIXA (PDV BALCÃO ÁGIL) & SANGRIA / SUPRIMENTO
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
    cash_movements: Mapped[list["POSCashMovement"]] = relationship(back_populates="session", cascade="all, delete-orphan", lazy="selectin")


class POSCashMovement(Base):
    """
    Tabela 'pos_cash_movement' - Registro de Sangria (retirada) e Suprimento (reforço) de caixa.
    """
    __tablename__ = "pos_cash_movement"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    pos_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pos_session.id", ondelete="CASCADE"), nullable=False)

    movement_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "SANGRIA" ou "SUPRIMENTO"
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relacionamentos
    session: Mapped["POSSession"] = relationship(back_populates="cash_movements")


class POSSale(Base):
    """
    Tabela 'pos_sale' - Venda instantânea realizada no PDV Balcão.
    """
    __tablename__ = "pos_sale"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    pos_session_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("pos_session.id", ondelete="SET NULL"), nullable=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customer.id", ondelete="SET NULL"), nullable=True)
    
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
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product.id", ondelete="CASCADE"), nullable=False)
    
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    # Relacionamento
    sale: Mapped["POSSale"] = relationship(back_populates="items")


# ==============================================================================
# 5. GESTÃO COMERCIAL (Metas, Comissões e Tabelas de Preços)
# ==============================================================================

class SalesGoal(Base):
    """
    Tabela 'sales_goal' - Metas comerciais por vendedor.
    """
    __tablename__ = "sales_goal"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False)

    seller_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 a 12
    year: Mapped[int] = mapped_column(Integer, nullable=False)   # 2026
    target_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    commission_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("2.00")) # Ex: 2.5%

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class PriceTable(Base):
    """
    Tabela 'price_table' - Tabelas de preços personalizadas (Varejo, Atacado, Convênio).
    """
    __tablename__ = "price_table"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamentos
    items: Mapped[list["PriceTableItem"]] = relationship(back_populates="price_table", cascade="all, delete-orphan", lazy="selectin")


class PriceTableItem(Base):
    """
    Tabela 'price_table_item' - Preço diferenciado por produto na tabela.
    """
    __tablename__ = "price_table_item"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    price_table_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("price_table.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product.id", ondelete="CASCADE"), nullable=False)

    price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"))

    # Relacionamentos
    price_table: Mapped["PriceTable"] = relationship(back_populates="items")


class CommercialSettings(Base):
    """Parâmetros comerciais únicos por organização, consumidos por CRM e Vendas."""
    __tablename__ = "commercial_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    default_payment_terms: Mapped[str] = mapped_column(String(100), default="30 DDL", nullable=False)
    quote_validity_days: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    maximum_discount_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("100.00"), nullable=False
    )
    default_commission_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("2.00"), nullable=False
    )
    automatic_discount_limit_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("5.00"), nullable=False
    )
    minimum_margin_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0.00"), nullable=False
    )
    maximum_payment_term_days_without_approval: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# ==============================================================================
# 6. PÓS-VENDA (Devoluções, Trocas e Histórico de Compras)
# ==============================================================================

class SalesReturn(Base):
    """
    Tabela 'sales_return' - Gestão de devoluções e trocas com estorno opcional ao estoque.
    """
    __tablename__ = "sales_return"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    
    sales_order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sales_order.id", ondelete="SET NULL"), nullable=True)
    pos_sale_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("pos_sale.id", ondelete="SET NULL"), nullable=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customer.id", ondelete="SET NULL"), nullable=True)
    
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    return_type: Mapped[str] = mapped_column(String(50), default="DEVOLUCAO")  # DEVOLUCAO, TROCA, CANCELAMENTO
    status: Mapped[str] = mapped_column(String(50), default="COMPLETED")       # PENDING, COMPLETED, REJECTED
    
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    restock_items: Mapped[bool] = mapped_column(Boolean, default=True)         # Se estorna produtos ao estoque
    
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relacionamentos
    items: Mapped[list["SalesReturnItem"]] = relationship(back_populates="sales_return", cascade="all, delete-orphan", lazy="selectin")


class SalesReturnItem(Base):
    """
    Tabela 'sales_return_item' - Itens devolvidos/trocados.
    """
    __tablename__ = "sales_return_item"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sales_return_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sales_return.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product.id", ondelete="CASCADE"), nullable=False)
    
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    condition: Mapped[str] = mapped_column(String(50), default="GOOD")  # GOOD (reestocável), DAMAGED (avaria)

    # Relacionamentos
    sales_return: Mapped["SalesReturn"] = relationship(back_populates="items")
