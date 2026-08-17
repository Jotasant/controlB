"""
service.py - Camada de Regras de Negócio de Identidade (Usuários, Cargos, Organizações)

Responsabilidades:
1. Validação de regras de negócio de Usuários (criação, edição, exclusão, verificação de e-mail).
2. Validação de regras de negócio de Organizações (criação e exclusão).
3. Validação de regras de negócio de Cargos e Matriz de Permissões RBAC.
4. Re-exportação de utilitários de segurança e autenticação a partir de 'security.py'.
"""

import uuid
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from controlb.modules.identity import repository
from controlb.modules.identity.models import User
from controlb.modules.identity.schemas import (
    UserCreate, UserUpdate,
    OrganizationCreate, OrganizationUpdate,
    RoleCreate, RoleUpdate
)

# Re-exporta utilitários e guards de segurança a partir de security.py
from controlb.modules.identity.security import (
    DEFAULT_PERMISSIONS,
    seed_default_permissions,
    verify_password,
    get_password_hash,
    create_access_token,
    get_user_permissions,
    get_current_user,
    require_permission,
    oauth2_scheme,
    password_hash,
)

__all__ = [
    "DEFAULT_PERMISSIONS",
    "seed_default_permissions",
    "verify_password",
    "get_password_hash",
    "create_access_token",
    "get_user_permissions",
    "get_current_user",
    "require_permission",
    "oauth2_scheme",
    "create_new_user",
    "update_user",
    "delete_user",
    "create_new_organization",
    "delete_organization",
    "create_new_role",
    "update_role",
    "delete_role",
]


# ==============================================================================
# 1. REGRAS DE NEGÓCIO DE USUÁRIOS
# ==============================================================================

def create_new_user(db: Session, user_data: UserCreate):
    """Regra de negócio para criação de novo usuário."""
    existing_user = repository.get_user_by_email(db, email=user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este e-mail já está em uso."
        )
    
    hashed_pwd = get_password_hash(user_data.password)

    existing_organization = repository.get_organization_by_id(db, id=user_data.organization_id)
    if not existing_organization:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organização não encontrada."
        )
        
    if user_data.role_id:
        existing_role = repository.get_role_by_id(db, id=user_data.role_id)
        if not existing_role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cargo não encontrado."
            )
            
    return repository.create_user(db, user_data, hashed_pwd)


def update_user(db: Session, user_id: uuid.UUID, user_data: UserUpdate):
    """Regra de negócio para edição de perfil do usuário."""
    db_user = repository.get_user_by_id(db, id=user_id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado."
        )

    if user_data.email and user_data.email != db_user.email:
        existing = repository.get_user_by_email(db, email=user_data.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este e-mail já está em uso por outro usuário."
            )

    if user_data.organization_id:
        existing_org = repository.get_organization_by_id(db, id=user_data.organization_id)
        if not existing_org:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organização informada não existe."
            )

    if user_data.role_id:
        existing_role = repository.get_role_by_id(db, id=user_data.role_id)
        if not existing_role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cargo informado não existe."
            )

    hashed_pwd = get_password_hash(user_data.password) if user_data.password else None

    return repository.update_user(db, db_user, user_data, hashed_pwd)


def delete_user(db: Session, user_id: uuid.UUID, current_user_id: uuid.UUID):
    """Regra de negócio: Exclui e desvincula o usuário (impede autoexclusão)."""
    if user_id == current_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Você não pode excluir sua própria conta enquanto estiver logado."
        )

    db_user = repository.get_user_by_id(db, id=user_id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado."
        )

    repository.delete_user(db, db_user)
    return {"message": "Usuário excluído com sucesso."}


# ==============================================================================
# 2. REGRAS DE NEGÓCIO DE ORGANIZAÇÃO
# ==============================================================================

def create_new_organization(db: Session, organization_data: OrganizationCreate):
    """Regra de negócio: Impede cadastro de organizações com nomes duplicados."""
    existing_organization = repository.get_organization_by_name(db, name=organization_data.name)
    if existing_organization:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta organização já existe."
        )
    return repository.create_organization(db, organization_data)


def update_organization(db: Session, organization_id: uuid.UUID, organization_data: OrganizationUpdate):
    """Regra de negócio: Atualiza organização validando duplicidade de nomes."""
    db_org = repository.get_organization_by_id(db, id=organization_id)
    if not db_org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organização não encontrada."
        )
    if organization_data.name and organization_data.name.strip() != db_org.name:
        existing = repository.get_organization_by_name(db, name=organization_data.name.strip())
        if existing and existing.id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Já existe outra organização cadastrada com este nome."
            )
    return repository.update_organization(db, db_org, organization_data)


