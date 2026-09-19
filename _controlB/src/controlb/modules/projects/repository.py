"""
modules/projects/repository.py - Camada de Acesso a Dados (Repository Pattern)

Concentra todas as queries SQLAlchemy do módulo de Projetos & Operações.
Cada função recebe a sessão `db` e retorna models ORM ou escalares.

Convenções:
- get_*: busca única (retorna modelo ou None)
- list_*: busca múltipla com filtros opcionais (retorna lista)
- create_*: INSERT
- update_*: UPDATE (recebe modelo já carregado)
- count_*: COUNT para paginação e dashboards
"""

import uuid
from typing import Any

from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from controlb.modules.projects.models import (
    Checklist,
    ChecklistItem,
    ChecklistTemplate,
    ChecklistTemplateItem,
    Comment,
    Issue,
    Project,
    ProjectMember,
    ProjectStageHistory,
    ProjectType,
    Task,
    TaskAssignment,
    TaskDependency,
    WorkflowStage,
    WorkflowTemplate,
    WorkOrder,
    WorkOrderType,
)

# ==============================================================================
# PROJECT TYPE
# ==============================================================================

def get_project_type(db: Session, *, org_id: uuid.UUID, type_id: uuid.UUID) -> ProjectType | None:
    return db.execute(
        select(ProjectType).where(
            ProjectType.organization_id == org_id,
            ProjectType.id == type_id,
        )
    ).scalar_one_or_none()


def list_project_types(db: Session, *, org_id: uuid.UUID, active_only: bool = True) -> list[ProjectType]:
    stmt = select(ProjectType).where(ProjectType.organization_id == org_id)
    if active_only:
        stmt = stmt.where(ProjectType.is_active.is_(True))
    stmt = stmt.order_by(ProjectType.name)
    return list(db.execute(stmt).scalars().all())


def create_project_type(db: Session, *, org_id: uuid.UUID, **kwargs: Any) -> ProjectType:
    obj = ProjectType(organization_id=org_id, **kwargs)
    db.add(obj)
    db.flush()
    return obj


# ==============================================================================
# WORK ORDER TYPE
# ==============================================================================

def get_work_order_type(db: Session, *, org_id: uuid.UUID, type_id: uuid.UUID) -> WorkOrderType | None:
    return db.execute(
        select(WorkOrderType).where(
            WorkOrderType.organization_id == org_id,
            WorkOrderType.id == type_id,
        )
    ).scalar_one_or_none()


def list_work_order_types(db: Session, *, org_id: uuid.UUID, active_only: bool = True) -> list[WorkOrderType]:
    stmt = select(WorkOrderType).where(WorkOrderType.organization_id == org_id)
    if active_only:
        stmt = stmt.where(WorkOrderType.is_active.is_(True))
    stmt = stmt.order_by(WorkOrderType.name)
    return list(db.execute(stmt).scalars().all())


def create_work_order_type(db: Session, *, org_id: uuid.UUID, **kwargs: Any) -> WorkOrderType:
    obj = WorkOrderType(organization_id=org_id, **kwargs)
    db.add(obj)
    db.flush()
    return obj


# ==============================================================================
# WORKFLOW TEMPLATE & STAGE
# ==============================================================================

def get_workflow(db: Session, *, org_id: uuid.UUID, workflow_id: uuid.UUID) -> WorkflowTemplate | None:
    return db.execute(
        select(WorkflowTemplate)
        .options(selectinload(WorkflowTemplate.stages))
        .where(
            WorkflowTemplate.organization_id == org_id,
            WorkflowTemplate.id == workflow_id,
        )
    ).scalar_one_or_none()


def list_workflows(
    db: Session,
    *,
    org_id: uuid.UUID,
    target_entity: str | None = None,
    active_only: bool = True,
) -> list[WorkflowTemplate]:
    stmt = (
        select(WorkflowTemplate)
        .options(selectinload(WorkflowTemplate.stages))
        .where(WorkflowTemplate.organization_id == org_id)
    )
    if active_only:
        stmt = stmt.where(WorkflowTemplate.is_active.is_(True))
    if target_entity:
        stmt = stmt.where(WorkflowTemplate.target_entity == target_entity)
    stmt = stmt.order_by(WorkflowTemplate.name)
    return list(db.execute(stmt).scalars().all())


