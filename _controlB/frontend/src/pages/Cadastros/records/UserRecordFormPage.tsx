import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { KeyRound, Save, Trash2, UserRound } from 'lucide-react';

import { ConfirmModal } from '@/components/ConfirmModal/ConfirmModal';
import { RecordFormGrid, RecordFormPage, RecordFormSection, UnsavedChangesGuard, type RecordFormTab } from '@/components/RecordForm';
import { useToast } from '@/components/Toast/ToastContext';
import { usePermissions } from '@/hooks/usePermissions';
import { useRecordFormNavigation } from '@/hooks/useRecordFormNavigation';
import { useRecordFormTab } from '@/hooks/useRecordFormTab';
import { buildRecordFormPath, isNewRecordSegment } from '@/routing/recordRoutes';
import { formatApiError, identityService } from '@/services/api';
import type { Organization, Role, User, UserMe } from '@/types';

import './IdentityRecordForm.scss';

const TABS = ['personal', 'access'] as const;
type FormTab = typeof TABS[number];
const TAB_ITEMS: RecordFormTab[] = [
  { id: 'personal', label: 'Dados pessoais', icon: UserRound },
  { id: 'access', label: 'Acesso e segurança', icon: KeyRound },
];
interface FormState { full_name: string; email: string; organization_id: string; role_id: string; is_active: boolean; is_seller: boolean; password: string }
const emptyForm = (organizationId = ''): FormState => ({ full_name: '', email: '', organization_id: organizationId, role_id: '', is_active: true, is_seller: false, password: '' });
const recordToForm = (record: User): FormState => ({ full_name: record.full_name || '', email: record.email || '', organization_id: record.organization_id || '', role_id: record.role_id || '', is_active: record.is_active, is_seller: Boolean(record.is_seller), password: '' });
const serialize = (form: FormState) => JSON.stringify(form);

