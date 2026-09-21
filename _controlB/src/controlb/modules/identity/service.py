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
from controlb.modules.identity.models import User, Team
from controlb.modules.identity.schemas import (
    UserCreate, UserUpdate,
    OrganizationCreate, OrganizationUpdate,
    RoleCreate, RoleUpdate,
    ContactCreate, ContactUpdate,
    TeamCreate, TeamUpdate
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
    require_any_permission,
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
    "require_any_permission",
    "oauth2_scheme",
    "create_new_user",
    "get_user",
    "update_user",
    "delete_user",
    "create_new_organization",
    "get_organization",
    "delete_organization",
    "create_new_role",
    "get_role",
    "update_role",
    "delete_role",
]


# ==============================================================================
# 1. REGRAS DE NEGÓCIO DE USUÁRIOS
# ==============================================================================

def get_user(db: Session, user_id: uuid.UUID, organization_id: uuid.UUID):
    """Busca um usuário sem permitir leitura fora da organização atual."""
    db_user = repository.get_user_by_id(db, id=user_id)
    if not db_user or db_user.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado."
        )
    return db_user

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

def get_organization(db: Session, organization_id: uuid.UUID):
    """Busca uma organização por ID ou retorna 404."""
    db_org = repository.get_organization_by_id(db, id=organization_id)
    if not db_org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organização não encontrada."
        )
    return db_org

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

def get_role(db: Session, role_id: uuid.UUID):
    """Busca um cargo por ID ou retorna 404."""
    db_role = repository.get_role_by_id(db, id=role_id)
    if not db_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cargo não encontrado."
        )
    return db_role

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


def list_contacts(
    db: Session,
    organization_id: uuid.UUID,
    search: str | None = None,
    is_customer: bool | None = None,
    is_supplier: bool | None = None,
    is_carrier: bool | None = None,
    is_active: bool | None = None,
):
    """Lista contatos/parceiros da organização com filtros de papéis (Odoo res.partner)."""
    return repository.list_contacts(
        db,
        organization_id,
        search=search,
        is_customer=is_customer,
        is_supplier=is_supplier,
        is_carrier=is_carrier,
        is_active=is_active
    )


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
    """Cria um novo contato/parceiro unificado na organização."""
    name = (data.name or data.full_name or "").strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A Razão Social ou Nome do contato é obrigatório."
        )
    data.name = name
    if not data.full_name:
        data.full_name = name

    if data.document and data.document.strip():
        existing = repository.get_contact_by_document(db, data.document, organization_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Já existe um contato cadastrado com o documento '{data.document}' ({existing.name})."
            )

    contact = repository.create_contact(db, organization_id, data)
    contact.name_manually_set = True
    db.flush()
    return contact


def update_contact(db: Session, contact_id: uuid.UUID, organization_id: uuid.UUID, data: ContactUpdate):
    """Atualiza dados cadastrais de um contato."""
    contact = get_contact(db, contact_id, organization_id)
    if data.contact_origin_id:
        from .models import ContactOrigin
        from sqlalchemy import select
        if not db.scalar(select(ContactOrigin.id).where(ContactOrigin.id == data.contact_origin_id, ContactOrigin.organization_id == organization_id)):
            raise HTTPException(422, "Origem inválida para a organização.")
    if contact.first_contact_at and "phone" in data.model_fields_set and data.phone != contact.phone:
        raise HTTPException(409, "Telefone sincronizado identifica o contato. Cadastre outro contato para outro número.")
    if data.document and data.document.strip():
        existing = repository.get_contact_by_document(db, data.document, organization_id)
        if existing and existing.id != contact.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Já existe outro contato cadastrado com o documento '{data.document}' ({existing.name})."
            )
    if "name" in data.model_fields_set and data.name is not None:
        if not data.name.strip():
            raise HTTPException(422, "Informe o nome do contato.")
        contact.name_manually_set = True
    result = repository.update_contact(db, contact, data)
    from controlb.modules.chat.models import ChatConversation
    from sqlalchemy import update
    db.execute(update(ChatConversation).where(
        ChatConversation.organization_id == organization_id,
        ChatConversation.contact_id == contact.id,
        ChatConversation.is_group.is_(False),
    ).values(display_name=contact.name))
    db.flush()
    return result


