"""Testes unitários e de integração para a infraestrutura transversal do módulo Documents."""

import uuid
from datetime import UTC, datetime
from typing import Generator

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from controlb.db import Base
from controlb.modules.documents import api as documents_api
from controlb.modules.documents import schemas, security, service
from controlb.modules.documents.models import (
    BusinessDocument,
    DocumentEvent,
    DocumentRelation,
    DocumentSequence,
)
from controlb.modules.identity.models import (
    Contact,
    Organization,
    Permission,
    Role,
    User,
    role_permission,
)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            Organization.__table__,
            Permission.__table__,
            Role.__table__,
            role_permission,
            User.__table__,
            Contact.__table__,
            BusinessDocument.__table__,
            DocumentSequence.__table__,
            DocumentRelation.__table__,
            DocumentEvent.__table__,
        ],
    )
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        yield session


def test_document_sequence_generator(db: Session):
    """Testa a geração atômica e independente de sequenciais de negócio por categoria e ano."""
    org_id = uuid.uuid4()
    current_year = datetime.now(UTC).year

    # 1. CRM Lead
    lead1 = service.repository.next_document_number(db, org_id, "crm.lead")
    lead2 = service.repository.next_document_number(db, org_id, "crm.lead")
    assert lead1 == f"LEAD-{current_year}-0001"
    assert lead2 == f"LEAD-{current_year}-0002"

    # 2. Sales Order (PV)
    pv1 = service.repository.next_document_number(db, org_id, "sales.order")
    assert pv1 == f"PV-{current_year}-0001"

    # 3. Purchasing Request (SC) e Order (PC)
    sc1 = service.repository.next_document_number(db, org_id, "purchase.request")
    pc1 = service.repository.next_document_number(db, org_id, "purchase.order")
    assert sc1 == f"SC-{current_year}-0001"
    assert pc1 == f"PC-{current_year}-0001"


def test_create_document_and_lifecycle_events(db: Session):
    """Testa criação centralizada de documento, atualização e transições de status com auditoria."""
    org_id = uuid.uuid4()

    # 1. Cria documento transacional
    doc = service.create_document(
        db,
        organization_id=org_id,
        payload=schemas.DocumentCreate(
            category="sales.order",
            document_type="SALES_ORDER",
            title="Pedido #001 - Hospital Alpha",
            current_status="DRAFT",
            priority="HIGH",
            description="Pedido emergencial de medicamentos",
            tags=["hospitalar", "urgente"],
            origin_module="SALES",
            payload={"total_amount": "15000.00", "items_count": 5},
        ),
    )
    assert doc.id is not None
    assert doc.document_number.startswith("PV-")
    assert doc.current_status == "DRAFT"
    assert doc.tags == ["hospitalar", "urgente"]

    # 2. Valida evento inicial CREATED
    events = service.repository.list_events_by_document(db, doc.id, org_id)
    assert len(events) == 1
    assert events[0].event_type == "CREATED"
    assert events[0].new_status == "DRAFT"

    # 3. Altera status formal com motivo
    updated_doc = service.change_document_status(
        db,
        document_id=doc.id,
        organization_id=org_id,
        new_status="CONFIRMED",
        reason="Crédito aprovado pela diretoria financeira",
    )
    assert updated_doc.current_status == "CONFIRMED"

    # 4. Cancela documento com justificativa
    cancelled_doc = service.change_document_status(
        db,
        document_id=doc.id,
        organization_id=org_id,
        new_status="CANCELLED",
        reason="Cliente solicitou desistência por alteração de orçamento",
    )
    assert cancelled_doc.current_status == "CANCELLED"

    # 5. Verifica timeline completa
    timeline = service.repository.list_events_by_document(db, doc.id, org_id)
    assert len(timeline) == 3
    assert timeline[1].event_type == "STATUS_CHANGED"
    assert timeline[1].new_status == "CONFIRMED"
    assert timeline[2].event_type == "CANCELLED"
    assert timeline[2].event_metadata.get("reason") == "Cliente solicitou desistência por alteração de orçamento"


