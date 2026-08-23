"""
modules/inventory/models.py - Modelos Relacionais do Módulo de Estoque e Inventário (Inventory Domain)

Define a estrutura de dados relacional para:
1. Categorias de Produtos: ProductCategory.
2. Catálogo de Produtos, Insumos e Medicamentos: Product (rastreabilidade, validades, saldo físico e ponto de pedido).
3. Auditoria e Histórico de Movimentações: StockMovement (entradas por compra/ajuste, saídas por venda/perda/ajuste).
"""

import uuid
from decimal import Decimal
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
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
    """Retorna o horário atual com fuso horário UTC padronizado."""
    return datetime.now(timezone.utc)


class ProductCategory(Base):
    """
    Tabela 'product_category' - Categorias de agrupamento e taxonomia de produtos e insumos.
    """
    __tablename__ = "product_category"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamento 1:N com produtos
    products: Mapped[list["Product"]] = relationship(back_populates="category", cascade="all, delete-orphan")


class Product(Base):
    """
    Tabela 'product' - Catálogo de produtos, insumos, medicamentos e controle de estoque físico.
    """
    __tablename__ = "product"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_product_id_org"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("product_category.id", ondelete="SET NULL"), nullable=True)
    
    sku: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit_of_measure: Mapped[str] = mapped_column(String(50), default="UN")  # UN, KG, L, CX, AMP, etc.
    reference_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.0000"))
    cost_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.0000"))
    sale_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.0000"))

    # Rastreabilidade, Integrações & Validade
    external_code: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    brand: Mapped[str | None] = mapped_column(String(200), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    ncm: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_perishable: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_batch: Mapped[bool] = mapped_column(Boolean, default=False)
    shelf_life_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Parâmetros de Estoque Físico & Ponto de Pedido
    current_stock: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.0000"))
    min_stock: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    max_stock: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    storage_location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamento N:1 com categoria
    category: Mapped["ProductCategory | None"] = relationship(back_populates="products", lazy="selectin")
    
    # Relacionamento 1:N com movimentações de estoque
    movements: Mapped[list["StockMovement"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="select",
    )


class StockMovement(Base):
    """
    Tabela 'stock_movement' - Registro imutável de todas as movimentações físicas de estoque.
    
    Tipos de Movimentação (movement_type):
    - 'in_purchase': Entrada por recebimento de Ordem de Compra (PO)
    - 'in_adjustment': Entrada por ajuste manual / contagem de inventário físico
    - 'out_sale': Saída por faturamento / venda
    - 'out_adjustment': Saída por ajuste manual / perda / avaria
    - 'out_loss': Perda por validade expirada / quebra
    """
    __tablename__ = "stock_movement"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product.id", ondelete="CASCADE"), nullable=False)
    
    movement_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.0000"))
    balance_after: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    
    reference_doc: Mapped[str | None] = mapped_column(String(200), nullable=True)  # ex: "PO-2026-0001", "NF-e 12345", "Inventário Anual"
    invoice_attachment: Mapped[str | None] = mapped_column(Text, nullable=True)  # Arquivo anexado da NF-e (PDF/XML/Imagem)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relacionamento com o produto
    product: Mapped["Product"] = relationship(back_populates="movements", lazy="selectin")


class StockReservation(Base):
    """Reserva integral de estoque vinculada a um pedido de venda."""

    __tablename__ = "stock_reservation"
    __table_args__ = (
        ForeignKeyConstraint(
            ["sales_order_id", "organization_id"],
            ["sales_order.id", "sales_order.organization_id"],
            name="fk_stock_reservation_sales_order_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["business_document.id", "business_document.organization_id"],
            name="fk_stock_reservation_document_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("sales_order_id", name="uq_stock_reservation_sales_order"),
        UniqueConstraint("document_id", name="uq_stock_reservation_document"),
        UniqueConstraint(
            "organization_id",
            "reservation_number",
            name="uq_stock_reservation_number_org",
        ),
        UniqueConstraint("id", "organization_id", name="uq_stock_reservation_id_org"),
        CheckConstraint(
            "status IN ('RESERVED', 'RELEASED')",
            name="ck_stock_reservation_status",
        ),
        CheckConstraint("status_version > 0", name="ck_stock_reservation_version_positive"),
        Index("ix_stock_reservation_org_status", "organization_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    sales_order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reservation_number: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="RESERVED")
    status_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    released_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    document: Mapped["BusinessDocument"] = relationship(lazy="select")
    items: Mapped[list["StockReservationItem"]] = relationship(
        back_populates="reservation",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="StockReservationItem.product_id",
    )


class StockReservationItem(Base):
    """Quantidade reservada de um produto, sem movimentar o saldo físico."""

    __tablename__ = "stock_reservation_item"
    __table_args__ = (
        ForeignKeyConstraint(
            ["reservation_id", "organization_id"],
            ["stock_reservation.id", "stock_reservation.organization_id"],
            name="fk_stock_reservation_item_reservation_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["product_id", "organization_id"],
            ["product.id", "product.organization_id"],
            name="fk_stock_reservation_item_product_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "reservation_id",
            "product_id",
            name="uq_stock_reservation_item_product",
        ),
        CheckConstraint("quantity > 0", name="ck_stock_reservation_item_quantity_positive"),
        Index("ix_stock_reservation_item_product", "organization_id", "product_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reservation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    reservation: Mapped["StockReservation"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(
        lazy="selectin",
        overlaps="items,reservation",
    )
