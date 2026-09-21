"""
modules/sales/service.py - Regras de Negócio e Serviços do Módulo de Vendas & PDV
"""

import re
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from controlb.logger import logger
from controlb.modules.documents import schemas as document_schemas
from controlb.modules.documents import service as documents_service
from controlb.modules.identity.models import User
from controlb.modules.inventory import repository as inventory_repository
from controlb.modules.inventory.models import Product
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


def _default_commercial_settings(organization_id: uuid.UUID) -> models.CommercialSettings:
    return models.CommercialSettings(
        organization_id=organization_id,
        default_payment_terms="30 DDL",
        quote_validity_days=15,
        maximum_discount_percent=Decimal("100.00"),
        default_commission_percent=Decimal("2.00"),
        automatic_discount_limit_percent=Decimal("5.00"),
        minimum_margin_percent=Decimal("0.00"),
        maximum_payment_term_days_without_approval=0,
    )


def get_commercial_settings(
    db: Session,
    organization_id: uuid.UUID,
) -> models.CommercialSettings:
    """Retorna parâmetros persistidos ou defaults sem criar dados durante uma leitura."""
    return (
        repository.get_commercial_settings(db, organization_id)
        or _default_commercial_settings(organization_id)
    )


def update_commercial_settings(
    db: Session,
    organization_id: uuid.UUID,
    payload: schemas.CommercialSettingsUpdate,
) -> models.CommercialSettings:
    settings = repository.get_commercial_settings(db, organization_id)
    if settings is None:
        settings = _default_commercial_settings(organization_id)

    if payload.default_payment_terms is not None:
        payment_terms = payload.default_payment_terms.strip()
        if not payment_terms:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A condição de pagamento padrão é obrigatória.",
            )
        settings.default_payment_terms = payment_terms
    if payload.quote_validity_days is not None:
        settings.quote_validity_days = payload.quote_validity_days
    if payload.maximum_discount_percent is not None:
        settings.maximum_discount_percent = payload.maximum_discount_percent
    if payload.default_commission_percent is not None:
        settings.default_commission_percent = payload.default_commission_percent
    if payload.automatic_discount_limit_percent is not None:
        settings.automatic_discount_limit_percent = payload.automatic_discount_limit_percent
    if payload.minimum_margin_percent is not None:
        settings.minimum_margin_percent = payload.minimum_margin_percent
    if payload.maximum_payment_term_days_without_approval is not None:
        settings.maximum_payment_term_days_without_approval = (
            payload.maximum_payment_term_days_without_approval
        )
    if settings.automatic_discount_limit_percent > settings.maximum_discount_percent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A alçada automática não pode superar o desconto máximo absoluto.",
        )

    return repository.save_commercial_settings(db, settings)


def _validate_discount_limit(
    settings: models.CommercialSettings,
    total_gross: Decimal,
    total_discount: Decimal,
) -> None:
    if total_gross <= 0:
        return
    discount_percent = (total_discount / total_gross) * Decimal("100")
    if discount_percent > settings.maximum_discount_percent:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"O desconto de {discount_percent.quantize(Decimal('0.01'))}% supera o limite "
                f"comercial de {settings.maximum_discount_percent}% configurado para a organização."
            ),
        )


def _payment_term_days(payment_terms: str | None) -> int:
    if not payment_terms:
        return 0
    normalized = payment_terms.casefold()
    if "vista" in normalized:
        return 0
    days = [int(value) for value in re.findall(r"\d+", normalized)]
    return max(days, default=0)


def _commercial_approval_triggers(
    db: Session,
    organization_id: uuid.UUID,
    document: models.SalesQuote | models.SalesOrder,
    settings: models.CommercialSettings,
) -> dict[str, tuple[Decimal, Decimal, str]]:
    triggers: dict[str, tuple[Decimal, Decimal, str]] = {}
    total_gross = Decimal(document.total_amount or 0)
    total_discount = Decimal(document.discount_amount or 0)
    net_amount = Decimal(document.net_amount or 0)

    discount_percent = (
        (total_discount / total_gross) * Decimal("100")
        if total_gross > 0
        else Decimal("0.00")
    )
    if discount_percent > settings.automatic_discount_limit_percent:
        triggers["DISCOUNT"] = (
            discount_percent,
            Decimal(settings.automatic_discount_limit_percent),
            (
                f"Desconto de {discount_percent.quantize(Decimal('0.01'))}% acima da "
                f"alçada automática de {settings.automatic_discount_limit_percent}%."
            ),
        )

    total_cost = Decimal("0.00")
    for item in document.items:
        product = inventory_repository.get_product_by_id(
            db, item.product_id, organization_id
        )
        if product:
            total_cost += Decimal(item.quantity) * Decimal(product.cost_price or 0)
    margin_percent = (
        ((net_amount - total_cost) / net_amount) * Decimal("100")
        if net_amount > 0
        else Decimal("0.00")
    )
    if (
        settings.minimum_margin_percent > 0
        and margin_percent < settings.minimum_margin_percent
    ):
        triggers["MARGIN"] = (
            margin_percent,
            Decimal(settings.minimum_margin_percent),
            (
                f"Margem de {margin_percent.quantize(Decimal('0.01'))}% abaixo da mínima "
                f"de {settings.minimum_margin_percent}%."
            ),
        )

    payment_days = _payment_term_days(document.payment_terms)
    if (
        settings.maximum_payment_term_days_without_approval > 0
        and payment_days > settings.maximum_payment_term_days_without_approval
    ):
        triggers["PAYMENT_TERM"] = (
            Decimal(payment_days),
            Decimal(settings.maximum_payment_term_days_without_approval),
            (
                f"Prazo de {payment_days} dias acima da alçada automática de "
                f"{settings.maximum_payment_term_days_without_approval} dias."
            ),
        )
    return triggers


def _recalculate_commercial_approval_status(
    document: models.SalesQuote | models.SalesOrder,
    approvals: list[models.CommercialApprovalRequest],
) -> None:
    active = [item for item in approvals if item.status != "CANCELLED"]
    if any(item.status == "REJECTED" for item in active):
        document.commercial_approval_status = "REJECTED"
    elif any(item.status == "PENDING" for item in active):
        document.commercial_approval_status = "PENDING"
    elif active:
        document.commercial_approval_status = "APPROVED"
    else:
        document.commercial_approval_status = "NOT_REQUIRED"


