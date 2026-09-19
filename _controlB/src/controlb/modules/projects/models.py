"""
modules/projects/models.py - Modelos ORM do Módulo de Projetos & Operações

Define a estrutura de dados relacional para:
1. Cadastros de apoio: ProjectType, WorkOrderType
2. Workflows configuráveis: WorkflowTemplate, WorkflowStage
3. Projetos: Project, ProjectMember, ProjectStageHistory
4. Ordens de Trabalho: WorkOrder
5. Tarefas: Task, TaskAssignment, TaskDependency
6. Issues: Issue
7. Checklists: ChecklistTemplate, ChecklistTemplateItem, Checklist, ChecklistItem
8. Comentários: Comment

Integra-se com BusinessDocument, DocumentEvent e DocumentSequence do módulo Documents
para identidade documental, timeline e numeração automática.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from controlb.db import Base
from controlb.modules.documents.models import BusinessDocument


def utcnow() -> datetime:
    """Função utilitária que retorna o horário atual com fuso horário UTC padronizado."""
    return datetime.now(timezone.utc)


# ==============================================================================
# 1. CADASTROS DE APOIO — Tipos e Configurações
# ==============================================================================

class ProjectType(Base):
    """
    Tabela 'project_type' - Tipos configuráveis de projeto por organização.

    Cada organização pode definir seus próprios tipos:
    - Instalação Fotovoltaica, CFTV, Rede, Manutenção, Desenvolvimento, etc.
    O tipo agrupa configurações como workflow padrão e prefixo de numeração.
    """
    __tablename__ = "project_type"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_project_type_org_code"),
        UniqueConstraint("organization_id", "name", name="uq_project_type_org_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str] = mapped_column(String(20), default="#6366f1", nullable=False)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    prefix: Mapped[str] = mapped_column(String(10), default="PRJ", nullable=False)

    default_workflow_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflow_template.id", ondelete="SET NULL"), nullable=True
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relacionamentos
    default_workflow: Mapped["WorkflowTemplate | None"] = relationship(
        lazy="select", foreign_keys=[default_workflow_id]
    )
    projects: Mapped[list["Project"]] = relationship(back_populates="project_type", lazy="noload")


class WorkOrderType(Base):
    """
    Tabela 'work_order_type' - Tipos configuráveis de ordem de trabalho.

    Exemplos: Instalação, Manutenção Corretiva, Manutenção Preventiva,
    Vistoria, Montagem, Desenvolvimento, etc.
    """
    __tablename__ = "work_order_type"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_work_order_type_org_code"),
        UniqueConstraint("organization_id", "name", name="uq_work_order_type_org_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str] = mapped_column(String(20), default="#8b5cf6", nullable=False)
    prefix: Mapped[str] = mapped_column(String(10), default="OS", nullable=False)

    default_workflow_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflow_template.id", ondelete="SET NULL"), nullable=True
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relacionamentos
    default_workflow: Mapped["WorkflowTemplate | None"] = relationship(
        lazy="select", foreign_keys=[default_workflow_id]
    )


# ==============================================================================
# 2. WORKFLOWS CONFIGURÁVEIS — Templates de Fluxo de Trabalho
# ==============================================================================

class WorkflowTemplate(Base):
    """
    Tabela 'workflow_template' - Template de fluxo de trabalho reutilizável.

    Cada workflow define uma sequência de etapas (stages) que projetos ou
    ordens percorrem. Uma organização pode ter vários workflows:
    - "Fluxo Solar": Proposta → Projeto → Compras → Instalação → Vistoria → Entregue
    - "Fluxo Manutenção": Triagem → Em Atendimento → Concluído
    - "Fluxo Dev": Backlog → Em Desenvolvimento → Review → QA → Deploy

    Inspirado no padrão CRMStage já existente no módulo CRM, mas com suporte
    a múltiplos templates na mesma organização.
    """
    __tablename__ = "workflow_template"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_workflow_template_org_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_entity: Mapped[str] = mapped_column(
        String(50), default="PROJECT", nullable=False
    )  # PROJECT, WORK_ORDER, TASK — indica a qual entidade o workflow se aplica

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relacionamentos
    stages: Mapped[list["WorkflowStage"]] = relationship(
        back_populates="workflow",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="WorkflowStage.position",
    )


class WorkflowStage(Base):
    """
    Tabela 'workflow_stage' - Etapa individual dentro de um WorkflowTemplate.

    Cada etapa possui:
    - position: ordem de exibição (1, 2, 3...)
    - color: cor do card no Kanban
    - is_initial: flag para etapa padrão ao criar novo projeto
    - is_terminal: flag para etapas finais (Concluído, Cancelado)
    - allowed_transitions: lista de IDs de etapas para as quais se pode transicionar (JSON)
    """
    __tablename__ = "workflow_stage"
    __table_args__ = (
        UniqueConstraint(
            "workflow_id", "name", name="uq_workflow_stage_name"
        ),
        UniqueConstraint(
            "workflow_id", "position", name="uq_workflow_stage_position"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_template.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    color: Mapped[str] = mapped_column(String(20), default="#6366f1", nullable=False)

    is_initial: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_terminal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Lista de UUIDs das etapas permitidas como destino (vazio = qualquer transição permitida)
    allowed_transitions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relacionamentos
    workflow: Mapped["WorkflowTemplate"] = relationship(back_populates="stages")


# ==============================================================================
# 3. PROJETOS — Entidade Central do Módulo
# ==============================================================================

class Project(Base):
    """
    Tabela 'project' - Projeto operacional.

    Representa uma unidade de execução que pode ter sido originada de:
    - Um Pedido de Venda (SalesOrder)
    - Um Orçamento (SalesQuote)
    - Uma Oportunidade CRM (Opportunity)
    - Criação manual (projeto interno)

    Integra-se ao hub documental BusinessDocument para numeração automática,
    timeline de eventos e rastreabilidade transversal.

    Status possíveis: draft, planning, in_progress, on_hold, completed,
                      cancelled, archived
    """
    __tablename__ = "project"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["business_document.id", "business_document.organization_id"],
            ondelete="RESTRICT",
            name="fk_project_document_org",
        ),
        UniqueConstraint("document_id", name="uq_project_document"),
        UniqueConstraint("id", "organization_id", name="uq_project_id_org"),
        UniqueConstraint("organization_id", "project_number", name="uq_project_org_number"),
        Index("ix_project_org_status", "organization_id", "status"),
        Index("ix_project_org_type", "organization_id", "project_type_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Identificação
    project_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Classificação
    project_type_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("project_type.id", ondelete="SET NULL"), nullable=True
    )
    priority: Mapped[str] = mapped_column(String(20), default="MEDIUM", nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    # Status e Workflow
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False, index=True)
    workflow_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflow_template.id", ondelete="SET NULL"), nullable=True
    )
    current_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflow_stage.id", ondelete="SET NULL"), nullable=True
    )
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Datas
    planned_start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    planned_end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Orçamento
    estimated_budget: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    actual_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    estimated_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    actual_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)

    # Responsáveis
    manager_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("team.id", ondelete="SET NULL"), nullable=True
    )

    # Cliente
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("customer.id", ondelete="SET NULL"), nullable=True
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contact.id", ondelete="SET NULL"), nullable=True
    )

    # Origens (apenas uma preenchida = rastreabilidade da venda/oportunidade que gerou o projeto)
    sales_order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sales_order.id", ondelete="SET NULL"), nullable=True
    )
    sales_quote_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sales_quote.id", ondelete="SET NULL"), nullable=True
    )
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("opportunity.id", ondelete="SET NULL"), nullable=True
    )

    # Centro de Custo
    cost_center_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cost_center.id", ondelete="SET NULL"), nullable=True
    )

    # Endereço de execução
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    zip_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)

    # Payload extensível
    custom_fields: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_billable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Auditoria
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relacionamentos
    document: Mapped["BusinessDocument"] = relationship(lazy="select")
    project_type: Mapped["ProjectType | None"] = relationship(back_populates="projects", lazy="selectin")
    workflow: Mapped["WorkflowTemplate | None"] = relationship(lazy="selectin", foreign_keys=[workflow_id])
    current_stage: Mapped["WorkflowStage | None"] = relationship(lazy="selectin", foreign_keys=[current_stage_id])

    members: Mapped[list["ProjectMember"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", lazy="selectin"
    )
    stage_history: Mapped[list["ProjectStageHistory"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", lazy="noload",
        order_by="ProjectStageHistory.created_at.desc()",
    )
    work_orders: Mapped[list["WorkOrder"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", lazy="noload"
    )
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", lazy="noload"
    )
    issues: Mapped[list["Issue"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", lazy="noload"
    )
    comments: Mapped[list["Comment"]] = relationship(
        primaryjoin="and_(Comment.project_id == Project.id)",
        cascade="all, delete-orphan", lazy="noload",
        foreign_keys="Comment.project_id",
    )


class ProjectMember(Base):
    """
    Tabela 'project_member' - Participantes de um projeto.

    Roles possíveis:
    - manager: gerente do projeto (pode haver apenas 1, espelha manager_id)
    - member: membro ativo da equipe
    - observer: apenas visualização
    """
    __tablename__ = "project_member"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_member_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(50), default="member", nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    added_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )

    # Relacionamentos
    project: Mapped["Project"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(lazy="selectin", foreign_keys=[user_id])


class ProjectStageHistory(Base):
    """
    Tabela 'project_stage_history' - Registro imutável de transições de etapa.

    Cada registro representa uma mudança de etapa no workflow do projeto.
    Funciona como complemento ao DocumentEvent, com campos tipados para
    consultas rápidas de etapas anteriores.
    """
    __tablename__ = "project_stage_history"
    __table_args__ = (
        Index("ix_project_stage_history_project", "project_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), nullable=False
    )
    from_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflow_stage.id", ondelete="SET NULL"), nullable=True
    )
    to_stage_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_stage.id", ondelete="CASCADE"), nullable=False
    )
    changed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relacionamentos
    project: Mapped["Project"] = relationship(back_populates="stage_history")
    from_stage: Mapped["WorkflowStage | None"] = relationship(
        lazy="selectin", foreign_keys=[from_stage_id]
    )
    to_stage: Mapped["WorkflowStage"] = relationship(
        lazy="selectin", foreign_keys=[to_stage_id]
    )


# ==============================================================================
# 4. ORDENS DE TRABALHO — Unidades de Execução
# ==============================================================================

class WorkOrder(Base):
    """
    Tabela 'work_order' - Ordem de trabalho / serviço / produção.

    Uma ordem de trabalho é uma unidade executável dentro de um projeto.
    Um projeto de instalação solar pode ter:
    - OS-001: Instalação estrutura
    - OS-002: Instalação painéis
    - OS-003: Instalação inversor
    - OS-004: Vistoria final

    Cada ordem pode ter seu próprio workflow, tarefas e equipe.

    Status possíveis: draft, scheduled, in_progress, on_hold,
                      completed, cancelled
    """
    __tablename__ = "work_order"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["business_document.id", "business_document.organization_id"],
            ondelete="RESTRICT",
            name="fk_work_order_document_org",
        ),
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["project.id", "project.organization_id"],
            ondelete="RESTRICT",
            name="fk_work_order_project_org",
        ),
        UniqueConstraint("document_id", name="uq_work_order_document"),
        UniqueConstraint("id", "organization_id", name="uq_work_order_id_org"),
        UniqueConstraint("organization_id", "order_number", name="uq_work_order_org_number"),
        Index("ix_work_order_org_status", "organization_id", "status"),
        Index("ix_work_order_project", "project_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Identificação
    order_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Classificação
    order_type_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("work_order_type.id", ondelete="SET NULL"), nullable=True
    )
    priority: Mapped[str] = mapped_column(String(20), default="MEDIUM", nullable=False)

    # Status e Workflow
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False, index=True)
    workflow_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflow_template.id", ondelete="SET NULL"), nullable=True
    )
    current_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflow_stage.id", ondelete="SET NULL"), nullable=True
    )
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Datas
    scheduled_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Responsáveis
    responsible_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("team.id", ondelete="SET NULL"), nullable=True
    )

    # Endereço (herda do projeto ou pode ser diferente)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Custos
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    actual_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    estimated_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    actual_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)

    # Notas e extras
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    custom_fields: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # Auditoria
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relacionamentos
    document: Mapped["BusinessDocument"] = relationship(lazy="select", overlaps="work_orders")
    project: Mapped["Project | None"] = relationship(
        back_populates="work_orders", overlaps="document"
    )
    order_type: Mapped["WorkOrderType | None"] = relationship(lazy="selectin")
    workflow: Mapped["WorkflowTemplate | None"] = relationship(lazy="selectin", foreign_keys=[workflow_id])
    current_stage: Mapped["WorkflowStage | None"] = relationship(lazy="selectin", foreign_keys=[current_stage_id])

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="work_order", cascade="all, delete-orphan", lazy="noload"
    )
    issues: Mapped[list["Issue"]] = relationship(
        back_populates="work_order", cascade="all, delete-orphan", lazy="noload"
    )


# ==============================================================================
# 5. TAREFAS — Unidades Executáveis Individuais
# ==============================================================================

class Task(Base):
    """
    Tabela 'task' - Tarefa executável.

    Tarefas são as menores unidades de trabalho. Podem estar vinculadas a:
    - Um projeto diretamente
    - Uma ordem de trabalho (que por sua vez pertence a um projeto)

    Status possíveis: backlog, todo, in_progress, in_review,
                      blocked, done, cancelled
    """
    __tablename__ = "task"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["business_document.id", "business_document.organization_id"],
            ondelete="RESTRICT",
            name="fk_task_document_org",
        ),
        UniqueConstraint("document_id", name="uq_task_document"),
        UniqueConstraint("organization_id", "task_number", name="uq_task_org_number"),
        Index("ix_task_org_status", "organization_id", "status"),
        Index("ix_task_project", "project_id"),
        Index("ix_task_work_order", "work_order_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Vínculos (ao menos um deve estar preenchido)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), nullable=True
    )
    work_order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("work_order.id", ondelete="CASCADE"), nullable=True
    )

    # Identificação
    task_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Classificação
    priority: Mapped[str] = mapped_column(String(20), default="MEDIUM", nullable=False)
    task_type: Mapped[str] = mapped_column(String(50), default="task", nullable=False)

    # Status
    status: Mapped[str] = mapped_column(String(50), default="todo", nullable=False, index=True)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Datas
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Tempo
    estimated_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    actual_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)

    # Posição (para ordenação no Kanban e listas)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Auditoria
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relacionamentos
    document: Mapped["BusinessDocument"] = relationship(lazy="select")
    project: Mapped["Project | None"] = relationship(back_populates="tasks")
    work_order: Mapped["WorkOrder | None"] = relationship(back_populates="tasks")

    assignments: Mapped[list["TaskAssignment"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", lazy="selectin"
    )
    dependencies: Mapped[list["TaskDependency"]] = relationship(
        back_populates="dependent_task",
        foreign_keys="TaskDependency.dependent_task_id",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    checklists: Mapped[list["Checklist"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", lazy="noload"
    )
    comments: Mapped[list["Comment"]] = relationship(
        primaryjoin="and_(Comment.task_id == Task.id)",
        cascade="all, delete-orphan", lazy="noload",
        foreign_keys="Comment.task_id",
    )


class TaskAssignment(Base):
    """
    Tabela 'task_assignment' - Vínculo entre tarefa e responsáveis.
    Uma tarefa pode ter múltiplos responsáveis.
    """
    __tablename__ = "task_assignment"
    __table_args__ = (
        UniqueConstraint("task_id", "user_id", name="uq_task_assignment_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("task.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(50), default="assignee", nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    assigned_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )

    # Relacionamentos
    task: Mapped["Task"] = relationship(back_populates="assignments")
    user: Mapped["User"] = relationship(lazy="selectin", foreign_keys=[user_id])


class TaskDependency(Base):
    """
    Tabela 'task_dependency' - Dependências entre tarefas.

    dependent_task_id DEPENDE DE dependency_task_id.
    Tipo: finish_to_start (padrão), start_to_start, finish_to_finish.
    """
    __tablename__ = "task_dependency"
    __table_args__ = (
        UniqueConstraint(
            "dependent_task_id", "dependency_task_id",
            name="uq_task_dependency_pair"
        ),
        CheckConstraint(
            "dependent_task_id <> dependency_task_id",
            name="ck_task_dependency_not_self"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dependent_task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("task.id", ondelete="CASCADE"), nullable=False
    )
    dependency_task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("task.id", ondelete="CASCADE"), nullable=False
    )
    dependency_type: Mapped[str] = mapped_column(
        String(50), default="finish_to_start", nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relacionamentos
    dependent_task: Mapped["Task"] = relationship(
        back_populates="dependencies", foreign_keys=[dependent_task_id]
    )
    dependency_task: Mapped["Task"] = relationship(
        foreign_keys=[dependency_task_id], lazy="selectin"
    )


# ==============================================================================
# 6. OCORRÊNCIAS / PENDÊNCIAS
# ==============================================================================

class Issue(Base):
    """
    Tabela 'issue' - Ocorrências, pendências e bloqueios.

    Registra problemas encontrados durante a execução:
    - Defeito encontrado
    - Material em falta
    - Alteração solicitada pelo cliente
    - Condição climática adversa
    - Acesso negado ao local

    Severity: low, medium, high, critical
    Status: open, investigating, resolved, closed, wont_fix
    """
    __tablename__ = "issue"
    __table_args__ = (
        UniqueConstraint("organization_id", "issue_number", name="uq_issue_org_number"),
        Index("ix_issue_org_status", "organization_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )

    # Vínculos
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), nullable=True
    )
    work_order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("work_order.id", ondelete="CASCADE"), nullable=True
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("task.id", ondelete="SET NULL"), nullable=True
    )

    # Identificação
    issue_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Classificação
    issue_type: Mapped[str] = mapped_column(String(50), default="problem", nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="open", nullable=False, index=True)
    impact_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    impact_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Resolução
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )

    # Responsável
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )

    # Auditoria
    reported_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relacionamentos
    project: Mapped["Project | None"] = relationship(back_populates="issues")
    work_order: Mapped["WorkOrder | None"] = relationship(back_populates="issues")
    comments: Mapped[list["Comment"]] = relationship(
        primaryjoin="and_(Comment.issue_id == Issue.id)",
        cascade="all, delete-orphan", lazy="noload",
        foreign_keys="Comment.issue_id",
    )


# ==============================================================================
# 7. CHECKLISTS — Templates e Instâncias
# ==============================================================================

class ChecklistTemplate(Base):
    """
    Tabela 'checklist_template' - Template reutilizável de checklist.

    Exemplo: "Checklist de Vistoria Fotovoltaica"
    - [x] Verificar aterramento
    - [x] Verificar tensão dos painéis
    - [x] Testar inversor
    - [x] Fotografar instalação
    """
    __tablename__ = "checklist_template"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_checklist_template_org_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relacionamentos
    items: Mapped[list["ChecklistTemplateItem"]] = relationship(
        back_populates="template", cascade="all, delete-orphan", lazy="selectin",
        order_by="ChecklistTemplateItem.position",
    )


class ChecklistTemplateItem(Base):
    """Tabela 'checklist_template_item' - Item de um template de checklist."""
    __tablename__ = "checklist_template_item"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("checklist_template.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(String(500), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    template: Mapped["ChecklistTemplate"] = relationship(back_populates="items")


class Checklist(Base):
    """
    Tabela 'checklist' - Instância de checklist vinculada a uma tarefa ou ordem.

    Pode ser instanciado a partir de um template ou criado avulso.
    """
    __tablename__ = "checklist"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("task.id", ondelete="CASCADE"), nullable=True
    )
    work_order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("work_order.id", ondelete="SET NULL"), nullable=True
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("checklist_template.id", ondelete="SET NULL"), nullable=True
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    total_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    checked_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relacionamentos
    task: Mapped["Task | None"] = relationship(back_populates="checklists")
    items: Mapped[list["ChecklistItem"]] = relationship(
        back_populates="checklist", cascade="all, delete-orphan", lazy="selectin",
        order_by="ChecklistItem.position",
    )


class ChecklistItem(Base):
    """Tabela 'checklist_item' - Item individual de um checklist instanciado."""
    __tablename__ = "checklist_item"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    checklist_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("checklist.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(String(500), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_checked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checked_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )

    # Relacionamentos
    checklist: Mapped["Checklist"] = relationship(back_populates="items")


# ==============================================================================
# 8. COMENTÁRIOS — Discussão Contextual
# ==============================================================================

class Comment(Base):
    """
    Tabela 'comment' - Comentários vinculados a projetos, ordens, tarefas ou issues.

    Usa 4 FKs opcionais (apenas uma preenchida por vez) para simplicidade
    e consultas diretas sem JOIN polimórfico.
    """
    __tablename__ = "comment"
    __table_args__ = (
        Index("ix_comment_project", "project_id"),
        Index("ix_comment_work_order", "work_order_id"),
        Index("ix_comment_task", "task_id"),
        Index("ix_comment_issue", "issue_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )

    # Vínculos — apenas um preenchido por vez
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), nullable=True
    )
    work_order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("work_order.id", ondelete="CASCADE"), nullable=True
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("task.id", ondelete="CASCADE"), nullable=True
    )
    issue_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("issue.id", ondelete="CASCADE"), nullable=True
    )

    # Conteúdo
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Auditoria
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relacionamentos
    author: Mapped["User"] = relationship(lazy="selectin", foreign_keys=[author_id])


# ==============================================================================
# IMPORTS NECESSÁRIOS PARA REFERÊNCIAS FORWARD
# ==============================================================================
# Os imports abaixo garantem que as referências forward de tipos como "User"
# sejam resolvidas. O SQLAlchemy resolve strings como "User" via registry global.
from controlb.modules.identity.models import Contact, Team, User  # noqa: E402, F401
from controlb.modules.sales.models import Customer  # noqa: E402, F401
