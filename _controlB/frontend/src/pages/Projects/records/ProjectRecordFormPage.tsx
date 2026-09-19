import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import {
  Building2,
  CalendarDays,
  ClipboardCheck,
  ClipboardList,
  FolderKanban,
  MapPin,
  Save,
  Trash2,
  Users,
} from 'lucide-react';

import { ConfirmModal } from '@/components/ConfirmModal/ConfirmModal';
import {
  RecordFormGrid,
  RecordFormPage,
  RecordFormSection,
  UnsavedChangesGuard,
  type RecordFormTab,
} from '@/components/RecordForm';
import { useRecordFormNavigation } from '@/hooks/useRecordFormNavigation';
import { useRecordFormTab } from '@/hooks/useRecordFormTab';
import { buildRecordFormPath, isNewRecordSegment } from '@/routing/recordRoutes';
import { formatApiError, identityService, projectsService, salesService } from '@/services/api';
import { useToast } from '@/components/Toast/ToastContext';
import type { Customer, Project, ProjectPriority, ProjectType, Team, User, WorkflowTemplate } from '@/types';

import { emptyToUndefined, serializeForm, statusLabel, toDateInput } from './recordFormUtils';
import { TasksRelationTab } from './TasksRelationTab';
import './OperationalRecordForm.scss';

const PROJECT_TABS = ['general', 'team', 'planning', 'scope', 'tasks'] as const;
type ProjectTab = typeof PROJECT_TABS[number];

interface ProjectFormState {
  name: string;
  project_type_id: string;
  priority: ProjectPriority;
  workflow_id: string;
  current_stage_id: string;
  customer_id: string;
  manager_id: string;
  team_id: string;
  planned_start_date: string;
  planned_end_date: string;
  estimated_budget: number;
  estimated_hours: number;
  progress_percent: number;
  zip_code: string;
  address: string;
  city: string;
  state: string;
  is_billable: boolean;
  description: string;
  notes: string;
}

const EMPTY_FORM: ProjectFormState = {
  name: '',
  project_type_id: '',
  priority: 'MEDIUM',
  workflow_id: '',
  current_stage_id: '',
  customer_id: '',
  manager_id: '',
  team_id: '',
  planned_start_date: '',
  planned_end_date: '',
  estimated_budget: 0,
  estimated_hours: 0,
  progress_percent: 0,
  zip_code: '',
  address: '',
  city: '',
  state: '',
  is_billable: true,
  description: '',
  notes: '',
};

const TABS: RecordFormTab[] = [
  { id: 'general', label: 'Geral', icon: FolderKanban },
  { id: 'team', label: 'Responsáveis', icon: Users },
  { id: 'planning', label: 'Planejamento', icon: CalendarDays },
  { id: 'scope', label: 'Escopo', icon: ClipboardList },
  { id: 'tasks', label: 'Tarefas', icon: ClipboardCheck },
];

const projectToForm = (project: Project): ProjectFormState => ({
  name: project.title || project.name || '',
  project_type_id: project.project_type?.id || '',
  priority: project.priority,
  workflow_id: project.workflow_id || '',
  current_stage_id: project.current_stage_id || project.current_stage?.id || '',
  customer_id: project.customer_id || '',
  manager_id: project.manager_id || '',
  team_id: project.team_id || '',
  planned_start_date: toDateInput(project.planned_start_date),
  planned_end_date: toDateInput(project.planned_end_date),
  estimated_budget: Number(project.estimated_budget || 0),
  estimated_hours: Number(project.estimated_hours || 0),
  progress_percent: Number(project.progress_percent || 0),
  zip_code: project.zip_code || '',
  address: project.address || '',
  city: project.city || '',
  state: project.state || '',
  is_billable: project.is_billable ?? true,
  description: project.description || '',
  notes: project.notes || '',
});

