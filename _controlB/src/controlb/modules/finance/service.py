"""
modules/finance/service.py - Regras de Negócio e Serviços do Módulo Financeiro e Faturamento
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from controlb.logger import logger
from controlb.modules.identity.models import User
from controlb.modules.purchasing import models as purchasing_models
from controlb.modules.finance import models, repository, schemas


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ==============================================================================
# 1. CATEGORIAS FINANCEIRAS & CONTAS BANCÁRIAS
# ==============================================================================

def create_financial_category(db: Session, organization_id: uuid.UUID, payload: schemas.FinancialCategoryCreate) -> models.FinancialCategory:
    cat = models.FinancialCategory(
        organization_id=organization_id,
        name=payload.name.strip(),
        code=payload.code.strip() if payload.code else None,
        category_type=payload.category_type.upper(),
        description=payload.description,
        is_active=payload.is_active
    )
    return repository.create_category(db, cat)


def list_financial_categories(db: Session, organization_id: uuid.UUID, category_type: str | None = None) -> list[models.FinancialCategory]:
    return repository.list_categories(db, organization_id, category_type)


def update_financial_category(
    db: Session,
    organization_id: uuid.UUID,
    category_id: uuid.UUID,
    payload: schemas.FinancialCategoryUpdate,
) -> models.FinancialCategory:
    category = repository.get_category_by_id(db, category_id, organization_id)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoria financeira não encontrada.")
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is not None:
        changes["name"] = changes["name"].strip()
    if "code" in changes and changes["code"] is not None:
        changes["code"] = changes["code"].strip() or None
    if "category_type" in changes and changes["category_type"] is not None:
        changes["category_type"] = changes["category_type"].strip().upper()
        if changes["category_type"] not in {"EXPENSE", "REVENUE"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tipo de categoria inválido.")
    for field, value in changes.items():
        setattr(category, field, value)
    return repository.update_category(db, category)


def create_bank_account(db: Session, organization_id: uuid.UUID, payload: schemas.BankAccountCreate) -> models.BankAccount:
    account = models.BankAccount(
        organization_id=organization_id,
        bank_name=payload.bank_name.strip(),
        bank_code=payload.bank_code.strip() if payload.bank_code else None,
        agency=payload.agency.strip() if payload.agency else None,
        account_number=payload.account_number.strip() if payload.account_number else None,
        account_type=payload.account_type,
        opening_balance=payload.opening_balance,
        current_balance=payload.opening_balance,
        is_active=payload.is_active
    )
    return repository.create_bank_account(db, account)


def list_bank_accounts(db: Session, organization_id: uuid.UUID) -> list[models.BankAccount]:
    return repository.list_bank_accounts(db, organization_id)


def update_bank_account(
    db: Session,
    organization_id: uuid.UUID,
    account_id: uuid.UUID,
    payload: schemas.BankAccountUpdate,
) -> models.BankAccount:
    account = repository.get_bank_account_by_id(db, account_id, organization_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta bancária não encontrada.")
    changes = payload.model_dump(exclude_unset=True)
    if "current_balance" in changes and changes["current_balance"] != account.current_balance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O saldo atual não pode ser editado diretamente. Registre um ajuste bancário.",
        )
    for field in ("bank_name", "bank_code", "agency", "account_number"):
        if field in changes and changes[field] is not None:
            changes[field] = changes[field].strip() or None
    if changes.get("account_type"):
        changes["account_type"] = changes["account_type"].strip().upper()
    for field, value in changes.items():
        setattr(account, field, value)
    return repository.update_bank_account(db, account)


# ==============================================================================
# 2. DOCUMENTOS FISCAIS (FiscalDocument)
# ==============================================================================

def get_fiscal_document_header(
    db: Session,
    fiscal_document: models.FiscalDocument,
    organization_id: uuid.UUID,
):
    from controlb.modules.documents import service as documents_service

    document = documents_service.get_document(
        db, fiscal_document.document_id, organization_id
    )
    if (
        document.document_type != "FISCAL_DOCUMENT"
        or document.native_id != fiscal_document.id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O cabeçalho documental do documento fiscal é inconsistente.",
        )
    fiscal_document.status = document.current_status.lower()
    return document


def persist_fiscal_document(
    db: Session,
    organization_id: uuid.UUID,
    current_user: User,
    payload: schemas.FiscalDocumentCreate,
    *,
    source_document=None,
) -> models.FiscalDocument:
    """Cria a identidade transversal e a extensão fiscal na mesma transação."""
    from controlb.modules.documents import schemas as document_schemas
    from controlb.modules.documents import service as documents_service

    purchase_order = None
    if payload.purchase_order_id:
        purchase_order = db.scalar(
            select(purchasing_models.PurchaseOrder).where(
                purchasing_models.PurchaseOrder.id == payload.purchase_order_id,
                purchasing_models.PurchaseOrder.organization_id == organization_id,
            )
        )
        if not purchase_order:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A Ordem de Compra vinculada ao documento fiscal é inválida.",
            )

    if payload.supplier_id:
        supplier = db.scalar(
            select(purchasing_models.Supplier).where(
                purchasing_models.Supplier.id == payload.supplier_id,
                purchasing_models.Supplier.organization_id == organization_id,
            )
        )
        if not supplier:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O fornecedor vinculado ao documento fiscal é inválido.",
            )

    fiscal_id = uuid.uuid4()
    normalized_status = payload.status.strip().upper()
    header = documents_service.create_document(
        db,
        organization_id=organization_id,
        payload=document_schemas.DocumentCreate(
            category="finance.fiscal_document",
            document_type="FISCAL_DOCUMENT",
            native_id=fiscal_id,
            title=f"Documento Fiscal {payload.document_number.strip()}",
            current_status=normalized_status,
            description=payload.notes,
            origin_module="FINANCE",
            responsible_id=current_user.id,
            payload={
                "direction": payload.direction.upper(),
                "fiscal_type": payload.document_type.upper(),
                "external_number": payload.document_number.strip(),
                "series": payload.series,
                "access_key": payload.access_key,
                "purchase_order_id": (
                    str(payload.purchase_order_id) if payload.purchase_order_id else None
                ),
                "supplier_id": str(payload.supplier_id) if payload.supplier_id else None,
                "total_amount": str(payload.total_amount),
            },
            issued_at=datetime.combine(
                payload.issue_date, datetime.min.time(), tzinfo=timezone.utc
            ),
        ),
        current_user=current_user,
    )
    header.title = (
        f"Documento Fiscal {header.document_number} • {payload.document_number.strip()}"
    )

    doc = models.FiscalDocument(
        id=fiscal_id,
        organization_id=organization_id,
        document_id=header.id,
        direction=payload.direction.upper(),
        document_type=payload.document_type.upper(),
        document_number=payload.document_number.strip(),
        series=payload.series.strip() if payload.series else None,
        access_key=payload.access_key.strip() if payload.access_key else None,
        issuer_name=payload.issuer_name.strip(),
        issuer_cnpj_cpf=payload.issuer_cnpj_cpf.strip() if payload.issuer_cnpj_cpf else None,
        recipient_name=payload.recipient_name.strip() if payload.recipient_name else None,
        recipient_cnpj_cpf=payload.recipient_cnpj_cpf.strip() if payload.recipient_cnpj_cpf else None,
        issue_date=payload.issue_date,
        total_amount=payload.total_amount,
        tax_amount=payload.tax_amount,
        purchase_order_id=payload.purchase_order_id,
        supplier_id=payload.supplier_id,
        file_attachment=payload.file_attachment,
        notes=payload.notes,
        status=normalized_status.lower(),
    )
    saved = repository.create_fiscal_document(db, doc)

    if source_document is None and purchase_order and purchase_order.document_id:
        from controlb.modules.purchasing.service import get_purchase_order_document

        source_document = get_purchase_order_document(db, purchase_order, organization_id)
    if source_document is not None:
        documents_service.relate_documents(
            db,
            organization_id=organization_id,
            parent_document=source_document,
            child_document=header,
            relation_type="DOCUMENTED_BY",
            created_by_id=current_user.id,
            relation_metadata={"external_number": payload.document_number.strip()},
        )
    db.flush()
    return saved


def create_fiscal_document(
    db: Session,
    organization_id: uuid.UUID,
    current_user: User,
    payload: schemas.FiscalDocumentCreate,
) -> models.FiscalDocument:
    return persist_fiscal_document(db, organization_id, current_user, payload)


def list_fiscal_documents(
    db: Session,
    organization_id: uuid.UUID,
    direction: str | None = None,
    document_type: str | None = None
) -> list[models.FiscalDocument]:
    return repository.list_fiscal_documents(db, organization_id, direction, document_type)


def update_fiscal_document(
    db: Session,
    organization_id: uuid.UUID,
    fiscal_document_id: uuid.UUID,
    current_user: User,
    payload: schemas.FiscalDocumentUpdate,
) -> models.FiscalDocument:
    from controlb.modules.documents import schemas as document_schemas
    from controlb.modules.documents import service as documents_service

    fiscal = repository.get_fiscal_document_by_id(db, fiscal_document_id, organization_id)
    if not fiscal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento fiscal não encontrado.")
    header = get_fiscal_document_header(db, fiscal, organization_id)
    current_status = fiscal.status.strip().upper()
    changes = payload.model_dump(exclude_unset=True)
    if current_status == "CANCELLED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Documento fiscal cancelado não pode ser editado.")
    if current_status == "AUTHORIZED":
        immutable = set(changes) - {"notes", "file_attachment", "status"}
        if immutable:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Documento fiscal autorizado permite alterar apenas observações, anexo ou cancelamento.",
            )
    if changes.get("status"):
        normalized_status = changes["status"].strip().upper()
        if normalized_status not in {"DRAFT", "AUTHORIZED", "CANCELLED"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Status fiscal inválido.")
        if current_status == "AUTHORIZED" and normalized_status != "CANCELLED":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Documento autorizado somente pode ser cancelado.")
        changes["status"] = normalized_status.lower()
    for field in ("direction", "document_type"):
        if changes.get(field):
            changes[field] = changes[field].strip().upper()
    for field in ("document_number", "series", "access_key", "issuer_name", "issuer_cnpj_cpf", "recipient_name", "recipient_cnpj_cpf"):
        if field in changes and changes[field] is not None:
            changes[field] = changes[field].strip() or None
    for field, value in changes.items():
        setattr(fiscal, field, value)

    document_payload = dict(header.payload or {})
    document_payload.update({
        "direction": fiscal.direction,
        "fiscal_type": fiscal.document_type,
        "external_number": fiscal.document_number,
        "series": fiscal.series,
        "access_key": fiscal.access_key,
        "total_amount": str(fiscal.total_amount),
    })
    documents_service.update_document(
        db,
        header.id,
        organization_id,
        document_schemas.DocumentUpdate(
            title=f"Documento Fiscal {header.document_number} • {fiscal.document_number}",
            current_status=fiscal.status.upper(),
            description=fiscal.notes,
            payload=document_payload,
        ),
        current_user=current_user,
    )
    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=header,
        event_type="FISCAL_DOCUMENT_UPDATED",
        created_by_id=current_user.id,
        event_metadata={"updated_fields": sorted(changes)},
    )
    return repository.update_fiscal_document(db, fiscal)


# ==============================================================================
# 3. CONTAS A PAGAR (Payable) & DESPESAS AVULSAS
# ==============================================================================

def create_payable_expense(
    db: Session,
    organization_id: uuid.UUID,
    current_user: User,
    payload: schemas.PayableCreate
) -> list[models.Payable]:
    """
    Cria uma ou mais obrigações a pagar (com suporte a parcelamento automático).
    Não depende de Ordem de Compra prévia (suporta Despesas Avulsas: Aluguel, Energia, TI, etc.).
    """
    from controlb.modules.documents import schemas as document_schemas
    from controlb.modules.documents import service as documents_service

    source_document = None
    fiscal_document = None
    purchase_order = None
    if payload.new_fiscal_document:
        fiscal_document = persist_fiscal_document(
            db, organization_id, current_user, payload.new_fiscal_document
        )
        payload.fiscal_document_id = fiscal_document.id
        source_document = get_fiscal_document_header(
            db, fiscal_document, organization_id
        )
    elif payload.fiscal_document_id:
        fiscal_document = repository.get_fiscal_document_by_id(
            db, payload.fiscal_document_id, organization_id
        )
        if not fiscal_document:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O documento fiscal vinculado à conta a pagar é inválido.",
            )
        source_document = get_fiscal_document_header(
            db, fiscal_document, organization_id
        )
    if payload.purchase_order_id:
        purchase_order = db.scalar(
            select(purchasing_models.PurchaseOrder).where(
                purchasing_models.PurchaseOrder.id == payload.purchase_order_id,
                purchasing_models.PurchaseOrder.organization_id == organization_id,
            )
        )
        if not purchase_order:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A Ordem de Compra vinculada à conta a pagar é inválida.",
            )
        if source_document is None:
            from controlb.modules.purchasing.service import get_purchase_order_document

            source_document = get_purchase_order_document(
                db, purchase_order, organization_id
            )

    obligation_type = payload.obligation_type
    if obligation_type == "OTHER" and (payload.supplier_id or purchase_order):
        obligation_type = "GOODS_SUPPLIER"

    business_origin = payload.business_origin
    if business_origin == "MANUAL":
        if purchase_order and purchase_order.replenishment_id:
            business_origin = "REPLENISHMENT"
        elif purchase_order:
            business_origin = "PURCHASE"
        elif fiscal_document:
            business_origin = "FISCAL_DOCUMENT"

    installments_count = payload.installments_count or 1
    freq_days = payload.installment_frequency_days or 30
    
    total_amount = payload.original_amount
    installment_val = (total_amount / Decimal(str(installments_count))).quantize(Decimal("0.01"))
    
    created_payables: list[models.Payable] = []

    for i in range(1, installments_count + 1):
        # Ajuste de centavos na última parcela
        if i == installments_count:
            part_amount = total_amount - (installment_val * Decimal(str(installments_count - 1)))
        else:
            part_amount = installment_val

        due_date = payload.due_date + timedelta(days=(i - 1) * freq_days)
        desc = payload.description.strip()
        if installments_count > 1:
            desc = f"{desc} (Parcela {i}/{installments_count})"

        payable_id = uuid.uuid4()
        payable_status = "APPROVED" if payload.purchase_order_id else "PENDING_APPROVAL"
        payable_document = documents_service.create_document(
            db,
            organization_id=organization_id,
            payload=document_schemas.DocumentCreate(
                category="finance.payable",
                document_type="PAYABLE",
                native_id=payable_id,
                title="Conta a Pagar",
                current_status=payable_status,
                description=desc,
                origin_module="FINANCE",
                responsible_id=current_user.id,
                payload={
                    "supplier_id": str(payload.supplier_id) if payload.supplier_id else None,
                    "purchase_order_id": (
                        str(payload.purchase_order_id) if payload.purchase_order_id else None
                    ),
                    "fiscal_document_id": (
                        str(payload.fiscal_document_id)
                        if payload.fiscal_document_id
                        else None
                    ),
                    "expense_nature": payload.expense_nature,
                    "obligation_type": obligation_type,
                    "business_origin": business_origin,
                    "installment_number": i,
                    "total_installments": installments_count,
                    "due_date": due_date.isoformat(),
                    "amount": str(part_amount),
                },
                issued_at=datetime.combine(
                    payload.issue_date, datetime.min.time(), tzinfo=timezone.utc
                ),
            ),
            current_user=current_user,
        )
        payable_document.title = f"Conta a Pagar {payable_document.document_number}"

        payable = models.Payable(
            id=payable_id,
            organization_id=organization_id,
            document_id=payable_document.id,
            payable_number=payable_document.document_number,
            supplier_id=payload.supplier_id,
            purchase_order_id=payload.purchase_order_id,
            fiscal_document_id=payload.fiscal_document_id,
            inventory_receipt_id=payload.inventory_receipt_id,
            cost_center_id=payload.cost_center_id,
            financial_category_id=payload.financial_category_id,
            description=desc,
            favored_name=payload.favored_name.strip(),
            original_amount=part_amount,
            outstanding_amount=part_amount,
            issue_date=payload.issue_date,
            due_date=due_date,
            expense_nature=payload.expense_nature.upper(),
            obligation_type=obligation_type,
            business_origin=business_origin,
            payment_method_expected=payload.payment_method_expected,
            installment_number=i,
            total_installments=installments_count,
            status=payable_status,
            notes=payload.notes,
            created_by_id=current_user.id
        )
        saved_payable = repository.create_payable(db, payable)

        if source_document is not None:
            documents_service.relate_documents(
                db,
                organization_id=organization_id,
                parent_document=source_document,
                child_document=payable_document,
                relation_type="GENERATED",
                created_by_id=current_user.id,
                relation_metadata={
                    "installment_number": i,
                    "total_installments": installments_count,
                },
            )

        # Instrumento de Pagamento (Boleto/PIX/etc) em todas as parcelas
        inst_payload = None
        if payload.instruments and len(payload.instruments) >= i:
            inst_payload = payload.instruments[i - 1]
        elif payload.instrument:
            inst_payload = payload.instrument

        if inst_payload:
            doc_num = inst_payload.document_number
            if not doc_num:
                doc_num = f"{payable_document.document_number}"
            elif installments_count > 1 and not doc_num.endswith(f"/{installments_count}"):
                doc_num = f"{doc_num}-{i}/{installments_count}"

            inst = models.PaymentInstrument(
                payable_id=saved_payable.id,
                instrument_type=inst_payload.instrument_type,
                barcode=inst_payload.barcode,
                digitable_line=inst_payload.digitable_line,
                pix_code=inst_payload.pix_code,
                document_number=doc_num,
                due_date=inst_payload.due_date if (i == 1 and inst_payload.due_date) else due_date,
                amount=part_amount,
                file_attachment=inst_payload.file_attachment,
            )
            repository.create_payment_instrument(db, inst)
            db.refresh(saved_payable)

        created_payables.append(saved_payable)

    logger.info(f"💰 [PAYABLE CREATED] {len(created_payables)} parcela(s) gerada(s) para '{payload.favored_name}': Total {total_amount} R$")
    db.flush()
    return created_payables


def get_payable_header(
    db: Session,
    payable: models.Payable,
    organization_id: uuid.UUID,
):
    from controlb.modules.documents import service as documents_service

    document = documents_service.get_document(db, payable.document_id, organization_id)
    if document.document_type != "PAYABLE" or document.native_id != payable.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O cabeçalho documental da conta a pagar é inconsistente.",
        )
    payable.payable_number = document.document_number
    payable.status = document.current_status
    return document


def transition_payable_status(
    db: Session,
    payable: models.Payable,
    organization_id: uuid.UUID,
    new_status: str,
    *,
    actor_id: uuid.UUID | None = None,
    event_type: str = "STATUS_CHANGED",
    event_metadata: dict | None = None,
    idempotency_key: str | None = None,
) -> models.Payable:
    from controlb.modules.documents import service as documents_service

    document = get_payable_header(db, payable, organization_id)
    previous_status = document.current_status
    normalized_status = new_status.strip().upper()
    payable.status = normalized_status
    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=document,
        event_type=event_type,
        previous_status=previous_status,
        new_status=normalized_status,
        created_by_id=actor_id,
        event_metadata=event_metadata,
        idempotency_key=idempotency_key,
    )
    repository.update_payable(db, payable)
    return payable


def register_payable_payment(
    db: Session,
    organization_id: uuid.UUID,
    payable_id: uuid.UUID,
    current_user: User,
    payload: schemas.PaymentCreate
) -> models.Payment:
    """
    Realiza a baixa financeira (parcial ou total) de uma conta a pagar:
    1. Valida saldo devedor.
    2. Abate do outstanding_amount.
    3. Se liquidado, altera status para PAID; se parcial, PARTIALLY_PAID.
    4. Se vinculada uma conta bancária, debita do saldo e gera BankTransaction de saída.
    """
    payable = repository.get_payable_by_id(db, payable_id, organization_id)
    if not payable:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta a pagar não encontrada.")

    if payable.status in ["PAID", "CANCELLED"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Esta conta não pode ser paga pois já está no status '{payable.status}'.")

    pay_amount = payload.amount
    discount = payload.discount_amount or Decimal("0.00")
    effective_reduction = pay_amount + discount

    if effective_reduction > payable.outstanding_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"O valor pago ({pay_amount} R$) + desconto ({discount} R$) excede o saldo devedor ({payable.outstanding_amount} R$)."
        )

    # 1. Cria o registro do pagamento
    payment = models.Payment(
        organization_id=organization_id,
        payable_id=payable.id,
        bank_account_id=payload.bank_account_id,
        amount=pay_amount,
        discount_amount=discount,
        interest_amount=payload.interest_amount or Decimal("0.00"),
        payment_date=payload.payment_date,
        payment_method=payload.payment_method,
        reference=payload.reference,
        notes=payload.notes,
        created_by_id=current_user.id
    )
    saved_payment = repository.create_payment(db, payment)

    # Anexos
    for att in payload.attachments:
        p_att = models.PaymentAttachment(
            payment_id=saved_payment.id,
            file_name=att.file_name,
            file_url=att.file_url,
            mime_type=att.mime_type,
            uploaded_by_id=current_user.id
        )
        db.add(p_att)

    # 2. Atualiza o saldo da conta a pagar
    new_outstanding = payable.outstanding_amount - effective_reduction
    payable.outstanding_amount = new_outstanding
    if new_outstanding <= Decimal("0.00"):
        payable.status = "PAID"
    else:
        payable.status = "PARTIALLY_PAID"
    
    transition_payable_status(
        db,
        payable,
        organization_id,
        payable.status,
        actor_id=current_user.id,
        event_type="PAYMENT_REGISTERED",
        event_metadata={
            "payment_id": str(saved_payment.id),
            "amount": str(pay_amount),
            "outstanding_amount": str(new_outstanding),
        },
        idempotency_key=f"payable:{payable.id}:payment:{saved_payment.id}",
    )

    # 3. Atualiza a Conta Bancária / Caixa e registra movimentação no extrato
    if payload.bank_account_id:
        bank = repository.get_bank_account_by_id(db, payload.bank_account_id, organization_id)
        if bank:
            bank.current_balance = (bank.current_balance or Decimal("0.00")) - pay_amount
            repository.update_bank_account(db, bank)

            # Gera transação no extrato
            tx = models.BankTransaction(
                organization_id=organization_id,
                bank_account_id=bank.id,
                transaction_date=payload.payment_date,
                description=f"Pagamento: {payable.description} ({payable.favored_name})",
                amount=pay_amount,
                transaction_type="DEBIT",
                document_number=payload.reference or str(payable.installment_number),
                balance_after=bank.current_balance,
                status="reconciled"
            )
            saved_tx = repository.create_bank_transaction(db, tx)

            # Auto-conciliação
            rec = models.Reconciliation(
                organization_id=organization_id,
                bank_transaction_id=saved_tx.id,
                payment_id=saved_payment.id,
                reconciled_by_id=current_user.id,
                status="reconciled",
                notes="Conciliado automaticamente no momento da baixa"
            )
            repository.create_reconciliation(db, rec)

    logger.info(f"✅ [PAYMENT REGISTERED] Baixa de {pay_amount} R$ em '{payable.description}'. Saldo restante: {payable.outstanding_amount} R$")
    return saved_payment


def list_payables(
    db: Session,
    organization_id: uuid.UUID,
    status: str | None = None,
    expense_nature: str | None = None,
    start_due_date: date | None = None,
    end_due_date: date | None = None,
    obligation_type: str | None = None,
    business_origin: str | None = None,
) -> list[models.Payable]:
    # Atualiza automaticamente para OVERDUE títulos vencidos que não foram pagos
    today = date.today()
    all_payables = repository.list_payables(
        db,
        organization_id,
        status=status,
        expense_nature=expense_nature,
        start_due_date=start_due_date,
        end_due_date=end_due_date,
        obligation_type=obligation_type,
        business_origin=business_origin,
    )
    for p in all_payables:
        if p.status in ["PENDING_APPROVAL", "APPROVED", "SCHEDULED"] and p.due_date < today and p.outstanding_amount > 0:
            transition_payable_status(
                db,
                p,
                organization_id,
                "OVERDUE",
                event_type="OVERDUE",
                idempotency_key=f"payable:{p.id}:overdue",
            )
    return all_payables


def update_payable(
    db: Session,
    organization_id: uuid.UUID,
    payable_id: uuid.UUID,
    current_user: User,
    payload: schemas.PayableUpdate,
) -> models.Payable:
    from controlb.modules.documents import schemas as document_schemas
    from controlb.modules.documents import service as documents_service

    payable = repository.get_payable_by_id(db, payable_id, organization_id)
    if not payable:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta a pagar não encontrada.")
    header = get_payable_header(db, payable, organization_id)
    if payable.status in {"PAID", "RECONCILED"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conta liquidada ou conciliada não pode ser editada.",
        )

    changes = payload.model_dump(exclude_unset=True)
    requested_status = changes.pop("status", None)
    if requested_status:
        requested_status = requested_status.strip().upper()
        editable_statuses = {"DRAFT", "PENDING_APPROVAL", "APPROVED", "SCHEDULED", "OVERDUE", "CANCELLED"}
        if requested_status not in editable_statuses:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Status da conta a pagar inválido para edição manual.")
        if payable.payments and requested_status == "CANCELLED":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Conta com pagamentos registrados não pode ser cancelada diretamente.")
    elif payable.status == "CANCELLED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conta cancelada só pode ser editada para reabertura de status.",
        )

    if "supplier_id" in changes and changes["supplier_id"] is not None:
        supplier = db.scalar(
            select(purchasing_models.Supplier).where(
                purchasing_models.Supplier.id == changes["supplier_id"],
                purchasing_models.Supplier.organization_id == organization_id,
            )
        )
        if not supplier:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Fornecedor inválido.")

    if "original_amount" in changes:
        settled_amount = payable.original_amount - payable.outstanding_amount
        if changes["original_amount"] < settled_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O novo valor não pode ser inferior ao montante já liquidado.",
            )
        payable.outstanding_amount = changes["original_amount"] - settled_amount
    for field in ("description", "favored_name"):
        if field in changes and changes[field] is not None:
            changes[field] = changes[field].strip()
    for field, value in changes.items():
        setattr(payable, field, value)
    if requested_status:
        payable.status = requested_status

    document_payload = dict(header.payload or {})
    document_payload.update({
        "supplier_id": str(payable.supplier_id) if payable.supplier_id else None,
        "expense_nature": payable.expense_nature,
        "obligation_type": payable.obligation_type,
        "business_origin": payable.business_origin,
        "due_date": payable.due_date.isoformat(),
        "amount": str(payable.original_amount),
    })
    documents_service.update_document(
        db,
        header.id,
        organization_id,
        document_schemas.DocumentUpdate(
            current_status=payable.status,
            description=payable.description,
            payload=document_payload,
        ),
        current_user=current_user,
    )
    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=header,
        event_type="PAYABLE_UPDATED",
        created_by_id=current_user.id,
        event_metadata={"updated_fields": sorted(set(changes) | ({"status"} if requested_status else set()))},
    )
    return repository.update_payable(db, payable)


# ==============================================================================
# 4. TESOURARIA & CONCILIAÇÃO BANCÁRIA
# ==============================================================================

def create_bank_transaction(
    db: Session,
    organization_id: uuid.UUID,
    payload: schemas.BankTransactionCreate
) -> models.BankTransaction:
    bank = repository.get_bank_account_by_id(db, payload.bank_account_id, organization_id)
    if not bank:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta bancária não encontrada.")

    # Atualiza o saldo bancário
    if payload.transaction_type.upper() == "CREDIT":
        bank.current_balance = (bank.current_balance or Decimal("0.00")) + payload.amount
    else:
        bank.current_balance = (bank.current_balance or Decimal("0.00")) - payload.amount
    
    repository.update_bank_account(db, bank)

    tx = models.BankTransaction(
        organization_id=organization_id,
        bank_account_id=bank.id,
        transaction_date=payload.transaction_date,
        description=payload.description.strip(),
        amount=payload.amount,
        transaction_type=payload.transaction_type.upper(),
        external_id=payload.external_id,
        document_number=payload.document_number,
        balance_after=bank.current_balance,
        status="pending"
    )
    return repository.create_bank_transaction(db, tx)


def list_bank_transactions(
    db: Session,
    organization_id: uuid.UUID,
    bank_account_id: uuid.UUID | None = None,
    status: str | None = None
) -> list[models.BankTransaction]:
    return repository.list_bank_transactions(db, organization_id, bank_account_id, status)


def update_bank_transaction(
    db: Session,
    organization_id: uuid.UUID,
    transaction_id: uuid.UUID,
    payload: schemas.BankTransactionUpdate,
) -> models.BankTransaction:
    """Edita somente lançamento manual pendente, recompondo os saldos envolvidos."""
    transaction = repository.get_bank_transaction_by_id(
        db, transaction_id, organization_id
    )
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movimentação bancária não encontrada.",
        )
    if transaction.status != "pending" or transaction.reconciliation is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Movimentação conciliada não pode ser editada. Registre um estorno.",
        )

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return transaction
    if "bank_account_id" in changes and changes["bank_account_id"] is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A conta bancária não pode ser removida.",
        )
    old_bank = repository.get_bank_account_by_id(
        db, transaction.bank_account_id, organization_id
    )
    new_bank_id = changes.get("bank_account_id", transaction.bank_account_id)
    new_bank = repository.get_bank_account_by_id(db, new_bank_id, organization_id)
    if not old_bank or not new_bank:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conta bancária inválida.",
        )

    new_type = changes.get("transaction_type", transaction.transaction_type)
    if new_type is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="O tipo da movimentação não pode ser removido.",
        )
    new_type = new_type.strip().upper()
    if new_type not in {"CREDIT", "DEBIT"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipo de movimentação inválido. Use CREDIT ou DEBIT.",
        )
    new_amount = changes.get("amount", transaction.amount)
    if new_amount is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="O valor da movimentação não pode ser removido.",
        )

    old_effect = transaction.amount if transaction.transaction_type == "CREDIT" else -transaction.amount
    new_effect = new_amount if new_type == "CREDIT" else -new_amount
    old_bank.current_balance = (old_bank.current_balance or Decimal("0.00")) - old_effect
    if new_bank.id == old_bank.id:
        new_bank.current_balance = (old_bank.current_balance or Decimal("0.00")) + new_effect
        repository.update_bank_account(db, new_bank)
    else:
        repository.update_bank_account(db, old_bank)
        new_bank.current_balance = (new_bank.current_balance or Decimal("0.00")) + new_effect
        repository.update_bank_account(db, new_bank)

    for field in ("description", "external_id", "document_number"):
        if field in changes and changes[field] is not None:
            changes[field] = changes[field].strip() or None
    changes["transaction_type"] = new_type
    changes["amount"] = new_amount
    for field, value in changes.items():
        setattr(transaction, field, value)
    transaction.balance_after = new_bank.current_balance
    return repository.update_bank_transaction(db, transaction)


def reconcile_transaction(
    db: Session,
    organization_id: uuid.UUID,
    current_user: User,
    payload: schemas.ReconciliationCreate
) -> models.Reconciliation:
    tx = repository.get_bank_transaction_by_id(db, payload.bank_transaction_id, organization_id)
    if not tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transação bancária não encontrada.")

    if not payload.payment_id and not payload.receipt_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Informe um Pagamento ou Recebimento para conciliar.")

    rec = models.Reconciliation(
        organization_id=organization_id,
        bank_transaction_id=tx.id,
        payment_id=payload.payment_id,
        receipt_id=payload.receipt_id,
        reconciled_by_id=current_user.id,
        status="reconciled",
        notes=payload.notes
    )
    saved_rec = repository.create_reconciliation(db, rec)
    
    tx.status = "reconciled"
    db.commit()
    return saved_rec


def link_fiscal_document_to_transaction(
    db: Session,
    organization_id: uuid.UUID,
    transaction_id: uuid.UUID,
    current_user: User,
    payload: schemas.BankTransactionLinkFiscalRequest,
) -> models.BankTransaction:
    tx = repository.get_bank_transaction_by_id(db, transaction_id, organization_id)
    if not tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movimentação bancária não encontrada.")

    fiscal_doc = None
    if payload.new_fiscal_document:
        fiscal_doc = create_fiscal_document(db, organization_id, current_user, payload.new_fiscal_document)
    elif payload.fiscal_document_id:
        fiscal_doc = repository.get_fiscal_document_by_id(db, payload.fiscal_document_id, organization_id)
        if not fiscal_doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento fiscal não encontrado.")
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Informe um documento fiscal existente ou os dados para cadastro.")

    tx.fiscal_document_id = fiscal_doc.id
    db.flush()
    db.refresh(tx)
    return tx


def unlink_fiscal_document_from_transaction(
    db: Session,
    organization_id: uuid.UUID,
    transaction_id: uuid.UUID,
) -> models.BankTransaction:
    tx = repository.get_bank_transaction_by_id(db, transaction_id, organization_id)
    if not tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movimentação bancária não encontrada.")
    tx.fiscal_document_id = None
    db.flush()
    db.refresh(tx)
    return tx


def attach_receipt_to_transaction(
    db: Session,
    organization_id: uuid.UUID,
    transaction_id: uuid.UUID,
    current_user: User,
    payload: schemas.BankTransactionAttachReceiptRequest,
) -> models.BankTransaction:
    tx = repository.get_bank_transaction_by_id(db, transaction_id, organization_id)
    if not tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movimentação bancária não encontrada.")

    tx.receipt_url = payload.file_url
    tx.receipt_filename = payload.file_name

    # Se informado um payable_id ou se já houver payment conciliado:
    if payload.payable_id:
        payable = repository.get_payable_by_id(db, payload.payable_id, organization_id)
        if payable and payable.payments:
            last_payment = payable.payments[-1]
            att = models.PaymentAttachment(
                payment_id=last_payment.id,
                file_name=payload.file_name,
                file_url=payload.file_url,
                mime_type=payload.mime_type,
                uploaded_by_id=current_user.id
            )
            db.add(att)
            db.flush()
            tx.payment_attachment_id = att.id

    db.flush()
    db.refresh(tx)
    return tx


def remove_receipt_from_transaction(
    db: Session,
    organization_id: uuid.UUID,
    transaction_id: uuid.UUID,
) -> models.BankTransaction:
    tx = repository.get_bank_transaction_by_id(db, transaction_id, organization_id)
    if not tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movimentação bancária não encontrada.")

    tx.receipt_url = None
    tx.receipt_filename = None
    tx.payment_attachment_id = None
    db.flush()
    db.refresh(tx)
    return tx


# ==============================================================================
# 5. CONTAS A RECEBER (Receivable) & RECEBIMENTOS
# ==============================================================================

def create_receivable(
    db: Session,
    organization_id: uuid.UUID,
    payload: schemas.ReceivableCreate,
    *,
    current_user: User | None = None,
    source_document=None,
    invoice_installment_id: uuid.UUID | None = None,
) -> models.Receivable:
    """Cria a identidade documental e o título financeiro atomicamente."""
    from controlb.modules.documents import schemas as document_schemas
    from controlb.modules.documents import service as documents_service

    fiscal_document = None
    if payload.fiscal_document_id:
        fiscal_document = repository.get_fiscal_document_by_id(
            db, payload.fiscal_document_id, organization_id
        )
        if not fiscal_document:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O documento fiscal vinculado à conta a receber é inválido.",
            )
        if source_document is None:
            source_document = get_fiscal_document_header(
                db, fiscal_document, organization_id
            )

    if invoice_installment_id:
        from controlb.modules.billing.models import Invoice, InvoiceInstallment

        installment = db.scalar(
            select(InvoiceInstallment)
            .join(Invoice, Invoice.id == InvoiceInstallment.invoice_id)
            .where(
                InvoiceInstallment.id == invoice_installment_id,
                Invoice.organization_id == organization_id,
            )
        )
        if not installment:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A parcela de fatura vinculada à conta a receber é inválida.",
            )

    receivable_id = uuid.uuid4()
    actor_id = current_user.id if current_user else None
    header = documents_service.create_document(
        db,
        organization_id=organization_id,
        payload=document_schemas.DocumentCreate(
            category="finance.receivable",
            document_type="RECEIVABLE",
            native_id=receivable_id,
            title="Conta a Receber",
            current_status="PENDING",
            description=payload.description.strip(),
            origin_module="FINANCE",
            responsible_id=actor_id,
            payload={
                "customer_id": (
                    str(payload.customer_id) if payload.customer_id else None
                ),
                "fiscal_document_id": (
                    str(payload.fiscal_document_id)
                    if payload.fiscal_document_id
                    else None
                ),
                "invoice_installment_id": (
                    str(invoice_installment_id) if invoice_installment_id else None
                ),
                "customer_name": payload.customer_name.strip(),
                "customer_document": payload.customer_document,
                "due_date": payload.due_date.isoformat(),
                "amount": str(payload.original_amount),
            },
            issued_at=datetime.combine(
                payload.issue_date, datetime.min.time(), tzinfo=timezone.utc
            ),
        ),
        current_user=current_user,
    )
    header.title = f"Conta a Receber {header.document_number}"

    rec = models.Receivable(
        id=receivable_id,
        organization_id=organization_id,
        document_id=header.id,
        receivable_number=header.document_number,
        customer_id=payload.customer_id,
        customer_name=payload.customer_name.strip(),
        customer_document=payload.customer_document,
        fiscal_document_id=payload.fiscal_document_id,
        invoice_installment_id=invoice_installment_id,
        cost_center_id=payload.cost_center_id,
        financial_category_id=payload.financial_category_id,
        description=payload.description.strip(),
        original_amount=payload.original_amount,
        outstanding_amount=payload.original_amount,
        issue_date=payload.issue_date,
        due_date=payload.due_date,
        payment_method_expected=payload.payment_method_expected,
        status="PENDING",
        notes=payload.notes
    )
    saved = repository.create_receivable(db, rec)
    if source_document is not None:
        documents_service.relate_documents(
            db,
            organization_id=organization_id,
            parent_document=source_document,
            child_document=header,
            relation_type="GENERATED",
            created_by_id=actor_id,
            relation_metadata={
                "invoice_installment_id": (
                    str(invoice_installment_id) if invoice_installment_id else None
                )
            },
        )
    db.flush()
    return saved


def get_receivable_header(
    db: Session,
    receivable: models.Receivable,
    organization_id: uuid.UUID,
):
    from controlb.modules.documents import service as documents_service

    document = documents_service.get_document(
        db, receivable.document_id, organization_id
    )
    if document.document_type != "RECEIVABLE" or document.native_id != receivable.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O cabeçalho documental da conta a receber é inconsistente.",
        )
    receivable.receivable_number = document.document_number
    receivable.status = document.current_status
    return document


def transition_receivable_status(
    db: Session,
    receivable: models.Receivable,
    organization_id: uuid.UUID,
    new_status: str,
    *,
    actor_id: uuid.UUID | None = None,
    event_type: str = "STATUS_CHANGED",
    event_metadata: dict | None = None,
    idempotency_key: str | None = None,
) -> models.Receivable:
    from controlb.modules.documents import service as documents_service

    document = get_receivable_header(db, receivable, organization_id)
    previous_status = document.current_status
    normalized_status = new_status.strip().upper()
    receivable.status = normalized_status
    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=document,
        event_type=event_type,
        previous_status=previous_status,
        new_status=normalized_status,
        created_by_id=actor_id,
        event_metadata=event_metadata,
        idempotency_key=idempotency_key,
    )
    repository.update_receivable(db, receivable)
    if receivable.invoice_installment_id:
        from controlb.modules.billing import service as billing_service

        billing_service.synchronize_invoice_payment_status(
            db,
            organization_id,
            receivable.invoice_installment_id,
            actor_id=actor_id,
        )
    return receivable


def list_receivables(db: Session, organization_id: uuid.UUID, status: str | None = None) -> list[models.Receivable]:
    today = date.today()
    all_recs = repository.list_receivables(db, organization_id, status)
    for r in all_recs:
        if r.status == "PENDING" and r.due_date < today and r.outstanding_amount > 0:
            transition_receivable_status(
                db, r, organization_id, "OVERDUE", event_type="BECAME_OVERDUE"
            )
        else:
            get_receivable_header(db, r, organization_id)
    return all_recs


def update_receivable(
    db: Session,
    organization_id: uuid.UUID,
    receivable_id: uuid.UUID,
    current_user: User,
    payload: schemas.ReceivableUpdate,
) -> models.Receivable:
    from controlb.modules.documents import schemas as document_schemas
    from controlb.modules.documents import service as documents_service

    receivable = repository.get_receivable_by_id(db, receivable_id, organization_id)
    if not receivable:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta a receber não encontrada.")
    header = get_receivable_header(db, receivable, organization_id)
    if receivable.status == "RECEIVED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conta já recebida não pode ser editada.",
        )

    changes = payload.model_dump(exclude_unset=True)
    requested_status = changes.pop("status", None)
    if requested_status:
        requested_status = requested_status.strip().upper()
        if requested_status not in {"PENDING", "OVERDUE", "CANCELLED"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Status da conta a receber inválido para edição manual.")
        if receivable.receipts and requested_status == "CANCELLED":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Conta com recebimentos registrados não pode ser cancelada diretamente.")
    elif receivable.status == "CANCELLED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conta cancelada só pode ser editada para reabertura de status.",
        )

    if "original_amount" in changes:
        settled_amount = receivable.original_amount - receivable.outstanding_amount
        if changes["original_amount"] < settled_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O novo valor não pode ser inferior ao montante já recebido.",
            )
        receivable.outstanding_amount = changes["original_amount"] - settled_amount
    for field in ("customer_name", "customer_document", "description"):
        if field in changes and changes[field] is not None:
            changes[field] = changes[field].strip() or None
    for field, value in changes.items():
        setattr(receivable, field, value)
    if requested_status:
        receivable.status = requested_status

    document_payload = dict(header.payload or {})
    document_payload.update({
        "customer_id": str(receivable.customer_id) if receivable.customer_id else None,
        "customer_name": receivable.customer_name,
        "customer_document": receivable.customer_document,
        "due_date": receivable.due_date.isoformat(),
        "amount": str(receivable.original_amount),
    })
    documents_service.update_document(
        db,
        header.id,
        organization_id,
        document_schemas.DocumentUpdate(
            current_status=receivable.status,
            description=receivable.description,
            payload=document_payload,
        ),
        current_user=current_user,
    )
    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=header,
        event_type="RECEIVABLE_UPDATED",
        created_by_id=current_user.id,
        event_metadata={"updated_fields": sorted(set(changes) | ({"status"} if requested_status else set()))},
    )
    updated = repository.update_receivable(db, receivable)
    if receivable.invoice_installment_id:
        from controlb.modules.billing import service as billing_service

        billing_service.synchronize_invoice_payment_status(
            db,
            organization_id,
            receivable.invoice_installment_id,
            actor_id=current_user.id,
        )
    return updated


def register_receipt(
    db: Session,
    organization_id: uuid.UUID,
    receivable_id: uuid.UUID,
    current_user: User,
    payload: schemas.ReceiptCreate
) -> models.Receipt:
    rec = repository.get_receivable_by_id(db, receivable_id, organization_id)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta a receber não encontrada.")

    if payload.amount > rec.outstanding_amount:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="O valor recebido é superior ao saldo restante a receber.")

    receipt = models.Receipt(
        organization_id=organization_id,
        receivable_id=rec.id,
        bank_account_id=payload.bank_account_id,
        amount=payload.amount,
        receipt_date=payload.receipt_date,
        payment_method=payload.payment_method,
        reference=payload.reference,
        notes=payload.notes,
        received_by_id=current_user.id
    )
    saved_receipt = repository.create_receipt(db, receipt)

    # Abate saldo
    rec.outstanding_amount = rec.outstanding_amount - payload.amount
    if rec.outstanding_amount <= Decimal("0.00"):
        rec.status = "RECEIVED"
    else:
        rec.status = "PARTIALLY_RECEIVED"
    transition_receivable_status(
        db,
        rec,
        organization_id,
        rec.status,
        actor_id=current_user.id,
        event_type="RECEIPT_REGISTERED",
        event_metadata={
            "receipt_id": str(saved_receipt.id),
            "amount": str(payload.amount),
            "outstanding_amount": str(rec.outstanding_amount),
        },
        idempotency_key=f"receivable:{rec.id}:receipt:{saved_receipt.id}",
    )

    # Atualiza banco e gera extrato
    if payload.bank_account_id:
        bank = repository.get_bank_account_by_id(db, payload.bank_account_id, organization_id)
        if bank:
            bank.current_balance = (bank.current_balance or Decimal("0.00")) + payload.amount
            repository.update_bank_account(db, bank)

            tx = models.BankTransaction(
                organization_id=organization_id,
                bank_account_id=bank.id,
                transaction_date=payload.receipt_date,
                description=f"Recebimento: {rec.description} ({rec.customer_name})",
                amount=payload.amount,
                transaction_type="CREDIT",
                document_number=payload.reference or str(rec.id)[:8],
                balance_after=bank.current_balance,
                status="reconciled"
            )
            saved_tx = repository.create_bank_transaction(db, tx)

            reconciliation = models.Reconciliation(
                organization_id=organization_id,
                bank_transaction_id=saved_tx.id,
                receipt_id=saved_receipt.id,
                reconciled_by_id=current_user.id,
                status="reconciled",
                notes="Conciliação automática de recebimento"
            )
            repository.create_reconciliation(db, reconciliation)

    return saved_receipt


# ==============================================================================
# 6. FATURAMENTO & FECHAMENTO DIÁRIO DE VENDAS DO PDV
# ==============================================================================

def process_sales_report(
    db: Session,
    organization_id: uuid.UUID,
    current_user: User,
    payload: schemas.SalesReportCreate
) -> models.SalesReport:
    """
    Processa o fechamento diário do PDV e gera automaticamente as contas a receber
    divididas por meios de liquidação (Dinheiro, PIX, Débito, Crédito).
    """
    report = models.SalesReport(
        organization_id=organization_id,
        report_date=payload.report_date,
        gross_sales=payload.gross_sales,
        discounts=payload.discounts,
        returns=payload.returns,
        net_sales=payload.net_sales,
        cash_amount=payload.cash_amount,
        pix_amount=payload.pix_amount,
        debit_amount=payload.debit_amount,
        credit_amount=payload.credit_amount,
        other_amount=payload.other_amount,
        source=payload.source,
        notes=payload.notes,
        created_by_id=current_user.id
    )
    saved_report = repository.create_sales_report(db, report)

    # Gera contas a receber se solicitado
    if payload.generate_receivables:
        channels = [
            ("PIX", payload.pix_amount, 0),
            ("Dinheiro / Caixa", payload.cash_amount, 0),
            ("Cartão de Débito", payload.debit_amount, 1),
            ("Cartão de Crédito", payload.credit_amount, 30),
        ]
        for name, amt, days in channels:
            if amt and amt > Decimal("0.00"):
                due = payload.report_date + timedelta(days=days)
                create_receivable(
                    db,
                    organization_id,
                    schemas.ReceivableCreate(
                    customer_name=f"Vendas Balcão ({name})",
                    description=f"Receita PDV {payload.report_date.strftime('%d/%m/%Y')} - {name}",
                    original_amount=amt,
                    issue_date=payload.report_date,
                    due_date=due,
                    payment_method_expected=name,
                    notes=f"Gerado a partir do Fechamento de Vendas #{str(saved_report.id)[:8]}"
                    ),
                    current_user=current_user,
                )

    return saved_report


def list_sales_reports(db: Session, organization_id: uuid.UUID) -> list[models.SalesReport]:
    return repository.list_sales_reports(db, organization_id)


# ==============================================================================
# 7. DASHBOARD & INDICADORES CONSOLIDADOS
# ==============================================================================

def get_finance_dashboard_summary(db: Session, organization_id: uuid.UUID) -> schemas.FinanceDashboardSummary:
    today = date.today()
    first_day_month = today.replace(day=1)
    
    # 1. Saldo disponível total
    accounts = repository.list_bank_accounts(db, organization_id)
    total_balance = sum(Decimal(str(a.current_balance or 0)) for a in accounts)

    # 2. Contas a Pagar
    payables = repository.list_payables(db, organization_id)
    p_today = sum(p.outstanding_amount for p in payables if p.due_date == today and p.status not in ["PAID", "CANCELLED"])
    p_month = sum(p.outstanding_amount for p in payables if p.due_date >= first_day_month and p.status not in ["PAID", "CANCELLED"])
    p_overdue = sum(p.outstanding_amount for p in payables if p.due_date < today and p.status not in ["PAID", "CANCELLED"])
    
    capex_m = sum(p.original_amount for p in payables if p.due_date >= first_day_month and p.expense_nature == "CAPEX" and p.status != "CANCELLED")
    opex_m = sum(p.original_amount for p in payables if p.due_date >= first_day_month and p.expense_nature == "OPEX" and p.status != "CANCELLED")

    # 3. Contas a Receber
    receivables = repository.list_receivables(db, organization_id)
    r_today = sum(r.outstanding_amount for r in receivables if r.due_date == today and r.status not in ["RECEIVED", "CANCELLED"])
    r_month = sum(r.outstanding_amount for r in receivables if r.due_date >= first_day_month and r.status not in ["RECEIVED", "CANCELLED"])
    r_overdue = sum(r.outstanding_amount for r in receivables if r.due_date < today and r.status not in ["RECEIVED", "CANCELLED"])

    # 4. Conciliações Pendentes
    txs = repository.list_bank_transactions(db, organization_id, status="pending")

    return schemas.FinanceDashboardSummary(
        total_available_balance=total_balance,
        payables_today=p_today,
        payables_month=p_month,
        payables_overdue=p_overdue,
        receivables_today=r_today,
        receivables_month=r_month,
        receivables_overdue=r_overdue,
        projected_net_cashflow=(total_balance + r_month - p_month),
        capex_month=capex_m,
        opex_month=opex_m,
        unreconciled_transactions_count=len(txs)
    )


def reopen_payable(
    db: Session,
    organization_id: uuid.UUID,
    payable_id: uuid.UUID,
    current_user: User,
) -> models.Payable:
    payable = repository.get_payable_by_id(db, payable_id, organization_id)
    if not payable:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta a pagar não encontrada.")
    if payable.status != "CANCELLED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Apenas contas canceladas podem ser reabertas. Status atual: {payable.status}."
        )
    new_status = "APPROVED" if payable.purchase_order_id else "PENDING_APPROVAL"
    transition_payable_status(
        db,
        payable,
        organization_id,
        new_status,
        actor_id=current_user.id,
        event_type="PAYABLE_REOPENED",
        event_metadata={"reason": "Reabertura manual de conta a pagar"},
    )
    db.commit()
    db.refresh(payable)
    return payable


def delete_payable(
    db: Session,
    organization_id: uuid.UUID,
    payable_id: uuid.UUID,
    current_user: User,
) -> None:
    from controlb.modules.documents import repository as documents_repository

    payable = repository.get_payable_by_id(db, payable_id, organization_id)
    if not payable:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta a pagar não encontrada.")
    if payable.payments:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conta a pagar com pagamentos registrados não pode ser excluída.",
        )
    if payable.status not in {"CANCELLED", "DRAFT", "PENDING_APPROVAL"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Apenas contas canceladas ou pendentes podem ser excluídas. Status atual: {payable.status}.",
        )
    document = get_payable_header(db, payable, organization_id)
    repository.delete_payable(db, payable)
    if document:
        documents_repository.delete_document(db, document)
    db.commit()


def reopen_receivable(
    db: Session,
    organization_id: uuid.UUID,
    receivable_id: uuid.UUID,
    current_user: User,
) -> models.Receivable:
    receivable = repository.get_receivable_by_id(db, receivable_id, organization_id)
    if not receivable:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta a receber não encontrada.")
    if receivable.status != "CANCELLED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Apenas títulos cancelados podem ser reabertos. Status atual: {receivable.status}."
        )
    transition_receivable_status(
        db,
        receivable,
        organization_id,
        "PENDING",
        actor_id=current_user.id,
        event_type="RECEIVABLE_REOPENED",
        event_metadata={"reason": "Reabertura manual de conta a receber"},
    )
    db.commit()
    db.refresh(receivable)
    return receivable


def delete_receivable(
    db: Session,
    organization_id: uuid.UUID,
    receivable_id: uuid.UUID,
    current_user: User,
) -> None:
    from controlb.modules.documents import repository as documents_repository

    receivable = repository.get_receivable_by_id(db, receivable_id, organization_id)
    if not receivable:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta a receber não encontrada.")
    if receivable.receipts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Título com recebimentos registrados não pode ser excluído.",
        )
    if receivable.status not in {"CANCELLED", "PENDING"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Apenas títulos cancelados ou pendentes podem ser excluídos. Status atual: {receivable.status}.",
        )
    document = get_receivable_header(db, receivable, organization_id)
    repository.delete_receivable(db, receivable)
    if document:
        documents_repository.delete_document(db, document)
    db.commit()


def create_or_update_payable_instrument(
    db: Session,
    organization_id: uuid.UUID,
    payable_id: uuid.UUID,
    payload: schemas.PaymentInstrumentCreate,
) -> models.PaymentInstrument:
    payable = repository.get_payable_by_id(db, payable_id, organization_id)
    if not payable:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta a pagar não encontrada.")

    existing = next((inst for inst in payable.instruments if inst.instrument_type == payload.instrument_type), None)
    if existing:
        if payload.barcode is not None:
            existing.barcode = payload.barcode
        if payload.digitable_line is not None:
            existing.digitable_line = payload.digitable_line
        if payload.pix_code is not None:
            existing.pix_code = payload.pix_code
        if payload.document_number is not None:
            existing.document_number = payload.document_number
        if payload.due_date is not None:
            existing.due_date = payload.due_date
        if payload.amount is not None:
            existing.amount = payload.amount
        if payload.file_attachment is not None:
            existing.file_attachment = payload.file_attachment
        db.flush()
        db.commit()
        db.refresh(existing)
        return existing

    inst = models.PaymentInstrument(
        payable_id=payable.id,
        instrument_type=payload.instrument_type,
        barcode=payload.barcode,
        digitable_line=payload.digitable_line,
        pix_code=payload.pix_code,
        document_number=payload.document_number or payable.payable_number,
        due_date=payload.due_date or payable.due_date,
        amount=payload.amount or payable.outstanding_amount,
        file_attachment=payload.file_attachment,
    )
    saved = repository.create_payment_instrument(db, inst)
    db.commit()
    db.refresh(saved)
    return saved


def delete_payable_instrument(
    db: Session,
    organization_id: uuid.UUID,
    payable_id: uuid.UUID,
    instrument_id: uuid.UUID,
) -> None:
    payable = repository.get_payable_by_id(db, payable_id, organization_id)
    if not payable:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta a pagar não encontrada.")
    inst = repository.get_payment_instrument_by_id(db, instrument_id, payable_id)
    if not inst:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instrumento de pagamento não encontrado.")
    repository.delete_payment_instrument(db, inst)
    db.commit()

