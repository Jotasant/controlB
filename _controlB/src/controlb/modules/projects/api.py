"""
modules/projects/api.py - Roteador FastAPI do Módulo de Projetos & Operações

Expõe os endpoints REST para gerenciamento de projetos, ordens de trabalho,
tarefas, ocorrências, checklists, comentários e configurações (tipos e workflows).

Cada endpoint é protegido por permissões RBAC via require_permission/require_any_permission.
"""

import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from controlb.db import get_db
from controlb.modules.identity.models import User
from controlb.modules.identity.security import (
    require_any_permission,
    require_permission,
)
from controlb.modules.projects import schemas, service

router = APIRouter(prefix="/projects", tags=["Projetos & Operações"])


def _org_id(user: User) -> uuid.UUID:
    """Extrai o organization_id do usuário logado para isolamento multi-org."""
    return user.organization_id


def _handle_value_error(e: ValueError) -> None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ==============================================================================
# PROJECT TYPES (Configuração)
# ==============================================================================

@router.get("/types", response_model=list[schemas.ProjectTypeResponse])
def list_project_types(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("projects:view", "workflows:manage")),
    active_only: bool = Query(True),
):
    """Lista os tipos de projeto configurados para a organização."""
    return service.list_project_types(db, org_id=_org_id(current_user), active_only=active_only)


@router.post("/types", response_model=schemas.ProjectTypeResponse, status_code=status.HTTP_201_CREATED)
def create_project_type(
    data: schemas.ProjectTypeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("workflows:manage", "projects:create")),
):
    """Cria um novo tipo de projeto."""
    return service.create_project_type(db, org_id=_org_id(current_user), data=data)


@router.get("/types/{type_id:uuid}", response_model=schemas.ProjectTypeResponse)
def get_project_type(
    type_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("projects:view", "workflows:manage")),
):
    """Retorna um tipo de projeto, inclusive quando estiver inativo."""
    try:
        return service.get_project_type(db, org_id=_org_id(current_user), type_id=type_id)
    except ValueError as e:
        _handle_value_error(e)


@router.put("/types/{type_id:uuid}", response_model=schemas.ProjectTypeResponse)
def update_project_type(
    type_id: uuid.UUID,
    data: schemas.ProjectTypeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("workflows:manage", "projects:create")),
):
    """Atualiza um tipo de projeto existente."""
    try:
        return service.update_project_type(db, org_id=_org_id(current_user), type_id=type_id, data=data)
    except ValueError as e:
        _handle_value_error(e)


@router.delete("/types/{type_id:uuid}", status_code=status.HTTP_200_OK)
def delete_project_type(
    type_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("workflows:manage", "projects:create")),
):
    """Exclui um tipo de projeto."""
    try:
        return service.delete_project_type(db, org_id=_org_id(current_user), type_id=type_id, current_user=current_user)
    except ValueError as e:
        _handle_value_error(e)


# ==============================================================================
# WORK ORDER TYPES (Configuração)
# ==============================================================================

@router.get("/order-types", response_model=list[schemas.WorkOrderTypeResponse])
def list_work_order_types(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("projects:view", "workflows:manage")),
    active_only: bool = Query(True),
):
    """Lista os tipos de ordem de trabalho configurados."""
    return service.list_work_order_types(db, org_id=_org_id(current_user), active_only=active_only)


@router.post("/order-types", response_model=schemas.WorkOrderTypeResponse, status_code=status.HTTP_201_CREATED)
def create_work_order_type(
    data: schemas.WorkOrderTypeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("workflows:manage", "work_orders:create", "projects:create")),
):
    """Cria um novo tipo de ordem de trabalho."""
    return service.create_work_order_type(db, org_id=_org_id(current_user), data=data)


@router.get("/order-types/{type_id:uuid}", response_model=schemas.WorkOrderTypeResponse)
def get_work_order_type(
    type_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("projects:view", "workflows:manage")),
):
    """Retorna um tipo de ordem, inclusive quando estiver inativo."""
    try:
        return service.get_work_order_type(db, org_id=_org_id(current_user), type_id=type_id)
    except ValueError as e:
        _handle_value_error(e)


@router.put("/order-types/{type_id:uuid}", response_model=schemas.WorkOrderTypeResponse)
def update_work_order_type(
    type_id: uuid.UUID,
    data: schemas.WorkOrderTypeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("workflows:manage", "work_orders:create", "projects:create")),
):
    """Atualiza um tipo de ordem de trabalho."""
    try:
        return service.update_work_order_type(db, org_id=_org_id(current_user), type_id=type_id, data=data)
    except ValueError as e:
        _handle_value_error(e)


