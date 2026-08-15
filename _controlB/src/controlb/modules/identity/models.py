"""
models.py - Mapeamento Objeto-Relacional (SQLAlchemy ORM Models)

Define a estrutura das tabelas do banco de dados PostgreSQL para o módulo Identity:
1. Organization: Empresas e unidades de negócio.
2. Role: Cargos e permissões vinculados a uma organização.
3. User: Contas de usuários autenticáveis vinculadas a organização e cargo.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from controlb.db import Base


def utcnow() -> datetime:
    """Função utilitária que retorna o horário atual com fuso horário UTC padronizado."""
    return datetime.now(timezone.utc)


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

    # Relacionamentos 1-para-N (Uma organização possui múltiplos usuários e múltiplos cargos)
    users: Mapped[list["User"]] = relationship(back_populates="organization")
    roles: Mapped[list["Role"]] = relationship(back_populates="organization")


class Role(Base):
    """
    Tabela 'role' - Representa os cargos / funções dos colaboradores dentro de uma organização.
    """
    __tablename__ = "role"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Chave estrangeira ligando o cargo obrigatoriamente a uma organização existente
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)

    name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True) # Descrição opcional

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamentos bidirecionais
    organization: Mapped["Organization"] = relationship(back_populates="roles")
    users: Mapped[list["User"]] = relationship(back_populates="role")


class User(Base):
    """
    Tabela 'user' - Representa os usuários autenticáveis do ControlB.
    """
    __tablename__ = "user"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Chave estrangeira obrigatória para a organização
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    # Chave estrangeira opcional para o cargo (pode ser nulo)
    role_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("role.id"), nullable=True)

    # E-mail com índice exclusivo (não permite e-mails duplicados e acelera buscas no login)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False) # Hash seguro Argon2

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamentos ORM
    organization: Mapped["Organization"] = relationship(back_populates="users")
    role: Mapped["Role"] = relationship(back_populates="users")