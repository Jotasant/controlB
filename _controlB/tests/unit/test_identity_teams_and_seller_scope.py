"""
tests/unit/test_identity_teams_and_seller_scope.py - Testes de Equipes Multimodulares e Escopo de Vendedor/Gestor
"""

import uuid
from decimal import Decimal
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from controlb.db import Base
from controlb.modules.identity import models as id_models, schemas as id_schemas, service as id_service
from controlb.modules.crm import models as crm_models, schemas as crm_schemas, service as crm_service
from controlb.modules.sales import service as sales_service


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


def test_team_creation_and_member_assignment(db: Session):
    """Testa criação de equipe de vendas, vinculação de líder e membros."""
    org = id_models.Organization(name="Empresa Teste")
    db.add(org)
    db.commit()

    gestor = id_models.User(
        organization_id=org.id,
        email="gestor@empresa.com",
        full_name="Gestor Comercial",
        hashed_password="hash",
        is_seller=False
    )
    vendedor_1 = id_models.User(
        organization_id=org.id,
        email="vendedor1@empresa.com",
        full_name="Vendedor Um",
        hashed_password="hash",
        is_seller=True
    )
    vendedor_2 = id_models.User(
        organization_id=org.id,
        email="vendedor2@empresa.com",
        full_name="Vendedor Dois",
        hashed_password="hash",
        is_seller=True
    )
    db.add_all([gestor, vendedor_1, vendedor_2])
    db.commit()

    # Criação de Equipe de Vendas
    team_data = id_schemas.TeamCreate(
        name="Equipe Vendas Sul",
        code="EQ-SUL",
        module_category="SALES",
        leader_id=gestor.id,
        member_ids=[vendedor_1.id, vendedor_2.id]
    )
    created_team = id_service.create_team(db, org.id, team_data)
    assert created_team.id is not None
    assert created_team.name == "Equipe Vendas Sul"
    assert created_team.module_category == "SALES"
    assert created_team.leader_id == gestor.id
    assert len(created_team.members) == 3
    assert gestor.id in {member.id for member in created_team.members}

    # Lista vendedores ativos e verifica vínculo da equipe
    sellers = sales_service.list_sellers(db, org.id)
    assert len(sellers) == 2
    assert any(s.full_name == "Vendedor Um" and s.sales_team_name == "Equipe Vendas Sul" for s in sellers)


def test_row_level_scope_for_seller_and_manager(db: Session):
    """
    Testa o escopo de visibilidade:
    - Vendedor 1 só visualiza suas oportunidades.
    - Gestor visualiza as oportunidades de todos os membros da sua equipe.
    - Administrador visualiza todas as oportunidades da organização.
    """
    org = id_models.Organization(name="Empresa Escopo")
    db.add(org)
    db.commit()

    admin_role = id_models.Role(organization_id=org.id, name="Administrador")
    seller_role = id_models.Role(organization_id=org.id, name="Vendedor")
    manager_role = id_models.Role(organization_id=org.id, name="Supervisor")
    db.add_all([admin_role, seller_role, manager_role])
    db.commit()

    admin_user = id_models.User(
        organization_id=org.id,
        role_id=admin_role.id,
        email="admin@empresa.com",
        full_name="Diretor Admin",
        hashed_password="hash"
    )
    gestor_user = id_models.User(
        organization_id=org.id,
        role_id=manager_role.id,
        email="lider@empresa.com",
        full_name="Líder Equipe",
        hashed_password="hash"
    )
    vendedor_a = id_models.User(
        organization_id=org.id,
        role_id=seller_role.id,
        email="vendedor_a@empresa.com",
        full_name="Vendedor A",
        hashed_password="hash",
        is_seller=True
    )
    vendedor_b = id_models.User(
        organization_id=org.id,
        role_id=seller_role.id,
        email="vendedor_b@empresa.com",
        full_name="Vendedor B",
        hashed_password="hash",
        is_seller=True
    )
    db.add_all([admin_user, gestor_user, vendedor_a, vendedor_b])
    db.commit()

    # Cria equipe com Gestor liderando Vendedor A
    team_data = id_schemas.TeamCreate(
        name="Equipe Alpha",
        module_category="SALES",
        leader_id=gestor_user.id,
        member_ids=[vendedor_a.id]
    )
    id_service.create_team(db, org.id, team_data)

    # Cria Oportunidade do Vendedor A
    opp_a = crm_service.create_opportunity(
        db,
        org.id,
        crm_schemas.OpportunityCreate(
            title="Contrato Alpha",
            customer_name="Cliente A",
            estimated_amount=Decimal("10000.00"),
            assigned_to_id=vendedor_a.id
        )
    )

    # Cria Oportunidade do Vendedor B (Outra equipe/solitário)
    opp_b = crm_service.create_opportunity(
        db,
        org.id,
        crm_schemas.OpportunityCreate(
            title="Contrato Beta",
            customer_name="Cliente B",
            estimated_amount=Decimal("20000.00"),
            assigned_to_id=vendedor_b.id
        )
    )

    # 1. Consulta como Vendedor A: apenas oportunidade Alpha
    opps_a = crm_service.list_opportunities(db, org.id, current_user=vendedor_a)
    assert len(opps_a) == 1
    assert opps_a[0].title == "Contrato Alpha"

    # 2. Consulta como Gestor da Equipe Alpha: visualiza oportunidade Alpha (seu liderado)
    opps_gestor = crm_service.list_opportunities(db, org.id, current_user=gestor_user)
    assert len(opps_gestor) == 1
    assert opps_gestor[0].title == "Contrato Alpha"

    # 3. Consulta como Administrador: visualiza todas as oportunidades da organização
    opps_admin = crm_service.list_opportunities(db, org.id, current_user=admin_user)
    assert len(opps_admin) == 2