@router.delete("/order-types/{type_id:uuid}", status_code=status.HTTP_200_OK)
def delete_work_order_type(
    type_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("workflows:manage", "projects:create")),
):
    """Exclui um tipo de ordem de trabalho."""
    try:
        return service.delete_work_order_type(db, org_id=_org_id(current_user), type_id=type_id, current_user=current_user)
    except ValueError as e:
        _handle_value_error(e)


# ==============================================================================
# WORKFLOWS (Configuração)
# ==============================================================================

@router.get("/workflows", response_model=list[schemas.WorkflowTemplateResponse])
def list_workflows(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("projects:view", "workflows:manage")),
    target_entity: str | None = Query(None),
    active_only: bool = Query(True),
):
    """Lista os templates de workflow disponíveis."""
    return service.list_workflows(
        db, org_id=_org_id(current_user), target_entity=target_entity, active_only=active_only,
    )


@router.post("/workflows", response_model=schemas.WorkflowTemplateResponse, status_code=status.HTTP_201_CREATED)
def create_workflow(
    data: schemas.WorkflowTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("workflows:manage", "projects:create")),
):
    """Cria um novo template de workflow com etapas."""
    return service.create_workflow(db, org_id=_org_id(current_user), data=data)


@router.get("/workflows/{workflow_id:uuid}", response_model=schemas.WorkflowTemplateResponse)
def get_workflow(
    workflow_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("projects:view", "workflows:manage")),
):
    """Retorna um workflow com todas as suas etapas."""
    try:
        return service.get_workflow(db, org_id=_org_id(current_user), workflow_id=workflow_id)
    except ValueError as e:
        _handle_value_error(e)


@router.put("/workflows/{workflow_id:uuid}", response_model=schemas.WorkflowTemplateResponse)
def update_workflow(
    workflow_id: uuid.UUID,
    data: schemas.WorkflowTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workflows:manage")),
):
    """Atualiza metadados de um workflow."""
    try:
        return service.update_workflow(db, org_id=_org_id(current_user), workflow_id=workflow_id, data=data)
    except ValueError as e:
        _handle_value_error(e)


@router.post("/workflows/{workflow_id:uuid}/stages", response_model=schemas.WorkflowStageResponse, status_code=status.HTTP_201_CREATED)
def add_workflow_stage(
    workflow_id: uuid.UUID,
    data: schemas.WorkflowStageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("workflows:manage", "projects:create", "projects:update")),
):
    """Adiciona uma nova etapa a um workflow existente."""
    try:
        return service.add_workflow_stage(
            db, org_id=_org_id(current_user), workflow_id=workflow_id, data=data
        )
    except ValueError as e:
        _handle_value_error(e)


@router.put("/workflows/stages/{stage_id:uuid}", response_model=schemas.WorkflowStageResponse)
def update_workflow_stage(
    stage_id: uuid.UUID,
    data: schemas.WorkflowStageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workflows:manage")),
):
    """Atualiza uma etapa de workflow."""
    try:
        return service.update_workflow_stage(
            db, org_id=_org_id(current_user), stage_id=stage_id, data=data
        )
    except ValueError as e:
        _handle_value_error(e)


@router.delete("/workflows/{workflow_id:uuid}", status_code=status.HTTP_200_OK)
def delete_workflow(
    workflow_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workflows:manage")),
):
    """Exclui um template de workflow."""
    try:
        return service.delete_workflow(db, org_id=_org_id(current_user), workflow_id=workflow_id, current_user=current_user)
    except ValueError as e:
        _handle_value_error(e)


@router.delete("/workflows/stages/{stage_id:uuid}", status_code=status.HTTP_200_OK)
def delete_workflow_stage(
    stage_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("workflows:manage", "projects:delete", "projects:update", "projects:manage")),
):
    """Exclui uma etapa de workflow."""
    try:
        return service.delete_workflow_stage(
            db, org_id=_org_id(current_user), stage_id=stage_id, current_user=current_user
        )
    except ValueError as e:
        _handle_value_error(e)


# ==============================================================================
# PROJECTS (CRUD Principal)
# ==============================================================================

