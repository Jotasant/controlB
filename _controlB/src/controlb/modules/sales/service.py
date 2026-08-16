"""
modules/sales/service.py - Regras de Negócio e Serviços do Módulo de Vendas & PDV
"""

import uuid
from datetime import datetime, timezone, date
from decimal import Decimal
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from controlb.logger import logger
from controlb.modules.identity.models import User
from controlb.modules.sales import models, repository, schemas


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ==============================================================================
# ORÇAMENTOS (QUOTES)
# ==============================================================================

def create_sales_quote(
    db: Session,
    organization_id: uuid.UUID,
    current_user: User,
    payload: schemas.SalesQuoteCreate
) -> models.SalesQuote:
    quote_num = f"ORC-{date.today().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
    
    quote = models.SalesQuote(
        organization_id=organization_id,
        quote_number=quote_num,
        customer_name=payload.customer_name.strip(),
        customer_document=payload.customer_document.strip() if payload.customer_document else None,
        customer_email=payload.customer_email.strip() if payload.customer_email else None,
        customer_phone=payload.customer_phone.strip() if payload.customer_phone else None,
        valid_until=payload.valid_until,
        notes=payload.notes,
        created_by_id=current_user.id
    )

    total_gross = Decimal("0.00")
    total_disc = Decimal("0.00")

    for it in payload.items:
        it_total = (it.quantity * it.unit_price) - it.discount_amount
        total_gross += (it.quantity * it.unit_price)
        total_disc += it.discount_amount
        
        q_item = models.SalesQuoteItem(
            product_id=it.product_id,
            quantity=it.quantity,
            unit_price=it.unit_price,
            discount_amount=it.discount_amount,
            total_price=it_total,
            notes=it.notes
        )
        quote.items.append(q_item)

    quote.total_amount = total_gross
    quote.discount_amount = total_disc
    quote.net_amount = total_gross - total_disc

    return repository.create_quote(db, quote)


def list_sales_quotes(db: Session, organization_id: uuid.UUID) -> list[models.SalesQuote]:
    return repository.list_quotes(db, organization_id)


# ==============================================================================
# PEDIDOS DE VENDA (SALES ORDERS)
# ==============================================================================

def create_sales_order(
    db: Session,
    organization_id: uuid.UUID,
    current_user: User,
    payload: schemas.SalesOrderCreate
) -> models.SalesOrder:
    order_num = f"PED-{date.today().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"

    order = models.SalesOrder(
        organization_id=organization_id,
        order_number=order_num,
        customer_name=payload.customer_name.strip(),
        customer_document=payload.customer_document.strip() if payload.customer_document else None,
        payment_terms=payload.payment_terms,
        delivery_status=payload.delivery_status,
        notes=payload.notes,
        created_by_id=current_user.id
    )

    total_gross = Decimal("0.00")
    total_disc = Decimal("0.00")

    for it in payload.items:
        it_total = (it.quantity * it.unit_price) - it.discount_amount
        total_gross += (it.quantity * it.unit_price)
        total_disc += it.discount_amount

        o_item = models.SalesOrderItem(
            product_id=it.product_id,
            quantity=it.quantity,
            unit_price=it.unit_price,
            discount_amount=it.discount_amount,
            total_price=it_total,
            notes=it.notes
        )
        order.items.append(o_item)

    order.total_amount = total_gross
    order.discount_amount = total_disc
    order.net_amount = total_gross - total_disc

    return repository.create_order(db, order)


def list_sales_orders(db: Session, organization_id: uuid.UUID) -> list[models.SalesOrder]:
    return repository.list_orders(db, organization_id)


# ==============================================================================
# FRENTE DE CAIXA / PDV BALCÃO
# ==============================================================================

def open_pos_session(
    db: Session,
    organization_id: uuid.UUID,
    current_user: User,
    payload: schemas.POSSessionCreate
) -> models.POSSession:
    session = models.POSSession(
        organization_id=organization_id,
        pos_terminal=payload.pos_terminal,
        opened_by_id=current_user.id,
        opening_cash=payload.opening_cash,
        status="OPEN"
    )
    return repository.create_pos_session(db, session)


def list_pos_sessions(db: Session, organization_id: uuid.UUID) -> list[models.POSSession]:
    return repository.list_pos_sessions(db, organization_id)


def process_pos_sale(
    db: Session,
    organization_id: uuid.UUID,
    current_user: User,
    payload: schemas.POSSaleCreate
) -> models.POSSale:
    if not payload.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A venda do PDV deve conter pelo menos 1 item.")

    sale = models.POSSale(
        organization_id=organization_id,
        pos_session_id=payload.pos_session_id,
        customer_name=payload.customer_name.strip() if payload.customer_name else "Consumidor Final",
        customer_document=payload.customer_document.strip() if payload.customer_document else None,
        discount_amount=payload.discount_amount,
        payment_method=payload.payment_method,
        created_by_id=current_user.id
    )

    total_gross = Decimal("0.00")

    for it in payload.items:
        it_total = (it.quantity * it.unit_price)
        total_gross += it_total

        sale_item = models.POSSaleItem(
            product_id=it.product_id,
            quantity=it.quantity,
            unit_price=it.unit_price,
            total_price=it_total
        )
        sale.items.append(sale_item)

    sale.total_amount = total_gross
    sale.net_amount = max(Decimal("0.00"), total_gross - payload.discount_amount)

    saved_sale = repository.create_pos_sale(db, sale)
    logger.info(f"🛍️ [PDV SALE] Venda #{str(saved_sale.id)[:8]} concluída com sucesso: {saved_sale.net_amount} R$ via {saved_sale.payment_method}")
    return saved_sale


def list_pos_sales(db: Session, organization_id: uuid.UUID) -> list[models.POSSale]:
    return repository.list_pos_sales(db, organization_id)
