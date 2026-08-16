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
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from controlb.db import get_db
from controlb.modules.identity import schemas, service, repository

# Instancia o roteador com prefixo '/identity' e tag para documentação Swagger
router = APIRouter(prefix="/identity", tags=["Identity"])


# ==============================================================================
# 1. ENDPOINTS DE AUTENTICAÇÃO E PERFIL DO USUÁRIO LOGADO
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
    return repository.get_all_users(db)


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


@router.delete("/organization/{org_id}", status_code=status.HTTP_200_OK)
def delete_organization(
    org_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(service.require_permission("organizations:manage"))
):
    """Exclui a organização cadastrada (Exige permissão: organizations:manage)."""
    return service.delete_organization(db=db, organization_id=org_id)