def test_document_tree_and_typed_relations(db: Session):
    """
    Testa o grafo de rastreabilidade (Tree) completo:
    Lead -> Oportunidade -> Cotação -> Pedido de Venda
    """
    org_id = uuid.uuid4()

    # 1. Cria Lead
    lead = service.create_document(
        db,
        organization_id=org_id,
        payload=schemas.DocumentCreate(
            category="crm.lead",
            document_type="LEAD",
            title="Lead: Dr. Roberto Santos",
            current_status="QUALIFIED",
            origin_module="CRM",
        ),
    )

    # 2. Cria Oportunidade
    opp = service.create_document(
        db,
        organization_id=org_id,
        payload=schemas.DocumentCreate(
            category="crm.opportunity",
            document_type="OPPORTUNITY",
            title="Oportunidade: Fornecimento Anual Clínica",
            current_status="PROPOSAL",
            origin_module="CRM",
        ),
    )
    service.relate_documents(
        db,
        organization_id=org_id,
        parent_document=lead,
        child_document=opp,
        relation_type="originated_from",
    )

    # 3. Cria Cotação
    quote = service.create_document(
        db,
        organization_id=org_id,
        payload=schemas.DocumentCreate(
            category="sales.quotation",
            document_type="SALES_QUOTE",
            title="Proposta Comercial #1029",
            current_status="APPROVED",
            origin_module="SALES",
        ),
    )
    service.relate_documents(
        db,
        organization_id=org_id,
        parent_document=opp,
        child_document=quote,
        relation_type="generated",
    )

    # 4. Cria Pedido de Venda
    order = service.create_document(
        db,
        organization_id=org_id,
        payload=schemas.DocumentCreate(
            category="sales.order",
            document_type="SALES_ORDER",
            title="Pedido de Venda PV-001",
            current_status="CONFIRMED",
            origin_module="SALES",
        ),
    )
    service.relate_documents(
        db,
        organization_id=org_id,
        parent_document=quote,
        child_document=order,
        relation_type="generated",
    )

    # 5. Consulta árvore a partir da Oportunidade
    opp_tree = service.get_document_tree(db, organization_id=org_id, document_id=opp.id)
    assert len(opp_tree.origin) == 1
    assert opp_tree.origin[0].id == lead.id
    assert len(opp_tree.derived) == 1
    assert opp_tree.derived[0].id == quote.id

    # 6. Consulta árvore a partir do Pedido de Venda
    order_tree = service.get_document_tree(db, organization_id=org_id, document_id=order.id)
    assert len(order_tree.derived) == 0
    assert len(order_tree.previous) == 1
    assert order_tree.previous[0].id == quote.id


def test_transversal_document_search(db: Session):
    """Testa o motor de busca transversal com múltiplos filtros (categoria, módulo, status, termo)."""
    org_id = uuid.uuid4()

    # Cria documentos em diferentes categorias
    service.create_document(
        db,
        org_id,
        schemas.DocumentCreate(
            category="crm.lead",
            document_type="LEAD",
            title="Lead TechCorp",
            current_status="NEW",
            origin_module="CRM",
        ),
    )
    service.create_document(
        db,
        org_id,
        schemas.DocumentCreate(
            category="sales.order",
            document_type="SALES_ORDER",
            title="Pedido TechCorp #001",
            current_status="CONFIRMED",
            origin_module="SALES",
        ),
    )
    service.create_document(
        db,
        org_id,
        schemas.DocumentCreate(
            category="purchase.order",
            document_type="PURCHASE_ORDER",
            title="Ordem de Compra Insumos",
            current_status="ISSUED",
            origin_module="PURCHASING",
        ),
    )

    # 1. Filtro por módulo
    crm_docs = service.list_documents(db, org_id, schemas.DocumentFilterParams(origin_module="CRM"))
    assert len(crm_docs) == 1
    assert crm_docs[0].title == "Lead TechCorp"

    # 2. Filtro por categoria
    sales_docs = service.list_documents(db, org_id, schemas.DocumentFilterParams(category="sales.order"))
    assert len(sales_docs) == 1
    assert sales_docs[0].title == "Pedido TechCorp #001"

    # 3. Busca textual
    search_docs = service.list_documents(db, org_id, schemas.DocumentFilterParams(search="TechCorp"))
    assert len(search_docs) == 2


