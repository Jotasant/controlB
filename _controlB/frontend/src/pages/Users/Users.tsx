/**
 * pages/Users/Users.tsx - Gestão de Usuários e Contas de Acesso
 */

import React, { useEffect, useState } from 'react';
import { Search, CheckCircle2, XCircle, RefreshCw, Plus, Mail, Briefcase, Users as UsersIcon, X } from 'lucide-react';
import { identityService } from '@/services/api';
import { User, Team } from '@/types';
import './Users.scss';

export const Users: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal de Criação / Edição de Usuário
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [userForm, setUserForm] = useState({
    full_name: '',
    email: '',
    password: '',
    is_seller: false
  });

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [usersData, teamsData] = await Promise.all([
        identityService.getUsers(),
        identityService.getTeams().catch(() => [])
      ]);
      setUsers(usersData);
      setTeams(teamsData);
    } catch (err) {
      console.error(err);
      setError('Erro ao carregar lista de usuários.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleToggleSeller = async (user: User) => {
    try {
      const newStatus = !user.is_seller;
      await identityService.updateUser(user.id, { is_seller: newStatus });
      setUsers(prev => prev.map(u => u.id === user.id ? { ...u, is_seller: newStatus } : u));
    } catch (err) {
      console.error('Erro ao atualizar status de vendedor:', err);
      alert('Erro ao atualizar status de vendedor do usuário.');
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!userForm.full_name || !userForm.email || !userForm.password) {
      alert('Por favor, preencha todos os campos obrigatórios.');
      return;
    }

    setIsSaving(true);
    try {
      await identityService.createUser({
        full_name: userForm.full_name,
        email: userForm.email,
        password: userForm.password,
        is_seller: userForm.is_seller
      });
      setIsModalOpen(false);
      setUserForm({ full_name: '', email: '', password: '', is_seller: false });
      await loadData();
    } catch (err: any) {
      console.error('Erro ao criar usuário:', err);
      alert(err?.response?.data?.detail || 'Erro ao criar usuário.');
    } finally {
      setIsSaving(false);
    }
  };

  const filteredUsers = users.filter(u =>
    u.full_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    u.email.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="page-container">
      <main className="page-content">

        <header className="page-header">
          <div>
            <h1>Gestão de Usuários</h1>
            <p>Contas de acesso, colaboradores, administradores e força de vendas do ControlB</p>
          </div>

          <div className="header-actions">
            <button className="btn-refresh" onClick={loadData} disabled={loading} title="Atualizar">
              <RefreshCw size={13} className={loading ? 'spin' : ''} />
              <span>Atualizar</span>
            </button>

            <button className="btn-primary" onClick={() => setIsModalOpen(true)}>
              <Plus size={14} />
              <span>Novo Usuário</span>
            </button>
          </div>
        </header>

        {error && <div className="alert-error">{error}</div>}

        <div className="table-card">
          <div className="table-toolbar">
            <div className="search-wrap">
              <Search size={14} />
              <input
                type="text"
                placeholder="Buscar por nome ou e-mail..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            <span className="results-count">
              {filteredUsers.length} usuário(s) • {users.filter(u => u.is_seller).length} vendedor(es) • {teams.length} equipe(s)
            </span>
          </div>

          {loading ? (
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
                    <th>Força de Vendas</th>
                    <th>Equipes Vinculadas</th>
                    <th>Status</th>
                    <th>Data de Cadastro</th>
                    <th style={{ textAlign: 'center' }}>Ações</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredUsers.map(user => {
                    const userTeams = user.teams && user.teams.length > 0 ? user.teams : [];
                    return (
                      <tr key={user.id}>
                        <td>
                          <div className="user-cell">
                            <div className="user-avatar-badge">
                              {user.full_name.charAt(0).toUpperCase()}
                            </div>
                            <strong>{user.full_name}</strong>
                          </div>
                        </td>
                        <td>
                          <span className="email-text">
                            <Mail size={12} />
                            {user.email}
                          </span>
                        </td>
                        <td>
                          <button
                            type="button"
                            className={`seller-toggle-btn ${user.is_seller ? 'is-seller' : 'not-seller'}`}
                            onClick={() => handleToggleSeller(user)}
                            title={user.is_seller ? 'Clique para desmarcar vendedor' : 'Clique para marcar como vendedor'}
                          >
                            <Briefcase size={12} />
                            <span>{user.is_seller ? 'Vendedor Ativo' : 'Não Vendedor'}</span>
                          </button>
                        </td>
                        <td>
                          {userTeams.length > 0 ? (
                            <div style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap' }}>
                              {userTeams.map(t => (
                                <span key={t.id} className="team-pill-badge">
                                  <UsersIcon size={10} />
                                  <span>{t.name}</span>
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Sem equipe</span>
                          )}
                        </td>
                        <td>
                          <span className={`badge-pill ${user.is_active ? 'active' : 'inactive'}`}>
                            {user.is_active ? <CheckCircle2 size={11} /> : <XCircle size={11} />}
                            {user.is_active ? 'Ativo' : 'Inativo'}
                          </span>
                        </td>
                        <td>{new Date(user.created_at).toLocaleDateString('pt-BR')}</td>
                        <td style={{ textAlign: 'center' }}>
                          <button
                            className="btn-quick-seller-action"
                            onClick={() => handleToggleSeller(user)}
                          >
                            {user.is_seller ? 'Remover Vendas' : 'Tornar Vendedor'}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Modal de Criação de Usuário */}
        {isModalOpen && (
          <div className="users-modal-backdrop">
            <div className="users-modal-dialog">
              <div className="modal-header">
                <h3>Novo Usuário do Sistema</h3>
                <button type="button" className="btn-close" onClick={() => setIsModalOpen(false)}>
                  <X size={16} />
                </button>
              </div>

              <form onSubmit={handleCreateUser} className="modal-body">
                <div className="form-group">
                  <label>Nome Completo *</label>
                  <input
                    type="text"
                    required
                    placeholder="Ex: João da Silva"
                    value={userForm.full_name}
                    onChange={(e) => setUserForm({ ...userForm, full_name: e.target.value })}
                  />
                </div>

                <div className="form-group">
                  <label>E-mail de Acesso *</label>
                  <input
                    type="email"
                    required
                    placeholder="Ex: joao@controlb.com"
                    value={userForm.email}
                    onChange={(e) => setUserForm({ ...userForm, email: e.target.value })}
                  />
                </div>

                <div className="form-group">
                  <label>Senha Provisória *</label>
                  <input
                    type="password"
                    required
                    placeholder="Mínimo 6 caracteres"
                    value={userForm.password}
                    onChange={(e) => setUserForm({ ...userForm, password: e.target.value })}
                  />
                </div>

                <div className="seller-checkbox-card">
                  <label className="checkbox-row">
                    <input
                      type="checkbox"
                      checked={userForm.is_seller}
                      onChange={(e) => setUserForm({ ...userForm, is_seller: e.target.checked })}
                    />
                    <div>
                      <strong>Marcar como Vendedor Comercial (Força de Vendas)</strong>
                      <p>Permite associar este usuário a propostas, oportunidades de CRM e equipes comerciais.</p>
                    </div>
                  </label>
                </div>

                <div className="modal-footer">
                  <button type="button" className="btn-cancel" onClick={() => setIsModalOpen(false)}>
                    Cancelar
                  </button>
                  <button type="submit" className="btn-save" disabled={isSaving}>
                    {isSaving ? 'Salvando...' : 'Criar Usuário'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

      </main>
    </div>
  );
};