@router.get("/dashboard", response_model=schemas.ProjectDashboardResponse)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("projects:view")),
):
    """Retorna indicadores consolidados do módulo operacional."""
    return service.get_dashboard(db, org_id=_org_id(current_user))


@router.get("/", response_model=schemas.PaginatedResponse)
def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("projects:view")),
    status_filter: str | None = Query(None, alias="status"),
    project_type_id: uuid.UUID | None = Query(None),
    manager_id: uuid.UUID | None = Query(None),
    customer_id: uuid.UUID | None = Query(None),
    stage_id: uuid.UUID | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Lista projetos com filtros, paginação e busca textual."""
    return service.list_projects(
        db, org_id=_org_id(current_user),
        status=status_filter, project_type_id=project_type_id,
        manager_id=manager_id, customer_id=customer_id, stage_id=stage_id,
        search=search, page=page, page_size=page_size,
    )


@router.post("/", response_model=schemas.ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    data: schemas.ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("projects:create")),
):
    """Cria um novo projeto operacional."""
    return service.create_project(db, org_id=_org_id(current_user), data=data, current_user=current_user)


@router.get("/{project_id:uuid}", response_model=schemas.ProjectResponse)
def get_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("projects:view")),
):
    """Retorna os detalhes completos de um projeto."""
    try:
        return service.get_project(db, org_id=_org_id(current_user), project_id=project_id)
    except ValueError as e:
        _handle_value_error(e)


@router.put("/{project_id:uuid}", response_model=schemas.ProjectResponse)
def update_project(
    project_id: uuid.UUID,
    data: schemas.ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("projects:update")),
):
    """Atualiza dados de um projeto."""
    try:
        return service.update_project(
            db, org_id=_org_id(current_user), project_id=project_id,
            data=data, current_user=current_user,
        )
    except ValueError as e:
        _handle_value_error(e)


@router.patch("/{project_id:uuid}/status", response_model=schemas.ProjectResponse)
def change_project_status(
    project_id: uuid.UUID,
    data: schemas.ProjectStatusChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("projects:update")),
):
    """Altera o status de um projeto (draft → in_progress → completed etc.)."""
    try:
        return service.change_project_status(
            db, org_id=_org_id(current_user), project_id=project_id,
            data=data, current_user=current_user,
        )
    except ValueError as e:
        _handle_value_error(e)


@router.post("/{project_id:uuid}/stage", response_model=schemas.ProjectResponse)
@router.patch("/{project_id:uuid}/stage", response_model=schemas.ProjectResponse)
def change_project_stage(
    project_id: uuid.UUID,
    data: schemas.ProjectStageChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("projects:update")),
):
    """Avança ou altera a etapa do projeto no workflow."""
    try:
        return service.change_project_stage(
            db, org_id=_org_id(current_user), project_id=project_id,
            data=data, current_user=current_user,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{project_id:uuid}", status_code=status.HTTP_200_OK)
def delete_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("projects:delete", "projects:update")),
):
    """Exclui um projeto e cancela/atualiza o documento correspondente."""
    try:
        return service.delete_project(db, org_id=_org_id(current_user), project_id=project_id, current_user=current_user)
    except ValueError as e:
        _handle_value_error(e)


# ==============================================================================
# PROJECT MEMBERS
# ==============================================================================

@router.get("/{project_id:uuid}/members", response_model=list[schemas.ProjectMemberResponse])
def list_project_members(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("projects:view")),
):
    """Lista os membros de um projeto."""
    return service.list_project_members(db, project_id=project_id)


@router.post("/{project_id:uuid}/members", response_model=schemas.ProjectMemberResponse, status_code=status.HTTP_201_CREATED)
def add_project_member(
    project_id: uuid.UUID,
    data: schemas.ProjectMemberCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("projects:manage_members")),
):
    """Adiciona um membro ao projeto."""
    try:
        return service.add_project_member(
            db, org_id=_org_id(current_user), project_id=project_id,
            data=data, current_user=current_user,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.delete("/{project_id:uuid}/members/{member_id:uuid}", status_code=status.HTTP_204_NO_CONTENT)
def remove_project_member(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("projects:manage_members")),
):
    """Remove um membro do projeto."""
    try:
        service.remove_project_member(db, project_id=project_id, member_id=member_id)
    except ValueError as e:
        _handle_value_error(e)


# ==============================================================================
# WORK ORDERS
# ==============================================================================

@router.get("/orders", response_model=schemas.PaginatedResponse)
@router.get("/orders/list", response_model=schemas.PaginatedResponse)
def list_all_work_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("work_orders:view")),
    project_id: uuid.UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    responsible_id: uuid.UUID | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Lista ordens de trabalho com filtros."""
    return service.list_work_orders(
        db, org_id=_org_id(current_user), project_id=project_id,
        status=status_filter, responsible_id=responsible_id,
        search=search, page=page, page_size=page_size,
    )


