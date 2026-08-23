"""
modules/inventory/repository.py - Camada de Acesso a Dados do Módulo de Estoque e Inventário (Inventory Domain)

Isola todas as consultas SQLAlchemy para:
1. Categorias de Produtos (ProductCategory).
2. Catálogo de Produtos e Saldos Físicos (Product).
3. Auditoria de Movimentações de Estoque (StockMovement).
"""

import uuid
from decimal import Decimal
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session, noload

from controlb.modules.inventory.models import (
    ProductCategory,
    Product,
    StockMovement,
    StockReservation,
    StockReservationItem,
)


# ==============================================================================
# 1. CATEGORIAS DE PRODUTOS
# ==============================================================================

def get_category_by_id(db: Session, category_id: uuid.UUID, organization_id: uuid.UUID) -> ProductCategory | None:
    stmt = select(ProductCategory).where(
        ProductCategory.id == category_id,
        ProductCategory.organization_id == organization_id
    )
    return db.scalars(stmt).first()


def get_category_by_name(db: Session, name: str, organization_id: uuid.UUID) -> ProductCategory | None:
    stmt = select(ProductCategory).where(
        func.lower(ProductCategory.name) == name.strip().lower(),
        ProductCategory.organization_id == organization_id
    )
    return db.scalars(stmt).first()


def list_categories(db: Session, organization_id: uuid.UUID) -> list[ProductCategory]:
    stmt = select(ProductCategory).where(
        ProductCategory.organization_id == organization_id
    ).order_by(ProductCategory.name.asc())
    return list(db.scalars(stmt).all())


def create_category(db: Session, category: ProductCategory) -> ProductCategory:
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def update_category(db: Session, category: ProductCategory) -> ProductCategory:
    db.commit()
    db.refresh(category)
    return category


def delete_category(db: Session, category: ProductCategory) -> None:
    db.delete(category)
    db.commit()


def count_products_in_category(db: Session, category_id: uuid.UUID, organization_id: uuid.UUID) -> int:
    stmt = select(func.count(Product.id)).where(
        Product.category_id == category_id,
        Product.organization_id == organization_id
    )
    return db.scalar(stmt) or 0


# ==============================================================================
# 2. CATÁLOGO DE PRODUTOS & SALDO DE ESTOQUE
# ==============================================================================

def get_product_by_id(db: Session, product_id: uuid.UUID, organization_id: uuid.UUID) -> Product | None:
    stmt = select(Product).where(
        Product.id == product_id,
        Product.organization_id == organization_id
    )
    return db.scalars(stmt).first()


def get_product_by_sku(db: Session, sku: str, organization_id: uuid.UUID) -> Product | None:
    stmt = select(Product).where(
        Product.sku == sku.strip().upper(),
        Product.organization_id == organization_id
    )
    return db.scalars(stmt).first()


def list_products(
    db: Session, 
    organization_id: uuid.UUID, 
    category_id: uuid.UUID | None = None
) -> list[Product]:
    stmt = select(Product).where(Product.organization_id == organization_id)
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    stmt = stmt.order_by(Product.name.asc())
    return list(db.scalars(stmt).all())


def create_product(db: Session, product: Product) -> Product:
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def update_product(db: Session, product: Product) -> Product:
    db.commit()
    db.refresh(product)
    return product


def delete_product(db: Session, product: Product) -> None:
    db.delete(product)
    db.commit()


def update_product_stock_balance(
    db: Session, 
    product_id: uuid.UUID, 
    organization_id: uuid.UUID, 
    new_balance: Decimal
) -> Product | None:
    product = get_product_by_id(db, product_id, organization_id)
    if product:
        product.current_stock = new_balance
        db.commit()
        db.refresh(product)
    return product


def get_products_below_replenishment_point(
    db: Session, 
    organization_id: uuid.UUID
) -> list[Product]:
    """
    Retorna produtos ativos cujo estoque físico atual é menor ou igual ao estoque mínimo configurado.
    """
    stmt = select(Product).where(
        Product.organization_id == organization_id,
        Product.is_active == True,
        Product.current_stock <= Product.min_stock
    ).order_by(Product.current_stock.asc(), Product.name.asc())
    return list(db.scalars(stmt).all())


