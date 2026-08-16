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
  Loader2, AlertCircle, Trash2, ShieldCheck, Box, Check, BarChart2, Award, Edit
} from 'lucide-react';
import { purchasingService } from '@/services/api';
import { 
  Supplier, Product, ProductCategory, CostCenter, 
  PurchaseRequest, PurchaseOrder, QuotationProcess,
  QuotationComparisonMatrix, SupplierQuotePayload
} from '@/types';
import { Navbar } from '@/components/Navbar';
import { Modal } from '@/components/Modal/Modal';
import './Purchasing.scss';

type PurchasingMenuOption = 'solicitacoes' | 'cotacoes' | 'ordens' | 'fornecedores' | 'produtos' | 'centros-custo';

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

  // Estados de Carregamento e Erro
  const [loading, setLoading] = useState(true);

  // Modais de Criação & Edição
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // Estados para Edição
  const [editingSupplier, setEditingSupplier] = useState<Supplier | null>(null);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [editingCostCenter, setEditingCostCenter] = useState<CostCenter | null>(null);
  const [editingRequest, setEditingRequest] = useState<PurchaseRequest | null>(null);

  // Campos de Fornecedor
  const [supplierName, setSupplierName] = useState('');
  const [supplierTradeName, setSupplierTradeName] = useState('');
  const [supplierCnpj, setSupplierCnpj] = useState('');
  const [supplierEmail, setSupplierEmail] = useState('');
  const [supplierPhone, setSupplierPhone] = useState('');
  const [supplierCity, setSupplierCity] = useState('');
  const [supplierState, setSupplierState] = useState('');

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
      const [reqData, quotData, poData, supData, prodData, catData, ccData] = await Promise.all([
        purchasingService.getPurchaseRequests(),
        purchasingService.getQuotationProcesses(),
        purchasingService.getPurchaseOrders(),
        purchasingService.getSuppliers(),
        purchasingService.getProducts(),
        purchasingService.getCategories(),
        purchasingService.getCostCenters()
      ]);

      setRequests(reqData);
      setQuotations(quotData);
      setOrders(poData);
      setSuppliers(supData);
      setProducts(prodData);
      setCategories(catData);
      setCostCenters(ccData);
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
      setModalError(err?.response?.data?.detail || "Erro ao salvar proposta do fornecedor.");
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
      alert(err?.response?.data?.detail || "Erro ao gerar mapa comparativo.");
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

  const handleDeleteSupplierQuote = async (quotationId: string, quoteId: string) => {
    if (!confirm("Deseja realmente excluir esta proposta de fornecedor?")) return;
    try {
      setIsSaving(true);
      await purchasingService.deleteSupplierQuote(quotationId, quoteId);
      await loadAllPurchasingData();
      // Recarrega matriz do modal
      const matrix = await purchasingService.getQuotationComparison(quotationId);
      setComparisonMatrix(matrix);
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Erro ao remover proposta comercial.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancelOrder = async (orderId: string) => {
    if (!confirm("Deseja realmente cancelar esta Ordem de Compra oficial?")) return;
    try {
      setIsSaving(true);
      await purchasingService.cancelPurchaseOrder(orderId);
      await loadAllPurchasingData();
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Erro ao cancelar ordem de compra.");
    } finally {
      setIsSaving(false);
    }
  };

  // =========================================================================
  // GESTÃO DE CADASTROS (EDIÇÃO E EXCLUSÃO)
  // =========================================================================
  const handleEditSupplier = (sup: Supplier) => {
    setEditingSupplier(sup);
    setSupplierName(sup.name);
    setSupplierTradeName(sup.trade_name || '');
    setSupplierCnpj(sup.cnpj_cpf || '');
    setSupplierEmail(sup.email || '');
    setSupplierPhone(sup.phone || '');
    setSupplierCity(sup.city || '');
    setSupplierState(sup.state || '');
    setModalError(null);
    setIsModalOpen(true);
  };

  const handleDeleteSupplier = async (sup: Supplier) => {
    if (!confirm(`Deseja realmente excluir o fornecedor "${sup.name}"?`)) return;
    try {
      setIsSaving(true);
      await purchasingService.deleteSupplier(sup.id);
      await loadAllPurchasingData();
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Erro ao excluir fornecedor. Verifique se ele possui cotações ou ordens vinculadas.");
    } finally {
      setIsSaving(false);
    }
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
    setProductMinStock(String(prod.min_stock || 0));
    setProductMaxStock(prod.max_stock ? String(prod.max_stock) : '');
    setProductStorageLocation(prod.storage_location || '');
    setModalError(null);
    setIsModalOpen(true);
  };

  const handleDeleteProduct = async (prod: Product) => {
    if (!confirm(`Deseja realmente excluir o produto "${prod.name}" (${prod.sku})?`)) return;
    try {
      setIsSaving(true);
      await purchasingService.deleteProduct(prod.id);
      await loadAllPurchasingData();
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Erro ao excluir produto. Verifique se ele está presente em solicitações ou cotações.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleEditCostCenter = (cc: CostCenter) => {
    setEditingCostCenter(cc);
    setCostCenterCode(cc.code);
    setCostCenterName(cc.name);
    setCostCenterDesc(cc.description || '');
    setModalError(null);
    setIsModalOpen(true);
  };

  const handleDeleteCostCenter = async (cc: CostCenter) => {
    if (!confirm(`Deseja realmente excluir o centro de custo "${cc.name}" (${cc.code})?`)) return;
    try {
      setIsSaving(true);
      await purchasingService.deleteCostCenter(cc.id);
      await loadAllPurchasingData();
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Erro ao excluir centro de custo.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleEditRequest = (req: PurchaseRequest) => {
    setEditingRequest(req);
    setRequestJustification(req.justification);
    setRequestCostCenterId(req.cost_center_id || '');
    setRequestRequiredDate(req.required_date ? req.required_date.substring(0, 10) : '');
    setModalError(null);
    setIsModalOpen(true);
  };

  const handleDeleteRequest = async (req: PurchaseRequest) => {
    if (!confirm(`Deseja realmente excluir a solicitação ${req.request_number}?`)) return;
    try {
      setIsSaving(true);
      await purchasingService.deletePurchaseRequest(req.id);
      await loadAllPurchasingData();
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Erro ao excluir solicitação. Se estiver aprovada ou com cotações, utilize o cancelamento.");
    } finally {
      setIsSaving(false);
    }
  };

  // =========================================================================
  // GESTÃO DE SOLICITAÇÃO DE COMPRA (CRIAÇÃO)
  // =========================================================================
  const handleOpenCreateModal = () => {
    setEditingSupplier(null);
    setEditingProduct(null);
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
      setSupplierEmail('');
      setSupplierPhone('');
      setSupplierCity('');
      setSupplierState('');
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
            justification: requestJustification,
            cost_center_id: requestCostCenterId || undefined,
            required_date: requestRequiredDate ? new Date(requestRequiredDate).toISOString() : undefined,
            items: requestItems.map(it => ({
              product_id: it.product_id,
              quantity: it.quantity,
              estimated_unit_price: it.estimated_unit_price,
              notes: it.notes
            }))
          });
        }
      } else if (activeMenu === 'fornecedores') {
        if (!supplierName.trim()) {
          setModalError("A Razão Social do fornecedor é obrigatória.");
          setIsSaving(false);
          return;
        }
        if (editingSupplier) {
          await purchasingService.updateSupplier(editingSupplier.id, {
            name: supplierName,
            trade_name: supplierTradeName || undefined,
            cnpj_cpf: supplierCnpj || '00.000.000/0000-00',
            email: supplierEmail || undefined,
            phone: supplierPhone || undefined,
            city: supplierCity || undefined,
            state: supplierState || undefined
          });
        } else {
          await purchasingService.createSupplier({
            name: supplierName,
            trade_name: supplierTradeName || undefined,
            cnpj_cpf: supplierCnpj || '00.000.000/0000-00',
            email: supplierEmail || undefined,
            phone: supplierPhone || undefined,
            city: supplierCity || undefined,
            state: supplierState || undefined
          });
        }
      } else if (activeMenu === 'produtos') {
        if (!productName.trim()) {
          setModalError("O nome do produto é obrigatório.");
          setIsSaving(false);
          return;
        }
        if (editingProduct) {
          await purchasingService.updateProduct(editingProduct.id, {
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
            min_stock: parseFloat(productMinStock) || 0,
            max_stock: productMaxStock ? parseFloat(productMaxStock) : null,
            storage_location: productStorageLocation || undefined
          });
        } else {
          await purchasingService.createProduct({
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
      setEditingCostCenter(null);
      setEditingRequest(null);
    } catch (err: any) {
      setModalError(err?.response?.data?.detail || "Erro ao salvar registro.");
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
      setModalError(err?.response?.data?.detail || "Erro ao processar aprovação.");
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
    setReceiveNotes('');
    setModalError(null);
    setIsReceiveModalOpen(true);
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
        notes: receiveNotes.trim() || undefined
      });
      await loadAllPurchasingData();
      setIsReceiveModalOpen(false);
    } catch (err: any) {
      setModalError(err?.response?.data?.detail || "Erro ao registrar recebimento.");
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
      <Navbar />

      <div className="purchasing-layout">
        {/* 1. SIDEBAR LATERAL ESQUERDA */}
        <aside className="sidebar-left">
          <div className="sidebar-header">
            <ShoppingCart className="brand-icon" size={20} />
            <div className="sidebar-title-wrap">
              <span className="sidebar-title">Módulo de Compras</span>
              <span className="sidebar-subtitle">Procure-to-Pay</span>
            </div>
          </div>

          <nav className="nav-menu">
            <span className="menu-group-label">Fluxo Operacional</span>

            <button 
              className={`nav-item ${activeMenu === 'solicitacoes' ? 'active' : ''}`}
              onClick={() => setActiveMenu('solicitacoes')}
            >
              <div className="nav-item-content">
                <FileText size={16} />
                <span>Solicitações de Compra</span>
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

            <span className="menu-group-label">Cadastros Estratégicos</span>

            <button 
              className={`nav-item ${activeMenu === 'fornecedores' ? 'active' : ''}`}
              onClick={() => setActiveMenu('fornecedores')}
            >
              <div className="nav-item-content">
                <Truck size={16} />
                <span>Fornecedores</span>
              </div>
              <span className="nav-badge">{suppliers.length}</span>
            </button>

            <button 
              className={`nav-item ${activeMenu === 'produtos' ? 'active' : ''}`}
              onClick={() => setActiveMenu('produtos')}
            >
              <div className="nav-item-content">
                <Package size={16} />
                <span>Produtos & Insumos</span>
              </div>
              <span className="nav-badge">{products.length}</span>
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
                  {activeMenu === 'solicitacoes' && 'Solicitações de Compra'}
                  {activeMenu === 'cotacoes' && 'Processos de Cotação (RFQ)'}
                  {activeMenu === 'ordens' && 'Ordens de Compra (PO)'}
                  {activeMenu === 'fornecedores' && 'Fornecedores Homologados'}
                  {activeMenu === 'produtos' && 'Catálogo de Produtos & Insumos'}
                  {activeMenu === 'centros-custo' && 'Centros de Custo'}
                </span>
              </div>
              <h1 className="section-title">
                {activeMenu === 'solicitacoes' && 'Solicitações de Compra'}
                {activeMenu === 'cotacoes' && 'Processos de Cotação de Mercado (RFQ)'}
                {activeMenu === 'ordens' && 'Ordens de Compra Oficiais (Purchase Orders)'}
                {activeMenu === 'fornecedores' && 'Fornecedores Homologados'}
                {activeMenu === 'produtos' && 'Produtos, Medicamentos & Insumos'}
                {activeMenu === 'centros-custo' && 'Centros de Custo e Orçamentos'}
              </h1>
            </div>

            <div className="header-actions">
              <button className="btn-refresh" onClick={loadAllPurchasingData} title="Recarregar Dados">
                <RefreshCw size={15} className={loading ? 'spinning' : ''} />
              </button>

              {activeMenu !== 'ordens' && activeMenu !== 'cotacoes' && (
                <button className="btn-primary" onClick={handleOpenCreateModal}>
                  <Plus size={16} />
                  <span>
                    {activeMenu === 'solicitacoes' && 'Nova Solicitação'}
                    {activeMenu === 'fornecedores' && 'Novo Fornecedor'}
                    {activeMenu === 'produtos' && 'Novo Produto'}
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
                                <>
                                  <button 
                                    className="btn-action-icon edit" 
                                    title="Editar Solicitação"
                                    onClick={() => handleEditRequest(req)}
                                  >
                                    <Edit size={14} />
                                  </button>
                                  <button 
                                    className="btn-action-icon delete" 
                                    title="Excluir Solicitação"
                                    onClick={() => handleDeleteRequest(req)}
                                  >
                                    <Trash2 size={14} />
                                  </button>
                                </>
                              )}
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
                              <span className="code-tag">NF: {ord.invoice_number}</span>
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
                                    onClick={() => handleCancelOrder(ord.id)}
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
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {/* 4. FORNECEDORES */}
            {activeMenu === 'fornecedores' && (
              <div className="table-responsive">
                <table className="enterprise-table">
                  <thead>
                    <tr>
                      <th>Razão Social</th>
                      <th>CNPJ / CPF</th>
                      <th>Contato</th>
                      <th>Localização</th>
                      <th>Status</th>
                      <th style={{ textAlign: 'right' }}>Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {suppliers.length === 0 ? (
                      <tr><td colSpan={6} className="state-empty">Nenhum fornecedor cadastrado.</td></tr>
                    ) : (
                      suppliers.map(sup => (
                        <tr key={sup.id}>
                          <td>
                            <div className="cell-with-icon">
                              <div className="icon-badge orange-bg"><Truck size={15} /></div>
                              <div>
                                <strong>{sup.name}</strong>
                                {sup.trade_name && <span className="sub-label">{sup.trade_name}</span>}
                              </div>
                            </div>
                          </td>
                          <td><span className="code-tag">{sup.cnpj_cpf || '-'}</span></td>
                          <td>
                            <div className="contact-cell">
                              {sup.email && <span><Mail size={12} /> {sup.email}</span>}
                              {sup.phone && <span><Phone size={12} /> {sup.phone}</span>}
                            </div>
                          </td>
                          <td>{sup.city && sup.state ? `${sup.city} / ${sup.state}` : '-'}</td>
                          <td><span className={`badge-pill ${sup.is_active ? 'active' : 'inactive'}`}>{sup.is_active ? 'Homologado' : 'Inativo'}</span></td>
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
                      ))
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
                      <th>Unidade</th>
                      <th>Preço Referência</th>
                      <th>Rastreabilidade & Validade</th>
                      <th style={{ textAlign: 'right' }}>Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {products.length === 0 ? (
                      <tr><td colSpan={6} className="state-empty">Nenhum produto cadastrado.</td></tr>
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
                          <td>{prod.category?.name || '-'}</td>
                          <td><span className="unit-badge">{prod.unit_of_measure}</span></td>
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
                  className="btn-cancel" 
                  onClick={() => setIsComparisonModalOpen(false)}
                >
                  Fechar Mapa
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
            setEditingCostCenter(null);
            setEditingRequest(null);
          }}
          title={
            activeMenu === 'solicitacoes' ? (editingRequest ? 'Editar Solicitação de Compra' : 'Nova Solicitação de Compra') :
            activeMenu === 'fornecedores' ? (editingSupplier ? 'Editar Fornecedor Homologado' : 'Novo Fornecedor Homologado') :
            activeMenu === 'produtos' ? (editingProduct ? 'Editar Produto / Insumo' : 'Novo Produto / Insumo') : 
            (editingCostCenter ? 'Editar Centro de Custo' : 'Novo Centro de Custo')
          }
          size={activeMenu === 'solicitacoes' || activeMenu === 'produtos' ? 'lg' : 'md'}
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
                <div className="form-group">
                  <label>Razão Social *</label>
                  <input type="text" value={supplierName} onChange={e => setSupplierName(e.target.value)} required />
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label>Nome Fantasia</label>
                    <input type="text" value={supplierTradeName} onChange={e => setSupplierTradeName(e.target.value)} />
                  </div>
                  <div className="form-group">
                    <label>CNPJ / CPF</label>
                    <input type="text" value={supplierCnpj} onChange={e => setSupplierCnpj(e.target.value)} />
                  </div>
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label>E-mail Corporativo</label>
                    <input type="email" value={supplierEmail} onChange={e => setSupplierEmail(e.target.value)} />
                  </div>
                  <div className="form-group">
                    <label>Telefone</label>
                    <input type="text" value={supplierPhone} onChange={e => setSupplierPhone(e.target.value)} />
                  </div>
                </div>
              </>
            )}

            {/* Formulário de Produto */}
            {activeMenu === 'produtos' && (
              <>
                <div className="form-row">
                  <div className="form-group" style={{ flex: 2 }}>
                    <label>Nome do Produto / Medicamento *</label>
                    <input 
                      type="text" 
                      value={productName} 
                      onChange={e => {
                        setProductName(e.target.value);
                        setProductSku(generateAutomaticSku(e.target.value, productCategoryId, productIsPerishable));
                      }} 
                      required 
                    />
                  </div>
                  <div className="form-group" style={{ flex: 1 }}>
                    <label>SKU Automático *</label>
                    <input type="text" value={productSku} onChange={e => setProductSku(e.target.value)} required />
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>Categoria</label>
                    <select 
                      value={productCategoryId} 
                      onChange={e => {
                        setProductCategoryId(e.target.value);
                        setProductSku(generateAutomaticSku(productName, e.target.value, productIsPerishable));
                      }}
                    >
                      <option value="">Sem Categoria</option>
                      {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label>Unidade de Medida</label>
                    <select value={productUnit} onChange={e => setProductUnit(e.target.value)}>
                      <option value="UN">Unidade (UN)</option>
                      <option value="CX">Caixa (CX)</option>
                      <option value="KG">Quilo (KG)</option>
                      <option value="L">Litro (L)</option>
                      <option value="MT">Metro (MT)</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label>Preço Unitário Ref. (R$)</label>
                    <input type="number" step="0.01" value={productPrice} onChange={e => setProductPrice(e.target.value)} />
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
                      <small>Exige controle de validade</small>
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
                      <small>Exige número de lote na entrada</small>
                    </div>
                  </label>
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
                  setEditingCostCenter(null);
                  setEditingRequest(null);
                }}
              >
                Cancelar
              </button>
              <button type="submit" className="btn-save" disabled={isSaving}>
                {isSaving ? <Loader2 size={16} className="spinning" /> : <Check size={16} />}
                <span>
                  {editingSupplier || editingProduct || editingCostCenter || editingRequest 
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
    </div>
  );
};
