"""
modules/sales/service.py - Regras de Negócio e Serviços do Módulo de Vendas & PDV
"""

import uuid
from datetime import datetime, timezone, date, timedelta
from decimal import Decimal
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from controlb.logger import logger
from controlb.modules.documents import service as documents_service
from controlb.modules.identity.models import User
from controlb.modules.inventory import repository as inventory_repository
from controlb.modules.inventory.models import Product, StockMovement
from controlb.modules.sales import models, repository, schemas


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


QUOTE_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "DRAFT": frozenset({"SENT", "APPROVED", "CANCELLED", "EXPIRED"}),
    "SENT": frozenset({"APPROVED", "REJECTED", "CANCELLED", "EXPIRED"}),
    "APPROVED": frozenset({"CANCELLED"}),
    "REJECTED": frozenset(),
    "EXPIRED": frozenset(),
    "CANCELLED": frozenset(),
    "CONVERTED": frozenset(),
}


# ==============================================================================
# 0. SERVIÇOS DE CLIENTES (Customer) COM VÍNCULO UNIFICADO A CONTACT (Identity)
# ==============================================================================

def list_customers(
    db: Session,
    organization_id: uuid.UUID,
    search: str | None = None,
    is_active: bool | None = None,
) -> list[models.Customer]:
    """Retorna os clientes da organização, com filtro opcional por termo ou status."""
    return repository.list_customers(db, organization_id, search, is_active)


def get_customer(
    db: Session,
    customer_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> models.Customer:
    """Busca os detalhes de um cliente por ID dentro da organização."""
    customer = repository.get_customer_by_id(db, customer_id, organization_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente não encontrado.",
        )
    return customer


def create_customer(
    db: Session,
    organization_id: uuid.UUID,
    payload: schemas.CustomerCreate,
) -> models.Customer:
    """
    Cadastra um cliente no módulo de Vendas e sincroniza o perfil unificado Contact em Identity.
    """
    doc_clean = payload.document.strip() if payload.document else ""
    if not doc_clean:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O CPF/CNPJ do cliente é obrigatório.",
        )
    name_clean = payload.name.strip() if payload.name else ""
    if not name_clean:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A Razão Social ou Nome do cliente é obrigatório.",
        )

    # 1. Verifica duplicidade na tabela customer
    existing = repository.get_customer_by_document(db, doc_clean, organization_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Já existe um cliente cadastrado com o documento '{doc_clean}' ({existing.name}).",
        )

    # 2. Sincroniza / Garante Contact unificado em Identity
    from controlb.modules.identity import repository as identity_repo, schemas as identity_schemas
    contact = None
    if payload.contact_id:
        contact = identity_repo.get_contact_by_id(db, payload.contact_id, organization_id)
        if contact:
            contact.is_customer = True
            db.flush()

    if not contact:
        contact = identity_repo.get_contact_by_document(db, doc_clean, organization_id)
        if contact:
            contact.is_customer = True
            if not contact.name:
                contact.name = name_clean
            db.flush()
        else:
            contact_create = identity_schemas.ContactCreate(
                person_type=payload.person_type,
                document=doc_clean,
                name=name_clean,
                trade_name=payload.trade_name.strip() if payload.trade_name else None,
                state_registration=payload.state_registration.strip() if payload.state_registration else None,
                full_name=name_clean,
                email=payload.email.strip() if payload.email else None,
                phone=payload.phone.strip() if payload.phone else None,
                address_street=payload.address_street,
                address_number=payload.address_number,
                address_neighborhood=payload.address_neighborhood,
                address_city=payload.address_city,
                address_state=payload.address_state,
                address_zip_code=payload.address_zip_code,
                is_customer=True,
                is_supplier=False,
                is_carrier=False,
                origin_module="SALES",
                credit_limit=payload.credit_limit,
                is_active=payload.is_active,
                notes=payload.notes,
            )
            contact = identity_repo.create_contact(db, organization_id, contact_create)

    payload.document = doc_clean
    payload.name = name_clean
    cid = contact.id if contact else None

    created = repository.create_customer(db, organization_id, payload, contact_id=cid)
    if cid and not created.contact_id:
        created.contact_id = cid
        db.commit()
        db.refresh(created)
    return created


