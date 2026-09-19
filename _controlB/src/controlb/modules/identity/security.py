"""
security.py - Camada Central de Segurança, Criptografia, Tokens JWT e RBAC Auto-Discovery

Responsabilidades:
1. Declarar as permissões de acesso nativas de Identidade/Administração (MODULE_PERMISSIONS).
2. Motor de Auto-Discovery (discover_system_permissions): escaneia dinamicamente todos os
   módulos do ControlB em 'controlb.modules' e agrega suas listas 'MODULE_PERMISSIONS'.
3. Suporte opcional a sincronização/exportação via arquivo CSV (permissions.csv).
4. Função de Seed idempotente no banco de dados (seed_default_permissions).
5. Criptografia de senhas com algoritmo Argon2 (padrão OWASP via pwdlib).
6. Emissão e validação de tokens JWT assinados (PyJWT).
7. Dependências e guards FastAPI (get_current_user, require_permission).
"""

import csv
import io
import os
import uuid
import importlib
import pkgutil
from datetime import datetime, timedelta, timezone
from typing import Callable, List, Dict, Any
import jwt
from pwdlib import PasswordHash
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from controlb.db import get_db
from controlb.config import get_settings
from controlb.logger import logger
from controlb.modules.identity import repository
from controlb.modules.identity.models import User

# Carrega as configurações centralizadas
settings = get_settings()

# Inicializa o hasher com o algoritmo recomendado pelo pwdlib (Argon2)
password_hash = PasswordHash.recommended()

# Esquema OAuth2 Password Bearer para Swagger e extração do cabeçalho Authorization
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="identity/token")


# ==============================================================================
# 0. PERMISSÕES ESPECÍFICAS DO MÓDULO DE IDENTIDADE & ADMINISTRAÇÃO
# ==============================================================================

MODULE_PERMISSIONS: List[Dict[str, Any]] = [
    # Dashboard & Indicadores
    {
        "code": "dashboard:view",
        "name": "Visualizar Dashboard",
        "module": "Dashboard",
        "description": "Acesso aos gráficos executivos, KPIs e painéis analíticos consolidados"
    },
    {
        "code": "dashboard:export",
        "name": "Exportar Relatórios",
        "module": "Dashboard",
        "description": "Permissão para exportar dados, relatórios e planilhas gerenciais"
    },

    # Usuários & Colaboradores
    {
        "code": "users:view",
        "name": "Visualizar Usuários",
        "module": "Usuários",
        "description": "Consultar a listagem e perfil de colaboradores cadastrados"
    },
    {
        "code": "users:create",
        "name": "Cadastrar Usuários",
        "module": "Usuários",
        "description": "Criar novos usuários e acessos no sistema"
    },
    {
        "code": "users:edit",
        "name": "Editar Usuários",
        "module": "Usuários",
        "description": "Editar informações cadastrais, cargos e credenciais de usuários"
    },
    {
        "code": "users:delete",
        "name": "Desvincular/Excluir Usuários",
        "module": "Usuários",
        "description": "Excluir ou desativar contas de usuários do sistema"
    },

    # Organizações & Filiais
    {
        "code": "teams:view",
        "name": "Visualizar Equipes",
        "module": "Equipes",
        "description": "Consultar equipes e seus integrantes"
    },
    {
        "code": "teams:manage",
        "name": "Gerenciar Equipes",
        "module": "Equipes",
        "description": "Criar, alterar e excluir equipes e seus vínculos"
    },

    {
        "code": "organizations:view",
        "name": "Visualizar Organizações",
        "module": "Organizações",
        "description": "Consultar empresas matriz e filiais cadastradas"
    },
    {
        "code": "organizations:manage",
        "name": "Gerenciar Organizações",
        "module": "Organizações",
        "description": "Cadastrar, editar e excluir empresas, matrizes e filiais"
    },

    # Cargos & Matriz RBAC
    {
        "code": "roles:view",
        "name": "Visualizar Cargos",
        "module": "Cargos",
        "description": "Consultar os cargos existentes e suas permissões associadas"
    },
    {
        "code": "roles:manage",
        "name": "Gerenciar Cargos e Permissões",
        "module": "Cargos",
        "description": "Criar, alterar cargos e configurar a matriz de permissões RBAC"
    },
]


# ==============================================================================
# 1. MOTOR DE AUTO-DESCOBERTA DE PERMISSÕES MODULARES (Auto-Discovery)
# ==============================================================================

