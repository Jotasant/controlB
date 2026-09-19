import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { CheckCircle2, GitBranch, GripVertical, Pencil, Plus, Save, Settings2, Trash2 } from 'lucide-react';

import { ConfirmModal } from '@/components/ConfirmModal/ConfirmModal';
import { Modal } from '@/components/Modal/Modal';
import { RecordFormGrid, RecordFormPage, RecordFormSection, UnsavedChangesGuard, type RecordFormTab } from '@/components/RecordForm';
import { useToast } from '@/components/Toast/ToastContext';
import { useRecordFormNavigation } from '@/hooks/useRecordFormNavigation';
import { useRecordFormTab } from '@/hooks/useRecordFormTab';
import { buildRecordFormPath, isNewRecordSegment } from '@/routing/recordRoutes';
import { formatApiError, projectsService } from '@/services/api';
import type { WorkflowStage, WorkflowTemplate } from '@/types';

import { serializeForm } from './recordFormUtils';
import './OperationalRecordForm.scss';

const TABS = ['general', 'stages'] as const;
type FormTab = typeof TABS[number];

interface FormState {
  name: string;
  description: string;
  target_entity: 'PROJECT' | 'WORK_ORDER';
  is_active: boolean;
  create_default_stages: boolean;
}

interface StageFormState {
  id?: string;
  name: string;
  description: string;
  color: string;
  position: number;
  is_initial: boolean;
  is_terminal: boolean;
}

const EMPTY_FORM: FormState = {
  name: '', description: '', target_entity: 'PROJECT', is_active: true, create_default_stages: true,
};

const emptyStage = (position: number): StageFormState => ({
  name: '', description: '', color: '#6366f1', position, is_initial: false, is_terminal: false,
});

const recordToForm = (record: WorkflowTemplate): FormState => ({
  name: record.name || '', description: record.description || '',
  target_entity: record.target_entity, is_active: record.is_active, create_default_stages: false,
});

const DEFAULT_STAGES = [
  { name: 'Planejamento', position: 0, color: '#6366f1', is_initial: true, is_terminal: false, allowed_transitions: [] },
  { name: 'Execução', position: 1, color: '#3b82f6', is_initial: false, is_terminal: false, allowed_transitions: [] },
  { name: 'Revisão / Qualidade', position: 2, color: '#f59e0b', is_initial: false, is_terminal: false, allowed_transitions: [] },
  { name: 'Concluído', position: 3, color: '#10b981', is_initial: false, is_terminal: true, allowed_transitions: [] },
];

const TAB_ITEMS = (count: number, isNew: boolean): RecordFormTab[] => [
  { id: 'general', label: 'Geral', icon: Settings2 },
  { id: 'stages', label: 'Etapas', icon: GitBranch, badge: count, disabled: isNew },
];

