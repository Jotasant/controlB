"""
api.py - Controladores e Rotas HTTP do Módulo Identity (FastAPI Endpoints)

Disponibiliza os endpoints RESTful para:
1. Autenticação: Login OAuth2 Form (/identity/token).
2. Perfil do Usuário Logado: Dados e Permissões (/identity/users/me).
3. Usuários: Listagem, Cadastro, Atualização e Exclusão (com require_permission).
4. Permissões: Catálogo de permissões do sistema (/identity/permissions).
5. Cargos (Roles): Cadastro, Matriz de Permissões e Exclusão (com require_permission).
6. Organizações: Cadastro, Listagem e Exclusão (com require_permission).
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from controlb.db import get_db
from controlb.modules.identity import schemas, service, repository

# Instancia o roteador com prefixo '/identity' e tag para documentação Swagger
router = APIRouter(prefix="/identity", tags=["Identity"])


# ==============================================================================
# 1. AUTENTICAÇÃO E PERFIL DO USUÁRIO LOGADO
# ==============================================================================

@router.post("/token")
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Endpoint de Login (OAuth2). Retorna o Bearer Token JWT."""
    # Garante que as permissões padrão existam no banco
    service.seed_default_permissions(db)

    user = repository.get_user_by_email(db, email=form_data.username)
    if not user or not service.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token = service.create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/users/me", response_model=schemas.UserMeResponse)
def get_current_user_profile(
    current_user = Depends(service.get_current_user)
):
    """
    Retorna o perfil do usuário logado e sua lista ativa de permissões (ex: ['users:view', 'dashboard:view']).
    Consumido pelo Frontend para controlar a visibilidade de botões e rotas.
    """
    role_name = current_user.role.name if current_user.role else None
    permissions = service.get_user_permissions(current_user)

    return schemas.UserMeResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        organization_id=current_user.organization_id,
        role_id=current_user.role_id,
        role_name=role_name,
        permissions=permissions,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at
    )


# ==============================================================================
# 2. ENDPOINTS DE CATÁLOGO DE PERMISSÕES (Permission)
# ==============================================================================

@router.get("/permissions", response_model=list[schemas.PermissionResponse])
def get_permissions(
    db: Session = Depends(get_db),
    current_user = Depends(service.get_current_user)
):
    """Retorna todas as permissões cadastradas no catálogo do sistema."""
    service.seed_default_permissions(db)
    return repository.get_all_permissions(db)


# ==============================================================================
# 3. ENDPOINTS DE USUÁRIOS (User) - Protegidos por Permissões
# ==============================================================================

@router.post("/users", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(
    user: schemas.UserCreate, 
    db: Session = Depends(get_db),
    current_user = Depends(service.require_permission("users:create"))
):
    """Cadastra um novo usuário no sistema (Exige permissão: users:create)."""
    return service.create_new_user(db=db, user_data=user)


@router.get("/users", response_model=list[schemas.UserResponse])
def get_users(
    db: Session = Depends(get_db),
    current_user = Depends(service.require_permission("users:view"))
):
    """Retorna a lista de todos os usuários cadastrados (Exige permissão: users:view)."""
    return repository.get_all_users(db, current_user.organization_id)


@router.get("/users/{user_id}", response_model=schemas.UserResponse)
def get_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(service.require_permission("users:view"))
):
    """Retorna um usuário da organização atual para a página de formulário."""
    return service.get_user(db, user_id, current_user.organization_id)


@router.put("/users/{user_id}", response_model=schemas.UserResponse)
def update_user_profile(
    user_id: uuid.UUID,
    user_data: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(service.require_permission("users:edit"))
):
    """Atualiza dados do perfil de um usuário (Exige permissão: users:edit)."""
    return service.update_user(db=db, user_id=user_id, user_data=user_data)


@router.delete("/users/{user_id}", status_code=status.HTTP_200_OK)
def delete_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(service.require_permission("users:delete"))
):
    """Exclui/desvincula permanentemente o usuário do sistema (Exige permissão: users:delete)."""
    return service.delete_user(db=db, user_id=user_id, current_user_id=current_user.id)


