"""
modules/sales/service.py - Regras de Negócio e Serviços do Módulo de Vendas & PDV
"""

import uuid
from datetime import datetime, timezone, date, timedelta
from decimal import Decimal
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from controlb.logger import logger
from controlb.modules.identity.models import User
from controlb.modules.inventory.models import Product, StockMovement
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
        customer_id=payload.customer_id,
        opportunity_id=payload.opportunity_id,
        customer_name=payload.customer_name.strip(),
        customer_document=payload.customer_document.strip() if payload.customer_document else None,
        customer_email=payload.customer_email.strip() if payload.customer_email else None,
        customer_phone=payload.customer_phone.strip() if payload.customer_phone else None,
        payment_terms=payload.payment_terms or "À Vista",
        valid_until=payload.valid_until or (date.today() + timedelta(days=15)),
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


def get_sales_quote(db: Session, quote_id: uuid.UUID, organization_id: uuid.UUID) -> models.SalesQuote:
    quote = repository.get_quote_by_id(db, quote_id, organization_id)
    if not quote:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orçamento não encontrado.")
    return quote


def update_sales_quote(
    db: Session,
    quote_id: uuid.UUID,
    organization_id: uuid.UUID,
    payload: schemas.SalesQuoteUpdate
) -> models.SalesQuote:
    quote = repository.get_quote_by_id(db, quote_id, organization_id)
    if not quote:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orçamento não encontrado.")

    if payload.customer_id is not None:
        quote.customer_id = payload.customer_id
    if payload.opportunity_id is not None:
        quote.opportunity_id = payload.opportunity_id
    if payload.customer_name is not None:
        quote.customer_name = payload.customer_name.strip()
    if payload.customer_document is not None:
        quote.customer_document = payload.customer_document.strip() or None
    if payload.customer_email is not None:
        quote.customer_email = payload.customer_email.strip() or None
    if payload.customer_phone is not None:
        quote.customer_phone = payload.customer_phone.strip() or None
    if payload.payment_terms is not None:
        quote.payment_terms = payload.payment_terms
    if payload.valid_until is not None:
        quote.valid_until = payload.valid_until
    if payload.status is not None:
        quote.status = payload.status.upper()
    if payload.notes is not None:
        quote.notes = payload.notes

    if payload.items is not None:
        quote.items.clear()
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

    return repository.update_quote(db, quote)


def update_sales_quote_status(
    db: Session,
    quote_id: uuid.UUID,
    organization_id: uuid.UUID,
    new_status: str
) -> models.SalesQuote:
    quote = repository.get_quote_by_id(db, quote_id, organization_id)
    if not quote:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orçamento não encontrado.")
    quote.status = new_status.upper()
    return repository.update_quote(db, quote)


def convert_quote_to_order(
    db: Session,
    quote_id: uuid.UUID,
    organization_id: uuid.UUID,
    current_user: User
) -> models.SalesOrder:
    quote = repository.get_quote_by_id(db, quote_id, organization_id)
    if not quote:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orçamento não encontrado.")
    
    order_num = f"PED-{date.today().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
    order = models.SalesOrder(
        organization_id=organization_id,
        order_number=order_num,
        customer_id=quote.customer_id,
        sales_quote_id=quote.id,
        opportunity_id=quote.opportunity_id,
        customer_name=quote.customer_name,
        customer_document=quote.customer_document,
        payment_terms=quote.payment_terms,
        delivery_status="PENDING",
        billing_status="PENDING",
        status="CONFIRMED",
        total_amount=quote.total_amount,
        discount_amount=quote.discount_amount,
        net_amount=quote.net_amount,
        notes=f"Convertido do Orçamento #{quote.quote_number}. {quote.notes or ''}".strip(),
        created_by_id=current_user.id
    )

    for q_it in quote.items:
        o_item = models.SalesOrderItem(
            product_id=q_it.product_id,
            quantity=q_it.quantity,
            unit_price=q_it.unit_price,
            discount_amount=q_it.discount_amount,
            total_price=q_it.total_price,
            notes=q_it.notes
        )
        order.items.append(o_item)

    quote.status = "CONVERTED"
    db.add(order)
    
    # Se vinculado a uma oportunidade CRM, atualiza o estágio da oportunidade para WON
    if quote.opportunity_id:
        from controlb.modules.crm import repository as crm_repo
        opp = crm_repo.get_opportunity_by_id(db, quote.opportunity_id, organization_id)
        if opp:
            opp.stage = "WON"
            db.add(opp)

    db.commit()
    db.refresh(order)
    return order