export function WorkflowRecordFormPage() {
  const { recordId } = useParams<{ recordId: string }>();
  const isNew = isNewRecordSegment(recordId);
  const location = useLocation();
  const navigate = useNavigate();
  const goBack = useRecordFormNavigation('/projetos?view=workflows');
  const toast = useToast();
  const [activeTab, setActiveTab] = useRecordFormTab<FormTab>(TABS, 'general');
  const [record, setRecord] = useState<WorkflowTemplate | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [initialForm, setInitialForm] = useState(serializeForm(EMPTY_FORM));
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [stageDelete, setStageDelete] = useState<WorkflowStage | null>(null);
  const [stageModalOpen, setStageModalOpen] = useState(false);
  const [stageSaving, setStageSaving] = useState(false);
  const [stageForm, setStageForm] = useState<StageFormState>(emptyStage(0));
  const [draggedStageId, setDraggedStageId] = useState<string | null>(null);

  const stages = useMemo(
    () => [...(record?.stages || [])].sort((left, right) => left.position - right.position),
    [record?.stages],
  );

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const workflow = isNew || !recordId ? null : await projectsService.getWorkflowTemplate(recordId);
      setRecord(workflow);
      const next = workflow ? recordToForm(workflow) : EMPTY_FORM;
      setForm(next); setInitialForm(serializeForm(next));
    } catch (loadError) { setError(formatApiError(loadError, 'Não foi possível carregar o workflow')); }
    finally { setLoading(false); }
  }, [isNew, recordId]);

  const refreshRecord = useCallback(async () => {
    if (isNew || !recordId) return;
    setRecord(await projectsService.getWorkflowTemplate(recordId));
  }, [isNew, recordId]);

  useEffect(() => { void load(); }, [load]);
  const dirty = !loading && serializeForm(form) !== initialForm;
  const title = isNew ? 'Novo workflow' : (record?.name || 'Workflow');

  const save = async () => {
    if (!form.name.trim()) { setActiveTab('general'); toast.error('Informe o nome do workflow.'); return; }
    setSaving(true);
    try {
      const payload = {
        name: form.name.trim(), description: form.description.trim() || null,
        target_entity: form.target_entity,
      };
      const saved = isNew || !recordId
        ? await projectsService.createWorkflowTemplate({
            ...payload, stages: form.create_default_stages ? DEFAULT_STAGES : [],
          })
        : await projectsService.updateWorkflowTemplate(recordId, { ...payload, is_active: form.is_active });
      const next = recordToForm(saved); setRecord(saved); setForm(next); setInitialForm(serializeForm(next));
      toast.success(isNew ? 'Workflow criado com sucesso.' : 'Workflow atualizado com sucesso.');
      if (isNew) navigate(buildRecordFormPath('projetos', 'workflows', saved.id), { replace: true, state: location.state });
    } catch (saveError) { toast.error(formatApiError(saveError, 'Não foi possível salvar o workflow')); }
    finally { setSaving(false); }
  };

  const remove = async () => {
    if (!recordId || isNew) return;
    setDeleting(true);
    try { await projectsService.deleteWorkflowTemplate(recordId); toast.success('Workflow excluído com sucesso.'); navigate('/projetos?view=workflows', { replace: true }); }
    catch (deleteError) { toast.error(formatApiError(deleteError, 'Não foi possível excluir o workflow')); setDeleting(false); setDeleteOpen(false); }
  };

  const openNewStage = () => {
    setStageForm(emptyStage(stages.length)); setStageModalOpen(true);
  };

  const openEditStage = (stage: WorkflowStage) => {
    setStageForm({
      id: stage.id, name: stage.name, description: stage.description || '', color: stage.color,
      position: stage.position, is_initial: stage.is_initial, is_terminal: Boolean(stage.is_terminal),
    });
    setStageModalOpen(true);
  };

  const saveStage = async () => {
    if (!recordId || isNew || !stageForm.name.trim()) { toast.error('Informe o nome da etapa.'); return; }
    setStageSaving(true);
    try {
      const payload = {
        name: stageForm.name.trim(), description: stageForm.description.trim() || null,
        color: stageForm.color, position: Number(stageForm.position),
        is_initial: stageForm.is_initial, is_terminal: stageForm.is_terminal,
      };
      if (stageForm.id) await projectsService.updateWorkflowStage(stageForm.id, payload);
      else await projectsService.addWorkflowStage(recordId, payload);
      setStageModalOpen(false); await refreshRecord();
      toast.success(stageForm.id ? 'Etapa atualizada.' : 'Etapa adicionada.');
    } catch (stageError) { toast.error(formatApiError(stageError, 'Não foi possível salvar a etapa')); }
    finally { setStageSaving(false); }
  };

  const removeStage = async () => {
    if (!stageDelete) return;
    try { await projectsService.deleteWorkflowStage(stageDelete.id); setStageDelete(null); await refreshRecord(); toast.success('Etapa excluída.'); }
    catch (stageError) { toast.error(formatApiError(stageError, 'Não foi possível excluir a etapa')); setStageDelete(null); }
  };

  const dropStage = async (targetId: string) => {
    if (!draggedStageId || draggedStageId === targetId) return;
    const fromIndex = stages.findIndex((stage) => stage.id === draggedStageId);
    const toIndex = stages.findIndex((stage) => stage.id === targetId);
    if (fromIndex < 0 || toIndex < 0) return;
    const reordered = [...stages];
    const [moved] = reordered.splice(fromIndex, 1);
    reordered.splice(toIndex, 0, moved);
    setRecord((current) => current ? { ...current, stages: reordered.map((stage, index) => ({ ...stage, position: index })) } : current);
    setDraggedStageId(null);
    try {
      await Promise.all(reordered.map((stage, index) => projectsService.updateWorkflowStage(stage.id, { position: index })));
      toast.success('Ordem das etapas atualizada.');
    } catch (stageError) { toast.error(formatApiError(stageError, 'Não foi possível reordenar as etapas')); await refreshRecord(); }
  };

  return <div className="operational-record-form">
    <RecordFormPage title={title} eyebrow="Parametrização operacional" description="Ciclo de vida aplicado a projetos ou ordens de trabalho."
      icon={GitBranch} status={<span className="record-status-pill">{isNew ? 'Novo' : form.is_active ? 'Ativo' : 'Inativo'}</span>}
      breadcrumbs={[{ label: 'Workflows', to: '/projetos?view=workflows' }, { label: isNew ? 'Novo' : title }]}
      actions={!isNew ? <button type="button" className="ui-button ui-button--danger" onClick={() => setDeleteOpen(true)}><Trash2 size={15} /> Excluir</button> : undefined}
      tabs={TAB_ITEMS(stages.length, isNew)} activeTab={activeTab} onTabChange={(tab) => setActiveTab(tab as FormTab)} onBack={goBack}
      isLoading={loading} error={error} onRetry={() => void load()}
      footer={<><span className={`record-form-footer-message${dirty ? ' is-dirty' : ''}`}>{dirty ? 'Existem alterações não salvas.' : 'Todas as alterações estão salvas.'}</span><button type="button" className="ui-button ui-button--secondary" onClick={goBack} disabled={saving || deleting}>Cancelar</button><button type="button" className="ui-button ui-button--primary" onClick={() => void save()} disabled={saving || deleting || !dirty}><Save size={16} /> {saving ? 'Salvando...' : 'Salvar'}</button></>}
    >
      {activeTab === 'general' && <RecordFormSection title="Definição do fluxo" description="Onde o workflow será usado e como será identificado." icon={Settings2}><div className="ui-form"><RecordFormGrid columns={2}>
        <div className="form-group is-full-width"><label>Nome *</label><input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></div>
        <div className="form-group"><label>Entidade alvo *</label><select value={form.target_entity} onChange={(event) => setForm({ ...form, target_entity: event.target.value as FormState['target_entity'] })}><option value="PROJECT">Projetos operacionais</option><option value="WORK_ORDER">Ordens de trabalho</option></select></div>
        {!isNew && <label className="record-form-checkbox"><input type="checkbox" checked={form.is_active} onChange={(event) => setForm({ ...form, is_active: event.target.checked })} /> Disponível para novos registros</label>}
        <div className="form-group is-full-width"><label>Descrição</label><textarea rows={6} value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></div>
        {isNew && <label className="record-form-checkbox is-full-width"><input type="checkbox" checked={form.create_default_stages} onChange={(event) => setForm({ ...form, create_default_stages: event.target.checked })} /> Criar etapas recomendadas: Planejamento, Execução, Revisão e Concluído</label>}
      </RecordFormGrid></div></RecordFormSection>}
      {activeTab === 'stages' && <RecordFormSection title="Etapas do workflow" description="Arraste as etapas para definir a ordem de execução." icon={GitBranch}
        actions={<button type="button" className="ui-button ui-button--primary" onClick={openNewStage}><Plus size={15} /> Nova etapa</button>}>
        <div className="record-form-stage-list">{stages.length === 0 ? <div className="record-form-empty-state"><GitBranch size={28} /><strong>Nenhuma etapa configurada</strong><span>Adicione a primeira etapa para começar a estruturar o fluxo.</span></div> : stages.map((stage, index) => <div key={stage.id} className={`record-form-stage${draggedStageId === stage.id ? ' is-dragging' : ''}`} draggable onDragStart={() => setDraggedStageId(stage.id)} onDragEnd={() => setDraggedStageId(null)} onDragOver={(event) => event.preventDefault()} onDrop={() => void dropStage(stage.id)}>
          <GripVertical size={18} className="record-form-stage__grip" /><span className="record-form-stage__color" style={{ backgroundColor: stage.color }} /><span className="record-form-stage__position">{index + 1}</span><div className="record-form-stage__identity"><strong>{stage.name}</strong><small>{stage.description || 'Sem instruções adicionais'}</small></div><div className="record-form-stage__flags">{stage.is_initial && <span>Inicial</span>}{stage.is_terminal && <span className="is-terminal"><CheckCircle2 size={12} /> Final</span>}</div><button type="button" className="ui-button ui-button--icon" onClick={() => openEditStage(stage)} title="Editar etapa"><Pencil size={15} /></button><button type="button" className="ui-button ui-button--icon ui-button--danger" onClick={() => setStageDelete(stage)} title="Excluir etapa"><Trash2 size={15} /></button>
        </div>)}</div>
      </RecordFormSection>}
    </RecordFormPage>
    <UnsavedChangesGuard when={dirty && !saving && !deleting} />
    <ConfirmModal isOpen={deleteOpen} onClose={() => setDeleteOpen(false)} onConfirm={remove} title="Excluir workflow" message={<>Deseja excluir <strong>{title}</strong>?</>} confirmText="Excluir workflow" type="danger" isLoading={deleting} />
    <ConfirmModal isOpen={Boolean(stageDelete)} onClose={() => setStageDelete(null)} onConfirm={removeStage} title="Excluir etapa" message={<>Deseja excluir a etapa <strong>{stageDelete?.name}</strong>?</>} confirmText="Excluir etapa" type="danger" />
    <Modal isOpen={stageModalOpen} onClose={() => setStageModalOpen(false)} title={stageForm.id ? 'Editar etapa' : 'Nova etapa'} subtitle="Ação rápida no fluxo atual" size="md">
      <div className="ui-form record-form-stage-modal"><RecordFormGrid columns={2}>
        <div className="form-group is-full-width"><label>Nome *</label><input value={stageForm.name} onChange={(event) => setStageForm({ ...stageForm, name: event.target.value })} /></div>
        <div className="form-group"><label>Posição</label><input type="number" min="0" value={stageForm.position} onChange={(event) => setStageForm({ ...stageForm, position: Number(event.target.value) })} /></div>
        <div className="form-group"><label>Cor</label><div className="record-form-color"><input type="color" value={stageForm.color} onChange={(event) => setStageForm({ ...stageForm, color: event.target.value })} /><input value={stageForm.color} onChange={(event) => setStageForm({ ...stageForm, color: event.target.value })} /></div></div>
        <label className="record-form-checkbox"><input type="checkbox" checked={stageForm.is_initial} onChange={(event) => setStageForm({ ...stageForm, is_initial: event.target.checked })} /> Etapa inicial</label>
        <label className="record-form-checkbox"><input type="checkbox" checked={stageForm.is_terminal} onChange={(event) => setStageForm({ ...stageForm, is_terminal: event.target.checked })} /> Etapa final</label>
        <div className="form-group is-full-width"><label>Descrição e instruções</label><textarea rows={4} value={stageForm.description} onChange={(event) => setStageForm({ ...stageForm, description: event.target.value })} /></div>
      </RecordFormGrid><div className="record-form-modal-actions"><button type="button" className="ui-button ui-button--secondary" onClick={() => setStageModalOpen(false)}>Cancelar</button><button type="button" className="ui-button ui-button--primary" onClick={() => void saveStage()} disabled={stageSaving}>{stageSaving ? 'Salvando...' : 'Salvar etapa'}</button></div></div>
    </Modal>
  </div>;
}
