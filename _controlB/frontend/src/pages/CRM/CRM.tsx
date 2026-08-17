/**
 * pages/CRM/CRM.tsx - Módulo de CRM, Funil de Vendas & Relacionamento (ControlB)
 * Integrado conceitualmente ao padrão Odoo:
 * - Base centralizada de Clientes / Contatos
 * - Oportunidades vinculadas a 1:N Cotações Comerciais
 * - Geração de Cotações com produtos do inventário e avanço automático no pipeline
 */

import React, { useState, useEffect } from 'react';
import {
  Users, UserPlus, RefreshCw, Calendar,
  TrendingUp, Plus, ArrowRight, DollarSign,
  Phone, Mail, FileText, UserCheck, Trash2
} from 'lucide-react';
import { crmService, salesService, inventoryService, formatApiError } from '@/services/api';
import { Lead, Opportunity, Customer, Product, SalesQuote } from '@/types';
import { Modal } from '@/components/Modal/Modal';
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
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [quotes, setQuotes] = useState<SalesQuote[]>([]);

  // Modais
  const [isLeadModalOpen, setIsLeadModalOpen] = useState<boolean>(false);
  const [isOppModalOpen, setIsOppModalOpen] = useState<boolean>(false);
  const [isQuoteModalOpen, setIsQuoteModalOpen] = useState<boolean>(false);
  const [selectedOppForQuote, setSelectedOppForQuote] = useState<Opportunity | null>(null);

  // Form Lead
  const [leadForm, setLeadForm] = useState({
    name: '',
    company_name: '',
    email: '',
    phone: '',
    lead_source: 'WEBSITE',
    notes: ''
  });

  // Form Oportunidade
  const [oppForm, setOppForm] = useState({
    title: '',
    customer_id: '',
    customer_name: '',
    estimated_amount: '',
    probability_percent: 50,
    expected_closing_date: '',
    stage: 'PROSPECTING',
    notes: ''
  });

  // Form Cotação vinculada
  const [quoteItems, setQuoteItems] = useState<Array<{
    product_id: string;
    quantity: number;
    unit_price: number;
    discount_amount: number;
    notes?: string;
  }>>([]);
  const [quotePaymentTerms, setQuotePaymentTerms] = useState<string>('30 DDL');
  const [quoteValidUntil, setQuoteValidUntil] = useState<string>('');
  const [isSavingQuote, setIsSavingQuote] = useState<boolean>(false);

  const loadCRMData = async () => {
    setLoading(true);
    try {
      const [leadsRes, oppsRes, custsRes, prodsRes, quotesRes] = await Promise.all([
        crmService.getLeads().catch(() => []),
        crmService.getOpportunities().catch(() => []),
        salesService.getCustomers().catch(() => []),
        inventoryService.getProducts().catch(() => []),
        salesService.getQuotes().catch(() => [])
      ]);
      setLeads(leadsRes);
      setOpportunities(oppsRes);
      setCustomers(custsRes);
      setProducts(prodsRes);
      setQuotes(quotesRes);
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
    if (!leadForm.name.trim()) {
      alert("O nome do contato / lead é obrigatório.");
      return;
    }
    try {
      await crmService.createLead({
        name: leadForm.name.trim(),
        company_name: leadForm.company_name?.trim() || undefined,
        email: leadForm.email?.trim() || undefined,
        phone: leadForm.phone?.trim() || undefined,
        source: leadForm.lead_source || "Indicação",
        notes: leadForm.notes?.trim() || undefined
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
      alert(formatApiError(err, "Erro ao cadastrar lead."));
    }
  };

  const handleCustomerSelectChange = (custId: string) => {
    if (!custId) {
      setOppForm(prev => ({ ...prev, customer_id: '', customer_name: '' }));
      return;
    }
    const found = customers.find(c => c.id === custId);
    if (found) {
      setOppForm(prev => ({
        ...prev,
        customer_id: found.id,
        customer_name: found.trade_name || found.name
      }));
    }
  };

  const handleCreateOpp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!oppForm.title.trim()) {
      alert("O título da oportunidade é obrigatório.");
      return;
    }
    if (!oppForm.customer_name.trim()) {
      alert("O nome do cliente / empresa é obrigatório.");
      return;
    }
    const amount = parseFloat(oppForm.estimated_amount || '0');
    if (isNaN(amount) || amount < 0) {
      alert("Informe um valor estimado válido.");
      return;
    }
    try {
      await crmService.createOpportunity({
        title: oppForm.title.trim(),
        customer_id: oppForm.customer_id || undefined,
        customer_name: oppForm.customer_name.trim(),
        estimated_amount: amount,
        probability_percent: oppForm.probability_percent,
        expected_closing_date: oppForm.expected_closing_date ? oppForm.expected_closing_date : undefined,
        stage: oppForm.stage
      });
      setIsOppModalOpen(false);
      setOppForm({
        title: '',
        customer_id: '',
        customer_name: '',
        estimated_amount: '',
        probability_percent: 50,
        expected_closing_date: '',
        stage: 'PROSPECTING',
        notes: ''
      });
      loadCRMData();
    } catch (err: any) {
      alert(formatApiError(err, "Erro ao cadastrar oportunidade."));
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

  const handleOpenQuoteModal = (opp: Opportunity) => {
    setSelectedOppForQuote(opp);
    setQuoteValidUntil(opp.expected_closing_date || '');
    setQuotePaymentTerms('30 DDL');
    if (products.length > 0) {
      setQuoteItems([{
        product_id: products[0].id,
        quantity: 1,
        unit_price: Number(products[0].reference_price) || (opp.estimated_amount > 0 ? opp.estimated_amount : 10.00),
        discount_amount: 0
      }]);
    } else {
      setQuoteItems([]);
    }
    setIsQuoteModalOpen(true);
  };

  const handleAddQuoteItem = () => {
    if (products.length > 0) {
      setQuoteItems([
        ...quoteItems,
        {
          product_id: products[0].id,
          quantity: 1,
          unit_price: Number(products[0].reference_price) || 10.00,
          discount_amount: 0
        }
      ]);
    }
  };

  const handleRemoveQuoteItem = (index: number) => {
    setQuoteItems(quoteItems.filter((_, idx) => idx !== index));
  };

  const handleSaveOpportunityQuote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedOppForQuote) return;
    if (quoteItems.length === 0) {
      alert("Adicione pelo menos um item à cotação.");
      return;
    }

    setIsSavingQuote(true);
    try {
      await salesService.createQuote({
        customer_id: selectedOppForQuote.customer_id || undefined,
        opportunity_id: selectedOppForQuote.id,
        customer_name: selectedOppForQuote.customer_name,
        payment_terms: quotePaymentTerms,
        valid_until: quoteValidUntil || undefined,
        notes: `Cotação originada da Oportunidade CRM: ${selectedOppForQuote.title}`,
        items: quoteItems.map(it => ({
          product_id: it.product_id,
          quantity: it.quantity,
          unit_price: it.unit_price,
          discount_amount: it.discount_amount,
          notes: it.notes
        }))
      });

      // Avança a oportunidade para PROPOSAL caso ainda esteja em estágio anterior
      if (['PROSPECTING', 'QUALIFICATION'].includes(selectedOppForQuote.stage)) {
        await crmService.updateOpportunityStage(selectedOppForQuote.id, 'PROPOSAL');
      }

      setIsQuoteModalOpen(false);
      setSelectedOppForQuote(null);
      alert("Cotação emitida com sucesso e vinculada à oportunidade!");
      loadCRMData();
    } catch (err: any) {
      alert(formatApiError(err, "Erro ao gerar cotação para a oportunidade."));
    } finally {
      setIsSavingQuote(false);
    }
  };

  const handleConvertLeadToCustomer = async (leadId: string) => {
    try {
      await crmService.convertLeadToCustomer(leadId);
      alert("Lead convertido com sucesso em Cliente no Módulo de Vendas e Contato no Identity!");
      loadCRMData();
    } catch (err: any) {
      alert(formatApiError(err, "Erro ao converter lead em cliente."));
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
                <span>Funil de Oportunidades</span>
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
                        stageOpps.map((opp) => {
                          // Busca cotações vinculadas
                          const linkedQuotes = quotes.filter(q => q.opportunity_id === opp.id || (opp.quotes && opp.quotes.some(oq => oq.id === q.id)));

                          return (
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

                              {/* Cotações Vinculadas */}
                              {linkedQuotes.length > 0 && (
                                <div className="opp-quotes-list" style={{ marginTop: '0.35rem', paddingTop: '0.35rem', borderTop: '1px dashed var(--border-subtle)' }}>
                                  <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontWeight: 600, display: 'block', marginBottom: '0.2rem' }}>
                                    Cotações ({linkedQuotes.length}):
                                  </span>
                                  {linkedQuotes.map(q => (
                                    <div key={q.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.7rem', background: 'var(--bg-surface)', padding: '0.2rem 0.4rem', borderRadius: '4px', marginBottom: '0.2rem' }}>
                                      <span><strong>{q.quote_number}</strong>: {fmtCurrency(q.net_amount)}</span>
                                      <span style={{ fontSize: '0.65rem', padding: '0.05rem 0.3rem', borderRadius: '3px', background: q.status === 'CONVERTED' ? '#10b981' : '#f59e0b', color: '#fff', fontWeight: 600 }}>
                                        {q.status}
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              )}

                              <div className="opp-actions">
                                <button
                                  type="button"
                                  className="btn-quote"
                                  onClick={() => handleOpenQuoteModal(opp)}
                                  title="Nova Cotação no Módulo de Vendas"
                                >
                                  <FileText size={12} />
                                  <span>Nova Cotação</span>
                                </button>

                                {stage.id !== 'WON' && stage.id !== 'LOST' && (
                                  <button
                                    type="button"
                                    className="btn-advance"
                                    onClick={() => handleAdvanceStage(opp.id, opp.stage)}
                                    title="Avançar para próximo estágio"
                                  >
                                    <span>Avançar</span>
                                    <ArrowRight size={12} />
                                  </button>
                                )}
                              </div>
                            </div>
                          );
                        })
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
                    <th>Ações</th>
                  </tr>
                </thead>
                <tbody>
                  {leads.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="empty-row">
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
                        <td>
                          {lead.status !== 'CONVERTED' ? (
                            <button
                              type="button"
                              className="btn-convert-lead"
                              onClick={() => handleConvertLeadToCustomer(lead.id)}
                              title="Converter em Cliente no Módulo de Vendas"
                            >
                              <UserCheck size={13} /> Converter em Cliente
                            </button>
                          ) : (
                            <span className="converted-tag">Cliente Ativo</span>
                          )}
                        </td>
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
      <Modal
        isOpen={isLeadModalOpen}
        onClose={() => setIsLeadModalOpen(false)}
        title="Novo Lead / Prospect"
        subtitle="Cadastro de novo contato no funil de vendas"
        size="md"
      >
        <form onSubmit={handleCreateLead} className="wizard-form">
          <div className="form-group">
            <label>Nome do Contato *</label>
            <input
              type="text"
              required
              placeholder="Ex: Carlos Mendonça"
              value={leadForm.name}
              onChange={(e) => setLeadForm({ ...leadForm, name: e.target.value })}
            />
          </div>

          <div className="form-group">
            <label>Empresa / Razão Social</label>
            <input
              type="text"
              placeholder="Ex: Distribuidora Sol Ltda"
              value={leadForm.company_name}
              onChange={(e) => setLeadForm({ ...leadForm, company_name: e.target.value })}
            />
          </div>

          <div className="form-row">
            <div className="form-group flex-1">
              <label>E-mail</label>
              <input
                type="email"
                placeholder="carlos@exemplo.com"
                value={leadForm.email}
                onChange={(e) => setLeadForm({ ...leadForm, email: e.target.value })}
              />
            </div>

            <div className="form-group flex-1">
              <label>Telefone / WhatsApp</label>
              <input
                type="text"
                placeholder="(11) 98765-4321"
                value={leadForm.phone}
                onChange={(e) => setLeadForm({ ...leadForm, phone: e.target.value })}
              />
            </div>
          </div>

          <div className="form-group">
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

          <div className="modal-footer">
            <button type="button" className="btn-secondary" onClick={() => setIsLeadModalOpen(false)}>
              Cancelar (ESC)
            </button>
            <button type="submit" className="btn-primary">
              Salvar Lead
            </button>
          </div>
        </form>
      </Modal>

      {/* Modal Nova Oportunidade */}
      <Modal
        isOpen={isOppModalOpen}
        onClose={() => setIsOppModalOpen(false)}
        title="Nova Oportunidade Comercial"
        subtitle="Criação de negócio no pipeline de vendas integrado à base de clientes"
        size="md"
      >
        <form onSubmit={handleCreateOpp} className="wizard-form">
          <div className="form-group">
            <label>Título do Negócio *</label>
            <input
              type="text"
              required
              placeholder="Ex: Fornecimento Mensal de Insumos"
              value={oppForm.title}
              onChange={(e) => setOppForm({ ...oppForm, title: e.target.value })}
            />
          </div>

          <div className="form-group">
            <label>Cliente Centralizado (Vendas)</label>
            <select
              value={oppForm.customer_id}
              onChange={(e) => handleCustomerSelectChange(e.target.value)}
            >
              <option value="">-- Selecionar Cliente Existente ou Digitar Abaixo --</option>
              {customers.map(c => (
                <option key={c.id} value={c.id}>
                  {c.trade_name ? `${c.trade_name} (${c.name})` : c.name} - {c.document}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
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
            <div className="form-group flex-1">
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

            <div className="form-group flex-1">
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
            <div className="form-group flex-1">
              <label>Previsão de Fechamento</label>
              <input
                type="date"
                value={oppForm.expected_closing_date}
                onChange={(e) => setOppForm({ ...oppForm, expected_closing_date: e.target.value })}
              />
            </div>

            <div className="form-group flex-1">
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

          <div className="modal-footer">
            <button type="button" className="btn-secondary" onClick={() => setIsOppModalOpen(false)}>
              Cancelar (ESC)
            </button>
            <button type="submit" className="btn-primary">
              Salvar Oportunidade
            </button>
          </div>
        </form>
      </Modal>

      {/* Modal Nova Cotação Vinculada à Oportunidade */}
      <Modal
        isOpen={isQuoteModalOpen}
        onClose={() => {
          setIsQuoteModalOpen(false);
          setSelectedOppForQuote(null);
        }}
        title={`Nova Cotação Comercial: ${selectedOppForQuote?.title || ''}`}
        subtitle={`Cliente: ${selectedOppForQuote?.customer_name || ''}`}
        size="lg"
      >
        <form onSubmit={handleSaveOpportunityQuote} className="wizard-form">
          <div className="form-row">
            <div className="form-group flex-1">
              <label>Condição de Pagamento</label>
              <select
                value={quotePaymentTerms}
                onChange={(e) => setQuotePaymentTerms(e.target.value)}
              >
                <option value="À Vista">À Vista</option>
                <option value="30 DDL">30 DDL</option>
                <option value="30/60 DDL">30/60 DDL</option>
                <option value="PIX">PIX</option>
              </select>
            </div>
            <div className="form-group flex-1">
              <label>Validade da Cotação</label>
              <input
                type="date"
                value={quoteValidUntil}
                onChange={(e) => setQuoteValidUntil(e.target.value)}
              />
            </div>
          </div>

          <div className="form-items-section" style={{ marginTop: '1rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <h4 style={{ margin: 0, fontSize: '0.85rem' }}>Itens da Cotação (Catálogo de Produtos)</h4>
              <button type="button" className="btn-secondary sm" onClick={handleAddQuoteItem} style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }}>
                <Plus size={12} /> Adicionar Item
              </button>
            </div>

            {quoteItems.map((item, idx) => (
              <div key={idx} style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '0.5rem' }}>
                <div style={{ flex: 3 }}>
                  <select
                    value={item.product_id}
                    onChange={(e) => {
                      const pid = e.target.value;
                      const prod = products.find(p => p.id === pid);
                      const updated = [...quoteItems];
                      updated[idx].product_id = pid;
                      if (prod) updated[idx].unit_price = Number(prod.reference_price) || 10.00;
                      setQuoteItems(updated);
                    }}
                    style={{ width: '100%', padding: '0.4rem', borderRadius: '6px', border: '1px solid var(--border-subtle)', background: 'var(--bg-surface-elevated)', color: 'var(--text-primary)' }}
                  >
                    {products.map(p => (
                      <option key={p.id} value={p.id}>{p.name} ({p.sku})</option>
                    ))}
                  </select>
                </div>
                <div style={{ flex: 1 }}>
                  <input
                    type="number"
                    min="1"
                    placeholder="Qtd"
                    value={item.quantity}
                    onChange={(e) => {
                      const updated = [...quoteItems];
                      updated[idx].quantity = Math.max(1, parseInt(e.target.value) || 1);
                      setQuoteItems(updated);
                    }}
                    style={{ width: '100%', padding: '0.4rem', borderRadius: '6px', border: '1px solid var(--border-subtle)', background: 'var(--bg-surface-elevated)', color: 'var(--text-primary)' }}
                  />
                </div>
                <div style={{ flex: 1 }}>
                  <input
                    type="number"
                    step="0.01"
                    placeholder="Preço (R$)"
                    value={item.unit_price}
                    onChange={(e) => {
                      const updated = [...quoteItems];
                      updated[idx].unit_price = parseFloat(e.target.value) || 0;
                      setQuoteItems(updated);
                    }}
                    style={{ width: '100%', padding: '0.4rem', borderRadius: '6px', border: '1px solid var(--border-subtle)', background: 'var(--bg-surface-elevated)', color: 'var(--text-primary)' }}
                  />
                </div>
                <button
                  type="button"
                  onClick={() => handleRemoveQuoteItem(idx)}
                  style={{ background: 'transparent', border: 'none', color: '#ef4444', cursor: 'pointer', padding: '0.3rem' }}
                  title="Remover Item"
                >
                  <Trash2 size={15} />
                </button>
              </div>
            ))}
          </div>

          <div className="modal-footer" style={{ marginTop: '1.25rem' }}>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => {
                setIsQuoteModalOpen(false);
                setSelectedOppForQuote(null);
              }}
            >
              Cancelar (ESC)
            </button>
            <button type="submit" className="btn-primary" disabled={isSavingQuote}>
              {isSavingQuote ? 'Emitindo...' : 'Emitir Cotação e Avançar Funil'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

export default CRM;