def list_sales_quotes(db: Session, organization_id: uuid.UUID, opportunity_id: uuid.UUID | None = None) -> list[models.SalesQuote]:
    quotes = repository.list_quotes(db, organization_id)
    if opportunity_id:
        quotes = [q for q in quotes if q.opportunity_id == opportunity_id]
    return quotes


def delete_sales_quote(db: Session, quote_id: uuid.UUID, organization_id: uuid.UUID):
    quote = repository.get_quote_by_id(db, quote_id, organization_id)
    if not quote:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orçamento não encontrado.")
    repository.delete_quote(db, quote)
    return {"message": "Orçamento excluído com sucesso."}


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
        customer_id=payload.customer_id,
        sales_quote_id=payload.sales_quote_id,
        opportunity_id=payload.opportunity_id,
        customer_name=payload.customer_name.strip(),
        customer_document=payload.customer_document.strip() if payload.customer_document else None,
        payment_terms=payload.payment_terms or "À Vista",
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


def get_sales_order(db: Session, order_id: uuid.UUID, organization_id: uuid.UUID) -> models.SalesOrder:
    order = repository.get_order_by_id(db, order_id, organization_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido de venda não encontrado.")
    return order


def list_sales_orders(db: Session, organization_id: uuid.UUID) -> list[models.SalesOrder]:
    return repository.list_orders(db, organization_id)


def delete_sales_order(db: Session, order_id: uuid.UUID, organization_id: uuid.UUID):
    order = repository.get_order_by_id(db, order_id, organization_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido de venda não encontrado.")
    repository.delete_order(db, order)
    return {"message": "Pedido de venda excluído com sucesso."}



# ==============================================================================
# FRENTE DE CAIXA / PDV BALCÃO
# ==============================================================================

def open_pos_session(
    db: Session,
    organization_id: uuid.UUID,
    current_user: User,
    payload: schemas.POSSessionCreate
) -> models.POSSession:
    # Se já existir uma sessão aberta, podemos reaproveitá-la ou avisar
    active = repository.get_active_pos_session(db, organization_id)
    if active:
        return active

    session = models.POSSession(
        organization_id=organization_id,
        pos_terminal=payload.pos_terminal,
        opened_by_id=current_user.id,
        opening_cash=payload.opening_cash,
        status="OPEN"
    )
    return repository.create_pos_session(db, session)


def get_active_pos_session(db: Session, organization_id: uuid.UUID) -> models.POSSession | None:
    return repository.get_active_pos_session(db, organization_id)


def close_pos_session(
    db: Session,
    organization_id: uuid.UUID,
    session_id: uuid.UUID,
    current_user: User,
    payload: schemas.POSSessionClose
) -> models.POSSession:
    session = repository.get_pos_session_by_id(db, session_id, organization_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Turno de caixa não encontrado.")
    if session.status == "CLOSED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Este turno de caixa já foi encerrado.")
    
    session.status = "CLOSED"
    session.closed_at = utcnow()
    session.closing_cash = payload.closing_cash
    db.commit()
    db.refresh(session)
    logger.info(f"🔒 [PDV CAIXA] Turno de caixa {session.pos_terminal} (#{str(session.id)[:8]}) encerrado por {current_user.email} com R$ {session.closing_cash}")
    return session


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

    # 1. Vincular automaticamente à sessão de caixa ativa se não foi enviada
    pos_session_id = payload.pos_session_id
    if not pos_session_id:
        active_sess = repository.get_active_pos_session(db, organization_id)
        if active_sess:
            pos_session_id = active_sess.id

    sale = models.POSSale(
        organization_id=organization_id,
        pos_session_id=pos_session_id,
        customer_name=payload.customer_name.strip() if payload.customer_name else "Consumidor Final",
        customer_document=payload.customer_document.strip() if payload.customer_document else None,
        discount_amount=payload.discount_amount,
        payment_method=payload.payment_method,
        created_by_id=current_user.id
    )

    total_gross = Decimal("0.00")

    for it in payload.items:
        # Validar produto e baixar estoque
        product = db.query(Product).filter(
            Product.id == it.product_id,
            Product.organization_id == organization_id
        ).first()

        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Produto ID '{it.product_id}' não encontrado no catálogo da organização."
            )

        it_total = (it.quantity * it.unit_price)
        total_gross += it_total

        sale_item = models.POSSaleItem(
            product_id=it.product_id,
            quantity=it.quantity,
            unit_price=it.unit_price,
            total_price=it_total
        )
        sale.items.append(sale_item)

        # 2. Baixa física de estoque
        prev_stock = product.current_stock or Decimal("0.0000")
        product.current_stock = prev_stock - it.quantity

        # 3. Registro de Auditoria / Kardex (StockMovement)
        movement = StockMovement(
            organization_id=organization_id,
            product_id=product.id,
            movement_type="out_sale",
            quantity=it.quantity,
            unit_cost=product.cost_price or product.reference_price or Decimal("0.00"),
            balance_after=product.current_stock,
            reference_doc=f"PDV-{str(sale.id)[:8].upper()}",
            notes=f"Venda Balcão PDV - Cliente: {sale.customer_name} ({sale.payment_method})",
            created_by_id=current_user.id
        )
        db.add(movement)

    sale.total_amount = total_gross
    sale.net_amount = max(Decimal("0.00"), total_gross - payload.discount_amount)

    saved_sale = repository.create_pos_sale(db, sale)
    logger.info(f"🛍️ [PDV SALE] Venda #{str(saved_sale.id)[:8]} concluída com sucesso: R$ {saved_sale.net_amount} via {saved_sale.payment_method} (Estoque físico baixado)")
    return saved_sale


def list_pos_sales(db: Session, organization_id: uuid.UUID) -> list[models.POSSale]:
    return repository.list_pos_sales(db, organization_id)


# ==============================================================================
# 5. SANGRIA E SUPRIMENTO DE CAIXA PDV
# ==============================================================================

def record_pos_cash_movement(
    db: Session,
    organization_id: uuid.UUID,
    current_user: User,
    payload: schemas.POSCashMovementCreate
) -> models.POSCashMovement:
    session = repository.get_pos_session_by_id(db, payload.pos_session_id, organization_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Turno de caixa não encontrado.")
    if session.status != "OPEN":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Não é possível realizar movimentação em caixa fechado.")

    mov_type = payload.movement_type.upper().strip()
    if mov_type not in ["SANGRIA", "SUPRIMENTO"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tipo de movimentação inválido. Use 'SANGRIA' ou 'SUPRIMENTO'.")

    movement = models.POSCashMovement(
        organization_id=organization_id,
        pos_session_id=payload.pos_session_id,
        movement_type=mov_type,
        amount=payload.amount,
        reason=payload.reason.strip(),
        created_by_id=current_user.id
    )
    saved = repository.create_cash_movement(db, movement)
    logger.info(f"💵 [PDV CAIXA] {mov_type} de R$ {payload.amount} registrada no caixa {session.pos_terminal} por {current_user.email}: {payload.reason}")
    return saved


def list_pos_cash_movements(
    db: Session,
    organization_id: uuid.UUID,
    session_id: uuid.UUID | None = None
) -> list[models.POSCashMovement]:
    return repository.list_cash_movements(db, organization_id, session_id)


# ==============================================================================
# 6. CADASTRO CENTRALIZADO DE CLIENTES (Customer)
# ==============================================================================

def list_customers(
    db: Session,
    organization_id: uuid.UUID,
    search: str | None = None,
    is_active: bool | None = None
) -> list[models.Customer]:
    return repository.list_customers(db, organization_id, search, is_active)


def get_customer(db: Session, customer_id: uuid.UUID, organization_id: uuid.UUID) -> models.Customer:
    customer = repository.get_customer_by_id(db, customer_id, organization_id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado.")
    return customer


def create_customer(
    db: Session,
    organization_id: uuid.UUID,
    payload: schemas.CustomerCreate
) -> models.Customer:
    doc = payload.document.strip()
    existing = repository.get_customer_by_document(db, doc, organization_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Já existe um cliente cadastrado com o documento '{doc}'."
        )
    return repository.create_customer(db, organization_id, payload)


def update_customer(
    db: Session,
    customer_id: uuid.UUID,
    organization_id: uuid.UUID,
    payload: schemas.CustomerUpdate
) -> models.Customer:
    customer = get_customer(db, customer_id, organization_id)
    if payload.document and payload.document.strip() != customer.document:
        doc = payload.document.strip()
        existing = repository.get_customer_by_document(db, doc, organization_id)
        if existing and existing.id != customer_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Já existe outro cliente cadastrado com o documento '{doc}'."
            )
    return repository.update_customer(db, customer, payload)


def delete_customer(db: Session, customer_id: uuid.UUID, organization_id: uuid.UUID):
    customer = get_customer(db, customer_id, organization_id)
    repository.delete_customer(db, customer)
    return {"message": "Cliente excluído com sucesso."}




# ==============================================================================
# 8. GESTÃO COMERCIAL (Metas e Tabelas de Preços)
# ==============================================================================

def list_sales_goals(db: Session, organization_id: uuid.UUID, year: int | None = None) -> list[models.SalesGoal]:
    return repository.list_sales_goals(db, organization_id, year)


def create_sales_goal(
    db: Session,
    organization_id: uuid.UUID,
    current_user: User,
    payload: schemas.SalesGoalCreate
) -> models.SalesGoal:
    user = db.query(User).filter(User.id == payload.user_id, User.organization_id == organization_id).first()
    seller_name = user.full_name if user else payload.seller_name or "Vendedor"

    goal = models.SalesGoal(
        organization_id=organization_id,
        user_id=payload.user_id,
        seller_name=seller_name,
        month=payload.month,
        year=payload.year,
        target_amount=payload.target_amount,
        commission_percent=payload.commission_percent
    )
    return repository.create_sales_goal(db, goal)


def list_sales_goals(db: Session, organization_id: uuid.UUID, year: int | None = None) -> list[models.SalesGoal]:
    return repository.list_sales_goals(db, organization_id, year)


def delete_sales_goal(db: Session, goal_id: uuid.UUID, organization_id: uuid.UUID):
    goal = repository.get_sales_goal_by_id(db, goal_id, organization_id)
    if not goal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meta comercial não encontrada.")
    repository.delete_sales_goal(db, goal)
    return {"message": "Meta comercial excluída com sucesso."}


def list_price_tables(db: Session, organization_id: uuid.UUID) -> list[models.PriceTable]:
    return repository.list_price_tables(db, organization_id)


def create_price_table(
    db: Session,
    organization_id: uuid.UUID,
    payload: schemas.PriceTableCreate
) -> models.PriceTable:
    table = models.PriceTable(
        organization_id=organization_id,
        name=payload.name.strip(),
        description=payload.description,
        is_default=payload.is_default,
        is_active=payload.is_active
    )
    for it in payload.items:
        table.items.append(
            models.PriceTableItem(
                product_id=it.product_id,
                price=it.price,
                discount_percent=it.discount_percent
            )
        )
    return repository.create_price_table(db, table)


def delete_price_table(db: Session, table_id: uuid.UUID, organization_id: uuid.UUID):
    table = repository.get_price_table_by_id(db, table_id, organization_id)
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tabela de preços não encontrada.")
    repository.delete_price_table(db, table)
    return {"message": "Tabela de preços excluída com sucesso."}


# ==============================================================================
# 9. PÓS-VENDA (Devoluções e Trocas com Reestocagem)
# ==============================================================================

def process_sales_return(
    db: Session,
    organization_id: uuid.UUID,
    current_user: User,
    payload: schemas.SalesReturnCreate
) -> models.SalesReturn:
    if not payload.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A devolução deve conter pelo menos 1 item.")

    sales_return = models.SalesReturn(
        organization_id=organization_id,
        sales_order_id=payload.sales_order_id,
        pos_sale_id=payload.pos_sale_id,
        customer_id=payload.customer_id,
        customer_name=payload.customer_name.strip(),
        return_type=payload.return_type.upper(),
        status="COMPLETED",
        total_amount=Decimal("0.00"),
        reason=payload.reason.strip(),
        restock_items=payload.restock_items,
        created_by_id=current_user.id
    )

    tot = Decimal("0.00")
    for it in payload.items:
        item_total = it.quantity * it.unit_price
        tot += item_total

        r_item = models.SalesReturnItem(
            product_id=it.product_id,
            quantity=it.quantity,
            unit_price=it.unit_price,
            total_price=item_total,
            condition=it.condition
        )
        sales_return.items.append(r_item)

        # Se os itens estiverem em bom estado e restock ativado, estorna ao estoque
        if payload.restock_items and it.condition.upper() == "GOOD":
            product = db.query(Product).filter(Product.id == it.product_id, Product.organization_id == organization_id).first()
            if product:
                prev_stock = product.current_stock or Decimal("0.0000")
                product.current_stock = prev_stock + it.quantity
                movement = StockMovement(
                    organization_id=organization_id,
                    product_id=product.id,
                    movement_type="in_return",
                    quantity=it.quantity,
                    unit_cost=product.cost_price or product.reference_price or Decimal("0.00"),
                    balance_after=product.current_stock,
                    reference_doc=f"DEV-{str(sales_return.id)[:8].upper()}",
                    notes=f"Devolução/Troca Pós-Venda - Cliente: {payload.customer_name} ({payload.reason})",
                    created_by_id=current_user.id
                )
                db.add(movement)

    sales_return.total_amount = tot
    saved = repository.create_sales_return(db, sales_return)
    logger.info(f"🔄 [PÓS-VENDA] {saved.return_type} #{str(saved.id)[:8]} registrada para {saved.customer_name}: R$ {saved.total_amount}")
    return saved


def list_sales_returns(db: Session, organization_id: uuid.UUID) -> list[models.SalesReturn]:
    return repository.list_sales_returns(db, organization_id)


def delete_sales_return(db: Session, return_id: uuid.UUID, organization_id: uuid.UUID):
    ret = repository.get_sales_return_by_id(db, return_id, organization_id)
    if not ret:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Devolução não encontrada.")
    repository.delete_sales_return(db, ret)
    return {"message": "Registro de devolução excluído com sucesso."}




# ==============================================================================
# 10. INDICADORES E BI ANALÍTICO
# ==============================================================================

def get_sales_analytics(db: Session, organization_id: uuid.UUID) -> schemas.SalesAnalyticsResponse:
    orders = repository.list_orders(db, organization_id)
    pos_sales = repository.list_pos_sales(db, organization_id)
    quotes = repository.list_quotes(db, organization_id)
    goals = repository.list_sales_goals(db, organization_id, year=date.today().year)

    # 1. Faturamento total e contagens
    orders_revenue = sum([o.net_amount for o in orders if o.status not in ["CANCELLED", "DRAFT"]])
    pos_revenue = sum([s.net_amount for s in pos_sales if s.status != "CANCELLED"])
    total_revenue = orders_revenue + pos_revenue
    total_sales_count = len(orders) + len(pos_sales)
    avg_ticket = (total_revenue / Decimal(str(total_sales_count))) if total_sales_count > 0 else Decimal("0.00")

    # 2. Conversão de orçamentos
    converted_quotes = len([q for q in quotes if q.status in ["APPROVED", "CONVERTED"]])
    conv_rate = (Decimal(str(converted_quotes)) / Decimal(str(len(quotes))) * Decimal("100.00")) if quotes else Decimal("0.00")

    # 3. Produtos mais vendidos
    product_revenue_map: dict[uuid.UUID, dict] = {}

    for o in orders:
        if o.status != "CANCELLED":
            for it in o.items:
                if it.product_id not in product_revenue_map:
                    product_revenue_map[it.product_id] = {"name": f"Produto #{str(it.product_id)[:6]}", "qty": Decimal("0.00"), "rev": Decimal("0.00")}
                product_revenue_map[it.product_id]["qty"] += it.quantity
                product_revenue_map[it.product_id]["rev"] += it.total_price

    for s in pos_sales:
        if s.status != "CANCELLED":
            for it in s.items:
                if it.product_id not in product_revenue_map:
                    product_revenue_map[it.product_id] = {"name": f"Produto #{str(it.product_id)[:6]}", "qty": Decimal("0.00"), "rev": Decimal("0.00")}
                product_revenue_map[it.product_id]["qty"] += it.quantity
                product_revenue_map[it.product_id]["rev"] += it.total_price

    # Busca nomes reais dos produtos
    prod_ids = list(product_revenue_map.keys())
    if prod_ids:
        prods = db.query(Product).filter(Product.id.in_(prod_ids)).all()
        prod_dict = {p.id: p.name for p in prods}
        for pid in product_revenue_map:
            if pid in prod_dict:
                product_revenue_map[pid]["name"] = prod_dict[pid]

    sorted_prods = sorted(product_revenue_map.items(), key=lambda x: x[1]["rev"], reverse=True)[:5]
    top_products = [
        schemas.TopProductMetric(
            product_id=pid,
            product_name=data["name"],
            total_quantity_sold=data["qty"],
            total_revenue=data["rev"]
        )
        for pid, data in sorted_prods
    ]

    # 4. Performance de Vendedores
    seller_perf = [
        schemas.SellerPerformanceMetric(
            seller_name=g.seller_name or "Vendedor",
            total_sales_amount=total_revenue,  # Estimativa ou consolidado
            sales_count=total_sales_count,
            target_amount=g.target_amount,
            achievement_percent=(total_revenue / g.target_amount * Decimal("100.00")) if g.target_amount > 0 else Decimal("0.00")
        )
        for g in goals[:4]
    ]

    return schemas.SalesAnalyticsResponse(
        total_revenue=total_revenue,
        total_orders_count=len(orders),
        total_pos_sales_count=len(pos_sales),
        average_ticket=avg_ticket,
        quote_conversion_rate=conv_rate,
        top_selling_products=top_products,
        seller_performance=seller_perf
    )


