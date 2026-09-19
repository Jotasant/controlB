/**
 * types/projects.ts - Tipos e Interfaces do Módulo de Projetos & Operações
 * 
 * Espelha integralmente os modelos relacionais e schemas Pydantic do backend FastAPI,
 * garantindo tipagem estrita, auto-complete e robustez na camada de apresentação.
 */

// ==============================================================================
// 1. CONFIGURAÇÕES: TIPOS, WORKFLOWS E TEMPLATES
// ==============================================================================

export interface WorkflowStage {
  id: string;
  workflow_id: string;
  name: string;
  description?: string | null;
  position: number;
  color: string;
  is_initial: boolean;
  is_final?: boolean;
  is_terminal?: boolean;
  requires_checklist?: boolean;
  checklist_template_id?: string | null;
  created_at: string;
  updated_at?: string;
}

export interface WorkflowTemplate {
  id: string;
  organization_id: string;
  name: string;
  description?: string | null;
  target_entity: 'PROJECT' | 'WORK_ORDER';
  is_active: boolean;
  stages?: WorkflowStage[];
  created_at: string;
  updated_at: string;
}

export interface ProjectType {
  id: string;
  organization_id: string;
  code: string;
  name: string;
  description?: string | null;
  color: string;
  icon?: string | null;
  prefix: string;
  default_workflow_id?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface WorkOrderType {
  id: string;
  organization_id: string;
  code: string;
  name: string;
  description?: string | null;
  color: string;
  prefix: string;
  default_workflow_id?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ChecklistTemplateItem {
  id: string;
  template_id: string;
  text: string;
  position: number;
  is_required: boolean;
}

export interface ChecklistTemplate {
  id: string;
  organization_id: string;
  name: string;
  description?: string | null;
  category?: string | null;
  is_active: boolean;
  items?: ChecklistTemplateItem[];
  created_at: string;
  updated_at: string;
}

// ==============================================================================
// 2. CHECKLISTS INSTANCIADOS
// ==============================================================================

export interface ChecklistItem {
  id: string;
  checklist_id: string;
  text: string;
  position: number;
  is_required: boolean;
  is_checked: boolean;
  checked_at?: string | null;
  checked_by_id?: string | null;
  notes?: string | null;
}

export interface Checklist {
  id: string;
  organization_id: string;
  name: string;
  project_id?: string | null;
  work_order_id?: string | null;
  task_id?: string | null;
  stage_id?: string | null;
  template_id?: string | null;
  is_completed: boolean;
  completed_at?: string | null;
  completed_by_id?: string | null;
  items?: ChecklistItem[];
  created_at: string;
  updated_at: string;
}

// ==============================================================================
// 3. PROJETOS
// ==============================================================================

export type ProjectStatus = 'DRAFT' | 'PLANNING' | 'IN_PROGRESS' | 'ON_HOLD' | 'COMPLETED' | 'CANCELLED';
export type ProjectPriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface ProjectMember {
  id: string;
  project_id: string;
  user_id: string;
  role: 'LEADER' | 'TECHNICAL' | 'MEMBER' | 'STAKEHOLDER';
  joined_at: string;
  user_name?: string | null;
  user_email?: string | null;
}

export interface ProjectStageHistory {
  id: string;
  project_id: string;
  from_stage_id?: string | null;
  to_stage_id: string;
  changed_by_id?: string | null;
  changed_at: string;
  notes?: string | null;
  from_stage_name?: string | null;
  to_stage_name?: string | null;
}

export interface Project {
  id: string;
  organization_id: string;
  document_id?: string;
  project_number?: string;
  code: string;
  name: string;
  title: string;
  description?: string | null;
  project_type_id: string;
  status: ProjectStatus;
  priority: ProjectPriority;
  customer_id?: string | null;
  contact_id?: string | null;
  lead_id?: string | null;
  opportunity_id?: string | null;
  sales_quote_id?: string | null;
  sales_order_id?: string | null;
  cost_center_id?: string | null;
  team_id?: string | null;
  manager_id?: string | null;
  workflow_template_id?: string | null;
  current_stage_id?: string | null;
  workflow_id?: string | null;
  start_date?: string | null;
  target_end_date?: string | null;
  actual_end_date?: string | null;
  planned_start_date?: string | null;
  planned_end_date?: string | null;
  estimated_budget: number;
  committed_cost: number;
  realized_cost: number;
  invoiced_amount: number;
  estimated_hours?: number;
  actual_hours?: number;
  progress_percent: number;
  is_billable: boolean;
  address?: string | null;
  city?: string | null;
  state?: string | null;
  zip_code?: string | null;
  color?: string | null;
  tags: string[];
  custom_fields: Record<string, unknown>;
  notes?: string | null;
  created_at: string;
  updated_at: string;

  // Relações embutidas para exibição amigável
  project_type?: ProjectType | null;
  current_stage?: WorkflowStage | null;
  members?: ProjectMember[];
  work_orders?: WorkOrder[];
  tasks?: Task[];
  issues?: Issue[];
  checklists?: Checklist[];
  customer_name?: string | null;
  manager_name?: string | null;
}

// ==============================================================================
// 4. ORDENS DE SERVIÇO (WORK ORDERS)
// ==============================================================================

export type WorkOrderStatus = 'DRAFT' | 'OPEN' | 'IN_PROGRESS' | 'WAITING_PARTS' | 'REVIEW' | 'COMPLETED' | 'CANCELLED';

export interface WorkOrder {
  id: string;
  organization_id: string;
  code: string;
  order_number?: string;
  title: string;
  description?: string | null;
  order_type_id?: string | null;
  project_id?: string | null;
  status: WorkOrderStatus;
  priority: ProjectPriority;
  customer_id?: string | null;
  contact_id?: string | null;
  cost_center_id?: string | null;
  responsible_id?: string | null;
  team_id?: string | null;
  current_stage_id?: string | null;
  document_id?: string | null;
  workflow_id?: string | null;
  start_date?: string | null;
  due_date?: string | null;
  scheduled_start?: string | null;
  scheduled_end?: string | null;
  completed_at?: string | null;
  estimated_hours: number;
  actual_hours: number;
  estimated_cost: number;
  actual_cost: number;
  progress_percent?: number;
  address?: string | null;
  tags: string[];
  notes?: string | null;
  created_at: string;
  updated_at: string;

  order_type?: WorkOrderType | null;
  current_stage?: WorkflowStage | null;
  project_name?: string | null;
  responsible_name?: string | null;
  customer_name?: string | null;
  tasks?: Task[];
}

// ==============================================================================
// 5. TAREFAS (TASKS)
// ==============================================================================

export type TaskStatus = 'TODO' | 'IN_PROGRESS' | 'REVIEW' | 'BLOCKED' | 'DONE' | 'CANCELLED';

export interface TaskAssignment {
  id: string;
  task_id: string;
  user_id: string;
  assigned_at: string;
  user_name?: string | null;
}

export interface TaskDependency {
  id: string;
  task_id: string;
  depends_on_task_id: string;
  dependency_type: 'FINISH_TO_START' | 'START_TO_START' | 'FINISH_TO_FINISH';
  depends_on_task_title?: string | null;
}

export interface Task {
  id: string;
  organization_id: string;
  task_number?: string;
  title: string;
  description?: string | null;
  project_id?: string | null;
  work_order_id?: string | null;
  parent_task_id?: string | null;
  status: TaskStatus;
  priority: ProjectPriority;
  stage_id?: string | null;
  start_date?: string | null;
  due_date?: string | null;
  completed_at?: string | null;
  estimated_hours: number;
  actual_hours: number;
  position: number;
  tags: string[];
  is_milestone: boolean;
  created_at: string;
  updated_at: string;

  assignments?: TaskAssignment[];
  dependencies?: TaskDependency[];
  checklists?: Checklist[];
  project_name?: string | null;
  work_order_title?: string | null;
  assignees_names?: string[];
}

// ==============================================================================
// 6. OCORRÊNCIAS & BLOQUEIOS (ISSUES)
// ==============================================================================

export type IssueStatus = 'OPEN' | 'INVESTIGATING' | 'WAITING' | 'RESOLVED' | 'CLOSED';
export type IssueSeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type IssueType = 'BUG' | 'BLOCKER' | 'MATERIAL_SHORTAGE' | 'CLIENT_DELAY' | 'SCOPE_CHANGE' | 'WEATHER' | 'ACCIDENT' | 'OTHER';

export interface Issue {
  id: string;
  organization_id: string;
  issue_number: string;
  code?: string;
  title: string;
  description?: string | null;
  issue_type: IssueType;
  severity: IssueSeverity;
  status: IssueStatus;
  project_id?: string | null;
  work_order_id?: string | null;
  task_id?: string | null;
  reported_by_id?: string | null;
  assigned_to_id?: string | null;
  resolved_by_id?: string | null;
  resolution?: string | null;
  resolution_notes?: string | null;
  resolved_at?: string | null;
  impact_cost: number;
  impact_days: number;
  created_at: string;
  updated_at: string;

  project_name?: string | null;
  work_order_title?: string | null;
  reported_by_name?: string | null;
  assigned_to_name?: string | null;
}

// ==============================================================================
// 7. COMENTÁRIOS E APONTAMENTOS
// ==============================================================================

export interface Comment {
  id: string;
  organization_id: string;
  author_id: string;
  text: string;
  project_id?: string | null;
  work_order_id?: string | null;
  task_id?: string | null;
  issue_id?: string | null;
  author_name?: string | null;
  created_at: string;
  updated_at: string;
}

// ==============================================================================
// 8. PAYLOADS DE CRIAÇÃO E FILTROS
// ==============================================================================

export interface ProjectCreatePayload {
  name: string;
  title?: string;
  code?: string;
  description?: string;
  project_type_id: string;
  priority?: ProjectPriority;
  customer_id?: string;
  contact_id?: string;
  sales_order_id?: string;
  opportunity_id?: string;
  cost_center_id?: string;
  team_id?: string;
  manager_id?: string;
  workflow_template_id?: string;
  workflow_id?: string | null;
  current_stage_id?: string | null;
  start_date?: string;
  target_end_date?: string;
  planned_start_date?: string;
  planned_end_date?: string;
  estimated_budget?: number;
  estimated_hours?: number;
  progress_percent?: number;
  address?: string;
  city?: string;
  state?: string;
  zip_code?: string;
  is_billable?: boolean;
  color?: string;
  tags?: string[];
  notes?: string;
}

export interface WorkOrderCreatePayload {
  title: string;
  code?: string;
  description?: string;
  work_order_type_id: string;
  order_type_id?: string;
  project_id?: string | null;
  priority?: ProjectPriority;
  customer_id?: string;
  contact_id?: string;
  cost_center_id?: string;
  responsible_id?: string;
  team_id?: string;
  start_date?: string;
  due_date?: string;
  scheduled_start?: string;
  scheduled_end?: string;
  address?: string;
  estimated_hours?: number;
  estimated_cost?: number;
  tags?: string[];
  notes?: string;
}

export interface TaskCreatePayload {
  title: string;
  description?: string;
  project_id?: string | null;
  work_order_id?: string | null;
  parent_task_id?: string;
  priority?: ProjectPriority;
  status?: string;
  stage_id?: string;
  start_date?: string;
  due_date?: string;
  estimated_hours?: number;
  position?: number;
  is_milestone?: boolean;
  tags?: string[];
  assigned_user_ids?: string[];
}

export interface IssueCreatePayload {
  title: string;
  description: string;
  issue_type: IssueType;
  severity: IssueSeverity;
  project_id?: string | null;
  work_order_id?: string | null;
  task_id?: string | null;
  assigned_to_id?: string;
  impact_cost?: number;
  impact_days?: number;
}

export interface ProjectsFilterParams {
  status?: ProjectStatus;
  project_type_id?: string;
  customer_id?: string;
  manager_id?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

export interface WorkOrdersFilterParams {
  status?: WorkOrderStatus;
  project_id?: string;
  customer_id?: string;
  responsible_id?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

export interface TasksFilterParams {
  status?: TaskStatus;
  project_id?: string;
  work_order_id?: string;
  assigned_to_id?: string;
  page?: number;
  page_size?: number;
  search?: string;
  limit?: number;
  offset?: number;
}
