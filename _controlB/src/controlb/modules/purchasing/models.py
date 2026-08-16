"""
modules/purchasing/models.py - Modelos Relacionais do Módulo de Compras (Purchasing & Catalogs)

Define a estrutura de dados relacional para:
1. Cadastros de Apoio: Fornecedores (Supplier), Centros de Custo (CostCenter), 
   Categorias (ProductCategory) e Catálogo de Produtos (Product).
2. Solicitações de Compra: PurchaseRequest, PurchaseRequestItem e Eventos de Aprovação (ApprovalEvent).
3. Ordens de Compra: PurchaseOrder e PurchaseOrderItem.
"""

import uuid
from decimal import Decimal
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Numeric, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from controlb.db import Base
from controlb.modules.inventory.models import Product, ProductCategory


def utcnow() -> datetime:
    """Função utilitária que retorna o horário atual com fuso horário UTC padronizado."""
    return datetime.now(timezone.utc)


# ==============================================================================
# 1. CADASTROS DE APOIO COMERCIAIS (Supplier, CostCenter)
# ==============================================================================

class Supplier(Base):
    """
    Tabela 'supplier' - Fornecedores homologados e parceiros de negócio.
    """
    __tablename__ = "supplier"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    trade_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cnpj_cpf: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    state_registration: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    segments: Mapped[str | None] = mapped_column(String(500), nullable=True)  # ex: "Medicamentos, Perfumaria, Insumos Médicos"
    payment_terms: Mapped[str | None] = mapped_column(String(200), nullable=True)
    min_order_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    anvisa_license: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    zip_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), default="BR")
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class CostCenter(Base):
    """
    Tabela 'cost_center' - Centros de custo e unidades orçamentárias.
    """
    __tablename__ = "cost_center"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    manager_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# ==============================================================================
# 2. FLUXO DE SOLICITAÇÃO DE COMPRA E APROVAÇÃO POR ALÇADA

# ==============================================================================

class PurchaseRequest(Base):
    """
    Tabela 'purchase_request' - Solicitações de compra abertas por colaboradores.
    """
    __tablename__ = "purchase_request"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    requester_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id", ondelete="RESTRICT"), nullable=False)
    cost_center_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cost_center.id", ondelete="SET NULL"), nullable=True)
    
    request_number: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", index=True)  # draft, pending_approval, approved, rejected, cancelled
    total_estimated_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    required_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamento 1:N com os itens da solicitação
    items: Mapped[list["PurchaseRequestItem"]] = relationship(
        back_populates="purchase_request", 
        cascade="all, delete-orphan", 
        lazy="selectin"
    )

    # Relacionamento 1:N com o histórico de eventos de aprovação
    approval_events: Mapped[list["ApprovalEvent"]] = relationship(
        back_populates="purchase_request", 
        cascade="all, delete-orphan", 
        lazy="selectin"
    )

    # Relacionamento 1:1 com o Processo de Cotação (RFQ)
    quotation_process: Mapped["QuotationProcess | None"] = relationship(
        back_populates="purchase_request",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin"
    )


class PurchaseRequestItem(Base):
    """
    Tabela 'purchrequestase__item' - Linhas/produtos de uma solicitação de compra.
    """
    __tablename__ = "purchase_request_item"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    purchase_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("purchase_request.id", ondelete="CASCADE"), 
        nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product.id", ondelete="RESTRICT"), nullable=False)
    
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    estimated_unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.0000"))
    total_estimated_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamentos
    purchase_request: Mapped["PurchaseRequest"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(lazy="selectin")


class ApprovalEvent(Base):
    """
    Tabela 'approval_event' - Trilha de auditoria das decisões de aprovação por alçada.
    """
    __tablename__ = "approval_event"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    purchase_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("purchase_request.id", ondelete="CASCADE"), 
        nullable=False
    )
    approver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id", ondelete="RESTRICT"), nullable=False)
    
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # approved, rejected
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relacionamento com a solicitação
    purchase_request: Mapped["PurchaseRequest"] = relationship(back_populates="approval_events")


# ==============================================================================
# 3. ORDENS DE COMPRA OFICIAIS (PurchaseOrder)
# ==============================================================================

