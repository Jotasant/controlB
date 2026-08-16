"""
repository.py - Camada de Acesso a Dados (Data Access Layer)

Responsabilidade única: Executar consultas e operações diretas de banco de dados (SQLAlchemy)
para as entidades do módulo Identity (User, Organization, Role, Permission).
Não contém regras de negócio (as regras ficam na camada 'service').
"""

import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session
from controlb.modules.identity.models import User, Organization, Role, Permission
from controlb.modules.identity.schemas import (
    UserCreate, UserUpdate,
    OrganizationCreate, OrganizationUpdate,
    RoleCreate, RoleUpdate
)


# ==============================================================================
# 1. CONSULTAS E OPERAÇÕES DE PERMISSÃO (Permission)
# ==============================================================================

def get_all_permissions(db: Session) -> list[Permission]:
    """Retorna todas as permissões cadastradas no catálogo do sistema."""
    stmt = select(Permission).order_by(Permission.module, Permission.code)
    return db.execute(stmt).scalars().all()


def get_permissions_by_ids(db: Session, permission_ids: list[uuid.UUID]) -> list[Permission]:
    """Busca uma lista de objetos Permission a partir de seus IDs UUID."""
    if not permission_ids:
        return []
    stmt = select(Permission).where(Permission.id.in_(permission_ids))
    return db.execute(stmt).scalars().all()


def get_permission_by_code(db: Session, code: str) -> Permission | None:
    """Busca uma permissão pelo seu código único (ex: 'users:view')."""
    stmt = select(Permission).where(Permission.code == code)
    return db.execute(stmt).scalar_one_or_none()


def create_permission_if_not_exists(db: Session, code: str, name: str, module: str, description: str | None = None) -> Permission:
    """Cria uma permissão padrão caso ela ainda não exista no banco."""
    existing = get_permission_by_code(db, code)
    if not existing:
        perm = Permission(code=code, name=name, module=module, description=description)
        db.add(perm)
        db.commit()
        db.refresh(perm)
        return perm
    return existing


# ==============================================================================
# 2. CONSULTAS E OPERAÇÕES DE USUÁRIO (User)
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
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user(db: Session, db_user: User, user_data: UserUpdate, hashed_password: str | None = None) -> User:
    """Atualiza os campos do perfil do usuário e desvincula se necessário."""
    if user_data.full_name is not None:
        db_user.full_name = user_data.full_name
    if user_data.email is not None:
        db_user.email = user_data.email
    if user_data.organization_id is not None:
        db_user.organization_id = user_data.organization_id
    if user_data.role_id is not None:
        db_user.role_id = user_data.role_id
    if user_data.is_active is not None:
        db_user.is_active = user_data.is_active
    if hashed_password:
        db_user.hashed_password = hashed_password

    db.commit()
    db.refresh(db_user)
    return db_user


def delete_user(db: Session, db_user: User) -> None:
    """Remove permanentemente o usuário do banco de dados (exclusão/desvinculação)."""
    db.delete(db_user)
    db.commit()


# ==============================================================================
# 3. CONSULTAS E OPERAÇÕES DE ORGANIZAÇÃO (Organization)
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


def delete_organization(db: Session, db_org: Organization) -> None:
    """Exclui a organização do banco de dados."""
    db.delete(db_org)
    db.commit()


# ==============================================================================
# 4. CONSULTAS E OPERAÇÕES DE CARGO (Role)
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
    """Retorna todos os cargos cadastrados no banco com suas permissões."""
    stmt = select(Role)
    return db.execute(stmt).scalars().all()


def create_role(db: Session, role_data: RoleCreate, permissions: list[Permission] = []) -> Role:
    """Cria e persiste um novo cargo com sua lista de permissões associadas."""
    db_role = Role(
        name=role_data.name,
        description=role_data.description,
        is_active=role_data.is_active,
        organization_id=role_data.organization_id,
        permissions=permissions
    )
    db.add(db_role)
    db.commit()
    db.refresh(db_role)
    return db_role


def update_role(db: Session, db_role: Role, role_data: RoleUpdate, permissions: list[Permission] | None = None) -> Role:
    """Atualiza dados do cargo e sincroniza a lista de permissões associadas."""
    if role_data.name is not None:
        db_role.name = role_data.name
    if role_data.description is not None:
        db_role.description = role_data.description
    if role_data.is_active is not None:
        db_role.is_active = role_data.is_active
    if permissions is not None:
        db_role.permissions = permissions

    db.commit()
    db.refresh(db_role)
    return db_role


def delete_role(db: Session, db_role: Role) -> None:
    """Exclui o cargo do banco de dados."""
    db.delete(db_role)
    db.commit()