"""
modules/sales/repository.py - Camada de Persistência do Módulo de Vendas & PDV
"""

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from controlb.modules.documents.models import BusinessDocument
from controlb.modules.sales.models import (
    CommercialApprovalRequest,
    CommercialSettings,
    CreditApprovalRequest,
    Customer,
    POSCashMovement,
    POSSale,
    POSSaleItem,
    POSSession,
    PriceTable,
    PriceTableItem,
    SalesGoal,
    SalesOrder,
    SalesOrderItem,
    SalesQuote,
    SalesQuoteItem,
    SalesReturn,
    SalesReturnItem,
)
from controlb.modules.sales.schemas import CustomerCreate, CustomerUpdate

# ==============================================================================
# 1. CLIENTES (Customer)
# ==============================================================================

def list_customers(db: Session, organization_id: uuid.UUID, search: str | None = None, is_active: bool | None = None) -> list[Customer]:
    from controlb.modules.identity.models import Contact
    stmt = select(Customer).outerjoin(Contact, (Customer.contact_id == Contact.id) & (Contact.organization_id == organization_id)).where(Customer.organization_id == organization_id)
    if is_active is not None:
        stmt = stmt.where(Customer.is_active == is_active)
    if search:
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            (Customer.name.ilike(term)) |
            (Customer.document.ilike(term)) |
            (Customer.trade_name.ilike(term)) |
            (Contact.email.ilike(term)) |
            (Contact.phone.ilike(term)) |
            (Contact.mobile.ilike(term))
        )
    stmt = stmt.order_by(Customer.name)
    return list(db.scalars(stmt).all())


def get_customer_by_id(db: Session, customer_id: uuid.UUID, organization_id: uuid.UUID) -> Customer | None:
    stmt = select(Customer).where(Customer.id == customer_id, Customer.organization_id == organization_id)
    return db.scalars(stmt).first()