def create_workflow(db: Session, *, org_id: uuid.UUID, name: str, **kwargs: Any) -> WorkflowTemplate:
    obj = WorkflowTemplate(organization_id=org_id, name=name, **kwargs)
    db.add(obj)
    db.flush()
    return obj


def create_workflow_stage(db: Session, *, workflow_id: uuid.UUID, **kwargs: Any) -> WorkflowStage:
    obj = WorkflowStage(workflow_id=workflow_id, **kwargs)
    db.add(obj)
    db.flush()
    return obj


def get_workflow_stage(db: Session, *, stage_id: uuid.UUID) -> WorkflowStage | None:
    return db.execute(
        select(WorkflowStage).where(WorkflowStage.id == stage_id)
    ).scalar_one_or_none()


def get_initial_stage(db: Session, *, workflow_id: uuid.UUID) -> WorkflowStage | None:
    return db.execute(
        select(WorkflowStage).where(
            WorkflowStage.workflow_id == workflow_id,
            WorkflowStage.is_initial.is_(True),
        )
    ).scalar_one_or_none()


# ==============================================================================
# PROJECT
# ==============================================================================

def get_project(db: Session, *, org_id: uuid.UUID, project_id: uuid.UUID) -> Project | None:
    return db.execute(
        select(Project)
        .options(
            selectinload(Project.project_type),
            selectinload(Project.current_stage),
            selectinload(Project.members).selectinload(ProjectMember.user),
        )
        .where(
            Project.organization_id == org_id,
            Project.id == project_id,
        )
    ).scalar_one_or_none()


def get_project_by_number(db: Session, *, org_id: uuid.UUID, project_number: str) -> Project | None:
    return db.execute(
        select(Project).where(
            Project.organization_id == org_id,
            Project.project_number == project_number,
        )
    ).scalar_one_or_none()


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
) -> tuple[list[Project], int]:
    """Retorna (lista_paginada, total_count)."""
    stmt = (
        select(Project)
        .options(
            selectinload(Project.project_type),
            selectinload(Project.current_stage),
            selectinload(Project.members),
        )
        .where(Project.organization_id == org_id)
    )

    if status:
        stmt = stmt.where(Project.status == status)
    if project_type_id:
        stmt = stmt.where(Project.project_type_id == project_type_id)
    if manager_id:
        stmt = stmt.where(Project.manager_id == manager_id)
    if customer_id:
        stmt = stmt.where(Project.customer_id == customer_id)
    if stage_id:
        stmt = stmt.where(Project.current_stage_id == stage_id)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                Project.title.ilike(pattern),
                Project.project_number.ilike(pattern),
                Project.description.ilike(pattern),
            )
        )

    # Count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar() or 0

    # Paginate
    offset = (page - 1) * page_size
    stmt = stmt.order_by(desc(Project.created_at)).offset(offset).limit(page_size)
    items = list(db.execute(stmt).scalars().all())

    return items, total


def create_project(db: Session, **kwargs: Any) -> Project:
    obj = Project(**kwargs)
    db.add(obj)
    db.flush()
    return obj


def count_projects_by_status(db: Session, *, org_id: uuid.UUID) -> dict[str, int]:
    rows = db.execute(
        select(Project.status, func.count())
        .where(Project.organization_id == org_id)
        .group_by(Project.status)
    ).all()
    return {status: count for status, count in rows}


# ==============================================================================
# PROJECT MEMBER
# ==============================================================================

def get_project_member(
    db: Session, *, project_id: uuid.UUID, user_id: uuid.UUID
) -> ProjectMember | None:
    return db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    ).scalar_one_or_none()


def list_project_members(db: Session, *, project_id: uuid.UUID) -> list[ProjectMember]:
    return list(
        db.execute(
            select(ProjectMember)
            .options(selectinload(ProjectMember.user))
            .where(ProjectMember.project_id == project_id)
        ).scalars().all()
    )


def create_project_member(db: Session, **kwargs: Any) -> ProjectMember:
    obj = ProjectMember(**kwargs)
    db.add(obj)
    db.flush()
    return obj


def delete_project_member(db: Session, member: ProjectMember) -> None:
    db.delete(member)
    db.flush()


# ==============================================================================
# PROJECT STAGE HISTORY
# ==============================================================================

