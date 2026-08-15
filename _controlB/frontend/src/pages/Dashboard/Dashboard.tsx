/**
 * pages/Dashboard/Dashboard.tsx - Painel Principal do ControlB
 * 
 * Exibe a Navbar superior e cards interativos com dados do backend FastAPI
 * (Usuários, Cargos e Organizações) carregados em paralelo via Axios.
 */

import React, { useEffect, useState } from 'react';
import { Users, Shield, Building2, RefreshCw, CheckCircle2, XCircle, Mail } from 'lucide-react';
import { identityService } from '@/services/api';
import { User, Role, Organization } from '@/types';
import { Navbar } from '@/components/Navbar';
import './Dashboard.scss';

export const Dashboard: React.FC = () => {
  // Estados para armazenar as listas retornadas da API
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [organizations, setOrganizations] = useState<Organization[]>([]);

  // Estados de Carregamento individuais
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Função para buscar todos os dados em paralelo
  const loadData = async () => {
    setLoading(true);
    setError(null);

    try {
      const [usersData, rolesData, orgsData] = await Promise.all([
        identityService.getUsers(),
        identityService.getRoles(),
        identityService.getOrganizations(),
      ]);

      setUsers(usersData);
      setRoles(rolesData);
      setOrganizations(orgsData);
    } catch (err: any) {
      console.error('Erro ao carregar dados do Dashboard:', err);
      setError('Não foi possível se comunicar com o backend FastAPI.');
    } finally {
      setLoading(false);
    }
  };

  // Carrega os dados ao montar o componente
  useEffect(() => {
    loadData();
  }, []);

  return (
    <div className="dashboard-page">
      <Navbar />

      <main className="dashboard-content">
        <div className="dashboard-header">
          <div>
            <h1>Visão Geral do Sistema</h1>
            <p>Gerencie organizações, acessos e usuários cadastrados</p>
          </div>

          <button className="btn-refresh" onClick={loadData} disabled={loading} title="Recarregar Dados">
            <RefreshCw size={16} className={loading ? 'spin' : ''} />
            <span>Atualizar</span>
          </button>
        </div>

        {error && (
          <div className="dashboard-error">
            <span>{error}</span>
          </div>
        )}

        <div className="cards-grid">
          {/* Card 1: Organizações */}
          <div className="dash-card card-orgs">
            <div className="card-header">
              <div className="icon-badge badge-orgs">
                <Building2 size={20} />
              </div>
              <div>
                <h2>Organizações</h2>
                <span className="card-count">{organizations.length} cadastrada(s)</span>
              </div>
            </div>

            <div className="card-body">
              {loading ? (
                <div className="loading-state">Carregando organizações...</div>
              ) : organizations.length === 0 ? (
                <div className="empty-state">Nenhuma organização cadastrada.</div>
              ) : (
                <ul className="items-list">
                  {organizations.map((org) => (
                    <li key={org.id} className="item-row">
                      <div className="item-info">
                        <strong>{org.name}</strong>
                        <span className="item-date">Criado em: {new Date(org.created_at).toLocaleDateString('pt-BR')}</span>
                      </div>
                      <span className={`status-pill ${org.is_active ? 'active' : 'inactive'}`}>
                        {org.is_active ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
                        {org.is_active ? 'Ativa' : 'Inativa'}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {/* Card 2: Usuários */}
          <div className="dash-card card-users">
            <div className="card-header">
              <div className="icon-badge badge-users">
                <Users size={20} />
              </div>
              <div>
                <h2>Usuários</h2>
                <span className="card-count">{users.length} cadastrado(s)</span>
              </div>
            </div>

            <div className="card-body">
              {loading ? (
                <div className="loading-state">Carregando usuários...</div>
              ) : users.length === 0 ? (
                <div className="empty-state">Nenhum usuário cadastrado.</div>
              ) : (
                <ul className="items-list">
                  {users.map((user) => (
                    <li key={user.id} className="item-row">
                      <div className="item-info">
                        <strong>{user.full_name}</strong>
                        <span className="item-sub">
                          <Mail size={12} />
                          {user.email}
                        </span>
                      </div>
                      <span className={`status-pill ${user.is_active ? 'active' : 'inactive'}`}>
                        {user.is_active ? 'Ativo' : 'Inativo'}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {/* Card 3: Cargos (Roles) */}
          <div className="dash-card card-roles">
            <div className="card-header">
              <div className="icon-badge badge-roles">
                <Shield size={20} />
              </div>
              <div>
                <h2>Cargos (Roles)</h2>
                <span className="card-count">{roles.length} cadastrado(s)</span>
              </div>
            </div>

            <div className="card-body">
              {loading ? (
                <div className="loading-state">Carregando cargos...</div>
              ) : roles.length === 0 ? (
                <div className="empty-state">Nenhum cargo cadastrado.</div>
              ) : (
                <ul className="items-list">
                  {roles.map((role) => (
                    <li key={role.id} className="item-row">
                      <div className="item-info">
                        <strong>{role.name}</strong>
                        <span className="item-sub">{role.description || 'Sem descrição cadastrada'}</span>
                      </div>
                      <span className={`status-pill ${role.is_active ? 'active' : 'inactive'}`}>
                        {role.is_active ? 'Ativo' : 'Inativo'}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};
