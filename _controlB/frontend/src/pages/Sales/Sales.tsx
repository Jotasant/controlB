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
import {
  ShoppingBag, FileText, RefreshCw, Search,
  Trash2, Users, Plus, Target, DollarSign,
  TrendingUp, Undo2, ChevronRight, Award, BarChart3,
  Package, CheckCircle2, Layers, Edit, Filter, ArrowUpRight, GitBranch
} from 'lucide-react';
import {
  Bar, BarChart, CartesianGrid, ResponsiveContainer,
  Tooltip, XAxis, YAxis
} from 'recharts';
import {
  salesService, inventoryService, identityService, documentService, formatApiError
} from '@/services/api';
import {
  SalesOrder, SalesQuote, Product,
  Customer, Contact, SalesGoal, PriceTable, SalesReturn, SalesAnalytics,
  BusinessDocumentChain
} from '@/types';
import { formatCurrency, formatQuantity } from '@/utils/formatters';
import { Modal } from '@/components/Modal/Modal';
import { ConfirmModal, ConfirmModalType } from '@/components/ConfirmModal/ConfirmModal';
import { Can } from '@/components/Can';
import { DocumentTimeline } from '@/components/DocumentTimeline/DocumentTimeline';
import { useToast } from '@/components/Toast/ToastContext';
import './Sales.scss';

type ActiveSalesTab =
  | 'quotes'
  | 'orders'
  | 'customers'
  | 'commercial'
  | 'post_sales'
  | 'analytics';