@router.get("/{project_id:uuid}/orders", response_model=schemas.PaginatedResponse)
def list_project_work_orders(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("work_orders:view")),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Lista ordens de trabalho de um projeto específico."""
    return service.list_work_orders(
        db, org_id=_org_id(current_user), project_id=project_id,
        page=page, page_size=page_size,
    )


@router.post("/orders", response_model=schemas.WorkOrderResponse, status_code=status.HTTP_201_CREATED)
def create_work_order(
    data: schemas.WorkOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("work_orders:create")),
):
    """Cria uma nova ordem de trabalho vinculada a um projeto."""
    try:
        return service.create_work_order(
            db, org_id=_org_id(current_user), data=data, current_user=current_user,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/orders/{order_id:uuid}", response_model=schemas.WorkOrderResponse)
def get_work_order(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("work_orders:view")),
):
    """Retorna detalhes de uma ordem de trabalho."""
    try:
        return service.get_work_order(db, org_id=_org_id(current_user), order_id=order_id)
    except ValueError as e:
        _handle_value_error(e)


@router.put("/orders/{order_id:uuid}", response_model=schemas.WorkOrderResponse)
def update_work_order(
    order_id: uuid.UUID,
    data: schemas.WorkOrderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("work_orders:update")),
):
    """Atualiza uma ordem de trabalho."""
    try:
        return service.update_work_order(
            db, org_id=_org_id(current_user), order_id=order_id,
            data=data, current_user=current_user,
        )
    except ValueError as e:
        _handle_value_error(e)


@router.patch("/orders/{order_id:uuid}/status", response_model=schemas.WorkOrderResponse)
@router.post("/orders/{order_id:uuid}/status", response_model=schemas.WorkOrderResponse)
def change_work_order_status(
    order_id: uuid.UUID,
    data: schemas.WorkOrderStatusChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("work_orders:update", "work_orders:complete")),
):
    """Altera o status de uma ordem de trabalho."""
    try:
        return service.change_work_order_status(
            db, org_id=_org_id(current_user), order_id=order_id,
            data=data, current_user=current_user,
        )
    except ValueError as e:
        _handle_value_error(e)


@router.delete("/orders/{order_id:uuid}", status_code=status.HTTP_200_OK)
def delete_work_order(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("work_orders:delete", "work_orders:update", "projects:update")),
):
    """Exclui uma ordem de serviço/produção."""
    try:
        return service.delete_work_order(db, org_id=_org_id(current_user), order_id=order_id, current_user=current_user)
    except ValueError as e:
        _handle_value_error(e)


# ==============================================================================
# TASKS
# ==============================================================================

@router.get("/tasks", response_model=schemas.PaginatedResponse)
@router.get("/tasks/list", response_model=schemas.PaginatedResponse)
def list_all_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("tasks:view")),
    project_id: uuid.UUID | None = Query(None),
    work_order_id: uuid.UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    assigned_to: uuid.UUID | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Lista tarefas com filtros. Use assigned_to=<user_id> para 'Minhas Tarefas'."""
    return service.list_tasks(
        db, org_id=_org_id(current_user), project_id=project_id,
        work_order_id=work_order_id, status=status_filter,
        assigned_to=assigned_to, search=search, page=page, page_size=page_size,
    )