def delete_organization(db: Session, organization_id: uuid.UUID):
    """Exclui a organização do banco e limpa dependências em cascata."""
    db_org = repository.get_organization_by_id(db, id=organization_id)
    if not db_org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organização não encontrada."
        )
    repository.delete_organization(db, db_org)
    return {"message": "Organização excluída com sucesso."}


def bulk_delete_organizations(db: Session, org_ids: list[uuid.UUID]):
    """Exclui múltiplas organizações em lote."""
    count = repository.bulk_delete_organizations(db, org_ids)
    return {"message": f"{count} organização(ões) excluída(s) com sucesso.", "deleted_count": count}


def bulk_delete_users(db: Session, user_ids: list[uuid.UUID], current_user_id: uuid.UUID):
    """Exclui múltiplos usuários em lote, impedindo autoexclusão."""
    count = repository.bulk_delete_users(db, user_ids, current_user_id)
    return {"message": f"{count} usuário(s) excluído(s) com sucesso.", "deleted_count": count}


def bulk_delete_roles(db: Session, role_ids: list[uuid.UUID]):
    """Exclui múltiplos cargos em lote."""
    count = repository.bulk_delete_roles(db, role_ids)
    return {"message": f"{count} cargo(s) excluído(s) com sucesso.", "deleted_count": count}


# ==============================================================================
# 3. REGRAS DE NEGÓCIO DE CARGOS E PERMISSÕES (RBAC)
# ==============================================================================

def create_new_role(db: Session, role_data: RoleCreate):
    """Regra de negócio: Cria novo cargo e associa sua matriz de permissões."""
    existing_role = repository.get_role_by_name(db, name=role_data.name)
    if existing_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este cargo já existe."
        )
        
    existing_organization = repository.get_organization_by_id(db, id=role_data.organization_id)
    if not existing_organization:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organização não encontrada."
        )
        
    permissions = []
    if role_data.permission_ids:
        permissions = repository.get_permissions_by_ids(db, role_data.permission_ids)

    return repository.create_role(db, role_data, permissions=permissions)


def update_role(db: Session, role_id: uuid.UUID, role_data: RoleUpdate):
    """Atualiza dados do cargo e sincroniza a matriz de permissões."""
    db_role = repository.get_role_by_id(db, id=role_id)
    if not db_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cargo não encontrado."
        )

    permissions = None
    if role_data.permission_ids is not None:
        permissions = repository.get_permissions_by_ids(db, role_data.permission_ids)

    return repository.update_role(db, db_role, role_data, permissions=permissions)


def delete_role(db: Session, role_id: uuid.UUID):
    """Exclui o cargo do banco."""
    db_role = repository.get_role_by_id(db, id=role_id)
    if not db_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cargo não encontrado."
        )
    repository.delete_role(db, db_role)
    return {"message": "Cargo excluído com sucesso."}


# ==============================================================================
# 4. REGRAS DE NEGÓCIO DE CONTATOS (Contact)
# ==============================================================================

from controlb.modules.identity.schemas import ContactCreate, ContactUpdate


def list_contacts(db: Session, organization_id: uuid.UUID, search: str | None = None):
    """Lista contatos institucionais da organização com filtro opcional."""
    return repository.list_contacts(db, organization_id, search)


def get_contact(db: Session, contact_id: uuid.UUID, organization_id: uuid.UUID):
    """Busca contato por ID, validando tenant."""
    contact = repository.get_contact_by_id(db, contact_id, organization_id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contato não encontrado."
        )
    return contact


def create_contact(db: Session, organization_id: uuid.UUID, data: ContactCreate):
    """Cria um novo contato na organização."""
    if not data.full_name or not data.full_name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O nome completo do contato é obrigatório."
        )
    return repository.create_contact(db, organization_id, data)


def update_contact(db: Session, contact_id: uuid.UUID, organization_id: uuid.UUID, data: ContactUpdate):
    """Atualiza dados cadastrais de um contato."""
    contact = get_contact(db, contact_id, organization_id)
    return repository.update_contact(db, contact, data)


def delete_contact(db: Session, contact_id: uuid.UUID, organization_id: uuid.UUID):
    """Remove um contato institucional."""
    contact = get_contact(db, contact_id, organization_id)
    repository.delete_contact(db, contact)
    return {"message": "Contato excluído com sucesso."}