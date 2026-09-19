import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { Save, Shield, ShieldCheck, Trash2 } from 'lucide-react';

import { ConfirmModal } from '@/components/ConfirmModal/ConfirmModal';
import { RecordFormGrid, RecordFormPage, RecordFormSection, UnsavedChangesGuard, type RecordFormTab } from '@/components/RecordForm';
import { useToast } from '@/components/Toast/ToastContext';
import { usePermissions } from '@/hooks/usePermissions';
import { useRecordFormNavigation } from '@/hooks/useRecordFormNavigation';
import { useRecordFormTab } from '@/hooks/useRecordFormTab';
import { buildRecordFormPath, isNewRecordSegment } from '@/routing/recordRoutes';
import { formatApiError, identityService } from '@/services/api';
import type { Organization, Permission, Role } from '@/types';

import './IdentityRecordForm.scss';

const TABS = ['identity', 'permissions'] as const;
type FormTab = typeof TABS[number];
const TAB_ITEMS: RecordFormTab[] = [
  { id: 'identity', label: 'Identificação', icon: Shield },
  { id: 'permissions', label: 'Matriz de permissões', icon: ShieldCheck },
];
interface FormState { name: string; description: string; organization_id: string; is_active: boolean; permission_ids: string[] }
const emptyForm = (organizationId = ''): FormState => ({ name: '', description: '', organization_id: organizationId, is_active: true, permission_ids: [] });
const recordToForm = (record: Role): FormState => ({ name: record.name || '', description: record.description || '', organization_id: record.organization_id, is_active: record.is_active, permission_ids: record.permissions?.map((permission) => permission.id) || [] });
const serialize = (form: FormState) => JSON.stringify({ ...form, permission_ids: [...form.permission_ids].sort() });

