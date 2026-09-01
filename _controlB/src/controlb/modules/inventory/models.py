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
    text,
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


class InventoryLocation(Base):
    """Local físico cadastral; não possui ciclo documental próprio."""

    __tablename__ = "inventory_location"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_inventory_location_org_code"),
        UniqueConstraint("id", "organization_id", name="uq_inventory_location_id_org"),
        Index("ix_inventory_location_org_active", "organization_id", "is_active"),
        Index(
            "uq_inventory_location_default_org",
            "organization_id",
            unique=True,
            postgresql_where=text("is_default"),
            sqlite_where=text("is_default = 1"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class InventoryBalance(Base):
    """Projeção do saldo físico de um produto em uma localização."""

    __tablename__ = "inventory_balance"
    __table_args__ = (
        ForeignKeyConstraint(
            ["product_id", "organization_id"],
            ["product.id", "product.organization_id"],
            name="fk_inventory_balance_product_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["inventory_location.id", "inventory_location.organization_id"],
            name="fk_inventory_balance_location_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "product_id", "location_id", name="uq_inventory_balance_product_location"
        ),
        CheckConstraint("quantity >= 0", name="ck_inventory_balance_quantity_nonnegative"),
        Index("ix_inventory_balance_location", "organization_id", "location_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    location_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), nullable=False, default=Decimal("0.0000")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


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
    balances: Mapped[list["InventoryBalance"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )


class InventoryReceipt(Base):
    """Cabeçalho imutável de um recebimento físico originado por compra."""

    __tablename__ = "inventory_receipt"
    __table_args__ = (
        ForeignKeyConstraint(
            ["purchase_order_id", "organization_id"],
            ["purchase_order.id", "purchase_order.organization_id"],
            name="fk_inventory_receipt_purchase_order_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["business_document.id", "business_document.organization_id"],
            name="fk_inventory_receipt_document_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["fiscal_document_id", "organization_id"],
            ["fiscal_document.id", "fiscal_document.organization_id"],
            name="fk_inventory_receipt_fiscal_document_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("purchase_order_id", name="uq_inventory_receipt_purchase_order"),
        UniqueConstraint("document_id", name="uq_inventory_receipt_document"),
        UniqueConstraint(
            "organization_id",
            "receipt_number",
            name="uq_inventory_receipt_org_number",
        ),
        UniqueConstraint("id", "organization_id", name="uq_inventory_receipt_id_org"),
        Index("ix_inventory_receipt_org_received", "organization_id", "received_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    fiscal_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    receipt_number: Mapped[str] = mapped_column(String(100), nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False)
    invoice_attachment: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    document: Mapped["BusinessDocument"] = relationship(lazy="select")
    movements: Mapped[list["StockMovement"]] = relationship(
        back_populates="receipt",
        lazy="selectin",
        overlaps="delivery,movements",
    )


class InventoryDelivery(Base):
    """Expedição física integral de um pedido de venda."""

    __tablename__ = "inventory_delivery"
    __table_args__ = (
        ForeignKeyConstraint(
            ["sales_order_id", "organization_id"],
            ["sales_order.id", "sales_order.organization_id"],
            name="fk_inventory_delivery_sales_order_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["reservation_id", "organization_id"],
            ["stock_reservation.id", "stock_reservation.organization_id"],
            name="fk_inventory_delivery_reservation_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["business_document.id", "business_document.organization_id"],
            name="fk_inventory_delivery_document_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["fiscal_document_id", "organization_id"],
            ["fiscal_document.id", "fiscal_document.organization_id"],
            name="fk_inventory_delivery_fiscal_document_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("sales_order_id", name="uq_inventory_delivery_sales_order"),
        UniqueConstraint("reservation_id", name="uq_inventory_delivery_reservation"),
        UniqueConstraint("document_id", name="uq_inventory_delivery_document"),
        UniqueConstraint("id", "organization_id", name="uq_inventory_delivery_id_org"),
        UniqueConstraint(
            "organization_id", "delivery_number", name="uq_inventory_delivery_number_org"
        ),
        CheckConstraint(
            "status IN ('DISPATCHED', 'DELIVERED', 'CANCELLED')",
            name="ck_inventory_delivery_status",
        ),
        Index("ix_inventory_delivery_org_status", "organization_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    sales_order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    fiscal_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    delivery_number: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DISPATCHED")
    stock_posted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    dispatched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    delivered_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    document: Mapped["BusinessDocument"] = relationship(lazy="select")
    items: Mapped[list["InventoryDeliveryItem"]] = relationship(
        back_populates="delivery",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="InventoryDeliveryItem.product_id",
    )
    movements: Mapped[list["StockMovement"]] = relationship(
        back_populates="delivery", lazy="selectin", overlaps="movements,receipt"
    )


class InventoryDeliveryItem(Base):
    """Snapshot imutável dos itens expedidos."""

    __tablename__ = "inventory_delivery_item"
    __table_args__ = (
        ForeignKeyConstraint(
            ["delivery_id", "organization_id"],
            ["inventory_delivery.id", "inventory_delivery.organization_id"],
            name="fk_inventory_delivery_item_delivery_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["product_id", "organization_id"],
            ["product.id", "product.organization_id"],
            name="fk_inventory_delivery_item_product_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "delivery_id", "product_id", name="uq_inventory_delivery_item_product"
        ),
        CheckConstraint(
            "quantity > 0", name="ck_inventory_delivery_item_quantity_positive"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    delivery_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    delivery: Mapped["InventoryDelivery"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(
        lazy="selectin", overlaps="delivery,items"
    )


class InventoryTransfer(Base):
    """Movimentação interna atômica entre duas localizações físicas."""

    __tablename__ = "inventory_transfer"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["business_document.id", "business_document.organization_id"],
            name="fk_inventory_transfer_document_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["source_location_id", "organization_id"],
            ["inventory_location.id", "inventory_location.organization_id"],
            name="fk_inventory_transfer_source_location_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["destination_location_id", "organization_id"],
            ["inventory_location.id", "inventory_location.organization_id"],
            name="fk_inventory_transfer_destination_location_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("document_id", name="uq_inventory_transfer_document"),
        UniqueConstraint("id", "organization_id", name="uq_inventory_transfer_id_org"),
        UniqueConstraint(
            "organization_id", "transfer_number", name="uq_inventory_transfer_number_org"
        ),
        CheckConstraint(
            "source_location_id <> destination_location_id",
            name="ck_inventory_transfer_distinct_locations",
        ),
        CheckConstraint(
            "status IN ('COMPLETED', 'CANCELLED')",
            name="ck_inventory_transfer_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    transfer_number: Mapped[str] = mapped_column(String(100), nullable=False)
    source_location_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    destination_location_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="COMPLETED")
    completed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    document: Mapped["BusinessDocument"] = relationship(lazy="select")
    items: Mapped[list["InventoryTransferItem"]] = relationship(
        back_populates="transfer",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="InventoryTransferItem.product_id",
    )


class InventoryTransferItem(Base):
    __tablename__ = "inventory_transfer_item"
    __table_args__ = (
        ForeignKeyConstraint(
            ["transfer_id", "organization_id"],
            ["inventory_transfer.id", "inventory_transfer.organization_id"],
            name="fk_inventory_transfer_item_transfer_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["product_id", "organization_id"],
            ["product.id", "product.organization_id"],
            name="fk_inventory_transfer_item_product_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "transfer_id", "product_id", name="uq_inventory_transfer_item_product"
        ),
        CheckConstraint(
            "quantity > 0", name="ck_inventory_transfer_item_quantity_positive"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    transfer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    transfer: Mapped["InventoryTransfer"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(
        lazy="selectin", overlaps="items,transfer"
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
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["business_document.id", "business_document.organization_id"],
            name="fk_stock_movement_document_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["receipt_id", "organization_id"],
            ["inventory_receipt.id", "inventory_receipt.organization_id"],
            name="fk_stock_movement_receipt_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["delivery_id", "organization_id"],
            ["inventory_delivery.id", "inventory_delivery.organization_id"],
            name="fk_stock_movement_delivery_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["transfer_id", "organization_id"],
            ["inventory_transfer.id", "inventory_transfer.organization_id"],
            name="fk_stock_movement_transfer_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["inventory_location.id", "inventory_location.organization_id"],
            name="fk_stock_movement_location_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["source_location_id", "organization_id"],
            ["inventory_location.id", "inventory_location.organization_id"],
            name="fk_stock_movement_source_location_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["destination_location_id", "organization_id"],
            ["inventory_location.id", "inventory_location.organization_id"],
            name="fk_stock_movement_destination_location_org",
            ondelete="RESTRICT",
        ),
        Index("ix_stock_movement_receipt", "organization_id", "receipt_id"),
        Index("ix_stock_movement_delivery", "organization_id", "delivery_id"),
        Index("ix_stock_movement_transfer", "organization_id", "transfer_id"),
        Index("ix_stock_movement_document", "organization_id", "document_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    receipt_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    delivery_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    transfer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    location_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_location_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    destination_location_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    fiscal_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    payable_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    
    movement_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.0000"))
    balance_after: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    location_balance_after: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4), nullable=True
    )
    
    reference_doc: Mapped[str | None] = mapped_column(String(200), nullable=True)  # ex: "PO-2026-0001", "NF-e 12345", "Inventário Anual"
    invoice_attachment: Mapped[str | None] = mapped_column(Text, nullable=True)  # Arquivo anexado da NF-e (PDF/XML/Imagem)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relacionamento com o produto e documento canônico
    document: Mapped["BusinessDocument"] = relationship(
        lazy="select", overlaps="delivery,movements,receipt"
    )
    product: Mapped["Product"] = relationship(back_populates="movements", lazy="selectin")
    receipt: Mapped["InventoryReceipt | None"] = relationship(
        back_populates="movements",
        lazy="select",
        overlaps="delivery,document,movements",
    )
    delivery: Mapped["InventoryDelivery | None"] = relationship(
        back_populates="movements",
        lazy="select",
        overlaps="document,movements,receipt",
    )


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
            "status IN ('RESERVED', 'RELEASED', 'CONSUMED')",
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
    consumed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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


class InventoryImportBatch(Base):
    """
    Tabela 'inventory_import_batch' - Registro de lote de importação de planilha de estoque.
    Audita todo o processo de carga, incluindo apuração de vendas, reposições, alterações de preço e estagnação.
    """
    __tablename__ = "inventory_import_batch"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["business_document.id", "business_document.organization_id"],
            name="fk_inventory_import_batch_document_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "organization_id", name="uq_inventory_import_batch_id_org"),
        UniqueConstraint("document_id", name="uq_inventory_import_batch_document"),
        Index("ix_inventory_import_batch_org_created", "organization_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    batch_number: Mapped[str] = mapped_column(String(50), nullable=False)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    inventory_date: Mapped[str | None] = mapped_column(String(100), nullable=True)

    total_products_read: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_products_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_products_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_categories_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    sales_identified_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_sales_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    total_sales_estimated_revenue: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)

    entries_identified_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_entries_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    total_entries_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)

    cost_increases_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_decreases_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    stagnant_products_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_stagnant_capital: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)

    total_inventory_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    total_inventory_sale: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)

    imported_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    document: Mapped["BusinessDocument"] = relationship(lazy="select")
    items: Mapped[list["InventoryImportItem"]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        lazy="select",
    )


class InventoryImportItem(Base):
    """
    Tabela 'inventory_import_item' - Item individual auditado dentro de um lote de importação.
    Registra a variação de saldo, preço de custo, preço de venda, receita apurada e valor estagnado.
    """
    __tablename__ = "inventory_import_item"
    __table_args__ = (
        ForeignKeyConstraint(
            ["batch_id", "organization_id"],
            ["inventory_import_batch.id", "inventory_import_batch.organization_id"],
            name="fk_inventory_import_item_batch_org",
            ondelete="CASCADE",
        ),
        Index("ix_inventory_import_item_batch", "batch_id"),
        Index("ix_inventory_import_item_product", "organization_id", "product_id"),
        Index("ix_inventory_import_item_action", "organization_id", "action_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("product.id", ondelete="SET NULL"), nullable=True)

    code: Mapped[str] = mapped_column(String(100), nullable=False)
    barcode: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    ncm: Mapped[str | None] = mapped_column(String(20), nullable=True)
    unit_of_measure: Mapped[str] = mapped_column(String(20), default="UN", nullable=False)

    action_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'created', 'sale_detected', 'entry_detected', 'stagnant_unchanged', 'zero_stock_unchanged'

    previous_stock: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    new_stock: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    delta_stock: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)

    previous_cost_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    new_cost_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    cost_variation_amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    cost_variation_percent: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)

    previous_sale_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    new_sale_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    sale_variation_amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    sale_variation_percent: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)

    stagnant_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    estimated_sales_revenue: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    batch: Mapped["InventoryImportBatch"] = relationship(back_populates="items")
    product: Mapped["Product | None"] = relationship(lazy="selectin")