def _apply_commercial_approval_rules(
    db: Session,
    organization_id: uuid.UUID,
    document: models.SalesQuote | models.SalesOrder,
    actor_id: uuid.UUID | None,
) -> None:
    settings = get_commercial_settings(db, organization_id)
    triggers = _commercial_approval_triggers(db, organization_id, document, settings)
    is_quote = isinstance(document, models.SalesQuote)
    quote_id = document.id if is_quote else None
    order_id = document.id if not is_quote else None
    current = repository.list_commercial_approvals_for_document(
        db,
        organization_id,
        quote_id=quote_id,
        order_id=order_id,
    )
    current_by_type = {item.approval_type: item for item in current}
    requested: list[models.CommercialApprovalRequest] = []

    for approval_type, (metric, threshold, reason) in triggers.items():
        approval = current_by_type.get(approval_type)
        changed = (
            approval is None
            or Decimal(approval.metric_value) != metric
            or Decimal(approval.threshold_value) != threshold
        )
        should_request = approval is None or changed or approval.status in {
            "REJECTED", "CANCELLED"
        }
        if approval is None:
            approval = models.CommercialApprovalRequest(
                organization_id=organization_id,
                sales_quote_id=quote_id,
                sales_order_id=order_id,
                approval_type=approval_type,
                status="PENDING",
                metric_value=metric,
                threshold_value=threshold,
                request_reason=reason,
                requested_by_id=actor_id,
            )
        elif changed or approval.status in {"REJECTED", "CANCELLED"}:
            approval.status = "PENDING"
            approval.metric_value = metric
            approval.threshold_value = threshold
            approval.request_reason = reason
            approval.requested_by_id = actor_id
            approval.decision_reason = None
            approval.decided_by_id = None
            approval.decided_at = None
        repository.save_commercial_approval_request(db, approval)
        if should_request:
            requested.append(approval)

    for approval in current:
        if approval.approval_type not in triggers and approval.status != "CANCELLED":
            approval.status = "CANCELLED"

    db.flush()
    approvals = repository.list_commercial_approvals_for_document(
        db,
        organization_id,
        quote_id=quote_id,
        order_id=order_id,
    )
    _recalculate_commercial_approval_status(document, approvals)

    if requested:
        business_document = (
            _ensure_quote_document(db, document, organization_id)
            if is_quote
            else _ensure_order_document(db, document, organization_id)
        )
        for approval in requested:
            documents_service.record_event(
                db,
                organization_id=organization_id,
                document=business_document,
                event_type="COMMERCIAL_APPROVAL_REQUESTED",
                previous_status=None,
                new_status=None,
                created_by_id=actor_id,
                event_metadata={
                    "approval_id": str(approval.id),
                    "approval_type": approval.approval_type,
                    "metric_value": str(approval.metric_value),
                    "threshold_value": str(approval.threshold_value),
                    "reason": approval.request_reason,
                },
                idempotency_key=(
                    f"sales-commercial-approval:{approval.id}:requested:"
                    f"{uuid.uuid4().hex}"
                ),
            )


def _assert_commercial_approval_released(
    document: models.SalesQuote | models.SalesOrder,
) -> None:
    if document.commercial_approval_status in {"PENDING", "REJECTED"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "O documento possui aprovação comercial pendente ou rejeitada. "
                "Conclua as alçadas de desconto, margem e prazo antes de prosseguir."
            ),
        )


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


