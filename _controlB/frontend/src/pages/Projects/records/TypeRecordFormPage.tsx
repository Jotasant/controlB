import { useCallback, useEffect, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { Braces, GitBranch, Palette, Save, Settings2, Trash2 } from 'lucide-react';

import { ConfirmModal } from '@/components/ConfirmModal/ConfirmModal';
import { RecordFormGrid, RecordFormPage, RecordFormSection, UnsavedChangesGuard, type RecordFormTab } from '@/components/RecordForm';
import { useToast } from '@/components/Toast/ToastContext';
import { useRecordFormNavigation } from '@/hooks/useRecordFormNavigation';
import { useRecordFormTab } from '@/hooks/useRecordFormTab';
import { buildRecordFormPath, isNewRecordSegment } from '@/routing/recordRoutes';
import { formatApiError, projectsService } from '@/services/api';
import type { ProjectType, WorkflowTemplate, WorkOrderType } from '@/types';

import { serializeForm } from './recordFormUtils';
import './OperationalRecordForm.scss';

type TypeKind = 'project' | 'work_order';
type TypeRecord = ProjectType | WorkOrderType;
const TABS = ['identity', 'rules'] as const;
type FormTab = typeof TABS[number];

const TAB_ITEMS: RecordFormTab[] = [
  { id: 'identity', label: 'Identificação', icon: Braces },
  { id: 'rules', label: 'Regras e aparência', icon: Palette },
];

interface FormState {
  name: string;
  code: string;
  prefix: string;
  color: string;
  description: string;
  default_workflow_id: string;
  is_active: boolean;
}

const emptyForm = (kind: TypeKind): FormState => ({
  name: '', code: '', prefix: kind === 'project' ? 'PRJ' : 'OS',
  color: kind === 'project' ? '#6366f1' : '#8b5cf6', description: '',
  default_workflow_id: '', is_active: true,
});

const recordToForm = (record: TypeRecord): FormState => ({
  name: record.name || '', code: record.code || '', prefix: record.prefix || '',
  color: record.color || '#6366f1', description: record.description || '',
  default_workflow_id: record.default_workflow_id || '', is_active: record.is_active,
});

interface TypeRecordFormProps { kind: TypeKind }

function TypeRecordForm({ kind }: TypeRecordFormProps) {
  const { recordId } = useParams<{ recordId: string }>();
  const isNew = isNewRecordSegment(recordId);
  const location = useLocation();
  const navigate = useNavigate();
  const toast = useToast();
  const view = kind === 'project' ? 'project_types' : 'wo_types';
  const resource = kind === 'project' ? 'tipos-de-projeto' : 'tipos-de-ordem';
  const singular = kind === 'project' ? 'tipo de projeto' : 'tipo de ordem';
  const label = kind === 'project' ? 'Tipo de projeto' : 'Tipo de ordem de trabalho';
  const targetEntity = kind === 'project' ? 'PROJECT' : 'WORK_ORDER';
  const goBack = useRecordFormNavigation(`/projetos?view=${view}`);
  const [activeTab, setActiveTab] = useRecordFormTab<FormTab>(TABS, 'identity');
  const initialEmpty = emptyForm(kind);

  const [record, setRecord] = useState<TypeRecord | null>(null);
  const [form, setForm] = useState<FormState>(initialEmpty);
  const [initialForm, setInitialForm] = useState(serializeForm(initialEmpty));
  const [workflows, setWorkflows] = useState<WorkflowTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [workflowData, typeRecord] = await Promise.all([
        projectsService.getWorkflowTemplates(false, false),
        isNew || !recordId
          ? Promise.resolve(null)
          : kind === 'project'
            ? projectsService.getProjectType(recordId)
            : projectsService.getWorkOrderType(recordId),
      ]);
      setWorkflows(workflowData.filter((workflow) => workflow.target_entity === targetEntity));
      setRecord(typeRecord);
      const next = typeRecord ? recordToForm(typeRecord) : emptyForm(kind);
      setForm(next); setInitialForm(serializeForm(next));
    } catch (loadError) { setError(formatApiError(loadError, `Não foi possível carregar o ${singular}`)); }
    finally { setLoading(false); }
  }, [isNew, kind, recordId, singular, targetEntity]);

  useEffect(() => { void load(); }, [load]);
  const dirty = !loading && serializeForm(form) !== initialForm;
  const title = isNew ? `Novo ${singular}` : (record?.name || label);

  const save = async () => {
    if (!form.name.trim() || !form.code.trim() || !form.prefix.trim()) {
      setActiveTab('identity'); toast.error('Informe nome, código e prefixo.'); return;
    }
    setSaving(true);
    try {
      const basePayload = {
        name: form.name.trim(), code: form.code.trim().toUpperCase(),
        prefix: form.prefix.trim().toUpperCase(), color: form.color,
        description: form.description.trim() || null,
        default_workflow_id: form.default_workflow_id || null,
      };
      let saved: TypeRecord;
      if (kind === 'project') {
        saved = isNew || !recordId
          ? await projectsService.createProjectType(basePayload)
          : await projectsService.updateProjectType(recordId, { ...basePayload, is_active: form.is_active });
      } else {
        saved = isNew || !recordId
          ? await projectsService.createWorkOrderType(basePayload)
          : await projectsService.updateWorkOrderType(recordId, { ...basePayload, is_active: form.is_active });
      }
      const next = recordToForm(saved); setRecord(saved); setForm(next); setInitialForm(serializeForm(next));
      toast.success(isNew ? `${label} criado com sucesso.` : `${label} atualizado com sucesso.`);
      if (isNew) navigate(buildRecordFormPath('projetos', resource, saved.id), { replace: true, state: location.state });
    } catch (saveError) { toast.error(formatApiError(saveError, `Não foi possível salvar o ${singular}`)); }
    finally { setSaving(false); }
  };

  const remove = async () => {
    if (!recordId || isNew) return;
    setDeleting(true);
    try {
      if (kind === 'project') await projectsService.deleteProjectType(recordId);
      else await projectsService.deleteWorkOrderType(recordId);
      toast.success(`${label} excluído com sucesso.`);
      navigate(`/projetos?view=${view}`, { replace: true });
    } catch (deleteError) {
      toast.error(formatApiError(deleteError, `Não foi possível excluir o ${singular}`));
      setDeleting(false); setDeleteOpen(false);
    }
  };

  return <div className="operational-record-form">
    <RecordFormPage title={title} eyebrow="Parametrização operacional" description={`Identificação e regras do ${singular}.`}
      recordCode={record?.code} icon={Settings2}
      status={<span className="record-status-pill">{isNew ? 'Novo' : form.is_active ? 'Ativo' : 'Inativo'}</span>}
      breadcrumbs={[{ label: kind === 'project' ? 'Tipos de projeto' : 'Tipos de ordem', to: `/projetos?view=${view}` }, { label: isNew ? 'Novo' : title }]}
      actions={!isNew ? <button type="button" className="ui-button ui-button--danger" onClick={() => setDeleteOpen(true)}><Trash2 size={15} /> Excluir</button> : undefined}
      tabs={TAB_ITEMS} activeTab={activeTab} onTabChange={(tab) => setActiveTab(tab as FormTab)} onBack={goBack}
      isLoading={loading} error={error} onRetry={() => void load()}
      footer={<><span className={`record-form-footer-message${dirty ? ' is-dirty' : ''}`}>{dirty ? 'Existem alterações não salvas.' : 'Todas as alterações estão salvas.'}</span><button type="button" className="ui-button ui-button--secondary" onClick={goBack} disabled={saving || deleting}>Cancelar</button><button type="button" className="ui-button ui-button--primary" onClick={() => void save()} disabled={saving || deleting || !dirty}><Save size={16} /> {saving ? 'Salvando...' : 'Salvar'}</button></>}
    >
      {activeTab === 'identity' && <RecordFormSection title="Identificação" description="Nome técnico e padrão de numeração usado pelo sistema." icon={Braces}><div className="ui-form"><RecordFormGrid columns={3}>
        <div className="form-group is-full-width"><label>Nome *</label><input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder={kind === 'project' ? 'Ex.: Instalação fotovoltaica' : 'Ex.: Manutenção preventiva'} /></div>
        <div className="form-group"><label>Código *</label><input value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value.toUpperCase() })} placeholder={kind === 'project' ? 'SOLAR_INST' : 'MANUT_PREV'} /></div>
        <div className="form-group"><label>Prefixo *</label><input maxLength={8} value={form.prefix} onChange={(event) => setForm({ ...form, prefix: event.target.value.toUpperCase() })} /></div>
        {!isNew && <label className="record-form-checkbox"><input type="checkbox" checked={form.is_active} onChange={(event) => setForm({ ...form, is_active: event.target.checked })} /> Disponível para novos registros</label>}
        <div className="form-group is-full-width"><label>Descrição</label><textarea rows={6} value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></div>
      </RecordFormGrid></div></RecordFormSection>}
      {activeTab === 'rules' && <RecordFormSection title="Regras e aparência" description="Workflow padrão e identificação visual nas listagens." icon={Palette}><div className="ui-form"><RecordFormGrid columns={2}>
        <div className="form-group"><label>Workflow padrão</label><select value={form.default_workflow_id} onChange={(event) => setForm({ ...form, default_workflow_id: event.target.value })}><option value="">Nenhum workflow padrão</option>{workflows.map((workflow) => <option key={workflow.id} value={workflow.id}>{workflow.name}{workflow.is_active ? '' : ' (inativo)'}</option>)}</select></div>
        <div className="form-group"><label>Cor identificadora</label><div className="record-form-color"><input type="color" value={form.color} onChange={(event) => setForm({ ...form, color: event.target.value })} /><input value={form.color} onChange={(event) => setForm({ ...form, color: event.target.value })} /></div></div>
        <div className="record-form-notice is-full-width"><GitBranch size={16} /><span>O workflow padrão é sugerido na criação; ele pode ser alterado individualmente no registro operacional.</span></div>
      </RecordFormGrid></div></RecordFormSection>}
    </RecordFormPage>
    <UnsavedChangesGuard when={dirty && !saving && !deleting} />
    <ConfirmModal isOpen={deleteOpen} onClose={() => setDeleteOpen(false)} onConfirm={remove} title={`Excluir ${singular}`} message={<>Deseja excluir <strong>{title}</strong>?</>} confirmText="Excluir" type="danger" isLoading={deleting} />
  </div>;
}

export function ProjectTypeRecordFormPage() { return <TypeRecordForm kind="project" />; }
export function WorkOrderTypeRecordFormPage() { return <TypeRecordForm kind="work_order" />; }