export function RoleRecordFormPage() {
  const { recordId } = useParams<{ recordId: string }>();
  const isNew = isNewRecordSegment(recordId);
  const location = useLocation();
  const navigate = useNavigate();
  const goBack = useRecordFormNavigation('/cadastros?view=cargos');
  const toast = useToast();
  const { hasPermission } = usePermissions();
  const canManage = hasPermission('roles:manage');
  const [activeTab, setActiveTab] = useRecordFormTab<FormTab>(TABS, 'identity');

  const [record, setRecord] = useState<Role | null>(null);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
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
      const [me, organizationData, permissionData, roleRecord] = await Promise.all([
        identityService.getMe(), identityService.getOrganizations().catch(() => []), identityService.getPermissions(),
        isNew || !recordId ? Promise.resolve(null) : identityService.getRole(recordId, true),
      ]);
      const next = roleRecord ? recordToForm(roleRecord) : emptyForm(me.organization_id);
      setRecord(roleRecord); setOrganizations(organizationData); setPermissions(permissionData); setForm(next); setInitialForm(serialize(next));
    } catch (loadError) { setError(formatApiError(loadError, 'Não foi possível carregar o cargo.')); }
    finally { setLoading(false); }
  }, [isNew, recordId]);

  useEffect(() => { void load(); }, [load]);
  const permissionsByModule = useMemo(() => permissions.reduce<Record<string, Permission[]>>((groups, permission) => { (groups[permission.module] ||= []).push(permission); return groups; }, {}), [permissions]);
  const organizationIsMissing = Boolean(form.organization_id && !organizations.some((organization) => organization.id === form.organization_id));
  const dirty = !loading && serialize(form) !== initialForm;
  const title = isNew ? 'Novo cargo' : (record?.name || 'Cargo');

  const togglePermission = (permissionId: string) => setForm((current) => ({ ...current, permission_ids: current.permission_ids.includes(permissionId) ? current.permission_ids.filter((id) => id !== permissionId) : [...current.permission_ids, permissionId] }));
  const save = async () => {
    if (!form.name.trim()) { setActiveTab('identity'); toast.error('Informe o nome do cargo.'); return; }
    if (!form.organization_id) { setActiveTab('identity'); toast.error('Selecione a organização do cargo.'); return; }
    setSaving(true);
    try {
      const saved = isNew || !recordId
        ? await identityService.createRole(form.name.trim(), form.description.trim(), form.organization_id, form.permission_ids)
        : await identityService.updateRole(recordId, { name: form.name.trim(), description: form.description.trim(), is_active: form.is_active, permission_ids: form.permission_ids });
      const next = recordToForm(saved); setRecord(saved); setForm(next); setInitialForm(serialize(next));
      toast.success(isNew ? 'Cargo criado com sucesso.' : 'Cargo atualizado com sucesso.');
      if (isNew) navigate(buildRecordFormPath('cadastros', 'cargos', saved.id), { replace: true, state: location.state });
    } catch (saveError) { toast.error(formatApiError(saveError, 'Não foi possível salvar o cargo.')); }
    finally { setSaving(false); }
  };
  const remove = async () => {
    if (!recordId || isNew) return;
    setDeleting(true);
    try { await identityService.deleteRole(recordId); toast.success('Cargo excluído com sucesso.'); navigate('/cadastros?view=cargos', { replace: true }); }
    catch (deleteError) { toast.error(formatApiError(deleteError, 'Não foi possível excluir o cargo.')); setDeleting(false); setDeleteOpen(false); }
  };

  return <div className="identity-record-form operational-record-form">
    <RecordFormPage title={title} eyebrow="Cadastros" description="Responsabilidades do cargo e acessos concedidos aos usuários." icon={Shield}
      status={<span className="record-status-pill">{isNew ? 'Novo' : form.is_active ? 'Ativo' : 'Inativo'}</span>}
      breadcrumbs={[{ label: 'Cargos', to: '/cadastros?view=cargos' }, { label: isNew ? 'Novo' : title }]}
      actions={!isNew && canManage ? <button type="button" className="ui-button ui-button--danger" onClick={() => setDeleteOpen(true)}><Trash2 size={15} /> Excluir</button> : undefined}
      tabs={TAB_ITEMS.map((tab) => tab.id === 'permissions' ? { ...tab, badge: form.permission_ids.length } : tab)} activeTab={activeTab} onTabChange={(tab) => setActiveTab(tab as FormTab)} onBack={goBack}
      isLoading={loading} error={error} onRetry={() => void load()}
      footer={<><span className={`record-form-footer-message${dirty ? ' is-dirty' : ''}`}>{dirty ? 'Existem alterações não salvas.' : 'Todas as alterações estão salvas.'}</span><button type="button" className="ui-button ui-button--secondary" onClick={goBack} disabled={saving || deleting}>Cancelar</button><button type="button" className="ui-button ui-button--primary" onClick={() => void save()} disabled={saving || deleting || !dirty || !canManage}><Save size={16} /> {saving ? 'Salvando...' : 'Salvar'}</button></>}
    >
      {activeTab === 'identity' && <RecordFormSection title="Identificação" description="Nome, finalidade e organização proprietária do cargo." icon={Shield}><div className="ui-form"><RecordFormGrid columns={2}>
        <div className="form-group"><label>Nome do cargo *</label><input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} disabled={!canManage} placeholder="Ex.: Gestor de compras" /></div>
        <div className="form-group"><label>Organização *</label><select value={form.organization_id} onChange={(event) => setForm({ ...form, organization_id: event.target.value })} disabled={!canManage || !isNew}><option value="">Selecione...</option>{organizationIsMissing && <option value={form.organization_id}>Organização atual</option>}{organizations.map((organization) => <option key={organization.id} value={organization.id}>{organization.name}</option>)}</select></div>
        {!isNew && <label className="record-form-checkbox"><input type="checkbox" checked={form.is_active} onChange={(event) => setForm({ ...form, is_active: event.target.checked })} disabled={!canManage} /> Cargo disponível para novos vínculos</label>}
        <div className="form-group is-full-width"><label>Descrição da função</label><textarea rows={6} value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} disabled={!canManage} placeholder="Descreva as responsabilidades deste cargo." /></div>
      </RecordFormGrid></div></RecordFormSection>}
      {activeTab === 'permissions' && <RecordFormSection title="Matriz de permissões" description="Selecione somente os acessos necessários para o exercício da função." icon={ShieldCheck}><div className="identity-permission-groups">{Object.entries(permissionsByModule).map(([moduleName, modulePermissions]) => <section key={moduleName} className="identity-permission-group"><header><strong>{moduleName}</strong><span>{modulePermissions.filter((permission) => form.permission_ids.includes(permission.id)).length}/{modulePermissions.length}</span></header><div className="identity-permission-grid">{modulePermissions.map((permission) => { const checked = form.permission_ids.includes(permission.id); return <label key={permission.id} className={`identity-permission${checked ? ' is-checked' : ''}`}><input type="checkbox" checked={checked} onChange={() => togglePermission(permission.id)} disabled={!canManage} /><span><strong>{permission.name}</strong><small>{permission.code}</small>{permission.description && <small>{permission.description}</small>}</span></label>; })}</div></section>)}</div></RecordFormSection>}
    </RecordFormPage>
    <UnsavedChangesGuard when={dirty && !saving && !deleting} />
    <ConfirmModal isOpen={deleteOpen} onClose={() => setDeleteOpen(false)} onConfirm={remove} title="Excluir cargo" message={<>Deseja excluir permanentemente <strong>{title}</strong>? Os usuários vinculados ficarão sem cargo.</>} confirmText="Excluir" type="danger" isLoading={deleting} />
  </div>;
}
