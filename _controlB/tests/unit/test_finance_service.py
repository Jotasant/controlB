"""
tests/unit/test_finance_service.py - Testes Automatizados de Regras de Negócio do Módulo Financeiro e Faturamento
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from controlb.db import SessionLocal
from controlb.modules.identity import models as id_models
from controlb.modules.finance import service, schemas, repository, models
from controlb.modules.documents.models import BusinessDocument, DocumentEvent


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def current_org(db: Session):
    org = db.query(id_models.Organization).first()
    if not org:
        org = id_models.Organization(name="Empresa Teste Financeiro")
        db.add(org)
        db.commit()
        db.refresh(org)
    return org


@pytest.fixture
def current_user(db: Session, current_org):
    user = db.query(id_models.User).filter(id_models.User.organization_id == current_org.id).first()
    if not user:
        user = id_models.User(
            organization_id=current_org.id,
            email=f"finance_test_{uuid.uuid4().hex[:6]}@controlb.com",
            full_name="Gestor Financeiro",
            hashed_password="fake_hash_password",
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def test_create_category_and_bank_account(db: Session, current_org):
    # 1. Categoria Financeira
    cat = service.create_financial_category(
        db,
        current_org.id,
        schemas.FinancialCategoryCreate(name="TI e Software", code="1.05.01", category_type="EXPENSE")
    )
    assert cat.id is not None
    assert cat.name == "TI e Software"
    assert cat.category_type == "EXPENSE"

    # 2. Conta Bancária
    bank = service.create_bank_account(
        db,
        current_org.id,
        schemas.BankAccountCreate(
            bank_name="Banco Itaú",
            bank_code="341",
            agency="1234",
            account_number="56789-0",
            account_type="CHECKING",
            opening_balance=Decimal("10000.00")
        )
    )
    assert bank.id is not None
    assert bank.current_balance == Decimal("10000.00")


def test_update_pending_manual_transaction_recomposes_bank_balance(
    db: Session, current_org
):
    bank = service.create_bank_account(
        db,
        current_org.id,
        schemas.BankAccountCreate(
            bank_name="Conta para ajuste",
            opening_balance=Decimal("1000.00"),
        ),
    )
    transaction = service.create_bank_transaction(
        db,
        current_org.id,
        schemas.BankTransactionCreate(
            bank_account_id=bank.id,
            transaction_date=date.today(),
            description="Entrada digitada incorretamente",
            amount=Decimal("100.00"),
            transaction_type="CREDIT",
        ),
    )
    assert bank.current_balance == Decimal("1100.00")

    updated = service.update_bank_transaction(
        db,
        current_org.id,
        transaction.id,
        schemas.BankTransactionUpdate(
            description="Saída corrigida",
            amount=Decimal("40.00"),
            transaction_type="DEBIT",
        ),
    )
    assert updated.description == "Saída corrigida"
    assert updated.transaction_type == "DEBIT"
    assert updated.balance_after == Decimal("960.00")
    assert bank.current_balance == Decimal("960.00")

    updated.status = "reconciled"
    with pytest.raises(HTTPException) as exc:
        service.update_bank_transaction(
            db,
            current_org.id,
            transaction.id,
            schemas.BankTransactionUpdate(amount=Decimal("50.00")),
        )
    assert exc.value.status_code == 400


def test_create_payable_expense_with_installments_and_instrument(db: Session, current_org, current_user):
    # Criação de despesa avulsa (ex: Licenças de Software Anuais em 3x) com Boleto
    payables = service.create_payable_expense(
        db,
        current_org.id,
        current_user,
        schemas.PayableCreate(
            description="Assinatura Servidores Cloud AWS",
            favored_name="Amazon Web Services Inc.",
            original_amount=Decimal("3000.00"),
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=10),
            expense_nature="OPEX",
            payment_method_expected="BOLETO",
            installments_count=3,
            installment_frequency_days=30,
            instrument=schemas.PaymentInstrumentCreate(
                instrument_type="BOLETO",
                digitable_line="34191.79001 01043.510047 91020.150008 5 91230000100000",
                barcode="34195912300001000001790001043510049102015000"
            )
        )
    )

    assert len(payables) == 3
    assert payables[0].original_amount == Decimal("1000.00")
    assert payables[0].installment_number == 1
    assert payables[1].installment_number == 2
    assert payables[2].installment_number == 3
    assert len(payables[0].instruments) == 1
    assert payables[0].instruments[0].digitable_line is not None
    assert all(payable.document_id is not None for payable in payables)
    assert all(payable.payable_number.startswith("PAG-") for payable in payables)
    assert all(
        db.get(BusinessDocument, payable.document_id).native_id == payable.id
        for payable in payables
    )


def test_payable_classifications_are_independent_and_searchable(
    db: Session, current_org, current_user
):
    payables = service.create_payable_expense(
        db,
        current_org.id,
        current_user,
        schemas.PayableCreate(
            description="Aquisição de equipamento produtivo",
            favored_name="Fornecedor de Imobilizado",
            original_amount=Decimal("8500.00"),
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=20),
            expense_nature="CAPEX",
            obligation_type="GOODS_SUPPLIER",
            business_origin="INVESTMENT",
            payment_method_expected="TRANSFERENCIA",
        ),
    )

    payable = payables[0]
    assert payable.expense_nature == "CAPEX"
    assert payable.obligation_type == "GOODS_SUPPLIER"
    assert payable.business_origin == "INVESTMENT"
    header = db.get(BusinessDocument, payable.document_id)
    assert header.payload["expense_nature"] == "CAPEX"
    assert header.payload["obligation_type"] == "GOODS_SUPPLIER"
    assert header.payload["business_origin"] == "INVESTMENT"

    filtered = service.list_payables(
        db,
        current_org.id,
        obligation_type="GOODS_SUPPLIER",
        business_origin="INVESTMENT",
    )
    assert payable.id in {item.id for item in filtered}


def test_payable_classification_rejects_mixed_or_unknown_values():
    with pytest.raises(ValueError, match="Natureza contábil inválida"):
        schemas.PayableCreate(
            description="Classificação inválida",
            favored_name="Favorecido",
            original_amount=Decimal("100.00"),
            issue_date=date.today(),
            due_date=date.today(),
            expense_nature="FORNECEDOR",
        )


def test_update_open_payable_preserves_settled_amount_and_audits_document(
    db: Session, current_org, current_user
):
    payable = service.create_payable_expense(
        db,
        current_org.id,
        current_user,
        schemas.PayableCreate(
            description="Serviço recorrente",
            favored_name="Prestador Original",
            original_amount=Decimal("500.00"),
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=10),
            obligation_type="SERVICE_PROVIDER",
        ),
    )[0]

    updated = service.update_payable(
        db,
        current_org.id,
        payable.id,
        current_user,
        schemas.PayableUpdate(
            favored_name="Prestador Atualizado",
            original_amount=Decimal("650.00"),
            business_origin="CONTRACT",
            due_date=date.today() + timedelta(days=20),
        ),
    )

    assert updated.favored_name == "Prestador Atualizado"
    assert updated.original_amount == Decimal("650.00")
    assert updated.outstanding_amount == Decimal("650.00")
    assert updated.business_origin == "CONTRACT"
    header = db.get(BusinessDocument, updated.document_id)
    assert header.payload["amount"] == "650.00"
    assert header.payload["business_origin"] == "CONTRACT"
    assert db.scalar(
        select(DocumentEvent).where(
            DocumentEvent.document_id == updated.document_id,
            DocumentEvent.event_type == "PAYABLE_UPDATED",
        )
    ) is not None


def test_update_receivable_and_fiscal_document_rules(
    db: Session, current_org, current_user
):
    receivable = service.create_receivable(
        db,
        current_org.id,
        schemas.ReceivableCreate(
            customer_name="Cliente Original",
            description="Mensalidade",
            original_amount=Decimal("900.00"),
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=5),
        ),
        current_user=current_user,
    )
    updated_receivable = service.update_receivable(
        db,
        current_org.id,
        receivable.id,
        current_user,
        schemas.ReceivableUpdate(
            customer_name="Cliente Atualizado",
            original_amount=Decimal("950.00"),
        ),
    )
    assert updated_receivable.customer_name == "Cliente Atualizado"
    assert updated_receivable.outstanding_amount == Decimal("950.00")

    fiscal = service.create_fiscal_document(
        db,
        current_org.id,
        current_user,
        schemas.FiscalDocumentCreate(
            document_number="RASC-EDIT-001",
            issuer_name="Emissor",
            issue_date=date.today(),
            total_amount=Decimal("100.00"),
            status="draft",
        ),
    )
    updated_fiscal = service.update_fiscal_document(
        db,
        current_org.id,
        fiscal.id,
        current_user,
        schemas.FiscalDocumentUpdate(
            document_number="RASC-EDIT-002",
            total_amount=Decimal("120.00"),
            status="authorized",
        ),
    )
    assert updated_fiscal.document_number == "RASC-EDIT-002"
    assert updated_fiscal.total_amount == Decimal("120.00")
    assert updated_fiscal.status == "authorized"

    with pytest.raises(HTTPException, match="autorizado"):
        service.update_fiscal_document(
            db,
            current_org.id,
            fiscal.id,
            current_user,
            schemas.FiscalDocumentUpdate(total_amount=Decimal("130.00")),
        )


def test_create_fiscal_document_uses_canonical_header(
    db: Session, current_org, current_user
):
    fiscal = service.create_fiscal_document(
        db,
        current_org.id,
        current_user,
        schemas.FiscalDocumentCreate(
            document_number="NF-TEST-001",
            issuer_name="Fornecedor Fiscal",
            issue_date=date.today(),
            total_amount=Decimal("250.00"),
        ),
    )

    header = db.get(BusinessDocument, fiscal.document_id)
    assert header is not None
    assert header.native_id == fiscal.id
    assert header.category == "finance.fiscal_document"
    assert header.document_number.startswith("DFE-")


def test_register_payable_partial_and_total_payment(db: Session, current_org, current_user):
    # Cria conta bancária
    bank = service.create_bank_account(
        db,
        current_org.id,
        schemas.BankAccountCreate(
            bank_name="Caixa Econômica",
            account_type="CHECKING",
            opening_balance=Decimal("5000.00")
        )
    )

    # Cria despesa de R$ 1000
    payables = service.create_payable_expense(
        db,
        current_org.id,
        current_user,
        schemas.PayableCreate(
            description="Manutenção de Ar-Condicionado",
            favored_name="Clima Frio Serviços",
            original_amount=Decimal("1000.00"),
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=5),
            expense_nature="OPEX"
        )
    )
    p = payables[0]

    # 1. Baixa Parcial de R$ 400
    payment1 = service.register_payable_payment(
        db,
        current_org.id,
        p.id,
        current_user,
        schemas.PaymentCreate(
            amount=Decimal("400.00"),
            payment_date=date.today(),
            payment_method="PIX",
            bank_account_id=bank.id,
            reference="PIX-E2E-12345"
        )
    )
    assert payment1.id is not None
    db.refresh(p)
    assert p.outstanding_amount == Decimal("600.00")
    assert p.status == "PARTIALLY_PAID"
    
    db.refresh(bank)
    assert bank.current_balance == Decimal("4600.00")

    # 2. Baixa Total do restante R$ 600
    payment2 = service.register_payable_payment(
        db,
        current_org.id,
        p.id,
        current_user,
        schemas.PaymentCreate(
            amount=Decimal("600.00"),
            payment_date=date.today(),
            payment_method="PIX",
            bank_account_id=bank.id,
            reference="PIX-E2E-67890"
        )
    )
    assert payment2.id is not None
    db.refresh(p)
    assert p.outstanding_amount == Decimal("0.00")
    assert p.status == "PAID"
    payable_header = db.get(BusinessDocument, p.document_id)
    assert payable_header.current_status == "PAID"
    assert payable_header.completed_at is not None
    payment_events = set(
        db.scalars(
            select(DocumentEvent.event_type).where(
                DocumentEvent.document_id == p.document_id
            )
        ).all()
    )
    assert "PAYMENT_REGISTERED" in payment_events
    
    db.refresh(bank)
    assert bank.current_balance == Decimal("4000.00")


def test_receivable_and_receipt_flow(db: Session, current_org, current_user):
    bank = service.create_bank_account(
        db,
        current_org.id,
        schemas.BankAccountCreate(
            bank_name="Banco Santander",
            opening_balance=Decimal("2000.00")
        )
    )

    # Cria conta a receber
    rec = service.create_receivable(
        db,
        current_org.id,
        schemas.ReceivableCreate(
            customer_name="Hospital Regional São Lucas",
            description="Fornecimento de Insumos Hospitalares",
            original_amount=Decimal("5000.00"),
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=15)
        )
    )
    assert rec.id is not None
    assert rec.status == "PENDING"
    assert rec.document_id is not None
    assert rec.receivable_number.startswith("REC-")

    # Baixa de recebimento
    receipt = service.register_receipt(
        db,
        current_org.id,
        rec.id,
        current_user,
        schemas.ReceiptCreate(
            amount=Decimal("5000.00"),
            receipt_date=date.today(),
            payment_method="TRANSFERENCIA",
            bank_account_id=bank.id,
            reference="TED-889977"
        )
    )
    assert receipt.id is not None
    db.refresh(rec)
    assert rec.outstanding_amount == Decimal("0.00")
    assert rec.status == "RECEIVED"
    receivable_header = db.get(BusinessDocument, rec.document_id)
    assert receivable_header.current_status == "RECEIVED"
    assert receivable_header.completed_at is not None
    assert "RECEIPT_REGISTERED" in set(
        db.scalars(
            select(DocumentEvent.event_type).where(
                DocumentEvent.document_id == rec.document_id
            )
        ).all()
    )

    db.refresh(bank)
    assert bank.current_balance == Decimal("7000.00")


def test_sales_report_pdv_integration(db: Session, current_org, current_user):
    report = service.process_sales_report(
        db,
        current_org.id,
        current_user,
        schemas.SalesReportCreate(
            report_date=date.today(),
            gross_sales=Decimal("2500.00"),
            discounts=Decimal("100.00"),
            returns=Decimal("0.00"),
            net_sales=Decimal("2400.00"),
            cash_amount=Decimal("400.00"),
            pix_amount=Decimal("800.00"),
            debit_amount=Decimal("500.00"),
            credit_amount=Decimal("700.00"),
            generate_receivables=True
        )
    )
    assert report.id is not None
    assert report.net_sales == Decimal("2400.00")

    # Verifica se os títulos a receber foram gerados
    recs = service.list_receivables(db, current_org.id)
    pdv_recs = [r for r in recs if "Vendas Balcão" in r.customer_name]
    assert len(pdv_recs) >= 4


def test_finance_dashboard_metrics(db: Session, current_org):
    summary = service.get_finance_dashboard_summary(db, current_org.id)
    assert summary.total_available_balance >= Decimal("0.00")
    assert summary.payables_today >= Decimal("0.00")
    assert summary.receivables_today >= Decimal("0.00")
