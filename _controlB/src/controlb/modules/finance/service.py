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


# ==============================================================================
# 2. DOCUMENTOS FISCAIS (FiscalDocument)
# ==============================================================================

def create_fiscal_document(db: Session, organization_id: uuid.UUID, payload: schemas.FiscalDocumentCreate) -> models.FiscalDocument:
    doc = models.FiscalDocument(
        organization_id=organization_id,
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
        status=payload.status
    )
    return repository.create_fiscal_document(db, doc)


def list_fiscal_documents(
    db: Session,
    organization_id: uuid.UUID,
    direction: str | None = None,
    document_type: str | None = None
) -> list[models.FiscalDocument]:
    return repository.list_fiscal_documents(db, organization_id, direction, document_type)


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

        payable = models.Payable(
            organization_id=organization_id,
            supplier_id=payload.supplier_id,
            purchase_order_id=payload.purchase_order_id,
            fiscal_document_id=payload.fiscal_document_id,
            cost_center_id=payload.cost_center_id,
            financial_category_id=payload.financial_category_id,
            description=desc,
            favored_name=payload.favored_name.strip(),
            original_amount=part_amount,
            outstanding_amount=part_amount,
            issue_date=payload.issue_date,
            due_date=due_date,
            expense_nature=payload.expense_nature.upper(),
            payment_method_expected=payload.payment_method_expected,
            installment_number=i,
            total_installments=installments_count,
            status="APPROVED" if payload.purchase_order_id else "PENDING_APPROVAL",
            notes=payload.notes,
            created_by_id=current_user.id
        )
        saved_payable = repository.create_payable(db, payable)

        # Se houver instrumento (Boleto/PIX) na 1ª parcela
        if payload.instrument and i == 1:
            inst = models.PaymentInstrument(
                payable_id=saved_payable.id,
                instrument_type=payload.instrument.instrument_type,
                barcode=payload.instrument.barcode,
                digitable_line=payload.instrument.digitable_line,
                pix_code=payload.instrument.pix_code,
                document_number=payload.instrument.document_number,
                due_date=payload.instrument.due_date or due_date,
                amount=part_amount,
                file_attachment=payload.instrument.file_attachment
            )
            repository.create_payment_instrument(db, inst)
            db.refresh(saved_payable)

        created_payables.append(saved_payable)

    logger.info(f"💰 [PAYABLE CREATED] {len(created_payables)} parcela(s) gerada(s) para '{payload.favored_name}': Total {total_amount} R$")
    return created_payables


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
    
    repository.update_payable(db, payable)

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
    end_due_date: date | None = None
) -> list[models.Payable]:
    # Atualiza automaticamente para OVERDUE títulos vencidos que não foram pagos
    today = date.today()
    all_payables = repository.list_payables(db, organization_id, status, expense_nature, start_due_date, end_due_date)
    for p in all_payables:
        if p.status in ["PENDING_APPROVAL", "APPROVED", "SCHEDULED"] and p.due_date < today and p.outstanding_amount > 0:
            p.status = "OVERDUE"
            repository.update_payable(db, p)
    return all_payables


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


# ==============================================================================
# 5. CONTAS A RECEBER (Receivable) & RECEBIMENTOS
# ==============================================================================

def create_receivable(db: Session, organization_id: uuid.UUID, payload: schemas.ReceivableCreate) -> models.Receivable:
    rec = models.Receivable(
        organization_id=organization_id,
        customer_name=payload.customer_name.strip(),
        customer_document=payload.customer_document,
        fiscal_document_id=payload.fiscal_document_id,
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
    return repository.create_receivable(db, rec)


def list_receivables(db: Session, organization_id: uuid.UUID, status: str | None = None) -> list[models.Receivable]:
    today = date.today()
    all_recs = repository.list_receivables(db, organization_id, status)
    for r in all_recs:
        if r.status == "PENDING" and r.due_date < today and r.outstanding_amount > 0:
            r.status = "OVERDUE"
            repository.update_receivable(db, r)
    return all_recs


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
    repository.update_receivable(db, rec)

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
                rec = models.Receivable(
                    organization_id=organization_id,
                    customer_name=f"Vendas Balcão ({name})",
                    description=f"Receita PDV {payload.report_date.strftime('%d/%m/%Y')} - {name}",
                    original_amount=amt,
                    outstanding_amount=amt,
                    issue_date=payload.report_date,
                    due_date=due,
                    payment_method_expected=name,
                    status="PENDING",
                    notes=f"Gerado a partir do Fechamento de Vendas #{str(saved_report.id)[:8]}"
                )
                repository.create_receivable(db, rec)

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
