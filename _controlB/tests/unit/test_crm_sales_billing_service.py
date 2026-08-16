"""
tests/unit/test_crm_sales_billing_service.py - Testes unitários dos módulos CRM, Vendas/PDV e Faturamento
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal
import pytest
from sqlalchemy.orm import Session

from controlb.db import SessionLocal
from controlb.modules.identity.models import Organization, User
from controlb.modules.inventory.models import ProductCategory, Product
from controlb.modules.crm import service as crm_service, schemas as crm_schemas
from controlb.modules.sales import service as sales_service, schemas as sales_schemas
from controlb.modules.billing import service as billing_service, schemas as billing_schemas
from controlb.modules.finance import service as finance_service


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def mock_org(db: Session) -> Organization:
    org = Organization(name=f"Matriz Teste {uuid.uuid4().hex[:6]}")
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@pytest.fixture
def mock_user(db: Session, mock_org: Organization) -> User:
    user = User(
        organization_id=mock_org.id,
        email=f"vendedor_{uuid.uuid4().hex[:6]}@empresa.com",
        full_name="Vendedor Teste",
        hashed_password="hash123"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def mock_product(db: Session, mock_org: Organization) -> Product:
    cat = ProductCategory(organization_id=mock_org.id, name=f"Cat_{uuid.uuid4().hex[:4]}", code=f"C{uuid.uuid4().hex[:3].upper()}")
    db.add(cat)
    db.commit()
    db.refresh(cat)

    prod = Product(
        organization_id=mock_org.id,
        category_id=cat.id,
        sku=f"SKU-{uuid.uuid4().hex[:6].upper()}",
        name="Dipirona 500mg",
        current_stock=Decimal("100"),
        min_stock=Decimal("10"),
        max_stock=Decimal("200"),
        reference_price=Decimal("12.50")
    )
    db.add(prod)
    db.commit()
    db.refresh(prod)
    return prod


def test_crm_lead_and_opportunity_pipeline_flow(db: Session, mock_org: Organization, mock_user: User):
    # 1. Cria Lead
    lead = crm_service.create_lead(
        db,
        mock_org.id,
        crm_schemas.LeadCreate(
            name="Hospital São Lucas",
            company_name="Rede São Lucas S.A.",
            email="compras@saolucas.com",
            phone="11988887777",
            source="Prospecção Ativa",
            status="QUALIFIED"
        )
    )
    assert lead.id is not None
    assert lead.name == "Hospital São Lucas"

    # 2. Cria Oportunidade no Pipeline
    opp = crm_service.create_opportunity(
        db,
        mock_org.id,
        crm_schemas.OpportunityCreate(
            lead_id=lead.id,
            title="Fornecimento Mensal de Insumos",
            customer_name="Hospital São Lucas",
            estimated_amount=Decimal("50000.00"),
            probability_percent=80,
            expected_closing_date=date.today() + timedelta(days=15),
            stage="PROPOSAL"
        )
    )
    assert opp.stage == "PROPOSAL"
    assert opp.estimated_amount == Decimal("50000.00")

    # 3. Move oportunidade para WON (Ganho)
    updated_opp = crm_service.update_opportunity_stage(
        db,
        opp.id,
        mock_org.id,
        stage="WON"
    )
    assert updated_opp.stage == "WON"


def test_sales_quote_and_order_flow(db: Session, mock_org: Organization, mock_user: User, mock_product: Product):
    # 1. Cria Orçamento
    quote = sales_service.create_sales_quote(
        db,
        mock_org.id,
        mock_user,
        sales_schemas.SalesQuoteCreate(
            customer_name="Clínica Santa Maria",
            customer_document="22.333.444/0001-55",
            valid_until=date.today() + timedelta(days=10),
            items=[
                sales_schemas.SalesQuoteItemCreate(
                    product_id=mock_product.id,
                    quantity=Decimal("20"),
                    unit_price=Decimal("12.50"),
                    discount_amount=Decimal("10.00")
                )
            ]
        )
    )
    assert quote.id is not None
    assert quote.total_amount == Decimal("250.00")
    assert quote.net_amount == Decimal("240.00")
    assert len(quote.items) == 1

    # 2. Cria Pedido de Venda Oficial
    order = sales_service.create_sales_order(
        db,
        mock_org.id,
        mock_user,
        sales_schemas.SalesOrderCreate(
            customer_name="Clínica Santa Maria",
            customer_document="22.333.444/0001-55",
            payment_terms="30 dias",
            items=[
                sales_schemas.SalesOrderItemCreate(
                    product_id=mock_product.id,
                    quantity=Decimal("50"),
                    unit_price=Decimal("12.00"),
                    discount_amount=Decimal("0.00")
                )
            ]
        )
    )
    assert order.id is not None
    assert order.total_amount == Decimal("600.00")
    assert order.net_amount == Decimal("600.00")


def test_pos_session_and_quick_sale(db: Session, mock_org: Organization, mock_user: User, mock_product: Product):
    # 1. Abre Turno de Caixa no PDV
    session = sales_service.open_pos_session(
        db,
        mock_org.id,
        mock_user,
        sales_schemas.POSSessionCreate(
            pos_terminal="Caixa 01 - Balcão",
            opening_cash=Decimal("150.00")
        )
    )
    assert session.status == "OPEN"
    assert session.opening_cash == Decimal("150.00")

    # 2. Processa Venda Rápida de Balcão
    sale = sales_service.process_pos_sale(
        db,
        mock_org.id,
        mock_user,
        sales_schemas.POSSaleCreate(
            pos_session_id=session.id,
            customer_name="Cliente Balcão",
            discount_amount=Decimal("2.00"),
            payment_method="PIX",
            items=[
                sales_schemas.POSSaleItemCreate(
                    product_id=mock_product.id,
                    quantity=Decimal("2"),
                    unit_price=Decimal("12.50")
                )
            ]
        )
    )
    assert sale.id is not None
    assert sale.total_amount == Decimal("25.00")
    assert sale.net_amount == Decimal("23.00")
    assert sale.payment_method == "PIX"


def test_billing_invoice_creates_receivables_in_finance(db: Session, mock_org: Organization, mock_user: User):
    # 1. Emite Fatura Comercial com 3 parcelas
    invoice = billing_service.create_invoice(
        db,
        mock_org.id,
        mock_user,
        billing_schemas.InvoiceCreate(
            customer_name="Empresa Cliente S.A.",
            customer_document="33.444.555/0001-66",
            total_amount=Decimal("3000.00"),
            tax_amount=Decimal("150.00"),
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            installments_count=3,
            generate_receivables_in_finance=True
        )
    )
    assert invoice.id is not None
    assert invoice.net_amount == Decimal("3150.00")
    assert len(invoice.installments) == 3
    assert invoice.installments[0].amount == Decimal("1050.00")

    # 2. Valida se gerou automaticamente as contas a receber no Financeiro
    receivables = finance_service.list_receivables(db, mock_org.id)
    assert len(receivables) >= 3
    assert receivables[0].customer_name == "Empresa Cliente S.A."
    assert sum([r.original_amount for r in receivables]) == Decimal("3150.00")
