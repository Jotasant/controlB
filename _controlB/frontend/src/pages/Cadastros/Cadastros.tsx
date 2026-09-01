/**
 * pages/Cadastros/Cadastros.tsx - Central de Configurações, Organizações, Usuários e Perfis de Acesso (RBAC)
 * 
 * Permite gerenciar de forma integrada:
 * 1. 🏢 Organizações (Empresas e Filiais: Criação, Edição, Seleção em Lote e Exclusão)
 * 2. 👥 Usuários (Perfis, Permissões, Status, Seleção em Lote e Desvinculação)
 * 3. 🛡️ Cargos (Matriz de Permissões de Acesso, Seleção em Lote e Exclusão)
 */

import React, { useEffect, useState } from 'react';
import { 
  Building2, Users, Shield, ChevronRight, 
  Search, CheckCircle2, XCircle, RefreshCw, Plus, Mail,
  Loader2, AlertCircle, Trash2, ShieldAlert
} from 'lucide-react';
import { identityService, authService, formatApiError } from '@/services/api';
import { User, Role, Organization, Permission } from '@/types';
import { Modal } from '@/components/Modal/Modal';
import { usePermissions } from '@/hooks/usePermissions';
import { useListPagination } from '@/hooks/useListPagination';
import { ListPagination } from '@/components/ListPagination';
import './Cadastros.scss';

type MenuOption = 'usuarios' | 'organizacoes' | 'cargos';

interface CadastrosProps {
  initialMenu?: MenuOption;
}

