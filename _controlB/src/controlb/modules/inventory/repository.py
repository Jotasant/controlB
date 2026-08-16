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
from sqlalchemy.orm import Session

from controlb.modules.inventory.models import ProductCategory, Product, StockMovement


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