def create_stage_history(db: Session, **kwargs: Any) -> ProjectStageHistory:
    obj = ProjectStageHistory(**kwargs)
    db.add(obj)
    db.flush()
    return obj


def list_stage_history(
    db: Session, *, project_id: uuid.UUID, limit: int = 50
) -> list[ProjectStageHistory]:
    return list(
        db.execute(
            select(ProjectStageHistory)
            .options(
                selectinload(ProjectStageHistory.from_stage),
                selectinload(ProjectStageHistory.to_stage),
            )
            .where(ProjectStageHistory.project_id == project_id)
            .order_by(desc(ProjectStageHistory.created_at))
            .limit(limit)
        ).scalars().all()
    )


# ==============================================================================
# WORK ORDER
# ==============================================================================

def get_work_order(db: Session, *, org_id: uuid.UUID, order_id: uuid.UUID) -> WorkOrder | None:
    return db.execute(
        select(WorkOrder)
        .options(
            selectinload(WorkOrder.order_type),
            selectinload(WorkOrder.current_stage),
        )
        .where(
            WorkOrder.organization_id == org_id,
            WorkOrder.id == order_id,
        )
    ).scalar_one_or_none()


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
) -> tuple[list[WorkOrder], int]:
    stmt = (
        select(WorkOrder)
        .options(
            selectinload(WorkOrder.order_type),
            selectinload(WorkOrder.current_stage),
        )
        .where(WorkOrder.organization_id == org_id)
    )

    if project_id:
        stmt = stmt.where(WorkOrder.project_id == project_id)
    if status:
        stmt = stmt.where(WorkOrder.status == status)
    if responsible_id:
        stmt = stmt.where(WorkOrder.responsible_id == responsible_id)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                WorkOrder.title.ilike(pattern),
                WorkOrder.order_number.ilike(pattern),
            )
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar() or 0

    offset = (page - 1) * page_size
    stmt = stmt.order_by(desc(WorkOrder.created_at)).offset(offset).limit(page_size)
    items = list(db.execute(stmt).scalars().all())

    return items, total


def create_work_order(db: Session, **kwargs: Any) -> WorkOrder:
    obj = WorkOrder(**kwargs)
    db.add(obj)
    db.flush()
    return obj


def count_work_orders(db: Session, *, org_id: uuid.UUID, project_id: uuid.UUID | None = None) -> int:
    stmt = select(func.count()).select_from(WorkOrder).where(WorkOrder.organization_id == org_id)
    if project_id:
        stmt = stmt.where(WorkOrder.project_id == project_id)
    return db.execute(stmt).scalar() or 0


def count_work_orders_active(db: Session, *, org_id: uuid.UUID) -> int:
    return db.execute(
        select(func.count()).select_from(WorkOrder).where(
            WorkOrder.organization_id == org_id,
            WorkOrder.status.in_(["draft", "scheduled", "in_progress", "on_hold"]),
        )
    ).scalar() or 0


# ==============================================================================
# TASK
# ==============================================================================

def get_task(db: Session, *, org_id: uuid.UUID, task_id: uuid.UUID) -> Task | None:
    return db.execute(
        select(Task)
        .options(
            selectinload(Task.assignments).selectinload(TaskAssignment.user),
            selectinload(Task.dependencies),
        )
        .where(
            Task.organization_id == org_id,
            Task.id == task_id,
        )
    ).scalar_one_or_none()


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
) -> tuple[list[Task], int]:
    stmt = (
        select(Task)
        .options(
            selectinload(Task.assignments).selectinload(TaskAssignment.user),
        )
        .where(Task.organization_id == org_id)
    )

    if project_id:
        project_work_orders = select(WorkOrder.id).where(
            WorkOrder.organization_id == org_id,
            WorkOrder.project_id == project_id,
        )
        stmt = stmt.where(
            or_(
                Task.project_id == project_id,
                Task.work_order_id.in_(project_work_orders),
            )
        )
    if work_order_id:
        stmt = stmt.where(Task.work_order_id == work_order_id)
    if status:
        stmt = stmt.where(Task.status == status)
    if assigned_to:
        stmt = stmt.where(
            Task.id.in_(
                select(TaskAssignment.task_id).where(TaskAssignment.user_id == assigned_to)
            )
        )
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                Task.title.ilike(pattern),
                Task.task_number.ilike(pattern),
            )
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar() or 0

    offset = (page - 1) * page_size
    stmt = stmt.order_by(Task.position, desc(Task.created_at)).offset(offset).limit(page_size)
    items = list(db.execute(stmt).scalars().all())

    return items, total


