/**
 * pages/CRM/CRM.tsx - Módulo Central de CRM, Funil Comercial & Relacionamento (ControlB)
 * 
 * Funcionalidades das Fases 1 & 2:
 * 1. 📊 Menu Lateral Estruturado (Dashboard, Funil Kanban, Lista de Oportunidades, Leads, Atividades, Etapas)
 * 2. 🔀 Pipeline Kanban Moderno com Drag-and-Drop Nativo (HTML5) entre quaisquer etapas com contadores e totais em R$
 * 3. ❌ Modal Inteligente de Motivo de Perda ao mover para 'Perdido' ou clicar em Descartar
 * 4. 🔍 Gaveta / Visualização 360º da Oportunidade com Trilha Chevron de Estágios, Timeline, Atividades e Cotações
 * 5. 👥 Ciclo Completo de Qualificação de Leads (Status, WhatsApp direto, E-mail, Conversão direta em Oportunidade)
 * 6. 📅 Central de Atividades com Agenda e Filtros de Follow-up (Todas, Atrasadas, Hoje, Próximas, Concluídas)
 * 7. ⚙️ Gestão Dinâmica de Etapas do Funil com Cores, Ordenação e Contadores
 */

import React, { useState, useEffect, useMemo } from 'react';
import {
  LayoutDashboard, Kanban, ListFilter, Users,
  Clock, Phone, Mail, FileText,
  Trash2, Settings, CheckCircle2, Layers,
  Package, Plus, DollarSign, TrendingUp,
  RefreshCw, UserPlus, MessageSquare,
  ArrowRight, X, AlertTriangle,
  Building2, Send, Eye,
  Edit3, CalendarDays,
  ArrowUpRight, Check
} from 'lucide-react';
import { crmService, inventoryService, formatApiError } from '@/services/api';
import type { Lead, Opportunity, Product, SalesQuote, CRMStage, Customer, CustomerInteraction } from '@/types';
import { Modal } from '@/components/Modal/Modal';
import { CustomerPicker } from '@/components/CustomerPicker';
import { useToast } from '@/components/Toast/ToastContext';
import './CRM.scss';

const COLOR_PRESETS = [
  '#10b981', '#3b82f6', '#f59e0b', '#8b5cf6',
  '#ec4899', '#06b6d4', '#6366f1', '#ef4444'
];

const LOSS_REASONS = [
  'Preço acima do mercado / Sem desconto',
  'Concorrente escolhido',
  'Sem orçamento disponível no momento',
  'Cliente desistiu do projeto / Perdeu prioridade',
  'Projeto adiado / Congelado para o próximo trimestre',
  'Sem retorno do contato (Sem resposta aos follow-ups)',
  'Produto ou Serviço não atende aos requisitos técnicos',
  'Outro motivo'
];

export const DEFAULT_FALLBACK_STAGES: CRMStage[] = [
  { id: '1', organization_id: '', code: 'PROSPECTING', name: 'Prospecção', color: '#10b981', order: 0, is_won: false, is_lost: false, is_system: true, created_at: '', updated_at: '' },
  { id: '2', organization_id: '', code: 'QUALIFICATION', name: 'Qualificação', color: '#3b82f6', order: 1, is_won: false, is_lost: false, is_system: true, created_at: '', updated_at: '' },
  { id: '3', organization_id: '', code: 'PROPOSAL', name: 'Proposta Comercial', color: '#f59e0b', order: 2, is_won: false, is_lost: false, is_system: true, created_at: '', updated_at: '' },
  { id: '4', organization_id: '', code: 'NEGOTIATION', name: 'Negociação', color: '#8b5cf6', order: 3, is_won: false, is_lost: false, is_system: true, created_at: '', updated_at: '' },
  { id: '5', organization_id: '', code: 'WON', name: 'Ganho / Fechado', color: '#10b981', order: 4, is_won: true, is_lost: false, is_system: true, created_at: '', updated_at: '' },
  { id: '6', organization_id: '', code: 'LOST', name: 'Perdido', color: '#ef4444', order: 5, is_won: false, is_lost: true, is_system: true, created_at: '', updated_at: '' },
];

