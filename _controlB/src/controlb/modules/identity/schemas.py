"""
schemas.py - Contratos de Dados e Validações (Pydantic Models)

Define os esquemas de validação de entrada (Requests) e formatação de saída (Responses)
para o módulo de Identidade (Organizações, Permissões, Cargos e Usuários).
Garante tipagem estrita, prevenção de vazamento de senhas e serialização segura.
"""

import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr


# ==============================================================================
# 1. ESQUEMAS DE PERMISSÃO (Permission)
# ==============================================================================

class PermissionBase(BaseModel):
    """Atributos básicos de uma Permissão."""
    code: str                           # Código único (ex: "users:create")
    name: str                           # Nome legível (ex: "Cadastrar Usuários")
    module: str                         # Módulo de negócio (ex: "Identity", "Stock")
    description: str | None = None      # Descrição detalhada da autorização
    is_active: bool = True


class PermissionResponse(PermissionBase):
    """Dados da Permissão enviados na resposta da API."""
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 2. ESQUEMAS DE ORGANIZAÇÃO (Organization)
# ==============================================================================

class OrganizationBase(BaseModel):
    """Atributos compartilhados por todos os esquemas de Organização."""
    name: str                           # Nome da empresa/organização
    is_active: bool = True              # Se a organização está ativa no sistema


class OrganizationCreate(OrganizationBase):
    """Dados necessários para cadastrar uma nova Organização (Payload de Entrada)."""
    pass


class OrganizationUpdate(BaseModel):
    """Dados opcionais para atualizar uma Organização."""
    name: str | None = None
    is_active: bool | None = None


class OrganizationResponse(OrganizationBase):
    """
    Dados retornados para o cliente (Payload de Saída).
    Inclui os identificadores únicos e timestamps gerados pelo banco de dados.
    """
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 3. ESQUEMAS DE CARGO / FUNÇÃO (Role)
# ==============================================================================

class RoleBase(BaseModel):
    """Atributos básicos de um Cargo (Role)."""
    name: str                           # Nome do cargo (ex: Administrador, Vendedor, Gerente)
    description: str | None = None      # Descrição opcional das atribuições do cargo
    is_active: bool = True              # Status de ativação


class RoleCreate(RoleBase):
    """Dados necessários para criar um novo Cargo."""
    organization_id: uuid.UUID          # ID da organização à qual este cargo pertence
    permission_ids: list[uuid.UUID] = [] # IDs das permissões atribuídas no cadastro


class RoleUpdate(BaseModel):
    """Dados opcionais para atualizar um Cargo e suas Permissões."""
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    permission_ids: list[uuid.UUID] | None = None # Nova lista de permissões do cargo


class RoleResponse(RoleBase):
    """Dados do Cargo enviados na resposta da API com lista de permissões."""
    id: uuid.UUID
    organization_id: uuid.UUID
    permissions: list[PermissionResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 4. ESQUEMAS DE USUÁRIO (User)
# ==============================================================================

class UserBase(BaseModel):
    """Atributos básicos do Usuário."""
    email: EmailStr                     # O Pydantic valida automaticamente o formato do e-mail
    full_name: str                      # Nome completo do usuário
    is_active: bool = True              # Se o usuário pode realizar login


class UserCreate(UserBase):
    """
    Dados enviados no cadastro de usuário.
    Recebe a senha em texto plano (password), que será convertida em hash seguro no service.
    """
    organization_id: uuid.UUID          # Organização obrigatória
    role_id: uuid.UUID | None = None    # Cargo opcional
    password: str                       # Senha em texto claro informada pelo usuário


class UserUpdate(BaseModel):
    """
    Dados enviados na edição de Perfil / Desvinculação do Usuário.
    Todos os campos são opcionais.
    """
    full_name: str | None = None
    email: EmailStr | None = None
    organization_id: uuid.UUID | None = None
    role_id: uuid.UUID | None = None
    is_active: bool | None = None
    password: str | None = None         # Opcional para redefinição de senha


class UserResponse(UserBase):
    """
    Dados do Usuário retornados pela API.
    IMPORTANTE: Por segurança, NUNCA expomos 'password' ou 'hashed_password' aqui!
    """
    id: uuid.UUID
    organization_id: uuid.UUID
    role_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserMeResponse(UserBase):
    """
    Retorno do endpoint '/identity/users/me' com permissões resolvidas para o Frontend.
    """
    id: uuid.UUID
    organization_id: uuid.UUID
    role_id: uuid.UUID | None
    role_name: str | None = None
    permissions: list[str] = []         # Lista de códigos: ["users:view", "dashboard:view", ...]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
