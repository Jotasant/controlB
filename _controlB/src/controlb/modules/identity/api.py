"""
api.py - Controladores e Rotas HTTP do Módulo Identity (FastAPI Endpoints)

Disponibiliza os endpoints RESTful para:
1. Autenticação: Login OAuth2 Form com retorno de JWT (/identity/token).
2. Usuários: Cadastro (/identity/users POST) e Listagem autenticada (/identity/users GET).
3. Organizações: Cadastro e Listagem (/identity/organization).
4. Cargos (Roles): Cadastro e Listagem (/identity/role).
"""

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
    """
    Endpoint de Login (OAuth2):
    Recebe 'username' (e-mail) e 'password' no corpo form-urlencoded.
    Verifica as credenciais no banco e retorna o Bearer Token JWT.
    """
    # 1. Busca o usuário pelo e-mail
    user = repository.get_user_by_email(db, email=form_data.username)
    
    # 2. Valida existência do usuário e correspondência do hash da senha
    if not user or not service.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # 3. Cria e retorna o token de acesso contendo o ID do usuário como Subject (sub)
    access_token = service.create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}


# ==============================================================================
# 2. ENDPOINTS DE USUÁRIOS (User)
# ==============================================================================

@router.post("/users", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    Cadastra um novo usuário no sistema.
    Aplica validações de negócio e criptografa a senha com Argon2.
    """
    return service.create_new_user(db=db, user_data=user)


@router.get("/users", response_model=list[schemas.UserResponse])
def get_users(
    db: Session = Depends(get_db),
    current_user = Depends(service.get_current_user) # Rota protegida: Exige token JWT válido
):
    """
    Retorna a lista de todos os usuários cadastrados.
    Apenas clientes autenticados conseguem acessar este endpoint.
    """
    return repository.get_all_users(db)


# ==============================================================================
# 3. ENDPOINTS DE ORGANIZAÇÕES (Organization)
# ==============================================================================

@router.post("/organization", response_model=schemas.OrganizationResponse, status_code=status.HTTP_201_CREATED)
def register_organization(organization: schemas.OrganizationCreate, db: Session = Depends(get_db)):
    """Cadastra uma nova organização (empresa/unidade) no banco de dados."""
    return service.create_new_organization(db=db, organization_data=organization)


@router.get("/organization", response_model=list[schemas.OrganizationResponse])
def get_organizations(
    db: Session = Depends(get_db),
    current_user = Depends(service.get_current_user) # Rota protegida por JWT
):
    """Retorna todas as organizações cadastradas no sistema."""
    return repository.get_all_organizations(db)


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
    current_user = Depends(service.get_current_user) # Rota protegida por JWT
):
    """Retorna todos os cargos cadastrados no sistema."""
    return repository.get_all_roles(db)