def update_customer(
    db: Session,
    customer_id: uuid.UUID,
    organization_id: uuid.UUID,
    payload: schemas.CustomerUpdate,
) -> models.Customer:
    """Atualiza dados cadastrais de um cliente e mantém sincronismo com o Contact em Identity."""
    customer = get_customer(db, customer_id, organization_id)

    if payload.document is not None:
        doc_clean = payload.document.strip()
        if not doc_clean:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O CPF/CNPJ do cliente não pode ser vazio.",
            )
        existing = repository.get_customer_by_document(db, doc_clean, organization_id)
        if existing and existing.id != customer.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Já existe outro cliente cadastrado com o documento '{doc_clean}' ({existing.name}).",
            )
        payload.document = doc_clean

    if payload.name is not None:
        name_clean = payload.name.strip()
        if not name_clean:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A Razão Social ou Nome do cliente não pode ser vazio.",
            )
        payload.name = name_clean

    # Sincroniza com contact em Identity se existir
    if customer.contact_id:
        from controlb.modules.identity import repository as identity_repo, schemas as identity_schemas
        contact = identity_repo.get_contact_by_id(db, customer.contact_id, organization_id)
        if contact:
            contact_update = identity_schemas.ContactUpdate(
                person_type=payload.person_type,
                document=payload.document,
                name=payload.name,
                trade_name=payload.trade_name,
                state_registration=payload.state_registration,
                email=payload.email,
                phone=payload.phone,
                address_street=payload.address_street,
                address_number=payload.address_number,
                address_neighborhood=payload.address_neighborhood,
                address_city=payload.address_city,
                address_state=payload.address_state,
                address_zip_code=payload.address_zip_code,
                credit_limit=payload.credit_limit,
                is_active=payload.is_active,
                notes=payload.notes,
            )
            identity_repo.update_contact(db, contact, contact_update)

    return repository.update_customer(db, customer, payload)


def delete_customer(
    db: Session,
    customer_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> dict:
    """Exclui um cliente garantindo que não haja cotações ou pedidos vinculados."""
    customer = get_customer(db, customer_id, organization_id)
    if customer.quotes or customer.orders:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível excluir este cliente pois existem cotações ou pedidos vinculados a ele.",
        )
    repository.delete_customer(db, customer)
    return {"detail": "Cliente excluído com sucesso."}


def _validate_current_user_tenant(current_user: User, organization_id: uuid.UUID) -> None:
    if current_user.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="O usuário não pertence à organização informada.",
        )


def _validate_commercial_references(
    db: Session,
    organization_id: uuid.UUID,
    *,
    customer_id: uuid.UUID | None,
    opportunity_id: uuid.UUID | None,
    product_ids: list[uuid.UUID],
):
    customer = None
    if customer_id:
        customer = repository.get_customer_by_id(db, customer_id, organization_id)
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O cliente vinculado não pertence à organização.",
            )

    opportunity = None
    if opportunity_id:
        from controlb.modules.crm import repository as crm_repository

        opportunity = crm_repository.get_opportunity_by_id(
            db,
            opportunity_id,
            organization_id,
        )
        if not opportunity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A oportunidade vinculada não pertence à organização.",
            )
        if customer_id and opportunity.customer_id and opportunity.customer_id != customer_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A cotação e a oportunidade estão vinculadas a clientes diferentes.",
            )

    for product_id in set(product_ids):
        if not inventory_repository.get_product_by_id(db, product_id, organization_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Um dos produtos vinculados não pertence à organização.",
            )

    return customer, opportunity


def _ensure_quote_document(
    db: Session,
    quote: models.SalesQuote,
    organization_id: uuid.UUID,
):
    document = documents_service.ensure_document(
        db,
        organization_id=organization_id,
        category="sales.quotation",
        document_type="SALES_QUOTE",
        native_id=quote.id,
        document_number=quote.quote_number,
        title=f"Cotação {quote.quote_number} - {quote.customer_name}",
        current_status=quote.status,
        origin_module="SALES",
        created_by_id=quote.created_by_id,
        issued_at=quote.created_at,
    )
    quote.document_id = document.id
    return document