@router.get("/tasks/my", response_model=schemas.PaginatedResponse)
def list_my_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("tasks:view")),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Lista tarefas atribuídas ao usuário logado."""
    return service.list_tasks(
        db, org_id=_org_id(current_user), assigned_to=current_user.id,
        status=status_filter, page=page, page_size=page_size,
    )


@router.post("/tasks", response_model=schemas.TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    data: schemas.TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("tasks:create")),
):
    """Cria uma nova tarefa vinculada a um projeto ou ordem."""
    try:
        return service.create_task(
            db, org_id=_org_id(current_user), data=data, current_user=current_user,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/tasks/{task_id:uuid}", response_model=schemas.TaskResponse)
def get_task(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("tasks:view")),
):
    """Retorna detalhes de uma tarefa."""
    try:
        return service.get_task(db, org_id=_org_id(current_user), task_id=task_id)
    except ValueError as e:
        _handle_value_error(e)


@router.put("/tasks/{task_id:uuid}", response_model=schemas.TaskResponse)
def update_task(
    task_id: uuid.UUID,
    data: schemas.TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("tasks:update")),
):
    """Atualiza uma tarefa."""
    try:
        return service.update_task(
            db, org_id=_org_id(current_user), task_id=task_id,
            data=data, current_user=current_user,
        )
    except ValueError as e:
        _handle_value_error(e)


@router.patch("/tasks/{task_id:uuid}/status", response_model=schemas.TaskResponse)
@router.post("/tasks/{task_id:uuid}/status", response_model=schemas.TaskResponse)
def change_task_status(
    task_id: uuid.UUID,
    data: schemas.TaskStatusChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("tasks:update", "tasks:complete")),
):
    """Altera o status de uma tarefa."""
    try:
        return service.change_task_status(
            db, org_id=_org_id(current_user), task_id=task_id,
            data=data, current_user=current_user,
        )
    except ValueError as e:
        _handle_value_error(e)


@router.post("/tasks/{task_id:uuid}/assignments", response_model=schemas.TaskAssignmentResponse, status_code=status.HTTP_201_CREATED)
def add_task_assignment(
    task_id: uuid.UUID,
    data: schemas.TaskAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("tasks:assign")),
):
    """Atribui um responsável a uma tarefa."""
    try:
        return service.add_task_assignment(
            db, org_id=_org_id(current_user), task_id=task_id,
            data=data, current_user=current_user,
        )
    except ValueError as e:
        _handle_value_error(e)


@router.post("/tasks/{task_id:uuid}/dependencies", response_model=schemas.TaskDependencyResponse, status_code=status.HTTP_201_CREATED)
def add_task_dependency(
    task_id: uuid.UUID,
    data: schemas.TaskDependencyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("tasks:update")),
):
    """Adiciona uma dependência a uma tarefa."""
    return service.add_task_dependency(
        db, org_id=_org_id(current_user), task_id=task_id,
        data=data, current_user=current_user,
    )


@router.delete("/tasks/{task_id:uuid}", status_code=status.HTTP_200_OK)
def delete_task(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("tasks:delete", "tasks:update", "projects:update")),
):
    """Exclui uma tarefa."""
    try:
        return service.delete_task(db, org_id=_org_id(current_user), task_id=task_id, current_user=current_user)
    except ValueError as e:
        _handle_value_error(e)


# ==============================================================================
# ISSUES
# ==============================================================================

@router.get("/issues", response_model=schemas.PaginatedResponse)
@router.get("/issues/list", response_model=schemas.PaginatedResponse)
def list_issues(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("issues:manage")),
    project_id: uuid.UUID | None = Query(None),
    work_order_id: uuid.UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    severity: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Lista ocorrências/pendências com filtros."""
    return service.list_issues(
        db, org_id=_org_id(current_user), project_id=project_id,
        work_order_id=work_order_id, status=status_filter, severity=severity,
        search=search, page=page, page_size=page_size,
    )


@router.post("/issues", response_model=schemas.IssueResponse, status_code=status.HTTP_201_CREATED)
def create_issue(
    data: schemas.IssueCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("issues:manage")),
):
    """Registra uma nova ocorrência/pendência."""
    return service.create_issue(
        db, org_id=_org_id(current_user), data=data, current_user=current_user,
    )


@router.get("/issues/{issue_id:uuid}", response_model=schemas.IssueResponse)
def get_issue(
    issue_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("issues:manage")),
):
    """Retorna detalhes de uma ocorrência."""
    try:
        return service.get_issue(db, org_id=_org_id(current_user), issue_id=issue_id)
    except ValueError as e:
        _handle_value_error(e)


@router.put("/issues/{issue_id:uuid}", response_model=schemas.IssueResponse)
def update_issue(
    issue_id: uuid.UUID,
    data: schemas.IssueUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("issues:manage")),
):
    """Atualiza ou resolve uma ocorrência."""
    try:
        return service.update_issue(
            db, org_id=_org_id(current_user), issue_id=issue_id,
            data=data, current_user=current_user,
        )
    except ValueError as e:
        _handle_value_error(e)


