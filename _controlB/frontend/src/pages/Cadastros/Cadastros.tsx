/**
 * pages/Cadastros/Cadastros.tsx - Central de Cadastros com Perfil de Usuários e Desvinculação/Exclusão
 * 
 * Funcionalidades:
 * 1. 🏢 Organizações (Listar, Criar, Excluir)
 * 2. 👥 Usuários (Listar, Criar, Editar Perfil Completo, Desvincular/Excluir)
 * 3. 🛡️ Cargos (Listar, Criar, Excluir)
 * 4. 📦 Produtos & Insumos
 */

import React, { useEffect, useState } from 'react';
import { 
  Building2, Users, Shield, Package, ChevronRight, 
  Search, CheckCircle2, XCircle, RefreshCw, Plus, Mail, 
  Loader2, AlertCircle, Trash2, Edit3, ShieldAlert
} from 'lucide-react';
import { identityService, authService } from '@/services/api';
import { User, Role, Organization } from '@/types';
import { Navbar } from '@/components/Navbar';
import { Modal } from '@/components/Modal/Modal';
import './Cadastros.scss';

type MenuOption = 'organizacoes' | 'usuarios' | 'cargos' | 'produtos';

export const Cadastros: React.FC = () => {
  // Estado do Menu Ativo na Sidebar
  const [activeMenu, setActiveMenu] = useState<MenuOption>('usuarios');
  const [searchTerm, setSearchTerm] = useState('');

  // Estados dos Dados carregados da API
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);

  // Estados de Carregamento da Lista
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // =========================================================================
  // ESTADOS DO WIZARD / MODAL DE NOVO CADASTRO
  // =========================================================================
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // Campos do Formulário de Criação
  const [userFullName, setUserFullName] = useState('');
  const [userEmail, setUserEmail] = useState('');
  const [userPassword, setUserPassword] = useState('');
  const [userOrgId, setUserOrgId] = useState('');
  const [userRoleId, setUserRoleId] = useState('');
  const [orgName, setOrgName] = useState('');
  const [roleName, setRoleName] = useState('');
  const [roleDescription, setRoleDescription] = useState('');

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

  // Estado do Modal de Confirmação de Exclusão
  const [itemToDelete, setItemToDelete] = useState<{ id: string; name: string; type: 'user' | 'org' | 'role' } | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const currentUserEmail = authService.getUserEmail();

  // 1. Busca todos os dados da API em paralelo
  const loadData = async () => {
    setLoading(true);
    setError(null);

    try {
      const [orgsData, usersData, rolesData] = await Promise.all([
        identityService.getOrganizations(),
        identityService.getUsers(),
        identityService.getRoles(),
      ]);

      setOrganizations(orgsData);
      setUsers(usersData);
      setRoles(rolesData);
    } catch (err: any) {
      console.error('Erro ao carregar dados de cadastros:', err);
      setError('Não foi possível se comunicar com o backend FastAPI.');
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
  };

  // Abre o modal de criação e limpa os campos anteriores
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
    setIsModalOpen(true);
  };

  // Abre o modal de Perfil do Usuário para edição
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
        await identityService.createRole(roleName.trim(), roleDescription.trim(), organizations[0]?.id);
      }

      setIsModalOpen(false);
      await loadData();
    } catch (err: any) {
      setModalError(
        err.response?.data?.detail || err.message || 'Erro ao salvar o registro no servidor.'
      );
    } finally {
      setIsSaving(false);
    }
  };

  // 3. Salvar Edição de Perfil do Usuário
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
      setModalError(
        err.response?.data?.detail || err.message || 'Erro ao atualizar o perfil do usuário.'
      );
    } finally {
      setIsSaving(false);
    }
  };

  // 4. Executar Exclusão / Desvinculação Confirmada
  const handleConfirmDelete = async () => {
    if (!itemToDelete || isDeleting) return;

    setIsDeleting(true);
    try {
      if (itemToDelete.type === 'user') {
        await identityService.deleteUser(itemToDelete.id);
        if (selectedUser?.id === itemToDelete.id) {
          setIsProfileModalOpen(false);
        }
      } else if (itemToDelete.type === 'org') {
        await identityService.deleteOrganization(itemToDelete.id);
      } else if (itemToDelete.type === 'role') {
        await identityService.deleteRole(itemToDelete.id);
      }

      setItemToDelete(null);
      await loadData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Erro ao desvincular/excluir o registro.');
    } finally {
      setIsDeleting(false);
    }
  };

  // Filtros de busca
  const filteredOrgs = organizations.filter(o =>
    o.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const filteredUsers = users.filter(u =>
    u.full_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    u.email.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const filteredRoles = roles.filter(r =>
    r.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (r.description && r.description.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  return (
    <div className="cadastros-page">
      <Navbar />

      <div className="cadastros-layout">
        
        {/* ========================================================= */}
        {/* 1. BARRA LATERAL ESQUERDA (Sidebar)                       */}
        {/* ========================================================= */}
        <aside className="sidebar-left">
          <div className="sidebar-header">
            <span className="sidebar-section-title">Menu de Cadastros</span>
          </div>

          <nav className="sidebar-menu-list">
            <button
              type="button"
              className={`sidebar-menu-btn ${activeMenu === 'organizacoes' ? 'active' : ''}`}
              onClick={() => handleSelectMenu('organizacoes')}
            >
              <div className="btn-label">
                <Building2 size={16} className="icon-org" />
                <span>Organizações</span>
              </div>
              <div className="btn-end">
                <span className="count-pill">{organizations.length}</span>
                <ChevronRight size={14} className="arrow" />
              </div>
            </button>

            <button
              type="button"
              className={`sidebar-menu-btn ${activeMenu === 'usuarios' ? 'active' : ''}`}
              onClick={() => handleSelectMenu('usuarios')}
            >
              <div className="btn-label">
                <Users size={16} className="icon-users" />
                <span>Usuários</span>
              </div>
              <div className="btn-end">
                <span className="count-pill">{users.length}</span>
                <ChevronRight size={14} className="arrow" />
              </div>
            </button>

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
                <span className="count-pill">{roles.length}</span>
                <ChevronRight size={14} className="arrow" />
              </div>
            </button>

            <button
              type="button"
              className={`sidebar-menu-btn ${activeMenu === 'produtos' ? 'active' : ''}`}
              onClick={() => handleSelectMenu('produtos')}
            >
              <div className="btn-label">
                <Package size={16} className="icon-products" />
                <span>Produtos & Insumos</span>
              </div>
              <div className="btn-end">
                <ChevronRight size={14} className="arrow" />
              </div>
            </button>
          </nav>
        </aside>

        {/* ========================================================= */}
        {/* 2. ÁREA DE CONTEÚDO PRINCIPAL                             */}
        {/* ========================================================= */}
        <main className="content-right">
          
          <header className="content-header">
            <div className="titles">
              <h1>
                {activeMenu === 'organizacoes' && 'Gestão de Organizações'}
                {activeMenu === 'usuarios' && 'Gestão de Usuários & Perfis'}
                {activeMenu === 'cargos' && 'Cargos e Perfis de Acesso'}
                {activeMenu === 'produtos' && 'Produtos & Insumos'}
              </h1>
              <p>
                {activeMenu === 'organizacoes' && 'Empresas, filiais e unidades de negócio cadastradas'}
                {activeMenu === 'usuarios' && 'Gerencie perfis, permissões, vinculação de organizações e desvinculação'}
                {activeMenu === 'cargos' && 'Níveis de permissão e atribuições de responsabilidade'}
                {activeMenu === 'produtos' && 'Catálogo de itens, matérias-primas e insumos'}
              </p>
            </div>

            <div className="header-actions">
              <button className="btn-refresh" onClick={loadData} disabled={loading} title="Atualizar Dados">
                <RefreshCw size={13} className={loading ? 'spin' : ''} />
                <span>Atualizar</span>
              </button>

              {activeMenu !== 'produtos' && (
                <button className="btn-primary" onClick={handleOpenCreateModal}>
                  <Plus size={14} />
                  <span>
                    {activeMenu === 'organizacoes' && 'Nova Organização'}
                    {activeMenu === 'usuarios' && 'Novo Usuário'}
                    {activeMenu === 'cargos' && 'Novo Cargo'}
                  </span>
                </button>
              )}
            </div>
          </header>

          {error && <div className="alert-error">{error}</div>}

          {/* Painel com Toolbar de Busca */}
          <div className="table-card">
            <div className="table-toolbar">
              <div className="search-wrap">
                <Search size={14} />
                <input
                  type="text"
                  placeholder={
                    activeMenu === 'organizacoes' ? 'Buscar organização...' :
                    activeMenu === 'usuarios' ? 'Buscar por nome ou e-mail...' :
                    activeMenu === 'cargos' ? 'Buscar cargo ou descrição...' :
                    'Buscar produto...'
                  }
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>

              <span className="results-count">
                {activeMenu === 'organizacoes' && `${filteredOrgs.length} organização(ões)`}
                {activeMenu === 'usuarios' && `${filteredUsers.length} usuário(s)`}
                {activeMenu === 'cargos' && `${filteredRoles.length} cargo(s)`}
                {activeMenu === 'produtos' && 'Módulo de Estoque'}
              </span>
            </div>

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
                        <th>Nome da Organização</th>
                        <th>Status</th>
                        <th>Data de Cadastro</th>
                        <th style={{ textAlign: 'right' }}>Ações</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredOrgs.map(org => (
                        <tr key={org.id}>
                          <td>
                            <div className="cell-with-icon">
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
                          <td>{new Date(org.created_at).toLocaleDateString('pt-BR')}</td>
                          <td style={{ textAlign: 'right' }}>
                            <button
                              className="btn-action-icon delete"
                              onClick={() => setItemToDelete({ id: org.id, name: org.name, type: 'org' })}
                              title="Excluir Organização"
                            >
                              <Trash2 size={14} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            )}

            {/* TABELA: USUÁRIOS (Com Ações de Perfil e Exclusão) */}
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
                        <th>Colaborador</th>
                        <th>E-mail Corporativo</th>
                        <th>Status</th>
                        <th>Data de Cadastro</th>
                        <th style={{ textAlign: 'right' }}>Ações / Perfil</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredUsers.map(user => {
                        const isSelf = user.email === currentUserEmail;
                        return (
                          <tr key={user.id}>
                            <td>
                              <div 
                                className="cell-with-icon clickable" 
                                onClick={() => handleOpenUserProfile(user)}
                                title="Clique para abrir o perfil do usuário"
                              >
                                <div className="avatar-circle-sm">
                                  {user.full_name.charAt(0).toUpperCase()}
                                </div>
                                <div>
                                  <strong>{user.full_name}</strong>
                                  {isSelf && <span className="badge-self">Você</span>}
                                </div>
                              </div>
                            </td>
                            <td>
                              <span className="email-text">
                                <Mail size={12} />
                                {user.email}
                              </span>
                            </td>
                            <td>
                              <span className={`badge-pill ${user.is_active ? 'active' : 'inactive'}`}>
                                {user.is_active ? <CheckCircle2 size={11} /> : <XCircle size={11} />}
                                {user.is_active ? 'Ativo' : 'Inativo'}
                              </span>
                            </td>
                            <td>{new Date(user.created_at).toLocaleDateString('pt-BR')}</td>
                            <td style={{ textAlign: 'right' }}>
                              <div className="row-actions">
                                <button
                                  className="btn-action-icon edit"
                                  onClick={() => handleOpenUserProfile(user)}
                                  title="Editar Perfil do Usuário"
                                >
                                  <Edit3 size={14} />
                                </button>

                                <button
                                  className="btn-action-icon delete"
                                  onClick={() => setItemToDelete({ id: user.id, name: user.full_name, type: 'user' })}
                                  disabled={isSelf}
                                  title={isSelf ? 'Você não pode excluir sua própria conta' : 'Desvincular / Excluir Usuário'}
                                >
                                  <Trash2 size={14} />
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )
            )}

            {/* TABELA: CARGOS */}
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
                        <th>Nome do Cargo</th>
                        <th>Descrição da Função</th>
                        <th>Status</th>
                        <th style={{ textAlign: 'right' }}>Ações</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredRoles.map(role => (
                        <tr key={role.id}>
                          <td>
                            <div className="cell-with-icon">
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
                            <span className={`badge-pill ${role.is_active ? 'active' : 'inactive'}`}>
                              {role.is_active ? <CheckCircle2 size={11} /> : <XCircle size={11} />}
                              {role.is_active ? 'Ativo' : 'Inativo'}
                            </span>
                          </td>
                          <td style={{ textAlign: 'right' }}>
                            <button
                              className="btn-action-icon delete"
                              onClick={() => setItemToDelete({ id: role.id, name: role.name, type: 'role' })}
                              title="Excluir Cargo"
                            >
                              <Trash2 size={14} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            )}

            {/* PRODUTOS */}
            {activeMenu === 'produtos' && (
              <div className="state-empty">
                <Package size={32} style={{ color: 'var(--accent-brand)', marginBottom: '0.5rem' }} />
                <p><strong>Módulo de Catálogo de Produtos e Insumos</strong></p>
                <p style={{ fontSize: '0.8rem', marginTop: '0.25rem' }}>Pronto para cadastro e integração com o módulo de Estoque & Compras.</p>
              </div>
            )}

          </div>
        </main>

      </div>

      {/* ============================================================= */}
      {/* 3. WIZARD / MODAL DE CRIAÇÃO                                  */}
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
          'Defina um novo nível de acesso no sistema'
        }
      >
        <form onSubmit={handleCreateSubmit} className="wizard-form">
          {modalError && (
            <div className="modal-alert-error">
              <AlertCircle size={14} />
              <span>{modalError}</span>
            </div>
          )}

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
            </>
          )}

          <footer className="modal-footer">
            <button
              type="button"
              className="btn-cancel"
              onClick={() => setIsModalOpen(false)}
              disabled={isSaving}
            >
              Cancelar
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
      {/* 4. MODAL DE PERFIL / EDIÇÃO DE USUÁRIO & UNLINK               */}
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

            {/* Cabeçalho do Perfil com Avatar */}
            <div className="profile-card-header">
              <div className="avatar-xl">
                {selectedUser.full_name.charAt(0).toUpperCase()}
              </div>
              <div className="info">
                <h3>{selectedUser.full_name}</h3>
                <span className="email">{selectedUser.email}</span>
                <span className="created">Cadastrado em {new Date(selectedUser.created_at).toLocaleDateString('pt-BR')}</span>
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
                disabled={isSaving}
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
                disabled={isSaving}
              />
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor="editOrg">Organização Vinculada</label>
                <select
                  id="editOrg"
                  value={editOrgId}
                  onChange={(e) => setEditOrgId(e.target.value)}
                  disabled={isSaving}
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
                  disabled={isSaving}
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
                  disabled={isSaving}
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
              {/* Botão de Desvincular / Excluir na Esquerda */}
              <button
                type="button"
                className="btn-danger-unlink"
                onClick={() => setItemToDelete({ id: selectedUser.id, name: selectedUser.full_name, type: 'user' })}
                disabled={isSaving || selectedUser.email === currentUserEmail}
                title={selectedUser.email === currentUserEmail ? 'Você não pode excluir sua própria conta' : 'Desvincular e Excluir Usuário'}
              >
                <Trash2 size={14} />
                <span>Desvincular Usuário</span>
              </button>

              <div className="right-actions">
                <button
                  type="button"
                  className="btn-cancel"
                  onClick={() => setIsProfileModalOpen(false)}
                  disabled={isSaving}
                >
                  Cancelar
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
      {/* 5. MODAL DE CONFIRMAÇÃO DE EXCLUSÃO / DESVINCULAÇÃO           */}
      {/* ============================================================= */}
      <Modal
        isOpen={!!itemToDelete}
        onClose={() => !isDeleting && setItemToDelete(null)}
        title="Confirmar Desvinculação / Exclusão"
      >
        {itemToDelete && (
          <div className="delete-confirm-box">
            <div className="icon-warning-wrap">
              <ShieldAlert size={32} />
            </div>

            <p className="confirm-text">
              Tem certeza que deseja desvincular e excluir permanentemente{' '}
              <strong>"{itemToDelete.name}"</strong>?
            </p>
            <p className="subtext">
              Esta ação removerá todos os acessos associados e não poderá ser desfeita.
            </p>

            <div className="confirm-actions">
              <button
                className="btn-cancel"
                onClick={() => setItemToDelete(null)}
                disabled={isDeleting}
              >
                Voltar
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
                    <span>Sim, Desvincular e Excluir</span>
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