@router.delete("/users", response_model=schemas.BulkDeleteResponse, status_code=status.HTTP_200_OK)
def bulk_delete_users(
    payload: schemas.BulkDeleteUsersRequest,
    db: Session = Depends(get_db),
    current_user = Depends(service.require_permission("users:delete"))
):
    """Exclui múltiplos usuários selecionados em lote (Exige permissão: users:delete)."""
    return service.bulk_delete_users(db=db, user_ids=payload.user_ids, current_user_id=current_user.id)


# ==============================================================================
# 4. ENDPOINTS DE CARGOS / PAPÉIS (Role) - Protegidos por Permissões
# ==============================================================================

@router.post("/role", response_model=schemas.RoleResponse, status_code=status.HTTP_201_CREATED)
def register_role(
    role: schemas.RoleCreate, 
    db: Session = Depends(get_db),
    current_user = Depends(service.require_permission("roles:manage"))
):
    """Cadastra um novo cargo com sua lista de permissões (Exige permissão: roles:manage)."""
    return service.create_new_role(db=db, role_data=role)


@router.get("/role", response_model=list[schemas.RoleResponse])
def get_roles(
    db: Session = Depends(get_db),
    current_user = Depends(service.require_permission("roles:view"))
):
    """Retorna todos os cargos cadastrados (Exige permissão: roles:view)."""
    return repository.get_all_roles(db)


@router.get("/role/{role_id}", response_model=schemas.RoleResponse)
def get_role(
    role_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(service.require_permission("roles:view"))
):
    """Retorna um cargo para a página de formulário."""
    return service.get_role(db, role_id)


@router.put("/role/{role_id}", response_model=schemas.RoleResponse)
def update_role(
    role_id: uuid.UUID,
    role_data: schemas.RoleUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(service.require_permission("roles:manage"))
):
    """Atualiza um cargo e sincroniza sua matriz de permissões (Exige permissão: roles:manage)."""
    return service.update_role(db=db, role_id=role_id, role_data=role_data)


@router.delete("/role/{role_id}", status_code=status.HTTP_200_OK)
def delete_role(
    role_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(service.require_permission("roles:manage"))
):
    """Exclui o cargo cadastrado (Exige permissão: roles:manage)."""
    return service.delete_role(db=db, role_id=role_id)


@router.delete("/role", response_model=schemas.BulkDeleteResponse, status_code=status.HTTP_200_OK)
def bulk_delete_roles(
    payload: schemas.BulkDeleteRolesRequest,
    db: Session = Depends(get_db),
    current_user = Depends(service.require_permission("roles:manage"))
):
    """Exclui múltiplos cargos selecionados em lote (Exige permissão: roles:manage)."""
    return service.bulk_delete_roles(db=db, role_ids=payload.role_ids)


# ==============================================================================
# 5. ENDPOINTS DE ORGANIZAÇÕES (Organization) - Protegidos por Permissões
# ==============================================================================

@router.post("/organization", response_model=schemas.OrganizationResponse, status_code=status.HTTP_201_CREATED)
def register_organization(
    organization: schemas.OrganizationCreate, 
    db: Session = Depends(get_db),
    current_user = Depends(service.require_permission("organizations:manage"))
):
    """Cadastra uma nova organização (Exige permissão: organizations:manage)."""
    return service.create_new_organization(db=db, organization_data=organization)


@router.get("/organization", response_model=list[schemas.OrganizationResponse])
def get_organizations(
    db: Session = Depends(get_db),
    current_user = Depends(service.require_permission("organizations:view"))
):
    """Retorna todas as organizações cadastradas (Exige permissão: organizations:view)."""
    return repository.get_all_organizations(db)


@router.get("/organization/{org_id}", response_model=schemas.OrganizationResponse)
def get_organization(
    org_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(service.require_permission("organizations:view"))
):
    """Retorna uma organização para a página de formulário."""
    return service.get_organization(db, org_id)


@router.put("/organization/{org_id}", response_model=schemas.OrganizationResponse)
def update_organization(
    org_id: uuid.UUID,
    organization: schemas.OrganizationUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(service.require_permission("organizations:manage"))
):
    """Atualiza dados cadastrais de uma organização (Exige permissão: organizations:manage)."""
    return service.update_organization(db=db, organization_id=org_id, organization_data=organization)


