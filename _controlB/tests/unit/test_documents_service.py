"""Testes isolados da fundação transversal de documentos relacionados."""

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from controlb.db import Base
from controlb.modules.documents import service
from controlb.modules.documents.models import BusinessDocument, DocumentEvent, DocumentRelation
from controlb.modules.identity.models import (
    Contact,
    Organization,
    Permission,
    Role,
    User,
    role_permission,
)


@pytest.fixture
def db() -> Session:
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
            DocumentRelation.__table__,
            DocumentEvent.__table__,
        ],
    )
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        yield session


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
