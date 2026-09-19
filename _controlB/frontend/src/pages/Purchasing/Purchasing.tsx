/**
 * pages/Purchasing/Purchasing.tsx - Central Operacional do Módulo de Compras (Procure-to-Pay)
 * 
 * Gerencia de ponta a ponta:
 * 1. 📝 Solicitações de Compra (com itens dinâmicos, edição, exclusão e cálculo em tempo real)
 * 2. 🛡️ Fluxo de Aprovação por Alçada (Parecer de Aprovação/Rejeição)
 * 3. 📊 Processos de Cotação (RFQ - Request For Quotation & Mapa Comparativo de Preços)
 * 4. 🏆 Homologação de Proposta Vencedora e Emissão da Ordem de Compra (PO)
 * 5. 📦 Recebimento Físico no Almoxarifado (Conferência de NF e Entrega)
 * 6. 🚚 Gestão Completa de Fornecedores Homologados (CRUD)
 * 7. 📦 Catálogo Avançado de Produtos, Insumos e Medicamentos (SKU Automático, Rastreabilidade e Validade)
 * 8. 🎯 Centros de Custo e Alocação Orçamentária (CRUD)
 */

import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  ShoppingCart, FileText, Truck, Package, Target, ChevronRight,
  Search, CheckCircle2, XCircle, RefreshCw, Plus, Mail, Phone,
  Loader2, AlertCircle, Trash2, ShieldCheck, Box, Check, BarChart2, Award,
  Tags, Users, Sparkles, Building, X, DollarSign, Zap, SlidersHorizontal,
  CheckSquare, Square, ArrowUpRight, ArrowDownRight, AlertTriangle,
  UploadCloud, Paperclip, ArrowUpDown, ArrowUp, ArrowDown
} from 'lucide-react';
import { purchasingService, inventoryService, cacheManager, formatApiError } from '@/services/api';
import {
  Supplier, Product, ProductCategory, CostCenter,
  PurchaseRequest, PurchaseOrder, QuotationProcess,
  QuotationComparisonMatrix, SupplierQuotePayload,
  PurchaseSuggestionsSummary,
  StockMovement
} from '@/types';
import { formatCurrency, formatQuantity, formatPriceInput, formatQuantityInput } from '@/utils/formatters';

import { Modal } from '@/components/Modal/Modal';
import { ConfirmModal } from '@/components/ConfirmModal/ConfirmModal';
import { BulkActionsBar } from '@/components/BulkActionsBar';
import { ListPagination } from '@/components/ListPagination';
import { useBulkSelection } from '@/hooks/useBulkSelection';
import { useListPagination } from '@/hooks/useListPagination';
import { RecordLink, useRecordDeepLink, isRequestedView } from '@/components/RecordLink';
import { useToast } from '@/components/Toast/ToastContext';
import './Purchasing.scss';

const ALLOWED_PURCHASING_MENUS = [
  'solicitacoes',
  'sugestoes',
  'cotacoes',
  'ordens',
  'fornecedores',
  'produtos',
  'categorias',
  'centros-custo',
  'movimentacoes'
] as const;

type PurchasingMenuOption = typeof ALLOWED_PURCHASING_MENUS[number];

const PRESET_SEGMENTS = [
  'Medicamentos Éticos',
  'Genéricos & Similares',
  'Perfumaria & Cosméticos',
  'Insumos Médicos & Hospitalares',
  'Nutrição & Suplementos',
  'Higiene & Limpeza',
  'Material de Escritório & TI',
  'Equipamentos & Descartáveis'
];

