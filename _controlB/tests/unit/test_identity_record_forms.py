"""Regressões dos contratos usados pelas páginas de formulário de Cadastros."""

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from controlb.db import Base
from controlb.modules.identity import models, schemas, service


@pytest.fixture
def db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        yield session


def test_get_user_is_scoped_to_current_organization(db: Session):
    own_org = models.Organization(name="Organização Atual")
    other_org = models.Organization(name="Outra Organização")
    db.add_all([own_org, other_org])
    db.flush()
    user = models.User(
        organization_id=other_org.id,
        email="outside@example.com",
        full_name="Usuário Externo",
        hashed_password="hash",
    )
    db.add(user)
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        service.get_user(db, user.id, own_org.id)

    assert exc_info.value.status_code == 404


def test_update_user_can_remove_role_link(db: Session):
    organization = models.Organization(name="Organização")
    db.add(organization)
    db.flush()
    role = models.Role(organization_id=organization.id, name="Cargo Antigo")
    db.add(role)
    db.flush()
    user = models.User(
        organization_id=organization.id,
        role_id=role.id,
        email="user@example.com",
        full_name="Usuário",
        hashed_password="hash",
    )
    db.add(user)
    db.commit()

    updated = service.update_user(db, user.id, schemas.UserUpdate(role_id=None))

    assert updated.role_id is None


@pytest.mark.parametrize(
    ("getter", "expected_detail"),
    [
        (lambda session, missing_id: service.get_organization(session, missing_id), "Organização não encontrada."),
        (lambda session, missing_id: service.get_role(session, missing_id), "Cargo não encontrado."),
    ],
)
def test_record_getters_return_not_found(db: Session, getter, expected_detail: str):
    with pytest.raises(HTTPException) as exc_info:
        getter(db, uuid.uuid4())

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == expected_detail