def _ensure_order_document(
    db: Session,
    order: models.SalesOrder,
    organization_id: uuid.UUID,
):
    document = documents_service.ensure_document(
        db,
        organization_id=organization_id,
        category="sales.order",
        document_type="SALES_ORDER",
        native_id=order.id,
        document_number=order.order_number,
        title=f"Pedido de Venda {order.order_number} - {order.customer_name}",
        current_status=order.status,
        origin_module="SALES",
        created_by_id=order.created_by_id,
        issued_at=order.created_at,
    )
    order.document_id = document.id
    return document


def _record_created_event(
    db: Session,
    *,
    organization_id: uuid.UUID,
    document,
    document_kind: str,
    native_id: uuid.UUID,
    status_value: str,
    created_by_id: uuid.UUID | None,
    event_metadata: dict | None = None,
) -> None:
    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=document,
        event_type="CREATED",
        new_status=status_value,
        created_by_id=created_by_id,
        event_metadata=event_metadata,
        idempotency_key=f"{document_kind}:{native_id}:created",
    )


def _record_quote_conversion_chain(
    db: Session,
    *,
    organization_id: uuid.UUID,
    quote: models.SalesQuote,
    order: models.SalesOrder,
    current_user: User,
) -> None:
    quote_document = _ensure_quote_document(db, quote, organization_id)
    order_document = _ensure_order_document(db, order, organization_id)
    documents_service.relate_documents(
        db,
        organization_id=organization_id,
        parent_document=quote_document,
        child_document=order_document,
        relation_type="CONVERTED_TO",
        created_by_id=current_user.id,
        relation_metadata={
            "quote_id": str(quote.id),
            "order_id": str(order.id),
        },
    )
    _record_created_event(
        db,
        organization_id=organization_id,
        document=order_document,
        document_kind="sales-order",
        native_id=order.id,
        status_value=order.status,
        created_by_id=current_user.id,
        event_metadata={
            "origin": "SALES_QUOTE",
            "quote_id": str(quote.id),
        },
    )
    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=quote_document,
        event_type="CONVERTED_TO_ORDER",
        previous_status="APPROVED",
        new_status="CONVERTED",
        created_by_id=current_user.id,
        event_metadata={"order_id": str(order.id)},
        idempotency_key=f"sales-quote:{quote.id}:converted-to:{order.id}",
    )


# ==============================================================================
# ORÇAMENTOS (QUOTES)
# ==============================================================================