def get_customer_by_id_for_update(
    db: Session,
    customer_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> Customer | None:
    stmt = (
        select(Customer)
        .where(
            Customer.id == customer_id,
            Customer.organization_id == organization_id,
        )
        .with_for_update()
    )
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
        website=data.website,
        segment=data.segment,
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
        if field not in {"email", "phone", "secondary_phone", "contact_role"}:
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


def get_unbilled_order_exposure(
    db: Session,
    organization_id: uuid.UUID,
    customer_id: uuid.UUID,
    *,
    exclude_order_id: uuid.UUID | None = None,
) -> Decimal:
    """Soma pedidos ainda não transformados em contas a receber."""
    stmt = (
        select(func.coalesce(func.sum(SalesOrder.net_amount), 0))
        .join(BusinessDocument, BusinessDocument.id == SalesOrder.document_id)
        .where(
            SalesOrder.organization_id == organization_id,
            BusinessDocument.organization_id == organization_id,
            SalesOrder.customer_id == customer_id,
            BusinessDocument.current_status != "CANCELLED",
            SalesOrder.credit_status != "REJECTED",
            SalesOrder.billing_status != "INVOICED",
        )
    )
    if exclude_order_id:
        stmt = stmt.where(SalesOrder.id != exclude_order_id)
    return Decimal(db.scalar(stmt) or 0)


def get_open_receivable_exposure(
    db: Session,
    organization_id: uuid.UUID,
    customer_document: str,
) -> Decimal:
    """Soma o saldo financeiro aberto sem duplicar pedidos já faturados."""
    from controlb.modules.finance.models import Receivable

    stmt = select(func.coalesce(func.sum(Receivable.outstanding_amount), 0)).where(
        Receivable.organization_id == organization_id,
        Receivable.customer_document == customer_document,
        Receivable.status.notin_(("RECEIVED", "CANCELLED")),
    )
    return Decimal(db.scalar(stmt) or 0)


def save_credit_approval_request(
    db: Session,
    approval: CreditApprovalRequest,
) -> CreditApprovalRequest:
    db.add(approval)
    db.flush()
    db.refresh(approval)
    return approval


def get_credit_approval_by_id_for_update(
    db: Session,
    approval_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> CreditApprovalRequest | None:
    stmt = (
        select(CreditApprovalRequest)
        .where(
            CreditApprovalRequest.id == approval_id,
            CreditApprovalRequest.organization_id == organization_id,
        )
        .options(selectinload(CreditApprovalRequest.order))
        .with_for_update()
    )
    return db.scalars(stmt).first()


def get_credit_approval_by_order_id(
    db: Session,
    order_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> CreditApprovalRequest | None:
    stmt = select(CreditApprovalRequest).where(
        CreditApprovalRequest.sales_order_id == order_id,
        CreditApprovalRequest.organization_id == organization_id,
    )
    return db.scalars(stmt).first()


def list_credit_approval_requests(
    db: Session,
    organization_id: uuid.UUID,
    approval_status: str | None = None,
) -> list[CreditApprovalRequest]:
    stmt = (
        select(CreditApprovalRequest)
        .where(CreditApprovalRequest.organization_id == organization_id)
        .options(selectinload(CreditApprovalRequest.order))
    )
    if approval_status:
        stmt = stmt.where(CreditApprovalRequest.status == approval_status)
    stmt = stmt.order_by(CreditApprovalRequest.created_at.desc())
    return list(db.scalars(stmt).all())


def save_commercial_approval_request(
    db: Session,
    approval: CommercialApprovalRequest,
) -> CommercialApprovalRequest:
    db.add(approval)
    db.flush()
    db.refresh(approval)
    return approval


def get_commercial_approval_by_id_for_update(
    db: Session,
    approval_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> CommercialApprovalRequest | None:
    stmt = (
        select(CommercialApprovalRequest)
        .where(
            CommercialApprovalRequest.id == approval_id,
            CommercialApprovalRequest.organization_id == organization_id,
        )
        .options(
            selectinload(CommercialApprovalRequest.quote),
            selectinload(CommercialApprovalRequest.order),
        )
        .with_for_update()
    )
    return db.scalars(stmt).first()


def get_commercial_approval_by_document_type(
    db: Session,
    organization_id: uuid.UUID,
    approval_type: str,
    *,
    quote_id: uuid.UUID | None = None,
    order_id: uuid.UUID | None = None,
) -> CommercialApprovalRequest | None:
    stmt = select(CommercialApprovalRequest).where(
        CommercialApprovalRequest.organization_id == organization_id,
        CommercialApprovalRequest.approval_type == approval_type,
    )
    if quote_id:
        stmt = stmt.where(CommercialApprovalRequest.sales_quote_id == quote_id)
    elif order_id:
        stmt = stmt.where(CommercialApprovalRequest.sales_order_id == order_id)
    else:
        return None
    return db.scalars(stmt).first()


def list_commercial_approval_requests(
    db: Session,
    organization_id: uuid.UUID,
    approval_status: str | None = None,
    approval_type: str | None = None,
) -> list[CommercialApprovalRequest]:
    stmt = (
        select(CommercialApprovalRequest)
        .where(CommercialApprovalRequest.organization_id == organization_id)
        .options(
            selectinload(CommercialApprovalRequest.quote),
            selectinload(CommercialApprovalRequest.order),
        )
    )
    if approval_status:
        stmt = stmt.where(CommercialApprovalRequest.status == approval_status)
    if approval_type:
        stmt = stmt.where(CommercialApprovalRequest.approval_type == approval_type)
    stmt = stmt.order_by(CommercialApprovalRequest.created_at.desc())
    return list(db.scalars(stmt).all())


def list_commercial_approvals_for_document(
    db: Session,
    organization_id: uuid.UUID,
    *,
    quote_id: uuid.UUID | None = None,
    order_id: uuid.UUID | None = None,
) -> list[CommercialApprovalRequest]:
    stmt = select(CommercialApprovalRequest).where(
        CommercialApprovalRequest.organization_id == organization_id
    )
    if quote_id:
        stmt = stmt.where(CommercialApprovalRequest.sales_quote_id == quote_id)
    elif order_id:
        stmt = stmt.where(CommercialApprovalRequest.sales_order_id == order_id)
    else:
        return []
    return list(db.scalars(stmt).all())


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


def get_commercial_settings(
    db: Session,
    organization_id: uuid.UUID,
) -> CommercialSettings | None:
    stmt = select(CommercialSettings).where(
        CommercialSettings.organization_id == organization_id
    )
    return db.scalars(stmt).first()


def save_commercial_settings(
    db: Session,
    settings: CommercialSettings,
) -> CommercialSettings:
    db.add(settings)
    db.flush()
    db.refresh(settings)
    return settings


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
