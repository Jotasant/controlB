"""
modules/projects/service.py - Camada de Lógica de Negócio (Service Layer)

Orquestra as operações do módulo de Projetos & Operações:
1. Criação integrada com BusinessDocument + DocumentSequence (numeração automática)
2. Registro de eventos na timeline via DocumentEvent
3. Validação de transições de workflow
4. Cálculo de progresso e totais
5. Instanciação de checklists a partir de templates

Segue o padrão já utilizado nos módulos Sales, Purchasing e Billing.
"""

import math
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from controlb.logger import logger
from controlb.modules.documents.models import (
    BusinessDocument,
    DocumentEvent,
    DocumentRelation,
    DocumentSequence,
)
from controlb.modules.identity.models import User
from controlb.modules.projects import repository as repo
from controlb.modules.projects import schemas
from controlb.modules.projects.models import (
    Project,
    ProjectMember,
    WorkflowStage,
    WorkOrder,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ==============================================================================
# UTILITÁRIOS INTERNOS — Numeração e Documentos
# ==============================================================================

def _next_document_number(
    db: Session,
    *,
    org_id: uuid.UUID,
    category: str,
    prefix: str,
) -> str:
    """
    Gera o próximo número sequencial utilizando DocumentSequence.

    Formato: PREFIX-ANO-NUMERO (ex: PRJ-2026-00001)
    Utiliza SELECT ... FOR UPDATE para evitar duplicatas em concorrência.
    """
    year = utcnow().year

    seq = db.execute(
        select(DocumentSequence)
        .where(
            DocumentSequence.organization_id == org_id,
            DocumentSequence.category == category,
            DocumentSequence.year == year,
        )
        .with_for_update()
    ).scalar_one_or_none()

    if seq is None:
        seq = DocumentSequence(
            organization_id=org_id,
            category=category,
            year=year,
            current_value=0,
            prefix=prefix,
        )
        db.add(seq)
        db.flush()

    seq.current_value += 1
    db.flush()

    return f"{prefix}-{year}-{seq.current_value:05d}"


def _create_business_document(
    db: Session,
    *,
    org_id: uuid.UUID,
    document_type: str,
    native_id: uuid.UUID,
    document_number: str,
    title: str,
    status: str,
    priority: str = "MEDIUM",
    description: str | None = None,
    responsible_id: uuid.UUID | None = None,
    created_by_id: uuid.UUID | None = None,
    category: str = "project",
    origin_module: str = "PROJECTS",
    tags: list[str] | None = None,
) -> BusinessDocument:
    """Cria o registro canônico no hub documental BusinessDocument."""
    doc = BusinessDocument(
        organization_id=org_id,
        category=category,
        document_type=document_type,
        native_id=native_id,
        document_number=document_number,
        title=title,
        current_status=status,
        priority=priority,
        description=description,
        tags=tags or [],
        origin_module=origin_module,
        responsible_id=responsible_id,
        created_by_id=created_by_id,
    )
    db.add(doc)
    db.flush()
    return doc


def _emit_event(
    db: Session,
    *,
    org_id: uuid.UUID,
    document_id: uuid.UUID,
    event_type: str,
    previous_status: str | None = None,
    new_status: str | None = None,
    metadata: dict | None = None,
    created_by_id: uuid.UUID | None = None,
    idempotency_key: str | None = None,
) -> DocumentEvent:
    """Registra um evento append-only na timeline do documento."""
    event = DocumentEvent(
        organization_id=org_id,
        document_id=document_id,
        event_type=event_type,
        previous_status=previous_status,
        new_status=new_status,
        event_metadata=metadata or {},
        created_by_id=created_by_id,
        idempotency_key=idempotency_key,
    )
    db.add(event)
    db.flush()
    return event


def _create_document_relation(
    db: Session,
    *,
    org_id: uuid.UUID,
    parent_document_id: uuid.UUID,
    child_document_id: uuid.UUID,
    relation_type: str,
    created_by_id: uuid.UUID | None = None,
    metadata: dict | None = None,
) -> DocumentRelation:
    """Cria vínculo de rastreabilidade entre dois documentos."""
    rel = DocumentRelation(
        organization_id=org_id,
        parent_document_id=parent_document_id,
        child_document_id=child_document_id,
        relation_type=relation_type,
        relation_metadata=metadata or {},
        created_by_id=created_by_id,
    )
    db.add(rel)
    db.flush()
    return rel


# ==============================================================================
# PROJECT TYPE
# ==============================================================================

def create_project_type(
    db: Session, *, org_id: uuid.UUID, data: schemas.ProjectTypeCreate
) -> schemas.ProjectTypeResponse:
    obj = repo.create_project_type(db, org_id=org_id, **data.model_dump())
    db.commit()
    db.refresh(obj)
    logger.info(f"✅ [PROJECTS] Tipo de projeto criado: {obj.name} (org={org_id})")
    return schemas.ProjectTypeResponse.model_validate(obj)


def list_project_types(
    db: Session, *, org_id: uuid.UUID, active_only: bool = True
) -> list[schemas.ProjectTypeResponse]:
    items = repo.list_project_types(db, org_id=org_id, active_only=active_only)
    return [schemas.ProjectTypeResponse.model_validate(i) for i in items]


def get_project_type(
    db: Session, *, org_id: uuid.UUID, type_id: uuid.UUID
) -> schemas.ProjectTypeResponse:
    obj = repo.get_project_type(db, org_id=org_id, type_id=type_id)
    if not obj:
        raise ValueError("Tipo de projeto não encontrado.")
    return schemas.ProjectTypeResponse.model_validate(obj)


def update_project_type(
    db: Session, *, org_id: uuid.UUID, type_id: uuid.UUID, data: schemas.ProjectTypeUpdate
) -> schemas.ProjectTypeResponse:
    obj = repo.get_project_type(db, org_id=org_id, type_id=type_id)
    if not obj:
        raise ValueError("Tipo de projeto não encontrado.")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(obj, key, val)
    db.commit()
    db.refresh(obj)
    return schemas.ProjectTypeResponse.model_validate(obj)


# ==============================================================================
# WORK ORDER TYPE
# ==============================================================================

def create_work_order_type(
    db: Session, *, org_id: uuid.UUID, data: schemas.WorkOrderTypeCreate
) -> schemas.WorkOrderTypeResponse:
    obj = repo.create_work_order_type(db, org_id=org_id, **data.model_dump())
    db.commit()
    db.refresh(obj)
    logger.info(f"✅ [PROJECTS] Tipo de OS criado: {obj.name} (org={org_id})")
    return schemas.WorkOrderTypeResponse.model_validate(obj)


def list_work_order_types(
    db: Session, *, org_id: uuid.UUID, active_only: bool = True
) -> list[schemas.WorkOrderTypeResponse]:
    items = repo.list_work_order_types(db, org_id=org_id, active_only=active_only)
    return [schemas.WorkOrderTypeResponse.model_validate(i) for i in items]


def get_work_order_type(
    db: Session, *, org_id: uuid.UUID, type_id: uuid.UUID
) -> schemas.WorkOrderTypeResponse:
    obj = repo.get_work_order_type(db, org_id=org_id, type_id=type_id)
    if not obj:
        raise ValueError("Tipo de OS não encontrado.")
    return schemas.WorkOrderTypeResponse.model_validate(obj)


def update_work_order_type(
    db: Session, *, org_id: uuid.UUID, type_id: uuid.UUID, data: schemas.WorkOrderTypeUpdate
) -> schemas.WorkOrderTypeResponse:
    obj = repo.get_work_order_type(db, org_id=org_id, type_id=type_id)
    if not obj:
        raise ValueError("Tipo de OS não encontrado.")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(obj, key, val)
    db.commit()
    db.refresh(obj)
    return schemas.WorkOrderTypeResponse.model_validate(obj)


# ==============================================================================
# WORKFLOW TEMPLATE
# ==============================================================================

def create_workflow(
    db: Session,
    *,
    org_id: uuid.UUID,
    data: schemas.WorkflowTemplateCreate,
) -> schemas.WorkflowTemplateResponse:
    wf = repo.create_workflow(
        db,
        org_id=org_id,
        name=data.name,
        description=data.description,
        target_entity=data.target_entity,
    )
    for stage_data in data.stages:
        repo.create_workflow_stage(db, workflow_id=wf.id, **stage_data.model_dump())
    db.commit()
    db.refresh(wf)
    logger.info(f"✅ [PROJECTS] Workflow criado: {wf.name} com {len(data.stages)} etapas (org={org_id})")
    return schemas.WorkflowTemplateResponse.model_validate(wf)


def list_workflows(
    db: Session,
    *,
    org_id: uuid.UUID,
    target_entity: str | None = None,
    active_only: bool = True,
) -> list[schemas.WorkflowTemplateResponse]:
    items = repo.list_workflows(db, org_id=org_id, target_entity=target_entity, active_only=active_only)
    return [schemas.WorkflowTemplateResponse.model_validate(i) for i in items]


def get_workflow(
    db: Session, *, org_id: uuid.UUID, workflow_id: uuid.UUID
) -> schemas.WorkflowTemplateResponse:
    wf = repo.get_workflow(db, org_id=org_id, workflow_id=workflow_id)
    if not wf:
        raise ValueError("Workflow não encontrado.")
    return schemas.WorkflowTemplateResponse.model_validate(wf)


def update_workflow(
    db: Session, *, org_id: uuid.UUID, workflow_id: uuid.UUID, data: schemas.WorkflowTemplateUpdate
) -> schemas.WorkflowTemplateResponse:
    wf = repo.get_workflow(db, org_id=org_id, workflow_id=workflow_id)
    if not wf:
        raise ValueError("Workflow não encontrado.")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(wf, key, val)
    db.commit()
    db.refresh(wf)
    return schemas.WorkflowTemplateResponse.model_validate(wf)


def add_workflow_stage(
    db: Session,
    *,
    org_id: uuid.UUID,
    workflow_id: uuid.UUID,
    data: schemas.WorkflowStageCreate,
) -> schemas.WorkflowStageResponse:
    workflow = repo.get_workflow(db, org_id=org_id, workflow_id=workflow_id)
    if not workflow:
        raise ValueError("Workflow não encontrado.")
    if data.is_initial:
        db.query(WorkflowStage).filter(WorkflowStage.workflow_id == workflow_id).update(
            {WorkflowStage.is_initial: False}
        )
    stage = repo.create_workflow_stage(db, workflow_id=workflow_id, **data.model_dump())
    db.commit()
    db.refresh(stage)
    return schemas.WorkflowStageResponse.model_validate(stage)


def update_workflow_stage(
    db: Session,
    *,
    org_id: uuid.UUID,
    stage_id: uuid.UUID,
    data: schemas.WorkflowStageUpdate,
) -> schemas.WorkflowStageResponse:
    stage = repo.get_workflow_stage(db, stage_id=stage_id)
    if not stage or not repo.get_workflow(db, org_id=org_id, workflow_id=stage.workflow_id):
        raise ValueError("Etapa não encontrada.")
    changes = data.model_dump(exclude_unset=True)
    if changes.get("is_initial"):
        db.query(WorkflowStage).filter(
            WorkflowStage.workflow_id == stage.workflow_id,
            WorkflowStage.id != stage.id,
        ).update({WorkflowStage.is_initial: False})
    for key, val in changes.items():
        setattr(stage, key, val)
    db.commit()
    db.refresh(stage)
    return schemas.WorkflowStageResponse.model_validate(stage)


# ==============================================================================
# PROJECT — Criação, Listagem, Atualização
# ==============================================================================

def create_project(
    db: Session,
    *,
    org_id: uuid.UUID,
    data: schemas.ProjectCreate,
    current_user: User,
) -> schemas.ProjectResponse:
    """
    Cria um novo projeto com integração completa ao hub documental:
    1. Gera número sequencial (PRJ-2026-00001)
    2. Cria BusinessDocument
    3. Cria Project vinculado
    4. Determina etapa inicial do workflow
    5. Adiciona criador como membro
    6. Emite evento CREATED na timeline
    """
    # Determinar prefixo a partir do tipo, se informado
    prefix = "PRJ"
    if data.project_type_id:
        pt = repo.get_project_type(db, org_id=org_id, type_id=data.project_type_id)
        if pt:
            prefix = pt.prefix
            # Se não informou workflow, usar o default do tipo
            if not data.workflow_id and pt.default_workflow_id:
                data.workflow_id = pt.default_workflow_id

    # 1. Numeração
    project_number = _next_document_number(db, org_id=org_id, category="project", prefix=prefix)

    # 2. ID do projeto (precisa existir antes do BusinessDocument)
    project_id = uuid.uuid4()

    # 3. BusinessDocument
    doc = _create_business_document(
        db,
        org_id=org_id,
        document_type="PROJECT",
        native_id=project_id,
        document_number=project_number,
        title=data.title,
        status="draft",
        priority=data.priority,
        description=data.description,
        responsible_id=data.manager_id,
        created_by_id=current_user.id,
        category="project",
        tags=data.tags,
    )

    # 4. Etapa do workflow: respeita a escolha do formulário e usa a inicial
    # somente quando nenhuma etapa foi informada.
    initial_stage_id = None
    if data.workflow_id:
        workflow = repo.get_workflow(db, org_id=org_id, workflow_id=data.workflow_id)
        if not workflow:
            raise ValueError("Workflow não encontrado.")
        if data.current_stage_id:
            selected_stage = repo.get_workflow_stage(db, stage_id=data.current_stage_id)
            if not selected_stage or selected_stage.workflow_id != workflow.id:
                raise ValueError("A etapa selecionada não pertence ao workflow do projeto.")
            initial_stage_id = selected_stage.id
        else:
            initial_stage = repo.get_initial_stage(db, workflow_id=data.workflow_id)
            if initial_stage:
                initial_stage_id = initial_stage.id
    elif data.current_stage_id:
        raise ValueError("Selecione um workflow antes de definir a etapa do projeto.")

    # 5. Criar Project
    project_data = data.model_dump(exclude={"assignee_ids"} if hasattr(data, "assignee_ids") else set())
    project = repo.create_project(
        db,
        id=project_id,
        organization_id=org_id,
        document_id=doc.id,
        project_number=project_number,
        current_stage_id=initial_stage_id,
        status="draft",
        created_by_id=current_user.id,
        workflow_id=data.workflow_id,
        **{k: v for k, v in project_data.items() if k not in (
            "project_number", "status", "created_by_id", "name", "workflow_id", "current_stage_id"
        )},
    )

    # 6. Adicionar criador como membro (manager)
    repo.create_project_member(
        db,
        project_id=project.id,
        user_id=current_user.id,
        role="manager",
        added_by_id=current_user.id,
    )

    # Se manager_id foi informado e é diferente do criador, adicionar também
    if data.manager_id and data.manager_id != current_user.id:
        repo.create_project_member(
            db,
            project_id=project.id,
            user_id=data.manager_id,
            role="manager",
            added_by_id=current_user.id,
        )

    # 7. Registrar etapa inicial no histórico
    if initial_stage_id:
        repo.create_stage_history(
            db,
            project_id=project.id,
            from_stage_id=None,
            to_stage_id=initial_stage_id,
            changed_by_id=current_user.id,
            notes="Etapa selecionada ao criar o projeto" if data.current_stage_id else "Etapa inicial ao criar o projeto",
        )

    # 8. Evento na timeline
    _emit_event(
        db,
        org_id=org_id,
        document_id=doc.id,
        event_type="CREATED",
        new_status="draft",
        metadata={"title": data.title, "project_number": project_number},
        created_by_id=current_user.id,
        idempotency_key=f"project-created-{project.id}",
    )

    # 9. Vincular a documentos de origem via DocumentRelation
    if data.sales_order_id:
        _link_origin_document(db, org_id=org_id, project_doc_id=doc.id,
                              origin_table="sales_order", origin_id=data.sales_order_id,
                              created_by_id=current_user.id)
    if data.sales_quote_id:
        _link_origin_document(db, org_id=org_id, project_doc_id=doc.id,
                              origin_table="sales_quote", origin_id=data.sales_quote_id,
                              created_by_id=current_user.id)

    db.commit()
    db.refresh(project)

    logger.info(
        f"✅ [PROJECTS] Projeto criado: {project_number} - {data.title} "
        f"(org={org_id}, user={current_user.id})"
    )

    return _project_to_response(project)


def _link_origin_document(
    db: Session,
    *,
    org_id: uuid.UUID,
    project_doc_id: uuid.UUID,
    origin_table: str,
    origin_id: uuid.UUID,
    created_by_id: uuid.UUID | None,
) -> None:
    """Tenta vincular projeto ao documento de origem (SalesOrder, SalesQuote) via DocumentRelation."""
    origin_doc = db.execute(
        select(BusinessDocument).where(
            BusinessDocument.organization_id == org_id,
            BusinessDocument.native_id == origin_id,
        )
    ).scalar_one_or_none()

    if origin_doc:
        _create_document_relation(
            db,
            org_id=org_id,
            parent_document_id=origin_doc.id,
            child_document_id=project_doc_id,
            relation_type="project_origin",
            created_by_id=created_by_id,
            metadata={"origin_table": origin_table, "origin_id": str(origin_id)},
        )


def _project_to_response(project: Project) -> schemas.ProjectResponse:
    """Converte model ORM para schema de resposta com campos aninhados."""
    members = []
    for m in (project.members or []):
        members.append(schemas.ProjectMemberSummary(
            id=m.id,
            user_id=m.user_id,
            role=m.role,
            joined_at=m.joined_at,
            user_name=m.user.full_name if m.user else None,
            user_email=m.user.email if m.user else None,
        ))

    return schemas.ProjectResponse(
        id=project.id,
        organization_id=project.organization_id,
        document_id=project.document_id,
        project_number=project.project_number,
        title=project.title,
        code=project.project_number,
        name=project.title,
        description=project.description,
        project_type=schemas.ProjectTypeSummary.model_validate(project.project_type) if project.project_type else None,
        priority=project.priority,
        tags=project.tags or [],
        status=project.status,
        workflow_id=project.workflow_id,
        current_stage_id=project.current_stage_id,
        current_stage=schemas.ProjectStageSummary.model_validate(project.current_stage) if project.current_stage else None,
        progress_percent=project.progress_percent,
        planned_start_date=project.planned_start_date,
        planned_end_date=project.planned_end_date,
        actual_start_date=project.actual_start_date,
        actual_end_date=project.actual_end_date,
        estimated_budget=project.estimated_budget,
        actual_cost=project.actual_cost,
        estimated_hours=project.estimated_hours,
        actual_hours=project.actual_hours,
        manager_id=project.manager_id,
        team_id=project.team_id,
        customer_id=project.customer_id,
        contact_id=project.contact_id,
        sales_order_id=project.sales_order_id,
        sales_quote_id=project.sales_quote_id,
        opportunity_id=project.opportunity_id,
        cost_center_id=project.cost_center_id,
        address=project.address,
        city=project.city,
        state=project.state,
        zip_code=project.zip_code,
        custom_fields=project.custom_fields or {},
        notes=project.notes,
        is_billable=project.is_billable,
        members=members,
        created_by_id=project.created_by_id,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def list_projects(
    db: Session,
    *,
    org_id: uuid.UUID,
    status: str | None = None,
    project_type_id: uuid.UUID | None = None,
    manager_id: uuid.UUID | None = None,
    customer_id: uuid.UUID | None = None,
    stage_id: uuid.UUID | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> schemas.PaginatedResponse:
    items, total = repo.list_projects(
        db,
        org_id=org_id,
        status=status,
        project_type_id=project_type_id,
        manager_id=manager_id,
        customer_id=customer_id,
        stage_id=stage_id,
        search=search,
        page=page,
        page_size=page_size,
    )
    return schemas.PaginatedResponse(
        items=[_project_to_response(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if page_size > 0 else 0,
    )


def get_project(
    db: Session, *, org_id: uuid.UUID, project_id: uuid.UUID
) -> schemas.ProjectResponse:
    project = repo.get_project(db, org_id=org_id, project_id=project_id)
    if not project:
        raise ValueError("Projeto não encontrado.")
    return _project_to_response(project)


def update_project(
    db: Session,
    *,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    data: schemas.ProjectUpdate,
    current_user: User,
) -> schemas.ProjectResponse:
    project = repo.get_project(db, org_id=org_id, project_id=project_id)
    if not project:
        raise ValueError("Projeto não encontrado.")

    changes = data.model_dump(exclude_unset=True)
    stage_was_explicit = "current_stage_id" in changes
    requested_stage_id = changes.pop("current_stage_id", project.current_stage_id)
    workflow_changed = "workflow_id" in changes and changes["workflow_id"] != project.workflow_id

    if workflow_changed:
        next_workflow_id = changes["workflow_id"]
        if next_workflow_id:
            workflow = repo.get_workflow(db, org_id=org_id, workflow_id=next_workflow_id)
            if not workflow:
                raise ValueError("Workflow não encontrado.")
            if not stage_was_explicit:
                initial_stage = repo.get_initial_stage(db, workflow_id=next_workflow_id)
                requested_stage_id = initial_stage.id if initial_stage else None
        else:
            requested_stage_id = None

    selected_stage = None
    effective_workflow_id = changes.get("workflow_id", project.workflow_id)
    if requested_stage_id:
        selected_stage = repo.get_workflow_stage(db, stage_id=requested_stage_id)
        if not selected_stage or not effective_workflow_id or selected_stage.workflow_id != effective_workflow_id:
            raise ValueError("A etapa selecionada não pertence ao workflow do projeto.")

    old_stage = project.current_stage
    old_stage_id = project.current_stage_id
    if requested_stage_id != old_stage_id and old_stage and old_stage.allowed_transitions and not workflow_changed:
        allowed = [str(stage_id) for stage_id in old_stage.allowed_transitions]
        if requested_stage_id and str(requested_stage_id) not in allowed:
            raise ValueError(f"Transição não permitida de '{old_stage.name}' para '{selected_stage.name}'.")

    for key, val in changes.items():
        setattr(project, key, val)

    if requested_stage_id != old_stage_id:
        project.current_stage_id = requested_stage_id
        if requested_stage_id:
            repo.create_stage_history(
                db,
                project_id=project.id,
                from_stage_id=old_stage_id,
                to_stage_id=requested_stage_id,
                changed_by_id=current_user.id,
                notes="Etapa alterada pelo formulário do projeto",
            )
            if selected_stage and selected_stage.is_terminal:
                project.status = "completed"
                project.actual_end_date = utcnow()
                project.progress_percent = 100
            elif project.status == "draft":
                project.status = "in_progress"
                project.actual_start_date = project.actual_start_date or utcnow()

    # Atualizar BusinessDocument se título ou prioridade mudou
    if "title" in changes or "priority" in changes or requested_stage_id != old_stage_id:
        doc = project.document
        if doc:
            if "title" in changes:
                doc.title = changes["title"]
            if "priority" in changes:
                doc.priority = changes["priority"]
            if requested_stage_id != old_stage_id:
                doc.current_status = project.status

    _emit_event(
        db,
        org_id=org_id,
        document_id=project.document_id,
        event_type="UPDATED",
        metadata={"changes": [*changes.keys(), *(["current_stage_id"] if requested_stage_id != old_stage_id else [])]},
        created_by_id=current_user.id,
    )

    db.commit()
    db.refresh(project)
    return _project_to_response(project)


def change_project_status(
    db: Session,
    *,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    data: schemas.ProjectStatusChange,
    current_user: User,
) -> schemas.ProjectResponse:
    project = repo.get_project(db, org_id=org_id, project_id=project_id)
    if not project:
        raise ValueError("Projeto não encontrado.")

    old_status = project.status
    project.status = data.status

    # Atualizar datas automáticas
    now = utcnow()
    if data.status == "in_progress" and not project.actual_start_date:
        project.actual_start_date = now
    elif data.status in ("completed", "cancelled"):
        project.actual_end_date = now
        if data.status == "completed":
            project.progress_percent = 100

    # Sincronizar BusinessDocument
    if project.document:
        project.document.current_status = data.status
        if data.status in ("completed", "cancelled"):
            project.document.completed_at = now

    _emit_event(
        db,
        org_id=org_id,
        document_id=project.document_id,
        event_type="STATUS_CHANGED",
        previous_status=old_status,
        new_status=data.status,
        metadata={"notes": data.notes} if data.notes else {},
        created_by_id=current_user.id,
    )

    db.commit()
    db.refresh(project)
    logger.info(f"✅ [PROJECTS] Status alterado: {project.project_number} {old_status} → {data.status}")
    return _project_to_response(project)


def change_project_stage(
    db: Session,
    *,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    data: schemas.ProjectStageChange,
    current_user: User,
) -> schemas.ProjectResponse:
    """Muda a etapa do projeto no workflow com validação de transição permitida."""
    project = repo.get_project(db, org_id=org_id, project_id=project_id)
    if not project:
        raise ValueError("Projeto não encontrado.")

    new_stage = repo.get_workflow_stage(db, stage_id=data.stage_id)
    if (
        not new_stage
        or not project.workflow_id
        or new_stage.workflow_id != project.workflow_id
        or not repo.get_workflow(db, org_id=org_id, workflow_id=new_stage.workflow_id)
    ):
        raise ValueError("Etapa de destino não encontrada.")

    old_stage = project.current_stage
    old_stage_id = project.current_stage_id

    # Validar transição permitida (se a etapa atual tem restrições)
    if old_stage and old_stage.allowed_transitions:
        allowed = [str(t) for t in old_stage.allowed_transitions]
        if str(data.stage_id) not in allowed:
            raise ValueError(
                f"Transição não permitida de '{old_stage.name}' para '{new_stage.name}'."
            )

    project.current_stage_id = data.stage_id

    # Se a nova etapa é terminal, atualizar status automaticamente
    if new_stage.is_terminal:
        project.status = "completed"
        project.actual_end_date = utcnow()
        project.progress_percent = 100
    elif project.status == "draft":
        project.status = "in_progress"
        if not project.actual_start_date:
            project.actual_start_date = utcnow()

    # Registrar no histórico de etapas
    repo.create_stage_history(
        db,
        project_id=project.id,
        from_stage_id=old_stage_id,
        to_stage_id=data.stage_id,
        changed_by_id=current_user.id,
        notes=data.notes,
    )

    # Evento na timeline
    _emit_event(
        db,
        org_id=org_id,
        document_id=project.document_id,
        event_type="STAGE_CHANGED",
        previous_status=old_stage.name if old_stage else None,
        new_status=new_stage.name,
        metadata={
            "from_stage_id": str(old_stage_id) if old_stage_id else None,
            "to_stage_id": str(data.stage_id),
            "notes": data.notes,
        },
        created_by_id=current_user.id,
    )

    db.commit()
    db.refresh(project)
    logger.info(
        f"✅ [PROJECTS] Etapa alterada: {project.project_number} "
        f"'{old_stage.name if old_stage else 'N/A'}' → '{new_stage.name}'"
    )
    return _project_to_response(project)


# ==============================================================================
# PROJECT MEMBERS
# ==============================================================================

def add_project_member(
    db: Session,
    *,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    data: schemas.ProjectMemberCreate,
    current_user: User,
) -> schemas.ProjectMemberResponse:
    existing = repo.get_project_member(db, project_id=project_id, user_id=data.user_id)
    if existing:
        raise ValueError("Usuário já é membro deste projeto.")

    member = repo.create_project_member(
        db,
        project_id=project_id,
        user_id=data.user_id,
        role=data.role,
        added_by_id=current_user.id,
    )

    # Buscar o project para emitir evento
    project = repo.get_project(db, org_id=org_id, project_id=project_id)
    if project:
        _emit_event(
            db,
            org_id=org_id,
            document_id=project.document_id,
            event_type="MEMBER_ADDED",
            metadata={"user_id": str(data.user_id), "role": data.role},
            created_by_id=current_user.id,
        )

    db.commit()
    db.refresh(member)
    return schemas.ProjectMemberResponse.model_validate(member)


def remove_project_member(
    db: Session,
    *,
    project_id: uuid.UUID,
    member_id: uuid.UUID,
) -> None:
    member = db.get(ProjectMember, member_id)
    if not member or member.project_id != project_id:
        raise ValueError("Membro não encontrado neste projeto.")
    repo.delete_project_member(db, member)
    db.commit()


def list_project_members(
    db: Session, *, project_id: uuid.UUID
) -> list[schemas.ProjectMemberResponse]:
    members = repo.list_project_members(db, project_id=project_id)
    return [schemas.ProjectMemberResponse.model_validate(m) for m in members]


# ==============================================================================
# WORK ORDER
# ==============================================================================

def create_work_order(
    db: Session,
    *,
    org_id: uuid.UUID,
    data: schemas.WorkOrderCreate,
    current_user: User,
) -> schemas.WorkOrderResponse:
    # A ordem pode ser independente. Quando houver projeto, validar o vínculo
    # dentro da mesma organização antes de criar qualquer documento.
    project = None
    if data.project_id:
        project = repo.get_project(db, org_id=org_id, project_id=data.project_id)
        if not project:
            raise ValueError("Projeto não encontrado.")

    # Prefixo
    prefix = "OS"
    if data.order_type_id:
        ot = repo.get_work_order_type(db, org_id=org_id, type_id=data.order_type_id)
        if ot:
            prefix = ot.prefix
            if not data.workflow_id and ot.default_workflow_id:
                data.workflow_id = ot.default_workflow_id

    order_number = _next_document_number(db, org_id=org_id, category="work_order", prefix=prefix)
    order_id = uuid.uuid4()

    doc = _create_business_document(
        db,
        org_id=org_id,
        document_type="WORK_ORDER",
        native_id=order_id,
        document_number=order_number,
        title=data.title,
        status="draft",
        priority=data.priority,
        description=data.description,
        responsible_id=data.responsible_id,
        created_by_id=current_user.id,
        category="work_order",
    )

    initial_stage_id = None
    if data.workflow_id:
        initial_stage = repo.get_initial_stage(db, workflow_id=data.workflow_id)
        if initial_stage:
            initial_stage_id = initial_stage.id

    order_data = data.model_dump()
    order = repo.create_work_order(
        db,
        id=order_id,
        organization_id=org_id,
        document_id=doc.id,
        order_number=order_number,
        current_stage_id=initial_stage_id,
        status="draft",
        created_by_id=current_user.id,
        **{k: v for k, v in order_data.items() if k not in (
            "order_number", "status", "created_by_id"
        )},
    )

    # A rastreabilidade projeto -> OS só existe quando o vínculo foi informado.
    if project:
        _create_document_relation(
            db,
            org_id=org_id,
            parent_document_id=project.document_id,
            child_document_id=doc.id,
            relation_type="project_work_order",
            created_by_id=current_user.id,
        )

    _emit_event(
        db,
        org_id=org_id,
        document_id=doc.id,
        event_type="CREATED",
        new_status="draft",
        metadata={
            "title": data.title,
            "order_number": order_number,
            "project_id": str(data.project_id) if data.project_id else None,
        },
        created_by_id=current_user.id,
        idempotency_key=f"work-order-created-{order.id}",
    )

    db.commit()
    db.refresh(order)
    project_context = f" no projeto {project.project_number}" if project else " sem projeto vinculado"
    logger.info(f"✅ [PROJECTS] OS criada: {order_number}{project_context}")
    return schemas.WorkOrderResponse.model_validate(order)


def list_work_orders(
    db: Session,
    *,
    org_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    status: str | None = None,
    responsible_id: uuid.UUID | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> schemas.PaginatedResponse:
    items, total = repo.list_work_orders(
        db, org_id=org_id, project_id=project_id, status=status,
        responsible_id=responsible_id, search=search, page=page, page_size=page_size,
    )
    return schemas.PaginatedResponse(
        items=[schemas.WorkOrderListResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if page_size > 0 else 0,
    )


def get_work_order(
    db: Session, *, org_id: uuid.UUID, order_id: uuid.UUID
) -> schemas.WorkOrderResponse:
    order = repo.get_work_order(db, org_id=org_id, order_id=order_id)
    if not order:
        raise ValueError("Ordem de trabalho não encontrada.")
    return schemas.WorkOrderResponse.model_validate(order)


def update_work_order(
    db: Session,
    *,
    org_id: uuid.UUID,
    order_id: uuid.UUID,
    data: schemas.WorkOrderUpdate,
    current_user: User,
) -> schemas.WorkOrderResponse:
    order = repo.get_work_order(db, org_id=org_id, order_id=order_id)
    if not order:
        raise ValueError("Ordem de trabalho não encontrada.")
    changes = data.model_dump(exclude_unset=True)

    old_project_id = order.project_id
    linked_project = None
    if changes.get("project_id"):
        linked_project = repo.get_project(db, org_id=org_id, project_id=changes["project_id"])
        if not linked_project:
            raise ValueError("Projeto não encontrado.")

    for key, val in changes.items():
        setattr(order, key, val)

    if "project_id" in changes and changes["project_id"] != old_project_id:
        existing_relations = db.execute(
            select(DocumentRelation).where(
                DocumentRelation.organization_id == org_id,
                DocumentRelation.child_document_id == order.document_id,
                DocumentRelation.relation_type == "project_work_order",
            )
        ).scalars().all()
        for relation in existing_relations:
            db.delete(relation)
        if existing_relations:
            db.flush()

        if linked_project:
            _create_document_relation(
                db,
                org_id=org_id,
                parent_document_id=linked_project.document_id,
                child_document_id=order.document_id,
                relation_type="project_work_order",
                created_by_id=current_user.id,
            )
    _emit_event(
        db, org_id=org_id, document_id=order.document_id,
        event_type="UPDATED", metadata={"changes": list(changes.keys())},
        created_by_id=current_user.id,
    )
    db.commit()
    db.refresh(order)
    return schemas.WorkOrderResponse.model_validate(order)


def change_work_order_status(
    db: Session,
    *,
    org_id: uuid.UUID,
    order_id: uuid.UUID,
    data: schemas.WorkOrderStatusChange,
    current_user: User,
) -> schemas.WorkOrderResponse:
    order = repo.get_work_order(db, org_id=org_id, order_id=order_id)
    if not order:
        raise ValueError("Ordem de trabalho não encontrada.")
    old_status = order.status
    order.status = data.status
    now = utcnow()
    if data.status == "in_progress" and not order.actual_start:
        order.actual_start = now
    elif data.status in ("completed", "cancelled"):
        order.actual_end = now
        if data.status == "completed":
            order.progress_percent = 100
    if order.document:
        order.document.current_status = data.status
    _emit_event(
        db, org_id=org_id, document_id=order.document_id,
        event_type="STATUS_CHANGED", previous_status=old_status, new_status=data.status,
        metadata={"notes": data.notes} if data.notes else {},
        created_by_id=current_user.id,
    )
    db.commit()
    db.refresh(order)
    return schemas.WorkOrderResponse.model_validate(order)


# ==============================================================================
# TASK
# ==============================================================================

def create_task(
    db: Session,
    *,
    org_id: uuid.UUID,
    data: schemas.TaskCreate,
    current_user: User,
) -> schemas.TaskResponse:
    if not data.project_id and not data.work_order_id:
        raise ValueError("A tarefa deve estar vinculada a um projeto ou ordem de trabalho.")

    assignee_ids = set(data.assignee_ids or [])
    if assignee_ids:
        valid_user_ids = set(
            db.scalars(
                select(User.id).where(
                    User.organization_id == org_id,
                    User.id.in_(assignee_ids),
                )
            ).all()
        )
        if valid_user_ids != assignee_ids:
            raise ValueError("Um ou mais responsáveis não pertencem à organização.")

    linked_order = None
    if data.work_order_id:
        linked_order = repo.get_work_order(db, org_id=org_id, order_id=data.work_order_id)
        if not linked_order:
            raise ValueError("Ordem de trabalho não encontrada.")
        if data.project_id and linked_order.project_id and data.project_id != linked_order.project_id:
            raise ValueError("A ordem de trabalho pertence a outro projeto.")
        if not data.project_id and linked_order.project_id:
            data.project_id = linked_order.project_id

    linked_project = None
    if data.project_id:
        linked_project = repo.get_project(db, org_id=org_id, project_id=data.project_id)
        if not linked_project:
            raise ValueError("Projeto não encontrado.")

    task_number = _next_document_number(db, org_id=org_id, category="task", prefix="TK")
    task_id = uuid.uuid4()

    initial_status = data.status
    doc = _create_business_document(
        db,
        org_id=org_id,
        document_type="TASK",
        native_id=task_id,
        document_number=task_number,
        title=data.title,
        status=initial_status,
        priority=data.priority,
        description=data.description,
        created_by_id=current_user.id,
        category="task",
    )

    task_data = data.model_dump(exclude={"assignee_ids", "status"})
    task = repo.create_task(
        db,
        id=task_id,
        organization_id=org_id,
        document_id=doc.id,
        task_number=task_number,
        status=initial_status,
        created_by_id=current_user.id,
        **{k: v for k, v in task_data.items() if k not in (
            "task_number", "status", "created_by_id"
        )},
    )

    now = utcnow()
    if initial_status == "in_progress":
        task.started_at = now
    elif initial_status in ("done", "cancelled"):
        task.completed_at = now
        if initial_status == "done":
            task.progress_percent = 100

    if linked_project:
        _create_document_relation(
            db,
            org_id=org_id,
            parent_document_id=linked_project.document_id,
            child_document_id=doc.id,
            relation_type="project_task",
            created_by_id=current_user.id,
        )
    if linked_order:
        _create_document_relation(
            db,
            org_id=org_id,
            parent_document_id=linked_order.document_id,
            child_document_id=doc.id,
            relation_type="work_order_task",
            created_by_id=current_user.id,
        )

    # Atribuir responsáveis
    for uid in assignee_ids:
        repo.create_task_assignment(
            db, task_id=task.id, user_id=uid, assigned_by_id=current_user.id,
        )

    _emit_event(
        db,
        org_id=org_id,
        document_id=doc.id,
        event_type="CREATED",
        new_status=initial_status,
        metadata={
            "title": data.title,
            "task_number": task_number,
            "project_id": str(data.project_id) if data.project_id else None,
            "work_order_id": str(data.work_order_id) if data.work_order_id else None,
        },
        created_by_id=current_user.id,
        idempotency_key=f"task-created-{task.id}",
    )

    db.commit()
    db.refresh(task)
    logger.info(f"✅ [PROJECTS] Tarefa criada: {task_number} - {data.title}")
    return schemas.TaskResponse.model_validate(task)


def list_tasks(
    db: Session,
    *,
    org_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    work_order_id: uuid.UUID | None = None,
    status: str | None = None,
    assigned_to: uuid.UUID | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> schemas.PaginatedResponse:
    items, total = repo.list_tasks(
        db, org_id=org_id, project_id=project_id, work_order_id=work_order_id,
        status=status, assigned_to=assigned_to, search=search, page=page, page_size=page_size,
    )
    return schemas.PaginatedResponse(
        items=[schemas.TaskListResponse.model_validate(t) for t in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if page_size > 0 else 0,
    )


def get_task(
    db: Session, *, org_id: uuid.UUID, task_id: uuid.UUID
) -> schemas.TaskResponse:
    task = repo.get_task(db, org_id=org_id, task_id=task_id)
    if not task:
        raise ValueError("Tarefa não encontrada.")
    return schemas.TaskResponse.model_validate(task)


def update_task(
    db: Session,
    *,
    org_id: uuid.UUID,
    task_id: uuid.UUID,
    data: schemas.TaskUpdate,
    current_user: User,
) -> schemas.TaskResponse:
    task = repo.get_task(db, org_id=org_id, task_id=task_id)
    if not task:
        raise ValueError("Tarefa não encontrada.")
    changes = data.model_dump(exclude_unset=True)
    assignee_ids = changes.pop("assignee_ids", None)
    old_status = task.status

    associations_changed = "project_id" in changes or "work_order_id" in changes
    next_project_id = changes.get("project_id", task.project_id)
    next_work_order_id = changes.get("work_order_id", task.work_order_id)
    if not next_project_id and not next_work_order_id:
        raise ValueError("A tarefa deve estar vinculada a um projeto ou ordem de trabalho.")

    linked_order = None
    if next_work_order_id:
        linked_order = repo.get_work_order(db, org_id=org_id, order_id=next_work_order_id)
        if not linked_order:
            raise ValueError("Ordem de trabalho não encontrada.")
        if next_project_id and linked_order.project_id and next_project_id != linked_order.project_id:
            raise ValueError("A ordem de trabalho pertence a outro projeto.")
        if not next_project_id and linked_order.project_id:
            next_project_id = linked_order.project_id
            changes["project_id"] = next_project_id

    linked_project = None
    if next_project_id:
        linked_project = repo.get_project(db, org_id=org_id, project_id=next_project_id)
        if not linked_project:
            raise ValueError("Projeto não encontrado.")

    for key, val in changes.items():
        setattr(task, key, val)

    new_status = changes.get("status")
    if new_status and new_status != old_status:
        now = utcnow()
        if new_status == "in_progress" and not task.started_at:
            task.started_at = now
        elif new_status in ("done", "cancelled"):
            task.completed_at = now
            if new_status == "done":
                task.progress_percent = 100
        elif old_status in ("done", "cancelled"):
            task.completed_at = None
        if task.document:
            task.document.current_status = new_status
        _emit_event(
            db, org_id=org_id, document_id=task.document_id,
            event_type="STATUS_CHANGED", previous_status=old_status, new_status=new_status,
            metadata={"source": "task_form"}, created_by_id=current_user.id,
        )

    if assignee_ids is not None:
        requested_ids = set(assignee_ids)
        if requested_ids:
            valid_user_ids = set(
                db.scalars(
                    select(User.id).where(
                        User.organization_id == org_id,
                        User.id.in_(requested_ids),
                    )
                ).all()
            )
            if valid_user_ids != requested_ids:
                raise ValueError("Um ou mais responsáveis não pertencem à organização.")

        existing_by_user = {assignment.user_id: assignment for assignment in task.assignments}
        for user_id, assignment in existing_by_user.items():
            if user_id not in requested_ids:
                db.delete(assignment)
        for user_id in requested_ids - existing_by_user.keys():
            repo.create_task_assignment(
                db,
                task_id=task.id,
                user_id=user_id,
                assigned_by_id=current_user.id,
            )

    if associations_changed:
        existing_relations = db.execute(
            select(DocumentRelation).where(
                DocumentRelation.organization_id == org_id,
                DocumentRelation.child_document_id == task.document_id,
                DocumentRelation.relation_type.in_(("project_task", "work_order_task")),
            )
        ).scalars().all()
        for relation in existing_relations:
            db.delete(relation)
        if existing_relations:
            db.flush()

        if linked_project:
            _create_document_relation(
                db,
                org_id=org_id,
                parent_document_id=linked_project.document_id,
                child_document_id=task.document_id,
                relation_type="project_task",
                created_by_id=current_user.id,
            )
        if linked_order:
            _create_document_relation(
                db,
                org_id=org_id,
                parent_document_id=linked_order.document_id,
                child_document_id=task.document_id,
                relation_type="work_order_task",
                created_by_id=current_user.id,
            )
    _emit_event(
        db, org_id=org_id, document_id=task.document_id,
        event_type="UPDATED", metadata={"changes": list(changes.keys())},
        created_by_id=current_user.id,
    )
    db.commit()
    db.refresh(task)
    return schemas.TaskResponse.model_validate(task)


def change_task_status(
    db: Session,
    *,
    org_id: uuid.UUID,
    task_id: uuid.UUID,
    data: schemas.TaskStatusChange,
    current_user: User,
) -> schemas.TaskResponse:
    task = repo.get_task(db, org_id=org_id, task_id=task_id)
    if not task:
        raise ValueError("Tarefa não encontrada.")
    old_status = task.status
    task.status = data.status
    now = utcnow()
    if data.status == "in_progress" and not task.started_at:
        task.started_at = now
    elif data.status in ("done", "cancelled"):
        task.completed_at = now
        if data.status == "done":
            task.progress_percent = 100
    if task.document:
        task.document.current_status = data.status
    _emit_event(
        db, org_id=org_id, document_id=task.document_id,
        event_type="STATUS_CHANGED", previous_status=old_status, new_status=data.status,
        metadata={"notes": data.notes} if data.notes else {},
        created_by_id=current_user.id,
    )
    db.commit()
    db.refresh(task)
    return schemas.TaskResponse.model_validate(task)


def add_task_assignment(
    db: Session,
    *,
    org_id: uuid.UUID,
    task_id: uuid.UUID,
    data: schemas.TaskAssignmentCreate,
    current_user: User,
) -> schemas.TaskAssignmentResponse:
    task = repo.get_task(db, org_id=org_id, task_id=task_id)
    if not task:
        raise ValueError("Tarefa não encontrada.")
    assignment = repo.create_task_assignment(
        db, task_id=task_id, user_id=data.user_id, role=data.role,
        assigned_by_id=current_user.id,
    )
    db.commit()
    db.refresh(assignment)
    return schemas.TaskAssignmentResponse.model_validate(assignment)


def add_task_dependency(
    db: Session,
    *,
    org_id: uuid.UUID,
    task_id: uuid.UUID,
    data: schemas.TaskDependencyCreate,
    current_user: User,
) -> schemas.TaskDependencyResponse:
    dep = repo.create_task_dependency(
        db, dependent_task_id=task_id, dependency_task_id=data.dependency_task_id,
        dependency_type=data.dependency_type,
    )
    db.commit()
    db.refresh(dep)
    return schemas.TaskDependencyResponse.model_validate(dep)


# ==============================================================================
# ISSUE
# ==============================================================================

def create_issue(
    db: Session, *, org_id: uuid.UUID, data: schemas.IssueCreate, current_user: User
) -> schemas.IssueResponse:
    issue_number = _next_document_number(db, org_id=org_id, category="issue", prefix="ISS")
    issue = repo.create_issue(
        db,
        organization_id=org_id,
        issue_number=issue_number,
        reported_by_id=current_user.id,
        **data.model_dump(),
    )
    db.commit()
    db.refresh(issue)
    logger.info(f"✅ [PROJECTS] Ocorrência criada: {issue_number} - {data.title}")
    return schemas.IssueResponse.model_validate(issue)


def list_issues(
    db: Session, *, org_id: uuid.UUID, **kwargs
) -> schemas.PaginatedResponse:
    items, total = repo.list_issues(db, org_id=org_id, **kwargs)
    page = kwargs.get("page", 1)
    page_size = kwargs.get("page_size", 20)
    return schemas.PaginatedResponse(
        items=[schemas.IssueResponse.model_validate(i) for i in items],
        total=total, page=page, page_size=page_size,
        total_pages=math.ceil(total / page_size) if page_size > 0 else 0,
    )


def get_issue(
    db: Session, *, org_id: uuid.UUID, issue_id: uuid.UUID
) -> schemas.IssueResponse:
    issue = repo.get_issue(db, org_id=org_id, issue_id=issue_id)
    if not issue:
        raise ValueError("Ocorrência não encontrada.")
    return schemas.IssueResponse.model_validate(issue)


def update_issue(
    db: Session, *, org_id: uuid.UUID, issue_id: uuid.UUID,
    data: schemas.IssueUpdate, current_user: User
) -> schemas.IssueResponse:
    issue = repo.get_issue(db, org_id=org_id, issue_id=issue_id)
    if not issue:
        raise ValueError("Ocorrência não encontrada.")
    changes = data.model_dump(exclude_unset=True)
    for key, val in changes.items():
        setattr(issue, key, val)
    if "status" in changes and changes["status"] in ("resolved", "closed"):
        issue.resolved_at = utcnow()
        issue.resolved_by_id = current_user.id
    db.commit()
    db.refresh(issue)
    return schemas.IssueResponse.model_validate(issue)


# ==============================================================================
# CHECKLIST
# ==============================================================================

def create_checklist_template(
    db: Session, *, org_id: uuid.UUID, data: schemas.ChecklistTemplateCreate
) -> schemas.ChecklistTemplateResponse:
    tmpl = repo.create_checklist_template(
        db, org_id=org_id, name=data.name, description=data.description, category=data.category,
    )
    for item_data in data.items:
        repo.create_checklist_template_item(
            db, template_id=tmpl.id, **item_data.model_dump(),
        )
    db.commit()
    db.refresh(tmpl)
    return schemas.ChecklistTemplateResponse.model_validate(tmpl)


def list_checklist_templates(
    db: Session, *, org_id: uuid.UUID
) -> list[schemas.ChecklistTemplateResponse]:
    items = repo.list_checklist_templates(db, org_id=org_id)
    return [schemas.ChecklistTemplateResponse.model_validate(i) for i in items]


def create_checklist(
    db: Session, *, org_id: uuid.UUID, data: schemas.ChecklistCreate, current_user: User
) -> schemas.ChecklistResponse:
    checklist = repo.create_checklist(
        db,
        organization_id=org_id,
        name=data.name,
        task_id=data.task_id,
        work_order_id=data.work_order_id,
        template_id=data.template_id,
    )

    # Se baseado em template, copiar itens
    if data.template_id:
        tmpl = repo.get_checklist_template(db, org_id=org_id, template_id=data.template_id)
        if tmpl:
            for item in tmpl.items:
                repo.create_checklist_item(
                    db,
                    checklist_id=checklist.id,
                    text=item.text,
                    position=item.position,
                    is_required=item.is_required,
                )
            checklist.total_items = len(tmpl.items)

    db.commit()
    db.refresh(checklist)
    return schemas.ChecklistResponse.model_validate(checklist)


def list_checklists(
    db: Session,
    *,
    org_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    work_order_id: uuid.UUID | None = None,
    task_id: uuid.UUID | None = None,
) -> list[schemas.ChecklistResponse]:
    items = repo.list_checklists(
        db, org_id=org_id, project_id=project_id,
        work_order_id=work_order_id, task_id=task_id,
    )
    return [schemas.ChecklistResponse.model_validate(i) for i in items]


def toggle_checklist_item(
    db: Session,
    *,
    checklist_id: uuid.UUID,
    item_id: uuid.UUID,
    data: schemas.ChecklistItemToggle,
    current_user: User,
) -> schemas.ChecklistItemResponse:
    item = repo.get_checklist_item(db, item_id=item_id)
    if not item or item.checklist_id != checklist_id:
        raise ValueError("Item do checklist não encontrado.")

    item.is_checked = data.is_checked
    item.checked_at = utcnow() if data.is_checked else None
    item.checked_by_id = current_user.id if data.is_checked else None

    # Atualizar contador do checklist pai
    checklist = repo.get_checklist(db, checklist_id=checklist_id)
    if checklist:
        checked = sum(1 for i in checklist.items if i.is_checked)
        checklist.checked_items = checked

    db.commit()
    db.refresh(item)
    return schemas.ChecklistItemResponse.model_validate(item)


# ==============================================================================
# COMMENT
# ==============================================================================

def create_comment(
    db: Session, *, org_id: uuid.UUID, data: schemas.CommentCreate, current_user: User
) -> schemas.CommentResponse:
    comment = repo.create_comment(
        db,
        organization_id=org_id,
        author_id=current_user.id,
        **data.model_dump(),
    )
    db.commit()
    db.refresh(comment)
    result = schemas.CommentResponse.model_validate(comment)
    result.author_name = current_user.full_name
    return result


def list_comments(
    db: Session, *, org_id: uuid.UUID, **kwargs
) -> list[schemas.CommentResponse]:
    comments = repo.list_comments(db, org_id=org_id, **kwargs)
    results = []
    for c in comments:
        r = schemas.CommentResponse.model_validate(c)
        if c.author:
            r.author_name = c.author.full_name
        results.append(r)
    return results


# ==============================================================================
# DASHBOARD
# ==============================================================================

def get_dashboard(
    db: Session, *, org_id: uuid.UUID
) -> schemas.ProjectDashboardResponse:
    status_counts = repo.count_projects_by_status(db, org_id=org_id)

    total = sum(status_counts.values())
    active = sum(v for k, v in status_counts.items() if k in ("draft", "planning", "in_progress", "on_hold"))
    completed = status_counts.get("completed", 0)

    # Projetos atrasados (planned_end_date < now e não concluídos)
    overdue = db.execute(
        select(func.count()).select_from(Project).where(
            Project.organization_id == org_id,
            Project.planned_end_date < utcnow(),
            Project.status.in_(["draft", "planning", "in_progress", "on_hold"]),
        )
    ).scalar() or 0

    return schemas.ProjectDashboardResponse(
        total_projects=total,
        active_projects=active,
        completed_projects=completed,
        overdue_projects=overdue,
        total_orders=repo.count_work_orders(db, org_id=org_id),
        active_orders=repo.count_work_orders_active(db, org_id=org_id),
        total_tasks=repo.count_tasks(db, org_id=org_id),
        pending_tasks=repo.count_tasks_pending(db, org_id=org_id),
        open_issues=repo.count_issues_open(db, org_id=org_id),
        projects_by_status=status_counts,
    )


# ==============================================================================
# EXCLUSÕES (DELETE)
# ==============================================================================

def delete_project(db: Session, *, org_id: uuid.UUID, project_id: uuid.UUID, current_user: User) -> dict:
    project = repo.get_project(db, org_id=org_id, project_id=project_id)
    if not project:
        raise ValueError("Projeto não encontrado.")
    if project.document_id:
        _emit_event(
            db,
            org_id=org_id,
            document_id=project.document_id,
            event_type="DELETED",
            new_status="cancelled",
            metadata={"title": project.title, "project_number": project.project_number},
            created_by_id=current_user.id,
        )
    num = project.project_number
    repo.delete_project(db, project=project)
    db.commit()
    logger.info(f"🗑️ [PROJECTS] Projeto excluído: {num} (id={project_id})")
    return {"detail": f"Projeto {num} excluído com sucesso."}


def delete_work_order(db: Session, *, org_id: uuid.UUID, order_id: uuid.UUID, current_user: User) -> dict:
    order = repo.get_work_order(db, org_id=org_id, order_id=order_id)
    if not order:
        raise ValueError("Ordem de serviço não encontrada.")
    if order.document_id:
        _emit_event(
            db,
            org_id=org_id,
            document_id=order.document_id,
            event_type="DELETED",
            new_status="cancelled",
            metadata={"title": order.title, "order_number": order.order_number},
            created_by_id=current_user.id,
        )
    num = order.order_number
    repo.delete_work_order(db, order=order)
    db.commit()
    logger.info(f"🗑️ [PROJECTS] Ordem de serviço excluída: {num} (id={order_id})")
    return {"detail": f"Ordem {num} excluída com sucesso."}


def delete_task(db: Session, *, org_id: uuid.UUID, task_id: uuid.UUID, current_user: User) -> dict:
    task = repo.get_task(db, org_id=org_id, task_id=task_id)
    if not task:
        raise ValueError("Tarefa não encontrada.")
    num = task.task_number
    repo.delete_task(db, task=task)
    db.commit()
    logger.info(f"🗑️ [PROJECTS] Tarefa excluída: {num} (id={task_id})")
    return {"detail": f"Tarefa {num} excluída com sucesso."}


def delete_issue(db: Session, *, org_id: uuid.UUID, issue_id: uuid.UUID, current_user: User) -> dict:
    issue = repo.get_issue(db, org_id=org_id, issue_id=issue_id)
    if not issue:
        raise ValueError("Ocorrência não encontrada.")
    num = issue.issue_number
    repo.delete_issue(db, issue=issue)
    db.commit()
    logger.info(f"🗑️ [PROJECTS] Ocorrência excluída: {num} (id={issue_id})")
    return {"detail": f"Ocorrência {num} excluída com sucesso."}


def delete_project_type(db: Session, *, org_id: uuid.UUID, type_id: uuid.UUID, current_user: User) -> dict:
    ptype = repo.get_project_type(db, org_id=org_id, type_id=type_id)
    if not ptype:
        raise ValueError("Tipo de projeto não encontrado.")
    name = ptype.name
    repo.delete_project_type(db, ptype=ptype)
    db.commit()
    logger.info(f"🗑️ [PROJECTS] Tipo de projeto excluído: {name} (id={type_id})")
    return {"detail": f"Tipo de projeto '{name}' excluído com sucesso."}


def delete_work_order_type(db: Session, *, org_id: uuid.UUID, type_id: uuid.UUID, current_user: User) -> dict:
    wtype = repo.get_work_order_type(db, org_id=org_id, type_id=type_id)
    if not wtype:
        raise ValueError("Tipo de ordem não encontrado.")
    name = wtype.name
    repo.delete_work_order_type(db, wtype=wtype)
    db.commit()
    logger.info(f"🗑️ [PROJECTS] Tipo de ordem excluído: {name} (id={type_id})")
    return {"detail": f"Tipo de ordem '{name}' excluído com sucesso."}


def delete_workflow(db: Session, *, org_id: uuid.UUID, workflow_id: uuid.UUID, current_user: User) -> dict:
    workflow = repo.get_workflow(db, org_id=org_id, workflow_id=workflow_id)
    if not workflow:
        raise ValueError("Workflow não encontrado.")
    name = workflow.name
    repo.delete_workflow(db, workflow=workflow)
    db.commit()
    logger.info(f"🗑️ [PROJECTS] Workflow excluído: {name} (id={workflow_id})")
    return {"detail": f"Workflow '{name}' excluído com sucesso."}


def delete_workflow_stage(
    db: Session,
    *,
    org_id: uuid.UUID,
    stage_id: uuid.UUID,
    current_user: User,
) -> dict:
    stage = repo.get_workflow_stage(db, stage_id=stage_id)
    if not stage or not repo.get_workflow(db, org_id=org_id, workflow_id=stage.workflow_id):
        raise ValueError("Etapa de workflow não encontrada.")
    name = stage.name
    # Desvincula projetos e ordens que estejam nesta etapa para evitar violações de chave
    db.query(Project).filter(Project.current_stage_id == stage_id).update(
        {Project.current_stage_id: None}
    )
    db.query(WorkOrder).filter(WorkOrder.current_stage_id == stage_id).update(
        {WorkOrder.current_stage_id: None}
    )
    repo.delete_workflow_stage(db, stage=stage)
    db.commit()
    logger.info(f"🗑️ [PROJECTS] Etapa de workflow excluída: {name} (id={stage_id})")
    return {"detail": f"Etapa '{name}' excluída com sucesso."}
