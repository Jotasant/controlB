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
    initial_stock = mock_product.current_stock

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

    # 2. Processa Venda Rápida de Balcão (sem passar session_id explicitamente -> auto-vincula)
    sale = sales_service.process_pos_sale(
        db,
        mock_org.id,
        mock_user,
        sales_schemas.POSSaleCreate(
            pos_session_id=None,
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
    assert sale.pos_session_id == session.id
    assert sale.total_amount == Decimal("25.00")
    assert sale.net_amount == Decimal("23.00")
    assert sale.payment_method == "PIX"

    # 3. Valida baixa física real no estoque e geração de StockMovement
    db.refresh(mock_product)
    assert mock_product.current_stock == initial_stock - Decimal("2")

    from controlb.modules.inventory import repository as inv_repo
    movements = inv_repo.list_stock_movements(db, mock_org.id, product_id=mock_product.id)
    assert len(movements) > 0
    sale_mov = [m for m in movements if m.movement_type == "out_sale"]
    assert len(sale_mov) >= 1
    assert sale_mov[0].quantity == Decimal("2")

    # 4. Encerra o Turno de Caixa
    closed_session = sales_service.close_pos_session(
        db,
        mock_org.id,
        session.id,
        mock_user,
        sales_schemas.POSSessionClose(closing_cash=Decimal("173.00"))
    )
    assert closed_session.status == "CLOSED"
    assert closed_session.closing_cash == Decimal("173.00")
    assert closed_session.closed_at is not None



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


def test_identity_contact_and_sales_customer_relationship(db: Session, mock_org: Organization):
    from controlb.modules.identity import service as id_service, schemas as id_schemas

    # 1. Cria Contato Institucional no Módulo Identity
    contact = id_service.create_contact(
        db,
        mock_org.id,
        id_schemas.ContactCreate(
            full_name="Carlos Eduardo Silveira",
            email="carlos.silveira@hospitalalvorada.com.br",
            phone="1133334444",
            mobile="11999998888",
            position="Diretor de Suprimentos",
            document="123.456.789-00"
        )
    )
    assert contact.id is not None
    assert contact.full_name == "Carlos Eduardo Silveira"

    # 2. Cria Cliente PJ no Módulo de Vendas vinculado ao Contato
    customer = sales_service.create_customer(
        db,
        mock_org.id,
        sales_schemas.CustomerCreate(
            contact_id=contact.id,
            person_type="PJ",
            document="11.222.333/0001-99",
            name="Hospital Alvorada Diagnósticos S.A.",
            trade_name="Hospital Alvorada",
            state_registration="123456789",
            email="contato@hospitalalvorada.com.br",
            credit_limit=Decimal("50000.00")
        )
    )
    assert customer.id is not None
    assert customer.contact_id == contact.id
    assert customer.name == "Hospital Alvorada Diagnósticos S.A."

    # 3. Busca e validação
    cust_list = sales_service.list_customers(db, mock_org.id, search="Alvorada")
    assert len(cust_list) >= 1
    assert cust_list[0].id == customer.id


def test_quote_conversion_to_order(db: Session, mock_org: Organization, mock_user: User, mock_product: Product):
    # 1. Cria Orçamento
    quote = sales_service.create_sales_quote(
        db,
        mock_org.id,
        mock_user,
        sales_schemas.SalesQuoteCreate(
            customer_name="Drogaria Central",
            customer_document="44.555.666/0001-77",
            valid_until=date.today() + timedelta(days=7),
            items=[
                sales_schemas.SalesQuoteItemCreate(
                    product_id=mock_product.id,
                    quantity=Decimal("10"),
                    unit_price=Decimal("15.00"),
                    discount_amount=Decimal("5.00")
                )
            ]
        )
    )
    assert quote.status == "DRAFT"

    # 2. Converte Orçamento em Pedido de Venda
    order = sales_service.convert_quote_to_order(db, quote.id, mock_org.id, mock_user)
    assert order.id is not None
    assert order.customer_name == "Drogaria Central"
    assert order.net_amount == Decimal("145.00")
    assert quote.status == "CONVERTED"


def test_pos_cash_movements_sangria_and_suprimento(db: Session, mock_org: Organization, mock_user: User):
    # 1. Abre Turno
    session = sales_service.open_pos_session(
        db,
        mock_org.id,
        mock_user,
        sales_schemas.POSSessionCreate(pos_terminal="CAIXA-02", opening_cash=Decimal("200.00"))
    )

    # 2. Registra Suprimento
    suprimento = sales_service.record_pos_cash_movement(
        db,
        mock_org.id,
        mock_user,
        sales_schemas.POSCashMovementCreate(
            pos_session_id=session.id,
            movement_type="SUPRIMENTO",
            amount=Decimal("100.00"),
            reason="Reforço de moedas e notas de troco"
        )
    )
    assert suprimento.id is not None
    assert suprimento.movement_type == "SUPRIMENTO"

    # 3. Registra Sangria
    sangria = sales_service.record_pos_cash_movement(
        db,
        mock_org.id,
        mock_user,
        sales_schemas.POSCashMovementCreate(
            pos_session_id=session.id,
            movement_type="SANGRIA",
            amount=Decimal("150.00"),
            reason="Retirada para cofre central"
        )
    )
    assert sangria.id is not None
    assert sangria.movement_type == "SANGRIA"

    movs = sales_service.list_pos_cash_movements(db, mock_org.id, session.id)
    assert len(movs) >= 2


def test_sales_return_with_inventory_restock(db: Session, mock_org: Organization, mock_user: User, mock_product: Product):
    initial_stock = mock_product.current_stock

    # Registra Devolução de 5 unidades em bom estado com restock_items = True
    ret = sales_service.process_sales_return(
        db,
        mock_org.id,
        mock_user,
        sales_schemas.SalesReturnCreate(
            customer_name="Farmácia Popular",
            return_type="DEVOLUCAO",
            reason="Excedente de pedido do cliente",
            restock_items=True,
            items=[
                sales_schemas.SalesReturnItemCreate(
                    product_id=mock_product.id,
                    quantity=Decimal("5"),
                    unit_price=Decimal("12.50"),
                    condition="GOOD"
                )
            ]
        )
    )
    assert ret.id is not None
    assert ret.total_amount == Decimal("62.50")

    # Verifica que o estoque físico foi reestocado e gerou StockMovement
    db.refresh(mock_product)
    assert mock_product.current_stock == initial_stock + Decimal("5")

    from controlb.modules.inventory import repository as inv_repo
    movements = inv_repo.list_stock_movements(db, mock_org.id, product_id=mock_product.id)
    ret_movs = [m for m in movements if m.movement_type == "in_return"]
    assert len(ret_movs) >= 1
    assert ret_movs[0].quantity == Decimal("5")


def test_crm_convert_lead_to_customer(db: Session, mock_org: Organization, mock_user: User):
    # 1. Cria Lead
    lead = crm_service.create_lead(
        db,
        mock_org.id,
        crm_schemas.LeadCreate(
            name="Dra. Roberta Martins",
            company_name="Clínica Médica Martins Ltda",
            email="roberta@clinicamartins.com.br",
            phone="11999887766",
            source="Indicação Médica"
        )
    )
    assert lead.status == "NEW"

    # 2. Converte Lead em Cliente no módulo de Vendas e Contato no Identity
    customer = crm_service.convert_lead_to_customer(db, lead.id, mock_org.id, mock_user)
    assert customer.id is not None
    assert customer.name == "Clínica Médica Martins Ltda"
    assert customer.person_type == "PJ"
    assert customer.email == "roberta@clinicamartins.com.br"
    assert customer.contact_id is not None

    db.refresh(lead)
    assert lead.status == "CONVERTED"


def test_crm_create_quote_from_opportunity(db: Session, mock_org: Organization, mock_user: User, mock_product: Product):
    # 1. Cria Oportunidade
    opp = crm_service.create_opportunity(
        db,
        mock_org.id,
        crm_schemas.OpportunityCreate(
            title="Aquisição de 500 caixas de Dipirona",
            customer_name="Hospital Regional do Sul",
            estimated_amount=Decimal("6250.00"),
            probability_percent=70,
            expected_closing_date=date.today() + timedelta(days=20),
            stage="QUALIFICATION"
        )
    )
    assert opp.stage == "QUALIFICATION"

    # 2. Gera Cotação / Orçamento comercial formal a partir da Oportunidade
    quote = crm_service.create_quote_from_opportunity(
        db,
        opp.id,
        mock_org.id,
        mock_user,
        items=[{
            "product_id": str(mock_product.id),
            "quantity": 500,
            "unit_price": 12.50,
            "discount_amount": 0
        }]
    )

    assert quote.id is not None
    assert quote.customer_name == "Hospital Regional do Sul"
    assert quote.net_amount == Decimal("6250.00")
    assert len(quote.items) == 1
    assert quote.opportunity_id == opp.id

    db.refresh(opp)
    assert opp.stage == "PROPOSAL"

    # 3. Converte a Cotação em Pedido de Venda
    order = sales_service.convert_quote_to_order(
        db,
        quote.id,
        mock_org.id,
        mock_user
    )

    assert order.id is not None
    assert order.sales_quote_id == quote.id
    assert order.opportunity_id == opp.id
    assert order.status == "CONFIRMED"

    db.refresh(quote)
    assert quote.status == "CONVERTED"

    db.refresh(opp)
    assert opp.stage == "WON"


def test_crm_lead_conversion_to_customer_and_opportunity_quote_flow(db: Session, mock_org: Organization, mock_user: User, mock_product: Product):
    # 1. Lead entra no CRM
    lead = crm_service.create_lead(
        db,
        mock_org.id,
        crm_schemas.LeadCreate(
            name="Dr. Roberto Silva",
            company_name="Clínica Oftalmológica Visão Ltda",
            email="roberto@visaoclinica.com.br",
            phone="11977776666",
            source="Indicação Médica",
            status="NEW"
        )
    )
    assert lead.status == "NEW"

    # 2. Converte Lead em Cliente Centralizado
    customer = crm_service.convert_lead_to_customer(db, lead.id, mock_org.id, mock_user)
    assert customer.id is not None
    assert customer.name == "Clínica Oftalmológica Visão Ltda"
    assert customer.email == "roberto@visaoclinica.com.br"
    assert customer.contact_id is not None

    db.refresh(lead)
    assert lead.status == "CONVERTED"

    # 3. Cria Oportunidade vinculada ao Cliente Centralizado
    opp = crm_service.create_opportunity(
        db,
        mock_org.id,
        crm_schemas.OpportunityCreate(
            lead_id=lead.id,
            customer_id=customer.id,
            contact_id=customer.contact_id,
            title="Aquisição de Insumos Oftalmológicos",
            customer_name=customer.name,
            estimated_amount=Decimal("15000.00"),
            probability_percent=60,
            expected_closing_date=date.today() + timedelta(days=30),
            stage="QUALIFICATION"
        )
    )
    assert opp.customer_id == customer.id
    assert opp.contact_id == customer.contact_id

    # 4. Cria 2 Cotações diferentes para a mesma Oportunidade (1:N)
    quote1 = sales_service.create_sales_quote(
        db,
        mock_org.id,
        mock_user,
        sales_schemas.SalesQuoteCreate(
            customer_id=customer.id,
            opportunity_id=opp.id,
            customer_name=customer.name,
            payment_terms="30 DDL",
            items=[
                sales_schemas.SalesQuoteItemCreate(
                    product_id=mock_product.id,
                    quantity=Decimal("100"),
                    unit_price=Decimal("12.50"),
                    discount_amount=Decimal("50.00")
                )
            ]
        )
    )
    assert quote1.id is not None

    quote2 = sales_service.create_sales_quote(
        db,
        mock_org.id,
        mock_user,
        sales_schemas.SalesQuoteCreate(
            customer_id=customer.id,
            opportunity_id=opp.id,
            customer_name=customer.name,
            payment_terms="30/60 DDL",
            items=[
                sales_schemas.SalesQuoteItemCreate(
                    product_id=mock_product.id,
                    quantity=Decimal("200"),
                    unit_price=Decimal("12.00"),
                    discount_amount=Decimal("100.00")
                )
            ]
        )
    )
    assert quote2.id is not None

    # 5. Lista cotações vinculadas à oportunidade
    opp_quotes = sales_service.list_sales_quotes(db, mock_org.id, opportunity_id=opp.id)
    assert len(opp_quotes) == 2
    assert all(q.opportunity_id == opp.id for q in opp_quotes)

    # 6. Cliente aceita a Cotação 2 -> Converte em Pedido de Venda
    order = sales_service.convert_quote_to_order(db, quote2.id, mock_org.id, mock_user)
    assert order.id is not None
    assert order.customer_id == customer.id
    assert order.opportunity_id == opp.id
    assert order.sales_quote_id == quote2.id
    assert order.net_amount == Decimal("2300.00")

    db.refresh(quote2)
    assert quote2.status == "CONVERTED"

    db.refresh(opp)
    assert opp.stage == "WON"




