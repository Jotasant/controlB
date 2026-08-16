/**
 * pages/Organizations/Organizations.tsx - Gestão de Organizações
 */

import React, { useEffect, useState } from 'react';
import { Building2, Search, CheckCircle2, XCircle, RefreshCw, Plus } from 'lucide-react';
import { identityService } from '@/services/api';
import { Organization } from '@/types';
import './Organizations.scss';

export const Organizations: React.FC = () => {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await identityService.getOrganizations();
      setOrganizations(data);
    } catch (err) {
      console.error(err);
      setError('Erro ao carregar lista de organizações.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const filteredOrgs = organizations.filter(o =>
    o.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="page-container">
      <main className="page-content">

        <header className="page-header">
          <div>
            <h1>Gestão de Organizações</h1>
            <p>Empresas, filiais e unidades de negócio cadastradas no ControlB</p>
          </div>

          <div className="header-actions">
            <button className="btn-refresh" onClick={loadData} disabled={loading} title="Atualizar">
              <RefreshCw size={13} className={loading ? 'spin' : ''} />
              <span>Atualizar</span>
            </button>

            <button className="btn-primary">
              <Plus size={14} />
              <span>Nova Organização</span>
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
                placeholder="Buscar por nome..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            <span className="results-count">{filteredOrgs.length} organização(ões)</span>
          </div>

          {loading ? (
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
                    <th>Identificador (ID)</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredOrgs.map(org => (
                    <tr key={org.id}>
                      <td>
                        <div className="org-cell">
                          <div className="org-icon-badge">
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
                      <td><code className="code-tag">{org.id}</code></td>
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
