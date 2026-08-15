/**
 * pages/Users/Users.tsx - Gestão de Usuários e Contas de Acesso
 */

import React, { useEffect, useState } from 'react';
import { Search, CheckCircle2, XCircle, RefreshCw, Plus, Mail } from 'lucide-react';
import { identityService } from '@/services/api';
import { User } from '@/types';
import { Navbar } from '@/components/Navbar';
import './Users.scss';

export const Users: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await identityService.getUsers();
      setUsers(data);
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

  const filteredUsers = users.filter(u =>
    u.full_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    u.email.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="page-container">
      <Navbar />

      <main className="page-content">
        <header className="page-header">
          <div>
            <h1>Gestão de Usuários</h1>
            <p>Contas de acesso, colaboradores e administradores do ControlB</p>
          </div>

          <div className="header-actions">
            <button className="btn-refresh" onClick={loadData} disabled={loading} title="Atualizar">
              <RefreshCw size={13} className={loading ? 'spin' : ''} />
              <span>Atualizar</span>
            </button>

            <button className="btn-primary">
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
            <span className="results-count">{filteredUsers.length} usuário(s)</span>
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
                    <th>Status</th>
                    <th>Data de Cadastro</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredUsers.map(user => (
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
                        <span className={`badge-pill ${user.is_active ? 'active' : 'inactive'}`}>
                          {user.is_active ? <CheckCircle2 size={11} /> : <XCircle size={11} />}
                          {user.is_active ? 'Ativo' : 'Inativo'}
                        </span>
                      </td>
                      <td>{new Date(user.created_at).toLocaleDateString('pt-BR')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  );
};