def create_task(db: Session, **kwargs: Any) -> Task:
    obj = Task(**kwargs)
    db.add(obj)
    db.flush()
    return obj


def create_task_assignment(db: Session, **kwargs: Any) -> TaskAssignment:
    obj = TaskAssignment(**kwargs)
    db.add(obj)
    db.flush()
    return obj


def create_task_dependency(db: Session, **kwargs: Any) -> TaskDependency:
    obj = TaskDependency(**kwargs)
    db.add(obj)
    db.flush()
    return obj


def count_tasks(
    db: Session,
    *,
    org_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    status: str | None = None,
) -> int:
    stmt = select(func.count()).select_from(Task).where(Task.organization_id == org_id)
    if project_id:
        project_work_orders = select(WorkOrder.id).where(
            WorkOrder.organization_id == org_id,
            WorkOrder.project_id == project_id,
        )
        stmt = stmt.where(
            or_(
                Task.project_id == project_id,
                Task.work_order_id.in_(project_work_orders),
            )
        )
    if status:
        stmt = stmt.where(Task.status == status)
    return db.execute(stmt).scalar() or 0


def count_tasks_pending(db: Session, *, org_id: uuid.UUID) -> int:
    return db.execute(
        select(func.count()).select_from(Task).where(
            Task.organization_id == org_id,
            Task.status.in_(["backlog", "todo", "in_progress", "in_review", "blocked"]),
        )
    ).scalar() or 0


# ==============================================================================
# ISSUE
# ==============================================================================

def get_issue(db: Session, *, org_id: uuid.UUID, issue_id: uuid.UUID) -> Issue | None:
    return db.execute(
        select(Issue).where(
            Issue.organization_id == org_id,
            Issue.id == issue_id,
        )
    ).scalar_one_or_none()


def list_issues(
    db: Session,
    *,
    org_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    work_order_id: uuid.UUID | None = None,
    status: str | None = None,
    severity: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Issue], int]:
    stmt = select(Issue).where(Issue.organization_id == org_id)

    if project_id:
        stmt = stmt.where(Issue.project_id == project_id)
    if work_order_id:
        stmt = stmt.where(Issue.work_order_id == work_order_id)
    if status:
        stmt = stmt.where(Issue.status == status)
    if severity:
        stmt = stmt.where(Issue.severity == severity)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                Issue.title.ilike(pattern),
                Issue.issue_number.ilike(pattern),
            )
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar() or 0

    offset = (page - 1) * page_size
    stmt = stmt.order_by(desc(Issue.created_at)).offset(offset).limit(page_size)
    items = list(db.execute(stmt).scalars().all())

    return items, total


def create_issue(db: Session, **kwargs: Any) -> Issue:
    obj = Issue(**kwargs)
    db.add(obj)
    db.flush()
    return obj


def count_issues_open(db: Session, *, org_id: uuid.UUID) -> int:
    return db.execute(
        select(func.count()).select_from(Issue).where(
            Issue.organization_id == org_id,
            Issue.status.in_(["open", "investigating"]),
        )
    ).scalar() or 0


# ==============================================================================
# CHECKLIST
# ==============================================================================

def get_checklist_template(
    db: Session, *, org_id: uuid.UUID, template_id: uuid.UUID
) -> ChecklistTemplate | None:
    return db.execute(
        select(ChecklistTemplate)
        .options(selectinload(ChecklistTemplate.items))
        .where(
            ChecklistTemplate.organization_id == org_id,
            ChecklistTemplate.id == template_id,
        )
    ).scalar_one_or_none()


def list_checklist_templates(
    db: Session, *, org_id: uuid.UUID, active_only: bool = True
) -> list[ChecklistTemplate]:
    stmt = (
        select(ChecklistTemplate)
        .options(selectinload(ChecklistTemplate.items))
        .where(ChecklistTemplate.organization_id == org_id)
    )
    if active_only:
        stmt = stmt.where(ChecklistTemplate.is_active.is_(True))
    stmt = stmt.order_by(ChecklistTemplate.name)
    return list(db.execute(stmt).scalars().all())


