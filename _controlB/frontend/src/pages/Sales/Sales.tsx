/**
 * pages/Sales/Sales.tsx - Módulo Comercial, Cotações & Vendas (ControlB ERP)
 * 
 * Funcionalidades Estruturais:
 * 1. 📝 Cotações & Propostas Comerciais (Orçamentos, Descontos, Alçadas, Validade e Conversão em Pedido)
 * 2. 📦 Pedidos de Venda (Gestão de status, itens, faturamento e entregas)
 * 3. 👥 Clientes PJ / PF (Cadastro com CNPJ/CPF, Limite de Crédito, Contato Identity e CRM)
 * 4. 🎯 Gestão Comercial (Metas por Vendedor, Comissões e Tabelas de Preços)
 * 5. 🔄 Pós-Venda (Cancelamentos, Devoluções e Trocas com Reestocagem no Kardex)
 * 6. 📊 Indicadores & BI Comercial (Faturamento, Ticket Médio, Conversão e Ranking de Vendedores)
 */

import React, { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  ShoppingBag, FileText, RefreshCw, Search,
  Trash2, Users, Plus, Target, DollarSign,
  TrendingUp, Undo2, ChevronRight, Award, BarChart3,
  Package, CheckCircle2, Layers, Filter, ArrowUpRight, GitBranch,
  Truck, Check, Settings, ShieldAlert, XCircle
} from 'lucide-react';
import {
  Bar, BarChart, CartesianGrid, ResponsiveContainer,
  Tooltip, XAxis, YAxis
} from 'recharts';
import {
  salesService, inventoryService, documentService, formatApiError
} from '@/services/api';
import {
  SalesOrder, SalesQuote, Product,
  Customer, SalesGoal, PriceTable, SalesReturn, SalesAnalytics,
  BusinessDocumentChain, SellerResponse, CreditApprovalRequest, CommercialApprovalRequest,
  InventoryDelivery, StockReservation
} from '@/types';
import { formatCurrency, formatQuantity } from '@/utils/formatters';
import { Modal } from '@/components/Modal/Modal';
import { ConfirmModal, ConfirmModalType } from '@/components/ConfirmModal/ConfirmModal';
import { Can } from '@/components/Can';
import { DocumentTimeline } from '@/components/DocumentTimeline/DocumentTimeline';
import { CustomerModal } from '@/components/CustomerModal/CustomerModal';
import { QuoteModal } from '@/components/QuoteModal/QuoteModal';
import { OrderModal } from '@/components/OrderModal/OrderModal';
import { CommercialTeamsSettings } from '@/components/CommercialTeamsSettings/CommercialTeamsSettings';
import { CommercialPoliciesSettings } from '@/components/CommercialPoliciesSettings/CommercialPoliciesSettings';
import { useToast } from '@/components/Toast/ToastContext';
import { BulkActionsBar } from '@/components/BulkActionsBar';
import { ListPagination } from '@/components/ListPagination';
import { useBulkSelection } from '@/hooks/useBulkSelection';
import { useListPagination } from '@/hooks/useListPagination';
import { DocumentLink, RecordLink, useRecordDeepLink, isRequestedView, parseRecordReference } from '@/components/RecordLink';
import './Sales.scss';

type ActiveSalesTab =
  | 'quotes'
  | 'orders'
  | 'approvals'
  | 'deliveries'
  | 'customers'
  | 'commercial'
  | 'post_sales'
  | 'analytics'
  | 'settings';

const ALLOWED_SALES_TABS: readonly ActiveSalesTab[] = [
  'quotes', 'orders', 'approvals', 'deliveries', 'customers', 'commercial', 'post_sales', 'analytics', 'settings'
];