export function UserRecordFormPage() {
  const { recordId } = useParams<{ recordId: string }>();
  const isNew = isNewRecordSegment(recordId);
  const location = useLocation();
  const navigate = useNavigate();
  const goBack = useRecordFormNavigation('/cadastros?view=usuarios');
  const toast = useToast();
  const { hasPermission } = usePermissions();
  const canSave = isNew ? hasPermission('users:create') : hasPermission('users:edit');
  const [activeTab, setActiveTab] = useRecordFormTab<FormTab>(TABS, 'personal');

  const [record, setRecord] = useState<User | null>(null);
  const [currentUser, setCurrentUser] = useState<UserMe | null>(null);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [form, setForm] = useState<FormState>(emptyForm());
  const [initialForm, setInitialForm] = useState(serialize(emptyForm()));
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [me, organizationData, roleData, userRecord] = await Promise.all([
        identityService.getMe(), identityService.getOrganizations().catch(() => []), identityService.getRoles().catch(() => []),
        isNew || !recordId ? Promise.resolve(null) : identityService.getUser(recordId, true),
      ]);
      const next = userRecord ? recordToForm(userRecord) : emptyForm(me.organization_id);
      setCurrentUser(me); setOrganizations(organizationData); setRoles(roleData); setRecord(userRecord); setForm(next); setInitialForm(serialize(next));
    } catch (loadError) { setError(formatApiError(loadError, 'Não foi possível carregar o usuário.')); }
    finally { setLoading(false); }
  }, [isNew, recordId]);

  useEffect(() => { void load(); }, [load]);
  const availableRoles = useMemo(() => roles.filter((role) => role.organization_id === form.organization_id), [form.organization_id, roles]);
  const organizationName = organizations.find((organization) => organization.id === form.organization_id)?.name || 'Organização atual';
  const dirty = !loading && serialize(form) !== initialForm;
  const title = isNew ? 'Novo usuário' : (record?.full_name || 'Usuário');
  const isSelf = Boolean(record && currentUser?.id === record.id);

  const save = async () => {
    if (!form.full_name.trim() || !form.email.trim()) { setActiveTab('personal'); toast.error('Informe nome e e-mail.'); return; }
    if (!form.organization_id) { setActiveTab('access'); toast.error('A organização do usuário não foi identificada.'); return; }
    if (isNew && !form.password) { setActiveTab('access'); toast.error('Informe a senha inicial.'); return; }
    setSaving(true);
    try {
      const saved = isNew || !recordId
        ? await identityService.createUser({ full_name: form.full_name.trim(), email: form.email.trim(), password: form.password, organization_id: form.organization_id, role_id: form.role_id || null, is_seller: form.is_seller })
        : await identityService.updateUser(recordId, { full_name: form.full_name.trim(), email: form.email.trim(), organization_id: form.organization_id, role_id: form.role_id || null, is_active: form.is_active, is_seller: form.is_seller, password: form.password || undefined });
      const next = recordToForm(saved); setRecord(saved); setForm(next); setInitialForm(serialize(next));
      toast.success(isNew ? 'Usuário criado com sucesso.' : 'Usuário atualizado com sucesso.');
      if (isNew) navigate(buildRecordFormPath('cadastros', 'usuarios', saved.id), { replace: true, state: location.state });
    } catch (saveError) { toast.error(formatApiError(saveError, 'Não foi possível salvar o usuário.')); }
    finally { setSaving(false); }
  };

  const remove = async () => {
    if (!recordId || isNew || isSelf) return;
    setDeleting(true);
    try { await identityService.deleteUser(recordId); toast.success('Usuário excluído com sucesso.'); navigate('/cadastros?view=usuarios', { replace: true }); }
    catch (deleteError) { toast.error(formatApiError(deleteError, 'Não foi possível excluir o usuário.')); setDeleting(false); setDeleteOpen(false); }
  };

  return <div className="identity-record-form operational-record-form">
    <RecordFormPage title={title} eyebrow="Cadastros" description="Perfil do colaborador e regras de acesso ao sistema." icon={UserRound}
      status={<span className="record-status-pill">{isNew ? 'Novo' : form.is_active ? 'Ativo' : 'Inativo'}</span>}
      breadcrumbs={[{ label: 'Usuários', to: '/cadastros?view=usuarios' }, { label: isNew ? 'Novo' : title }]}
      actions={!isNew && hasPermission('users:delete') && !isSelf ? <button type="button" className="ui-button ui-button--danger" onClick={() => setDeleteOpen(true)}><Trash2 size={15} /> Excluir</button> : undefined}
      tabs={TAB_ITEMS} activeTab={activeTab} onTabChange={(tab) => setActiveTab(tab as FormTab)} onBack={goBack}
      isLoading={loading} error={error} onRetry={() => void load()}
      footer={<><span className={`record-form-footer-message${dirty ? ' is-dirty' : ''}`}>{dirty ? 'Existem alterações não salvas.' : 'Todas as alterações estão salvas.'}</span><button type="button" className="ui-button ui-button--secondary" onClick={goBack} disabled={saving || deleting}>Cancelar</button><button type="button" className="ui-button ui-button--primary" onClick={() => void save()} disabled={saving || deleting || !dirty || !canSave}><Save size={16} /> {saving ? 'Salvando...' : 'Salvar'}</button></>}
    >
      {activeTab === 'personal' && <RecordFormSection title="Dados pessoais" description="Informações usadas para identificar o colaborador." icon={UserRound}><div className="ui-form"><RecordFormGrid columns={2}>
        <div className="form-group"><label>Nome completo *</label><input value={form.full_name} onChange={(event) => setForm({ ...form, full_name: event.target.value })} disabled={!canSave} placeholder="Ex.: Carlos Silva" /></div>
        <div className="form-group"><label>E-mail corporativo *</label><input type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} disabled={!canSave} placeholder="nome@empresa.com" /></div>
        <label className="record-form-checkbox"><input type="checkbox" checked={form.is_seller} onChange={(event) => setForm({ ...form, is_seller: event.target.checked })} disabled={!canSave} /> Atua como vendedor</label>
      </RecordFormGrid></div></RecordFormSection>}
      {activeTab === 'access' && <RecordFormSection title="Acesso e segurança" description="Organização, cargo, status da conta e credencial." icon={KeyRound}><div className="ui-form"><RecordFormGrid columns={2}>
        <div className="form-group"><label>Organização</label><input value={organizationName} disabled /><small className="field-help">O usuário pertence ao ambiente organizacional atual.</small></div>
        <div className="form-group"><label>Cargo / perfil</label><select value={form.role_id} onChange={(event) => setForm({ ...form, role_id: event.target.value })} disabled={!canSave}><option value="">Sem cargo vinculado</option>{availableRoles.map((role) => <option key={role.id} value={role.id}>{role.name}{role.is_active ? '' : ' (inativo)'}</option>)}</select></div>
        {!isNew && <div className="form-group"><label>Status da conta</label><select value={form.is_active ? 'active' : 'inactive'} onChange={(event) => setForm({ ...form, is_active: event.target.value === 'active' })} disabled={!canSave}><option value="active">Ativo (acesso liberado)</option><option value="inactive">Inativo (acesso bloqueado)</option></select></div>}
        <div className="form-group"><label>{isNew ? 'Senha inicial *' : 'Redefinir senha'}</label><input type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} disabled={!canSave} placeholder={isNew ? 'Informe uma senha inicial' : 'Deixe em branco para manter a atual'} /></div>
      </RecordFormGrid></div></RecordFormSection>}
    </RecordFormPage>
    <UnsavedChangesGuard when={dirty && !saving && !deleting} />
    <ConfirmModal isOpen={deleteOpen} onClose={() => setDeleteOpen(false)} onConfirm={remove} title="Excluir usuário" message={<>Deseja excluir permanentemente <strong>{title}</strong>?</>} confirmText="Excluir" type="danger" isLoading={deleting} />
  </div>;
}
