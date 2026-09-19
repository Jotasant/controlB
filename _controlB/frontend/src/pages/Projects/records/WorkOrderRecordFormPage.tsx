import { useCallback, useEffect, useState } from 'react';
import { useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { CalendarClock, ClipboardCheck, ClipboardList, MapPin, Save, Trash2, Users, Wrench } from 'lucide-react';

import { ConfirmModal } from '@/components/ConfirmModal/ConfirmModal';
import { RecordFormGrid, RecordFormPage, RecordFormSection, UnsavedChangesGuard, type RecordFormTab } from '@/components/RecordForm';
import { useRecordFormNavigation } from '@/hooks/useRecordFormNavigation';
import { useRecordFormTab } from '@/hooks/useRecordFormTab';
import { buildRecordFormPath, isNewRecordSegment } from '@/routing/recordRoutes';
import { formatApiError, identityService, projectsService } from '@/services/api';
import { useToast } from '@/components/Toast/ToastContext';
import type { Project, ProjectPriority, Team, User, WorkOrder, WorkOrderType } from '@/types';

import { emptyToUndefined, serializeForm, statusLabel, toDateTimeInput } from './recordFormUtils';
import { TasksRelationTab } from './TasksRelationTab';
import './OperationalRecordForm.scss';

const TABS = ['general', 'execution', 'instructions', 'tasks'] as const;
type FormTab = typeof TABS[number];

const TAB_ITEMS: RecordFormTab[] = [
  { id: 'general', label: 'Geral', icon: ClipboardList },
  { id: 'execution', label: 'Execução', icon: CalendarClock },
  { id: 'instructions', label: 'Instruções', icon: Wrench },
  { id: 'tasks', label: 'Tarefas', icon: ClipboardCheck },
];

interface FormState {
  title: string;
  work_order_type_id: string;
  project_id: string;
  priority: ProjectPriority;
  responsible_id: string;
  team_id: string;
  scheduled_start: string;
  scheduled_end: string;
  address: string;
  estimated_hours: number;
  estimated_cost: number;
  notes: string;
  description: string;
}

const emptyForm = (projectId = ''): FormState => ({
  title: '', work_order_type_id: '', project_id: projectId, priority: 'MEDIUM',
  responsible_id: '', team_id: '', scheduled_start: '', scheduled_end: '', address: '',
  estimated_hours: 0, estimated_cost: 0, notes: '', description: '',
});

const recordToForm = (record: WorkOrder): FormState => ({
  title: record.title || '',
  work_order_type_id: record.order_type?.id || record.order_type_id || '',
  project_id: record.project_id || '',
  priority: record.priority,
  responsible_id: record.responsible_id || '',
  team_id: record.team_id || '',
  scheduled_start: toDateTimeInput(record.scheduled_start),
  scheduled_end: toDateTimeInput(record.scheduled_end),
  address: record.address || '',
  estimated_hours: Number(record.estimated_hours || 0),
  estimated_cost: Number(record.estimated_cost || 0),
  notes: record.notes || '',
  description: record.description || '',
});

export function WorkOrderRecordFormPage() {
  const { recordId } = useParams<{ recordId: string }>();
  const [searchParams] = useSearchParams();
  const linkedProjectId = searchParams.get('projectId') || '';
  const isNew = isNewRecordSegment(recordId);
  const location = useLocation();
  const navigate = useNavigate();
  const goBack = useRecordFormNavigation('/projetos?view=work_orders');
  const toast = useToast();
  const [activeTab, setActiveTab] = useRecordFormTab<FormTab>(TABS, 'general');
  const initialEmpty = emptyForm(linkedProjectId);

  const [record, setRecord] = useState<WorkOrder | null>(null);
  const [form, setForm] = useState<FormState>(initialEmpty);
  const [initialForm, setInitialForm] = useState(serializeForm(initialEmpty));
  const [types, setTypes] = useState<WorkOrderType[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [taskCount, setTaskCount] = useState<number | undefined>(undefined);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [typeData, projectData, userData, teamData, workOrder] = await Promise.all([
        projectsService.getWorkOrderTypes(), projectsService.getProjects(),
        identityService.getUsers().catch(() => []), identityService.getTeams().catch(() => []),
        isNew || !recordId ? Promise.resolve(null) : projectsService.getWorkOrder(recordId),
      ]);
      setTypes(typeData); setProjects(projectData); setUsers(userData); setTeams(teamData); setRecord(workOrder);
      const next = workOrder ? recordToForm(workOrder) : { ...emptyForm(linkedProjectId), work_order_type_id: typeData[0]?.id || '' };
      setForm(next); setInitialForm(serializeForm(next));
    } catch (loadError) {
      setError(formatApiError(loadError, 'Não foi possível carregar a ordem de trabalho'));
    } finally { setLoading(false); }
  }, [isNew, linkedProjectId, recordId]);

  useEffect(() => { void load(); }, [load]);
  const dirty = !loading && serializeForm(form) !== initialForm;
  const title = isNew ? 'Nova ordem de trabalho' : (record?.title || 'Ordem de trabalho');

  const save = async () => {
    if (!form.title.trim() || !form.work_order_type_id) {
      setActiveTab('general'); toast.error('Informe o título e o tipo da ordem.'); return;
    }
    setSaving(true);
    try {
      const payload = {
        title: form.title.trim(), work_order_type_id: form.work_order_type_id,
        order_type_id: form.work_order_type_id, project_id: form.project_id || null,
        priority: form.priority, responsible_id: emptyToUndefined(form.responsible_id),
        team_id: emptyToUndefined(form.team_id), scheduled_start: emptyToUndefined(form.scheduled_start),
        scheduled_end: emptyToUndefined(form.scheduled_end), address: emptyToUndefined(form.address),
        estimated_hours: Number(form.estimated_hours) || 0, estimated_cost: Number(form.estimated_cost) || 0,
        notes: emptyToUndefined(form.notes), description: emptyToUndefined(form.description),
      };
      const saved = isNew || !recordId ? await projectsService.createWorkOrder(payload) : await projectsService.updateWorkOrder(recordId, payload);
      const next = recordToForm(saved); setRecord(saved); setForm(next); setInitialForm(serializeForm(next));
      toast.success(isNew ? 'Ordem criada com sucesso.' : 'Ordem atualizada com sucesso.');
      if (isNew) navigate(buildRecordFormPath('projetos', 'ordens-de-trabalho', saved.id), { replace: true, state: location.state });
    } catch (saveError) { toast.error(formatApiError(saveError, 'Não foi possível salvar a ordem')); }
    finally { setSaving(false); }
  };

  const remove = async () => {
    if (!recordId || isNew) return;
    setDeleting(true);
    try { await projectsService.deleteWorkOrder(recordId); toast.success('Ordem excluída com sucesso.'); navigate('/projetos?view=work_orders', { replace: true }); }
    catch (deleteError) { toast.error(formatApiError(deleteError, 'Não foi possível excluir a ordem')); setDeleting(false); setDeleteOpen(false); }
  };

  return <div className="operational-record-form">
    <RecordFormPage title={title} eyebrow="Execução operacional" description="Planejamento, responsáveis e instruções da ordem de trabalho."
      recordCode={record?.order_number || record?.code} icon={ClipboardList}
      status={<span className="record-status-pill">{statusLabel(record?.status)}</span>}
      breadcrumbs={[{ label: 'Ordens de trabalho', to: '/projetos?view=work_orders' }, { label: isNew ? 'Nova' : title }]}
      actions={!isNew ? <button type="button" className="ui-button ui-button--danger" onClick={() => setDeleteOpen(true)}><Trash2 size={15} /> Excluir</button> : undefined}
      tabs={TAB_ITEMS.map((tab) => tab.id === 'tasks' ? { ...tab, badge: isNew ? undefined : taskCount, disabled: isNew } : tab)} activeTab={activeTab} onTabChange={(tab) => setActiveTab(tab as FormTab)} onBack={goBack}
      isLoading={loading} error={error} onRetry={() => void load()}
      footer={<><span className={`record-form-footer-message${dirty ? ' is-dirty' : ''}`}>{dirty ? 'Existem alterações não salvas.' : 'Todas as alterações estão salvas.'}</span><button type="button" className="ui-button ui-button--secondary" onClick={goBack}>Cancelar</button><button type="button" className="ui-button ui-button--primary" onClick={() => void save()} disabled={saving || !dirty}><Save size={16} /> {saving ? 'Salvando...' : 'Salvar'}</button></>}
    >
      {activeTab === 'general' && <RecordFormSection title="Identificação" description="Classificação e vínculo principal da ordem." icon={ClipboardList}><div className="ui-form"><RecordFormGrid columns={3}>
        <div className="form-group is-full-width"><label>Título da ordem *</label><input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></div>
        <div className="form-group"><label>Tipo de ordem *</label><select value={form.work_order_type_id} onChange={(e) => setForm({ ...form, work_order_type_id: e.target.value })}><option value="">Selecione...</option>{types.map((type) => <option key={type.id} value={type.id}>{type.name}</option>)}</select></div>
        <div className="form-group"><label>Projeto vinculado</label><select value={form.project_id} onChange={(e) => setForm({ ...form, project_id: e.target.value })}><option value="">Ordem avulsa</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.code} — {project.name}</option>)}</select></div>
        <div className="form-group"><label>Prioridade</label><select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value as ProjectPriority })}><option value="LOW">Baixa</option><option value="MEDIUM">Média</option><option value="HIGH">Alta</option><option value="CRITICAL">Crítica</option></select></div>
      </RecordFormGrid></div></RecordFormSection>}
      {activeTab === 'execution' && <><RecordFormSection title="Responsáveis" description="Responsável técnico e equipe executora." icon={Users}><div className="ui-form"><RecordFormGrid columns={2}>
        <div className="form-group"><label>Responsável técnico</label><select value={form.responsible_id} onChange={(e) => setForm({ ...form, responsible_id: e.target.value })}><option value="">Selecione...</option>{users.map((user) => <option key={user.id} value={user.id}>{user.full_name || user.email}</option>)}</select></div>
        <div className="form-group"><label>Equipe</label><select value={form.team_id} onChange={(e) => setForm({ ...form, team_id: e.target.value })}><option value="">Selecione...</option>{teams.map((team) => <option key={team.id} value={team.id}>{team.name}</option>)}</select></div>
      </RecordFormGrid></div></RecordFormSection><RecordFormSection title="Agendamento e estimativas" description="Quando, onde e com quais recursos a ordem será executada." icon={CalendarClock}><div className="ui-form"><RecordFormGrid columns={4}>
        <div className="form-group"><label>Início previsto</label><input type="datetime-local" value={form.scheduled_start} onChange={(e) => setForm({ ...form, scheduled_start: e.target.value })} /></div>
        <div className="form-group"><label>Conclusão prevista</label><input type="datetime-local" value={form.scheduled_end} onChange={(e) => setForm({ ...form, scheduled_end: e.target.value })} /></div>
        <div className="form-group"><label>Horas estimadas</label><input type="number" min="0" step="0.5" value={form.estimated_hours || ''} onChange={(e) => setForm({ ...form, estimated_hours: Number(e.target.value) })} /></div>
        <div className="form-group"><label>Custo estimado</label><input type="number" min="0" step="0.01" value={form.estimated_cost || ''} onChange={(e) => setForm({ ...form, estimated_cost: Number(e.target.value) })} /></div>
        <div className="form-group is-full-width"><label>Local de execução</label><div style={{ position: 'relative' }}><MapPin size={15} style={{ position: 'absolute', left: 10, top: 11, color: 'var(--text-muted)' }} /><input style={{ paddingLeft: 32 }} value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} /></div></div>
      </RecordFormGrid></div></RecordFormSection></>}
      {activeTab === 'instructions' && <RecordFormSection title="Procedimentos e instruções" description="Orientações técnicas para a equipe executora." icon={Wrench}><div className="ui-form"><RecordFormGrid columns={1}>
        <div className="form-group"><label>Notas técnicas e procedimentos</label><textarea rows={6} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></div>
        <div className="form-group"><label>Descrição detalhada do trabalho</label><textarea rows={7} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
      </RecordFormGrid></div></RecordFormSection>}
      {activeTab === 'tasks' && !isNew && <TasksRelationTab context="work_order" recordId={recordId} onCountChange={setTaskCount} />}
    </RecordFormPage>
    <UnsavedChangesGuard when={dirty && !saving && !deleting} />
    <ConfirmModal isOpen={deleteOpen} onClose={() => setDeleteOpen(false)} onConfirm={remove} title="Excluir ordem de trabalho" message={<>Deseja excluir <strong>{title}</strong>?</>} confirmText="Excluir ordem" type="danger" isLoading={deleting} />
  </div>;
}
