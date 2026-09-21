"""
modules/projects/schemas.py - Schemas Pydantic do Módulo de Projetos & Operações

Define os contratos de entrada (Create/Update) e saída (Response) para todas
as entidades do módulo. Segue o padrão existente do ControlB:
- ClasseCreate: dados obrigatórios para criação
- ClasseUpdate: dados opcionais para atualização parcial
- ClasseResponse: serialização de saída (model_config com from_attributes=True)
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from controlb.modules.projects.engine_schema import TypeConfiguration

# ==============================================================================
# 1. PROJECT TYPE
# ==============================================================================

class ProjectTypeCreate(BaseModel):
    configuration: TypeConfiguration | None = None
    name: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=1, max_length=50)
    description: str | None = None
    color: str = "#6366f1"
    icon: str | None = None
    prefix: str = "PRJ"
    default_workflow_id: uuid.UUID | None = None

class ProjectTypeUpdate(BaseModel):
    configuration: TypeConfiguration | None = None
    name: str | None = None
    code: str | None = None
    description: str | None = None
    color: str | None = None
    icon: str | None = None
    prefix: str | None = None
    default_workflow_id: uuid.UUID | None = None
    is_active: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def _clean_empty_uuids(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "default_workflow_id" in data and data["default_workflow_id"] == "":
                data["default_workflow_id"] = None
        return data

class ProjectTypeResponse(BaseModel):
    configuration: dict | None = None
    published_revision_id: uuid.UUID | None = None
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    code: str
    name: str
    description: str | None
    color: str
    icon: str | None
    prefix: str
    default_workflow_id: uuid.UUID | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ==============================================================================
# 2. WORK ORDER TYPE
# ==============================================================================

class WorkOrderTypeCreate(BaseModel):
    configuration: TypeConfiguration | None = None
    name: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=1, max_length=50)
    description: str | None = None
    color: str = "#8b5cf6"
    prefix: str = "OS"
    default_workflow_id: uuid.UUID | None = None

class WorkOrderTypeUpdate(BaseModel):
    configuration: TypeConfiguration | None = None
    name: str | None = None
    code: str | None = None
    description: str | None = None
    color: str | None = None
    prefix: str | None = None
    default_workflow_id: uuid.UUID | None = None
    is_active: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def _clean_empty_uuids(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "default_workflow_id" in data and data["default_workflow_id"] == "":
                data["default_workflow_id"] = None
        return data

class WorkOrderTypeResponse(BaseModel):
    configuration: dict | None = None
    published_revision_id: uuid.UUID | None = None
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    code: str
    name: str
    description: str | None
    color: str
    prefix: str
    default_workflow_id: uuid.UUID | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ==============================================================================
# 3. WORKFLOW TEMPLATE & STAGE
# ==============================================================================

class WorkflowStageCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    position: int = Field(..., ge=0)
    color: str = "#6366f1"
    is_initial: bool = False
    is_terminal: bool = False
    allowed_transitions: list[uuid.UUID] = []

class WorkflowStageUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    position: int | None = None
    color: str | None = None
    is_initial: bool | None = None
    is_terminal: bool | None = None
    allowed_transitions: list[uuid.UUID] | None = None

class WorkflowStageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    workflow_id: uuid.UUID
    name: str
    description: str | None
    position: int
    color: str
    is_initial: bool
    is_terminal: bool
    allowed_transitions: list
    created_at: datetime

class WorkflowTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    target_entity: str = "PROJECT"
    stages: list[WorkflowStageCreate] = []

class WorkflowTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    target_entity: str | None = None
    is_active: bool | None = None

class WorkflowTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: str | None
    target_entity: str
    is_active: bool
    stages: list[WorkflowStageResponse] = []
    created_at: datetime
    updated_at: datetime


# ==============================================================================
# 4. PROJECT
# ==============================================================================

class ProjectCreate(BaseModel):
    title: str | None = None
    name: str | None = None
    description: str | None = None
    project_type_id: uuid.UUID | None = None
    workflow_id: uuid.UUID | None = None
    current_stage_id: uuid.UUID | None = None
    priority: str = "MEDIUM"
    tags: list[str] = []

    planned_start_date: datetime | None = None
    planned_end_date: datetime | None = None

    estimated_budget: Decimal = Decimal("0.00")
    estimated_hours: Decimal = Decimal("0.00")

    manager_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    cost_center_id: uuid.UUID | None = None

    sales_order_id: uuid.UUID | None = None
    sales_quote_id: uuid.UUID | None = None
    opportunity_id: uuid.UUID | None = None

    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    notes: str | None = None
    is_billable: bool = True
    custom_fields: dict = {}

    @model_validator(mode="before")
    @classmethod
    def harmonize_title_and_name(cls, data: Any) -> Any:
        if isinstance(data, dict):
            t = data.get("title") or data.get("name")
            if t:
                data["title"] = str(t).strip()
                data["name"] = str(t).strip()
            else:
                raise ValueError("O campo 'title' ou 'name' do projeto é obrigatório.")
            for key in ("project_type_id", "workflow_id", "current_stage_id", "manager_id", "team_id", "customer_id", "contact_id", "cost_center_id", "sales_order_id", "sales_quote_id", "opportunity_id"):
                if data.get(key) == "":
                    data[key] = None
        return data

class ProjectUpdate(BaseModel):
    title: str | None = None
    name: str | None = None
    description: str | None = None
    project_type_id: uuid.UUID | None = None
    priority: str | None = None
    tags: list[str] | None = None

    planned_start_date: datetime | None = None
    planned_end_date: datetime | None = None

    estimated_budget: Decimal | None = None
    estimated_hours: Decimal | None = None

    manager_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    cost_center_id: uuid.UUID | None = None
    workflow_id: uuid.UUID | None = None
    current_stage_id: uuid.UUID | None = None
    progress_percent: int | None = None

    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    notes: str | None = None
    is_billable: bool | None = None
    custom_fields: dict | None = None

    @model_validator(mode="before")
    @classmethod
    def _harmonize_and_clean_update(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "name" in data and "title" not in data:
                data["title"] = data["name"]
            elif "title" in data and "name" not in data:
                data["name"] = data["title"]
            uuid_fields = [
                "project_type_id", "manager_id", "team_id", "customer_id",
                "contact_id", "cost_center_id", "workflow_id", "current_stage_id"
            ]
            for field in uuid_fields:
                if field in data and data[field] == "":
                    data[field] = None
        return data

class ProjectStageChange(BaseModel):
    """Payload para mudar a etapa do projeto no workflow."""
    stage_id: uuid.UUID | None = None
    to_stage_id: uuid.UUID | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def resolve_stage(self):
        if not self.stage_id and not self.to_stage_id:
            raise ValueError("stage_id é obrigatório.")
        if not self.stage_id and self.to_stage_id:
            self.stage_id = self.to_stage_id
        return self

class ProjectStatusChange(BaseModel):
    """Payload para mudar o status do projeto."""
    status: str = Field(..., pattern="^(draft|planning|in_progress|on_hold|completed|cancelled|archived)$")
    notes: str | None = None

class ProjectMemberSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    role: str
    joined_at: datetime
    user_name: str | None = None
    user_email: str | None = None

class ProjectStageSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    color: str

class ProjectTypeSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    color: str
    prefix: str

class ProjectResponse(BaseModel):
    type_revision_id: uuid.UUID | None = None
    execution_schema: dict | None = None
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    document_id: uuid.UUID
    project_number: str
    title: str
    code: str | None = None
    name: str | None = None
    description: str | None
    project_type: ProjectTypeSummary | None = None
    priority: str
    tags: list[str]
    status: str
    workflow_id: uuid.UUID | None
    current_stage_id: uuid.UUID | None
    current_stage: ProjectStageSummary | None = None
    progress_percent: int

    planned_start_date: datetime | None
    planned_end_date: datetime | None
    actual_start_date: datetime | None
    actual_end_date: datetime | None

    estimated_budget: Decimal
    actual_cost: Decimal
    estimated_hours: Decimal
    actual_hours: Decimal

    manager_id: uuid.UUID | None
    team_id: uuid.UUID | None
    customer_id: uuid.UUID | None
    contact_id: uuid.UUID | None
    sales_order_id: uuid.UUID | None
    sales_quote_id: uuid.UUID | None
    opportunity_id: uuid.UUID | None
    cost_center_id: uuid.UUID | None

    address: str | None
    city: str | None
    state: str | None
    zip_code: str | None

    custom_fields: dict
    notes: str | None
    is_billable: bool
    members: list[ProjectMemberSummary] = []

    created_by_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def populate_aliases(self):
        if not self.code:
            self.code = self.project_number
        if not self.name:
            self.name = self.title
        return self

class ProjectListResponse(BaseModel):
    """Versão resumida do projeto para listagens e kanban."""
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    project_number: str
    title: str
    code: str | None = None
    name: str | None = None
    project_type: ProjectTypeSummary | None = None
    priority: str
    status: str
    current_stage: ProjectStageSummary | None = None
    progress_percent: int
    planned_end_date: datetime | None
    manager_id: uuid.UUID | None
    customer_id: uuid.UUID | None
    tags: list[str]
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def populate_aliases(self):
        if not self.code:
            self.code = self.project_number
        if not self.name:
            self.name = self.title
        return self


# ==============================================================================
# 5. PROJECT MEMBER
# ==============================================================================

class ProjectMemberCreate(BaseModel):
    user_id: uuid.UUID
    role: str = "member"

class ProjectMemberUpdate(BaseModel):
    role: str

class ProjectMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    joined_at: datetime
    added_by_id: uuid.UUID | None


# ==============================================================================
# 6. PROJECT STAGE HISTORY
# ==============================================================================

class ProjectStageHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    from_stage: ProjectStageSummary | None = None
    to_stage: ProjectStageSummary | None = None
    changed_by_id: uuid.UUID | None
    notes: str | None
    created_at: datetime


# ==============================================================================
# 7. WORK ORDER
# ==============================================================================

class WorkOrderCreate(BaseModel):
    current_stage_id: uuid.UUID | None = None
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    project_id: uuid.UUID | None = None
    order_type_id: uuid.UUID | None = None
    workflow_id: uuid.UUID | None = None
    priority: str = "MEDIUM"

    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    estimated_cost: Decimal = Decimal("0.00")
    estimated_hours: Decimal = Decimal("0.00")

    responsible_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    address: str | None = None
    notes: str | None = None
    custom_fields: dict = {}

    @model_validator(mode="before")
    @classmethod
    def sanitize_work_order(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("order_type_id") and data.get("work_order_type_id"):
                data["order_type_id"] = data["work_order_type_id"]
            for key in ("project_id", "order_type_id", "workflow_id", "responsible_id", "team_id"):
                if data.get(key) == "":
                    data[key] = None
        return data

class WorkOrderUpdate(BaseModel):
    current_stage_id: uuid.UUID | None = None
    title: str | None = None
    name: str | None = None
    description: str | None = None
    project_id: uuid.UUID | None = None
    order_type_id: uuid.UUID | None = None
    priority: str | None = None

    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    estimated_cost: Decimal | None = None
    estimated_hours: Decimal | None = None

    responsible_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    workflow_id: uuid.UUID | None = None
    progress_percent: int | None = None
    address: str | None = None
    notes: str | None = None
    custom_fields: dict | None = None

    @model_validator(mode="before")
    @classmethod
    def sanitize_work_order_update(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "name" in data and "title" not in data:
                data["title"] = data["name"]
            elif "title" in data and "name" not in data:
                data["name"] = data["title"]
            if not data.get("order_type_id") and data.get("work_order_type_id"):
                data["order_type_id"] = data["work_order_type_id"]
            for key in ("project_id", "order_type_id", "workflow_id", "responsible_id", "team_id"):
                if data.get(key) == "":
                    data[key] = None
        return data

class WorkOrderStatusChange(BaseModel):
    status: str = Field(..., pattern="^(draft|scheduled|in_progress|on_hold|completed|cancelled)$")
    notes: str | None = None

class WorkOrderResponse(BaseModel):
    type_revision_id: uuid.UUID | None = None
    execution_schema: dict | None = None
    current_stage_id: uuid.UUID | None = None
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    document_id: uuid.UUID
    project_id: uuid.UUID | None
    order_number: str
    title: str
    description: str | None
    order_type: WorkOrderTypeResponse | None = None
    priority: str
    status: str
    workflow_id: uuid.UUID | None
    current_stage: ProjectStageSummary | None = None
    progress_percent: int

    scheduled_start: datetime | None
    scheduled_end: datetime | None
    actual_start: datetime | None
    actual_end: datetime | None

    estimated_cost: Decimal
    actual_cost: Decimal
    estimated_hours: Decimal
    actual_hours: Decimal

    responsible_id: uuid.UUID | None
    team_id: uuid.UUID | None
    address: str | None
    notes: str | None
    custom_fields: dict

    created_by_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

class WorkOrderListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID | None
    order_number: str
    title: str
    priority: str
    status: str
    current_stage: ProjectStageSummary | None = None
    progress_percent: int
    scheduled_end: datetime | None
    responsible_id: uuid.UUID | None
    created_at: datetime


# ==============================================================================
# 8. TASK
# ==============================================================================

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    project_id: uuid.UUID | None = None
    work_order_id: uuid.UUID | None = None
    priority: str = "MEDIUM"
    status: str = Field("todo", pattern="^(backlog|todo|in_progress|in_review|blocked|done|cancelled)$")
    task_type: str = "task"
    due_date: datetime | None = None
    estimated_hours: Decimal = Decimal("0.00")
    position: int = 0
    assignee_ids: list[uuid.UUID] = []

    @model_validator(mode="before")
    @classmethod
    def sanitize_task(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("assignee_ids") and data.get("assigned_user_ids"):
                data["assignee_ids"] = data["assigned_user_ids"]
            for key in ("project_id", "work_order_id"):
                if data.get(key) == "":
                    data[key] = None
            if data.get("status"):
                normalized_status = str(data["status"]).lower()
                data["status"] = "in_review" if normalized_status == "review" else normalized_status
        return data

class TaskUpdate(BaseModel):
    title: str | None = None
    name: str | None = None
    description: str | None = None
    project_id: uuid.UUID | None = None
    work_order_id: uuid.UUID | None = None
    priority: str | None = None
    status: str | None = Field(None, pattern="^(backlog|todo|in_progress|in_review|blocked|done|cancelled)$")
    task_type: str | None = None
    due_date: datetime | None = None
    estimated_hours: Decimal | None = None
    position: int | None = None
    assignee_ids: list[uuid.UUID] | None = None

    @model_validator(mode="before")
    @classmethod
    def sanitize_task_update(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "assigned_user_ids" in data and "assignee_ids" not in data:
                data["assignee_ids"] = data["assigned_user_ids"]
            if "name" in data and "title" not in data:
                data["title"] = data["name"]
            elif "title" in data and "name" not in data:
                data["name"] = data["title"]
            for key in ("project_id", "work_order_id"):
                if data.get(key) == "":
                    data[key] = None
            if data.get("status"):
                normalized_status = str(data["status"]).lower()
                data["status"] = "in_review" if normalized_status == "review" else normalized_status
        return data

class TaskStatusChange(BaseModel):
    status: str = Field(..., pattern="^(backlog|todo|in_progress|in_review|blocked|done|cancelled)$")
    notes: str | None = None

class TaskAssignmentCreate(BaseModel):
    user_id: uuid.UUID
    role: str = "assignee"

class TaskAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    task_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    assigned_at: datetime

class TaskDependencyCreate(BaseModel):
    dependency_task_id: uuid.UUID
    dependency_type: str = "finish_to_start"

class TaskDependencyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    dependent_task_id: uuid.UUID
    dependency_task_id: uuid.UUID
    dependency_type: str

class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    document_id: uuid.UUID
    project_id: uuid.UUID | None
    work_order_id: uuid.UUID | None
    task_number: str
    title: str
    description: str | None
    priority: str
    task_type: str
    status: str
    progress_percent: int
    due_date: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    estimated_hours: Decimal
    actual_hours: Decimal
    position: int
    assignments: list[TaskAssignmentResponse] = []
    dependencies: list[TaskDependencyResponse] = []
    created_by_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

class TaskListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID | None
    work_order_id: uuid.UUID | None
    task_number: str
    title: str
    priority: str
    status: str
    due_date: datetime | None
    progress_percent: int
    assignments: list[TaskAssignmentResponse] = []
    created_at: datetime


# ==============================================================================
# 9. ISSUE
# ==============================================================================

class IssueCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    project_id: uuid.UUID | None = None
    work_order_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    issue_type: str = "problem"
    severity: str = "medium"
    assigned_to_id: uuid.UUID | None = None
    impact_cost: Decimal = Decimal("0.00")
    impact_days: int = 0

    @model_validator(mode="before")
    @classmethod
    def sanitize_issue(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for key in ("project_id", "work_order_id", "task_id", "assigned_to_id"):
                if data.get(key) == "":
                    data[key] = None
        return data

class IssueUpdate(BaseModel):
    title: str | None = None
    name: str | None = None
    description: str | None = None
    issue_type: str | None = None
    severity: str | None = None
    status: str | None = None
    project_id: uuid.UUID | None = None
    work_order_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    assigned_to_id: uuid.UUID | None = None
    resolution: str | None = None
    impact_cost: Decimal | None = None
    impact_days: int | None = None

    @model_validator(mode="before")
    @classmethod
    def sanitize_issue_update(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "resolution_notes" in data and "resolution" not in data:
                data["resolution"] = data["resolution_notes"]
            if "name" in data and "title" not in data:
                data["title"] = data["name"]
            elif "title" in data and "name" not in data:
                data["name"] = data["title"]
            for key in ("project_id", "work_order_id", "task_id", "assigned_to_id"):
                if data.get(key) == "":
                    data[key] = None
        return data

class IssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID | None
    work_order_id: uuid.UUID | None
    task_id: uuid.UUID | None
    issue_number: str
    title: str
    description: str | None
    issue_type: str
    severity: str
    status: str
    impact_cost: Decimal
    impact_days: int
    resolution: str | None
    resolved_at: datetime | None
    resolved_by_id: uuid.UUID | None
    assigned_to_id: uuid.UUID | None
    reported_by_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


# ==============================================================================
# 10. CHECKLIST
# ==============================================================================

class ChecklistTemplateItemCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)
    position: int
    is_required: bool = False

class ChecklistTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    category: str | None = None
    items: list[ChecklistTemplateItemCreate] = []

class ChecklistTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    is_active: bool | None = None

class ChecklistTemplateItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    text: str
    position: int
    is_required: bool

class ChecklistTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: str | None
    category: str | None
    is_active: bool
    items: list[ChecklistTemplateItemResponse] = []
    created_at: datetime
    updated_at: datetime

class ChecklistCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    task_id: uuid.UUID | None = None
    work_order_id: uuid.UUID | None = None
    template_id: uuid.UUID | None = None

class ChecklistItemToggle(BaseModel):
    is_checked: bool

class ChecklistItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    text: str
    position: int
    is_required: bool
    is_checked: bool
    checked_at: datetime | None
    checked_by_id: uuid.UUID | None

class ChecklistResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    task_id: uuid.UUID | None
    work_order_id: uuid.UUID | None
    template_id: uuid.UUID | None
    name: str
    total_items: int
    checked_items: int
    items: list[ChecklistItemResponse] = []
    created_at: datetime
    updated_at: datetime


# ==============================================================================
# 11. COMMENT
# ==============================================================================

class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1)
    project_id: uuid.UUID | None = None
    work_order_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    issue_id: uuid.UUID | None = None

class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID | None
    work_order_id: uuid.UUID | None
    task_id: uuid.UUID | None
    issue_id: uuid.UUID | None
    content: str
    author_id: uuid.UUID | None
    author_name: str | None = None
    created_at: datetime
    updated_at: datetime


# ==============================================================================
# 12. DASHBOARD & ANALYTICS
# ==============================================================================

class ProjectDashboardResponse(BaseModel):
    total_projects: int = 0
    active_projects: int = 0
    completed_projects: int = 0
    overdue_projects: int = 0
    total_orders: int = 0
    active_orders: int = 0
    total_tasks: int = 0
    pending_tasks: int = 0
    open_issues: int = 0
    projects_by_status: dict[str, int] = {}
    projects_by_type: list[dict] = []
    recent_activity: list[dict] = []


# ==============================================================================
# 13. PAGINATION WRAPPER
# ==============================================================================

class PaginatedResponse(BaseModel):
    """Wrapper genérico para respostas paginadas."""
    items: list = []
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0