def test_team_contract_rejects_client_supplied_organization():
    """O tenant deve vir da autenticacao, nunca do corpo enviado pelo navegador."""
    with pytest.raises(ValidationError):
        id_schemas.TeamCreate(
            organization_id=uuid.uuid4(),
            name="Equipe indevida",
        )


def test_team_rejects_duplicates_and_cross_tenant_members(db: Session):
    org = id_models.Organization(name="Empresa Principal")
    other_org = id_models.Organization(name="Outra Empresa")
    db.add_all([org, other_org])
    db.commit()
    external_user = id_models.User(
        organization_id=other_org.id,
        email="externo@empresa.com",
        full_name="Usuario Externo",
        hashed_password="hash",
    )
    db.add(external_user)
    db.commit()

    id_service.create_team(
        db,
        org.id,
        id_schemas.TeamCreate(name="Equipe Norte", code="NORTE"),
    )

    with pytest.raises(HTTPException) as duplicate_error:
        id_service.create_team(
            db,
            org.id,
            id_schemas.TeamCreate(name="equipe norte", code="OUTRO"),
        )
    assert duplicate_error.value.status_code == 409

    with pytest.raises(HTTPException) as tenant_error:
        id_service.create_team(
            db,
            org.id,
            id_schemas.TeamCreate(
                name="Equipe Invalida",
                leader_id=external_user.id,
            ),
        )
    assert tenant_error.value.status_code == 400


def test_team_leader_lifecycle_and_candidates_are_tenant_scoped(db: Session):
    org = id_models.Organization(name="Empresa Equipes")
    other_org = id_models.Organization(name="Empresa Externa")
    db.add_all([org, other_org])
    db.commit()
    leader = id_models.User(
        organization_id=org.id,
        email="lider@equipes.com",
        full_name="Lider Ativo",
        hashed_password="hash",
    )
    inactive = id_models.User(
        organization_id=org.id,
        email="inativo@equipes.com",
        full_name="Usuario Inativo",
        hashed_password="hash",
        is_active=False,
    )
    external = id_models.User(
        organization_id=other_org.id,
        email="externo@equipes.com",
        full_name="Usuario Externo",
        hashed_password="hash",
    )
    db.add_all([leader, inactive, external])
    db.commit()

    team = id_service.create_team(
        db,
        org.id,
        id_schemas.TeamCreate(name="Equipe Comercial", leader_id=leader.id),
    )
    assert leader.id in {member.id for member in team.members}

    with pytest.raises(HTTPException) as leader_error:
        id_service.remove_team_member(db, team.id, org.id, leader.id)
    assert leader_error.value.status_code == 409

    updated = id_service.update_team(
        db,
        team.id,
        org.id,
        id_schemas.TeamUpdate(leader_id=None),
    )
    assert updated.leader_id is None
    updated = id_service.remove_team_member(db, team.id, org.id, leader.id)
    assert leader.id not in {member.id for member in updated.members}

    candidates = id_service.list_team_candidates(db, org.id)
    assert [candidate.id for candidate in candidates] == [leader.id]