export const Sales: React.FC = () => {
  const toast = useToast();
  const [activeTab, setActiveTab] = useState<ActiveSalesTab>('quotes');
  const [loading, setLoading] = useState<boolean>(true);

  // --- DADOS DO SERVIDOR ---
  const [quotes, setQuotes] = useState<SalesQuote[]>([]);
  const [orders, setOrders] = useState<SalesOrder[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [salesGoals, setSalesGoals] = useState<SalesGoal[]>([]);
  const [priceTables, setPriceTables] = useState<PriceTable[]>([]);
  const [salesReturns, setSalesReturns] = useState<SalesReturn[]>([]);
  const [analytics, setAnalytics] = useState<SalesAnalytics | null>(null);

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
  const [quoteCustomerName, setQuoteCustomerName] = useState<string>('');
  const [quoteCustomerDocument, setQuoteCustomerDocument] = useState<string>('');
  const [quoteValidUntil, setQuoteValidUntil] = useState<string>('');
  const [quotePaymentTerms, setQuotePaymentTerms] = useState<string>('30 DDL');
  const [quoteNotes, setQuoteNotes] = useState<string>('');
  const [quoteItems, setQuoteItems] = useState<Array<{
    product_id: string;
    quantity: number;
    unit_price: number;
    discount_amount: number;
    notes?: string;
  }>>([]);

  // =========================================================================
  // ESTADOS: 2. PEDIDOS DE VENDA
  // =========================================================================
  const [isOrderModalOpen, setIsOrderModalOpen] = useState<boolean>(false);
  const [orderCustomerName, setOrderCustomerName] = useState<string>('');
  const [orderCustomerDocument, setOrderCustomerDocument] = useState<string>('');
  const [orderPaymentTerms, setOrderPaymentTerms] = useState<string>('À Vista');
  const [orderDeliveryStatus, setOrderDeliveryStatus] = useState<string>('PENDING');
  const [orderNotes, setOrderNotes] = useState<string>('');
  const [orderItems, setOrderItems] = useState<Array<{
    product_id: string;
    quantity: number;
    unit_price: number;
    discount_amount: number;
    notes?: string;
  }>>([]);

  // =========================================================================
  // ESTADOS: 3. CLIENTES (PF / PJ)
  // =========================================================================
  const [isCustomerModalOpen, setIsCustomerModalOpen] = useState<boolean>(false);
  const [editingCustomerId, setEditingCustomerId] = useState<string | null>(null);
  const [custPersonType, setCustPersonType] = useState<'PJ' | 'PF'>('PJ');
  const [custName, setCustName] = useState<string>('');
  const [custTradeName, setCustTradeName] = useState<string>('');
  const [custDocument, setCustDocument] = useState<string>('');
  const [custStateReg, setCustStateReg] = useState<string>('');
  const [custEmail, setCustEmail] = useState<string>('');
  const [custPhone, setCustPhone] = useState<string>('');
  const [custCreditLimit, setCustCreditLimit] = useState<string>('50000.00');
  const [custStreet, setCustStreet] = useState<string>('');
  const [custNumber, setCustNumber] = useState<string>('');
  const [custNeighborhood, setCustNeighborhood] = useState<string>('');
  const [custCity, setCustCity] = useState<string>('');
  const [custState, setCustState] = useState<string>('SP');
  const [custZipCode, setCustZipCode] = useState<string>('');
  const [custContactId, setCustContactId] = useState<string>('');
  const [custNotes, setCustNotes] = useState<string>('');

  // =========================================================================
  // ESTADOS: 4. GESTÃO COMERCIAL (METAS & TABELAS DE PREÇOS)
  // =========================================================================
  const [isGoalModalOpen, setIsGoalModalOpen] = useState<boolean>(false);
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
        contactsRes, goalsRes, priceTablesRes, returnsRes, analyticsRes
      ] = await Promise.all([
        salesService.getQuotes(force),
        salesService.getOrders(force),
        inventoryService.getProducts(undefined, force),
        salesService.getCustomers('', force),
        identityService.getContacts(force),
        salesService.getSalesGoals(yearFilter, force),
        salesService.getPriceTables(force),
        salesService.getSalesReturns(force),
        salesService.getSalesAnalytics(force)
      ]);

      setQuotes(quotesRes || []);
      setOrders(ordersRes || []);
      setProducts(productsRes || []);
      setCustomers(customersRes || []);
      setContacts(contactsRes || []);
      setSalesGoals(goalsRes || []);
      setPriceTables(priceTablesRes || []);
      setSalesReturns(returnsRes || []);
      setAnalytics(analyticsRes || null);
    } catch (err: any) {
      console.error("Erro ao carregar dados de vendas:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAllData();
  }, [yearFilter]);

  // =========================================================================
  // HANDLERS: COTAÇÕES & PROPOSTAS COMERCIAIS
  // =========================================================================
  const handleOpenQuoteModal = () => {
    setModalError(null);
    setQuoteCustomerName('');
    setQuoteCustomerDocument('');
    setQuoteValidUntil('');
    setQuotePaymentTerms('30 DDL');
    setQuoteNotes('');
    if (products.length > 0) {
      setQuoteItems([{
        product_id: products[0].id,
        quantity: 1,
        unit_price: safeNumber(products[0].reference_price) || 10.00,
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
          unit_price: safeNumber(products[0].reference_price) || 10.00,
          discount_amount: 0
        }
      ]);
    }
  };

  const handleRemoveQuoteItem = (index: number) => {
    setQuoteItems(quoteItems.filter((_, idx) => idx !== index));
  };

  const handleSaveQuote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!quoteCustomerName.trim()) {
      setModalError("Informe o nome do cliente.");
      return;
    }
    if (quoteItems.length === 0) {
      setModalError("Adicione pelo menos um item à proposta comercial.");
      return;
    }

    setIsSaving(true);
    setModalError(null);
    try {
      await salesService.createQuote({
        customer_name: quoteCustomerName.trim(),
        customer_document: quoteCustomerDocument.trim() || undefined,
        valid_until: quoteValidUntil || undefined,
        notes: quoteNotes.trim() ? `${quoteNotes.trim()} | Condição: ${quotePaymentTerms}` : `Condição: ${quotePaymentTerms}`,
        items: quoteItems.map(it => ({
          product_id: it.product_id,
          quantity: it.quantity,
          unit_price: it.unit_price,
          discount_amount: it.discount_amount,
          notes: it.notes
        }))
      });
      setIsQuoteModalOpen(false);
      triggerSuccess("Cotação comercial emitida com sucesso!");
      loadAllData();
    } catch (err: any) {
      setModalError(formatApiError(err, "Erro ao salvar proposta comercial."));
    } finally {
      setIsSaving(false);
    }
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
      title: 'Cancelar Cotação Comercial',
      subtitle: `Cotação #${quote.quote_number}`,
      message: `Deseja realmente cancelar a cotação #${quote.quote_number} de ${quote.customer_name}?`,
      type: 'danger',
      confirmText: 'Cancelar Cotação',
      onConfirm: async () => {
        try {
          await salesService.deleteQuote(quote.id);
          triggerSuccess("Cotação cancelada com sucesso.");
          closeConfirm();
          loadAllData();
        } catch (err: any) {
          toast.error(formatApiError(err, "Erro ao cancelar cotação."), 'Falha ao cancelar cotação');
        }
      }
    });
  };

  // =========================================================================
  // HANDLERS: PEDIDOS DE VENDA
  // =========================================================================
  const handleOpenOrderModal = () => {
    setModalError(null);
    setOrderCustomerName('');
    setOrderCustomerDocument('');
    setOrderPaymentTerms('À Vista');
    setOrderDeliveryStatus('PENDING');
    setOrderNotes('');
    if (products.length > 0) {
      setOrderItems([{
        product_id: products[0].id,
        quantity: 1,
        unit_price: safeNumber(products[0].reference_price) || 10.00,
        discount_amount: 0
      }]);
    } else {
      setOrderItems([]);
    }
    setIsOrderModalOpen(true);
  };

  const handleAddOrderItem = () => {
    if (products.length > 0) {
      setOrderItems([
        ...orderItems,
        {
          product_id: products[0].id,
          quantity: 1,
          unit_price: safeNumber(products[0].reference_price) || 10.00,
          discount_amount: 0
        }
      ]);
    }
  };

  const handleRemoveOrderItem = (index: number) => {
    setOrderItems(orderItems.filter((_, idx) => idx !== index));
  };

  const handleSaveOrder = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!orderCustomerName.trim()) {
      setModalError("Informe o nome do cliente.");
      return;
    }
    if (orderItems.length === 0) {
      setModalError("Adicione pelo menos um produto ao pedido.");
      return;
    }

    setIsSaving(true);
    setModalError(null);
    try {
      await salesService.createOrder({
        customer_name: orderCustomerName.trim(),
        customer_document: orderCustomerDocument.trim() || undefined,
        payment_terms: orderPaymentTerms,
        delivery_status: orderDeliveryStatus,
        notes: orderNotes.trim() || undefined,
        items: orderItems.map(it => ({
          product_id: it.product_id,
          quantity: it.quantity,
          unit_price: it.unit_price,
          discount_amount: it.discount_amount,
          notes: it.notes
        }))
      });
      setIsOrderModalOpen(false);
      triggerSuccess("Pedido de venda cadastrado com sucesso!");
      loadAllData();
    } catch (err: any) {
      setModalError(formatApiError(err, "Erro ao salvar pedido de venda."));
    } finally {
      setIsSaving(false);
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
      message: `Deseja realmente cancelar o pedido #${order.order_number} de ${order.customer_name}?`,
      type: 'danger',
      confirmText: 'Cancelar Pedido',
      onConfirm: async () => {
        try {
          await salesService.deleteOrder(order.id);
          triggerSuccess("Pedido cancelado com sucesso.");
          closeConfirm();
          loadAllData();
        } catch (err: any) {
          toast.error(formatApiError(err, "Erro ao cancelar pedido."), 'Falha ao cancelar pedido');
        }
      }
    });
  };

  // =========================================================================
  // HANDLERS: CLIENTES (PF / PJ)
  // =========================================================================
  const handleOpenCustomerModal = (customer?: Customer) => {
    setModalError(null);
    if (customer) {
      setEditingCustomerId(customer.id);
      setCustPersonType(customer.person_type as 'PJ' | 'PF');
      setCustName(customer.name);
      setCustTradeName(customer.trade_name || '');
      setCustDocument(customer.document);
      setCustStateReg(customer.state_registration || '');
      setCustEmail(customer.email || '');
      setCustPhone(customer.phone || '');
      setCustCreditLimit(String(customer.credit_limit || '50000.00'));
      setCustStreet(customer.address_street || '');
      setCustNumber(customer.address_number || '');
      setCustNeighborhood(customer.address_neighborhood || '');
      setCustCity(customer.address_city || '');
      setCustState(customer.address_state || 'SP');
      setCustZipCode(customer.address_zip_code || '');
      setCustContactId(customer.contact_id || '');
      setCustNotes(customer.notes || '');
    } else {
      setEditingCustomerId(null);
      setCustPersonType('PJ');
      setCustName('');
      setCustTradeName('');
      setCustDocument('');
      setCustStateReg('');
      setCustEmail('');
      setCustPhone('');
      setCustCreditLimit('50000.00');
      setCustStreet('');
      setCustNumber('');
      setCustNeighborhood('');
      setCustCity('');
      setCustState('SP');
      setCustZipCode('');
      setCustContactId('');
      setCustNotes('');
    }
    setIsCustomerModalOpen(true);
  };

  const handleSaveCustomer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!custName.trim() || !custDocument.trim()) {
      setModalError("Nome/Razão Social e CPF/CNPJ são campos obrigatórios.");
      return;
    }

    setIsSaving(true);
    setModalError(null);
    try {
      const payload: any = {
        person_type: custPersonType,
        document: custDocument.trim(),
        name: custName.trim(),
        trade_name: custTradeName.trim() || undefined,
        state_registration: custStateReg.trim() || undefined,
        email: custEmail.trim() || undefined,
        phone: custPhone.trim() || undefined,
        credit_limit: safeNumber(custCreditLimit),
        address_street: custStreet.trim() || undefined,
        address_number: custNumber.trim() || undefined,
        address_neighborhood: custNeighborhood.trim() || undefined,
        address_city: custCity.trim() || undefined,
        address_state: custState.trim() || undefined,
        address_zip_code: custZipCode.trim() || undefined,
        contact_id: custContactId || undefined,
        notes: custNotes.trim() || undefined
      };

      if (editingCustomerId) {
        await salesService.updateCustomer(editingCustomerId, payload);
        triggerSuccess("Cadastro de cliente atualizado com sucesso!");
      } else {
        await salesService.createCustomer(payload);
        triggerSuccess("Novo cliente cadastrado com sucesso!");
      }
      setIsCustomerModalOpen(false);
      loadAllData();
    } catch (err: any) {
      setModalError(formatApiError(err, "Erro ao salvar cliente."));
    } finally {
      setIsSaving(false);
    }
  };

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
  const handleSaveGoal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!goalSellerName.trim()) {
      setModalError("O nome do vendedor é obrigatório.");
      return;
    }

    setIsSaving(true);
    setModalError(null);
    try {
      await salesService.createSalesGoal({
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
                  {activeTab === 'customers' && 'Base Centralizada de Clientes'}
                  {activeTab === 'commercial' && 'Gestão Comercial, Metas & Preços'}
                  {activeTab === 'post_sales' && 'Pós-Venda & Reestocagem no Kardex'}
                  {activeTab === 'analytics' && 'Inteligência Comercial & BI'}
                </span>
              </div>
              <h1 className="ui-page-header__title">
                {activeTab === 'quotes' && 'Cotações & Propostas Comerciais'}
                {activeTab === 'orders' && 'Pedidos de Venda'}
                {activeTab === 'customers' && 'Clientes (Pessoa Jurídica / Física)'}
                {activeTab === 'commercial' && 'Gestão de Metas & Tabelas de Preços'}
                {activeTab === 'post_sales' && 'Pós-Venda & Trocas / Devoluções'}
                {activeTab === 'analytics' && 'Painel Analítico de Vendas & BI'}
              </h1>
            </div>

            <div className="header-actions ui-page-header__actions">
              <button className="btn-refresh ui-button ui-button--icon" onClick={() => loadAllData(true)} title="Atualizar Dados">
                <RefreshCw size={15} className={loading ? 'spinning' : ''} />
              </button>

              {activeTab === 'quotes' && (
                <button className="btn-primary ui-button ui-button--primary" onClick={handleOpenQuoteModal}>
                  <Plus size={16} /> Nova Cotação
                </button>
              )}

              {activeTab === 'orders' && (
                <button className="btn-primary ui-button ui-button--primary" onClick={handleOpenOrderModal}>
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
                  <button className="btn-primary ui-button ui-button--primary" onClick={() => setIsGoalModalOpen(true)}>
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
                    <option value="APPROVED">Aprovado</option>
                    <option value="CONVERTED">Convertido em Pedido</option>
                    <option value="REJECTED">Rejeitado</option>
                  </select>
                </div>
              </div>

              <div className="table-container ui-table-wrap">
                <table className="data-table ui-table ui-table--wide">
                  <thead>
                    <tr>
                      <th>Cotação</th>
                      <th>Cliente</th>
                      <th>Emissão</th>
                      <th>Validade</th>
                      <th>Total Líquido</th>
                      <th>Status</th>
                      <th>Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredQuotes.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="empty-state ui-empty-state">
                          Nenhuma cotação comercial encontrada.
                        </td>
                      </tr>
                    ) : (
                      filteredQuotes.map(q => (
                        <tr key={q.id}>
                          <td><strong>#{q.quote_number}</strong></td>
                          <td>
                            <div className="cell-client">
                              <span className="client-name">{q.customer_name}</span>
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
                              q.status === 'REJECTED' ? 'danger' : 'warning'
                            }`}>
                              {q.status === 'CONVERTED' ? 'Convertido' :
                               q.status === 'APPROVED' ? 'Aprovado' :
                               q.status === 'DRAFT' ? 'Rascunho' : q.status}
                            </span>
                          </td>
                          <td>
                            <div className="table-actions ui-table-actions">
                              <button
                                type="button"
                                className="table-action-btn ui-table-action"
                                onClick={() => void openDocumentTimeline('SALES_QUOTE', q.id, `Cotação #${q.quote_number}`)}
                                title="Ver cadeia documental"
                                aria-label={`Ver cadeia da cotação ${q.quote_number}`}
                              >
                                <GitBranch size={14} /> Rastrear
                              </button>
                              {q.status === 'APPROVED' && (
                                <button
                                  type="button"
                                  className="table-action-btn ui-table-action primary"
                                  onClick={() => handleConvertToOrder(q)}
                                  title="Converter em Pedido de Venda"
                                >
                                  <ArrowUpRight size={14} /> Converter
                                </button>
                              )}
                              <button
                                type="button"
                                className="table-action-btn ui-table-action danger"
                                onClick={() => handleDeleteQuote(q)}
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
                    <option value="DRAFT">Rascunho</option>
                    <option value="CONFIRMED">Confirmado</option>
                    <option value="COMPLETED">Faturado / Concluído</option>
                    <option value="CANCELLED">Cancelado</option>
                  </select>
                </div>
              </div>

              <div className="table-container ui-table-wrap">
                <table className="data-table ui-table ui-table--wide">
                  <thead>
                    <tr>
                      <th>Pedido</th>
                      <th>Cliente</th>
                      <th>Emissão</th>
                      <th>Entrega</th>
                      <th>Faturamento</th>
                      <th>Total</th>
                      <th>Status</th>
                      <th>Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredOrders.length === 0 ? (
                      <tr>
                        <td colSpan={8} className="empty-state ui-empty-state">
                          Nenhum pedido de venda encontrado.
                        </td>
                      </tr>
                    ) : (
                      filteredOrders.map(o => (
                        <tr key={o.id}>
                          <td><strong>#{o.order_number}</strong></td>
                          <td>
                            <div className="cell-client">
                              <span className="client-name">{o.customer_name}</span>
                              {o.customer_document && <span className="client-doc">{o.customer_document}</span>}
                            </div>
                          </td>
                          <td>{new Date(o.created_at).toLocaleDateString('pt-BR')}</td>
                          <td>
                            <span className={`status-pill ui-status ${
                              o.delivery_status === 'CANCELLED' ? 'danger' :
                              o.delivery_status === 'DELIVERED' ? 'success' :
                              o.delivery_status === 'DISPATCHED' || o.delivery_status === 'RESERVED' ? 'info' : 'warning'
                            }`}>
                              {o.delivery_status === 'CANCELLED' ? 'Cancelado' :
                               o.delivery_status === 'DELIVERED' ? 'Entregue' :
                               o.delivery_status === 'DISPATCHED' ? 'Em Trânsito' :
                               o.delivery_status === 'RESERVED' ? 'Reservado' : 'Pendente'}
                            </span>
                          </td>
                          <td>
                            <span className={`status-pill ui-status ${o.billing_status === 'INVOICED' ? 'success' : 'warning'}`}>
                              {o.billing_status === 'INVOICED' ? 'Faturado' : 'Aguardando'}
                            </span>
                          </td>
                          <td><strong>{fmtCurrency(o.net_amount)}</strong></td>
                          <td>
                            <span className={`status-pill ui-status ${
                              o.status === 'COMPLETED' ? 'success' :
                              o.status === 'CONFIRMED' ? 'info' :
                              o.status === 'CANCELLED' ? 'danger' : 'warning'
                            }`}>
                              {o.status}
                            </span>
                          </td>
                          <td>
                            <div className="table-actions ui-table-actions">
                              <Can permission="inventory:move">
                                {o.status === 'CONFIRMED' && o.delivery_status === 'PENDING' && (
                                  <button
                                    type="button"
                                    className="table-action-btn ui-table-action primary"
                                    onClick={() => void handleReserveOrderStock(o)}
                                    disabled={reservingOrderId !== null}
                                    aria-busy={reservingOrderId === o.id}
                                    title="Reservar estoque para o pedido"
                                    aria-label={`Reservar estoque do pedido ${o.order_number}`}
                                  >
                                    <Package size={14} />
                                    {reservingOrderId === o.id ? 'Reservando...' : 'Reservar estoque'}
                                  </button>
                                )}
                              </Can>
                              <button
                                type="button"
                                className="table-action-btn ui-table-action"
                                onClick={() => void openDocumentTimeline('SALES_ORDER', o.id, `Pedido #${o.order_number}`)}
                                title="Ver cadeia documental"
                                aria-label={`Ver cadeia do pedido ${o.order_number}`}
                              >
                                <GitBranch size={14} /> Rastrear
                              </button>
                              <button
                                type="button"
                                className="table-action-btn ui-table-action danger"
                                onClick={() => handleDeleteOrder(o)}
                                title="Cancelar pedido"
                                aria-label={`Cancelar pedido ${o.order_number}`}
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

              <div className="table-container ui-table-wrap">
                <table className="data-table ui-table ui-table--wide">
                  <thead>
                    <tr>
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
                        <td colSpan={7} className="empty-state ui-empty-state">
                          Nenhum cliente cadastrado no módulo de vendas.
                        </td>
                      </tr>
                    ) : (
                      filteredCustomers.map(c => (
                        <tr key={c.id}>
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
                            <div className="table-actions ui-table-actions">
                              <button
                                type="button"
                                className="table-action-btn ui-table-action"
                                onClick={() => handleOpenCustomerModal(c)}
                                title="Editar Cliente"
                              >
                                <Edit size={14} />
                              </button>
                              <button
                                type="button"
                                className="table-action-btn ui-table-action danger"
                                onClick={() => handleDeleteCustomer(c)}
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

                  <div className="table-container mini ui-table-wrap">
                    <table className="data-table ui-table">
                      <thead>
                        <tr>
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
                            <td colSpan={5} className="empty-state ui-empty-state">
                              Nenhuma meta comercial cadastrada para {yearFilter}.
                            </td>
                          </tr>
                        ) : (
                          salesGoals.map(g => (
                            <tr key={g.id}>
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

                  <div className="table-container mini ui-table-wrap">
                    <table className="data-table ui-table">
                      <thead>
                        <tr>
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
                            <td colSpan={5} className="empty-state ui-empty-state">
                              Nenhuma tabela de preços cadastrada.
                            </td>
                          </tr>
                        ) : (
                          priceTables.map(t => (
                            <tr key={t.id}>
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

              <div className="table-container ui-table-wrap">
                <table className="data-table ui-table ui-table--wide">
                  <thead>
                    <tr>
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
                        <td colSpan={8} className="empty-state ui-empty-state">
                          Nenhum registro de pós-venda encontrado.
                        </td>
                      </tr>
                    ) : (
                      filteredReturns.map(r => (
                        <tr key={r.id}>
                          <td>
                            <span className={`status-pill ui-status ${
                              r.return_type === 'DEVOLUCAO' ? 'danger' :
                              r.return_type === 'TROCA' ? 'info' : 'warning'
                            }`}>
                              {r.return_type}
                            </span>
                          </td>
                          <td><strong>{r.customer_name}</strong></td>
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
                              onClick={() => handleDeleteReturn(r)}
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
        </main>
      </div>

      {/* =================================================================== */}
      {/* MODAIS DO MÓDULO DE VENDAS                                          */}
      {/* =================================================================== */}

      {/* Modal 1: Nova Cotação / Proposta Comercial */}
      <Modal
        isOpen={isQuoteModalOpen}
        onClose={() => setIsQuoteModalOpen(false)}
        title="Nova Cotação / Proposta Comercial"
        subtitle="Emissão de proposta comercial formal com alçada e condições"
        size="lg"
      >
        <form onSubmit={handleSaveQuote} className="wizard-form ui-form">
          {modalError && <div className="form-error-callout ui-form__error" role="alert">{modalError}</div>}
          <div className="form-row">
            <div className="form-group flex-2">
              <label>Nome do Cliente *</label>
              <input
                type="text"
                required
                placeholder="Ex: Laboratório Santa Maria Ltda"
                value={quoteCustomerName}
                onChange={(e) => setQuoteCustomerName(e.target.value)}
              />
            </div>
            <div className="form-group flex-1">
              <label>Condição Comercial</label>
              <select value={quotePaymentTerms} onChange={(e) => setQuotePaymentTerms(e.target.value)}>
                <option value="À Vista">À Vista</option>
                <option value="30 DDL">30 DDL</option>
                <option value="30/60 DDL">30/60 DDL</option>
                <option value="PIX">PIX</option>
              </select>
            </div>
            <div className="form-group flex-1">
              <label>Validade da Proposta</label>
              <input
                type="date"
                value={quoteValidUntil}
                onChange={(e) => setQuoteValidUntil(e.target.value)}
              />
            </div>
          </div>

          <div className="form-items-section ui-form__section">
            <div className="section-title-row ui-form__section-header">
              <h4>Itens do Orçamento</h4>
              <button type="button" className="btn-secondary sm ui-button ui-button--secondary ui-button--sm" onClick={handleAddQuoteItem}>
                <Plus size={13} /> Adicionar Produto
              </button>
            </div>

            {quoteItems.map((item, idx) => (
              <div key={idx} className="dynamic-item-row ui-form__item-row">
                <div className="form-group flex-3">
                  <select
                    value={item.product_id}
                    onChange={(e) => {
                      const pid = e.target.value;
                      const prod = products.find(p => p.id === pid);
                      const updated = [...quoteItems];
                      updated[idx].product_id = pid;
                      if (prod) updated[idx].unit_price = safeNumber(prod.reference_price) || 10.00;
                      setQuoteItems(updated);
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
                    min="1"
                    placeholder="Qtd"
                    value={item.quantity}
                    onChange={(e) => {
                      const updated = [...quoteItems];
                      updated[idx].quantity = Math.max(1, parseInt(e.target.value) || 1);
                      setQuoteItems(updated);
                    }}
                  />
                </div>
                <div className="form-group flex-1">
                  <input
                    type="number"
                    step="0.01"
                    placeholder="Preço"
                    value={item.unit_price}
                    onChange={(e) => {
                      const updated = [...quoteItems];
                      updated[idx].unit_price = safeNumber(e.target.value);
                      setQuoteItems(updated);
                    }}
                  />
                </div>
                <button type="button" className="btn-del-item ui-form__remove" onClick={() => handleRemoveQuoteItem(idx)}>
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>

          <div className="modal-footer ui-form__actions">
            <button type="button" className="btn-secondary ui-button ui-button--secondary" onClick={() => setIsQuoteModalOpen(false)}>
              Cancelar
            </button>
            <button type="submit" className="btn-primary ui-button ui-button--primary" disabled={isSaving}>
              {isSaving ? 'Salvando...' : 'Salvar Cotação'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Modal 2: Novo Pedido de Venda */}
      <Modal
        isOpen={isOrderModalOpen}
        onClose={() => setIsOrderModalOpen(false)}
        title="Novo Pedido de Venda"
        subtitle="Cadastro direto de pedido comercial"
        size="lg"
      >
        <form onSubmit={handleSaveOrder} className="wizard-form ui-form">
          {modalError && <div className="form-error-callout ui-form__error" role="alert">{modalError}</div>}
          <div className="form-row">
            <div className="form-group flex-2">
              <label>Cliente *</label>
              <input
                type="text"
                required
                placeholder="Nome / Razão Social"
                value={orderCustomerName}
                onChange={(e) => setOrderCustomerName(e.target.value)}
              />
            </div>
            <div className="form-group flex-1">
              <label>Condição de Pgto</label>
              <select value={orderPaymentTerms} onChange={(e) => setOrderPaymentTerms(e.target.value)}>
                <option value="À Vista">À Vista</option>
                <option value="30 DDL">30 DDL</option>
                <option value="30/60 DDL">30/60 DDL</option>
                <option value="PIX">PIX</option>
                <option value="Cartão">Cartão</option>
              </select>
            </div>
            <div className="form-group flex-1">
              <label>Status Entrega</label>
              <select value={orderDeliveryStatus} onChange={(e) => setOrderDeliveryStatus(e.target.value)}>
                <option value="PENDING">Pendente</option>
                <option value="DISPATCHED">Em Trânsito</option>
                <option value="DELIVERED">Entregue</option>
              </select>
            </div>
          </div>

          <div className="form-items-section ui-form__section">
            <div className="section-title-row ui-form__section-header">
              <h4>Produtos do Pedido</h4>
              <button type="button" className="btn-secondary sm ui-button ui-button--secondary ui-button--sm" onClick={handleAddOrderItem}>
                <Plus size={13} /> Adicionar Produto
              </button>
            </div>

            {orderItems.map((item, idx) => (
              <div key={idx} className="dynamic-item-row ui-form__item-row">
                <div className="form-group flex-3">
                  <select
                    value={item.product_id}
                    onChange={(e) => {
                      const pid = e.target.value;
                      const prod = products.find(p => p.id === pid);
                      const updated = [...orderItems];
                      updated[idx].product_id = pid;
                      if (prod) updated[idx].unit_price = safeNumber(prod.reference_price) || 10.00;
                      setOrderItems(updated);
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
                    min="1"
                    placeholder="Qtd"
                    value={item.quantity}
                    onChange={(e) => {
                      const updated = [...orderItems];
                      updated[idx].quantity = Math.max(1, parseInt(e.target.value) || 1);
                      setOrderItems(updated);
                    }}
                  />
                </div>
                <div className="form-group flex-1">
                  <input
                    type="number"
                    step="0.01"
                    placeholder="Preço"
                    value={item.unit_price}
                    onChange={(e) => {
                      const updated = [...orderItems];
                      updated[idx].unit_price = safeNumber(e.target.value);
                      setOrderItems(updated);
                    }}
                  />
                </div>
                <button type="button" className="btn-del-item ui-form__remove" onClick={() => handleRemoveOrderItem(idx)}>
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>

          <div className="modal-footer ui-form__actions">
            <button type="button" className="btn-secondary ui-button ui-button--secondary" onClick={() => setIsOrderModalOpen(false)}>
              Cancelar
            </button>
            <button type="submit" className="btn-primary ui-button ui-button--primary" disabled={isSaving}>
              {isSaving ? 'Salvando...' : 'Salvar Pedido'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Modal 3: Cadastro / Edição de Cliente */}
      <Modal
        isOpen={isCustomerModalOpen}
        onClose={() => setIsCustomerModalOpen(false)}
        title={editingCustomerId ? "Editar Cliente" : "Novo Cliente (PJ / PF)"}
        subtitle="Cadastro centralizado para Vendas, CRM, Faturamento e Identity"
        size="lg"
      >
        <form onSubmit={handleSaveCustomer} className="wizard-form ui-form">
          {modalError && <div className="form-error-callout ui-form__error" role="alert">{modalError}</div>}
          <div className="form-row">
            <div className="form-group flex-1">
              <label>Tipo de Pessoa *</label>
              <select value={custPersonType} onChange={(e) => setCustPersonType(e.target.value as any)}>
                <option value="PJ">Pessoa Jurídica (PJ)</option>
                <option value="PF">Pessoa Física (PF)</option>
              </select>
            </div>
            <div className="form-group flex-2">
              <label>{custPersonType === 'PJ' ? 'Razão Social *' : 'Nome Completo *'}</label>
              <input
                type="text"
                required
                value={custName}
                onChange={(e) => setCustName(e.target.value)}
              />
            </div>
            <div className="form-group flex-1">
              <label>{custPersonType === 'PJ' ? 'CNPJ *' : 'CPF *'}</label>
              <input
                type="text"
                required
                value={custDocument}
                onChange={(e) => setCustDocument(e.target.value)}
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group flex-2">
              <label>Nome Fantasia</label>
              <input
                type="text"
                value={custTradeName}
                onChange={(e) => setCustTradeName(e.target.value)}
              />
            </div>
            <div className="form-group flex-1">
              <label>Inscrição Estadual</label>
              <input
                type="text"
                value={custStateReg}
                onChange={(e) => setCustStateReg(e.target.value)}
              />
            </div>
            <div className="form-group flex-1">
              <label>Limite de Crédito (R$)</label>
              <input
                type="number"
                step="0.01"
                value={custCreditLimit}
                onChange={(e) => setCustCreditLimit(e.target.value)}
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group flex-1">
              <label>E-mail Comercial</label>
              <input
                type="email"
                value={custEmail}
                onChange={(e) => setCustEmail(e.target.value)}
              />
            </div>
            <div className="form-group flex-1">
              <label>Telefone / WhatsApp</label>
              <input
                type="text"
                value={custPhone}
                onChange={(e) => setCustPhone(e.target.value)}
              />
            </div>
            <div className="form-group flex-1">
              <label>Contato Identity</label>
              <select value={custContactId} onChange={(e) => setCustContactId(e.target.value)}>
                <option value="">Nenhum contato vinculado</option>
                {contacts.map(ct => (
                  <option key={ct.id} value={ct.id}>{ct.full_name} ({ct.email || ct.phone || 'S/ dados'})</option>
                ))}
              </select>
            </div>
          </div>

          <div className="modal-footer ui-form__actions">
            <button type="button" className="btn-secondary ui-button ui-button--secondary" onClick={() => setIsCustomerModalOpen(false)}>
              Cancelar
            </button>
            <button type="submit" className="btn-primary ui-button ui-button--primary" disabled={isSaving}>
              {isSaving ? 'Salvando...' : 'Salvar Cliente'}
            </button>
          </div>
        </form>
      </Modal>

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
            <label>Nome do Vendedor *</label>
            <input
              type="text"
              required
              placeholder="Ex: Amanda Silva"
              value={goalSellerName}
              onChange={(e) => setGoalSellerName(e.target.value)}
            />
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
    </div>
  );
};

export default Sales;