class PurchaseOrder(Base):
    """
    Tabela 'purchase_order' - Ordens de compra oficiais emitidas para fornecedores.
    """
    __tablename__ = "purchase_order"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    purchase_request_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("purchase_request.id", ondelete="SET NULL"), 
        nullable=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("supplier.id", ondelete="RESTRICT"), nullable=False)
    buyer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id", ondelete="RESTRICT"), nullable=False)
    cost_center_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cost_center.id", ondelete="SET NULL"), nullable=True)
    
    order_number: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", index=True)  # draft, issued, partially_received, received, closed, cancelled
    payment_terms: Mapped[str | None] = mapped_column(String(200), nullable=True)  # Ex: 30 dias, A vista
    freight_type: Mapped[str | None] = mapped_column(String(50), default="CIF")  # CIF, FOB, Sem Frete
    freight_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    expected_delivery_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))

    # Faturamento e Recebimento Físico no Almoxarifado
    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invoice_attachment: Mapped[str | None] = mapped_column(Text, nullable=True)  # Arquivo anexado da NF-e (PDF/XML/Imagem)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamentos
    items: Mapped[list["PurchaseOrderItem"]] = relationship(
        back_populates="purchase_order", 
        cascade="all, delete-orphan", 
        lazy="selectin"
    )
    supplier: Mapped["Supplier"] = relationship(lazy="selectin")
    purchase_request: Mapped["PurchaseRequest | None"] = relationship(lazy="selectin")
    supplier_quote_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("supplier_quote.id", ondelete="SET NULL"), 
        nullable=True
    )
    supplier_quote: Mapped["SupplierQuote | None"] = relationship(lazy="selectin")


class PurchaseOrderItem(Base):
    """
    Tabela 'purchase_order_item' - Linhas/produtos negociados de uma ordem de compra.
    """
    __tablename__ = "purchase_order_item"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("purchase_order.id", ondelete="CASCADE"), 
        nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product.id", ondelete="RESTRICT"), nullable=False)
    
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamentos
    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(lazy="selectin")


# ==============================================================================
# 4. PROCESSO DE COTAÇÃO (RFQ) E MAPA COMPARATIVO DE FORNECEDORES
# ==============================================================================

class QuotationProcess(Base):
    """
    Tabela 'quotation_process' - Processos de cotação abertos para solicitações aprovadas.
    """
    __tablename__ = "quotation_process"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    purchase_request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchase_request.id", ondelete="CASCADE"), nullable=False, unique=True)

    quotation_number: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="open", index=True)  # open, analyzing, completed, cancelled
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamentos
    purchase_request: Mapped["PurchaseRequest"] = relationship(back_populates="quotation_process", lazy="selectin")
    quotes: Mapped[list["SupplierQuote"]] = relationship(
        back_populates="quotation_process", 
        cascade="all, delete-orphan", 
        lazy="selectin"
    )


class SupplierQuote(Base):
    """
    Tabela 'supplier_quote' - Propostas comerciais enviadas por fornecedores concorrentes.
    """
    __tablename__ = "supplier_quote"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    quotation_process_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quotation_process.id", ondelete="CASCADE"), 
        nullable=False
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("supplier.id", ondelete="RESTRICT"), nullable=False)

    quote_reference: Mapped[str | None] = mapped_column(String(150), nullable=True)  # Ex: Proposta #1029/2026
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)  # pending, selected, rejected
    payment_terms: Mapped[str | None] = mapped_column(String(200), nullable=True)  # Ex: 30 DDL, À Vista
    freight_type: Mapped[str | None] = mapped_column(String(50), default="CIF")  # CIF, FOB, Sem Frete
    freight_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Prazo em dias úteis
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamentos
    quotation_process: Mapped["QuotationProcess"] = relationship(back_populates="quotes")
    supplier: Mapped["Supplier"] = relationship(lazy="selectin")
    items: Mapped[list["SupplierQuoteItem"]] = relationship(
        back_populates="supplier_quote", 
        cascade="all, delete-orphan", 
        lazy="selectin"
    )


class SupplierQuoteItem(Base):
    """
    Tabela 'supplier_quote_item' - Itens e preços cotados por um fornecedor específico.
    """
    __tablename__ = "supplier_quote_item"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supplier_quote_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_quote.id", ondelete="CASCADE"), 
        nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product.id", ondelete="RESTRICT"), nullable=False)

    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    brand_offered: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamentos
    supplier_quote: Mapped["SupplierQuote"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(lazy="selectin")


