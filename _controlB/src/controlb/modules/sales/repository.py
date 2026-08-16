"""
modules/sales/repository.py - Camada de Persistência do Módulo de Vendas & PDV
"""

import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from controlb.modules.sales.models import (
    SalesQuote, SalesQuoteItem, SalesOrder, SalesOrderItem,
    POSSession, POSSale, POSSaleItem
)


# ==============================================================================
# ORÇAMENTOS
# ==============================================================================

def get_quote_by_id(db: Session, quote_id: uuid.UUID, organization_id: uuid.UUID) -> SalesQuote | None:
    stmt = select(SalesQuote).where(SalesQuote.id == quote_id, SalesQuote.organization_id == organization_id)
    return db.scalars(stmt).first()


def list_quotes(db: Session, organization_id: uuid.UUID) -> list[SalesQuote]:
    stmt = select(SalesQuote).where(SalesQuote.organization_id == organization_id).order_by(SalesQuote.created_at.desc())
    return list(db.scalars(stmt).all())


def create_quote(db: Session, quote: SalesQuote) -> SalesQuote:
    db.add(quote)
    db.commit()
    db.refresh(quote)
    return quote


# ==============================================================================
# PEDIDOS DE VENDA
# ==============================================================================

def get_order_by_id(db: Session, order_id: uuid.UUID, organization_id: uuid.UUID) -> SalesOrder | None:
    stmt = select(SalesOrder).where(SalesOrder.id == order_id, SalesOrder.organization_id == organization_id)
    return db.scalars(stmt).first()


def list_orders(db: Session, organization_id: uuid.UUID) -> list[SalesOrder]:
    stmt = select(SalesOrder).where(SalesOrder.organization_id == organization_id).order_by(SalesOrder.created_at.desc())
    return list(db.scalars(stmt).all())


def create_order(db: Session, order: SalesOrder) -> SalesOrder:
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


# ==============================================================================
# PDV / FRENTE DE CAIXA
# ==============================================================================

def create_pos_session(db: Session, session: POSSession) -> POSSession:
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_active_pos_session(db: Session, organization_id: uuid.UUID) -> POSSession | None:
    stmt = select(POSSession).where(POSSession.organization_id == organization_id, POSSession.status == "OPEN")
    return db.scalars(stmt).first()


def list_pos_sessions(db: Session, organization_id: uuid.UUID) -> list[POSSession]:
    stmt = select(POSSession).where(POSSession.organization_id == organization_id).order_by(POSSession.opened_at.desc())
    return list(db.scalars(stmt).all())


def create_pos_sale(db: Session, sale: POSSale) -> POSSale:
    db.add(sale)
    db.commit()
    db.refresh(sale)
    return sale


def list_pos_sales(db: Session, organization_id: uuid.UUID) -> list[POSSale]:
    stmt = select(POSSale).where(POSSale.organization_id == organization_id).order_by(POSSale.created_at.desc())
    return list(db.scalars(stmt).all())