export function ProjectRecordFormPage() {
  const { recordId } = useParams<{ recordId: string }>();
  const isNew = isNewRecordSegment(recordId);
  const location = useLocation();
  const navigate = useNavigate();
  const goBack = useRecordFormNavigation('/projetos?view=projects');
  const toast = useToast();
  const [activeTab, setActiveTab] = useRecordFormTab<ProjectTab>(PROJECT_TABS, 'general');

  const [record, setRecord] = useState<Project | null>(null);
  const [form, setForm] = useState<ProjectFormState>(EMPTY_FORM);
  const [initialForm, setInitialForm] = useState(serializeForm(EMPTY_FORM));
  const [projectTypes, setProjectTypes] = useState<ProjectType[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowTemplate[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [taskCount, setTaskCount] = useState<number | undefined>(undefined);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [typesData, workflowData, customerData, userData, teamData, projectData] = await Promise.all([
        projectsService.getProjectTypes(),
        projectsService.getWorkflowTemplates(),
        salesService.getCustomers().catch(() => []),
        identityService.getUsers().catch(() => []),
        identityService.getTeams().catch(() => []),
        isNew || !recordId ? Promise.resolve(null) : projectsService.getProject(recordId),
      ]);
      setProjectTypes(typesData);
      setWorkflows(workflowData.filter((workflow) => workflow.target_entity === 'PROJECT'));
      setCustomers(customerData);
      setUsers(userData);
      setTeams(teamData);
      setRecord(projectData);
      const availableWorkflows = workflowData.filter((workflow) => workflow.target_entity === 'PROJECT');
      const defaultType = typesData[0];
      const defaultWorkflowId = defaultType?.default_workflow_id || '';
      const defaultWorkflow = availableWorkflows.find((workflow) => workflow.id === defaultWorkflowId);
      const defaultStageId = [...(defaultWorkflow?.stages || [])]
        .sort((left, right) => left.position - right.position)
        .find((stage) => stage.is_initial)?.id || defaultWorkflow?.stages?.[0]?.id || '';
      const nextForm = projectData
        ? projectToForm(projectData)
        : { ...EMPTY_FORM, project_type_id: defaultType?.id || '', workflow_id: defaultWorkflowId, current_stage_id: defaultStageId };
      setForm(nextForm);
      setInitialForm(serializeForm(nextForm));
    } catch (loadError) {
      setError(formatApiError(loadError, 'Não foi possível carregar o projeto'));
    } finally {
      setLoading(false);
    }
  }, [isNew, recordId]);

  useEffect(() => { void load(); }, [load]);

  const dirty = !loading && serializeForm(form) !== initialForm;
  const title = isNew ? 'Novo projeto' : (record?.title || record?.name || 'Projeto');
  const status = useMemo(() => statusLabel(record?.status), [record?.status]);
  const workflowStages = useMemo(() => [...(workflows.find((workflow) => workflow.id === form.workflow_id)?.stages || [])].sort((left, right) => left.position - right.position), [form.workflow_id, workflows]);

  const selectWorkflow = (workflowId: string) => {
    const stages = [...(workflows.find((workflow) => workflow.id === workflowId)?.stages || [])].sort((left, right) => left.position - right.position);
    const initialStageId = stages.find((stage) => stage.is_initial)?.id || stages[0]?.id || '';
    setForm((current) => ({ ...current, workflow_id: workflowId, current_stage_id: initialStageId }));
  };

  const selectProjectType = (projectTypeId: string) => {
    const defaultWorkflowId = projectTypes.find((type) => type.id === projectTypeId)?.default_workflow_id || form.workflow_id;
    const stages = [...(workflows.find((workflow) => workflow.id === defaultWorkflowId)?.stages || [])].sort((left, right) => left.position - right.position);
    const initialStageId = stages.find((stage) => stage.is_initial)?.id || stages[0]?.id || '';
    setForm((current) => ({ ...current, project_type_id: projectTypeId, workflow_id: defaultWorkflowId, current_stage_id: initialStageId }));
  };

  const save = async () => {
    if (!form.name.trim() || !form.project_type_id) {
      setActiveTab('general');
      toast.error('Informe o nome e o tipo do projeto.');
      return;
    }
    setSaving(true);
    try {
      const payload = {
        name: form.name.trim(),
        title: form.name.trim(),
        project_type_id: form.project_type_id,
        priority: form.priority,
        workflow_id: form.workflow_id || null,
        current_stage_id: form.current_stage_id || null,
        customer_id: emptyToUndefined(form.customer_id),
        manager_id: emptyToUndefined(form.manager_id),
        team_id: emptyToUndefined(form.team_id),
        planned_start_date: emptyToUndefined(form.planned_start_date),
        planned_end_date: emptyToUndefined(form.planned_end_date),
        estimated_budget: Number(form.estimated_budget) || 0,
        estimated_hours: Number(form.estimated_hours) || 0,
        progress_percent: Number(form.progress_percent) || 0,
        zip_code: emptyToUndefined(form.zip_code),
        address: emptyToUndefined(form.address),
        city: emptyToUndefined(form.city),
        state: emptyToUndefined(form.state),
        is_billable: form.is_billable,
        description: emptyToUndefined(form.description),
        notes: emptyToUndefined(form.notes),
      };
      const saved = isNew || !recordId
        ? await projectsService.createProject(payload)
        : await projectsService.updateProject(recordId, payload);
      const nextForm = projectToForm(saved);
      setRecord(saved);
      setForm(nextForm);
      setInitialForm(serializeForm(nextForm));
      toast.success(isNew ? 'Projeto criado com sucesso.' : 'Projeto atualizado com sucesso.');
      if (isNew) {
        navigate(buildRecordFormPath('projetos', 'projetos', saved.id), {
          replace: true,
          state: location.state,
        });
      }
    } catch (saveError) {
      toast.error(formatApiError(saveError, 'Não foi possível salvar o projeto'));
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!recordId || isNew) return;
    setDeleting(true);
    try {
      await projectsService.deleteProject(recordId);
      toast.success('Projeto excluído com sucesso.');
      navigate('/projetos?view=projects', { replace: true });
    } catch (deleteError) {
      toast.error(formatApiError(deleteError, 'Não foi possível excluir o projeto'));
      setDeleting(false);
      setDeleteOpen(false);
    }
  };

  const footer = (
    <>
      <span className={`record-form-footer-message${dirty ? ' is-dirty' : ''}`}>
        {dirty ? 'Existem alterações não salvas.' : 'Todas as alterações estão salvas.'}
      </span>
      <button type="button" className="ui-button ui-button--secondary" onClick={goBack} disabled={saving || deleting}>
        Cancelar
      </button>
      <button type="button" className="ui-button ui-button--primary" onClick={() => void save()} disabled={saving || deleting || !dirty}>
        <Save size={16} /> {saving ? 'Salvando...' : 'Salvar'}
      </button>
    </>
  );

  return (
    <div className="operational-record-form">
      <RecordFormPage
        title={title}
        eyebrow="Projetos operacionais"
        description="Dados gerais, responsáveis, planejamento e escopo do projeto."
        recordCode={record?.code || record?.project_number}
        icon={FolderKanban}
        status={<span className="record-status-pill">{status}</span>}
        breadcrumbs={[{ label: 'Projetos', to: '/projetos?view=projects' }, { label: isNew ? 'Novo' : title }]}
        actions={!isNew ? (
          <button type="button" className="ui-button ui-button--danger" onClick={() => setDeleteOpen(true)} disabled={saving || deleting}>
            <Trash2 size={15} /> Excluir
          </button>
        ) : undefined}
        tabs={TABS.map((tab) => tab.id === 'tasks' ? { ...tab, badge: isNew ? undefined : taskCount, disabled: isNew } : tab)}
        activeTab={activeTab}
        onTabChange={(tab) => setActiveTab(tab as ProjectTab)}
        onBack={goBack}
        isLoading={loading}
        error={error}
        onRetry={() => void load()}
        footer={footer}
      >
        {activeTab === 'general' && (
          <RecordFormSection title="Identificação" description="Como o projeto será reconhecido e conduzido." icon={FolderKanban}>
            <div className="ui-form">
              <RecordFormGrid columns={3}>
                <div className="form-group is-full-width">
                  <label>Nome do projeto *</label>
                  <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="Ex.: Instalação fotovoltaica — Unidade Salvador" />
                </div>
                <div className="form-group">
                  <label>Tipo de projeto *</label>
                  <select value={form.project_type_id} onChange={(event) => selectProjectType(event.target.value)}>
                    <option value="">Selecione...</option>
                    {projectTypes.map((type) => <option key={type.id} value={type.id}>{type.name}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label>Prioridade</label>
                  <select value={form.priority} onChange={(event) => setForm({ ...form, priority: event.target.value as ProjectPriority })}>
                    <option value="LOW">Baixa</option><option value="MEDIUM">Média</option><option value="HIGH">Alta</option><option value="CRITICAL">Crítica</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Workflow</label>
                  <select value={form.workflow_id} onChange={(event) => selectWorkflow(event.target.value)}>
                    <option value="">Fluxo padrão</option>
                    {workflows.map((workflow) => <option key={workflow.id} value={workflow.id}>{workflow.name}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label>Estágio atual *</label>
                  <select value={form.current_stage_id} onChange={(event) => setForm({ ...form, current_stage_id: event.target.value })} disabled={!form.workflow_id || workflowStages.length === 0}>
                    <option value="">{form.workflow_id ? 'Workflow sem estágios' : 'Selecione um workflow'}</option>
                    {workflowStages.map((stage) => <option key={stage.id} value={stage.id}>{stage.name}{stage.is_initial ? ' (inicial)' : ''}{stage.is_terminal ? ' (final)' : ''}</option>)}
                  </select>
                </div>
              </RecordFormGrid>
            </div>
          </RecordFormSection>
        )}

        {activeTab === 'team' && (
          <RecordFormSection title="Cliente e responsáveis" description="Pessoas e equipes envolvidas na execução." icon={Building2}>
            <div className="ui-form">
              <RecordFormGrid columns={3}>
                <div className="form-group"><label>Cliente</label><select value={form.customer_id} onChange={(event) => setForm({ ...form, customer_id: event.target.value })}><option value="">Projeto interno</option>{customers.map((customer) => <option key={customer.id} value={customer.id}>{customer.trade_name || customer.name}</option>)}</select></div>
                <div className="form-group"><label>Gerente do projeto</label><select value={form.manager_id} onChange={(event) => setForm({ ...form, manager_id: event.target.value })}><option value="">Selecione...</option>{users.map((user) => <option key={user.id} value={user.id}>{user.full_name || user.email}</option>)}</select></div>
                <div className="form-group"><label>Equipe executora</label><select value={form.team_id} onChange={(event) => setForm({ ...form, team_id: event.target.value })}><option value="">Selecione...</option>{teams.map((team) => <option key={team.id} value={team.id}>{team.name}</option>)}</select></div>
              </RecordFormGrid>
            </div>
          </RecordFormSection>
        )}

        {activeTab === 'planning' && (
          <>
            <RecordFormSection title="Local de execução" description="Endereço operacional do projeto." icon={MapPin}>
              <div className="ui-form"><RecordFormGrid columns={4}>
                <div className="form-group"><label>CEP</label><input value={form.zip_code} onChange={(event) => setForm({ ...form, zip_code: event.target.value })} placeholder="00000-000" /></div>
                <div className="form-group is-full-width"><label>Endereço</label><input value={form.address} onChange={(event) => setForm({ ...form, address: event.target.value })} /></div>
                <div className="form-group"><label>Cidade</label><input value={form.city} onChange={(event) => setForm({ ...form, city: event.target.value })} /></div>
                <div className="form-group"><label>UF</label><input maxLength={2} value={form.state} onChange={(event) => setForm({ ...form, state: event.target.value.toUpperCase() })} /></div>
              </RecordFormGrid></div>
            </RecordFormSection>
            <RecordFormSection title="Prazos e orçamento" description="Metas previstas para a execução." icon={CalendarDays}>
              <div className="ui-form"><RecordFormGrid columns={4}>
                <div className="form-group"><label>Início previsto</label><input type="date" value={form.planned_start_date} onChange={(event) => setForm({ ...form, planned_start_date: event.target.value })} /></div>
                <div className="form-group"><label>Término previsto</label><input type="date" value={form.planned_end_date} onChange={(event) => setForm({ ...form, planned_end_date: event.target.value })} /></div>
                <div className="form-group"><label>Orçamento previsto (R$)</label><input type="number" min="0" step="0.01" value={form.estimated_budget || ''} onChange={(event) => setForm({ ...form, estimated_budget: Number(event.target.value) })} /></div>
                <div className="form-group"><label>Horas estimadas</label><input type="number" min="0" step="0.5" value={form.estimated_hours || ''} onChange={(event) => setForm({ ...form, estimated_hours: Number(event.target.value) })} /></div>
                <div className="form-group is-full-width"><label>Avanço físico</label><div className="record-form-range"><input type="range" min="0" max="100" value={form.progress_percent} onChange={(event) => setForm({ ...form, progress_percent: Number(event.target.value) })} /><strong>{form.progress_percent}%</strong></div></div>
                <label className="record-form-checkbox is-full-width"><input type="checkbox" checked={form.is_billable} onChange={(event) => setForm({ ...form, is_billable: event.target.checked })} /> Projeto faturável para o cliente</label>
              </RecordFormGrid></div>
            </RecordFormSection>
          </>
        )}

        {activeTab === 'scope' && (
          <RecordFormSection title="Escopo e especificações" description="Entregáveis, requisitos e observações de execução." icon={ClipboardList}>
            <div className="ui-form"><RecordFormGrid columns={1}>
              <div className="form-group"><label>Descrição do escopo</label><textarea rows={7} value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></div>
              <div className="form-group"><label>Observações e requisitos especiais</label><textarea rows={5} value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} /></div>
            </RecordFormGrid></div>
          </RecordFormSection>
        )}

        {activeTab === 'tasks' && !isNew && (
          <TasksRelationTab context="project" recordId={recordId} onCountChange={setTaskCount} />
        )}
      </RecordFormPage>

      <UnsavedChangesGuard when={dirty && !saving && !deleting} />
      <ConfirmModal isOpen={deleteOpen} onClose={() => setDeleteOpen(false)} onConfirm={remove} title="Excluir projeto" message={<>Deseja excluir definitivamente <strong>{title}</strong>?</>} confirmText="Excluir projeto" type="danger" isLoading={deleting} />
    </div>
  );
}
