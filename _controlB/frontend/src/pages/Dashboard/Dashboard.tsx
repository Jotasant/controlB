/**
 * pages/Dashboard/Dashboard.tsx - Painel Executivo Focado em Gráficos & KPIs com RBAC
 * 
 * Exibe métricas de compras, gráficos de desempenho financeiro (Recharts)
 * e cards de KPIs condicionados estritamente às permissões do usuário logado.
 */

import React, { useEffect, useState } from 'react';
import { 
  Users, Shield, Building2, RefreshCw, CheckCircle2, 
  ArrowUpRight, TrendingUp, DollarSign
} from 'lucide-react';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, 
  CartesianGrid, PieChart, Pie, Cell
} from 'recharts';
import { identityService } from '@/services/api';
import { User, Role, Organization } from '@/types';
import { Navbar } from '@/components/Navbar';
import { usePermissions } from '@/hooks/usePermissions';
import './Dashboard.scss';

// Dados de Exemplo para os Gráficos Analíticos
const dadosCompras = [
  { mes: 'Jan', compras: 14500, orcamento: 18000 },
  { mes: 'Fev', compras: 19800, orcamento: 20000 },
  { mes: 'Mar', compras: 16200, orcamento: 19000 },
  { mes: 'Abr', compras: 24300, orcamento: 22000 },
  { mes: 'Mai', compras: 21500, orcamento: 25000 },
  { mes: 'Jun', compras: 28900, orcamento: 30000 },
];

const dadosCategorias = [
  { name: 'Estoque & Matéria-Prima', value: 45, color: '#ff5500' },
  { name: 'Contas & Fornecedores', value: 25, color: '#3b82f6' },
  { name: 'Logística & Frota', value: 18, color: '#a855f7' },
  { name: 'Infraestrutura & TI', value: 12, color: '#10b981' },
];