def discover_system_permissions() -> List[Dict[str, Any]]:
    """
    Escaneia dinamicamente todos os pacotes em 'controlb.modules', importa seus
    respectivos arquivos 'security.py' e agrega as listas 'MODULE_PERMISSIONS'.
    
    Elimina a necessidade de registrar permissões manualmente no módulo identity.
    """
    all_permissions: List[Dict[str, Any]] = []
    seen_codes = set()

    # 1. Inclui as permissões do próprio módulo de Identidade
    for perm in MODULE_PERMISSIONS:
        code = perm.get("code")
        if code and code not in seen_codes:
            all_permissions.append(perm)
            seen_codes.add(code)

    # 2. Varre dinamicamente as pastas de todos os outros módulos
    import controlb.modules as modules_pkg
    for pkg_path in modules_pkg.__path__:
        try:
            for item in os.listdir(pkg_path):
                subpath = os.path.join(pkg_path, item)
                if os.path.isdir(subpath) and not item.startswith("__") and item != "identity":
                    security_module_path = f"controlb.modules.{item}.security"
                    try:
                        sec_mod = importlib.import_module(security_module_path)
                        mod_perms = getattr(sec_mod, "MODULE_PERMISSIONS", None)
                        if mod_perms and isinstance(mod_perms, list):
                            for perm in mod_perms:
                                code = perm.get("code")
                                if code and code not in seen_codes:
                                    all_permissions.append(perm)
                                    seen_codes.add(code)
                    except ModuleNotFoundError:
                        continue
                    except Exception as exc:
                        logger.warning(f"⚠️ [SECURITY AUTO-DISCOVERY] Falha ao inspecionar '{security_module_path}': {exc}")
        except Exception as err:
            logger.warning(f"⚠️ [SECURITY AUTO-DISCOVERY] Erro ao iterar diretório '{pkg_path}': {err}")

    return all_permissions


# Catálogo consolidado dinamicamente no carregamento do módulo
DEFAULT_PERMISSIONS: List[Dict[str, Any]] = discover_system_permissions()


def export_permissions_to_csv_string() -> str:
    """Exporta o catálogo completo de permissões ativas em formato CSV."""
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["code", "name", "module", "description"])
    for perm in discover_system_permissions():
        writer.writerow([
            perm.get("code", ""),
            perm.get("name", ""),
            perm.get("module", ""),
            perm.get("description", "")
        ])
    return output.getvalue()


def seed_default_permissions(db: Session) -> None:
    """
    Garante que todas as permissões padrão descobertas dinamicamente existam no banco de dados.
    Executado de forma idempotente.
    """
    current_perms = discover_system_permissions()
    for perm_data in current_perms:
        repository.create_permission_if_not_exists(
            db=db,
            code=perm_data["code"],
            name=perm_data["name"],
            module=perm_data["module"],
            description=perm_data["description"]
        )


# ==============================================================================
# 2. FUNÇÕES DE CRIPTOGRAFIA E TOKENS JWT
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
# 3. DEPENDÊNCIAS DE SEGURANÇA E AUTORIZAÇÃO (Guards / RBAC)
# ==============================================================================

def get_user_permissions(user: User) -> list[str]:
    """Extrai e retorna a lista de códigos de permissões ativas de um usuário."""
    if not user.role or not user.role.is_active:
        return []
    perms = [p.code for p in user.role.permissions if p.is_active]
    # Usuários administradores possuem acesso universal irrestrito a todos os módulos do ERP
    if user.role.name and user.role.name.strip().lower() in ["administrador", "admin", "diretor", "diretoria"]:
        if "*:*" not in perms:
            perms.append("*:*")
    return perms


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
        if "*:*" not in user_perms and permission_code not in user_perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso negado: Você não possui a permissão '{permission_code}'."
            )
        return current_user

    return permission_checker


def require_any_permission(*permission_codes: str) -> Callable:
    """Autoriza quando o usuário possui ao menos uma das permissões informadas."""
    def permission_checker(current_user: User = Depends(get_current_user)) -> User:
        user_perms = set(get_user_permissions(current_user))
        if "*:*" not in user_perms and not user_perms.intersection(permission_codes):
            expected = "', '".join(permission_codes)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso negado: é necessária uma das permissões '{expected}'."
            )
        return current_user

    return permission_checker
