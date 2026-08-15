"""
schemas.py - Contratos de Dados e Validações (Pydantic Models)

Define os esquemas de validação de entrada (Requests) e formatação de saída (Responses)
para o módulo de Identidade (Organizações, Cargos e Usuários).
Garante tipagem estrita, prevenção de vazamento de senhas e serialização segura.
"""

import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr


# ==============================================================================
# 1. ESQUEMAS DE ORGANIZAÇÃO (Organization)
# ==============================================================================

class OrganizationBase(BaseModel):
    """Atributos compartilhados por todos os esquemas de Organização."""
    name: str                           # Nome da empresa/organização
    is_active: bool = True              # Se a organização está ativa no sistema


class OrganizationCreate(OrganizationBase):
    """Dados necessários para cadastrar uma nova Organização (Payload de Entrada)."""
    pass


class OrganizationResponse(OrganizationBase):
    """
    Dados retornados para o cliente (Payload de Saída).
    Inclui os identificadores únicos e timestamps gerados pelo banco de dados.
    """
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    # Permite ao Pydantic ler os dados diretamente a partir de objetos ORM do SQLAlchemy
    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 2. ESQUEMAS DE CARGO / FUNÇÃO (Role)
# ==============================================================================

class RoleBase(BaseModel):
    """Atributos básicos de um Cargo (Role)."""
    name: str                           # Nome do cargo (ex: Administrador, Vendedor, Gerente)
    description: str | None = None      # Descrição opcional das atribuições do cargo
    is_active: bool = True              # Status de ativação


class RoleCreate(RoleBase):
    """Dados necessários para criar um novo Cargo."""
    organization_id: uuid.UUID          # ID da organização à qual este cargo pertence


class RoleResponse(RoleBase):
    """Dados do Cargo enviados na resposta da API."""
    id: uuid.UUID
    organization_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 3. ESQUEMAS DE USUÁRIO (User)
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