def create_checklist_template(db: Session, *, org_id: uuid.UUID, **kwargs: Any) -> ChecklistTemplate:
    obj = ChecklistTemplate(organization_id=org_id, **kwargs)
    db.add(obj)
    db.flush()
    return obj


def create_checklist_template_item(db: Session, **kwargs: Any) -> ChecklistTemplateItem:
    obj = ChecklistTemplateItem(**kwargs)
    db.add(obj)
    db.flush()
    return obj


def get_checklist(db: Session, *, checklist_id: uuid.UUID) -> Checklist | None:
    return db.execute(
        select(Checklist)
        .options(selectinload(Checklist.items))
        .where(Checklist.id == checklist_id)
    ).scalar_one_or_none()


def list_checklists_for_task(db: Session, *, task_id: uuid.UUID) -> list[Checklist]:
    return list(
        db.execute(
            select(Checklist)
            .options(selectinload(Checklist.items))
            .where(Checklist.task_id == task_id)
        ).scalars().all()
    )


def list_checklists(
    db: Session,
    *,
    org_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    work_order_id: uuid.UUID | None = None,
    task_id: uuid.UUID | None = None,
) -> list[Checklist]:
    stmt = (
        select(Checklist)
        .options(selectinload(Checklist.items))
        .where(Checklist.organization_id == org_id)
    )
    if task_id:
        stmt = stmt.where(Checklist.task_id == task_id)
    if work_order_id:
        stmt = stmt.where(Checklist.work_order_id == work_order_id)
    return list(db.execute(stmt).scalars().all())


def create_checklist(db: Session, **kwargs: Any) -> Checklist:
    obj = Checklist(**kwargs)
    db.add(obj)
    db.flush()
    return obj


def create_checklist_item(db: Session, **kwargs: Any) -> ChecklistItem:
    obj = ChecklistItem(**kwargs)
    db.add(obj)
    db.flush()
    return obj


def get_checklist_item(db: Session, *, item_id: uuid.UUID) -> ChecklistItem | None:
    return db.execute(
        select(ChecklistItem).where(ChecklistItem.id == item_id)
    ).scalar_one_or_none()


# ==============================================================================
# COMMENT
# ==============================================================================

def list_comments(
    db: Session,
    *,
    org_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    work_order_id: uuid.UUID | None = None,
    task_id: uuid.UUID | None = None,
    issue_id: uuid.UUID | None = None,
) -> list[Comment]:
    stmt = (
        select(Comment)
        .options(selectinload(Comment.author))
        .where(Comment.organization_id == org_id)
    )
    if project_id:
        stmt = stmt.where(Comment.project_id == project_id)
    if work_order_id:
        stmt = stmt.where(Comment.work_order_id == work_order_id)
    if task_id:
        stmt = stmt.where(Comment.task_id == task_id)
    if issue_id:
        stmt = stmt.where(Comment.issue_id == issue_id)

    stmt = stmt.order_by(Comment.created_at)
    return list(db.execute(stmt).scalars().all())


def create_comment(db: Session, **kwargs: Any) -> Comment:
    obj = Comment(**kwargs)
    db.add(obj)
    db.flush()
    return obj


# ==============================================================================
# EXCLUSÕES (DELETE)
# ==============================================================================

def delete_project(db: Session, *, project: Project) -> None:
    db.delete(project)
    db.flush()


def delete_work_order(db: Session, *, order: WorkOrder) -> None:
    db.delete(order)
    db.flush()


def delete_task(db: Session, *, task: Task) -> None:
    db.delete(task)
    db.flush()


def delete_issue(db: Session, *, issue: Issue) -> None:
    db.delete(issue)
    db.flush()


def delete_project_type(db: Session, *, ptype: ProjectType) -> None:
    db.delete(ptype)
    db.flush()


def delete_work_order_type(db: Session, *, wtype: WorkOrderType) -> None:
    db.delete(wtype)
    db.flush()


def delete_workflow(db: Session, *, workflow: WorkflowTemplate) -> None:
    db.delete(workflow)
    db.flush()


def delete_workflow_stage(db: Session, *, stage: WorkflowStage) -> None:
    db.delete(stage)
    db.flush()
