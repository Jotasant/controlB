"""
api.py - Controladores e Rotas HTTP do Módulo Identity (FastAPI Endpoints)

Disponibiliza os endpoints RESTful para:
1. Autenticação: Login OAuth2 Form com retorno de JWT (/identity/token).
2. Usuários: Cadastro, Listagem, Atualização de Perfil e Exclusão/Desvinculação.
3. Organizações: Cadastro, Listagem e Exclusão.
4. Cargos (Roles): Cadastro, Listagem e Exclusão.
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
# 1. ENDPOINTS DE AUTENTICAÇÃO
# ==============================================================================

@router.post("/token")
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Endpoint de Login (OAuth2)."""
    user = repository.get_user_by_email(db, email=form_data.username)
    if not user or not service.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token = service.create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}


# ==============================================================================
# 2. ENDPOINTS DE USUÁRIOS (User)
# ==============================================================================

@router.post("/users", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Cadastra um novo usuário no sistema."""
    return service.create_new_user(db=db, user_data=user)


@router.get("/users", response_model=list[schemas.UserResponse])
def get_users(
    db: Session = Depends(get_db),
    current_user = Depends(service.get_current_user)
):
    """Retorna a lista de todos os usuários cadastrados."""
    return repository.get_all_users(db)


@router.put("/users/{user_id}", response_model=schemas.UserResponse)
def update_user_profile(
    user_id: uuid.UUID,
    user_data: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(service.get_current_user)
):
    """Atualiza dados do perfil de um usuário (Nome, E-mail, Organização, Cargo, Senha, Status)."""
    return service.update_user(db=db, user_id=user_id, user_data=user_data)


@router.delete("/users/{user_id}", status_code=status.HTTP_200_OK)
def delete_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(service.get_current_user)
):
    """Exclui/desvincula permanentemente o usuário do sistema."""
    return service.delete_user(db=db, user_id=user_id, current_user_id=current_user.id)


# ==============================================================================
# 3. ENDPOINTS DE ORGANIZAÇÕES (Organization)
# ==============================================================================

@router.post("/organization", response_model=schemas.OrganizationResponse, status_code=status.HTTP_201_CREATED)
def register_organization(organization: schemas.OrganizationCreate, db: Session = Depends(get_db)):
    """Cadastra uma nova organização."""
    return service.create_new_organization(db=db, organization_data=organization)


@router.get("/organization", response_model=list[schemas.OrganizationResponse])
def get_organizations(
    db: Session = Depends(get_db),
    current_user = Depends(service.get_current_user)
):
    """Retorna todas as organizações cadastradas."""
    return repository.get_all_organizations(db)


@router.delete("/organization/{org_id}", status_code=status.HTTP_200_OK)
def delete_organization(
    org_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(service.get_current_user)
):
    """Exclui a organização cadastrada."""
    return service.delete_organization(db=db, organization_id=org_id)


# ==============================================================================
# 4. ENDPOINTS DE CARGOS / PAPÉIS (Role)
# ==============================================================================

@router.post("/role", response_model=schemas.RoleResponse, status_code=status.HTTP_201_CREATED)
def register_role(role: schemas.RoleCreate, db: Session = Depends(get_db)):
    """Cadastra um novo cargo vinculado a uma organização."""
    return service.create_new_role(db=db, role_data=role)


@router.get("/role", response_model=list[schemas.RoleResponse])
def get_roles(
    db: Session = Depends(get_db),
    current_user = Depends(service.get_current_user)
):
    """Retorna todos os cargos cadastrados."""
    return repository.get_all_roles(db)


@router.delete("/role/{role_id}", status_code=status.HTTP_200_OK)
def delete_role(
    role_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(service.get_current_user)
):
    """Exclui o cargo cadastrado."""
    return service.delete_role(db=db, role_id=role_id)
