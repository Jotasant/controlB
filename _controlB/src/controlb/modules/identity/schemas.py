"""
schemas.py - Contratos de Dados e Validações (Pydantic Models)

Define os esquemas de validação de entrada (Requests) e formatação de saída (Responses)
para o módulo de Identidade (Organizações, Permissões, Cargos e Usuários).
Garante tipagem estrita, prevenção de vazamento de senhas e serialização segura.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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
    is_seller: bool = False             # Se o usuário atua como Vendedor no sistema


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
    is_seller: bool | None = None
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


# ==============================================================================
# 5. ESQUEMAS DE OPERAÇÕES EM LOTE (Bulk Operations)
# ==============================================================================

class BulkDeleteUsersRequest(BaseModel):
    user_ids: list[uuid.UUID]


class BulkDeleteOrganizationsRequest(BaseModel):
    org_ids: list[uuid.UUID]


class BulkDeleteRolesRequest(BaseModel):
    role_ids: list[uuid.UUID]


class BulkDeleteResponse(BaseModel):
    message: str
    deleted_count: int


# ==============================================================================
# 6. ESQUEMAS DE CONTATO / PARCEIRO UNIFICADO (Contact - Padrão Odoo res.partner)
# ==============================================================================

class ContactBase(BaseModel):
    person_type: str = "PJ"
    document: str | None = None
    name: str | None = None
    trade_name: str | None = None
    state_registration: str | None = None

    full_name: str | None = None
    position: str | None = None
    email: str | None = None
    phone: str | None = None
    mobile: str | None = None

    address_street: str | None = None
    address_number: str | None = None
    address_neighborhood: str | None = None
    address_city: str | None = None
    address_state: str | None = None
    address_zip_code: str | None = None

    is_customer: bool = False
    is_supplier: bool = False
    is_carrier: bool = False

    credit_limit: Decimal = Decimal("0.00")
    origin_module: str = "IDENTITY"
    is_active: bool = True
    notes: str | None = None


class ContactCreate(BaseModel):
    person_type: str = "PJ"
    document: str | None = None
    name: str | None = None
    trade_name: str | None = None
    state_registration: str | None = None

    full_name: str | None = None
    position: str | None = None
    email: str | None = None
    phone: str | None = None
    mobile: str | None = None

    address_street: str | None = None
    address_number: str | None = None
    address_neighborhood: str | None = None
    address_city: str | None = None
    address_state: str | None = None
    address_zip_code: str | None = None

    is_customer: bool = False
    is_supplier: bool = False
    is_carrier: bool = False

    credit_limit: Decimal = Decimal("0.00")
    origin_module: str = "IDENTITY"
    is_active: bool = True
    notes: str | None = None


class ContactUpdate(BaseModel):
    contact_origin_id: uuid.UUID | None = None
    person_type: str | None = None
    document: str | None = None
    name: str | None = None
    trade_name: str | None = None
    state_registration: str | None = None

    full_name: str | None = None
    position: str | None = None
    email: str | None = None
    phone: str | None = None
    mobile: str | None = None

    address_street: str | None = None
    address_number: str | None = None
    address_neighborhood: str | None = None
    address_city: str | None = None
    address_state: str | None = None
    address_zip_code: str | None = None

    is_customer: bool | None = None
    is_supplier: bool | None = None
    is_carrier: bool | None = None

    credit_limit: Decimal | None = None
    is_active: bool | None = None
    notes: str | None = None


class ContactResponse(ContactBase):
    contact_origin_id: uuid.UUID | None = None
    normalized_phone: str | None = None
    first_contact_at: datetime | None = None
    last_contact_at: datetime | None = None
    id: uuid.UUID
    organization_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 7. ESQUEMAS DE EQUIPE / GRUPO DE TRABALHO MULTIMODULAR (Team)
# ==============================================================================

class TeamMemberInfo(BaseModel):
    id: uuid.UUID
    full_name: str
    email: EmailStr
    is_seller: bool = False
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class TeamBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    code: str | None = Field(default=None, max_length=50)
    module_category: Literal["SALES", "PURCHASING", "INVENTORY", "FINANCE", "SUPPORT"] = "SALES"
    description: str | None = Field(default=None, max_length=255)
    leader_id: uuid.UUID | None = None
    is_active: bool = True

    model_config = ConfigDict(extra="forbid")


class TeamCreate(TeamBase):
    member_ids: list[uuid.UUID] = Field(default_factory=list)


class TeamUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(default=None, max_length=50)
    module_category: Literal["SALES", "PURCHASING", "INVENTORY", "FINANCE", "SUPPORT"] | None = None
    description: str | None = Field(default=None, max_length=255)
    leader_id: uuid.UUID | None = None
    is_active: bool | None = None
    member_ids: list[uuid.UUID] | None = None

    model_config = ConfigDict(extra="forbid")


class TeamResponse(TeamBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    leader_name: str | None = None
    members: list[TeamMemberInfo] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TeamMemberAddRequest(BaseModel):
    user_ids: list[uuid.UUID]
