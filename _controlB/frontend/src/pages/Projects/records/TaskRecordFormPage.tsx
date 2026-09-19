import { useCallback, useEffect, useState } from 'react';
import { useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { CalendarDays, ClipboardCheck, Link2, Save, Trash2, Users } from 'lucide-react';

import { ConfirmModal } from '@/components/ConfirmModal/ConfirmModal';
import { RecordFormGrid, RecordFormPage, RecordFormSection, UnsavedChangesGuard, type RecordFormTab } from '@/components/RecordForm';
import { useToast } from '@/components/Toast/ToastContext';
import { useRecordFormNavigation } from '@/hooks/useRecordFormNavigation';
import { useRecordFormTab } from '@/hooks/useRecordFormTab';
import { buildRecordFormPath, isNewRecordSegment } from '@/routing/recordRoutes';
import { formatApiError, identityService, projectsService } from '@/services/api';
import type { Project, ProjectPriority, Task, User, WorkOrder } from '@/types';

import { emptyToUndefined, serializeForm, statusLabel, toDateInput } from './recordFormUtils';
import './OperationalRecordForm.scss';

const TABS = ['general', 'planning', 'details'] as const;
type FormTab = typeof TABS[number];

const TAB_ITEMS: RecordFormTab[] = [
  { id: 'general', label: 'Geral', icon: ClipboardCheck },
  { id: 'planning', label: 'Planejamento', icon: CalendarDays },
  { id: 'details', label: 'Detalhes', icon: Users },
];

interface FormState {
  title: string;
  project_id: string;
  work_order_id: string;
  priority: ProjectPriority;
  status: string;
  due_date: string;
  estimated_hours: number;
  assigned_user_ids: string[];
  description: string;
}

const emptyForm = (projectId = '', workOrderId = ''): FormState => ({
  title: '', project_id: workOrderId ? '' : projectId, work_order_id: workOrderId,
  priority: 'MEDIUM', due_date: '', estimated_hours: 0,
  status: 'todo',
  assigned_user_ids: [], description: '',
});

const recordToForm = (record: Task): FormState => ({
  title: record.title || '',
  project_id: record.work_order_id ? '' : (record.project_id || ''),
  work_order_id: record.work_order_id || '',
  priority: record.priority,
  status: String(record.status || 'todo').toLowerCase() === 'review' ? 'in_review' : String(record.status || 'todo').toLowerCase(),
  due_date: toDateInput(record.due_date),
  estimated_hours: Number(record.estimated_hours || 0),
  assigned_user_ids: record.assignments?.map((assignment) => assignment.user_id) || [],
  description: record.description || '',
});

export function TaskRecordFormPage() {
  const { recordId } = useParams<{ recordId: string }>();
  const [searchParams] = useSearchParams();
  const linkedProjectId = searchParams.get('projectId') || '';
  const linkedWorkOrderId = searchParams.get('workOrderId') || '';
  const isNew = isNewRecordSegment(recordId);
  const location = useLocation();
  const navigate = useNavigate();
  const goBack = useRecordFormNavigation('/projetos?view=tasks');
  const toast = useToast();
  const [activeTab, setActiveTab] = useRecordFormTab<FormTab>(TABS, 'general');
  const initialEmpty = emptyForm(linkedProjectId, linkedWorkOrderId);

  const [record, setRecord] = useState<Task | null>(null);
  const [form, setForm] = useState<FormState>(initialEmpty);
  const [initialForm, setInitialForm] = useState(serializeForm(initialEmpty));
  const [projects, setProjects] = useState<Project[]>([]);
  const [workOrders, setWorkOrders] = useState<WorkOrder[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [projectData, workOrderData, userData, task] = await Promise.all([
        projectsService.getProjects(), projectsService.getWorkOrders(),
        identityService.getUsers().catch(() => []),
        isNew || !recordId ? Promise.resolve(null) : projectsService.getTask(recordId),
      ]);
      setProjects(projectData); setWorkOrders(workOrderData); setUsers(userData); setRecord(task);
      const next = task ? recordToForm(task) : emptyForm(linkedProjectId, linkedWorkOrderId);
      setForm(next); setInitialForm(serializeForm(next));
    } catch (loadError) {
      setError(formatApiError(loadError, 'Não foi possível carregar a tarefa'));
    } finally { setLoading(false); }
  }, [isNew, linkedProjectId, linkedWorkOrderId, recordId]);

  useEffect(() => { void load(); }, [load]);
  const dirty = !loading && serializeForm(form) !== initialForm;
  const title = isNew ? 'Nova tarefa' : (record?.title || 'Tarefa');

  const save = async () => {
    if (!form.title.trim()) { setActiveTab('general'); toast.error('Informe o título da tarefa.'); return; }
    if (!form.project_id && !form.work_order_id) {
      setActiveTab('general'); toast.error('Vincule a tarefa a um projeto ou a uma ordem de trabalho.'); return;
    }
    setSaving(true);
    try {
      const payload = {
        title: form.title.trim(), project_id: form.project_id || null,
        work_order_id: form.work_order_id || null, priority: form.priority,
        status: form.status,
        due_date: emptyToUndefined(form.due_date), estimated_hours: Number(form.estimated_hours) || 0,
        assigned_user_ids: form.assigned_user_ids, description: emptyToUndefined(form.description),
      };
      const saved = isNew || !recordId
        ? await projectsService.createTask(payload)
        : await projectsService.updateTask(recordId, payload);
      const next = recordToForm(saved); setRecord(saved); setForm(next); setInitialForm(serializeForm(next));
      toast.success(isNew ? 'Tarefa criada com sucesso.' : 'Tarefa atualizada com sucesso.');
      if (isNew) navigate(buildRecordFormPath('projetos', 'tarefas', saved.id), { replace: true, state: location.state });
    } catch (saveError) { toast.error(formatApiError(saveError, 'Não foi possível salvar a tarefa')); }
    finally { setSaving(false); }
  };

  const remove = async () => {
    if (!recordId || isNew) return;
    setDeleting(true);
    try { await projectsService.deleteTask(recordId); toast.success('Tarefa excluída com sucesso.'); goBack(); }
    catch (deleteError) { toast.error(formatApiError(deleteError, 'Não foi possível excluir a tarefa')); setDeleting(false); setDeleteOpen(false); }
  };

  const toggleAssignee = (userId: string) => setForm((current) => ({
    ...current,
    assigned_user_ids: current.assigned_user_ids.includes(userId)
      ? current.assigned_user_ids.filter((id) => id !== userId)
      : [...current.assigned_user_ids, userId],
  }));

  return <div className="operational-record-form">
    <RecordFormPage title={title} eyebrow="Execução operacional" description="Vínculo, prazo, esforço e responsáveis da tarefa."
      icon={ClipboardCheck} status={<span className="record-status-pill">{statusLabel(isNew ? form.status : record?.status)}</span>}
      breadcrumbs={[{ label: 'Tarefas', to: '/projetos?view=tasks' }, { label: isNew ? 'Nova' : title }]}
      actions={!isNew ? <button type="button" className="ui-button ui-button--danger" onClick={() => setDeleteOpen(true)}><Trash2 size={15} /> Excluir</button> : undefined}
      tabs={TAB_ITEMS} activeTab={activeTab} onTabChange={(tab) => setActiveTab(tab as FormTab)} onBack={goBack}
      isLoading={loading} error={error} onRetry={() => void load()}
      footer={<><span className={`record-form-footer-message${dirty ? ' is-dirty' : ''}`}>{dirty ? 'Existem alterações não salvas.' : 'Todas as alterações estão salvas.'}</span><button type="button" className="ui-button ui-button--secondary" onClick={goBack} disabled={saving || deleting}>Cancelar</button><button type="button" className="ui-button ui-button--primary" onClick={() => void save()} disabled={saving || deleting || !dirty}><Save size={16} /> {saving ? 'Salvando...' : 'Salvar'}</button></>}
    >
      {activeTab === 'general' && <RecordFormSection title="Identificação e vínculo" description="Toda tarefa pertence a um projeto ou a uma ordem de trabalho." icon={Link2}><div className="ui-form"><RecordFormGrid columns={2}>
        <div className="form-group is-full-width"><label>Título da tarefa *</label><input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} /></div>
        <div className="form-group"><label>Projeto</label><select value={form.project_id} onChange={(event) => setForm({ ...form, project_id: event.target.value, work_order_id: event.target.value ? '' : form.work_order_id })}><option value="">Não vincular diretamente</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.code} — {project.name}</option>)}</select></div>
        <div className="form-group"><label>Ordem de trabalho</label><select value={form.work_order_id} onChange={(event) => setForm({ ...form, work_order_id: event.target.value, project_id: event.target.value ? '' : form.project_id })}><option value="">Não vincular diretamente</option>{workOrders.map((order) => <option key={order.id} value={order.id}>{order.order_number || order.code} — {order.title}</option>)}</select></div>
        <div className="form-group"><label>Etapa do Kanban *</label><select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}><option value="todo">A fazer</option><option value="in_progress">Em execução</option><option value="in_review">Revisão / inspeção</option><option value="blocked">Impedida / bloqueada</option><option value="done">Concluída</option>{!isNew && <option value="cancelled">Cancelada</option>}</select></div>
        <div className="record-form-notice is-full-width"><Link2 size={16} /><span>Os vínculos são alternativos: ao selecionar uma ordem, o projeto direto é limpo — e vice-versa.</span></div>
      </RecordFormGrid></div></RecordFormSection>}
      {activeTab === 'planning' && <RecordFormSection title="Planejamento" description="Prioridade, prazo e esforço esperado." icon={CalendarDays}><div className="ui-form"><RecordFormGrid columns={3}>
        <div className="form-group"><label>Prioridade</label><select value={form.priority} onChange={(event) => setForm({ ...form, priority: event.target.value as ProjectPriority })}><option value="LOW">Baixa</option><option value="MEDIUM">Média</option><option value="HIGH">Alta</option><option value="CRITICAL">Crítica</option></select></div>
        <div className="form-group"><label>Prazo</label><input type="date" value={form.due_date} onChange={(event) => setForm({ ...form, due_date: event.target.value })} /></div>
        <div className="form-group"><label>Horas estimadas</label><input type="number" min="0" step="0.5" value={form.estimated_hours || ''} onChange={(event) => setForm({ ...form, estimated_hours: Number(event.target.value) })} /></div>
      </RecordFormGrid></div></RecordFormSection>}
      {activeTab === 'details' && <><RecordFormSection title="Responsáveis" description="Selecione uma ou mais pessoas para executar a tarefa." icon={Users}>
        <div className="record-form-choice-grid">{users.length === 0 ? <span className="record-form-empty">Nenhum colaborador disponível.</span> : users.map((user) => <label className="record-form-choice" key={user.id}><input type="checkbox" checked={form.assigned_user_ids.includes(user.id)} onChange={() => toggleAssignee(user.id)} /><span><strong>{user.full_name || user.email}</strong><small>{user.email}</small></span></label>)}</div>
      </RecordFormSection><RecordFormSection title="Descrição" description="Contexto e critérios para conclusão." icon={ClipboardCheck}><div className="ui-form"><div className="form-group"><label>Descrição detalhada</label><textarea rows={8} value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></div></div></RecordFormSection></>}
    </RecordFormPage>
    <UnsavedChangesGuard when={dirty && !saving && !deleting} />
    <ConfirmModal isOpen={deleteOpen} onClose={() => setDeleteOpen(false)} onConfirm={remove} title="Excluir tarefa" message={<>Deseja excluir <strong>{title}</strong>?</>} confirmText="Excluir tarefa" type="danger" isLoading={deleting} />
  </div>;
}