@router.delete("/organization/{org_id}", status_code=status.HTTP_200_OK)
def delete_organization(
    org_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(service.require_permission("organizations:manage"))
):
    """Exclui a organização cadastrada (Exige permissão: organizations:manage)."""
    return service.delete_organization(db=db, organization_id=org_id)


@router.delete("/organization", response_model=schemas.BulkDeleteResponse, status_code=status.HTTP_200_OK)
def bulk_delete_organizations(
    payload: schemas.BulkDeleteOrganizationsRequest,
    db: Session = Depends(get_db),
    current_user = Depends(service.require_permission("organizations:manage"))
):
    """Exclui múltiplas organizações selecionadas em lote (Exige permissão: organizations:manage)."""
    return service.bulk_delete_organizations(db=db, org_ids=payload.org_ids)


# ==============================================================================
# 6. ENDPOINTS DE CONTATOS INSTITUCIONAIS (Contact)
# ==============================================================================

@router.get("/contacts", response_model=list[schemas.ContactResponse], summary="Listar Contatos / Parceiros Unificados")
def list_contacts(
    search: str | None = Query(None, description="Busca por nome, razão social, documento, e-mail ou telefone"),
    is_customer: bool | None = Query(None, description="Filtrar perfil Cliente"),
    is_supplier: bool | None = Query(None, description="Filtrar perfil Fornecedor"),
    is_carrier: bool | None = Query(None, description="Filtrar perfil Transportadora"),
    is_active: bool | None = Query(None, description="Filtrar por status ativo"),
    db: Session = Depends(get_db),
    current_user = Depends(service.get_current_user)
):
    """Retorna contatos e parceiros unificados (Odoo res.partner) cadastrados para a organização do usuário."""
    return service.list_contacts(
        db,
        current_user.organization_id,
        search=search,
        is_customer=is_customer,
        is_supplier=is_supplier,
        is_carrier=is_carrier,
        is_active=is_active
    )


@router.get("/contacts/{contact_id}", response_model=schemas.ContactResponse, summary="Obter Contato")
def get_contact(
    contact_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(service.get_current_user)
):
    """Busca os dados de um contato pelo ID."""
    return service.get_contact(db, contact_id, current_user.organization_id)


@router.post("/contacts", response_model=schemas.ContactResponse, status_code=status.HTTP_201_CREATED, summary="Cadastrar Contato")
def create_contact(
    payload: schemas.ContactCreate,
    db: Session = Depends(get_db),
    current_user = Depends(service.get_current_user)
):
    """Cadastra um novo contato na organização."""
    return service.create_contact(db, current_user.organization_id, payload)


@router.put("/contacts/{contact_id}", response_model=schemas.ContactResponse, summary="Atualizar Contato")
def update_contact(
    contact_id: uuid.UUID,
    payload: schemas.ContactUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(service.get_current_user)
):
    """Atualiza dados cadastrais de um contato."""
    return service.update_contact(db, contact_id, current_user.organization_id, payload)


@router.delete("/contacts/{contact_id}", status_code=status.HTTP_200_OK, summary="Excluir Contato")
def delete_contact(
    contact_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(service.get_current_user)
):
    """Remove um contato cadastrado."""
    return service.delete_contact(db, contact_id, current_user.organization_id)


@router.post("/contacts/bulk-delete", status_code=status.HTTP_200_OK, summary="Excluir Múltiplos Contatos em Massa")
def bulk_delete_contacts(
    payload: dict,
    db: Session = Depends(get_db),
    current_user = Depends(service.get_current_user)
):
    """Remove múltiplos contatos cadastrados de uma vez."""
    contact_ids = [uuid.UUID(cid) for cid in payload.get("contact_ids", [])]
    return service.bulk_delete_contacts(db, current_user.organization_id, contact_ids)


# ==============================================================================
# 7. ENDPOINTS DE EQUIPES E GRUPOS MULTIMODULARES (Team)
# ==============================================================================