export const Sales: React.FC = () => {
  const toast = useToast();
  const [searchParams] = useSearchParams();
  const initialTab = isRequestedView(searchParams, ALLOWED_SALES_TABS, 'quotes');
  const [activeTab, setActiveTab] = useState<ActiveSalesTab>(initialTab);
  const [loading, setLoading] = useState<boolean>(true);

  // --- DADOS DO SERVIDOR ---
  const [quotes, setQuotes] = useState<SalesQuote[]>([]);
  const [orders, setOrders] = useState<SalesOrder[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [salesGoals, setSalesGoals] = useState<SalesGoal[]>([]);
  const [priceTables, setPriceTables] = useState<PriceTable[]>([]);
  const [salesReturns, setSalesReturns] = useState<SalesReturn[]>([]);
  const [analytics, setAnalytics] = useState<SalesAnalytics | null>(null);
  const [sellers, setSellers] = useState<SellerResponse[]>([]);
  const [creditApprovals, setCreditApprovals] = useState<CreditApprovalRequest[]>([]);
  const [commercialApprovals, setCommercialApprovals] = useState<CommercialApprovalRequest[]>([]);
  const quoteSelection = useBulkSelection<SalesQuote>();
  const orderSelection = useBulkSelection<SalesOrder>();
  const customerSelection = useBulkSelection<Customer>();
  const returnSelection = useBulkSelection<SalesReturn>();
  const goalSelection = useBulkSelection<SalesGoal>();
  const priceTableSelection = useBulkSelection<PriceTable>();

  // --- FILTROS E BUSCAS GLOBAIS POR ABA ---
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [typeFilter, setTypeFilter] = useState<string>('ALL');
  const [yearFilter, setYearFilter] = useState<number>(new Date().getFullYear());

  // --- FEEDBACK E CONTROLE ---
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [modalError, setModalError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [isDocumentTimelineOpen, setIsDocumentTimelineOpen] = useState(false);
  const [documentTimelineLoading, setDocumentTimelineLoading] = useState(false);
  const [documentTimelineLabel, setDocumentTimelineLabel] = useState('');
  const [documentTimelineError, setDocumentTimelineError] = useState<string | null>(null);
  const [documentChain, setDocumentChain] = useState<BusinessDocumentChain | null>(null);
  const [documentTimelineTarget, setDocumentTimelineTarget] = useState<{
    documentType: 'SALES_QUOTE' | 'SALES_ORDER';
    nativeId: string;
  } | null>(null);
  const [reservingOrderId, setReservingOrderId] = useState<string | null>(null);
  const [creditDecision, setCreditDecision] = useState<{
    approval: CreditApprovalRequest;
    approved: boolean;
  } | null>(null);
  const [creditDecisionReason, setCreditDecisionReason] = useState('');
  const [creditDecisionSaving, setCreditDecisionSaving] = useState(false);
  const [commercialDecision, setCommercialDecision] = useState<{
    approval: CommercialApprovalRequest;
    approved: boolean;
  } | null>(null);
  const [commercialDecisionReason, setCommercialDecisionReason] = useState('');
  const [commercialDecisionSaving, setCommercialDecisionSaving] = useState(false);

  // --- CONFIRM MODAL GENÉRICO ---
  const [confirmModal, setConfirmModal] = useState<{
    isOpen: boolean;
    title: string;
    subtitle?: string;
    message: React.ReactNode;
    type: ConfirmModalType;
    confirmText: string;
    onConfirm: () => Promise<void>;
  }>({
    isOpen: false,
    title: '',
    message: '',
    type: 'danger',
    confirmText: 'Confirmar',
    onConfirm: async () => {}
  });

  const openConfirm = (opts: {
    title: string;
    subtitle?: string;
    message: React.ReactNode;
    type?: ConfirmModalType;
    confirmText?: string;
    onConfirm: () => Promise<void>;
  }) => {
    setConfirmModal({
      isOpen: true,
      title: opts.title,
      subtitle: opts.subtitle,
      message: opts.message,
      type: opts.type || 'danger',
      confirmText: opts.confirmText || 'Confirmar Exclusão',
      onConfirm: opts.onConfirm
    });
  };

  const closeConfirm = () => {
    setConfirmModal(prev => ({ ...prev, isOpen: false }));
  };

  // =========================================================================
  // ESTADOS: 1. COTAÇÕES & PROPOSTAS COMERCIAIS
  // =========================================================================
  const [isQuoteModalOpen, setIsQuoteModalOpen] = useState<boolean>(false);
  const [editingQuote, setEditingQuote] = useState<SalesQuote | null>(null);
  const [quoteToCancel, setQuoteToCancel] = useState<SalesQuote | null>(null);
  const [cancelReasonInput, setCancelReasonInput] = useState<string>('');
  const [isCancellingQuote, setIsCancellingQuote] = useState<boolean>(false);

  // =========================================================================
  // ESTADOS: 2. PEDIDOS DE VENDA
  // =========================================================================
  const [isOrderModalOpen, setIsOrderModalOpen] = useState<boolean>(false);
  const [editingOrder, setEditingOrder] = useState<SalesOrder | null>(null);
  const [billingOrderId, setBillingOrderId] = useState<string | null>(null);

  // =========================================================================
  // ESTADOS: 3. CLIENTES (PF / PJ)
  // =========================================================================
  const [isCustomerModalOpen, setIsCustomerModalOpen] = useState<boolean>(false);
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null);

  // =========================================================================
  // ESTADOS: 4. GESTÃO COMERCIAL (METAS & TABELAS DE PREÇOS)
  // =========================================================================
  const [isGoalModalOpen, setIsGoalModalOpen] = useState<boolean>(false);
  const [goalSellerId, setGoalSellerId] = useState<string>('');
  const [goalSellerName, setGoalSellerName] = useState<string>('');
  const [goalMonth, setGoalMonth] = useState<number>(new Date().getMonth() + 1);
  const [goalTargetAmount, setGoalTargetAmount] = useState<string>('50000.00');
  const [goalCommission, setGoalCommission] = useState<string>('3.0');

  const [isPriceTableModalOpen, setIsPriceTableModalOpen] = useState<boolean>(false);
  const [priceTableName, setPriceTableName] = useState<string>('');
  const [priceTableDesc, setPriceTableDesc] = useState<string>('');
  const [priceTableIsDefault, setPriceTableIsDefault] = useState<boolean>(false);
  const [priceTableItems, setPriceTableItems] = useState<Array<{
    product_id: string;
    price: number;
    discount_percent: number;
  }>>([]);

  // =========================================================================
  // ESTADOS: 5. PÓS-VENDA (DEVOLUÇÕES / TROCAS)
  // =========================================================================
  const [isReturnModalOpen, setIsReturnModalOpen] = useState<boolean>(false);
  const [selectedReturn, setSelectedReturn] = useState<SalesReturn | null>(null);
  const [logisticsDetail, setLogisticsDetail] = useState<
    | { kind: 'DELIVERY'; record: InventoryDelivery }
    | { kind: 'STOCK_RESERVATION'; record: StockReservation }
    | null
  >(null);
  const [logisticsDetailError, setLogisticsDetailError] = useState<string | null>(null);
  const [retCustomerName, setRetCustomerName] = useState<string>('');
  const [retType, setRetType] = useState<'DEVOLUCAO' | 'TROCA' | 'CANCELAMENTO'>('DEVOLUCAO');
  const [retReason, setRetReason] = useState<string>('Defeito de fábrica');
  const [retRestock, setRetRestock] = useState<boolean>(true);
  const [retProductId, setRetProductId] = useState<string>('');
  const [retQuantity, setRetQuantity] = useState<string>('1');
  const [retUnitPrice, setRetUnitPrice] = useState<string>('0.00');
  const [retCondition, setRetCondition] = useState<'GOOD' | 'DAMAGED'>('GOOD');

  // =========================================================================
  // HELPERS DE FORMATAÇÃO SEGURA (Evitam TypeError com toFixed)
  // =========================================================================
  const safeNumber = (val: number | string | undefined | null): number => {
    if (val === undefined || val === null) return 0;
    const n = typeof val === 'string' ? parseFloat(val) : Number(val);
    return isNaN(n) ? 0 : n;
  };

  const fmtCurrency = (val: number | string | undefined | null): string => {
    return formatCurrency(safeNumber(val));
  };
  const billingStatusLabel = (value: SalesOrder['billing_status']) => ({
    PENDING: 'Não solicitado',
    REQUESTED: 'Solicitado',
    PARTIALLY_INVOICED: 'Parcialmente faturado',
    INVOICED: 'Faturado'
  }[value]);

  const fmtPercent = (val: number | string | undefined | null): string => {
    return `${safeNumber(val).toFixed(1)}%`;
  };

  const fmtCompactCurrency = (val: number | string | undefined | null): string => {
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'BRL',
      notation: 'compact',
      maximumFractionDigits: 1
    }).format(safeNumber(val));
  };

  const triggerSuccess = (msg: string) => {
    setActionSuccess(msg);
    setTimeout(() => setActionSuccess(null), 4000);
  };

  const openDocumentTimeline = async (
    documentType: 'SALES_QUOTE' | 'SALES_ORDER',
    nativeId: string,
    label: string
  ) => {
    setDocumentTimelineLabel(label);
    setDocumentTimelineError(null);
    setDocumentChain(null);
    setDocumentTimelineTarget({ documentType, nativeId });
    setIsDocumentTimelineOpen(true);
    setDocumentTimelineLoading(true);

    try {
      const chain = await documentService.getChain(documentType, nativeId, true);
      setDocumentChain(chain);
    } catch (err: unknown) {
      const message = formatApiError(
        err,
        'Não foi possível consultar a cadeia deste documento.'
      );
      setDocumentTimelineError(message);
      toast.error(message, 'Rastreabilidade indisponível');
    } finally {
      setDocumentTimelineLoading(false);
    }
  };

  // =========================================================================
  // CARREGAMENTO DE DADOS DO SERVIDOR
  // =========================================================================
  const loadAllData = async (force = false) => {
    setLoading(true);
    try {
      const [
        quotesRes, ordersRes, productsRes, customersRes,
        goalsRes, priceTablesRes, returnsRes, analyticsRes, sellersRes
      ] = await Promise.all([
        salesService.getQuotes(force),
        salesService.getOrders(force),
        inventoryService.getProducts(undefined, force),
        salesService.getCustomers('', force),
        salesService.getSalesGoals(yearFilter, force),
        salesService.getPriceTables(force),
        salesService.getSalesReturns(force),
        salesService.getSalesAnalytics(force),
        salesService.getSellers(force)
      ]);

      setQuotes(quotesRes || []);
      setOrders(ordersRes || []);
      setProducts(productsRes || []);
      setCustomers(customersRes || []);
      setSalesGoals(goalsRes || []);
      setPriceTables(priceTablesRes || []);
      setSalesReturns(returnsRes || []);
      setAnalytics(analyticsRes || null);
      setSellers(sellersRes || []);
    } catch (err: any) {
      console.error("Erro ao carregar dados de vendas:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAllData();
  }, [yearFilter]);

  useEffect(() => {
    if (activeTab !== 'approvals') return;
    Promise.all([
      salesService.getCreditApprovals(undefined, true),
      salesService.getCommercialApprovals(undefined, true),
    ])
      .then(([creditRows, commercialRows]) => {
        setCreditApprovals(creditRows);
        setCommercialApprovals(commercialRows);
      })
      .catch((err: unknown) => {
        toast.error(formatApiError(err, 'Não foi possível carregar as aprovações.'));
      });
  }, [activeTab, toast]);

  // =========================================================================
  // HANDLERS: COTAÇÕES & PROPOSTAS COMERCIAIS
  // =========================================================================
  const handleOpenQuoteModal = (quote?: SalesQuote) => {
    setEditingQuote(quote || null);
    setIsQuoteModalOpen(true);
  };

  const handleConvertToOrder = (quote: SalesQuote) => {
    openConfirm({
      title: 'Converter Cotação em Pedido de Venda',
      subtitle: `Cotação #${quote.quote_number}`,
      message: (
        <div>
          <p>Deseja converter a cotação comercial de <strong>{quote.customer_name}</strong> em um Pedido de Venda definitivo?</p>
          <p style={{ marginTop: '0.5rem', color: '#10b981', fontWeight: 600 }}>
            Valor Total: {fmtCurrency(quote.net_amount)}
          </p>
        </div>
      ),
      type: 'success',
      confirmText: 'Converter em Pedido',
      onConfirm: async () => {
        try {
          await salesService.convertQuoteToOrder(quote.id);
          triggerSuccess("Cotação convertida em Pedido de Venda com sucesso!");
          closeConfirm();
          loadAllData();
        } catch (err: any) {
          toast.error(formatApiError(err, "Erro ao converter cotação."), 'Falha na conversão');
        }
      }
    });
  };

  const handleDeleteQuote = (quote: SalesQuote) => {
    openConfirm({
      title: 'Excluir Cotação Definitivamente',
      subtitle: `Cotação #${quote.quote_number}`,
      message: `Deseja realmente excluir permanentemente a cotação #${quote.quote_number} de ${quote.customer_name}? Esta ação removerá o registro e todos os seus itens do sistema.`,
      type: 'danger',
      confirmText: 'Excluir Permanentemente',
      onConfirm: async () => {
        try {
          await salesService.deleteQuote(quote.id, true);
          triggerSuccess(`Cotação #${quote.quote_number} excluída com sucesso.`);
          closeConfirm();
          loadAllData(true);
        } catch (err: any) {
          toast.error(formatApiError(err, "Erro ao excluir cotação."), 'Falha ao excluir cotação');
        }
      }
    });
  };

  // =========================================================================
  // HANDLERS: PEDIDOS DE VENDA & WORKFLOW
  // =========================================================================
  const handleOpenOrderModal = (order?: SalesOrder) => {
    setEditingOrder(order || null);
    setIsOrderModalOpen(true);
  };

  const handleUpdateQuoteStatus = async (quote: SalesQuote, newStatus: string) => {
    try {
      await salesService.updateQuoteStatus(quote.id, newStatus);
      triggerSuccess(`Status da cotação #${quote.quote_number} alterado para ${newStatus}.`);
      loadAllData();
    } catch (err: any) {
      toast.error(formatApiError(err, "Erro ao alterar status da cotação."));
    }
  };

  const handleConfirmCancelQuote = async () => {
    if (!quoteToCancel || !cancelReasonInput.trim()) {
      toast.error('Informe o motivo do cancelamento / desistência.');
      return;
    }
    setIsCancellingQuote(true);
    try {
      await salesService.cancelQuote(quoteToCancel.id, cancelReasonInput.trim());
      triggerSuccess(`Cotação #${quoteToCancel.quote_number} cancelada com sucesso.`);
      setQuoteToCancel(null);
      setCancelReasonInput('');
      loadAllData(true);
    } catch (err: any) {
      toast.error(formatApiError(err, 'Erro ao cancelar cotação'));
    } finally {
      setIsCancellingQuote(false);
    }
  };

  const handleRequestBilling = async (order: SalesOrder) => {
    if (billingOrderId !== null) return;
    setBillingOrderId(order.id);
    try {
      await salesService.requestOrderBilling(order.id);
      triggerSuccess(`Pedido #${order.order_number} enviado para a fila do Faturamento.`);
      loadAllData();
    } catch (err: any) {
      toast.error(formatApiError(err, "Erro ao solicitar faturamento do pedido."));
    } finally {
      setBillingOrderId(null);
    }
  };

  const handleCreditDecision = async () => {
    if (!creditDecision || creditDecisionReason.trim().length < 3) {
      toast.error('Informe uma justificativa com pelo menos 3 caracteres.');
      return;
    }
    setCreditDecisionSaving(true);
    try {
      await salesService.decideCreditApproval(
        creditDecision.approval.id,
        creditDecision.approved,
        creditDecisionReason.trim()
      );
      triggerSuccess(
        `Crédito do pedido #${creditDecision.approval.order.order_number} ${creditDecision.approved ? 'aprovado' : 'rejeitado'}.`
      );
      setCreditDecision(null);
      setCreditDecisionReason('');
      const [approvalRows, orderRows] = await Promise.all([
        salesService.getCreditApprovals(undefined, true),
        salesService.getOrders(true)
      ]);
      setCreditApprovals(approvalRows);
      setOrders(orderRows);
    } catch (err: unknown) {
      toast.error(formatApiError(err, 'Não foi possível registrar a decisão de crédito.'));
    } finally {
      setCreditDecisionSaving(false);
    }
  };

  const handleCommercialDecision = async () => {
    if (!commercialDecision || commercialDecisionReason.trim().length < 3) {
      toast.error('Informe uma justificativa com pelo menos 3 caracteres.');
      return;
    }
    setCommercialDecisionSaving(true);
    try {
      await salesService.decideCommercialApproval(
        commercialDecision.approval.id,
        commercialDecision.approved,
        commercialDecisionReason.trim()
      );
      triggerSuccess('Decisão comercial registrada com sucesso.');
      setCommercialDecision(null);
      setCommercialDecisionReason('');
      const [approvalRows, quoteRows, orderRows] = await Promise.all([
        salesService.getCommercialApprovals(undefined, true),
        salesService.getQuotes(true),
        salesService.getOrders(true),
      ]);
      setCommercialApprovals(approvalRows);
      setQuotes(quoteRows);
      setOrders(orderRows);
    } catch (err: unknown) {
      toast.error(formatApiError(err, 'Não foi possível registrar a decisão comercial.'));
    } finally {
      setCommercialDecisionSaving(false);
    }
  };

  const handleUpdateOrderStatus = async (order: SalesOrder, data: Partial<SalesOrder>) => {
    try {
      await salesService.updateOrderStatus(order.id, data);
      triggerSuccess(`Pedido #${order.order_number} atualizado com sucesso.`);
      loadAllData();
    } catch (err: any) {
      toast.error(formatApiError(err, "Erro ao atualizar pedido."));
    }
  };

  const handleReserveOrderStock = async (order: SalesOrder) => {
    if (reservingOrderId !== null) return;

    setReservingOrderId(order.id);
    try {
      const reservation = await inventoryService.reserveSalesOrderStock(order.id);
      toast.success(
        `Reserva #${reservation.reservation_number} criada para ${reservation.items.length} item(ns).`,
        'Estoque reservado'
      );
      setOrders(current => current.map(item => (
        item.id === order.id ? { ...item, delivery_status: 'RESERVED' } : item
      )));

      try {
        const ordersRes = await salesService.getOrders(true);
        setOrders(ordersRes || []);
      } catch (refreshError: unknown) {
        toast.warning(
          formatApiError(
            refreshError,
            'A reserva foi concluída, mas os dados da tela não puderam ser atualizados.'
          ),
          'Atualização pendente'
        );
      }

      if (
        isDocumentTimelineOpen &&
        documentTimelineTarget?.documentType === 'SALES_ORDER' &&
        documentTimelineTarget.nativeId === order.id
      ) {
        setDocumentTimelineLoading(true);
        setDocumentTimelineError(null);
        try {
          const chain = await documentService.getChain('SALES_ORDER', order.id, true);
          setDocumentChain(chain);
        } catch (timelineError: unknown) {
          const message = formatApiError(
            timelineError,
            'A reserva foi concluída, mas a rastreabilidade não pôde ser atualizada.'
          );
          setDocumentTimelineError(message);
          toast.warning(message, 'Rastreabilidade pendente');
        } finally {
          setDocumentTimelineLoading(false);
        }
      }
    } catch (err: unknown) {
      toast.error(
        formatApiError(err, 'Não foi possível reservar o estoque deste pedido.'),
        'Falha na reserva de estoque'
      );
    } finally {
      setReservingOrderId(null);
    }
  };

  const handleDeleteOrder = (order: SalesOrder) => {
    openConfirm({
      title: 'Cancelar Pedido de Venda',
      subtitle: `Pedido #${order.order_number}`,
      message: `Deseja realmente cancelar o pedido #${order.order_number} de ${order.customer_name}? As reservas de estoque serão liberadas e eventuais solicitações de faturamento serão canceladas.`,
      type: 'danger',
      confirmText: 'Cancelar Pedido',
      onConfirm: async () => {
        try {
          await salesService.deleteOrder(order.id, 'Cancelamento operacional', false);
          triggerSuccess(`Pedido #${order.order_number} cancelado com sucesso.`);
          closeConfirm();
          loadAllData(true);
        } catch (err: any) {
          toast.error(formatApiError(err, "Erro ao cancelar pedido."), 'Falha ao cancelar pedido');
        }
      }
    });
  };

  const handlePermanentDeleteOrder = (order: SalesOrder) => {
    openConfirm({
      title: 'Excluir Pedido Definitivamente',
      subtitle: `Pedido #${order.order_number}`,
      message: `Deseja realmente excluir permanentemente o pedido #${order.order_number} de ${order.customer_name}? Esta ação removerá o registro e todos os seus itens do sistema.`,
      type: 'danger',
      confirmText: 'Excluir Permanentemente',
      onConfirm: async () => {
        try {
          await salesService.deleteOrder(order.id, undefined, true);
          triggerSuccess(`Pedido #${order.order_number} excluído definitivamente com sucesso.`);
          closeConfirm();
          loadAllData(true);
        } catch (err: any) {
          toast.error(formatApiError(err, "Erro ao excluir pedido."), 'Falha ao excluir pedido');
        }
      }
    });
  };

  // =========================================================================
  // HANDLERS: CLIENTES (PF / PJ)
  // =========================================================================
  const handleOpenCustomerModal = (customer?: Customer) => {
    setEditingCustomer(customer || null);
    setIsCustomerModalOpen(true);
  };

  useRecordDeepLink({
    types: ['CUSTOMER', 'CLIENT'],
    records: customers,
    onOpen: (customer) => {
      setActiveTab('customers');
      handleOpenCustomerModal(customer);
    },
  });

  useRecordDeepLink({
    types: ['SALES_QUOTE', 'QUOTE'],
    records: quotes,
    onOpen: (quote) => {
      setActiveTab('quotes');
      handleOpenQuoteModal(quote);
    },
  });

  useRecordDeepLink({
    types: ['SALES_ORDER', 'ORDER'],
    records: orders,
    onOpen: (order) => {
      setActiveTab('orders');
      handleOpenOrderModal(order);
    },
  });

  useRecordDeepLink({
    types: ['SALES_RETURN'],
    records: salesReturns,
    onOpen: (salesReturn) => {
      setActiveTab('post_sales');
      setSelectedReturn(salesReturn);
    },
  });

  const requestedRecord = parseRecordReference(searchParams);
  const requestedLogisticsType = requestedRecord?.type === 'DELIVERY'
    || requestedRecord?.type === 'STOCK_RESERVATION'
    ? requestedRecord.type
    : null;
  const requestedLogisticsId = requestedLogisticsType ? requestedRecord?.id || '' : '';

  useEffect(() => {
    if (!requestedLogisticsType || !requestedLogisticsId) return;
    let cancelled = false;
    setActiveTab('deliveries');
    setLogisticsDetailError(null);

    const handleError = (error: unknown) => {
      if (!cancelled) setLogisticsDetailError(formatApiError(error, 'Não foi possível abrir o registro logístico.'));
    };
    if (requestedLogisticsType === 'DELIVERY') {
      inventoryService.getInventoryDelivery(requestedLogisticsId)
        .then(record => { if (!cancelled) setLogisticsDetail({ kind: 'DELIVERY', record }); })
        .catch(handleError);
    } else {
      inventoryService.getStockReservation(requestedLogisticsId)
        .then(record => { if (!cancelled) setLogisticsDetail({ kind: 'STOCK_RESERVATION', record }); })
        .catch(handleError);
    }

    return () => { cancelled = true; };
  }, [requestedLogisticsId, requestedLogisticsType]);

  const handleDeleteCustomer = (customer: Customer) => {
    openConfirm({
      title: 'Excluir Cliente',
      subtitle: customer.name,
      message: `Deseja realmente remover o cliente ${customer.name} (${customer.document})?`,
      type: 'danger',
      confirmText: 'Excluir Cliente',
      onConfirm: async () => {
        try {
          await salesService.deleteCustomer(customer.id);
          triggerSuccess("Cliente excluído com sucesso.");
          closeConfirm();
          loadAllData();
        } catch (err: any) {
          toast.error(formatApiError(err, "Erro ao excluir cliente."), 'Falha ao excluir cliente');
        }
      }
    });
  };

  // =========================================================================
  // HANDLERS: GESTÃO COMERCIAL (METAS & TABELAS)
  // =========================================================================
  const handleOpenGoalModal = async () => {
    setModalError(null);
    const firstSeller = sellers[0];
    setGoalSellerId(firstSeller?.id || '');
    setGoalSellerName(firstSeller?.full_name || '');
    try {
      const settings = await salesService.getCommercialSettings();
      setGoalCommission(String(settings.default_commission_percent));
    } catch {
      setGoalCommission('2');
    }
    setIsGoalModalOpen(true);
  };

  const handleSaveGoal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!goalSellerId) {
      setModalError("Selecione um vendedor vinculado ao Identity.");
      return;
    }

    setIsSaving(true);
    setModalError(null);
    try {
      await salesService.createSalesGoal({
        user_id: goalSellerId,
        seller_name: goalSellerName.trim(),
        month: Number(goalMonth),
        year: Number(yearFilter),
        target_amount: safeNumber(goalTargetAmount),
        commission_percent: safeNumber(goalCommission)
      });
      setIsGoalModalOpen(false);
      triggerSuccess("Meta comercial cadastrada com sucesso!");
      loadAllData();
    } catch (err: any) {
      setModalError(formatApiError(err, "Erro ao cadastrar meta comercial."));
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteGoal = (goal: SalesGoal) => {
    openConfirm({
      title: 'Excluir Meta Comercial',
      subtitle: `${goal.seller_name} - Mês ${goal.month}/${goal.year}`,
      message: `Deseja realmente remover a meta de ${fmtCurrency(goal.target_amount)} para ${goal.seller_name}?`,
      type: 'danger',
      confirmText: 'Excluir Meta',
      onConfirm: async () => {
        try {
          await salesService.deleteSalesGoal(goal.id);
          triggerSuccess("Meta comercial excluída com sucesso.");
          closeConfirm();
          loadAllData();
        } catch (err: any) {
          toast.error(formatApiError(err, "Erro ao excluir meta."), 'Falha ao excluir meta');
        }
      }
    });
  };

  const handleSavePriceTable = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!priceTableName.trim()) {
      setModalError("O nome da tabela de preços é obrigatório.");
      return;
    }

    setIsSaving(true);
    setModalError(null);
    try {
      await salesService.createPriceTable({
        name: priceTableName.trim(),
        description: priceTableDesc.trim() || undefined,
        is_default: priceTableIsDefault,
        is_active: true,
        items: priceTableItems.map(it => ({
          product_id: it.product_id,
          price: it.price,
          discount_percent: it.discount_percent
        }))
      });
      setIsPriceTableModalOpen(false);
      triggerSuccess("Tabela de preços cadastrada com sucesso!");
      loadAllData();
    } catch (err: any) {
      setModalError(formatApiError(err, "Erro ao cadastrar tabela de preços."));
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeletePriceTable = (table: PriceTable) => {
    openConfirm({
      title: 'Excluir Tabela de Preços',
      subtitle: table.name,
      message: `Deseja realmente remover a tabela de preços ${table.name}?`,
      type: 'danger',
      confirmText: 'Excluir Tabela',
      onConfirm: async () => {
        try {
          await salesService.deletePriceTable(table.id);
          triggerSuccess("Tabela de preços excluída com sucesso.");
          closeConfirm();
          loadAllData();
        } catch (err: any) {
          toast.error(formatApiError(err, "Erro ao excluir tabela."), 'Falha ao excluir tabela');
        }
      }
    });
  };

  // =========================================================================
  // HANDLERS: PÓS-VENDA
  // =========================================================================
  const handleOpenReturnModal = () => {
    setModalError(null);
    setRetCustomerName('');
    setRetType('DEVOLUCAO');
    setRetReason('Defeito de fabricação');
    setRetRestock(true);
    setRetQuantity('1');
    setRetCondition('GOOD');
    if (products.length > 0) {
      setRetProductId(products[0].id);
      setRetUnitPrice(String(products[0].reference_price || '10.00'));
    }
    setIsReturnModalOpen(true);
  };

  const handleSaveReturn = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!retCustomerName.trim() || !retProductId) {
      setModalError("Cliente e Produto são obrigatórios.");
      return;
    }

    setIsSaving(true);
    setModalError(null);
    try {
      const q = Math.max(1, parseInt(retQuantity) || 1);
      const p = safeNumber(retUnitPrice);
      await salesService.createSalesReturn({
        customer_name: retCustomerName.trim(),
        return_type: retType,
        reason: retReason.trim(),
        restock_items: retRestock,
        items: [{
          product_id: retProductId,
          quantity: q,
          unit_price: p,
          total_price: q * p,
          condition: retCondition
        }]
      });
      setIsReturnModalOpen(false);
      triggerSuccess("Registro de pós-venda processado com sucesso!");
      loadAllData();
    } catch (err: any) {
      setModalError(formatApiError(err, "Erro ao registrar devolução/troca."));
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteReturn = (ret: SalesReturn) => {
    openConfirm({
      title: 'Excluir Registro de Pós-Venda',
      subtitle: `${ret.return_type} - ${ret.customer_name}`,
      message: `Deseja realmente remover o registro de ${ret.return_type} de ${ret.customer_name}?`,
      type: 'danger',
      confirmText: 'Excluir Registro',
      onConfirm: async () => {
        try {
          await salesService.deleteSalesReturn(ret.id);
          triggerSuccess("Registro excluído com sucesso.");
          closeConfirm();
          loadAllData();
        } catch (err: any) {
          toast.error(formatApiError(err, "Erro ao excluir registro."), 'Falha ao excluir registro');
        }
      }
    });
  };

  // =========================================================================
  // FILTROS DINÂMICOS
  // =========================================================================
  const filteredQuotes = useMemo(() => {
    return quotes.filter(q => {
      const term = searchTerm.toLowerCase().trim();
      const matchesSearch = !term || (
        q.quote_number.toLowerCase().includes(term) ||
        q.customer_name.toLowerCase().includes(term) ||
        Boolean(q.customer_document && q.customer_document.toLowerCase().includes(term))
      );
      const matchesStatus = statusFilter === 'ALL' || q.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [quotes, searchTerm, statusFilter]);

  const filteredOrders = useMemo(() => {
    return orders.filter(o => {
      const term = searchTerm.toLowerCase().trim();
      const matchesSearch = !term || (
        o.order_number.toLowerCase().includes(term) ||
        o.customer_name.toLowerCase().includes(term) ||
        Boolean(o.customer_document && o.customer_document.toLowerCase().includes(term))
      );
      const matchesStatus = statusFilter === 'ALL' || o.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [orders, searchTerm, statusFilter]);

  const filteredCreditApprovals = useMemo(() => {
    return creditApprovals.filter(item => {
      const term = searchTerm.toLowerCase().trim();
      const matchesSearch = !term
        || item.order.order_number.toLowerCase().includes(term)
        || item.order.customer_name.toLowerCase().includes(term);
      const matchesStatus = statusFilter === 'ALL' || item.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [creditApprovals, searchTerm, statusFilter]);

  const filteredCommercialApprovals = useMemo(() => {
    return commercialApprovals.filter(item => {
      const target = item.quote || item.order;
      const number = item.quote?.quote_number || item.order?.order_number || '';
      const term = searchTerm.toLowerCase().trim();
      const matchesSearch = !term
        || number.toLowerCase().includes(term)
        || Boolean(target?.customer_name.toLowerCase().includes(term));
      const matchesStatus = statusFilter === 'ALL' || item.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [commercialApprovals, searchTerm, statusFilter]);

  const filteredCustomers = useMemo(() => {
    return customers.filter(c => {
      const term = searchTerm.toLowerCase().trim();
      const matchesSearch = !term || (
        c.name.toLowerCase().includes(term) ||
        c.document.toLowerCase().includes(term) ||
        Boolean(c.trade_name && c.trade_name.toLowerCase().includes(term)) ||
        Boolean(c.email && c.email.toLowerCase().includes(term)) ||
        Boolean(c.address_city && c.address_city.toLowerCase().includes(term))
      );
      const matchesType = typeFilter === 'ALL' || c.person_type === typeFilter;
      return matchesSearch && matchesType;
    });
  }, [customers, searchTerm, typeFilter]);

  const filteredReturns = useMemo(() => {
    return salesReturns.filter(r => {
      const term = searchTerm.toLowerCase().trim();
      const matchesSearch = !term || (
        r.customer_name.toLowerCase().includes(term) ||
        r.reason.toLowerCase().includes(term) ||
        r.return_type.toLowerCase().includes(term)
      );
      const matchesType = typeFilter === 'ALL' || r.return_type === typeFilter;
      return matchesSearch && matchesType;
    });
  }, [salesReturns, searchTerm, typeFilter]);

  const quotePagination = useListPagination(filteredQuotes);
  const orderPagination = useListPagination(filteredOrders);
  const customerPagination = useListPagination(filteredCustomers);
  const returnPagination = useListPagination(filteredReturns);

  const openBulkAction = (
    label: string,
    ids: string[],
    action: (id: string) => Promise<unknown>,
    clearSelection: () => void,
  ) => {
    if (ids.length === 0) return;
    openConfirm({
      title: `${label} em massa`,
      message: `Confirma a operação em ${ids.length} registro(s) selecionado(s)? As regras individuais de cada registro serão preservadas.`,
      type: 'danger',
      confirmText: `${label} selecionados`,
      onConfirm: async () => {
        const results = await Promise.allSettled(ids.map(action));
        const succeeded = results.filter(result => result.status === 'fulfilled').length;
        const failed = results.length - succeeded;
        clearSelection();
        closeConfirm();
        if (failed) toast.warning(`${succeeded} registro(s) processado(s); ${failed} não atenderam às regras da operação.`, 'Operação parcial');
        else triggerSuccess(`${succeeded} registro(s) processado(s) com sucesso.`);
        await loadAllData(true);
      },
    });
  };

  return (
    <div className="sales-page">
      <div className="sales-layout">
        {/* ================================================================= */}
        {/* 1. SIDEBAR LATERAL ESQUERDA (PADRÃO CORPORATIVO CONTROLB)         */}
        {/* ================================================================= */}
        <aside className="sidebar-left">
          <div className="sidebar-header">
            <ShoppingBag className="brand-icon" size={20} />
            <div className="sidebar-title-wrap">
              <span className="sidebar-title"><strong>Vendas & Cotações</strong></span>
              <span className="sidebar-subtitle">Gestão Comercial B2B/B2C</span>
            </div>
          </div>

          <nav className="nav-menu">
            <span className="menu-group-label">Pipeline & Negociação</span>

            <button
              className={`nav-item ${activeTab === 'quotes' ? 'active' : ''}`}
              onClick={() => { setActiveTab('quotes'); setSearchTerm(''); setStatusFilter('ALL'); }}
            >
              <div className="nav-item-content">
                <FileText size={16} />
                <span>Cotações & Propostas</span>
              </div>
              <span className="nav-badge">{quotes.length}</span>
            </button>

            <button
              className={`nav-item ${activeTab === 'orders' ? 'active' : ''}`}
              onClick={() => { setActiveTab('orders'); setSearchTerm(''); setStatusFilter('ALL'); }}
            >
              <div className="nav-item-content">
                <Package size={16} />
                <span>Pedidos de Venda</span>
              </div>
              <span className="nav-badge">{orders.length}</span>
            </button>

            <Can anyOf={["sales:credit:view", "sales:approvals:view"]}>
              <button
                className={`nav-item ${activeTab === 'approvals' ? 'active' : ''}`}
                onClick={() => { setActiveTab('approvals'); setSearchTerm(''); setStatusFilter('ALL'); }}
              >
                <div className="nav-item-content">
                  <ShieldAlert size={16} />
                  <span>Aprovações</span>
                </div>
                <span className="nav-badge">
                  {creditApprovals.filter(item => item.status === 'PENDING').length
                    + commercialApprovals.filter(item => item.status === 'PENDING').length}
                </span>
              </button>
            </Can>

            <button
              className={`nav-item ${activeTab === 'deliveries' ? 'active' : ''}`}
              onClick={() => { setActiveTab('deliveries'); setSearchTerm(''); setStatusFilter('ALL'); }}
            >
              <div className="nav-item-content">
                <Truck size={16} />
                <span>Entregas & Expedição</span>
              </div>
              <span className="nav-badge">{orders.filter(o => o.delivery_status !== 'DELIVERED' && o.delivery_status !== 'CANCELLED').length}</span>
            </button>

            <span className="menu-group-label">Relacionamento & Clientes</span>

            <button
              className={`nav-item ${activeTab === 'customers' ? 'active' : ''}`}
              onClick={() => { setActiveTab('customers'); setSearchTerm(''); setTypeFilter('ALL'); }}
            >
              <div className="nav-item-content">
                <Users size={16} />
                <span>Base de Clientes (PJ / PF)</span>
              </div>
              <span className="nav-badge">{customers.length}</span>
            </button>

            <span className="menu-group-label">Estratégia & Qualidade</span>

            <button
              className={`nav-item ${activeTab === 'commercial' ? 'active' : ''}`}
              onClick={() => { setActiveTab('commercial'); setSearchTerm(''); }}
            >
              <div className="nav-item-content">
                <Target size={16} />
                <span>Gestão Comercial & Metas</span>
              </div>
              <span className="nav-badge">{salesGoals.length}</span>
            </button>

            <button
              className={`nav-item ${activeTab === 'post_sales' ? 'active' : ''}`}
              onClick={() => { setActiveTab('post_sales'); setSearchTerm(''); setTypeFilter('ALL'); }}
            >
              <div className="nav-item-content">
                <Undo2 size={16} />
                <span>Pós-Venda & Devoluções</span>
              </div>
              <span className="nav-badge">{salesReturns.length}</span>
            </button>

            <button
              className={`nav-item ${activeTab === 'analytics' ? 'active' : ''}`}
              onClick={() => { setActiveTab('analytics'); setSearchTerm(''); }}
            >
              <div className="nav-item-content">
                <BarChart3 size={16} />
                <span>Indicadores & BI</span>
              </div>
            </button>

            <span className="menu-group-label">Configurações</span>

            <button
              className={`nav-item ${activeTab === 'settings' ? 'active' : ''}`}
              onClick={() => { setActiveTab('settings'); setSearchTerm(''); }}
            >
              <div className="nav-item-content">
                <Settings size={16} />
                <span>Equipes Comerciais</span>
              </div>
            </button>
          </nav>
        </aside>

        {/* ================================================================= */}
        {/* 2. ÁREA PRINCIPAL DE TRABALHO                                     */}
        {/* ================================================================= */}
        <main className="content-right">
          {actionSuccess && (
            <div className="alert-banner success">
              <CheckCircle2 size={16} />
              <span>{actionSuccess}</span>
            </div>
          )}

          {/* CABEÇALHO DA SEÇÃO */}
          <div className="content-header ui-page-header">
            <div className="header-titles ui-page-header__info">
              <div className="breadcrumbs ui-page-header__breadcrumb">
                <span>Comercial</span>
                <ChevronRight size={12} />
                <span className="current">
                  {activeTab === 'quotes' && 'Cotações & Propostas Comerciais'}
                  {activeTab === 'orders' && 'Pedidos de Venda'}
                  {activeTab === 'approvals' && 'Aprovações Comerciais e de Crédito'}
                  {activeTab === 'deliveries' && 'Entregas & Logística de Expedição'}
                  {activeTab === 'customers' && 'Base Centralizada de Clientes'}
                  {activeTab === 'commercial' && 'Gestão Comercial, Metas & Preços'}
                  {activeTab === 'post_sales' && 'Pós-Venda & Reestocagem no Kardex'}
                  {activeTab === 'analytics' && 'Inteligência Comercial & BI'}
                  {activeTab === 'settings' && 'Configurações Comerciais'}
                </span>
              </div>
              <h1 className="ui-page-header__title">
                {activeTab === 'quotes' && 'Cotações & Propostas Comerciais'}
                {activeTab === 'orders' && 'Pedidos de Venda Executáveis'}
                {activeTab === 'approvals' && 'Fila Unificada de Aprovações'}
                {activeTab === 'deliveries' && 'Painel de Entregas & Expedição'}
                {activeTab === 'customers' && 'Clientes (Pessoa Jurídica / Física)'}
                {activeTab === 'commercial' && 'Gestão de Metas & Tabelas de Preços'}
                {activeTab === 'post_sales' && 'Pós-Venda & Trocas / Devoluções'}
                {activeTab === 'analytics' && 'Painel Analítico de Vendas & BI'}
                {activeTab === 'settings' && 'Equipes Comerciais'}
              </h1>
            </div>

            <div className="header-actions ui-page-header__actions">
              <button className="btn-refresh ui-button ui-button--icon" onClick={() => loadAllData(true)} title="Atualizar Dados">
                <RefreshCw size={15} className={loading ? 'spinning' : ''} />
              </button>

              {activeTab === 'quotes' && (
                <button className="btn-primary ui-button ui-button--primary" onClick={() => handleOpenQuoteModal()}>
                  <Plus size={16} /> Nova Cotação
                </button>
              )}

              {activeTab === 'orders' && (
                <button className="btn-primary ui-button ui-button--primary" onClick={() => handleOpenOrderModal()}>
                  <Plus size={16} /> Novo Pedido
                </button>
              )}

              {activeTab === 'customers' && (
                <button className="btn-primary ui-button ui-button--primary" onClick={() => handleOpenCustomerModal()}>
                  <Plus size={16} /> Novo Cliente
                </button>
              )}

              {activeTab === 'commercial' && (
                <>
                  <button className="btn-secondary ui-button ui-button--secondary" onClick={() => setIsPriceTableModalOpen(true)}>
                    <Layers size={16} /> Nova Tabela de Preços
                  </button>
                  <button className="btn-primary ui-button ui-button--primary" onClick={() => void handleOpenGoalModal()}>
                    <Plus size={16} /> Nova Meta
                  </button>
                </>
              )}

              {activeTab === 'post_sales' && (
                <button className="btn-primary ui-button ui-button--primary" onClick={handleOpenReturnModal}>
                  <Plus size={16} /> Registrar Devolução
                </button>
              )}
            </div>
          </div>

          {/* =============================================================== */}
          {/* ABA 1: COTAÇÕES & PROPOSTAS COMERCIAIS                          */}
          {/* =============================================================== */}
          {activeTab === 'quotes' && (
            <div className="tab-pane">
              <div className="toolbar ui-toolbar">
                <div className="search-box ui-search-box">
                  <Search size={16} />
                  <input
                    type="text"
                    placeholder="Buscar por número da cotação ou cliente..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>
                <div className="filter-group ui-filter-group">
                  <Filter size={14} />
                  <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                    <option value="ALL">Todos os Status</option>
                    <option value="DRAFT">Rascunho</option>
                    <option value="SENT">Enviado ao Cliente</option>
                    <option value="APPROVED">Aprovado</option>
                    <option value="CONVERTED">Convertido em Pedido</option>
                    <option value="REJECTED">Rejeitado</option>
                  </select>
                </div>
              </div>

              <BulkActionsBar
                selectedCount={quoteSelection.selectedCount}
                resourceName={{ singular: 'cotação', plural: 'cotações' }}
                onClear={quoteSelection.clearSelection}
                onDelete={() => openBulkAction('Excluir definitivamente', quoteSelection.selectedIdList, (id) => salesService.deleteQuote(id, true), quoteSelection.clearSelection)}
                deleteLabel="Excluir selecionadas"
              >
                <button
                  type="button"
                  className="bulk-btn bulk-btn--warning"
                  onClick={() => openBulkAction('Cancelar', quoteSelection.selectedIdList, (id) => salesService.cancelQuote(id, 'Cancelamento em massa via seleção'), quoteSelection.clearSelection)}
                  title="Cancelar cotações selecionadas"
                >
                  <XCircle size={14} />
                  <span>Cancelar selecionadas</span>
                </button>
              </BulkActionsBar>
              <div className="table-container ui-table-wrap">
                <table className="data-table ui-table ui-table--wide">
                  <thead>
                    <tr>
                      <th className="ui-selection-cell">
                        <input className="ui-selection-checkbox" type="checkbox" aria-label="Selecionar cotações desta página" checked={quoteSelection.isAllSelected(quotePagination.pageItems)} onChange={() => quoteSelection.toggleSelectAll(quotePagination.pageItems)} />
                      </th>
                      <th>Cotação</th>
                      <th>Cliente</th>
                      <th>Emissão</th>
                      <th>Validade</th>
                      <th>Total Líquido</th>
                      <th>Status</th>
                      <th>Ações Comerciais</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredQuotes.length === 0 ? (
                      <tr>
                        <td colSpan={8} className="empty-state ui-empty-state">
                          Nenhuma cotação comercial encontrada.
                        </td>
                      </tr>
                    ) : (
                      quotePagination.pageItems.map(q => (
                        <tr
                          key={q.id}
                          onClick={(event) => {
                            if ((event.target as HTMLElement).closest('button, a, input, label, .ui-selection-cell')) return;
                            handleOpenQuoteModal(q);
                          }}
                          className={`ui-record-row ${quoteSelection.isSelected(q.id) ? 'ui-record-row--selected' : ''}`}
                          role="button"
                          tabIndex={0}
                          onKeyDown={(event) => { if (['Enter', ' '].includes(event.key)) { event.preventDefault(); handleOpenQuoteModal(q); } }}
                          title="Clique na linha para abrir/visualizar a cotação"
                        >
                          <td className="ui-selection-cell" onClick={(event) => event.stopPropagation()}>
                            <input
                              className="ui-selection-checkbox"
                              type="checkbox"
                              aria-label={`Selecionar cotação ${q.quote_number}`}
                              checked={quoteSelection.isSelected(q.id)}
                              onChange={() => quoteSelection.toggleSelect(q.id)}
                            />
                          </td>
                          <td><strong>#{q.quote_number}</strong></td>
                          <td>
                            <div className="cell-client">
                              <RecordLink type="CUSTOMER" id={q.customer_id} className="client-name">
                                {q.customer_name}
                              </RecordLink>
                              {q.customer_document && <span className="client-doc">{q.customer_document}</span>}
                            </div>
                          </td>
                          <td>{new Date(q.created_at).toLocaleDateString('pt-BR')}</td>
                          <td>{q.valid_until ? new Date(q.valid_until).toLocaleDateString('pt-BR') : '15 dias'}</td>
                          <td><strong>{fmtCurrency(q.net_amount)}</strong></td>
                          <td>
                            <span className={`status-pill ui-status ${
                              q.status === 'APPROVED' ? 'success' :
                              q.status === 'CONVERTED' ? 'info' :
                              q.status === 'SENT' ? 'warning' :
                              q.status === 'CANCELLED' ? 'danger' :
                              q.status === 'REJECTED' ? 'danger' : 'neutral'
                            }`}>
                              {q.status === 'CONVERTED' ? 'Convertido' :
                               q.status === 'APPROVED' ? 'Aprovado' :
                               q.status === 'SENT' ? 'Enviado' :
                               q.status === 'CANCELLED' ? 'Cancelado' :
                               q.status === 'DRAFT' ? 'Rascunho' : q.status}
                            </span>
                            {['PENDING', 'REJECTED'].includes(q.commercial_approval_status) && (
                              <span className={`status-pill ui-status ${q.commercial_approval_status === 'PENDING' ? 'warning' : 'danger'}`}>
                                {q.commercial_approval_status === 'PENDING' ? 'Alçada pendente' : 'Alçada rejeitada'}
                              </span>
                            )}
                          </td>
                          <td>
                            <div className="table-actions ui-table-actions" onClick={(e) => e.stopPropagation()}>
                              {q.status === 'DRAFT' && (
                                <>
                                  <button
                                    type="button"
                                    className="table-action-btn ui-table-action"
                                    onClick={(e) => { e.stopPropagation(); handleUpdateQuoteStatus(q, 'SENT'); }}
                                    title="Marcar como enviada ao cliente"
                                  >
                                    📤 Enviar
                                  </button>
                                  <button
                                    type="button"
                                    className="table-action-btn ui-table-action primary"
                                    onClick={(e) => { e.stopPropagation(); handleUpdateQuoteStatus(q, 'APPROVED'); }}
                                    title="Aprovar cotação"
                                    disabled={['PENDING', 'REJECTED'].includes(q.commercial_approval_status)}
                                  >
                                    ✅ Aprovar
                                  </button>
                                  <button
                                    type="button"
                                    className="table-action-btn ui-table-action danger"
                                    onClick={(e) => { e.stopPropagation(); setQuoteToCancel(q); setCancelReasonInput(''); }}
                                    title="Cancelar cotação"
                                  >
                                    ❌ Cancelar
                                  </button>
                                </>
                              )}
                              {q.status === 'SENT' && (
                                <>
                                  <button
                                    type="button"
                                    className="table-action-btn ui-table-action primary"
                                    onClick={(e) => { e.stopPropagation(); handleUpdateQuoteStatus(q, 'APPROVED'); }}
                                    title="Aceitar e aprovar proposta"
                                    disabled={['PENDING', 'REJECTED'].includes(q.commercial_approval_status)}
                                  >
                                    ✅ Aceitar
                                  </button>
                                  <button
                                    type="button"
                                    className="table-action-btn ui-table-action danger"
                                    onClick={(e) => { e.stopPropagation(); handleUpdateQuoteStatus(q, 'REJECTED'); }}
                                    title="Recusar proposta"
                                  >
                                    ❌ Recusar
                                  </button>
                                  <button
                                    type="button"
                                    className="table-action-btn ui-table-action danger"
                                    onClick={(e) => { e.stopPropagation(); setQuoteToCancel(q); setCancelReasonInput(''); }}
                                    title="Cancelar cotação por desistência"
                                  >
                                    ❌ Cancelar
                                  </button>
                                </>
                              )}
                              {q.status === 'APPROVED' && (
                                <>
                                  <button
                                    type="button"
                                    className="table-action-btn ui-table-action primary"
                                    onClick={(e) => { e.stopPropagation(); handleConvertToOrder(q); }}
                                    title="Converter em Pedido de Venda oficial"
                                    disabled={['PENDING', 'REJECTED'].includes(q.commercial_approval_status)}
                                  >
                                    <ArrowUpRight size={14} /> <strong>Converter em Pedido</strong>
                                  </button>
                                  <button
                                    type="button"
                                    className="table-action-btn ui-table-action danger"
                                    onClick={(e) => { e.stopPropagation(); setQuoteToCancel(q); setCancelReasonInput(''); }}
                                    title="Cancelar cotação aprovada por desistência"
                                  >
                                    ❌ Cancelar
                                  </button>
                                </>
                              )}
                              <button
                                type="button"
                                className="table-action-btn ui-table-action"
                                onClick={(e) => { e.stopPropagation(); void openDocumentTimeline('SALES_QUOTE', q.id, `Cotação #${q.quote_number}`); }}
                                title="Ver cadeia documental completa"
                              >
                                <GitBranch size={14} /> Rastrear
                              </button>
                              <button
                                type="button"
                                className="table-action-btn ui-table-action danger"
                                onClick={(e) => { e.stopPropagation(); handleDeleteQuote(q); }}
                                title="Excluir Cotação"
                              >
                                <Trash2 size={14} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
                <ListPagination {...quotePagination} onPageChange={quotePagination.setPage} onPageSizeChange={quotePagination.setPageSize} />
              </div>
            </div>
          )}

          {/* =============================================================== */}
          {/* ABA 2: PEDIDOS DE VENDA                                         */}
          {/* =============================================================== */}
          {activeTab === 'orders' && (
            <div className="tab-pane">
              <div className="toolbar ui-toolbar">
                <div className="search-box ui-search-box">
                  <Search size={16} />
                  <input
                    type="text"
                    placeholder="Buscar por número do pedido ou cliente..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>
                <div className="filter-group ui-filter-group">
                  <Filter size={14} />
                  <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                    <option value="ALL">Todos os Status</option>
                    <option value="CONFIRMED">Confirmado</option>
                    <option value="COMPLETED">Faturado / Concluído</option>
                    <option value="CANCELLED">Cancelado</option>
                  </select>
                </div>
              </div>

              <BulkActionsBar
                selectedCount={orderSelection.selectedCount}
                resourceName={{ singular: 'pedido', plural: 'pedidos' }}
                onClear={orderSelection.clearSelection}
                onDelete={() => openBulkAction('Excluir definitivamente', orderSelection.selectedIdList, (id) => salesService.deleteOrder(id, undefined, true), orderSelection.clearSelection)}
                deleteLabel="Excluir selecionados"
              >
                <button
                  type="button"
                  className="bulk-btn bulk-btn--warning"
                  onClick={() => openBulkAction('Cancelar', orderSelection.selectedIdList, (id) => salesService.deleteOrder(id, 'Cancelamento em massa via seleção', false), orderSelection.clearSelection)}
                  title="Cancelar pedidos selecionados"
                >
                  <XCircle size={14} />
                  <span>Cancelar selecionados</span>
                </button>
              </BulkActionsBar>
                  {/* Header e Seleção de Pedidos */}
                  {(() => {
                    const selectablePageOrders = orderPagination.pageItems.filter(o =>
                      o.status === 'CANCELLED' ||
                      (o.status !== 'COMPLETED' && !['INVOICED', 'PARTIALLY_INVOICED'].includes(o.billing_status) && !['DISPATCHED', 'DELIVERED'].includes(o.delivery_status))
                    );
                    return (
                      <div className="table-container ui-table-wrap">
                        <table className="data-table ui-table ui-table--wide">
                          <thead>
                            <tr>
                              <th className="ui-selection-cell">
                                <input
                                  className="ui-selection-checkbox"
                                  type="checkbox"
                                  aria-label="Selecionar pedidos desta página"
                                  checked={selectablePageOrders.length > 0 && orderSelection.isAllSelected(selectablePageOrders)}
                                  disabled={selectablePageOrders.length === 0}
                                  title={selectablePageOrders.length === 0 ? 'Nenhum pedido selecionável nesta página' : 'Selecionar todos os pedidos operáveis desta página'}
                                  onChange={() => orderSelection.toggleSelectAll(selectablePageOrders)}
                                />
                              </th>
                              <th>Pedido</th>
                              <th>Cliente</th>
                              <th>Emissão</th>
                              <th>Condição</th>
                              <th>Estoque / Execução</th>
                              <th>Faturamento</th>
                              <th>Crédito</th>
                              <th>Total Líquido</th>
                              <th>Status Geral</th>
                              <th>Ações Operacionais</th>
                            </tr>
                          </thead>
                          <tbody>
                            {filteredOrders.length === 0 ? (
                              <tr>
                                <td colSpan={11} className="empty-state ui-empty-state">
                                  Nenhum pedido de venda encontrado.
                                </td>
                              </tr>
                            ) : (
                              orderPagination.pageItems.map(o => {
                                const isCancellable = o.status !== 'CANCELLED' && o.status !== 'COMPLETED' && !['INVOICED', 'PARTIALLY_INVOICED'].includes(o.billing_status) && !['DISPATCHED', 'DELIVERED'].includes(o.delivery_status);
                                const isDeletable = o.status === 'CANCELLED';
                                const isSelectable = isCancellable || isDeletable;
                                return (
                                <tr
                                  key={o.id}
                                  onClick={(event) => {
                                    if ((event.target as HTMLElement).closest('button, a, input, label, .ui-selection-cell')) return;
                                    handleOpenOrderModal(o);
                                  }}
                                  className={`ui-record-row ${orderSelection.isSelected(o.id) ? 'ui-record-row--selected' : ''}`}
                                  role="button"
                                  tabIndex={0}
                                  onKeyDown={(event) => { if (['Enter', ' '].includes(event.key)) { event.preventDefault(); handleOpenOrderModal(o); } }}
                                  title="Clique na linha para abrir/editar o pedido"
                                >
                                  <td className="ui-selection-cell" onClick={(event) => event.stopPropagation()}>
                                    <input
                                      className="ui-selection-checkbox"
                                      type="checkbox"
                                      aria-label={`Selecionar pedido ${o.order_number}`}
                                      disabled={!isSelectable}
                                      title={
                                        o.status === 'COMPLETED' ? 'Pedido concluído com faturamento/entrega' :
                                        ['INVOICED', 'PARTIALLY_INVOICED'].includes(o.billing_status) ? 'Pedido com faturas ativas vinculadas' :
                                        ['DISPATCHED', 'DELIVERED'].includes(o.delivery_status) ? 'Pedido já despachado ou entregue' :
                                        o.status === 'CANCELLED' ? 'Selecionar pedido cancelado para exclusão definitiva' :
                                        'Selecionar pedido'
                                      }
                                      checked={orderSelection.isSelected(o.id)}
                                      onChange={() => orderSelection.toggleSelect(o.id)}
                                    />
                                  </td>
                          <td><strong>#{o.order_number}</strong></td>
                          <td>
                            <div className="cell-client">
                              <RecordLink type="CUSTOMER" id={o.customer_id} className="client-name">
                                {o.customer_name}
                              </RecordLink>
                              {o.customer_document && <span className="client-doc">{o.customer_document}</span>}
                            </div>
                          </td>
                          <td>{new Date(o.created_at).toLocaleDateString('pt-BR')}</td>
                          <td>{o.payment_terms || 'À Vista'}</td>
                          <td>
                            <span className={`status-pill ui-status ${
                              o.delivery_status === 'CANCELLED' ? 'danger' :
                              o.delivery_status === 'DELIVERED' ? 'success' :
                              o.delivery_status === 'DISPATCHED' ? 'info' :
                              o.delivery_status === 'RESERVED' ? 'info' : 'warning'
                            }`}>
                              {o.delivery_status === 'CANCELLED' ? 'Cancelado' :
                               o.delivery_status === 'DELIVERED' ? 'Entregue' :
                               o.delivery_status === 'DISPATCHED' ? 'Em Trânsito' :
                               o.delivery_status === 'RESERVED' ? 'Reservado' : 'Pendente'}
                            </span>
                          </td>
                          <td>
                            <span className={`status-pill ui-status ${o.billing_status === 'INVOICED' ? 'success' : o.billing_status === 'PARTIALLY_INVOICED' ? 'info' : 'warning'}`}>
                              {billingStatusLabel(o.billing_status)}
                            </span>
                          </td>
                          <td>
                            <span className={`status-pill ui-status ${
                              o.credit_status === 'APPROVED' ? 'success' :
                              o.credit_status === 'PENDING' ? 'warning' :
                              o.credit_status === 'REJECTED' ? 'danger' : 'info'
                            }`}>
                              {o.credit_status === 'APPROVED' ? 'Liberado' :
                               o.credit_status === 'PENDING' ? 'Em análise' :
                               o.credit_status === 'REJECTED' ? 'Rejeitado' : 'Não aplicável'}
                            </span>
                            <span className={`status-pill ui-status ${
                              o.commercial_approval_status === 'APPROVED' ? 'success' :
                              o.commercial_approval_status === 'PENDING' ? 'warning' :
                              o.commercial_approval_status === 'REJECTED' ? 'danger' : 'info'
                            }`}>
                              Comercial: {o.commercial_approval_status === 'APPROVED' ? 'Liberado' :
                               o.commercial_approval_status === 'PENDING' ? 'Em análise' :
                               o.commercial_approval_status === 'REJECTED' ? 'Rejeitado' : 'N/A'}
                            </span>
                          </td>
                          <td><strong>{fmtCurrency(o.net_amount)}</strong></td>
                          <td>
                            <span className={`status-pill ui-status ${
                              o.status === 'COMPLETED' ? 'success' :
                              o.status === 'CONFIRMED' ? 'info' :
                              o.status === 'CANCELLED' ? 'danger' : 'warning'
                            }`}>
                              {o.status === 'COMPLETED' ? 'Concluído' :
                               o.status === 'CONFIRMED' ? 'Confirmado' :
                               o.status === 'CANCELLED' ? 'Cancelado' : o.status}
                            </span>
                          </td>
                          <td>
                            <div className="table-actions ui-table-actions" onClick={(e) => e.stopPropagation()}>
                              {/* Ação 1: Reserva de Estoque */}
                              <Can permission="inventory:move">
                                {o.status === 'CONFIRMED' && o.delivery_status === 'PENDING'
                                  && !['PENDING', 'REJECTED'].includes(o.credit_status)
                                  && !['PENDING', 'REJECTED'].includes(o.commercial_approval_status) && (
                                  <button
                                    type="button"
                                    className="table-action-btn ui-table-action primary"
                                    onClick={(e) => { e.stopPropagation(); void handleReserveOrderStock(o); }}
                                    disabled={reservingOrderId !== null}
                                    title="Reservar estoque fisicamente no Kardex"
                                  >
                                    <Package size={14} />
                                    {reservingOrderId === o.id ? 'Reservando...' : 'Reservar'}
                                  </button>
                                )}
                              </Can>

                              {/* Ação 2: Solicitação ao domínio de Faturamento */}
                              {['PENDING', 'PARTIALLY_INVOICED'].includes(o.billing_status) && o.status !== 'CANCELLED'
                                && !['PENDING', 'REJECTED'].includes(o.credit_status)
                                && !['PENDING', 'REJECTED'].includes(o.commercial_approval_status) && (
                                <button
                                  type="button"
                                  className="table-action-btn ui-table-action primary"
                                  onClick={(e) => { e.stopPropagation(); void handleRequestBilling(o); }}
                                  disabled={billingOrderId === o.id}
                                  title="Enviar o saldo do pedido para a fila do Faturamento"
                                >
                                  <DollarSign size={14} />
                                  {billingOrderId === o.id ? 'Solicitando...' : 'Solicitar faturamento'}
                                </button>
                              )}

                              {/* Ação 3: Expedição e Entrega */}
                              {o.delivery_status === 'RESERVED' && (
                                <button
                                  type="button"
                                  className="table-action-btn ui-table-action"
                                  onClick={(e) => { e.stopPropagation(); handleUpdateOrderStatus(o, { delivery_status: 'DISPATCHED' }); }}
                                  title="Marcar pedido como despachado / em trânsito"
                                >
                                  <Truck size={14} /> Despachar
                                </button>
                              )}

                              {o.delivery_status === 'DISPATCHED' && (
                                <button
                                  type="button"
                                  className="table-action-btn ui-table-action success"
                                  onClick={(e) => { e.stopPropagation(); handleUpdateOrderStatus(o, { delivery_status: 'DELIVERED', status: 'COMPLETED' }); }}
                                  title="Confirmar entrega e concluir pedido"
                                >
                                  <Check size={14} /> Entregue
                                </button>
                              )}

                              {/* Ação 4: Rastrear Cadeia */}
                              <button
                                type="button"
                                className="table-action-btn ui-table-action"
                                onClick={(e) => { e.stopPropagation(); void openDocumentTimeline('SALES_ORDER', o.id, `Pedido #${o.order_number}`); }}
                                title="Ver cadeia documental ponta a ponta"
                              >
                                <GitBranch size={14} /> Rastrear
                              </button>

                              {/* Ação 5: Cancelar Pedido */}
                              {o.status !== 'CANCELLED' && o.status !== 'COMPLETED' && o.billing_status !== 'INVOICED' && o.billing_status !== 'PARTIALLY_INVOICED' && o.delivery_status !== 'DISPATCHED' && o.delivery_status !== 'DELIVERED' && (
                                <button
                                  type="button"
                                  className="table-action-btn ui-table-action danger"
                                  onClick={(e) => { e.stopPropagation(); handleDeleteOrder(o); }}
                                  title="Cancelar pedido"
                                >
                                  <XCircle size={14} />
                                </button>
                              )}

                              {/* Ação 6: Excluir Pedido Definitivamente */}
                              {o.status === 'CANCELLED' && (
                                <button
                                  type="button"
                                  className="table-action-btn ui-table-action danger"
                                  onClick={(e) => { e.stopPropagation(); handlePermanentDeleteOrder(o); }}
                                  title="Excluir pedido definitivamente"
                                >
                                  <Trash2 size={14} />
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
                <ListPagination {...orderPagination} onPageChange={orderPagination.setPage} onPageSizeChange={orderPagination.setPageSize} />
              </div>
            );
          })()}
        </div>
      )}

          {activeTab === 'approvals' && (
            <div className="tab-pane credit-approvals-pane">
              <h3 className="approval-section-title">Aprovações de crédito</h3>
              <div className="toolbar ui-toolbar">
                <div className="search-box ui-search-box">
                  <Search size={16} />
                  <input
                    type="text"
                    placeholder="Buscar por pedido ou cliente..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>
                <div className="filter-group ui-filter-group">
                  <Filter size={14} />
                  <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                    <option value="ALL">Todas as decisões</option>
                    <option value="PENDING">Pendentes</option>
                    <option value="APPROVED">Aprovadas</option>
                    <option value="REJECTED">Rejeitadas</option>
                    <option value="CANCELLED">Canceladas</option>
                  </select>
                </div>
              </div>

              <div className="table-container ui-table-wrap">
                <table className="data-table ui-table ui-table--wide">
                  <thead>
                    <tr>
                      <th>Pedido</th>
                      <th>Cliente</th>
                      <th>Limite</th>
                      <th>Já utilizado</th>
                      <th>Novo pedido</th>
                      <th>Excesso</th>
                      <th>Status</th>
                      <th>Decisão</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredCreditApprovals.map(item => (
                      <tr key={item.id}>
                        <td>
                          <RecordLink type="SALES_ORDER" id={item.order.id}>
                            <strong>#{item.order.order_number}</strong>
                          </RecordLink>
                        </td>
                        <td>
                          <RecordLink type="CUSTOMER" id={item.order.customer_id}>
                            {item.order.customer_name}
                          </RecordLink>
                        </td>
                        <td>{fmtCurrency(item.credit_limit)}</td>
                        <td>{fmtCurrency(item.exposure_before_order)}</td>
                        <td><strong>{fmtCurrency(item.order_amount)}</strong></td>
                        <td className="credit-excess-value">{fmtCurrency(item.excess_amount)}</td>
                        <td>
                          <span className={`status-pill ui-status ${
                            item.status === 'APPROVED' ? 'success' :
                            item.status === 'REJECTED' || item.status === 'CANCELLED' ? 'danger' : 'warning'
                          }`}>
                            {item.status === 'APPROVED' ? 'Aprovado' :
                             item.status === 'REJECTED' ? 'Rejeitado' :
                             item.status === 'CANCELLED' ? 'Cancelado' : 'Pendente'}
                          </span>
                        </td>
                        <td>
                          {item.status === 'PENDING' ? (
                            <Can permission="sales:credit:approve" fallback={<span className="text-muted">Sem alçada</span>}>
                              <div className="table-actions ui-table-actions">
                                <button
                                  type="button"
                                  className="table-action-btn ui-table-action success"
                                  onClick={() => {
                                    setCreditDecision({ approval: item, approved: true });
                                    setCreditDecisionReason('');
                                  }}
                                >
                                  <Check size={14} /> Aprovar
                                </button>
                                <button
                                  type="button"
                                  className="table-action-btn ui-table-action danger"
                                  onClick={() => {
                                    setCreditDecision({ approval: item, approved: false });
                                    setCreditDecisionReason('');
                                  }}
                                >
                                  <XCircle size={14} /> Rejeitar
                                </button>
                              </div>
                            </Can>
                          ) : (
                            <span className="text-muted">{item.decision_reason || 'Decisão registrada'}</span>
                          )}
                        </td>
                      </tr>
                    ))}
                    {filteredCreditApprovals.length === 0 && (
                      <tr>
                        <td colSpan={8} className="empty-state ui-empty-state">
                          Nenhuma solicitação de crédito encontrada.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              <h3 className="approval-section-title">Exceções comerciais</h3>
              <div className="table-container ui-table-wrap">
                <table className="data-table ui-table ui-table--wide">
                  <thead>
                    <tr>
                      <th>Documento</th>
                      <th>Cliente</th>
                      <th>Regra</th>
                      <th>Valor</th>
                      <th>Limite</th>
                      <th>Status</th>
                      <th>Decisão</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredCommercialApprovals.map(item => {
                      const number = item.quote?.quote_number || item.order?.order_number || '—';
                      const customer = item.quote?.customer_name || item.order?.customer_name || '—';
                      const typeLabel = item.approval_type === 'DISCOUNT'
                        ? 'Desconto' : item.approval_type === 'MARGIN' ? 'Margem' : 'Prazo';
                      const suffix = item.approval_type === 'PAYMENT_TERM' ? ' dias' : '%';
                      const customerId = item.quote?.customer_id || item.order?.customer_id;
                      return (
                        <tr key={item.id}>
                          <td>
                            {item.quote ? (
                              <RecordLink type="SALES_QUOTE" id={item.quote.id}>
                                <strong>#{item.quote.quote_number}</strong>
                              </RecordLink>
                            ) : item.order ? (
                              <RecordLink type="SALES_ORDER" id={item.order.id}>
                                <strong>#{item.order.order_number}</strong>
                              </RecordLink>
                            ) : (
                              <strong>#{number}</strong>
                            )}
                            <br /><small>{item.quote ? 'Orçamento' : 'Pedido'}</small>
                          </td>
                          <td>
                            <RecordLink type="CUSTOMER" id={customerId}>
                              {customer}
                            </RecordLink>
                          </td>
                          <td>{typeLabel}</td>
                          <td><strong>{safeNumber(item.metric_value).toFixed(2)}{suffix}</strong></td>
                          <td>{safeNumber(item.threshold_value).toFixed(2)}{suffix}</td>
                          <td>
                            <span className={`status-pill ui-status ${
                              item.status === 'APPROVED' ? 'success' :
                              item.status === 'REJECTED' || item.status === 'CANCELLED' ? 'danger' : 'warning'
                            }`}>
                              {item.status === 'APPROVED' ? 'Aprovado' :
                               item.status === 'REJECTED' ? 'Rejeitado' :
                               item.status === 'CANCELLED' ? 'Cancelado' : 'Pendente'}
                            </span>
                          </td>
                          <td>
                            {item.status === 'PENDING' ? (
                              <Can permission="sales:approvals:approve" fallback={<span className="text-muted">Sem alçada</span>}>
                                <div className="table-actions ui-table-actions">
                                  <button type="button" className="table-action-btn ui-table-action success" onClick={() => {
                                    setCommercialDecision({ approval: item, approved: true });
                                    setCommercialDecisionReason('');
                                  }}><Check size={14} /> Aprovar</button>
                                  <button type="button" className="table-action-btn ui-table-action danger" onClick={() => {
                                    setCommercialDecision({ approval: item, approved: false });
                                    setCommercialDecisionReason('');
                                  }}><XCircle size={14} /> Rejeitar</button>
                                </div>
                              </Can>
                            ) : <span className="text-muted">{item.decision_reason || 'Decisão registrada'}</span>}
                          </td>
                        </tr>
                      );
                    })}
                    {filteredCommercialApprovals.length === 0 && (
                      <tr><td colSpan={7} className="empty-state ui-empty-state">Nenhuma exceção comercial encontrada.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* =============================================================== */}
          {/* NOVA ABA: ENTREGAS & EXPEDIÇÃO (LOGÍSTICA)                      */}
          {/* =============================================================== */}
          {activeTab === 'deliveries' && (
            <div className="tab-pane">
              <div className="toolbar ui-toolbar">
                <div className="search-box ui-search-box">
                  <Search size={16} />
                  <input
                    type="text"
                    placeholder="Buscar por número do pedido ou cliente para entrega..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>
                <div className="filter-group ui-filter-group">
                  <Filter size={14} />
                  <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                    <option value="ALL">Todas as Entregas</option>
                    <option value="PENDING">Aguardando Reserva</option>
                    <option value="RESERVED">Pronto para Despacho</option>
                    <option value="DISPATCHED">Em Trânsito</option>
                    <option value="DELIVERED">Entregue</option>
                  </select>
                </div>
              </div>

              <div className="table-container ui-table-wrap">
                <table className="data-table ui-table ui-table--wide">
                  <thead>
                    <tr>
                      <th>Pedido</th>
                      <th>Cliente</th>
                      <th>Endereço / Observações de Entrega</th>
                      <th>Status da Entrega</th>
                      <th>Faturamento</th>
                      <th>Emissão</th>
                      <th>Ações de Logística</th>
                    </tr>
                  </thead>
                  <tbody>
                    {orders
                      .filter(o => {
                        if (statusFilter !== 'ALL' && o.delivery_status !== statusFilter) return false;
                        if (searchTerm) {
                          const term = searchTerm.toLowerCase();
                          return o.order_number.toLowerCase().includes(term) || o.customer_name.toLowerCase().includes(term);
                        }
                        return true;
                      })
                      .map(o => (
                        <tr
                          key={o.id}
                          onClick={() => handleOpenOrderModal(o)}
                          style={{ cursor: 'pointer' }}
                          title="Clique na linha para abrir/visualizar o pedido"
                        >
                          <td>
                            <RecordLink type="SALES_ORDER" id={o.id}>
                              <strong>#{o.order_number}</strong>
                            </RecordLink>
                          </td>
                          <td>
                            <div className="cell-client">
                              <RecordLink type="CUSTOMER" id={o.customer_id} className="client-name">
                                {o.customer_name}
                              </RecordLink>
                              {o.customer_document && <span className="client-doc">{o.customer_document}</span>}
                            </div>
                          </td>
                          <td>
                            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                              {o.notes || 'Endereço cadastral do cliente'}
                            </span>
                          </td>
                          <td>
                            <span className={`status-pill ui-status ${
                              o.delivery_status === 'CANCELLED' ? 'danger' :
                              o.delivery_status === 'DELIVERED' ? 'success' :
                              o.delivery_status === 'DISPATCHED' ? 'info' :
                              o.delivery_status === 'RESERVED' ? 'info' : 'warning'
                            }`}>
                              {o.delivery_status === 'CANCELLED' ? 'Cancelado' :
                               o.delivery_status === 'DELIVERED' ? 'Entregue' :
                               o.delivery_status === 'DISPATCHED' ? 'Em Trânsito' :
                               o.delivery_status === 'RESERVED' ? 'Pronto para Envio' : 'Aguardando Reserva'}
                            </span>
                          </td>
                          <td>
                            <span className={`status-pill ui-status ${o.billing_status === 'INVOICED' ? 'success' : o.billing_status === 'PARTIALLY_INVOICED' ? 'info' : 'warning'}`}>
                              {billingStatusLabel(o.billing_status)}
                            </span>
                          </td>
                          <td>{new Date(o.created_at).toLocaleDateString('pt-BR')}</td>
                          <td>
                            <div className="table-actions ui-table-actions" onClick={(e) => e.stopPropagation()}>
                              {o.delivery_status === 'PENDING' && o.status === 'CONFIRMED' && (
                                <button
                                  type="button"
                                  className="table-action-btn ui-table-action primary"
                                  onClick={(e) => { e.stopPropagation(); void handleReserveOrderStock(o); }}
                                  disabled={reservingOrderId !== null}
                                  title="Reservar produtos para expedição"
                                >
                                  <Package size={14} /> Reservar
                                </button>
                              )}

                              {o.delivery_status === 'RESERVED' && (
                                <button
                                  type="button"
                                  className="table-action-btn ui-table-action primary"
                                  onClick={(e) => { e.stopPropagation(); handleUpdateOrderStatus(o, { delivery_status: 'DISPATCHED' }); }}
                                  title="Despachar entrega"
                                >
                                  <Truck size={14} /> Despachar
                                </button>
                              )}

                              {o.delivery_status === 'DISPATCHED' && (
                                <button
                                  type="button"
                                  className="table-action-btn ui-table-action success"
                                  onClick={(e) => { e.stopPropagation(); handleUpdateOrderStatus(o, { delivery_status: 'DELIVERED', status: 'COMPLETED' }); }}
                                  title="Confirmar que o cliente recebeu a mercadoria"
                                >
                                  <Check size={14} /> Confirmar Entrega
                                </button>
                              )}

                              <button
                                type="button"
                                className="table-action-btn ui-table-action"
                                onClick={(e) => { e.stopPropagation(); void openDocumentTimeline('SALES_ORDER', o.id, `Pedido #${o.order_number}`); }}
                                title="Ver linha do tempo documental"
                              >
                                <GitBranch size={14} /> Rastrear
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* =============================================================== */}
          {/* ABA 3: CLIENTES (PJ / PF)                                       */}
          {/* =============================================================== */}
          {activeTab === 'customers' && (
            <div className="tab-pane">
              <div className="toolbar ui-toolbar">
                <div className="search-box ui-search-box">
                  <Search size={16} />
                  <input
                    type="text"
                    placeholder="Buscar por Razão Social, CNPJ/CPF, E-mail ou Cidade..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>
                <div className="filter-group ui-filter-group">
                  <Filter size={14} />
                  <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
                    <option value="ALL">Todos os Tipos</option>
                    <option value="PJ">Pessoa Jurídica (PJ)</option>
                    <option value="PF">Pessoa Física (PF)</option>
                  </select>
                </div>
              </div>

              <BulkActionsBar
                selectedCount={customerSelection.selectedCount}
                resourceName={{ singular: 'cliente', plural: 'clientes' }}
                onClear={customerSelection.clearSelection}
                onDelete={() => openBulkAction('Excluir', customerSelection.selectedIdList, salesService.deleteCustomer, customerSelection.clearSelection)}
                deleteLabel="Excluir selecionados"
              />
              <div className="table-container ui-table-wrap">
                <table className="data-table ui-table ui-table--wide">
                  <thead>
                    <tr>
                      <th className="ui-selection-cell"><input className="ui-selection-checkbox" type="checkbox" aria-label="Selecionar clientes desta página" checked={customerSelection.isAllSelected(customerPagination.pageItems)} onChange={() => customerSelection.toggleSelectAll(customerPagination.pageItems)} /></th>
                      <th>Tipo</th>
                      <th>Cliente / Razão Social</th>
                      <th>CNPJ / CPF</th>
                      <th>Contato Principal</th>
                      <th>Cidade / UF</th>
                      <th>Limite Crédito</th>
                      <th>Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredCustomers.length === 0 ? (
                      <tr>
                        <td colSpan={8} className="empty-state ui-empty-state">
                          Nenhum cliente cadastrado no módulo de vendas.
                        </td>
                      </tr>
                    ) : (
                      customerPagination.pageItems.map(c => (
                        <tr
                          key={c.id}
                          onClick={(event) => {
                            if ((event.target as HTMLElement).closest('button, a, input, label, .ui-selection-cell')) return;
                            handleOpenCustomerModal(c);
                          }}
                          className={`ui-record-row ${customerSelection.isSelected(c.id) ? 'ui-record-row--selected' : ''}`}
                          role="button"
                          tabIndex={0}
                          onKeyDown={(event) => { if (['Enter', ' '].includes(event.key)) { event.preventDefault(); handleOpenCustomerModal(c); } }}
                          title="Clique na linha para abrir/editar os dados do cliente"
                        >
                          <td className="ui-selection-cell" onClick={(event) => event.stopPropagation()}>
                            <input
                              className="ui-selection-checkbox"
                              type="checkbox"
                              aria-label={`Selecionar cliente ${c.name}`}
                              checked={customerSelection.isSelected(c.id)}
                              onChange={() => customerSelection.toggleSelect(c.id)}
                            />
                          </td>
                          <td>
                            <span className={`person-badge ${c.person_type.toLowerCase()}`}>
                              {c.person_type}
                            </span>
                          </td>
                          <td>
                            <div className="cell-client">
                              <span className="client-name">{c.name}</span>
                              {c.trade_name && <span className="client-doc">Nome Fantasia: {c.trade_name}</span>}
                            </div>
                          </td>
                          <td><strong>{c.document}</strong></td>
                          <td>
                            <div className="cell-contact">
                              <span>{c.email || '-'}</span>
                              <span className="sub">{c.phone || '-'}</span>
                            </div>
                          </td>
                          <td>{c.address_city ? `${c.address_city}/${c.address_state}` : '-'}</td>
                          <td><strong>{fmtCurrency(c.credit_limit)}</strong></td>
                          <td>
                            <div className="table-actions ui-table-actions" onClick={(e) => e.stopPropagation()}>
                              <button
                                type="button"
                                className="table-action-btn ui-table-action danger"
                                onClick={(e) => { e.stopPropagation(); handleDeleteCustomer(c); }}
                                title="Excluir Cliente"
                              >
                                <Trash2 size={14} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
                <ListPagination {...customerPagination} onPageChange={customerPagination.setPage} onPageSizeChange={customerPagination.setPageSize} />
              </div>
            </div>
          )}

          {/* =============================================================== */}
          {/* ABA 4: GESTÃO COMERCIAL (METAS & TABELAS DE PREÇOS)              */}
          {/* =============================================================== */}
          {activeTab === 'commercial' && (
            <div className="tab-pane commercial-pane">
              <div className="commercial-subgrid ui-section-stack">
                {/* Seção 1: Metas por Vendedor */}
                <div className="subgrid-card ui-section">
                  <div className="card-header-row ui-section__header">
                    <h3><Target size={16} /> Metas Comerciais por Vendedor ({yearFilter})</h3>
                    <select
                      value={yearFilter}
                      onChange={(e) => setYearFilter(Number(e.target.value))}
                      className="year-picker ui-field ui-field--select"
                    >
                      <option value={2025}>Ano 2025</option>
                      <option value={2026}>Ano 2026</option>
                      <option value={2027}>Ano 2027</option>
                    </select>
                  </div>

                  <BulkActionsBar
                    selectedCount={goalSelection.selectedCount}
                    resourceName={{ singular: 'meta', plural: 'metas' }}
                    onClear={goalSelection.clearSelection}
                    onDelete={() => openBulkAction('Excluir', goalSelection.selectedIdList, salesService.deleteSalesGoal, goalSelection.clearSelection)}
                    deleteLabel="Excluir selecionadas"
                  />

                  <div className="table-container mini ui-table-wrap">
                    <table className="data-table ui-table">
                      <thead>
                        <tr>
                          <th className="ui-selection-cell">
                            <input
                              className="ui-selection-checkbox"
                              type="checkbox"
                              aria-label="Selecionar todas as metas comerciais"
                              checked={goalSelection.isAllSelected(salesGoals)}
                              disabled={salesGoals.length === 0}
                              onChange={() => goalSelection.toggleSelectAll(salesGoals)}
                            />
                          </th>
                          <th>Vendedor</th>
                          <th>Mês</th>
                          <th>Meta R$</th>
                          <th>Comissão %</th>
                          <th>Ações</th>
                        </tr>
                      </thead>
                      <tbody>
                        {salesGoals.length === 0 ? (
                          <tr>
                            <td colSpan={6} className="empty-state ui-empty-state">
                              Nenhuma meta comercial cadastrada para {yearFilter}.
                            </td>
                          </tr>
                        ) : (
                          salesGoals.map(g => (
                            <tr key={g.id} className={goalSelection.isSelected(g.id) ? 'ui-record-row--selected' : ''}>
                              <td className="ui-selection-cell" onClick={(e) => e.stopPropagation()}>
                                <input
                                  className="ui-selection-checkbox"
                                  type="checkbox"
                                  aria-label={`Selecionar meta do vendedor ${g.seller_name || ''}`}
                                  checked={goalSelection.isSelected(g.id)}
                                  onChange={() => goalSelection.toggleSelect(g.id)}
                                />
                              </td>
                              <td><strong>{g.seller_name || 'Vendedor'}</strong></td>
                              <td>Mês {g.month}</td>
                              <td><strong>{fmtCurrency(g.target_amount)}</strong></td>
                              <td>{fmtPercent(g.commission_percent)}</td>
                              <td>
                                <button
                                  type="button"
                                  className="table-action-btn ui-table-action danger"
                                  onClick={() => handleDeleteGoal(g)}
                                  title="Excluir Meta"
                                >
                                  <Trash2 size={14} />
                                </button>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Seção 2: Tabelas de Preços */}
                <div className="subgrid-card ui-section">
                  <div className="card-header-row ui-section__header">
                    <h3><Layers size={16} /> Tabelas de Preços Personalizadas</h3>
                  </div>

                  <BulkActionsBar
                    selectedCount={priceTableSelection.selectedCount}
                    resourceName={{ singular: 'tabela', plural: 'tabelas' }}
                    onClear={priceTableSelection.clearSelection}
                    onDelete={() => openBulkAction('Excluir', priceTableSelection.selectedIdList, salesService.deletePriceTable, priceTableSelection.clearSelection)}
                    deleteLabel="Excluir selecionadas"
                  />

                  <div className="table-container mini ui-table-wrap">
                    <table className="data-table ui-table">
                      <thead>
                        <tr>
                          <th className="ui-selection-cell">
                            <input
                              className="ui-selection-checkbox"
                              type="checkbox"
                              aria-label="Selecionar todas as tabelas de preços"
                              checked={priceTableSelection.isAllSelected(priceTables)}
                              disabled={priceTables.length === 0}
                              onChange={() => priceTableSelection.toggleSelectAll(priceTables)}
                            />
                          </th>
                          <th>Nome da Tabela</th>
                          <th>Descrição</th>
                          <th>Padrão</th>
                          <th>Status</th>
                          <th>Ações</th>
                        </tr>
                      </thead>
                      <tbody>
                        {priceTables.length === 0 ? (
                          <tr>
                            <td colSpan={6} className="empty-state ui-empty-state">
                              Nenhuma tabela de preços cadastrada.
                            </td>
                          </tr>
                        ) : (
                          priceTables.map(t => (
                            <tr key={t.id} className={priceTableSelection.isSelected(t.id) ? 'ui-record-row--selected' : ''}>
                              <td className="ui-selection-cell" onClick={(e) => e.stopPropagation()}>
                                <input
                                  className="ui-selection-checkbox"
                                  type="checkbox"
                                  aria-label={`Selecionar tabela ${t.name}`}
                                  checked={priceTableSelection.isSelected(t.id)}
                                  onChange={() => priceTableSelection.toggleSelect(t.id)}
                                />
                              </td>
                              <td><strong>{t.name}</strong></td>
                              <td>{t.description || '-'}</td>
                              <td>
                                <span className={`status-pill ui-status ${t.is_default ? 'success' : 'info'}`}>
                                  {t.is_default ? 'Sim' : 'Não'}
                                </span>
                              </td>
                              <td>
                                <span className={`status-pill ui-status ${t.is_active ? 'success' : 'danger'}`}>
                                  {t.is_active ? 'Ativa' : 'Inativa'}
                                </span>
                              </td>
                              <td>
                                <button
                                  type="button"
                                  className="table-action-btn ui-table-action danger"
                                  onClick={() => handleDeletePriceTable(t)}
                                  title="Excluir Tabela"
                                >
                                  <Trash2 size={14} />
                                </button>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* =============================================================== */}
          {/* ABA 5: PÓS-VENDA & DEVOLUÇÕES                                   */}
          {/* =============================================================== */}
          {activeTab === 'post_sales' && (
            <div className="tab-pane">
              <div className="toolbar ui-toolbar">
                <div className="search-box ui-search-box">
                  <Search size={16} />
                  <input
                    type="text"
                    placeholder="Buscar por cliente ou motivo da devolução..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>
                <div className="filter-group ui-filter-group">
                  <Filter size={14} />
                  <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
                    <option value="ALL">Todos os Tipos</option>
                    <option value="DEVOLUCAO">Devolução</option>
                    <option value="TROCA">Troca</option>
                    <option value="CANCELAMENTO">Cancelamento</option>
                  </select>
                </div>
              </div>

              <BulkActionsBar
                selectedCount={returnSelection.selectedCount}
                resourceName={{ singular: 'registro', plural: 'registros' }}
                onClear={returnSelection.clearSelection}
                onDelete={() => openBulkAction('Excluir', returnSelection.selectedIdList, salesService.deleteSalesReturn, returnSelection.clearSelection)}
                deleteLabel="Excluir selecionados"
              />
              <div className="table-container ui-table-wrap">
                <table className="data-table ui-table ui-table--wide">
                  <thead>
                    <tr>
                      <th className="ui-selection-cell"><input className="ui-selection-checkbox" type="checkbox" aria-label="Selecionar registros desta página" checked={returnSelection.isAllSelected(returnPagination.pageItems)} onChange={() => returnSelection.toggleSelectAll(returnPagination.pageItems)} /></th>
                      <th>Tipo</th>
                      <th>Cliente</th>
                      <th>Data</th>
                      <th>Motivo</th>
                      <th>Reestocado</th>
                      <th>Valor Estornado</th>
                      <th>Status</th>
                      <th>Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredReturns.length === 0 ? (
                      <tr>
                        <td colSpan={9} className="empty-state ui-empty-state">
                          Nenhum registro de pós-venda encontrado.
                        </td>
                      </tr>
                    ) : (
                      returnPagination.pageItems.map(r => (
                        <tr
                          key={r.id}
                          className={`ui-record-row ${returnSelection.isSelected(r.id) ? 'ui-record-row--selected' : ''}`}
                          role="button"
                          tabIndex={0}
                          onClick={(event) => {
                            if ((event.target as HTMLElement).closest('button, a, input, label, .ui-selection-cell')) return;
                            setSelectedReturn(r);
                          }}
                          onKeyDown={(event) => {
                            if (event.key === 'Enter' || event.key === ' ') {
                              event.preventDefault();
                              setSelectedReturn(r);
                            }
                          }}
                        >
                          <td className="ui-selection-cell" onClick={(event) => event.stopPropagation()}>
                            <input
                              className="ui-selection-checkbox"
                              type="checkbox"
                              aria-label={`Selecionar registro de ${r.customer_name}`}
                              checked={returnSelection.isSelected(r.id)}
                              onChange={() => returnSelection.toggleSelect(r.id)}
                            />
                          </td>
                          <td>
                            <span className={`status-pill ui-status ${
                              r.return_type === 'DEVOLUCAO' ? 'danger' :
                              r.return_type === 'TROCA' ? 'info' : 'warning'
                            }`}>
                              {r.return_type}
                            </span>
                          </td>
                          <td>
                            <RecordLink type="CUSTOMER" id={r.customer_id}>
                              <strong>{r.customer_name}</strong>
                            </RecordLink>
                          </td>
                          <td>{new Date(r.created_at).toLocaleDateString('pt-BR')}</td>
                          <td>{r.reason}</td>
                          <td>
                            <span className={`status-pill ui-status ${r.restock_items ? 'success' : 'danger'}`}>
                              {r.restock_items ? 'Sim (Kardex)' : 'Não'}
                            </span>
                          </td>
                          <td><strong>{fmtCurrency(r.total_amount)}</strong></td>
                          <td>
                            <span className={`status-pill ui-status ${
                              r.status === 'COMPLETED' ? 'success' :
                              r.status === 'REJECTED' ? 'danger' : 'warning'
                            }`}>
                              {r.status}
                            </span>
                          </td>
                          <td>
                            <button
                              type="button"
                              className="table-action-btn ui-table-action danger"
                              onClick={(event) => { event.stopPropagation(); handleDeleteReturn(r); }}
                              title="Excluir Registro"
                            >
                              <Trash2 size={14} />
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
                <ListPagination {...returnPagination} onPageChange={returnPagination.setPage} onPageSizeChange={returnPagination.setPageSize} />
              </div>
            </div>
          )}

          {/* =============================================================== */}
          {/* ABA 6: INDICADORES & BI COMERCIAL                               */}
          {/* =============================================================== */}
          {activeTab === 'analytics' && (
            <div className="tab-pane analytics-pane tab-analytics-container">
              {/* Cards de Métricas Principais */}
              <div className="kpi-grid ui-kpi-grid">
                <div className="kpi-card ui-kpi-card ui-kpi-card--success">
                  <div className="kpi-header ui-kpi-card__header">
                    <span className="label ui-kpi-card__label">Faturamento Total Comercial</span>
                    <DollarSign size={18} className="icon green ui-kpi-card__icon" />
                  </div>
                  <div className="kpi-value ui-kpi-card__value">{fmtCurrency(analytics?.total_revenue || 0)}</div>
                  <span className="kpi-sub ui-kpi-card__sub">Receita consolidada de pedidos no período</span>
                </div>

                <div className="kpi-card ui-kpi-card ui-kpi-card--info">
                  <div className="kpi-header ui-kpi-card__header">
                    <span className="label ui-kpi-card__label">Ticket Médio por Pedido</span>
                    <TrendingUp size={18} className="icon blue ui-kpi-card__icon" />
                  </div>
                  <div className="kpi-value ui-kpi-card__value">{fmtCurrency(analytics?.average_ticket || 0)}</div>
                  <span className="kpi-sub ui-kpi-card__sub">Média líquida por transação comercial</span>
                </div>

                <div className="kpi-card ui-kpi-card ui-kpi-card--purple">
                  <div className="kpi-header ui-kpi-card__header">
                    <span className="label ui-kpi-card__label">Taxa de Conversão de Cotações</span>
                    <Award size={18} className="icon purple ui-kpi-card__icon" />
                  </div>
                  <div className="kpi-value ui-kpi-card__value">{fmtPercent(analytics?.quote_conversion_rate || 0)}</div>
                  <span className="kpi-sub ui-kpi-card__sub">Propostas convertidas em pedidos</span>
                </div>

                <div className="kpi-card ui-kpi-card ui-kpi-card--warning">
                  <div className="kpi-header ui-kpi-card__header">
                    <span className="label ui-kpi-card__label">Volume Total de Vendas</span>
                    <ShoppingBag size={18} className="icon amber ui-kpi-card__icon" />
                  </div>
                  <div className="kpi-value ui-kpi-card__value">{orders.length}</div>
                  <span className="kpi-sub ui-kpi-card__sub">Pedidos emitidos no período</span>
                </div>
              </div>

              <section className="ui-chart-panel" aria-labelledby="sales-products-chart-title">
                <div className="ui-chart-panel__header">
                  <h3 id="sales-products-chart-title">Receita dos Produtos Mais Vendidos</h3>
                  <p>Comparativo de faturamento dos cinco produtos com maior receita.</p>
                </div>

                {(!analytics?.top_selling_products || analytics.top_selling_products.length === 0) ? (
                  <div className="ui-empty-state">
                    Ainda não existem vendas de produtos suficientes para gerar o gráfico.
                  </div>
                ) : (
                  <div
                    className="ui-chart-panel__canvas"
                    role="img"
                    aria-label="Gráfico de barras da receita dos produtos mais vendidos"
                  >
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={analytics.top_selling_products.map(product => ({
                          name: product.product_name,
                          revenue: safeNumber(product.total_revenue)
                        }))}
                        layout="vertical"
                        margin={{ top: 8, right: 24, bottom: 8, left: 8 }}
                      >
                        <CartesianGrid
                          stroke="var(--border-subtle)"
                          strokeDasharray="3 3"
                          horizontal={false}
                        />
                        <XAxis
                          type="number"
                          axisLine={false}
                          tickLine={false}
                          tickFormatter={(value) => fmtCompactCurrency(value)}
                        />
                        <YAxis
                          type="category"
                          dataKey="name"
                          width={190}
                          axisLine={false}
                          tickLine={false}
                          tickFormatter={(value: string) => (
                            value.length > 28 ? `${value.slice(0, 28)}…` : value
                          )}
                        />
                        <Tooltip
                          cursor={{ fill: 'var(--bg-surface-hover)' }}
                          contentStyle={{
                            background: 'var(--bg-surface-elevated)',
                            border: '1px solid var(--border-highlight)',
                            borderRadius: '6px',
                            color: 'var(--text-primary)',
                            fontSize: '0.8rem'
                          }}
                          labelStyle={{ color: 'var(--text-primary)', fontWeight: 600 }}
                          formatter={(value) => [fmtCurrency(safeNumber(value as number)), 'Receita']}
                        />
                        <Bar
                          dataKey="revenue"
                          name="Receita"
                          fill="var(--accent-brand)"
                          radius={[0, 5, 5, 0]}
                          maxBarSize={30}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </section>

              {/* Ranking e Desempenho */}
              <div className="analytics-details-grid ui-panel-grid">
                <div className="details-card ui-panel">
                  <h3>Top 5 Produtos Mais Vendidos</h3>
                  {(!analytics?.top_selling_products || analytics.top_selling_products.length === 0) ? (
                    <p className="empty-sub ui-empty-state">Nenhuma movimentação de produto registrada.</p>
                  ) : (
                    <div className="ui-table-wrap ui-table-wrap--embedded">
                    <table className="data-table ui-table">
                      <thead>
                        <tr>
                          <th>Produto</th>
                          <th>Qtd Vendida</th>
                          <th>Receita Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {analytics.top_selling_products.map((p, idx) => (
                          <tr key={idx}>
                            <td><strong>{p.product_name}</strong></td>
                            <td>{formatQuantity(p.total_quantity_sold)}</td>
                            <td><strong>{fmtCurrency(p.total_revenue)}</strong></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    </div>
                  )}
                </div>

                <div className="details-card ui-panel">
                  <h3>Desempenho da Equipe Comercial</h3>
                  {(!analytics?.seller_performance || analytics.seller_performance.length === 0) ? (
                    <p className="empty-sub ui-empty-state">Nenhuma meta apurada para a equipe comercial.</p>
                  ) : (
                    <div className="ui-table-wrap ui-table-wrap--embedded">
                    <table className="data-table ui-table">
                      <thead>
                        <tr>
                          <th>Vendedor</th>
                          <th>Meta R$</th>
                          <th>Realizado R$</th>
                          <th>Atingimento</th>
                        </tr>
                      </thead>
                      <tbody>
                        {analytics.seller_performance.map((s, idx) => (
                          <tr key={idx}>
                            <td><strong>{s.seller_name}</strong></td>
                            <td>{fmtCurrency(s.target_amount)}</td>
                            <td>{fmtCurrency(s.total_sales_amount)}</td>
                            <td>
                              <div className="progress-cell ui-progress">
                                <span>{fmtPercent(s.achievement_percent)}</span>
                                <div className="progress-bar-bg ui-progress__track">
                                  <div
                                    className="progress-bar-fill ui-progress__fill"
                                    style={{ width: `${Math.min(100, safeNumber(s.achievement_percent))}%` }}
                                  ></div>
                                </div>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'settings' && (
            <div className="tab-pane sales-settings-pane">
              <CommercialPoliciesSettings />
              <CommercialTeamsSettings />
            </div>
          )}
        </main>
      </div>

      {/* =================================================================== */}
      {/* MODAIS DO MÓDULO DE VENDAS                                          */}
      {/* =================================================================== */}

      {/* Modal 1: Cotação Comercial Unificada */}
      <QuoteModal
        isOpen={isQuoteModalOpen}
        onClose={() => {
          setIsQuoteModalOpen(false);
          setEditingQuote(null);
        }}
        quote={editingQuote}
        onSuccess={() => {
          triggerSuccess(editingQuote ? "Cotação comercial atualizada com sucesso!" : "Cotação comercial emitida com sucesso!");
          loadAllData(true);
        }}
      />

      {/* Modal 2: Novo Pedido de Venda Canônico (Wizard Multietapas) */}
      <OrderModal
        isOpen={isOrderModalOpen}
        onClose={() => {
          setIsOrderModalOpen(false);
          setEditingOrder(null);
        }}
        order={editingOrder}
        onSuccess={() => {
          triggerSuccess(editingOrder ? "Pedido atualizado com sucesso!" : "Pedido de venda emitido com sucesso!");
          loadAllData(true);
        }}
      />

      {/* Modal 3: Cadastro / Edição de Cliente Unificado */}
      <Modal
        isOpen={creditDecision !== null}
        onClose={() => {
          if (creditDecisionSaving) return;
          setCreditDecision(null);
          setCreditDecisionReason('');
        }}
        title={creditDecision?.approved ? 'Aprovar Crédito do Pedido' : 'Rejeitar Crédito do Pedido'}
        subtitle={creditDecision ? `Pedido #${creditDecision.approval.order.order_number} · Excesso de ${fmtCurrency(creditDecision.approval.excess_amount)}` : undefined}
        size="sm"
      >
        <div className="wizard-form ui-form credit-decision-modal">
          <div className="credit-decision-summary">
            <span>Cliente <strong>{creditDecision?.approval.order.customer_name}</strong></span>
            <span>Limite <strong>{fmtCurrency(creditDecision?.approval.credit_limit)}</strong></span>
            <span>Exposição projetada <strong>{fmtCurrency(
              safeNumber(creditDecision?.approval.exposure_before_order)
              + safeNumber(creditDecision?.approval.order_amount)
            )}</strong></span>
          </div>
          <div className="form-group">
            <label>Justificativa da decisão *</label>
            <textarea
              rows={4}
              maxLength={1000}
              value={creditDecisionReason}
              onChange={(event) => setCreditDecisionReason(event.target.value)}
              placeholder="Registre os critérios usados nesta decisão..."
              autoFocus
            />
          </div>
          <div className="modal-footer">
            <button
              type="button"
              className="btn-secondary ui-button ui-button--secondary"
              onClick={() => setCreditDecision(null)}
              disabled={creditDecisionSaving}
            >
              Cancelar
            </button>
            <button
              type="button"
              className={`btn-primary ui-button ${creditDecision?.approved ? 'ui-button--primary' : 'ui-button--danger'}`}
              onClick={() => void handleCreditDecision()}
              disabled={creditDecisionSaving || creditDecisionReason.trim().length < 3}
            >
              {creditDecisionSaving ? 'Registrando...' : creditDecision?.approved ? 'Confirmar aprovação' : 'Confirmar rejeição'}
            </button>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={commercialDecision !== null}
        onClose={() => {
          if (commercialDecisionSaving) return;
          setCommercialDecision(null);
          setCommercialDecisionReason('');
        }}
        title={commercialDecision?.approved ? 'Aprovar Exceção Comercial' : 'Rejeitar Exceção Comercial'}
        subtitle={commercialDecision ? commercialDecision.approval.request_reason : undefined}
        size="sm"
      >
        <div className="wizard-form ui-form credit-decision-modal">
          <div className="credit-decision-summary">
            <span>Regra <strong>{commercialDecision?.approval.approval_type}</strong></span>
            <span>Valor <strong>{safeNumber(commercialDecision?.approval.metric_value).toFixed(2)}</strong></span>
            <span>Limite <strong>{safeNumber(commercialDecision?.approval.threshold_value).toFixed(2)}</strong></span>
          </div>
          <div className="form-group">
            <label>Justificativa da decisão *</label>
            <textarea
              rows={4}
              maxLength={1000}
              value={commercialDecisionReason}
              onChange={(event) => setCommercialDecisionReason(event.target.value)}
              placeholder="Registre os critérios usados nesta decisão..."
              autoFocus
            />
          </div>
          <div className="modal-footer">
            <button type="button" className="btn-secondary ui-button ui-button--secondary"
              onClick={() => setCommercialDecision(null)} disabled={commercialDecisionSaving}>
              Cancelar
            </button>
            <button
              type="button"
              className={`btn-primary ui-button ${commercialDecision?.approved ? 'ui-button--primary' : 'ui-button--danger'}`}
              onClick={() => void handleCommercialDecision()}
              disabled={commercialDecisionSaving || commercialDecisionReason.trim().length < 3}
            >
              {commercialDecisionSaving ? 'Registrando...' : commercialDecision?.approved ? 'Confirmar aprovação' : 'Confirmar rejeição'}
            </button>
          </div>
        </div>
      </Modal>

      <CustomerModal
        isOpen={isCustomerModalOpen}
        onClose={() => {
          setIsCustomerModalOpen(false);
          setEditingCustomer(null);
        }}
        customer={editingCustomer}
        onSuccess={() => {
          triggerSuccess(editingCustomer ? "Cliente atualizado com sucesso!" : "Cliente cadastrado com sucesso!");
          loadAllData(true);
        }}
      />

      {/* Modal 4: Nova Meta Comercial */}
      <Modal
        isOpen={isGoalModalOpen}
        onClose={() => setIsGoalModalOpen(false)}
        title="Nova Meta Comercial de Vendas"
        subtitle="Definição de objetivos por vendedor e comissão"
        size="sm"
      >
        <form onSubmit={handleSaveGoal} className="wizard-form ui-form">
          {modalError && <div className="form-error-callout ui-form__error" role="alert">{modalError}</div>}
          <div className="form-group">
            <label>Vendedor *</label>
            <select
              required
              value={goalSellerId}
              onChange={(e) => {
                const seller = sellers.find((item) => item.id === e.target.value);
                setGoalSellerId(e.target.value);
                setGoalSellerName(seller?.full_name || '');
              }}
            >
              <option value="">Selecione um vendedor</option>
              {sellers.map((seller) => (
                <option key={seller.id} value={seller.id}>{seller.full_name}</option>
              ))}
            </select>
            {sellers.length === 0 && (
              <span className="input-hint">Marque um usuário ativo como vendedor no módulo Identity.</span>
            )}
          </div>
          <div className="form-group">
            <label>Mês de Referência *</label>
            <select value={goalMonth} onChange={(e) => setGoalMonth(Number(e.target.value))}>
              {Array.from({ length: 12 }, (_, i) => (
                <option key={i + 1} value={i + 1}>Mês {i + 1}</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label>Meta de Faturamento (R$) *</label>
            <input
              type="number"
              step="0.01"
              required
              value={goalTargetAmount}
              onChange={(e) => setGoalTargetAmount(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label>Comissão (%)</label>
            <input
              type="number"
              step="0.1"
              value={goalCommission}
              onChange={(e) => setGoalCommission(e.target.value)}
            />
          </div>
          <div className="modal-footer ui-form__actions">
            <button type="button" className="btn-secondary ui-button ui-button--secondary" onClick={() => setIsGoalModalOpen(false)}>
              Cancelar
            </button>
            <button type="submit" className="btn-primary ui-button ui-button--primary" disabled={isSaving}>
              {isSaving ? 'Salvando...' : 'Salvar Meta'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Modal 5: Nova Tabela de Preços */}
      <Modal
        isOpen={isPriceTableModalOpen}
        onClose={() => setIsPriceTableModalOpen(false)}
        title="Nova Tabela de Preços"
        subtitle="Precificação diferenciada por canal de venda"
        size="md"
      >
        <form onSubmit={handleSavePriceTable} className="wizard-form ui-form">
          {modalError && <div className="form-error-callout ui-form__error" role="alert">{modalError}</div>}
          <div className="form-group">
            <label>Nome da Tabela *</label>
            <input
              type="text"
              required
              placeholder="Ex: Tabela Atacado / Hospitais"
              value={priceTableName}
              onChange={(e) => setPriceTableName(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label>Descrição</label>
            <input
              type="text"
              value={priceTableDesc}
              onChange={(e) => setPriceTableDesc(e.target.value)}
            />
          </div>
          <div className="form-group checkbox-group ui-form__checkbox">
            <label>
              <input
                type="checkbox"
                checked={priceTableIsDefault}
                onChange={(e) => setPriceTableIsDefault(e.target.checked)}
              />
              <span>Definir como tabela padrão para novos clientes</span>
            </label>
          </div>

          <div className="form-items-section ui-form__section">
            <div className="section-title-row ui-form__section-header">
              <h4>Produtos da Tabela (Opcional)</h4>
              <button
                type="button"
                className="btn-secondary sm ui-button ui-button--secondary ui-button--sm"
                onClick={() => {
                  if (products.length > 0) {
                    setPriceTableItems([
                      ...priceTableItems,
                      { product_id: products[0].id, price: safeNumber(products[0].reference_price) || 10, discount_percent: 0 }
                    ]);
                  }
                }}
              >
                <Plus size={13} /> Adicionar Produto
              </button>
            </div>
            {priceTableItems.map((item, idx) => (
              <div key={idx} className="dynamic-item-row ui-form__item-row">
                <div className="form-group flex-3">
                  <select
                    value={item.product_id}
                    onChange={(e) => {
                      const updated = [...priceTableItems];
                      updated[idx].product_id = e.target.value;
                      setPriceTableItems(updated);
                    }}
                  >
                    {products.map(p => (
                      <option key={p.id} value={p.id}>{p.name} ({p.sku})</option>
                    ))}
                  </select>
                </div>
                <div className="form-group flex-1">
                  <input
                    type="number"
                    step="0.01"
                    placeholder="Preço (R$)"
                    value={item.price}
                    onChange={(e) => {
                      const updated = [...priceTableItems];
                      updated[idx].price = safeNumber(e.target.value);
                      setPriceTableItems(updated);
                    }}
                  />
                </div>
                <button
                  type="button"
                  className="btn-del-item ui-form__remove"
                  onClick={() => setPriceTableItems(priceTableItems.filter((_, i) => i !== idx))}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>

          <div className="modal-footer ui-form__actions">
            <button type="button" className="btn-secondary ui-button ui-button--secondary" onClick={() => setIsPriceTableModalOpen(false)}>
              Cancelar
            </button>
            <button type="submit" className="btn-primary ui-button ui-button--primary" disabled={isSaving}>
              {isSaving ? 'Salvando...' : 'Salvar Tabela'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Modal 6: Registrar Devolução / Pós-Venda */}
      <Modal
        isOpen={isReturnModalOpen}
        onClose={() => setIsReturnModalOpen(false)}
        title="Registrar Devolução ou Troca (Pós-Venda)"
        subtitle="Estorno financeiro e reestocagem auditada no Kardex"
        size="md"
      >
        <form onSubmit={handleSaveReturn} className="wizard-form ui-form">
          {modalError && <div className="form-error-callout ui-form__error" role="alert">{modalError}</div>}
          <div className="form-row">
            <div className="form-group flex-2">
              <label>Cliente *</label>
              <input
                type="text"
                required
                value={retCustomerName}
                onChange={(e) => setRetCustomerName(e.target.value)}
              />
            </div>
            <div className="form-group flex-1">
              <label>Tipo *</label>
              <select value={retType} onChange={(e) => setRetType(e.target.value as any)}>
                <option value="DEVOLUCAO">Devolução</option>
                <option value="TROCA">Troca</option>
                <option value="CANCELAMENTO">Cancelamento</option>
              </select>
            </div>
          </div>

          <div className="form-group">
            <label>Produto Devolvido *</label>
            <select
              value={retProductId}
              onChange={(e) => {
                const pid = e.target.value;
                setRetProductId(pid);
                const p = products.find(prod => prod.id === pid);
                if (p) setRetUnitPrice(String(p.reference_price || '10.00'));
              }}
            >
              {products.map(p => (
                <option key={p.id} value={p.id}>{p.name} ({p.sku})</option>
              ))}
            </select>
          </div>

          <div className="form-row">
            <div className="form-group flex-1">
              <label>Quantidade *</label>
              <input
                type="number"
                min="1"
                required
                value={retQuantity}
                onChange={(e) => setRetQuantity(e.target.value)}
              />
            </div>
            <div className="form-group flex-1">
              <label>Preço Unitário (R$) *</label>
              <input
                type="number"
                step="0.01"
                required
                value={retUnitPrice}
                onChange={(e) => setRetUnitPrice(e.target.value)}
              />
            </div>
            <div className="form-group flex-1">
              <label>Estado do Item</label>
              <select value={retCondition} onChange={(e) => setRetCondition(e.target.value as any)}>
                <option value="GOOD">Bom Estado (Reestocável)</option>
                <option value="DAMAGED">Avariado / Danificado</option>
              </select>
            </div>
          </div>

          <div className="form-group">
            <label>Motivo da Devolução / Troca *</label>
            <input
              type="text"
              required
              placeholder="Ex: Item com lacre rompido / Erro no pedido do cliente"
              value={retReason}
              onChange={(e) => setRetReason(e.target.value)}
            />
          </div>

          <div className="form-group checkbox-group ui-form__checkbox">
            <label>
              <input
                type="checkbox"
                checked={retRestock}
                onChange={(e) => setRetRestock(e.target.checked)}
              />
              <span>Reestocar produto no inventário (Kardex) se em bom estado</span>
            </label>
          </div>

          <div className="modal-footer ui-form__actions">
            <button type="button" className="btn-secondary ui-button ui-button--secondary" onClick={() => setIsReturnModalOpen(false)}>
              Cancelar
            </button>
            <button type="submit" className="btn-primary ui-button ui-button--primary" disabled={isSaving}>
              {isSaving ? 'Processando...' : 'Processar Devolução'}
            </button>
          </div>
        </form>
      </Modal>

      {/* CONFIRM MODAL GENÉRICO */}
      <Modal
        isOpen={Boolean(selectedReturn)}
        onClose={() => setSelectedReturn(null)}
        title={`Pós-venda · ${selectedReturn?.return_type || ''}`}
        subtitle="Registro concluído preservado para auditoria; os vínculos abaixo abrem os objetos de origem."
        size="lg"
      >
        {selectedReturn && (
          <div className="wizard-form ui-form">
            <div className="form-row cols-2">
              <div className="form-group"><label>Cliente</label><RecordLink type="CUSTOMER" id={selectedReturn.customer_id}><strong>{selectedReturn.customer_name}</strong></RecordLink></div>
              <div className="form-group"><label>Status</label><strong>{selectedReturn.status}</strong></div>
            </div>
            <div className="form-row cols-2">
              <div className="form-group"><label>Pedido de venda</label>{selectedReturn.sales_order_id ? <RecordLink type="SALES_ORDER" id={selectedReturn.sales_order_id}>Abrir pedido vinculado</RecordLink> : <span>Não vinculado</span>}</div>
              <div className="form-group"><label>Venda de PDV</label>{selectedReturn.pos_sale_id ? <RecordLink type="POS_SALE" id={selectedReturn.pos_sale_id}>Abrir venda vinculada</RecordLink> : <span>Não vinculada</span>}</div>
            </div>
            <div className="form-group"><label>Motivo</label><p>{selectedReturn.reason}</p></div>
            <div className="table-container ui-table-wrap">
              <table className="data-table ui-table">
                <thead><tr><th>Produto</th><th>Condição</th><th>Quantidade</th><th>Total</th></tr></thead>
                <tbody>{selectedReturn.items.map(item => (
                  <tr key={item.id}>
                    <td><RecordLink type="PRODUCT" id={item.product_id}>{item.product?.name || item.product_id}</RecordLink></td>
                    <td>{item.condition}</td>
                    <td>{formatQuantity(item.quantity)}</td>
                    <td>{fmtCurrency(item.total_price)}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
            <div className="modal-footer ui-form__actions">
              <DocumentLink documentId={selectedReturn.document_id}>Abrir na Central de Documentos</DocumentLink>
              <button type="button" className="btn-secondary ui-button ui-button--secondary" onClick={() => setSelectedReturn(null)}>Fechar</button>
            </div>
          </div>
        )}
      </Modal>

      <Modal
        isOpen={Boolean(logisticsDetail)}
        onClose={() => setLogisticsDetail(null)}
        title={logisticsDetail?.kind === 'DELIVERY'
          ? `Entrega ${logisticsDetail.record.delivery_number}`
          : `Reserva ${logisticsDetail?.record.reservation_number || ''}`}
        subtitle="Registro logístico rastreável e vinculado ao pedido de venda."
        size="lg"
      >
        {logisticsDetail && (
          <div className="wizard-form ui-form">
            <div className="form-row cols-2">
              <div className="form-group"><label>Pedido</label><RecordLink type="SALES_ORDER" id={logisticsDetail.record.sales_order_id}>Abrir pedido de venda</RecordLink></div>
              <div className="form-group"><label>Status</label><strong>{logisticsDetail.record.status}</strong></div>
            </div>
            {logisticsDetail.kind === 'DELIVERY' && logisticsDetail.record.reservation_id && (
              <div className="form-group"><label>Reserva consumida</label><RecordLink type="STOCK_RESERVATION" id={logisticsDetail.record.reservation_id}>Abrir reserva de estoque</RecordLink></div>
            )}
            <div className="table-container ui-table-wrap">
              <table className="data-table ui-table">
                <thead><tr><th>Produto</th><th>Quantidade</th></tr></thead>
                <tbody>{logisticsDetail.record.items.map(item => (
                  <tr key={item.id}>
                    <td><RecordLink type="PRODUCT" id={item.product_id}>{item.product?.name || item.product_id}</RecordLink></td>
                    <td>{formatQuantity(item.quantity)}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
            <div className="modal-footer ui-form__actions">
              <DocumentLink documentId={logisticsDetail.record.document_id}>Abrir na Central de Documentos</DocumentLink>
              <button type="button" className="btn-secondary ui-button ui-button--secondary" onClick={() => setLogisticsDetail(null)}>Fechar</button>
            </div>
          </div>
        )}
      </Modal>

      <Modal
        isOpen={Boolean(logisticsDetailError)}
        onClose={() => setLogisticsDetailError(null)}
        title="Registro logístico indisponível"
        size="sm"
      >
        <div className="modal-alert-error" role="alert">{logisticsDetailError}</div>
      </Modal>

      <Modal
        isOpen={isDocumentTimelineOpen}
        onClose={() => setIsDocumentTimelineOpen(false)}
        title={`Cadeia documental · ${documentTimelineLabel}`}
        subtitle="Rastreabilidade entre os documentos realmente vinculados pelos módulos."
        size="lg"
      >
        {documentTimelineLoading ? (
          <div className="ui-document-timeline-loading" role="status">
            <RefreshCw size={18} /> Consultando documentos relacionados...
          </div>
        ) : documentTimelineError ? (
          <div className="modal-alert-error" role="alert">
            {documentTimelineError}
          </div>
        ) : documentChain ? (
          <DocumentTimeline chain={documentChain} />
        ) : (
          <div className="ui-empty-state">Nenhuma cadeia documental disponível.</div>
        )}
      </Modal>

      <ConfirmModal
        isOpen={confirmModal.isOpen}
        onClose={closeConfirm}
        onConfirm={confirmModal.onConfirm}
        title={confirmModal.title}
        subtitle={confirmModal.subtitle}
        message={confirmModal.message}
        type={confirmModal.type}
        confirmText={confirmModal.confirmText}
      />

      {/* MODAL DE JUSTIFICATIVA DE CANCELAMENTO DE COTAÇÃO */}
      {quoteToCancel && (
        <Modal
          isOpen={Boolean(quoteToCancel)}
          onClose={() => setQuoteToCancel(null)}
          title="Cancelar Cotação Comercial"
          subtitle={`Informe o motivo do cancelamento / desistência da cotação #${quoteToCancel.quote_number}`}
          size="md"
        >
          <div style={{ padding: '0.5rem 0' }}>
            <div className="form-group" style={{ marginBottom: '1.25rem' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600 }}>
                Motivo do Cancelamento / Desistência *
              </label>
              <textarea
                rows={3}
                required
                placeholder="Ex: Cliente optou por proposta concorrente / Cancelamento do projeto / Sem orçamento no momento"
                value={cancelReasonInput}
                onChange={(e) => setCancelReasonInput(e.target.value)}
                className="ui-input"
                style={{ width: '100%', resize: 'vertical' }}
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
              <button
                type="button"
                className="ui-button ui-button--secondary"
                onClick={() => setQuoteToCancel(null)}
                disabled={isCancellingQuote}
              >
                Voltar
              </button>
              <button
                type="button"
                className="ui-button ui-button--danger"
                style={{ background: '#ef4444', color: '#fff' }}
                onClick={handleConfirmCancelQuote}
                disabled={isCancellingQuote || !cancelReasonInput.trim()}
              >
                {isCancellingQuote ? 'Cancelando...' : 'Confirmar Cancelamento'}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};

export default Sales;
