"""
modules/sales/repository.py - Camada de Persistência do Módulo de Vendas & PDV
"""

import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from controlb.modules.sales.models import (
    Customer, SalesQuote, SalesQuoteItem, SalesOrder, SalesOrderItem,
    POSSession, POSSale, POSSaleItem, POSCashMovement,
    SalesGoal, PriceTable, PriceTableItem, SalesReturn, SalesReturnItem
)
from controlb.modules.sales.schemas import CustomerCreate, CustomerUpdate


# ==============================================================================
# 1. CLIENTES (Customer)
# ==============================================================================

def list_customers(db: Session, organization_id: uuid.UUID, search: str | None = None, is_active: bool | None = None) -> list[Customer]:
    stmt = select(Customer).where(Customer.organization_id == organization_id)
    if is_active is not None:
        stmt = stmt.where(Customer.is_active == is_active)
    if search:
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            (Customer.name.ilike(term)) |
            (Customer.document.ilike(term)) |
            (Customer.trade_name.ilike(term)) |
            (Customer.email.ilike(term)) |
            (Customer.phone.ilike(term))
        )
    stmt = stmt.order_by(Customer.name)
    return list(db.scalars(stmt).all())


def get_customer_by_id(db: Session, customer_id: uuid.UUID, organization_id: uuid.UUID) -> Customer | None:
    stmt = select(Customer).where(Customer.id == customer_id, Customer.organization_id == organization_id)
    return db.scalars(stmt).first()


def get_customer_by_document(db: Session, document: str, organization_id: uuid.UUID) -> Customer | None:
    stmt = select(Customer).where(Customer.document == document, Customer.organization_id == organization_id)
    return db.scalars(stmt).first()


