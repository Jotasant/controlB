"""
modules/finance/api.py - Roteador de Endpoints REST do Módulo Financeiro e Faturamento (Finance & Billing Domain)
"""

import uuid
from datetime import date
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from controlb.db import get_db
from controlb.modules.identity import service as identity_service
from controlb.modules.finance import service, schemas

router = APIRouter(prefix="", tags=["Finance & Billing / Gestão Financeira e Faturamento"])


# ==============================================================================
# 1. DASHBOARD & MÉTRICAS CONSOLIDADAS
# ==============================================================================

@router.get("/finance/dashboard", response_model=schemas.FinanceDashboardSummary, summary="Dashboard Financeiro & Fluxo de Caixa")
def get_finance_dashboard(
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.get_finance_dashboard_summary(db, current_user.organization_id)


# ==============================================================================
# 2. CATEGORIAS FINANCEIRAS & CONTAS BANCÁRIAS
# ==============================================================================

@router.get("/finance/categories", response_model=list[schemas.FinancialCategoryResponse], summary="Listar Categorias Financeiras")
def list_financial_categories(
    category_type: str | None = Query(None, description="EXPENSE ou REVENUE"),
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.list_financial_categories(db, current_user.organization_id, category_type)


@router.post("/finance/categories", response_model=schemas.FinancialCategoryResponse, status_code=status.HTTP_201_CREATED, summary="Criar Categoria Financeira")
def create_financial_category(
    payload: schemas.FinancialCategoryCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.create_financial_category(db, current_user.organization_id, payload)


@router.get("/finance/bank-accounts", response_model=list[schemas.BankAccountResponse], summary="Listar Contas Bancárias & Caixas")
def list_bank_accounts(
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.list_bank_accounts(db, current_user.organization_id)


@router.post("/finance/bank-accounts", response_model=schemas.BankAccountResponse, status_code=status.HTTP_201_CREATED, summary="Cadastrar Conta Bancária")
def create_bank_account(
    payload: schemas.BankAccountCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.create_bank_account(db, current_user.organization_id, payload)


# ==============================================================================
# 3. DOCUMENTOS FISCAIS (FiscalDocument)
# ==============================================================================

@router.get("/finance/fiscal-documents", response_model=list[schemas.FiscalDocumentResponse], summary="Listar Documentos Fiscais")
def list_fiscal_documents(
    direction: str | None = Query(None, description="INBOUND ou OUTBOUND"),
    document_type: str | None = Query(None, description="NFE, NFSE, NFCE, CTE"),
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.list_fiscal_documents(db, current_user.organization_id, direction, document_type)


@router.post("/finance/fiscal-documents", response_model=schemas.FiscalDocumentResponse, status_code=status.HTTP_201_CREATED, summary="Cadastrar Documento Fiscal")
def create_fiscal_document(
    payload: schemas.FiscalDocumentCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.create_fiscal_document(db, current_user.organization_id, payload)


# ==============================================================================
# 4. CONTAS A PAGAR (Payable) & PAGAMENTOS
# ==============================================================================

@router.get("/finance/payables", response_model=list[schemas.PayableResponse], summary="Listar Títulos a Pagar")
def list_payables(
    status: str | None = Query(None),
    expense_nature: str | None = Query(None, description="CAPEX ou OPEX"),
    start_due_date: date | None = Query(None),
    end_due_date: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.list_payables(db, current_user.organization_id, status, expense_nature, start_due_date, end_due_date)


@router.post("/finance/payables", response_model=list[schemas.PayableResponse], status_code=status.HTTP_201_CREATED, summary="Lançar Despesa Avulsa / Título a Pagar")
def create_payable(
    payload: schemas.PayableCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.create_payable_expense(db, current_user.organization_id, current_user, payload)


@router.post("/finance/payables/{payable_id}/payments", response_model=schemas.PaymentResponse, status_code=status.HTTP_201_CREATED, summary="Efetuar Baixa / Pagamento de Conta")
def register_payment(
    payable_id: uuid.UUID,
    payload: schemas.PaymentCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.register_payable_payment(db, current_user.organization_id, payable_id, current_user, payload)


# ==============================================================================
# 5. TESOURARIA & CONCILIAÇÃO BANCÁRIA
# ==============================================================================

@router.get("/finance/transactions", response_model=list[schemas.BankTransactionResponse], summary="Extrato de Movimentações Bancárias")
def list_bank_transactions(
    bank_account_id: uuid.UUID | None = Query(None),
    status: str | None = Query(None, description="pending ou reconciled"),
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.list_bank_transactions(db, current_user.organization_id, bank_account_id, status)


@router.post("/finance/transactions", response_model=schemas.BankTransactionResponse, status_code=status.HTTP_201_CREATED, summary="Lançar Movimentação Bancária Manual")
def create_bank_transaction(
    payload: schemas.BankTransactionCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.create_bank_transaction(db, current_user.organization_id, payload)


@router.post("/finance/reconciliations", response_model=schemas.ReconciliationResponse, status_code=status.HTTP_201_CREATED, summary="Realizar Conciliação Bancária")
def reconcile_transaction(
    payload: schemas.ReconciliationCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.reconcile_transaction(db, current_user.organization_id, current_user, payload)


# ==============================================================================
# 6. CONTAS A RECEBER (Receivable) & RECEBIMENTOS
# ==============================================================================

@router.get("/finance/receivables", response_model=list[schemas.ReceivableResponse], summary="Listar Títulos a Receber")
def list_receivables(
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.list_receivables(db, current_user.organization_id, status)


@router.post("/finance/receivables", response_model=schemas.ReceivableResponse, status_code=status.HTTP_201_CREATED, summary="Criar Título a Receber")
def create_receivable(
    payload: schemas.ReceivableCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.create_receivable(db, current_user.organization_id, payload)


@router.post("/finance/receivables/{receivable_id}/receipts", response_model=schemas.ReceiptResponse, status_code=status.HTTP_201_CREATED, summary="Registrar Baixa de Recebimento")
def register_receipt(
    receivable_id: uuid.UUID,
    payload: schemas.ReceiptCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.register_receipt(db, current_user.organization_id, receivable_id, current_user, payload)


# ==============================================================================
# 7. FATURAMENTO & PDV
# ==============================================================================

@router.get("/billing/sales-reports", response_model=list[schemas.SalesReportResponse], summary="Listar Fechamentos de Vendas do PDV")
def list_sales_reports(
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.list_sales_reports(db, current_user.organization_id)


@router.post("/billing/sales-reports", response_model=schemas.SalesReportResponse, status_code=status.HTTP_201_CREATED, summary="Lançar Fechamento de Vendas do PDV")
def create_sales_report(
    payload: schemas.SalesReportCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.process_sales_report(db, current_user.organization_id, current_user, payload)