def create_sales_quote(
    db: Session,
    organization_id: uuid.UUID,
    current_user: User,
    payload: schemas.SalesQuoteCreate
) -> models.SalesQuote:
    _validate_current_user_tenant(current_user, organization_id)
    if not payload.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A cotação deve conter pelo menos um item.",
        )

    customer, opportunity = _validate_commercial_references(
        db,
        organization_id,
        customer_id=payload.customer_id,
        opportunity_id=payload.opportunity_id,
        product_ids=[item.product_id for item in payload.items],
    )

    quote_num = f"ORC-{date.today().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
    quote_id = uuid.uuid4()
    quote = models.SalesQuote(
        id=quote_id,
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
        status="DRAFT",
        notes=payload.notes,
        created_by_id=current_user.id
    )

    quote_document = _ensure_quote_document(db, quote, organization_id)

    total_gross = Decimal("0.00")
    total_disc = Decimal("0.00")

    for it in payload.items:
        gross_item_total = it.quantity * it.unit_price
        if it.discount_amount > gross_item_total:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O desconto de um item não pode superar seu valor bruto.",
            )
        it_total = gross_item_total - it.discount_amount
        total_gross += gross_item_total
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

    saved_quote = repository.create_quote(db, quote)
    quote_document.issued_at = saved_quote.created_at
    _record_created_event(
        db,
        organization_id=organization_id,
        document=quote_document,
        document_kind="sales-quote",
        native_id=saved_quote.id,
        status_value=saved_quote.status,
        created_by_id=current_user.id,
    )

    if opportunity:
        opp_doc = documents_service.ensure_document(
            db,
            organization_id=organization_id,
            document_type="OPPORTUNITY",
            native_id=opportunity.id,
            document_number=opportunity.title,
            current_status=opportunity.stage,
            created_by_id=opportunity.assigned_to_id or current_user.id,
            issued_at=opportunity.created_at,
        )
        documents_service.relate_documents(
            db,
            organization_id=organization_id,
            parent_document=opp_doc,
            child_document=quote_document,
            relation_type="GENERATED_QUOTE",
        )
        documents_service.record_event(
            db,
            organization_id=organization_id,
            document=opp_doc,
            event_type="QUOTE_CREATED",
            previous_status=opportunity.stage,
            new_status="PROPOSAL" if opportunity.stage in ("QUALIFICATION", "PROSPECTING", "DISCOVERY") else opportunity.stage,
            created_by_id=current_user.id,
            event_metadata={"quote_id": str(saved_quote.id), "quote_number": saved_quote.quote_number},
            idempotency_key=f"opportunity:{opportunity.id}:quote:{saved_quote.id}",
        )
        if opportunity.stage in ("QUALIFICATION", "PROSPECTING", "DISCOVERY"):
            opportunity.stage = "PROPOSAL"
            db.add(opportunity)

    db.flush()
    return saved_quote


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

    if quote.status != "DRAFT":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Somente cotações em rascunho podem ser alteradas.",
        )
    if payload.status is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use a operação específica de mudança de status da cotação.",
        )
    if payload.items is not None and not payload.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A cotação deve conter pelo menos um item.",
        )

    _validate_commercial_references(
        db,
        organization_id,
        customer_id=payload.customer_id if payload.customer_id is not None else quote.customer_id,
        opportunity_id=(
            payload.opportunity_id
            if payload.opportunity_id is not None
            else quote.opportunity_id
        ),
        product_ids=(
            [item.product_id for item in payload.items]
            if payload.items is not None
            else [item.product_id for item in quote.items]
        ),
    )

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
    if payload.notes is not None:
        quote.notes = payload.notes

    if payload.items is not None:
        quote.items.clear()
        total_gross = Decimal("0.00")
        total_disc = Decimal("0.00")

        for it in payload.items:
            gross_item_total = it.quantity * it.unit_price
            if it.discount_amount > gross_item_total:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="O desconto de um item não pode superar seu valor bruto.",
                )
            it_total = gross_item_total - it.discount_amount
            total_gross += gross_item_total
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
    new_status: str,
    current_user: User,
) -> models.SalesQuote:
    _validate_current_user_tenant(current_user, organization_id)
    quote = repository.get_quote_by_id_for_update(db, quote_id, organization_id)
    if not quote:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orçamento não encontrado.")

    normalized_status = new_status.strip().upper()
    if normalized_status == "CONVERTED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O status CONVERTED só pode ser produzido pela conversão em pedido.",
        )
    if normalized_status not in QUOTE_STATUS_TRANSITIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status de cotação inválido.",
        )
    if normalized_status == quote.status:
        _ensure_quote_document(db, quote, organization_id)
        db.flush()
        return quote
    if normalized_status not in QUOTE_STATUS_TRANSITIONS.get(quote.status, frozenset()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Não é permitido alterar a cotação de {quote.status} para {normalized_status}.",
        )

    previous_status = quote.status
    quote_document = _ensure_quote_document(db, quote, organization_id)
    quote.status = normalized_status
    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=quote_document,
        event_type="STATUS_CHANGED",
        previous_status=previous_status,
        new_status=normalized_status,
        created_by_id=current_user.id,
        event_metadata={"quote_id": str(quote.id)},
        idempotency_key=(
            f"sales-quote:{quote.id}:status:{previous_status.lower()}:{normalized_status.lower()}"
        ),
    )
    db.flush()
    return quote