def test_document_chain_is_idempotent_and_keeps_timeline(db: Session):
    organization_id = uuid.uuid4()
    actor_id = None
    quote_native_id = uuid.uuid4()
    order_native_id = uuid.uuid4()

    quote = service.ensure_document(
        db,
        organization_id=organization_id,
        document_type="sales_quote",
        native_id=quote_native_id,
        document_number="ORC-0001",
        current_status="APPROVED",
        created_by_id=actor_id,
    )
    same_quote = service.ensure_document(
        db,
        organization_id=organization_id,
        document_type="SALES_QUOTE",
        native_id=quote_native_id,
        document_number="ORC-0001",
        current_status="APPROVED",
        created_by_id=actor_id,
    )
    order = service.ensure_document(
        db,
        organization_id=organization_id,
        document_type="SALES_ORDER",
        native_id=order_native_id,
        document_number="PED-0001",
        current_status="CONFIRMED",
        created_by_id=actor_id,
    )

    first_relation = service.relate_documents(
        db,
        organization_id=organization_id,
        parent_document=quote,
        child_document=order,
        relation_type="converted_to",
    )
    same_relation = service.relate_documents(
        db,
        organization_id=organization_id,
        parent_document=quote,
        child_document=order,
        relation_type="CONVERTED_TO",
    )
    first_event = service.record_event(
        db,
        organization_id=organization_id,
        document=quote,
        event_type="converted",
        previous_status="APPROVED",
        new_status="CONVERTED",
        idempotency_key=f"quote:{quote_native_id}:converted",
    )
    same_event = service.record_event(
        db,
        organization_id=organization_id,
        document=quote,
        event_type="CONVERTED",
        previous_status="APPROVED",
        new_status="CONVERTED",
        idempotency_key=f"quote:{quote_native_id}:converted",
    )
    db.commit()

    chain = service.get_document_chain(
        db,
        organization_id=organization_id,
        document_type="SALES_QUOTE",
        native_id=quote_native_id,
    )

    assert same_quote.id == quote.id
    assert same_relation.id == first_relation.id
    assert same_event.id == first_event.id
    assert quote.current_status == "CONVERTED"
    assert {item.native_id for item in chain.documents} == {quote_native_id, order_native_id}
    assert len(chain.relations) == 1
    assert len(chain.events) == 1


def test_documents_from_different_organizations_cannot_be_related(db: Session):
    first_org = uuid.uuid4()
    second_org = uuid.uuid4()
    first = service.ensure_document(
        db,
        organization_id=first_org,
        document_type="SALES_QUOTE",
        native_id=uuid.uuid4(),
        document_number="ORC-A",
        current_status="APPROVED",
    )
    second = service.ensure_document(
        db,
        organization_id=second_org,
        document_type="SALES_ORDER",
        native_id=uuid.uuid4(),
        document_number="PED-B",
        current_status="CONFIRMED",
    )

    with pytest.raises(HTTPException) as exc_info:
        service.relate_documents(
            db,
            organization_id=first_org,
            parent_document=first,
            child_document=second,
            relation_type="CONVERTED_TO",
        )

    assert exc_info.value.status_code == 400


def test_document_cannot_be_related_to_itself(db: Session):
    organization_id = uuid.uuid4()
    document = service.ensure_document(
        db,
        organization_id=organization_id,
        document_type="SALES_QUOTE",
        native_id=uuid.uuid4(),
        document_number="ORC-SELF",
        current_status="DRAFT",
    )

    with pytest.raises(HTTPException) as exc_info:
        service.relate_documents(
            db,
            organization_id=organization_id,
            parent_document=document,
            child_document=document,
            relation_type="CONVERTED_TO",
        )

    assert exc_info.value.status_code == 400


