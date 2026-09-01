"""Regras de negócio do módulo de faturamento comercial."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from controlb.logger import logger
from controlb.modules.billing import models, repository, schemas
from controlb.modules.finance import models as finance_models
from controlb.modules.finance import repository as finance_repository
from controlb.modules.finance import schemas as finance_schemas
from controlb.modules.finance import service as finance_service
from controlb.modules.identity.models import Organization, User
from controlb.modules.inventory import models as inventory_models
from controlb.modules.sales import models as sales_models

MONEY = Decimal("0.01")
QUANTITY = Decimal("0.0001")


def _validate_current_user_tenant(
    current_user: User, organization_id: uuid.UUID
) -> None:
    if current_user.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário não pertence à organização do faturamento.",
        )


def _invoiced_quantities_by_order_item(
    db: Session,
    organization_id: uuid.UUID,
    sales_order_id: uuid.UUID,
) -> dict[uuid.UUID, Decimal]:
    rows = db.execute(
        select(
            models.InvoiceItem.sales_order_item_id,
            func.sum(models.InvoiceItem.quantity),
        )
        .join(models.Invoice, models.Invoice.id == models.InvoiceItem.invoice_id)
        .where(
            models.Invoice.organization_id == organization_id,
            models.Invoice.sales_order_id == sales_order_id,
            models.Invoice.status != "CANCELLED",
        )
        .group_by(models.InvoiceItem.sales_order_item_id)
    ).all()
    return {item_id: Decimal(str(quantity or 0)) for item_id, quantity in rows}


def _invoiced_discounts_by_order_item(
    db: Session,
    organization_id: uuid.UUID,
    sales_order_id: uuid.UUID,
) -> dict[uuid.UUID, Decimal]:
    rows = db.execute(
        select(
            models.InvoiceItem.sales_order_item_id,
            func.sum(models.InvoiceItem.discount_amount),
        )
        .join(models.Invoice, models.Invoice.id == models.InvoiceItem.invoice_id)
        .where(
            models.Invoice.organization_id == organization_id,
            models.Invoice.sales_order_id == sales_order_id,
            models.Invoice.status != "CANCELLED",
        )
        .group_by(models.InvoiceItem.sales_order_item_id)
    ).all()
    return {item_id: Decimal(str(discount or 0)) for item_id, discount in rows}


def _prepare_invoice_lines(
    db: Session,
    organization_id: uuid.UUID,
    order: sales_models.SalesOrder,
    requested_items: list[schemas.InvoiceItemCreate],
) -> tuple[list[dict], Decimal]:
    """Valida saldos e calcula snapshots monetários sem confiar no frontend."""
    if not requested_items:
        return [], Decimal("0.00")
    requested_ids = [item.sales_order_item_id for item in requested_items]
    if len(requested_ids) != len(set(requested_ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Um item do pedido foi informado mais de uma vez no faturamento.",
        )

    order_items = {item.id: item for item in order.items}
    unknown_ids = set(requested_ids) - set(order_items)
    if unknown_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Existem itens que não pertencem ao pedido de venda informado.",
        )

    invoiced = _invoiced_quantities_by_order_item(
        db, organization_id, order.id
    )
    invoiced_discounts = _invoiced_discounts_by_order_item(
        db, organization_id, order.id
    )
    products = {
        product.id: product
        for product in db.scalars(
            select(inventory_models.Product).where(
                inventory_models.Product.organization_id == organization_id,
                inventory_models.Product.id.in_(
                    [order_items[item_id].product_id for item_id in requested_ids]
                ),
            )
        ).all()
    }
    lines: list[dict] = []
    total = Decimal("0.00")
    for requested in requested_items:
        order_item = order_items[requested.sales_order_item_id]
        quantity = Decimal(str(requested.quantity)).quantize(QUANTITY)
        remaining = (
            Decimal(str(order_item.quantity))
            - invoiced.get(order_item.id, Decimal("0"))
        ).quantize(QUANTITY)
        if remaining <= 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Um dos itens selecionados já foi integralmente faturado.",
            )
        if quantity > remaining:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "A quantidade solicitada excede o saldo faturável do item "
                    f"({remaining})."
                ),
            )
        remaining_discount = max(
            Decimal("0.00"),
            Decimal(str(order_item.discount_amount))
            - invoiced_discounts.get(order_item.id, Decimal("0.00")),
        )
        proportional_discount = (
            remaining_discount
            if quantity == remaining
            else (
                Decimal(str(order_item.discount_amount))
                * quantity
                / Decimal(str(order_item.quantity))
            ).quantize(MONEY)
        )
        line_total = (
            Decimal(str(order_item.unit_price)) * quantity - proportional_discount
        ).quantize(MONEY)
        product = products.get(order_item.product_id)
        lines.append(
            {
                "sales_order_item_id": order_item.id,
                "product_id": order_item.product_id,
                "description": product.name if product else f"Produto {order_item.product_id}",
                "product_sku": product.sku if product else None,
                "quantity": quantity,
                "unit_price": order_item.unit_price,
                "discount_amount": proportional_discount,
                "total_amount": line_total,
            }
        )
        total += line_total
    return lines, total.quantize(MONEY)


def _remaining_invoice_items(
    db: Session,
    organization_id: uuid.UUID,
    order: sales_models.SalesOrder,
) -> list[schemas.InvoiceItemCreate]:
    invoiced = _invoiced_quantities_by_order_item(db, organization_id, order.id)
    return [
        schemas.InvoiceItemCreate(
            sales_order_item_id=item.id,
            quantity=(
                Decimal(str(item.quantity))
                - invoiced.get(item.id, Decimal("0"))
            ).quantize(QUANTITY),
        )
        for item in order.items
        if Decimal(str(item.quantity)) - invoiced.get(item.id, Decimal("0")) > 0
    ]


def _calculate_order_billing_status(
    db: Session,
    organization_id: uuid.UUID,
    order: sales_models.SalesOrder,
) -> str:
    invoiced = _invoiced_quantities_by_order_item(db, organization_id, order.id)
    if invoiced:
        fully_invoiced = all(
            invoiced.get(item.id, Decimal("0")) >= Decimal(str(item.quantity))
            for item in order.items
        )
        return "INVOICED" if fully_invoiced else "PARTIALLY_INVOICED"

    # Compatibilidade com faturas legadas criadas antes do snapshot por item.
    legacy_invoice_exists = db.scalar(
        select(models.Invoice.id).where(
            models.Invoice.organization_id == organization_id,
            models.Invoice.sales_order_id == order.id,
            models.Invoice.status != "CANCELLED",
        )
    )
    return "INVOICED" if legacy_invoice_exists else "PENDING"


def get_invoice_header(
    db: Session,
    invoice: models.Invoice,
    organization_id: uuid.UUID,
):
    from controlb.modules.documents import service as documents_service

    document = documents_service.get_document(db, invoice.document_id, organization_id)
    if document.document_type != "INVOICE" or document.native_id != invoice.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O cabeçalho documental da fatura é inconsistente.",
        )
    invoice.invoice_number = document.document_number
    invoice.status = document.current_status
    return document


def create_invoice(
    db: Session,
    organization_id: uuid.UUID,
    current_user: User,
    payload: schemas.InvoiceCreate,
    *,
    source_document=None,
) -> models.Invoice:
    """Cria fatura, registro fiscal e recebíveis dentro da mesma transação."""
    from controlb.modules.documents import schemas as document_schemas
    from controlb.modules.documents import service as documents_service

    _validate_current_user_tenant(current_user, organization_id)
    if payload.due_date < payload.issue_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O vencimento não pode ser anterior à emissão.",
        )
    order = None
    invoice_lines: list[dict] = []
    if payload.sales_order_id:
        order = db.scalar(
            select(sales_models.SalesOrder).where(
                sales_models.SalesOrder.id == payload.sales_order_id,
                sales_models.SalesOrder.organization_id == organization_id,
            )
        )
        if not order:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O pedido de venda vinculado à fatura é inválido.",
            )
        from controlb.modules.sales.service import get_sales_order_document

        if source_document is None:
            source_document = get_sales_order_document(db, order, organization_id)
        if payload.items:
            invoice_lines, calculated_total = _prepare_invoice_lines(
                db, organization_id, order, payload.items
            )
            if calculated_total <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="O valor dos itens selecionados deve ser maior que zero.",
                )
            if abs(calculated_total - payload.total_amount) > MONEY:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "O total informado diverge dos itens do pedido. "
                        f"Total calculado: {calculated_total}."
                    ),
                )
    elif payload.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Itens de pedido exigem o vínculo com um pedido de venda.",
        )

    organization = db.scalar(
        select(Organization).where(Organization.id == organization_id)
    )
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A organização da fatura é inválida.",
        )

    invoice_id = uuid.uuid4()
    net_amount = payload.total_amount + payload.tax_amount
    header = documents_service.create_document(
        db,
        organization_id=organization_id,
        payload=document_schemas.DocumentCreate(
            category="billing.invoice",
            document_type="INVOICE",
            native_id=invoice_id,
            title="Fatura Comercial",
            current_status="ISSUED",
            description=payload.notes,
            origin_module="BILLING",
            responsible_id=current_user.id,
            payload={
                "sales_order_id": (
                    str(payload.sales_order_id) if payload.sales_order_id else None
                ),
                "customer_name": payload.customer_name.strip(),
                "customer_document": payload.customer_document,
                "total_amount": str(payload.total_amount),
                "tax_amount": str(payload.tax_amount),
                "net_amount": str(net_amount),
                "due_date": payload.due_date.isoformat(),
                "items": [
                    {
                        "sales_order_item_id": str(line["sales_order_item_id"]),
                        "product_id": str(line["product_id"]),
                        "description": line["description"],
                        "product_sku": line["product_sku"],
                        "quantity": str(line["quantity"]),
                        "unit_price": str(line["unit_price"]),
                        "discount_amount": str(line["discount_amount"]),
                        "total_amount": str(line["total_amount"]),
                    }
                    for line in invoice_lines
                ],
            },
            issued_at=datetime.combine(
                payload.issue_date, datetime.min.time(), tzinfo=timezone.utc
            ),
        ),
        current_user=current_user,
    )
    header.title = f"Fatura Comercial {header.document_number}"

    invoice = models.Invoice(
        id=invoice_id,
        organization_id=organization_id,
        document_id=header.id,
        sales_order_id=payload.sales_order_id,
        invoice_number=header.document_number,
        customer_name=payload.customer_name.strip(),
        customer_document=(
            payload.customer_document.strip() if payload.customer_document else None
        ),
        total_amount=payload.total_amount,
        tax_amount=payload.tax_amount,
        net_amount=net_amount,
        issue_date=payload.issue_date,
        due_date=payload.due_date,
        status="ISSUED",
        notes=payload.notes,
        created_by_id=current_user.id,
    )

    for line in invoice_lines:
        invoice.items.append(
            models.InvoiceItem(
                organization_id=organization_id,
                sales_order_item_id=line["sales_order_item_id"],
                product_id=line["product_id"],
                description=line["description"],
                product_sku=line["product_sku"],
                quantity=line["quantity"],
                unit_price=line["unit_price"],
                discount_amount=line["discount_amount"],
                total_amount=line["total_amount"],
            )
        )

    installment_count = payload.installments_count or 1
    installment_value = (
        net_amount / Decimal(str(installment_count))
    ).quantize(Decimal("0.01"))
    for number in range(1, installment_count + 1):
        amount = (
            net_amount - installment_value * Decimal(str(installment_count - 1))
            if number == installment_count
            else installment_value
        )
        invoice.installments.append(
            models.InvoiceInstallment(
                installment_number=number,
                total_installments=installment_count,
                amount=amount,
                due_date=payload.due_date + timedelta(days=(number - 1) * 30),
                status="PENDING",
            )
        )

    saved_invoice = repository.create_invoice(db, invoice)

    if source_document is not None:
        documents_service.relate_documents(
            db,
            organization_id=organization_id,
            parent_document=source_document,
            child_document=header,
            relation_type=(
                "GENERATED"
                if source_document.document_type == "BILLING_REQUEST"
                else "INVOICED_BY"
            ),
            created_by_id=current_user.id,
        )

    fiscal_document = None
    if payload.generate_outbound_fiscal_document:
        fiscal_document = finance_service.persist_fiscal_document(
            db,
            organization_id,
            current_user,
            finance_schemas.FiscalDocumentCreate(
                direction="OUTBOUND",
                document_type=payload.fiscal_document_type.upper(),
                document_number=(payload.fiscal_document_number or header.document_number),
                series=payload.fiscal_series,
                access_key=payload.fiscal_access_key,
                issuer_name=organization.name,
                recipient_name=invoice.customer_name,
                recipient_cnpj_cpf=invoice.customer_document,
                issue_date=invoice.issue_date,
                total_amount=invoice.net_amount,
                tax_amount=invoice.tax_amount,
                notes=f"Registro fiscal de saída originado da fatura {invoice.invoice_number}",
                status="draft",
            ),
            source_document=header,
        )
        invoice.fiscal_document_id = fiscal_document.id
        if invoice.sales_order_id:
            from controlb.modules.inventory import service as inventory_service

            inventory_service.link_sales_order_delivery_to_fiscal_document(
                db,
                organization_id=organization_id,
                sales_order_id=invoice.sales_order_id,
                fiscal_document=fiscal_document,
                actor_id=current_user.id,
            )

    if payload.generate_receivables_in_finance:
        receivable_source = (
            finance_service.get_fiscal_document_header(db, fiscal_document, organization_id)
            if fiscal_document
            else header
        )
        for installment in saved_invoice.installments:
            finance_service.create_receivable(
                db,
                organization_id,
                finance_schemas.ReceivableCreate(
                    customer_id=getattr(saved_invoice, 'customer_id', None),
                    customer_name=invoice.customer_name,
                    customer_document=invoice.customer_document,
                    fiscal_document_id=(fiscal_document.id if fiscal_document else None),
                    description=(
                        f"Fatura {invoice.invoice_number} "
                        f"(Parcela {installment.installment_number}/{installment.total_installments})"
                    ),
                    original_amount=installment.amount,
                    issue_date=invoice.issue_date,
                    due_date=installment.due_date,
                    payment_method_expected="BOLETO",
                    notes=f"Originado da Fatura Comercial #{invoice.invoice_number}",
                ),
                current_user=current_user,
                source_document=receivable_source,
                invoice_installment_id=installment.id,
            )

    db.flush()
    logger.info(
        "[INVOICE CREATED] Fatura #%s emitida para '%s': %s R$ em %s parcela(s)",
        invoice.invoice_number,
        invoice.customer_name,
        net_amount,
        installment_count,
    )
    return saved_invoice


def list_invoices(db: Session, organization_id: uuid.UUID) -> list[models.Invoice]:
    invoices = repository.list_invoices(db, organization_id)
    for invoice in invoices:
        get_invoice_header(db, invoice, organization_id)
    return invoices


def get_invoice(
    db: Session,
    organization_id: uuid.UUID,
    invoice_id: uuid.UUID,
) -> models.Invoice:
    invoice = repository.get_invoice_by_id(db, invoice_id, organization_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fatura não encontrada.",
        )
    get_invoice_header(db, invoice, organization_id)
    return invoice


def list_billing_requests(db: Session, organization_id: uuid.UUID):
    """Expõe a fila documental criada por Vendas para o módulo de Faturamento."""
    from controlb.modules.documents import schemas as document_schemas
    from controlb.modules.documents import service as documents_service

    return documents_service.list_documents(
        db,
        organization_id,
        document_schemas.DocumentFilterParams(
            category="billing.request",
            limit=500,
        ),
    )


def process_billing_request(
    db: Session,
    organization_id: uuid.UUID,
    request_id: uuid.UUID,
    current_user: User,
    payload: schemas.BillingRequestIssue,
) -> models.Invoice:
    """Atende a solicitação de Vendas e materializa toda a cadeia de faturamento."""
    from controlb.modules.documents import repository as documents_repository
    from controlb.modules.documents import service as documents_service
    from controlb.modules.sales import repository as sales_repository
    from controlb.modules.sales.service import get_sales_order_document

    _validate_current_user_tenant(current_user, organization_id)
    request = documents_service.get_document(db, request_id, organization_id)
    if request.category != "billing.request" or request.document_type != "BILLING_REQUEST":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O documento informado não é uma solicitação de faturamento.",
        )

    # Repetir a operação devolve a fatura já relacionada, evitando emissão dupla.
    for relation in documents_repository.list_relations_by_parent(
        db, request.id, organization_id
    ):
        child = documents_service.get_document(
            db, relation.child_document_id, organization_id
        )
        if child.document_type == "INVOICE" and child.native_id:
            return get_invoice(db, organization_id, child.native_id)

    if request.current_status != "REQUESTED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Somente solicitações pendentes podem ser processadas. "
                f"Status atual: {request.current_status}."
            ),
        )
    if payload.due_date < payload.issue_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O vencimento não pode ser anterior à emissão.",
        )

    try:
        sales_order_id = uuid.UUID(str((request.payload or {}).get("sales_order_id")))
    except (TypeError, ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A solicitação não possui um pedido de venda válido.",
        ) from None

    order = sales_repository.get_order_by_id_for_update(
        db, sales_order_id, organization_id
    )
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="O pedido de venda da solicitação não foi encontrado.",
        )
    if order.status == "CANCELLED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O pedido foi cancelado e não pode ser faturado.",
        )
    if order.billing_status == "INVOICED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O pedido já possui faturamento concluído.",
        )

    requested_items = payload.items or _remaining_invoice_items(
        db, organization_id, order
    )
    if not requested_items:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O pedido não possui saldo pendente de faturamento.",
        )
    _, invoice_total = _prepare_invoice_lines(
        db, organization_id, order, requested_items
    )

    invoice = create_invoice(
        db,
        organization_id,
        current_user,
        schemas.InvoiceCreate(
            sales_order_id=order.id,
            customer_name=order.customer_name,
            customer_document=order.customer_document,
            total_amount=invoice_total,
            tax_amount=payload.tax_amount,
            issue_date=payload.issue_date,
            due_date=payload.due_date,
            installments_count=payload.installments_count,
            notes=(
                payload.notes
                or f"Faturamento processado a partir do Pedido #{order.order_number}"
            ),
            generate_receivables_in_finance=payload.generate_receivables_in_finance,
            generate_outbound_fiscal_document=payload.generate_outbound_fiscal_document,
            fiscal_document_type=payload.fiscal_document_type,
            fiscal_document_number=payload.fiscal_document_number,
            fiscal_series=payload.fiscal_series,
            fiscal_access_key=payload.fiscal_access_key,
            items=requested_items,
        ),
        source_document=request,
    )

    request.payload = {
        **(request.payload or {}),
        "invoice_id": str(invoice.id),
        "invoice_number": invoice.invoice_number,
        "invoiced_amount": str(invoice.total_amount),
        "invoiced_items": [
            {
                "sales_order_item_id": str(item.sales_order_item_id),
                "quantity": str(item.quantity),
            }
            for item in invoice.items
        ],
    }

    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=request,
        event_type="INVOICE_CREATED",
        previous_status="REQUESTED",
        new_status="COMPLETED",
        created_by_id=current_user.id,
        event_metadata={
            "sales_order_id": str(order.id),
            "invoice_id": str(invoice.id),
            "invoice_number": invoice.invoice_number,
        },
        idempotency_key=f"billing-request:{request.id}:invoice:{invoice.id}",
    )
    order.billing_status = _calculate_order_billing_status(
        db, organization_id, order
    )
    order_header = get_sales_order_document(db, order, organization_id)
    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=order_header,
        event_type=(
            "PARTIALLY_INVOICED"
            if order.billing_status == "PARTIALLY_INVOICED"
            else "INVOICED"
        ),
        previous_status=order.status,
        new_status=order.status,
        created_by_id=current_user.id,
        event_metadata={
            "billing_request_id": str(request.id),
            "invoice_id": str(invoice.id),
            "invoice_number": invoice.invoice_number,
            "billing_status": order.billing_status,
            "invoiced_amount": str(invoice.total_amount),
        },
        idempotency_key=f"sales-order:{order.id}:invoiced:{invoice.id}",
    )
    db.flush()
    return invoice


def cancel_billing_request(
    db: Session,
    organization_id: uuid.UUID,
    request_id: uuid.UUID,
    current_user: User,
    payload: schemas.BillingRequestCancel,
):
    """Cancela uma pendência ainda não emitida e reabre o saldo do pedido."""
    from controlb.modules.documents import service as documents_service
    from controlb.modules.sales import repository as sales_repository
    from controlb.modules.sales.service import get_sales_order_document

    _validate_current_user_tenant(current_user, organization_id)
    request = documents_service.get_document(db, request_id, organization_id)
    if request.category != "billing.request" or request.document_type != "BILLING_REQUEST":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O documento informado não é uma solicitação de faturamento.",
        )
    if request.current_status == "CANCELLED":
        return request
    if request.current_status != "REQUESTED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Somente solicitações pendentes podem ser canceladas.",
        )

    sales_order_id = (request.payload or {}).get("sales_order_id")
    try:
        order_id = uuid.UUID(str(sales_order_id))
    except (TypeError, ValueError, AttributeError):
        order_id = None
    order = (
        sales_repository.get_order_by_id_for_update(db, order_id, organization_id)
        if order_id
        else None
    )

    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=request,
        event_type="BILLING_REQUEST_CANCELLED",
        previous_status="REQUESTED",
        new_status="CANCELLED",
        created_by_id=current_user.id,
        event_metadata={"reason": payload.reason},
    )
    if order:
        order.billing_status = _calculate_order_billing_status(
            db, organization_id, order
        )
        order_header = get_sales_order_document(db, order, organization_id)
        documents_service.record_event(
            db,
            organization_id=organization_id,
            document=order_header,
            event_type="BILLING_REQUEST_CANCELLED",
            created_by_id=current_user.id,
            event_metadata={
                "billing_request_id": str(request.id),
                "reason": payload.reason,
                "billing_status": order.billing_status,
            },
        )
    request.payload = {
        **(request.payload or {}),
        "cancellation_reason": payload.reason,
    }
    db.flush()
    return request


def _invoice_receivables(
    db: Session,
    invoice: models.Invoice,
) -> list[finance_models.Receivable]:
    installment_ids = [installment.id for installment in invoice.installments]
    if not installment_ids:
        return []
    return list(
        db.scalars(
            select(finance_models.Receivable).where(
                finance_models.Receivable.organization_id == invoice.organization_id,
                finance_models.Receivable.invoice_installment_id.in_(installment_ids),
            )
        ).all()
    )


def update_invoice(
    db: Session,
    organization_id: uuid.UUID,
    invoice_id: uuid.UUID,
    current_user: User,
    payload: schemas.InvoiceUpdate,
) -> models.Invoice:
    """Atualiza a fatura e projeta os dados nos títulos ainda não liquidados."""
    from controlb.modules.documents import schemas as document_schemas
    from controlb.modules.documents import service as documents_service

    _validate_current_user_tenant(current_user, organization_id)
    invoice = get_invoice(db, organization_id, invoice_id)
    header = get_invoice_header(db, invoice, organization_id)
    if invoice.status in {"CANCELLED", "PAID"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fatura cancelada ou paga não pode ser editada.",
        )

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return invoice
    if "customer_name" in changes and changes["customer_name"] is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="O nome do cliente não pode ser removido.",
        )
    if any(
        changes.get(field) is None
        for field in ("issue_date", "due_date")
        if field in changes
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="As datas de emissão e vencimento não podem ser removidas.",
        )
    receivables = _invoice_receivables(db, invoice)
    has_receipts = any(
        receivable.outstanding_amount < receivable.original_amount
        for receivable in receivables
    )
    commercial_fields = set(changes) - {"notes"}
    if has_receipts and commercial_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Após o primeiro recebimento, apenas as observações da fatura podem ser editadas.",
        )

    old_due_date = invoice.due_date
    new_due_date = changes.get("due_date", old_due_date)
    new_issue_date = changes.get("issue_date", invoice.issue_date)
    if new_due_date < new_issue_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O vencimento não pode ser anterior à data de emissão.",
        )

    if "customer_name" in changes:
        changes["customer_name"] = changes["customer_name"].strip()
    if "customer_document" in changes and changes["customer_document"] is not None:
        changes["customer_document"] = changes["customer_document"].strip() or None
    for field, value in changes.items():
        setattr(invoice, field, value)

    due_delta = new_due_date - old_due_date
    installments_by_id = {item.id: item for item in invoice.installments}
    if "due_date" in changes:
        for installment in invoice.installments:
            installment.due_date = installment.due_date + due_delta

    for receivable in receivables:
        receivable_changes: dict = {}
        if "customer_name" in changes:
            receivable_changes["customer_name"] = invoice.customer_name
        if "customer_document" in changes:
            receivable_changes["customer_document"] = invoice.customer_document
        if "issue_date" in changes:
            receivable_changes["issue_date"] = invoice.issue_date
        if "due_date" in changes:
            installment = installments_by_id.get(receivable.invoice_installment_id)
            if installment:
                receivable_changes["due_date"] = installment.due_date
        if receivable_changes:
            finance_service.update_receivable(
                db,
                organization_id,
                receivable.id,
                current_user,
                finance_schemas.ReceivableUpdate(**receivable_changes),
            )

    document_payload = dict(header.payload or {})
    document_payload.update(
        {
            "customer_name": invoice.customer_name,
            "customer_document": invoice.customer_document,
            "due_date": invoice.due_date.isoformat(),
        }
    )
    documents_service.update_document(
        db,
        header.id,
        organization_id,
        document_schemas.DocumentUpdate(
            title=f"Fatura Comercial {invoice.invoice_number} - {invoice.customer_name}",
            description=invoice.notes,
            payload=document_payload,
        ),
        current_user=current_user,
    )
    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=header,
        event_type="INVOICE_UPDATED",
        created_by_id=current_user.id,
        event_metadata={"updated_fields": sorted(changes)},
    )
    repository.update_invoice(db, invoice)
    db.flush()
    return get_invoice(db, organization_id, invoice.id)


def cancel_invoice(
    db: Session,
    organization_id: uuid.UUID,
    invoice_id: uuid.UUID,
    current_user: User,
    payload: schemas.InvoiceCancel,
) -> models.Invoice:
    """Cancela uma fatura ainda não liquidada e seus derivados em aberto."""
    from controlb.modules.documents import service as documents_service

    _validate_current_user_tenant(current_user, organization_id)
    invoice = get_invoice(db, organization_id, invoice_id)
    header = get_invoice_header(db, invoice, organization_id)
    if invoice.status == "CANCELLED":
        return invoice
    receivables = _invoice_receivables(db, invoice)
    if any(receivable.outstanding_amount < receivable.original_amount for receivable in receivables):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fatura com recebimento registrado não pode ser cancelada. Faça o estorno financeiro antes.",
        )

    if invoice.fiscal_document_id:
        fiscal = finance_repository.get_fiscal_document_by_id(
            db, invoice.fiscal_document_id, organization_id
        )
        if fiscal:
            finance_service.get_fiscal_document_header(db, fiscal, organization_id)
            if fiscal.status.upper() == "AUTHORIZED":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="A nota fiscal está autorizada. Cancele o documento fiscal antes da fatura.",
                )
            if fiscal.status.upper() != "CANCELLED":
                finance_service.update_fiscal_document(
                    db,
                    organization_id,
                    fiscal.id,
                    current_user,
                    finance_schemas.FiscalDocumentUpdate(status="CANCELLED"),
                )

    for receivable in receivables:
        if receivable.status != "CANCELLED":
            finance_service.transition_receivable_status(
                db,
                receivable,
                organization_id,
                "CANCELLED",
                actor_id=current_user.id,
                event_type="INVOICE_CANCELLED",
                event_metadata={"invoice_id": str(invoice.id), "reason": payload.reason},
            )
    for installment in invoice.installments:
        installment.status = "CANCELLED"

    previous_status = header.current_status
    invoice.status = "CANCELLED"
    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=header,
        event_type="INVOICE_CANCELLED",
        previous_status=previous_status,
        new_status="CANCELLED",
        created_by_id=current_user.id,
        event_metadata={"reason": payload.reason},
    )

    # Reabre o pedido para um novo ciclo de faturamento sem apagar a
    # solicitação/fatura canceladas da cadeia documental.
    if invoice.sales_order_id:
        order = db.scalar(
            select(sales_models.SalesOrder).where(
                sales_models.SalesOrder.id == invoice.sales_order_id,
                sales_models.SalesOrder.organization_id == organization_id,
            )
        )
        if order:
            from controlb.modules.sales.service import get_sales_order_document

            order.billing_status = _calculate_order_billing_status(
                db, organization_id, order
            )
            order_header = get_sales_order_document(db, order, organization_id)
            documents_service.record_event(
                db,
                organization_id=organization_id,
                document=order_header,
                event_type="BILLING_REOPENED",
                created_by_id=current_user.id,
                event_metadata={
                    "cancelled_invoice_id": str(invoice.id),
                    "reason": payload.reason,
                    "billing_status": order.billing_status,
                },
            )

    from controlb.modules.documents import repository as documents_repository

    for relation in documents_repository.list_relations_by_child(
        db, header.id, organization_id
    ):
        if relation.relation_type != "GENERATED":
            continue
        source = documents_service.get_document(
            db, relation.parent_document_id, organization_id
        )
        if source.document_type == "BILLING_REQUEST" and source.current_status != "CANCELLED":
            documents_service.record_event(
                db,
                organization_id=organization_id,
                document=source,
                event_type="INVOICE_CANCELLED",
                previous_status=source.current_status,
                new_status="CANCELLED",
                created_by_id=current_user.id,
                event_metadata={
                    "invoice_id": str(invoice.id),
                    "reason": payload.reason,
                },
            )
    repository.update_invoice(db, invoice)
    db.flush()
    return get_invoice(db, organization_id, invoice.id)


def synchronize_invoice_payment_status(
    db: Session,
    organization_id: uuid.UUID,
    invoice_installment_id: uuid.UUID,
    *,
    actor_id: uuid.UUID | None = None,
) -> None:
    """Projeta a baixa do Contas a Receber no ciclo da parcela e da fatura."""
    from controlb.modules.documents import service as documents_service

    installment = db.get(models.InvoiceInstallment, invoice_installment_id)
    if not installment:
        return
    invoice = repository.get_invoice_by_id(db, installment.invoice_id, organization_id)
    if not invoice or invoice.status == "CANCELLED":
        return
    receivables = _invoice_receivables(db, invoice)
    receivable_by_installment = {
        receivable.invoice_installment_id: receivable for receivable in receivables
    }
    status_mapping = {
        "RECEIVED": "PAID",
        "PARTIALLY_RECEIVED": "PARTIALLY_RECEIVED",
        "OVERDUE": "OVERDUE",
        "CANCELLED": "CANCELLED",
    }
    for item in invoice.installments:
        receivable = receivable_by_installment.get(item.id)
        if receivable:
            item.status = status_mapping.get(receivable.status, "PENDING")

    installment_statuses = {item.status for item in invoice.installments}
    if installment_statuses == {"PAID"}:
        new_status = "PAID"
    elif "PARTIALLY_RECEIVED" in installment_statuses or "PAID" in installment_statuses:
        new_status = "PARTIALLY_RECEIVED"
    elif "OVERDUE" in installment_statuses:
        new_status = "OVERDUE"
    else:
        new_status = "ISSUED"

    header = get_invoice_header(db, invoice, organization_id)
    previous_status = header.current_status
    invoice.status = new_status
    if new_status != previous_status:
        documents_service.record_event(
            db,
            organization_id=organization_id,
            document=header,
            event_type="PAYMENT_STATUS_UPDATED",
            previous_status=previous_status,
            new_status=new_status,
            created_by_id=actor_id,
            event_metadata={"invoice_installment_id": str(invoice_installment_id)},
        )
    repository.update_invoice(db, invoice)
