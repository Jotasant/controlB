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

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, Kanban, Users,
  Clock, Phone, Mail, FileText,
  Trash2, Settings, CheckCircle2, Layers,
  Package, Plus, DollarSign, TrendingUp,
  RefreshCw, UserPlus, MessageSquare,
  ArrowRight, X, AlertTriangle,
  Building2, Eye,
  Edit3, CalendarDays,
  ArrowUpRight, Check,
  BarChart3, Download, Award, TrendingDown,
  Target, Zap, Printer, Copy, Tag,
  ShieldCheck, Star, CheckCheck,
  Briefcase, CreditCard,
  User, UserCheck, Calendar, Sparkles,
  FileCheck, ExternalLink, GitBranch,
  SlidersHorizontal, List, LayoutGrid
} from 'lucide-react';
import { crmService, salesService, inventoryService, documentService, formatApiError } from '@/services/api';
import type { Lead, Opportunity, Product, SalesQuote, CRMStage, Customer, CustomerInteraction, BusinessDocumentChain, SellerResponse } from '@/types';
import { Modal } from '@/components/Modal/Modal';
import { CustomerPicker } from '@/components/CustomerPicker';
import { CustomerModal } from '@/components/CustomerModal/CustomerModal';
import { QuoteModal } from '@/components/QuoteModal/QuoteModal';
import { DocumentTimeline } from '@/components/DocumentTimeline/DocumentTimeline';
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

const DEFAULT_OPP_COLUMNS: Record<string, boolean> = {
  title: true,
  customer: true,
  estimated_amount: true,
  probability_percent: true,
  stage: true,
  activity_status: true,
  expected_closing_date: true,
  responsible_name: true,
  sales_team: true,
  actions: true,
};

