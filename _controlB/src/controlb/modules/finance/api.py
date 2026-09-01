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


@router.patch("/finance/categories/{category_id}", response_model=schemas.FinancialCategoryResponse, summary="Editar Categoria Financeira")
def update_financial_category(
    category_id: uuid.UUID,
    payload: schemas.FinancialCategoryUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user),
):
    return service.update_financial_category(db, current_user.organization_id, category_id, payload)


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


@router.patch("/finance/bank-accounts/{account_id}", response_model=schemas.BankAccountResponse, summary="Editar Conta Bancária")
def update_bank_account(
    account_id: uuid.UUID,
    payload: schemas.BankAccountUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user),
):
    return service.update_bank_account(db, current_user.organization_id, account_id, payload)


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
    return service.create_fiscal_document(
        db, current_user.organization_id, current_user, payload
    )


@router.patch("/finance/fiscal-documents/{fiscal_document_id}", response_model=schemas.FiscalDocumentResponse, summary="Editar Documento Fiscal")
def update_fiscal_document(
    fiscal_document_id: uuid.UUID,
    payload: schemas.FiscalDocumentUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user),
):
    return service.update_fiscal_document(
        db, current_user.organization_id, fiscal_document_id, current_user, payload
    )


# ==============================================================================
# 4. CONTAS A PAGAR (Payable) & PAGAMENTOS
# ==============================================================================

@router.get("/finance/payables", response_model=list[schemas.PayableResponse], summary="Listar Títulos a Pagar")
def list_payables(
    status: str | None = Query(None),
    expense_nature: str | None = Query(None, description="Natureza contábil"),
    obligation_type: str | None = Query(None, description="Tipo da obrigação"),
    business_origin: str | None = Query(None, description="Origem de negócio"),
    start_due_date: date | None = Query(None),
    end_due_date: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.list_payables(
        db,
        current_user.organization_id,
        status=status,
        expense_nature=expense_nature,
        start_due_date=start_due_date,
        end_due_date=end_due_date,
        obligation_type=obligation_type,
        business_origin=business_origin,
    )


@router.post("/finance/payables", response_model=list[schemas.PayableResponse], status_code=status.HTTP_201_CREATED, summary="Lançar Despesa Avulsa / Título a Pagar")
def create_payable(
    payload: schemas.PayableCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.create_payable_expense(db, current_user.organization_id, current_user, payload)


@router.patch("/finance/payables/{payable_id}", response_model=schemas.PayableResponse, summary="Editar Conta a Pagar")
def update_payable(
    payable_id: uuid.UUID,
    payload: schemas.PayableUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user),
):
    return service.update_payable(
        db, current_user.organization_id, payable_id, current_user, payload
    )


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


@router.patch("/finance/transactions/{transaction_id}", response_model=schemas.BankTransactionResponse, summary="Editar Movimentação Bancária Manual")
def update_bank_transaction(
    transaction_id: uuid.UUID,
    payload: schemas.BankTransactionUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user),
):
    return service.update_bank_transaction(
        db, current_user.organization_id, transaction_id, payload
    )


@router.post("/finance/transactions/{transaction_id}/fiscal-document", response_model=schemas.BankTransactionResponse, summary="Vincular ou Cadastrar Nota Fiscal na Movimentação Bancária")
def link_fiscal_document_to_transaction(
    transaction_id: uuid.UUID,
    payload: schemas.BankTransactionLinkFiscalRequest,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user),
):
    return service.link_fiscal_document_to_transaction(
        db, current_user.organization_id, transaction_id, current_user, payload
    )


@router.delete("/finance/transactions/{transaction_id}/fiscal-document", response_model=schemas.BankTransactionResponse, summary="Desvincular Nota Fiscal da Movimentação Bancária")
def unlink_fiscal_document_from_transaction(
    transaction_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user),
):
    return service.unlink_fiscal_document_from_transaction(
        db, current_user.organization_id, transaction_id
    )


@router.post("/finance/transactions/{transaction_id}/receipt", response_model=schemas.BankTransactionResponse, summary="Anexar Comprovante de Pagamento na Movimentação Bancária")
def attach_receipt_to_transaction(
    transaction_id: uuid.UUID,
    payload: schemas.BankTransactionAttachReceiptRequest,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user),
):
    return service.attach_receipt_to_transaction(
        db, current_user.organization_id, transaction_id, current_user, payload
    )


@router.delete("/finance/transactions/{transaction_id}/receipt", response_model=schemas.BankTransactionResponse, summary="Remover Comprovante da Movimentação Bancária")
def remove_receipt_from_transaction(
    transaction_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user),
):
    return service.remove_receipt_from_transaction(
        db, current_user.organization_id, transaction_id
    )


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
    return service.create_receivable(
        db, current_user.organization_id, payload, current_user=current_user
    )


@router.patch("/finance/receivables/{receivable_id}", response_model=schemas.ReceivableResponse, summary="Editar Conta a Receber")
def update_receivable(
    receivable_id: uuid.UUID,
    payload: schemas.ReceivableUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user),
):
    return service.update_receivable(
        db, current_user.organization_id, receivable_id, current_user, payload
    )


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
