"""
service.py - Camada de Regras de Negócio, Permissões e Segurança (RBAC)

Responsabilidades:
1. Hashing e verificação de senhas com algoritmo Argon2 (padrão OWASP).
2. Geração e decodificação de tokens JWT assinados (PyJWT).
3. Catálogo e Seed automático de permissões padrão do ControlB.
4. Validação de regras de negócio de Usuários, Cargos, Organizações e Permissões.
5. Dependências FastAPI de autorização: 'get_current_user' e 'require_permission'.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable
import jwt
from pwdlib import PasswordHash
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from controlb.db import get_db
from controlb.config import get_settings
from controlb.modules.identity import repository
from controlb.modules.identity.models import User, Permission
from controlb.modules.identity.schemas import (
    UserCreate, UserUpdate,
    OrganizationCreate, OrganizationUpdate,
    RoleCreate, RoleUpdate
)

# Carrega as configurações de segurança
settings = get_settings()

# Inicializa o hasher com o algoritmo recomendado pelo pwdlib (Argon2)
password_hash = PasswordHash.recommended()


# ==============================================================================
# 0. CATÁLOGO DE PERMISSÕES PADRÃO DO SISTEMA (Default Seeds)
# ==============================================================================

DEFAULT_PERMISSIONS = [
    # Dashboard
    {"code": "dashboard:view", "name": "Visualizar Dashboard", "module": "Dashboard", "description": "Acesso aos gráficos e KPIs executivos"},
    {"code": "dashboard:export", "name": "Exportar Relatórios", "module": "Dashboard", "description": "Permissão para exportar dados e planilhas"},

    # Usuários & Perfis
    {"code": "users:view", "name": "Visualizar Usuários", "module": "Usuários", "description": "Consultar a lista e perfil de colaboradores"},
    {"code": "users:create", "name": "Cadastrar Usuários", "module": "Usuários", "description": "Criar novos usuários e acessos no sistema"},
    {"code": "users:edit", "name": "Editar Usuários", "module": "Usuários", "description": "Editar informações, cargos e senhas de usuários"},
    {"code": "users:delete", "name": "Desvincular/Excluir Usuários", "module": "Usuários", "description": "Excluir permanentemente contas de usuários"},

    # Organizações
    {"code": "organizations:view", "name": "Visualizar Organizações", "module": "Organizações", "description": "Consultar empresas e filiais"},
    {"code": "organizations:manage", "name": "Gerenciar Organizações", "module": "Organizações", "description": "Cadastrar, editar e excluir empresas e filiais"},

    # Cargos & Matriz de Permissões
    {"code": "roles:view", "name": "Visualizar Cargos", "module": "Cargos", "description": "Consultar os cargos existentes"},
    {"code": "roles:manage", "name": "Gerenciar Cargos e Permissões", "module": "Cargos", "description": "Criar cargos e configurar a matriz de permissões"},

    # Catálogo de Produtos & Estoque (Módulos Futuros)
    {"code": "products:view", "name": "Visualizar Catálogo de Produtos", "module": "Estoque", "description": "Consultar produtos e insumos"},
    {"code": "products:manage", "name": "Gerenciar Produtos", "module": "Estoque", "description": "Cadastrar e alterar produtos"},
]


def seed_default_permissions(db: Session) -> None:
    """Garante que todas as permissões padrão existam no banco de dados."""
    for perm_data in DEFAULT_PERMISSIONS:
        repository.create_permission_if_not_exists(
            db=db,
            code=perm_data["code"],
            name=perm_data["name"],
            module=perm_data["module"],
            description=perm_data["description"]
        )


# ==============================================================================
# 1. FUNÇÕES DE CRIPTOGRAFIA E TOKENS JWT
# ==============================================================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a senha em texto claro bate com o hash criptografado salvo no banco."""
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Transforma a senha em texto claro em um hash irreversível utilizando Argon2."""
    return password_hash.hash(password)


def create_access_token(data: dict) -> str:
    """Gera um token JWT assinado digitalmente com tempo de expiração."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.secret_key, 
        algorithm=settings.algorithm
    )
    return encoded_jwt


# ==============================================================================
# 2. REGRAS DE NEGÓCIO DE USUÁRIOS
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
# 3. REGRAS DE NEGÓCIO DE ORGANIZAÇÃO
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


def delete_organization(db: Session, organization_id: uuid.UUID):
    """Exclui a organização do banco."""
    db_org = repository.get_organization_by_id(db, id=organization_id)
    if not db_org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organização não encontrada."
        )
    repository.delete_organization(db, db_org)
    return {"message": "Organização excluída com sucesso."}


# ==============================================================================
# 4. REGRAS DE NEGÓCIO DE CARGOS E PERMISSÕES (RBAC)
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


def get_user_permissions(user: User) -> list[str]:
    """Extrai e retorna a lista de códigos de permissões ativas de um usuário."""
    if not user.role or not user.role.is_active:
        return []
    return [p.code for p in user.role.permissions if p.is_active]


# ==============================================================================
# 5. DEPENDÊNCIAS DE SEGURANÇA E AUTORIZAÇÃO (Guards)
# ==============================================================================

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="identity/token")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Guarda de Autenticação (AuthN): Valida o token JWT e retorna o usuário logado."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas ou token expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm]
        )
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
            
        user_id = uuid.UUID(user_id_str)
        
    except (jwt.PyJWTError, ValueError):
        raise credentials_exception
    
    user = repository.get_user_by_id(db, id=user_id)
    if user is None or not user.is_active:
        raise credentials_exception
        
    return user


def require_permission(permission_code: str) -> Callable:
    """
    Guarda de Autorização (AuthZ):
    Garante que o usuário autenticado possua o código de permissão necessário.
    Caso contrário, bloqueia com HTTP 403 Forbidden.
    """
    def permission_checker(current_user: User = Depends(get_current_user)) -> User:
        user_perms = get_user_permissions(current_user)
        if permission_code not in user_perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso negado: Você não possui a permissão '{permission_code}'."
            )
        return current_user

    return permission_checker