export const CRM: React.FC = () => {
  const toast = useToast();
  const navigate = useNavigate();

  // Tab & View Switcher State
  const [activeTab, setActiveTab] = useState<'dashboard' | 'pipeline' | 'leads' | 'activities' | 'stages' | 'reports'>('pipeline');
  const [oppViewMode, setOppViewMode] = useState<'kanban' | 'list'>('kanban');
  const [isColumnSelectorOpen, setIsColumnSelectorOpen] = useState<boolean>(false);
  const [visibleColumns, setVisibleColumns] = useState<Record<string, boolean>>(() => {
    try {
      const saved = localStorage.getItem('controlb_crm_opp_columns');
      return saved ? { ...DEFAULT_OPP_COLUMNS, ...JSON.parse(saved) } : DEFAULT_OPP_COLUMNS;
    } catch {
      return DEFAULT_OPP_COLUMNS;
    }
  });

  const [loading, setLoading] = useState<boolean>(true);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [stages, setStages] = useState<CRMStage[]>(DEFAULT_FALLBACK_STAGES);
  const [products, setProducts] = useState<Product[]>([]);
  const [allInteractions, setAllInteractions] = useState<CustomerInteraction[]>([]);
  const [sellersList, setSellersList] = useState<SellerResponse[]>([]);
  const [pendingSidebarActivities, setPendingSidebarActivities] = useState<any[]>([]);

  const toggleColumnVisibility = (colKey: string) => {
    setVisibleColumns(prev => {
      const next = { ...prev, [colKey]: !prev[colKey] };
      localStorage.setItem('controlb_crm_opp_columns', JSON.stringify(next));
      return next;
    });
  };

  // Metas Comerciais & Previsibilidade (Fase 4)
  const [monthlySalesGoal, setMonthlySalesGoal] = useState<number>(() => {
    const saved = localStorage.getItem('controlb_crm_monthly_goal');
    return saved ? Number(saved) : 100000;
  });
  const [isGoalModalOpen, setIsGoalModalOpen] = useState<boolean>(false);
  const [tempGoalInput, setTempGoalInput] = useState<string>(() => {
    const saved = localStorage.getItem('controlb_crm_monthly_goal');
    return saved ? saved : '100000';
  });

  // Filtros Oportunidades
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [stageFilter, setStageFilter] = useState<string>('ALL');
  const [oppActivityFilter, setOppActivityFilter] = useState<'ALL' | 'STAGNANT'>('ALL');

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

  // Detalhes da Oportunidade & Studio
  const [selectedOpp, setSelectedOpp] = useState<Opportunity | null>(null);
  const [oppInteractions, setOppInteractions] = useState<CustomerInteraction[]>([]);

  // Modal Motivo de Perda
  const [lossModalOpp, setLossModalOpp] = useState<Opportunity | null>(null);
  const [lossReason, setLossReason] = useState<string>(LOSS_REASONS[0]);
  const [lossCompetitor, setLossCompetitor] = useState<string>('');
  const [lossNotes, setLossNotes] = useState<string>('');
  const [isSavingLoss, setIsSavingLoss] = useState<boolean>(false);

  // Modais de Criação
  const [isLeadModalOpen, setIsLeadModalOpen] = useState<boolean>(false);
  const [isQuoteModalOpen, setIsQuoteModalOpen] = useState<boolean>(false);
  const [selectedOppForQuote, setSelectedOppForQuote] = useState<Opportunity | null>(null);

  // Rastreabilidade & Timeline Documental Transversal
  const [isDocumentTimelineOpen, setIsDocumentTimelineOpen] = useState<boolean>(false);
  const [documentTimelineLoading, setDocumentTimelineLoading] = useState<boolean>(false);
  const [documentTimelineError, setDocumentTimelineError] = useState<string | null>(null);
  const [documentChain, setDocumentChain] = useState<BusinessDocumentChain | null>(null);
  const [documentTimelineLabel, setDocumentTimelineLabel] = useState<string>('');

  const openDocumentTimeline = async (
    documentType: 'OPPORTUNITY' | 'SALES_QUOTE' | 'SALES_ORDER',
    nativeId: string,
    label: string
  ) => {
    setDocumentTimelineLabel(label);
    setDocumentTimelineError(null);
    setDocumentChain(null);
    setIsDocumentTimelineOpen(true);
    setDocumentTimelineLoading(true);

    try {
      const chain = await documentService.getChain(documentType, nativeId, true);
      setDocumentChain(chain);
    } catch (err: unknown) {
      const message = formatApiError(err, 'Não foi possível consultar a cadeia deste documento.');
      setDocumentTimelineError(message);
      toast.error(message, 'Rastreabilidade indisponível');
    } finally {
      setDocumentTimelineLoading(false);
    }
  };

  /** Handler de navegação clicável na cadeia documental */
  const handleTimelineNavigate = useCallback((documentType: string, nativeId: string) => {
    // Fecha o modal de rastreabilidade
    setIsDocumentTimelineOpen(false);

    if (documentType === 'OPPORTUNITY') {
      // Encontra e abre o detalhe da oportunidade no próprio CRM
      const opp = opportunities.find(o => o.id === nativeId);
      if (opp) {
        setActiveTab('pipeline');
        setSelectedOpp(opp);
      } else {
        toast.info('Oportunidade não encontrada na listagem atual.');
      }
    } else if (documentType === 'LEAD') {
      setActiveTab('leads');
    } else {
      // SALES_QUOTE, SALES_ORDER, INVOICE, etc. → módulo de Vendas
      navigate('/vendas');
    }
  }, [opportunities, navigate, toast]);

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

  // Proposal Studio Workspace State (Formulário Avançado de Propostas Comerciais)
  const [proposalActiveTab, setProposalActiveTab] = useState<'general' | 'customer' | 'quotes' | 'items' | 'terms' | 'approvals'>('general');
  const [proposalForm, setProposalForm] = useState({
    quote_number: 'PR-2026-0187',
    title: '',
    status: 'DRAFT' as 'DRAFT' | 'SENT' | 'APPROVED' | 'REJECTED' | 'CONVERTED',
    customer_id: '',
    customer_name: '',
    customer_document: '',
    customer_email: '',
    customer_phone: '',
    contact_person: 'Carlos Mendes',
    assigned_to_id: '' as string | undefined,
    responsible_name: 'Jefferson Santos',
    sales_team: 'Equipe Comercial Principal',
    pipeline_stage: 'PROPOSAL',
    priority: 'HIGH' as 'LOW' | 'MEDIUM' | 'HIGH',
    source: 'Indicação',
    creation_date: new Date().toISOString().split('T')[0],
    expected_closing_date: new Date(Date.now() + 20 * 86400000).toISOString().split('T')[0],
    probability_percent: 70,
    tags: ['CFTV', 'Rede', 'Infraestrutura'] as string[],
    notes: 'Cliente busca modernização do sistema de segurança e rede da nova unidade.\nProjeto inclui fornecimento, configuração e treinamento da equipe interna.',
    payment_method: 'Transferência Bancária',
    installment_terms: '30% entrada + 2x',
    delivery_deadline: '15 dias úteis',
    valid_until: new Date(Date.now() + 30 * 86400000).toISOString().split('T')[0],
    warranty_terms: '12 meses',
    sla_support: '8x5 - NBR 15965 / Suporte Remoto',
    special_conditions: 'Treinamento incluso e suporte remoto nos primeiros 30 dias.',
    digital_acceptance: true,
    tax_amount: 0,
    freight_amount: 0
  });
  const [tagInput, setTagInput] = useState<string>('');
  const [activeQuoteId, setActiveQuoteId] = useState<string | null>(null);

  // Cliente vinculado à oportunidade e Wizard de Cadastro de Cliente (Módulo de Vendas)
  const [linkedCustomer, setLinkedCustomer] = useState<Customer | null>(null);
  const [isCustomerModalOpen, setIsCustomerModalOpen] = useState<boolean>(false);
  const [isCustomerPickerModalOpen, setIsCustomerPickerModalOpen] = useState<boolean>(false);

  // Cotações vinculadas à oportunidade e Formulário Próprio de Cotação
  const [oppQuotations, setOppQuotations] = useState<SalesQuote[]>([]);
  const [isDedicatedQuoteModalOpen, setIsDedicatedQuoteModalOpen] = useState<boolean>(false);
  const [editingQuote, setEditingQuote] = useState<SalesQuote | null>(null);

  // Itens da Proposta Principal
  const [quoteItems, setQuoteItems] = useState<Array<{
    product_id: string;
    product_name?: string;
    quantity: number;
    unit_price: number;
    discount_amount: number;
    notes?: string;
  }>>([]);
  const [isSavingQuote, setIsSavingQuote] = useState<boolean>(false);
  const [isAddingSidebarActivity, setIsAddingSidebarActivity] = useState<boolean>(false);
  const [sidebarActivityForm, setSidebarActivityForm] = useState({
    type: 'NOTE' as 'NOTE' | 'WHATSAPP' | 'CALL' | 'MEETING' | 'EMAIL',
    summary: '',
    date: new Date().toISOString().split('T')[0],
    time: new Date().toTimeString().slice(0, 5)
  });

  // ===========================================================================
  // CARREGAMENTO DE DADOS
  // ===========================================================================

  const loadCRMData = async (forceRefresh = false) => {
    setLoading(true);
    try {
      const [fetchedStages, fetchedLeads, fetchedOpps, fetchedProducts, fetchedInteractions, fetchedSellers] = await Promise.all([
        crmService.getStages(forceRefresh).catch(() => []),
        crmService.getLeads(undefined, forceRefresh).catch(() => []),
        crmService.getOpportunities(undefined, forceRefresh).catch(() => []),
        inventoryService.getProducts(undefined, forceRefresh).catch(() => []),
        crmService.getInteractions(undefined, undefined, forceRefresh).catch(() => []),
        salesService.getSellers(forceRefresh).catch(() => [])
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
      setSellersList(fetchedSellers || []);
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

  const loadOpportunityDetails = async (opp: Opportunity) => {
    setSelectedOpp(opp);
    setSelectedOppForQuote(opp);
    setConvertingLead(null);
    setProposalActiveTab('general');
    
    try {
      const [interactions, quotes] = await Promise.all([
        crmService.getInteractions(undefined, opp.id, true).catch(() => []),
        crmService.getOpportunityQuotations(opp.id, true).catch(() => [])
      ]);
      setOppInteractions(interactions);
      setOppQuotations(quotes);

      // Carrega itens da primeira cotação vinculada se existir, ou inicializa itens padrão
      const mainQuote = quotes.length > 0 ? quotes[0] : null;
      if (mainQuote && mainQuote.items && mainQuote.items.length > 0) {
        setActiveQuoteId(mainQuote.id);
        setQuoteItems(mainQuote.items.map((it: any) => ({
          product_id: it.product_id,
          product_name: it.product?.name,
          quantity: it.quantity,
          unit_price: it.unit_price,
          discount_amount: it.discount_amount || 0,
          notes: it.notes || ''
        })));
      } else {
        setActiveQuoteId(null);
        initDefaultItems();
      }

      if (opp.customer_id) {
        salesService.getCustomer(opp.customer_id, true).then(cust => {
          if (cust) {
            setLinkedCustomer(cust);
            setProposalForm(prev => ({
              ...prev,
              customer_id: cust.id,
              customer_name: cust.trade_name || cust.name,
              customer_document: cust.document || prev.customer_document,
              customer_email: cust.email || prev.customer_email,
              customer_phone: cust.phone || prev.customer_phone
            }));
          }
        }).catch(() => {
          setLinkedCustomer(null);
        });
      } else {
        setLinkedCustomer(null);
      }

      const matchedSeller = sellersList.find(s => s.id === opp.assigned_to_id);
      setPendingSidebarActivities([]);

      setProposalForm({
        quote_number: `OP-${opp.id.slice(0, 8).toUpperCase()}`,
        title: opp.title,
        status: opp.stage === 'WON' ? 'APPROVED' : (opp.stage === 'LOST' ? 'REJECTED' : 'DRAFT'),
        customer_id: opp.customer_id || '',
        customer_name: opp.customer_name,
        customer_document: (opp as any).customer?.document || '',
        customer_email: opp.lead?.email || '',
        customer_phone: opp.lead?.phone || '',
        contact_person: opp.lead?.name || 'Contato Principal',
        assigned_to_id: opp.assigned_to_id || undefined,
        responsible_name: matchedSeller ? matchedSeller.full_name : ((opp as any).assigned_to?.full_name || 'Vendedor Comercial'),
        sales_team: matchedSeller?.sales_team_name || 'Equipe Comercial',
        pipeline_stage: opp.stage,
        priority: 'HIGH',
        source: opp.lead?.source || 'Indicação',
        creation_date: opp.created_at ? opp.created_at.split('T')[0] : new Date().toISOString().split('T')[0],
        expected_closing_date: opp.expected_closing_date ? opp.expected_closing_date.split('T')[0] : new Date(Date.now() + 20 * 86400000).toISOString().split('T')[0],
        probability_percent: opp.probability_percent || 70,
        tags: ['CFTV', 'Rede', 'Infraestrutura'],
        notes: opp.lead?.notes || `Cliente busca modernização do sistema de segurança e rede da nova unidade.\nProjeto inclui fornecimento, configuração e treinamento da equipe interna.`,
        payment_method: 'Transferência Bancária',
        installment_terms: '30% entrada + 2x',
        delivery_deadline: '15 dias úteis',
        valid_until: new Date(Date.now() + 30 * 86400000).toISOString().split('T')[0],
        warranty_terms: '12 meses',
        sla_support: '8x5 - NBR 15965',
        special_conditions: 'Treinamento incluso e suporte remoto nos primeiros 30 dias.',
        digital_acceptance: true,
        tax_amount: 0,
        freight_amount: 0
      });

      setIsQuoteModalOpen(true);
    } catch (err: any) {
      toast.error(formatApiError(err, "Falha ao carregar detalhes completos da oportunidade."));
    }
  };

  const handleOpenNewOppStudio = (leadToConvert?: Lead | null, initialStage?: string) => {
    setSelectedOpp(null);
    setSelectedOppForQuote(null);
    setConvertingLead(leadToConvert || null);
    setActiveQuoteId(null);
    setProposalActiveTab('general');
    setOppInteractions([]);
    setPendingSidebarActivities([]);
    initDefaultItems();

    const defaultSeller = sellersList.length > 0 ? sellersList[0] : null;

    if (leadToConvert) {
      setProposalForm({
        quote_number: `OP-2026-${Math.floor(1000 + Math.random() * 9000)}`,
        title: `Negócio - ${leadToConvert.company_name || leadToConvert.name}`,
        status: 'DRAFT',
        customer_id: leadToConvert.customer_id || '',
        customer_name: leadToConvert.company_name || leadToConvert.name,
        customer_document: '',
        customer_email: leadToConvert.email || '',
        customer_phone: leadToConvert.phone || '',
        contact_person: leadToConvert.name,
        assigned_to_id: defaultSeller?.id || undefined,
        responsible_name: defaultSeller ? defaultSeller.full_name : 'Vendedor Comercial',
        sales_team: defaultSeller?.sales_team_name || 'Equipe Comercial',
        pipeline_stage: initialStage || stages[0]?.code || 'PROSPECTING',
        priority: 'HIGH',
        source: leadToConvert.source || 'Indicação',
        creation_date: new Date().toISOString().split('T')[0],
        expected_closing_date: new Date(Date.now() + 20 * 86400000).toISOString().split('T')[0],
        probability_percent: 50,
        tags: ['Convertido do Lead'],
        notes: `Convertido do Lead: ${leadToConvert.name} (${leadToConvert.source || 'Sem origem'}). Anotações: ${leadToConvert.notes || '-'}`,
        payment_method: 'Transferência Bancária',
        installment_terms: '30% entrada + 2x',
        delivery_deadline: '15 dias úteis',
        valid_until: new Date(Date.now() + 30 * 86400000).toISOString().split('T')[0],
        warranty_terms: '12 meses',
        sla_support: '8x5 - NBR 15965',
        special_conditions: 'Treinamento incluso e suporte remoto nos primeiros 30 dias.',
        digital_acceptance: true,
        tax_amount: 0,
        freight_amount: 0
      });
    } else {
      setProposalForm({
        quote_number: `OP-2026-${Math.floor(1000 + Math.random() * 9000)}`,
        title: '',
        status: 'DRAFT',
        customer_id: '',
        customer_name: '',
        customer_document: '',
        customer_email: '',
        customer_phone: '',
        contact_person: '',
        assigned_to_id: defaultSeller?.id || undefined,
        responsible_name: defaultSeller ? defaultSeller.full_name : 'Vendedor Comercial',
        sales_team: defaultSeller?.sales_team_name || 'Equipe Comercial',
        pipeline_stage: initialStage || stages[0]?.code || 'PROSPECTING',
        priority: 'HIGH',
        source: 'Indicação',
        creation_date: new Date().toISOString().split('T')[0],
        expected_closing_date: new Date(Date.now() + 20 * 86400000).toISOString().split('T')[0],
        probability_percent: 50,
        tags: ['Comercial'],
        notes: '',
        payment_method: 'Transferência Bancária',
        installment_terms: '30 DDL',
        delivery_deadline: '15 dias úteis',
        valid_until: new Date(Date.now() + 30 * 86400000).toISOString().split('T')[0],
        warranty_terms: '12 meses',
        sla_support: '8x5 - NBR 15965',
        special_conditions: 'Condições comerciais padrão.',
        digital_acceptance: true,
        tax_amount: 0,
        freight_amount: 0
      });
    }

    setIsQuoteModalOpen(true);
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
    handleOpenNewOppStudio(lead);
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
  // PROPOSAL STUDIO — WORKSPACE & ENRIQUECIMENTO DE PROPOSTAS COMERCIAIS
  // ===========================================================================

  const initDefaultItems = () => {
    if (products.length > 0) {
      setQuoteItems([
        {
          product_id: products[0].id,
          product_name: products[0].name,
          quantity: 1,
          unit_price: products[0].sale_price || products[0].reference_price || 12000.0,
          discount_amount: 600.0
        },
        ...(products.length > 1 ? [{
          product_id: products[1].id,
          product_name: products[1].name,
          quantity: 2,
          unit_price: products[1].sale_price || products[1].reference_price || 1850.0,
          discount_amount: 0
        }] : [])
      ]);
    } else {
      setQuoteItems([]);
    }
  };

  const handleAddQuoteItem = () => {
    if (products.length === 0) {
      toast.warning("Cadastre produtos no Almoxarifado / Estoque para adicioná-los à proposta.", "Catálogo Vazio");
      return;
    }
    const defaultProduct = products[0];
    setQuoteItems(prev => [
      ...prev,
      {
        product_id: defaultProduct.id,
        product_name: defaultProduct.name,
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
          item.product_name = p.name;
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

  const handleAddTag = (e?: React.KeyboardEvent | React.MouseEvent) => {
    if (e && 'key' in e && e.key !== 'Enter') return;
    if (e) e.preventDefault();
    const trimmed = tagInput.trim();
    if (!trimmed) return;
    if (!proposalForm.tags.includes(trimmed)) {
      setProposalForm(prev => ({ ...prev, tags: [...prev.tags, trimmed] }));
    }
    setTagInput('');
  };

  const handleRemoveTag = (tagToRemove: string) => {
    setProposalForm(prev => ({ ...prev, tags: prev.tags.filter(t => t !== tagToRemove) }));
  };

  const proposalItemsSubtotal = useMemo(() => {
    return quoteItems.reduce((acc, it) => acc + (it.quantity * it.unit_price), 0);
  }, [quoteItems]);

  const proposalTotalDiscount = useMemo(() => {
    return quoteItems.reduce((acc, it) => acc + (it.discount_amount || 0), 0);
  }, [quoteItems]);

  const proposalFinalTotal = useMemo(() => {
    const sub = proposalItemsSubtotal - proposalTotalDiscount;
    const tax = Number(proposalForm.tax_amount) || 0;
    const freight = Number(proposalForm.freight_amount) || 0;
    return Math.max(0, sub + tax + freight);
  }, [proposalItemsSubtotal, proposalTotalDiscount, proposalForm.tax_amount, proposalForm.freight_amount]);



  // Handlers do Formulário Dedicado de Cotação
  const handleOpenNewQuoteModal = () => {
    setEditingQuote(null);
    setIsDedicatedQuoteModalOpen(true);
  };

  const handleOpenEditQuoteModal = (quote: SalesQuote) => {
    setEditingQuote(quote);
    setIsDedicatedQuoteModalOpen(true);
  };

  const handleSetMainQuote = async (quote: SalesQuote) => {
    if (!selectedOpp) return;
    try {
      setActiveQuoteId(quote.id);
      if (quote.items && quote.items.length > 0) {
        const mappedItems = quote.items.map((it: any) => ({
          product_id: it.product_id,
          product_name: it.product?.name,
          quantity: it.quantity,
          unit_price: it.unit_price,
          discount_amount: it.discount_amount || 0,
          notes: it.notes || ''
        }));
        setQuoteItems(mappedItems);
        const sub = mappedItems.reduce((acc, it) => acc + ((it.quantity * it.unit_price) - (it.discount_amount || 0)), 0);
        await crmService.updateOpportunity(selectedOpp.id, {
          estimated_amount: sub
        });
        setOpportunities(prev => prev.map(o => o.id === selectedOpp.id ? { ...o, estimated_amount: sub } : o));
        setSelectedOpp(prev => prev ? { ...prev, estimated_amount: sub } : null);
      }
      toast.success(`Cotação '${quote.quote_number}' definida como principal da oportunidade.`, "Cotação Principal");
    } catch (err: any) {
      toast.error(formatApiError(err, "Erro ao definir cotação principal."));
    }
  };

  // Handlers do Wizard de Cadastro e Vinculação de Clientes (Módulo de Vendas)
  const handleOpenEditCustomerModal = () => {
    setIsCustomerModalOpen(true);
  };

  const handleOpenNewCustomerModal = () => {
    setLinkedCustomer(null);
    setIsCustomerModalOpen(true);
  };



  const handleLinkCustomerFromPicker = async (cust: Customer | null) => {
    if (!cust) return;
    setLinkedCustomer(cust);
    setProposalForm(prev => ({
      ...prev,
      customer_id: cust.id,
      customer_name: cust.trade_name || cust.name,
      customer_document: cust.document || '',
      customer_email: cust.email || '',
      customer_phone: cust.phone || ''
    }));

    const targetOppId = selectedOpp?.id || selectedOppForQuote?.id;
    if (targetOppId) {
      try {
        await crmService.updateOpportunity(targetOppId, {
          customer_id: cust.id,
          customer_name: cust.trade_name || cust.name
        });
        setOpportunities(prev => prev.map(o => o.id === targetOppId ? {
          ...o,
          customer_id: cust.id,
          customer_name: cust.trade_name || cust.name
        } : o));
        setSelectedOpp(prev => prev ? {
          ...prev,
          customer_id: cust.id,
          customer_name: cust.trade_name || cust.name
        } : null);
        toast.success(`Cliente '${cust.name}' vinculado a esta oportunidade!`, "Cliente Vinculado");
      } catch (err: any) {
        toast.error(formatApiError(err, "Erro ao vincular cliente à oportunidade."));
      }
    }
    setIsCustomerPickerModalOpen(false);
  };

  const handleSaveProposal = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!proposalForm.title.trim()) {
      toast.warning("Informe o título da oportunidade comercial.", "Título Obrigatório");
      return;
    }

    setIsSavingQuote(true);
    try {
      if (selectedOppForQuote) {
        // Atualiza oportunidade existente no funil
        await crmService.updateOpportunityStage(selectedOppForQuote.id, proposalForm.pipeline_stage);
        await crmService.updateOpportunity(selectedOppForQuote.id, {
          title: proposalForm.title.trim(),
          customer_name: proposalForm.customer_name.trim(),
          estimated_amount: proposalFinalTotal,
          probability_percent: proposalForm.probability_percent,
          expected_closing_date: proposalForm.expected_closing_date,
          assigned_to_id: proposalForm.assigned_to_id || undefined,
        });
        
        // Emite/atualiza itens cotados
        if (quoteItems.length > 0) {
          await crmService.createQuoteFromOpportunity(selectedOppForQuote.id, quoteItems);
        }

        // Persiste atividades pendentes se houver
        if (pendingSidebarActivities.length > 0) {
          for (const act of pendingSidebarActivities) {
            try {
              await crmService.createInteraction({
                opportunity_id: selectedOppForQuote.id,
                interaction_type: act.interaction_type,
                summary: act.summary,
                interaction_date: act.interaction_date
              });
            } catch (err) {
              console.error("Erro ao salvar atividade pendente:", err);
            }
          }
          setPendingSidebarActivities([]);
        }

        setOpportunities(prev => prev.map(o => o.id === selectedOppForQuote.id ? {
          ...o,
          title: proposalForm.title.trim(),
          customer_name: proposalForm.customer_name.trim(),
          estimated_amount: proposalFinalTotal,
          probability_percent: proposalForm.probability_percent,
          expected_closing_date: proposalForm.expected_closing_date,
          stage: proposalForm.pipeline_stage || o.stage,
          assigned_to_id: proposalForm.assigned_to_id || o.assigned_to_id
        } : o));

        toast.success(`Oportunidade '${proposalForm.title}' atualizada com sucesso!`, "Negócio Salvo");
      } else {
        // Cria nova oportunidade comercial
        const created = await crmService.createOpportunity({
          title: proposalForm.title.trim(),
          customer_name: proposalForm.customer_name.trim() || 'Cliente sem identificação',
          customer_id: proposalForm.customer_id || undefined,
          assigned_to_id: proposalForm.assigned_to_id || undefined,
          estimated_amount: proposalFinalTotal,
          probability_percent: proposalForm.probability_percent || 50,
          expected_closing_date: proposalForm.expected_closing_date || undefined,
          stage: proposalForm.pipeline_stage || (stages[0]?.code || 'PROSPECTING'),
          lead_id: convertingLead ? convertingLead.id : undefined
        });

        if (quoteItems.length > 0) {
          await crmService.createQuoteFromOpportunity(created.id, quoteItems);
        }

        // Persiste anotações/follow-ups adicionados durante a criação
        if (pendingSidebarActivities.length > 0) {
          for (const act of pendingSidebarActivities) {
            try {
              await crmService.createInteraction({
                opportunity_id: created.id,
                interaction_type: act.interaction_type,
                summary: act.summary,
                interaction_date: act.interaction_date
              });
            } catch (err) {
              console.error("Erro ao salvar atividade pendente na nova oportunidade:", err);
            }
          }
          setPendingSidebarActivities([]);
        }

        if (convertingLead) {
          await crmService.updateLead(convertingLead.id, { status: 'CONVERTED' });
          setConvertingLead(null);
        }

        toast.success(`Oportunidade '${proposalForm.title}' criada e adicionada ao funil!`, "Negócio Criado");
      }

      setIsQuoteModalOpen(false);
      setSelectedOpp(null);
      setSelectedOppForQuote(null);
      void loadCRMData();
    } catch (err: any) {
      toast.error(formatApiError(err, "Falha ao salvar oportunidade comercial."));
    } finally {
      setIsSavingQuote(false);
    }
  };

  const handleSendProposalWhatsApp = () => {
    const phone = proposalForm.customer_phone || selectedOppForQuote?.lead?.phone;
    const digits = cleanPhone(phone);
    if (!digits) {
      toast.warning("Informe o telefone/WhatsApp do cliente na aba '2. Cliente' para compartilhar.", "WhatsApp Ausente");
      return;
    }
    const lines = [
      `*PROPOSTA COMERCIAL — CONTROLB*`,
      `📄 *Proposta:* ${proposalForm.quote_number}`,
      `🏢 *Cliente:* ${proposalForm.customer_name}`,
      `📌 *Negócio:* ${proposalForm.title}`,
      `💰 *Valor Total:* ${fmtCurrency(proposalFinalTotal)}`,
      `💳 *Condições:* ${proposalForm.payment_method} (${proposalForm.installment_terms})`,
      `⏳ *Validade:* até ${fmtDate(proposalForm.valid_until)}`,
      `🚚 *Prazo de Entrega:* ${proposalForm.delivery_deadline}`,
      `🛡️ *Garantia & SLA:* ${proposalForm.warranty_terms} / ${proposalForm.sla_support}`,
      ``,
      `Olá ${proposalForm.contact_person || proposalForm.customer_name}, segue nossa proposta comercial detalhada para sua apreciação. Ficamos à disposição!`
    ].join('\n');
    window.open(`https://wa.me/${digits}?text=${encodeURIComponent(lines)}`, '_blank');
  };

  const handleSendProposalEmail = () => {
    const email = proposalForm.customer_email || selectedOppForQuote?.lead?.email;
    if (!email) {
      toast.warning("Informe o e-mail do cliente na aba '2. Cliente' para enviar a proposta.", "E-mail Ausente");
      return;
    }
    const subject = `Proposta Comercial ${proposalForm.quote_number} — ${proposalForm.title} (ControlB)`;
    const body = [
      `Prezado(a) ${proposalForm.contact_person || proposalForm.customer_name},\n\n`,
      `Agradecemos pela oportunidade e apresentamos nossa proposta comercial detalhada:\n\n`,
      `• Número da Proposta: ${proposalForm.quote_number}\n`,
      `• Projeto/Escopo: ${proposalForm.title}\n`,
      `• Valor Total: ${fmtCurrency(proposalFinalTotal)}\n`,
      `• Condição de Pagamento: ${proposalForm.payment_method} (${proposalForm.installment_terms})\n`,
      `• Prazo de Entrega: ${proposalForm.delivery_deadline}\n`,
      `• Garantia: ${proposalForm.warranty_terms}\n`,
      `• SLA / Suporte: ${proposalForm.sla_support}\n`,
      `• Validade: ${fmtDate(proposalForm.valid_until)}\n\n`,
      `Observações do Projeto:\n${proposalForm.notes}\n\n`,
      `Atenciosamente,\n${proposalForm.responsible_name}\nControlB — Gestão Empresarial Integrada`
    ].join('');
    window.location.href = `mailto:${email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  };

  const handlePrintProposal = () => {
    window.print();
  };

  const handleDuplicateProposal = () => {
    const newNum = `${proposalForm.quote_number}-V2`;
    setProposalForm(prev => ({
      ...prev,
      quote_number: newNum,
      status: 'DRAFT',
      creation_date: new Date().toISOString().split('T')[0]
    }));
    setActiveQuoteId(null);
    toast.info(`Proposta duplicada como ${newNum}. Salve para persistir a nova versão.`, "Proposta Duplicada");
  };

  const handleSaveSidebarActivity = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sidebarActivityForm.summary.trim()) {
      toast.warning("Informe o resumo do follow-up.", "Resumo Obrigatório");
      return;
    }

    const scheduledDate = `${sidebarActivityForm.date}T${sidebarActivityForm.time}:00Z`;

    if (!selectedOppForQuote) {
      // Registro em rascunho de proposta ainda não persistida
      const draftActivity = {
        id: `draft_${Date.now()}`,
        interaction_type: sidebarActivityForm.type,
        summary: sidebarActivityForm.summary.trim(),
        interaction_date: scheduledDate,
        created_at: new Date().toISOString(),
        is_pending: true
      };
      setPendingSidebarActivities(prev => [draftActivity, ...prev]);
      setIsAddingSidebarActivity(false);
      setSidebarActivityForm({
        type: 'NOTE',
        summary: '',
        date: new Date().toISOString().split('T')[0],
        time: new Date().toTimeString().slice(0, 5)
      });
      toast.info("Anotação adicionada ao rascunho. Será salva junto com a oportunidade!", "Rascunho Adicionado");
      return;
    }

    try {
      const interaction = await crmService.createInteraction({
        opportunity_id: selectedOppForQuote.id,
        interaction_type: sidebarActivityForm.type,
        summary: sidebarActivityForm.summary.trim(),
        interaction_date: scheduledDate
      });
      setAllInteractions(prev => [interaction, ...prev]);
      if (selectedOpp?.id === selectedOppForQuote.id) {
        setOppInteractions(prev => [interaction, ...prev]);
      }
      setIsAddingSidebarActivity(false);
      setSidebarActivityForm({
        type: 'NOTE',
        summary: '',
        date: new Date().toISOString().split('T')[0],
        time: new Date().toTimeString().slice(0, 5)
      });
      toast.success("Atualização registrada no histórico da proposta!", "Follow-up Registrado");
    } catch (err: any) {
      toast.error(formatApiError(err, "Falha ao registrar atualização."));
    }
  };

  const handleApproveProposal = () => {
    setProposalForm(prev => ({ ...prev, status: 'APPROVED' }));
    toast.success("Proposta aprovada com sucesso na governança comercial!", "Proposta Aprovada");
  };

  const handleRejectProposal = () => {
    setProposalForm(prev => ({ ...prev, status: 'REJECTED' }));
    toast.warning("Proposta rejeitada / devolvida para revisão comercial.", "Revisão Solicitada");
  };

  const handleConvertAndWinFromStudio = async () => {
    const targetOppId = selectedOppForQuote?.id || selectedOpp?.id;
    if (!targetOppId) {
      toast.warning("Salve a oportunidade antes de marcá-la como ganha.", "Negócio Não Salvo");
      return;
    }
    try {
      if (activeQuoteId) {
        const order = await crmService.convertQuoteToOrder(activeQuoteId);
        const orderNum = order.order_number || (order.id ? order.id.slice(0, 8) : 'S/N');
        toast.success(`Pedido de Venda #${orderNum} gerado com sucesso!`, "Pedido de Venda");
      }
      await crmService.updateOpportunityStage(targetOppId, 'WON');
      setOpportunities(prev => prev.map(o => o.id === targetOppId ? { ...o, stage: 'WON' } : o));
      if (selectedOpp?.id === targetOppId) {
        setSelectedOpp(prev => prev ? { ...prev, stage: 'WON' } : null);
      }
      setProposalForm(prev => ({ ...prev, status: 'APPROVED', pipeline_stage: 'WON' }));
      toast.success(`🏆 Parabéns! Oportunidade marcada como Ganha no Pipeline!`, "Negócio Ganho");
      setIsQuoteModalOpen(false);
      void loadCRMData();
    } catch (err: any) {
      toast.error(formatApiError(err, "Falha ao marcar oportunidade como ganha."));
    }
  };

  // ===========================================================================
  // CONVERSÃO DE COTAÇÃO EM PEDIDO DE VENDA & EXPORTAÇÃO CSV (FASE 3)
  // ===========================================================================



  const handleExportCSV = () => {
    if (opportunities.length === 0) {
      toast.info("Não há oportunidades cadastradas para exportar.");
      return;
    }
    const headers = ['ID', 'Título', 'Cliente', 'Valor Estimado (R$)', 'Probabilidade (%)', 'Estágio', 'Data Previsão', 'Motivo de Perda', 'Criado Em'];
    const rows = opportunities.map(opp => [
      opp.id,
      `"${(opp.title || '').replace(/"/g, '""')}"`,
      `"${(opp.customer_name || '').replace(/"/g, '""')}"`,
      (Number(opp.estimated_amount) || 0).toFixed(2),
      opp.probability_percent || 0,
      opp.stage,
      opp.expected_closing_date || '',
      `"${(opp.loss_reason || '').replace(/"/g, '""')}"`,
      opp.created_at || ''
    ]);

    const csvContent = 'data:text/csv;charset=utf-8,\uFEFF' + [headers.join(','), ...rows.map(e => e.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `oportunidades_crm_controlb_${new Date().toISOString().split('T')[0]}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    toast.success("Relatório de oportunidades exportado em CSV com sucesso!", "Exportação Concluída");
  };

  // ===========================================================================
  // METAS COMERCIAIS & DETECÇÃO DE INATIVIDADE (FASE 4)
  // ===========================================================================

  const handleSaveGoal = (e: React.FormEvent) => {
    e.preventDefault();
    const val = Number(tempGoalInput);
    if (isNaN(val) || val <= 0) {
      toast.error("Informe um valor de meta válido superior a R$ 0,00.");
      return;
    }
    setMonthlySalesGoal(val);
    localStorage.setItem('controlb_crm_monthly_goal', val.toString());
    setIsGoalModalOpen(false);
    toast.success(`Meta comercial mensal definida para ${fmtCurrency(val)}!`, "Meta Atualizada");
  };

  const getOppInactivityInfo = (opp: Opportunity) => {
    const todayStr = new Date().toISOString().split('T')[0];
    const now = Date.now();
    const oppActs = allInteractions.filter(a => a.opportunity_id === opp.id);
    let lastDateMs = opp.created_at ? new Date(opp.created_at).getTime() : now;
    if (oppActs.length > 0) {
      const maxActDate = Math.max(...oppActs.map(a => new Date(a.interaction_date || a.created_at || '').getTime()));
      if (!isNaN(maxActDate)) lastDateMs = Math.max(lastDateMs, maxActDate);
    }
    const daysInactive = Math.max(0, Math.round((now - lastDateMs) / (1000 * 60 * 60 * 24)));
    const isOverdueClosing = !!(opp.expected_closing_date && opp.expected_closing_date < todayStr);
    const isStagnant = (opp.stage !== 'WON' && opp.stage !== 'LOST') && (daysInactive >= 7 || isOverdueClosing);
    return { daysInactive, isOverdueClosing, isStagnant };
  };

  const handleScheduleUrgentFollowUp = (opp: Opportunity) => {
    setGlobalActivityForm({
      type: 'CALL',
      linked_type: 'OPPORTUNITY',
      linked_id: opp.id,
      summary: `🚨 Follow-up Emergencial: ${opp.title}`,
      details: `Contato prioritário devido à estagnação de negociação no CRM. Retomar contato comercial com ${opp.customer_name}.`,
      date: new Date().toISOString().split('T')[0],
      time: '10:00'
    });
    setIsGlobalActivityModalOpen(true);
  };

  const selectedOppCustomerLTV = useMemo(() => {
    const custId = selectedOpp?.customer_id || proposalForm.customer_id;
    const custName = selectedOpp?.customer_name || proposalForm.customer_name;
    if (!custId && !custName) return { totalLTV: 0, wonCount: 0, openCount: 0, lostCount: 0, customerOpps: [] };
    const custOpps = opportunities.filter(o =>
      (custId && o.customer_id === custId) ||
      (custName && o.customer_name && o.customer_name.toLowerCase() === custName.toLowerCase())
    );
    const won = custOpps.filter(o => o.stage === 'WON');
    const open = custOpps.filter(o => o.stage !== 'WON' && o.stage !== 'LOST');
    const lost = custOpps.filter(o => o.stage === 'LOST');
    const totalLTV = won.reduce((acc, o) => acc + (Number(o.estimated_amount) || 0), 0);
    return {
      totalLTV,
      wonCount: won.length,
      openCount: open.length,
      lostCount: lost.length,
      customerOpps: custOpps
    };
  }, [selectedOpp, proposalForm.customer_id, proposalForm.customer_name, opportunities]);

  // ===========================================================================
  // CÁLCULOS MEMOIZADOS (DASHBOARD, RELATÓRIOS & FILTROS)
  // ===========================================================================

  const reportAnalytics = useMemo(() => {
    const wonStages = new Set(stages.filter(s => s.is_won || s.code === 'WON').map(s => s.code));
    const lostStages = new Set(stages.filter(s => s.is_lost || s.code === 'LOST').map(s => s.code));

    const wonList = opportunities.filter(o => wonStages.has(o.stage));
    const lostList = opportunities.filter(o => lostStages.has(o.stage));
    const openList = opportunities.filter(o => !wonStages.has(o.stage) && !lostStages.has(o.stage));

    const totalWon = wonList.reduce((acc, o) => acc + (Number(o.estimated_amount) || 0), 0);
    const totalLost = lostList.reduce((acc, o) => acc + (Number(o.estimated_amount) || 0), 0);
    const totalOpen = openList.reduce((acc, o) => acc + (Number(o.estimated_amount) || 0), 0);

    // Previsão de Receita Ponderada (Sales Forecast)
    const weightedOpenPipeline = openList.reduce((acc, o) => {
      const prob = (o.probability_percent !== undefined ? o.probability_percent : 50) / 100;
      return acc + ((Number(o.estimated_amount) || 0) * prob);
    }, 0);

    const avgTicket = wonList.length > 0 ? totalWon / wonList.length : 0;
    const closedCount = wonList.length + lostList.length;
    const globalWinRate = closedCount > 0 ? Math.round((wonList.length / closedCount) * 100) : 0;

    // Cálculo do Ciclo Médio (Dias) para negócios fechados
    let totalCycleDays = 0;
    let cycleCount = 0;
    [...wonList, ...lostList].forEach(o => {
      if (o.created_at) {
        const created = new Date(o.created_at).getTime();
        const closed = o.updated_at ? new Date(o.updated_at).getTime() : Date.now();
        const diffDays = Math.max(1, Math.round((closed - created) / (1000 * 60 * 60 * 24)));
        totalCycleDays += diffDays;
        cycleCount++;
      }
    });
    const avgCycleDays = cycleCount > 0 ? Math.round(totalCycleDays / cycleCount) : 0;

    // Distribuição de Motivos de Perda
    const lossCounts: Record<string, number> = {};
    lostList.forEach(o => {
      const reason = o.loss_reason || 'Outro motivo';
      lossCounts[reason] = (lossCounts[reason] || 0) + 1;
    });
    const lossReasonsArray = Object.entries(lossCounts).map(([reason, count]) => ({
      reason,
      count,
      percent: lostList.length > 0 ? Math.round((count / lostList.length) * 100) : 0
    })).sort((a, b) => b.count - a.count);

    // Performance por Canal de Lead
    const sourceCounts: Record<string, { total: number; converted: number }> = {};
    leads.forEach(l => {
      const src = l.source || 'Indicação';
      if (!sourceCounts[src]) sourceCounts[src] = { total: 0, converted: 0 };
      sourceCounts[src].total += 1;
      if (l.status === 'CONVERTED' || l.status === 'QUALIFIED') {
        sourceCounts[src].converted += 1;
      }
    });
    const sourceEfficiencyArray = Object.entries(sourceCounts).map(([source, data]) => ({
      source,
      total: data.total,
      converted: data.converted,
      rate: data.total > 0 ? Math.round((data.converted / data.total) * 100) : 0
    })).sort((a, b) => b.total - a.total);

    return {
      wonList,
      lostList,
      openList,
      totalWon,
      totalLost,
      totalOpen,
      weightedOpenPipeline,
      avgTicket,
      globalWinRate,
      avgCycleDays,
      lossReasonsArray,
      sourceEfficiencyArray
    };
  }, [opportunities, stages, leads]);

  const kpis = useMemo(() => {
    const totalOpps = opportunities.length;
    const totalPipelineAmount = opportunities
      .filter(o => o.stage !== 'LOST')
      .reduce((acc, o) => acc + (Number(o.estimated_amount) || 0), 0);

    // Pipeline Ponderado (Forecast Realista)
    const weightedPipelineAmount = opportunities
      .filter(o => o.stage !== 'LOST' && o.stage !== 'WON')
      .reduce((acc, o) => {
        const prob = (o.probability_percent !== undefined ? o.probability_percent : 50) / 100;
        return acc + ((Number(o.estimated_amount) || 0) * prob);
      }, 0);

    const wonOpps = opportunities.filter(o => o.stage === 'WON');
    const wonAmount = wonOpps.reduce((acc, o) => acc + (Number(o.estimated_amount) || 0), 0);
    const conversionRate = totalOpps > 0 ? ((wonOpps.length / totalOpps) * 100).toFixed(1) : '0.0';

    // Acompanhamento de Meta Comercial
    const goalPercent = monthlySalesGoal > 0 ? Math.min(200, Math.round((wonAmount / monthlySalesGoal) * 100)) : 0;
    const goalRemaining = Math.max(0, monthlySalesGoal - wonAmount);

    // Contagem de Oportunidades Estagnadas
    const stagnantCount = opportunities.filter(o => getOppInactivityInfo(o).isStagnant).length;

    return {
      totalOpps,
      totalPipelineAmount,
      weightedPipelineAmount,
      wonOppsCount: wonOpps.length,
      wonAmount,
      conversionRate,
      totalLeads: leads.length,
      qualifiedLeads: leads.filter(l => l.status === 'QUALIFIED' || l.status === 'CONVERTED').length,
      monthlySalesGoal,
      goalPercent,
      goalRemaining,
      stagnantCount
    };
  }, [opportunities, leads, monthlySalesGoal, allInteractions]);

  const filteredOpportunities = useMemo(() => {
    return opportunities.filter(o => {
      const matchSearch = searchTerm.trim() === '' ||
        o.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
        o.customer_name.toLowerCase().includes(searchTerm.toLowerCase());
      const matchStage = stageFilter === 'ALL' || o.stage === stageFilter;

      if (oppActivityFilter === 'STAGNANT') {
        const inact = getOppInactivityInfo(o);
        if (!inact.isStagnant) return false;
      }

      return matchSearch && matchStage;
    });
  }, [opportunities, searchTerm, stageFilter, oppActivityFilter, allInteractions]);

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
                <span>Funil de Vendas</span>
                <span className="nav-badge">{opportunities.length}</span>
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
              <span className="nav-group-title">Inteligência & Relatórios</span>
              <button
                type="button"
                className={`nav-item ${activeTab === 'reports' ? 'active' : ''}`}
                onClick={() => setActiveTab('reports')}
              >
                <BarChart3 size={16} />
                <span>Relatórios & Inteligência</span>
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
                {activeTab === 'pipeline' && (oppViewMode === 'kanban' ? 'Funil de Vendas (Kanban)' : 'Lista de Oportunidades')}
                {activeTab === 'leads' && 'Base de Leads & Prospecção'}
                {activeTab === 'activities' && 'Central de Atividades & Follow-ups'}
                {activeTab === 'stages' && 'Configuração das Etapas do Funil de Vendas'}
                {activeTab === 'reports' && 'Inteligência Comercial & Relatórios'}
              </h1>
              <p className="subtitle">
                {activeTab === 'dashboard' && 'Visão panorâmica de negociações, taxas de conversão e metas comerciais'}
                {activeTab === 'pipeline' && (oppViewMode === 'kanban' ? 'Arraste os cards entre as colunas para atualizar a fase de cada negociação' : 'Listagem tabular com personalização de colunas, valores e follow-ups')}
                {activeTab === 'leads' && 'Qualifique potenciais clientes e converta contatos em negociações ativas'}
                {activeTab === 'activities' && 'Organize ligações, reuniões, conversas de WhatsApp e lembretes com prazos'}
                {activeTab === 'stages' && 'Personalize a sequência, nomes e cores das colunas do quadro Kanban'}
                {activeTab === 'reports' && 'Métricas de conversão, motivos de perda, tempo médio de fechamento e ticket médio'}
              </p>
            </div>

            <div className="header-actions">
              {activeTab === 'pipeline' && (
                <div className="view-mode-toggle-group">
                  <button
                    type="button"
                    className={`btn-view-toggle ${oppViewMode === 'kanban' ? 'active' : ''}`}
                    onClick={() => setOppViewMode('kanban')}
                    title="Visualização em Quadro Kanban"
                  >
                    <LayoutGrid size={15} />
                    <span>Kanban</span>
                  </button>
                  <button
                    type="button"
                    className={`btn-view-toggle ${oppViewMode === 'list' ? 'active' : ''}`}
                    onClick={() => setOppViewMode('list')}
                    title="Visualização em Lista Tabular"
                  >
                    <List size={15} />
                    <span>Lista</span>
                  </button>
                </div>
              )}

              <button
                type="button"
                className="btn-refresh"
                onClick={() => void loadCRMData(true)}
                title="Atualizar dados agora"
                disabled={loading}
              >
                <RefreshCw size={16} className={loading ? 'spinning' : ''} />
              </button>

              {activeTab === 'reports' && (
                <button
                  type="button"
                  className="btn-secondary ui-button ui-button--secondary"
                  onClick={handleExportCSV}
                  title="Baixar planilha consolidada de oportunidades"
                >
                  <Download size={16} />
                  <span>Exportar CSV</span>
                </button>
              )}

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

              {activeTab !== 'leads' && activeTab !== 'activities' && activeTab !== 'reports' && (
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
                    onClick={() => handleOpenNewOppStudio()}
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
                <span className="kpi-label">Pipeline Bruto</span>
                <DollarSign size={18} />
              </div>
              <span className="kpi-value">{fmtCurrency(kpis.totalPipelineAmount)}</span>
              <span className="kpi-sub">{kpis.totalOpps} oportunidades ativas</span>
            </div>

            <div className="kpi-card">
              <div className="kpi-top">
                <span className="kpi-label">Forecast Ponderado</span>
                <Zap size={18} style={{ color: 'var(--accent-brand)' }} />
              </div>
              <span className="kpi-value brand">{fmtCurrency(kpis.weightedPipelineAmount)}</span>
              <span className="kpi-sub">Previsão realista baseada em probabilidade</span>
            </div>

            <div className="kpi-card">
              <div className="kpi-top">
                <span className="kpi-label">Negócios Ganhos</span>
                <CheckCircle2 size={18} style={{ color: '#10b981' }} />
              </div>
              <span className="kpi-value green">{fmtCurrency(kpis.wonAmount)}</span>
              <span className="kpi-sub">{kpis.wonOppsCount} negócios fechados</span>
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
                <span className="kpi-label">Negócios Estagnados</span>
                <AlertTriangle size={18} style={{ color: kpis.stagnantCount > 0 ? '#f59e0b' : 'var(--text-muted)' }} />
              </div>
              <span className={`kpi-value ${kpis.stagnantCount > 0 ? 'amber' : ''}`}>{kpis.stagnantCount}</span>
              <span className="kpi-sub">{kpis.stagnantCount > 0 ? 'Exigem follow-up emergencial' : 'Todos os negócios ativos'}</span>
            </div>
          </section>

          {/* ================================================================= */}
          {/* TAB 1: DASHBOARD                                                  */}
          {/* ================================================================= */}
          {activeTab === 'dashboard' && (
            <div className="dashboard-view">
              {/* CARD DE META COMERCIAL DO MÊS (FASE 4) */}
              <div className="sales-goal-card">
                <div className="goal-header">
                  <div className="goal-title-box">
                    <Target size={20} className="text-brand" />
                    <div>
                      <h3>Meta Comercial do Mês</h3>
                      <p>Acompanhamento de faturamento realizado vs. objetivo mensal da equipe</p>
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn-define-goal ui-button ui-button--secondary"
                    onClick={() => {
                      setTempGoalInput(monthlySalesGoal.toString());
                      setIsGoalModalOpen(true);
                    }}
                  >
                    <Edit3 size={13} />
                    <span>Definir Meta</span>
                  </button>
                </div>

                <div className="goal-progress-wrap">
                  <div className="goal-progress-bar">
                    <div
                      className={`goal-progress-fill ${kpis.goalPercent >= 100 ? 'completed' : ''}`}
                      style={{ width: `${Math.min(kpis.goalPercent, 100)}%` }}
                    />
                  </div>
                  <div className={`goal-percent-badge ${kpis.goalPercent >= 100 ? 'completed' : ''}`}>
                    {kpis.goalPercent}% Atingido
                  </div>
                </div>

                <div className="goal-numbers-grid">
                  <div className="goal-num-item">
                    <span className="label">Meta Estabelecida</span>
                    <strong className="val">{fmtCurrency(kpis.monthlySalesGoal)}</strong>
                  </div>
                  <div className="goal-num-item">
                    <span className="label">Realizado (Ganhos)</span>
                    <strong className="val green">{fmtCurrency(kpis.wonAmount)}</strong>
                  </div>
                  <div className="goal-num-item">
                    <span className="label">Faltante p/ Meta</span>
                    <strong className="val">{fmtCurrency(kpis.goalRemaining)}</strong>
                  </div>
                  <div className="goal-num-item">
                    <span className="label">Forecast Ponderado</span>
                    <strong className="val brand">{fmtCurrency(kpis.weightedPipelineAmount)}</strong>
                  </div>
                </div>
              </div>

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
                        const inact = getOppInactivityInfo(opp);
                        return (
                          <div
                            key={opp.id}
                            className="dash-opp-item"
                            onClick={() => void loadOpportunityDetails(opp)}
                          >
                            <div className="opp-info">
                              <div className="title-with-badge">
                                <h4>{opp.title}</h4>
                                {inact.isStagnant && (
                                  <span className="mini-stagnant-tag" title={`${inact.daysInactive}d sem contato`}>
                                    <AlertTriangle size={11} /> Estagnado
                                  </span>
                                )}
                              </div>
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
          {/* TAB 2: PIPELINE COMERCIAL (KANBAN & LISTA TABULAR UNIFICADOS)     */}
          {/* ================================================================= */}
          {activeTab === 'pipeline' && (
            <>
              {oppViewMode === 'kanban' ? (
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
                                onClick={() => handleOpenNewOppStudio(null, stage.code)}
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
                                const inact = getOppInactivityInfo(opp);
                                return (
                                  <div
                                    key={opp.id}
                                    className={`kanban-card ${isDragging ? 'is-dragging' : ''} ${inact.isStagnant ? 'is-stagnant' : ''}`}
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

                                    {inact.isStagnant && (
                                      <div className="opp-stagnant-alert">
                                        <div className="stagnant-pill">
                                          <AlertTriangle size={11} />
                                          <span>{inact.daysInactive > 0 ? `${inact.daysInactive}d sem contato` : 'Previsão vencida'}</span>
                                        </div>
                                        <button
                                          type="button"
                                          className="btn-urgent-followup"
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            handleScheduleUrgentFollowUp(opp);
                                          }}
                                          title="Agendar follow-up prioritário agora"
                                        >
                                          <Clock size={11} />
                                          <span>Follow-up</span>
                                        </button>
                                      </div>
                                    )}

                                    <div className="card-footer-actions" onClick={(e) => e.stopPropagation()}>
                                      <button
                                        type="button"
                                        className="btn-card-action"
                                        onClick={() => void loadOpportunityDetails(opp)}
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
              ) : (
                <div className="table-card">
                  <div className="table-toolbar flex-between">
                    <div className="toolbar-left-filters" style={{ display: 'flex', gap: '0.65rem', alignItems: 'center', flexWrap: 'wrap' }}>
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
                          value={oppActivityFilter}
                          onChange={(e) => setOppActivityFilter(e.target.value as 'ALL' | 'STAGNANT')}
                          className="select-activity-filter"
                        >
                          <option value="ALL">Todas as Atividades ({opportunities.length})</option>
                          <option value="STAGNANT">🚨 Estagnadas / Sem Contato ({kpis.stagnantCount})</option>
                        </select>
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

                    {/* Dropdown de Personalização de Colunas com Flags */}
                    <div className="column-customizer-wrapper" style={{ position: 'relative' }}>
                      <button
                        type="button"
                        className="btn-custom-columns ui-button ui-button--secondary"
                        onClick={() => setIsColumnSelectorOpen(!isColumnSelectorOpen)}
                        title="Personalizar colunas visíveis da tabela"
                      >
                        <SlidersHorizontal size={14} />
                        <span>Personalizar Colunas</span>
                      </button>

                      {isColumnSelectorOpen && (
                        <div className="column-customizer-popover">
                          <div className="customizer-title">
                            <span>Exibir Colunas</span>
                            <button
                              type="button"
                              className="btn-close-popover"
                              onClick={() => setIsColumnSelectorOpen(false)}
                              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
                            >
                              <X size={14} />
                            </button>
                          </div>
                          <div className="customizer-items">
                            {[
                              { key: 'title', label: 'Título do Negócio' },
                              { key: 'customer', label: 'Cliente / Empresa' },
                              { key: 'estimated_amount', label: 'Valor Estimado' },
                              { key: 'probability_percent', label: 'Probabilidade' },
                              { key: 'stage', label: 'Estágio Atual' },
                              { key: 'activity_status', label: 'Status de Atividade' },
                              { key: 'expected_closing_date', label: 'Previsão de Fechamento' },
                              { key: 'responsible_name', label: 'Vendedor Responsável' },
                              { key: 'sales_team', label: 'Equipe Comercial' },
                              { key: 'actions', label: 'Ações' }
                            ].map(col => (
                              <label key={col.key} className="customizer-item">
                                <input
                                  type="checkbox"
                                  checked={!!visibleColumns[col.key]}
                                  onChange={() => toggleColumnVisibility(col.key)}
                                />
                                <span>{col.label}</span>
                              </label>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="table-responsive">
                    <table className="data-table">
                      <thead>
                        <tr>
                          {visibleColumns.title && <th>Título do Negócio</th>}
                          {visibleColumns.customer && <th>Cliente / Empresa</th>}
                          {visibleColumns.estimated_amount && <th>Valor Estimado</th>}
                          {visibleColumns.probability_percent && <th>Probabilidade</th>}
                          {visibleColumns.stage && <th>Estágio Atual</th>}
                          {visibleColumns.activity_status && <th>Status de Atividade</th>}
                          {visibleColumns.expected_closing_date && <th>Previsão Fechamento</th>}
                          {visibleColumns.responsible_name && <th>Vendedor</th>}
                          {visibleColumns.sales_team && <th>Equipe</th>}
                          {visibleColumns.actions && <th style={{ textAlign: 'center' }}>Ações</th>}
                        </tr>
                      </thead>
                      <tbody>
                        {filteredOpportunities.length === 0 ? (
                          <tr>
                            <td colSpan={10} className="empty-row">Nenhuma oportunidade encontrada com os filtros selecionados.</td>
                          </tr>
                        ) : (
                          filteredOpportunities.map(opp => {
                            const stg = stages.find(s => s.code === opp.stage);
                            const inact = getOppInactivityInfo(opp);
                            const matchedSeller = sellersList.find(s => s.id === opp.assigned_to_id);
                            return (
                              <tr key={opp.id} onClick={() => void loadOpportunityDetails(opp)} style={{ cursor: 'pointer' }}>
                                {visibleColumns.title && <td><strong>{opp.title}</strong></td>}
                                {visibleColumns.customer && <td>{opp.customer_name}</td>}
                                {visibleColumns.estimated_amount && (
                                  <td><span className="opp-val-highlight">{fmtCurrency(opp.estimated_amount)}</span></td>
                                )}
                                {visibleColumns.probability_percent && <td>{opp.probability_percent}%</td>}
                                {visibleColumns.stage && (
                                  <td>
                                    <span className="stage-pill" style={{ backgroundColor: stg?.color ? `${stg.color}22` : 'var(--accent-brand-subtle)', color: stg?.color || 'var(--accent-brand)' }}>
                                      {stg?.name || opp.stage}
                                    </span>
                                  </td>
                                )}
                                {visibleColumns.activity_status && (
                                  <td>
                                    {inact.isStagnant ? (
                                      <div className="stagnant-table-pill" title={`${inact.daysInactive} dias sem nova atividade registrada`}>
                                        <AlertTriangle size={12} />
                                        <span>Estagnado ({inact.daysInactive}d)</span>
                                      </div>
                                    ) : (
                                      <div className="active-table-pill">
                                        <Check size={12} />
                                        <span>Ativo</span>
                                      </div>
                                    )}
                                  </td>
                                )}
                                {visibleColumns.expected_closing_date && <td>{fmtDate(opp.expected_closing_date)}</td>}
                                {visibleColumns.responsible_name && (
                                  <td>
                                    <span className="seller-name-cell">
                                      {matchedSeller ? matchedSeller.full_name : ((opp as any).assigned_to?.full_name || '-')}
                                    </span>
                                  </td>
                                )}
                                {visibleColumns.sales_team && (
                                  <td>
                                    <span className="team-badge-cell">
                                      {matchedSeller?.sales_team_name || '-'}
                                    </span>
                                  </td>
                                )}
                                {visibleColumns.actions && (
                                  <td style={{ textAlign: 'center' }} onClick={(e) => e.stopPropagation()}>
                                    {inact.isStagnant && (
                                      <button
                                        className="btn-icon-action urgent"
                                        onClick={() => handleScheduleUrgentFollowUp(opp)}
                                        title="Agendar Follow-up Emergencial"
                                      >
                                        <Clock size={15} />
                                      </button>
                                    )}
                                    <button
                                      className="btn-icon-action"
                                      onClick={() => void loadOpportunityDetails(opp)}
                                      title="Ver Detalhes e Proposta"
                                    >
                                      <Eye size={15} />
                                    </button>
                                  </td>
                                )}
                              </tr>
                            );
                          })
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
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

          {/* ================================================================= */}
          {/* TAB 6: RELATÓRIOS & INTELIGÊNCIA COMERCIAL (FASE 3)               */}
          {/* ================================================================= */}
          {activeTab === 'reports' && (
            <div className="reports-view">
              {/* Grid de KPIs Executivos */}
              <section className="reports-kpi-grid">
                <div className="rep-kpi-card">
                  <div className="rep-kpi-header">
                    <span className="rep-kpi-title">Ticket Médio</span>
                    <DollarSign size={18} className="rep-kpi-icon brand" />
                  </div>
                  <span className="rep-kpi-value">{fmtCurrency(reportAnalytics.avgTicket)}</span>
                  <span className="rep-kpi-sub">Por negócio ganho e fechado</span>
                </div>

                <div className="rep-kpi-card">
                  <div className="rep-kpi-header">
                    <span className="rep-kpi-title">Ciclo Médio de Fechamento</span>
                    <Clock size={18} className="rep-kpi-icon blue" />
                  </div>
                  <span className="rep-kpi-value">{reportAnalytics.avgCycleDays} <small>dias</small></span>
                  <span className="rep-kpi-sub">Tempo médio de maturação comercial</span>
                </div>

                <div className="rep-kpi-card">
                  <div className="rep-kpi-header">
                    <span className="rep-kpi-title">Taxa Global de Fechamento</span>
                    <TrendingUp size={18} className="rep-kpi-icon green" />
                  </div>
                  <span className="rep-kpi-value">{reportAnalytics.globalWinRate}%</span>
                  <span className="rep-kpi-sub">{reportAnalytics.wonList.length} ganhos / {reportAnalytics.wonList.length + reportAnalytics.lostList.length} finalizados</span>
                </div>

                <div className="rep-kpi-card">
                  <div className="rep-kpi-header">
                    <span className="rep-kpi-title">Faturamento Ganho</span>
                    <CheckCircle2 size={18} className="rep-kpi-icon green" />
                  </div>
                  <span className="rep-kpi-value green">{fmtCurrency(reportAnalytics.totalWon)}</span>
                  <span className="rep-kpi-sub">{reportAnalytics.wonList.length} negócios convertidos</span>
                </div>

                <div className="rep-kpi-card">
                  <div className="rep-kpi-header">
                    <span className="rep-kpi-title">Volume Perdido</span>
                    <TrendingDown size={18} className="rep-kpi-icon red" />
                  </div>
                  <span className="rep-kpi-value red">{fmtCurrency(reportAnalytics.totalLost)}</span>
                  <span className="rep-kpi-sub">{reportAnalytics.lostList.length} oportunidades descartadas</span>
                </div>
              </section>

              {/* Grid Analítico: Motivos de Perda & Funil de Conversão */}
              <div className="reports-analytics-grid">
                {/* CARD 1: MOTIVOS DE PERDA */}
                <div className="analytics-card">
                  <div className="card-header-bar">
                    <div className="title-wrapper">
                      <TrendingDown size={18} className="text-danger" />
                      <h3>Diagnóstico de Motivos de Perda</h3>
                    </div>
                    <span className="count-tag">{reportAnalytics.lostList.length} perdas</span>
                  </div>
                  <p className="card-desc">Identifique os principais obstáculos apontados pelos clientes durante a negociação.</p>

                  {reportAnalytics.lossReasonsArray.length === 0 ? (
                    <div className="empty-analytics-box">
                      <CheckCircle2 size={28} />
                      <p>Nenhuma oportunidade perdida registrada no histórico comercial.</p>
                    </div>
                  ) : (
                    <div className="loss-reasons-list">
                      {reportAnalytics.lossReasonsArray.map((item, idx) => (
                        <div key={idx} className="loss-reason-item">
                          <div className="loss-item-header">
                            <span className="loss-name">{item.reason}</span>
                            <div className="loss-values">
                              <strong>{item.count} {item.count === 1 ? 'negócio' : 'negócios'}</strong>
                              <span className="loss-percent">({item.percent}%)</span>
                            </div>
                          </div>
                          <div className="progress-bar-wrap">
                            <div
                              className="progress-bar-fill red"
                              style={{ width: `${Math.max(item.percent, 4)}%` }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* CARD 2: FUNIL DE CONVERSÃO POR ETAPA */}
                <div className="analytics-card">
                  <div className="card-header-bar">
                    <div className="title-wrapper">
                      <BarChart3 size={18} className="text-brand" />
                      <h3>Volume do Funil por Estágio</h3>
                    </div>
                    <span className="count-tag">{opportunities.length} oportunidades</span>
                  </div>
                  <p className="card-desc">Distribuição de oportunidades e volume financeiro em cada fase do funil.</p>

                  <div className="stage-funnel-list">
                    {stages.map((stg) => {
                      const stageOpps = opportunities.filter(o => o.stage === stg.code);
                      const stageTotal = stageOpps.reduce((acc, o) => acc + (Number(o.estimated_amount) || 0), 0);
                      const totalPipeline = kpis.totalPipelineAmount || 1;
                      const percentOfPipeline = Math.min(100, Math.round((stageTotal / totalPipeline) * 100));

                      return (
                        <div key={stg.id || stg.code} className="stage-funnel-item">
                          <div className="stage-item-header">
                            <div className="stage-name-box">
                              <span className="stage-dot" style={{ backgroundColor: stg.color || '#10b981' }} />
                              <span className="stage-label">{stg.name}</span>
                            </div>
                            <div className="stage-meta-box">
                              <span className="stage-count">{stageOpps.length} {stageOpps.length === 1 ? 'negócio' : 'negócios'}</span>
                              <strong className="stage-amount">{fmtCurrency(stageTotal)}</strong>
                            </div>
                          </div>
                          <div className="progress-bar-wrap">
                            <div
                              className="progress-bar-fill"
                              style={{
                                width: `${Math.max(percentOfPipeline, stageOpps.length > 0 ? 6 : 0)}%`,
                                backgroundColor: stg.color || 'var(--accent-brand)'
                              }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* Grid Analítico Inferior: Eficiência de Canais & Fechamentos Recentes */}
              <div className="reports-analytics-grid bottom">
                {/* CARD 3: EFICIÊNCIA DE CANAIS DE LEADS */}
                <div className="analytics-card">
                  <div className="card-header-bar">
                    <div className="title-wrapper">
                      <Users size={18} className="text-blue" />
                      <h3>Eficiência por Canal de Prospecção</h3>
                    </div>
                    <span className="count-tag">{leads.length} leads</span>
                  </div>
                  <p className="card-desc">Avalie quais canais de atração geram contatos mais qualificados para o time.</p>

                  <div className="source-efficiency-table-wrap">
                    <table className="source-efficiency-table">
                      <thead>
                        <tr>
                          <th>Canal de Origem</th>
                          <th style={{ width: '80px', textAlign: 'center' }}>Total</th>
                          <th style={{ width: '100px', textAlign: 'center' }}>Qualificados</th>
                          <th style={{ width: '130px', textAlign: 'right' }}>Conversão</th>
                        </tr>
                      </thead>
                      <tbody>
                        {reportAnalytics.sourceEfficiencyArray.map((src, idx) => (
                          <tr key={idx}>
                            <td>
                              <strong className="source-name">{src.source}</strong>
                            </td>
                            <td style={{ textAlign: 'center' }}>{src.total}</td>
                            <td style={{ textAlign: 'center' }}>
                              <span className="qualified-tag">{src.converted}</span>
                            </td>
                            <td style={{ textAlign: 'right' }}>
                              <div className="source-rate-cell">
                                <span className="rate-text">{src.rate}%</span>
                                <div className="mini-progress-bar">
                                  <div
                                    className="mini-fill"
                                    style={{ width: `${src.rate}%` }}
                                  />
                                </div>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* CARD 4: ÚLTIMAS NEGOCIAÇÕES FINALIZADAS */}
                <div className="analytics-card">
                  <div className="card-header-bar">
                    <div className="title-wrapper">
                      <Award size={18} className="text-purple" />
                      <h3>Últimos Fechamentos Registrados</h3>
                    </div>
                    <span className="count-tag">{reportAnalytics.wonList.length + reportAnalytics.lostList.length} finalizados</span>
                  </div>
                  <p className="card-desc">Registro histórico dos negócios mais recentes que atingiram conclusão.</p>

                  {[...reportAnalytics.wonList, ...reportAnalytics.lostList].length === 0 ? (
                    <div className="empty-analytics-box">
                      <Clock size={28} />
                      <p>Nenhuma oportunidade foi concluída ainda.</p>
                    </div>
                  ) : (
                    <div className="closed-opps-list">
                      {[...reportAnalytics.wonList, ...reportAnalytics.lostList]
                        .sort((a, b) => new Date(b.updated_at || b.created_at).getTime() - new Date(a.updated_at || a.created_at).getTime())
                        .slice(0, 5)
                        .map(opp => {
                          const isWon = opp.stage === 'WON' || stages.find(s => s.code === opp.stage)?.is_won;
                          return (
                            <div key={opp.id} className="closed-opp-item">
                              <div className="closed-opp-info">
                                <strong>{opp.title}</strong>
                                <span>{opp.customer_name} • {fmtDate(opp.updated_at || opp.created_at)}</span>
                              </div>
                              <div className="closed-opp-meta">
                                <span className="closed-amount">{fmtCurrency(opp.estimated_amount)}</span>
                                <span className={`status-badge-pill ${isWon ? 'won' : 'lost'}`}>
                                  {isWon ? 'GANHO' : 'PERDIDO'}
                                </span>
                              </div>
                            </div>
                          );
                        })}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </main>
      </div>



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
      {/* OPPORTUNITY STUDIO — WORKSPACE 360º DA OPORTUNIDADE COMERCIAL       */}
      {/* =================================================================== */}
      {isQuoteModalOpen && (
        <div className="proposal-studio-overlay">
          <div className="proposal-studio-modal">
            
            {/* 1. Header Banner & Top Bar */}
            <div className="opp-studio-header">
              <div className="header-left">
                <div className="breadcrumb-row">
                  <span className="breadcrumb-root">
                    <Briefcase size={13} />
                    <span>CRM & Pipeline</span>
                  </span>
                  <span className="breadcrumb-separator">/</span>
                  <span className="code-badge">{proposalForm.quote_number}</span>
                </div>
                <div className="title-row">
                  <h2 className="studio-main-title">
                    {proposalForm.title || 'Nova Oportunidade Comercial'}
                  </h2>
                  {proposalForm.customer_name && (
                    <span className="customer-subtitle">
                      <Building2 size={13} />
                      <span>{proposalForm.customer_name}</span>
                    </span>
                  )}
                </div>
              </div>

              <div className="header-actions">
                <button
                  type="button"
                  className="btn-action-primary"
                  onClick={handleSaveProposal}
                  disabled={isSavingQuote}
                >
                  <CheckCheck size={16} />
                  <span>{isSavingQuote ? 'Salvando...' : 'Salvar Negócio'}</span>
                </button>

                <button
                  type="button"
                  className="btn-action-win"
                  onClick={handleConvertAndWinFromStudio}
                  title="Marcar como Ganha e Gerar Pedido de Venda"
                >
                  <Award size={16} />
                  <span>Marcar como ganho</span>
                </button>

                <div className="actions-utility-group">
                  <button
                    type="button"
                    className="btn-action-icon"
                    onClick={handleSendProposalWhatsApp}
                    title="Enviar resumo via WhatsApp"
                  >
                    <MessageSquare size={14} />
                    <span>WhatsApp</span>
                  </button>
                  <button
                    type="button"
                    className="btn-action-icon"
                    onClick={handleSendProposalEmail}
                    title="Enviar via E-mail"
                  >
                    <Mail size={14} />
                    <span>E-mail</span>
                  </button>
                  <button
                    type="button"
                    className="btn-action-icon"
                    onClick={handlePrintProposal}
                    title="Gerar PDF / Imprimir"
                  >
                    <Printer size={14} />
                    <span>PDF</span>
                  </button>
                  <button
                    type="button"
                    className="btn-action-icon icon-only"
                    onClick={handleDuplicateProposal}
                    title="Duplicar Oportunidade"
                  >
                    <Copy size={14} />
                  </button>
                  {selectedOpp && (
                    <button
                      type="button"
                      className="btn-action-icon"
                      onClick={() => void openDocumentTimeline('OPPORTUNITY', selectedOpp.id, selectedOpp.title)}
                      title="Ver cadeia documental completa da oportunidade até a entrega"
                    >
                      <GitBranch size={14} />
                      <span>Rastrear</span>
                    </button>
                  )}
                </div>

                <button
                  type="button"
                  className="btn-close-modal"
                  onClick={() => {
                    setIsQuoteModalOpen(false);
                    setSelectedOpp(null);
                  }}
                  title="Fechar Workspace"
                >
                  <X size={18} />
                </button>
              </div>
            </div>

            {/* 2. Key Metrics Bar (Essential Decision Indicators) */}
            <div className="opp-stat-strip">
              <div className="stat-card stat-amount">
                <span className="stat-label">Valor Estimado</span>
                <div className="stat-main-row">
                  <strong className="stat-val">{fmtCurrency(proposalFinalTotal)}</strong>
                  <span className="stat-sub-tag">{quoteItems.length} {quoteItems.length === 1 ? 'item' : 'itens'}</span>
                </div>
              </div>

              <div className="stat-card stat-stage">
                <span className="stat-label">Etapa no Funil</span>
                <div className="stat-select-wrap">
                  <select
                    value={proposalForm.pipeline_stage}
                    onChange={(e) => setProposalForm({ ...proposalForm, pipeline_stage: e.target.value })}
                    className="pipeline-stage-select"
                  >
                    {stages.map(st => (
                      <option key={st.id || st.code} value={st.code}>{st.name}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="stat-card stat-forecast">
                <span className="stat-label">Probabilidade & Forecast</span>
                <div className="stat-main-row">
                  <span className="forecast-prob-badge">{proposalForm.probability_percent}%</span>
                  <span className="forecast-amount-text">
                    {fmtCurrency((proposalFinalTotal * (proposalForm.probability_percent || 0)) / 100)} ponderado
                  </span>
                </div>
              </div>

              <div className="stat-card stat-closing">
                <span className="stat-label">Previsão Fechamento</span>
                <div className="stat-date-row">
                  <CalendarDays size={14} className="date-icon" />
                  <span className="date-text">{fmtDate(proposalForm.expected_closing_date)}</span>
                </div>
              </div>

              <div className="stat-card stat-owner">
                <span className="stat-label">Responsável</span>
                <div className="owner-profile-row">
                  <div className="avatar-circle">
                    {proposalForm.responsible_name.split(' ').map(n => n[0]).slice(0, 2).join('').toUpperCase()}
                  </div>
                  <div className="owner-meta">
                    <span className="owner-name">{proposalForm.responsible_name}</span>
                    <span className="owner-team">{proposalForm.sales_team}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* 3. Main 2-Column Workspace */}
            <div className="proposal-workspace-grid">
              
              {/* Left Column (70%) - Tabs & Enrichment Forms */}
              <div className="proposal-main-pane">
                
                {/* Modern Pill Tabs */}
                <div className="opp-nav-tabs">
                  <button
                    type="button"
                    className={`nav-tab-item ${proposalActiveTab === 'general' ? 'active' : ''}`}
                    onClick={() => setProposalActiveTab('general')}
                  >
                    <FileText size={15} />
                    <span>Dados Gerais</span>
                  </button>
                  <button
                    type="button"
                    className={`nav-tab-item ${proposalActiveTab === 'customer' ? 'active' : ''}`}
                    onClick={() => setProposalActiveTab('customer')}
                  >
                    <Building2 size={15} />
                    <span>Cliente & LTV 360º</span>
                  </button>
                  <button
                    type="button"
                    className={`nav-tab-item ${proposalActiveTab === 'quotes' ? 'active' : ''}`}
                    onClick={() => setProposalActiveTab('quotes')}
                  >
                    <FileCheck size={15} />
                    <span>Cotações & Propostas</span>
                    <span className="tab-count-badge">{oppQuotations.length}</span>
                  </button>
                  <button
                    type="button"
                    className={`nav-tab-item ${proposalActiveTab === 'items' ? 'active' : ''}`}
                    onClick={() => setProposalActiveTab('items')}
                  >
                    <Package size={15} />
                    <span>Itens & Serviços</span>
                    <span className="tab-count-badge">{quoteItems.length}</span>
                  </button>
                  <button
                    type="button"
                    className={`nav-tab-item ${proposalActiveTab === 'terms' ? 'active' : ''}`}
                    onClick={() => setProposalActiveTab('terms')}
                  >
                    <CreditCard size={15} />
                    <span>Condições Comerciais</span>
                  </button>
                  <button
                    type="button"
                    className={`nav-tab-item ${proposalActiveTab === 'approvals' ? 'active' : ''}`}
                    onClick={() => setProposalActiveTab('approvals')}
                  >
                    <ShieldCheck size={15} />
                    <span>Aprovações</span>
                  </button>
                </div>

                {/* Tab 1: Dados Gerais */}
                {proposalActiveTab === 'general' && (
                  <div className="opp-tab-content">
                    
                    {/* Card 1: Identificação & Cliente */}
                    <div className="form-section-card">
                      <div className="card-header">
                        <Building2 size={16} className="card-header-icon" />
                        <div>
                          <h4>Identificação do Negócio & Cliente</h4>
                          <p>Defina o título da oportunidade e selecione a conta do cliente</p>
                        </div>
                      </div>

                      <div className="card-body">
                        <div className="form-grid-2">
                          <div className="form-group span-2">
                            <label>Título da Oportunidade / Negócio *</label>
                            <div className="input-with-icon-box">
                              <Briefcase size={16} className="input-prefix-icon" />
                              <input
                                type="text"
                                className="ui-input lg-input has-prefix-icon"
                                value={proposalForm.title}
                                onChange={(e) => setProposalForm({ ...proposalForm, title: e.target.value })}
                                placeholder="Ex: Implantação de CFTV e Rede Estruturada - Unidade Sul"
                                required
                              />
                            </div>
                          </div>

                          <div className="form-group span-2">
                            <CustomerPicker
                              value={proposalForm.customer_id}
                              onChange={(customer: Customer | null) => {
                                if (customer) {
                                  setProposalForm(prev => ({
                                    ...prev,
                                    customer_id: customer.id,
                                    customer_name: customer.trade_name || customer.name,
                                    customer_document: customer.document || '',
                                    customer_email: customer.email || '',
                                    customer_phone: customer.phone || ''
                                  }));
                                } else {
                                  setProposalForm(prev => ({ ...prev, customer_id: '', customer_name: '' }));
                                }
                              }}
                              label="Empresa / Cliente Vinculado *"
                              placeholder="Selecione o cliente oficial ou clique para cadastrar..."
                            />
                          </div>

                          <div className="form-group">
                            <label>Contato Principal na Empresa</label>
                            <div className="input-with-icon-box">
                              <User size={15} className="input-prefix-icon" />
                              <input
                                type="text"
                                className="ui-input has-prefix-icon"
                                value={proposalForm.contact_person}
                                onChange={(e) => setProposalForm({ ...proposalForm, contact_person: e.target.value })}
                                placeholder="Ex: Carlos Mendes"
                              />
                            </div>
                          </div>

                          <div className="form-group">
                            <label>Origem do Negócio</label>
                            <div className="select-with-icon-box">
                              <Sparkles size={15} className="input-prefix-icon" />
                              <select
                                value={proposalForm.source}
                                onChange={(e) => setProposalForm({ ...proposalForm, source: e.target.value })}
                                className="ui-input custom-styled-select has-prefix-icon"
                              >
                                <option value="Indicação">Indicação</option>
                                <option value="Site / Formulário">Site / Formulário</option>
                                <option value="Contato Telefônico">Contato Telefônico</option>
                                <option value="Prospecção Ativa">Prospecção Ativa</option>
                                <option value="Evento / Feira">Evento / Feira</option>
                              </select>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Card 2: Gestão Comercial & Prazos */}
                    <div className="form-section-card">
                      <div className="card-header">
                        <TrendingUp size={16} className="card-header-icon" />
                        <div>
                          <h4>Planejamento Comercial & Metas</h4>
                          <p>Responsável, equipe, prazos previstos e probabilidades</p>
                        </div>
                      </div>

                      <div className="card-body">
                        <div className="form-grid-3">
                          <div className="form-group">
                            <label>Vendedor Responsável (Força de Vendas)</label>
                            <div className="input-with-icon-box">
                              <UserCheck size={15} className="input-prefix-icon" />
                              <select
                                className="ui-input has-prefix-icon"
                                value={proposalForm.assigned_to_id || ''}
                                onChange={(e) => {
                                  const selectedId = e.target.value;
                                  const seller = sellersList.find(s => s.id === selectedId);
                                  setProposalForm({
                                    ...proposalForm,
                                    assigned_to_id: selectedId || undefined,
                                    responsible_name: seller ? seller.full_name : (selectedId ? proposalForm.responsible_name : ''),
                                    sales_team: seller?.sales_team_name || (selectedId ? 'Sem Equipe Comercial' : '')
                                  });
                                }}
                              >
                                <option value="">Selecione o Vendedor Responsável...</option>
                                {sellersList.map(seller => (
                                  <option key={seller.id} value={seller.id}>
                                    {seller.full_name} {seller.sales_team_name ? `• ${seller.sales_team_name}` : '• Sem Equipe'}
                                  </option>
                                ))}
                              </select>
                            </div>
                          </div>

                          <div className="form-group">
                            <label>Equipe Comercial Vinculada</label>
                            <div className="input-with-icon-box">
                              <Users size={15} className="input-prefix-icon" />
                              <input
                                type="text"
                                className="ui-input has-prefix-icon"
                                value={proposalForm.sales_team || 'Nenhuma equipe vinculada'}
                                readOnly
                                placeholder="Vinculada automaticamente ao vendedor"
                                style={{ backgroundColor: 'var(--bg-muted, rgba(255,255,255,0.03))', cursor: 'not-allowed' }}
                              />
                            </div>
                          </div>

                          <div className="form-group">
                            <label>Nível de Prioridade</label>
                            <div className="priority-pills-container">
                              {[
                                { id: 'HIGH', label: 'Alta', dotColor: '#ef4444' },
                                { id: 'MEDIUM', label: 'Média', dotColor: '#f59e0b' },
                                { id: 'LOW', label: 'Baixa', dotColor: '#10b981' }
                              ].map(pr => (
                                <button
                                  key={pr.id}
                                  type="button"
                                  className={`priority-pill-btn ${proposalForm.priority === pr.id ? 'active' : ''} ${pr.id.toLowerCase()}`}
                                  onClick={() => setProposalForm({ ...proposalForm, priority: pr.id as any })}
                                >
                                  <span className="priority-indicator-dot" style={{ backgroundColor: pr.dotColor }} />
                                  <span>{pr.label}</span>
                                </button>
                              ))}
                            </div>
                          </div>

                          <div className="form-group">
                            <label>Data de Criação</label>
                            <div className="input-with-icon-box">
                              <Calendar size={15} className="input-prefix-icon" />
                              <input
                                type="date"
                                className="ui-input has-prefix-icon"
                                value={proposalForm.creation_date}
                                onChange={(e) => setProposalForm({ ...proposalForm, creation_date: e.target.value })}
                              />
                            </div>
                          </div>

                          <div className="form-group">
                            <label>Previsão de Fechamento</label>
                            <div className="input-with-icon-box">
                              <CalendarDays size={15} className="input-prefix-icon" />
                              <input
                                type="date"
                                className="ui-input has-prefix-icon"
                                value={proposalForm.expected_closing_date}
                                onChange={(e) => setProposalForm({ ...proposalForm, expected_closing_date: e.target.value })}
                              />
                            </div>
                          </div>

                          <div className="form-group">
                            <div className="label-with-prob-val">
                              <label>Probabilidade de Fechamento</label>
                              <span className="prob-display-badge">{proposalForm.probability_percent}%</span>
                            </div>
                            <div className="custom-slider-container">
                              <input
                                type="range"
                                min="0"
                                max="100"
                                step="5"
                                value={proposalForm.probability_percent}
                                onChange={(e) => setProposalForm({ ...proposalForm, probability_percent: Number(e.target.value) })}
                                className="custom-range-slider"
                              />
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Card 3: Categorização & Escopo */}
                    <div className="form-section-card">
                      <div className="card-header">
                        <Tag size={16} className="card-header-icon" />
                        <div>
                          <h4>Tags & Escopo do Projeto</h4>
                          <p>Categorias de produto e detalhamento técnico do fornecimento</p>
                        </div>
                      </div>

                      <div className="card-body">
                        {/* Tags */}
                        <div className="form-group">
                          <label>Tags & Categorias Comerciais</label>
                          <div className="modern-tags-container">
                            <div className="tag-list">
                              {proposalForm.tags.map(tag => (
                                <span key={tag} className="modern-tag-pill">
                                  <Tag size={12} />
                                  <span>{tag}</span>
                                  <button
                                    type="button"
                                    className="btn-remove-tag"
                                    onClick={() => handleRemoveTag(tag)}
                                    title="Remover tag"
                                  >
                                    <X size={12} />
                                  </button>
                                </span>
                              ))}
                            </div>
                            <div className="tag-input-box">
                              <input
                                type="text"
                                placeholder="Digitar tag (ex: CFTV, Fibra, Servidor)..."
                                value={tagInput}
                                onChange={(e) => setTagInput(e.target.value)}
                                onKeyDown={handleAddTag}
                                className="ui-input tag-field"
                              />
                              <button
                                type="button"
                                className="btn-tag-add"
                                onClick={handleAddTag}
                              >
                                <Plus size={14} />
                                <span>Adicionar</span>
                              </button>
                            </div>
                          </div>
                        </div>

                        {/* Escopo */}
                        <div className="form-group" style={{ marginTop: '0.5rem' }}>
                          <div className="label-with-counter">
                            <label>Escopo Técnico & Detalhes da Negociação</label>
                            <span className="char-counter">{proposalForm.notes.length} / 1000</span>
                          </div>
                          <textarea
                            rows={4}
                            className="ui-input modern-textarea"
                            placeholder="Descreva as especificações técnicas, escopo acordado com o decisor, necessidades e detalhes operacionais..."
                            value={proposalForm.notes}
                            onChange={(e) => setProposalForm({ ...proposalForm, notes: e.target.value })}
                            maxLength={1000}
                          />
                        </div>
                      </div>
                    </div>

                  </div>
                )}

                {/* Tab 2: Cliente & LTV 360º */}
                {proposalActiveTab === 'customer' && (
                  <div className="opp-tab-content">
                    
                    {/* Card Executivo de Dados do Cliente (Módulo de Vendas) */}
                    <div className="form-section-card customer-executive-card">
                      <div className="card-header customer-card-header">
                        <div className="customer-header-left">
                          <div className="customer-avatar-badge">
                            {linkedCustomer?.person_type === 'PF' ? <User size={20} /> : <Building2 size={20} />}
                          </div>
                          <div>
                            <div className="customer-title-row">
                              <h4>{linkedCustomer?.name || proposalForm.customer_name || 'Cliente da Oportunidade'}</h4>
                              {linkedCustomer?.trade_name && (
                                <span className="customer-trade-pill">({linkedCustomer.trade_name})</span>
                              )}
                              <span className="customer-status-badge">
                                {linkedCustomer?.person_type === 'PF' ? 'Pessoa Física (PF)' : 'Pessoa Jurídica (PJ)'}
                              </span>
                              <span className="customer-sync-badge">
                                Sincronizado com Vendas
                              </span>
                            </div>
                            <p className="customer-sub-text">
                              Cadastro centralizado de clientes e faturamento corporativo
                            </p>
                          </div>
                        </div>

                        <div className="customer-header-actions">
                          <button
                            type="button"
                            className="btn-customer-action btn-edit-customer"
                            onClick={handleOpenEditCustomerModal}
                            title="Editar dados cadastrais do cliente"
                          >
                            <Edit3 size={14} />
                            <span>Editar Cliente</span>
                          </button>
                          <button
                            type="button"
                            className="btn-customer-action btn-switch-customer"
                            onClick={() => setIsCustomerPickerModalOpen(true)}
                            title="Trocar cliente vinculado selecionando da base comercial"
                          >
                            <RefreshCw size={14} />
                            <span>Trocar Cliente</span>
                          </button>
                        </div>
                      </div>

                      <div className="card-body">
                        <div className="customer-executive-grid">
                          <div className="customer-field-card">
                            <span className="field-label">
                              <FileText size={13} />
                              <span>CNPJ / CPF</span>
                            </span>
                            <strong className="field-value document-value">
                              {linkedCustomer?.document || proposalForm.customer_document || 'Não informado'}
                            </strong>
                          </div>

                          <div className="customer-field-card">
                            <span className="field-label">
                              <Mail size={13} />
                              <span>E-mail Comercial</span>
                            </span>
                            <span className="field-value email-value">
                              {(linkedCustomer?.email || proposalForm.customer_email) ? (
                                <a href={`mailto:${linkedCustomer?.email || proposalForm.customer_email}`}>
                                  {linkedCustomer?.email || proposalForm.customer_email}
                                </a>
                              ) : (
                                <span className="text-muted">Não informado</span>
                              )}
                            </span>
                          </div>

                          <div className="customer-field-card">
                            <span className="field-label">
                              <Phone size={13} />
                              <span>Telefone / WhatsApp</span>
                            </span>
                            <div className="field-value phone-value-box">
                              <span>{linkedCustomer?.phone || proposalForm.customer_phone || 'Não informado'}</span>
                              {(linkedCustomer?.phone || proposalForm.customer_phone) && (
                                <button
                                  type="button"
                                  className="btn-wa-direct"
                                  onClick={() => handleOpenWhatsApp(linkedCustomer?.phone || proposalForm.customer_phone, linkedCustomer?.name || proposalForm.customer_name)}
                                  title="Iniciar conversa no WhatsApp"
                                >
                                  <MessageSquare size={13} />
                                  <span>WhatsApp</span>
                                </button>
                              )}
                            </div>
                          </div>

                          <div className="customer-field-card">
                            <span className="field-label">
                              <User size={13} />
                              <span>Contato Principal</span>
                            </span>
                            <strong className="field-value">
                              {proposalForm.contact_person || (linkedCustomer as any)?.contact_name || 'Carlos Mendes (Comprador)'}
                            </strong>
                          </div>

                          <div className="customer-field-card">
                            <span className="field-label">
                              <Building2 size={13} />
                              <span>Praça / Localização</span>
                            </span>
                            <span className="field-value">
                              {(linkedCustomer as any)?.address_city ? `${(linkedCustomer as any).address_city} - ${(linkedCustomer as any).address_state || 'SP'}` : 'São Paulo / SP'}
                            </span>
                          </div>

                          <div className="customer-field-card">
                            <span className="field-label">
                              <ShieldCheck size={13} />
                              <span>Status Cadastral</span>
                            </span>
                            <span className="field-value status-active">
                              <CheckCircle2 size={13} />
                              <span>Ativo no Módulo de Vendas</span>
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Resumo Financeiro e LTV 360 */}
                    <div className="form-section-card">
                      <div className="card-header">
                        <TrendingUp size={16} className="card-header-icon" />
                        <div>
                          <h4>Indicadores de LTV & Relacionamento</h4>
                          <p>Histórico financeiro consolidado com a conta do cliente</p>
                        </div>
                      </div>

                      <div className="card-body">
                        <div className="ltv-stat-grid">
                          <div className="ltv-box ltv-won">
                            <span className="box-label">LTV Total Faturado</span>
                            <strong className="box-value">{fmtCurrency(selectedOppCustomerLTV.totalLTV)}</strong>
                            <span className="box-sub">{selectedOppCustomerLTV.wonCount} negócios fechados</span>
                          </div>
                          <div className="ltv-box ltv-open">
                            <span className="box-label">Em Aberto no Funil</span>
                            <strong className="box-value">
                              {fmtCurrency(selectedOppCustomerLTV.customerOpps.filter(o => o.stage !== 'WON' && o.stage !== 'LOST').reduce((acc, o) => acc + (Number(o.estimated_amount) || 0), 0))}
                            </strong>
                            <span className="box-sub">{selectedOppCustomerLTV.openCount} negociações ativas</span>
                          </div>
                          <div className="ltv-box ltv-total">
                            <span className="box-label">Histórico de Oportunidades</span>
                            <strong className="box-value">{selectedOppCustomerLTV.customerOpps.length}</strong>
                            <span className="box-sub">Total de negócios com a empresa</span>
                          </div>
                        </div>

                        {selectedOppCustomerLTV.customerOpps.length > 0 && (
                          <div className="customer-opps-wrapper">
                            <h5 className="sub-title">Negociações com este Cliente</h5>
                            <div className="customer-opps-list">
                              {selectedOppCustomerLTV.customerOpps.map(opp => {
                                const stg = stages.find(s => s.code === opp.stage);
                                const isCurrent = opp.id === selectedOpp?.id;
                                return (
                                  <div key={opp.id} className={`cust-opp-row ${isCurrent ? 'is-current' : ''}`}>
                                    <div className="opp-info">
                                      <div className="title-row">
                                        <strong>{opp.title}</strong>
                                        {isCurrent && <span className="current-tag">Negócio Atual</span>}
                                      </div>
                                      <span className="date-sub">Criado em {fmtDate(opp.created_at)}</span>
                                    </div>
                                    <div className="opp-vals">
                                      <span className="amount">{fmtCurrency(opp.estimated_amount)}</span>
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
                          </div>
                        )}
                      </div>
                    </div>

                  </div>
                )}

                {/* Tab: Propostas Comerciais & Cotações Vinculadas */}
                {proposalActiveTab === 'quotes' && (
                  <div className="opp-tab-content">
                    <div className="form-section-card">
                      <div className="card-header quotes-header-flex">
                        <div className="header-left-flex">
                          <FileCheck size={18} className="card-header-icon" />
                          <div>
                            <h4>Propostas Comerciais & Cotações Vinculadas</h4>
                            <p>Histórico de orçamentos e versões de propostas geradas para esta oportunidade</p>
                          </div>
                        </div>
                        <button
                          type="button"
                          className="btn-create-quote-primary ui-button ui-button--primary ui-button--sm"
                          onClick={handleOpenNewQuoteModal}
                        >
                          <Plus size={14} />
                          <span>Nova Cotação / Versão</span>
                        </button>
                      </div>

                      <div className="card-body">
                        {oppQuotations.length === 0 ? (
                          <div className="empty-quotes-state">
                            <div className="empty-icon-wrap">
                              <FileCheck size={36} />
                            </div>
                            <h4>Nenhuma Cotação Formal Registrada</h4>
                            <p>Crie versões de orçamentos detalhadas com itens do catálogo, descontos, prazos e condições para envio ao cliente.</p>
                            <button
                              type="button"
                              className="btn-create-first-quote ui-button ui-button--primary ui-button--sm"
                              onClick={handleOpenNewQuoteModal}
                            >
                              <Plus size={14} />
                              <span>Criar Primeira Cotação</span>
                            </button>
                          </div>
                        ) : (
                          <div className="quotes-cards-grid">
                            {oppQuotations.map((q, idx) => {
                              const isMain = activeQuoteId === q.id || (idx === 0 && !activeQuoteId);
                              const quoteTotal = q.items ? q.items.reduce((acc: number, it: any) => acc + ((it.quantity * it.unit_price) - (it.discount_amount || 0)), 0) : 0;
                              return (
                                <div key={q.id} className={`quote-item-card ${isMain ? 'is-main-quote' : ''}`}>
                                  <div className="quote-card-header">
                                    <div className="quote-title-box">
                                      <div className="quote-id-row">
                                        <span className="quote-code-badge">{q.quote_number}</span>
                                        {isMain && <span className="main-quote-tag">★ Cotação Principal</span>}
                                      </div>
                                      <h4 className="quote-title">{(q as any).title || `Proposta Comercial v${oppQuotations.length - idx}`}</h4>
                                    </div>
                                    <span className={`quote-status-badge status-${(q.status || 'DRAFT').toLowerCase()}`}>
                                      {q.status === 'APPROVED' ? '✓ Aprovada' : (q.status === 'SENT' ? '✉️ Enviada' : (q.status === 'REJECTED' ? '✕ Recusada' : '📝 Rascunho'))}
                                    </span>
                                  </div>

                                  <div className="quote-card-meta-grid">
                                    <div className="meta-cell">
                                      <span className="meta-label">Valor Total</span>
                                      <strong className="meta-val price-val">{fmtCurrency(quoteTotal)}</strong>
                                    </div>
                                    <div className="meta-cell">
                                      <span className="meta-label">Itens Cotados</span>
                                      <strong className="meta-val">{q.items?.length || 0} produtos</strong>
                                    </div>
                                    <div className="meta-cell">
                                      <span className="meta-label">Validade</span>
                                      <strong className="meta-val">{fmtDate(q.valid_until)}</strong>
                                    </div>
                                    <div className="meta-cell">
                                      <span className="meta-label">Condição</span>
                                      <strong className="meta-val">{q.payment_terms || '30 DDL'}</strong>
                                    </div>
                                  </div>

                                  {q.notes && (
                                    <p className="quote-card-notes">
                                      <strong>Obs:</strong> {q.notes}
                                    </p>
                                  )}

                                  <div className="quote-card-actions">
                                    {!isMain && (
                                      <button
                                        type="button"
                                        className="btn-set-main"
                                        onClick={() => handleSetMainQuote(q)}
                                        title="Definir itens e valor como os principais do negócio"
                                      >
                                        <CheckCheck size={13} />
                                        <span>Tornar Principal</span>
                                      </button>
                                    )}
                                    <button
                                      type="button"
                                      className="btn-edit-quote"
                                      onClick={() => handleOpenEditQuoteModal(q)}
                                    >
                                      <ExternalLink size={13} />
                                      <span>Editar Cotação</span>
                                    </button>
                                    <button
                                      type="button"
                                      className="btn-edit-quote"
                                      onClick={() => void openDocumentTimeline('SALES_QUOTE', q.id, `Cotação #${q.quote_number}`)}
                                      title="Ver rastreabilidade completa desta cotação"
                                    >
                                      <GitBranch size={13} />
                                      <span>Rastrear</span>
                                    </button>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                {/* Tab 3: Itens da Oportunidade & Catálogo */}
                {proposalActiveTab === 'items' && (
                  <div className="opp-tab-content">
                    <div className="form-section-card">
                      <div className="card-header flex-between">
                        <div className="header-left-flex">
                          <Package size={16} className="card-header-icon" />
                          <div>
                            <h4>Itens, Produtos & Serviços Cotados</h4>
                            <p>Adicione itens do catálogo de materiais ou serviços sob medida</p>
                          </div>
                        </div>
                        <button
                          type="button"
                          className="btn-add-item ui-button ui-button--primary ui-button--sm"
                          onClick={handleAddQuoteItem}
                        >
                          <Plus size={14} />
                          <span>Adicionar Item</span>
                        </button>
                      </div>

                      <div className="card-body">
                        {quoteItems.length === 0 ? (
                          <div className="empty-items-box">
                            <Package size={32} />
                            <p>Nenhum item inserido na oportunidade.</p>
                            <button
                              type="button"
                              className="ui-button ui-button--secondary ui-button--sm"
                              onClick={handleAddQuoteItem}
                            >
                              <Plus size={14} /> Adicionar Primeiro Item
                            </button>
                          </div>
                        ) : (
                          <div className="proposal-items-table-wrap">
                            <table className="proposal-items-table">
                              <thead>
                                <tr>
                                  <th style={{ width: '40px' }}>#</th>
                                  <th>Descrição / Produto</th>
                                  <th style={{ width: '90px' }}>Qtd</th>
                                  <th style={{ width: '130px' }}>Valor Unitário</th>
                                  <th style={{ width: '110px' }}>Desconto (R$)</th>
                                  <th style={{ width: '130px' }}>Total</th>
                                  <th style={{ width: '40px', textAlign: 'center' }}></th>
                                </tr>
                              </thead>
                              <tbody>
                                {quoteItems.map((item, idx) => {
                                  const itemSub = (item.quantity * item.unit_price) - (item.discount_amount || 0);
                                  return (
                                    <tr key={idx}>
                                      <td className="row-num">{idx + 1}</td>
                                      <td>
                                        <select
                                          value={item.product_id}
                                          onChange={(e) => handleQuoteItemChange(idx, 'product_id', e.target.value)}
                                          className="ui-input custom-styled-select item-select"
                                        >
                                          {products.map(p => (
                                            <option key={p.id} value={p.id}>
                                              {p.name} {p.sku ? `(${p.sku})` : ''}
                                            </option>
                                          ))}
                                        </select>
                                      </td>
                                      <td>
                                        <input
                                          type="number"
                                          min="1"
                                          value={item.quantity}
                                          onChange={(e) => handleQuoteItemChange(idx, 'quantity', e.target.value)}
                                          className="ui-input text-center"
                                        />
                                      </td>
                                      <td>
                                        <input
                                          type="number"
                                          step="0.01"
                                          value={item.unit_price}
                                          onChange={(e) => handleQuoteItemChange(idx, 'unit_price', e.target.value)}
                                          className="ui-input"
                                        />
                                      </td>
                                      <td>
                                        <input
                                          type="number"
                                          step="0.01"
                                          value={item.discount_amount}
                                          onChange={(e) => handleQuoteItemChange(idx, 'discount_amount', e.target.value)}
                                          className="ui-input text-danger"
                                        />
                                      </td>
                                      <td className="row-total">
                                        <strong>{fmtCurrency(Math.max(0, itemSub))}</strong>
                                      </td>
                                      <td style={{ textAlign: 'center' }}>
                                        <button
                                          type="button"
                                          className="btn-remove-item"
                                          onClick={() => handleRemoveQuoteItem(idx)}
                                          title="Remover item"
                                        >
                                          <Trash2 size={14} />
                                        </button>
                                      </td>
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>
                        )}

                        {/* Financial Summary Box */}
                        <div className="proposal-financial-summary-panel">
                          <div className="summary-rows">
                            <div className="fin-row">
                              <span>Subtotal dos itens:</span>
                              <strong>{fmtCurrency(proposalItemsSubtotal)}</strong>
                            </div>
                            <div className="fin-row discount-row">
                              <span>Descontos comerciais:</span>
                              <strong className="text-danger">- {fmtCurrency(proposalTotalDiscount)}</strong>
                            </div>
                            <div className="fin-row">
                              <span>Impostos estimados:</span>
                              <input
                                type="number"
                                step="0.01"
                                value={proposalForm.tax_amount}
                                onChange={(e) => setProposalForm({ ...proposalForm, tax_amount: Number(e.target.value) })}
                                className="ui-input mini-input"
                                placeholder="0,00"
                              />
                            </div>
                            <div className="fin-row">
                              <span>Frete / Deslocamento:</span>
                              <input
                                type="number"
                                step="0.01"
                                value={proposalForm.freight_amount}
                                onChange={(e) => setProposalForm({ ...proposalForm, freight_amount: Number(e.target.value) })}
                                className="ui-input mini-input"
                                placeholder="0,00"
                              />
                            </div>
                            <div className="fin-row total-highlight-row">
                              <span>Valor Total da Oportunidade:</span>
                              <strong className="final-price">{fmtCurrency(proposalFinalTotal)}</strong>
                            </div>
                          </div>
                        </div>

                      </div>
                    </div>
                  </div>
                )}

                {/* Tab 4: Condições Comerciais */}
                {proposalActiveTab === 'terms' && (
                  <div className="opp-tab-content">
                    <div className="form-section-card">
                      <div className="card-header">
                        <CreditCard size={16} className="card-header-icon" />
                        <div>
                          <h4>Condições Comerciais & Faturamento</h4>
                          <p>Defina as modalidades de pagamento, prazos de entrega e garantias</p>
                        </div>
                      </div>

                      <div className="card-body">
                        <div className="form-grid-3">
                          <div className="form-group">
                            <label>Forma de Pagamento *</label>
                            <div className="select-with-icon-box">
                              <CreditCard size={15} className="input-prefix-icon" />
                              <select
                                value={proposalForm.payment_method}
                                onChange={(e) => setProposalForm({ ...proposalForm, payment_method: e.target.value })}
                                className="ui-input custom-styled-select has-prefix-icon"
                              >
                                <option value="Transferência Bancária">Transferência Bancária (TED/Pix)</option>
                                <option value="Boleto Bancário">Boleto Bancário</option>
                                <option value="Faturado 30 DDL">Faturado 30 DDL</option>
                                <option value="Faturado 30/60/90 DDL">Faturado 30/60/90 DDL</option>
                                <option value="Cartão de Crédito Corporativo">Cartão de Crédito Corporativo</option>
                              </select>
                            </div>
                          </div>

                          <div className="form-group">
                            <label>Parcelamento / Entrada</label>
                            <div className="input-with-icon-box">
                              <DollarSign size={15} className="input-prefix-icon" />
                              <input
                                type="text"
                                className="ui-input has-prefix-icon"
                                placeholder="Ex: 30% entrada + 2x boletos"
                                value={proposalForm.installment_terms}
                                onChange={(e) => setProposalForm({ ...proposalForm, installment_terms: e.target.value })}
                              />
                            </div>
                          </div>

                          <div className="form-group">
                            <label>Prazo de Entrega</label>
                            <div className="input-with-icon-box">
                              <Clock size={15} className="input-prefix-icon" />
                              <input
                                type="text"
                                className="ui-input has-prefix-icon"
                                placeholder="Ex: 15 dias úteis"
                                value={proposalForm.delivery_deadline}
                                onChange={(e) => setProposalForm({ ...proposalForm, delivery_deadline: e.target.value })}
                              />
                            </div>
                          </div>
                        </div>

                        <div className="form-grid-3" style={{ marginTop: '0.85rem' }}>
                          <div className="form-group">
                            <label>Validade da Proposta</label>
                            <div className="input-with-icon-box">
                              <Calendar size={15} className="input-prefix-icon" />
                              <input
                                type="date"
                                className="ui-input has-prefix-icon"
                                value={proposalForm.valid_until}
                                onChange={(e) => setProposalForm({ ...proposalForm, valid_until: e.target.value })}
                              />
                            </div>
                          </div>

                          <div className="form-group">
                            <label>Garantia dos Equipamentos / Serviços</label>
                            <div className="input-with-icon-box">
                              <ShieldCheck size={15} className="input-prefix-icon" />
                              <input
                                type="text"
                                className="ui-input has-prefix-icon"
                                placeholder="Ex: 12 meses"
                                value={proposalForm.warranty_terms}
                                onChange={(e) => setProposalForm({ ...proposalForm, warranty_terms: e.target.value })}
                              />
                            </div>
                          </div>

                          <div className="form-group">
                            <label>SLA & Suporte Técnico</label>
                            <div className="input-with-icon-box">
                              <Zap size={15} className="input-prefix-icon" />
                              <input
                                type="text"
                                className="ui-input has-prefix-icon"
                                placeholder="Ex: 8x5 - Atendimento Remoto"
                                value={proposalForm.sla_support}
                                onChange={(e) => setProposalForm({ ...proposalForm, sla_support: e.target.value })}
                              />
                            </div>
                          </div>
                        </div>

                        <div className="form-group" style={{ marginTop: '0.85rem' }}>
                          <label>Condições Especiais e Cláusulas Comerciais</label>
                          <textarea
                            rows={3}
                            className="ui-input modern-textarea"
                            placeholder="Descreva detalhes de frete, instalação, alçadas e responsabilidades do cliente..."
                            value={proposalForm.special_conditions}
                            onChange={(e) => setProposalForm({ ...proposalForm, special_conditions: e.target.value })}
                          />
                        </div>

                        <div className="acceptance-toggle-box" style={{ marginTop: '1rem' }}>
                          <div className="toggle-left">
                            <ShieldCheck size={20} className="shield-icon" />
                            <div>
                              <strong>Aceite Digital & Validação Jurídica</strong>
                              <p>Habilita link de assinatura digital para envio e aprovação do cliente via portal online.</p>
                            </div>
                          </div>
                          <label className="switch-control">
                            <input
                              type="checkbox"
                              checked={proposalForm.digital_acceptance}
                              onChange={(e) => setProposalForm({ ...proposalForm, digital_acceptance: e.target.checked })}
                            />
                            <span className="slider-round"></span>
                          </label>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Tab 5: Aprovações & Governança */}
                {proposalActiveTab === 'approvals' && (
                  <div className="opp-tab-content">
                    <div className="form-section-card">
                      <div className="card-header flex-between">
                        <div className="header-left-flex">
                          <ShieldCheck size={18} className="card-header-icon" />
                          <div>
                            <h4>Governança Comercial & Alçadas</h4>
                            <p>Validação de desconto, margem de contribuição e aprovação de gestores</p>
                          </div>
                        </div>
                        <div className={`gov-status-pill ${proposalForm.status.toLowerCase()}`}>
                          {proposalForm.status === 'APPROVED' && <CheckCircle2 size={14} />}
                          {proposalForm.status === 'REJECTED' && <X size={14} />}
                          {proposalForm.status === 'DRAFT' && <FileText size={14} />}
                          <span>
                            {proposalForm.status === 'APPROVED' ? 'Proposta Aprovada' :
                             proposalForm.status === 'REJECTED' ? 'Devolvida para Revisão' :
                             proposalForm.status === 'CONVERTED' ? 'Convertida em Pedido' :
                             'Rascunho Comercial'}
                          </span>
                        </div>
                      </div>

                      <div className="card-body">
                        {/* Resumo Financeiro da Proposta */}
                        <div className="gov-summary-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '1.5rem', background: 'var(--bg-surface-elevated, rgba(255,255,255,0.02))', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                          <div>
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Valor Total do Negócio</span>
                            <h3 style={{ margin: '0.2rem 0 0', color: 'var(--text-primary)' }}>{fmtCurrency(proposalFinalTotal)}</h3>
                          </div>
                          <div>
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Desconto Total Aplicado</span>
                            <h3 style={{ margin: '0.2rem 0 0', color: proposalTotalDiscount > 0 ? '#f59e0b' : 'var(--text-secondary)' }}>
                              {fmtCurrency(proposalTotalDiscount)}
                            </h3>
                          </div>
                          <div>
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Vendedor Responsável</span>
                            <div style={{ fontWeight: 600, marginTop: '0.2rem', color: 'var(--text-primary)' }}>{proposalForm.responsible_name}</div>
                            <span style={{ fontSize: '0.72rem', color: 'var(--accent-brand)' }}>{proposalForm.sales_team || 'Sem Equipe'}</span>
                          </div>
                        </div>

                        {/* Painel de Ações de Governança para Gestores */}
                        <div className="gov-action-box" style={{ background: 'var(--bg-surface)', padding: '1.2rem', borderRadius: '8px', border: '1px solid var(--border-subtle)', marginBottom: '1rem' }}>
                          <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.9rem', color: 'var(--text-primary)' }}>Parecer e Decisão do Gestor</h4>
                          <p style={{ margin: '0 0 1rem', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                            Gestores comerciais e administradores podem aprovar ou devolver esta proposta comercial para adequação de margem e escopo.
                          </p>

                          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                            <button
                              type="button"
                              className="ui-button ui-button--primary"
                              onClick={handleApproveProposal}
                              disabled={proposalForm.status === 'APPROVED'}
                              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', background: '#10b981', borderColor: '#10b981' }}
                            >
                              <CheckCircle2 size={15} />
                              <span>{proposalForm.status === 'APPROVED' ? 'Proposta Já Aprovada' : 'Aprovar Proposta'}</span>
                            </button>

                            <button
                              type="button"
                              className="ui-button ui-button--secondary"
                              onClick={handleRejectProposal}
                              disabled={proposalForm.status === 'REJECTED'}
                              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', color: '#ef4444' }}
                            >
                              <X size={15} />
                              <span>Solicitar Revisão / Rejeitar</span>
                            </button>

                            <button
                              type="button"
                              className="ui-button ui-button--secondary"
                              onClick={() => setProposalForm(prev => ({ ...prev, status: 'DRAFT' }))}
                              disabled={proposalForm.status === 'DRAFT'}
                            >
                              Voltar para Rascunho
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

              </div>

              {/* Right Column (30%) - Real-Time Follow-up & Activity Sidebar */}
              <div className="opp-sidebar-pane">
                
                {/* Header da Sidebar */}
                <div className="sidebar-header-bar">
                  <div className="header-title-box">
                    <MessageSquare size={16} className="title-icon" />
                    <h4>Follow-ups & Atualizações</h4>
                  </div>
                  <button
                    type="button"
                    className="btn-add-activity-pill"
                    onClick={() => setIsAddingSidebarActivity(!isAddingSidebarActivity)}
                  >
                    <Plus size={13} />
                    <span>{isAddingSidebarActivity ? 'Fechar' : 'Nova Atualização'}</span>
                  </button>
                </div>

                {/* Composer de Atualizações / Follow-ups da Proposta */}
                {isAddingSidebarActivity && (
                  <form onSubmit={handleSaveSidebarActivity} className="modern-inline-activity-card">
                    <div className="activity-type-chips">
                      {[
                        { id: 'NOTE', label: 'Nota', icon: FileText },
                        { id: 'WHATSAPP', label: 'WhatsApp', icon: MessageSquare },
                        { id: 'CALL', label: 'Ligação', icon: Phone },
                        { id: 'MEETING', label: 'Reunião', icon: Users },
                        { id: 'EMAIL', label: 'E-mail', icon: Mail }
                      ].map(t => {
                        const Icon = t.icon;
                        const isSelected = sidebarActivityForm.type === t.id;
                        return (
                          <button
                            key={t.id}
                            type="button"
                            className={`type-chip chip-${t.id.toLowerCase()} ${isSelected ? 'selected' : ''}`}
                            onClick={() => setSidebarActivityForm({ ...sidebarActivityForm, type: t.id as any })}
                          >
                            <Icon size={12} />
                            <span>{t.label}</span>
                          </button>
                        );
                      })}
                    </div>

                    <div className="update-textarea-wrap">
                      <textarea
                        rows={3}
                        className="update-composer-textarea"
                        placeholder={
                          sidebarActivityForm.type === 'NOTE' ? "Escreva uma anotação ou ocorrência da proposta (ex: Cliente aguardando validação interna)..." :
                          sidebarActivityForm.type === 'WHATSAPP' ? "O que foi conversado ou acordado via WhatsApp..." :
                          sidebarActivityForm.type === 'CALL' ? "Resumo do alinhamento realizado por telefone..." :
                          sidebarActivityForm.type === 'MEETING' ? "Principais pontos discutidos na reunião..." :
                          "Assunto e detalhes do e-mail enviado/recebido..."
                        }
                        value={sidebarActivityForm.summary}
                        onChange={(e) => setSidebarActivityForm({ ...sidebarActivityForm, summary: e.target.value })}
                        required
                      />
                    </div>

                    <div className="update-composer-meta-row">
                      <div className="composer-date-group">
                        <div className="input-with-icon-box">
                          <Calendar size={13} className="input-prefix-icon" />
                          <input
                            type="date"
                            value={sidebarActivityForm.date}
                            onChange={(e) => setSidebarActivityForm({ ...sidebarActivityForm, date: e.target.value })}
                            className="ui-input has-prefix-icon sm"
                          />
                        </div>
                        <div className="input-with-icon-box">
                          <Clock size={13} className="input-prefix-icon" />
                          <input
                            type="time"
                            value={sidebarActivityForm.time}
                            onChange={(e) => setSidebarActivityForm({ ...sidebarActivityForm, time: e.target.value })}
                            className="ui-input has-prefix-icon sm"
                          />
                        </div>
                      </div>

                      <div className="activity-card-actions">
                        <button
                          type="button"
                          className="btn-cancel-action"
                          onClick={() => setIsAddingSidebarActivity(false)}
                        >
                          Cancelar
                        </button>
                        <button
                          type="submit"
                          className="btn-submit-action"
                        >
                          <Plus size={13} />
                          <span>Registrar</span>
                        </button>
                      </div>
                    </div>
                  </form>
                )}

                {/* Próxima Ação Destaque */}
                <div className="modern-spotlight-card">
                  <div className="spotlight-top">
                    <span className="spotlight-tag">Último Andamento</span>
                    <span className="priority-tag">Em Negociação</span>
                  </div>
                  <div className="spotlight-content">
                    <div className="icon-wrapper">
                      <Phone size={15} />
                    </div>
                    <div className="info-wrapper">
                      <strong>Follow-up com Decisor</strong>
                      <span className="due-time">{fmtDate(proposalForm.expected_closing_date)}</span>
                      <span className="agent-text">Resp: {proposalForm.responsible_name}</span>
                    </div>
                  </div>
                </div>

                {/* Linha do Tempo de Atualizações */}
                <div className="modern-timeline-container">
                  <div className="timeline-title-row">
                    <span>Histórico de Atualizações</span>
                    <span className="count-tag">{pendingSidebarActivities.length + oppInteractions.length}</span>
                  </div>

                  <div className="timeline-track">
                    {(pendingSidebarActivities.length > 0 || oppInteractions.length > 0) ? (
                      <>
                        {/* Atividades em Rascunho */}
                        {pendingSidebarActivities.map((act) => (
                          <div key={act.id} className="timeline-entry pending-entry">
                            <div className={`timeline-node ${act.interaction_type.toLowerCase()}`}>
                              <FileText size={12} />
                            </div>
                            <div className="timeline-card pending-card">
                              <div className="card-top">
                                <span className="card-title">{act.summary}</span>
                                <span className="pending-badge" style={{ fontSize: '0.68rem', padding: '0.1rem 0.4rem', borderRadius: '4px', background: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b' }}>
                                  Pendente a salvar
                                </span>
                              </div>
                            </div>
                          </div>
                        ))}

                        {/* Atividades Persistidas */}
                        {oppInteractions.map((act) => (
                          <div key={act.id} className="timeline-entry">
                            <div className={`timeline-node ${act.interaction_type.toLowerCase()}`}>
                              {act.interaction_type === 'CALL' && <Phone size={12} />}
                              {act.interaction_type === 'WHATSAPP' && <MessageSquare size={12} />}
                              {act.interaction_type === 'MEETING' && <Users size={12} />}
                              {act.interaction_type === 'EMAIL' && <Mail size={12} />}
                              {act.interaction_type === 'NOTE' && <FileText size={12} />}
                            </div>
                            <div className="timeline-card">
                              <div className="card-top">
                                <span className="card-title">{act.summary}</span>
                                <span className="card-time">{fmtDate(act.interaction_date || act.created_at)}</span>
                              </div>
                              {act.details && <p className="card-details">{act.details}</p>}
                            </div>
                          </div>
                        ))}
                      </>
                    ) : (
                      <div className="empty-timeline-hint">
                        <p>Nenhuma atualização registrada ainda.</p>
                        <span>Clique em <strong>+ Nova Atualização</strong> acima para registrar contatos, notas ou alinhamentos desta proposta.</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Próximo Passo Acordado */}
                <div className="modern-next-step-box">
                  <div className="step-icon-wrap">
                    <Star size={15} />
                  </div>
                  <div className="step-body">
                    <span className="step-label">Próximo Passo</span>
                    <p>Alinhamento dos itens e fechamento com {proposalForm.contact_person || proposalForm.customer_name}.</p>
                  </div>
                  <span className="step-date">{fmtDate(proposalForm.expected_closing_date)}</span>
                </div>

                {/* Feed de Auditoria */}
                <div className="audit-history-footer">
                  <span className="audit-title">Registro do Negócio</span>
                  <div className="audit-row">
                    <span className="audit-dot" />
                    <span>Criado em {fmtDate(proposalForm.creation_date)} por {proposalForm.responsible_name}</span>
                  </div>
                </div>

              </div>

            </div>

          </div>
        </div>
      )}

      {/* =================================================================== */}
      {/* MODAL DE DEFINIR META COMERCIAL DO MÊS (FASE 4)                     */}
      {/* =================================================================== */}
      {isGoalModalOpen && (
        <Modal
          isOpen={true}
          onClose={() => setIsGoalModalOpen(false)}
          title="Definir Meta Comercial do Mês"
          subtitle="Estabeleça o objetivo financeiro de faturamento em negociações ganhas para a equipe"
          size="sm"
        >
          <form onSubmit={handleSaveGoal} className="wizard-form">
            <div className="form-group">
              <label>Valor da Meta Mensal (R$) *</label>
              <input
                type="number"
                step="1000"
                min="1000"
                required
                className="ui-input"
                placeholder="Ex: 150000"
                value={tempGoalInput}
                onChange={(e) => setTempGoalInput(e.target.value)}
              />
              <span className="field-hint">
                Meta atual: {fmtCurrency(monthlySalesGoal)} • Realizado até o momento: {fmtCurrency(kpis.wonAmount)}
              </span>
            </div>

            <div className="modal-footer ui-form__actions">
              <button
                type="button"
                className="btn-secondary ui-button ui-button--secondary"
                onClick={() => setIsGoalModalOpen(false)}
              >
                Cancelar
              </button>
              <button
                type="submit"
                className="btn-primary ui-button ui-button--primary"
              >
                <Target size={14} />
                <span>Salvar Meta</span>
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* =================================================================== */}
      {/* MODAL DEDICADO DE COTAÇÃO / PROPOSTA COMERCIAL (UNIFICADO)          */}
      {/* =================================================================== */}
      <QuoteModal
        isOpen={isDedicatedQuoteModalOpen}
        onClose={() => {
          setIsDedicatedQuoteModalOpen(false);
          setEditingQuote(null);
        }}
        quote={editingQuote}
        fixedCustomerId={selectedOpp?.customer_id || linkedCustomer?.id || null}
        fixedOpportunityId={selectedOpp?.id || null}
        fixedCustomerName={selectedOpp?.customer_name || linkedCustomer?.name || ''}
        onSuccess={async (_savedQuote) => {
          if (selectedOpp) {
            try {
              const quotes = await crmService.getOpportunityQuotations(selectedOpp.id, true);
              setOppQuotations(quotes);
              await loadCRMData();
            } catch (e) {
              console.error("Erro ao sincronizar cotações:", e);
            }
          }
        }}
      />

      {/* ========================================================================= */}
      {/* MODAL / WIZARD DEDICADO: CADASTRO DO CLIENTE (UNIFICADO MÓDULO DE VENDAS)  */}
      {/* ========================================================================= */}
      <CustomerModal
        isOpen={isCustomerModalOpen}
        onClose={() => setIsCustomerModalOpen(false)}
        customer={linkedCustomer}
        onSuccess={async (savedCust) => {
          setLinkedCustomer(savedCust);
          setProposalForm(prev => ({
            ...prev,
            customer_id: savedCust.id,
            customer_name: savedCust.trade_name || savedCust.name,
            customer_document: savedCust.document || '',
            customer_email: savedCust.email || '',
            customer_phone: savedCust.phone || ''
          }));

          const targetOppId = selectedOpp?.id || selectedOppForQuote?.id;
          if (targetOppId) {
            try {
              await crmService.updateOpportunity(targetOppId, {
                customer_id: savedCust.id,
                customer_name: savedCust.trade_name || savedCust.name
              });
              setOpportunities(prev => prev.map(o => o.id === targetOppId ? {
                ...o,
                customer_id: savedCust.id,
                customer_name: savedCust.trade_name || savedCust.name
              } : o));
              setSelectedOpp(prev => prev ? {
                ...prev,
                customer_id: savedCust.id,
                customer_name: savedCust.trade_name || savedCust.name
              } : null);
            } catch (err: any) {
              console.error("Erro ao sincronizar oportunidade com cliente:", err);
            }
          }
        }}
      />

      {/* ========================================================================= */}
      {/* 6. MODAL / WIZARD: SELECIONAR / VINCULAR CLIENTE DA BASE COMERCIAL        */}
      {/* ========================================================================= */}
      {isCustomerPickerModalOpen && (
        <Modal
          isOpen={isCustomerPickerModalOpen}
          onClose={() => setIsCustomerPickerModalOpen(false)}
          title="Vincular Cliente do Módulo de Vendas"
          subtitle="Selecione um cliente existente ou cadastre um novo para associar à proposta"
          size="md"
        >
          <div className="customer-picker-modal-body" style={{ padding: '1rem 0' }}>
            <p style={{ fontSize: '0.825rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
              Pesquise pelo nome, razão social, CNPJ ou e-mail na base mestre de Vendas:
            </p>
            <CustomerPicker
              value={proposalForm.customer_id}
              onChange={handleLinkCustomerFromPicker}
              allowCreate={true}
            />
            <div style={{ marginTop: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <button
                type="button"
                className="btn-secondary ui-button ui-button--secondary"
                onClick={() => {
                  setIsCustomerPickerModalOpen(false);
                  handleOpenNewCustomerModal();
                }}
              >
                <Plus size={14} />
                <span>Cadastrar Novo Cliente</span>
              </button>
              <button
                type="button"
                className="btn-secondary ui-button ui-button--secondary"
                onClick={() => setIsCustomerPickerModalOpen(false)}
              >
                Fechar
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* MODAL DE RASTREABILIDADE DOCUMENTAL TRANSVERSAL */}
      <Modal
        isOpen={isDocumentTimelineOpen}
        onClose={() => setIsDocumentTimelineOpen(false)}
        title={`Cadeia documental · ${documentTimelineLabel}`}
        subtitle="Rastreabilidade entre os documentos realmente vinculados de ponta a ponta"
        size="lg"
      >
        {documentTimelineLoading ? (
          <div className="ui-document-timeline-loading" role="status" style={{ padding: '2rem', textAlign: 'center' }}>
            <RefreshCw size={20} className="spinner" />
            <p style={{ marginTop: '0.75rem', color: 'var(--text-secondary)' }}>Consultando documentos relacionados no grafo...</p>
          </div>
        ) : documentTimelineError ? (
          <div className="modal-alert-error" role="alert" style={{ padding: '1rem', background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', borderRadius: '8px' }}>
            {documentTimelineError}
          </div>
        ) : documentChain ? (
          <DocumentTimeline chain={documentChain} onNavigate={handleTimelineNavigate} />
        ) : (
          <div className="ui-empty-state" style={{ padding: '2rem', textAlign: 'center' }}>Nenhuma cadeia documental disponível.</div>
        )}
      </Modal>
    </div>
  );
};