export const CRM: React.FC = () => {
  const toast = useToast();

  // Tab State
  const [activeTab, setActiveTab] = useState<'dashboard' | 'pipeline' | 'opportunities_list' | 'leads' | 'activities' | 'stages'>('pipeline');
  const [loading, setLoading] = useState<boolean>(true);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [stages, setStages] = useState<CRMStage[]>(DEFAULT_FALLBACK_STAGES);
  const [products, setProducts] = useState<Product[]>([]);
  const [allInteractions, setAllInteractions] = useState<CustomerInteraction[]>([]);

  // Filtros Oportunidades
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [stageFilter, setStageFilter] = useState<string>('ALL');

  // Filtros Leads (Fase 2)
  const [leadSearch, setLeadSearch] = useState<string>('');
  const [leadStatusFilter, setLeadStatusFilter] = useState<string>('ALL');
  const [editingLead, setEditingLead] = useState<Lead | null>(null);
  const [convertingLead, setConvertingLead] = useState<Lead | null>(null);
  const [editLeadForm, setEditLeadForm] = useState({
    name: '',
    company_name: '',
    email: '',
    phone: '',
    source: 'Indicação',
    status: 'NEW',
    notes: ''
  });

  // Filtros Atividades (Fase 2)
  const [activitySearch, setActivitySearch] = useState<string>('');
  const [activityTabFilter, setActivityTabFilter] = useState<'ALL' | 'OVERDUE' | 'TODAY' | 'UPCOMING' | 'COMPLETED'>('ALL');
  const [isGlobalActivityModalOpen, setIsGlobalActivityModalOpen] = useState<boolean>(false);
  const [globalActivityForm, setGlobalActivityForm] = useState({
    type: 'CALL',
    linked_type: 'OPPORTUNITY' as 'OPPORTUNITY' | 'LEAD',
    linked_id: '',
    summary: '',
    details: '',
    date: new Date().toISOString().split('T')[0],
    time: '14:00'
  });
  const [isSavingGlobalActivity, setIsSavingGlobalActivity] = useState<boolean>(false);

  // Drag and Drop State
  const [draggedOppId, setDraggedOppId] = useState<string | null>(null);
  const [dragOverStageCode, setDragOverStageCode] = useState<string | null>(null);

  // Detalhes 360º da Oportunidade (Drawer / Modal)
  const [selectedOpp, setSelectedOpp] = useState<Opportunity | null>(null);
  const [oppInteractions, setOppInteractions] = useState<CustomerInteraction[]>([]);
  const [oppQuotes, setOppQuotes] = useState<SalesQuote[]>([]);
  const [oppDrawerTab, setOppDrawerTab] = useState<'timeline' | 'quotes' | 'customer' | 'new_activity'>('timeline');

  // Nova Interação Rápida no Drawer
  const [quickActivityForm, setQuickActivityForm] = useState({
    type: 'CALL',
    summary: '',
    details: ''
  });
  const [isSavingActivity, setIsSavingActivity] = useState<boolean>(false);

  // Modal Motivo de Perda
  const [lossModalOpp, setLossModalOpp] = useState<Opportunity | null>(null);
  const [lossReason, setLossReason] = useState<string>(LOSS_REASONS[0]);
  const [lossCompetitor, setLossCompetitor] = useState<string>('');
  const [lossNotes, setLossNotes] = useState<string>('');
  const [isSavingLoss, setIsSavingLoss] = useState<boolean>(false);

  // Modais de Criação
  const [isLeadModalOpen, setIsLeadModalOpen] = useState<boolean>(false);
  const [isOppModalOpen, setIsOppModalOpen] = useState<boolean>(false);
  const [isQuoteModalOpen, setIsQuoteModalOpen] = useState<boolean>(false);
  const [selectedOppForQuote, setSelectedOppForQuote] = useState<Opportunity | null>(null);

  // Form Lead
  const [leadForm, setLeadForm] = useState({
    customer_id: '',
    name: '',
    company_name: '',
    document: '',
    email: '',
    phone: '',
    lead_source: 'Indicação',
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
    stage: '',
    notes: ''
  });

  // Form Nova Etapa
  const [newStageForm, setNewStageForm] = useState({
    name: '',
    code: '',
    color: '#10b981',
    order: 0,
    is_won: false,
    is_lost: false
  });
  const [isSavingStage, setIsSavingStage] = useState<boolean>(false);

  // Form Cotação vinculada
  const [quoteItems, setQuoteItems] = useState<Array<{
    product_id: string;
    quantity: number;
    unit_price: number;
    discount_amount: number;
    notes?: string;
  }>>([]);
  const [quoteValidUntil, setQuoteValidUntil] = useState<string>('');
  const [quotePaymentTerms, setQuotePaymentTerms] = useState<string>('30 DDL');
  const [isSavingQuote, setIsSavingQuote] = useState<boolean>(false);

  // ===========================================================================
  // CARREGAMENTO DE DADOS
  // ===========================================================================

  const loadCRMData = async (forceRefresh = false) => {
    setLoading(true);
    try {
      const [fetchedStages, fetchedLeads, fetchedOpps, fetchedProducts, fetchedInteractions] = await Promise.all([
        crmService.getStages(forceRefresh).catch(() => []),
        crmService.getLeads(undefined, forceRefresh).catch(() => []),
        crmService.getOpportunities(undefined, forceRefresh).catch(() => []),
        inventoryService.getProducts(undefined, forceRefresh).catch(() => []),
        crmService.getInteractions(undefined, undefined, forceRefresh).catch(() => [])
      ]);

      if (fetchedStages && fetchedStages.length > 0) {
        const sortedStages = [...fetchedStages].sort((a, b) => (a.order || 0) - (b.order || 0));
        setStages(sortedStages);
      } else {
        setStages(DEFAULT_FALLBACK_STAGES);
      }

      setLeads(fetchedLeads || []);
      setOpportunities(fetchedOpps || []);
      setProducts(fetchedProducts || []);
      setAllInteractions(fetchedInteractions || []);
    } catch (err: any) {
      toast.error(formatApiError(err, "Falha ao carregar dados do CRM."));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadCRMData();
  }, []);

  // Formatação
  const fmtCurrency = (val?: number | string | null) => {
    const n = typeof val === 'string' ? parseFloat(val) : (val ?? 0);
    return isNaN(n) ? 'R$ 0,00' : n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  };

  const fmtDate = (d?: string | null) => {
    if (!d) return '-';
    try {
      return new Date(d).toLocaleDateString('pt-BR');
    } catch {
      return d;
    }
  };

  const cleanPhone = (phone?: string | null) => {
    if (!phone) return '';
    const digits = phone.replace(/\D/g, '');
    if (digits.length === 10 || digits.length === 11) {
      return `55${digits}`;
    }
    return digits;
  };

  const handleOpenWhatsApp = (phone?: string | null, name?: string) => {
    const digits = cleanPhone(phone);
    if (!digits) {
      toast.warning("Este contato não possui telefone válido cadastrado.", "Telefone Ausente");
      return;
    }
    const msg = `Olá ${name || ''}! Tudo bem? Estou entrando em contato referente à sua solicitação na ControlB.`;
    window.open(`https://wa.me/${digits}?text=${encodeURIComponent(msg)}`, '_blank');
  };

  // ===========================================================================
  // MUDANÇA DE ESTÁGIO & MOTIVO DE PERDA (DRAG AND DROP)
  // ===========================================================================

  const handleMoveStage = async (oppId: string, targetStageCode: string) => {
    const opp = opportunities.find(o => o.id === oppId);
    if (!opp) return;

    if (opp.stage === targetStageCode) return;

    const targetStage = stages.find(s => s.code === targetStageCode);
    const isLostStage = targetStage?.is_lost || targetStageCode === 'LOST';

    if (isLostStage) {
      setLossModalOpp(opp);
      setLossReason(LOSS_REASONS[0]);
      setLossCompetitor('');
      setLossNotes('');
      return;
    }

    // Atualização otimista
    const prevStage = opp.stage;
    setOpportunities(prev => prev.map(o => o.id === oppId ? { ...o, stage: targetStageCode } : o));

    try {
      await crmService.updateOpportunityStage(oppId, targetStageCode);
      const stageName = targetStage?.name || targetStageCode;
      toast.success(`Oportunidade '${opp.title}' movida para ${stageName}!`, "Estágio Atualizado");
      if (selectedOpp?.id === oppId) {
        setSelectedOpp(prev => prev ? { ...prev, stage: targetStageCode } : null);
      }
    } catch (err: any) {
      setOpportunities(prev => prev.map(o => o.id === oppId ? { ...o, stage: prevStage } : o));
      toast.error(formatApiError(err, "Falha ao mover oportunidade."));
    }
  };

  const handleConfirmLoss = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!lossModalOpp) return;

    const opp = lossModalOpp;
    const finalReason = lossCompetitor.trim() 
      ? `${lossReason} (Concorrente: ${lossCompetitor.trim()})`
      : lossReason;

    setIsSavingLoss(true);
    try {
      await crmService.updateOpportunityStage(opp.id, 'LOST', finalReason);
      
      setOpportunities(prev => prev.map(o => o.id === opp.id ? { 
        ...o, 
        stage: 'LOST', 
        loss_reason: finalReason 
      } : o));

      if (lossNotes.trim()) {
        await crmService.createInteraction({
          opportunity_id: opp.id,
          interaction_type: 'NOTE',
          summary: `Negócio Marcado como Perdido: ${finalReason}`,
          details: lossNotes.trim()
        });
      }

      setLossModalOpp(null);
      toast.info(`Oportunidade '${opp.title}' foi registrada como perdida.`, "Motivo Registrado");
      if (selectedOpp?.id === opp.id) {
        void loadOpportunityDetails(opp);
      }
    } catch (err: any) {
      toast.error(formatApiError(err, "Falha ao registrar motivo da perda."));
      void loadCRMData();
    } finally {
      setIsSavingLoss(false);
    }
  };

  // Drag and Drop Event Handlers
  const handleDragStart = (e: React.DragEvent, oppId: string) => {
    setDraggedOppId(oppId);
    e.dataTransfer.setData('text/plain', oppId);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e: React.DragEvent, stageCode: string) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    if (dragOverStageCode !== stageCode) {
      setDragOverStageCode(stageCode);
    }
  };

  const handleDragLeave = (_e: React.DragEvent, stageCode: string) => {
    if (dragOverStageCode === stageCode) {
      setDragOverStageCode(null);
    }
  };

  const handleDrop = (e: React.DragEvent, stageCode: string) => {
    e.preventDefault();
    setDragOverStageCode(null);
    const oppId = e.dataTransfer.getData('text/plain') || draggedOppId;
    if (oppId) {
      void handleMoveStage(oppId, stageCode);
    }
    setDraggedOppId(null);
  };

  // ===========================================================================
  // INTERAÇÕES & TIMELINE (GAVETA 360º)
  // ===========================================================================

  const handleAddQuickActivity = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedOpp) return;
    if (!quickActivityForm.summary.trim()) {
      toast.warning("Descreva o resumo da atividade antes de salvar.", "Campo Obrigatório");
      return;
    }

    setIsSavingActivity(true);
    try {
      const created = await crmService.createInteraction({
        opportunity_id: selectedOpp.id,
        interaction_type: quickActivityForm.type,
        summary: quickActivityForm.summary.trim(),
        details: quickActivityForm.details.trim() || undefined
      });

      setOppInteractions(prev => [created, ...prev]);
      setAllInteractions(prev => [created, ...prev]);
      setQuickActivityForm({ type: 'CALL', summary: '', details: '' });
      setOppDrawerTab('timeline');
      toast.success("Atividade registrada na timeline da oportunidade!", "Atividade Salva");
    } catch (err: any) {
      toast.error(formatApiError(err, "Erro ao registrar atividade."));
    } finally {
      setIsSavingActivity(false);
    }
  };

  const loadOpportunityDetails = async (opp: Opportunity) => {
    setSelectedOpp(opp);
    setOppDrawerTab('timeline');
    try {
      const [interactions, quotes] = await Promise.all([
        crmService.getInteractions(undefined, opp.id, true).catch(() => []),
        crmService.getOpportunityQuotations(opp.id, true).catch(() => [])
      ]);
      setOppInteractions(interactions);
      setOppQuotes(quotes);
    } catch (err: any) {
      toast.error(formatApiError(err, "Falha ao carregar detalhes completos da oportunidade."));
    }
  };

  // ===========================================================================
  // OPERAÇÕES DE LEADS (FASE 2)
  // ===========================================================================

  const handleCreateLead = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!leadForm.name.trim()) {
      toast.warning("Informe o nome do contato.", "Nome Obrigatório");
      return;
    }

    try {
      await crmService.createLead({
        name: leadForm.name.trim(),
        company_name: leadForm.company_name.trim() || undefined,
        document: leadForm.document.trim() || undefined,
        email: leadForm.email.trim() || undefined,
        phone: leadForm.phone.trim() || undefined,
        source: leadForm.lead_source,
        notes: leadForm.notes.trim() || undefined,
        customer_id: leadForm.customer_id || undefined
      });

      setLeadForm({
        customer_id: '',
        name: '',
        company_name: '',
        document: '',
        email: '',
        phone: '',
        lead_source: 'Indicação',
        notes: ''
      });
      setIsLeadModalOpen(false);
      toast.success("Lead cadastrado com sucesso!", "Lead Adicionado");
      void loadCRMData();
    } catch (err: any) {
      toast.error(formatApiError(err, "Erro ao cadastrar lead."));
    }
  };

  const handleOpenEditLead = (lead: Lead) => {
    setEditingLead(lead);
    setEditLeadForm({
      name: lead.name,
      company_name: lead.company_name || '',
      email: lead.email || '',
      phone: lead.phone || '',
      source: lead.source || 'Indicação',
      status: lead.status || 'NEW',
      notes: lead.notes || ''
    });
  };

  const handleSaveEditLead = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingLead) return;
    try {
      await crmService.updateLead(editingLead.id, {
        name: editLeadForm.name.trim(),
        company_name: editLeadForm.company_name.trim() || undefined,
        email: editLeadForm.email.trim() || undefined,
        phone: editLeadForm.phone.trim() || undefined,
        source: editLeadForm.source,
        status: editLeadForm.status as any,
        notes: editLeadForm.notes.trim() || undefined
      });
      toast.success("Dados do lead atualizados com sucesso!", "Lead Atualizado");
      setEditingLead(null);
      void loadCRMData();
    } catch (err: any) {
      toast.error(formatApiError(err, "Erro ao atualizar lead."));
    }
  };

  const handleDeleteLead = async (leadId: string, leadName: string) => {
    if (!window.confirm(`Deseja realmente excluir o lead '${leadName}'?`)) return;
    try {
      await crmService.deleteLead(leadId);
      toast.success(`Lead '${leadName}' excluído com sucesso.`, "Lead Removido");
      void loadCRMData();
    } catch (err: any) {
      toast.error(formatApiError(err, "Falha ao excluir lead."));
    }
  };

  const handleChangeLeadStatus = async (leadId: string, newStatus: string) => {
    try {
      await crmService.updateLead(leadId, { status: newStatus as any });
      toast.success(`Status do lead alterado para ${newStatus}.`, "Status Atualizado");
      void loadCRMData();
    } catch (err: any) {
      toast.error(formatApiError(err, "Falha ao atualizar status do lead."));
    }
  };

  const handleStartConvertLead = (lead: Lead) => {
    setConvertingLead(lead);
    setOppForm({
      title: `Negócio - ${lead.company_name || lead.name}`,
      customer_id: lead.customer_id || '',
      customer_name: lead.company_name || lead.name,
      estimated_amount: '15000',
      probability_percent: 50,
      expected_closing_date: new Date(Date.now() + 15 * 86400000).toISOString().split('T')[0],
      stage: stages[0]?.code || 'PROSPECTING',
      notes: `Convertido do Lead: ${lead.name} (${lead.source || 'Sem origem'}). Anotações: ${lead.notes || '-'}`
    });
    setIsOppModalOpen(true);
  };

  // ===========================================================================
  // OPERAÇÕES DE ATIVIDADES GLOBAIS (FASE 2)
  // ===========================================================================

  const handleSaveGlobalActivity = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!globalActivityForm.summary.trim()) {
      toast.warning("Informe o resumo da atividade.", "Resumo Obrigatório");
      return;
    }

    setIsSavingGlobalActivity(true);
    try {
      const scheduledDateTime = `${globalActivityForm.date}T${globalActivityForm.time}:00Z`;
      const payload: any = {
        interaction_type: globalActivityForm.type,
        summary: globalActivityForm.summary.trim(),
        details: globalActivityForm.details.trim() || undefined,
        interaction_date: scheduledDateTime
      };

      if (globalActivityForm.linked_type === 'OPPORTUNITY' && globalActivityForm.linked_id) {
        payload.opportunity_id = globalActivityForm.linked_id;
      } else if (globalActivityForm.linked_type === 'LEAD' && globalActivityForm.linked_id) {
        payload.lead_id = globalActivityForm.linked_id;
      }

      const created = await crmService.createInteraction(payload);
      setAllInteractions(prev => [created, ...prev]);
      setIsGlobalActivityModalOpen(false);
      setGlobalActivityForm({
        type: 'CALL',
        linked_type: 'OPPORTUNITY',
        linked_id: '',
        summary: '',
        details: '',
        date: new Date().toISOString().split('T')[0],
        time: '14:00'
      });
      toast.success("Atividade agendada com sucesso!", "Atividade Criada");
      void loadCRMData();
    } catch (err: any) {
      toast.error(formatApiError(err, "Erro ao agendar atividade comercial."));
    } finally {
      setIsSavingGlobalActivity(false);
    }
  };

  // ===========================================================================
  // OPERAÇÕES DE OPORTUNIDADES & ETAPAS
  // ===========================================================================

  const handleCreateOpp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!oppForm.title.trim()) {
      toast.warning("Informe o título da oportunidade.", "Título Obrigatório");
      return;
    }

    const estimatedAmount = parseFloat(oppForm.estimated_amount) || 0;
    const stageCode = oppForm.stage || (stages[0]?.code || 'PROSPECTING');

    try {
      await crmService.createOpportunity({
        title: oppForm.title.trim(),
        customer_name: oppForm.customer_name.trim() || 'Cliente sem identificação',
        customer_id: oppForm.customer_id || undefined,
        estimated_amount: estimatedAmount,
        probability_percent: oppForm.probability_percent || 50,
        expected_closing_date: oppForm.expected_closing_date || undefined,
        stage: stageCode,
        lead_id: convertingLead ? convertingLead.id : undefined
      });

      if (convertingLead) {
        await crmService.updateLead(convertingLead.id, { status: 'CONVERTED' });
        setConvertingLead(null);
      }

      setIsOppModalOpen(false);
      setOppForm({
        title: '',
        customer_id: '',
        customer_name: '',
        estimated_amount: '',
        probability_percent: 50,
        expected_closing_date: '',
        stage: '',
        notes: ''
      });
      toast.success("Oportunidade adicionada ao pipeline comercial!", "Negócio Criado");
      void loadCRMData();
    } catch (err: any) {
      toast.error(formatApiError(err, "Erro ao salvar oportunidade."));
    }
  };

  const handleCreateStage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newStageForm.name.trim()) {
      toast.warning("Informe o nome da etapa.", "Nome Obrigatório");
      return;
    }

    setIsSavingStage(true);
    try {
      const generatedCode = newStageForm.code.trim() 
        ? newStageForm.code.trim().toUpperCase().replace(/\s+/g, '_')
        : newStageForm.name.trim().toUpperCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^A-Z0-9]/g, '_');

      await crmService.createStage({
        name: newStageForm.name.trim(),
        code: generatedCode,
        color: newStageForm.color || '#10b981',
        order: stages.length,
        is_won: newStageForm.is_won,
        is_lost: newStageForm.is_lost
      });

      setNewStageForm({
        name: '',
        code: '',
        color: '#10b981',
        order: 0,
        is_won: false,
        is_lost: false
      });
      toast.success("Nova etapa adicionada ao funil de vendas!", "Etapa criada");
      void loadCRMData();
    } catch (err: any) {
      toast.error(formatApiError(err, "Erro ao criar nova etapa."));
    } finally {
      setIsSavingStage(false);
    }
  };

  const handleDeleteStage = async (stageId: string, stageName: string) => {
    if (!window.confirm(`Deseja realmente remover a etapa '${stageName}' do Funil?`)) return;
    try {
      await crmService.deleteStage(stageId);
      toast.success(`Etapa '${stageName}' removida com sucesso!`, "Etapa Excluída");
      void loadCRMData();
    } catch (err: any) {
      toast.error(formatApiError(err, "Falha ao excluir etapa. Certifique-se de que não há oportunidades vinculadas a ela."));
    }
  };

  // ===========================================================================
  // COTAÇÃO VINCULADA À OPORTUNIDADE
  // ===========================================================================

  const handleOpenQuoteModal = (opp: Opportunity) => {
    setSelectedOppForQuote(opp);
    setQuoteItems([]);
    setQuoteValidUntil(new Date(Date.now() + 15 * 86400000).toISOString().split('T')[0]);
    setQuotePaymentTerms('30 DDL');
    setIsQuoteModalOpen(true);
  };

  const handleAddQuoteItem = () => {
    if (products.length === 0) {
      toast.warning("Cadastre produtos no Almoxarifado / Estoque para adicioná-los à cotação.", "Catálogo Vazio");
      return;
    }
    const defaultProduct = products[0];
    setQuoteItems(prev => [
      ...prev,
      {
        product_id: defaultProduct.id,
        quantity: 1,
        unit_price: defaultProduct.sale_price || defaultProduct.reference_price || 10.0,
        discount_amount: 0
      }
    ]);
  };

  const handleRemoveQuoteItem = (index: number) => {
    setQuoteItems(prev => prev.filter((_, i) => i !== index));
  };

  const handleQuoteItemChange = (index: number, field: string, value: any) => {
    setQuoteItems(prev => {
      const next = [...prev];
      const item = { ...next[index] };
      if (field === 'product_id') {
        item.product_id = value;
        const p = products.find(prod => prod.id === value);
        if (p) {
          item.unit_price = p.sale_price || p.reference_price || 10.0;
        }
      } else if (field === 'quantity') {
        item.quantity = Math.max(1, parseFloat(value) || 1);
      } else if (field === 'unit_price') {
        item.unit_price = Math.max(0, parseFloat(value) || 0);
      } else if (field === 'discount_amount') {
        item.discount_amount = Math.max(0, parseFloat(value) || 0);
      }
      next[index] = item;
      return next;
    });
  };

  const quoteTotalAmount = useMemo(() => {
    return quoteItems.reduce((acc, it) => acc + (it.quantity * it.unit_price - (it.discount_amount || 0)), 0);
  }, [quoteItems]);

  const handleSaveQuotation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedOppForQuote) return;

    setIsSavingQuote(true);
    try {
      await crmService.createQuoteFromOpportunity(selectedOppForQuote.id, quoteItems.length > 0 ? quoteItems : undefined);
      toast.success("Cotação comercial gerada e vinculada à oportunidade!", "Proposta Emitida");
      setIsQuoteModalOpen(false);
      if (selectedOpp?.id === selectedOppForQuote.id) {
        void loadOpportunityDetails(selectedOppForQuote);
      }
      void loadCRMData();
    } catch (err: any) {
      toast.error(formatApiError(err, "Falha ao emitir cotação comercial."));
    } finally {
      setIsSavingQuote(false);
    }
  };

  // ===========================================================================
  // CÁLCULOS MEMOIZADOS (DASHBOARD & FILTROS)
  // ===========================================================================

  const kpis = useMemo(() => {
    const totalOpps = opportunities.length;
    const totalPipelineAmount = opportunities
      .filter(o => o.stage !== 'LOST')
      .reduce((acc, o) => acc + (Number(o.estimated_amount) || 0), 0);
    const wonOpps = opportunities.filter(o => o.stage === 'WON');
    const wonAmount = wonOpps.reduce((acc, o) => acc + (Number(o.estimated_amount) || 0), 0);
    const conversionRate = totalOpps > 0 ? ((wonOpps.length / totalOpps) * 100).toFixed(1) : '0.0';

    return {
      totalOpps,
      totalPipelineAmount,
      wonOppsCount: wonOpps.length,
      wonAmount,
      conversionRate,
      totalLeads: leads.length,
      qualifiedLeads: leads.filter(l => l.status === 'QUALIFIED' || l.status === 'CONVERTED').length
    };
  }, [opportunities, leads]);

  const filteredOpportunities = useMemo(() => {
    return opportunities.filter(o => {
      const matchSearch = searchTerm.trim() === '' ||
        o.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
        o.customer_name.toLowerCase().includes(searchTerm.toLowerCase());
      const matchStage = stageFilter === 'ALL' || o.stage === stageFilter;
      return matchSearch && matchStage;
    });
  }, [opportunities, searchTerm, stageFilter]);

  const filteredLeads = useMemo(() => {
    return leads.filter(l => {
      const matchSearch = leadSearch.trim() === '' ||
        l.name.toLowerCase().includes(leadSearch.toLowerCase()) ||
        (l.company_name && l.company_name.toLowerCase().includes(leadSearch.toLowerCase())) ||
        (l.email && l.email.toLowerCase().includes(leadSearch.toLowerCase())) ||
        (l.phone && l.phone.includes(leadSearch));
      const matchStatus = leadStatusFilter === 'ALL' || l.status === leadStatusFilter;
      return matchSearch && matchStatus;
    });
  }, [leads, leadSearch, leadStatusFilter]);

  const filteredActivities = useMemo(() => {
    const todayStr = new Date().toISOString().split('T')[0];
    return allInteractions.filter(act => {
      if (activitySearch.trim()) {
        const term = activitySearch.toLowerCase();
        const match = act.summary.toLowerCase().includes(term) ||
                      (act.details && act.details.toLowerCase().includes(term)) ||
                      act.interaction_type.toLowerCase().includes(term);
        if (!match) return false;
      }

      const actDateStr = (act.interaction_date || act.created_at || '').split('T')[0];
      if (activityTabFilter === 'TODAY') {
        return actDateStr === todayStr;
      }
      if (activityTabFilter === 'OVERDUE') {
        return actDateStr < todayStr;
      }
      if (activityTabFilter === 'UPCOMING') {
        return actDateStr > todayStr;
      }
      return true;
    });
  }, [allInteractions, activitySearch, activityTabFilter]);

  const recentOpps = useMemo(() => {
    return [...opportunities]
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      .slice(0, 5);
  }, [opportunities]);

  const recentActivities = useMemo(() => {
    return [...allInteractions]
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      .slice(0, 5);
  }, [allInteractions]);

  return (
    <div className="crm-page">
      <div className="crm-layout">
        {/* =================================================================== */}
        {/* 1. SIDEBAR LATERAL DO CRM                                           */}
        {/* =================================================================== */}
        <aside className="crm-sidebar">
          <div className="module-brand">
            <div className="brand-icon">
              <Building2 size={20} />
            </div>
            <div className="brand-text">
              <h2>Módulo CRM</h2>
              <span>GESTÃO COMERCIAL</span>
            </div>
          </div>

          <nav className="sidebar-nav">
            <div className="nav-group">
              <span className="nav-group-title">Visão Geral</span>
              <button
                type="button"
                className={`nav-item ${activeTab === 'dashboard' ? 'active' : ''}`}
                onClick={() => setActiveTab('dashboard')}
              >
                <LayoutDashboard size={16} />
                <span>Dashboard Comercial</span>
              </button>
            </div>

            <div className="nav-group">
              <span className="nav-group-title">Pipeline & Negócios</span>
              <button
                type="button"
                className={`nav-item ${activeTab === 'pipeline' ? 'active' : ''}`}
                onClick={() => setActiveTab('pipeline')}
              >
                <Kanban size={16} />
                <span>Funil de Vendas (Kanban)</span>
                <span className="nav-badge">{opportunities.length}</span>
              </button>
              <button
                type="button"
                className={`nav-item ${activeTab === 'opportunities_list' ? 'active' : ''}`}
                onClick={() => setActiveTab('opportunities_list')}
              >
                <ListFilter size={16} />
                <span>Lista de Oportunidades</span>
                <span className="nav-badge-subtle">{opportunities.length}</span>
              </button>
              <button
                type="button"
                className={`nav-item ${activeTab === 'leads' ? 'active' : ''}`}
                onClick={() => setActiveTab('leads')}
              >
                <Users size={16} />
                <span>Base de Leads</span>
                <span className="nav-badge-subtle">{leads.length}</span>
              </button>
            </div>

            <div className="nav-group">
              <span className="nav-group-title">Operação Comercial</span>
              <button
                type="button"
                className={`nav-item ${activeTab === 'activities' ? 'active' : ''}`}
                onClick={() => setActiveTab('activities')}
              >
                <Clock size={16} />
                <span>Atividades & Agenda</span>
                <span className="nav-badge-subtle">{allInteractions.length}</span>
              </button>
            </div>

            <div className="nav-group">
              <span className="nav-group-title">Configurações</span>
              <button
                type="button"
                className={`nav-item ${activeTab === 'stages' ? 'active' : ''}`}
                onClick={() => setActiveTab('stages')}
              >
                <Settings size={16} />
                <span>Etapas do Funil (Kanban)</span>
                <span className="nav-badge-subtle">{stages.length}</span>
              </button>
            </div>
          </nav>
        </aside>

        {/* =================================================================== */}
        {/* 2. ÁREA DE CONTEÚDO PRINCIPAL                                       */}
        {/* =================================================================== */}
        <main className="main-content">
          {/* Header Superior */}
          <header className="page-header">
            <div className="header-titles">
              <h1>
                {activeTab === 'dashboard' && 'Dashboard Executivo do CRM'}
                {activeTab === 'pipeline' && 'Funil de Vendas Comercial'}
                {activeTab === 'opportunities_list' && 'Gestão de Oportunidades'}
                {activeTab === 'leads' && 'Base de Leads & Prospecção'}
                {activeTab === 'activities' && 'Central de Atividades & Follow-ups'}
                {activeTab === 'stages' && 'Configuração das Etapas do Funil de Vendas'}
              </h1>
              <p className="subtitle">
                {activeTab === 'dashboard' && 'Visão panorâmica de negociações, taxas de conversão e metas comerciais'}
                {activeTab === 'pipeline' && 'Arraste os cards entre as colunas para atualizar a fase de cada negociação'}
                {activeTab === 'opportunities_list' && 'Listagem tabular de todos os negócios com filtros rápidos e valores'}
                {activeTab === 'leads' && 'Qualifique potenciais clientes e converta contatos em negociações ativas'}
                {activeTab === 'activities' && 'Organize ligações, reuniões, conversas de WhatsApp e lembretes com prazos'}
                {activeTab === 'stages' && 'Personalize a sequência, nomes e cores das colunas do quadro Kanban'}
              </p>
            </div>

            <div className="header-actions">
              <button
                type="button"
                className="btn-refresh"
                onClick={() => void loadCRMData(true)}
                title="Atualizar dados agora"
                disabled={loading}
              >
                <RefreshCw size={16} className={loading ? 'spinning' : ''} />
              </button>

              {activeTab === 'leads' && (
                <button
                  type="button"
                  className="btn-primary ui-button ui-button--primary"
                  onClick={() => setIsLeadModalOpen(true)}
                >
                  <UserPlus size={16} />
                  <span>Novo Lead</span>
                </button>
              )}

              {activeTab === 'activities' && (
                <button
                  type="button"
                  className="btn-primary ui-button ui-button--primary"
                  onClick={() => setIsGlobalActivityModalOpen(true)}
                >
                  <Plus size={16} />
                  <span>+ Agendar Atividade</span>
                </button>
              )}

              {activeTab !== 'leads' && activeTab !== 'activities' && (
                <>
                  <button
                    type="button"
                    className="btn-secondary ui-button ui-button--secondary"
                    onClick={() => setIsLeadModalOpen(true)}
                  >
                    <UserPlus size={16} />
                    <span>+ Novo Lead</span>
                  </button>

                  <button
                    type="button"
                    className="btn-primary ui-button ui-button--primary"
                    onClick={() => {
                      setConvertingLead(null);
                      setOppForm({
                        title: '',
                        customer_id: '',
                        customer_name: '',
                        estimated_amount: '',
                        probability_percent: 50,
                        expected_closing_date: '',
                        stage: stages[0]?.code || 'PROSPECTING',
                        notes: ''
                      });
                      setIsOppModalOpen(true);
                    }}
                  >
                    <Plus size={16} />
                    <span>+ Nova Oportunidade</span>
                  </button>
                </>
              )}
            </div>
          </header>

          {/* Cards de Métricas Comerciais */}
          <section className="kpi-grid">
            <div className="kpi-card">
              <div className="kpi-top">
                <span className="kpi-label">Pipeline Ativo</span>
                <DollarSign size={18} />
              </div>
              <span className="kpi-value">{fmtCurrency(kpis.totalPipelineAmount)}</span>
              <span className="kpi-sub">{kpis.totalOpps} oportunidades em andamento</span>
            </div>

            <div className="kpi-card">
              <div className="kpi-top">
                <span className="kpi-label">Negócios Ganhos</span>
                <CheckCircle2 size={18} />
              </div>
              <span className="kpi-value">{fmtCurrency(kpis.wonAmount)}</span>
              <span className="kpi-sub">{kpis.wonOppsCount} negócios fechados com sucesso</span>
            </div>

            <div className="kpi-card">
              <div className="kpi-top">
                <span className="kpi-label">Taxa de Conversão</span>
                <TrendingUp size={18} />
              </div>
              <span className="kpi-value">{kpis.conversionRate}%</span>
              <span className="kpi-sub">Eficiência de fechamento do funil</span>
            </div>

            <div className="kpi-card">
              <div className="kpi-top">
                <span className="kpi-label">Base de Leads</span>
                <Users size={18} />
              </div>
              <span className="kpi-value">{kpis.totalLeads}</span>
              <span className="kpi-sub">{kpis.qualifiedLeads} qualificados / convertidos</span>
            </div>
          </section>

          {/* ================================================================= */}
          {/* TAB 1: DASHBOARD                                                  */}
          {/* ================================================================= */}
          {activeTab === 'dashboard' && (
            <div className="dashboard-view">
              <div className="dashboard-grid">
                {/* Card de Oportunidades Recentes */}
                <div className="dashboard-card">
                  <div className="card-header-line">
                    <div className="title-box">
                      <Kanban size={18} />
                      <h3>Negócios Recentes</h3>
                    </div>
                    <button
                      type="button"
                      className="btn-text-link"
                      onClick={() => setActiveTab('pipeline')}
                    >
                      Ver Funil Completo <ArrowRight size={14} />
                    </button>
                  </div>
                  {recentOpps.length === 0 ? (
                    <p className="empty-notice">Nenhuma oportunidade recente.</p>
                  ) : (
                    <div className="dashboard-opps-list">
                      {recentOpps.map(opp => {
                        const stg = stages.find(s => s.code === opp.stage);
                        return (
                          <div
                            key={opp.id}
                            className="dash-opp-item"
                            onClick={() => void loadOpportunityDetails(opp)}
                          >
                            <div className="opp-info">
                              <h4>{opp.title}</h4>
                              <span>{opp.customer_name}</span>
                            </div>
                            <div className="opp-meta">
                              <span className="opp-val">{fmtCurrency(opp.estimated_amount)}</span>
                              <span
                                className="stage-pill"
                                style={{
                                  backgroundColor: stg?.color ? `${stg.color}22` : 'var(--accent-brand-subtle)',
                                  color: stg?.color || 'var(--accent-brand)'
                                }}
                              >
                                {stg?.name || opp.stage}
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* Card de Interações Recentes */}
                <div className="dashboard-card">
                  <div className="card-header-line">
                    <div className="title-box">
                      <Clock size={18} />
                      <h3>Últimas Interações</h3>
                    </div>
                    <button
                      type="button"
                      className="btn-text-link"
                      onClick={() => setActiveTab('activities')}
                    >
                      Ver Todas <ArrowRight size={14} />
                    </button>
                  </div>
                  {recentActivities.length === 0 ? (
                    <p className="empty-notice">Nenhuma atividade registrada ainda.</p>
                  ) : (
                    <div className="dashboard-activities-list">
                      {recentActivities.map(act => (
                        <div key={act.id} className="dash-activity-item">
                          <div className="activity-icon-badge">
                            {act.interaction_type === 'CALL' && <Phone size={14} />}
                            {act.interaction_type === 'WHATSAPP' && <MessageSquare size={14} />}
                            {act.interaction_type === 'MEETING' && <Users size={14} />}
                            {act.interaction_type === 'EMAIL' && <Mail size={14} />}
                            {act.interaction_type === 'NOTE' && <FileText size={14} />}
                          </div>
                          <div className="activity-content">
                            <h4 className="act-summary">{act.summary}</h4>
                            <span className="act-time">{fmtDate(act.created_at)}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* ================================================================= */}
          {/* TAB 2: PIPELINE KANBAN (DRAG AND DROP)                            */}
          {/* ================================================================= */}
          {activeTab === 'pipeline' && (
            <div className="kanban-container">
              <div className="kanban-board">
                {stages.map((stage) => {
                  const stageOpps = opportunities.filter(o => o.stage === stage.code);
                  const stageTotalAmount = stageOpps.reduce((acc, o) => acc + (Number(o.estimated_amount) || 0), 0);
                  const isDragOver = dragOverStageCode === stage.code;

                  return (
                    <div
                      key={stage.id || stage.code}
                      className={`kanban-column ${isDragOver ? 'drag-over' : ''}`}
                      onDragOver={(e) => handleDragOver(e, stage.code)}
                      onDragLeave={(e) => handleDragLeave(e, stage.code)}
                      onDrop={(e) => handleDrop(e, stage.code)}
                    >
                      {/* Cabeçalho da Coluna com Totais */}
                      <div className="column-header" style={{ borderTopColor: stage.color || 'var(--accent-brand)' }}>
                        <div className="header-main-info">
                          <div className="title-wrapper">
                            <span className="stage-bullet" style={{ backgroundColor: stage.color || '#10b981' }} />
                            <h3 className="column-title">{stage.name}</h3>
                          </div>
                          <span className="count-pill">{stageOpps.length}</span>
                        </div>

                        <div className="column-sub-info">
                          <span className="column-amount">{fmtCurrency(stageTotalAmount)}</span>
                          <button
                            type="button"
                            className="btn-quick-add"
                            onClick={() => {
                              setConvertingLead(null);
                              setOppForm({
                                title: '',
                                customer_id: '',
                                customer_name: '',
                                estimated_amount: '',
                                probability_percent: 50,
                                expected_closing_date: '',
                                stage: stage.code,
                                notes: ''
                              });
                              setIsOppModalOpen(true);
                            }}
                            title={`Criar oportunidade na etapa '${stage.name}'`}
                          >
                            <Plus size={13} />
                          </button>
                        </div>
                      </div>

                      {/* Lista de Cards da Coluna */}
                      <div className="cards-list">
                        {stageOpps.length === 0 ? (
                          <div className="empty-column-dropzone">
                            <span>Arraste oportunidades para esta etapa</span>
                          </div>
                        ) : (
                          stageOpps.map((opp) => {
                            const isDragging = draggedOppId === opp.id;
                            return (
                              <div
                                key={opp.id}
                                className={`kanban-card ${isDragging ? 'is-dragging' : ''}`}
                                draggable
                                onDragStart={(e) => handleDragStart(e, opp.id)}
                                onClick={() => void loadOpportunityDetails(opp)}
                              >
                                <div className="card-top-row">
                                  <h4 className="opp-title">{opp.title}</h4>
                                  <span className="opp-prob">{opp.probability_percent}%</span>
                                </div>

                                <div className="opp-customer">
                                  <Building2 size={13} />
                                  <span>{opp.customer_name}</span>
                                </div>

                                <div className="opp-amount-row">
                                  <span className="opp-amount">{fmtCurrency(opp.estimated_amount)}</span>
                                </div>

                                {opp.expected_closing_date && (
                                  <div className="opp-date">
                                    <Clock size={12} />
                                    <span>Previsão: {fmtDate(opp.expected_closing_date)}</span>
                                  </div>
                                )}

                                {opp.loss_reason && (
                                  <div className="opp-loss-alert">
                                    <AlertTriangle size={12} />
                                    <span>{opp.loss_reason}</span>
                                  </div>
                                )}

                                <div className="card-footer-actions" onClick={(e) => e.stopPropagation()}>
                                  <button
                                    type="button"
                                    className="btn-card-action"
                                    onClick={() => handleOpenQuoteModal(opp)}
                                    title="Emitir Proposta Comercial"
                                  >
                                    <FileText size={13} />
                                    <span>Proposta</span>
                                  </button>

                                  <select
                                    value={opp.stage}
                                    onChange={(e) => void handleMoveStage(opp.id, e.target.value)}
                                    className="stage-selector-select"
                                  >
                                    {stages.map(stg => (
                                      <option key={stg.id || stg.code} value={stg.code}>{stg.name}</option>
                                    ))}
                                  </select>
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
            </div>
          )}

          {/* ================================================================= */}
          {/* TAB 3: LISTA TABULAR DE OPORTUNIDADES                             */}
          {/* ================================================================= */}
          {activeTab === 'opportunities_list' && (
            <div className="table-card">
              <div className="table-toolbar">
                <div className="search-box">
                  <input
                    type="text"
                    placeholder="Pesquisar por título ou cliente..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>

                <div className="filter-select-wrapper">
                  <select
                    value={stageFilter}
                    onChange={(e) => setStageFilter(e.target.value)}
                  >
                    <option value="ALL">Todos os Estágios ({opportunities.length})</option>
                    {stages.map(stg => (
                      <option key={stg.id || stg.code} value={stg.code}>{stg.name}</option>
                    ))}
                  </select>
                </div>
              </div>

              <table className="data-table">
                <thead>
                  <tr>
                    <th>Título do Negócio</th>
                    <th>Cliente / Empresa</th>
                    <th>Valor Estimado</th>
                    <th>Probabilidade</th>
                    <th>Estágio Atual</th>
                    <th>Previsão Fechamento</th>
                    <th style={{ textAlign: 'center' }}>Ações</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredOpportunities.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="empty-row">Nenhuma oportunidade encontrada com os filtros selecionados.</td>
                    </tr>
                  ) : (
                    filteredOpportunities.map(opp => {
                      const stg = stages.find(s => s.code === opp.stage);
                      return (
                        <tr key={opp.id} onClick={() => void loadOpportunityDetails(opp)} style={{ cursor: 'pointer' }}>
                          <td><strong>{opp.title}</strong></td>
                          <td>{opp.customer_name}</td>
                          <td><span className="opp-val-highlight">{fmtCurrency(opp.estimated_amount)}</span></td>
                          <td>{opp.probability_percent}%</td>
                          <td>
                            <span className="stage-pill" style={{ backgroundColor: stg?.color ? `${stg.color}22` : 'var(--accent-brand-subtle)', color: stg?.color || 'var(--accent-brand)' }}>
                              {stg?.name || opp.stage}
                            </span>
                          </td>
                          <td>{fmtDate(opp.expected_closing_date)}</td>
                          <td style={{ textAlign: 'center' }} onClick={(e) => e.stopPropagation()}>
                            <button
                              className="btn-icon-action"
                              onClick={() => void loadOpportunityDetails(opp)}
                              title="Ver Detalhes 360º"
                            >
                              <Eye size={15} />
                            </button>
                            <button
                              className="btn-icon-action"
                              onClick={() => handleOpenQuoteModal(opp)}
                              title="Emitir Proposta"
                            >
                              <FileText size={15} />
                            </button>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* ================================================================= */}
          {/* TAB 4: BASE DE LEADS & QUALIFICAÇÃO (FASE 2)                      */}
          {/* ================================================================= */}
          {activeTab === 'leads' && (
            <div className="table-card">
              {/* Barra de Filtros e Busca de Leads */}
              <div className="table-toolbar">
                <div className="search-box">
                  <input
                    type="text"
                    placeholder="Pesquisar por nome, empresa, e-mail ou telefone..."
                    value={leadSearch}
                    onChange={(e) => setLeadSearch(e.target.value)}
                  />
                </div>

                <div className="filter-select-wrapper">
                  <select
                    value={leadStatusFilter}
                    onChange={(e) => setLeadStatusFilter(e.target.value)}
                  >
                    <option value="ALL">Todos os Status ({leads.length})</option>
                    <option value="NEW">🟢 Novos ({leads.filter(l => l.status === 'NEW').length})</option>
                    <option value="CONTACTED">🟡 Em Contato ({leads.filter(l => l.status === 'CONTACTED').length})</option>
                    <option value="QUALIFIED">⭐ Qualificados ({leads.filter(l => l.status === 'QUALIFIED').length})</option>
                    <option value="CONVERTED">🏆 Convertidos em Negócio ({leads.filter(l => l.status === 'CONVERTED').length})</option>
                    <option value="DISQUALIFIED">⚪ Desqualificados ({leads.filter(l => l.status === 'DISQUALIFIED').length})</option>
                  </select>
                </div>
              </div>

              <table className="data-table">
                <thead>
                  <tr>
                    <th>Nome do Lead</th>
                    <th>Empresa / Razão Social</th>
                    <th>Contatos Rápidos</th>
                    <th>Origem</th>
                    <th>Status de Qualificação</th>
                    <th style={{ textAlign: 'center' }}>Ações Comerciais</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredLeads.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="empty-row">Nenhum lead encontrado com os filtros selecionados.</td>
                    </tr>
                  ) : (
                    filteredLeads.map((lead) => (
                      <tr key={lead.id}>
                        <td>
                          <div className="lead-identity-cell">
                            <strong>{lead.name}</strong>
                            {lead.customer_id && (
                              <span className="customer-sync-badge" title="Cliente sincronizado no módulo de Vendas">
                                <CheckCircle2 size={11} /> Cliente Vendas
                              </span>
                            )}
                          </div>
                        </td>
                        <td>{lead.company_name || '-'}</td>
                        <td>
                          <div className="quick-contact-actions">
                            {lead.phone ? (
                              <>
                                <button
                                  type="button"
                                  className="btn-quick-contact whatsapp"
                                  onClick={() => handleOpenWhatsApp(lead.phone, lead.name)}
                                  title="Chamar no WhatsApp Web"
                                >
                                  <MessageSquare size={13} />
                                  <span>WhatsApp</span>
                                </button>
                                <a
                                  href={`tel:${lead.phone}`}
                                  className="btn-quick-contact phone"
                                  title={`Ligar para ${lead.phone}`}
                                >
                                  <Phone size={13} />
                                </a>
                              </>
                            ) : (
                              <span className="text-muted-small">Sem telefone</span>
                            )}

                            {lead.email && (
                              <a
                                href={`mailto:${lead.email}`}
                                className="btn-quick-contact email"
                                title={`Enviar e-mail para ${lead.email}`}
                              >
                                <Mail size={13} />
                              </a>
                            )}
                          </div>
                        </td>
                        <td>{lead.source || '-'}</td>
                        <td>
                          <select
                            value={lead.status}
                            onChange={(e) => void handleChangeLeadStatus(lead.id, e.target.value)}
                            className={`lead-status-select ${lead.status.toLowerCase()}`}
                          >
                            <option value="NEW">🟢 Novo</option>
                            <option value="CONTACTED">🟡 Em Contato</option>
                            <option value="QUALIFIED">⭐ Qualificado</option>
                            <option value="CONVERTED">🏆 Convertido</option>
                            <option value="DISQUALIFIED">⚪ Desqualificado</option>
                          </select>
                        </td>
                        <td style={{ textAlign: 'center' }}>
                          <div className="row-actions-group">
                            {lead.status !== 'CONVERTED' && (
                              <button
                                type="button"
                                className="btn-action-convert"
                                onClick={() => handleStartConvertLead(lead)}
                                title="Converter este Lead em Oportunidade no Funil"
                              >
                                <ArrowUpRight size={14} />
                                <span>Criar Negócio</span>
                              </button>
                            )}
                            <button
                              type="button"
                              className="btn-icon-action"
                              onClick={() => handleOpenEditLead(lead)}
                              title="Editar Informações do Lead"
                            >
                              <Edit3 size={15} />
                            </button>
                            <button
                              type="button"
                              className="btn-icon-action danger"
                              onClick={() => void handleDeleteLead(lead.id, lead.name)}
                              title="Excluir Lead"
                            >
                              <Trash2 size={15} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* ================================================================= */}
          {/* TAB 5: CENTRAL DE ATIVIDADES & AGENDA COMERCIAL (FASE 2)          */}
          {/* ================================================================= */}
          {activeTab === 'activities' && (
            <div className="activities-page-wrapper">
              {/* Barra de Abas Temporais de Atividades */}
              <div className="activity-tabs-bar">
                <div className="activity-tabs-nav">
                  <button
                    type="button"
                    className={`act-tab-btn ${activityTabFilter === 'ALL' ? 'active' : ''}`}
                    onClick={() => setActivityTabFilter('ALL')}
                  >
                    Todas as Ações ({allInteractions.length})
                  </button>
                  <button
                    type="button"
                    className={`act-tab-btn overdue ${activityTabFilter === 'OVERDUE' ? 'active' : ''}`}
                    onClick={() => setActivityTabFilter('OVERDUE')}
                  >
                    🔴 Atrasadas
                  </button>
                  <button
                    type="button"
                    className={`act-tab-btn today ${activityTabFilter === 'TODAY' ? 'active' : ''}`}
                    onClick={() => setActivityTabFilter('TODAY')}
                  >
                    🟡 Para Hoje
                  </button>
                  <button
                    type="button"
                    className={`act-tab-btn upcoming ${activityTabFilter === 'UPCOMING' ? 'active' : ''}`}
                    onClick={() => setActivityTabFilter('UPCOMING')}
                  >
                    🟢 Próximas
                  </button>
                </div>

                <div className="activity-search-box">
                  <input
                    type="text"
                    placeholder="Pesquisar atividade por resumo ou detalhes..."
                    value={activitySearch}
                    onChange={(e) => setActivitySearch(e.target.value)}
                  />
                </div>
              </div>

              <div className="table-card">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Tipo de Ação</th>
                      <th>Resumo da Atividade</th>
                      <th>Detalhes & Observações</th>
                      <th>Data Programada / Registro</th>
                      <th style={{ textAlign: 'center' }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredActivities.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="empty-row">Nenhuma atividade encontrada com os filtros selecionados.</td>
                      </tr>
                    ) : (
                      filteredActivities.map(act => (
                        <tr key={act.id}>
                          <td>
                            <div className="cell-activity-type">
                              {act.interaction_type === 'CALL' && <Phone size={14} className="icon-call" />}
                              {act.interaction_type === 'WHATSAPP' && <MessageSquare size={14} className="icon-whatsapp" />}
                              {act.interaction_type === 'MEETING' && <Users size={14} className="icon-meeting" />}
                              {act.interaction_type === 'EMAIL' && <Mail size={14} className="icon-email" />}
                              {act.interaction_type === 'NOTE' && <FileText size={14} className="icon-note" />}
                              <span>{act.interaction_type}</span>
                            </div>
                          </td>
                          <td><strong>{act.summary}</strong></td>
                          <td>{act.details || '-'}</td>
                          <td>
                            <div className="activity-date-cell">
                              <CalendarDays size={13} />
                              <span>{fmtDate(act.interaction_date || act.created_at)}</span>
                            </div>
                          </td>
                          <td style={{ textAlign: 'center' }}>
                            <span className="status-badge" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#10b981' }}>
                              <Check size={12} /> Concluída
                            </span>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ================================================================= */}
          {/* TAB 6: CONFIGURAÇÃO DE ETAPAS DO FUNIL                            */}
          {/* ================================================================= */}
          {activeTab === 'stages' && (
            <div className="stages-page-view">
              <div className="stages-grid-layout">
                {/* Formulário de Nova Etapa */}
                <div className="stages-form-card">
                  <div className="card-header">
                    <div className="header-icon-box">
                      <Layers size={20} />
                    </div>
                    <div>
                      <h3>Adicionar Nova Etapa</h3>
                      <p>Defina o nome, código e cor da coluna no Kanban</p>
                    </div>
                  </div>

                  <form onSubmit={handleCreateStage} className="stages-form">
                    <div className="form-group">
                      <label htmlFor="stage-name-input">Nome da Etapa *</label>
                      <input
                        id="stage-name-input"
                        type="text"
                        required
                        className="ui-input"
                        placeholder="Ex: Análise Técnica, Follow-up..."
                        value={newStageForm.name}
                        onChange={(e) => setNewStageForm({ ...newStageForm, name: e.target.value })}
                      />
                      <span className="input-hint">Nome visível na coluna do quadro Kanban.</span>
                    </div>

                    <div className="form-group">
                      <label htmlFor="stage-code-input">Código Identificador (Opcional)</label>
                      <input
                        id="stage-code-input"
                        type="text"
                        className="ui-input"
                        placeholder="Ex: TECHNICAL_REVIEW"
                        value={newStageForm.code}
                        onChange={(e) => setNewStageForm({ ...newStageForm, code: e.target.value })}
                      />
                      <span className="input-hint">Gerado automaticamente se deixado em branco.</span>
                    </div>

                    <div className="form-group">
                      <label>Cor da Coluna no Kanban</label>
                      <div className="color-presets-wrapper">
                        <div className="color-presets-row">
                          {COLOR_PRESETS.map((color) => (
                            <button
                              key={color}
                              type="button"
                              className={`color-chip ${newStageForm.color === color ? 'selected' : ''}`}
                              style={{ backgroundColor: color }}
                              onClick={() => setNewStageForm({ ...newStageForm, color })}
                              title={`Selecionar cor ${color}`}
                            />
                          ))}
                        </div>
                        <div className="custom-color-picker">
                          <input
                            type="color"
                            id="custom-stage-color"
                            value={newStageForm.color}
                            onChange={(e) => setNewStageForm({ ...newStageForm, color: e.target.value })}
                            title="Escolher cor personalizada"
                          />
                          <label htmlFor="custom-stage-color" className="custom-color-label">
                            <span className="color-preview-dot" style={{ backgroundColor: newStageForm.color }} />
                            <span>{newStageForm.color}</span>
                          </label>
                        </div>
                      </div>
                    </div>

                    <div className="form-actions">
                      <button type="submit" className="btn-submit-stage" disabled={isSavingStage || !newStageForm.name.trim()}>
                        <Plus size={16} />
                        <span>{isSavingStage ? 'Salvando Etapa...' : 'Adicionar Etapa ao Funil'}</span>
                      </button>
                    </div>
                  </form>
                </div>

                {/* Tabela de Etapas Ativas */}
                <div className="stages-list-card">
                  <div className="card-header">
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                        <h3>Etapas Ativas no Kanban</h3>
                        <span className="stages-count-badge">{stages.length} etapas</span>
                      </div>
                      <p>Sequência oficial e status das colunas do pipeline comercial</p>
                    </div>
                  </div>

                  <div className="stages-table-container">
                    <table className="stages-data-table">
                      <thead>
                        <tr>
                          <th>Ordem / Cor</th>
                          <th>Nome da Etapa</th>
                          <th>Código</th>
                          <th>Negócios Ativos</th>
                          <th>Tipo de Etapa</th>
                          <th style={{ textAlign: 'center' }}>Ações</th>
                        </tr>
                      </thead>
                      <tbody>
                        {stages.map((stg, index) => {
                          const countOpps = opportunities.filter(o => o.stage === stg.code).length;
                          return (
                            <tr key={stg.id || stg.code}>
                              <td>
                                <div className="stage-order-col">
                                  <span className="order-pill">#{index + 1}</span>
                                  <div
                                    className="color-bullet"
                                    style={{ backgroundColor: stg.color || '#10b981' }}
                                    title={`Cor: ${stg.color || '#10b981'}`}
                                  />
                                </div>
                              </td>
                              <td>
                                <div className="stage-name-col">
                                  <span className="stage-main-name">{stg.name}</span>
                                </div>
                              </td>
                              <td>
                                <code className="code-pill">{stg.code}</code>
                              </td>
                              <td>
                                <div className={`opps-count-pill ${countOpps > 0 ? 'has-opps' : 'empty'}`}>
                                  <TrendingUp size={13} />
                                  <span>{countOpps} {countOpps === 1 ? 'oportunidade' : 'oportunidades'}</span>
                                </div>
                              </td>
                              <td>
                                {stg.is_won ? (
                                  <span className="stage-type-tag won">Ganho / Fechado</span>
                                ) : stg.is_lost ? (
                                  <span className="stage-type-tag lost">Perdido</span>
                                ) : (
                                  <span className="stage-type-tag in-progress">Em Negociação</span>
                                )}
                              </td>
                              <td style={{ textAlign: 'center' }}>
                                <button
                                  type="button"
                                  className="btn-delete-stage"
                                  onClick={() => handleDeleteStage(stg.id, stg.name)}
                                  title={`Excluir etapa '${stg.name}'`}
                                >
                                  <Trash2 size={15} />
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>

      {/* =================================================================== */}
      {/* GAVETA / MODAL 360º DE DETALHE DA OPORTUNIDADE                      */}
      {/* =================================================================== */}
      {selectedOpp && (
        <div className="opportunity-drawer-overlay" onClick={() => setSelectedOpp(null)}>
          <div className="opportunity-drawer" onClick={(e) => e.stopPropagation()}>
            {/* Header da Gaveta */}
            <div className="drawer-header">
              <div className="header-info">
                <span className="drawer-customer-name">
                  <Building2 size={14} /> {selectedOpp.customer_name}
                </span>
                <h2 className="drawer-title">{selectedOpp.title}</h2>
              </div>
              <div className="header-actions">
                <button
                  type="button"
                  className="btn-drawer-action btn-won"
                  onClick={() => void handleMoveStage(selectedOpp.id, 'WON')}
                  title="Marcar como Ganho"
                >
                  <CheckCircle2 size={15} />
                  <span>Ganho</span>
                </button>
                <button
                  type="button"
                  className="btn-drawer-action btn-lost"
                  onClick={() => {
                    setLossModalOpp(selectedOpp);
                    setLossReason(LOSS_REASONS[0]);
                    setLossCompetitor('');
                    setLossNotes('');
                  }}
                  title="Marcar como Perdido"
                >
                  <X size={15} />
                  <span>Perdido</span>
                </button>
                <button
                  type="button"
                  className="btn-drawer-close"
                  onClick={() => setSelectedOpp(null)}
                >
                  <X size={18} />
                </button>
              </div>
            </div>

            {/* Trilha de Estágios (Chevron Progress Tracker) */}
            <div className="stage-chevron-tracker">
              {stages.map((stg) => {
                const isCurrent = selectedOpp.stage === stg.code;
                return (
                  <button
                    key={stg.id || stg.code}
                    type="button"
                    className={`chevron-item ${isCurrent ? 'active' : ''}`}
                    onClick={() => void handleMoveStage(selectedOpp.id, stg.code)}
                    style={{
                      borderBottomColor: isCurrent ? (stg.color || 'var(--accent-brand)') : 'transparent'
                    }}
                  >
                    <span className="chevron-bullet" style={{ backgroundColor: stg.color || '#10b981' }} />
                    <span className="chevron-label">{stg.name}</span>
                  </button>
                );
              })}
            </div>

            {/* Cards de Resumo da Oportunidade */}
            <div className="drawer-summary-grid">
              <div className="summary-item">
                <span className="label">Valor Estimado</span>
                <span className="value-highlight">{fmtCurrency(selectedOpp.estimated_amount)}</span>
              </div>
              <div className="summary-item">
                <span className="label">Probabilidade</span>
                <span className="value">{selectedOpp.probability_percent}%</span>
              </div>
              <div className="summary-item">
                <span className="label">Previsão Fechamento</span>
                <span className="value">{fmtDate(selectedOpp.expected_closing_date)}</span>
              </div>
              <div className="summary-item">
                <span className="label">Ação Rápida</span>
                <button
                  type="button"
                  className="btn-emit-quote-fast"
                  onClick={() => handleOpenQuoteModal(selectedOpp)}
                >
                  <FileText size={13} />
                  <span>Emitir Proposta</span>
                </button>
              </div>
            </div>

            {/* Abas Internas da Gaveta */}
            <div className="drawer-tabs-nav">
              <button
                type="button"
                className={`drawer-tab-btn ${oppDrawerTab === 'timeline' ? 'active' : ''}`}
                onClick={() => setOppDrawerTab('timeline')}
              >
                <Clock size={14} />
                <span>Timeline ({oppInteractions.length})</span>
              </button>
              <button
                type="button"
                className={`drawer-tab-btn ${oppDrawerTab === 'quotes' ? 'active' : ''}`}
                onClick={() => setOppDrawerTab('quotes')}
              >
                <FileText size={14} />
                <span>Propostas ({oppQuotes.length})</span>
              </button>
              <button
                type="button"
                className={`drawer-tab-btn ${oppDrawerTab === 'new_activity' ? 'active' : ''}`}
                onClick={() => setOppDrawerTab('new_activity')}
              >
                <Plus size={14} />
                <span>Registrar Ação</span>
              </button>
            </div>

            {/* Corpo das Abas */}
            <div className="drawer-tab-body">
              {/* ABA 1: TIMELINE */}
              {oppDrawerTab === 'timeline' && (
                <div className="timeline-view">
                  {oppInteractions.length === 0 ? (
                    <div className="empty-timeline">
                      <Clock size={32} />
                      <p>Nenhuma atividade ou interação registrada para este negócio.</p>
                      <button
                        type="button"
                        className="btn-primary ui-button"
                        onClick={() => setOppDrawerTab('new_activity')}
                      >
                        <Plus size={14} /> Registrar Primeira Ação
                      </button>
                    </div>
                  ) : (
                    <div className="timeline-list">
                      {oppInteractions.map((act) => (
                        <div key={act.id} className="timeline-item">
                          <div className="timeline-icon">
                            {act.interaction_type === 'CALL' && <Phone size={14} />}
                            {act.interaction_type === 'WHATSAPP' && <MessageSquare size={14} />}
                            {act.interaction_type === 'MEETING' && <Users size={14} />}
                            {act.interaction_type === 'EMAIL' && <Mail size={14} />}
                            {act.interaction_type === 'NOTE' && <FileText size={14} />}
                          </div>
                          <div className="timeline-content">
                            <div className="timeline-top">
                              <span className="timeline-type">{act.interaction_type}</span>
                              <span className="timeline-date">{fmtDate(act.created_at)}</span>
                            </div>
                            <h4 className="timeline-summary">{act.summary}</h4>
                            {act.details && <p className="timeline-details">{act.details}</p>}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* ABA 2: PROPOSTAS & COTAÇÕES */}
              {oppDrawerTab === 'quotes' && (
                <div className="drawer-quotes-view">
                  <div className="quotes-header-row">
                    <h4>Cotações e Propostas Vinculadas</h4>
                    <button
                      type="button"
                      className="btn-primary ui-button"
                      onClick={() => handleOpenQuoteModal(selectedOpp)}
                    >
                      <Plus size={14} /> Nova Cotação
                    </button>
                  </div>
                  {oppQuotes.length === 0 ? (
                    <p className="empty-notice">Nenhuma cotação formal emitida para este negócio.</p>
                  ) : (
                    <div className="quotes-list-card">
                      {oppQuotes.map(q => (
                        <div key={q.id} className="quote-item-row">
                          <div className="q-info">
                            <strong>{q.quote_number}</strong>
                            <span>{fmtDate(q.created_at)} - Vencimento: {fmtDate(q.valid_until)}</span>
                          </div>
                          <div className="q-values">
                            <span className="q-amount">{fmtCurrency(q.total_amount)}</span>
                            <span className={`q-status-badge ${q.status.toLowerCase()}`}>{q.status}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* ABA 3: REGISTRAR NOVA ATIVIDADE */}
              {oppDrawerTab === 'new_activity' && (
                <form onSubmit={handleAddQuickActivity} className="quick-activity-form">
                  <div className="activity-type-selector">
                    {[
                      { id: 'CALL', label: 'Ligação', icon: Phone },
                      { id: 'WHATSAPP', label: 'WhatsApp', icon: MessageSquare },
                      { id: 'MEETING', label: 'Reunião', icon: Users },
                      { id: 'EMAIL', label: 'E-mail', icon: Mail },
                      { id: 'NOTE', label: 'Anotação', icon: FileText }
                    ].map(t => {
                      const Icon = t.icon;
                      const isSelected = quickActivityForm.type === t.id;
                      return (
                        <button
                          key={t.id}
                          type="button"
                          className={`type-btn ${isSelected ? 'selected' : ''}`}
                          onClick={() => setQuickActivityForm({ ...quickActivityForm, type: t.id })}
                        >
                          <Icon size={14} />
                          <span>{t.label}</span>
                        </button>
                      );
                    })}
                  </div>

                  <div className="form-group">
                    <label>Resumo da Ação / Próximo Passo *</label>
                    <input
                      type="text"
                      required
                      className="ui-input"
                      placeholder="Ex: Alinhamento da proposta técnica com decisor"
                      value={quickActivityForm.summary}
                      onChange={(e) => setQuickActivityForm({ ...quickActivityForm, summary: e.target.value })}
                    />
                  </div>

                  <div className="form-group">
                    <label>Detalhes e Observações</label>
                    <textarea
                      rows={3}
                      className="ui-input"
                      placeholder="Registre os pontos acordados, prazos ou pendências..."
                      value={quickActivityForm.details}
                      onChange={(e) => setQuickActivityForm({ ...quickActivityForm, details: e.target.value })}
                    />
                  </div>

                  <div className="form-actions">
                    <button type="submit" className="btn-primary ui-button" disabled={isSavingActivity}>
                      <Send size={14} />
                      <span>{isSavingActivity ? 'Salvando...' : 'Salvar Atividade na Timeline'}</span>
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>
        </div>
      )}

      {/* =================================================================== */}
      {/* MODAL DE AGENDAR ATIVIDADE GLOBAL (FASE 2)                          */}
      {/* =================================================================== */}
      {isGlobalActivityModalOpen && (
        <Modal
          isOpen={true}
          onClose={() => setIsGlobalActivityModalOpen(false)}
          title="Agendar Ação Comercial / Follow-up"
          subtitle="Programe ligações, reuniões, follow-ups ou conversas de WhatsApp com prazos definidos"
          size="md"
        >
          <form onSubmit={handleSaveGlobalActivity} className="wizard-form">
            <div className="form-group">
              <label>Tipo de Atividade Comercial *</label>
              <div className="activity-type-selector">
                {[
                  { id: 'CALL', label: 'Ligação', icon: Phone },
                  { id: 'WHATSAPP', label: 'WhatsApp', icon: MessageSquare },
                  { id: 'MEETING', label: 'Reunião', icon: Users },
                  { id: 'EMAIL', label: 'E-mail', icon: Mail },
                  { id: 'NOTE', label: 'Anotação', icon: FileText }
                ].map(t => {
                  const Icon = t.icon;
                  const isSelected = globalActivityForm.type === t.id;
                  return (
                    <button
                      key={t.id}
                      type="button"
                      className={`type-btn ${isSelected ? 'selected' : ''}`}
                      onClick={() => setGlobalActivityForm({ ...globalActivityForm, type: t.id })}
                    >
                      <Icon size={14} />
                      <span>{t.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="form-group">
              <label>Vincular a:</label>
              <div className="linked-selector-row">
                <select
                  value={globalActivityForm.linked_type}
                  onChange={(e) => setGlobalActivityForm({
                    ...globalActivityForm,
                    linked_type: e.target.value as any,
                    linked_id: ''
                  })}
                  className="ui-input linked-type-select"
                >
                  <option value="OPPORTUNITY">Oportunidade / Negócio</option>
                  <option value="LEAD">Lead / Prospect</option>
                </select>

                {globalActivityForm.linked_type === 'OPPORTUNITY' ? (
                  <select
                    value={globalActivityForm.linked_id}
                    onChange={(e) => setGlobalActivityForm({ ...globalActivityForm, linked_id: e.target.value })}
                    className="ui-input flex-1"
                  >
                    <option value="">Selecione a oportunidade (Opcional)...</option>
                    {opportunities.map(opp => (
                      <option key={opp.id} value={opp.id}>{opp.title} ({opp.customer_name})</option>
                    ))}
                  </select>
                ) : (
                  <select
                    value={globalActivityForm.linked_id}
                    onChange={(e) => setGlobalActivityForm({ ...globalActivityForm, linked_id: e.target.value })}
                    className="ui-input flex-1"
                  >
                    <option value="">Selecione o lead (Opcional)...</option>
                    {leads.map(lead => (
                      <option key={lead.id} value={lead.id}>{lead.name} ({lead.company_name || 'Sem empresa'})</option>
                    ))}
                  </select>
                )}
              </div>
            </div>

            <div className="form-group">
              <label>Resumo da Ação / Assunto *</label>
              <input
                type="text"
                required
                className="ui-input"
                placeholder="Ex: Reunião de demonstração do sistema para diretoria"
                value={globalActivityForm.summary}
                onChange={(e) => setGlobalActivityForm({ ...globalActivityForm, summary: e.target.value })}
              />
            </div>

            <div className="form-row cols-2">
              <div className="form-group flex-1">
                <label>Data Programada *</label>
                <input
                  type="date"
                  required
                  className="ui-input"
                  value={globalActivityForm.date}
                  onChange={(e) => setGlobalActivityForm({ ...globalActivityForm, date: e.target.value })}
                />
              </div>
              <div className="form-group flex-1">
                <label>Horário *</label>
                <input
                  type="time"
                  required
                  className="ui-input"
                  value={globalActivityForm.time}
                  onChange={(e) => setGlobalActivityForm({ ...globalActivityForm, time: e.target.value })}
                />
              </div>
            </div>

            <div className="form-group">
              <label>Detalhes e Pauta</label>
              <textarea
                rows={3}
                className="ui-input"
                placeholder="Pontos a abordar, objetivos da conversa ou pauta..."
                value={globalActivityForm.details}
                onChange={(e) => setGlobalActivityForm({ ...globalActivityForm, details: e.target.value })}
              />
            </div>

            <div className="modal-footer ui-form__actions">
              <button
                type="button"
                className="btn-secondary ui-button ui-button--secondary"
                onClick={() => setIsGlobalActivityModalOpen(false)}
              >
                Cancelar
              </button>
              <button
                type="submit"
                className="btn-primary ui-button ui-button--primary"
                disabled={isSavingGlobalActivity}
              >
                {isSavingGlobalActivity ? 'Agendando...' : 'Confirmar Agendamento'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* =================================================================== */}
      {/* MODAL DE EDITAR LEAD (FASE 2)                                       */}
      {/* =================================================================== */}
      {editingLead && (
        <Modal
          isOpen={true}
          onClose={() => setEditingLead(null)}
          title={`Editar Lead: ${editingLead.name}`}
          subtitle="Atualize os dados cadastrais, origem e status de qualificação"
          size="md"
        >
          <form onSubmit={handleSaveEditLead} className="wizard-form">
            <div className="form-group">
              <label>Nome do Contato *</label>
              <input
                type="text"
                required
                className="ui-input"
                value={editLeadForm.name}
                onChange={(e) => setEditLeadForm({ ...editLeadForm, name: e.target.value })}
              />
            </div>

            <div className="form-row cols-2">
              <div className="form-group flex-1">
                <label>Empresa / Razão Social</label>
                <input
                  type="text"
                  className="ui-input"
                  value={editLeadForm.company_name}
                  onChange={(e) => setEditLeadForm({ ...editLeadForm, company_name: e.target.value })}
                />
              </div>
              <div className="form-group flex-1">
                <label>Status de Qualificação</label>
                <select
                  value={editLeadForm.status}
                  onChange={(e) => setEditLeadForm({ ...editLeadForm, status: e.target.value })}
                  className="ui-input"
                >
                  <option value="NEW">🟢 Novo</option>
                  <option value="CONTACTED">🟡 Em Contato</option>
                  <option value="QUALIFIED">⭐ Qualificado</option>
                  <option value="CONVERTED">🏆 Convertido em Negócio</option>
                  <option value="DISQUALIFIED">⚪ Desqualificado</option>
                </select>
              </div>
            </div>

            <div className="form-row cols-2">
              <div className="form-group flex-1">
                <label>E-mail</label>
                <input
                  type="email"
                  className="ui-input"
                  value={editLeadForm.email}
                  onChange={(e) => setEditLeadForm({ ...editLeadForm, email: e.target.value })}
                />
              </div>
              <div className="form-group flex-1">
                <label>Telefone / WhatsApp</label>
                <input
                  type="text"
                  className="ui-input"
                  value={editLeadForm.phone}
                  onChange={(e) => setEditLeadForm({ ...editLeadForm, phone: e.target.value })}
                />
              </div>
            </div>

            <div className="form-group">
              <label>Origem do Lead</label>
              <select
                value={editLeadForm.source}
                onChange={(e) => setEditLeadForm({ ...editLeadForm, source: e.target.value })}
                className="ui-input"
              >
                <option value="Site / Formulário">Site / Formulário</option>
                <option value="Indicação">Indicação</option>
                <option value="Contato Telefônico">Contato Telefônico</option>
                <option value="Evento / Feira">Evento / Feira</option>
                <option value="Outro">Outro</option>
              </select>
            </div>

            <div className="form-group">
              <label>Observações & Notas</label>
              <textarea
                rows={3}
                className="ui-input"
                value={editLeadForm.notes}
                onChange={(e) => setEditLeadForm({ ...editLeadForm, notes: e.target.value })}
              />
            </div>

            <div className="modal-footer ui-form__actions">
              <button
                type="button"
                className="btn-secondary ui-button ui-button--secondary"
                onClick={() => setEditingLead(null)}
              >
                Cancelar
              </button>
              <button
                type="submit"
                className="btn-primary ui-button ui-button--primary"
              >
                Salvar Alterações
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* =================================================================== */}
      {/* MODAL DE MOTIVO DE PERDA                                            */}
      {/* =================================================================== */}
      {lossModalOpp && (
        <Modal
          isOpen={true}
          onClose={() => setLossModalOpp(null)}
          title="Registrar Motivo da Perda"
          subtitle={`Informe o motivo pelo qual a oportunidade '${lossModalOpp.title}' não foi fechada.`}
          size="md"
        >
          <form onSubmit={handleConfirmLoss} className="wizard-form">
            <div className="form-group">
              <label>Motivo Principal da Perda *</label>
              <select
                value={lossReason}
                onChange={(e) => setLossReason(e.target.value)}
                className="ui-input"
              >
                {LOSS_REASONS.map(r => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </div>

            {lossReason === 'Concorrente escolhido' && (
              <div className="form-group">
                <label>Nome do Concorrente (Opcional)</label>
                <input
                  type="text"
                  className="ui-input"
                  placeholder="Ex: Empresa Concorrente Ltda"
                  value={lossCompetitor}
                  onChange={(e) => setLossCompetitor(e.target.value)}
                />
              </div>
            )}

            <div className="form-group">
              <label>Observações e Aprendizados</label>
              <textarea
                rows={3}
                className="ui-input"
                placeholder="Detalhe o feedback do cliente para alimentar a inteligência comercial..."
                value={lossNotes}
                onChange={(e) => setLossNotes(e.target.value)}
              />
            </div>

            <div className="modal-footer ui-form__actions">
              <button
                type="button"
                className="btn-secondary ui-button ui-button--secondary"
                onClick={() => setLossModalOpp(null)}
              >
                Cancelar
              </button>
              <button
                type="submit"
                className="btn-danger ui-button ui-button--danger"
                disabled={isSavingLoss}
              >
                {isSavingLoss ? 'Registrando...' : 'Confirmar e Marcar como Perdido'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* =================================================================== */}
      {/* MODAL NOVO LEAD                                                     */}
      {/* =================================================================== */}
      <Modal
        isOpen={isLeadModalOpen}
        onClose={() => setIsLeadModalOpen(false)}
        title="Novo Lead / Prospect"
        subtitle="Cadastro integrado com a base centralizada de clientes de Vendas"
        size="md"
      >
        <form onSubmit={handleCreateLead} className="wizard-form">
          <CustomerPicker
            value={leadForm.customer_id}
            onChange={(customer: Customer | null) => {
              if (customer) {
                setLeadForm(prev => ({
                  ...prev,
                  customer_id: customer.id,
                  name: customer.trade_name || customer.name,
                  company_name: customer.name,
                  document: customer.document || '',
                  email: customer.email || '',
                  phone: customer.phone || ''
                }));
              } else {
                setLeadForm(prev => ({ ...prev, customer_id: '' }));
              }
            }}
            label="Vincular a Cliente Existente ou Cadastrar Novo *"
            placeholder="Pesquise cliente existente ou clique em + Novo Cliente..."
          />

          <div className="form-group">
            <label>Nome do Contato / Responsável *</label>
            <input
              type="text"
              required
              className="ui-input"
              placeholder="Ex: Carlos Mendonça"
              value={leadForm.name}
              onChange={(e) => setLeadForm({ ...leadForm, name: e.target.value })}
            />
          </div>

          <div className="form-row cols-2">
            <div className="form-group flex-1">
              <label>Empresa / Razão Social</label>
              <input
                type="text"
                className="ui-input"
                placeholder="Ex: Distribuidora Sol Ltda"
                value={leadForm.company_name}
                onChange={(e) => setLeadForm({ ...leadForm, company_name: e.target.value })}
              />
            </div>

            <div className="form-group flex-1">
              <label>CPF / CNPJ</label>
              <input
                type="text"
                className="ui-input"
                placeholder="00.000.000/0000-00"
                value={leadForm.document}
                onChange={(e) => setLeadForm({ ...leadForm, document: e.target.value })}
              />
            </div>
          </div>

          <div className="form-row cols-2">
            <div className="form-group flex-1">
              <label>E-mail</label>
              <input
                type="email"
                className="ui-input"
                placeholder="carlos@exemplo.com"
                value={leadForm.email}
                onChange={(e) => setLeadForm({ ...leadForm, email: e.target.value })}
              />
            </div>

            <div className="form-group flex-1">
              <label>Telefone / WhatsApp</label>
              <input
                type="text"
                className="ui-input"
                placeholder="(00) 00000-0000"
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
              className="ui-input"
            >
              <option value="Site / Formulário">Site / Formulário</option>
              <option value="Indicação">Indicação</option>
              <option value="Contato Telefônico">Contato Telefônico</option>
              <option value="Evento / Feira">Evento / Feira</option>
              <option value="Outro">Outro</option>
            </select>
          </div>

          <div className="form-group">
            <label>Notas e Perfil do Prospect</label>
            <textarea
              rows={3}
              className="ui-input"
              placeholder="Interesses, necessidades e observações..."
              value={leadForm.notes}
              onChange={(e) => setLeadForm({ ...leadForm, notes: e.target.value })}
            />
          </div>

          <div className="modal-footer ui-form__actions">
            <button
              type="button"
              className="btn-secondary ui-button ui-button--secondary"
              onClick={() => setIsLeadModalOpen(false)}
            >
              Cancelar
            </button>
            <button
              type="submit"
              className="btn-primary ui-button ui-button--primary"
            >
              Salvar Lead
            </button>
          </div>
        </form>
      </Modal>

      {/* =================================================================== */}
      {/* MODAL NOVA OPORTUNIDADE                                             */}
      {/* =================================================================== */}
      <Modal
        isOpen={isOppModalOpen}
        onClose={() => setIsOppModalOpen(false)}
        title={convertingLead ? `Converter Lead em Oportunidade: ${convertingLead.name}` : "Nova Oportunidade Comercial"}
        subtitle="Vincule um cliente oficial cadastrado em Vendas para o controle do pipeline"
        size="md"
      >
        <form onSubmit={handleCreateOpp} className="wizard-form">
          <CustomerPicker
            value={oppForm.customer_id}
            onChange={(customer: Customer | null) => {
              if (customer) {
                setOppForm(prev => ({
                  ...prev,
                  customer_id: customer.id,
                  customer_name: customer.trade_name || customer.name
                }));
              } else {
                setOppForm(prev => ({ ...prev, customer_id: '', customer_name: '' }));
              }
            }}
            label="Cliente / Empresa Vinculada *"
            placeholder="Selecione o cliente oficial ou clique em + Novo Cliente..."
          />

          <div className="form-group">
            <label>Título do Negócio / Oportunidade *</label>
            <input
              type="text"
              required
              className="ui-input"
              placeholder="Ex: Fornecimento Anual de Insumos - 2026"
              value={oppForm.title}
              onChange={(e) => setOppForm({ ...oppForm, title: e.target.value })}
            />
          </div>

          <div className="form-row cols-2">
            <div className="form-group flex-1">
              <label>Valor Estimado (R$)</label>
              <input
                type="number"
                step="0.01"
                min="0"
                className="ui-input"
                placeholder="0.00"
                value={oppForm.estimated_amount}
                onChange={(e) => setOppForm({ ...oppForm, estimated_amount: e.target.value })}
              />
            </div>

            <div className="form-group flex-1">
              <label>Probabilidade de Fechamento (%)</label>
              <input
                type="number"
                min="0"
                max="100"
                className="ui-input"
                value={oppForm.probability_percent}
                onChange={(e) => setOppForm({ ...oppForm, probability_percent: parseInt(e.target.value) || 50 })}
              />
            </div>
          </div>

          <div className="form-row cols-2">
            <div className="form-group flex-1">
              <label>Previsão de Fechamento</label>
              <input
                type="date"
                className="ui-input"
                value={oppForm.expected_closing_date}
                onChange={(e) => setOppForm({ ...oppForm, expected_closing_date: e.target.value })}
              />
            </div>

            <div className="form-group flex-1">
              <label>Estágio Inicial no Funil</label>
              <select
                value={oppForm.stage}
                onChange={(e) => setOppForm({ ...oppForm, stage: e.target.value })}
                className="ui-input"
              >
                {stages.map(stg => (
                  <option key={stg.id || stg.code} value={stg.code}>{stg.name}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="modal-footer ui-form__actions">
            <button
              type="button"
              className="btn-secondary ui-button ui-button--secondary"
              onClick={() => setIsOppModalOpen(false)}
            >
              Cancelar
            </button>
            <button
              type="submit"
              className="btn-primary ui-button ui-button--primary"
            >
              {convertingLead ? 'Converter e Criar Oportunidade' : 'Criar Oportunidade'}
            </button>
          </div>
        </form>
      </Modal>

      {/* =================================================================== */}
      {/* MODAL NOVA COTAÇÃO VINCULADA                                        */}
      {/* =================================================================== */}
      <Modal
        isOpen={isQuoteModalOpen}
        onClose={() => setIsQuoteModalOpen(false)}
        title={`Emitir Cotação Comercial: ${selectedOppForQuote?.title || ''}`}
        subtitle={`Cliente: ${selectedOppForQuote?.customer_name || ''}`}
        size="lg"
      >
        <form onSubmit={handleSaveQuotation} className="wizard-form">
          <div className="form-row cols-2">
            <div className="form-group flex-1">
              <label>Validade da Proposta *</label>
              <input
                type="date"
                required
                className="ui-input"
                value={quoteValidUntil}
                onChange={(e) => setQuoteValidUntil(e.target.value)}
              />
            </div>
            <div className="form-group flex-1">
              <label>Condição de Pagamento</label>
              <input
                type="text"
                className="ui-input"
                placeholder="Ex: 30 DDL, À Vista com 5% de desconto"
                value={quotePaymentTerms}
                onChange={(e) => setQuotePaymentTerms(e.target.value)}
              />
            </div>
          </div>

          <div className="items-section">
            <div className="items-header-line">
              <h4>Itens e Produtos da Proposta ({quoteItems.length})</h4>
              <button
                type="button"
                className="btn-secondary sm ui-button ui-button--secondary ui-button--sm"
                onClick={handleAddQuoteItem}
              >
                <Plus size={14} /> Adicionar Item
              </button>
            </div>

            {quoteItems.length === 0 ? (
              <div className="empty-items-box">
                <Package size={24} />
                <p>Nenhum item adicionado à proposta. Clique acima para incluir produtos cadastrados no Estoque.</p>
              </div>
            ) : (
              <div className="quote-items-table-wrap">
                <table className="quote-items-table">
                  <thead>
                    <tr>
                      <th>Produto</th>
                      <th style={{ width: '100px' }}>Qtd</th>
                      <th style={{ width: '130px' }}>Preço Un.</th>
                      <th style={{ width: '120px' }}>Desconto</th>
                      <th style={{ width: '130px' }}>Subtotal</th>
                      <th style={{ width: '50px', textAlign: 'center' }}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {quoteItems.map((item, idx) => {
                      const subtotal = (item.quantity * item.unit_price) - (item.discount_amount || 0);
                      return (
                        <tr key={idx}>
                          <td>
                            <select
                              value={item.product_id}
                              onChange={(e) => handleQuoteItemChange(idx, 'product_id', e.target.value)}
                              className="ui-input item-product-select"
                            >
                              {products.map(p => (
                                <option key={p.id} value={p.id}>{p.name} ({p.sku || 'Sem SKU'})</option>
                              ))}
                            </select>
                          </td>
                          <td>
                            <input
                              type="number"
                              min="1"
                              value={item.quantity}
                              onChange={(e) => handleQuoteItemChange(idx, 'quantity', e.target.value)}
                              className="ui-input"
                            />
                          </td>
                          <td>
                            <input
                              type="number"
                              step="0.01"
                              min="0"
                              value={item.unit_price}
                              onChange={(e) => handleQuoteItemChange(idx, 'unit_price', e.target.value)}
                              className="ui-input"
                            />
                          </td>
                          <td>
                            <input
                              type="number"
                              step="0.01"
                              min="0"
                              value={item.discount_amount}
                              onChange={(e) => handleQuoteItemChange(idx, 'discount_amount', e.target.value)}
                              className="ui-input"
                            />
                          </td>
                          <td>
                            <strong className="subtotal-val">{fmtCurrency(subtotal)}</strong>
                          </td>
                          <td style={{ textAlign: 'center' }}>
                            <button
                              type="button"
                              className="btn-remove-item"
                              onClick={() => handleRemoveQuoteItem(idx)}
                              title="Remover Item"
                            >
                              <Trash2 size={15} />
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            <div className="quote-total-bar">
              <span>Total da Cotação:</span>
              <strong className="total-highlight">{fmtCurrency(quoteTotalAmount)}</strong>
            </div>
          </div>

          <div className="modal-footer ui-form__actions">
            <button
              type="button"
              className="btn-secondary ui-button ui-button--secondary"
              onClick={() => setIsQuoteModalOpen(false)}
            >
              Cancelar
            </button>
            <button
              type="submit"
              className="btn-primary ui-button ui-button--primary"
              disabled={isSavingQuote}
            >
              {isSavingQuote ? 'Gerando Cotação...' : 'Gerar e Vincular Cotação'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