def cancel_sales_quote(
    db: Session,
    quote_id: uuid.UUID,
    organization_id: uuid.UUID,
    reason: str,
    current_user: User,
) -> models.SalesQuote:
    _validate_current_user_tenant(current_user, organization_id)
    quote = repository.get_quote_by_id_for_update(db, quote_id, organization_id)
    if not quote:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orçamento não encontrado.")

    if quote.status in ("CANCELLED", "REJECTED", "EXPIRED"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A cotação já se encontra no status {quote.status}.",
        )
    if quote.status == "CONVERTED":
        existing_orders = repository.list_orders_by_quote_id(db, quote.id, organization_id)
        if existing_orders and any(o.status != "CANCELLED" for o in existing_orders):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A cotação já foi convertida em um Pedido de Venda ativo. Cancele primeiro o pedido de venda correspondente.",
            )

    previous_status = quote.status
    quote_document = _ensure_quote_document(db, quote, organization_id)
    quote.status = "CANCELLED"
    quote.cancellation_reason = reason.strip()

    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=quote_document,
        event_type="CANCELLED",
        previous_status=previous_status,
        new_status="CANCELLED",
        created_by_id=current_user.id,
        event_metadata={"quote_id": str(quote.id), "reason": quote.cancellation_reason},
        idempotency_key=f"sales-quote:{quote.id}:cancel:{datetime.now(timezone.utc).timestamp()}",
    )

    if quote.opportunity_id:
        from controlb.modules.crm import repository as crm_repo
        opp = crm_repo.get_opportunity_by_id(db, quote.opportunity_id, organization_id)
        if opp and opp.stage not in ("WON", "LOST"):
            other_active_quotes = [
                q for q in repository.list_quotes(db, organization_id)
                if q.opportunity_id == opp.id and q.id != quote.id and q.status in ("DRAFT", "SENT", "APPROVED")
            ]
            if not other_active_quotes:
                opp.stage = "NEGOTIATION"
                db.add(opp)

    db.flush()
    return quote


def convert_quote_to_order(
    db: Session,
    quote_id: uuid.UUID,
    organization_id: uuid.UUID,
    current_user: User
) -> models.SalesOrder:
    _validate_current_user_tenant(current_user, organization_id)
    quote = repository.get_quote_by_id_for_update(db, quote_id, organization_id)
    if not quote:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orçamento não encontrado.")

    existing_orders = repository.list_orders_by_quote_id(db, quote.id, organization_id)
    if len(existing_orders) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A cotação possui mais de um pedido vinculado e requer saneamento de dados.",
        )
    if existing_orders:
        existing_order = existing_orders[0]
        if quote.status != "CONVERTED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Já existe um pedido para a cotação, mas seu status está inconsistente.",
            )
        _validate_commercial_references(
            db,
            organization_id,
            customer_id=quote.customer_id,
            opportunity_id=quote.opportunity_id,
            product_ids=[item.product_id for item in quote.items],
        )
        _record_quote_conversion_chain(
            db,
            organization_id=organization_id,
            quote=quote,
            order=existing_order,
            current_user=current_user,
        )
        db.flush()
        return existing_order

    if quote.status != "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Somente uma cotação aprovada pode ser convertida em pedido de venda.",
        )
    if not quote.items:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Não é possível converter uma cotação sem itens.",
        )

    _, opportunity = _validate_commercial_references(
        db,
        organization_id,
        customer_id=quote.customer_id,
        opportunity_id=quote.opportunity_id,
        product_ids=[item.product_id for item in quote.items],
    )

    order_num = f"PED-{date.today().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
    order = models.SalesOrder(
        id=uuid.uuid4(),
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

    _record_quote_conversion_chain(
        db,
        organization_id=organization_id,
        quote=quote,
        order=order,
        current_user=current_user,
    )
    quote.status = "CONVERTED"
    db.add(order)
    if opportunity:
        opportunity.stage = "WON"
        db.add(opportunity)

    db.flush()
    return order


def list_sales_quotes(db: Session, organization_id: uuid.UUID, opportunity_id: uuid.UUID | None = None) -> list[models.SalesQuote]:
    quotes = repository.list_quotes(db, organization_id)
    if opportunity_id:
        quotes = [q for q in quotes if q.opportunity_id == opportunity_id]
    return quotes


def delete_sales_quote(
    db: Session,
    quote_id: uuid.UUID,
    organization_id: uuid.UUID,
    current_user: User,
):
    _validate_current_user_tenant(current_user, organization_id)
    quote = repository.get_quote_by_id_for_update(db, quote_id, organization_id)
    if not quote:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orçamento não encontrado.")
    if quote.status == "CONVERTED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Uma cotação convertida não pode ser cancelada.",
        )
    if quote.status == "CANCELLED":
        return {"message": "Cotação já estava cancelada."}

    previous_status = quote.status
    quote_document = _ensure_quote_document(db, quote, organization_id)
    quote.status = "CANCELLED"
    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=quote_document,
        event_type="CANCELLED",
        previous_status=previous_status,
        new_status="CANCELLED",
        created_by_id=current_user.id,
        event_metadata={"quote_id": str(quote.id)},
        idempotency_key=f"sales-quote:{quote.id}:cancelled",
    )
    db.flush()
    return {"message": "Cotação cancelada com sucesso."}


