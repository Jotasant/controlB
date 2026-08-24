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


def test_create_customer_pf_and_sync_contact(db: Session):
    """Valida o cadastro de cliente PF com sincronização unificada no Contact (Identity)."""
    org_id = uuid.uuid4()
    org = Organization(id=org_id, name="Empresa Teste")
    db.add(org)
    db.commit()

    payload = sales_schemas.CustomerCreate(
        person_type="PF",
        document="88844433321",
        name="Jefferson S",
        trade_name=None,
        email="jefferson@controlb.com",
        phone="11999998888",
    )

    created_customer = sales_service.create_customer(db, org_id, payload)
    assert created_customer.id is not None
    assert created_customer.person_type == "PF"
    assert created_customer.document == "88844433321"
    assert created_customer.name == "Jefferson S"
    assert created_customer.contact_id is not None

    # Verifica se o Contact correspondente foi criado no Identity com papel is_customer=True
    contact = db.query(Contact).filter(Contact.id == created_customer.contact_id).first()
    assert contact is not None
    assert contact.document == "88844433321"
    assert contact.name == "Jefferson S"
    assert contact.is_customer is True
    assert contact.origin_module == "SALES"


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