export const Purchasing: React.FC = () => {
  const toast = useToast();
  const [searchParams] = useSearchParams();
  const initialMenu = isRequestedView(searchParams, ALLOWED_PURCHASING_MENUS, 'solicitacoes');
  const [activeMenu, setActiveMenu] = useState<PurchasingMenuOption>(initialMenu);
  const [searchTerm, setSearchTerm] = useState('');
  const [searchField, setSearchField] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [urgencyFilter, setUrgencyFilter] = useState<string>('all');
  const [categoryFilter, setCategoryFilter] = useState<string>('');

  // Ordenação Dinâmica (order_by) por Tabela
  const [reqSortField, setReqSortField] = useState<string>('created_at');
  const [reqSortDir, setReqSortDir] = useState<'asc' | 'desc'>('desc');

  const [quotSortField, setQuotSortField] = useState<string>('created_at');
  const [quotSortDir, setQuotSortDir] = useState<'asc' | 'desc'>('desc');

  const [orderSortField, setOrderSortField] = useState<string>('created_at');
  const [orderSortDir, setOrderSortDir] = useState<'asc' | 'desc'>('desc');

  const [suggSortField, setSuggSortField] = useState<string>('urgency');
  const [suggSortDir, setSuggSortDir] = useState<'asc' | 'desc'>('asc');

  const [supSortField, setSupSortField] = useState<string>('name');
  const [supSortDir, setSupSortDir] = useState<'asc' | 'desc'>('asc');

  const [prodSortField, setProdSortField] = useState<string>('name');
  const [prodSortDir, setProdSortDir] = useState<'asc' | 'desc'>('asc');

  const [catSortField, setCatSortField] = useState<string>('name');
  const [catSortDir, setCatSortDir] = useState<'asc' | 'desc'>('asc');

  const [costSortField, setCostSortField] = useState<string>('code');
  const [costSortDir, setCostSortDir] = useState<'asc' | 'desc'>('asc');

  const [movSortField, setMovSortField] = useState<string>('created_at');
  const [movSortDir, setMovSortDir] = useState<'asc' | 'desc'>('desc');

  // Estados dos Dados carregados da API
  const [requests, setRequests] = useState<PurchaseRequest[]>([]);
  const [quotations, setQuotations] = useState<QuotationProcess[]>([]);
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<ProductCategory[]>([]);
  const [costCenters, setCostCenters] = useState<CostCenter[]>([]);
  const requestSelection = useBulkSelection<PurchaseRequest>();
  const quotationSelection = useBulkSelection<QuotationProcess>();
  const orderSelection = useBulkSelection<PurchaseOrder>();
  const supplierSelection = useBulkSelection<Supplier>();
  const productSelection = useBulkSelection<Product>();
  const categorySelection = useBulkSelection<ProductCategory>();
  const costCenterSelection = useBulkSelection<CostCenter>();

  // --- FLUXO ÁGIL: REPOSIÇÃO & INVENTÁRIO ---
  const [suggestionsSummary, setSuggestionsSummary] = useState<PurchaseSuggestionsSummary | null>(null);
  const [selectedSuggestionProductIds, setSelectedSuggestionProductIds] = useState<string[]>([]);
  const [customSuggestionQtys, setCustomSuggestionQtys] = useState<Record<string, number>>({});

  // Modal de Emissão Rápida de PO a partir de Sugestões
  const [isQuickOrderModalOpen, setIsQuickOrderModalOpen] = useState(false);
  const [replenishmentFlow, setReplenishmentFlow] = useState<'request' | 'order'>('order');
  const [quickOrderSupplierId, setQuickOrderSupplierId] = useState('');
  const [quickOrderCostCenterId, setQuickOrderCostCenterId] = useState('');
  const [quickOrderPaymentTerms, setQuickOrderPaymentTerms] = useState('30 DDL');
  const [quickOrderFreightType, setQuickOrderFreightType] = useState('CIF');
  const [quickOrderFreightAmount, setQuickOrderFreightAmount] = useState('0');
  const [quickOrderDiscountAmount, setQuickOrderDiscountAmount] = useState('0');
  const [quickOrderDeliveryDate, setQuickOrderDeliveryDate] = useState('');
  const [quickOrderNotes, setQuickOrderNotes] = useState('');
  const [quickOrderItems, setQuickOrderItems] = useState<Array<{
    product_id: string;
    product_name: string;
    sku: string;
    unit_of_measure: string;
    quantity: number;
    unit_price: number;
  }>>([]);
  const [selectedProductToAdd, setSelectedProductToAdd] = useState('');

  // Extrato de Movimentações de Estoque
  const [stockMovements, setStockMovements] = useState<StockMovement[]>([]);

  // Estados de Carregamento e Erro
  const [loading, setLoading] = useState(true);

  // Modais de Criação & Edição
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // Estados para Edição
  const [editingSupplier, setEditingSupplier] = useState<Supplier | null>(null);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [editingCategory, setEditingCategory] = useState<ProductCategory | null>(null);
  const [editingCostCenter, setEditingCostCenter] = useState<CostCenter | null>(null);
  const [editingRequest, setEditingRequest] = useState<PurchaseRequest | null>(null);

  // Campos de Fornecedor (Comercial, Segmentos, Regulatório)
  const [supplierName, setSupplierName] = useState('');
  const [supplierTradeName, setSupplierTradeName] = useState('');
  const [supplierCnpj, setSupplierCnpj] = useState('');
  const [supplierStateRegistration, setSupplierStateRegistration] = useState('');
  const [supplierContactName, setSupplierContactName] = useState('');
  const [supplierSegments, setSupplierSegments] = useState<string[]>([]);
  const [supplierCustomSegment, setSupplierCustomSegment] = useState('');
  const [supplierPaymentTerms, setSupplierPaymentTerms] = useState('30 DDL');
  const [supplierMinOrderAmount, setSupplierMinOrderAmount] = useState('0');
  const [supplierAnvisaLicense, setSupplierAnvisaLicense] = useState('');
  const [supplierNotes, setSupplierNotes] = useState('');
  const [supplierEmail, setSupplierEmail] = useState('');
  const [supplierPhone, setSupplierPhone] = useState('');
  const [supplierAddress, setSupplierAddress] = useState('');
  const [supplierCity, setSupplierCity] = useState('');
  const [supplierState, setSupplierState] = useState('');
  const [supplierZipCode, setSupplierZipCode] = useState('');

  // Modal de Confirmação & Exclusão Estilizado (Substitui window.confirm e window.alert)
  const [confirmModal, setConfirmModal] = useState<{
    isOpen: boolean;
    title: string;
    subtitle?: string;
    message: React.ReactNode;
    confirmText?: string;
    cancelText?: string;
    type?: 'danger' | 'warning' | 'info' | 'success';
    isLoading?: boolean;
    errorMessage?: string | null;
    onConfirm: () => Promise<void>;
  }>({
    isOpen: false,
    title: '',
    message: '',
    onConfirm: async () => {},
  });

  const openConfirmModal = (config: {
    title: string;
    subtitle?: string;
    message: React.ReactNode;
    confirmText?: string;
    cancelText?: string;
    type?: 'danger' | 'warning' | 'info' | 'success';
    onConfirm: () => Promise<void>;
  }) => {
    setConfirmModal({
      isOpen: true,
      title: config.title,
      subtitle: config.subtitle,
      message: config.message,
      confirmText: config.confirmText || 'Confirmar Exclusão',
      cancelText: config.cancelText || 'Cancelar',
      type: config.type || 'danger',
      isLoading: false,
      errorMessage: null,
      onConfirm: config.onConfirm,
    });
  };

  const closeConfirmModal = () => {
    setConfirmModal(prev => ({ ...prev, isOpen: false, errorMessage: null, isLoading: false }));
  };


  // Campos de Categoria de Produto
  const [categoryName, setCategoryName] = useState('');
  const [categoryCode, setCategoryCode] = useState('');
  const [categoryDesc, setCategoryDesc] = useState('');

  // Campos de Produto (Básico + Rastreabilidade + Estoque)
  const [productSku, setProductSku] = useState('');
  const [productName, setProductName] = useState('');
  const [productDesc, setProductDesc] = useState('');
  const [productUnit, setProductUnit] = useState('UN');
  const [productPrice, setProductPrice] = useState('0');
  const [productCategoryId, setProductCategoryId] = useState('');
  const [productBrand, setProductBrand] = useState('');
  const [productBarcode, setProductBarcode] = useState('');
  const [productNcm, setProductNcm] = useState('');
  const [productIsPerishable, setProductIsPerishable] = useState(false);
  const [productRequiresBatch, setProductRequiresBatch] = useState(false);
  const [productShelfLifeDays, setProductShelfLifeDays] = useState('');
  const [productCurrentStock, setProductCurrentStock] = useState('0');
  const [productMinStock, setProductMinStock] = useState('0');
  const [productMaxStock, setProductMaxStock] = useState('');
  const [productStorageLocation, setProductStorageLocation] = useState('');

  // Campos de Centro de Custo
  const [costCenterCode, setCostCenterCode] = useState('');
  const [costCenterName, setCostCenterName] = useState('');
  const [costCenterDesc, setCostCenterDesc] = useState('');

  // Campos de Solicitação de Compra
  const [requestJustification, setRequestJustification] = useState('');
  const [requestCostCenterId, setRequestCostCenterId] = useState('');
  const [requestRequiredDate, setRequestRequiredDate] = useState('');
  const [requestItems, setRequestItems] = useState<Array<{
    product_id: string;
    quantity: number;
    estimated_unit_price: number;
    notes?: string;
  }>>([]);

  // Modal de Aprovação de Solicitação
  const [isApprovalModalOpen, setIsApprovalModalOpen] = useState(false);
  const [selectedRequestForApproval, setSelectedRequestForApproval] = useState<PurchaseRequest | null>(null);
  const [approvalDecision, setApprovalDecision] = useState<'approved' | 'rejected'>('approved');
  const [approvalComments, setApprovalComments] = useState('');

  // =========================================================================
  // ESTADOS DO FLUXO DE COTAÇÃO (RFQ) & MAPA COMPARATIVO
  // =========================================================================
  const [isAddQuoteModalOpen, setIsAddQuoteModalOpen] = useState(false);
  const [activeQuotationForQuote, setActiveQuotationForQuote] = useState<QuotationProcess | null>(null);
  const [quoteSupplierId, setQuoteSupplierId] = useState('');
  const [quoteReference, setQuoteReference] = useState('');
  const [quotePaymentTerms, setQuotePaymentTerms] = useState('30 DDL');
  const [quoteFreightType, setQuoteFreightType] = useState('CIF');
  const [quoteFreightAmount, setQuoteFreightAmount] = useState('0');
  const [quoteDiscountAmount, setQuoteDiscountAmount] = useState('0');
  const [quoteLeadTimeDays, setQuoteLeadTimeDays] = useState('5');
  const [quoteValidUntil, setQuoteValidUntil] = useState('');
  const [quoteNotes, setQuoteNotes] = useState('');
  const [quoteItems, setQuoteItems] = useState<Array<{
    product_id: string;
    quantity: number;
    unit_price: number;
    brand_offered?: string;
    notes?: string;
  }>>([]);

  // Modal de Mapa Comparativo
  const [isComparisonModalOpen, setIsComparisonModalOpen] = useState(false);
  const [comparisonMatrix, setComparisonMatrix] = useState<QuotationComparisonMatrix | null>(null);
  const [loadingComparison, setLoadingComparison] = useState(false);

  // Modal de Recebimento de Ordem no Almoxarifado
  const [isReceiveModalOpen, setIsReceiveModalOpen] = useState(false);
  const [selectedOrderForReceive, setSelectedOrderForReceive] = useState<PurchaseOrder | null>(null);
  const [receiveInvoiceNumber, setReceiveInvoiceNumber] = useState('');
  const [receiveInvoiceType, setReceiveInvoiceType] = useState<'NFE' | 'NFSE' | 'NFCE' | 'CTE' | 'OUTRO'>('NFE');
  const [receiveInvoiceSeries, setReceiveInvoiceSeries] = useState('');
  const [receiveInvoiceAccessKey, setReceiveInvoiceAccessKey] = useState('');
  const [receiveInvoiceIssueDate, setReceiveInvoiceIssueDate] = useState('');
  const [receiveGeneratePayable, setReceiveGeneratePayable] = useState(false);
  const [receivePayableDueDate, setReceivePayableDueDate] = useState('');
  const [receiveInstallments, setReceiveInstallments] = useState('1');
  const [receiveInstallmentFrequency, setReceiveInstallmentFrequency] = useState('30');
  const [receiveExpenseNature, setReceiveExpenseNature] = useState<'OPEX' | 'CAPEX'>('OPEX');
  const [receivePaymentMethod, setReceivePaymentMethod] = useState('BOLETO');
  const [receiveDigitableLine, setReceiveDigitableLine] = useState('');
  const [receiveBarcode, setReceiveBarcode] = useState('');
  const [receivePixCode, setReceivePixCode] = useState('');
  const [receiveTaxAmount, setReceiveTaxAmount] = useState('');
  const [receiveInvoiceAttachment, setReceiveInvoiceAttachment] = useState<string | null>(null);
  const [receiveInvoiceAttachmentName, setReceiveInvoiceAttachmentName] = useState<string | null>(null);
  const [receiveNotes, setReceiveNotes] = useState('');

  // Modal de Detalhes / Espelho da Ordem de Compra
  const [isViewOrderModalOpen, setIsViewOrderModalOpen] = useState(false);
  const [selectedOrderForView, setSelectedOrderForView] = useState<PurchaseOrder | null>(null);

  // Carregamento Inicial
  useEffect(() => {
    loadAllPurchasingData();
  }, []);

  const loadAllPurchasingData = async (forceRefresh = false) => {
    const cachedRequests = cacheManager.get<PurchaseRequest[]>('purchasing:requests');
    if (!cachedRequests && !requests.length) {
      setLoading(true);
    } else if (forceRefresh) {
      setLoading(true);
    }

    try {
      const [reqData, quotData, poData, supData, prodData, catData, ccData, suggData, movData] = await Promise.all([
        purchasingService.getPurchaseRequests(forceRefresh),
        purchasingService.getQuotationProcesses(undefined, forceRefresh),
        purchasingService.getPurchaseOrders(undefined, forceRefresh),
        purchasingService.getSuppliers(forceRefresh),
        inventoryService.getProducts(undefined, forceRefresh),
        inventoryService.getCategories(forceRefresh),
        purchasingService.getCostCenters(forceRefresh),
        purchasingService.getReplenishmentSuggestions(forceRefresh),
        inventoryService.getInventoryMovements(undefined, undefined, forceRefresh)
      ]);

      setRequests(reqData);
      setQuotations(quotData);
      setOrders(poData);
      setSuppliers(supData);
      setProducts(prodData);
      setCategories(catData);
      setCostCenters(ccData);
      setSuggestionsSummary(suggData);
      setStockMovements(movData);
    } catch (err: any) {
      console.error("Erro ao carregar módulo de compras:", err);
    } finally {
      setLoading(false);
    }
  };


  // =========================================================================
  // GERAÇÃO AUTOMÁTICA DE SKU INTELIGENTE
  // =========================================================================
  const generateAutomaticSku = (name: string, categoryId: string, isPerishable: boolean) => {
    if (!name || name.trim().length === 0) return '';
    const cleanName = name.trim().toUpperCase()
      .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .replace(/[^A-Z0-9\s]/g, '');

    const words = cleanName.split(/\s+/).filter(Boolean);
    let namePrefix = 'PRD';
    if (words.length === 1) {
      namePrefix = words[0].substring(0, 4);
    } else if (words.length === 2) {
      namePrefix = `${words[0].substring(0, 2)}${words[1].substring(0, 2)}`;
    } else if (words.length >= 3) {
      namePrefix = `${words[0][0]}${words[1][0]}${words[2][0]}${words[3] ? words[3][0] : ''}`;
    }

    let catPrefix = 'GEN';
    if (categoryId) {
      const cat = categories.find(c => c.id === categoryId);
      if (cat && cat.code) {
        catPrefix = cat.code.toUpperCase().replace(/[^A-Z0-9]/g, '').substring(0, 3);
      } else if (cat && cat.name) {
        catPrefix = cat.name.trim().toUpperCase().replace(/[^A-Z0-9]/g, '').substring(0, 3);
      }
    }

    const typeSuffix = isPerishable ? 'PER' : 'MAT';
    const randSeq = Math.floor(100 + Math.random() * 900);
    return `${catPrefix}-${namePrefix}-${typeSuffix}-${randSeq}`.toUpperCase();
  };

  // =========================================================================
  // FLUXO DE COTAÇÃO (RFQ) & MAPA COMPARATIVO
  // =========================================================================
  const handleStartQuotation = async (req: PurchaseRequest) => {
    try {
      setIsSaving(true);
      const quot = await purchasingService.openQuotationProcess(req.id, "Processo de Cotação de Fornecedores");
      await loadAllPurchasingData();
      setActiveMenu('cotacoes');
      handleOpenAddQuoteModal(quot);
      toast.success("Processo de cotação aberto com sucesso!");
    } catch (err: any) {
      toast.error(formatApiError(err, "Erro ao abrir processo de cotação."));
    } finally {
      setIsSaving(false);
    }
  };

  const handleOpenAddQuoteModal = (quot: QuotationProcess) => {
    setActiveQuotationForQuote(quot);
    setQuoteSupplierId('');
    setQuoteReference(`PROP-${Math.floor(1000 + Math.random() * 9000)}/2026`);
    setQuotePaymentTerms('30 DDL');
    setQuoteFreightType('CIF');
    setQuoteFreightAmount('0');
    setQuoteDiscountAmount('0');
    setQuoteLeadTimeDays('5');
    setQuoteValidUntil('');
    setQuoteNotes('');

    // Preenche os itens com os produtos da solicitação de compra
    const initialItems = (quot.purchase_request?.items || []).map(it => ({
      product_id: it.product_id,
      quantity: Number(it.quantity),
      unit_price: Number(it.estimated_unit_price) || 0,
      brand_offered: '',
      notes: ''
    }));

    setQuoteItems(initialItems);
    setModalError(null);
    setIsAddQuoteModalOpen(true);
  };

  const handleSaveSupplierQuote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeQuotationForQuote) return;

    if (!quoteSupplierId) {
      setModalError("Selecione o fornecedor participante.");
      return;
    }

    if (quoteItems.some(it => it.unit_price <= 0)) {
      setModalError("Preencha o preço unitário cotado para todos os itens.");
      return;
    }

    setIsSaving(true);
    setModalError(null);

    try {
      const payload: SupplierQuotePayload = {
        supplier_id: quoteSupplierId,
        quote_reference: quoteReference || undefined,
        payment_terms: quotePaymentTerms || undefined,
        freight_type: quoteFreightType || undefined,
        freight_amount: parseFloat(quoteFreightAmount) || 0,
        discount_amount: parseFloat(quoteDiscountAmount) || 0,
        lead_time_days: parseInt(quoteLeadTimeDays) || undefined,
        valid_until: quoteValidUntil ? new Date(quoteValidUntil).toISOString() : undefined,
        notes: quoteNotes || undefined,
        items: quoteItems.map(it => ({
          product_id: it.product_id,
          quantity: it.quantity,
          unit_price: it.unit_price,
          brand_offered: it.brand_offered || undefined,
          notes: it.notes || undefined
        }))
      };

      await purchasingService.addSupplierQuote(activeQuotationForQuote.id, payload);
      await loadAllPurchasingData();
      setIsAddQuoteModalOpen(false);
      toast.success("Proposta do fornecedor salva com sucesso!");
    } catch (err: any) {
      setModalError(formatApiError(err, "Erro ao salvar proposta do fornecedor."));
    } finally {
      setIsSaving(false);
    }
  };

  const handleOpenComparisonModal = async (quot: QuotationProcess) => {
    setLoadingComparison(true);
    setIsComparisonModalOpen(true);
    try {
      const matrix = await purchasingService.getQuotationComparison(quot.id);
      setComparisonMatrix(matrix);
    } catch (err: any) {
      toast.error(formatApiError(err, "Erro ao gerar mapa comparativo."));
      setIsComparisonModalOpen(false);
    } finally {
      setLoadingComparison(false);
    }
  };


  const handleSelectWinnerQuote = (quotationId: string, quoteId: string) => {
    openConfirmModal({
      title: 'Homologar Proposta Vencedora',
      subtitle: 'Emissão de Ordem de Compra',
      message: 'Deseja homologar esta proposta como vencedora e gerar a Ordem de Compra oficial?',
      confirmText: 'Homologar e Gerar Ordem',
      type: 'success',
      onConfirm: async () => {
        try {
          setIsSaving(true);
          await purchasingService.selectWinnerQuote(quotationId, quoteId, "Homologado pelo Comprador");
          closeConfirmModal();
          await loadAllPurchasingData();
          setIsComparisonModalOpen(false);
          setActiveMenu('ordens');
          toast.success("Proposta homologada e Ordem de Compra gerada com sucesso!");
        } catch (err: any) {
          toast.error(formatApiError(err, "Erro ao homologar proposta vencedora."));
        } finally {
          setIsSaving(false);
        }
      }
    });
  };

  const handleCancelRequest = (requestId: string) => {
    openConfirmModal({
      title: 'Cancelar Solicitação de Compra',
      subtitle: `Solicitação #${requestId.slice(0, 8)}`,
      message: 'Deseja realmente cancelar esta solicitação de compra e eventuais cotações vinculadas?',
      confirmText: 'Cancelar Solicitação',
      type: 'danger',
      onConfirm: async () => {
        try {
          setIsSaving(true);
          await purchasingService.cancelPurchaseRequest(requestId);
          closeConfirmModal();
          await loadAllPurchasingData();
          toast.success("Solicitação de compra cancelada com sucesso!");
        } catch (err: any) {
          toast.error(formatApiError(err, "Erro ao cancelar solicitação de compra."));
        } finally {
          setIsSaving(false);
        }
      }
    });
  };

  const handleCancelQuotation = (quotationId: string) => {
    openConfirmModal({
      title: 'Cancelar Processo de Cotação',
      subtitle: `Cotação #${quotationId.slice(0, 8)}`,
      message: "Deseja realmente cancelar este processo de cotação? A solicitação de compra voltará para o status 'Aprovada'.",
      confirmText: 'Cancelar Cotação',
      type: 'danger',
      onConfirm: async () => {
        try {
          setIsSaving(true);
          await purchasingService.cancelQuotation(quotationId);
          closeConfirmModal();
          await loadAllPurchasingData();
          setIsComparisonModalOpen(false);
          toast.success("Processo de cotação cancelado com sucesso!");
        } catch (err: any) {
          toast.error(formatApiError(err, "Erro ao cancelar processo de cotação."));
        } finally {
          setIsSaving(false);
        }
      }
    });
  };

  const handleReopenQuotation = (quotationId: string) => {
    openConfirmModal({
      title: 'Reabrir Processo de Cotação',
      subtitle: `Cotação #${quotationId.slice(0, 8)}`,
      message: 'Deseja reabrir este processo de cotação? A homologação será desfeita e eventuais ordens de compra emitidas serão canceladas.',
      confirmText: 'Reabrir Cotação',
      type: 'warning',
      onConfirm: async () => {
        try {
          setIsSaving(true);
          await purchasingService.reopenQuotation(quotationId);
          closeConfirmModal();
          await loadAllPurchasingData();
          const matrix = await purchasingService.getQuotationComparison(quotationId);
          setComparisonMatrix(matrix);
          toast.success("Processo de cotação reaberto com sucesso!");
        } catch (err: any) {
          toast.error(formatApiError(err, "Erro ao reabrir processo de cotação."));
        } finally {
          setIsSaving(false);
        }
      }
    });
  };

  const handleDeleteSupplierQuote = (quotationId: string, quoteId: string) => {
    openConfirmModal({
      title: 'Excluir Proposta Comercial',
      subtitle: 'Esta cotação enviada pelo fornecedor será removida da matriz comparativa.',
      type: 'danger',
      message: 'Deseja realmente excluir esta proposta de fornecedor?',
      confirmText: 'Excluir Proposta',
      onConfirm: async () => {
        await purchasingService.deleteSupplierQuote(quotationId, quoteId);
        await loadAllPurchasingData();
        const matrix = await purchasingService.getQuotationComparison(quotationId);
        setComparisonMatrix(matrix);
      }
    });
  };

  const handleCancelOrder = (orderId: string, orderNumber: string) => {
    openConfirmModal({
      title: 'Cancelar Ordem de Compra',
      subtitle: 'O pedido deixará de constar como ativo no fluxo de suprimentos.',
      type: 'warning',
      message: (
        <>
          Deseja realmente cancelar a Ordem de Compra oficial <span className="highlight-item">{orderNumber}</span>?
        </>
      ),
      confirmText: 'Cancelar Pedido',
      onConfirm: async () => {
        await purchasingService.cancelPurchaseOrder(orderId);
        await loadAllPurchasingData();
      }
    });
  };


  // =========================================================================
  // GESTÃO DE CADASTROS (EDIÇÃO E EXCLUSÃO)
  // =========================================================================
  const handleEditSupplier = (sup: Supplier) => {
    setEditingSupplier(sup);
    setSupplierName(sup.name);
    setSupplierTradeName(sup.trade_name || '');
    setSupplierCnpj(sup.cnpj_cpf || '');
    setSupplierStateRegistration(sup.state_registration || '');
    setSupplierContactName(sup.contact_name || '');
    setSupplierSegments(sup.segments ? sup.segments.split(',').map(s => s.trim()).filter(Boolean) : []);
    setSupplierCustomSegment('');
    setSupplierPaymentTerms(sup.payment_terms || '30 DDL');
    setSupplierMinOrderAmount(sup.min_order_amount !== undefined ? String(sup.min_order_amount) : '0');
    setSupplierAnvisaLicense(sup.anvisa_license || '');
    setSupplierNotes(sup.notes || '');
    setSupplierEmail(sup.email || '');
    setSupplierPhone(sup.phone || '');
    setSupplierAddress(sup.address || '');
    setSupplierCity(sup.city || '');
    setSupplierState(sup.state || '');
    setSupplierZipCode(sup.zip_code || '');
    setModalError(null);
    setIsModalOpen(true);
  };

  const handleDeleteSupplier = (sup: Supplier) => {
    openConfirmModal({
      title: 'Excluir Fornecedor',
      subtitle: 'Esta ação removerá o parceiro do catálogo de compras.',
      type: 'danger',
      message: (
        <>
          Deseja realmente excluir o fornecedor <span className="highlight-item">{sup.name}</span> ({sup.cnpj_cpf || 'Sem CNPJ'})?
          <div className="alert-callout">
            <strong>Atenção:</strong> Fornecedores com histórico de compras ou cotações homologadas não podem ser excluídos fisicamente.
          </div>
        </>
      ),
      confirmText: 'Excluir Fornecedor',

      onConfirm: async () => {
        setConfirmModal(prev => ({ ...prev, isLoading: true, errorMessage: null }));
        try {
          await purchasingService.deleteSupplier(sup.id);
          await loadAllPurchasingData();
          closeConfirmModal();
        } catch (err: any) {
          setConfirmModal(prev => ({
            ...prev,
            isLoading: false,
            errorMessage: err?.response?.data?.detail || 'Erro ao excluir fornecedor. Verifique se ele possui cotações ou ordens vinculadas.'
          }));
        }
      }
    });
  };

  const handleEditCategory = (cat: ProductCategory) => {
    setEditingCategory(cat);
    setCategoryName(cat.name);
    setCategoryCode(cat.code || '');
    setCategoryDesc(cat.description || '');
    setModalError(null);
    setIsModalOpen(true);
  };

  const handleDeleteCategory = (cat: ProductCategory) => {
    openConfirmModal({
      title: 'Excluir Categoria',
      subtitle: 'Esta ação removerá a categoria de produtos.',
      type: 'danger',
      message: (
        <>
          Deseja realmente excluir a categoria <span className="highlight-item">{cat.name}</span>?
          <div className="alert-callout">
            <strong>Atenção:</strong> Categorias que possuem produtos vinculados não podem ser excluídas.
          </div>
        </>
      ),
      confirmText: 'Excluir Categoria',
      onConfirm: async () => {
        setConfirmModal(prev => ({ ...prev, isLoading: true, errorMessage: null }));
        try {
          await inventoryService.deleteCategory(cat.id);
          await loadAllPurchasingData();
          closeConfirmModal();
        } catch (err: any) {
          setConfirmModal(prev => ({
            ...prev,
            isLoading: false,
            errorMessage: err?.response?.data?.detail || 'Erro ao excluir categoria de produto.'
          }));
        }
      }
    });
  };

  const handleEditProduct = (prod: Product) => {
    setEditingProduct(prod);
    setProductName(prod.name);
    setProductSku(prod.sku);
    setProductDesc(prod.description || '');
    setProductUnit(prod.unit_of_measure);
    setProductPrice(formatPriceInput(prod.reference_price));
    setProductCategoryId(prod.category_id || '');
    setProductBrand(prod.brand || '');
    setProductBarcode(prod.barcode || '');
    setProductNcm(prod.ncm || '');
    setProductIsPerishable(Boolean(prod.is_perishable));
    setProductRequiresBatch(Boolean(prod.requires_batch));
    setProductShelfLifeDays(prod.shelf_life_days ? String(prod.shelf_life_days) : '');
    setProductCurrentStock(formatQuantityInput(prod.current_stock));
    setProductMinStock(formatQuantityInput(prod.min_stock));
    setProductMaxStock(prod.max_stock ? formatQuantityInput(prod.max_stock) : '');
    setProductStorageLocation(prod.storage_location || '');
    setModalError(null);
    setIsModalOpen(true);
  };

  const handleDeleteProduct = (prod: Product) => {
    openConfirmModal({
      title: 'Excluir Produto',
      subtitle: 'Esta ação removerá o produto do catálogo e do inventário.',
      type: 'danger',
      message: (
        <>
          Deseja realmente excluir o produto <span className="highlight-item">{prod.name}</span> (SKU: {prod.sku})?
          <div className="alert-callout">
            <strong>Atenção:</strong> Se o produto constar em Solicitações, Cotações ou Ordens de Compra, a exclusão será bloqueada para proteger o histórico.
          </div>
        </>
      ),
      confirmText: 'Excluir Produto',
      onConfirm: async () => {
        setConfirmModal(prev => ({ ...prev, isLoading: true, errorMessage: null }));
        try {
          await inventoryService.deleteProduct(prod.id);
          await loadAllPurchasingData();
          closeConfirmModal();
        } catch (err: any) {
          setConfirmModal(prev => ({
            ...prev,
            isLoading: false,
            errorMessage: err?.response?.data?.detail || 'Erro ao excluir produto.'
          }));
        }
      }
    });
  };


  const handleEditCostCenter = (cc: CostCenter) => {
    setEditingCostCenter(cc);
    setCostCenterCode(cc.code);
    setCostCenterName(cc.name);
    setCostCenterDesc(cc.description || '');
    setModalError(null);
    setIsModalOpen(true);
  };

  const handleDeleteCostCenter = (cc: CostCenter) => {
    openConfirmModal({
      title: 'Excluir Centro de Custo',
      subtitle: 'Esta ação removerá a conta contábil/departamento.',
      type: 'danger',
      message: (
        <>
          Deseja realmente excluir o centro de custo <span className="highlight-item">{cc.name}</span> ({cc.code})?
        </>
      ),
      confirmText: 'Excluir Centro de Custo',
      onConfirm: async () => {
        setConfirmModal(prev => ({ ...prev, isLoading: true, errorMessage: null }));
        try {
          await purchasingService.deleteCostCenter(cc.id);
          await loadAllPurchasingData();
          closeConfirmModal();
        } catch (err: any) {
          setConfirmModal(prev => ({
            ...prev,
            isLoading: false,
            errorMessage: err?.response?.data?.detail || 'Erro ao excluir centro de custo.'
          }));
        }
      }
    });
  };

  const handleEditRequest = (req: PurchaseRequest) => {
    setEditingRequest(req);
    setRequestJustification(req.justification);
    setRequestCostCenterId(req.cost_center_id || '');
    setRequestRequiredDate(req.required_date ? req.required_date.substring(0, 10) : '');
    setModalError(null);
    setIsModalOpen(true);
  };

  const handleDeleteRequest = (req: PurchaseRequest) => {
    openConfirmModal({
      title: 'Excluir Solicitação de Compra',
      subtitle: 'Esta ação removerá permanentemente a solicitação e seus itens.',
      type: 'danger',
      message: (
        <>
          Deseja realmente excluir permanentemente a solicitação <span className="highlight-item">{req.request_number}</span>?
          <div className="alert-callout">
            <strong>Atenção:</strong> Todos os itens associados a esta solicitação de compra serão removidos.
          </div>
        </>
      ),
      confirmText: 'Excluir Solicitação',
      onConfirm: async () => {
        setConfirmModal(prev => ({ ...prev, isLoading: true, errorMessage: null }));
        try {
          await purchasingService.deletePurchaseRequest(req.id);
          await loadAllPurchasingData();
          closeConfirmModal();
        } catch (err: any) {
          setConfirmModal(prev => ({
            ...prev,
            isLoading: false,
            errorMessage: err?.response?.data?.detail || 'Erro ao excluir solicitação de compra.'
          }));
        }
      }
    });
  };

  const handlePurgeAllRequests = () => {
    if (requests.length === 0) return;
    openConfirmModal({
      title: 'Limpar Solicitações de Compra',
      subtitle: 'Rotina de Desenvolvimento & Testes',
      type: 'danger',
      message: (
        <>
          Deseja realmente excluir permanentemente <strong>TODAS as {requests.length} solicitações de compra</strong>?
          <div className="alert-callout">
            <strong>⚠️ Ação Irreversível:</strong> Esta ação removerá em lote todas as solicitações, itens e processos associados criados durante os testes.
          </div>
        </>
      ),
      confirmText: `Excluir Todas (${requests.length})`,
      onConfirm: async () => {
        setConfirmModal(prev => ({ ...prev, isLoading: true, errorMessage: null }));
        try {
          await purchasingService.purgePurchaseRequests();
          await loadAllPurchasingData();
          closeConfirmModal();
        } catch (err: any) {
          setConfirmModal(prev => ({
            ...prev,
            isLoading: false,
            errorMessage: err?.response?.data?.detail || 'Erro ao remover solicitações de compra.'
          }));
        }
      }
    });
  };

  const handleDeleteQuotation = (quot: QuotationProcess) => {
    openConfirmModal({
      title: 'Excluir Cotação (RFQ)',
      subtitle: 'Esta ação removerá o processo de cotação e todas as propostas concorrentes.',
      type: 'danger',
      message: (
        <>
          Deseja realmente excluir permanentemente a cotação <span className="highlight-item">{quot.quotation_number}</span> com {quot.quotes.length} proposta(s)?
        </>
      ),
      confirmText: 'Excluir Cotação',
      onConfirm: async () => {
        setConfirmModal(prev => ({ ...prev, isLoading: true, errorMessage: null }));
        try {
          await purchasingService.deleteQuotation(quot.id);
          await loadAllPurchasingData();
          closeConfirmModal();
        } catch (err: any) {
          setConfirmModal(prev => ({
            ...prev,
            isLoading: false,
            errorMessage: err?.response?.data?.detail || 'Erro ao excluir processo de cotação.'
          }));
        }
      }
    });
  };

  const handlePurgeAllQuotations = () => {
    if (quotations.length === 0) return;
    openConfirmModal({
      title: 'Limpar Cotações (RFQ)',
      subtitle: 'Rotina de Desenvolvimento & Testes',
      type: 'danger',
      message: (
        <>
          Deseja realmente excluir permanentemente <strong>TODAS as {quotations.length} cotações de teste</strong>?
        </>
      ),
      confirmText: `Excluir Todas (${quotations.length})`,
      onConfirm: async () => {
        setConfirmModal(prev => ({ ...prev, isLoading: true, errorMessage: null }));
        try {
          await purchasingService.purgeQuotations();
          await loadAllPurchasingData();
          closeConfirmModal();
        } catch (err: any) {
          setConfirmModal(prev => ({
            ...prev,
            isLoading: false,
            errorMessage: err?.response?.data?.detail || 'Erro ao remover cotações.'
          }));
        }
      }
    });
  };

  const handleDeleteOrder = (order: PurchaseOrder) => {
    openConfirmModal({
      title: 'Excluir Ordem de Compra (PO)',
      subtitle: 'Esta ação removerá a ordem de compra emitida.',
      type: 'danger',
      message: (
        <>
          Deseja realmente excluir a ordem de compra <span className="highlight-item">{order.order_number}</span>?
          <div className="alert-callout">
            <strong>Atenção:</strong> A remoção da ordem de compra desvinculará o produto e os itens associados.
          </div>
        </>
      ),
      confirmText: 'Excluir Ordem de Compra',
      onConfirm: async () => {
        setConfirmModal(prev => ({ ...prev, isLoading: true, errorMessage: null }));
        try {
          await purchasingService.deletePurchaseOrder(order.id);
          await loadAllPurchasingData();
          closeConfirmModal();
        } catch (err: any) {
          setConfirmModal(prev => ({
            ...prev,
            isLoading: false,
            errorMessage: err?.response?.data?.detail || 'Erro ao excluir ordem de compra.'
          }));
        }
      }
    });
  };

  const handlePurgeAllOrders = () => {
    if (orders.length === 0) return;
    openConfirmModal({
      title: 'Limpar Ordens de Compra (PO)',
      subtitle: 'Rotina de Desenvolvimento & Testes',
      type: 'danger',
      message: (
        <>
          Deseja realmente excluir permanentemente <strong>TODAS as {orders.length} ordens de compra de teste</strong>?
        </>
      ),
      confirmText: `Excluir Todas (${orders.length})`,
      onConfirm: async () => {
        setConfirmModal(prev => ({ ...prev, isLoading: true, errorMessage: null }));
        try {
          await purchasingService.purgePurchaseOrders();
          await loadAllPurchasingData();
          closeConfirmModal();
        } catch (err: any) {
          setConfirmModal(prev => ({
            ...prev,
            isLoading: false,
            errorMessage: err?.response?.data?.detail || 'Erro ao remover ordens de compra.'
          }));
        }
      }
    });
  };

  useRecordDeepLink({
    types: ['SUPPLIER'],
    records: suppliers,
    onOpen: (sup) => {
      setActiveMenu('fornecedores');
      handleEditSupplier(sup);
    },
  });

  useRecordDeepLink({
    types: ['PRODUCT'],
    records: products,
    onOpen: (prod) => {
      setActiveMenu('produtos');
      handleEditProduct(prod);
    },
  });

  useRecordDeepLink({
    types: ['PURCHASE_REQUEST'],
    records: requests,
    onOpen: (req) => {
      setActiveMenu('solicitacoes');
      handleEditRequest(req);
    },
  });

  useRecordDeepLink({
    types: ['PURCHASE_QUOTATION'],
    records: quotations,
    onOpen: (quot) => {
      setActiveMenu('cotacoes');
      void handleOpenComparisonModal(quot);
    },
  });

  useRecordDeepLink({
    types: ['PURCHASE_ORDER'],
    records: orders,
    onOpen: (order) => {
      setActiveMenu('ordens');
      setSelectedOrderForView(order);
      setIsViewOrderModalOpen(true);
    },
  });




  // =========================================================================
  // GESTÃO DE CADASTROS (ABERTURA DO MODAL DE CRIAÇÃO)
  // =========================================================================
  const handleOpenCreateModal = () => {
    setEditingSupplier(null);
    setEditingProduct(null);
    setEditingCategory(null);
    setEditingCostCenter(null);
    setEditingRequest(null);
    setModalError(null);

    if (activeMenu === 'solicitacoes') {
      setRequestJustification('');
      setRequestCostCenterId(costCenters[0]?.id || '');
      setRequestRequiredDate('');
      if (products.length > 0) {
        setRequestItems([{
          product_id: products[0].id,
          quantity: 1,
          estimated_unit_price: Number(products[0].reference_price) || 0
        }]);
      } else {
        setRequestItems([]);
      }
    } else if (activeMenu === 'fornecedores') {
      setSupplierName('');
      setSupplierTradeName('');
      setSupplierCnpj('');
      setSupplierStateRegistration('');
      setSupplierContactName('');
      setSupplierSegments([]);
      setSupplierCustomSegment('');
      setSupplierPaymentTerms('30 DDL');
      setSupplierMinOrderAmount('0');
      setSupplierAnvisaLicense('');
      setSupplierNotes('');
      setSupplierEmail('');
      setSupplierPhone('');
      setSupplierAddress('');
      setSupplierCity('');
      setSupplierState('');
      setSupplierZipCode('');
    } else if (activeMenu === 'categorias') {
      setCategoryName('');
      setCategoryCode('');
      setCategoryDesc('');
    } else if (activeMenu === 'produtos') {
      setProductName('');
      setProductDesc('');
      setProductUnit('UN');
      setProductPrice('0');
      setProductCategoryId(categories[0]?.id || '');
      setProductBrand('');
      setProductBarcode('');
      setProductNcm('');
      setProductIsPerishable(false);
      setProductRequiresBatch(false);
      setProductShelfLifeDays('');
      setProductCurrentStock('0');
      setProductMinStock('0');
      setProductMaxStock('');
      setProductStorageLocation('');
      setProductSku(generateAutomaticSku('Novo Produto', categories[0]?.id || '', false));
    } else if (activeMenu === 'centros-custo') {
      setCostCenterCode(`CC-${Math.floor(100 + Math.random() * 900)}`);
      setCostCenterName('');
      setCostCenterDesc('');
    }
    setIsModalOpen(true);
  };

  const handleSaveNewItem = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setModalError(null);

    try {
      if (activeMenu === 'solicitacoes') {
        if (!requestJustification.trim()) {
          setModalError("A justificativa da compra é obrigatória.");
          setIsSaving(false);
          return;
        }
        if (editingRequest) {
          await purchasingService.updatePurchaseRequest(editingRequest.id, {
            justification: requestJustification,
            cost_center_id: requestCostCenterId || null,
            required_date: requestRequiredDate ? new Date(requestRequiredDate).toISOString() : null
          });
        } else {
          if (requestItems.length === 0) {
            setModalError("Adicione ao menos um produto à solicitação.");
            setIsSaving(false);
            return;
          }

          await purchasingService.createPurchaseRequest({
            justification: requestJustification.trim(),
            cost_center_id: requestCostCenterId || undefined,
            required_date: requestRequiredDate ? new Date(requestRequiredDate).toISOString() : undefined,
            items: requestItems.map(it => ({
              product_id: it.product_id,
              quantity: parseFloat(String(it.quantity)) || 1,
              estimated_unit_price: parseFloat(String(it.estimated_unit_price)) || 0,
              notes: it.notes ? it.notes.trim() : undefined
            }))
          });
        }

      } else if (activeMenu === 'fornecedores') {
        if (!supplierName.trim()) {
          setModalError("A Razão Social do fornecedor é obrigatória.");
          setIsSaving(false);
          return;
        }
        const supplierPayload = {
          name: supplierName,
          trade_name: supplierTradeName || undefined,
          cnpj_cpf: supplierCnpj || '00.000.000/0000-00',
          state_registration: supplierStateRegistration || undefined,
          contact_name: supplierContactName || undefined,
          segments: supplierSegments.length > 0 ? supplierSegments.join(', ') : undefined,
          payment_terms: supplierPaymentTerms || undefined,
          min_order_amount: parseFloat(supplierMinOrderAmount) || 0,
          anvisa_license: supplierAnvisaLicense || undefined,
          notes: supplierNotes || undefined,
          email: supplierEmail || undefined,
          phone: supplierPhone || undefined,
          address: supplierAddress || undefined,
          city: supplierCity || undefined,
          state: supplierState || undefined,
          zip_code: supplierZipCode || undefined,
        };

        if (editingSupplier) {
          await purchasingService.updateSupplier(editingSupplier.id, supplierPayload);
        } else {
          await purchasingService.createSupplier(supplierPayload);
        }
      } else if (activeMenu === 'categorias') {
        if (!categoryName.trim()) {
          setModalError("O nome da categoria é obrigatório.");
          setIsSaving(false);
          return;
        }
        if (editingCategory) {
          await inventoryService.updateCategory(editingCategory.id, {
            name: categoryName,
            code: categoryCode || undefined,
            description: categoryDesc || undefined
          });
        } else {
          await inventoryService.createCategory({
            name: categoryName,
            code: categoryCode || undefined,
            description: categoryDesc || undefined
          });
        }
      } else if (activeMenu === 'produtos') {
        if (!productName.trim()) {
          setModalError("O nome do produto é obrigatório.");
          setIsSaving(false);
          return;
        }
        if (editingProduct) {
          await inventoryService.updateProduct(editingProduct.id, {
            sku: productSku,
            name: productName,
            description: productDesc || undefined,
            unit_of_measure: productUnit,
            reference_price: parseFloat(productPrice) || 0,
            category_id: productCategoryId || undefined,
            brand: productBrand || undefined,
            barcode: productBarcode || undefined,
            ncm: productNcm || undefined,
            is_perishable: productIsPerishable,
            requires_batch: productRequiresBatch,
            shelf_life_days: productShelfLifeDays ? parseInt(productShelfLifeDays) : null,
            current_stock: parseFloat(productCurrentStock) || 0,
            min_stock: parseFloat(productMinStock) || 0,
            max_stock: productMaxStock ? parseFloat(productMaxStock) : null,
            storage_location: productStorageLocation || undefined
          });
        } else {
          await inventoryService.createProduct({
            sku: productSku || generateAutomaticSku(productName, productCategoryId, productIsPerishable),
            name: productName,
            description: productDesc || undefined,
            unit_of_measure: productUnit,
            reference_price: parseFloat(productPrice) || 0,
            category_id: productCategoryId || undefined,
            brand: productBrand || undefined,
            barcode: productBarcode || undefined,
            ncm: productNcm || undefined,
            is_perishable: productIsPerishable,
            requires_batch: productRequiresBatch,
            shelf_life_days: productShelfLifeDays ? parseInt(productShelfLifeDays) : undefined,
            current_stock: parseFloat(productCurrentStock) || 0,
            min_stock: parseFloat(productMinStock) || 0,
            max_stock: productMaxStock ? parseFloat(productMaxStock) : undefined,
            storage_location: productStorageLocation || undefined
          });
        }
      } else if (activeMenu === 'centros-custo') {

        if (!costCenterCode.trim() || !costCenterName.trim()) {
          setModalError("Código e Nome do Centro de Custo são obrigatórios.");
          setIsSaving(false);
          return;
        }
        if (editingCostCenter) {
          await purchasingService.updateCostCenter(editingCostCenter.id, {
            code: costCenterCode,
            name: costCenterName,
            description: costCenterDesc || undefined
          });
        } else {
          await purchasingService.createCostCenter({
            code: costCenterCode,
            name: costCenterName,
            description: costCenterDesc || undefined
          });
        }
      }

      await loadAllPurchasingData();
      setIsModalOpen(false);
      setEditingSupplier(null);
      setEditingProduct(null);
      setEditingCategory(null);
      setEditingCostCenter(null);
      setEditingRequest(null);
    } catch (err: any) {
      setModalError(formatApiError(err, "Erro ao processar operação."));
    } finally {
      setIsSaving(false);
    }
  };

  // =========================================================================
  // FLUXO DE APROVAÇÃO DE SOLICITAÇÃO
  // =========================================================================
  const handleOpenApprovalModal = (req: PurchaseRequest) => {
    setSelectedRequestForApproval(req);
    setApprovalDecision('approved');
    setApprovalComments('');
    setModalError(null);
    setIsApprovalModalOpen(true);
  };

  const handleProcessApproval = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRequestForApproval) return;

    setIsSaving(true);
    setModalError(null);
    try {
      await purchasingService.approveOrRejectRequest(
        selectedRequestForApproval.id,
        approvalDecision,
        approvalComments || undefined
      );
      await loadAllPurchasingData();
      setIsApprovalModalOpen(false);
    } catch (err: any) {
      setModalError(formatApiError(err, "Erro ao processar aprovação."));
    } finally {
      setIsSaving(false);
    }
  };

  // =========================================================================
  // RECEBIMENTO FÍSICO NO ALMOXARIFADO
  // =========================================================================
  const handleOpenReceiveModal = (order: PurchaseOrder) => {
    setSelectedOrderForReceive(order);
    setReceiveInvoiceNumber('');
    setReceiveInvoiceType('NFE');
    setReceiveInvoiceSeries('');
    setReceiveInvoiceAccessKey('');
    setReceiveInvoiceIssueDate(new Date().toISOString().slice(0, 10));
    setReceiveTaxAmount('');
    setReceiveGeneratePayable(true);
    setReceivePayableDueDate(order.expected_delivery_date || new Date().toISOString().slice(0, 10));
    setReceiveInstallments('1');
    setReceiveInstallmentFrequency('30');
    setReceiveExpenseNature('OPEX');
    setReceivePaymentMethod('BOLETO');
    setReceiveDigitableLine('');
    setReceiveBarcode('');
    setReceivePixCode('');
    setReceiveInvoiceAttachment(null);
    setReceiveInvoiceAttachmentName(null);
    setReceiveNotes('');
    setModalError(null);
    setIsReceiveModalOpen(true);
  };

  const handleReceiveInvoiceFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 10 * 1024 * 1024) {
      setModalError("O arquivo da Nota Fiscal não pode exceder 10 MB.");
      return;
    }

    setReceiveInvoiceAttachmentName(`${file.name} (${(file.size / 1024).toFixed(1)} KB)`);
    const reader = new FileReader();
    reader.onload = () => {
      setReceiveInvoiceAttachment(reader.result as string);
    };
    reader.readAsDataURL(file);
  };

  const handleProcessReceive = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedOrderForReceive) return;

    if (!receiveInvoiceNumber.trim()) {
      setModalError("O número da Nota Fiscal / DANFE é obrigatório.");
      return;
    }
    if (receiveGeneratePayable && !receivePayableDueDate) {
      setModalError("Informe o primeiro vencimento para gerar a conta a pagar.");
      return;
    }

    setIsSaving(true);
    setModalError(null);
    try {
      await purchasingService.receivePurchaseOrder(selectedOrderForReceive.id, {
        invoice_number: receiveInvoiceNumber.trim(),
        invoice_type: receiveInvoiceType,
        invoice_series: receiveInvoiceSeries.trim() || undefined,
        invoice_access_key: receiveInvoiceAccessKey.trim() || undefined,
        invoice_issue_date: receiveInvoiceIssueDate || undefined,
        invoice_tax_amount: receiveTaxAmount ? Number(receiveTaxAmount) : undefined,
        invoice_attachment: receiveInvoiceAttachment || undefined,
        generate_payable: receiveGeneratePayable,
        payable_due_date: receiveGeneratePayable ? receivePayableDueDate : undefined,
        installments_count: Math.max(1, Number(receiveInstallments) || 1),
        installment_frequency_days: Math.max(1, Number(receiveInstallmentFrequency) || 30),
        expense_nature: receiveExpenseNature,
        payment_method_expected: receivePaymentMethod,
        digitable_line: receiveDigitableLine.trim() || undefined,
        barcode: receiveBarcode.trim() || undefined,
        pix_code: receivePixCode.trim() || undefined,
        notes: receiveNotes.trim() || undefined
      });
      await loadAllPurchasingData();
      setIsReceiveModalOpen(false);
    } catch (err: any) {
      setModalError(formatApiError(err, "Erro ao registrar recebimento."));
    } finally {
      setIsSaving(false);
    }
  };


  // =========================================================================
  // FLUXO ÁGIL DE REPOSIÇÃO (SUGESTÕES DE COMPRA & EMISSÃO DIRETA DE PO)
  // =========================================================================
  const handleToggleSelectSuggestion = (productId: string) => {
    if (selectedSuggestionProductIds.includes(productId)) {
      setSelectedSuggestionProductIds(selectedSuggestionProductIds.filter(id => id !== productId));
    } else {
      setSelectedSuggestionProductIds([...selectedSuggestionProductIds, productId]);
    }
  };

  const handleOpenQuickOrderModal = (flow: 'request' | 'order') => {
    if (!suggestionsSummary) return;
    const selectedItems = suggestionsSummary.items.filter(it =>
      selectedSuggestionProductIds.includes(it.product_id)
    );

    if (selectedItems.length === 0) {
      toast.warning("Selecione ao menos um produto da sugestão de reposição para avançar.");
      return;
    }

    setReplenishmentFlow(flow);
    setQuickOrderSupplierId(suppliers[0]?.id || '');
    setQuickOrderCostCenterId(costCenters[0]?.id || '');
    setQuickOrderPaymentTerms(suppliers[0]?.payment_terms || '30 DDL');
    setQuickOrderFreightType('CIF');
    setQuickOrderFreightAmount('0');
    setQuickOrderDiscountAmount('0');
    setQuickOrderDeliveryDate('');
    setQuickOrderNotes(
      flow === 'request'
        ? 'Reposição formal de estoque de giro (Assistente de Compras)'
        : 'Reposição ágil de estoque de giro (Assistente de Compras)'
    );

    setQuickOrderItems(selectedItems.map(it => ({
      product_id: it.product_id,
      product_name: it.product_name,
      sku: it.sku,
      unit_of_measure: it.unit_of_measure,
      quantity: customSuggestionQtys[it.product_id] !== undefined ? customSuggestionQtys[it.product_id] : Number(it.suggested_quantity),
      unit_price: Number(it.reference_price) || 0
    })));

    setModalError(null);
    setIsQuickOrderModalOpen(true);
  };

  const handleEmitSingleItemQuickOrder = (item: any) => {
    setReplenishmentFlow('order');
    setSelectedSuggestionProductIds([item.product_id]);
    setQuickOrderSupplierId(suppliers[0]?.id || '');
    setQuickOrderCostCenterId(costCenters[0]?.id || '');
    setQuickOrderPaymentTerms(suppliers[0]?.payment_terms || '30 DDL');
    setQuickOrderFreightType('CIF');
    setQuickOrderFreightAmount('0');
    setQuickOrderDiscountAmount('0');
    setQuickOrderDeliveryDate('');
    setQuickOrderNotes(`Reposição ágil de item crítico: ${item.product_name}`);

    const qty = customSuggestionQtys[item.product_id] !== undefined ? customSuggestionQtys[item.product_id] : Number(item.suggested_quantity);
    setQuickOrderItems([{
      product_id: item.product_id,
      product_name: item.product_name,
      sku: item.sku,
      unit_of_measure: item.unit_of_measure,
      quantity: qty,
      unit_price: Number(item.reference_price) || 0
    }]);

    setModalError(null);
    setIsQuickOrderModalOpen(true);
  };

  const handleEmitQuickOrder = async (e: React.FormEvent) => {
    e.preventDefault();
    if (replenishmentFlow === 'order' && !quickOrderSupplierId) {
      setModalError("Selecione o fornecedor para onde a ordem será emitida.");
      return;
    }
    if (quickOrderItems.length === 0) {
      setModalError("A reposição precisa conter pelo menos um item.");
      return;
    }

    try {
      setIsSaving(true);
      if (replenishmentFlow === 'request') {
        await purchasingService.createFormalReplenishmentRequest({
          justification: quickOrderNotes || 'Reposição formal de estoque',
          cost_center_id: quickOrderCostCenterId || undefined,
          required_date: quickOrderDeliveryDate
            ? new Date(quickOrderDeliveryDate).toISOString()
            : undefined,
          items: quickOrderItems.map(it => ({
            product_id: it.product_id,
            quantity: it.quantity,
            estimated_unit_price: it.unit_price
          }))
        });
      } else {
        await purchasingService.createQuickReplenishmentOrder({
          supplier_id: quickOrderSupplierId,
          cost_center_id: quickOrderCostCenterId || undefined,
          payment_terms: quickOrderPaymentTerms || undefined,
          freight_type: quickOrderFreightType || 'CIF',
          freight_amount: parseFloat(quickOrderFreightAmount) || 0,
          discount_amount: parseFloat(quickOrderDiscountAmount) || 0,
          expected_delivery_date: quickOrderDeliveryDate ? new Date(quickOrderDeliveryDate).toISOString() : undefined,
          notes: quickOrderNotes || undefined,
          items: quickOrderItems.map(it => ({
            product_id: it.product_id,
            quantity: it.quantity,
            unit_price: it.unit_price
          }))
        });
      }

      await loadAllPurchasingData();
      setIsQuickOrderModalOpen(false);
      setSelectedSuggestionProductIds([]);
      setActiveMenu(replenishmentFlow === 'request' ? 'solicitacoes' : 'ordens');
    } catch (err: any) {
      setModalError(formatApiError(
        err,
        replenishmentFlow === 'request'
          ? "Erro ao criar solicitação formal de reposição."
          : "Erro ao emitir ordem de compra direta."
      ));
    } finally {
      setIsSaving(false);
    }
  };





  // Handlers de Ordenação Dinâmica
  const handleReqSort = (field: string) => {
    if (reqSortField === field) setReqSortDir(prev => prev === 'asc' ? 'desc' : 'asc');
    else { setReqSortField(field); setReqSortDir('asc'); }
  };
  const handleQuotSort = (field: string) => {
    if (quotSortField === field) setQuotSortDir(prev => prev === 'asc' ? 'desc' : 'asc');
    else { setQuotSortField(field); setQuotSortDir('asc'); }
  };
  const handleOrderSort = (field: string) => {
    if (orderSortField === field) setOrderSortDir(prev => prev === 'asc' ? 'desc' : 'asc');
    else { setOrderSortField(field); setOrderSortDir('asc'); }
  };
  const handleSuggSort = (field: string) => {
    if (suggSortField === field) setSuggSortDir(prev => prev === 'asc' ? 'desc' : 'asc');
    else { setSuggSortField(field); setSuggSortDir('asc'); }
  };
  const handleSupSort = (field: string) => {
    if (supSortField === field) setSupSortDir(prev => prev === 'asc' ? 'desc' : 'asc');
    else { setSupSortField(field); setSupSortDir('asc'); }
  };
  const handleProdSort = (field: string) => {
    if (prodSortField === field) setProdSortDir(prev => prev === 'asc' ? 'desc' : 'asc');
    else { setProdSortField(field); setProdSortDir('asc'); }
  };
  const handleCatSort = (field: string) => {
    if (catSortField === field) setCatSortDir(prev => prev === 'asc' ? 'desc' : 'asc');
    else { setCatSortField(field); setCatSortDir('asc'); }
  };
  const handleCostSort = (field: string) => {
    if (costSortField === field) setCostSortDir(prev => prev === 'asc' ? 'desc' : 'asc');
    else { setCostSortField(field); setCostSortDir('asc'); }
  };
  const handleMovSort = (field: string) => {
    if (movSortField === field) setMovSortDir(prev => prev === 'asc' ? 'desc' : 'asc');
    else { setMovSortField(field); setMovSortDir('asc'); }
  };

  // --- FILTROS E ORDENAÇÃO POR MÓDULO ---

  // 1. Sugestões de Reposição
  const filteredSuggestions = (suggestionsSummary?.items || []).filter(item => {
    const term = searchTerm.trim().toLowerCase();
    let matchesSearch = true;
    if (term) {
      if (searchField === 'all') {
        matchesSearch = (
          item.product_name.toLowerCase().includes(term) ||
          item.sku.toLowerCase().includes(term) ||
          Boolean(item.category_name && item.category_name.toLowerCase().includes(term)) ||
          Boolean(item.brand && item.brand.toLowerCase().includes(term)) ||
          Boolean(item.storage_location && item.storage_location.toLowerCase().includes(term))
        );
      } else if (searchField === 'name') {
        matchesSearch = item.product_name.toLowerCase().includes(term);
      } else if (searchField === 'sku') {
        matchesSearch = item.sku.toLowerCase().includes(term);
      } else if (searchField === 'brand') {
        matchesSearch = Boolean(item.brand && item.brand.toLowerCase().includes(term));
      } else if (searchField === 'location') {
        matchesSearch = Boolean(item.storage_location && item.storage_location.toLowerCase().includes(term));
      }
    }

    let matchesUrgency = true;
    if (urgencyFilter === 'criticos') {
      matchesUrgency = item.urgency_level === 'critical' || item.urgency_level === 'high';
    } else if (urgencyFilter === 'zerados') {
      matchesUrgency = item.urgency_level === 'critical';
    } else if (urgencyFilter === 'ponto_pedido') {
      matchesUrgency = item.urgency_level === 'medium';
    }

    let matchesCat = true;
    if (categoryFilter) {
      matchesCat = item.category_name === categoryFilter;
    }

    return matchesSearch && matchesUrgency && matchesCat;
  }).sort((a, b) => {
    let valA: any = '';
    let valB: any = '';

    if (suggSortField === 'urgency') {
      const priority = { critical: 1, high: 2, medium: 3, low: 4 };
      valA = priority[a.urgency_level as keyof typeof priority] || 99;
      valB = priority[b.urgency_level as keyof typeof priority] || 99;
    } else if (suggSortField === 'name') {
      valA = a.product_name.toLowerCase();
      valB = b.product_name.toLowerCase();
    } else if (suggSortField === 'sku') {
      valA = a.sku.toLowerCase();
      valB = b.sku.toLowerCase();
    } else if (suggSortField === 'category') {
      valA = (a.category_name || '').toLowerCase();
      valB = (b.category_name || '').toLowerCase();
    } else if (suggSortField === 'current_stock') {
      valA = Number(a.current_stock || 0);
      valB = Number(b.current_stock || 0);
    } else if (suggSortField === 'suggested_qty') {
      valA = Number(a.suggested_quantity || 0);
      valB = Number(b.suggested_quantity || 0);
    } else if (suggSortField === 'price') {
      valA = Number(a.reference_price || 0);
      valB = Number(b.reference_price || 0);
    } else if (suggSortField === 'subtotal') {
      valA = Number(a.suggested_quantity || 0) * Number(a.reference_price || 0);
      valB = Number(b.suggested_quantity || 0) * Number(b.reference_price || 0);
    }

    if (valA < valB) return suggSortDir === 'asc' ? -1 : 1;
    if (valA > valB) return suggSortDir === 'asc' ? 1 : -1;
    return 0;
  });

  // 2. Solicitações de Compra (PR)
  const filteredRequests = (requests || []).filter(req => {
    const term = searchTerm.trim().toLowerCase();
    let matchesSearch = true;
    if (term) {
      if (searchField === 'all') {
        matchesSearch = (
          req.request_number.toLowerCase().includes(term) ||
          Boolean(req.justification && req.justification.toLowerCase().includes(term))
        );
      } else if (searchField === 'number') {
        matchesSearch = req.request_number.toLowerCase().includes(term);
      } else if (searchField === 'justification') {
        matchesSearch = Boolean(req.justification && req.justification.toLowerCase().includes(term));
      }
    }

    let matchesStatus = true;
    if (statusFilter !== 'all') {
      matchesStatus = req.status === statusFilter;
    }

    return matchesSearch && matchesStatus;
  }).sort((a, b) => {
    let valA: any = '';
    let valB: any = '';
    if (reqSortField === 'number') {
      valA = a.request_number.toLowerCase();
      valB = b.request_number.toLowerCase();
    } else if (reqSortField === 'justification') {
      valA = (a.justification || '').toLowerCase();
      valB = (b.justification || '').toLowerCase();
    } else if (reqSortField === 'amount') {
      valA = Number(a.total_estimated_amount || 0);
      valB = Number(b.total_estimated_amount || 0);
    } else if (reqSortField === 'status') {
      valA = a.status;
      valB = b.status;
    } else if (reqSortField === 'date') {
      valA = a.required_date ? new Date(a.required_date).getTime() : 0;
      valB = b.required_date ? new Date(b.required_date).getTime() : 0;
    } else if (reqSortField === 'created_at') {
      valA = new Date(a.created_at).getTime();
      valB = new Date(b.created_at).getTime();
    }
    if (valA < valB) return reqSortDir === 'asc' ? -1 : 1;
    if (valA > valB) return reqSortDir === 'asc' ? 1 : -1;
    return 0;
  });

  // 3. Cotações (RFQ)
  const filteredQuotations = (quotations || []).filter(quot => {
    const term = searchTerm.trim().toLowerCase();
    let matchesSearch = true;
    if (term) {
      if (searchField === 'all') {
        matchesSearch = (
          quot.quotation_number.toLowerCase().includes(term) ||
          Boolean(quot.notes && quot.notes.toLowerCase().includes(term)) ||
          Boolean(quot.purchase_request?.request_number && quot.purchase_request.request_number.toLowerCase().includes(term))
        );
      } else if (searchField === 'number') {
        matchesSearch = quot.quotation_number.toLowerCase().includes(term);
      } else if (searchField === 'notes') {
        matchesSearch = Boolean(quot.notes && quot.notes.toLowerCase().includes(term));
      } else if (searchField === 'request') {
        matchesSearch = Boolean(quot.purchase_request?.request_number && quot.purchase_request.request_number.toLowerCase().includes(term));
      }
    }

    let matchesStatus = true;
    if (statusFilter !== 'all') {
      matchesStatus = quot.status === statusFilter;
    }

    return matchesSearch && matchesStatus;
  }).sort((a, b) => {
    let valA: any = '';
    let valB: any = '';
    if (quotSortField === 'number') {
      valA = a.quotation_number.toLowerCase();
      valB = b.quotation_number.toLowerCase();
    } else if (quotSortField === 'request') {
      valA = (a.purchase_request?.request_number || '').toLowerCase();
      valB = (b.purchase_request?.request_number || '').toLowerCase();
    } else if (quotSortField === 'proposals') {
      valA = a.quotes.length;
      valB = b.quotes.length;
    } else if (quotSortField === 'status') {
      valA = a.status;
      valB = b.status;
    } else if (quotSortField === 'created_at') {
      valA = new Date(a.created_at).getTime();
      valB = new Date(b.created_at).getTime();
    }
    if (valA < valB) return quotSortDir === 'asc' ? -1 : 1;
    if (valA > valB) return quotSortDir === 'asc' ? 1 : -1;
    return 0;
  });

  // 4. Ordens de Compra (PO)
  const filteredOrders = (orders || []).filter(ord => {
    const term = searchTerm.trim().toLowerCase();
    let matchesSearch = true;
    if (term) {
      if (searchField === 'all') {
        matchesSearch = (
          ord.order_number.toLowerCase().includes(term) ||
          Boolean(ord.supplier?.name && ord.supplier.name.toLowerCase().includes(term)) ||
          Boolean(ord.supplier?.cnpj_cpf && ord.supplier.cnpj_cpf.toLowerCase().includes(term)) ||
          Boolean(ord.invoice_number && ord.invoice_number.toLowerCase().includes(term)) ||
          Boolean(ord.purchase_request?.request_number && ord.purchase_request.request_number.toLowerCase().includes(term))
        );
      } else if (searchField === 'number') {
        matchesSearch = ord.order_number.toLowerCase().includes(term);
      } else if (searchField === 'supplier') {
        matchesSearch = Boolean(ord.supplier?.name && ord.supplier.name.toLowerCase().includes(term));
      } else if (searchField === 'cnpj') {
        matchesSearch = Boolean(ord.supplier?.cnpj_cpf && ord.supplier.cnpj_cpf.toLowerCase().includes(term));
      } else if (searchField === 'invoice') {
        matchesSearch = Boolean(ord.invoice_number && ord.invoice_number.toLowerCase().includes(term));
      }
    }

    let matchesStatus = true;
    if (statusFilter !== 'all') {
      matchesStatus = ord.status === statusFilter;
    }

    return matchesSearch && matchesStatus;
  }).sort((a, b) => {
    let valA: any = '';
    let valB: any = '';
    if (orderSortField === 'number') {
      valA = a.order_number.toLowerCase();
      valB = b.order_number.toLowerCase();
    } else if (orderSortField === 'supplier') {
      valA = (a.supplier?.name || '').toLowerCase();
      valB = (b.supplier?.name || '').toLowerCase();
    } else if (orderSortField === 'request') {
      valA = (a.purchase_request?.request_number || '').toLowerCase();
      valB = (b.purchase_request?.request_number || '').toLowerCase();
    } else if (orderSortField === 'amount') {
      valA = Number(a.total_amount || 0);
      valB = Number(b.total_amount || 0);
    } else if (orderSortField === 'status') {
      valA = a.status;
      valB = b.status;
    } else if (orderSortField === 'created_at') {
      valA = new Date(a.created_at).getTime();
      valB = new Date(b.created_at).getTime();
    }
    if (valA < valB) return orderSortDir === 'asc' ? -1 : 1;
    if (valA > valB) return orderSortDir === 'asc' ? 1 : -1;
    return 0;
  });

  // 5. Fornecedores
  const filteredSuppliers = (suppliers || []).filter(sup => {
    const term = searchTerm.trim().toLowerCase();
    if (!term) return true;
    if (searchField === 'all') {
      return (
        sup.name.toLowerCase().includes(term) ||
        Boolean(sup.trade_name && sup.trade_name.toLowerCase().includes(term)) ||
        Boolean(sup.cnpj_cpf && sup.cnpj_cpf.toLowerCase().includes(term)) ||
        Boolean(sup.segments && sup.segments.toLowerCase().includes(term)) ||
        Boolean(sup.city && sup.city.toLowerCase().includes(term))
      );
    } else if (searchField === 'name') {
      return sup.name.toLowerCase().includes(term) || Boolean(sup.trade_name && sup.trade_name.toLowerCase().includes(term));
    } else if (searchField === 'cnpj') {
      return Boolean(sup.cnpj_cpf && sup.cnpj_cpf.toLowerCase().includes(term));
    } else if (searchField === 'segments') {
      return Boolean(sup.segments && sup.segments.toLowerCase().includes(term));
    } else if (searchField === 'city') {
      return Boolean(sup.city && sup.city.toLowerCase().includes(term));
    }
    return true;
  }).sort((a, b) => {
    let valA: any = '';
    let valB: any = '';
    if (supSortField === 'name') {
      valA = a.name.toLowerCase();
      valB = b.name.toLowerCase();
    } else if (supSortField === 'cnpj') {
      valA = a.cnpj_cpf || '';
      valB = b.cnpj_cpf || '';
    } else if (supSortField === 'payment_terms') {
      valA = (a.payment_terms || '').toLowerCase();
      valB = (b.payment_terms || '').toLowerCase();
    } else if (supSortField === 'city') {
      valA = a.city?.toLowerCase() || '';
      valB = b.city?.toLowerCase() || '';
    }
    if (valA < valB) return supSortDir === 'asc' ? -1 : 1;
    if (valA > valB) return supSortDir === 'asc' ? 1 : -1;
    return 0;
  });

  // 6. Produtos
  const filteredProducts = (products || []).filter(prod => {
    const term = searchTerm.trim().toLowerCase();
    if (!term) return true;
    if (searchField === 'all') {
      return (
        prod.name.toLowerCase().includes(term) ||
        prod.sku.toLowerCase().includes(term) ||
        Boolean(prod.category?.name && prod.category.name.toLowerCase().includes(term)) ||
        Boolean(prod.brand && prod.brand.toLowerCase().includes(term))
      );
    } else if (searchField === 'name') {
      return prod.name.toLowerCase().includes(term);
    } else if (searchField === 'sku') {
      return prod.sku.toLowerCase().includes(term);
    } else if (searchField === 'brand') {
      return Boolean(prod.brand && prod.brand.toLowerCase().includes(term));
    }
    return true;
  }).sort((a, b) => {
    let valA: any = '';
    let valB: any = '';
    if (prodSortField === 'name') {
      valA = a.name.toLowerCase();
      valB = b.name.toLowerCase();
    } else if (prodSortField === 'sku') {
      valA = a.sku.toLowerCase();
      valB = b.sku.toLowerCase();
    } else if (prodSortField === 'category') {
      valA = (a.category?.name || '').toLowerCase();
      valB = (b.category?.name || '').toLowerCase();
    } else if (prodSortField === 'brand') {
      valA = (a.brand || '').toLowerCase();
      valB = (b.brand || '').toLowerCase();
    } else if (prodSortField === 'stock') {
      valA = Number(a.current_stock || 0);
      valB = Number(b.current_stock || 0);
    } else if (prodSortField === 'price') {
      valA = Number(a.reference_price || 0);
      valB = Number(b.reference_price || 0);
    }
    if (valA < valB) return prodSortDir === 'asc' ? -1 : 1;
    if (valA > valB) return prodSortDir === 'asc' ? 1 : -1;
    return 0;
  });

  // 7. Categorias
  const filteredCategories = (categories || []).filter(cat => {
    const term = searchTerm.trim().toLowerCase();
    if (!term) return true;
    return cat.name.toLowerCase().includes(term) || (cat.code && cat.code.toLowerCase().includes(term));
  }).sort((a, b) => {
    let valA: any = '';
    let valB: any = '';
    if (catSortField === 'code') {
      valA = (a.code || '').toLowerCase();
      valB = (b.code || '').toLowerCase();
    } else if (catSortField === 'name') {
      valA = a.name.toLowerCase();
      valB = b.name.toLowerCase();
    }
    if (valA < valB) return catSortDir === 'asc' ? -1 : 1;
    if (valA > valB) return catSortDir === 'asc' ? 1 : -1;
    return 0;
  });

  // 8. Centros de Custo
  const filteredCostCenters = (costCenters || []).filter(cc => {
    const term = searchTerm.trim().toLowerCase();
    if (!term) return true;
    return cc.name.toLowerCase().includes(term) || cc.code.toLowerCase().includes(term);
  }).sort((a, b) => {
    let valA: any = '';
    let valB: any = '';
    if (costSortField === 'code') {
      valA = a.code.toLowerCase();
      valB = b.code.toLowerCase();
    } else if (costSortField === 'name') {
      valA = a.name.toLowerCase();
      valB = b.name.toLowerCase();
    }
    if (valA < valB) return costSortDir === 'asc' ? -1 : 1;
    if (valA > valB) return costSortDir === 'asc' ? 1 : -1;
    return 0;
  });

  // 9. Movimentações
  const filteredMovements = (stockMovements || []).filter(mov => {
    const term = searchTerm.trim().toLowerCase();
    if (!term) return true;
    return (
      (mov.product_name && mov.product_name.toLowerCase().includes(term)) ||
      (mov.sku && mov.sku.toLowerCase().includes(term)) ||
      (mov.reference_doc && mov.reference_doc.toLowerCase().includes(term))
    );
  }).sort((a, b) => {
    let valA: any = '';
    let valB: any = '';
    if (movSortField === 'created_at') {
      valA = new Date(a.created_at).getTime();
      valB = new Date(b.created_at).getTime();
    } else if (movSortField === 'product') {
      valA = (a.product_name || '').toLowerCase();
      valB = (b.product_name || '').toLowerCase();
    } else if (movSortField === 'quantity') {
      valA = Number(a.quantity || 0);
      valB = Number(b.quantity || 0);
    } else if (movSortField === 'unit_cost') {
      valA = Number(a.unit_cost || 0);
      valB = Number(b.unit_cost || 0);
    } else if (movSortField === 'balance_after') {
      valA = Number(a.balance_after || 0);
      valB = Number(b.balance_after || 0);
    } else if (movSortField === 'type') {
      valA = a.movement_type;
      valB = b.movement_type;
    }
    if (valA < valB) return movSortDir === 'asc' ? -1 : 1;
    if (valA > valB) return movSortDir === 'asc' ? 1 : -1;
    return 0;
  });
  const suggestionPagination = useListPagination(filteredSuggestions);
  const requestPagination = useListPagination(filteredRequests);
  const quotationPagination = useListPagination(filteredQuotations);
  const orderPagination = useListPagination(filteredOrders);
  const supplierPagination = useListPagination(filteredSuppliers);
  const productPagination = useListPagination(filteredProducts);
  const categoryPagination = useListPagination(filteredCategories);
  const costCenterPagination = useListPagination(filteredCostCenters);
  const movementPagination = useListPagination(filteredMovements);

  const runPurchasingBulkAction = (
    ids: string[],
    label: string,
    action: (id: string) => Promise<unknown>,
    clearSelection: () => void,
  ) => {
    if (ids.length === 0) return;
    openConfirmModal({
      title: `${label} em Lote`,
      subtitle: `${ids.length} ${ids.length === 1 ? 'registro selecionado' : 'registros selecionados'}`,
      message: `Deseja realmente executar a ação "${label}" para os ${ids.length} registro(s) selecionado(s)?`,
      confirmText: `Confirmar (${ids.length})`,
      type: 'danger',
      onConfirm: async () => {
        const results = await Promise.allSettled(ids.map(action));
        const succeeded = results.filter(result => result.status === 'fulfilled').length;
        const failed = results.length - succeeded;
        clearSelection();
        closeConfirmModal();
        await loadAllPurchasingData(true);
        if (failed > 0) {
          toast.warning(`${succeeded} registro(s) processado(s); ${failed} possuem vínculos ou restrições.`);
        } else {
          toast.success(`${succeeded} registro(s) processado(s) com sucesso.`);
        }
      }
    });
  };

  // Totalizadores
  const totalQuoteSum = quoteItems.reduce((acc, it) => acc + (it.quantity * it.unit_price), 0);
  const totalQuoteFreight = parseFloat(quoteFreightAmount) || 0;
  const totalQuoteDiscount = parseFloat(quoteDiscountAmount) || 0;
  const totalQuoteNet = Math.max(0, totalQuoteSum + totalQuoteFreight - totalQuoteDiscount);

  return (
    <div className="purchasing-page">
      <div className="purchasing-layout">
        {/* 1. SIDEBAR LATERAL ESQUERDA */}

        <aside className="sidebar-left">
          <div className="sidebar-header">
            <ShoppingCart className="brand-icon" size={20} />
            <div className="sidebar-title-wrap">
              <span className="sidebar-title"><strong>Compras</strong></span>
              <span className="sidebar-subtitle">Procure-to-Pay</span>
            </div>
          </div>

          <nav className="nav-menu">
            <span className="menu-group-label">Fluxos de Compras</span>

            <button
              className={`nav-item ${activeMenu === 'sugestoes' ? 'active' : ''}`}
              onClick={() => setActiveMenu('sugestoes')}
            >
              <div className="nav-item-content">
                <Zap size={16} />
                <span>Assistente de Reposição</span>
              </div>
              <span className={`nav-badge ${(suggestionsSummary?.critical_count || 0) > 0 ? 'critical-badge' : ''}`}>
                {suggestionsSummary?.total_suggestions || 0}
              </span>
            </button>

            <button
              className={`nav-item ${activeMenu === 'solicitacoes' ? 'active' : ''}`}
              onClick={() => setActiveMenu('solicitacoes')}
            >
              <div className="nav-item-content">
                <FileText size={16} />
                <span>Solicitações Formais (PR)</span>
              </div>
              <span className="nav-badge">{requests.length}</span>
            </button>

            <button
              className={`nav-item ${activeMenu === 'cotacoes' ? 'active' : ''}`}
              onClick={() => setActiveMenu('cotacoes')}
            >
              <div className="nav-item-content">
                <BarChart2 size={16} />
                <span>Cotações & RFQ</span>
              </div>
              <span className="nav-badge">{quotations.length}</span>
            </button>

            <button
              className={`nav-item ${activeMenu === 'ordens' ? 'active' : ''}`}
              onClick={() => setActiveMenu('ordens')}
            >
              <div className="nav-item-content">
                <Truck size={16} />
                <span>Ordens de Compra (PO)</span>
              </div>
              <span className="nav-badge">{orders.length}</span>
            </button>

            <span className="menu-group-label">Estruturas Comerciais</span>

            <button
              className={`nav-item ${activeMenu === 'fornecedores' ? 'active' : ''}`}
              onClick={() => setActiveMenu('fornecedores')}
            >
              <div className="nav-item-content">
                <Users size={16} />
                <span>Fornecedores Homologados</span>
              </div>
              <span className="nav-badge">{suppliers.length}</span>
            </button>

            <button
              className={`nav-item ${activeMenu === 'centros-custo' ? 'active' : ''}`}
              onClick={() => setActiveMenu('centros-custo')}
            >
              <div className="nav-item-content">
                <Target size={16} />
                <span>Centros de Custo</span>
              </div>
              <span className="nav-badge">{costCenters.length}</span>
            </button>
          </nav>
        </aside>


        {/* 2. ÁREA DE TRABALHO PRINCIPAL */}
        <main className="content-right">
          <div className="content-header">
            <div className="header-info">
              <div className="breadcrumb">
                <span>Compras</span>
                <ChevronRight size={12} />
                <span className="current">
                  {activeMenu === 'sugestoes' && 'Assistente de Reposição & Sugestões de Compra'}
                  {activeMenu === 'solicitacoes' && 'Solicitações de Compra (PR)'}
                  {activeMenu === 'cotacoes' && 'Processos de Cotação (RFQ)'}
                  {activeMenu === 'ordens' && 'Ordens de Compra (PO)'}
                  {activeMenu === 'fornecedores' && 'Fornecedores Homologados'}
                  {activeMenu === 'produtos' && 'Catálogo de Produtos & Insumos'}
                  {activeMenu === 'categorias' && 'Categorias de Produtos'}
                  {activeMenu === 'centros-custo' && 'Centros de Custo'}
                  {activeMenu === 'movimentacoes' && 'Histórico de Movimentações de Estoque'}
                </span>
              </div>
              <h1 className="section-title">
                {activeMenu === 'sugestoes' && 'Assistente de Reposição Ágil de Estoque (Giro Rápido)'}
                {activeMenu === 'solicitacoes' && 'Solicitações de Compra Formais & Extraordinárias'}
                {activeMenu === 'cotacoes' && 'Processos de Cotação de Mercado (RFQ)'}
                {activeMenu === 'ordens' && 'Ordens de Compra Oficiais (Purchase Orders)'}
                {activeMenu === 'fornecedores' && 'Fornecedores Homologados & Linhas de Fornecimento'}
                {activeMenu === 'produtos' && 'Produtos, Medicamentos & Controle de Estoque'}
                {activeMenu === 'categorias' && 'Categorias e Grupos de Produtos'}
                {activeMenu === 'centros-custo' && 'Centros de Custo e Orçamentos'}
                {activeMenu === 'movimentacoes' && 'Extrato & Auditoria de Movimentações de Estoque'}
              </h1>
            </div>

            <div className="header-actions">
              <button className="btn-refresh" onClick={() => loadAllPurchasingData(true)} title="Recarregar Dados">
                <RefreshCw size={15} className={loading ? 'spinning' : ''} />
              </button>

              {activeMenu === 'sugestoes' && (
                <button
                  className="btn-primary highlight-btn"
                  onClick={() => handleOpenQuickOrderModal('order')}
                  disabled={selectedSuggestionProductIds.length === 0}
                >
                  <Zap size={16} />
                  <span>Gerar Pedido ({selectedSuggestionProductIds.length})</span>
                </button>
              )}

              {activeMenu === 'solicitacoes' && requests.length > 0 && (
                <button
                  className="btn-outline-danger"
                  onClick={handlePurgeAllRequests}
                  title="Excluir todas as solicitações de compra (Limpeza de Desenvolvimento)"
                >
                  <Trash2 size={15} />
                  <span>Limpar Base (Dev)</span>
                </button>
              )}

              {activeMenu === 'cotacoes' && quotations.length > 0 && (
                <button
                  className="btn-outline-danger"
                  onClick={handlePurgeAllQuotations}
                  title="Excluir todas as cotações (Limpeza de Desenvolvimento)"
                >
                  <Trash2 size={15} />
                  <span>Limpar Base (Dev)</span>
                </button>
              )}

              {activeMenu === 'ordens' && orders.length > 0 && (
                <button
                  className="btn-outline-danger"
                  onClick={handlePurgeAllOrders}
                  title="Excluir todas as ordens de compra (Limpeza de Desenvolvimento)"
                >
                  <Trash2 size={15} />
                  <span>Limpar Base (Dev)</span>
                </button>
              )}


              {activeMenu !== 'ordens' && activeMenu !== 'cotacoes' && activeMenu !== 'sugestoes' && activeMenu !== 'movimentacoes' && (
                <button className="btn-primary" onClick={handleOpenCreateModal}>
                  <Plus size={16} />
                  <span>
                    {activeMenu === 'solicitacoes' && 'Nova Solicitação'}
                    {activeMenu === 'fornecedores' && 'Novo Fornecedor'}
                    {activeMenu === 'produtos' && 'Novo Produto'}
                    {activeMenu === 'categorias' && 'Nova Categoria'}
                    {activeMenu === 'centros-custo' && 'Novo Centro de Custo'}
                  </span>
                </button>
              )}

            </div>
          </div>

          {/* Barra de Pesquisa & Filtros Avançados */}
          <div className="search-toolbar">
            <div className="search-composite">
              <select
                className="search-field-select"
                value={searchField}
                onChange={(e) => setSearchField(e.target.value)}
                title="Filtrar por campo específico"
              >
                <option value="all">Todos os Campos</option>
                {activeMenu === 'sugestoes' && (
                  <>
                    <option value="name">Nome do Produto</option>
                    <option value="sku">SKU</option>
                    <option value="brand">Marca / Fabricante</option>
                    <option value="location">Localização</option>
                  </>
                )}
                {activeMenu === 'solicitacoes' && (
                  <>
                    <option value="number">Número (SC)</option>
                    <option value="justification">Justificativa</option>
                    <option value="department">Departamento</option>
                  </>
                )}
                {activeMenu === 'cotacoes' && (
                  <>
                    <option value="number">Número (RFQ)</option>
                    <option value="notes">Notas / Título</option>
                    <option value="request">Solicitação de Origem</option>
                  </>
                )}
                {activeMenu === 'ordens' && (
                  <>
                    <option value="number">Número (PO)</option>
                    <option value="supplier">Fornecedor</option>
                    <option value="cnpj">CNPJ / CPF</option>
                    <option value="invoice">Nota Fiscal</option>
                  </>
                )}
                {activeMenu === 'fornecedores' && (
                  <>
                    <option value="name">Razão / Nome</option>
                    <option value="cnpj">CNPJ / CPF</option>
                    <option value="segments">Segmento</option>
                    <option value="city">Cidade / UF</option>
                  </>
                )}
                {activeMenu === 'produtos' && (
                  <>
                    <option value="name">Produto</option>
                    <option value="sku">SKU</option>
                    <option value="brand">Marca</option>
                  </>
                )}
              </select>

              <div className="search-box">
                <Search className="search-icon" size={16} />
                <input
                  type="text"
                  placeholder={
                    activeMenu === 'sugestoes' ? 'Pesquisar produto ou SKU para reposição...' :
                    activeMenu === 'solicitacoes' ? 'Pesquisar em solicitações...' :
                    activeMenu === 'cotacoes' ? 'Pesquisar em cotações e RFQ...' :
                    activeMenu === 'ordens' ? 'Pesquisar ordens de compra...' :
                    activeMenu === 'fornecedores' ? 'Pesquisar fornecedores...' :
                    activeMenu === 'produtos' ? 'Pesquisar produtos e insumos...' :
                    'Pesquisar...'
                  }
                  value={searchTerm}
                  onChange={e => setSearchTerm(e.target.value)}
                />
                {searchTerm && (
                  <button type="button" className="btn-clear-search" onClick={() => setSearchTerm('')} title="Limpar busca">
                    <X size={14} />
                  </button>
                )}
              </div>
            </div>

            {/* Filtros Específicos por Módulo */}
            <div className="filter-group">
              {activeMenu === 'sugestoes' && (
                <>
                  <select
                    className="filter-select"
                    value={urgencyFilter}
                    onChange={e => setUrgencyFilter(e.target.value)}
                    title="Filtrar por nível de criticidade"
                  >
                    <option value="all">Todas as Urgências</option>
                    <option value="criticos">🔴 Críticos (Zerados + Abaixo do Mín)</option>
                    <option value="zerados">🔴 Somente Zerados (Esgotados)</option>
                    <option value="ponto_pedido">🟡 Ponto de Pedido</option>
                  </select>

                  <select
                    className="filter-select"
                    value={categoryFilter}
                    onChange={e => setCategoryFilter(e.target.value)}
                    title="Filtrar por categoria"
                  >
                    <option value="">Todas as Categorias</option>
                    {categories.map(cat => (
                      <option key={cat.id} value={cat.name}>{cat.name}</option>
                    ))}
                  </select>
                </>
              )}

              {activeMenu === 'solicitacoes' && (
                <select
                  className="filter-select"
                  value={statusFilter}
                  onChange={e => setStatusFilter(e.target.value)}
                  title="Filtrar por status da solicitação"
                >
                  <option value="all">Todos os Status</option>
                  <option value="draft">Rascunho</option>
                  <option value="pending_approval">Pendente Aprovação</option>
                  <option value="approved">Aprovada</option>
                  <option value="ordered">Convertida em PO</option>
                  <option value="rejected">Rejeitada</option>
                  <option value="cancelled">Cancelada</option>
                </select>
              )}

              {activeMenu === 'cotacoes' && (
                <select
                  className="filter-select"
                  value={statusFilter}
                  onChange={e => setStatusFilter(e.target.value)}
                  title="Filtrar por status da cotação"
                >
                  <option value="all">Todos os Status</option>
                  <option value="open">Aberta</option>
                  <option value="analyzing">Em Análise</option>
                  <option value="completed">Homologada / PO Emitida</option>
                  <option value="cancelled">Cancelada</option>
                </select>
              )}

              {activeMenu === 'ordens' && (
                <select
                  className="filter-select"
                  value={statusFilter}
                  onChange={e => setStatusFilter(e.target.value)}
                  title="Filtrar por status da ordem de compra"
                >
                  <option value="all">Todos os Status</option>
                  <option value="draft">Rascunho</option>
                  <option value="issued">Emitida</option>
                  <option value="partially_received">Recebimento Parcial</option>
                  <option value="received">Recebida Total</option>
                  <option value="cancelled">Cancelada</option>
                </select>
              )}
            </div>

            <div className="results-count">
              {activeMenu === 'sugestoes' && `${filteredSuggestions.length} sugestões listadas`}
              {activeMenu === 'solicitacoes' && `${filteredRequests.length} solicitações`}
              {activeMenu === 'cotacoes' && `${filteredQuotations.length} processos de cotação`}
              {activeMenu === 'ordens' && `${filteredOrders.length} ordens de compra`}
              {activeMenu === 'fornecedores' && `${filteredSuppliers.length} fornecedores`}
              {activeMenu === 'produtos' && `${filteredProducts.length} produtos`}
              {activeMenu === 'categorias' && `${filteredCategories.length} categorias`}
              {activeMenu === 'centros-custo' && `${filteredCostCenters.length} centros de custo`}
              {activeMenu === 'movimentacoes' && `${filteredMovements.length} movimentações`}
            </div>
          </div>

          {/* TABELAS POR MÓDULO */}
          <div className="data-table-container">
            {/* 0. ASSISTENTE DE REPOSIÇÃO (SUGESTÕES DE COMPRA AUTOMÁTICAS) */}
            {activeMenu === 'sugestoes' && (
              <div className="replenishment-dashboard">
                {/* Cards de Métricas e Resumo */}
                <div className="replenishment-kpis-grid">
                  <div className="kpi-card critical">
                    <div className="kpi-icon"><AlertTriangle size={18} /></div>
                    <div className="kpi-info">
                      <span className="kpi-label">Itens em Estoque Crítico</span>
                      <strong className="kpi-value">{suggestionsSummary?.critical_count || 0}</strong>
                      <span className="kpi-sub">Estoque zerado ou esgotado</span>
                    </div>
                  </div>

                  <div className="kpi-card warning">
                    <div className="kpi-icon"><Zap size={18} /></div>
                    <div className="kpi-info">
                      <span className="kpi-label">Sugestões de Reposição</span>
                      <strong className="kpi-value">{suggestionsSummary?.total_suggestions || 0}</strong>
                      <span className="kpi-sub">Itens abaixo do estoque mínimo</span>
                    </div>
                  </div>

                  <div className="kpi-card total">
                    <div className="kpi-icon"><DollarSign size={18} /></div>
                    <div className="kpi-info">
                      <span className="kpi-label">Estimativa Total de Compra</span>
                      <strong className="kpi-value">{formatCurrency(suggestionsSummary?.estimated_total_cost || 0)}</strong>
                      <span className="kpi-sub">Custo de recomposição do estoque alvo</span>
                    </div>
                  </div>

                  <div className="kpi-card selected">
                    <div className="kpi-icon"><ShoppingCart size={18} /></div>
                    <div className="kpi-info">
                      <span className="kpi-label">Itens Marcados para Pedido</span>
                      <strong className="kpi-value">{selectedSuggestionProductIds.length} produtos</strong>
                      <span className="kpi-sub">
                        {formatCurrency(
                          (suggestionsSummary?.items || [])
                            .filter(it => selectedSuggestionProductIds.includes(it.product_id))
                            .reduce((acc, it) => {
                              const qty = customSuggestionQtys[it.product_id] !== undefined ? customSuggestionQtys[it.product_id] : Number(it.suggested_quantity);
                              return acc + (qty * Number(it.reference_price));
                            }, 0)
                        )}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Barra de Ações em Lote */}
                <div className="batch-actions-bar">
                  <div className="batch-selection-controls">
                    <button
                      type="button"
                      className="btn-select-preset"
                      onClick={() => {
                        if (selectedSuggestionProductIds.length === filteredSuggestions.length && filteredSuggestions.length > 0) {
                          setSelectedSuggestionProductIds([]);
                        } else {
                          setSelectedSuggestionProductIds(filteredSuggestions.map(it => it.product_id));
                        }
                      }}
                    >
                      {selectedSuggestionProductIds.length === filteredSuggestions.length && filteredSuggestions.length > 0 ? (
                        <><CheckSquare size={15} /> <span>Desmarcar Todos</span></>
                      ) : (
                        <><Square size={15} /> <span>Selecionar Todos ({filteredSuggestions.length})</span></>
                      )}
                    </button>

                    <button
                      type="button"
                      className="btn-select-preset critical"
                      onClick={() => {
                        const criticalIds = filteredSuggestions
                          .filter(it => it.urgency_level === 'critical' || it.urgency_level === 'high')
                          .map(it => it.product_id);
                        setSelectedSuggestionProductIds(criticalIds);
                      }}
                    >
                      <AlertTriangle size={14} />
                      <span>Marcar Somente Críticos</span>
                    </button>
                  </div>

                  <div className="replenishment-flow-actions">
                    <button
                      type="button"
                      className="btn-formal-replenishment"
                      onClick={() => handleOpenQuickOrderModal('request')}
                      disabled={selectedSuggestionProductIds.length === 0}
                    >
                      <FileText size={16} />
                      <span>Criar Solicitação Formal ({selectedSuggestionProductIds.length})</span>
                    </button>
                    <button
                      type="button"
                      className="btn-emit-quick-order"
                      onClick={() => handleOpenQuickOrderModal('order')}
                      disabled={selectedSuggestionProductIds.length === 0}
                    >
                      <Zap size={16} />
                      <span>Gerar Pedido Direto ({selectedSuggestionProductIds.length})</span>
                    </button>
                  </div>
                </div>

                {/* Tabela de Sugestões de Reposição */}
                <div className="table-responsive">
                  <table className="enterprise-table">
                    <thead>
                      <tr>
                        <th style={{ width: '40px' }}>
                          <input
                            type="checkbox"
                            checked={Boolean(filteredSuggestions.length && selectedSuggestionProductIds.length === filteredSuggestions.length)}
                            onChange={e => {
                              if (e.target.checked) {
                                setSelectedSuggestionProductIds(filteredSuggestions.map(it => it.product_id));
                              } else {
                                setSelectedSuggestionProductIds([]);
                              }
                            }}
                          />
                        </th>
                        <th className="th-sortable" onClick={() => handleSuggSort('name')}>
                          <div className="th-content">
                            <span>Produto / SKU</span>
                            {suggSortField === 'name' ? (suggSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                          </div>
                        </th>
                        <th className="th-sortable" onClick={() => handleSuggSort('category')}>
                          <div className="th-content">
                            <span>Categoria / Marca</span>
                            {suggSortField === 'category' ? (suggSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                          </div>
                        </th>
                        <th className="th-sortable" onClick={() => handleSuggSort('urgency')}>
                          <div className="th-content">
                            <span>Urgência</span>
                            {suggSortField === 'urgency' ? (suggSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                          </div>
                        </th>
                        <th className="th-sortable" onClick={() => handleSuggSort('current_stock')}>
                          <div className="th-content">
                            <span>Estoque Físico (Atual / Mín / Alvo)</span>
                            {suggSortField === 'current_stock' ? (suggSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                          </div>
                        </th>
                        <th className="th-sortable" onClick={() => handleSuggSort('suggested_qty')}>
                          <div className="th-content">
                            <span>Qtd. Sugerida (Editável)</span>
                            {suggSortField === 'suggested_qty' ? (suggSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                          </div>
                        </th>
                        <th className="th-sortable" onClick={() => handleSuggSort('price')}>
                          <div className="th-content">
                            <span>Preço Unit. Ref.</span>
                            {suggSortField === 'price' ? (suggSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                          </div>
                        </th>
                        <th className="th-sortable" onClick={() => handleSuggSort('subtotal')}>
                          <div className="th-content">
                            <span>Subtotal Estimado</span>
                            {suggSortField === 'subtotal' ? (suggSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                          </div>
                        </th>
                        <th style={{ textAlign: 'right' }}>Ações</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredSuggestions.length === 0 ? (
                        <tr>
                          <td colSpan={9} className="state-empty success-state">
                            <CheckCircle2 size={28} style={{ color: '#10b981', marginBottom: '0.5rem', display: 'inline-block' }} />
                            <div><strong>Estoque 100% Regularizado ou Nenhum Item Atende aos Filtros!</strong></div>
                            <small>Verifique os filtros de pesquisa e criticidade acima.</small>
                          </td>
                        </tr>
                      ) : (
                        suggestionPagination.pageItems.map(item => {
                          const isSelected = selectedSuggestionProductIds.includes(item.product_id);
                          const currentQty = customSuggestionQtys[item.product_id] !== undefined
                            ? customSuggestionQtys[item.product_id]
                            : Number(item.suggested_quantity);
                          const subtotal = currentQty * Number(item.reference_price);

                          return (
                            <tr key={item.product_id} className={isSelected ? 'row-selected' : ''}>
                              <td>
                                <input
                                  type="checkbox"
                                  checked={isSelected}
                                  onChange={() => handleToggleSelectSuggestion(item.product_id)}
                                />
                              </td>
                              <td>
                                <div className="cell-with-icon">
                                  <div className={`icon-badge ${item.urgency_level === 'critical' || item.urgency_level === 'high' ? 'red-bg' : 'brand-bg'}`}>
                                    <Package size={15} />
                                  </div>
                                  <div>
                                    <RecordLink type="PRODUCT" id={item.product_id}>
                                      <strong>{item.product_name}</strong>
                                    </RecordLink>
                                    <span className="sub-label">SKU: {item.sku}</span>
                                    {item.storage_location && (
                                      <span className="storage-sub-label">📍 {item.storage_location}</span>
                                    )}
                                  </div>
                                </div>
                              </td>
                              <td>
                                <div>
                                  {item.category_name ? <span className="category-tag">{item.category_name}</span> : <span className="text-muted-small">-</span>}
                                  {item.brand && <span className="sub-label">{item.brand}</span>}
                                </div>
                              </td>
                              <td>
                                {item.urgency_level === 'critical' && <span className="urgency-pill critical">🔴 Crítico (Zerado)</span>}
                                {item.urgency_level === 'high' && <span className="urgency-pill high">🔴 Crítico (Abaixo do Mín)</span>}
                                {item.urgency_level === 'medium' && <span className="urgency-pill medium">🟡 Ponto de Pedido</span>}
                              </td>
                              <td>
                                <div className="stock-balance-cell">
                                  <span className={`stock-now ${Number(item.current_stock) <= 0 ? 'zero' : ''}`}>
                                    Atual: <strong>{formatQuantity(item.current_stock)} {item.unit_of_measure}</strong>
                                  </span>
                                  <span className="stock-limits">
                                    Mín: {formatQuantity(item.min_stock)} | Alvo: {formatQuantity(item.max_stock || Number(item.min_stock) * 2)}
                                  </span>
                                </div>
                              </td>
                              <td>
                                <div className="qty-edit-input-wrapper">
                                  <input
                                    type="number"
                                    className="input-qty-suggestion"
                                    value={currentQty}
                                    min="1"
                                    step="any"
                                    onChange={e => {
                                      const val = parseFloat(e.target.value) || 1;
                                      setCustomSuggestionQtys({
                                        ...customSuggestionQtys,
                                        [item.product_id]: val
                                      });
                                    }}
                                  />
                                  <span className="unit-label">{item.unit_of_measure}</span>
                                </div>
                              </td>
                              <td><strong>{formatCurrency(item.reference_price)}</strong></td>
                              <td><strong className="subtotal-highlight">{formatCurrency(subtotal)}</strong></td>
                              <td style={{ textAlign: 'right' }}>
                                <div className="row-actions">
                                  <button
                                    type="button"
                                    className="btn-action-icon primary"
                                    title="⚡ Gerar Pedido Direto para este Item"
                                    onClick={() => handleEmitSingleItemQuickOrder(item)}
                                  >
                                    <Zap size={14} />
                                  </button>
                                </div>
                              </td>
                            </tr>
                          );
                        })
                      )}
                    </tbody>
                  </table>
                  <ListPagination {...suggestionPagination} onPageChange={suggestionPagination.setPage} onPageSizeChange={suggestionPagination.setPageSize} />
                </div>
              </div>
            )}

            {/* 1. SOLICITAÇÕES DE COMPRA */}
            {activeMenu === 'solicitacoes' && (
              <div className="table-responsive">
                <BulkActionsBar selectedCount={requestSelection.selectedCount} resourceName={{ singular: 'solicitação', plural: 'solicitações' }} onClear={requestSelection.clearSelection} onDelete={() => void runPurchasingBulkAction(requestSelection.selectedIdList, 'Excluir', purchasingService.deletePurchaseRequest, requestSelection.clearSelection)} deleteLabel="Excluir selecionadas" />
                <table className="enterprise-table">
                  <thead>
                    <tr>
                      <th className="ui-selection-cell"><input className="ui-selection-checkbox" type="checkbox" aria-label="Selecionar solicitações desta página" checked={requestSelection.isAllSelected(requestPagination.pageItems)} onChange={() => requestSelection.toggleSelectAll(requestPagination.pageItems)} /></th>
                      <th className="th-sortable" onClick={() => handleReqSort('number')}>
                        <div className="th-content">
                          <span>Número</span>
                          {reqSortField === 'number' ? (reqSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th className="th-sortable" onClick={() => handleReqSort('justification')}>
                        <div className="th-content">
                          <span>Justificativa</span>
                          {reqSortField === 'justification' ? (reqSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th className="th-sortable" onClick={() => handleReqSort('amount')}>
                        <div className="th-content">
                          <span>Valor Estimado</span>
                          {reqSortField === 'amount' ? (reqSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th className="th-sortable" onClick={() => handleReqSort('status')}>
                        <div className="th-content">
                          <span>Status</span>
                          {reqSortField === 'status' ? (reqSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th className="th-sortable" onClick={() => handleReqSort('date')}>
                        <div className="th-content">
                          <span>Data Limite</span>
                          {reqSortField === 'date' ? (reqSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th style={{ textAlign: 'right' }}>Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredRequests.length === 0 ? (
                      <tr><td colSpan={7} className="state-empty">Nenhuma solicitação de compra encontrada com os filtros selecionados.</td></tr>
                    ) : (
                      requestPagination.pageItems.map(req => (
                        <tr key={req.id} className={`${(req.status === 'draft' || req.status === 'pending_approval') ? 'ui-record-row' : ''} ${requestSelection.isSelected(req.id) ? 'ui-record-row--selected' : ''}`} role={(req.status === 'draft' || req.status === 'pending_approval') ? 'button' : undefined} tabIndex={(req.status === 'draft' || req.status === 'pending_approval') ? 0 : undefined} onClick={(event) => { if (!(event.target as HTMLElement).closest('button, a, input') && (req.status === 'draft' || req.status === 'pending_approval')) handleEditRequest(req); }} onKeyDown={(event) => { if (['Enter', ' '].includes(event.key) && (req.status === 'draft' || req.status === 'pending_approval')) { event.preventDefault(); handleEditRequest(req); } }}>
                          <td className="ui-selection-cell"><input className="ui-selection-checkbox" type="checkbox" aria-label={`Selecionar solicitação ${req.request_number}`} checked={requestSelection.isSelected(req.id)} onClick={(event) => event.stopPropagation()} onChange={() => requestSelection.toggleSelect(req.id)} /></td>
                          <td>
                            <div className="cell-with-icon">
                              <div className="icon-badge brand-bg"><FileText size={15} /></div>
                              <strong>{req.request_number}</strong>
                            </div>
                          </td>
                          <td><span className="text-truncate">{req.justification}</span></td>
                          <td><strong>{formatCurrency(req.total_estimated_amount)}</strong></td>
                          <td>
                            <span className={`badge-pill ${req.status}`}>
                              {req.status === 'draft' && 'Rascunho'}
                              {req.status === 'pending_approval' && 'Pendente Aprovação'}
                              {req.status === 'approved' && 'Aprovada'}
                              {req.status === 'ordered' && 'Convertida em PO'}
                              {req.status === 'rejected' && 'Rejeitada'}
                            </span>
                          </td>
                          <td>{req.required_date ? new Date(req.required_date).toLocaleDateString('pt-BR') : '-'}</td>
                          <td>
                            <div className="row-actions">
                              {req.status === 'pending_approval' && (
                                <button className="btn-approve-action" onClick={() => handleOpenApprovalModal(req)}>
                                  <ShieldCheck size={14} />
                                  <span>Parecer</span>
                                </button>
                              )}
                              {req.status === 'approved' && (
                                <button className="btn-quote-action" onClick={() => handleStartQuotation(req)}>
                                  <BarChart2 size={14} />
                                  <span>Iniciar Cotação (RFQ)</span>
                                </button>
                              )}
                              {req.status !== 'cancelled' && req.status !== 'ordered' && (
                                <button
                                  className="btn-cancel-action"
                                  onClick={() => handleCancelRequest(req.id)}
                                  title="Cancelar Solicitação de Compra"
                                >
                                  <XCircle size={14} />
                                  <span>Cancelar</span>
                                </button>
                              )}
                              <button
                                className="btn-action-icon delete"
                                title="Excluir Solicitação Permanentemente"
                                onClick={() => handleDeleteRequest(req)}
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
                <ListPagination {...requestPagination} onPageChange={requestPagination.setPage} onPageSizeChange={requestPagination.setPageSize} />
              </div>
            )}

            {/* 2. COTAÇÕES (RFQ) & MAPA COMPARATIVO */}
            {activeMenu === 'cotacoes' && (
              <div className="table-responsive">
                <BulkActionsBar selectedCount={quotationSelection.selectedCount} resourceName={{ singular: 'cotação', plural: 'cotações' }} onClear={quotationSelection.clearSelection} onDelete={() => void runPurchasingBulkAction(quotationSelection.selectedIdList, 'Excluir', purchasingService.deleteQuotation, quotationSelection.clearSelection)} deleteLabel="Excluir selecionadas" />
                <table className="enterprise-table">
                  <thead>
                    <tr>
                      <th className="ui-selection-cell"><input className="ui-selection-checkbox" type="checkbox" aria-label="Selecionar cotações desta página" checked={quotationSelection.isAllSelected(quotationPagination.pageItems)} onChange={() => quotationSelection.toggleSelectAll(quotationPagination.pageItems)} /></th>
                      <th className="th-sortable" onClick={() => handleQuotSort('number')}>
                        <div className="th-content">
                          <span>Cotação</span>
                          {quotSortField === 'number' ? (quotSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th className="th-sortable" onClick={() => handleQuotSort('request')}>
                        <div className="th-content">
                          <span>Solicitação de Origem</span>
                          {quotSortField === 'request' ? (quotSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th className="th-sortable" onClick={() => handleQuotSort('proposals')}>
                        <div className="th-content">
                          <span>Propostas Recebidas</span>
                          {quotSortField === 'proposals' ? (quotSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th className="th-sortable" onClick={() => handleQuotSort('status')}>
                        <div className="th-content">
                          <span>Status</span>
                          {quotSortField === 'status' ? (quotSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th className="th-sortable" onClick={() => handleQuotSort('created_at')}>
                        <div className="th-content">
                          <span>Data de Abertura</span>
                          {quotSortField === 'created_at' ? (quotSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th style={{ textAlign: 'right' }}>Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredQuotations.length === 0 ? (
                      <tr><td colSpan={7} className="state-empty">Nenhum processo de cotação encontrado com os filtros selecionados.</td></tr>
                    ) : (
                      quotationPagination.pageItems.map(quot => (
                        <tr key={quot.id} className={quotationSelection.isSelected(quot.id) ? 'ui-record-row--selected' : ''}>
                          <td className="ui-selection-cell"><input className="ui-selection-checkbox" type="checkbox" aria-label={`Selecionar cotação ${quot.quotation_number}`} checked={quotationSelection.isSelected(quot.id)} onChange={() => quotationSelection.toggleSelect(quot.id)} /></td>
                          <td>
                            <div className="cell-with-icon">
                              <div className="icon-badge orange-bg"><BarChart2 size={15} /></div>
                              <div>
                                <strong>{quot.quotation_number}</strong>
                                <span className="sub-label">{quot.notes || 'Cotação concorrencial'}</span>
                              </div>
                            </div>
                          </td>
                          <td>
                            {quot.purchase_request_id ? (
                              <RecordLink type="PURCHASE_REQUEST" id={quot.purchase_request_id}>
                                <span className="code-tag">{quot.purchase_request?.request_number || `PR #${quot.purchase_request_id.slice(0, 8)}`}</span>
                              </RecordLink>
                            ) : (
                              <span className="code-tag">{quot.purchase_request?.request_number || '-'}</span>
                            )}
                          </td>
                          <td>
                            <strong>{quot.quotes.length} {quot.quotes.length === 1 ? 'proposta' : 'propostas'}</strong>
                          </td>
                          <td>
                            <span className={`badge-pill ${quot.status}`}>
                              {quot.status === 'open' && 'Aberta'}
                              {quot.status === 'analyzing' && 'Em Análise Comparativa'}
                              {quot.status === 'completed' && 'Homologada / PO Emitida'}
                              {quot.status === 'cancelled' && 'Cancelada'}
                            </span>
                          </td>
                          <td>{new Date(quot.created_at).toLocaleDateString('pt-BR')}</td>
                          <td>
                            <div className="row-actions">
                              {quot.status === 'completed' && (
                                <button
                                  className="btn-reopen-action"
                                  onClick={() => handleReopenQuotation(quot.id)}
                                  title="Reabrir cotação para trocar vencedor ou lançar novos preços"
                                >
                                  <RefreshCw size={14} />
                                  <span>Reabrir</span>
                                </button>
                              )}
                              {quot.status !== 'completed' && quot.status !== 'cancelled' && (
                                <button
                                  className="btn-add-quote-action"
                                  onClick={() => handleOpenAddQuoteModal(quot)}
                                  title="Lançar proposta de fornecedor"
                                >
                                  <Plus size={14} />
                                  <span>Lançar Proposta</span>
                                </button>
                              )}
                              <button
                                className="btn-comparison-action"
                                onClick={() => handleOpenComparisonModal(quot)}
                                title="Ver mapa comparativo analítico"
                              >
                                <BarChart2 size={14} />
                                <span>Mapa Comparativo</span>
                              </button>
                              {quot.status !== 'cancelled' && (
                                <button
                                  className="btn-cancel-action"
                                  onClick={() => handleCancelQuotation(quot.id)}
                                  title="Cancelar Processo de Cotação"
                                >
                                  <XCircle size={14} />
                                  <span>Cancelar</span>
                                </button>
                              )}
                              <button
                                className="btn-action-icon delete"
                                onClick={() => handleDeleteQuotation(quot)}
                                title="Excluir Cotação Permanentemente"
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
                <ListPagination {...quotationPagination} onPageChange={quotationPagination.setPage} onPageSizeChange={quotationPagination.setPageSize} />
              </div>
            )}

            {/* 3. ORDENS DE COMPRA (PO) */}
            {activeMenu === 'ordens' && (
              <div className="table-responsive">
                <BulkActionsBar selectedCount={orderSelection.selectedCount} resourceName={{ singular: 'ordem', plural: 'ordens' }} onClear={orderSelection.clearSelection} onDelete={() => void runPurchasingBulkAction(orderSelection.selectedIdList, 'Excluir', purchasingService.deletePurchaseOrder, orderSelection.clearSelection)} deleteLabel="Excluir selecionadas" />
                <table className="enterprise-table">
                  <thead>
                    <tr>
                      <th className="ui-selection-cell"><input className="ui-selection-checkbox" type="checkbox" aria-label="Selecionar ordens desta página" checked={orderSelection.isAllSelected(orderPagination.pageItems)} onChange={() => orderSelection.toggleSelectAll(orderPagination.pageItems)} /></th>
                      <th className="th-sortable" onClick={() => handleOrderSort('number')}>
                        <div className="th-content">
                          <span>Ordem de Compra</span>
                          {orderSortField === 'number' ? (orderSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th className="th-sortable" onClick={() => handleOrderSort('supplier')}>
                        <div className="th-content">
                          <span>Fornecedor</span>
                          {orderSortField === 'supplier' ? (orderSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th className="th-sortable" onClick={() => handleOrderSort('request')}>
                        <div className="th-content">
                          <span>Origem (SC)</span>
                          {orderSortField === 'request' ? (orderSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th className="th-sortable" onClick={() => handleOrderSort('amount')}>
                        <div className="th-content">
                          <span>Total Líquido</span>
                          {orderSortField === 'amount' ? (orderSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th className="th-sortable" onClick={() => handleOrderSort('status')}>
                        <div className="th-content">
                          <span>Status</span>
                          {orderSortField === 'status' ? (orderSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th className="th-sortable" onClick={() => handleOrderSort('created_at')}>
                        <div className="th-content">
                          <span>Entrega / NF</span>
                          {orderSortField === 'created_at' ? (orderSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th style={{ textAlign: 'right' }}>Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredOrders.length === 0 ? (
                      <tr><td colSpan={8} className="state-empty">Nenhuma ordem de compra encontrada com os filtros selecionados.</td></tr>
                    ) : (
                      orderPagination.pageItems.map(ord => (
                        <tr key={ord.id} className={`ui-record-row ${orderSelection.isSelected(ord.id) ? 'ui-record-row--selected' : ''}`} role="button" tabIndex={0} onClick={() => { setSelectedOrderForView(ord); setIsViewOrderModalOpen(true); }} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setSelectedOrderForView(ord); setIsViewOrderModalOpen(true); } }}>
                          <td className="ui-selection-cell"><input className="ui-selection-checkbox" type="checkbox" aria-label={`Selecionar ordem ${ord.order_number}`} checked={orderSelection.isSelected(ord.id)} onClick={(event) => event.stopPropagation()} onChange={() => orderSelection.toggleSelect(ord.id)} /></td>
                          <td>
                            <div className="cell-with-icon">
                              <div className="icon-badge blue-bg"><Truck size={15} /></div>
                              <div>
                                <RecordLink type="PURCHASE_ORDER" id={ord.id}><strong>{ord.order_number}</strong></RecordLink>
                                <span className="sub-label">{new Date(ord.created_at).toLocaleDateString('pt-BR')}</span>
                              </div>
                            </div>
                          </td>
                          <td>
                            <RecordLink type="SUPPLIER" id={ord.supplier_id}>
                              <strong>{ord.supplier?.name || '-'}</strong>
                            </RecordLink>
                            <span className="sub-label">{ord.supplier?.cnpj_cpf || ''}</span>
                          </td>
                          <td>
                            {ord.purchase_request_id ? (
                              <RecordLink type="PURCHASE_REQUEST" id={ord.purchase_request_id}>
                                <span className="code-tag">{ord.purchase_request?.request_number || `PR #${ord.purchase_request_id.slice(0, 8)}`}</span>
                              </RecordLink>
                            ) : (
                              <span className="code-tag">{ord.purchase_request?.request_number || 'Direta'}</span>
                            )}
                          </td>
                          <td><strong>{formatCurrency(ord.total_amount)}</strong></td>
                          <td>
                            <span className={`badge-pill ${ord.status}`}>
                              {ord.status === 'draft' && 'Rascunho'}
                              {ord.status === 'issued' && 'Emitida'}
                              {ord.status === 'received' && 'Recebida'}
                              {ord.status === 'partially_received' && 'Recebimento Parcial'}
                              {ord.status === 'cancelled' && 'Cancelada'}
                            </span>
                          </td>
                          <td>
                            {ord.invoice_number ? (
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                                <span className="code-tag">NF: {ord.invoice_number}</span>
                                {ord.invoice_attachment && (
                                  <a
                                    href={ord.invoice_attachment}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    download={`NF_${ord.invoice_number}`}
                                    title="Baixar Nota Fiscal Anexada"
                                    style={{ color: 'var(--primary-color)', display: 'inline-flex' }}
                                  >
                                    <Paperclip size={13} />
                                  </a>
                                )}
                              </div>
                            ) : (
                              <span className="text-muted-small">Aguardando entrega</span>
                            )}
                          </td>
                          <td>
                            <div className="row-actions" onClick={(event) => event.stopPropagation()}>
                              {ord.status === 'issued' && (
                                <>
                                  <button className="btn-receive-action" onClick={() => handleOpenReceiveModal(ord)}>
                                    <Box size={14} />
                                    <span>Receber</span>
                                  </button>
                                  <button
                                    className="btn-cancel-action"
                                    onClick={() => handleCancelOrder(ord.id, ord.order_number)}
                                    title="Cancelar Ordem de Compra"
                                  >
                                    <XCircle size={14} />
                                    <span>Cancelar</span>
                                  </button>
                                </>
                              )}
                              <button
                                className="btn-action-icon edit"
                                title="Visualizar Ordem"
                                onClick={() => { setSelectedOrderForView(ord); setIsViewOrderModalOpen(true); }}
                              >
                                <FileText size={15} />
                              </button>
                              <button
                                className="btn-action-icon delete"
                                title="Excluir Ordem de Compra Permanentemente"
                                onClick={() => handleDeleteOrder(ord)}
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
                <ListPagination {...orderPagination} onPageChange={orderPagination.setPage} onPageSizeChange={orderPagination.setPageSize} />
              </div>
            )}

            {/* 4. FORNECEDORES HOMOLOGADOS */}
            {activeMenu === 'fornecedores' && (
              <div className="table-responsive">
                <BulkActionsBar selectedCount={supplierSelection.selectedCount} resourceName={{ singular: 'fornecedor', plural: 'fornecedores' }} onClear={supplierSelection.clearSelection} onDelete={() => void runPurchasingBulkAction(supplierSelection.selectedIdList, 'Excluir', purchasingService.deleteSupplier, supplierSelection.clearSelection)} deleteLabel="Excluir selecionados" />
                <table className="enterprise-table">
                  <thead>
                    <tr>
                      <th className="ui-selection-cell"><input className="ui-selection-checkbox" type="checkbox" aria-label="Selecionar fornecedores desta página" checked={supplierSelection.isAllSelected(supplierPagination.pageItems)} onChange={() => supplierSelection.toggleSelectAll(supplierPagination.pageItems)} /></th>
                      <th className="th-sortable" onClick={() => handleSupSort('name')}>
                        <div className="th-content">
                          <span>Fornecedor / Razão Social</span>
                          {supSortField === 'name' ? (supSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th className="th-sortable" onClick={() => handleSupSort('cnpj')}>
                        <div className="th-content">
                          <span>CNPJ / IE</span>
                          {supSortField === 'cnpj' ? (supSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th>Linhas / Segmentos Atendidos</th>
                      <th className="th-sortable" onClick={() => handleSupSort('payment_terms')}>
                        <div className="th-content">
                          <span>Condição Comercial</span>
                          {supSortField === 'payment_terms' ? (supSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th>Representante / Contato</th>
                      <th className="th-sortable" onClick={() => handleSupSort('city')}>
                        <div className="th-content">
                          <span>Localização</span>
                          {supSortField === 'city' ? (supSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th style={{ textAlign: 'right' }}>Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredSuppliers.length === 0 ? (
                      <tr><td colSpan={8} className="state-empty">Nenhum fornecedor encontrado com os filtros selecionados.</td></tr>
                    ) : (
                      supplierPagination.pageItems.map(sup => {
                        const segmentList = sup.segments ? sup.segments.split(',').map(s => s.trim()).filter(Boolean) : [];

                        return (
                          <tr key={sup.id} className={`ui-record-row ${supplierSelection.isSelected(sup.id) ? 'ui-record-row--selected' : ''}`} role="button" tabIndex={0} onClick={(event) => { if (!(event.target as HTMLElement).closest('button, a, input')) handleEditSupplier(sup); }} onKeyDown={(event) => { if (['Enter', ' '].includes(event.key)) { event.preventDefault(); handleEditSupplier(sup); } }}>
                            <td className="ui-selection-cell"><input className="ui-selection-checkbox" type="checkbox" aria-label={`Selecionar fornecedor ${sup.name}`} checked={supplierSelection.isSelected(sup.id)} onClick={(event) => event.stopPropagation()} onChange={() => supplierSelection.toggleSelect(sup.id)} /></td>
                            <td>
                              <div className="cell-with-icon">
                                <div className="icon-badge orange-bg"><Users size={15} /></div>
                                <div>
                                  <strong>{sup.name}</strong>
                                  {sup.trade_name && <span className="sub-label">{sup.trade_name}</span>}
                                  {sup.anvisa_license && (
                                    <span className="anvisa-badge" title="Autorização ANVISA / Alvará">
                                      <ShieldCheck size={11} /> {sup.anvisa_license}
                                    </span>
                                  )}
                                </div>
                              </div>
                            </td>
                            <td>
                              <span className="code-tag">{sup.cnpj_cpf || '-'}</span>
                              {sup.state_registration && <span className="sub-label">IE: {sup.state_registration}</span>}
                            </td>
                            <td>
                              <div className="segments-tags-cell">
                                {segmentList.length > 0 ? (
                                  segmentList.map((seg, i) => (
                                    <span key={i} className="segment-pill">{seg}</span>
                                  ))
                                ) : (
                                  <span className="text-muted-small">Geral / Sem segmento</span>
                                )}
                              </div>
                            </td>
                            <td>
                              <div>
                                <strong>{sup.payment_terms || '30 DDL'}</strong>
                                {sup.min_order_amount ? (
                                  <span className="sub-label">Mín: {formatCurrency(sup.min_order_amount)}</span>
                                ) : null}
                              </div>
                            </td>
                            <td>
                              <div className="contact-cell">
                                {sup.contact_name && <strong><Users size={12} /> {sup.contact_name}</strong>}
                                {sup.phone && <span><Phone size={12} /> {sup.phone}</span>}
                                {sup.email && <span><Mail size={12} /> {sup.email}</span>}
                              </div>
                            </td>
                            <td>{sup.city && sup.state ? `${sup.city} / ${sup.state}` : (sup.city || sup.state || '-')}</td>
                            <td style={{ textAlign: 'right' }}>
                              <div className="row-actions">
                                <button
                                  className="btn-action-icon delete"
                                  title="Excluir Fornecedor"
                                  onClick={() => handleDeleteSupplier(sup)}
                                >
                                  <Trash2 size={14} />
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
                <ListPagination {...supplierPagination} onPageChange={supplierPagination.setPage} onPageSizeChange={supplierPagination.setPageSize} />
              </div>
            )}

            {/* 5. PRODUTOS & INSUMOS */}
            {activeMenu === 'produtos' && (
              <div className="table-responsive">
                <BulkActionsBar selectedCount={productSelection.selectedCount} resourceName={{ singular: 'produto', plural: 'produtos' }} onClear={productSelection.clearSelection} onDelete={() => void runPurchasingBulkAction(productSelection.selectedIdList, 'Excluir', inventoryService.deleteProduct, productSelection.clearSelection)} deleteLabel="Excluir selecionados" />
                <table className="enterprise-table">
                  <thead>
                    <tr>
                      <th className="ui-selection-cell"><input className="ui-selection-checkbox" type="checkbox" aria-label="Selecionar produtos desta página" checked={productSelection.isAllSelected(productPagination.pageItems)} onChange={() => productSelection.toggleSelectAll(productPagination.pageItems)} /></th>
                      <th className="th-sortable" onClick={() => handleProdSort('name')}>
                        <div className="th-content">
                          <span>SKU / Produto</span>
                          {prodSortField === 'name' ? (prodSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th className="th-sortable" onClick={() => handleProdSort('category')}>
                        <div className="th-content">
                          <span>Categoria</span>
                          {prodSortField === 'category' ? (prodSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th className="th-sortable" onClick={() => handleProdSort('brand')}>
                        <div className="th-content">
                          <span>Marca / Fabricante</span>
                          {prodSortField === 'brand' ? (prodSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th>Unidade</th>
                      <th className="th-sortable" onClick={() => handleProdSort('stock')}>
                        <div className="th-content">
                          <span>Estoque Físico (Atual / Mín)</span>
                          {prodSortField === 'stock' ? (prodSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th className="th-sortable" onClick={() => handleProdSort('price')}>
                        <div className="th-content">
                          <span>Preço Referência</span>
                          {prodSortField === 'price' ? (prodSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th>Rastreabilidade & Validade</th>
                      <th style={{ textAlign: 'right' }}>Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredProducts.length === 0 ? (
                      <tr><td colSpan={9} className="state-empty">Nenhum produto cadastrado ou correspondente aos filtros.</td></tr>
                    ) : (
                      productPagination.pageItems.map(prod => (
                        <tr key={prod.id} className={`ui-record-row ${productSelection.isSelected(prod.id) ? 'ui-record-row--selected' : ''}`} role="button" tabIndex={0} onClick={(event) => { if (!(event.target as HTMLElement).closest('button, a, input')) handleEditProduct(prod); }} onKeyDown={(event) => { if (['Enter', ' '].includes(event.key)) { event.preventDefault(); handleEditProduct(prod); } }}>
                          <td className="ui-selection-cell"><input className="ui-selection-checkbox" type="checkbox" aria-label={`Selecionar produto ${prod.name}`} checked={productSelection.isSelected(prod.id)} onClick={(event) => event.stopPropagation()} onChange={() => productSelection.toggleSelect(prod.id)} /></td>
                          <td>
                            <div className="cell-with-icon">
                              <div className="icon-badge brand-bg"><Package size={15} /></div>
                              <div>
                                <strong>{prod.name}</strong>
                                <span className="sub-label">SKU: {prod.sku}</span>
                              </div>
                            </div>
                          </td>
                          <td>
                            {prod.category?.name ? (
                              <span className="category-tag">{prod.category.name}</span>
                            ) : (
                              <span className="text-muted-small">-</span>
                            )}
                          </td>
                          <td>{prod.brand || '-'}</td>
                          <td><span className="unit-badge">{prod.unit_of_measure}</span></td>
                          <td>
                            <div className="stock-balance-cell">
                              <span className={`stock-now ${Number(prod.current_stock || 0) <= 0 ? 'zero' : Number(prod.current_stock || 0) <= Number(prod.min_stock || 0) ? 'warning' : 'ok'}`}>
                                <strong>{formatQuantity(prod.current_stock)} {prod.unit_of_measure}</strong>
                              </span>
                              <span className="stock-limits">Mín: {formatQuantity(prod.min_stock)}</span>
                            </div>
                          </td>
                          <td><strong>{formatCurrency(prod.reference_price)}</strong></td>
                          <td>
                            <div className="stock-traceability-cell">
                              {prod.is_perishable && <span className="tag-pill perishable">Perecível ({prod.shelf_life_days || 0}d)</span>}
                              {prod.requires_batch && <span className="tag-pill batch">Exige Lote</span>}
                              {prod.storage_location && <span className="tag-pill storage">{prod.storage_location}</span>}
                              {!prod.is_perishable && !prod.requires_batch && <span className="text-muted-small">Padrão</span>}
                            </div>
                          </td>
                          <td style={{ textAlign: 'right' }}>
                            <div className="row-actions">
                              <button
                                className="btn-action-icon delete"
                                title="Excluir Produto / Insumo"
                                onClick={() => handleDeleteProduct(prod)}
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
                <ListPagination {...productPagination} onPageChange={productPagination.setPage} onPageSizeChange={productPagination.setPageSize} />
              </div>
            )}

            {/* 6. CATEGORIAS DE PRODUTOS */}
            {activeMenu === 'categorias' && (
              <div className="table-responsive">
                <BulkActionsBar selectedCount={categorySelection.selectedCount} resourceName={{ singular: 'categoria', plural: 'categorias' }} onClear={categorySelection.clearSelection} onDelete={() => void runPurchasingBulkAction(categorySelection.selectedIdList, 'Excluir', inventoryService.deleteCategory, categorySelection.clearSelection)} deleteLabel="Excluir selecionadas" />
                <table className="enterprise-table">
                  <thead>
                    <tr>
                      <th className="ui-selection-cell"><input className="ui-selection-checkbox" type="checkbox" aria-label="Selecionar categorias desta página" checked={categorySelection.isAllSelected(categoryPagination.pageItems)} onChange={() => categorySelection.toggleSelectAll(categoryPagination.pageItems)} /></th>
                      <th className="th-sortable" onClick={() => handleCatSort('code')}>
                        <div className="th-content">
                          <span>Código / Prefixo SKU</span>
                          {catSortField === 'code' ? (catSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th className="th-sortable" onClick={() => handleCatSort('name')}>
                        <div className="th-content">
                          <span>Nome da Categoria</span>
                          {catSortField === 'name' ? (catSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th>Descrição</th>
                      <th>Produtos Vinculados</th>
                      <th>Status</th>
                      <th style={{ textAlign: 'right' }}>Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredCategories.length === 0 ? (
                      <tr><td colSpan={7} className="state-empty">Nenhuma categoria encontrada com os filtros selecionados.</td></tr>
                    ) : (
                      categoryPagination.pageItems.map(cat => {
                        const linkedCount = products.filter(p => p.category_id === cat.id).length;

                        return (
                          <tr key={cat.id} className={`ui-record-row ${categorySelection.isSelected(cat.id) ? 'ui-record-row--selected' : ''}`} role="button" tabIndex={0} onClick={(event) => { if (!(event.target as HTMLElement).closest('button, a, input')) handleEditCategory(cat); }} onKeyDown={(event) => { if (['Enter', ' '].includes(event.key)) { event.preventDefault(); handleEditCategory(cat); } }}>
                            <td className="ui-selection-cell"><input className="ui-selection-checkbox" type="checkbox" aria-label={`Selecionar categoria ${cat.name}`} checked={categorySelection.isSelected(cat.id)} onClick={(event) => event.stopPropagation()} onChange={() => categorySelection.toggleSelect(cat.id)} /></td>
                            <td>
                              <span className="code-tag highlight">{cat.code || 'GEN'}</span>
                            </td>
                            <td>
                              <div className="cell-with-icon">
                                <div className="icon-badge brand-bg"><Tags size={15} /></div>
                                <div>
                                  <strong>{cat.name}</strong>
                                </div>
                              </div>
                            </td>
                            <td>{cat.description || '-'}</td>
                            <td>
                              <span className="counter-chip">
                                <Package size={12} /> {linkedCount} {linkedCount === 1 ? 'produto' : 'produtos'}
                              </span>
                            </td>
                            <td>
                              <span className="badge-pill active">Ativa</span>
                            </td>
                            <td style={{ textAlign: 'right' }}>
                              <div className="row-actions">
                                <button
                                  className="btn-action-icon delete"
                                  title="Excluir Categoria"
                                  onClick={() => handleDeleteCategory(cat)}
                                >
                                  <Trash2 size={14} />
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
                <ListPagination {...categoryPagination} onPageChange={categoryPagination.setPage} onPageSizeChange={categoryPagination.setPageSize} />
              </div>
            )}

            {/* 6. CENTROS DE CUSTO */}
            {activeMenu === 'centros-custo' && (
              <div className="table-responsive">
                <BulkActionsBar selectedCount={costCenterSelection.selectedCount} resourceName={{ singular: 'centro', plural: 'centros' }} onClear={costCenterSelection.clearSelection} onDelete={() => void runPurchasingBulkAction(costCenterSelection.selectedIdList, 'Excluir', purchasingService.deleteCostCenter, costCenterSelection.clearSelection)} deleteLabel="Excluir selecionados" />
                <table className="enterprise-table">
                  <thead>
                    <tr>
                      <th className="ui-selection-cell"><input className="ui-selection-checkbox" type="checkbox" aria-label="Selecionar centros de custo desta página" checked={costCenterSelection.isAllSelected(costCenterPagination.pageItems)} onChange={() => costCenterSelection.toggleSelectAll(costCenterPagination.pageItems)} /></th>
                      <th className="th-sortable" onClick={() => handleCostSort('code')}>
                        <div className="th-content">
                          <span>Código</span>
                          {costSortField === 'code' ? (costSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th className="th-sortable" onClick={() => handleCostSort('name')}>
                        <div className="th-content">
                          <span>Nome</span>
                          {costSortField === 'name' ? (costSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th>Descrição</th>
                      <th>Status</th>
                      <th style={{ textAlign: 'right' }}>Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredCostCenters.length === 0 ? (
                      <tr><td colSpan={6} className="state-empty">Nenhum centro de custo cadastrado ou correspondente aos filtros.</td></tr>
                    ) : (
                      costCenterPagination.pageItems.map(cc => (
                        <tr key={cc.id} className={`ui-record-row ${costCenterSelection.isSelected(cc.id) ? 'ui-record-row--selected' : ''}`} role="button" tabIndex={0} onClick={(event) => { if (!(event.target as HTMLElement).closest('button, a, input')) handleEditCostCenter(cc); }} onKeyDown={(event) => { if (['Enter', ' '].includes(event.key)) { event.preventDefault(); handleEditCostCenter(cc); } }}>
                          <td className="ui-selection-cell"><input className="ui-selection-checkbox" type="checkbox" aria-label={`Selecionar centro de custo ${cc.name}`} checked={costCenterSelection.isSelected(cc.id)} onClick={(event) => event.stopPropagation()} onChange={() => costCenterSelection.toggleSelect(cc.id)} /></td>
                          <td><span className="code-tag">{cc.code}</span></td>
                          <td><strong>{cc.name}</strong></td>
                          <td>{cc.description || '-'}</td>
                          <td><span className="badge-pill active">Ativo</span></td>
                          <td style={{ textAlign: 'right' }}>
                            <div className="row-actions">
                              <button
                                className="btn-action-icon delete"
                                title="Excluir Centro de Custo"
                                onClick={() => handleDeleteCostCenter(cc)}
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
                <ListPagination {...costCenterPagination} onPageChange={costCenterPagination.setPage} onPageSizeChange={costCenterPagination.setPageSize} />
              </div>
            )}

            {/* 7. EXTRATO DE MOVIMENTAÇÕES DE ESTOQUE */}
            {activeMenu === 'movimentacoes' && (
              <div className="table-responsive">
                <table className="enterprise-table">
                  <thead>
                    <tr>
                      <th className="th-sortable" onClick={() => handleMovSort('created_at')}>
                        <div className="th-content">
                          <span>Data / Horário</span>
                          {movSortField === 'created_at' ? (movSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th className="th-sortable" onClick={() => handleMovSort('product')}>
                        <div className="th-content">
                          <span>Produto / Insumo</span>
                          {movSortField === 'product' ? (movSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th className="th-sortable" onClick={() => handleMovSort('type')}>
                        <div className="th-content">
                          <span>Tipo de Movimentação</span>
                          {movSortField === 'type' ? (movSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th className="th-sortable" onClick={() => handleMovSort('quantity')}>
                        <div className="th-content">
                          <span>Quantidade Movimentada</span>
                          {movSortField === 'quantity' ? (movSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th className="th-sortable" onClick={() => handleMovSort('unit_cost')}>
                        <div className="th-content">
                          <span>Custo Unitário</span>
                          {movSortField === 'unit_cost' ? (movSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th className="th-sortable" onClick={() => handleMovSort('balance_after')}>
                        <div className="th-content">
                          <span>Saldo Resultante</span>
                          {movSortField === 'balance_after' ? (movSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                        </div>
                      </th>
                      <th>Documento / Referência</th>
                      <th>Observações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredMovements.length === 0 ? (
                      <tr><td colSpan={8} className="state-empty">Nenhuma movimentação de estoque registrada. Ao receber ordens de compra ou realizar ajustes, o histórico aparecerá aqui.</td></tr>
                    ) : (
                      movementPagination.pageItems.map(mov => {
                        const isPositive = mov.movement_type.startsWith('in_');

                        return (
                          <tr key={mov.id}>
                            <td>
                              <div className="time-cell">
                                <strong>{new Date(mov.created_at).toLocaleDateString('pt-BR')}</strong>
                                <span className="sub-label">{new Date(mov.created_at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}</span>
                              </div>
                            </td>
                            <td>
                              <div className="cell-with-icon">
                                <div className="icon-badge brand-bg"><Package size={14} /></div>
                                <div>
                                  <RecordLink type="PRODUCT" id={mov.product_id}>
                                    <strong>{mov.product_name || mov.product?.name || 'Produto'}</strong>
                                  </RecordLink>
                                  <span className="sub-label">SKU: {mov.sku || mov.product?.sku || '-'}</span>
                                </div>
                              </div>
                            </td>
                            <td>
                              {mov.movement_type === 'in_purchase' && (
                                <span className="movement-badge in-purchase">
                                  <ArrowDownRight size={13} /> Entrada por Compra (PO)
                                </span>
                              )}
                              {mov.movement_type === 'in_adjustment' && (
                                <span className="movement-badge in-adj">
                                  <ArrowDownRight size={13} /> Entrada (Ajuste Inventário)
                                </span>
                              )}
                              {mov.movement_type === 'out_sale' && (
                                <span className="movement-badge out-sale">
                                  <ArrowUpRight size={13} /> Saída por Venda
                                </span>
                              )}
                              {mov.movement_type === 'out_adjustment' && (
                                <span className="movement-badge out-adj">
                                  <ArrowUpRight size={13} /> Baixa (Ajuste Inventário)
                                </span>
                              )}
                              {mov.movement_type === 'out_loss' && (
                                <span className="movement-badge out-loss">
                                  <AlertTriangle size={13} /> Perda / Avaria / Validade
                                </span>
                              )}
                            </td>
                            <td>
                              <strong className={isPositive ? 'qty-pos' : 'qty-neg'}>
                                {isPositive ? '+' : '-'}{formatQuantity(mov.quantity)} {mov.product?.unit_of_measure || 'UN'}
                              </strong>
                            </td>
                            <td>{formatCurrency(mov.unit_cost)}</td>
                            <td>
                              <span className="balance-tag">
                                {formatQuantity(mov.balance_after)} {mov.product?.unit_of_measure || 'UN'}
                              </span>
                            </td>
                            <td>
                              <span className="code-tag">{mov.reference_doc || '-'}</span>
                            </td>
                            <td>
                              <span className="notes-cell">{mov.notes || '-'}</span>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
                <ListPagination {...movementPagination} onPageChange={movementPagination.setPage} onPageSizeChange={movementPagination.setPageSize} />
              </div>
            )}
          </div>
        </main>
      </div>

      {/* =====================================================================
          MODAL: LANÇAR PROPOSTA DE FORNECEDOR (RFQ)
      ===================================================================== */}
      {isAddQuoteModalOpen && activeQuotationForQuote && (
        <Modal
          isOpen={isAddQuoteModalOpen}
          onClose={() => setIsAddQuoteModalOpen(false)}
          title={`Lançar Proposta Comercial • Cotação ${activeQuotationForQuote.quotation_number}`}
          size="lg"
        >
          <form onSubmit={handleSaveSupplierQuote} className="wizard-form">
            {modalError && <div className="modal-alert-error"><AlertCircle size={16} /> {modalError}</div>}

            <div className="form-row">
              <div className="form-group" style={{ flex: 2 }}>
                <label>Fornecedor Participante *</label>
                <select
                  value={quoteSupplierId}
                  onChange={e => setQuoteSupplierId(e.target.value)}
                  required
                >
                  <option value="">Selecione o fornecedor participante...</option>
                  {suppliers.filter(s => s.is_active).map(s => (
                    <option key={s.id} value={s.id}>{s.name} ({s.cnpj_cpf || 'S/ CNPJ'})</option>
                  ))}
                </select>
              </div>

              <div className="form-group" style={{ flex: 1 }}>
                <label>Nº Proposta do Fornecedor</label>
                <input
                  type="text"
                  value={quoteReference}
                  onChange={e => setQuoteReference(e.target.value)}
                  placeholder="Ex: PROP-1029/2026"
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Condição de Pagamento</label>
                <input
                  type="text"
                  value={quotePaymentTerms}
                  onChange={e => setQuotePaymentTerms(e.target.value)}
                  placeholder="Ex: 30 DDL, À Vista"
                />
              </div>

              <div className="form-group">
                <label>Modalidade de Frete</label>
                <select value={quoteFreightType} onChange={e => setQuoteFreightType(e.target.value)}>
                  <option value="CIF">CIF (Por conta do Fornecedor)</option>
                  <option value="FOB">FOB (Por conta do Comprador)</option>
                  <option value="Sem Frete">Sem Frete / Retira</option>
                </select>
              </div>

              <div className="form-group">
                <label>Prazo de Entrega (Dias Úteis)</label>
                <input
                  type="number"
                  value={quoteLeadTimeDays}
                  onChange={e => setQuoteLeadTimeDays(e.target.value)}
                  min="0"
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Valor do Frete (R$)</label>
                <input
                  type="number"
                  step="0.01"
                  value={quoteFreightAmount}
                  onChange={e => setQuoteFreightAmount(e.target.value)}
                  min="0"
                />
              </div>

              <div className="form-group">
                <label>Desconto Comercial (R$)</label>
                <input
                  type="number"
                  step="0.01"
                  value={quoteDiscountAmount}
                  onChange={e => setQuoteDiscountAmount(e.target.value)}
                  min="0"
                />
              </div>
            </div>

            {/* ITENS DA COTAÇÃO */}
            <div className="items-section">
              <div className="items-header">
                <div className="items-header-left">
                  <span className="title">Preços Cotados por Item</span>
                  <span className="counter-badge">{quoteItems.length} itens</span>
                </div>
              </div>

              <div className="items-columns-header" style={{ gridTemplateColumns: '2fr 1fr 1.2fr 1.2fr 1.2fr' }}>
                <span>Produto</span>
                <span>Qtd Solicitada</span>
                <span>Preço Unit. Cotado (R$)</span>
                <span>Marca Ofertada</span>
                <span style={{ textAlign: 'right' }}>Total (R$)</span>
              </div>

              <div className="items-table-wrap">
                {quoteItems.map((item, idx) => {
                  const prod = products.find(p => p.id === item.product_id);
                  const itemTotal = item.quantity * item.unit_price;

                  return (
                    <div key={idx} className="item-row-card" style={{ gridTemplateColumns: '2fr 1fr 1.2fr 1.2fr 1.2fr' }}>
                      <div className="field-prod">
                        <strong>{prod?.name || 'Item'}</strong>
                        <span className="sub-label">{prod?.sku}</span>
                      </div>

                      <div className="field-qty">
                        <span>{item.quantity} {prod?.unit_of_measure || 'UN'}</span>
                      </div>

                      <div className="field-price">
                        <input
                          type="number"
                          step="0.01"
                          value={item.unit_price}
                          onChange={e => {
                            const newItems = [...quoteItems];
                            newItems[idx].unit_price = parseFloat(e.target.value) || 0;
                            setQuoteItems(newItems);
                          }}
                          placeholder="R$ 0,00"
                          min="0.01"
                          required
                        />
                      </div>

                      <div className="field-brand">
                        <input
                          type="text"
                          value={item.brand_offered || ''}
                          onChange={e => {
                            const newItems = [...quoteItems];
                            newItems[idx].brand_offered = e.target.value;
                            setQuoteItems(newItems);
                          }}
                          placeholder="Marca/Fabr."
                        />
                      </div>

                      <div className="field-total">
                        {formatCurrency(itemTotal)}
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="items-summary-bar">
                <div className="summary-left">
                  <span>Itens: {formatCurrency(totalQuoteSum)} | Frete: +{formatCurrency(totalQuoteFreight)} | Desconto: -{formatCurrency(totalQuoteDiscount)}</span>
                </div>
                <div className="summary-right">
                  <span className="summary-label">Total Líquido da Proposta:</span>
                  <span className="summary-value">{formatCurrency(totalQuoteNet)}</span>
                </div>
              </div>
            </div>

            <div className="modal-actions">
              <button type="button" className="btn-cancel" onClick={() => setIsAddQuoteModalOpen(false)}>Cancelar</button>
              <button type="submit" className="btn-save" disabled={isSaving}>
                {isSaving ? <Loader2 size={16} className="spinning" /> : <Check size={16} />}
                <span>Salvar Proposta Comercial</span>
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* =====================================================================
          MODAL: MAPA COMPARATIVO DE COTAÇÕES
      ===================================================================== */}
      {isComparisonModalOpen && (
        <Modal
          isOpen={isComparisonModalOpen}
          onClose={() => setIsComparisonModalOpen(false)}
          title={`📊 Mapa Comparativo de Cotações • ${comparisonMatrix?.quotation_number || ''}`}
          size="lg"
        >
          {loadingComparison ? (
            <div className="state-empty"><Loader2 size={24} className="spinning" /> Carregando mapa analítico...</div>
          ) : comparisonMatrix ? (
            <div className="comparison-matrix-view">
              {/* Banner de Homologação com Botão de Reabertura */}
              {comparisonMatrix.status === 'completed' && (
                <div className="homologated-alert-banner">
                  <div className="banner-text">
                    <CheckCircle2 size={18} />
                    <span>Esta cotação já foi homologada e gerou a Ordem de Compra oficial.</span>
                  </div>
                  <button
                    type="button"
                    className="btn-reopen-quotation"
                    onClick={() => handleReopenQuotation(comparisonMatrix.quotation_id)}
                    disabled={isSaving}
                  >
                    <RefreshCw size={14} className={isSaving ? 'spinning' : ''} />
                    <span>Reabrir Cotação / Trocar Vencedor</span>
                  </button>
                </div>
              )}

              {/* Resumo das Propostas Lado a Lado */}
              <div className="quotes-comparison-cards">
                {comparisonMatrix.quotes_summary.map(q => {
                  const isBestTotal = q.id === comparisonMatrix.best_total_quote_id;
                  const isBestLead = q.id === comparisonMatrix.best_lead_time_quote_id;

                  return (
                    <div key={q.id} className={`quote-comparison-card ${isBestTotal ? 'best-offer' : ''}`}>
                      {isBestTotal && (
                        <div className="winner-tag">
                          <Award size={14} />
                          <span>🏆 Melhor Preço Global</span>
                        </div>
                      )}

                      <div className="card-header">
                        <div className="card-header-titles">
                          <h4>{q.supplier?.name}</h4>
                          <span className="quote-ref">{q.quote_reference || 'Proposta'}</span>
                        </div>
                        {comparisonMatrix.status !== 'completed' && (
                          <button
                            type="button"
                            className="btn-delete-quote"
                            title="Excluir proposta deste fornecedor"
                            onClick={() => handleDeleteSupplierQuote(comparisonMatrix.quotation_id, q.id)}
                            disabled={isSaving}
                          >
                            <Trash2 size={13} />
                          </button>
                        )}
                      </div>

                      <div className="card-body">
                        <div className="metric-row">
                          <span className="label">Total Líquido:</span>
                          <span className="val-total">{formatCurrency(q.total_amount)}</span>
                        </div>
                        <div className="metric-row">
                          <span className="label">Prazo de Entrega:</span>
                          <span className="val">
                            {q.lead_time_days ? `${q.lead_time_days} dias úteis` : 'Imediato'}
                            {isBestLead && <span className="fast-pill">⚡ Mais Rápido</span>}
                          </span>
                        </div>
                        <div className="metric-row">
                          <span className="label">Condição:</span>
                          <span className="val">{q.payment_terms || '-'}</span>
                        </div>
                        <div className="metric-row">
                          <span className="label">Frete:</span>
                          <span className="val">{q.freight_type} ({formatCurrency(q.freight_amount)})</span>
                        </div>
                      </div>

                      <div className="card-footer">
                        {comparisonMatrix.status !== 'completed' ? (
                          <button
                            className="btn-select-winner"
                            onClick={() => handleSelectWinnerQuote(comparisonMatrix.quotation_id, q.id)}
                            disabled={isSaving}
                          >
                            <Award size={15} />
                            <span>Homologar Vencedor & Gerar PO</span>
                          </button>
                        ) : q.status === 'selected' ? (
                          <span className="selected-badge">🏆 Proposta Homologada</span>
                        ) : (
                          <span className="rejected-badge">Desclassificada</span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Tabela Item a Item com Destaque para Menor Preço */}
              <div className="matrix-items-table-wrap">
                <h4 className="matrix-table-title">Comparativo Item a Item (Menor Preço Destacado)</h4>
                <table className="enterprise-table matrix-table">
                  <thead>
                    <tr>
                      <th>Produto</th>
                      <th>Qtd</th>
                      <th>Preço Referência</th>
                      {comparisonMatrix.quotes_summary.map(q => (
                        <th key={q.id}>{q.supplier?.name}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {comparisonMatrix.items_comparison.map(item => (
                      <tr key={item.product_id}>
                        <td>
                          <strong>{item.product_name}</strong>
                          <span className="sub-label">{item.sku}</span>
                        </td>
                        <td>{item.requested_quantity} {item.unit_of_measure}</td>
                        <td>{formatCurrency(item.reference_unit_price)}</td>
                        {comparisonMatrix.quotes_summary.map(q => {
                          const unitPrice = item.supplier_prices[q.supplier_id];
                          const isLowest = item.lowest_unit_price !== null && unitPrice === item.lowest_unit_price;

                          return (
                            <td key={q.id} className={isLowest ? 'cell-lowest-price' : ''}>
                              {unitPrice !== undefined ? (
                                <div>
                                  <strong>{formatCurrency(unitPrice)}</strong>
                                  {isLowest && <span className="lowest-badge">🏆 Menor Preço</span>}
                                </div>
                              ) : (
                                <span className="text-muted-small">Não cotado</span>
                              )}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Ações no Rodapé do Modal */}
              <div className="matrix-footer-actions">
                {comparisonMatrix.status !== 'completed' && comparisonMatrix.status !== 'cancelled' ? (
                  <button
                    type="button"
                    className="btn-cancel-quotation-modal"
                    onClick={() => handleCancelQuotation(comparisonMatrix.quotation_id)}
                    disabled={isSaving}
                  >
                    <XCircle size={14} />
                    <span>Cancelar Processo de Cotação</span>
                  </button>
                ) : <div />}

                <button
                  type="button"
                  className="btn-close-map"
                  onClick={() => setIsComparisonModalOpen(false)}
                >
                  <X size={15} />
                  <span>Fechar Mapa Comparativo</span>
                </button>
              </div>
            </div>
          ) : null}
        </Modal>
      )}

      {/* =====================================================================
          MODAIS DE CRIAÇÃO & EDIÇÃO (WIZARD PADRÃO)
      ===================================================================== */}
      {isModalOpen && (
        <Modal
          isOpen={isModalOpen}
          onClose={() => {
            setIsModalOpen(false);
            setEditingSupplier(null);
            setEditingProduct(null);
            setEditingCategory(null);
            setEditingCostCenter(null);
            setEditingRequest(null);
          }}
          title={
            activeMenu === 'solicitacoes' ? (editingRequest ? 'Editar Solicitação de Compra' : 'Nova Solicitação de Compra') :
              activeMenu === 'fornecedores' ? (editingSupplier ? 'Editar Fornecedor Homologado' : 'Novo Fornecedor Homologado') :
                activeMenu === 'produtos' ? (editingProduct ? 'Editar Produto / Insumo' : 'Novo Produto / Insumo') :
                  activeMenu === 'categorias' ? (editingCategory ? 'Editar Categoria de Produto' : 'Nova Categoria de Produto') :
                    (editingCostCenter ? 'Editar Centro de Custo' : 'Novo Centro de Custo')
          }
          size={activeMenu === 'solicitacoes' || activeMenu === 'produtos' || activeMenu === 'fornecedores' ? 'lg' : 'md'}
        >
          <form onSubmit={handleSaveNewItem} className="wizard-form">
            {modalError && <div className="modal-alert-error"><AlertCircle size={16} /> {modalError}</div>}

            {/* Formulário de Solicitação de Compra */}
            {activeMenu === 'solicitacoes' && (
              <>
                <div className="form-group">
                  <label>Justificativa da Aquisição *</label>
                  <textarea
                    value={requestJustification}
                    onChange={e => setRequestJustification(e.target.value)}
                    placeholder="Descreva a finalidade, projeto ou necessidade desta compra..."
                    rows={2}
                    required
                  />
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>Centro de Custo</label>
                    <select
                      value={requestCostCenterId}
                      onChange={e => setRequestCostCenterId(e.target.value)}
                    >
                      <option value="">Selecione o centro de custo...</option>
                      {costCenters.map(cc => (
                        <option key={cc.id} value={cc.id}>{cc.code} - {cc.name}</option>
                      ))}
                    </select>
                  </div>

                  <div className="form-group">
                    <label>Data Limite Desejada</label>
                    <input
                      type="date"
                      value={requestRequiredDate}
                      onChange={e => setRequestRequiredDate(e.target.value)}
                    />
                  </div>
                </div>

                {/* Itens Solicitados */}
                <div className="items-section">
                  <div className="items-header">
                    <div className="items-header-left">
                      <span className="title">Itens Solicitados</span>
                      <span className="counter-badge">{requestItems.length} itens</span>
                    </div>
                    <button
                      type="button"
                      className="btn-add-item-row"
                      onClick={() => {
                        if (products.length > 0) {
                          setRequestItems([...requestItems, {
                            product_id: products[0].id,
                            quantity: 1,
                            estimated_unit_price: Number(products[0].reference_price) || 0
                          }]);
                        }
                      }}
                    >
                      <Plus size={14} />
                      <span>Adicionar Item</span>
                    </button>
                  </div>

                  <div className="items-columns-header">
                    <span>Produto</span>
                    <span>Qtd</span>
                    <span>Preço Est. (R$)</span>
                    <span style={{ textAlign: 'right' }}>Total (R$)</span>
                    <span></span>
                  </div>

                  <div className="items-table-wrap">
                    {requestItems.map((item, idx) => {
                      const itemTotal = item.quantity * item.estimated_unit_price;

                      return (
                        <div key={idx} className="item-row-card">
                          <div className="field-prod">
                            <select
                              value={item.product_id}
                              onChange={e => {
                                const selectedP = products.find(p => p.id === e.target.value);
                                const newItems = [...requestItems];
                                newItems[idx].product_id = e.target.value;
                                if (selectedP) {
                                  newItems[idx].estimated_unit_price = Number(selectedP.reference_price) || 0;
                                }
                                setRequestItems(newItems);
                              }}
                            >
                              {products.map(p => (
                                <option key={p.id} value={p.id}>{p.name} ({p.sku})</option>
                              ))}
                            </select>
                          </div>

                          <div className="field-qty">
                            <input
                              type="number"
                              value={item.quantity}
                              onChange={e => {
                                const newItems = [...requestItems];
                                newItems[idx].quantity = parseFloat(e.target.value) || 1;
                                setRequestItems(newItems);
                              }}
                              min="0.0001"
                              step="any"
                            />
                          </div>

                          <div className="field-price">
                            <input
                              type="number"
                              value={item.estimated_unit_price}
                              onChange={e => {
                                const newItems = [...requestItems];
                                newItems[idx].estimated_unit_price = parseFloat(e.target.value) || 0;
                                setRequestItems(newItems);
                              }}
                              step="0.01"
                            />
                          </div>

                          <div className="field-total">
                            {formatCurrency(itemTotal)}
                          </div>

                          <button
                            type="button"
                            className="btn-remove-row"
                            onClick={() => {
                              setRequestItems(requestItems.filter((_, i) => i !== idx));
                            }}
                          >
                            <Trash2 size={15} />
                          </button>
                        </div>
                      );
                    })}
                  </div>

                  <div className="items-summary-bar">
                    <span className="summary-label">Total Estimado da Requisição:</span>
                    <span className="summary-value">
                      {formatCurrency(requestItems.reduce((acc, it) => acc + (it.quantity * it.estimated_unit_price), 0))}
                    </span>
                  </div>
                </div>
              </>
            )}

            {/* Formulário de Fornecedor */}
            {activeMenu === 'fornecedores' && (
              <>
                <div className="form-section-divider">
                  <Building size={14} />
                  <span>1. Dados Cadastrais & Fiscais</span>
                </div>

                <div className="form-row">
                  <div className="form-group" style={{ flex: 2 }}>
                    <label>Razão Social / Nome Oficial *</label>
                    <input type="text" value={supplierName} onChange={e => setSupplierName(e.target.value)} placeholder="Ex: Distribuidora Farmacêutica Santa Cruz S.A." required />
                  </div>
                  <div className="form-group" style={{ flex: 1 }}>
                    <label>Nome Fantasia</label>
                    <input type="text" value={supplierTradeName} onChange={e => setSupplierTradeName(e.target.value)} placeholder="Ex: Santa Cruz Pharma" />
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>CNPJ / CPF *</label>
                    <input type="text" value={supplierCnpj} onChange={e => setSupplierCnpj(e.target.value)} placeholder="00.000.000/0000-00" required />
                  </div>
                  <div className="form-group">
                    <label>Inscrição Estadual (IE)</label>
                    <input type="text" value={supplierStateRegistration} onChange={e => setSupplierStateRegistration(e.target.value)} placeholder="Ex: 123.456.789.000" />
                  </div>
                  <div className="form-group">
                    <label>Alvará / Licença ANVISA (AFE)</label>
                    <input type="text" value={supplierAnvisaLicense} onChange={e => setSupplierAnvisaLicense(e.target.value)} placeholder="Ex: AFE 1.23456.7" />
                  </div>
                </div>

                <div className="form-section-divider">
                  <Tags size={14} />
                  <span>2. Segmentos & Linhas de Fornecimento</span>
                </div>

                <div className="segment-selector-wrapper">
                  <label className="sub-description">Selecione as categorias e linhas de itens fornecidas por esta empresa:</label>
                  <div className="segment-chips-grid">
                    {PRESET_SEGMENTS.map(seg => {
                      const isSelected = supplierSegments.includes(seg);
                      return (
                        <button
                          key={seg}
                          type="button"
                          className={`segment-chip ${isSelected ? 'selected' : ''}`}
                          onClick={() => {
                            if (isSelected) {
                              setSupplierSegments(supplierSegments.filter(s => s !== seg));
                            } else {
                              setSupplierSegments([...supplierSegments, seg]);
                            }
                          }}
                        >
                          {isSelected ? <Check size={13} /> : <Plus size={13} />}
                          <span>{seg}</span>
                        </button>
                      );
                    })}
                  </div>

                  <div className="custom-segment-input-row">
                    <input
                      type="text"
                      placeholder="Adicionar segmento personalizado (Ex: Vacinas, Fórmulas Especiais)..."
                      value={supplierCustomSegment}
                      onChange={e => setSupplierCustomSegment(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          if (supplierCustomSegment.trim() && !supplierSegments.includes(supplierCustomSegment.trim())) {
                            setSupplierSegments([...supplierSegments, supplierCustomSegment.trim()]);
                            setSupplierCustomSegment('');
                          }
                        }
                      }}
                    />
                    <button
                      type="button"
                      className="btn-add-segment"
                      onClick={() => {
                        if (supplierCustomSegment.trim() && !supplierSegments.includes(supplierCustomSegment.trim())) {
                          setSupplierSegments([...supplierSegments, supplierCustomSegment.trim()]);
                          setSupplierCustomSegment('');
                        }
                      }}
                    >
                      <Plus size={14} />
                      <span>Adicionar Linha</span>
                    </button>
                  </div>
                </div>

                <div className="form-section-divider">
                  <DollarSign size={14} />
                  <span>3. Condições Comerciais & Representante</span>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>Nome do Representante / Vendedor</label>
                    <input type="text" value={supplierContactName} onChange={e => setSupplierContactName(e.target.value)} placeholder="Ex: Carlos Silva" />
                  </div>
                  <div className="form-group">
                    <label>Condição de Pagamento Padrão</label>
                    <input type="text" value={supplierPaymentTerms} onChange={e => setSupplierPaymentTerms(e.target.value)} placeholder="Ex: 30 DDL, 15/30/45 DDL, À Vista" />
                  </div>
                  <div className="form-group">
                    <label>Pedido Mínimo (R$)</label>
                    <input type="number" step="0.01" value={supplierMinOrderAmount} onChange={e => setSupplierMinOrderAmount(e.target.value)} placeholder="0,00" />
                  </div>
                </div>

                <div className="form-section-divider">
                  <Mail size={14} />
                  <span>4. Contato & Endereço</span>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>E-mail Corporativo / Pedidos</label>
                    <input type="email" value={supplierEmail} onChange={e => setSupplierEmail(e.target.value)} placeholder="pedidos@fornecedor.com.br" />
                  </div>
                  <div className="form-group">
                    <label>Telefone / WhatsApp Comercial</label>
                    <input type="text" value={supplierPhone} onChange={e => setSupplierPhone(e.target.value)} placeholder="(11) 98765-4321" />
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group" style={{ flex: 2 }}>
                    <label>Endereço / Logradouro</label>
                    <input type="text" value={supplierAddress} onChange={e => setSupplierAddress(e.target.value)} placeholder="Av. das Indústrias, 1000" />
                  </div>
                  <div className="form-group" style={{ flex: 1 }}>
                    <label>Cidade</label>
                    <input type="text" value={supplierCity} onChange={e => setSupplierCity(e.target.value)} placeholder="São Paulo" />
                  </div>
                  <div className="form-group" style={{ flex: 0.6 }}>
                    <label>UF</label>
                    <input type="text" value={supplierState} onChange={e => setSupplierState(e.target.value.toUpperCase())} maxLength={2} placeholder="SP" />
                  </div>
                  <div className="form-group" style={{ flex: 0.8 }}>
                    <label>CEP</label>
                    <input type="text" value={supplierZipCode} onChange={e => setSupplierZipCode(e.target.value)} placeholder="01234-567" />
                  </div>
                </div>

                <div className="form-group">
                  <label>Observações Comerciais / Histórico</label>
                  <textarea value={supplierNotes} onChange={e => setSupplierNotes(e.target.value)} rows={2} placeholder="Informações relevantes sobre acordos comerciais, tabelas de preço, bonificações..." />
                </div>
              </>
            )}

            {/* Formulário de Produtos & Insumos */}
            {activeMenu === 'produtos' && (
              <>
                <div className="form-section-divider">
                  <Package size={14} />
                  <span>1. Identificação Básica & Classificação</span>
                </div>

                <div className="form-row cols-2-1">
                  <div className="form-group">
                    <label>Nome do Produto / Medicamento <span className="req">*</span></label>
                    <input
                      type="text"
                      value={productName}
                      onChange={e => {
                        setProductName(e.target.value);
                        if (!editingProduct && !productSku) {
                          setProductSku(generateAutomaticSku(e.target.value, productCategoryId, productIsPerishable));
                        }
                      }}
                      placeholder="Ex: Dipirona Monoidratada 500mg/ml Gotas 20ml"
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label>Categoria do Produto</label>
                    <select
                      value={productCategoryId}
                      onChange={e => {
                        setProductCategoryId(e.target.value);
                        if (!editingProduct) {
                          setProductSku(generateAutomaticSku(productName, e.target.value, productIsPerishable));
                        }
                      }}
                    >
                      <option value="">Sem Categoria</option>
                      {categories.map(c => <option key={c.id} value={c.id}>{c.code ? `[${c.code}] ` : ''}{c.name}</option>)}
                    </select>
                  </div>
                </div>

                <div className="form-row cols-3">
                  <div className="form-group">
                    <label>SKU (Código Interno)</label>
                    <div className="input-with-button">
                      <input type="text" value={productSku} onChange={e => setProductSku(e.target.value)} placeholder="Deixe em branco para auto" />
                      <button
                        type="button"
                        className="btn-inline-action"
                        title="Regerar SKU Automático"
                        onClick={() => setProductSku(generateAutomaticSku(productName, productCategoryId, productIsPerishable))}
                      >
                        <Sparkles size={13} /> Auto
                      </button>
                    </div>
                  </div>

                  <div className="form-group">
                    <label>Unidade de Medida</label>
                    <select value={productUnit} onChange={e => setProductUnit(e.target.value)}>
                      <option value="UN">Unidade (UN)</option>
                      <option value="CX">Caixa (CX)</option>
                      <option value="FR">Frasco (FR)</option>
                      <option value="AMP">Ampola (AMP)</option>
                      <option value="KG">Quilo (KG)</option>
                      <option value="L">Litro (L)</option>
                      <option value="MT">Metro (MT)</option>
                    </select>
                  </div>

                  <div className="form-group">
                    <label>Preço de Referência (R$)</label>
                    <input type="number" step="0.01" value={productPrice} onChange={e => setProductPrice(e.target.value)} placeholder="0,00" />
                  </div>
                </div>

                <div className="form-section-divider">
                  <SlidersHorizontal size={14} />
                  <span>2. Saldo Físico & Parâmetros de Ressuprimento</span>
                </div>

                {editingProduct ? (
                  <div className="stock-balance-badge-card">
                    <div className="stock-balance-info">
                      <span className="badge-label">Saldo Físico Atual:</span>
                      <strong className="badge-value">
                        {formatQuantity(productCurrentStock)} {productUnit}
                      </strong>
                    </div>
                    <div className="stock-balance-hint">
                      🔒 O saldo físico é imutável via cadastro. Alterações devem ser feitas via <strong>Movimentação de Estoque</strong>.
                    </div>
                  </div>
                ) : (
                  <div className="form-row cols-3">
                    <div className="form-group">
                      <label>Estoque Inicial de Implantação</label>
                      <input type="number" step="any" min="0" value={productCurrentStock} onChange={e => setProductCurrentStock(e.target.value)} placeholder="0" />
                    </div>
                    <div className="form-group">
                      <label>Estoque Mínimo (Ponto de Pedido)</label>
                      <input type="number" step="any" min="0" value={productMinStock} onChange={e => setProductMinStock(e.target.value)} placeholder="0" />
                    </div>
                    <div className="form-group">
                      <label>Estoque Alvo (Máximo)</label>
                      <input type="number" step="any" min="0" value={productMaxStock} onChange={e => setProductMaxStock(e.target.value)} placeholder="Ex: 50" />
                    </div>
                  </div>
                )}

                {editingProduct && (
                  <div className="form-row cols-2">
                    <div className="form-group">
                      <label>Estoque Mínimo (Ponto de Pedido)</label>
                      <input type="number" step="any" min="0" value={productMinStock} onChange={e => setProductMinStock(e.target.value)} placeholder="0" />
                    </div>
                    <div className="form-group">
                      <label>Estoque Alvo (Máximo)</label>
                      <input type="number" step="any" min="0" value={productMaxStock} onChange={e => setProductMaxStock(e.target.value)} placeholder="Ex: 50" />
                    </div>
                  </div>
                )}

                <div className="form-row cols-2">
                  <div className="form-group">
                    <label>Endereçamento / Localização Almoxarifado</label>
                    <input type="text" value={productStorageLocation} onChange={e => setProductStorageLocation(e.target.value)} placeholder="Ex: Corredor B - Prateleira 03" />
                  </div>
                  <div className="form-group">
                    <label>Marca / Fabricante</label>
                    <input type="text" value={productBrand} onChange={e => setProductBrand(e.target.value)} placeholder="Ex: EMS, Medley, Eurofarma" />
                  </div>
                </div>

                <div className="form-section-divider">
                  <Tags size={14} />
                  <span>3. Rastreabilidade & Tributário (Opcional)</span>
                </div>

                <div className="form-row cols-2">
                  <div className="form-group">
                    <label>Código de Barras / EAN-13</label>
                    <input type="text" value={productBarcode} onChange={e => setProductBarcode(e.target.value)} placeholder="Ex: 7891234567890" />
                  </div>
                  <div className="form-group">
                    <label>Classificação Fiscal (NCM)</label>
                    <input type="text" value={productNcm} onChange={e => setProductNcm(e.target.value)} placeholder="Ex: 3004.90.99" />
                  </div>
                </div>

                <div className="form-checkbox-row">
                  <label className="form-checkbox-label">
                    <input
                      type="checkbox"
                      checked={productIsPerishable}
                      onChange={e => {
                        setProductIsPerishable(e.target.checked);
                        setProductSku(generateAutomaticSku(productName, productCategoryId, e.target.checked));
                      }}
                    />
                    <div className="checkbox-text">
                      <strong>Item Perecível</strong>
                      <small>Exige controle estrito de data de validade</small>
                    </div>
                  </label>

                  <label className="form-checkbox-label">
                    <input
                      type="checkbox"
                      checked={productRequiresBatch}
                      onChange={e => setProductRequiresBatch(e.target.checked)}
                    />
                    <div className="checkbox-text">
                      <strong>Rastreabilidade de Lote</strong>
                      <small>Exige registro do número de lote na entrada</small>
                    </div>
                  </label>
                </div>

                <div className="form-group">
                  <label>Descrição Detalhada / Especificação Técnica</label>
                  <textarea value={productDesc} onChange={e => setProductDesc(e.target.value)} rows={2} placeholder="Indicações, apresentação, dosagem e observações..." />
                </div>
              </>
            )}

            {/* Formulário de Categorias */}
            {activeMenu === 'categorias' && (
              <>
                <div className="form-row">
                  <div className="form-group" style={{ flex: 2 }}>
                    <label>Nome da Categoria *</label>
                    <input
                      type="text"
                      value={categoryName}
                      onChange={e => {
                        setCategoryName(e.target.value);
                        if (!categoryCode) {
                          const autoCode = e.target.value.substring(0, 3).toUpperCase();
                          setCategoryCode(autoCode);
                        }
                      }}
                      placeholder="Ex: Medicamentos Controlados, Perfumaria, Insumos Médicos"
                      required
                    />
                  </div>
                  <div className="form-group" style={{ flex: 1 }}>
                    <label>Código / Prefixo SKU *</label>
                    <input
                      type="text"
                      value={categoryCode}
                      onChange={e => setCategoryCode(e.target.value.toUpperCase())}
                      placeholder="Ex: MED, PERF, INS"
                      maxLength={10}
                      required
                    />
                  </div>
                </div>
                <div className="form-group">
                  <label>Descrição da Categoria</label>
                  <textarea
                    value={categoryDesc}
                    onChange={e => setCategoryDesc(e.target.value)}
                    placeholder="Descreva os tipos de produtos pertencentes a este agrupamento..."
                    rows={3}
                  />
                </div>
              </>
            )}

            {/* Formulário de Centro de Custo */}
            {activeMenu === 'centros-custo' && (
              <>
                <div className="form-row">
                  <div className="form-group" style={{ flex: 1 }}>
                    <label>Código Contábil *</label>
                    <input type="text" value={costCenterCode} onChange={e => setCostCenterCode(e.target.value)} required />
                  </div>
                  <div className="form-group" style={{ flex: 2 }}>
                    <label>Nome do Centro de Custo *</label>
                    <input type="text" value={costCenterName} onChange={e => setCostCenterName(e.target.value)} required />
                  </div>
                </div>
                <div className="form-group">
                  <label>Descrição</label>
                  <textarea value={costCenterDesc} onChange={e => setCostCenterDesc(e.target.value)} rows={2} />
                </div>
              </>
            )}

            <div className="modal-actions">
              <button
                type="button"
                className="btn-cancel"
                onClick={() => {
                  setIsModalOpen(false);
                  setEditingSupplier(null);
                  setEditingProduct(null);
                  setEditingCategory(null);
                  setEditingCostCenter(null);
                  setEditingRequest(null);
                }}
              >
                Cancelar
              </button>
              <button type="submit" className="btn-save" disabled={isSaving}>
                {isSaving ? <Loader2 size={16} className="spinning" /> : <Check size={16} />}
                <span>
                  {editingSupplier || editingProduct || editingCategory || editingCostCenter || editingRequest
                    ? 'Salvar Alterações'
                    : 'Cadastrar Registro'
                  }
                </span>
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* =====================================================================
          MODAL: PARECER DE APROVAÇÃO DA SOLICITAÇÃO
      ===================================================================== */}
      {isApprovalModalOpen && selectedRequestForApproval && (
        <Modal
          isOpen={isApprovalModalOpen}
          onClose={() => setIsApprovalModalOpen(false)}
          title={`Parecer de Alçada • Solicitação ${selectedRequestForApproval.request_number}`}
          size="md"
        >
          <form onSubmit={handleProcessApproval} className="wizard-form">
            {modalError && <div className="modal-alert-error"><AlertCircle size={16} /> {modalError}</div>}

            <div className="approval-card-info">
              <div className="info-row">
                <span className="label">Total Estimado:</span>
                <span className="val">{formatCurrency(selectedRequestForApproval.total_estimated_amount)}</span>
              </div>
              <div className="info-row">
                <span className="label">Justificativa:</span>
                <span className="val-text">{selectedRequestForApproval.justification}</span>
              </div>
            </div>

            <div className="decision-toggle">
              <button
                type="button"
                className={`btn-decision approve ${approvalDecision === 'approved' ? 'active' : ''}`}
                onClick={() => setApprovalDecision('approved')}
              >
                <CheckCircle2 size={16} />
                <span>Aprovar Solicitação</span>
              </button>

              <button
                type="button"
                className={`btn-decision reject ${approvalDecision === 'rejected' ? 'active' : ''}`}
                onClick={() => setApprovalDecision('rejected')}
              >
                <XCircle size={16} />
                <span>Rejeitar Solicitação</span>
              </button>
            </div>

            <div className="form-group" style={{ marginTop: '0.85rem' }}>
              <label>Parecer / Observações da Decisão</label>
              <textarea
                value={approvalComments}
                onChange={e => setApprovalComments(e.target.value)}
                placeholder="Parecer técnico ou comercial para auditoria..."
                rows={3}
              />
            </div>

            <div className="modal-actions">
              <button type="button" className="btn-cancel" onClick={() => setIsApprovalModalOpen(false)}>Cancelar</button>
              <button type="submit" className={`btn-save ${approvalDecision === 'rejected' ? 'danger' : ''}`} disabled={isSaving}>
                {isSaving ? <Loader2 size={16} className="spinning" /> : <Check size={16} />}
                <span>Confirmar Parecer</span>
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* =====================================================================
          MODAL: RECEBIMENTO FÍSICO NO ALMOXARIFADO
      ===================================================================== */}
      {isReceiveModalOpen && selectedOrderForReceive && (
        <Modal
          isOpen={isReceiveModalOpen}
          onClose={() => setIsReceiveModalOpen(false)}
          title={`Recebimento no Almoxarifado • Ordem ${selectedOrderForReceive.order_number}`}
          size="lg"
        >
          <form onSubmit={handleProcessReceive} className="wizard-form">
            {modalError && <div className="modal-alert-error"><AlertCircle size={16} /> {modalError}</div>}

            <div className="approval-card-info">
              <div className="info-row">
                <span className="label">Fornecedor:</span>
                <span className="val-text">{selectedOrderForReceive.supplier?.name}</span>
              </div>
              <div className="info-row">
                <span className="label">Valor Total da Ordem:</span>
                <span className="val">{formatCurrency(selectedOrderForReceive.total_amount)}</span>
              </div>
            </div>

            <div className="form-section-title">
              <FileText size={15} /> Identificação Fiscal
            </div>

            <div className="receive-fields-grid">
              <div className="form-group">
                <label>Tipo *</label>
                <select value={receiveInvoiceType} onChange={e => setReceiveInvoiceType(e.target.value as typeof receiveInvoiceType)}>
                  <option value="NFE">NF-e</option>
                  <option value="NFSE">NFS-e</option>
                  <option value="NFCE">NFC-e</option>
                  <option value="CTE">CT-e</option>
                  <option value="OUTRO">Outro</option>
                </select>
              </div>
              <div className="form-group">
                <label>Número da Nota Fiscal / DANFE *</label>
                <input type="text" value={receiveInvoiceNumber} onChange={e => setReceiveInvoiceNumber(e.target.value)} placeholder="Ex: 001284912" required />
              </div>
              <div className="form-group">
                <label>Série</label>
                <input value={receiveInvoiceSeries} onChange={e => setReceiveInvoiceSeries(e.target.value)} placeholder="Ex: 1" />
              </div>
              <div className="form-group">
                <label>Data de Emissão *</label>
                <input type="date" value={receiveInvoiceIssueDate} onChange={e => setReceiveInvoiceIssueDate(e.target.value)} required />
              </div>
            </div>

            <div className="receive-fields-grid" style={{ gridTemplateColumns: '2fr 1fr' }}>
              <div className="form-group">
                <label>Chave de Acesso da NF-e (44 dígitos)</label>
                <input value={receiveInvoiceAccessKey} onChange={e => setReceiveInvoiceAccessKey(e.target.value)} placeholder="Ex: 35260912345678000190550010009876541234567890" maxLength={100} />
              </div>
              <div className="form-group">
                <label>Total de Impostos (R$)</label>
                <input type="number" step="0.01" min="0" value={receiveTaxAmount} onChange={e => setReceiveTaxAmount(e.target.value)} placeholder="0.00" />
              </div>
            </div>

            <div className="form-group">
              <label>Anexo da Nota Fiscal (PDF, XML ou Imagem)</label>
              {receiveInvoiceAttachmentName ? (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.65rem 0.85rem', background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', overflow: 'hidden' }}>
                    <Paperclip size={16} style={{ color: 'var(--primary-color)', flexShrink: 0 }} />
                    <span style={{ fontSize: '0.85rem', fontWeight: 500, textOverflow: 'ellipsis', whiteSpace: 'nowrap', overflow: 'hidden' }}>{receiveInvoiceAttachmentName}</span>
                  </div>
                  <button
                    type="button"
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444', padding: '0.2rem' }}
                    onClick={() => { setReceiveInvoiceAttachment(null); setReceiveInvoiceAttachmentName(null); }}
                    title="Remover anexo"
                  >
                    <X size={15} />
                  </button>
                </div>
              ) : (
                <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', padding: '0.85rem', border: '1.5px dashed var(--border-color)', borderRadius: '8px', cursor: 'pointer', background: 'var(--bg-input)' }}>
                  <UploadCloud size={18} style={{ color: 'var(--primary-color)' }} />
                  <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Selecionar ou arrastar NF-e (.pdf, .xml, imagem)</span>
                  <input
                    type="file"
                    accept=".pdf,.xml,image/*"
                    onChange={handleReceiveInvoiceFileChange}
                    style={{ display: 'none' }}
                  />
                </label>
              )}
            </div>

            <div className="form-section-title">
              <DollarSign size={15} /> Fatura Pendente & Título a Pagar
            </div>

            <div className="form-checkbox-row" style={{ gridTemplateColumns: '1fr' }}>
              <label className="form-checkbox-label">
                <input type="checkbox" checked={receiveGeneratePayable} onChange={e => setReceiveGeneratePayable(e.target.checked)} />
                <div className="checkbox-text">
                  <strong>Gerar fatura pendente de pagamento ao fornecedor</strong>
                  <small>Cria a obrigação financeira no Contas a Pagar vinculada à Ordem de Compra, NF-e e Entrada em Estoque.</small>
                </div>
              </label>
            </div>

            {receiveGeneratePayable && (
              <>
                <div className="receive-fields-grid">
                  <div className="form-group">
                    <label>Primeiro Vencimento *</label>
                    <input type="date" value={receivePayableDueDate} onChange={e => setReceivePayableDueDate(e.target.value)} required />
                  </div>
                  <div className="form-group">
                    <label>Parcelas *</label>
                    <input type="number" min="1" max="48" value={receiveInstallments} onChange={e => setReceiveInstallments(e.target.value)} required />
                  </div>
                  <div className="form-group">
                    <label>Intervalo (dias)</label>
                    <input type="number" min="1" max="365" value={receiveInstallmentFrequency} onChange={e => setReceiveInstallmentFrequency(e.target.value)} />
                  </div>
                  <div className="form-group">
                    <label>Natureza</label>
                    <select value={receiveExpenseNature} onChange={e => setReceiveExpenseNature(e.target.value as 'OPEX' | 'CAPEX')}>
                      <option value="OPEX">OPEX (Operacional)</option>
                      <option value="CAPEX">CAPEX (Investimento)</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label>Forma Prevista</label>
                    <select value={receivePaymentMethod} onChange={e => setReceivePaymentMethod(e.target.value)}>
                      <option value="BOLETO">Boleto Bancário</option>
                      <option value="PIX">PIX</option>
                      <option value="TRANSFERENCIA">Transferência / TED</option>
                      <option value="CARTAO">Cartão Corporativo</option>
                    </select>
                  </div>
                </div>

                {receivePaymentMethod === 'BOLETO' && (
                  <div className="receive-fields-grid" style={{ gridTemplateColumns: '1.2fr 1fr' }}>
                    <div className="form-group">
                      <label>Linha Digitável do Boleto (47/48 dígitos)</label>
                      <input
                        type="text"
                        value={receiveDigitableLine}
                        onChange={e => setReceiveDigitableLine(e.target.value)}
                        placeholder="Ex: 34191.79001 01043.510047 91020.150008 5 99990000150000"
                      />
                    </div>
                    <div className="form-group">
                      <label>Código de Barras</label>
                      <input
                        type="text"
                        value={receiveBarcode}
                        onChange={e => setReceiveBarcode(e.target.value)}
                        placeholder="Ex: 34195999900001500001790001043510049102015000"
                      />
                    </div>
                  </div>
                )}

                {receivePaymentMethod === 'PIX' && (
                  <div className="form-group">
                    <label>Chave PIX ou Código Copia e Cola</label>
                    <input
                      type="text"
                      value={receivePixCode}
                      onChange={e => setReceivePixCode(e.target.value)}
                      placeholder="Ex: 12.345.678/0001-90 ou payload pix..."
                    />
                  </div>
                )}
              </>
            )}

            <div className="form-group">
              <label>Notas de Conferência Física</label>
              <textarea
                value={receiveNotes}
                onChange={e => setReceiveNotes(e.target.value)}
                placeholder="Ex: Mercadoria conferida integralmente sem avarias..."
                rows={2}
              />
            </div>

            <div className="modal-actions">
              <button type="button" className="btn-cancel" onClick={() => setIsReceiveModalOpen(false)}>Cancelar</button>
              <button type="submit" className="btn-save" disabled={isSaving}>
                {isSaving ? <Loader2 size={16} className="spinning" /> : <Box size={16} />}
                <span>Confirmar Entrada no Almoxarifado</span>
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* =====================================================================
          MODAL: ESPELHO / DETALHES DA ORDEM DE COMPRA
      ===================================================================== */}
      {isViewOrderModalOpen && selectedOrderForView && (
        <Modal
          isOpen={isViewOrderModalOpen}
          onClose={() => setIsViewOrderModalOpen(false)}
          title={`Ordem de Compra Oficial • ${selectedOrderForView.order_number}`}
          size="lg"
        >
          <div className="wizard-form">
            <div className="approval-card-info">
              <div className="info-row">
                <span className="label">Fornecedor:</span>
                <span className="val-text"><strong>{selectedOrderForView.supplier?.name}</strong></span>
              </div>
              <div className="info-row">
                <span className="label">Condição de Pagamento:</span>
                <span className="val-text">{selectedOrderForView.payment_terms || '-'}</span>
              </div>
              <div className="info-row">
                <span className="label">Frete:</span>
                <span className="val-text">{selectedOrderForView.freight_type} ({formatCurrency(selectedOrderForView.freight_amount)})</span>
              </div>
              <div className="info-row">
                <span className="label">Total Líquido da Ordem:</span>
                <span className="val">{formatCurrency(selectedOrderForView.total_amount)}</span>
              </div>
              {selectedOrderForView.invoice_number && (
                <div className="info-row" style={{ gridColumn: '1 / -1', borderTop: '1px solid var(--border-color)', paddingTop: '0.5rem', marginTop: '0.25rem' }}>
                  <span className="label">Nota Fiscal / DANFE:</span>
                  <span className="val-text" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <strong>{selectedOrderForView.invoice_number}</strong>
                    {selectedOrderForView.invoice_attachment && (
                      <a
                        href={selectedOrderForView.invoice_attachment}
                        target="_blank"
                        rel="noopener noreferrer"
                        download={`NF_${selectedOrderForView.invoice_number}`}
                        style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.8rem', color: 'var(--primary-color)', textDecoration: 'underline', fontWeight: 600 }}
                      >
                        <Paperclip size={14} /> Baixar Arquivo da NF-e
                      </a>
                    )}
                  </span>
                </div>
              )}
            </div>

            <div className="items-section">
              <div className="items-header">
                <span className="title">Itens e Quantidades Negociadas</span>
                <span className="counter-badge">{selectedOrderForView.items.length} itens</span>
              </div>

              <div className="items-columns-header" style={{ gridTemplateColumns: '2.5fr 1fr 1.2fr 1.2fr' }}>
                <span>Produto</span>
                <span>Quantidade</span>
                <span>Preço Unitário</span>
                <span style={{ textAlign: 'right' }}>Total (R$)</span>
              </div>

              <div className="items-table-wrap">
                {selectedOrderForView.items.map(it => (
                  <div key={it.id} className="item-row-card" style={{ gridTemplateColumns: '2.5fr 1fr 1.2fr 1.2fr' }}>
                    <div className="field-prod">
                      <strong>{it.product?.name}</strong>
                      <span className="sub-label">{it.product?.sku}</span>
                    </div>
                    <div>{it.quantity} {it.product?.unit_of_measure}</div>
                    <div>{formatCurrency(it.unit_price)}</div>
                    <div className="field-total">{formatCurrency(it.total_price)}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="modal-actions">
              <button type="button" className="btn-cancel" onClick={() => setIsViewOrderModalOpen(false)}>Fechar</button>
            </div>
          </div>
        </Modal>
      )}

      {/* =====================================================================
          MODAL: EMISSÃO ÁGIL DE ORDEM DE COMPRA (SUGESTÕES DE REPOSIÇÃO)
      ===================================================================== */}
      {isQuickOrderModalOpen && (
        <Modal
          isOpen={isQuickOrderModalOpen}
          onClose={() => setIsQuickOrderModalOpen(false)}
          title={
            replenishmentFlow === 'request'
              ? "Solicitação Formal de Compra • Reposição de Estoque"
              : "Emissão Ágil de Ordem de Compra • Reposição de Estoque"
          }
          size="lg"
        >
          <form onSubmit={handleEmitQuickOrder} className="wizard-form">
            {modalError && (
              <div className="modal-error-banner">
                <AlertCircle size={16} />
                <span>{modalError}</span>
              </div>
            )}

            {replenishmentFlow === 'order' ? (<>
            <div className="form-section-divider">
              <Truck size={14} />
              <span>1. Fornecedor & Condições Comerciais</span>
            </div>

            <div className="form-row">
              <div className="form-group" style={{ flex: 2 }}>
                <label>Fornecedor Homologado *</label>
                <select
                  value={quickOrderSupplierId}
                  onChange={e => {
                    const supId = e.target.value;
                    setQuickOrderSupplierId(supId);
                    const sup = suppliers.find(s => s.id === supId);
                    if (sup && sup.payment_terms) {
                      setQuickOrderPaymentTerms(sup.payment_terms);
                    }
                  }}
                  required
                >
                  <option value="">Selecione o Fornecedor...</option>
                  {suppliers.map(s => (
                    <option key={s.id} value={s.id}>
                      {s.name} {s.trade_name ? `(${s.trade_name})` : ''} - CNPJ: {s.cnpj_cpf}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group" style={{ flex: 1 }}>
                <label>Centro de Custo / Orçamento</label>
                <select
                  value={quickOrderCostCenterId}
                  onChange={e => setQuickOrderCostCenterId(e.target.value)}
                >
                  <option value="">Sem Centro de Custo</option>
                  {costCenters.map(cc => (
                    <option key={cc.id} value={cc.id}>[{cc.code}] {cc.name}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Condição de Pagamento</label>
                <input
                  type="text"
                  value={quickOrderPaymentTerms}
                  onChange={e => setQuickOrderPaymentTerms(e.target.value)}
                  placeholder="Ex: 30 DDL, 15/30/45 DDL"
                />
              </div>

              <div className="form-group">
                <label>Tipo de Frete</label>
                <select value={quickOrderFreightType} onChange={e => setQuickOrderFreightType(e.target.value)}>
                  <option value="CIF">CIF (Por conta do Fornecedor)</option>
                  <option value="FOB">FOB (Por conta do Comprador)</option>
                </select>
              </div>

              <div className="form-group">
                <label>Valor do Frete (R$)</label>
                <input
                  type="number"
                  step="0.01"
                  value={quickOrderFreightAmount}
                  onChange={e => setQuickOrderFreightAmount(e.target.value)}
                  placeholder="0,00"
                />
              </div>

              <div className="form-group">
                <label>Desconto Global (R$)</label>
                <input
                  type="number"
                  step="0.01"
                  value={quickOrderDiscountAmount}
                  onChange={e => setQuickOrderDiscountAmount(e.target.value)}
                  placeholder="0,00"
                />
              </div>

              <div className="form-group">
                <label>Previsão de Entrega</label>
                <input
                  type="date"
                  value={quickOrderDeliveryDate}
                  onChange={e => setQuickOrderDeliveryDate(e.target.value)}
                />
              </div>
            </div>
            </>) : (<>
              <div className="form-section-divider">
                <FileText size={14} />
                <span>1. Dados da Solicitação de Compra</span>
              </div>
              <div className="form-row">
                <div className="form-group" style={{ flex: 1 }}>
                  <label>Centro de Custo / Orçamento</label>
                  <select
                    value={quickOrderCostCenterId}
                    onChange={e => setQuickOrderCostCenterId(e.target.value)}
                  >
                    <option value="">Sem Centro de Custo</option>
                    {costCenters.map(cc => (
                      <option key={cc.id} value={cc.id}>[{cc.code}] {cc.name}</option>
                    ))}
                  </select>
                </div>
                <div className="form-group" style={{ flex: 1 }}>
                  <label>Data Necessária</label>
                  <input
                    type="date"
                    value={quickOrderDeliveryDate}
                    onChange={e => setQuickOrderDeliveryDate(e.target.value)}
                  />
                </div>
              </div>
            </>)}

            <div className="form-section-divider">
              <Package size={14} />
              <span>2. Itens da {replenishmentFlow === 'request' ? 'Solicitação' : 'Ordem'} ({quickOrderItems.length} produtos selecionados)</span>
            </div>

            <div className="quick-order-items-table-wrapper">
              <table className="enterprise-table mini-table">
                <thead>
                  <tr>
                    <th>Produto / SKU</th>
                    <th style={{ width: '130px' }}>Qtd. Pedida</th>
                    <th style={{ width: '140px' }}>Preço Unit. (R$)</th>
                    <th style={{ width: '130px', textAlign: 'right' }}>Total (R$)</th>
                    <th style={{ width: '50px' }}></th>
                  </tr>
                </thead>
                <tbody>
                  {quickOrderItems.map((item, idx) => {
                    const itemTotal = item.quantity * item.unit_price;

                    return (
                      <tr key={item.product_id}>
                        <td>
                          <strong>{item.product_name}</strong>
                          <span className="sub-label">SKU: {item.sku}</span>
                        </td>
                        <td>
                          <div className="qty-edit-input-wrapper small">
                            <input
                              type="number"
                              min="1"
                              step="any"
                              value={item.quantity}
                              onChange={e => {
                                const newQty = parseFloat(e.target.value) || 1;
                                const updated = [...quickOrderItems];
                                updated[idx].quantity = newQty;
                                setQuickOrderItems(updated);
                              }}
                            />
                            <span className="unit-label">{item.unit_of_measure}</span>
                          </div>
                        </td>
                        <td>
                          <input
                            type="number"
                            step="0.01"
                            className="input-price-item"
                            value={item.unit_price}
                            onChange={e => {
                              const newPrice = parseFloat(e.target.value) || 0;
                              const updated = [...quickOrderItems];
                              updated[idx].unit_price = newPrice;
                              setQuickOrderItems(updated);
                            }}
                          />
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <strong className="subtotal-highlight">{formatCurrency(itemTotal)}</strong>
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <button
                            type="button"
                            className="btn-action-icon delete"
                            onClick={() => {
                              setQuickOrderItems(quickOrderItems.filter((_, i) => i !== idx));
                            }}
                            title="Remover Item"
                          >
                            <Trash2 size={13} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>

              <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem', padding: '0.5rem', background: 'rgba(255,255,255,0.03)', borderRadius: '6px', border: '1px dashed var(--border-color)' }}>
                <select
                  style={{ flex: 1, padding: '0.45rem 0.65rem', borderRadius: '6px', border: '1px solid var(--border-color)', background: 'var(--bg-input, var(--bg-card))', color: 'inherit', fontSize: '0.85rem' }}
                  value={selectedProductToAdd}
                  onChange={e => {
                    const prodId = e.target.value;
                    if (!prodId) return;
                    const prod = products.find(p => p.id === prodId);
                    if (prod) {
                      if (quickOrderItems.some(it => it.product_id === prod.id)) {
                        toast.warning('Este produto já está na lista da ordem.');
                        setSelectedProductToAdd('');
                        return;
                      }
                      setQuickOrderItems([...quickOrderItems, {
                        product_id: prod.id,
                        product_name: prod.name,
                        sku: prod.sku,
                        unit_of_measure: prod.unit_of_measure,
                        quantity: 1,
                        unit_price: Number(prod.reference_price) || 0
                      }]);
                    }
                    setSelectedProductToAdd('');
                  }}
                >
                  <option value="">+ Adicionar outro produto do catálogo à ordem de compra...</option>
                  {products.map(p => (
                    <option key={p.id} value={p.id}>
                      {p.name} (SKU: {p.sku}) • Preço Ref: {formatCurrency(p.reference_price)}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Resumo Financeiro da Ordem */}
            <div className="order-summary-box">
              <div className="summary-line">
                <span>Subtotal dos Produtos:</span>
                <strong>{formatCurrency(quickOrderItems.reduce((acc, it) => acc + (it.quantity * it.unit_price), 0))}</strong>
              </div>
              {replenishmentFlow === 'order' && (<>
                <div className="summary-line">
                  <span>Frete (+):</span>
                  <span>{formatCurrency(parseFloat(quickOrderFreightAmount) || 0)}</span>
                </div>
                <div className="summary-line">
                  <span>Desconto (-):</span>
                  <span>{formatCurrency(parseFloat(quickOrderDiscountAmount) || 0)}</span>
                </div>
              </>)}
              <div className="summary-line total-net">
                <span>{replenishmentFlow === 'request' ? 'Total Estimado da Solicitação:' : 'Total Líquido da Ordem:'}</span>
                <span className="final-value">
                  {formatCurrency(
                    Math.max(
                      0,
                      quickOrderItems.reduce((acc, it) => acc + (it.quantity * it.unit_price), 0) +
                      (replenishmentFlow === 'order'
                        ? (parseFloat(quickOrderFreightAmount) || 0) -
                          (parseFloat(quickOrderDiscountAmount) || 0)
                        : 0)
                    )
                  )}
                </span>
              </div>
            </div>

            <div className="form-group">
              <label>{replenishmentFlow === 'request' ? 'Justificativa da Solicitação *' : 'Observações / Instruções de Entrega'}</label>
              <textarea
                value={quickOrderNotes}
                onChange={e => setQuickOrderNotes(e.target.value)}
                placeholder={replenishmentFlow === 'request'
                  ? 'Explique a necessidade da reposição...'
                  : 'Ex: Entregar em horário comercial no almoxarifado central...'}
                required={replenishmentFlow === 'request'}
                rows={2}
              />
            </div>

            <div className="modal-actions">
              <button type="button" className="btn-cancel" onClick={() => setIsQuickOrderModalOpen(false)}>Cancelar</button>
              <button type="submit" className="btn-save" disabled={isSaving || quickOrderItems.length === 0}>
                {isSaving
                  ? <Loader2 size={16} className="spinning" />
                  : replenishmentFlow === 'request' ? <FileText size={16} /> : <Zap size={16} />}
                <span>{replenishmentFlow === 'request'
                  ? 'Criar Solicitação e Encaminhar para Aprovação'
                  : 'Emitir Ordem de Compra Oficial (PO)'}</span>
              </button>
            </div>
          </form>
        </Modal>
      )}



      {/* =====================================================================
          MODAL DE CONFIRMAÇÃO & EXCLUSÃO ESTILIZADO (Substitui window.confirm)
      ===================================================================== */}
      <ConfirmModal
        isOpen={confirmModal.isOpen}
        onClose={closeConfirmModal}
        onConfirm={confirmModal.onConfirm}
        title={confirmModal.title}
        subtitle={confirmModal.subtitle}
        message={confirmModal.message}
        confirmText={confirmModal.confirmText}
        cancelText={confirmModal.cancelText}
        type={confirmModal.type}
        isLoading={confirmModal.isLoading}
        errorMessage={confirmModal.errorMessage}
      />
    </div>
  );
};