@router.get("/teams", response_model=list[schemas.TeamResponse], summary="Listar Equipes de Trabalho")
def list_teams(
    module_category: str | None = Query(None, description="Filtrar por módulo (SALES, PURCHASING, INVENTORY, etc.)"),
    is_active: bool | None = Query(None, description="Filtrar por status ativo"),
    db: Session = Depends(get_db),
    current_user = Depends(service.require_any_permission("teams:view", "teams:manage", "users:view", "users:edit", "crm:view", "crm:manage", "sales:view", "sales:manage"))
):
    """Lista as equipes da organização atual."""
    teams = service.list_teams(db, current_user.organization_id, module_category=module_category, is_active=is_active)
    # Formata a resposta com nome do líder
    result = []
    for t in teams:
        item = schemas.TeamResponse.model_validate(t)
        if t.leader:
            item.leader_name = t.leader.full_name
        result.append(item)
    return result


@router.post("/teams", response_model=schemas.TeamResponse, status_code=status.HTTP_201_CREATED, summary="Criar Equipe")
def create_team(
    payload: schemas.TeamCreate,
    db: Session = Depends(get_db),
    current_user = Depends(service.require_any_permission("teams:manage", "users:edit", "crm:manage", "sales:manage"))
):
    """Cria uma nova equipe multimodular."""
    team = service.create_team(db, current_user.organization_id, payload)
    item = schemas.TeamResponse.model_validate(team)
    if team.leader:
        item.leader_name = team.leader.full_name
    return item


@router.get("/teams/candidates", response_model=list[schemas.TeamMemberInfo], summary="Listar candidatos para equipes")
def list_team_candidates(
    db: Session = Depends(get_db),
    current_user = Depends(service.require_any_permission("teams:view", "teams:manage", "users:view", "users:edit", "crm:view", "crm:manage", "sales:view", "sales:manage"))
):
    """Lista colaboradores ativos do tenant sem expor o cadastro global de usuarios."""
    return service.list_team_candidates(db, current_user.organization_id)


@router.get("/teams/{team_id}", response_model=schemas.TeamResponse, summary="Obter Equipe por ID")
def get_team(
    team_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(service.require_any_permission("teams:view", "teams:manage", "users:view", "users:edit", "crm:view", "crm:manage", "sales:view", "sales:manage"))
):
    """Busca detalhes de uma equipe."""
    team = service.get_team(db, team_id, current_user.organization_id)
    item = schemas.TeamResponse.model_validate(team)
    if team.leader:
        item.leader_name = team.leader.full_name
    return item


@router.put("/teams/{team_id}", response_model=schemas.TeamResponse, summary="Atualizar Equipe")
def update_team(
    team_id: uuid.UUID,
    payload: schemas.TeamUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(service.require_any_permission("teams:manage", "users:edit", "crm:manage", "sales:manage"))
):
    """Atualiza dados e membros de uma equipe."""
    team = service.update_team(db, team_id, current_user.organization_id, payload)
    item = schemas.TeamResponse.model_validate(team)
    if team.leader:
        item.leader_name = team.leader.full_name
    return item


@router.delete("/teams/{team_id}", status_code=status.HTTP_200_OK, summary="Excluir Equipe")
def delete_team(
    team_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(service.require_any_permission("teams:manage", "users:edit", "crm:manage", "sales:manage"))
):
    """Remove uma equipe da organização."""
    return service.delete_team(db, team_id, current_user.organization_id)


@router.post("/teams/{team_id}/members", response_model=schemas.TeamResponse, summary="Adicionar Membros à Equipe")
def add_team_members(
    team_id: uuid.UUID,
    payload: schemas.TeamMemberAddRequest,
    db: Session = Depends(get_db),
    current_user = Depends(service.require_any_permission("teams:manage", "users:edit", "crm:manage", "sales:manage"))
):
    """Adiciona múltiplos usuários à equipe."""
    team = service.add_team_members(db, team_id, current_user.organization_id, payload.user_ids)
    item = schemas.TeamResponse.model_validate(team)
    if team.leader:
        item.leader_name = team.leader.full_name
    return item


@router.delete("/teams/{team_id}/members/{user_id}", response_model=schemas.TeamResponse, summary="Remover Membro da Equipe")
def remove_team_member(
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(service.require_any_permission("teams:manage", "users:edit", "crm:manage", "sales:manage"))
):
    """Remove um usuário da equipe."""
    team = service.remove_team_member(db, team_id, current_user.organization_id, user_id)
    item = schemas.TeamResponse.model_validate(team)
    if team.leader:
        item.leader_name = team.leader.full_name
    return item