def create_customer(
    db: Session,
    organization_id: uuid.UUID,
    data: CustomerCreate,
    contact_id: uuid.UUID | None = None,
) -> Customer:
    cid = contact_id if contact_id is not None else data.contact_id
    customer = Customer(
        id=uuid.uuid4(),
        organization_id=organization_id,
        person_type=data.person_type,
        document=data.document,
        name=data.name,
        trade_name=data.trade_name,
        state_registration=data.state_registration,
        email=data.email,
        phone=data.phone,
        address_street=data.address_street,
        address_number=data.address_number,
        address_neighborhood=data.address_neighborhood,
        address_city=data.address_city,
        address_state=data.address_state,
        address_zip_code=data.address_zip_code,
        credit_limit=data.credit_limit,
        contact_id=cid,
        is_active=data.is_active,
        notes=data.notes
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def update_customer(db: Session, customer: Customer, data: CustomerUpdate) -> Customer:
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(customer, field, val)
    db.commit()
    db.refresh(customer)
    return customer


def delete_customer(db: Session, customer: Customer) -> None:
    db.delete(customer)
    db.commit()


# ==============================================================================
# 2. ORÇAMENTOS
# ==============================================================================

def get_quote_by_id(db: Session, quote_id: uuid.UUID, organization_id: uuid.UUID) -> SalesQuote | None:
    stmt = select(SalesQuote).where(SalesQuote.id == quote_id, SalesQuote.organization_id == organization_id)
    return db.scalars(stmt).first()


def get_quote_by_id_for_update(
    db: Session,
    quote_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> SalesQuote | None:
    """Obtém e bloqueia a cotação durante uma transição transacional."""
    stmt = (
        select(SalesQuote)
        .where(
            SalesQuote.id == quote_id,
            SalesQuote.organization_id == organization_id,
        )
        .with_for_update()
    )
    return db.scalars(stmt).first()


def list_quotes(db: Session, organization_id: uuid.UUID) -> list[SalesQuote]:
    stmt = select(SalesQuote).where(SalesQuote.organization_id == organization_id).order_by(SalesQuote.created_at.desc())
    return list(db.scalars(stmt).all())


def create_quote(db: Session, quote: SalesQuote) -> SalesQuote:
    db.add(quote)
    db.flush()
    db.refresh(quote)
    return quote


# ==============================================================================
# 3. PEDIDOS DE VENDA
# ==============================================================================

def get_order_by_id(db: Session, order_id: uuid.UUID, organization_id: uuid.UUID) -> SalesOrder | None:
    stmt = select(SalesOrder).where(SalesOrder.id == order_id, SalesOrder.organization_id == organization_id)
    return db.scalars(stmt).first()


def get_order_by_id_for_update(
    db: Session,
    order_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> SalesOrder | None:
    stmt = (
        select(SalesOrder)
        .where(
            SalesOrder.id == order_id,
            SalesOrder.organization_id == organization_id,
        )
        .with_for_update()
    )
    return db.scalars(stmt).first()


def list_orders(db: Session, organization_id: uuid.UUID) -> list[SalesOrder]:
    stmt = select(SalesOrder).where(SalesOrder.organization_id == organization_id).order_by(SalesOrder.created_at.desc())
    return list(db.scalars(stmt).all())


def list_orders_by_quote_id(
    db: Session,
    sales_quote_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> list[SalesOrder]:
    stmt = select(SalesOrder).where(
        SalesOrder.sales_quote_id == sales_quote_id,
        SalesOrder.organization_id == organization_id,
    )
    return list(db.scalars(stmt).all())


def create_order(db: Session, order: SalesOrder) -> SalesOrder:
    db.add(order)
    db.flush()
    db.refresh(order)
    return order


# ==============================================================================
# 4. PDV / FRENTE DE CAIXA & SANGRIA / SUPRIMENTO
# ==============================================================================

def create_pos_session(db: Session, session: POSSession) -> POSSession:
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_pos_session_by_id(db: Session, session_id: uuid.UUID, organization_id: uuid.UUID) -> POSSession | None:
    stmt = select(POSSession).where(POSSession.id == session_id, POSSession.organization_id == organization_id)
    return db.scalars(stmt).first()


def get_active_pos_session(db: Session, organization_id: uuid.UUID) -> POSSession | None:
    stmt = select(POSSession).where(POSSession.organization_id == organization_id, POSSession.status == "OPEN").order_by(POSSession.opened_at.desc())
    return db.scalars(stmt).first()


def list_pos_sessions(db: Session, organization_id: uuid.UUID) -> list[POSSession]:
    stmt = select(POSSession).where(POSSession.organization_id == organization_id).order_by(POSSession.opened_at.desc())
    return list(db.scalars(stmt).all())


def create_pos_sale(db: Session, sale: POSSale) -> POSSale:
    db.add(sale)
    db.flush()
    db.refresh(sale)
    return sale


def list_pos_sales(db: Session, organization_id: uuid.UUID) -> list[POSSale]:
    stmt = select(POSSale).where(POSSale.organization_id == organization_id).order_by(POSSale.created_at.desc())
    return list(db.scalars(stmt).all())


def create_cash_movement(db: Session, movement: POSCashMovement) -> POSCashMovement:
    db.add(movement)
    db.commit()
    db.refresh(movement)
    return movement


def list_cash_movements(db: Session, organization_id: uuid.UUID, session_id: uuid.UUID | None = None) -> list[POSCashMovement]:
    stmt = select(POSCashMovement).where(POSCashMovement.organization_id == organization_id)
    if session_id:
        stmt = stmt.where(POSCashMovement.pos_session_id == session_id)
    stmt = stmt.order_by(POSCashMovement.created_at.desc())
    return list(db.scalars(stmt).all())


# ==============================================================================
# 5. GESTÃO COMERCIAL (Metas e Tabelas de Preços)
# ==============================================================================

def list_sales_goals(db: Session, organization_id: uuid.UUID, year: int | None = None) -> list[SalesGoal]:
    stmt = select(SalesGoal).where(SalesGoal.organization_id == organization_id)
    if year:
        stmt = stmt.where(SalesGoal.year == year)
    stmt = stmt.order_by(SalesGoal.year.desc(), SalesGoal.month.desc())
    return list(db.scalars(stmt).all())


def create_sales_goal(db: Session, goal: SalesGoal) -> SalesGoal:
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


def list_price_tables(db: Session, organization_id: uuid.UUID) -> list[PriceTable]:
    stmt = select(PriceTable).where(PriceTable.organization_id == organization_id).order_by(PriceTable.name)
    return list(db.scalars(stmt).all())


def get_price_table_by_id(db: Session, table_id: uuid.UUID, organization_id: uuid.UUID) -> PriceTable | None:
    stmt = select(PriceTable).where(PriceTable.id == table_id, PriceTable.organization_id == organization_id)
    return db.scalars(stmt).first()


def create_price_table(db: Session, table: PriceTable) -> PriceTable:
    db.add(table)
    db.commit()
    db.refresh(table)
    return table


# ==============================================================================
# 6. PÓS-VENDA (Devoluções e Trocas)
# ==============================================================================

def create_sales_return(db: Session, sales_return: SalesReturn) -> SalesReturn:
    db.add(sales_return)
    db.commit()
    db.refresh(sales_return)
    return sales_return


def list_sales_returns(db: Session, organization_id: uuid.UUID) -> list[SalesReturn]:
    stmt = select(SalesReturn).where(SalesReturn.organization_id == organization_id).order_by(SalesReturn.created_at.desc())
    return list(db.scalars(stmt).all())


def get_sales_return_by_id(db: Session, return_id: uuid.UUID, organization_id: uuid.UUID) -> SalesReturn | None:
    stmt = select(SalesReturn).where(SalesReturn.id == return_id, SalesReturn.organization_id == organization_id)
    return db.scalars(stmt).first()


def update_quote(db: Session, quote: SalesQuote) -> SalesQuote:
    db.flush()
    db.refresh(quote)
    return quote


def update_order(db: Session, order: SalesOrder) -> SalesOrder:
    db.flush()
    db.refresh(order)
    return order


def get_sales_goal_by_id(db: Session, goal_id: uuid.UUID, organization_id: uuid.UUID) -> SalesGoal | None:
    stmt = select(SalesGoal).where(SalesGoal.id == goal_id, SalesGoal.organization_id == organization_id)
    return db.scalars(stmt).first()


def delete_sales_goal(db: Session, goal: SalesGoal) -> None:
    db.delete(goal)
    db.commit()


def delete_price_table(db: Session, table: PriceTable) -> None:
    db.delete(table)
    db.commit()


def delete_sales_return(db: Session, sales_return: SalesReturn) -> None:
    db.delete(sales_return)
    db.commit()
