"""
models.py - Mapeamento Objeto-Relacional (SQLAlchemy ORM Models)

Define a estrutura das tabelas do banco de dados PostgreSQL para o módulo Identity:
1. Organization: Empresas e unidades de negócio.
2. Permission: Catálogo de permissões de acesso do sistema.
3. Role: Cargos com matriz de permissões vinculados a uma organização.
4. User: Contas de usuários autenticáveis vinculadas a organização e cargo.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Index, Numeric, String, Table, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from controlb.db import Base


# ==============================================================================
# 0. TABELAS ASSOCIATIVAS N:N (Role <-> Permission, Team <-> User)
# ==============================================================================

role_permission = Table(
    "role_permission",
    Base.metadata,
    Column("role_id", UUID(as_uuid=True), ForeignKey("role.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", UUID(as_uuid=True), ForeignKey("permission.id", ondelete="CASCADE"), primary_key=True)
)

team_member = Table(
    "team_member",
    Base.metadata,
    Column("team_id", UUID(as_uuid=True), ForeignKey("team.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), primary_key=True),
    Column("role_in_team", String(50), default="MEMBER")
)


def utcnow() -> datetime:
    """Função utilitária que retorna o horário atual com fuso horário UTC padronizado."""
    return datetime.now(timezone.utc)


# ==============================================================================
# 1. MODELO ORGANIZAÇÃO (Organization)
# ==============================================================================

class Organization(Base):
    """
    Tabela 'organization' - Representa uma empresa ou filial no sistema.
    """
    __tablename__ = "organization"

    # Chave primária UUID gerada automaticamente (uuid4)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False) # Nome da organização (não nulo)
    
    # Campos de controle de status e auditoria temporal
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamentos 1-para-N (Uma organização possui múltiplos usuários, cargos, equipes e contatos)
    users: Mapped[list["User"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    roles: Mapped[list["Role"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    teams: Mapped[list["Team"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    contacts: Mapped[list["Contact"]] = relationship(back_populates="organization", cascade="all, delete-orphan")



# ==============================================================================
# 2. MODELO PERMISSÃO (Permission)
# ==============================================================================

class Permission(Base):
    """
    Tabela 'permission' - Catálogo de ações e telas autorizáveis do ControlB.
    """
    __tablename__ = "permission"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True) # Ex: "users:create"
    name: Mapped[str] = mapped_column(String(100), nullable=False)                         # Ex: "Cadastrar Usuários"
    module: Mapped[str] = mapped_column(String(50), nullable=False, index=True)           # Ex: "Identity", "Stock"
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamento de volta para os cargos que contêm esta permissão
    roles: Mapped[list["Role"]] = relationship(secondary=role_permission, back_populates="permissions")


# ==============================================================================
# 3. MODELO CARGO / FUNÇÃO (Role)
# ==============================================================================

class Role(Base):
    """
    Tabela 'role' - Representa os cargos / funções dos colaboradores dentro de uma organização.
    """
    __tablename__ = "role"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Chave estrangeira ligando o cargo obrigatoriamente a uma organização existente
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)

    name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True) # Descrição opcional

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamentos bidirecionais
    organization: Mapped["Organization"] = relationship(back_populates="roles")
    users: Mapped[list["User"]] = relationship(back_populates="role")

    # Permissões atribuídas ao cargo (carregadas automaticamente nas consultas)
    permissions: Mapped[list["Permission"]] = relationship(
        secondary=role_permission,
        back_populates="roles",
        lazy="selectin"
    )


# ==============================================================================
# 4. MODELO USUÁRIO (User)
# ==============================================================================

class User(Base):
    """
    Tabela 'user' - Representa os usuários autenticáveis do ControlB.
    """
    __tablename__ = "user"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Chave estrangeira obrigatória para a organização
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    # Chave estrangeira opcional para o cargo (pode ser nulo)
    role_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("role.id", ondelete="SET NULL"), nullable=True)

    # E-mail com índice exclusivo (não permite e-mails duplicados e acelera buscas no login)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False) # Hash seguro Argon2

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_seller: Mapped[bool] = mapped_column(Boolean, default=False, index=True) # Identifica colaboradores que atuam como Vendedores
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamentos ORM
    organization: Mapped["Organization"] = relationship(back_populates="users")
    role: Mapped["Role"] = relationship(back_populates="users", lazy="selectin")
    teams: Mapped[list["Team"]] = relationship(secondary=team_member, back_populates="members", lazy="selectin")


# ==============================================================================
# 5. MODELO CONTATO / PARCEIRO UNIFICADO (Contact - Padrão Odoo res.partner)
# ==============================================================================

class ContactOrigin(Base):
    __tablename__ = "contact_origin"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_contact_origin_name"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    channel_type: Mapped[str] = mapped_column(String(50), default="OTHER", server_default="OTHER", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class Contact(Base):
    """
    Tabela 'contact' - Cadastro Unificado de Parceiros e Contatos (Padrão Odoo res.partner).
    Representa qualquer Pessoa Física (PF) ou Jurídica (PJ) que interage com o ERP:
    - Clientes (is_customer=True) -> Utilizado em Vendas, CRM, PDV e Faturamento a Receber
    - Fornecedores (is_supplier=True) -> Utilizado em Compras, Suprimentos e Faturamento a Pagar
    - Transportadoras (is_carrier=True) -> Utilizado em Logística e Expedição
    - Interlocutores/Contatos Institucionais (position, mobile, etc.)
    """
    __tablename__ = "contact"
    __table_args__ = (UniqueConstraint("organization_id", "normalized_phone", name="uq_contact_org_phone"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)

    person_type: Mapped[str] = mapped_column(String(10), default="PJ", index=True)  # "PJ" ou "PF"
    document: Mapped[str | None] = mapped_column(String(30), index=True, nullable=True)  # CNPJ ou CPF
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)  # Razão Social ou Nome Completo
    trade_name: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Nome Fantasia
    state_registration: Mapped[str | None] = mapped_column(String(50), nullable=True)  # Inscrição Estadual (IE)

    # Interlocutor / Pessoa de contato institucional
    full_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    name_manually_set: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    position: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Cargo / Função

    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(50), nullable=True)
    normalized_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    contact_origin_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contact_origin.id", ondelete="SET NULL"))
    first_contact_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_contact_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Endereço
    address_street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address_neighborhood: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address_state: Mapped[str | None] = mapped_column(String(10), nullable=True)
    address_zip_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Perfis / Papéis de Negócio (Odoo res.partner pattern)
    is_customer: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_supplier: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_carrier: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # Governança e Rastreabilidade de Origem
    credit_limit: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    origin_module: Mapped[str] = mapped_column(String(50), default="IDENTITY", nullable=False, index=True)  # "SALES", "CRM", "PURCHASES", "IDENTITY"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamentos
    organization: Mapped["Organization"] = relationship(back_populates="contacts")


# ==============================================================================
# 6. MODELO EQUIPE / GRUPO DE TRABALHO MULTIMODULAR (Team)
# ==============================================================================

class Team(Base):
    """
    Tabela 'team' - Equipes e Grupos de Trabalho Multimodulares.
    Organiza colaboradores por carteiras comerciais (SALES), compras (PURCHASING),
    estoque (INVENTORY), etc., com controle de liderança/gestão e escopo de visibilidade.
    """
    __tablename__ = "team"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "module_category", "name",
            name="uq_team_organization_category_name",
        ),
        UniqueConstraint(
            "organization_id", "module_category", "code",
            name="uq_team_organization_category_code",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)

    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    module_category: Mapped[str] = mapped_column(String(50), default="SALES", nullable=False, index=True) # SALES Ã© compartilhado por CRM e Vendas
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    leader_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id", ondelete="SET NULL"), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamentos
    organization: Mapped["Organization"] = relationship(back_populates="teams")
    leader: Mapped["User | None"] = relationship(foreign_keys=[leader_id], lazy="selectin")
    members: Mapped[list["User"]] = relationship(secondary=team_member, back_populates="teams", lazy="selectin")


class ContactIdentifier(Base):
    __tablename__ = "contact_identifier"
    __table_args__ = (UniqueConstraint("organization_id", "kind", "value", name="uq_contact_identifier_org_value"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contact.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    original_value: Mapped[str] = mapped_column(Text, nullable=False)


class ContactMigrationRun(Base):
    __tablename__ = "contact_migration_run"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    backup_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="APPLIED", nullable=False)
    journal: Mapped[dict] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
