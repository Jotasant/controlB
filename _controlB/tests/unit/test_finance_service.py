"""
tests/unit/test_finance_service.py - Testes Automatizados de Regras de Negócio do Módulo Financeiro e Faturamento
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal
import pytest
from sqlalchemy.orm import Session

from controlb.db import SessionLocal
from controlb.modules.identity import models as id_models
from controlb.modules.finance import service, schemas, repository, models


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def current_org(db: Session):
    org = db.query(id_models.Organization).first()
    if not org:
        org = id_models.Organization(trade_name="Empresa Teste Financeiro", legal_name="Empresa Teste Financeiro LTDA", cnpj="00000000000199")
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
