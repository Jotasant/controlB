import { useCallback, useEffect, useState } from 'react';
import { useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { AlertTriangle, CircleDollarSign, Link2, Save, Trash2, UserRound } from 'lucide-react';

import { ConfirmModal } from '@/components/ConfirmModal/ConfirmModal';
import { RecordFormGrid, RecordFormPage, RecordFormSection, UnsavedChangesGuard, type RecordFormTab } from '@/components/RecordForm';
import { useToast } from '@/components/Toast/ToastContext';
import { useRecordFormNavigation } from '@/hooks/useRecordFormNavigation';
import { useRecordFormTab } from '@/hooks/useRecordFormTab';
import { buildRecordFormPath, isNewRecordSegment } from '@/routing/recordRoutes';
import { formatApiError, identityService, projectsService } from '@/services/api';
import type { Issue, IssueSeverity, IssueType, Project, Task, User, WorkOrder } from '@/types';

import { emptyToUndefined, serializeForm, statusLabel } from './recordFormUtils';
import './OperationalRecordForm.scss';

const TABS = ['general', 'impact'] as const;
type FormTab = typeof TABS[number];
const TAB_ITEMS: RecordFormTab[] = [
  { id: 'general', label: 'Geral', icon: AlertTriangle },
  { id: 'impact', label: 'Impacto e tratamento', icon: CircleDollarSign },
];

interface FormState {
  title: string;
  description: string;
  issue_type: IssueType;
  severity: IssueSeverity;
  project_id: string;
  work_order_id: string;
  task_id: string;
  assigned_to_id: string;
  impact_cost: number;
  impact_days: number;
}

const emptyForm = (projectId = '', workOrderId = '', taskId = ''): FormState => ({
  title: '', description: '', issue_type: 'BLOCKER', severity: 'MEDIUM',
  project_id: projectId, work_order_id: workOrderId, task_id: taskId,
  assigned_to_id: '', impact_cost: 0, impact_days: 0,
});

const recordToForm = (record: Issue): FormState => ({
  title: record.title || '', description: record.description || '', issue_type: record.issue_type,
  severity: record.severity, project_id: record.project_id || '', work_order_id: record.work_order_id || '',
  task_id: record.task_id || '', assigned_to_id: record.assigned_to_id || '',
  impact_cost: Number(record.impact_cost || 0), impact_days: Number(record.impact_days || 0),
});

export function IssueRecordFormPage() {
  const { recordId } = useParams<{ recordId: string }>();
  const [searchParams] = useSearchParams();
  const linkedProjectId = searchParams.get('projectId') || '';
  const linkedWorkOrderId = searchParams.get('workOrderId') || '';
  const linkedTaskId = searchParams.get('taskId') || '';
  const isNew = isNewRecordSegment(recordId);
  const location = useLocation();
  const navigate = useNavigate();
  const goBack = useRecordFormNavigation('/projetos?view=issues');
  const toast = useToast();
  const [activeTab, setActiveTab] = useRecordFormTab<FormTab>(TABS, 'general');
  const initialEmpty = emptyForm(linkedProjectId, linkedWorkOrderId, linkedTaskId);

  const [record, setRecord] = useState<Issue | null>(null);
  const [form, setForm] = useState<FormState>(initialEmpty);
  const [initialForm, setInitialForm] = useState(serializeForm(initialEmpty));
  const [projects, setProjects] = useState<Project[]>([]);
  const [workOrders, setWorkOrders] = useState<WorkOrder[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [projectData, orderData, taskData, userData, issue] = await Promise.all([
        projectsService.getProjects(), projectsService.getWorkOrders(), projectsService.getTasks(),
        identityService.getUsers().catch(() => []),
        isNew || !recordId ? Promise.resolve(null) : projectsService.getIssue(recordId),
      ]);
      setProjects(projectData); setWorkOrders(orderData); setTasks(taskData); setUsers(userData); setRecord(issue);
      const next = issue ? recordToForm(issue) : emptyForm(linkedProjectId, linkedWorkOrderId, linkedTaskId);
      setForm(next); setInitialForm(serializeForm(next));
    } catch (loadError) { setError(formatApiError(loadError, 'Não foi possível carregar a ocorrência')); }
    finally { setLoading(false); }
  }, [isNew, linkedProjectId, linkedTaskId, linkedWorkOrderId, recordId]);

  useEffect(() => { void load(); }, [load]);
  const dirty = !loading && serializeForm(form) !== initialForm;
  const title = isNew ? 'Nova ocorrência' : (record?.title || 'Ocorrência');

  const save = async () => {
    if (!form.title.trim() || !form.description.trim()) {
      setActiveTab('general'); toast.error('Informe o título e a descrição da ocorrência.'); return;
    }
    setSaving(true);
    try {
      const payload = {
        title: form.title.trim(), description: form.description.trim(), issue_type: form.issue_type,
        severity: form.severity, project_id: form.project_id || null, work_order_id: form.work_order_id || null,
        task_id: form.task_id || null, assigned_to_id: emptyToUndefined(form.assigned_to_id),
        impact_cost: Number(form.impact_cost) || 0, impact_days: Number(form.impact_days) || 0,
      };
      const saved = isNew || !recordId
        ? await projectsService.createIssue(payload)
        : await projectsService.updateIssue(recordId, payload);
      const next = recordToForm(saved); setRecord(saved); setForm(next); setInitialForm(serializeForm(next));
      toast.success(isNew ? 'Ocorrência registrada com sucesso.' : 'Ocorrência atualizada com sucesso.');
      if (isNew) navigate(buildRecordFormPath('projetos', 'ocorrencias', saved.id), { replace: true, state: location.state });
    } catch (saveError) { toast.error(formatApiError(saveError, 'Não foi possível salvar a ocorrência')); }
    finally { setSaving(false); }
  };

  const remove = async () => {
    if (!recordId || isNew) return;
    setDeleting(true);
    try { await projectsService.deleteIssue(recordId); toast.success('Ocorrência excluída com sucesso.'); navigate('/projetos?view=issues', { replace: true }); }
    catch (deleteError) { toast.error(formatApiError(deleteError, 'Não foi possível excluir a ocorrência')); setDeleting(false); setDeleteOpen(false); }
  };

  return <div className="operational-record-form">
    <RecordFormPage title={title} eyebrow="Gestão de ocorrências" description="Registro, vínculo, responsável e impacto operacional."
      recordCode={record?.issue_number || record?.code} icon={AlertTriangle}
      status={<span className="record-status-pill">{statusLabel(record?.status)}</span>}
      breadcrumbs={[{ label: 'Ocorrências', to: '/projetos?view=issues' }, { label: isNew ? 'Nova' : title }]}
      actions={!isNew ? <button type="button" className="ui-button ui-button--danger" onClick={() => setDeleteOpen(true)}><Trash2 size={15} /> Excluir</button> : undefined}
      tabs={TAB_ITEMS} activeTab={activeTab} onTabChange={(tab) => setActiveTab(tab as FormTab)} onBack={goBack}
      isLoading={loading} error={error} onRetry={() => void load()}
      footer={<><span className={`record-form-footer-message${dirty ? ' is-dirty' : ''}`}>{dirty ? 'Existem alterações não salvas.' : 'Todas as alterações estão salvas.'}</span><button type="button" className="ui-button ui-button--secondary" onClick={goBack} disabled={saving || deleting}>Cancelar</button><button type="button" className="ui-button ui-button--primary" onClick={() => void save()} disabled={saving || deleting || !dirty}><Save size={16} /> {saving ? 'Salvando...' : 'Salvar'}</button></>}
    >
      {activeTab === 'general' && <><RecordFormSection title="Identificação" description="Classifique e descreva objetivamente o problema." icon={AlertTriangle}><div className="ui-form"><RecordFormGrid columns={2}>
        <div className="form-group is-full-width"><label>Título da ocorrência *</label><input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} /></div>
        <div className="form-group"><label>Tipo</label><select value={form.issue_type} onChange={(event) => setForm({ ...form, issue_type: event.target.value as IssueType })}><option value="BUG">Falha</option><option value="BLOCKER">Bloqueio</option><option value="MATERIAL_SHORTAGE">Falta de material</option><option value="CLIENT_DELAY">Atraso do cliente</option><option value="SCOPE_CHANGE">Mudança de escopo</option><option value="WEATHER">Clima</option><option value="ACCIDENT">Acidente</option><option value="OTHER">Outro</option></select></div>
        <div className="form-group"><label>Severidade</label><select value={form.severity} onChange={(event) => setForm({ ...form, severity: event.target.value as IssueSeverity })}><option value="LOW">Baixa</option><option value="MEDIUM">Média</option><option value="HIGH">Alta</option><option value="CRITICAL">Crítica</option></select></div>
        <div className="form-group is-full-width"><label>Descrição *</label><textarea rows={7} value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></div>
      </RecordFormGrid></div></RecordFormSection><RecordFormSection title="Vínculos" description="Contexto em que a ocorrência foi identificada." icon={Link2}><div className="ui-form"><RecordFormGrid columns={3}>
        <div className="form-group"><label>Projeto</label><select value={form.project_id} onChange={(event) => setForm({ ...form, project_id: event.target.value })}><option value="">Nenhum</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.code} — {project.name}</option>)}</select></div>
        <div className="form-group"><label>Ordem de trabalho</label><select value={form.work_order_id} onChange={(event) => setForm({ ...form, work_order_id: event.target.value })}><option value="">Nenhuma</option>{workOrders.map((order) => <option key={order.id} value={order.id}>{order.order_number || order.code} — {order.title}</option>)}</select></div>
        <div className="form-group"><label>Tarefa</label><select value={form.task_id} onChange={(event) => setForm({ ...form, task_id: event.target.value })}><option value="">Nenhuma</option>{tasks.map((task) => <option key={task.id} value={task.id}>{task.title}</option>)}</select></div>
      </RecordFormGrid></div></RecordFormSection></>}
      {activeTab === 'impact' && <><RecordFormSection title="Responsável pelo tratamento" description="Pessoa que acompanhará a ocorrência." icon={UserRound}><div className="ui-form"><RecordFormGrid columns={2}><div className="form-group"><label>Responsável</label><select value={form.assigned_to_id} onChange={(event) => setForm({ ...form, assigned_to_id: event.target.value })}><option value="">Não atribuído</option>{users.map((user) => <option key={user.id} value={user.id}>{user.full_name || user.email}</option>)}</select></div></RecordFormGrid></div></RecordFormSection><RecordFormSection title="Impacto previsto" description="Efeito estimado no custo e no cronograma." icon={CircleDollarSign}><div className="ui-form"><RecordFormGrid columns={2}>
        <div className="form-group"><label>Impacto financeiro (R$)</label><input type="number" min="0" step="0.01" value={form.impact_cost || ''} onChange={(event) => setForm({ ...form, impact_cost: Number(event.target.value) })} /></div>
        <div className="form-group"><label>Impacto no prazo (dias)</label><input type="number" min="0" step="1" value={form.impact_days || ''} onChange={(event) => setForm({ ...form, impact_days: Number(event.target.value) })} /></div>
      </RecordFormGrid></div></RecordFormSection></>}
    </RecordFormPage>
    <UnsavedChangesGuard when={dirty && !saving && !deleting} />
    <ConfirmModal isOpen={deleteOpen} onClose={() => setDeleteOpen(false)} onConfirm={remove} title="Excluir ocorrência" message={<>Deseja excluir <strong>{title}</strong>?</>} confirmText="Excluir ocorrência" type="danger" isLoading={deleting} />
  </div>;
}