# ==============================================================================
# 3. MOVIMENTAÇÕES DE ESTOQUE & AUDITORIA FÍSICA
# ==============================================================================

def create_stock_movement(db: Session, movement: StockMovement) -> StockMovement:
    db.add(movement)
    db.commit()
    db.refresh(movement)
    return movement


def list_stock_movements(
    db: Session, 
    organization_id: uuid.UUID, 
    product_id: uuid.UUID | None = None,
    limit: int = 100
) -> list[StockMovement]:
    stmt = select(StockMovement).where(StockMovement.organization_id == organization_id)
    if product_id:
        stmt = stmt.where(StockMovement.product_id == product_id)
    stmt = stmt.order_by(StockMovement.created_at.desc()).limit(limit)
    return list(db.scalars(stmt).all())


# ==============================================================================
# 4. RESERVAS E DISPONIBILIDADE
# ==============================================================================

def get_sales_order_for_update(
    db: Session,
    sales_order_id: uuid.UUID,
    organization_id: uuid.UUID,
):
    from controlb.modules.sales.models import SalesOrder

    stmt = (
        select(SalesOrder)
        .where(
            SalesOrder.id == sales_order_id,
            SalesOrder.organization_id == organization_id,
        )
        .with_for_update()
    )
    return db.scalars(stmt).first()


def lock_products_by_ids(
    db: Session,
    product_ids: list[uuid.UUID],
    organization_id: uuid.UUID,
) -> list[Product]:
    """Bloqueia produtos em ordem estável para evitar deadlocks entre reservas e PDV."""
    stable_ids = sorted(set(product_ids), key=str)
    if not stable_ids:
        return []
    stmt = (
        select(Product)
        .options(noload(Product.movements))
        .where(
            Product.organization_id == organization_id,
            Product.id.in_(stable_ids),
        )
        .order_by(Product.id.asc())
        .with_for_update()
    )
    return list(db.scalars(stmt).all())


def get_reservation_by_sales_order(
    db: Session,
    sales_order_id: uuid.UUID,
    organization_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> StockReservation | None:
    stmt = select(StockReservation).where(
        StockReservation.sales_order_id == sales_order_id,
        StockReservation.organization_id == organization_id,
    )
    if for_update:
        stmt = stmt.with_for_update()
    return db.scalars(stmt).first()


def get_reservation_by_id(
    db: Session,
    reservation_id: uuid.UUID,
    organization_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> StockReservation | None:
    stmt = select(StockReservation).where(
        StockReservation.id == reservation_id,
        StockReservation.organization_id == organization_id,
    )
    if for_update:
        stmt = stmt.with_for_update()
    return db.scalars(stmt).first()


def get_reserved_quantities(
    db: Session,
    organization_id: uuid.UUID,
    product_ids: list[uuid.UUID],
) -> dict[uuid.UUID, Decimal]:
    stable_ids = sorted(set(product_ids), key=str)
    if not stable_ids:
        return {}
    stmt = (
        select(
            StockReservationItem.product_id,
            func.sum(StockReservationItem.quantity),
        )
        .join(
            StockReservation,
            and_(
                StockReservation.id == StockReservationItem.reservation_id,
                StockReservation.organization_id == StockReservationItem.organization_id,
            ),
        )
        .where(
            StockReservation.organization_id == organization_id,
            StockReservation.status == "RESERVED",
            StockReservationItem.product_id.in_(stable_ids),
        )
        .group_by(StockReservationItem.product_id)
    )
    return {
        product_id: Decimal(str(quantity or 0))
        for product_id, quantity in db.execute(stmt).all()
    }


def save_reservation(
    db: Session,
    reservation: StockReservation,
) -> StockReservation:
    db.add(reservation)
    db.flush()
    return reservation