def _user_with_permissions(organization_id: uuid.UUID, *permission_codes: str) -> User:
    role = Role(
        id=uuid.uuid4(),
        organization_id=organization_id,
        name="Leitor documental",
        is_active=True,
    )
    role.permissions = [
        Permission(
            id=uuid.uuid4(),
            code=code,
            name=code,
            module=code.partition(":")[0],
            is_active=True,
        )
        for code in permission_codes
    ]
    return User(
        id=uuid.uuid4(),
        organization_id=organization_id,
        email=f"{uuid.uuid4()}@example.com",
        full_name="Leitor documental",
        hashed_password="not-used",
        is_active=True,
        role=role,
    )


def test_document_permission_policy_maps_all_integrated_types():
    assert security.required_view_permission("CRM_INTERACTION") == "crm:view"
    assert security.required_view_permission("INVOICE") == "billing:view"
    assert security.required_view_permission("BILLING_REQUEST") == "billing:view"
    assert security.required_view_permission("INVENTORY_RECEIPT") == "products:view"
    assert security.required_view_permission("INVENTORY_TRANSFER") == "products:view"
    assert security.required_view_permission("REPLENISHMENT") == "purchasing:view"
    assert security.required_view_permission("PAYABLE") == "finance:payables"
    assert security.required_view_permission("UNKNOWN_TYPE") == "documents:view"
    assert security.can_view_document_type("SALES_ORDER", {"sales:view"})
    assert not security.can_view_document_type("INVOICE", {"sales:view"})
    assert security.can_view_document_type("INVOICE", {"*:*"})


def test_document_api_filters_list_before_pagination_and_blocks_detail(db: Session):
    organization_id = uuid.uuid4()
    sales_document = service.ensure_document(
        db,
        organization_id=organization_id,
        category="sales.order",
        document_type="SALES_ORDER",
        native_id=uuid.uuid4(),
        document_number="PED-AUTH-001",
        current_status="CONFIRMED",
    )
    finance_document = service.ensure_document(
        db,
        organization_id=organization_id,
        category="finance.payable",
        document_type="PAYABLE",
        native_id=uuid.uuid4(),
        document_number="PAG-AUTH-001",
        current_status="PENDING",
    )
    sales_user = _user_with_permissions(organization_id, "sales:view")

    visible_documents = documents_api.list_documents(
        category=None,
        origin_module=None,
        current_status=None,
        search=None,
        responsible_id=None,
        limit=1,
        offset=0,
        db=db,
        current_user=sales_user,
    )

    assert [document.id for document in visible_documents] == [sales_document.id]
    with pytest.raises(HTTPException) as exc_info:
        documents_api.get_document(finance_document.id, db=db, current_user=sales_user)
    assert exc_info.value.status_code == 403
    assert "finance:payables" in exc_info.value.detail


def test_document_api_removes_unauthorized_nodes_relations_and_events(db: Session):
    organization_id = uuid.uuid4()
    sales_document = service.ensure_document(
        db,
        organization_id=organization_id,
        category="sales.order",
        document_type="SALES_ORDER",
        native_id=uuid.uuid4(),
        document_number="PED-CHAIN-001",
        current_status="CONFIRMED",
    )
    invoice_document = service.ensure_document(
        db,
        organization_id=organization_id,
        category="billing.invoice",
        document_type="INVOICE",
        native_id=uuid.uuid4(),
        document_number="FAT-CHAIN-001",
        current_status="ISSUED",
    )
    service.relate_documents(
        db,
        organization_id=organization_id,
        parent_document=sales_document,
        child_document=invoice_document,
        relation_type="INVOICED_BY",
    )
    service.record_event(
        db,
        organization_id=organization_id,
        document=invoice_document,
        event_type="ISSUED",
    )
    sales_user = _user_with_permissions(organization_id, "sales:view")

    chain = documents_api.get_document_chain(
        "SALES_ORDER",
        sales_document.native_id,
        db=db,
        current_user=sales_user,
    )
    tree = documents_api.get_document_tree(
        sales_document.id,
        db=db,
        current_user=sales_user,
    )

    assert [document.id for document in chain.documents] == [sales_document.id]
    assert chain.relations == []
    assert {event.document_id for event in chain.events} <= {sales_document.id}
    assert tree.related == []
