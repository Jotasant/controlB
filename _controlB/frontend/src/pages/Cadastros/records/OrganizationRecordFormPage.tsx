import { useCallback, useEffect, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { Building2, Save, Trash2 } from 'lucide-react';

import { ConfirmModal } from '@/components/ConfirmModal/ConfirmModal';
import { RecordFormGrid, RecordFormPage, RecordFormSection, UnsavedChangesGuard } from '@/components/RecordForm';
import { useToast } from '@/components/Toast/ToastContext';
import { usePermissions } from '@/hooks/usePermissions';
import { useRecordFormNavigation } from '@/hooks/useRecordFormNavigation';
import { buildRecordFormPath, isNewRecordSegment } from '@/routing/recordRoutes';
import { formatApiError, identityService } from '@/services/api';
import type { Organization } from '@/types';

import './IdentityRecordForm.scss';

interface FormState { name: string; is_active: boolean }
const EMPTY_FORM: FormState = { name: '', is_active: true };
const serialize = (form: FormState) => JSON.stringify(form);

export function OrganizationRecordFormPage() {
  const { recordId } = useParams<{ recordId: string }>();
  const isNew = isNewRecordSegment(recordId);
  const location = useLocation();
  const navigate = useNavigate();
  const goBack = useRecordFormNavigation('/cadastros?view=organizacoes');
  const toast = useToast();
  const { hasPermission } = usePermissions();
  const canManage = hasPermission('organizations:manage');

  const [record, setRecord] = useState<Organization | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [initialForm, setInitialForm] = useState(serialize(EMPTY_FORM));
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const organization = isNew || !recordId ? null : await identityService.getOrganization(recordId, true);
      const next = organization ? { name: organization.name, is_active: organization.is_active } : EMPTY_FORM;
      setRecord(organization); setForm(next); setInitialForm(serialize(next));
    } catch (loadError) { setError(formatApiError(loadError, 'Não foi possível carregar a organização.')); }
    finally { setLoading(false); }
  }, [isNew, recordId]);

  useEffect(() => { void load(); }, [load]);
  const dirty = !loading && serialize(form) !== initialForm;
  const title = isNew ? 'Nova organização' : (record?.name || 'Organização');

  const save = async () => {
    if (!form.name.trim()) { toast.error('Informe o nome da organização.'); return; }
    setSaving(true);
    try {
      const saved = isNew || !recordId
        ? await identityService.createOrganization(form.name.trim())
        : await identityService.updateOrganization(recordId, { name: form.name.trim(), is_active: form.is_active });
      const next = { name: saved.name, is_active: saved.is_active };
      setRecord(saved); setForm(next); setInitialForm(serialize(next));
      toast.success(isNew ? 'Organização criada com sucesso.' : 'Organização atualizada com sucesso.');
      if (isNew) navigate(buildRecordFormPath('cadastros', 'organizacoes', saved.id), { replace: true, state: location.state });
    } catch (saveError) { toast.error(formatApiError(saveError, 'Não foi possível salvar a organização.')); }
    finally { setSaving(false); }
  };

  const remove = async () => {
    if (!recordId || isNew) return;
    setDeleting(true);
    try {
      await identityService.deleteOrganization(recordId);
      toast.success('Organização excluída com sucesso.');
      navigate('/cadastros?view=organizacoes', { replace: true });
    } catch (deleteError) {
      toast.error(formatApiError(deleteError, 'Não foi possível excluir a organização.'));
      setDeleting(false); setDeleteOpen(false);
    }
  };

  return <div className="identity-record-form operational-record-form">
    <RecordFormPage
      title={title} eyebrow="Cadastros" description="Dados da empresa, filial ou unidade de negócio."
      icon={Building2} status={<span className="record-status-pill">{isNew ? 'Nova' : form.is_active ? 'Ativa' : 'Inativa'}</span>}
      breadcrumbs={[{ label: 'Organizações', to: '/cadastros?view=organizacoes' }, { label: isNew ? 'Nova' : title }]}
      actions={!isNew && canManage ? <button type="button" className="ui-button ui-button--danger" onClick={() => setDeleteOpen(true)}><Trash2 size={15} /> Excluir</button> : undefined}
      onBack={goBack} isLoading={loading} error={error} onRetry={() => void load()}
      footer={<><span className={`record-form-footer-message${dirty ? ' is-dirty' : ''}`}>{dirty ? 'Existem alterações não salvas.' : 'Todas as alterações estão salvas.'}</span><button type="button" className="ui-button ui-button--secondary" onClick={goBack} disabled={saving || deleting}>Cancelar</button><button type="button" className="ui-button ui-button--primary" onClick={() => void save()} disabled={saving || deleting || !dirty || !canManage}><Save size={16} /> {saving ? 'Salvando...' : 'Salvar'}</button></>}
    >
      <RecordFormSection title="Identificação" description="Informações que identificam esta unidade em todo o sistema." icon={Building2}>
        <div className="ui-form"><RecordFormGrid columns={2}>
          <div className="form-group is-full-width"><label>Nome da organização *</label><input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} disabled={!canManage} placeholder="Ex.: ControlB Matriz" /></div>
          {!isNew && <label className="record-form-checkbox"><input type="checkbox" checked={form.is_active} onChange={(event) => setForm({ ...form, is_active: event.target.checked })} disabled={!canManage} /> Organização ativa e operacional</label>}
        </RecordFormGrid></div>
      </RecordFormSection>
    </RecordFormPage>
    <UnsavedChangesGuard when={dirty && !saving && !deleting} />
    <ConfirmModal isOpen={deleteOpen} onClose={() => setDeleteOpen(false)} onConfirm={remove} title="Excluir organização" message={<>Deseja excluir permanentemente <strong>{title}</strong>? Os vínculos associados podem ser removidos.</>} confirmText="Excluir" type="danger" isLoading={deleting} />
  </div>;
}