def delete_contact(db: Session, contact_id: uuid.UUID, organization_id: uuid.UUID):
    """Remove um contato institucional."""
    contact = get_contact(db, contact_id, organization_id)
    repository.delete_contact(db, contact)
    return {"message": "Contato excluído com sucesso."}


def bulk_delete_contacts(db: Session, organization_id: uuid.UUID, contact_ids: list[uuid.UUID]):
    """Remove múltiplos contatos institucionais em massa."""
    deleted_count = 0
    for cid in contact_ids:
        contact = repository.get_contact_by_id(db, cid, organization_id)
        if contact:
            repository.delete_contact(db, contact)
            deleted_count += 1
    db.commit()
    return {"message": f"{deleted_count} contato(s) excluído(s) com sucesso.", "deleted_count": deleted_count}


# ==============================================================================
# 5. REGRAS DE NEGÓCIO DE EQUIPE E ESCOPO DE VISIBILIDADE (Team & Row-Level Scope)
# ==============================================================================

def list_teams(
    db: Session,
    organization_id: uuid.UUID,
    module_category: str | None = None,
    is_active: bool | None = None
):
    """Lista as equipes da organização com filtro opcional por módulo."""
    return repository.list_teams(db, organization_id, module_category, is_active)


def get_team(db: Session, team_id: uuid.UUID, organization_id: uuid.UUID):
    """Busca uma equipe específica, validando o tenant da organização."""
    team = repository.get_team_by_id(db, team_id, organization_id)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Equipe não encontrada."
        )
    return team


def list_team_candidates(db: Session, organization_id: uuid.UUID) -> list[User]:
    """Lista somente colaboradores ativos do tenant que podem integrar equipes."""
    return sorted(
        (user for user in repository.get_all_users(db, organization_id) if user.is_active),
        key=lambda user: user.full_name.casefold(),
    )


def _validate_team_uniqueness(
    db: Session,
    organization_id: uuid.UUID,
    module_category: str,
    name: str,
    code: str | None,
    team_id: uuid.UUID | None = None,
) -> None:
    existing_name = repository.get_team_by_name(db, organization_id, module_category, name)
    if existing_name and existing_name.id != team_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe uma equipe com este nome nesta categoria.",
        )
    if code:
        existing_code = repository.get_team_by_code(db, organization_id, module_category, code)
        if existing_code and existing_code.id != team_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Já existe uma equipe com este código nesta categoria.",
            )


def _validate_team_users(
    db: Session,
    organization_id: uuid.UUID,
    user_ids: set[uuid.UUID],
) -> None:
    if not user_ids:
        return
    valid_ids = {
        user.id
        for user in repository.get_all_users(db, organization_id)
        if user.is_active and user.id in user_ids
    }
    if user_ids - valid_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Um ou mais integrantes não existem, estão inativos ou pertencem a outra organização.",
        )


def create_team(db: Session, organization_id: uuid.UUID, data: TeamCreate):
    """Cria uma nova equipe multimodular vinculando membros."""
    name = data.name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O nome da equipe é obrigatório."
        )
    category = data.module_category.upper()
    code = data.code.strip().upper() if data.code and data.code.strip() else None
    member_ids = set(data.member_ids)
    if data.leader_id:
        member_ids.add(data.leader_id)
    _validate_team_uniqueness(db, organization_id, category, name, code)
    _validate_team_users(db, organization_id, member_ids)
    normalized = data.model_copy(update={
        "name": name,
        "code": code,
        "module_category": category,
        "member_ids": list(member_ids),
    })
    return repository.create_team(db, organization_id, normalized)


