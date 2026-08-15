"""
repository.py - Camada de Acesso a Dados (Data Access Layer)

Responsabilidade única: Executar consultas e operações diretas de banco de dados (SQLAlchemy)
para as entidades do módulo Identity (User, Organization, Role).
Não contém regras de negócio (as regras ficam na camada 'service').
"""

import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session
from controlb.modules.identity.models import User, Organization, Role
from controlb.modules.identity.schemas import UserCreate, OrganizationCreate, RoleCreate


# ==============================================================================
# 1. CONSULTAS E OPERAÇÕES DE USUÁRIO (User)
# ==============================================================================

def get_user_by_email(db: Session, email: str) -> User | None:
    """Busca um usuário no banco através do endereço de e-mail (usado no login)."""
    stmt = select(User).where(User.email == email)
    return db.execute(stmt).scalar_one_or_none()


def get_all_users(db: Session) -> list[User]:
    """Retorna a lista completa de todos os usuários cadastrados no banco."""
    stmt = select(User)
    return db.execute(stmt).scalars().all()


def get_user_by_id(db: Session, id: uuid.UUID) -> User | None:
    """Busca um usuário no banco pelo seu ID primário (UUID)."""
    stmt = select(User).where(User.id == id)
    return db.execute(stmt).scalar_one_or_none()


def create_user(db: Session, user_data: UserCreate, hashed_password: str) -> User:
    """Instancia, adiciona e persiste um novo usuário no banco de dados com commit."""
    db_user = User(
        organization_id=user_data.organization_id,
        role_id=user_data.role_id,
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=hashed_password,
    )
    db.add(db_user)
    db.commit()          # Grava as alterações permanentemente no PostgreSQL
    db.refresh(db_user)  # Recarrega o objeto com dados gerados pelo banco (id, created_at)
    return db_user


# ==============================================================================
# 2. CONSULTAS E OPERAÇÕES DE ORGANIZAÇÃO (Organization)
# ==============================================================================

def get_organization_by_name(db: Session, name: str) -> Organization | None:
    """Busca uma organização pelo nome exato."""
    stmt = select(Organization).where(Organization.name == name)
    return db.execute(stmt).scalar_one_or_none()


def get_organization_by_id(db: Session, id: uuid.UUID) -> Organization | None:
    """Busca uma organização pelo seu identificador UUID."""
    stmt = select(Organization).where(Organization.id == id)
    return db.execute(stmt).scalar_one_or_none()


def get_all_organizations(db: Session) -> list[Organization]:
    """Retorna todas as organizações cadastradas no sistema."""
    stmt = select(Organization)
    return db.execute(stmt).scalars().all()


def create_organization(db: Session, organization_data: OrganizationCreate) -> Organization:
    """Cria e salva uma nova organização no banco de dados."""
    db_organization = Organization(
        name=organization_data.name,
    )
    db.add(db_organization)
    db.commit()
    db.refresh(db_organization)
    return db_organization


# ==============================================================================
# 3. CONSULTAS E OPERAÇÕES DE CARGO (Role)
# ==============================================================================

def get_role_by_name(db: Session, name: str) -> Role | None:
    """Busca um cargo pelo seu nome."""
    stmt = select(Role).where(Role.name == name)
    return db.execute(stmt).scalar_one_or_none()


def get_role_by_id(db: Session, id: uuid.UUID) -> Role | None:
    """Busca um cargo pelo seu ID UUID."""
    stmt = select(Role).where(Role.id == id)
    return db.execute(stmt).scalar_one_or_none()


def get_all_roles(db: Session) -> list[Role]:
    """Retorna todos os cargos cadastrados no banco."""
    stmt = select(Role)
    return db.execute(stmt).scalars().all()


def create_role(db: Session, role_data: RoleCreate) -> Role:
    """Cria e persiste um novo cargo no banco de dados."""
    db_role = Role(
        name=role_data.name,
        description=role_data.description,
        is_active=role_data.is_active,
        organization_id=role_data.organization_id,
    )
    db.add(db_role)
    db.commit()
    db.refresh(db_role)
    return db_role