export const Cadastros: React.FC<CadastrosProps> = ({ initialMenu = 'usuarios' }) => {
  const { hasPermission } = usePermissions();

  const [activeMenu, setActiveMenu] = useState<MenuOption>(initialMenu);
  const [searchTerm, setSearchTerm] = useState('');

  // Estados dos Dados carregados da API
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);

  // Estados de Seleção Múltipla (Flags para Selecionar Tudo e Excluir em Lote)
  const [selectedUserIds, setSelectedUserIds] = useState<string[]>([]);
  const [selectedOrgIds, setSelectedOrgIds] = useState<string[]>([]);
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([]);

  // Estados de Carregamento
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // =========================================================================
  // ESTADOS DO MODAL DE CRIAÇÃO (WIZARD)
  // =========================================================================
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // Campos de Criação
  const [userFullName, setUserFullName] = useState('');
  const [userEmail, setUserEmail] = useState('');
  const [userPassword, setUserPassword] = useState('');
  const [userOrgId, setUserOrgId] = useState('');
  const [userRoleId, setUserRoleId] = useState('');
  const [orgName, setOrgName] = useState('');
  const [roleName, setRoleName] = useState('');
  const [roleDescription, setRoleDescription] = useState('');
  const [selectedPermissionIds, setSelectedPermissionIds] = useState<string[]>([]);

  // =========================================================================
  // ESTADOS DO MODAL DE EDIÇÃO DE ORGANIZAÇÃO
  // =========================================================================
  const [selectedOrg, setSelectedOrg] = useState<Organization | null>(null);
  const [isOrgModalOpen, setIsOrgModalOpen] = useState(false);
  const [editOrgName, setEditOrgName] = useState('');
  const [editOrgIsActive, setEditOrgIsActive] = useState(true);

  // =========================================================================
  // ESTADOS DO MODAL DE PERFIL / EDIÇÃO DE USUÁRIO
  // =========================================================================
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [isProfileModalOpen, setIsProfileModalOpen] = useState(false);
  const [editFullName, setEditFullName] = useState('');
  const [editEmail, setEditEmail] = useState('');
  const [editOrgId, setEditOrgId] = useState('');
  const [editRoleId, setEditRoleId] = useState('');
  const [editIsActive, setEditIsActive] = useState(true);
  const [editNewPassword, setEditNewPassword] = useState('');

  // =========================================================================
  // ESTADOS DO MODAL DE EDIÇÃO DE CARGO & MATRIZ DE PERMISSÕES
  // =========================================================================
  const [selectedRole, setSelectedRole] = useState<Role | null>(null);
  const [isRoleModalOpen, setIsRoleModalOpen] = useState(false);
  const [editRoleName, setEditRoleName] = useState('');
  const [editRoleDescription, setEditRoleDescription] = useState('');
  const [editRolePermissionIds, setEditRolePermissionIds] = useState<string[]>([]);

  // =========================================================================
  // ESTADO DO MODAL DE CONFIRMAÇÃO DE EXCLUSÃO (INDIVIDUAL OU EM LOTE)
  // =========================================================================
  const [itemToDelete, setItemToDelete] = useState<{ 
    ids: string[]; 
    names: string[]; 
    type: 'user' | 'org' | 'role' 
  } | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const currentUserEmail = authService.getUserEmail();

  // 1. Busca todos os dados da API em paralelo com tratamento de erros
  const loadData = async () => {
    setLoading(true);
    setError(null);

    try {
      const [
        orgsData, usersData, rolesData, permsData
      ] = await Promise.all([
        identityService.getOrganizations().catch(() => []),
        identityService.getUsers().catch(() => []),
        identityService.getRoles().catch(() => []),
        identityService.getPermissions().catch(() => []),
      ]);

      setOrganizations(Array.isArray(orgsData) ? orgsData : []);
      setUsers(Array.isArray(usersData) ? usersData : []);
      setRoles(Array.isArray(rolesData) ? rolesData : []);
      setPermissions(Array.isArray(permsData) ? permsData : []);
    } catch (err: any) {
      console.error('Erro ao carregar dados de configurações:', err);
      setError('Não foi possível se comunicar com o backend.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSelectMenu = (menu: MenuOption) => {
    setActiveMenu(menu);
    setSearchTerm('');
    setSelectedUserIds([]);
    setSelectedOrgIds([]);
    setSelectedRoleIds([]);
  };

  // Abre modal de criação e limpa os campos
  const handleOpenCreateModal = () => {
    setModalError(null);
    setUserFullName('');
    setUserEmail('');
    setUserPassword('');
    setUserOrgId(organizations[0]?.id || '');
    setUserRoleId(roles[0]?.id || '');
    setOrgName('');
    setRoleName('');
    setRoleDescription('');
    setSelectedPermissionIds([]);
    setIsModalOpen(true);
  };

  // Abre o modal de Edição de Organização
  const handleOpenOrgEdit = (org: Organization) => {
    setSelectedOrg(org);
    setEditOrgName(org.name);
    setEditOrgIsActive(org.is_active);
    setModalError(null);
    setIsOrgModalOpen(true);
  };

  // Abre o modal de Perfil do Usuário
  const handleOpenUserProfile = (user: User) => {
    setSelectedUser(user);
    setEditFullName(user.full_name);
    setEditEmail(user.email);
    setEditOrgId(user.organization_id || '');
    setEditRoleId(user.role_id || '');
    setEditIsActive(user.is_active);
    setEditNewPassword('');
    setModalError(null);
    setIsProfileModalOpen(true);
  };

  // Abre o modal de Edição de Cargo com Matriz de Permissões
  const handleOpenRoleEdit = (role: Role) => {
    setSelectedRole(role);
    setEditRoleName(role.name);
    setEditRoleDescription(role.description || '');
    setEditRolePermissionIds(role.permissions?.map(p => p.id) || []);
    setModalError(null);
    setIsRoleModalOpen(true);
  };

  const togglePermission = (permId: string, currentList: string[], setList: React.Dispatch<React.SetStateAction<string[]>>) => {
    if (currentList.includes(permId)) {
      setList(currentList.filter(id => id !== permId));
    } else {
      setList([...currentList, permId]);
    }
  };

  // 2. Submissão de Criação de Registro
  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSaving) return;

    setIsSaving(true);
    setModalError(null);

    try {
      if (activeMenu === 'organizacoes') {
        if (!orgName.trim()) throw new Error('O nome da organização é obrigatório.');
        await identityService.createOrganization(orgName.trim());
      } 
      else if (activeMenu === 'usuarios') {
        if (!userFullName.trim() || !userEmail.trim() || !userPassword) {
          throw new Error('Preencha todos os campos obrigatórios do usuário.');
        }
        await identityService.createUser({
          full_name: userFullName.trim(),
          email: userEmail.trim(),
          password: userPassword,
          organization_id: userOrgId || undefined,
          role_id: userRoleId || undefined,
        });
      } 
      else if (activeMenu === 'cargos') {
        if (!roleName.trim()) throw new Error('O nome do cargo é obrigatório.');
        await identityService.createRole(
          roleName.trim(),
          roleDescription.trim(),
          organizations[0]?.id || '00000000-0000-0000-0000-000000000000',
          selectedPermissionIds
        );
      }

      setIsModalOpen(false);
      await loadData();
    } catch (err: any) {
      setModalError(formatApiError(err, 'Erro ao salvar o registro no servidor.'));
    } finally {
      setIsSaving(false);
    }
  };

  // 3. Salvar Edição de Organização
  const handleSaveOrg = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedOrg || isSaving) return;

    setIsSaving(true);
    setModalError(null);

    try {
      if (!editOrgName.trim()) throw new Error('O nome da organização é obrigatório.');
      await identityService.updateOrganization(selectedOrg.id, {
        name: editOrgName.trim(),
        is_active: editOrgIsActive
      });

      setIsOrgModalOpen(false);
      await loadData();
    } catch (err: any) {
      setModalError(formatApiError(err, 'Erro ao atualizar os dados da organização.'));
    } finally {
      setIsSaving(false);
    }
  };

  // 4. Salvar Edição de Perfil do Usuário
  const handleSaveUserProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedUser || isSaving) return;

    setIsSaving(true);
    setModalError(null);

    try {
      await identityService.updateUser(selectedUser.id, {
        full_name: editFullName.trim(),
        email: editEmail.trim(),
        organization_id: editOrgId || undefined,
        role_id: editRoleId || undefined,
        is_active: editIsActive,
        password: editNewPassword.trim() ? editNewPassword : undefined,
      });

      setIsProfileModalOpen(false);
      await loadData();
    } catch (err: any) {
      setModalError(formatApiError(err, 'Erro ao atualizar o perfil do usuário.'));
    } finally {
      setIsSaving(false);
    }
  };

  // 5. Salvar Edição de Cargo & Permissões
  const handleSaveRole = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRole || isSaving) return;

    setIsSaving(true);
    setModalError(null);

    try {
      await identityService.updateRole(selectedRole.id, {
        name: editRoleName.trim(),
        description: editRoleDescription.trim(),
        permission_ids: editRolePermissionIds
      });

      setIsRoleModalOpen(false);
      await loadData();
    } catch (err: any) {
      setModalError(
        err.response?.data?.detail || err.message || 'Erro ao atualizar o cargo e permissões.'
      );
    } finally {
      setIsSaving(false);
    }
  };

  // 6. Executar Exclusão Confirmada (Individual ou em Lote)
  const handleConfirmDelete = async () => {
    if (!itemToDelete || isDeleting) return;

    setIsDeleting(true);
    try {
      if (itemToDelete.type === 'user') {
        if (itemToDelete.ids.length === 1) {
          await identityService.deleteUser(itemToDelete.ids[0]);
        } else {
          await identityService.bulkDeleteUsers(itemToDelete.ids);
        }
        setSelectedUserIds([]);
        if (selectedUser && itemToDelete.ids.includes(selectedUser.id)) {
          setIsProfileModalOpen(false);
        }
      } else if (itemToDelete.type === 'org') {
        if (itemToDelete.ids.length === 1) {
          await identityService.deleteOrganization(itemToDelete.ids[0]);
        } else {
          await identityService.bulkDeleteOrganizations(itemToDelete.ids);
        }
        setSelectedOrgIds([]);
        if (selectedOrg && itemToDelete.ids.includes(selectedOrg.id)) {
          setIsOrgModalOpen(false);
        }
      } else if (itemToDelete.type === 'role') {
        if (itemToDelete.ids.length === 1) {
          await identityService.deleteRole(itemToDelete.ids[0]);
        } else {
          await identityService.bulkDeleteRoles(itemToDelete.ids);
        }
        setSelectedRoleIds([]);
        if (selectedRole && itemToDelete.ids.includes(selectedRole.id)) {
          setIsRoleModalOpen(false);
        }
      }

      setItemToDelete(null);
      await loadData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Erro ao excluir o(s) registro(s).');
    } finally {
      setIsDeleting(false);
    }
  };

  // Agrupamento de permissões por Módulo (com verificação defensiva)
  const safePermissions = Array.isArray(permissions) ? permissions : [];
  const permissionsByModule = safePermissions.reduce((acc, perm) => {
    if (!perm || !perm.module) return acc;
    if (!acc[perm.module]) acc[perm.module] = [];
    acc[perm.module].push(perm);
    return acc;
  }, {} as Record<string, Permission[]>);

  // Filtros de busca defensivos
  const term = (searchTerm || '').toLowerCase().trim();

  const safeOrgs = Array.isArray(organizations) ? organizations : [];
  const filteredOrgs = safeOrgs.filter(o =>
    (o?.name || '').toLowerCase().includes(term)
  );

  const safeUsers = Array.isArray(users) ? users : [];
  const filteredUsers = safeUsers.filter(u =>
    (u?.full_name || '').toLowerCase().includes(term) ||
    (u?.email || '').toLowerCase().includes(term)
  );

  const safeRoles = Array.isArray(roles) ? roles : [];
  const filteredRoles = safeRoles.filter(r =>
    (r?.name || '').toLowerCase().includes(term) ||
    ((r?.description || '').toLowerCase().includes(term))
  );
  const userPagination = useListPagination(filteredUsers);
  const orgPagination = useListPagination(filteredOrgs);
  const rolePagination = useListPagination(filteredRoles);

  // =========================================================================
  // LÓGICA DE SELEÇÃO MÚLTIPLA E BOTÃO "SELECIONAR TUDO"
  // =========================================================================

  // 👥 Usuários
  const selectableUsers = userPagination.pageItems.filter(u => u.email !== currentUserEmail);
  const isAllUsersSelected = selectableUsers.length > 0 && selectableUsers.every(u => selectedUserIds.includes(u.id));
  const toggleSelectAllUsers = () => {
    if (isAllUsersSelected) {
      setSelectedUserIds(previous => previous.filter(id => !selectableUsers.some(user => user.id === id)));
    } else {
      setSelectedUserIds(previous => Array.from(new Set([...previous, ...selectableUsers.map(user => user.id)])));
    }
  };
  const toggleSelectUser = (userId: string) => {
    setSelectedUserIds(prev => 
      prev.includes(userId) ? prev.filter(id => id !== userId) : [...prev, userId]
    );
  };

  // 🏢 Organizações
  const isAllOrgsSelected = orgPagination.pageItems.length > 0 && orgPagination.pageItems.every(o => selectedOrgIds.includes(o.id));
  const toggleSelectAllOrgs = () => {
    if (isAllOrgsSelected) {
      setSelectedOrgIds(previous => previous.filter(id => !orgPagination.pageItems.some(org => org.id === id)));
    } else {
      setSelectedOrgIds(previous => Array.from(new Set([...previous, ...orgPagination.pageItems.map(org => org.id)])));
    }
  };
  const toggleSelectOrg = (orgId: string) => {
    setSelectedOrgIds(prev => 
      prev.includes(orgId) ? prev.filter(id => id !== orgId) : [...prev, orgId]
    );
  };

  // 🛡️ Cargos
  const isAllRolesSelected = rolePagination.pageItems.length > 0 && rolePagination.pageItems.every(r => selectedRoleIds.includes(r.id));
  const toggleSelectAllRoles = () => {
    if (isAllRolesSelected) {
      setSelectedRoleIds(previous => previous.filter(id => !rolePagination.pageItems.some(role => role.id === id)));
    } else {
      setSelectedRoleIds(previous => Array.from(new Set([...previous, ...rolePagination.pageItems.map(role => role.id)])));
    }
  };
  const toggleSelectRole = (roleId: string) => {
    setSelectedRoleIds(prev => 
      prev.includes(roleId) ? prev.filter(id => id !== roleId) : [...prev, roleId]
    );
  };

  // Disparo de Exclusão em Lote
  const handleOpenBulkDelete = () => {
    if (activeMenu === 'usuarios' && selectedUserIds.length > 0) {
      const names = users.filter(u => selectedUserIds.includes(u.id)).map(u => u.full_name);
      setItemToDelete({ ids: selectedUserIds, names, type: 'user' });
    } else if (activeMenu === 'organizacoes' && selectedOrgIds.length > 0) {
      const names = organizations.filter(o => selectedOrgIds.includes(o.id)).map(o => o.name);
      setItemToDelete({ ids: selectedOrgIds, names, type: 'org' });
    } else if (activeMenu === 'cargos' && selectedRoleIds.length > 0) {
      const names = roles.filter(r => selectedRoleIds.includes(r.id)).map(r => r.name);
      setItemToDelete({ ids: selectedRoleIds, names, type: 'role' });
    }
  };

  // Helpers de Rótulos de UI
  const getMenuTitle = () => {
    switch (activeMenu) {
      case 'usuarios': return 'Gestão de Usuários & Perfis';
      case 'organizacoes': return 'Gestão de Organizações & Filiais';
      case 'cargos': return 'Cargos e Matriz de Permissões';
    }
  };

  const getMenuSubtitle = () => {
    switch (activeMenu) {
      case 'usuarios': return 'Gerencie contas de colaboradores, status de acesso e papéis de permissão';
      case 'organizacoes': return 'Empresas, filiais e unidades de negócio cadastradas no ecossistema';
      case 'cargos': return 'Configure os níveis de acesso e matriz de permissões granulares por função';
    }
  };

  const getButtonLabel = () => {
    switch (activeMenu) {
      case 'usuarios': return 'Novo Usuário';
      case 'organizacoes': return 'Nova Organização';
      case 'cargos': return 'Novo Cargo';
    }
  };

  const getSearchPlaceholder = () => {
    switch (activeMenu) {
      case 'usuarios': return 'Buscar usuário por nome ou e-mail...';
      case 'organizacoes': return 'Buscar organização...';
      case 'cargos': return 'Buscar cargo...';
    }
  };

  const getCountLabel = () => {
    switch (activeMenu) {
      case 'usuarios': return `${filteredUsers.length} usuário(s)`;
      case 'organizacoes': return `${filteredOrgs.length} organização(ões)`;
      case 'cargos': return `${filteredRoles.length} cargo(s)`;
    }
  };

  const currentSelectedCount = 
    activeMenu === 'usuarios' ? selectedUserIds.length :
    activeMenu === 'organizacoes' ? selectedOrgIds.length :
    selectedRoleIds.length;

  return (
    <div className="cadastros-page">
      <div className="cadastros-layout">
        
        {/* ========================================================= */}
        {/* 1. BARRA LATERAL ESQUERDA (Sidebar Protegida por RBAC)    */}
        {/* ========================================================= */}
        <aside className="sidebar-left">
          <div className="sidebar-header">
            <span className="sidebar-section-title">Configurações Gerais</span>
          </div>

          <nav className="sidebar-menu-list">
            {/* 1. Usuários */}
            {hasPermission('users:view') && (
              <button
                type="button"
                className={`sidebar-menu-btn ${activeMenu === 'usuarios' ? 'active' : ''}`}
                onClick={() => handleSelectMenu('usuarios')}
              >
                <div className="btn-label">
                  <Users size={16} className="icon-users" />
                  <span>Usuários & Perfis</span>
                </div>
                <div className="btn-end">
                  <span className="count-pill">{safeUsers.length}</span>
                  <ChevronRight size={14} className="arrow" />
                </div>
              </button>
            )}

            {/* 2. Organizações */}
            {hasPermission('organizations:view') && (
              <button
                type="button"
                className={`sidebar-menu-btn ${activeMenu === 'organizacoes' ? 'active' : ''}`}
                onClick={() => handleSelectMenu('organizacoes')}
              >
                <div className="btn-label">
                  <Building2 size={16} className="icon-org" />
                  <span>Organizações & Filiais</span>
                </div>
                <div className="btn-end">
                  <span className="count-pill">{safeOrgs.length}</span>
                  <ChevronRight size={14} className="arrow" />
                </div>
              </button>
            )}

            {/* 3. Cargos e Permissões */}
            {hasPermission('roles:view') && (
              <button
                type="button"
                className={`sidebar-menu-btn ${activeMenu === 'cargos' ? 'active' : ''}`}
                onClick={() => handleSelectMenu('cargos')}
              >
                <div className="btn-label">
                  <Shield size={16} className="icon-roles" />
                  <span>Cargos e Permissões</span>
                </div>
                <div className="btn-end">
                  <span className="count-pill">{safeRoles.length}</span>
                  <ChevronRight size={14} className="arrow" />
                </div>
              </button>
            )}
          </nav>
        </aside>

        {/* ========================================================= */}
        {/* 2. ÁREA DE CONTEÚDO PRINCIPAL                             */}
        {/* ========================================================= */}
        <main className="content-right">
          
          <header className="content-header">
            <div className="titles">
              <h1>{getMenuTitle()}</h1>
              <p>{getMenuSubtitle()}</p>
            </div>

            <div className="header-actions">
              <button className="btn-refresh" onClick={loadData} disabled={loading} title="Atualizar Dados">
                <RefreshCw size={13} className={loading ? 'spin' : ''} />
                <span>Atualizar</span>
              </button>

              <button className="btn-primary" onClick={handleOpenCreateModal}>
                <Plus size={14} />
                <span>{getButtonLabel()}</span>
              </button>
            </div>
          </header>

          {error && <div className="alert-error">{error}</div>}

          {/* Painel com Toolbar de Busca e Ações em Lote */}
          <div className="table-card">
            <div className="table-toolbar">
              <div className="search-wrap">
                <Search size={14} />
                <input
                  type="text"
                  placeholder={getSearchPlaceholder()}
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>

              <div className="toolbar-right-actions">
                {currentSelectedCount > 0 && (
                  <div className="bulk-actions-wrap">
                    <span className="selected-count-badge">
                      {currentSelectedCount} selecionado(s)
                    </span>
                    <button 
                      type="button" 
                      className="btn-bulk-delete" 
                      onClick={handleOpenBulkDelete}
                      title="Excluir todos os itens selecionados"
                    >
                      <Trash2 size={13} />
                      <span>Excluir Selecionados</span>
                    </button>
                  </div>
                )}

                <span className="results-count">{getCountLabel()}</span>
              </div>
            </div>

            {/* TABELA: USUÁRIOS */}
            {activeMenu === 'usuarios' && (
              loading ? (
                <div className="state-empty">Carregando usuários...</div>
              ) : filteredUsers.length === 0 ? (
                <div className="state-empty">Nenhum usuário encontrado.</div>
              ) : (
                <div className="table-responsive">
                  <table className="enterprise-table">
                    <thead>
                      <tr>
                        <th className="th-checkbox">
                          <input 
                            type="checkbox" 
                            className="table-checkbox"
                            checked={isAllUsersSelected} 
                            onChange={toggleSelectAllUsers}
                            disabled={selectableUsers.length === 0}
                            title="Selecionar Todos os Usuários"
                          />
                        </th>
                        <th>Colaborador</th>
                        <th>E-mail Corporativo</th>
                        <th>Status</th>
                        <th>Data de Cadastro</th>
                        <th style={{ textAlign: 'right' }}>Ações / Perfil</th>
                      </tr>
                    </thead>
                    <tbody>
                      {userPagination.pageItems.map(user => {
                        const isSelf = user.email === currentUserEmail;
                        const isSelected = selectedUserIds.includes(user.id);
                        return (
                          <tr key={user.id} className={`${isSelected ? 'selected-row' : ''} ${(hasPermission('users:edit') || isSelf) ? 'ui-record-row' : ''}`} role={(hasPermission('users:edit') || isSelf) ? 'button' : undefined} tabIndex={(hasPermission('users:edit') || isSelf) ? 0 : undefined} onClick={(event) => { if (!(event.target as HTMLElement).closest('button, a, input, label') && (hasPermission('users:edit') || isSelf)) handleOpenUserProfile(user); }} onKeyDown={(event) => { if (['Enter', ' '].includes(event.key) && (hasPermission('users:edit') || isSelf)) { event.preventDefault(); handleOpenUserProfile(user); } }}>
                            <td className="td-checkbox">
                              <input 
                                type="checkbox" 
                                className="table-checkbox"
                                checked={isSelected} 
                                onChange={() => toggleSelectUser(user.id)}
                                disabled={isSelf}
                                title={isSelf ? 'Você não pode selecionar sua própria conta para exclusão' : 'Selecionar usuário'}
                              />
                            </td>
                            <td>
                              <div 
                                className="cell-with-icon clickable" 
                                onClick={() => (hasPermission('users:edit') || isSelf) && handleOpenUserProfile(user)}
                                title="Clique para abrir o perfil do usuário"
                              >
                                <div className="avatar-circle-sm">
                                  {(user?.full_name || 'U').charAt(0).toUpperCase()}
                                </div>
                                <div>
                                  <strong>{user?.full_name || 'Usuário sem nome'}</strong>
                                  {isSelf && <span className="badge-self">Você</span>}
                                </div>
                              </div>
                            </td>
                            <td>
                              <span className="email-text">
                                <Mail size={12} />
                                {user?.email || '-'}
                              </span>
                            </td>
                            <td>
                              <span className={`badge-pill ${user?.is_active ? 'active' : 'inactive'}`}>
                                {user?.is_active ? <CheckCircle2 size={11} /> : <XCircle size={11} />}
                                {user?.is_active ? 'Ativo' : 'Inativo'}
                              </span>
                            </td>
                            <td>{user?.created_at ? new Date(user.created_at).toLocaleDateString('pt-BR') : '-'}</td>
                            <td style={{ textAlign: 'right' }}>
                              <div className="row-actions">
                                {hasPermission('users:delete') && (
                                  <button
                                    className="btn-action-icon delete"
                                    onClick={() => setItemToDelete({ ids: [user.id], names: [user.full_name], type: 'user' })}
                                    disabled={isSelf}
                                    title={isSelf ? 'Você não pode excluir sua própria conta' : 'Desvincular / Excluir Usuário'}
                                  >
                                    <Trash2 size={14} />
                                  </button>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                  <ListPagination {...userPagination} onPageChange={userPagination.setPage} onPageSizeChange={userPagination.setPageSize} />
                </div>
              )
            )}

            {/* TABELA: ORGANIZAÇÕES */}
            {activeMenu === 'organizacoes' && (
              loading ? (
                <div className="state-empty">Carregando organizações...</div>
              ) : filteredOrgs.length === 0 ? (
                <div className="state-empty">Nenhuma organização encontrada.</div>
              ) : (
                <div className="table-responsive">
                  <table className="enterprise-table">
                    <thead>
                      <tr>
                        <th className="th-checkbox">
                          <input 
                            type="checkbox" 
                            className="table-checkbox"
                            checked={isAllOrgsSelected} 
                            onChange={toggleSelectAllOrgs}
                            title="Selecionar Todas as Organizações"
                          />
                        </th>
                        <th>Nome da Organização</th>
                        <th>Status</th>
                        <th>Data de Cadastro</th>
                        <th style={{ textAlign: 'right' }}>Ações</th>
                      </tr>
                    </thead>
                    <tbody>
                      {orgPagination.pageItems.map(org => {
                        const isSelected = selectedOrgIds.includes(org.id);
                        return (
                          <tr key={org.id} className={`${isSelected ? 'selected-row' : ''} ${hasPermission('organizations:manage') ? 'ui-record-row' : ''}`} role={hasPermission('organizations:manage') ? 'button' : undefined} tabIndex={hasPermission('organizations:manage') ? 0 : undefined} onClick={(event) => { if (!(event.target as HTMLElement).closest('button, a, input, label') && hasPermission('organizations:manage')) handleOpenOrgEdit(org); }} onKeyDown={(event) => { if (['Enter', ' '].includes(event.key) && hasPermission('organizations:manage')) { event.preventDefault(); handleOpenOrgEdit(org); } }}>
                            <td className="td-checkbox">
                              <input 
                                type="checkbox" 
                                className="table-checkbox"
                                checked={isSelected} 
                                onChange={() => toggleSelectOrg(org.id)}
                                title="Selecionar organização"
                              />
                            </td>
                            <td>
                              <div 
                                className={`cell-with-icon ${hasPermission('organizations:manage') ? 'clickable' : ''}`}
                                onClick={() => hasPermission('organizations:manage') && handleOpenOrgEdit(org)}
                                title="Clique para editar a organização"
                              >
                                <div className="icon-badge brand-bg">
                                  <Building2 size={14} />
                                </div>
                                <strong>{org.name}</strong>
                              </div>
                            </td>
                            <td>
                              <span className={`badge-pill ${org.is_active ? 'active' : 'inactive'}`}>
                                {org.is_active ? <CheckCircle2 size={11} /> : <XCircle size={11} />}
                                {org.is_active ? 'Ativa' : 'Inativa'}
                              </span>
                            </td>
                            <td>{org?.created_at ? new Date(org.created_at).toLocaleDateString('pt-BR') : '-'}</td>
                            <td style={{ textAlign: 'right' }}>
                              {hasPermission('organizations:manage') && (
                                <div className="row-actions">
                                  <button
                                    className="btn-action-icon delete"
                                    onClick={() => setItemToDelete({ ids: [org.id], names: [org.name], type: 'org' })}
                                    title="Excluir Organização"
                                  >
                                    <Trash2 size={14} />
                                  </button>
                                </div>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                  <ListPagination {...orgPagination} onPageChange={orgPagination.setPage} onPageSizeChange={orgPagination.setPageSize} />
                </div>
              )
            )}

            {/* TABELA: CARGOS & PERMISSÕES */}
            {activeMenu === 'cargos' && (
              loading ? (
                <div className="state-empty">Carregando cargos...</div>
              ) : filteredRoles.length === 0 ? (
                <div className="state-empty">Nenhum cargo encontrado.</div>
              ) : (
                <div className="table-responsive">
                  <table className="enterprise-table">
                    <thead>
                      <tr>
                        <th className="th-checkbox">
                          <input 
                            type="checkbox" 
                            className="table-checkbox"
                            checked={isAllRolesSelected} 
                            onChange={toggleSelectAllRoles}
                            title="Selecionar Todos os Cargos"
                          />
                        </th>
                        <th>Nome do Cargo</th>
                        <th>Descrição da Função</th>
                        <th>Permissões Atribuídas</th>
                        <th>Status</th>
                        <th style={{ textAlign: 'right' }}>Ações</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rolePagination.pageItems.map(role => {
                        const isSelected = selectedRoleIds.includes(role.id);
                        return (
                          <tr key={role.id} className={`${isSelected ? 'selected-row' : ''} ${hasPermission('roles:manage') ? 'ui-record-row' : ''}`} role={hasPermission('roles:manage') ? 'button' : undefined} tabIndex={hasPermission('roles:manage') ? 0 : undefined} onClick={(event) => { if (!(event.target as HTMLElement).closest('button, a, input, label') && hasPermission('roles:manage')) handleOpenRoleEdit(role); }} onKeyDown={(event) => { if (['Enter', ' '].includes(event.key) && hasPermission('roles:manage')) { event.preventDefault(); handleOpenRoleEdit(role); } }}>
                            <td className="td-checkbox">
                              <input 
                                type="checkbox" 
                                className="table-checkbox"
                                checked={isSelected} 
                                onChange={() => toggleSelectRole(role.id)}
                                title="Selecionar cargo"
                              />
                            </td>
                            <td>
                              <div 
                                className={`cell-with-icon ${hasPermission('roles:manage') ? 'clickable' : ''}`}
                                onClick={() => hasPermission('roles:manage') && handleOpenRoleEdit(role)}
                              >
                                <div className="icon-badge purple-bg">
                                  <Shield size={14} />
                                </div>
                                <strong>{role.name}</strong>
                              </div>
                            </td>
                            <td>
                              <span className="role-desc-text">
                                {role.description || 'Sem descrição cadastrada'}
                              </span>
                            </td>
                            <td>
                              <button 
                                type="button" 
                                className="badge-permissions-btn"
                                onClick={() => hasPermission('roles:manage') && handleOpenRoleEdit(role)}
                                disabled={!hasPermission('roles:manage')}
                                title="Configurar matriz de permissões"
                              >
                                <Shield size={12} />
                                <span>{role.permissions?.length || 0} permissões</span>
                              </button>
                            </td>
                            <td>
                              <span className={`badge-pill ${role.is_active ? 'active' : 'inactive'}`}>
                                {role.is_active ? <CheckCircle2 size={11} /> : <XCircle size={11} />}
                                {role.is_active ? 'Ativo' : 'Inativo'}
                              </span>
                            </td>
                            <td style={{ textAlign: 'right' }}>
                              {hasPermission('roles:manage') && (
                                <div className="row-actions">
                                  <button
                                    className="btn-action-icon delete"
                                    onClick={() => setItemToDelete({ ids: [role.id], names: [role.name], type: 'role' })}
                                    title="Excluir Cargo"
                                  >
                                    <Trash2 size={14} />
                                  </button>
                                </div>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                  <ListPagination {...rolePagination} onPageChange={rolePagination.setPage} onPageSizeChange={rolePagination.setPageSize} />
                </div>
              )
            )}

          </div>
        </main>
      </div>

      {/* ============================================================= */}
      {/* 3. MODAL DE CRIAÇÃO (WIZARD DE NOVO CADASTRO)                 */}
      {/* ============================================================= */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => !isSaving && setIsModalOpen(false)}
        title={
          activeMenu === 'organizacoes' ? 'Nova Organização' :
          activeMenu === 'usuarios' ? 'Novo Usuário' :
          'Novo Cargo'
        }
        subtitle={
          activeMenu === 'organizacoes' ? 'Cadastre uma nova empresa ou filial' :
          activeMenu === 'usuarios' ? 'Crie uma conta de acesso para um colaborador' :
          'Defina o cargo e selecione a matriz de permissões'
        }
      >
        <form onSubmit={handleCreateSubmit} className="wizard-form">
          {modalError && (
            <div className="modal-alert-error">
              <AlertCircle size={14} />
              <span>{modalError}</span>
            </div>
          )}

          {/* ORGANIZAÇÕES */}
          {activeMenu === 'organizacoes' && (
            <div className="form-group">
              <label htmlFor="orgName">Nome da Organização *</label>
              <input
                id="orgName"
                type="text"
                placeholder="Ex: FarmaNutri Filial Centro"
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                required
                autoFocus
                disabled={isSaving}
              />
            </div>
          )}

          {/* USUÁRIOS */}
          {activeMenu === 'usuarios' && (
            <>
              <div className="form-group">
                <label htmlFor="userName">Nome Completo *</label>
                <input
                  id="userName"
                  type="text"
                  placeholder="Ex: Carlos Silva"
                  value={userFullName}
                  onChange={(e) => setUserFullName(e.target.value)}
                  required
                  autoFocus
                  disabled={isSaving}
                />
              </div>

              <div className="form-group">
                <label htmlFor="userEmail">E-mail Corporativo *</label>
                <input
                  id="userEmail"
                  type="email"
                  placeholder="carlos@empresa.com"
                  value={userEmail}
                  onChange={(e) => setUserEmail(e.target.value)}
                  required
                  disabled={isSaving}
                />
              </div>

              <div className="form-group">
                <label htmlFor="userPassword">Senha Inicial *</label>
                <input
                  id="userPassword"
                  type="password"
                  placeholder="••••••••"
                  value={userPassword}
                  onChange={(e) => setUserPassword(e.target.value)}
                  required
                  disabled={isSaving}
                />
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="userOrg">Organização</label>
                  <select
                    id="userOrg"
                    value={userOrgId}
                    onChange={(e) => setUserOrgId(e.target.value)}
                    disabled={isSaving}
                  >
                    <option value="">Selecione...</option>
                    {organizations.map(org => (
                      <option key={org.id} value={org.id}>{org.name}</option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="userRole">Cargo (Role)</label>
                  <select
                    id="userRole"
                    value={userRoleId}
                    onChange={(e) => setUserRoleId(e.target.value)}
                    disabled={isSaving}
                  >
                    <option value="">Selecione...</option>
                    {roles.map(role => (
                      <option key={role.id} value={role.id}>{role.name}</option>
                    ))}
                  </select>
                </div>
              </div>
            </>
          )}

          {/* CARGOS */}
          {activeMenu === 'cargos' && (
            <>
              <div className="form-group">
                <label htmlFor="roleName">Nome do Cargo *</label>
                <input
                  id="roleName"
                  type="text"
                  placeholder="Ex: Gestor de Compras"
                  value={roleName}
                  onChange={(e) => setRoleName(e.target.value)}
                  required
                  autoFocus
                  disabled={isSaving}
                />
              </div>

              <div className="form-group">
                <label htmlFor="roleDesc">Descrição da Função</label>
                <input
                  id="roleDesc"
                  type="text"
                  placeholder="Ex: Responsável por cotações e pedidos"
                  value={roleDescription}
                  onChange={(e) => setRoleDescription(e.target.value)}
                  disabled={isSaving}
                />
              </div>

              <div className="permissions-matrix-wrap">
                <span className="matrix-title">Matriz de Permissões de Acesso</span>
                <div className="permissions-modules-list">
                  {Object.entries(permissionsByModule).map(([moduleName, modulePerms]) => (
                    <div key={moduleName} className="module-group">
                      <span className="module-name">{moduleName}</span>
                      <div className="module-perms">
                        {modulePerms.map(perm => {
                          const isChecked = selectedPermissionIds.includes(perm.id);
                          return (
                            <div 
                              key={perm.id} 
                              className={`perm-checkbox-item ${isChecked ? 'checked' : ''}`}
                              onClick={() => togglePermission(perm.id, selectedPermissionIds, setSelectedPermissionIds)}
                            >
                              <input 
                                type="checkbox" 
                                className="table-checkbox" 
                                checked={isChecked} 
                                onChange={() => {}} 
                              />
                              <div className="perm-labels">
                                <span className="perm-name">{perm.name}</span>
                                <span className="perm-code">{perm.code}</span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          <footer className="modal-footer">
            <button
              type="button"
              className="btn-cancel"
              onClick={() => setIsModalOpen(false)}
              disabled={isSaving}
            >
              Cancelar (ESC)
            </button>

            <button type="submit" className="btn-save" disabled={isSaving}>
              {isSaving ? (
                <>
                  <Loader2 size={14} className="spin" />
                  <span>Salvando...</span>
                </>
              ) : (
                <span>Salvar Registro</span>
              )}
            </button>
          </footer>
        </form>
      </Modal>

      {/* ============================================================= */}
      {/* 4. MODAL DE EDIÇÃO DE ORGANIZAÇÃO                             */}
      {/* ============================================================= */}
      <Modal
        isOpen={isOrgModalOpen}
        onClose={() => !isSaving && setIsOrgModalOpen(false)}
        title="Editar Organização"
        subtitle="Atualize os dados cadastrais da empresa ou filial"
      >
        {selectedOrg && (
          <form onSubmit={handleSaveOrg} className="wizard-form">
            {modalError && (
              <div className="modal-alert-error">
                <AlertCircle size={14} />
                <span>{modalError}</span>
              </div>
            )}

            <div className="form-group">
              <label htmlFor="editOrgName">Nome da Organização *</label>
              <input
                id="editOrgName"
                type="text"
                value={editOrgName}
                onChange={(e) => setEditOrgName(e.target.value)}
                required
                autoFocus
                disabled={isSaving}
              />
            </div>

            <div className="form-group">
              <label htmlFor="editOrgStatus">Status da Unidade</label>
              <select
                id="editOrgStatus"
                value={editOrgIsActive ? 'active' : 'inactive'}
                onChange={(e) => setEditOrgIsActive(e.target.value === 'active')}
                disabled={isSaving}
              >
                <option value="active">Ativa (Operacional)</option>
                <option value="inactive">Inativa (Bloqueada)</option>
              </select>
            </div>

            <footer className="modal-footer space-between">
              <button
                type="button"
                className="btn-danger-unlink"
                onClick={() => {
                  setIsOrgModalOpen(false);
                  setItemToDelete({ ids: [selectedOrg.id], names: [selectedOrg.name], type: 'org' });
                }}
                disabled={isSaving}
              >
                <Trash2 size={14} />
                <span>Excluir Organização</span>
              </button>

              <div className="right-actions">
                <button
                  type="button"
                  className="btn-cancel"
                  onClick={() => setIsOrgModalOpen(false)}
                  disabled={isSaving}
                >
                  Cancelar (ESC)
                </button>

                <button type="submit" className="btn-save" disabled={isSaving}>
                  {isSaving ? (
                    <>
                      <Loader2 size={14} className="spin" />
                      <span>Salvando...</span>
                    </>
                  ) : (
                    <span>Salvar Alterações</span>
                  )}
                </button>
              </div>
            </footer>
          </form>
        )}
      </Modal>

      {/* ============================================================= */}
      {/* 5. MODAL DE PERFIL / EDIÇÃO DE USUÁRIO                        */}
      {/* ============================================================= */}
      <Modal
        isOpen={isProfileModalOpen}
        onClose={() => !isSaving && setIsProfileModalOpen(false)}
        title="Perfil do Usuário"
        subtitle="Gerencie as informações cadastrais, acessos e desvinculação"
      >
        {selectedUser && (
          <form onSubmit={handleSaveUserProfile} className="wizard-form">
            {modalError && (
              <div className="modal-alert-error">
                <AlertCircle size={14} />
                <span>{modalError}</span>
              </div>
            )}

            <div className="profile-card-header">
              <div className="avatar-xl">
                {(selectedUser?.full_name || 'U').charAt(0).toUpperCase()}
              </div>
              <div className="info">
                <h3>{selectedUser?.full_name || 'Usuário'}</h3>
                <span className="email">{selectedUser?.email || '-'}</span>
                <span className="created">Cadastrado em {selectedUser?.created_at ? new Date(selectedUser.created_at).toLocaleDateString('pt-BR') : '-'}</span>
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="editName">Nome Completo *</label>
              <input
                id="editName"
                type="text"
                value={editFullName}
                onChange={(e) => setEditFullName(e.target.value)}
                required
                disabled={isSaving || (!hasPermission('users:edit') && selectedUser.email !== currentUserEmail)}
              />
            </div>

            <div className="form-group">
              <label htmlFor="editEmail">E-mail Corporativo *</label>
              <input
                id="editEmail"
                type="email"
                value={editEmail}
                onChange={(e) => setEditEmail(e.target.value)}
                required
                disabled={isSaving || !hasPermission('users:edit')}
              />
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor="editOrg">Organização Vinculada</label>
                <select
                  id="editOrg"
                  value={editOrgId}
                  onChange={(e) => setEditOrgId(e.target.value)}
                  disabled={isSaving || !hasPermission('users:edit')}
                >
                  <option value="">Selecione...</option>
                  {organizations.map(org => (
                    <option key={org.id} value={org.id}>{org.name}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="editRole">Cargo / Perfil</label>
                <select
                  id="editRole"
                  value={editRoleId}
                  onChange={(e) => setEditRoleId(e.target.value)}
                  disabled={isSaving || !hasPermission('users:edit')}
                >
                  <option value="">Selecione...</option>
                  {roles.map(role => (
                    <option key={role.id} value={role.id}>{role.name}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor="editStatus">Status da Conta</label>
                <select
                  id="editStatus"
                  value={editIsActive ? 'active' : 'inactive'}
                  onChange={(e) => setEditIsActive(e.target.value === 'active')}
                  disabled={isSaving || !hasPermission('users:edit')}
                >
                  <option value="active">Ativo (Acesso Liberado)</option>
                  <option value="inactive">Inativo (Acesso Bloqueado)</option>
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="editPassword">Redefinir Senha</label>
                <input
                  id="editPassword"
                  type="password"
                  placeholder="Nova senha (opcional)"
                  value={editNewPassword}
                  onChange={(e) => setEditNewPassword(e.target.value)}
                  disabled={isSaving}
                />
              </div>
            </div>

            <footer className="modal-footer space-between">
              {hasPermission('users:delete') && (
                <button
                  type="button"
                  className="btn-danger-unlink"
                  onClick={() => {
                    setIsProfileModalOpen(false);
                    setItemToDelete({ ids: [selectedUser.id], names: [selectedUser.full_name], type: 'user' });
                  }}
                  disabled={isSaving || selectedUser.email === currentUserEmail}
                  title={selectedUser.email === currentUserEmail ? 'Você não pode excluir sua própria conta' : 'Desvincular e Excluir Usuário'}
                >
                  <Trash2 size={14} />
                  <span>Desvincular Usuário</span>
                </button>
              )}

              <div className="right-actions">
                <button
                  type="button"
                  className="btn-cancel"
                  onClick={() => setIsProfileModalOpen(false)}
                  disabled={isSaving}
                >
                  Cancelar (ESC)
                </button>

                <button type="submit" className="btn-save" disabled={isSaving}>
                  {isSaving ? (
                    <>
                      <Loader2 size={14} className="spin" />
                      <span>Salvando...</span>
                    </>
                  ) : (
                    <span>Salvar Alterações</span>
                  )}
                </button>
              </div>
            </footer>
          </form>
        )}
      </Modal>

      {/* ============================================================= */}
      {/* 6. MODAL DE EDIÇÃO DE CARGO & MATRIZ DE PERMISSÕES             */}
      {/* ============================================================= */}
      <Modal
        isOpen={isRoleModalOpen}
        onClose={() => !isSaving && setIsRoleModalOpen(false)}
        title="Editar Cargo & Permissões"
        subtitle="Configure os dados do cargo e a matriz de acessos permitidos"
      >
        {selectedRole && (
          <form onSubmit={handleSaveRole} className="wizard-form">
            {modalError && (
              <div className="modal-alert-error">
                <AlertCircle size={14} />
                <span>{modalError}</span>
              </div>
            )}

            <div className="form-group">
              <label htmlFor="editRoleName">Nome do Cargo *</label>
              <input
                id="editRoleName"
                type="text"
                value={editRoleName}
                onChange={(e) => setEditRoleName(e.target.value)}
                required
                disabled={isSaving}
              />
            </div>

            <div className="form-group">
              <label htmlFor="editRoleDesc">Descrição da Função</label>
              <input
                id="editRoleDesc"
                type="text"
                value={editRoleDescription}
                onChange={(e) => setEditRoleDescription(e.target.value)}
                disabled={isSaving}
              />
            </div>

            <div className="permissions-matrix-wrap">
              <span className="matrix-title">Matriz de Permissões de Acesso</span>
              <div className="permissions-modules-list">
                {Object.entries(permissionsByModule).map(([moduleName, modulePerms]) => (
                  <div key={moduleName} className="module-group">
                    <span className="module-name">{moduleName}</span>
                    <div className="module-perms">
                      {modulePerms.map(perm => {
                        const isChecked = editRolePermissionIds.includes(perm.id);
                        return (
                          <div 
                            key={perm.id} 
                            className={`perm-checkbox-item ${isChecked ? 'checked' : ''}`}
                            onClick={() => togglePermission(perm.id, editRolePermissionIds, setEditRolePermissionIds)}
                          >
                            <input 
                              type="checkbox" 
                              className="table-checkbox" 
                              checked={isChecked} 
                              onChange={() => {}} 
                            />
                            <div className="perm-labels">
                              <span className="perm-name">{perm.name}</span>
                              <span className="perm-code">{perm.code}</span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <footer className="modal-footer space-between">
              <button
                type="button"
                className="btn-danger-unlink"
                onClick={() => {
                  setIsRoleModalOpen(false);
                  setItemToDelete({ ids: [selectedRole.id], names: [selectedRole.name], type: 'role' });
                }}
                disabled={isSaving}
              >
                <Trash2 size={14} />
                <span>Excluir Cargo</span>
              </button>

              <div className="right-actions">
                <button
                  type="button"
                  className="btn-cancel"
                  onClick={() => setIsRoleModalOpen(false)}
                  disabled={isSaving}
                >
                  Cancelar (ESC)
                </button>

                <button type="submit" className="btn-save" disabled={isSaving}>
                  {isSaving ? (
                    <>
                      <Loader2 size={14} className="spin" />
                      <span>Salvando...</span>
                    </>
                  ) : (
                    <span>Salvar Permissões</span>
                  )}
                </button>
              </div>
            </footer>
          </form>
        )}
      </Modal>

      {/* ============================================================= */}
      {/* 7. MODAL DE CONFIRMAÇÃO DE EXCLUSÃO (INDIVIDUAL OU EM LOTE)    */}
      {/* ============================================================= */}
      <Modal
        isOpen={!!itemToDelete}
        onClose={() => !isDeleting && setItemToDelete(null)}
        title="Confirmar Exclusão"
      >
        {itemToDelete && (
          <div className="delete-confirm-box">
            <div className="icon-warning-wrap">
              <ShieldAlert size={32} />
            </div>

            <p className="confirm-text">
              {itemToDelete.ids.length === 1 ? (
                <>
                  Tem certeza que deseja excluir permanentemente <strong>"{itemToDelete.names[0]}"</strong>?
                </>
              ) : (
                <>
                  Tem certeza que deseja excluir permanentemente os <strong>{itemToDelete.ids.length} itens selecionados</strong>?
                </>
              )}
            </p>
            <p className="subtext">
              Esta ação removerá todos os vínculos associados e não poderá ser desfeita.
            </p>

            <div className="confirm-actions">
              <button
                className="btn-cancel"
                onClick={() => setItemToDelete(null)}
                disabled={isDeleting}
              >
                Cancelar (ESC)
              </button>

              <button
                className="btn-confirm-delete"
                onClick={handleConfirmDelete}
                disabled={isDeleting}
              >
                {isDeleting ? (
                  <>
                    <Loader2 size={14} className="spin" />
                    <span>Excluindo...</span>
                  </>
                ) : (
                  <>
                    <Trash2 size={14} />
                    <span>Sim, Excluir</span>
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </Modal>

    </div>
  );
};

export default Cadastros;