def _normalize_phone_number(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if not digits:
        return None
    if len(digits) in (10, 11) and not digits.startswith("55"):
        return f"55{digits}"
    return digits


def create_customer(
    db: Session,
    organization_id: uuid.UUID,
    payload: schemas.CustomerCreate,
) -> models.Customer:
    """
    Cadastra o cliente referenciando um contato existente, sem alterar o Identity.
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

    from controlb.modules.identity.contact_identity import reject_legacy_fields, validate_link
    reject_legacy_fields(payload, ("email", "phone", "secondary_phone", "contact_role"))
    validate_link(db, organization_id, payload.contact_id)
    payload.document = doc_clean
    payload.name = name_clean
    return repository.create_customer(db, organization_id, payload)


def update_customer(
    db: Session,
    customer_id: uuid.UUID,
    organization_id: uuid.UUID,
    payload: schemas.CustomerUpdate,
) -> models.Customer:
    """Atualiza o cliente; dados pessoais pertencem exclusivamente ao Identity."""
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

    from controlb.modules.identity.contact_identity import reject_legacy_fields, validate_link
    reject_legacy_fields(payload, ("email", "phone", "secondary_phone", "contact_role"))
    if "contact_id" in payload.model_fields_set:
        validate_link(db, organization_id, payload.contact_id)
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
    if quote.document_id:
        document = documents_service.get_document(db, quote.document_id, organization_id)
        if document.document_type != "SALES_QUOTE" or document.native_id != quote.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="O cabeçalho documental vinculado à cotação é inconsistente.",
            )
    else:
        # Compatibilidade para registros legados ainda sem vínculo explícito. Depois
        # deste ponto, BusinessDocument passa a ser a fonte do número e do status.
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

    document.category = "sales.quotation"
    document.origin_module = "SALES"
    quote.document_id = document.id
    quote.quote_number = document.document_number
    quote.status = document.current_status
    return document


def _ensure_order_document(
    db: Session,
    order: models.SalesOrder,
    organization_id: uuid.UUID,
):
    if order.document_id:
        document = documents_service.get_document(db, order.document_id, organization_id)
        if document.document_type != "SALES_ORDER" or document.native_id != order.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="O cabeçalho documental vinculado ao pedido é inconsistente.",
            )
    else:
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

    document.category = "sales.order"
    document.origin_module = "SALES"
    order.document_id = document.id
    order.order_number = document.document_number
    order.status = document.current_status
    return document


def get_sales_order_document(
    db: Session,
    order: models.SalesOrder,
    organization_id: uuid.UUID,
):
    """Expõe o cabeçalho canônico sem vazar a persistência de Documents."""
    return _ensure_order_document(db, order, organization_id)


def _create_order_document(
    db: Session,
    *,
    organization_id: uuid.UUID,
    order_id: uuid.UUID,
    customer_name: str,
    current_user: User,
):
    return documents_service.create_document(
        db,
        organization_id=organization_id,
        payload=document_schemas.DocumentCreate(
            category="sales.order",
            document_type="SALES_ORDER",
            native_id=order_id,
            title=f"Pedido de Venda - {customer_name.strip()}",
            current_status="CONFIRMED",
            origin_module="SALES",
            responsible_id=current_user.id,
        ),
        current_user=current_user,
    )


def get_customer_credit_analysis(
    db: Session,
    organization_id: uuid.UUID,
    customer_id: uuid.UUID,
    proposed_order_amount: Decimal = Decimal("0.00"),
    exclude_order_id: uuid.UUID | None = None,
) -> schemas.CustomerCreditAnalysisResponse:
    """Calcula a exposição sem duplicar pedido faturado e título a receber."""
    customer = repository.get_customer_by_id(db, customer_id, organization_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente não encontrado.",
        )
    if proposed_order_amount < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O valor proposto não pode ser negativo.",
        )

    unbilled = repository.get_unbilled_order_exposure(
        db,
        organization_id,
        customer.id,
        exclude_order_id=exclude_order_id,
    )
    receivables = repository.get_open_receivable_exposure(
        db,
        organization_id,
        customer.document,
    )
    credit_limit = Decimal(customer.credit_limit or 0)
    utilized = unbilled + receivables
    available = max(credit_limit - utilized, Decimal("0.00"))
    projected = utilized + proposed_order_amount
    excess = (
        max(projected - credit_limit, Decimal("0.00"))
        if credit_limit > 0
        else Decimal("0.00")
    )

    return schemas.CustomerCreditAnalysisResponse(
        customer_id=customer.id,
        customer_name=customer.name,
        credit_limit=credit_limit,
        unbilled_orders_amount=unbilled,
        open_receivables_amount=receivables,
        utilized_amount=utilized,
        available_amount=available,
        proposed_order_amount=proposed_order_amount,
        projected_exposure=projected,
        excess_amount=excess,
        requires_approval=credit_limit > 0 and excess > 0,
    )


def _apply_credit_analysis_to_order(
    db: Session,
    organization_id: uuid.UUID,
    order: models.SalesOrder,
    current_user: User,
    *,
    request_reason: str,
) -> None:
    if not order.customer_id:
        order.credit_status = "NOT_REQUIRED"
        return

    # O lock no cliente serializa emissões concorrentes para o mesmo limite.
    customer = repository.get_customer_by_id_for_update(
        db,
        order.customer_id,
        organization_id,
    )
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente não encontrado durante a análise de crédito.",
        )
    analysis = get_customer_credit_analysis(
        db,
        organization_id,
        customer.id,
        proposed_order_amount=Decimal(order.net_amount or 0),
        exclude_order_id=order.id,
    )
    order.credit_limit_snapshot = analysis.credit_limit
    order.credit_exposure_snapshot = analysis.utilized_amount
    order.credit_excess_amount = analysis.excess_amount

    if analysis.credit_limit <= 0:
        order.credit_status = "NOT_REQUIRED"
        return
    if not analysis.requires_approval:
        order.credit_status = "APPROVED"
        return

    order.credit_status = "PENDING"
    approval = models.CreditApprovalRequest(
        organization_id=organization_id,
        sales_order_id=order.id,
        customer_id=customer.id,
        status="PENDING",
        request_reason=request_reason,
        credit_limit=analysis.credit_limit,
        exposure_before_order=analysis.utilized_amount,
        order_amount=Decimal(order.net_amount),
        excess_amount=analysis.excess_amount,
        requested_by_id=current_user.id,
    )
    order.credit_approval = approval
    repository.save_credit_approval_request(db, approval)

    order_document = _ensure_order_document(db, order, organization_id)
    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=order_document,
        event_type="CREDIT_APPROVAL_REQUESTED",
        previous_status=None,
        new_status=None,
        created_by_id=current_user.id,
        event_metadata={
            "approval_id": str(approval.id),
            "credit_limit": str(analysis.credit_limit),
            "exposure_before_order": str(analysis.utilized_amount),
            "order_amount": str(order.net_amount),
            "excess_amount": str(analysis.excess_amount),
            "reason": request_reason,
        },
        idempotency_key=f"sales-order:{order.id}:credit-requested",
    )


def _assert_credit_released(order: models.SalesOrder) -> None:
    if order.credit_status in {"PENDING", "REJECTED"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "O pedido aguarda liberação de crédito. "
                "A reserva, expedição e o faturamento permanecem bloqueados."
            ),
        )


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
    commercial_settings = get_commercial_settings(db, organization_id)

    quote_id = uuid.uuid4()
    quote_document = documents_service.create_document(
        db,
        organization_id=organization_id,
        payload=document_schemas.DocumentCreate(
            category="sales.quotation",
            document_type="SALES_QUOTE",
            native_id=quote_id,
            title=f"Cotação - {payload.customer_name.strip()}",
            current_status="DRAFT",
            origin_module="SALES",
            responsible_id=current_user.id,
        ),
        current_user=current_user,
    )
    quote = models.SalesQuote(
        id=quote_id,
        organization_id=organization_id,
        document_id=quote_document.id,
        quote_number=quote_document.document_number,
        customer_id=payload.customer_id,
        opportunity_id=payload.opportunity_id,
        customer_name=payload.customer_name.strip(),
        customer_document=(
            customer.document
            if customer
            else payload.customer_document.strip() if payload.customer_document else None
        ),
        customer_email=payload.customer_email.strip() if payload.customer_email else None,
        customer_phone=payload.customer_phone.strip() if payload.customer_phone else None,
        payment_terms=payload.payment_terms or commercial_settings.default_payment_terms,
        valid_until=payload.valid_until or (
            date.today() + timedelta(days=commercial_settings.quote_validity_days)
        ),
        status="DRAFT",
        notes=payload.notes,
        created_by_id=current_user.id
    )

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
    _validate_discount_limit(commercial_settings, total_gross, total_disc)

    saved_quote = repository.create_quote(db, quote)
    quote_document.issued_at = saved_quote.created_at
    documents_service.update_document(
        db,
        quote_document.id,
        organization_id,
        document_schemas.DocumentUpdate(
            title=f"Cotação {quote_document.document_number} - {saved_quote.customer_name}",
        ),
        current_user=current_user,
    )
    _apply_commercial_approval_rules(
        db,
        organization_id,
        saved_quote,
        current_user.id,
    )

    if opportunity:
        from controlb.modules.crm import service as crm_service

        opp_doc = crm_service.get_opportunity_document(
            db, opportunity, organization_id
        )
        documents_service.relate_documents(
            db,
            organization_id=organization_id,
            parent_document=opp_doc,
            child_document=quote_document,
            relation_type="GENERATED_QUOTE",
        )
        next_stage = (
            "PROPOSAL"
            if opportunity.stage in ("QUALIFICATION", "PROSPECTING", "DISCOVERY")
            else opportunity.stage
        )
        crm_service.transition_opportunity_stage(
            db,
            opportunity,
            organization_id,
            next_stage,
            current_user=current_user,
            event_type="QUOTE_CREATED",
            event_metadata={"quote_id": str(saved_quote.id), "quote_number": saved_quote.quote_number},
            idempotency_key=f"opportunity:{opportunity.id}:quote:{saved_quote.id}",
            record_if_unchanged=True,
        )

    db.flush()
    return saved_quote


def get_sales_quote(db: Session, quote_id: uuid.UUID, organization_id: uuid.UUID) -> models.SalesQuote:
    quote = repository.get_quote_by_id(db, quote_id, organization_id)
    if not quote:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orçamento não encontrado.")
    _ensure_quote_document(db, quote, organization_id)
    return quote


def update_sales_quote(
    db: Session,
    quote_id: uuid.UUID,
    organization_id: uuid.UUID,
    payload: schemas.SalesQuoteUpdate,
    current_user: User | None = None,
) -> models.SalesQuote:
    quote = repository.get_quote_by_id(db, quote_id, organization_id)
    if not quote:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orçamento não encontrado.")
    quote_document = _ensure_quote_document(db, quote, organization_id)

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
        _validate_discount_limit(
            get_commercial_settings(db, organization_id),
            total_gross,
            total_disc,
        )

    saved_quote = repository.update_quote(db, quote)
    documents_service.update_document(
        db,
        quote_document.id,
        organization_id,
        document_schemas.DocumentUpdate(
            title=f"Cotação {quote_document.document_number} - {saved_quote.customer_name}",
        ),
        current_user=current_user,
    )
    if payload.items is not None or payload.payment_terms is not None:
        _apply_commercial_approval_rules(
            db,
            organization_id,
            saved_quote,
            current_user.id if current_user else quote.created_by_id,
        )
    return saved_quote


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
    quote_document = _ensure_quote_document(db, quote, organization_id)

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
        db.flush()
        return quote
    if normalized_status not in QUOTE_STATUS_TRANSITIONS.get(quote.status, frozenset()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Não é permitido alterar a cotação de {quote.status} para {normalized_status}.",
        )
    if normalized_status == "APPROVED":
        _assert_commercial_approval_released(quote)

    previous_status = quote.status
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
    quote.status = quote_document.current_status
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
    quote_document = _ensure_quote_document(db, quote, organization_id)

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
    quote.cancellation_reason = reason.strip()
    for approval in quote.commercial_approvals:
        if approval.status == "PENDING":
            approval.status = "CANCELLED"
    quote.commercial_approval_status = "NOT_REQUIRED"

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
    quote.status = quote_document.current_status

    if quote.opportunity_id:
        from controlb.modules.crm import repository as crm_repo
        from controlb.modules.crm import service as crm_service

        opp = crm_repo.get_opportunity_by_id(db, quote.opportunity_id, organization_id)
        if opp:
            crm_service.get_opportunity_document(db, opp, organization_id)
        if opp and opp.stage not in ("WON", "LOST"):
            other_active_quotes = [
                q for q in repository.list_quotes(db, organization_id)
                if q.opportunity_id == opp.id and q.id != quote.id and q.status in ("DRAFT", "SENT", "APPROVED")
            ]
            if not other_active_quotes:
                crm_service.transition_opportunity_stage(
                    db,
                    opp,
                    organization_id,
                    "NEGOTIATION",
                    current_user=current_user,
                    event_type="QUOTE_CANCELLED_PIPELINE_REOPENED",
                    event_metadata={"quote_id": str(quote.id)},
                    idempotency_key=(
                        f"opportunity:{opp.id}:quote:{quote.id}:cancelled"
                    ),
                )

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
    quote_document = _ensure_quote_document(db, quote, organization_id)

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
    _assert_commercial_approval_released(quote)
    if not quote.items:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Não é possível converter uma cotação sem itens.",
        )

    customer, opportunity = _validate_commercial_references(
        db,
        organization_id,
        customer_id=quote.customer_id,
        opportunity_id=quote.opportunity_id,
        product_ids=[item.product_id for item in quote.items],
    )

    order_id = uuid.uuid4()
    order_document = _create_order_document(
        db,
        organization_id=organization_id,
        order_id=order_id,
        customer_name=quote.customer_name,
        current_user=current_user,
    )
    order = models.SalesOrder(
        id=order_id,
        organization_id=organization_id,
        document_id=order_document.id,
        order_number=order_document.document_number,
        customer_id=quote.customer_id,
        sales_quote_id=quote.id,
        opportunity_id=quote.opportunity_id,
        customer_name=quote.customer_name,
        customer_document=quote.customer_document or (customer.document if customer else None),
        payment_terms=quote.payment_terms,
        delivery_status="PENDING",
        billing_status="PENDING",
        status="CONFIRMED",
        commercial_approval_status=(
            "APPROVED"
            if quote.commercial_approval_status == "APPROVED"
            else "NOT_REQUIRED"
        ),
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
    quote.status = quote_document.current_status
    db.add(order)
    db.flush()
    order_document.issued_at = order.created_at
    documents_service.update_document(
        db,
        order_document.id,
        organization_id,
        document_schemas.DocumentUpdate(
            title=f"Pedido de Venda {order_document.document_number} - {order.customer_name}",
        ),
        current_user=current_user,
    )
    _apply_credit_analysis_to_order(
        db,
        organization_id,
        order,
        current_user,
        request_reason="Solicitação automática na conversão da cotação.",
    )
    if opportunity:
        from controlb.modules.crm import service as crm_service

        crm_service.transition_opportunity_stage(
            db,
            opportunity,
            organization_id,
            "WON",
            current_user=current_user,
            event_type="ORDER_CREATED",
            event_metadata={"order_id": str(order.id)},
            idempotency_key=f"opportunity:{opportunity.id}:order:{order.id}:won",
            record_if_unchanged=True,
        )

    db.flush()
    return order


def list_sales_quotes(db: Session, organization_id: uuid.UUID, opportunity_id: uuid.UUID | None = None) -> list[models.SalesQuote]:
    quotes = repository.list_quotes(db, organization_id)
    if opportunity_id:
        quotes = [q for q in quotes if q.opportunity_id == opportunity_id]
    for quote in quotes:
        _ensure_quote_document(db, quote, organization_id)
    return quotes


def delete_sales_quote(
    db: Session,
    quote_id: uuid.UUID,
    organization_id: uuid.UUID,
    current_user: User,
    permanent: bool = True,
):
    _validate_current_user_tenant(current_user, organization_id)
    quote = repository.get_quote_by_id_for_update(db, quote_id, organization_id)
    if not quote:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orçamento não encontrado.")

    # 1. Se for cancelamento lógico (permanent=False)
    if not permanent:
        quote_document = _ensure_quote_document(db, quote, organization_id)
        if quote.status == "CONVERTED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Uma cotação convertida não pode ser cancelada.",
            )
        if quote.status == "CANCELLED":
            return {"message": "Cotação já estava cancelada."}

        previous_status = quote.status
        for approval in quote.commercial_approvals:
            if approval.status == "PENDING":
                approval.status = "CANCELLED"
        quote.commercial_approval_status = "NOT_REQUIRED"
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
        quote.status = quote_document.current_status
        db.flush()
        return {"message": "Cotação cancelada com sucesso."}

    # 2. Se for exclusão física/permanente (permanent=True)
    if quote.status == "CONVERTED":
        active_order = db.scalar(
            select(models.SalesOrder).where(
                models.SalesOrder.sales_quote_id == quote.id,
                models.SalesOrder.organization_id == organization_id,
                models.SalesOrder.status != "CANCELLED",
            )
        )
        if active_order:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Não é possível excluir a cotação pois ela foi convertida no Pedido de Venda ativo #{active_order.order_number}."
                ),
            )

    # Desvincula pedidos de venda cancelados que apontavam para esta cotação
    cancelled_orders = db.scalars(
        select(models.SalesOrder).where(
            models.SalesOrder.sales_quote_id == quote.id,
            models.SalesOrder.organization_id == organization_id,
        )
    ).all()
    for o in cancelled_orders:
        o.sales_quote_id = None

    quote_number = quote.quote_number
    document_id = quote.document_id

    # Remover aprovações comerciais vinculadas
    for approval in list(quote.commercial_approvals):
        db.delete(approval)

    # Remover itens da cotação
    for item in list(quote.items):
        db.delete(item)

    # Deletar a cotação comercial
    db.delete(quote)
    db.flush()

    # Tratar remoção ou término no módulo de documentos
    if document_id:
        from controlb.modules.documents.models import BusinessDocument

        doc = db.get(BusinessDocument, document_id)
        if doc:
            db.delete(doc)

    db.flush()
    return {"message": f"Cotação #{quote_number} excluída com sucesso.", "deleted": True}


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

    customer, opportunity = _validate_commercial_references(
        db,
        organization_id,
        customer_id=payload.customer_id,
        opportunity_id=payload.opportunity_id,
        product_ids=[item.product_id for item in payload.items],
    )
    commercial_settings = get_commercial_settings(db, organization_id)

    order_id = uuid.uuid4()
    order_document = _create_order_document(
        db,
        organization_id=organization_id,
        order_id=order_id,
        customer_name=payload.customer_name,
        current_user=current_user,
    )
    order = models.SalesOrder(
        id=order_id,
        organization_id=organization_id,
        document_id=order_document.id,
        order_number=order_document.document_number,
        customer_id=payload.customer_id,
        sales_quote_id=None,
        opportunity_id=payload.opportunity_id,
        customer_name=payload.customer_name.strip(),
        customer_document=(
            customer.document
            if customer
            else payload.customer_document.strip() if payload.customer_document else None
        ),
        payment_terms=payload.payment_terms or commercial_settings.default_payment_terms,
        delivery_status="PENDING",
        billing_status="PENDING",
        status="CONFIRMED",
        notes=payload.notes,
        created_by_id=current_user.id
    )

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
    _validate_discount_limit(commercial_settings, total_gross, total_disc)

    saved_order = repository.create_order(db, order)
    order_document.issued_at = saved_order.created_at
    documents_service.update_document(
        db,
        order_document.id,
        organization_id,
        document_schemas.DocumentUpdate(
            title=f"Pedido de Venda {order_document.document_number} - {saved_order.customer_name}",
        ),
        current_user=current_user,
    )
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
    _apply_commercial_approval_rules(
        db,
        organization_id,
        saved_order,
        current_user.id,
    )
    _apply_credit_analysis_to_order(
        db,
        organization_id,
        saved_order,
        current_user,
        request_reason="Solicitação automática na emissão do pedido.",
    )
    if opportunity:
        from controlb.modules.crm import service as crm_service

        crm_service.transition_opportunity_stage(
            db,
            opportunity,
            organization_id,
            "WON",
            current_user=current_user,
            event_type="ORDER_CREATED",
            event_metadata={"order_id": str(saved_order.id)},
            idempotency_key=(
                f"opportunity:{opportunity.id}:order:{saved_order.id}:won"
            ),
            record_if_unchanged=True,
        )
    db.flush()
    return saved_order


def get_sales_order(db: Session, order_id: uuid.UUID, organization_id: uuid.UUID) -> models.SalesOrder:
    order = repository.get_order_by_id(db, order_id, organization_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido de venda não encontrado.")
    _ensure_order_document(db, order, organization_id)
    return order


def list_sales_orders(db: Session, organization_id: uuid.UUID) -> list[models.SalesOrder]:
    orders = repository.list_orders(db, organization_id)
    for order in orders:
        _ensure_order_document(db, order, organization_id)
    return orders


def list_credit_approval_requests(
    db: Session,
    organization_id: uuid.UUID,
    approval_status: str | None = None,
) -> list[models.CreditApprovalRequest]:
    normalized_status = approval_status.strip().upper() if approval_status else None
    if normalized_status and normalized_status not in {
        "PENDING", "APPROVED", "REJECTED", "CANCELLED"
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status de aprovação de crédito inválido.",
        )
    return repository.list_credit_approval_requests(
        db,
        organization_id,
        normalized_status,
    )


def list_commercial_approval_requests(
    db: Session,
    organization_id: uuid.UUID,
    approval_status: str | None = None,
    approval_type: str | None = None,
) -> list[models.CommercialApprovalRequest]:
    normalized_status = approval_status.strip().upper() if approval_status else None
    normalized_type = approval_type.strip().upper() if approval_type else None
    if normalized_status and normalized_status not in {
        "PENDING", "APPROVED", "REJECTED", "CANCELLED"
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status de aprovação comercial inválido.",
        )
    if normalized_type and normalized_type not in {
        "DISCOUNT", "MARGIN", "PAYMENT_TERM"
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipo de aprovação comercial inválido.",
        )
    return repository.list_commercial_approval_requests(
        db,
        organization_id,
        normalized_status,
        normalized_type,
    )


def decide_commercial_approval(
    db: Session,
    approval_id: uuid.UUID,
    organization_id: uuid.UUID,
    current_user: User,
    payload: schemas.CreditApprovalDecision,
) -> models.CommercialApprovalRequest:
    _validate_current_user_tenant(current_user, organization_id)
    approval = repository.get_commercial_approval_by_id_for_update(
        db, approval_id, organization_id
    )
    if not approval:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitação de aprovação comercial não encontrada.",
        )
    if approval.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta solicitação comercial já foi decidida.",
        )

    document = approval.quote or approval.order
    if not document or document.status in {"CANCELLED", "CONVERTED"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O documento não pode mais receber uma decisão comercial.",
        )

    approval.status = "APPROVED" if payload.approved else "REJECTED"
    approval.decision_reason = payload.reason.strip()
    approval.decided_by_id = current_user.id
    approval.decided_at = utcnow()

    is_quote = approval.sales_quote_id is not None
    approvals = repository.list_commercial_approvals_for_document(
        db,
        organization_id,
        quote_id=approval.sales_quote_id if is_quote else None,
        order_id=approval.sales_order_id if not is_quote else None,
    )
    _recalculate_commercial_approval_status(document, approvals)
    business_document = (
        _ensure_quote_document(db, document, organization_id)
        if is_quote
        else _ensure_order_document(db, document, organization_id)
    )
    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=business_document,
        event_type=(
            "COMMERCIAL_APPROVED" if payload.approved else "COMMERCIAL_REJECTED"
        ),
        previous_status=None,
        new_status=None,
        created_by_id=current_user.id,
        event_metadata={
            "approval_id": str(approval.id),
            "approval_type": approval.approval_type,
            "metric_value": str(approval.metric_value),
            "threshold_value": str(approval.threshold_value),
            "reason": approval.decision_reason,
        },
        idempotency_key=(
            f"sales-commercial-approval:{approval.id}:decision:{approval.status}"
        ),
    )
    db.flush()
    return approval


def request_credit_approval(
    db: Session,
    order_id: uuid.UUID,
    organization_id: uuid.UUID,
    current_user: User,
    reason: str,
) -> models.CreditApprovalRequest:
    _validate_current_user_tenant(current_user, organization_id)
    order = repository.get_order_by_id_for_update(db, order_id, organization_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pedido de venda não encontrado.",
        )
    order_document = _ensure_order_document(db, order, organization_id)
    if order.status == "CANCELLED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Um pedido cancelado não pode solicitar crédito.",
        )
    if not order.customer_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O pedido precisa estar vinculado a um cliente cadastrado.",
        )

    customer = repository.get_customer_by_id_for_update(
        db,
        order.customer_id,
        organization_id,
    )
    if not customer:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    analysis = get_customer_credit_analysis(
        db,
        organization_id,
        customer.id,
        proposed_order_amount=Decimal(order.net_amount),
        exclude_order_id=order.id,
    )
    if analysis.credit_limit <= 0 or not analysis.requires_approval:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O pedido não excede o limite atual e não requer liberação.",
        )

    approval = repository.get_credit_approval_by_order_id(
        db,
        order.id,
        organization_id,
    )
    if approval and approval.status == "PENDING":
        approval.request_reason = reason.strip()
        approval.requested_by_id = current_user.id
    elif approval:
        approval.status = "PENDING"
        approval.request_reason = reason.strip()
        approval.decision_reason = None
        approval.decided_by_id = None
        approval.decided_at = None
    else:
        approval = models.CreditApprovalRequest(
            organization_id=organization_id,
            sales_order_id=order.id,
            customer_id=customer.id,
            requested_by_id=current_user.id,
            request_reason=reason.strip(),
        )

    approval.credit_limit = analysis.credit_limit
    approval.exposure_before_order = analysis.utilized_amount
    approval.order_amount = Decimal(order.net_amount)
    approval.excess_amount = analysis.excess_amount
    order.credit_status = "PENDING"
    order.credit_limit_snapshot = analysis.credit_limit
    order.credit_exposure_snapshot = analysis.utilized_amount
    order.credit_excess_amount = analysis.excess_amount
    repository.save_credit_approval_request(db, approval)

    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=order_document,
        event_type="CREDIT_APPROVAL_REQUESTED",
        previous_status=None,
        new_status=None,
        created_by_id=current_user.id,
        event_metadata={
            "approval_id": str(approval.id),
            "excess_amount": str(approval.excess_amount),
            "reason": approval.request_reason,
        },
        idempotency_key=f"sales-order:{order.id}:credit-request:{uuid.uuid4().hex}",
    )
    db.flush()
    return approval


def decide_credit_approval(
    db: Session,
    approval_id: uuid.UUID,
    organization_id: uuid.UUID,
    current_user: User,
    payload: schemas.CreditApprovalDecision,
) -> models.CreditApprovalRequest:
    _validate_current_user_tenant(current_user, organization_id)
    approval = repository.get_credit_approval_by_id_for_update(
        db,
        approval_id,
        organization_id,
    )
    if not approval:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitação de crédito não encontrada.",
        )
    if approval.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta solicitação de crédito já foi decidida.",
        )

    order = approval.order
    order_document = _ensure_order_document(db, order, organization_id)
    if order.status == "CANCELLED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O pedido foi cancelado e não pode receber decisão de crédito.",
        )

    previous_status = approval.status
    approval.status = "APPROVED" if payload.approved else "REJECTED"
    approval.decision_reason = payload.reason.strip()
    approval.decided_by_id = current_user.id
    approval.decided_at = utcnow()
    order.credit_status = approval.status

    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=order_document,
        event_type=("CREDIT_APPROVED" if payload.approved else "CREDIT_REJECTED"),
        previous_status=None,
        new_status=None,
        created_by_id=current_user.id,
        event_metadata={
            "approval_id": str(approval.id),
            "previous_credit_status": previous_status,
            "new_credit_status": approval.status,
            "excess_amount": str(approval.excess_amount),
            "reason": approval.decision_reason,
        },
        idempotency_key=f"sales-order:{order.id}:credit-decision:{approval.status}",
    )
    db.flush()
    return approval


def delete_sales_order(
    db: Session,
    order_id: uuid.UUID,
    organization_id: uuid.UUID,
    current_user: User,
    reason: str | None = None,
    permanent: bool = False,
):
    _validate_current_user_tenant(current_user, organization_id)
    order = repository.get_order_by_id_for_update(db, order_id, organization_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido de venda não encontrado.")
    order_document = _ensure_order_document(db, order, organization_id)
    from controlb.modules.billing.models import Invoice
    from controlb.modules.inventory import service as inventory_service
    from controlb.modules.inventory.models import InventoryDelivery, StockReservation

    # 1. Validação de Faturas Ativas ou Status Faturado
    if order.billing_status in {"PARTIALLY_INVOICED", "INVOICED"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"O pedido #{order.order_number} possui faturamento iniciado ou concluído ({order.billing_status}). "
                "Não é possível cancelá-lo ou excluí-lo diretamente."
            ),
        )

    active_invoice = db.scalar(
        select(Invoice).where(
            Invoice.sales_order_id == order.id,
            Invoice.organization_id == organization_id,
            Invoice.status != "CANCELLED",
        )
    )
    if active_invoice:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Não é possível cancelar ou excluir o pedido #{order.order_number} pois existe a Fatura Ativa #{active_invoice.invoice_number}. "
                "Cancele a fatura primeiro no módulo de Faturamento."
            ),
        )

    # 2. Validação de Expedição e Conclusão
    if order.delivery_status in {"DISPATCHED", "DELIVERED"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"O pedido #{order.order_number} possui mercadorias já despachadas ou entregues "
                f"(status de entrega: {order.delivery_status}). Utilize o fluxo de devoluções em Pós-Venda."
            ),
        )
    if order.status == "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"O pedido #{order.order_number} já foi concluído e não pode ser cancelado.",
        )

    # 3. EXCLUSÃO DEFINITIVA (se permanent=True)
    if permanent:
        # Liberar quaisquer reservas de estoque
        inventory_service.release_sales_order_reservation(
            db,
            organization_id,
            current_user.id,
            order.id,
            locked_order=order,
            delivery_status_after="CANCELLED",
        )

        # Remover entregas associadas (não despachadas)
        deliveries = db.scalars(
            select(InventoryDelivery).where(
                InventoryDelivery.sales_order_id == order.id,
                InventoryDelivery.organization_id == organization_id,
            )
        ).all()
        for d in deliveries:
            db.delete(d)

        # Remover reservas associadas
        reservations = db.scalars(
            select(StockReservation).where(
                StockReservation.sales_order_id == order.id,
                StockReservation.organization_id == organization_id,
            )
        ).all()
        for r in reservations:
            db.delete(r)

        # Desvincular faturas canceladas se houver
        cancelled_invoices = db.scalars(
            select(Invoice).where(
                Invoice.sales_order_id == order.id,
                Invoice.organization_id == organization_id,
            )
        ).all()
        for inv in cancelled_invoices:
            inv.sales_order_id = None

        order_number = order.order_number
        document_id = order.document_id

        # Remover itens e aprovações
        for item in list(order.items):
            db.delete(item)
        if order.credit_approval:
            db.delete(order.credit_approval)
        for approval in list(order.commercial_approvals):
            db.delete(approval)

        # Deletar o SalesOrder
        db.delete(order)
        db.flush()

        # Deletar o BusinessDocument correspondente
        if document_id:
            from controlb.modules.documents.models import BusinessDocument

            doc = db.get(BusinessDocument, document_id)
            if doc:
                db.delete(doc)

        db.flush()
        return {"message": f"Pedido #{order_number} excluído definitivamente com sucesso.", "deleted": True}

    # 4. CANCELAMENTO LÓGICO SEGURO E IDEMPOTENTE
    # Reexecutar o fluxo também reconcilia estados derivados (entrega, reserva,
    # faturamento e aprovações) que possam ter ficado inconsistentes.
    previous_status = order.status
    inventory_service.release_sales_order_reservation(
        db,
        organization_id,
        current_user.id,
        order.id,
        locked_order=order,
        delivery_status_after="CANCELLED",
    )
    order.delivery_status = "CANCELLED"
    order.billing_status = "CANCELLED"
    if order.credit_approval and order.credit_approval.status == "PENDING":
        order.credit_approval.status = "CANCELLED"
    for approval in order.commercial_approvals:
        if approval.status == "PENDING":
            approval.status = "CANCELLED"
    order.commercial_approval_status = "NOT_REQUIRED"
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
    order.status = order_document.current_status
    db.flush()
    return {"message": f"Pedido #{order.order_number} cancelado com sucesso."}


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
    order_document = _ensure_order_document(db, order, organization_id)

    previous_status = order.status
    next_status = order.status
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
            order.customer_document = customer.document
            updated_fields.append("customer_id")
            updated_fields.append("customer_document")

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

    if "payment_terms" in updated_fields:
        _apply_commercial_approval_rules(
            db, organization_id, order, current_user.id
        )

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
        if next_status != norm_status:
            if norm_status == "COMPLETED":
                _assert_credit_released(order)
                _assert_commercial_approval_released(order)
            next_status = norm_status
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
            if norm_deliv in {"RESERVED", "DISPATCHED", "DELIVERED"}:
                _assert_credit_released(order)
                _assert_commercial_approval_released(order)
            if norm_deliv == "RESERVED":
                from controlb.modules.inventory import service as inventory_service

                inventory_service.reserve_sales_order(
                    db, organization_id, current_user.id, order.id
                )
            elif norm_deliv == "DISPATCHED":
                from controlb.modules.inventory import service as inventory_service

                inventory_service.dispatch_sales_order(
                    db,
                    organization_id,
                    current_user,
                    order.id,
                    locked_order=order,
                )
            elif norm_deliv == "DELIVERED":
                from controlb.modules.inventory import service as inventory_service

                inventory_service.confirm_sales_order_delivery(
                    db,
                    organization_id,
                    current_user,
                    order.id,
                    locked_order=order,
                )
            else:
                if order.delivery_status == "RESERVED":
                    from controlb.modules.inventory import service as inventory_service

                    inventory_service.release_sales_order_reservation(
                        db,
                        organization_id,
                        current_user.id,
                        order.id,
                        locked_order=order,
                        delivery_status_after="PENDING",
                    )
                elif order.delivery_status != "PENDING":
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Uma expedição iniciada não pode retornar ao status pendente.",
                    )
            updated_fields.append("delivery_status")

    if payload.notes is not None and order.notes != payload.notes:
        order.notes = payload.notes
        updated_fields.append("notes")

    if not updated_fields:
        db.flush()
        return order

    status_changed = (
        previous_status != next_status
        or previous_delivery_status != order.delivery_status
    )

    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=order_document,
        event_type="STATUS_CHANGED" if status_changed else "UPDATED",
        previous_status=previous_status,
        new_status=next_status if status_changed else None,
        created_by_id=current_user.id,
        event_metadata={
            "updated_fields": updated_fields,
            "delivery_status": order.delivery_status,
            "billing_status": order.billing_status,
        },
        idempotency_key=(
            f"sales-order:{order.id}:update:{next_status}:"
            f"{order.delivery_status}:{uuid.uuid4().hex[:6]}"
        ),
    )
    order.status = order_document.current_status
    if "customer_name" in updated_fields:
        documents_service.update_document(
            db,
            order_document.id,
            organization_id,
            document_schemas.DocumentUpdate(
                title=(
                    f"Pedido de Venda {order_document.document_number} - "
                    f"{order.customer_name}"
                ),
            ),
            current_user=current_user,
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
    order_document = _ensure_order_document(db, order, organization_id)

    if order.billing_status == "INVOICED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este pedido de venda já foi faturado.",
        )
    if order.billing_status == "REQUESTED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este pedido já possui uma solicitação de faturamento pendente.",
        )
    if order.status == "CANCELLED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Não é possível faturar um pedido cancelado.",
        )

    _assert_credit_released(order)
    _assert_commercial_approval_released(order)

    previous_billing_status = order.billing_status
    chain = documents_service.get_document_chain(
        db,
        organization_id=organization_id,
        document_type="SALES_ORDER",
        native_id=order.id,
    )
    active_invoice_documents = [
        documents_service.get_document(db, node.id, organization_id)
        for node in chain.documents
        if node.document_type == "INVOICE" and node.current_status != "CANCELLED"
    ]
    previously_invoiced_amount = sum(
        (
            Decimal(str(document.payload.get("total_amount", "0")))
            for document in active_invoice_documents
        ),
        Decimal("0.00"),
    )
    previously_invoiced_by_item: dict[str, Decimal] = {}
    for document in active_invoice_documents:
        for item in document.payload.get("items", []):
            item_id = str(item.get("sales_order_item_id", ""))
            if item_id:
                previously_invoiced_by_item[item_id] = (
                    previously_invoiced_by_item.get(item_id, Decimal("0"))
                    + Decimal(str(item.get("quantity", "0")))
                )
    requested_amount = max(
        Decimal("0.00"), order.net_amount - previously_invoiced_amount
    )
    if requested_amount <= 0:
        order.billing_status = "INVOICED"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O pedido não possui saldo pendente de faturamento.",
        )
    billing_request_id = uuid.uuid4()
    products = {
        product.id: product
        for product in db.query(Product).filter(
            Product.organization_id == organization_id,
            Product.id.in_([item.product_id for item in order.items]),
        ).all()
    }
    billing_request = documents_service.create_document(
        db,
        organization_id=organization_id,
        payload=document_schemas.DocumentCreate(
            category="billing.request",
            document_type="BILLING_REQUEST",
            native_id=billing_request_id,
            title="Solicitação de Faturamento",
            current_status="REQUESTED",
            description=(
                f"Solicitação de faturamento do Pedido {order.order_number}"
            ),
            origin_module="SALES",
            responsible_id=current_user.id,
            payload={
                "sales_order_id": str(order.id),
                "order_number": order.order_number,
                "customer_name": order.customer_name,
                "customer_document": order.customer_document,
                "amount": str(requested_amount),
                "previously_invoiced_amount": str(previously_invoiced_amount),
                "gross_amount": str(order.total_amount),
                "discount_amount": str(order.discount_amount),
                "payment_terms": order.payment_terms,
                "delivery_status": order.delivery_status,
                "items": [
                    {
                        "sales_order_item_id": str(item.id),
                        "product_id": str(item.product_id),
                        "product_name": (
                            products[item.product_id].name
                            if item.product_id in products
                            else f"Produto {item.product_id}"
                        ),
                        "product_sku": (
                            products[item.product_id].sku
                            if item.product_id in products
                            else None
                        ),
                        "quantity": str(item.quantity),
                        "invoiced_quantity": str(
                            previously_invoiced_by_item.get(str(item.id), Decimal("0"))
                        ),
                        "remaining_quantity": str(
                            max(
                                Decimal("0"),
                                Decimal(str(item.quantity))
                                - previously_invoiced_by_item.get(str(item.id), Decimal("0")),
                            )
                        ),
                        "unit_price": str(item.unit_price),
                        "discount_amount": str(item.discount_amount),
                        "total_price": str(item.total_price),
                    }
                    for item in order.items
                ],
            },
            issued_at=utcnow(),
        ),
        current_user=current_user,
    )
    billing_request.title = (
        f"Solicitação de Faturamento {billing_request.document_number}"
    )
    documents_service.relate_documents(
        db,
        organization_id=organization_id,
        parent_document=order_document,
        child_document=billing_request,
        relation_type="GENERATED",
        created_by_id=current_user.id,
    )

    order.billing_status = "REQUESTED"
    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=order_document,
        event_type="BILLING_REQUESTED",
        previous_status=order.status,
        new_status=order.status,
        created_by_id=current_user.id,
        event_metadata={
            "billing_request_id": str(billing_request.id),
            "requested_amount": str(requested_amount),
            "previous_billing_status": previous_billing_status,
        },
        idempotency_key=f"sales-order:{order.id}:billing-request:{billing_request.id}",
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

        # 3. Registro de Auditoria / Kardex (StockMovement) com documento canônico
        from controlb.modules.inventory.service import record_stock_movement
        record_stock_movement(
            db,
            organization_id,
            product_id=product.id,
            movement_type="out_sale",
            quantity=it.quantity,
            unit_cost=product.cost_price or product.reference_price or Decimal("0.00"),
            balance_after=product.current_stock,
            reference_doc=f"PDV-{str(sale.id)[:8].upper()}",
            notes=f"Venda Balcão PDV - Cliente: {sale.customer_name} ({sale.payment_method})",
            created_by_id=current_user.id,
            current_user=current_user,
        )

    sale.total_amount = total_gross
    _validate_discount_limit(
        get_commercial_settings(db, organization_id),
        total_gross,
        payload.discount_amount,
    )
    sale.net_amount = max(Decimal("0.00"), total_gross - payload.discount_amount)

    # Registro de documento canônico para a venda PDV
    pos_doc = documents_service.create_document(
        db,
        organization_id=organization_id,
        payload=document_schemas.DocumentCreate(
            category="sales.pos_sale",
            document_type="POS_SALE",
            native_id=sale.id,
            title=f"Venda PDV - {sale.customer_name}",
            current_status="COMPLETED",
            description=f"Venda Balcão PDV - {sale.customer_name} ({sale.payment_method}) - R$ {sale.net_amount}",
            origin_module="SALES",
            responsible_id=current_user.id,
        ),
        current_user=current_user,
    )
    sale.document_id = pos_doc.id

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
    user = db.query(User).filter(
        User.id == payload.user_id,
        User.organization_id == organization_id,
        User.is_active == True,
        User.is_seller == True,
    ).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O vendedor deve ser um usuário ativo da organização atual.",
        )
    seller_name = user.full_name

    commercial_settings = get_commercial_settings(db, organization_id)
    commission_percent = (
        payload.commission_percent
        if "commission_percent" in payload.model_fields_set
        else commercial_settings.default_commission_percent
    )

    goal = models.SalesGoal(
        organization_id=organization_id,
        user_id=payload.user_id,
        seller_name=seller_name,
        month=payload.month,
        year=payload.year,
        target_amount=payload.target_amount,
        commission_percent=commission_percent
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
                from controlb.modules.inventory.service import record_stock_movement
                record_stock_movement(
                    db,
                    organization_id,
                    product_id=product.id,
                    movement_type="in_return",
                    quantity=it.quantity,
                    unit_cost=product.cost_price or product.reference_price or Decimal("0.00"),
                    balance_after=product.current_stock,
                    reference_doc=f"DEV-{str(sales_return.id)[:8].upper()}",
                    notes=f"Devolução/Troca Pós-Venda - Cliente: {payload.customer_name} ({payload.reason})",
                    created_by_id=current_user.id,
                    current_user=current_user,
                )

    sales_return.total_amount = tot

    # Registro de documento canônico para a devolução
    return_doc = documents_service.create_document(
        db,
        organization_id=organization_id,
        payload=document_schemas.DocumentCreate(
            category="sales.return",
            document_type="SALES_RETURN",
            native_id=sales_return.id,
            title=f"Devolução/Troca - {payload.customer_name}",
            current_status="COMPLETED",
            description=f"{payload.return_type} - {payload.customer_name} ({payload.reason}) - R$ {tot}",
            origin_module="SALES",
            responsible_id=current_user.id,
        ),
        current_user=current_user,
    )
    sales_return.document_id = return_doc.id

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
    from controlb.modules.identity.models import User

    # Pertencer a uma equipe comercial concede escopo, mas nao transforma o lider em vendedor.
    users = db.query(User).filter(
        User.organization_id == organization_id,
        User.is_active == True,
        User.is_seller == True,
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
