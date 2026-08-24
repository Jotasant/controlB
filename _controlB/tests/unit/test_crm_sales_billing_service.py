"""
tests/unit/test_crm_sales_billing_service.py - Testes unitários dos módulos CRM, Vendas/PDV e Faturamento
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from sqlalchemy import select
from sqlalchemy.orm import Session

from controlb.db import SessionLocal
from controlb.modules.documents import service as documents_service
from controlb.modules.documents.models import BusinessDocument, DocumentEvent
from controlb.modules.identity.models import Organization, Permission, Role, User
from controlb.modules.inventory.models import ProductCategory, Product
from controlb.modules.crm import service as crm_service, schemas as crm_schemas
from controlb.modules.sales import (
    api as sales_api,
    repository as sales_repository,
    schemas as sales_schemas,
    service as sales_service,
)
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
    assert lead.customer_id is not None  # Integrado automaticamente com Vendas!

    # 2. Cria Oportunidade no Pipeline
    opp = crm_service.create_opportunity(
        db,
        mock_org.id,
        crm_schemas.OpportunityCreate(
            lead_id=lead.id,
            customer_id=lead.customer_id,
            title="Fornecimento Mensal de Insumos",
            customer_name="Hospital São Lucas",
            estimated_amount=Decimal("50000.00"),
            probability_percent=80,
            expected_closing_date=date.today() + timedelta(days=15),
            stage="PROPOSAL"
        )
    )
    assert opp.stage == "PROPOSAL"
    assert opp.customer_id == lead.customer_id
    assert opp.estimated_amount == Decimal("50000.00")

    # 3. Move oportunidade para WON (Ganho)
    updated_opp = crm_service.update_opportunity_stage(
        db,
        opp.id,
        mock_org.id,
        stage="WON"
    )
    assert updated_opp.stage == "WON"


def test_crm_interaction_lifecycle_edit_and_audit(
    db: Session,
    mock_org: Organization,
    mock_user: User,
):
    opportunity = crm_service.create_opportunity(
        db,
        mock_org.id,
        crm_schemas.OpportunityCreate(
            title="Renovação do contrato hospitalar",
            customer_name="Hospital Vida",
            estimated_amount=Decimal("8000.00"),
        ),
    )
    note = crm_service.register_interaction(
        db,
        mock_org.id,
        mock_user,
        crm_schemas.CustomerInteractionCreate(
            opportunity_id=opportunity.id,
            interaction_type="NOTE",
            summary="Cliente pediu revisão do escopo",
        ),
    )
    activity = crm_service.register_interaction(
        db,
        mock_org.id,
        mock_user,
        crm_schemas.CustomerInteractionCreate(
            opportunity_id=opportunity.id,
            interaction_type="CALL",
            summary="Retornar para a diretoria",
            interaction_date=datetime.now(UTC) + timedelta(days=1),
            responsible_id=mock_user.id,
        ),
    )

    assert note.status is None
    assert note.responsible_id is None
    assert activity.status == "SCHEDULED"
    assert activity.responsible_id == mock_user.id

    updated_note = crm_service.update_interaction(
        db,
        note.id,
        mock_org.id,
        mock_user,
        crm_schemas.CustomerInteractionUpdate(
            summary="Cliente aprovou o escopo revisado",
            details="Aprovação recebida por e-mail.",
        ),
    )
    updated_activity = crm_service.update_interaction(
        db,
        activity.id,
        mock_org.id,
        mock_user,
        crm_schemas.CustomerInteractionUpdate(status="COMPLETED"),
    )

    assert updated_note.summary == "Cliente aprovou o escopo revisado"
    assert updated_note.details == "Aprovação recebida por e-mail."
    assert updated_note.updated_by_id == mock_user.id
    assert updated_activity.status == "COMPLETED"
    assert updated_activity.updated_by_id == mock_user.id

    opportunity_document = db.scalars(
        select(BusinessDocument).where(
            BusinessDocument.organization_id == mock_org.id,
            BusinessDocument.document_type == "OPPORTUNITY",
            BusinessDocument.native_id == opportunity.id,
        )
    ).first()
    audit_events = list(
        db.scalars(
            select(DocumentEvent).where(
                DocumentEvent.document_id == opportunity_document.id,
                DocumentEvent.event_type == "INTERACTION_UPDATED",
            )
        ).all()
    )

    assert len(audit_events) == 2
    note_audit = next(
        event
        for event in audit_events
        if event.event_metadata["interaction_id"] == str(note.id)
    )
    assert note_audit.created_by_id == mock_user.id
    assert note_audit.event_metadata["previous_values"]["summary"] == (
        "Cliente pediu revisão do escopo"
    )


def test_crm_interaction_edit_respects_author_manager_and_tenant(
    db: Session,
    mock_org: Organization,
    mock_user: User,
):
    interaction = crm_service.register_interaction(
        db,
        mock_org.id,
        mock_user,
        crm_schemas.CustomerInteractionCreate(
            interaction_type="MEETING",
            summary="Reunião de alinhamento",
        ),
    )
    other_user = User(
        organization_id=mock_org.id,
        email=f"outro_{uuid.uuid4().hex[:6]}@empresa.com",
        full_name="Outro Usuário",
        hashed_password="hash123",
    )
    db.add(other_user)
    db.commit()
    db.refresh(other_user)

    with pytest.raises(HTTPException) as forbidden:
        crm_service.update_interaction(
            db,
            interaction.id,
            mock_org.id,
            other_user,
            crm_schemas.CustomerInteractionUpdate(summary="Edição indevida"),
        )
    assert forbidden.value.status_code == 403

    crm_manage = db.scalars(
        select(Permission).where(Permission.code == "crm:manage")
    ).first()
    if crm_manage is None:
        crm_manage = Permission(
            code="crm:manage",
            name="Gerenciar CRM & Oportunidades",
            module="CRM",
            description="Gerenciar interações do CRM",
        )
        db.add(crm_manage)
        db.flush()
    manager_role = Role(
        organization_id=mock_org.id,
        name=f"Gestor CRM {uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    manager_role.permissions.append(crm_manage)
    manager = User(
        organization_id=mock_org.id,
        role=manager_role,
        email=f"gestor_{uuid.uuid4().hex[:6]}@empresa.com",
        full_name="Gestor CRM",
        hashed_password="hash123",
    )
    db.add(manager)
    db.commit()
    db.refresh(manager)

    managed_update = crm_service.update_interaction(
        db,
        interaction.id,
        mock_org.id,
        manager,
        crm_schemas.CustomerInteractionUpdate(summary="Edição autorizada pelo gestor"),
    )
    assert managed_update.updated_by_id == manager.id

    other_org = Organization(name=f"Outra Organização {uuid.uuid4().hex[:6]}")
    db.add(other_org)
    db.commit()
    db.refresh(other_org)
    outsider = User(
        organization_id=other_org.id,
        email=f"externo_{uuid.uuid4().hex[:6]}@empresa.com",
        full_name="Usuário Externo",
        hashed_password="hash123",
    )
    db.add(outsider)
    db.commit()
    db.refresh(outsider)

    with pytest.raises(HTTPException) as not_found:
        crm_service.update_interaction(
            db,
            interaction.id,
            other_org.id,
            outsider,
            crm_schemas.CustomerInteractionUpdate(summary="Tentativa externa"),
        )
    assert not_found.value.status_code == 404


def test_crm_stages_dynamic_management(db: Session, mock_org: Organization):
    # 1. Lista etapas iniciais (auto-seed)
    stages = crm_service.list_stages(db, mock_org.id)
    assert len(stages) == 6
    stage_codes = [s.code for s in stages]
    assert "PROSPECTING" in stage_codes
    assert "WON" in stage_codes

    # 2. Cria etapa personalizada
    custom_stage = crm_service.create_stage(
        db,
        mock_org.id,
        crm_schemas.CRMStageCreate(
            code="TECHNICAL_ANALYSIS",
            name="Análise Técnica",
            color="#ec4899",
            order=2
        )
    )
    assert custom_stage.id is not None
    assert custom_stage.code == "TECHNICAL_ANALYSIS"
    assert custom_stage.name == "Análise Técnica"

    # 3. Atualiza etapa
    updated_stage = crm_service.update_stage(
        db,
        custom_stage.id,
        mock_org.id,
        crm_schemas.CRMStageUpdate(name="Análise Técnica e Laboratorial")
    )
    assert updated_stage.name == "Análise Técnica e Laboratorial"

    # 4. Exclui etapa vazia
    res = crm_service.delete_stage(db, custom_stage.id, mock_org.id)
    assert "excluída com sucesso" in res["message"]


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
    assert quote.document_id is not None

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
    assert order.document_id is not None


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
    db.commit()

    # Uma cotação ainda não aprovada não pode produzir pedido.
    with pytest.raises(HTTPException) as exc_info:
        sales_service.convert_quote_to_order(db, quote.id, mock_org.id, mock_user)
    assert exc_info.value.status_code == 409
    db.rollback()

    sales_service.update_sales_quote_status(
        db,
        quote.id,
        mock_org.id,
        "APPROVED",
        mock_user,
    )
    db.commit()

    # 2. Converte cotação aprovada em Pedido de Venda.
    order = sales_service.convert_quote_to_order(db, quote.id, mock_org.id, mock_user)
    db.commit()
    assert order.id is not None
    assert order.customer_name == "Drogaria Central"
    assert order.net_amount == Decimal("145.00")
    assert quote.status == "CONVERTED"
    assert order.document_id is not None

    # Repetir a mesma operação devolve o pedido original, sem duplicar.
    retried_order = sales_service.convert_quote_to_order(
        db,
        quote.id,
        mock_org.id,
        mock_user,
    )
    assert retried_order.id == order.id
    linked_orders = [
        item
        for item in sales_service.list_sales_orders(db, mock_org.id)
        if item.sales_quote_id == quote.id
    ]
    assert len(linked_orders) == 1

    chain = documents_service.get_document_chain(
        db,
        organization_id=mock_org.id,
        document_type="SALES_QUOTE",
        native_id=quote.id,
    )
    assert len([rel for rel in chain.relations if rel.relation_type == "CONVERTED_TO"]) == 1
    assert len(
        [event for event in chain.events if event.event_type == "CONVERTED_TO_ORDER"]
    ) == 1

    # A identidade documental impede apagar a origem depois da conversão.
    with pytest.raises(HTTPException) as delete_exc:
        sales_service.delete_sales_quote(
            db,
            quote.id,
            mock_org.id,
            mock_user,
        )
    assert delete_exc.value.status_code == 409


def test_quote_conversion_rolls_back_as_single_unit(
    db: Session,
    mock_org: Organization,
    mock_user: User,
    mock_product: Product,
):
    organization_id = mock_org.id
    quote = sales_service.create_sales_quote(
        db,
        organization_id,
        mock_user,
        sales_schemas.SalesQuoteCreate(
            customer_name="Cliente Transação Atômica",
            items=[
                sales_schemas.SalesQuoteItemCreate(
                    product_id=mock_product.id,
                    quantity=Decimal("2"),
                    unit_price=Decimal("20.00"),
                )
            ],
        ),
    )
    quote_id = quote.id
    db.commit()

    sales_service.update_sales_quote_status(
        db,
        quote_id,
        organization_id,
        "APPROVED",
        mock_user,
    )
    db.commit()

    pending_order = sales_service.convert_quote_to_order(
        db,
        quote_id,
        organization_id,
        mock_user,
    )
    pending_order_id = pending_order.id
    assert pending_order.document_id is not None
    assert sales_service.get_sales_quote(db, quote_id, organization_id).status == "CONVERTED"

    # Simula uma falha posterior do endpoint: toda a conversão deve desaparecer.
    db.rollback()

    persisted_quote = sales_service.get_sales_quote(db, quote_id, organization_id)
    assert persisted_quote.status == "APPROVED"
    assert sales_repository.list_orders_by_quote_id(db, quote_id, organization_id) == []

    chain = documents_service.get_document_chain(
        db,
        organization_id=organization_id,
        document_type="SALES_QUOTE",
        native_id=quote_id,
    )
    assert all(document.native_id != pending_order_id for document in chain.documents)
    assert all(relation.relation_type != "CONVERTED_TO" for relation in chain.relations)
    assert all(event.event_type != "CONVERTED_TO_ORDER" for event in chain.events)


def test_quote_and_order_delete_cancel_logically(
    db: Session,
    mock_org: Organization,
    mock_user: User,
    mock_product: Product,
):
    quote = sales_service.create_sales_quote(
        db,
        mock_org.id,
        mock_user,
        sales_schemas.SalesQuoteCreate(
            customer_name="Cliente Cancelamento",
            items=[
                sales_schemas.SalesQuoteItemCreate(
                    product_id=mock_product.id,
                    quantity=Decimal("1"),
                    unit_price=Decimal("10.00"),
                )
            ],
        ),
    )
    order = sales_service.create_sales_order(
        db,
        mock_org.id,
        mock_user,
        sales_schemas.SalesOrderCreate(
            customer_name="Cliente Cancelamento",
            items=[
                sales_schemas.SalesOrderItemCreate(
                    product_id=mock_product.id,
                    quantity=Decimal("1"),
                    unit_price=Decimal("10.00"),
                )
            ],
        ),
    )
    quote_id = quote.id
    order_id = order.id
    db.commit()

    quote_result = sales_service.delete_sales_quote(
        db,
        quote_id,
        mock_org.id,
        mock_user,
    )
    order_result = sales_service.delete_sales_order(
        db,
        order_id,
        mock_org.id,
        mock_user,
    )
    assert "cancelada" in quote_result["message"].lower()
    assert "cancelado" in order_result["message"].lower()

    # Repetir DELETE é seguro e não duplica os eventos de cancelamento.
    sales_service.delete_sales_quote(db, quote_id, mock_org.id, mock_user)
    sales_service.delete_sales_order(db, order_id, mock_org.id, mock_user)
    db.commit()

    assert sales_service.get_sales_quote(db, quote_id, mock_org.id).status == "CANCELLED"
    assert sales_service.get_sales_order(db, order_id, mock_org.id).status == "CANCELLED"

    quote_chain = documents_service.get_document_chain(
        db,
        organization_id=mock_org.id,
        document_type="SALES_QUOTE",
        native_id=quote_id,
    )
    order_chain = documents_service.get_document_chain(
        db,
        organization_id=mock_org.id,
        document_type="SALES_ORDER",
        native_id=order_id,
    )
    quote_root = next(doc for doc in quote_chain.documents if doc.id == quote_chain.root_document_id)
    order_root = next(doc for doc in order_chain.documents if doc.id == order_chain.root_document_id)
    assert quote_root.current_status == "CANCELLED"
    assert order_root.current_status == "CANCELLED"
    assert len([event for event in quote_chain.events if event.event_type == "CANCELLED"]) == 1
    assert len([event for event in order_chain.events if event.event_type == "CANCELLED"]) == 1


@pytest.mark.parametrize(
    ("field_name", "terminal_value"),
    [("billing_status", "INVOICED"), ("status", "COMPLETED")],
)
def test_terminal_order_cannot_be_cancelled(
    db: Session,
    mock_org: Organization,
    mock_user: User,
    mock_product: Product,
    field_name: str,
    terminal_value: str,
):
    order = sales_service.create_sales_order(
        db,
        mock_org.id,
        mock_user,
        sales_schemas.SalesOrderCreate(
            customer_name="Cliente Pedido Terminal",
            items=[
                sales_schemas.SalesOrderItemCreate(
                    product_id=mock_product.id,
                    quantity=Decimal("1"),
                    unit_price=Decimal("10.00"),
                )
            ],
        ),
    )
    setattr(order, field_name, terminal_value)
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        sales_service.delete_sales_order(
            db,
            order.id,
            mock_org.id,
            mock_user,
        )
    assert exc_info.value.status_code == 409


def test_sales_rejects_product_reference_from_another_tenant(
    db: Session,
    mock_org: Organization,
    mock_user: User,
):
    foreign_org = Organization(name=f"Tenant Externo {uuid.uuid4().hex[:6]}")
    db.add(foreign_org)
    db.flush()
    foreign_product = Product(
        organization_id=foreign_org.id,
        sku=f"EXT-{uuid.uuid4().hex[:8]}",
        name="Produto de Outro Tenant",
        reference_price=Decimal("99.00"),
    )
    db.add(foreign_product)
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        sales_service.create_sales_quote(
            db,
            mock_org.id,
            mock_user,
            sales_schemas.SalesQuoteCreate(
                customer_name="Cliente Tenant Local",
                items=[
                    sales_schemas.SalesQuoteItemCreate(
                        product_id=foreign_product.id,
                        quantity=Decimal("1"),
                        unit_price=Decimal("99.00"),
                    )
                ],
            ),
        )
    assert exc_info.value.status_code == 400
    assert "organização" in exc_info.value.detail.lower()
    assert sales_service.list_sales_quotes(db, mock_org.id) == []


def test_sales_mutation_routes_require_manage_permission(mock_user: User):
    protected_routes = {
        ("POST", "/sales/quotes"),
        ("PUT", "/sales/quotes/{quote_id}"),
        ("PATCH", "/sales/quotes/{quote_id}/status"),
        ("DELETE", "/sales/quotes/{quote_id}"),
        ("POST", "/sales/orders"),
        ("DELETE", "/sales/orders/{order_id}"),
        ("POST", "/sales/quotes/{quote_id}/convert"),
    }
    api_routes = [route for route in sales_api.router.routes if isinstance(route, APIRoute)]

    for method, path in protected_routes:
        route = next(
            item for item in api_routes if item.path == path and method in item.methods
        )
        current_user_dependency = next(
            dependency
            for dependency in route.dependant.dependencies
            if dependency.name == "current_user"
        )
        with pytest.raises(HTTPException) as exc_info:
            current_user_dependency.call(current_user=mock_user)
        assert exc_info.value.status_code == 403
        assert "sales:manage" in exc_info.value.detail


def test_sales_quote_and_order_read_routes_require_view_permission(mock_user: User):
    protected_routes = {
        ("GET", "/sales/quotes"),
        ("GET", "/sales/quotes/{quote_id}"),
        ("GET", "/sales/orders"),
        ("GET", "/sales/orders/{order_id}"),
    }
    api_routes = [route for route in sales_api.router.routes if isinstance(route, APIRoute)]

    for method, path in protected_routes:
        route = next(
            item for item in api_routes if item.path == path and method in item.methods
        )
        current_user_dependency = next(
            dependency
            for dependency in route.dependant.dependencies
            if dependency.name == "current_user"
        )
        with pytest.raises(HTTPException) as exc_info:
            current_user_dependency.call(current_user=mock_user)
        assert exc_info.value.status_code == 403
        assert "sales:view" in exc_info.value.detail


def test_commercial_approval_routes_require_specific_permissions(mock_user: User):
    expected_permissions = {
        ("GET", "/sales/commercial-approvals"): "sales:approvals:view",
        (
            "POST",
            "/sales/commercial-approvals/{approval_id}/decision",
        ): "sales:approvals:approve",
    }
    api_routes = [route for route in sales_api.router.routes if isinstance(route, APIRoute)]

    for (method, path), permission in expected_permissions.items():
        route = next(
            item for item in api_routes if item.path == path and method in item.methods
        )
        current_user_dependency = next(
            dependency
            for dependency in route.dependant.dependencies
            if dependency.name == "current_user"
        )
        with pytest.raises(HTTPException) as exc_info:
            current_user_dependency.call(current_user=mock_user)
        assert exc_info.value.status_code == 403
        assert permission in exc_info.value.detail


def test_sales_routes_do_not_register_duplicate_operations():
    """Cada combinação de método e caminho deve apontar para uma única operação."""
    operations: list[tuple[str, str]] = []
    for route in sales_api.router.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods:
            if method not in {"HEAD", "OPTIONS"}:
                operations.append((method, route.path))

    duplicates = sorted(
        {operation for operation in operations if operations.count(operation) > 1}
    )

    assert duplicates == []


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
    sales_service.update_sales_quote_status(
        db,
        quote.id,
        mock_org.id,
        "APPROVED",
        mock_user,
    )
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
    sales_service.update_sales_quote_status(
        db,
        quote2.id,
        mock_org.id,
        "APPROVED",
        mock_user,
    )
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


def test_order_status_update_and_request_billing_lifecycle(
    db: Session,
    mock_org: Organization,
    mock_user: User,
    mock_product: Product
):
    # 1. Criar cliente
    customer = sales_service.create_customer(
        db,
        mock_org.id,
        sales_schemas.CustomerCreate(
            name="Cliente Faturamento Teste",
            person_type="PJ",
            document="11223344000199",
            credit_limit=Decimal("50000.00")
        )
    )

    # 2. Criar pedido direto
    order = sales_service.create_sales_order(
        db,
        mock_org.id,
        mock_user,
        sales_schemas.SalesOrderCreate(
            customer_id=customer.id,
            customer_name=customer.name,
            payment_terms="30 DDL",
            items=[
                sales_schemas.SalesOrderItemCreate(
                    product_id=mock_product.id,
                    quantity=Decimal("10"),
                    unit_price=Decimal("50.00"),
                    discount_amount=Decimal("0.00")
                )
            ]
        )
    )
    assert order.status == "CONFIRMED"
    assert order.delivery_status == "PENDING"
    assert order.billing_status == "PENDING"
    assert order.net_amount == Decimal("500.00")

    # 3. Atualizar status de entrega para DISPATCHED
    updated_order = sales_service.update_sales_order_status(
        db,
        order.id,
        mock_org.id,
        sales_schemas.SalesOrderUpdate(delivery_status="DISPATCHED"),
        mock_user
    )
    assert updated_order.delivery_status == "DISPATCHED"

    # 4. Solicitar faturamento do pedido
    billed_order = sales_service.request_order_billing(
        db,
        order.id,
        mock_org.id,
        mock_user
    )
    assert billed_order.billing_status == "INVOICED"

    # 5. Validação da cadeia documental
    chain = documents_service.get_document_chain(
        db,
        organization_id=mock_org.id,
        document_type="SALES_ORDER",
        native_id=order.id
    )
    assert chain.root_document_id is not None
    assert len(chain.documents) >= 2
    assert any(d.document_type == "INVOICE" for d in chain.documents)


def test_order_update_persists_editable_commercial_fields(
    db: Session,
    mock_org: Organization,
    mock_user: User,
    mock_product: Product,
):
    order = sales_service.create_sales_order(
        db,
        mock_org.id,
        mock_user,
        sales_schemas.SalesOrderCreate(
            customer_name="Cliente Original",
            customer_document="11111111000111",
            payment_terms="30 DDL",
            notes="Observação original",
            items=[
                sales_schemas.SalesOrderItemCreate(
                    product_id=mock_product.id,
                    quantity=Decimal("2"),
                    unit_price=Decimal("25.00"),
                )
            ],
        ),
    )

    sales_service.update_sales_order_status(
        db,
        order.id,
        mock_org.id,
        sales_schemas.SalesOrderUpdate(
            customer_name="Cliente Atualizado",
            customer_document="22222222000122",
            payment_terms="45 DDL",
            notes="Observação atualizada",
        ),
        mock_user,
    )
    db.expire_all()

    persisted = sales_service.get_sales_order(db, order.id, mock_org.id)
    assert persisted.customer_name == "Cliente Atualizado"
    assert persisted.customer_document == "22222222000122"
    assert persisted.payment_terms == "45 DDL"
    assert persisted.notes == "Observação atualizada"


def test_order_generic_update_rejects_formal_cancellation(
    db: Session,
    mock_org: Organization,
    mock_user: User,
    mock_product: Product,
):
    order = sales_service.create_sales_order(
        db,
        mock_org.id,
        mock_user,
        sales_schemas.SalesOrderCreate(
            customer_name="Cliente Cancelamento Formal",
            items=[
                sales_schemas.SalesOrderItemCreate(
                    product_id=mock_product.id,
                    quantity=Decimal("1"),
                    unit_price=Decimal("10.00"),
                )
            ],
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        sales_service.update_sales_order_status(
            db,
            order.id,
            mock_org.id,
            sales_schemas.SalesOrderUpdate(status="CANCELLED"),
            mock_user,
        )

    assert exc_info.value.status_code == 400
    assert "operação formal" in exc_info.value.detail
    db.refresh(order)
    assert order.status == "CONFIRMED"


def test_opportunity_quote_synchronous_chain_and_filtering(
    db: Session,
    mock_org: Organization,
    mock_user: User,
    mock_product: Product
):
    # 1. Cria cliente
    customer = sales_service.create_customer(
        db,
        mock_org.id,
        sales_schemas.CustomerCreate(
            name="Cliente Rastreabilidade Teste",
            person_type="PJ",
            document="99887766000155"
        )
    )

    # 2. Cria Oportunidade no CRM
    opp1 = crm_service.create_opportunity(
        db,
        mock_org.id,
        crm_schemas.OpportunityCreate(
            customer_id=customer.id,
            title="Projeto Expansão TI",
            customer_name=customer.name,
            estimated_amount=Decimal("15000.00"),
            stage="QUALIFICATION"
        )
    )
    opp2 = crm_service.create_opportunity(
        db,
        mock_org.id,
        crm_schemas.OpportunityCreate(
            customer_id=customer.id,
            title="Projeto Reforma Elétrica",
            customer_name=customer.name,
            estimated_amount=Decimal("20000.00"),
            stage="QUALIFICATION"
        )
    )

    # 3. Cria Cotação vinculada à Oportunidade 1
    quote1 = sales_service.create_sales_quote(
        db,
        mock_org.id,
        mock_user,
        sales_schemas.SalesQuoteCreate(
            customer_id=customer.id,
            opportunity_id=opp1.id,
            customer_name=customer.name,
            items=[
                sales_schemas.SalesQuoteItemCreate(
                    product_id=mock_product.id,
                    quantity=Decimal("10"),
                    unit_price=Decimal("100.00")
                )
            ]
        )
    )
    assert quote1.opportunity_id == opp1.id

    # 4. Verifica se a oportunidade 1 avançou para PROPOSAL automaticamente
    db.refresh(opp1)
    assert opp1.stage == "PROPOSAL"

    # 5. Verifica se o grafo documental amarrou OPPORTUNITY -> SALES_QUOTE
    chain = documents_service.get_document_chain(
        db,
        organization_id=mock_org.id,
        document_type="OPPORTUNITY",
        native_id=opp1.id
    )
    assert chain.root_document_id is not None
    assert len(chain.documents) == 2
    types = [d.document_type for d in chain.documents]
    assert "OPPORTUNITY" in types
    assert "SALES_QUOTE" in types
    assert any(r.relation_type == "GENERATED_QUOTE" for r in chain.relations)

    # 6. Cria Cotação vinculada à Oportunidade 2
    quote2 = sales_service.create_sales_quote(
        db,
        mock_org.id,
        mock_user,
        sales_schemas.SalesQuoteCreate(
            customer_id=customer.id,
            opportunity_id=opp2.id,
            customer_name=customer.name,
            items=[
                sales_schemas.SalesQuoteItemCreate(
                    product_id=mock_product.id,
                    quantity=Decimal("5"),
                    unit_price=Decimal("200.00")
                )
            ]
        )
    )

    # 7. Valida que list_opportunity_quotations filtra ESTRITAMENTE pela oportunidade informada
    quotes_opp1 = crm_service.list_opportunity_quotations(db, mock_org.id, opp1.id)
    assert len(quotes_opp1) == 1
    assert quotes_opp1[0].id == quote1.id

    quotes_opp2 = crm_service.list_opportunity_quotations(db, mock_org.id, opp2.id)
    assert len(quotes_opp2) == 1
    assert quotes_opp2[0].id == quote2.id


def test_sales_quote_cancellation_with_reason_and_audit(
    db: Session,
    mock_org: Organization,
    mock_user: User,
    mock_product: Product
):
    # 1. Cria cliente e oportunidade
    customer = sales_service.create_customer(
        db,
        mock_org.id,
        sales_schemas.CustomerCreate(
            name="Cliente Cancelamento Teste",
            person_type="PJ",
            document="88776655000144"
        )
    )
    opp = crm_service.create_opportunity(
        db,
        mock_org.id,
        crm_schemas.OpportunityCreate(
            customer_id=customer.id,
            title="Aquisição de Servidores",
            customer_name=customer.name,
            estimated_amount=Decimal("30000.00"),
            stage="QUALIFICATION"
        )
    )

    # 2. Cria Cotação
    quote = sales_service.create_sales_quote(
        db,
        mock_org.id,
        mock_user,
        sales_schemas.SalesQuoteCreate(
            customer_id=customer.id,
            opportunity_id=opp.id,
            customer_name=customer.name,
            items=[
                sales_schemas.SalesQuoteItemCreate(
                    product_id=mock_product.id,
                    quantity=Decimal("3"),
                    unit_price=Decimal("5000.00")
                )
            ]
        )
    )
    assert quote.status == "DRAFT"

    # 3. Cancela Cotação em DRAFT com motivo
    cancelled_quote = sales_service.cancel_sales_quote(
        db,
        quote.id,
        mock_org.id,
        reason="Cliente optou por computação em nuvem em vez de servidores locais",
        current_user=mock_user
    )
    assert cancelled_quote.status == "CANCELLED"
    assert cancelled_quote.cancellation_reason == "Cliente optou por computação em nuvem em vez de servidores locais"

    # 4. Verifica reavaliação de estágio da Oportunidade (move para NEGOTIATION pois não há outras cotações ativas)
    db.refresh(opp)
    assert opp.stage == "NEGOTIATION"

    # 5. Verifica evento de auditoria no grafo transversal
    chain = documents_service.get_document_chain(
        db,
        organization_id=mock_org.id,
        document_type="SALES_QUOTE",
        native_id=quote.id
    )
    assert any(ev.event_type == "CANCELLED" for ev in chain.events)

    # 6. Teste de proteção: não pode cancelar cotação já cancelada
    with pytest.raises(HTTPException) as exc:
        sales_service.cancel_sales_quote(
            db,
            quote.id,
            mock_org.id,
            reason="Tentativa duplicada",
            current_user=mock_user
        )
    assert exc.value.status_code == 409


def test_commercial_settings_drive_quote_defaults_and_discount_limit(
    db: Session,
    mock_org: Organization,
    mock_user: User,
    mock_product: Product,
):
    defaults = sales_service.get_commercial_settings(db, mock_org.id)
    assert defaults.default_payment_terms == "30 DDL"
    assert defaults.quote_validity_days == 15
    assert defaults.maximum_discount_percent == Decimal("100.00")

    configured = sales_service.update_commercial_settings(
        db,
        mock_org.id,
        sales_schemas.CommercialSettingsUpdate(
            default_payment_terms="28 DDL",
            quote_validity_days=20,
            maximum_discount_percent=Decimal("5.00"),
            default_commission_percent=Decimal("3.50"),
        ),
    )
    assert configured.organization_id == mock_org.id

    quote = sales_service.create_sales_quote(
        db,
        mock_org.id,
        mock_user,
        sales_schemas.SalesQuoteCreate(
            customer_name="Cliente com Política",
            items=[
                sales_schemas.SalesQuoteItemCreate(
                    product_id=mock_product.id,
                    quantity=Decimal("2"),
                    unit_price=Decimal("100.00"),
                    discount_amount=Decimal("10.00"),
                )
            ],
        ),
    )
    assert quote.payment_terms == "28 DDL"
    assert quote.valid_until == date.today() + timedelta(days=20)

    with pytest.raises(HTTPException) as discount_error:
        sales_service.create_sales_quote(
            db,
            mock_org.id,
            mock_user,
            sales_schemas.SalesQuoteCreate(
                customer_name="Cliente acima do limite",
                items=[
                    sales_schemas.SalesQuoteItemCreate(
                        product_id=mock_product.id,
                        quantity=Decimal("1"),
                        unit_price=Decimal("100.00"),
                        discount_amount=Decimal("5.01"),
                    )
                ],
            ),
        )
    assert discount_error.value.status_code == 409

    mock_user.is_seller = True
    db.flush()
    goal = sales_service.create_sales_goal(
        db,
        mock_org.id,
        mock_user,
        sales_schemas.SalesGoalCreate(
            user_id=mock_user.id,
            month=8,
            year=2026,
            target_amount=Decimal("10000.00"),
        ),
    )
    assert goal.commission_percent == Decimal("3.50")


def test_commercial_approvals_block_quote_until_all_rules_are_decided(
    db: Session,
    mock_org: Organization,
    mock_user: User,
    mock_product: Product,
):
    mock_product.cost_price = Decimal("80.00")
    sales_service.update_commercial_settings(
        db,
        mock_org.id,
        sales_schemas.CommercialSettingsUpdate(
            maximum_discount_percent=Decimal("20.00"),
            automatic_discount_limit_percent=Decimal("5.00"),
            minimum_margin_percent=Decimal("20.00"),
            maximum_payment_term_days_without_approval=30,
        ),
    )

    quote = sales_service.create_sales_quote(
        db,
        mock_org.id,
        mock_user,
        sales_schemas.SalesQuoteCreate(
            customer_name="Cliente com Exceção Comercial",
            payment_terms="30/60 DDL",
            items=[
                sales_schemas.SalesQuoteItemCreate(
                    product_id=mock_product.id,
                    quantity=Decimal("1"),
                    unit_price=Decimal("100.00"),
                    discount_amount=Decimal("10.00"),
                )
            ],
        ),
    )

    approvals = sales_service.list_commercial_approval_requests(
        db, mock_org.id, "PENDING"
    )
    assert quote.commercial_approval_status == "PENDING"
    assert {item.approval_type for item in approvals} == {
        "DISCOUNT", "MARGIN", "PAYMENT_TERM"
    }
    assert sales_schemas.CommercialApprovalResponse.model_validate(
        approvals[0]
    ).quote.quote_number == quote.quote_number

    with pytest.raises(HTTPException) as approval_block:
        sales_service.update_sales_quote_status(
            db, quote.id, mock_org.id, "APPROVED", mock_user
        )
    assert approval_block.value.status_code == 409

    for approval in approvals:
        sales_service.decide_commercial_approval(
            db,
            approval.id,
            mock_org.id,
            mock_user,
            sales_schemas.CreditApprovalDecision(
                approved=True,
                reason="Exceção validada pela gestão comercial.",
            ),
        )

    assert quote.commercial_approval_status == "APPROVED"
    sales_service.update_sales_quote_status(
        db, quote.id, mock_org.id, "APPROVED", mock_user
    )
    order = sales_service.convert_quote_to_order(
        db, quote.id, mock_org.id, mock_user
    )
    assert order.commercial_approval_status == "APPROVED"

    chain = documents_service.get_document_chain(
        db,
        organization_id=mock_org.id,
        document_type="SALES_QUOTE",
        native_id=quote.id,
    )
    event_types = [event.event_type for event in chain.events]
    assert event_types.count("COMMERCIAL_APPROVAL_REQUESTED") == 3
    assert event_types.count("COMMERCIAL_APPROVED") == 3


def test_direct_order_commercial_approval_blocks_inventory_and_billing(
    db: Session,
    mock_org: Organization,
    mock_user: User,
    mock_product: Product,
):
    from controlb.modules.inventory import service as inventory_service

    order = sales_service.create_sales_order(
        db,
        mock_org.id,
        mock_user,
        sales_schemas.SalesOrderCreate(
            customer_name="Cliente com Desconto Extraordinário",
            items=[
                sales_schemas.SalesOrderItemCreate(
                    product_id=mock_product.id,
                    quantity=Decimal("1"),
                    unit_price=Decimal("100.00"),
                    discount_amount=Decimal("10.00"),
                )
            ],
        ),
    )
    assert order.commercial_approval_status == "PENDING"

    with pytest.raises(HTTPException) as stock_block:
        inventory_service.reserve_sales_order(
            db, mock_org.id, mock_user.id, order.id
        )
    assert stock_block.value.status_code == 409
    assert "aprovação comercial" in stock_block.value.detail

    with pytest.raises(HTTPException) as billing_block:
        sales_service.request_order_billing(
            db, order.id, mock_org.id, mock_user
        )
    assert billing_block.value.status_code == 409

    approval = sales_service.list_commercial_approval_requests(
        db, mock_org.id, "PENDING", "DISCOUNT"
    )[0]
    sales_service.decide_commercial_approval(
        db,
        approval.id,
        mock_org.id,
        mock_user,
        sales_schemas.CreditApprovalDecision(
            approved=True,
            reason="Desconto aprovado para esta negociação.",
        ),
    )
    reservation = inventory_service.reserve_sales_order(
        db, mock_org.id, mock_user.id, order.id
    )
    assert reservation.status == "RESERVED"


def test_credit_exposure_approval_and_operational_blocking(
    db: Session,
    mock_org: Organization,
    mock_user: User,
    mock_product: Product,
):
    customer = sales_service.create_customer(
        db,
        mock_org.id,
        sales_schemas.CustomerCreate(
            name="Cliente com Limite Controlado",
            person_type="PJ",
            document=f"77{uuid.uuid4().int % 10**12:012d}",
            credit_limit=Decimal("500.00"),
        ),
    )

    def create_order(amount: Decimal):
        return sales_service.create_sales_order(
            db,
            mock_org.id,
            mock_user,
            sales_schemas.SalesOrderCreate(
                customer_id=customer.id,
                customer_name=customer.name,
                customer_document=customer.document,
                payment_terms="30 DDL",
                items=[
                    sales_schemas.SalesOrderItemCreate(
                        product_id=mock_product.id,
                        quantity=Decimal("1"),
                        unit_price=amount,
                    )
                ],
            ),
        )

    first_order = create_order(Decimal("300.00"))
    assert first_order.credit_status == "APPROVED"
    assert first_order.credit_excess_amount == Decimal("0.00")

    second_order = create_order(Decimal("300.00"))
    assert second_order.credit_status == "PENDING"
    assert second_order.credit_limit_snapshot == Decimal("500.00")
    assert second_order.credit_exposure_snapshot == Decimal("300.00")
    assert second_order.credit_excess_amount == Decimal("100.00")
    assert second_order.credit_approval is not None
    assert second_order.credit_approval.status == "PENDING"

    analysis = sales_service.get_customer_credit_analysis(
        db,
        mock_org.id,
        customer.id,
        exclude_order_id=second_order.id,
    )
    assert analysis.utilized_amount == Decimal("300.00")
    assert analysis.available_amount == Decimal("200.00")

    with pytest.raises(HTTPException) as billing_block:
        sales_service.request_order_billing(
            db,
            second_order.id,
            mock_org.id,
            mock_user,
        )
    assert billing_block.value.status_code == 409
    assert "liberação de crédito" in billing_block.value.detail

    approval = sales_repository.get_credit_approval_by_order_id(
        db,
        second_order.id,
        mock_org.id,
    )
    decided = sales_service.decide_credit_approval(
        db,
        approval.id,
        mock_org.id,
        mock_user,
        sales_schemas.CreditApprovalDecision(
            approved=True,
            reason="Histórico de pagamento e garantias validados.",
        ),
    )
    assert decided.status == "APPROVED"
    assert decided.order.credit_status == "APPROVED"
    assert sales_schemas.CreditApprovalResponse.model_validate(decided).order.order_number

    billed = sales_service.request_order_billing(
        db,
        second_order.id,
        mock_org.id,
        mock_user,
    )
    assert billed.billing_status == "INVOICED"

    chain = documents_service.get_document_chain(
        db,
        organization_id=mock_org.id,
        document_type="SALES_ORDER",
        native_id=second_order.id,
    )
    event_types = {event.event_type for event in chain.events}
    assert "CREDIT_APPROVAL_REQUESTED" in event_types
    assert "CREDIT_APPROVED" in event_types


def test_identity_contact_partner_odoo_pattern_and_role_filtering(db, mock_org, mock_user):
    """
    Testa o modelo unificado de Contatos (Padrão Odoo res.partner) no Identity:
    1. Cadastro de contato como Cliente (is_customer=True, origin_module='SALES')
    2. Cadastro de contato como Fornecedor (is_supplier=True, origin_module='PURCHASES')
    3. Cadastro de parceiro híbrido (Cliente + Fornecedor)
    4. Filtragem especializada por papéis de módulo (is_customer vs is_supplier)
    5. Busca por múltiplos campos e proteção contra documento duplicado
    """
    from controlb.modules.identity import service as identity_service, schemas as identity_schemas

    # 1. Cria Contato Cliente
    client_contact = identity_service.create_contact(
        db,
        mock_org.id,
        identity_schemas.ContactCreate(
            person_type="PJ",
            document="11222333000199",
            name="Tech Alpha Corp",
            trade_name="Alpha Tech",
            email="contato@alpha.com",
            phone="1199998888",
            is_customer=True,
            is_supplier=False,
            origin_module="SALES",
            notes="Cliente corporativo de Vendas"
        )
    )
    assert client_contact.is_customer is True
    assert client_contact.is_supplier is False
    assert client_contact.origin_module == "SALES"

    # 2. Cria Contato Fornecedor
    supplier_contact = identity_service.create_contact(
        db,
        mock_org.id,
        identity_schemas.ContactCreate(
            person_type="PJ",
            document="99888777000111",
            name="Distribuidora de Peças Beta Ltda",
            email="vendas@betapecas.com",
            is_customer=False,
            is_supplier=True,
            origin_module="PURCHASES",
            notes="Fornecedor de matéria-prima"
        )
    )
    assert supplier_contact.is_customer is False
    assert supplier_contact.is_supplier is True
    assert supplier_contact.origin_module == "PURCHASES"

    # 3. Cria Parceiro Híbrido (Cliente & Fornecedor)
    hybrid_contact = identity_service.create_contact(
        db,
        mock_org.id,
        identity_schemas.ContactCreate(
            person_type="PJ",
            document="55444333000122",
            name="Mega Indústria & Comércio S.A.",
            is_customer=True,
            is_supplier=True,
            origin_module="IDENTITY"
        )
    )
    assert hybrid_contact.is_customer is True
    assert hybrid_contact.is_supplier is True

    # 4. Valida filtragem por papel de módulo
    all_customers = identity_service.list_contacts(db, mock_org.id, is_customer=True)
    customer_ids = {c.id for c in all_customers}
    assert client_contact.id in customer_ids
    assert hybrid_contact.id in customer_ids
    assert supplier_contact.id not in customer_ids  # Fornecedor puro NÃO aparece na lista de clientes!

    all_suppliers = identity_service.list_contacts(db, mock_org.id, is_supplier=True)
    supplier_ids = {s.id for s in all_suppliers}
    assert supplier_contact.id in supplier_ids
    assert hybrid_contact.id in supplier_ids
    assert client_contact.id not in supplier_ids  # Cliente puro NÃO aparece na lista de fornecedores!

    # 5. Valida busca por texto em múltiplos campos
    search_results = identity_service.list_contacts(db, mock_org.id, search="Alpha")
    assert len(search_results) == 1
    assert search_results[0].id == client_contact.id

    # 6. Teste de unicidade de documento por organização
    with pytest.raises(HTTPException) as exc:
        identity_service.create_contact(
            db,
            mock_org.id,
            identity_schemas.ContactCreate(
                name="Duplicata Alpha",
                document="11222333000199"
            )
        )
    assert exc.value.status_code == 409
