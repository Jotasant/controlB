import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Building2, CheckCircle2, ChevronRight, Mail, Plus, RefreshCw,
  Search, Shield, Trash2, Users, XCircle,
} from 'lucide-react';

import { ConfirmModal } from '@/components/ConfirmModal/ConfirmModal';
import { ListPagination } from '@/components/ListPagination';
import { useToast } from '@/components/Toast/ToastContext';
import { useListPagination } from '@/hooks/useListPagination';
import { usePermissions } from '@/hooks/usePermissions';
import { buildRecordFormPath } from '@/routing/recordRoutes';
import { formatApiError, identityService } from '@/services/api';
import type { Organization, Role, User } from '@/types';

import './Cadastros.scss';

type MenuOption = 'usuarios' | 'organizacoes' | 'cargos';
type DeleteTarget = { ids: string[]; names: string[]; type: 'user' | 'org' | 'role' };

interface CadastrosProps { initialMenu?: MenuOption }

const isMenuOption = (value: string | null): value is MenuOption =>
  value === 'usuarios' || value === 'organizacoes' || value === 'cargos';

export const Cadastros: React.FC<CadastrosProps> = ({ initialMenu = 'usuarios' }) => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const toast = useToast();
  const { hasPermission, user: currentUser } = usePermissions();
  const queryView = searchParams.get('view');
  const [activeMenu, setActiveMenu] = useState<MenuOption>(isMenuOption(queryView) ? queryView : initialMenu);
  const [searchTerm, setSearchTerm] = useState('');
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [selectedUserIds, setSelectedUserIds] = useState<string[]>([]);
  const [selectedOrgIds, setSelectedOrgIds] = useState<string[]>([]);
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [itemToDelete, setItemToDelete] = useState<DeleteTarget | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [orgsData, usersData, rolesData] = await Promise.all([
        identityService.getOrganizations(true).catch(() => []),
        identityService.getUsers(true).catch(() => []),
        identityService.getRoles(true).catch(() => []),
      ]);
      setOrganizations(orgsData); setUsers(usersData); setRoles(rolesData);
    } catch (loadError) {
      setError(formatApiError(loadError, 'Não foi possível carregar os cadastros.'));
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { void loadData(); }, [loadData]);
  useEffect(() => {
    if (isMenuOption(queryView) && queryView !== activeMenu) {
      setActiveMenu(queryView); setSearchTerm('');
    }
  }, [activeMenu, queryView]);

  const selectMenu = (menu: MenuOption) => {
    setActiveMenu(menu); setSearchTerm('');
    setSelectedUserIds([]); setSelectedOrgIds([]); setSelectedRoleIds([]);
    setSearchParams({ view: menu }, { replace: true });
  };

  const resourcePath = activeMenu === 'usuarios' ? 'usuarios' : activeMenu === 'organizacoes' ? 'organizacoes' : 'cargos';
  const openRecord = (id?: string) => navigate(buildRecordFormPath('cadastros', resourcePath, id));
  const canCreate = activeMenu === 'usuarios'
    ? hasPermission('users:create')
    : activeMenu === 'organizacoes' ? hasPermission('organizations:manage') : hasPermission('roles:manage');

  const term = searchTerm.toLocaleLowerCase('pt-BR').trim();
  const filteredUsers = useMemo(() => users.filter((user) => user.full_name.toLocaleLowerCase('pt-BR').includes(term) || user.email.toLocaleLowerCase('pt-BR').includes(term)), [term, users]);
  const filteredOrgs = useMemo(() => organizations.filter((org) => org.name.toLocaleLowerCase('pt-BR').includes(term)), [organizations, term]);
  const filteredRoles = useMemo(() => roles.filter((role) => role.name.toLocaleLowerCase('pt-BR').includes(term) || (role.description || '').toLocaleLowerCase('pt-BR').includes(term)), [roles, term]);
  const userPagination = useListPagination(filteredUsers);
  const orgPagination = useListPagination(filteredOrgs);
  const rolePagination = useListPagination(filteredRoles);

  const selectableUsers = userPagination.pageItems.filter((user) => user.id !== currentUser?.id);
  const allUsersSelected = selectableUsers.length > 0 && selectableUsers.every((user) => selectedUserIds.includes(user.id));
  const allOrgsSelected = orgPagination.pageItems.length > 0 && orgPagination.pageItems.every((org) => selectedOrgIds.includes(org.id));
  const allRolesSelected = rolePagination.pageItems.length > 0 && rolePagination.pageItems.every((role) => selectedRoleIds.includes(role.id));
  const toggleItem = (id: string, setter: React.Dispatch<React.SetStateAction<string[]>>) => setter((items) => items.includes(id) ? items.filter((item) => item !== id) : [...items, id]);
  const togglePage = <T extends { id: string }>(pageItems: T[], selected: string[], setter: React.Dispatch<React.SetStateAction<string[]>>) => {
    const allSelected = pageItems.length > 0 && pageItems.every((item) => selected.includes(item.id));
    setter((items) => allSelected ? items.filter((id) => !pageItems.some((item) => item.id === id)) : Array.from(new Set([...items, ...pageItems.map((item) => item.id)])));
  };

  const selectedCount = activeMenu === 'usuarios' ? selectedUserIds.length : activeMenu === 'organizacoes' ? selectedOrgIds.length : selectedRoleIds.length;
  const canBulkDelete = activeMenu === 'usuarios' ? hasPermission('users:delete') : activeMenu === 'organizacoes' ? hasPermission('organizations:manage') : hasPermission('roles:manage');
  const openBulkDelete = () => {
    if (activeMenu === 'usuarios' && selectedUserIds.length) setItemToDelete({ ids: selectedUserIds, names: users.filter((user) => selectedUserIds.includes(user.id)).map((user) => user.full_name), type: 'user' });
    if (activeMenu === 'organizacoes' && selectedOrgIds.length) setItemToDelete({ ids: selectedOrgIds, names: organizations.filter((org) => selectedOrgIds.includes(org.id)).map((org) => org.name), type: 'org' });
    if (activeMenu === 'cargos' && selectedRoleIds.length) setItemToDelete({ ids: selectedRoleIds, names: roles.filter((role) => selectedRoleIds.includes(role.id)).map((role) => role.name), type: 'role' });
  };

  const confirmDelete = async () => {
    if (!itemToDelete || isDeleting) return;
    setIsDeleting(true);
    try {
      if (itemToDelete.type === 'user') {
        if (itemToDelete.ids.length === 1) await identityService.deleteUser(itemToDelete.ids[0]);
        else await identityService.bulkDeleteUsers(itemToDelete.ids);
        setSelectedUserIds([]);
      } else if (itemToDelete.type === 'org') {
        if (itemToDelete.ids.length === 1) await identityService.deleteOrganization(itemToDelete.ids[0]);
        else await identityService.bulkDeleteOrganizations(itemToDelete.ids);
        setSelectedOrgIds([]);
      } else {
        if (itemToDelete.ids.length === 1) await identityService.deleteRole(itemToDelete.ids[0]);
        else await identityService.bulkDeleteRoles(itemToDelete.ids);
        setSelectedRoleIds([]);
      }
      setItemToDelete(null); await loadData(); toast.success('Exclusão realizada com sucesso.');
    } catch (deleteError) { toast.error(formatApiError(deleteError, 'Não foi possível excluir o(s) registro(s).')); }
    finally { setIsDeleting(false); }
  };

  const title = activeMenu === 'usuarios' ? 'Gestão de Usuários & Perfis' : activeMenu === 'organizacoes' ? 'Gestão de Organizações & Filiais' : 'Cargos e Matriz de Permissões';
  const subtitle = activeMenu === 'usuarios' ? 'Gerencie contas, status e papéis de acesso dos colaboradores' : activeMenu === 'organizacoes' ? 'Empresas, filiais e unidades de negócio do ecossistema' : 'Configure responsabilidades e permissões granulares por função';
  const createLabel = activeMenu === 'usuarios' ? 'Novo Usuário' : activeMenu === 'organizacoes' ? 'Nova Organização' : 'Novo Cargo';
  const countLabel = activeMenu === 'usuarios' ? `${filteredUsers.length} usuário(s)` : activeMenu === 'organizacoes' ? `${filteredOrgs.length} organização(ões)` : `${filteredRoles.length} cargo(s)`;

  return <div className="cadastros-page"><div className="cadastros-layout">
    <aside className="sidebar-left">
      <div className="sidebar-header"><span className="sidebar-section-title">Configurações Gerais</span></div>
      <nav className="sidebar-menu-list">
        {hasPermission('users:view') && <button type="button" className={`sidebar-menu-btn ${activeMenu === 'usuarios' ? 'active' : ''}`} onClick={() => selectMenu('usuarios')}><div className="btn-label"><Users size={16} className="icon-users" /><span>Usuários & Perfis</span></div><div className="btn-meta"><span className="count-badge">{users.length}</span><ChevronRight size={14} /></div></button>}
        {hasPermission('organizations:view') && <button type="button" className={`sidebar-menu-btn ${activeMenu === 'organizacoes' ? 'active' : ''}`} onClick={() => selectMenu('organizacoes')}><div className="btn-label"><Building2 size={16} className="icon-orgs" /><span>Organizações</span></div><div className="btn-meta"><span className="count-badge">{organizations.length}</span><ChevronRight size={14} /></div></button>}
        {hasPermission('roles:view') && <button type="button" className={`sidebar-menu-btn ${activeMenu === 'cargos' ? 'active' : ''}`} onClick={() => selectMenu('cargos')}><div className="btn-label"><Shield size={16} className="icon-roles" /><span>Cargos & Permissões</span></div><div className="btn-meta"><span className="count-badge">{roles.length}</span><ChevronRight size={14} /></div></button>}
      </nav>
    </aside>

    <main className="content-right">
      <header className="content-header"><div className="titles"><h1>{title}</h1><p>{subtitle}</p></div><div className="header-actions"><button className="btn-refresh" onClick={() => void loadData()} disabled={loading} title="Atualizar dados"><RefreshCw size={13} className={loading ? 'spin' : ''} /><span>Atualizar</span></button>{canCreate && <button className="btn-primary" onClick={() => openRecord()}><Plus size={14} /><span>{createLabel}</span></button>}</div></header>
      {error && <div className="alert-error">{error}</div>}
      <div className="table-card">
        <div className="table-toolbar"><div className="search-wrap"><Search size={14} /><input type="text" placeholder={`Buscar em ${title.toLocaleLowerCase('pt-BR')}...`} value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} /></div><div className="toolbar-right-actions">{selectedCount > 0 && canBulkDelete && <div className="bulk-actions-wrap"><span className="selected-count-badge">{selectedCount} selecionado(s)</span><button type="button" className="btn-bulk-delete" onClick={openBulkDelete}><Trash2 size={13} /><span>Excluir Selecionados</span></button></div>}<span className="results-count">{countLabel}</span></div></div>

        {activeMenu === 'usuarios' && (loading ? <div className="state-empty">Carregando usuários...</div> : filteredUsers.length === 0 ? <div className="state-empty">Nenhum usuário encontrado.</div> : <div className="table-responsive"><table className="enterprise-table"><thead><tr><th className="th-checkbox"><input type="checkbox" className="table-checkbox" checked={allUsersSelected} onChange={() => togglePage(selectableUsers, selectedUserIds, setSelectedUserIds)} disabled={!hasPermission('users:delete') || selectableUsers.length === 0} /></th><th>Colaborador</th><th>E-mail Corporativo</th><th>Status</th><th>Data de Cadastro</th><th style={{ textAlign: 'right' }}>Ações</th></tr></thead><tbody>{userPagination.pageItems.map((user) => {
          const self = user.id === currentUser?.id; const selected = selectedUserIds.includes(user.id); const canOpen = hasPermission('users:edit') || self;
          return <tr key={user.id} className={`${selected ? 'selected-row' : ''} ${canOpen ? 'ui-record-row' : ''}`} role={canOpen ? 'button' : undefined} tabIndex={canOpen ? 0 : undefined} onClick={(event) => { if (!(event.target as HTMLElement).closest('button, a, input, label') && canOpen) openRecord(user.id); }} onKeyDown={(event) => { if (canOpen && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); openRecord(user.id); } }}><td className="td-checkbox"><input type="checkbox" className="table-checkbox" checked={selected} onChange={() => toggleItem(user.id, setSelectedUserIds)} disabled={!hasPermission('users:delete') || self} /></td><td><div className={`cell-with-icon ${canOpen ? 'clickable' : ''}`}><div className="avatar-circle-sm">{(user.full_name || 'U').charAt(0).toUpperCase()}</div><div><strong>{user.full_name || 'Usuário sem nome'}</strong>{self && <span className="badge-self">Você</span>}</div></div></td><td><span className="email-text"><Mail size={12} />{user.email}</span></td><td><StatusBadge active={user.is_active} /></td><td>{new Date(user.created_at).toLocaleDateString('pt-BR')}</td><td style={{ textAlign: 'right' }}>{hasPermission('users:delete') && <button className="btn-action-icon delete" onClick={() => setItemToDelete({ ids: [user.id], names: [user.full_name], type: 'user' })} disabled={self} title="Excluir usuário"><Trash2 size={14} /></button>}</td></tr>;
        })}</tbody></table><ListPagination {...userPagination} onPageChange={userPagination.setPage} onPageSizeChange={userPagination.setPageSize} /></div>)}

        {activeMenu === 'organizacoes' && (loading ? <div className="state-empty">Carregando organizações...</div> : filteredOrgs.length === 0 ? <div className="state-empty">Nenhuma organização encontrada.</div> : <div className="table-responsive"><table className="enterprise-table"><thead><tr><th className="th-checkbox"><input type="checkbox" className="table-checkbox" checked={allOrgsSelected} onChange={() => togglePage(orgPagination.pageItems, selectedOrgIds, setSelectedOrgIds)} disabled={!hasPermission('organizations:manage')} /></th><th>Nome da Organização</th><th>Status</th><th>Data de Cadastro</th><th style={{ textAlign: 'right' }}>Ações</th></tr></thead><tbody>{orgPagination.pageItems.map((org) => { const selected = selectedOrgIds.includes(org.id); const canOpen = hasPermission('organizations:manage'); return <tr key={org.id} className={`${selected ? 'selected-row' : ''} ${canOpen ? 'ui-record-row' : ''}`} role={canOpen ? 'button' : undefined} tabIndex={canOpen ? 0 : undefined} onClick={(event) => { if (!(event.target as HTMLElement).closest('button, a, input, label') && canOpen) openRecord(org.id); }} onKeyDown={(event) => { if (canOpen && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); openRecord(org.id); } }}><td className="td-checkbox"><input type="checkbox" className="table-checkbox" checked={selected} onChange={() => toggleItem(org.id, setSelectedOrgIds)} disabled={!canOpen} /></td><td><div className={`cell-with-icon ${canOpen ? 'clickable' : ''}`}><div className="icon-badge brand-bg"><Building2 size={14} /></div><strong>{org.name}</strong></div></td><td><StatusBadge active={org.is_active} feminine /></td><td>{new Date(org.created_at).toLocaleDateString('pt-BR')}</td><td style={{ textAlign: 'right' }}>{canOpen && <button className="btn-action-icon delete" onClick={() => setItemToDelete({ ids: [org.id], names: [org.name], type: 'org' })} title="Excluir organização"><Trash2 size={14} /></button>}</td></tr>; })}</tbody></table><ListPagination {...orgPagination} onPageChange={orgPagination.setPage} onPageSizeChange={orgPagination.setPageSize} /></div>)}

        {activeMenu === 'cargos' && (loading ? <div className="state-empty">Carregando cargos...</div> : filteredRoles.length === 0 ? <div className="state-empty">Nenhum cargo encontrado.</div> : <div className="table-responsive"><table className="enterprise-table"><thead><tr><th className="th-checkbox"><input type="checkbox" className="table-checkbox" checked={allRolesSelected} onChange={() => togglePage(rolePagination.pageItems, selectedRoleIds, setSelectedRoleIds)} disabled={!hasPermission('roles:manage')} /></th><th>Nome do Cargo</th><th>Descrição</th><th>Permissões</th><th>Status</th><th style={{ textAlign: 'right' }}>Ações</th></tr></thead><tbody>{rolePagination.pageItems.map((role) => { const selected = selectedRoleIds.includes(role.id); const canOpen = hasPermission('roles:manage'); return <tr key={role.id} className={`${selected ? 'selected-row' : ''} ${canOpen ? 'ui-record-row' : ''}`} role={canOpen ? 'button' : undefined} tabIndex={canOpen ? 0 : undefined} onClick={(event) => { if (!(event.target as HTMLElement).closest('button, a, input, label') && canOpen) openRecord(role.id); }} onKeyDown={(event) => { if (canOpen && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); openRecord(role.id); } }}><td className="td-checkbox"><input type="checkbox" className="table-checkbox" checked={selected} onChange={() => toggleItem(role.id, setSelectedRoleIds)} disabled={!canOpen} /></td><td><div className={`cell-with-icon ${canOpen ? 'clickable' : ''}`}><div className="icon-badge purple-bg"><Shield size={14} /></div><strong>{role.name}</strong></div></td><td><span className="role-desc-text">{role.description || 'Sem descrição cadastrada'}</span></td><td><span className="badge-permissions-btn"><Shield size={12} /><span>{role.permissions?.length || 0} permissões</span></span></td><td><StatusBadge active={role.is_active} /></td><td style={{ textAlign: 'right' }}>{canOpen && <button className="btn-action-icon delete" onClick={() => setItemToDelete({ ids: [role.id], names: [role.name], type: 'role' })} title="Excluir cargo"><Trash2 size={14} /></button>}</td></tr>; })}</tbody></table><ListPagination {...rolePagination} onPageChange={rolePagination.setPage} onPageSizeChange={rolePagination.setPageSize} /></div>)}
      </div>
    </main>
  </div>
  <ConfirmModal isOpen={Boolean(itemToDelete)} onClose={() => setItemToDelete(null)} onConfirm={confirmDelete} title="Confirmar exclusão" subtitle="Esta ação não pode ser desfeita" message={itemToDelete?.ids.length === 1 ? <>Deseja excluir permanentemente <strong>{itemToDelete.names[0]}</strong>?</> : <>Deseja excluir permanentemente os <strong>{itemToDelete?.ids.length || 0} registros selecionados</strong>?</>} confirmText="Excluir" type="danger" isLoading={isDeleting} />
  </div>;
};

function StatusBadge({ active, feminine = false }: { active: boolean; feminine?: boolean }) {
  return <span className={`badge-pill ${active ? 'active' : 'inactive'}`}>{active ? <CheckCircle2 size={11} /> : <XCircle size={11} />}{active ? (feminine ? 'Ativa' : 'Ativo') : (feminine ? 'Inativa' : 'Inativo')}</span>;
}

export default Cadastros;