@router.post("/issues/{issue_id:uuid}/resolve", response_model=schemas.IssueResponse)
def resolve_issue(
    issue_id: uuid.UUID,
    data: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("issues:manage")),
):
    """Resolve uma ocorrência com anotações de resolução."""
    try:
        notes = data.get("resolution_notes", "")
        update_data = schemas.IssueUpdate(status="resolved", resolution=notes)
        return service.update_issue(
            db, org_id=_org_id(current_user), issue_id=issue_id,
            data=update_data, current_user=current_user,
        )
    except ValueError as e:
        _handle_value_error(e)


@router.delete("/issues/{issue_id:uuid}", status_code=status.HTTP_200_OK)
def delete_issue(
    issue_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("issues:delete", "issues:manage", "projects:update")),
):
    """Exclui uma ocorrência/pendência."""
    try:
        return service.delete_issue(db, org_id=_org_id(current_user), issue_id=issue_id, current_user=current_user)
    except ValueError as e:
        _handle_value_error(e)


# ==============================================================================
# CHECKLISTS
# ==============================================================================

@router.get("/checklists/templates", response_model=list[schemas.ChecklistTemplateResponse])
def list_checklist_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("projects:view", "workflows:manage")),
):
    """Lista templates de checklist disponíveis."""
    return service.list_checklist_templates(db, org_id=_org_id(current_user))


@router.post("/checklists/templates", response_model=schemas.ChecklistTemplateResponse, status_code=status.HTTP_201_CREATED)
def create_checklist_template(
    data: schemas.ChecklistTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workflows:manage")),
):
    """Cria um novo template de checklist."""
    return service.create_checklist_template(db, org_id=_org_id(current_user), data=data)


@router.get("/checklists", response_model=list[schemas.ChecklistResponse])
def list_checklists(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("projects:view")),
    project_id: uuid.UUID | None = Query(None),
    work_order_id: uuid.UUID | None = Query(None),
    task_id: uuid.UUID | None = Query(None),
):
    """Lista checklists de tarefas ou ordens de serviço."""
    return service.list_checklists(
        db, org_id=_org_id(current_user),
        project_id=project_id, work_order_id=work_order_id, task_id=task_id,
    )


@router.post("/checklists", response_model=schemas.ChecklistResponse, status_code=status.HTTP_201_CREATED)
def create_checklist(
    data: schemas.ChecklistCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("tasks:update", "work_orders:update")),
):
    """Instancia um checklist (opcionalmente a partir de um template)."""
    return service.create_checklist(
        db, org_id=_org_id(current_user), data=data, current_user=current_user,
    )


@router.patch("/checklists/{checklist_id:uuid}/items/{item_id:uuid}", response_model=schemas.ChecklistItemResponse)
@router.post("/checklists/{checklist_id:uuid}/items/{item_id:uuid}/toggle", response_model=schemas.ChecklistItemResponse)
def toggle_checklist_item(
    checklist_id: uuid.UUID,
    item_id: uuid.UUID,
    data: schemas.ChecklistItemToggle,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("tasks:update", "work_orders:update")),
):
    """Marca/desmarca um item do checklist."""
    try:
        return service.toggle_checklist_item(
            db, checklist_id=checklist_id, item_id=item_id,
            data=data, current_user=current_user,
        )
    except ValueError as e:
        _handle_value_error(e)


# ==============================================================================
# COMMENTS
# ==============================================================================

@router.post("/comments", response_model=schemas.CommentResponse, status_code=status.HTTP_201_CREATED)
def create_comment(
    data: schemas.CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("projects:view")),
):
    """Adiciona um comentário a um projeto, ordem, tarefa ou ocorrência."""
    return service.create_comment(
        db, org_id=_org_id(current_user), data=data, current_user=current_user,
    )


@router.get("/comments", response_model=list[schemas.CommentResponse])
def list_comments(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("projects:view")),
    project_id: uuid.UUID | None = Query(None),
    work_order_id: uuid.UUID | None = Query(None),
    task_id: uuid.UUID | None = Query(None),
    issue_id: uuid.UUID | None = Query(None),
):
    """Lista comentários filtrados por entidade."""
    return service.list_comments(
        db, org_id=_org_id(current_user),
        project_id=project_id, work_order_id=work_order_id,
        task_id=task_id, issue_id=issue_id,
    )
