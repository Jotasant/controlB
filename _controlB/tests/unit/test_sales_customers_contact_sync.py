"""Testes unitários do serviço de clientes em Vendas com sincronização unificada de Contatos em Identity."""

import uuid
from typing import Generator

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from controlb.db import Base
from controlb.modules.identity.models import (
    Contact,
    Organization,
    Permission,
    Role,
    User,
    role_permission,
)
from controlb.modules.sales import models as sales_models, schemas as sales_schemas, service as sales_service


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        yield session


def test_create_customer_references_identity_without_implicit_contact(db: Session):
    org = Organization(name="Empresa Teste")
    db.add(org)
    db.flush()
    contact = Contact(organization_id=org.id, name="Contato preservado",
                      email="jefferson@example.com", phone="11999998888")
    db.add(contact)
    db.commit()

    payload = sales_schemas.CustomerCreate(
        person_type="PF", document="88844433321", name="Nome comercial",
        contact_id=contact.id,
    )
    customer = sales_service.create_customer(db, org.id, payload)
    assert customer.contact_id == contact.id
    assert contact.name == "Contato preservado"
    assert customer.email is None  # Legacy column is never populated.
    assert sales_schemas.CustomerResponse.model_validate(customer).email == contact.email
    assert db.query(Contact).count() == 1
    with pytest.raises(HTTPException) as exc:
        sales_service.update_customer(db, customer.id, org.id,
                                      sales_schemas.CustomerUpdate(phone="11999998888"))
    assert exc.value.status_code == 422


def test_list_and_search_customers(db: Session):
    """Valida listagem e filtro de clientes."""
    org_id = uuid.uuid4()

    sales_service.create_customer(
        db,
        org_id,
        sales_schemas.CustomerCreate(
            person_type="PJ",
            document="11222333000199",
            name="Hospital Alpha S/A",
            trade_name="Hospital Alpha",
        ),
    )
    sales_service.create_customer(
        db,
        org_id,
        sales_schemas.CustomerCreate(
            person_type="PF",
            document="88844433321",
            name="Jefferson Santos",
        ),
    )

    # 1. Listagem completa
    all_customers = sales_service.list_customers(db, org_id)
    assert len(all_customers) == 2

    # 2. Busca por termo de CPF
    search_cpf = sales_service.list_customers(db, org_id, search="888444")
    assert len(search_cpf) == 1
    assert search_cpf[0].name == "Jefferson Santos"

    # 3. Busca por nome
    search_name = sales_service.list_customers(db, org_id, search="Hospital")
    assert len(search_name) == 1
    assert search_name[0].name == "Hospital Alpha S/A"


def test_create_customer_duplicate_document_fails(db: Session):
    """Valida que cadastro duplicado de CPF/CNPJ dentro da mesma organização é rejeitado com HTTP 400."""
    org_id = uuid.uuid4()

    payload = sales_schemas.CustomerCreate(
        person_type="PF",
        document="88844433321",
        name="Jefferson S",
    )
    sales_service.create_customer(db, org_id, payload)

    with pytest.raises(HTTPException) as exc_info:
        sales_service.create_customer(db, org_id, payload)

    assert exc_info.value.status_code == 400
    assert "Já existe um cliente cadastrado com o documento" in exc_info.value.detail