# ==============================================================================
# PEDIDOS DE VENDA (SALES ORDERS)
# ==============================================================================

def create_sales_order(
    db: Session,
    organization_id: uuid.UUID,
    current_user: User,
    payload: schemas.SalesOrderCreate
) -> models.SalesOrder:
    _validate_current_user_tenant(current_user, organization_id)
    if payload.sales_quote_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pedidos originados de cotação devem usar a operação de conversão.",
        )
    if not payload.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O pedido de venda deve conter pelo menos um item.",
        )
    if payload.delivery_status.upper() != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Um pedido novo deve iniciar com entrega PENDING.",
        )

    _, opportunity = _validate_commercial_references(
        db,
        organization_id,
        customer_id=payload.customer_id,
        opportunity_id=payload.opportunity_id,
        product_ids=[item.product_id for item in payload.items],
    )

    order_num = f"PED-{date.today().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"

    order = models.SalesOrder(
        id=uuid.uuid4(),
        organization_id=organization_id,
        order_number=order_num,
        customer_id=payload.customer_id,
        sales_quote_id=None,
        opportunity_id=payload.opportunity_id,
        customer_name=payload.customer_name.strip(),
        customer_document=payload.customer_document.strip() if payload.customer_document else None,
        payment_terms=payload.payment_terms or "À Vista",
        delivery_status="PENDING",
        billing_status="PENDING",
        status="CONFIRMED",
        notes=payload.notes,
        created_by_id=current_user.id
    )

    order_document = _ensure_order_document(db, order, organization_id)

    total_gross = Decimal("0.00")
    total_disc = Decimal("0.00")

    for it in payload.items:
        gross_item_total = it.quantity * it.unit_price
        if it.discount_amount > gross_item_total:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O desconto de um item não pode superar seu valor bruto.",
            )
        it_total = gross_item_total - it.discount_amount
        total_gross += gross_item_total
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

    saved_order = repository.create_order(db, order)
    order_document.issued_at = saved_order.created_at
    _record_created_event(
        db,
        organization_id=organization_id,
        document=order_document,
        document_kind="sales-order",
        native_id=saved_order.id,
        status_value=saved_order.status,
        created_by_id=current_user.id,
        event_metadata={"origin": "DIRECT"},
    )
    if opportunity:
        opportunity.stage = "WON"
        db.add(opportunity)
    db.flush()
    return saved_order


def get_sales_order(db: Session, order_id: uuid.UUID, organization_id: uuid.UUID) -> models.SalesOrder:
    order = repository.get_order_by_id(db, order_id, organization_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido de venda não encontrado.")
    return order


def list_sales_orders(db: Session, organization_id: uuid.UUID) -> list[models.SalesOrder]:
    return repository.list_orders(db, organization_id)


def delete_sales_order(
    db: Session,
    order_id: uuid.UUID,
    organization_id: uuid.UUID,
    current_user: User,
    reason: str | None = None,
):
    _validate_current_user_tenant(current_user, organization_id)
    order = repository.get_order_by_id_for_update(db, order_id, organization_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido de venda não encontrado.")
    from controlb.modules.inventory import service as inventory_service

    if order.billing_status == "INVOICED" or order.status == "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Um pedido faturado ou concluído não pode ser cancelado.",
        )
    if order.status == "CANCELLED":
        inventory_service.release_sales_order_reservation(
            db,
            organization_id,
            current_user.id,
            order.id,
            locked_order=order,
            delivery_status_after="CANCELLED",
        )
        return {"message": "Pedido de venda já estava cancelado."}

    previous_status = order.status
    order_document = _ensure_order_document(db, order, organization_id)
    inventory_service.release_sales_order_reservation(
        db,
        organization_id,
        current_user.id,
        order.id,
        locked_order=order,
        delivery_status_after="CANCELLED",
    )
    order.status = "CANCELLED"
    order.delivery_status = "CANCELLED"
    if reason:
        order.cancellation_reason = reason.strip()

    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=order_document,
        event_type="CANCELLED",
        previous_status=previous_status,
        new_status="CANCELLED",
        created_by_id=current_user.id,
        event_metadata={"order_id": str(order.id), "reason": order.cancellation_reason},
        idempotency_key=f"sales-order:{order.id}:cancelled",
    )
    db.flush()
    return {"message": "Pedido de venda cancelado com sucesso."}