// Tooltip Minimalista para os Gráficos
const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="custom-chart-tooltip">
        <p className="tooltip-label">{label}</p>
        <div className="tooltip-list">
          {payload.map((item: any, idx: number) => (
            <div key={idx} className="tooltip-row">
              <span className="tooltip-dot" style={{ background: item.stroke || item.color }} />
              <span className="tooltip-name">{item.name}:</span>
              <span className="tooltip-val">R$ {item.value.toLocaleString('pt-BR')}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }
  return null;
};

export const Dashboard: React.FC = () => {
  const { hasPermission, loading: permissionsLoading } = usePermissions();

  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [organizations, setOrganizations] = useState<Organization[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);

    try {
      // 🛡️ Busca SOMENTE os dados para os quais o usuário logado possui permissão
      const promises: Promise<any>[] = [];

      if (hasPermission('users:view')) {
        promises.push(identityService.getUsers().then(res => setUsers(res)).catch(() => setUsers([])));
      } else {
        setUsers([]);
      }

      if (hasPermission('roles:view')) {
        promises.push(identityService.getRoles().then(res => setRoles(res)).catch(() => setRoles([])));
      } else {
        setRoles([]);
      }

      if (hasPermission('organizations:view')) {
        promises.push(identityService.getOrganizations().then(res => setOrganizations(res)).catch(() => setOrganizations([])));
      } else {
        setOrganizations([]);
      }

      await Promise.all(promises);
    } catch (err: any) {
      console.error('Erro ao carregar dados do Dashboard:', err);
      // Não exibe erro para bloqueios de permissão esperados
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!permissionsLoading) {
      loadData();
    }
  }, [permissionsLoading]);

  return (
    <div className="dashboard-page">
      <Navbar />

      <main className="dashboard-content">
        {/* Cabeçalho Executivo Slim */}
        <header className="page-header">
          <div className="header-titles">
            <h1>Painel Executivo</h1>
            <p>Acompanhamento de compras, unidades e acessos operacionais</p>
          </div>

          <div className="header-actions">
            <button className="btn-refresh" onClick={loadData} disabled={loading} title="Atualizar Dados">
              <RefreshCw size={13} className={loading ? 'spin' : ''} />
              <span>Atualizar</span>
            </button>
          </div>
        </header>

        {error && (
          <div className="alert-error">
            <span>{error}</span>
          </div>
        )}

        {/* 1. CARDS DE KPIS EM GRID RESPONSIVO (Exibe apenas o que o usuário tem permissão) */}
        <section className="metrics-grid">
          
          {/* Card de Organizações: Somente se tiver permissão organizations:view */}
          {hasPermission('organizations:view') && (
            <div className="metric-card">
              <div className="metric-header">
                <span className="metric-title">Organizações</span>
                <Building2 size={15} className="metric-icon icon-brand" />
              </div>
              <div className="metric-body">
                <span className="metric-value">{organizations.length}</span>
                <span className="metric-tag green">
                  <ArrowUpRight size={11} />
                  Ativas
                </span>
              </div>
              <span className="metric-footer">Empresas e filiais cadastradas</span>
            </div>
          )}

          {/* Card de Usuários: Somente se tiver permissão users:view */}
          {hasPermission('users:view') && (
            <div className="metric-card">
              <div className="metric-header">
                <span className="metric-title">Usuários Ativos</span>
                <Users size={15} className="metric-icon icon-blue" />
              </div>
              <div className="metric-body">
                <span className="metric-value">{users.length}</span>
                <span className="metric-tag green">
                  <CheckCircle2 size={11} />
                  Online
                </span>
              </div>
              <span className="metric-footer">Contas com acesso ao sistema</span>
            </div>
          )}

          {/* Card de Cargos/Perfis: Somente se tiver permissão roles:view */}
          {hasPermission('roles:view') && (
            <div className="metric-card">
              <div className="metric-header">
                <span className="metric-title">Perfis de Acesso</span>
                <Shield size={15} className="metric-icon icon-purple" />
              </div>
              <div className="metric-body">
                <span className="metric-value">{roles.length}</span>
                <span className="metric-tag neutral">
                  Níveis
                </span>
              </div>
              <span className="metric-footer">Políticas de permissão</span>
            </div>
          )}

          {/* Card de Compras do Mês (Métricas de Compras e Operação) */}
          <div className="metric-card">
            <div className="metric-header">
              <span className="metric-title">Compras do Mês</span>
              <DollarSign size={15} className="metric-icon icon-emerald" />
            </div>
            <div className="metric-body">
              <span className="metric-value">R$ 28.9k</span>
              <span className="metric-tag green">
                <TrendingUp size={11} />
                +14.2%
              </span>
            </div>
            <span className="metric-footer">Volume consolidado em Junho</span>
          </div>
        </section>

        {/* 2. SEÇÃO DE GRÁFICOS ANALÍTICOS (RECHARTS) */}
        <section className="charts-grid">
          
          {/* Gráfico Principal: Área de Compras vs Orçamento */}
          <div className="panel-card chart-area-panel">
            <div className="panel-header">
              <div>
                <h2>Evolução Financeira & Orçamento</h2>
                <p>Comparativo semestral de aquisições</p>
              </div>
              <div className="legend-items">
                <span className="legend-badge"><span className="dot dot-brand" /> Compras</span>
                <span className="legend-badge"><span className="dot dot-blue" /> Orçamento</span>
              </div>
            </div>

            <div className="chart-wrapper">
              <ResponsiveContainer width="100%" height={320}>
                <AreaChart data={dadosCompras} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="gradientCompras" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ff5500" stopOpacity={0.35} />
                      <stop offset="95%" stopColor="#ff5500" stopOpacity={0.0} />
                    </linearGradient>
                    <linearGradient id="gradientOrcamento" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>

                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(128, 128, 128, 0.12)" vertical={false} />
                  <XAxis dataKey="mes" stroke="var(--text-muted)" fontSize={11} tickLine={false} />
                  <YAxis stroke="var(--text-muted)" fontSize={11} tickLine={false} tickFormatter={(v) => `k${v/1000}`} />
                  <Tooltip content={<CustomTooltip />} />
                  
                  <Area 
                    type="monotone" 
                    dataKey="orcamento" 
                    name="Orçamento"
                    stroke="#3b82f6" 
                    strokeWidth={1.5}
                    fillOpacity={1} 
                    fill="url(#gradientOrcamento)" 
                  />
                  <Area 
                    type="monotone" 
                    dataKey="compras" 
                    name="Compras"
                    stroke="#ff5500" 
                    strokeWidth={2.5}
                    fillOpacity={1} 
                    fill="url(#gradientCompras)" 
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Gráfico Secundário: Donut de Categorias */}
          <div className="panel-card chart-donut-panel">
            <div className="panel-header">
              <div>
                <h2>Alocação por Módulo</h2>
                <p>Distribuição de despesas</p>
              </div>
            </div>

            <div className="donut-body">
              <div className="donut-render">
                <ResponsiveContainer width="100%" height={180}>
                  <PieChart>
                    <Pie
                      data={dadosCategorias}
                      cx="50%"
                      cy="50%"
                      innerRadius={52}
                      outerRadius={78}
                      paddingAngle={4}
                      dataKey="value"
                    >
                      {dadosCategorias.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} stroke="var(--bg-surface)" strokeWidth={2} />
                      ))}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
              </div>

              <div className="donut-stats">
                {dadosCategorias.map((item, idx) => (
                  <div key={idx} className="stat-row">
                    <span className="dot" style={{ background: item.color }} />
                    <span className="name">{item.name}</span>
                    <span className="percent">{item.value}%</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

        </section>
      </main>
    </div>
  );
};
