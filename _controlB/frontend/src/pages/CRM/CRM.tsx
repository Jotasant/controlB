/**
 * pages/CRM/CRM.tsx - Módulo de CRM, Funil de Vendas & Relacionamento (ControlB)
 */

import React, { useState, useEffect } from 'react';
import {
  Users, UserPlus, RefreshCw, Calendar,
  TrendingUp, Plus, X, ArrowRight, DollarSign,
  Phone, Mail
} from 'lucide-react';
import { crmService } from '@/services/api';
import { Lead, Opportunity } from '@/types';
import './CRM.scss';

const PIPELINE_STAGES = [
  { id: 'PROSPECTING', label: 'Prospecção', color: '#10b981' },
  { id: 'QUALIFICATION', label: 'Qualificação', color: '#3b82f6' },
  { id: 'PROPOSAL', label: 'Proposta Comercial', color: '#f59e0b' },
  { id: 'NEGOTIATION', label: 'Negociação', color: '#8b5cf6' },
  { id: 'WON', label: 'Ganho / Fechado', color: '#10b981' },
  { id: 'LOST', label: 'Perdido', color: '#ef4444' }
];

export const CRM: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'pipeline' | 'leads'>('pipeline');
  const [loading, setLoading] = useState<boolean>(true);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);

  // Modais
  const [isLeadModalOpen, setIsLeadModalOpen] = useState<boolean>(false);
  const [isOppModalOpen, setIsOppModalOpen] = useState<boolean>(false);

  // Forms
  const [leadForm, setLeadForm] = useState({
    name: '',
    company_name: '',
    email: '',
    phone: '',
    lead_source: 'WEBSITE',
    notes: ''
  });

  const [oppForm, setOppForm] = useState({
    title: '',
    customer_name: '',
    estimated_amount: '',
    probability_percent: 50,
    expected_closing_date: '',
    stage: 'PROSPECTING',
    notes: ''
  });

  const loadCRMData = async () => {
    setLoading(true);
    try {
      const [leadsRes, oppsRes] = await Promise.all([
        crmService.getLeads().catch(() => []),
        crmService.getOpportunities().catch(() => [])
      ]);
      setLeads(leadsRes);
      setOpportunities(oppsRes);
    } catch (err) {
      console.error("Erro ao carregar CRM:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCRMData();
  }, []);

  const fmtCurrency = (val: number | undefined | null) => {
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val || 0);
  };

  const handleCreateLead = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await crmService.createLead({
        name: leadForm.name,
        company_name: leadForm.company_name || undefined,
        email: leadForm.email || undefined,
        phone: leadForm.phone || undefined,
        source: leadForm.lead_source || undefined
      });
      setIsLeadModalOpen(false);
      setLeadForm({
        name: '',
        company_name: '',
        email: '',
        phone: '',
        lead_source: 'WEBSITE',
        notes: ''
      });
      loadCRMData();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Erro ao cadastrar lead.");
    }
  };

  const handleCreateOpp = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await crmService.createOpportunity({
        title: oppForm.title,
        customer_name: oppForm.customer_name,
        estimated_amount: parseFloat(oppForm.estimated_amount || '0'),
        probability_percent: oppForm.probability_percent,
        expected_closing_date: oppForm.expected_closing_date ? new Date(oppForm.expected_closing_date).toISOString() : undefined,
        stage: oppForm.stage
      });
      setIsOppModalOpen(false);
      setOppForm({
        title: '',
        customer_name: '',
        estimated_amount: '',
        probability_percent: 50,
        expected_closing_date: '',
        stage: 'PROSPECTING',
        notes: ''
      });
      loadCRMData();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Erro ao cadastrar oportunidade.");
    }
  };

  const handleAdvanceStage = async (oppId: string, currentStage: string) => {
    const stageIdx = PIPELINE_STAGES.findIndex(s => s.id === currentStage);
    if (stageIdx >= 0 && stageIdx < PIPELINE_STAGES.length - 2) {
      const nextStage = PIPELINE_STAGES[stageIdx + 1].id;
      try {
        await crmService.updateOpportunityStage(oppId, nextStage);
        loadCRMData();
      } catch (err) {
        console.error("Erro ao avançar estágio:", err);
      }
    }
  };

  const totalPipelineAmount = opportunities
    .filter(o => o.stage !== 'LOST')
    .reduce((acc, o) => acc + (o.estimated_amount || 0), 0);

  const wonAmount = opportunities
    .filter(o => o.stage === 'WON')
    .reduce((acc, o) => acc + (o.estimated_amount || 0), 0);

  return (
    <div className="crm-page">
      <div className="crm-layout">
        {/* 1. SIDEBAR LATERAL ESQUERDA */}
        <aside className="sidebar-left">
          <div className="sidebar-header">
            <Users className="brand-icon" size={20} />
            <div className="sidebar-title-wrap">
              <span className="sidebar-title"><strong>Módulo CRM</strong></span>
              <span className="sidebar-subtitle">Gestão de Clientes</span>
            </div>
          </div>

          <nav className="nav-menu">
            <span className="menu-group-label">Pipeline & Contatos</span>

            <button
              className={`nav-item ${activeTab === 'pipeline' ? 'active' : ''}`}
              onClick={() => setActiveTab('pipeline')}
            >
              <div className="nav-item-content">
                <TrendingUp size={16} />
                <span>Funil de Vendas (Kanban)</span>
              </div>
              <span className="nav-badge">{opportunities.length}</span>
            </button>

            <button
              className={`nav-item ${activeTab === 'leads' ? 'active' : ''}`}
              onClick={() => setActiveTab('leads')}
            >
              <div className="nav-item-content">
                <UserPlus size={16} />
                <span>Base de Leads & Prospects</span>
              </div>
              <span className="nav-badge">{leads.length}</span>
            </button>
          </nav>
        </aside>

        {/* 2. CONTEÚDO PRINCIPAL */}
        <main className="main-content">
          <div className="content-header">
            <div className="header-titles">
              <h1>
                {activeTab === 'pipeline' && 'Funil de Oportunidades (Pipeline Comercial)'}
                {activeTab === 'leads' && 'Base de Leads & Contatos Qualificados'}
              </h1>
              <p className="subtitle">Prospecção estratégica, qualificação e conversão de novos clientes</p>
            </div>

            <div className="header-actions">
              <button className="btn-refresh" onClick={loadCRMData} title="Atualizar Dados">
                <RefreshCw size={15} className={loading ? 'spinning' : ''} />
              </button>

              <button className="btn-secondary" onClick={() => setIsLeadModalOpen(true)}>
                <UserPlus size={16} />
                <span>Novo Lead</span>
              </button>

              <button className="btn-primary" onClick={() => setIsOppModalOpen(true)}>
                <Plus size={16} />
                <span>Nova Oportunidade</span>
              </button>
            </div>
          </div>

          {/* Cards de Métricas Principais */}
          <div className="kpi-grid">
            <div className="kpi-card">
              <div className="kpi-top">
                <span className="kpi-label">Volume Total em Pipeline</span>
                <DollarSign size={18} />
              </div>
              <div className="kpi-value">{fmtCurrency(totalPipelineAmount)}</div>
              <div className="kpi-sub">{opportunities.filter(o => o.stage !== 'LOST').length} negócios ativos</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-top">
                <span className="kpi-label">Receita Fechada (Ganha)</span>
                <TrendingUp size={18} />
              </div>
              <div className="kpi-value">{fmtCurrency(wonAmount)}</div>
              <div className="kpi-sub">{opportunities.filter(o => o.stage === 'WON').length} oportunidades em WON</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-top">
                <span className="kpi-label">Total de Leads Prospectados</span>
                <Users size={18} />
              </div>
              <div className="kpi-value">{leads.length}</div>
              <div className="kpi-sub">Contatos cadastrados no funil</div>
            </div>
          </div>

          {/* Kanban Board */}
          {activeTab === 'pipeline' && (
            <div className="kanban-board">
              {PIPELINE_STAGES.map((stage) => {
                const stageOpps = opportunities.filter(o => o.stage === stage.id);
                const stageTotal = stageOpps.reduce((acc, o) => acc + (o.estimated_amount || 0), 0);

                return (
                  <div key={stage.id} className="kanban-column">
                    <div className="column-header" style={{ borderTopColor: stage.color }}>
                      <div className="title-row">
                        <span className="stage-name">{stage.label}</span>
                        <span className="count-badge">{stageOpps.length}</span>
                      </div>
                      <div className="stage-amount">{fmtCurrency(stageTotal)}</div>
                    </div>

                    <div className="column-cards">
                      {stageOpps.length === 0 ? (
                        <div className="empty-col">Nenhum negócio</div>
                      ) : (
                        stageOpps.map((opp) => (
                          <div key={opp.id} className="opp-card">
                            <div className="opp-header">
                              <h4>{opp.title}</h4>
                              <span className="opp-prob">{opp.probability_percent}%</span>
                            </div>
                            <div className="opp-customer">{opp.customer_name}</div>
                            <div className="opp-amount">{fmtCurrency(opp.estimated_amount)}</div>
                            {opp.expected_closing_date && (
                              <div className="opp-date">
                                <Calendar size={12} />
                                <span>{new Date(opp.expected_closing_date).toLocaleDateString('pt-BR')}</span>
                              </div>
                            )}
                            {stage.id !== 'WON' && stage.id !== 'LOST' && (
                              <div className="opp-actions">
                                <button
                                  className="btn-advance"
                                  onClick={() => handleAdvanceStage(opp.id, opp.stage)}
                                  title="Avançar para próximo estágio"
                                >
                                  <span>Avançar</span>
                                  <ArrowRight size={12} />
                                </button>
                              </div>
                            )}
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Tabela de Leads */}
          {activeTab === 'leads' && (
            <div className="table-card">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Nome do Lead</th>
                    <th>Empresa</th>
                    <th>E-mail</th>
                    <th>Telefone</th>
                    <th>Origem</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {leads.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="empty-row">
                        Nenhum lead cadastrado ainda.
                      </td>
                    </tr>
                  ) : (
                    leads.map((lead) => (
                      <tr key={lead.id}>
                        <td><strong>{lead.name}</strong></td>
                        <td>{lead.company_name || '-'}</td>
                        <td>
                          {lead.email ? (
                            <div className="cell-contact">
                              <Mail size={13} /> <span>{lead.email}</span>
                            </div>
                          ) : '-'}
                        </td>
                        <td>
                          {lead.phone ? (
                            <div className="cell-contact">
                              <Phone size={13} /> <span>{lead.phone}</span>
                            </div>
                          ) : '-'}
                        </td>
                        <td>{lead.source || '-'}</td>
                        <td><span className="status-badge">{lead.status}</span></td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </main>
      </div>

      {/* Modal Novo Lead */}
      {isLeadModalOpen && (
        <div className="modal-overlay">
          <div className="modal-box">
            <div className="modal-head">
              <h3>Novo Lead / Prospect</h3>
              <button className="btn-close-modal" onClick={() => setIsLeadModalOpen(false)}>
                <X size={18} />
              </button>
            </div>
            <form onSubmit={handleCreateLead}>
              <div className="modal-content-body">
                <div className="form-field">
                  <label>Nome do Contato *</label>
                  <input
                    type="text"
                    required
                    placeholder="Ex: Carlos Mendonça"
                    value={leadForm.name}
                    onChange={(e) => setLeadForm({ ...leadForm, name: e.target.value })}
                  />
                </div>

                <div className="form-field">
                  <label>Empresa / Razão Social</label>
                  <input
                    type="text"
                    placeholder="Ex: Distribuidora Sol Ltda"
                    value={leadForm.company_name}
                    onChange={(e) => setLeadForm({ ...leadForm, company_name: e.target.value })}
                  />
                </div>

                <div className="form-row">
                  <div className="form-field flex-1">
                    <label>E-mail</label>
                    <input
                      type="email"
                      placeholder="carlos@exemplo.com"
                      value={leadForm.email}
                      onChange={(e) => setLeadForm({ ...leadForm, email: e.target.value })}
                    />
                  </div>

                  <div className="form-field flex-1">
                    <label>Telefone / WhatsApp</label>
                    <input
                      type="text"
                      placeholder="(11) 98765-4321"
                      value={leadForm.phone}
                      onChange={(e) => setLeadForm({ ...leadForm, phone: e.target.value })}
                    />
                  </div>
                </div>

                <div className="form-field">
                  <label>Origem do Lead</label>
                  <select
                    value={leadForm.lead_source}
                    onChange={(e) => setLeadForm({ ...leadForm, lead_source: e.target.value })}
                  >
                    <option value="WEBSITE">Site / Formulário</option>
                    <option value="INDICATION">Indicação</option>
                    <option value="PHONE">Contato Telefônico</option>
                    <option value="EVENT">Evento / Feira</option>
                    <option value="OUTBOUND">Prospecção Ativa (Outbound)</option>
                  </select>
                </div>

                <div className="form-field">
                  <label>Observações</label>
                  <textarea
                    rows={2}
                    placeholder="Detalhes sobre as necessidades do cliente..."
                    value={leadForm.notes}
                    onChange={(e) => setLeadForm({ ...leadForm, notes: e.target.value })}
                  />
                </div>
              </div>

              <div className="modal-foot">
                <button type="button" className="btn-cancel" onClick={() => setIsLeadModalOpen(false)}>
                  Cancelar
                </button>
                <button type="submit" className="btn-submit">
                  Salvar Lead
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal Nova Oportunidade */}
      {isOppModalOpen && (
        <div className="modal-overlay">
          <div className="modal-box">
            <div className="modal-head">
              <h3>Nova Oportunidade Comercial</h3>
              <button className="btn-close-modal" onClick={() => setIsOppModalOpen(false)}>
                <X size={18} />
              </button>
            </div>
            <form onSubmit={handleCreateOpp}>
              <div className="modal-content-body">
                <div className="form-field">
                  <label>Título do Negócio *</label>
                  <input
                    type="text"
                    required
                    placeholder="Ex: Fornecimento Mensal de Insumos"
                    value={oppForm.title}
                    onChange={(e) => setOppForm({ ...oppForm, title: e.target.value })}
                  />
                </div>

                <div className="form-field">
                  <label>Nome do Cliente / Empresa *</label>
                  <input
                    type="text"
                    required
                    placeholder="Ex: Clínica Boa Saúde"
                    value={oppForm.customer_name}
                    onChange={(e) => setOppForm({ ...oppForm, customer_name: e.target.value })}
                  />
                </div>

                <div className="form-row">
                  <div className="form-field flex-1">
                    <label>Valor Estimado (R$) *</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0.01"
                      required
                      placeholder="0,00"
                      value={oppForm.estimated_amount}
                      onChange={(e) => setOppForm({ ...oppForm, estimated_amount: e.target.value })}
                    />
                  </div>

                  <div className="form-field flex-1">
                    <label>Probabilidade (%)</label>
                    <input
                      type="number"
                      min="0"
                      max="100"
                      value={oppForm.probability_percent}
                      onChange={(e) => setOppForm({ ...oppForm, probability_percent: parseInt(e.target.value) || 0 })}
                    />
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-field flex-1">
                    <label>Previsão de Fechamento</label>
                    <input
                      type="date"
                      value={oppForm.expected_closing_date}
                      onChange={(e) => setOppForm({ ...oppForm, expected_closing_date: e.target.value })}
                    />
                  </div>

                  <div className="form-field flex-1">
                    <label>Estágio Inicial</label>
                    <select
                      value={oppForm.stage}
                      onChange={(e) => setOppForm({ ...oppForm, stage: e.target.value })}
                    >
                      {PIPELINE_STAGES.map(s => (
                        <option key={s.id} value={s.id}>{s.label}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="form-field">
                  <label>Observações</label>
                  <textarea
                    rows={2}
                    placeholder="Notas da negociação..."
                    value={oppForm.notes}
                    onChange={(e) => setOppForm({ ...oppForm, notes: e.target.value })}
                  />
                </div>
              </div>

              <div className="modal-foot">
                <button type="button" className="btn-cancel" onClick={() => setIsOppModalOpen(false)}>
                  Cancelar
                </button>
                <button type="submit" className="btn-submit">
                  Salvar Oportunidade
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default CRM;