def update_sales_order_status(
    db: Session,
    order_id: uuid.UUID,
    organization_id: uuid.UUID,
    payload: schemas.SalesOrderUpdate,
    current_user: User,
) -> models.SalesOrder:
    _validate_current_user_tenant(current_user, organization_id)
    order = repository.get_order_by_id_for_update(db, order_id, organization_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido de venda não encontrado.")

    previous_status = order.status
    previous_delivery_status = order.delivery_status
    updated_fields: list[str] = []

    if payload.customer_id is not None:
        customer = repository.get_customer_by_id(db, payload.customer_id, organization_id)
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cliente não encontrado na organização atual.",
            )
        if order.customer_id != customer.id:
            order.customer_id = customer.id
            updated_fields.append("customer_id")

    if payload.customer_name is not None:
        customer_name = payload.customer_name.strip()
        if not customer_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O nome do cliente não pode ser vazio.",
            )
        if order.customer_name != customer_name:
            order.customer_name = customer_name
            updated_fields.append("customer_name")

    if payload.customer_document is not None:
        customer_document = payload.customer_document.strip() or None
        if order.customer_document != customer_document:
            order.customer_document = customer_document
            updated_fields.append("customer_document")

    if payload.payment_terms is not None:
        payment_terms = payload.payment_terms.strip() or None
        if order.payment_terms != payment_terms:
            order.payment_terms = payment_terms
            updated_fields.append("payment_terms")

    if payload.status is not None:
        norm_status = payload.status.strip().upper()
        if norm_status == "CANCELLED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Use a operação formal de cancelamento do pedido.",
            )
        if norm_status not in {"DRAFT", "CONFIRMED", "COMPLETED"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Status comercial do pedido inválido.",
            )
        if order.status != norm_status:
            order.status = norm_status
            updated_fields.append("status")

    if payload.delivery_status is not None:
        norm_deliv = payload.delivery_status.strip().upper()
        if norm_deliv == "CANCELLED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Use a operação formal de cancelamento do pedido.",
            )
        if norm_deliv not in {"PENDING", "RESERVED", "DISPATCHED", "DELIVERED"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Status de entrega do pedido inválido.",
            )
        if order.delivery_status != norm_deliv:
            order.delivery_status = norm_deliv
            updated_fields.append("delivery_status")

    if payload.notes is not None and order.notes != payload.notes:
        order.notes = payload.notes
        updated_fields.append("notes")

    if not updated_fields:
        db.flush()
        return order

    order_document = _ensure_order_document(db, order, organization_id)
    status_changed = (
        previous_status != order.status
        or previous_delivery_status != order.delivery_status
    )

    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=order_document,
        event_type="STATUS_CHANGED" if status_changed else "UPDATED",
        previous_status=previous_status,
        new_status=order.status if status_changed else None,
        created_by_id=current_user.id,
        event_metadata={
            "updated_fields": updated_fields,
            "delivery_status": order.delivery_status,
            "billing_status": order.billing_status,
        },
        idempotency_key=(
            f"sales-order:{order.id}:update:{order.status}:"
            f"{order.delivery_status}:{uuid.uuid4().hex[:6]}"
        ),
    )
    db.flush()
    return order


