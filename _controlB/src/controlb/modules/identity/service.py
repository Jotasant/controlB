"""
service.py - Camada de Regras de Negócio e Segurança (Business Logic & Security)

Responsabilidades:
1. Hashing e verificação de senhas com algoritmo Argon2 (padrão de alta segurança da OWASP).
2. Geração e decodificação de tokens JWT assinados (PyJWT).
3. Regras de negócio de cadastro (validação de duplicidades e integridade relacional).
4. Dependência de autenticação 'get_current_user' para proteger rotas no FastAPI.
"""

import uuid
from datetime import datetime, timedelta, timezone
import jwt
from pwdlib import PasswordHash
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from controlb.db import get_db
from controlb.config import get_settings
from controlb.modules.identity import repository
from controlb.modules.identity.schemas import UserCreate, OrganizationCreate, RoleCreate

# Carrega as configurações de segurança (secret_key, algorithm, expire_time)
settings = get_settings()

# Inicializa o hasher com o algoritmo recomendado pelo pwdlib (Argon2)
password_hash = PasswordHash.recommended()


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
    """
    Gera um token JWT assinado digitalmente com tempo de expiração.
    O payload recebe os dados (ex: 'sub' com o ID do usuário) e o timestamp 'exp'.
    """
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
# 2. REGRAS DE NEGÓCIO (Criação de Entidades)
# ==============================================================================

def create_new_user(db: Session, user_data: UserCreate):
    """
    Regra de negócio para criação de novo usuário:
    1. Valida se o e-mail já não está cadastrado.
    2. Criptografa a senha antes de persistir.
    3. Valida se a organização informada existe no banco.
    4. Valida se o cargo (se fornecido) existe no banco.
    5. Chama o repositório para salvar.
    """
    # 1. Checa duplicidade de e-mail
    existing_user = repository.get_user_by_email(db, email=user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este e-mail já está em uso."
        )
    
    # 2. Gera o hash da senha
    hashed_pwd = get_password_hash(user_data.password)

    # 3. Valida existência da organização
    existing_organization = repository.get_organization_by_id(db, id=user_data.organization_id)
    if not existing_organization:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organização não encontrada."
        )
        
    # 4. Valida existência do cargo se fornecido
    if user_data.role_id:
        existing_role = repository.get_role_by_id(db, id=user_data.role_id)
        if not existing_role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role não encontrado."
            )
            
    # 5. Persiste através da camada de repositório
    return repository.create_user(db, user_data, hashed_pwd)


def create_new_organization(db: Session, organization_data: OrganizationCreate):
    """Regra de negócio: Impede cadastro de organizações com nomes duplicados."""
    existing_organization = repository.get_organization_by_name(db, name=organization_data.name)
    if existing_organization:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta organização já existe."
        )
    return repository.create_organization(db, organization_data)


def create_new_role(db: Session, role_data: RoleCreate):
    """Regra de negócio: Valida se o cargo não é duplicado e se a organização associada existe."""
    existing_role = repository.get_role_by_name(db, name=role_data.name)
    if existing_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este role já existe."
        )
        
    existing_organization = repository.get_organization_by_id(db, id=role_data.organization_id)
    if not existing_organization:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organização não encontrada."
        )
        
    return repository.create_role(db, role_data)


# ==============================================================================
# 3. DEPENDÊNCIA DE PROTEÇÃO DE ROTAS (OAuth2 Bearer)
# ==============================================================================

# Informa ao OpenAPI/Swagger a URL de obtenção do token JWT
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="identity/token")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Guarda de Segurança para Rotas Protegidas:
    1. Intercepta o token JWT do cabeçalho HTTP Authorization.
    2. Valida a assinatura criptográfica e a expiração do token.
    3. Extrai o ID do usuário do campo 'sub'.
    4. Consulta o banco de dados para garantir que a conta ainda existe e está válida.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas ou token expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Decodifica e valida assinatura e expiração do JWT
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm]
        )
        
        # Extrai o ID do usuário
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
            
        user_id = uuid.UUID(user_id_str)
        
    except (jwt.PyJWTError, ValueError):
        # Dispara 401 caso o token tenha sido adulterado, expirado ou formato inválido
        raise credentials_exception
    
    # Valida se o usuário continua cadastrado e ativo no banco
    user = repository.get_user_by_id(db, id=user_id)
    if user is None:
        raise credentials_exception
        
    return user