def update_team(db: Session, team_id: uuid.UUID, organization_id: uuid.UUID, data: TeamUpdate):
    """Atualiza dados e membros de uma equipe existente."""
    team = get_team(db, team_id, organization_id)
    name = data.name.strip() if data.name is not None else team.name
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O nome da equipe é obrigatório.",
        )
    category = data.module_category.upper() if data.module_category else team.module_category
    if "code" in data.model_fields_set:
        code = data.code.strip().upper() if data.code and data.code.strip() else None
    else:
        code = team.code
    leader_id = data.leader_id if "leader_id" in data.model_fields_set else team.leader_id
    member_ids = (
        set(data.member_ids)
        if data.member_ids is not None
        else {member.id for member in team.members}
    )
    if leader_id:
        member_ids.add(leader_id)
    _validate_team_uniqueness(db, organization_id, category, name, code, team.id)
    _validate_team_users(db, organization_id, member_ids)
    normalized = data.model_copy(update={
        "name": name,
        "code": code,
        "module_category": category,
        "leader_id": leader_id,
        "member_ids": list(member_ids),
    })
    return repository.update_team(db, team, normalized)


def delete_team(db: Session, team_id: uuid.UUID, organization_id: uuid.UUID):
    """Remove uma equipe da organização."""
    team = get_team(db, team_id, organization_id)
    repository.delete_team(db, team)
    return {"message": "Equipe removida com sucesso."}


def add_team_members(db: Session, team_id: uuid.UUID, organization_id: uuid.UUID, user_ids: list[uuid.UUID]):
    """Adiciona colaboradores à equipe."""
    team = get_team(db, team_id, organization_id)
    _validate_team_users(db, organization_id, set(user_ids))
    return repository.add_team_members(db, team, user_ids)


def remove_team_member(db: Session, team_id: uuid.UUID, organization_id: uuid.UUID, user_id: uuid.UUID):
    """Remove um colaborador da equipe."""
    team = get_team(db, team_id, organization_id)
    if team.leader_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Defina outro líder antes de remover o líder atual da equipe.",
        )
    return repository.remove_team_member(db, team, user_id)


def get_accessible_user_ids(
    db: Session,
    current_user: User,
    module_category: str = "SALES"
) -> set[uuid.UUID] | None:
    """
    Retorna o conjunto de IDs de usuários cujos registros o `current_user` tem permissão de visualizar.
    
    Regras de Escopo (Row-Level Security):
    1. Usuários Administradores, Diretores, Gestores Globais, Marketing ou Consultores:
       -> Retorna `None` (significa ACESSO GLOBAL a 100% dos registros da organização).
    2. Gestores / Líderes de Equipe (onde `team.leader_id == current_user.id` na categoria do módulo):
       -> Retorna `{current_user.id, ...membros_das_equipes_lideradas}`.
    3. Usuários Comuns / Vendedores:
       -> Retorna `{current_user.id}` (visualiza estritamente seus próprios registros vinculados).
    """
    role_name = (current_user.role.name if current_user.role else "").lower()
    
    # Perfis com visão irrestrita/global
    broad_roles = ["admin", "administrador", "diretor", "diretoria", "gerente geral", "marketing", "consultor", "consultoria"]
    if any(br in role_name for br in broad_roles):
        return None

    # Verifica permissões explícitas amplas
    perms = get_user_permissions(current_user)
    if any(p in perms for p in ["crm:view_all", "sales:view_all", "crm:manage_all", "sales:manage_all", "*:*"]):
        return None

    # Verifica se o usuário é líder de equipes no módulo informado
    teams = repository.list_teams(db, current_user.organization_id, module_category=module_category, is_active=True)
    led_teams = [t for t in teams if t.leader_id == current_user.id]

    if led_teams:
        accessible_ids = {current_user.id}
        for team in led_teams:
            for member in team.members:
                accessible_ids.add(member.id)
        return accessible_ids

    # Usuário comum / vendedor: apenas seu próprio ID
    return {current_user.id}
