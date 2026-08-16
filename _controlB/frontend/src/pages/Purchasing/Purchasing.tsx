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
import {
  ShoppingCart, FileText, Truck, Package, Target, ChevronRight,
  Search, CheckCircle2, XCircle, RefreshCw, Plus, Mail, Phone,
  Loader2, AlertCircle, Trash2, ShieldCheck, Box, Check, BarChart2, Award, Edit,
  Tags, Users, Sparkles, Building, X, DollarSign, Zap, SlidersHorizontal,
  CheckSquare, Square, ArrowUpRight, ArrowDownRight, AlertTriangle,
  UploadCloud, Paperclip
} from 'lucide-react';
import { purchasingService, inventoryService, formatApiError } from '@/services/api';
import {
  Supplier, Product, ProductCategory, CostCenter,
  PurchaseRequest, PurchaseOrder, QuotationProcess,
  QuotationComparisonMatrix, SupplierQuotePayload,
  PurchaseSuggestionsSummary,
  StockMovement
} from '@/types';

import { Modal } from '@/components/Modal/Modal';
import { ConfirmModal } from '@/components/ConfirmModal/ConfirmModal';
import './Purchasing.scss';



type PurchasingMenuOption =
  | 'solicitacoes'
  | 'sugestoes'
  | 'cotacoes'
  | 'ordens'
  | 'fornecedores'
  | 'produtos'
  | 'categorias'
  | 'centros-custo'
  | 'movimentacoes';

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
  const [activeMenu, setActiveMenu] = useState<PurchasingMenuOption>('solicitacoes');
  const [searchTerm, setSearchTerm] = useState('');

  // Estados dos Dados carregados da API
  const [requests, setRequests] = useState<PurchaseRequest[]>([]);
  const [quotations, setQuotations] = useState<QuotationProcess[]>([]);
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<ProductCategory[]>([]);
  const [costCenters, setCostCenters] = useState<CostCenter[]>([]);

  // --- FLUXO ÁGIL: REPOSIÇÃO & INVENTÁRIO ---
  const [suggestionsSummary, setSuggestionsSummary] = useState<PurchaseSuggestionsSummary | null>(null);
  const [selectedSuggestionProductIds, setSelectedSuggestionProductIds] = useState<string[]>([]);
  const [customSuggestionQtys, setCustomSuggestionQtys] = useState<Record<string, number>>({});

  // Modal de Emissão Rápida de PO a partir de Sugestões
  const [isQuickOrderModalOpen, setIsQuickOrderModalOpen] = useState(false);
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

  const loadAllPurchasingData = async () => {
    setLoading(true);
    try {
      const [reqData, quotData, poData, supData, prodData, catData, ccData, suggData, movData] = await Promise.all([
        purchasingService.getPurchaseRequests(),
        purchasingService.getQuotationProcesses(),
        purchasingService.getPurchaseOrders(),
        purchasingService.getSuppliers(),
        inventoryService.getProducts(),
        inventoryService.getCategories(),
        purchasingService.getCostCenters(),
        purchasingService.getReplenishmentSuggestions(),
        inventoryService.getInventoryMovements()
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
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Erro ao abrir processo de cotação.");
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
      alert(formatApiError(err, "Erro ao gerar mapa comparativo."));
      setIsComparisonModalOpen(false);
    } finally {
      setLoadingComparison(false);
    }
  };


  const handleSelectWinnerQuote = async (quotationId: string, quoteId: string) => {
    if (!confirm("Deseja homologar esta proposta como vencedora e gerar a Ordem de Compra oficial?")) {
      return;
    }

    try {
      setIsSaving(true);
      await purchasingService.selectWinnerQuote(quotationId, quoteId, "Homologado pelo Comprador");
      await loadAllPurchasingData();
      setIsComparisonModalOpen(false);
      setActiveMenu('ordens');
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Erro ao homologar proposta vencedora.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancelRequest = async (requestId: string) => {
    if (!confirm("Deseja realmente cancelar esta solicitação de compra e eventuais cotações vinculadas?")) return;
    try {
      setIsSaving(true);
      await purchasingService.cancelPurchaseRequest(requestId);
      await loadAllPurchasingData();
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Erro ao cancelar solicitação de compra.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancelQuotation = async (quotationId: string) => {
    if (!confirm("Deseja realmente cancelar este processo de cotação? A solicitação de compra voltará para o status 'Aprovada'.")) return;
    try {
      setIsSaving(true);
      await purchasingService.cancelQuotation(quotationId);
      await loadAllPurchasingData();
      setIsComparisonModalOpen(false);
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Erro ao cancelar processo de cotação.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleReopenQuotation = async (quotationId: string) => {
    if (!confirm("Deseja reabrir este processo de cotação? A homologação será desfeita e eventuais ordens de compra emitidas serão canceladas.")) return;
    try {
      setIsSaving(true);
      await purchasingService.reopenQuotation(quotationId);
      await loadAllPurchasingData();
      // Recarrega matriz do modal
      const matrix = await purchasingService.getQuotationComparison(quotationId);
      setComparisonMatrix(matrix);
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Erro ao reabrir processo de cotação.");
    } finally {
      setIsSaving(false);
    }
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
    setProductPrice(String(prod.reference_price));
    setProductCategoryId(prod.category_id || '');
    setProductBrand(prod.brand || '');
    setProductBarcode(prod.barcode || '');
    setProductNcm(prod.ncm || '');
    setProductIsPerishable(Boolean(prod.is_perishable));
    setProductRequiresBatch(Boolean(prod.requires_batch));
    setProductShelfLifeDays(prod.shelf_life_days ? String(prod.shelf_life_days) : '');
    setProductCurrentStock(String(prod.current_stock || 0));
    setProductMinStock(String(prod.min_stock || 0));
    setProductMaxStock(prod.max_stock ? String(prod.max_stock) : '');
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

    setIsSaving(true);
    setModalError(null);
    try {
      await purchasingService.receivePurchaseOrder(selectedOrderForReceive.id, {
        invoice_number: receiveInvoiceNumber.trim(),
        invoice_attachment: receiveInvoiceAttachment || undefined,
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

  const handleSelectAllSuggestions = (selectAll: boolean) => {
    if (!suggestionsSummary) return;
    if (selectAll) {
      setSelectedSuggestionProductIds(suggestionsSummary.items.map(it => it.product_id));
    } else {
      setSelectedSuggestionProductIds([]);
    }
  };

  const handleSelectCriticalOnly = () => {
    if (!suggestionsSummary) return;
    const criticalIds = suggestionsSummary.items
      .filter(it => it.urgency_level === 'critical' || it.urgency_level === 'high')
      .map(it => it.product_id);
    setSelectedSuggestionProductIds(criticalIds);
  };

  const handleOpenQuickOrderModal = () => {
    if (!suggestionsSummary) return;
    const selectedItems = suggestionsSummary.items.filter(it =>
      selectedSuggestionProductIds.includes(it.product_id)
    );

    if (selectedItems.length === 0) {
      alert("Selecione ao menos um produto da sugestão de reposição para emitir o pedido.");
      return;
    }

    setQuickOrderSupplierId(suppliers[0]?.id || '');
    setQuickOrderCostCenterId(costCenters[0]?.id || '');
    setQuickOrderPaymentTerms(suppliers[0]?.payment_terms || '30 DDL');
    setQuickOrderFreightType('CIF');
    setQuickOrderFreightAmount('0');
    setQuickOrderDiscountAmount('0');
    setQuickOrderDeliveryDate('');
    setQuickOrderNotes('Reposição ágil de estoque de giro (Assistente de Compras)');

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
    if (!quickOrderSupplierId) {
      setModalError("Selecione o fornecedor para onde a ordem será emitida.");
      return;
    }
    if (quickOrderItems.length === 0) {
      setModalError("A ordem precisa conter pelo menos um item.");
      return;
    }

    try {
      setIsSaving(true);
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

      await loadAllPurchasingData();
      setIsQuickOrderModalOpen(false);
      setSelectedSuggestionProductIds([]);
      setActiveMenu('ordens');
    } catch (err: any) {
      setModalError(formatApiError(err, "Erro ao emitir ordem de compra direta."));
    } finally {
      setIsSaving(false);
    }
  };



  // Formatação de Moeda
  const formatCurrency = (val: number | string | undefined) => {
    const num = typeof val === 'string' ? parseFloat(val) : (val || 0);
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(num);
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
              <button className="btn-refresh" onClick={loadAllPurchasingData} title="Recarregar Dados">
                <RefreshCw size={15} className={loading ? 'spinning' : ''} />
              </button>

              {activeMenu === 'sugestoes' && (
                <button
                  className="btn-primary highlight-btn"
                  onClick={handleOpenQuickOrderModal}
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

          {/* Barra de Pesquisa */}
          <div className="search-toolbar">
            <div className="search-box">
              <Search className="search-icon" size={16} />
              <input
                type="text"
                placeholder="Pesquisar por código, descrição ou fornecedor..."
                value={searchTerm}
                onChange={e => setSearchTerm(e.target.value)}
              />
            </div>
            <div className="results-count">
              {activeMenu === 'solicitacoes' && `${requests.length} solicitações`}
              {activeMenu === 'cotacoes' && `${quotations.length} processos de cotação`}
              {activeMenu === 'ordens' && `${orders.length} ordens de compra`}
              {activeMenu === 'fornecedores' && `${suppliers.length} fornecedores`}
              {activeMenu === 'produtos' && `${products.length} produtos`}
              {activeMenu === 'centros-custo' && `${costCenters.length} centros de custo`}
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
                      onClick={() => handleSelectAllSuggestions(selectedSuggestionProductIds.length !== (suggestionsSummary?.items.length || 0))}
                    >
                      {selectedSuggestionProductIds.length === (suggestionsSummary?.items.length || 0) && (suggestionsSummary?.items.length || 0) > 0 ? (
                        <><CheckSquare size={15} /> <span>Desmarcar Todos</span></>
                      ) : (
                        <><Square size={15} /> <span>Selecionar Todos ({suggestionsSummary?.items.length || 0})</span></>
                      )}
                    </button>

                    <button
                      type="button"
                      className="btn-select-preset critical"
                      onClick={handleSelectCriticalOnly}
                    >
                      <AlertTriangle size={14} />
                      <span>Marcar Somente Críticos</span>
                    </button>
                  </div>

                  <button
                    type="button"
                    className="btn-emit-quick-order"
                    onClick={handleOpenQuickOrderModal}
                    disabled={selectedSuggestionProductIds.length === 0}
                  >
                    <Zap size={16} />
                    <span>⚡ Gerar Pedido com Itens Selecionados ({selectedSuggestionProductIds.length})</span>
                  </button>
                </div>

                {/* Tabela de Sugestões de Reposição */}
                <div className="table-responsive">
                  <table className="enterprise-table">
                    <thead>
                      <tr>
                        <th style={{ width: '40px' }}>
                          <input
                            type="checkbox"
                            checked={Boolean(suggestionsSummary?.items.length && selectedSuggestionProductIds.length === suggestionsSummary.items.length)}
                            onChange={e => handleSelectAllSuggestions(e.target.checked)}
                          />
                        </th>
                        <th>Produto / SKU</th>
                        <th>Categoria / Marca</th>
                        <th>Urgência</th>
                        <th>Estoque Físico (Atual / Mín / Alvo)</th>
                        <th>Qtd. Sugerida (Editável)</th>
                        <th>Preço Unit. Ref.</th>
                        <th>Subtotal Estimado</th>
                        <th style={{ textAlign: 'right' }}>Ações</th>
                      </tr>
                    </thead>
                    <tbody>
                      {!suggestionsSummary || suggestionsSummary.items.length === 0 ? (
                        <tr>
                          <td colSpan={9} className="state-empty success-state">
                            <CheckCircle2 size={28} style={{ color: '#10b981', marginBottom: '0.5rem', display: 'inline-block' }} />
                            <div><strong>Estoque 100% Regularizado!</strong></div>
                            <small>Nenhum produto está abaixo do ponto de ressuprimento no momento.</small>
                          </td>
                        </tr>
                      ) : (
                        suggestionsSummary.items.map(item => {
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
                                  <div className={`icon-badge ${item.urgency_level === 'critical' ? 'red-bg' : 'brand-bg'}`}>
                                    <Package size={15} />
                                  </div>
                                  <div>
                                    <strong>{item.product_name}</strong>
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
                                {item.urgency_level === 'high' && <span className="urgency-pill high">🟠 Alto (≤ 50% mín)</span>}
                                {item.urgency_level === 'medium' && <span className="urgency-pill medium">🟡 Ponto de Pedido</span>}
                              </td>
                              <td>
                                <div className="stock-balance-cell">
                                  <span className={`stock-now ${Number(item.current_stock) <= 0 ? 'zero' : ''}`}>
                                    Atual: <strong>{Number(item.current_stock)} {item.unit_of_measure}</strong>
                                  </span>
                                  <span className="stock-limits">
                                    Mín: {Number(item.min_stock)} | Alvo: {Number(item.max_stock || Number(item.min_stock) * 2)}
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
                </div>
              </div>
            )}

            {/* 1. SOLICITAÇÕES DE COMPRA */}
            {activeMenu === 'solicitacoes' && (
              <div className="table-responsive">
                <table className="enterprise-table">
                  <thead>
                    <tr>
                      <th>Número</th>
                      <th>Justificativa</th>
                      <th>Valor Estimado</th>
                      <th>Status</th>
                      <th>Data Limite</th>
                      <th style={{ textAlign: 'right' }}>Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {requests.length === 0 ? (
                      <tr><td colSpan={6} className="state-empty">Nenhuma solicitação de compra cadastrada.</td></tr>
                    ) : (
                      requests.map(req => (
                        <tr key={req.id}>
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
                              {(req.status === 'draft' || req.status === 'pending_approval') && (
                                <button
                                  className="btn-action-icon edit"
                                  title="Editar Solicitação"
                                  onClick={() => handleEditRequest(req)}
                                >
                                  <Edit size={14} />
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
              </div>
            )}

            {/* 2. COTAÇÕES (RFQ) & MAPA COMPARATIVO */}
            {activeMenu === 'cotacoes' && (
              <div className="table-responsive">
                <table className="enterprise-table">
                  <thead>
                    <tr>
                      <th>Cotação</th>
                      <th>Solicitação de Origem</th>
                      <th>Propostas Recebidas</th>
                      <th>Status</th>
                      <th>Data de Abertura</th>
                      <th style={{ textAlign: 'right' }}>Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {quotations.length === 0 ? (
                      <tr><td colSpan={6} className="state-empty">Nenhum processo de cotação aberto no momento.</td></tr>
                    ) : (
                      quotations.map(quot => (
                        <tr key={quot.id}>
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
                            <span className="code-tag">{quot.purchase_request?.request_number || '-'}</span>
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
              </div>
            )}

            {/* 3. ORDENS DE COMPRA (PO) */}
            {activeMenu === 'ordens' && (
              <div className="table-responsive">
                <table className="enterprise-table">
                  <thead>
                    <tr>
                      <th>Ordem de Compra</th>
                      <th>Fornecedor</th>
                      <th>Origem (SC)</th>
                      <th>Total Líquido</th>
                      <th>Status</th>
                      <th>Entrega / NF</th>
                      <th style={{ textAlign: 'right' }}>Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {orders.length === 0 ? (
                      <tr><td colSpan={7} className="state-empty">Nenhuma ordem de compra emitida.</td></tr>
                    ) : (
                      orders.map(ord => (
                        <tr key={ord.id}>
                          <td>
                            <div className="cell-with-icon">
                              <div className="icon-badge blue-bg"><Truck size={15} /></div>
                              <div>
                                <strong>{ord.order_number}</strong>
                                <span className="sub-label">{new Date(ord.created_at).toLocaleDateString('pt-BR')}</span>
                              </div>
                            </div>
                          </td>
                          <td>
                            <strong>{ord.supplier?.name || '-'}</strong>
                            <span className="sub-label">{ord.supplier?.cnpj_cpf || ''}</span>
                          </td>
                          <td>
                            <span className="code-tag">{ord.purchase_request?.request_number || 'Direta'}</span>
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
                            <div className="row-actions">
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
              </div>
            )}

            {/* 4. FORNECEDORES HOMOLOGADOS */}
            {activeMenu === 'fornecedores' && (
              <div className="table-responsive">
                <table className="enterprise-table">
                  <thead>
                    <tr>
                      <th>Fornecedor / Razão Social</th>
                      <th>CNPJ / IE</th>
                      <th>Linhas / Segmentos Atendidos</th>
                      <th>Condição Comercial</th>
                      <th>Representante / Contato</th>
                      <th>Localização</th>
                      <th style={{ textAlign: 'right' }}>Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {suppliers.length === 0 ? (
                      <tr><td colSpan={7} className="state-empty">Nenhum fornecedor cadastrado. Clique em "+ Novo Fornecedor" para cadastrar.</td></tr>
                    ) : (
                      suppliers.map(sup => {
                        const segmentList = sup.segments ? sup.segments.split(',').map(s => s.trim()).filter(Boolean) : [];

                        return (
                          <tr key={sup.id}>
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
                                  className="btn-action-icon edit"
                                  title="Editar Fornecedor"
                                  onClick={() => handleEditSupplier(sup)}
                                >
                                  <Edit size={14} />
                                </button>
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
              </div>
            )}

            {/* 5. PRODUTOS & INSUMOS */}
            {activeMenu === 'produtos' && (
              <div className="table-responsive">
                <table className="enterprise-table">
                  <thead>
                    <tr>
                      <th>SKU / Produto</th>
                      <th>Categoria</th>
                      <th>Marca / Fabricante</th>
                      <th>Unidade</th>
                      <th>Estoque Físico (Atual / Mín)</th>
                      <th>Preço Referência</th>
                      <th>Rastreabilidade & Validade</th>
                      <th style={{ textAlign: 'right' }}>Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {products.length === 0 ? (
                      <tr><td colSpan={8} className="state-empty">Nenhum produto cadastrado. Clique em "+ Novo Produto" para adicionar.</td></tr>
                    ) : (
                      products.map(prod => (
                        <tr key={prod.id}>
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
                                <strong>{Number(prod.current_stock || 0)} {prod.unit_of_measure}</strong>
                              </span>
                              <span className="stock-limits">Mín: {Number(prod.min_stock || 0)}</span>
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
                                className="btn-action-icon edit"
                                title="Editar Produto / Insumo"
                                onClick={() => handleEditProduct(prod)}
                              >
                                <Edit size={14} />
                              </button>
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
              </div>
            )}

            {/* 6. CATEGORIAS DE PRODUTOS */}
            {activeMenu === 'categorias' && (
              <div className="table-responsive">
                <table className="enterprise-table">
                  <thead>
                    <tr>
                      <th>Código / Prefixo SKU</th>
                      <th>Nome da Categoria</th>
                      <th>Descrição</th>
                      <th>Produtos Vinculados</th>
                      <th>Status</th>
                      <th style={{ textAlign: 'right' }}>Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {categories.length === 0 ? (
                      <tr><td colSpan={6} className="state-empty">Nenhuma categoria cadastrada. Clique em "+ Nova Categoria" para criar a primeira.</td></tr>
                    ) : (
                      categories.map(cat => {
                        const linkedCount = products.filter(p => p.category_id === cat.id).length;

                        return (
                          <tr key={cat.id}>
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
                                  className="btn-action-icon edit"
                                  title="Editar Categoria"
                                  onClick={() => handleEditCategory(cat)}
                                >
                                  <Edit size={14} />
                                </button>
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
              </div>
            )}

            {/* 6. CENTROS DE CUSTO */}
            {activeMenu === 'centros-custo' && (
              <div className="table-responsive">
                <table className="enterprise-table">
                  <thead>
                    <tr>
                      <th>Código</th>
                      <th>Nome</th>
                      <th>Descrição</th>
                      <th>Status</th>
                      <th style={{ textAlign: 'right' }}>Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {costCenters.length === 0 ? (
                      <tr><td colSpan={5} className="state-empty">Nenhum centro de custo cadastrado.</td></tr>
                    ) : (
                      costCenters.map(cc => (
                        <tr key={cc.id}>
                          <td><span className="code-tag">{cc.code}</span></td>
                          <td><strong>{cc.name}</strong></td>
                          <td>{cc.description || '-'}</td>
                          <td><span className="badge-pill active">Ativo</span></td>
                          <td style={{ textAlign: 'right' }}>
                            <div className="row-actions">
                              <button
                                className="btn-action-icon edit"
                                title="Editar Centro de Custo"
                                onClick={() => handleEditCostCenter(cc)}
                              >
                                <Edit size={14} />
                              </button>
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
              </div>
            )}

            {/* 7. EXTRATO DE MOVIMENTAÇÕES DE ESTOQUE */}
            {activeMenu === 'movimentacoes' && (
              <div className="table-responsive">
                <table className="enterprise-table">
                  <thead>
                    <tr>
                      <th>Data / Horário</th>
                      <th>Produto / Insumo</th>
                      <th>Tipo de Movimentação</th>
                      <th>Quantidade Movimentada</th>
                      <th>Custo Unitário</th>
                      <th>Saldo Resultante</th>
                      <th>Documento / Referência</th>
                      <th>Observações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stockMovements.length === 0 ? (
                      <tr><td colSpan={8} className="state-empty">Nenhuma movimentação de estoque registrada. Ao receber ordens de compra ou realizar ajustes, o histórico aparecerá aqui.</td></tr>
                    ) : (
                      stockMovements.map(mov => {
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
                                  <strong>{mov.product_name || mov.product?.name || 'Produto'}</strong>
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
                                {isPositive ? '+' : '-'}{Number(mov.quantity)} {mov.product?.unit_of_measure || 'UN'}
                              </strong>
                            </td>
                            <td>{formatCurrency(mov.unit_cost)}</td>
                            <td>
                              <span className="balance-tag">
                                {Number(mov.balance_after)} {mov.product?.unit_of_measure || 'UN'}
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
                        {productCurrentStock || 0} {productUnit}
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
          size="md"
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

            <div className="form-group">
              <label>Número da Nota Fiscal / DANFE *</label>
              <input
                type="text"
                value={receiveInvoiceNumber}
                onChange={e => setReceiveInvoiceNumber(e.target.value)}
                placeholder="Ex: NF-e 001.284.912"
                required
              />
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
            selectedSuggestionProductIds.length > 0
              ? "⚡ Emissão Ágil de Ordem de Compra • Reposição de Estoque"
              : "📄 Emissão Direta de Ordem de Compra Oficial (PO)"
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

            <div className="form-section-divider">
              <Package size={14} />
              <span>2. Itens do Pedido ({quickOrderItems.length} produtos selecionados)</span>
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
                        alert('Este produto já está na lista da ordem.');
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
              <div className="summary-line">
                <span>Frete (+):</span>
                <span>{formatCurrency(parseFloat(quickOrderFreightAmount) || 0)}</span>
              </div>
              <div className="summary-line">
                <span>Desconto (-):</span>
                <span>{formatCurrency(parseFloat(quickOrderDiscountAmount) || 0)}</span>
              </div>
              <div className="summary-line total-net">
                <span>Total Líquido da Ordem:</span>
                <span className="final-value">
                  {formatCurrency(
                    Math.max(
                      0,
                      quickOrderItems.reduce((acc, it) => acc + (it.quantity * it.unit_price), 0) +
                      (parseFloat(quickOrderFreightAmount) || 0) -
                      (parseFloat(quickOrderDiscountAmount) || 0)
                    )
                  )}
                </span>
              </div>
            </div>

            <div className="form-group">
              <label>Observações / Instruções de Entrega</label>
              <textarea
                value={quickOrderNotes}
                onChange={e => setQuickOrderNotes(e.target.value)}
                placeholder="Ex: Entregar em horário comercial no almoxarifado central..."
                rows={2}
              />
            </div>

            <div className="modal-actions">
              <button type="button" className="btn-cancel" onClick={() => setIsQuickOrderModalOpen(false)}>Cancelar</button>
              <button type="submit" className="btn-save" disabled={isSaving || quickOrderItems.length === 0}>
                {isSaving ? <Loader2 size={16} className="spinning" /> : <Zap size={16} />}
                <span>Emitir Ordem de Compra Oficial (PO)</span>
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


