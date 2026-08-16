/**
 * pages/Roles/Roles.tsx - Gestão de Cargos e Permissões
 */

import React, { useEffect, useState } from 'react';
import { Shield, Search, CheckCircle2, XCircle, RefreshCw, Plus } from 'lucide-react';
import { identityService } from '@/services/api';
import { Role } from '@/types';
import './Roles.scss';

export const Roles: React.FC = () => {
  const [roles, setRoles] = useState<Role[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await identityService.getRoles();
      setRoles(data);
    } catch (err) {
      console.error(err);
      setError('Erro ao carregar lista de cargos.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const filteredRoles = roles.filter(r =>
    r.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (r.description && r.description.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  return (
    <div className="page-container">
      <main className="page-content">

        <header className="page-header">
          <div>
            <h1>Cargos e Permissões</h1>
            <p>Perfis de acesso e atribuições de responsabilidade no ControlB</p>
          </div>

          <div className="header-actions">
            <button className="btn-refresh" onClick={loadData} disabled={loading} title="Atualizar">
              <RefreshCw size={13} className={loading ? 'spin' : ''} />
              <span>Atualizar</span>
            </button>

            <button className="btn-primary">
              <Plus size={14} />
              <span>Novo Cargo</span>
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
                placeholder="Buscar por cargo ou descrição..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            <span className="results-count">{filteredRoles.length} cargo(s)</span>
          </div>

          {loading ? (
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
                    <th>Data de Cadastro</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRoles.map(role => (
                    <tr key={role.id}>
                      <td>
                        <div className="role-cell">
                          <div className="role-icon-badge">
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
                      <td>{new Date(role.created_at).toLocaleDateString('pt-BR')}</td>
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