def request_order_billing(
    db: Session,
    order_id: uuid.UUID,
    organization_id: uuid.UUID,
    current_user: User,
) -> models.SalesOrder:
    _validate_current_user_tenant(current_user, organization_id)
    order = repository.get_order_by_id_for_update(db, order_id, organization_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido de venda não encontrado.")

    if order.billing_status == "INVOICED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este pedido de venda já foi faturado.",
        )
    if order.status == "CANCELLED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Não é possível faturar um pedido cancelado.",
        )

    from controlb.modules.billing import service as billing_service, schemas as billing_schemas
    
    invoice = billing_service.create_invoice(
        db,
        organization_id,
        current_user,
        billing_schemas.InvoiceCreate(
            sales_order_id=order.id,
            customer_name=order.customer_name,
            customer_document=order.customer_document,
            total_amount=order.net_amount,
            tax_amount=Decimal("0.00"),
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            installments_count=1,
            notes=f"Faturamento gerado a partir do Pedido #{order.order_number}",
            generate_receivables_in_finance=True,
        )
    )

    order.billing_status = "INVOICED"
    order_document = _ensure_order_document(db, order, organization_id)
    
    inv_doc = documents_service.ensure_document(
        db,
        organization_id=organization_id,
        document_type="INVOICE",
        native_id=invoice.id,
        document_number=invoice.invoice_number,
        current_status=invoice.status,
        created_by_id=current_user.id,
        issued_at=invoice.created_at,
    )
    documents_service.relate_documents(
        db,
        organization_id=organization_id,
        parent_document=order_document,
        child_document=inv_doc,
        relation_type="INVOICED_BY",
    )
    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=order_document,
        event_type="INVOICED",
        previous_status=order.status,
        new_status=order.status,
        created_by_id=current_user.id,
        event_metadata={"invoice_id": str(invoice.id), "invoice_number": invoice.invoice_number},
        idempotency_key=f"sales-order:{order.id}:invoiced:{invoice.id}",
    )
    db.flush()
    return order



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
        id=uuid.uuid4(),
        organization_id=organization_id,
        pos_session_id=pos_session_id,
        customer_name=payload.customer_name.strip() if payload.customer_name else "Consumidor Final",
        customer_document=payload.customer_document.strip() if payload.customer_document else None,
        discount_amount=payload.discount_amount,
        payment_method=payload.payment_method,
        created_by_id=current_user.id
    )

    from controlb.modules.inventory import service as inventory_service

    requested: dict[uuid.UUID, Decimal] = {}
    for item in payload.items:
        requested[item.product_id] = requested.get(
            item.product_id, Decimal("0.0000")
        ) + Decimal(str(item.quantity))

    products, available, _ = inventory_service.lock_products_and_get_availability(
        db, organization_id, list(requested)
    )
    products_by_id = {product.id: product for product in products}
    shortages = [
        (products_by_id[product_id], quantity, available[product_id])
        for product_id, quantity in sorted(requested.items(), key=lambda item: str(item[0]))
        if quantity > available[product_id]
    ]
    if shortages:
        details = "; ".join(
            f"{product.sku}: solicitado {quantity}, disponível {available_quantity}"
            for product, quantity, available_quantity in shortages
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Saldo disponível insuficiente para a venda no PDV. {details}.",
        )

    total_gross = Decimal("0.00")

    for it in payload.items:
        product = products_by_id[it.product_id]

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
        prev_stock = Decimal(str(product.current_stock or 0))
        product.current_stock = prev_stock - Decimal(str(it.quantity))
        if product.current_stock < 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A venda produziria saldo físico negativo para o SKU {product.sku}.",
            )

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


# ==============================================================================
# 9. VENDEDORES E FORÇA DE VENDAS
# ==============================================================================

def list_sellers(db: Session, organization_id: uuid.UUID) -> list[schemas.SellerResponse]:
    """
    Retorna todos os colaboradores que atuam como Vendedores na organização.
    Inclui a equipe comercial (SALES) vinculada.
    """
    from controlb.modules.identity.models import User, Team

    # Busca usuários que são vendedores ou pertencem a equipe comercial
    users = db.query(User).filter(
        User.organization_id == organization_id,
        User.is_active == True,
        (User.is_seller == True) | (User.teams.any(Team.module_category == "SALES"))
    ).all()

    # Fallback caso a base ainda não tenha marcado nenhum vendedor
    if not users:
        users = db.query(User).filter(
            User.organization_id == organization_id,
            User.is_active == True
        ).all()

    sellers: list[schemas.SellerResponse] = []
    for u in users:
        sales_team = next((t for t in u.teams if t.module_category == "SALES"), None)
        sellers.append(schemas.SellerResponse(
            id=u.id,
            full_name=u.full_name,
            email=u.email,
            is_seller=u.is_seller,
            sales_team_id=sales_team.id if sales_team else None,
            sales_team_name=sales_team.name if sales_team else None
        ))
    return sellers
