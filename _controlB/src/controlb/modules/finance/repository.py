"""
modules/finance/repository.py - Camada de Persistência e Acesso a Dados do Módulo Financeiro e Faturamento
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import Session

from controlb.modules.finance.models import (
    FinancialCategory, BankAccount, FiscalDocument,
    Payable, PaymentInstrument, Payment, PaymentAttachment,
    BankTransaction, Reconciliation, Receivable, Receipt, SalesReport
)


# ==============================================================================
# 1. CATEGORIAS FINANCEIRAS
# ==============================================================================

def get_category_by_id(db: Session, category_id: uuid.UUID, organization_id: uuid.UUID) -> FinancialCategory | None:
    stmt = select(FinancialCategory).where(
        FinancialCategory.id == category_id,
        FinancialCategory.organization_id == organization_id
    )
    return db.scalars(stmt).first()


def list_categories(db: Session, organization_id: uuid.UUID, category_type: str | None = None) -> list[FinancialCategory]:
    stmt = select(FinancialCategory).where(FinancialCategory.organization_id == organization_id)
    if category_type:
        stmt = stmt.where(FinancialCategory.category_type == category_type)
    stmt = stmt.order_by(FinancialCategory.name.asc())
    return list(db.scalars(stmt).all())


def create_category(db: Session, category: FinancialCategory) -> FinancialCategory:
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def update_category(db: Session, category: FinancialCategory) -> FinancialCategory:
    db.commit()
    db.refresh(category)
    return category


def delete_category(db: Session, category: FinancialCategory) -> None:
    db.delete(category)
    db.commit()


# ==============================================================================
# 2. CONTAS BANCÁRIAS / CAIXA
# ==============================================================================

def get_bank_account_by_id(db: Session, account_id: uuid.UUID, organization_id: uuid.UUID) -> BankAccount | None:
    stmt = select(BankAccount).where(
        BankAccount.id == account_id,
        BankAccount.organization_id == organization_id
    )
    return db.scalars(stmt).first()


def list_bank_accounts(db: Session, organization_id: uuid.UUID) -> list[BankAccount]:
    stmt = select(BankAccount).where(
        BankAccount.organization_id == organization_id
    ).order_by(BankAccount.bank_name.asc())
    return list(db.scalars(stmt).all())


def create_bank_account(db: Session, account: BankAccount) -> BankAccount:
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def update_bank_account(db: Session, account: BankAccount) -> BankAccount:
    db.flush()
    return account


def delete_bank_account(db: Session, account: BankAccount) -> None:
    db.delete(account)
    db.commit()


# ==============================================================================
# 3. DOCUMENTOS FISCAIS (FiscalDocument)
# ==============================================================================

def get_fiscal_document_by_id(db: Session, doc_id: uuid.UUID, organization_id: uuid.UUID) -> FiscalDocument | None:
    stmt = select(FiscalDocument).where(
        FiscalDocument.id == doc_id,
        FiscalDocument.organization_id == organization_id
    )
    return db.scalars(stmt).first()


def list_fiscal_documents(
    db: Session,
    organization_id: uuid.UUID,
    direction: str | None = None,
    document_type: str | None = None
) -> list[FiscalDocument]:
    stmt = select(FiscalDocument).where(FiscalDocument.organization_id == organization_id)
    if direction:
        stmt = stmt.where(FiscalDocument.direction == direction)
    if document_type:
        stmt = stmt.where(FiscalDocument.document_type == document_type)
    stmt = stmt.order_by(FiscalDocument.issue_date.desc())
    return list(db.scalars(stmt).all())


def create_fiscal_document(db: Session, doc: FiscalDocument) -> FiscalDocument:
    db.add(doc)
    db.flush()
    return doc


def update_fiscal_document(db: Session, doc: FiscalDocument) -> FiscalDocument:
    db.flush()
    return doc


def delete_fiscal_document(db: Session, doc: FiscalDocument) -> None:
    db.delete(doc)
    db.commit()


# ==============================================================================
# 4. CONTAS A PAGAR (Payable)
# ==============================================================================

def get_payable_by_id(db: Session, payable_id: uuid.UUID, organization_id: uuid.UUID) -> Payable | None:
    stmt = select(Payable).where(
        Payable.id == payable_id,
        Payable.organization_id == organization_id
    )
    return db.scalars(stmt).first()


def list_payables(
    db: Session,
    organization_id: uuid.UUID,
    status: str | None = None,
    expense_nature: str | None = None,
    start_due_date: date | None = None,
    end_due_date: date | None = None,
    obligation_type: str | None = None,
    business_origin: str | None = None,
) -> list[Payable]:
    stmt = select(Payable).where(Payable.organization_id == organization_id)
    if status:
        stmt = stmt.where(Payable.status == status)
    if expense_nature:
        stmt = stmt.where(Payable.expense_nature == expense_nature)
    if obligation_type:
        stmt = stmt.where(Payable.obligation_type == obligation_type)
    if business_origin:
        stmt = stmt.where(Payable.business_origin == business_origin)
    if start_due_date:
        stmt = stmt.where(Payable.due_date >= start_due_date)
    if end_due_date:
        stmt = stmt.where(Payable.due_date <= end_due_date)
    stmt = stmt.order_by(Payable.due_date.asc(), Payable.created_at.desc())
    return list(db.scalars(stmt).all())


def create_payable(db: Session, payable: Payable) -> Payable:
    db.add(payable)
    db.flush()
    return payable


def update_payable(db: Session, payable: Payable) -> Payable:
    db.flush()
    return payable


def delete_payable(db: Session, payable: Payable) -> None:
    db.delete(payable)
    db.commit()


def create_payment_instrument(db: Session, instrument: PaymentInstrument) -> PaymentInstrument:
    db.add(instrument)
    db.flush()
    return instrument


def create_payment(db: Session, payment: Payment) -> Payment:
    db.add(payment)
    db.flush()
    return payment


# ==============================================================================
# 5. TESOURARIA & CONCILIAÇÃO
# ==============================================================================

def list_bank_transactions(
    db: Session,
    organization_id: uuid.UUID,
    bank_account_id: uuid.UUID | None = None,
    status: str | None = None
) -> list[BankTransaction]:
    stmt = select(BankTransaction).where(BankTransaction.organization_id == organization_id)
    if bank_account_id:
        stmt = stmt.where(BankTransaction.bank_account_id == bank_account_id)
    if status:
        stmt = stmt.where(BankTransaction.status == status)
    stmt = stmt.order_by(BankTransaction.transaction_date.desc(), BankTransaction.created_at.desc())
    return list(db.scalars(stmt).all())


def get_bank_transaction_by_id(db: Session, tx_id: uuid.UUID, organization_id: uuid.UUID) -> BankTransaction | None:
    stmt = select(BankTransaction).where(
        BankTransaction.id == tx_id,
        BankTransaction.organization_id == organization_id
    )
    return db.scalars(stmt).first()


def create_bank_transaction(db: Session, tx: BankTransaction) -> BankTransaction:
    db.add(tx)
    db.flush()
    return tx


def update_bank_transaction(db: Session, tx: BankTransaction) -> BankTransaction:
    db.flush()
    return tx


def create_reconciliation(db: Session, rec: Reconciliation) -> Reconciliation:
    db.add(rec)
    db.flush()
    return rec


# ==============================================================================
# 6. CONTAS A RECEBER & RECEBIMENTOS
# ==============================================================================

def get_receivable_by_id(db: Session, receivable_id: uuid.UUID, organization_id: uuid.UUID) -> Receivable | None:
    stmt = select(Receivable).where(
        Receivable.id == receivable_id,
        Receivable.organization_id == organization_id
    )
    return db.scalars(stmt).first()


def list_receivables(
    db: Session,
    organization_id: uuid.UUID,
    status: str | None = None
) -> list[Receivable]:
    stmt = select(Receivable).where(Receivable.organization_id == organization_id)
    if status:
        stmt = stmt.where(Receivable.status == status)
    stmt = stmt.order_by(Receivable.due_date.asc(), Receivable.created_at.desc())
    return list(db.scalars(stmt).all())


def create_receivable(db: Session, receivable: Receivable) -> Receivable:
    db.add(receivable)
    db.flush()
    return receivable


def update_receivable(db: Session, receivable: Receivable) -> Receivable:
    db.flush()
    return receivable


def delete_receivable(db: Session, receivable: Receivable) -> None:
    db.delete(receivable)
    db.commit()


def create_receipt(db: Session, receipt: Receipt) -> Receipt:
    db.add(receipt)
    db.flush()
    return receipt


# ==============================================================================
# 7. FATURAMENTO & PDV
# ==============================================================================

def create_sales_report(db: Session, report: SalesReport) -> SalesReport:
    db.add(report)
    db.flush()
    return report


def list_sales_reports(db: Session, organization_id: uuid.UUID) -> list[SalesReport]:
    stmt = select(SalesReport).where(
        SalesReport.organization_id == organization_id
    ).order_by(SalesReport.report_date.desc())
    return list(db.scalars(stmt).all())
