/**
 * pages/Inventory/Inventory.tsx - Módulo de Gestão de Estoque, Catálogo de Produtos e Almoxarifado
 * 
 * Funcionalidades Avançadas:
 * 1. KPI Cards com métricas em tempo real (Total de SKUs, Valor do Estoque, Itens Críticos, Categorias).
 * 2. Catálogo de Produtos com Filtros Inteligentes (Status de Estoque, Categorias, Busca por SKU/Marca).
 * 3. Indicador Visual de Nível de Estoque (Barra de progresso e badges semânticos).
 * 4. Gestão de Categorias e Prefixo de SKU.
 * 5. Extrato de Movimentações (Kardex / Auditoria de Entradas e Baixas).
 * 6. Modal de Ajuste Físico de Inventário (Contagem, Sobra, Avaria e Validade).
 */

import React, { useEffect, useState } from 'react';
import {
  Package, Tags, History, Plus, Search, RefreshCw,
  Edit, Trash2, SlidersHorizontal, AlertTriangle, ArrowDownRight,
  ArrowUpRight, Check, Loader2, Sparkles, DollarSign,
  ChevronRight, CheckCircle2, ShieldCheck, FileText, Paperclip,
  UploadCloud, X, Scale
} from 'lucide-react';

import { inventoryService, formatApiError } from '@/services/api';
import { Product, ProductCategory, StockMovement } from '@/types';
import { Modal } from '@/components/Modal/Modal';
import { ConfirmModal } from '@/components/ConfirmModal/ConfirmModal';
import './Inventory.scss';



type InventoryMenuOption = 'produtos' | 'categorias' | 'movimentacoes' | 'auditoria';
type StockStatusFilter = 'todos' | 'criticos' | 'zerados' | 'regulares';

export const Inventory: React.FC = () => {
  const [activeMenu, setActiveMenu] = useState<InventoryMenuOption>('produtos');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategoryFilter, setSelectedCategoryFilter] = useState<string>('');
  const [stockStatusFilter, setStockStatusFilter] = useState<StockStatusFilter>('todos');

  // Estados dos Dados carregados da API
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<ProductCategory[]>([]);
  const [stockMovements, setStockMovements] = useState<StockMovement[]>([]);
  const [loading, setLoading] = useState(true);

  // Modais de Criação & Edição
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // Estados para Edição
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [editingCategory, setEditingCategory] = useState<ProductCategory | null>(null);

  // Campos de Categoria
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

  // Modal de Ajuste de Estoque / Inventário Físico
  const [isStockAdjustModalOpen, setIsStockAdjustModalOpen] = useState(false);
  const [stockAdjustProduct, setStockAdjustProduct] = useState<Product | null>(null);
  const [stockAdjustType, setStockAdjustType] = useState<'invoice_entry' | 'manual_loss' | 'reconciliation'>('invoice_entry');
  const [stockAdjustQty, setStockAdjustQty] = useState('1');
  const [stockAdjustCost, setStockAdjustCost] = useState('0');
  const [stockAdjustInvoice, setStockAdjustInvoice] = useState('');
  const [stockAdjustAttachment, setStockAdjustAttachment] = useState<string | null>(null);
  const [stockAdjustAttachmentName, setStockAdjustAttachmentName] = useState<string | null>(null);
  const [stockAdjustSupplier, setStockAdjustSupplier] = useState('');
  const [stockAdjustBatch, setStockAdjustBatch] = useState('');
  const [stockAdjustExpiry, setStockAdjustExpiry] = useState('');
  const [stockAdjustReason, setStockAdjustReason] = useState('Entrada por Nota Fiscal');
  const [stockAdjustNotes, setStockAdjustNotes] = useState('');
  const [stockAdjustAuditor, setStockAdjustAuditor] = useState('');


  // Carregamento Inicial
  useEffect(() => {
    loadInventoryData();
  }, []);

  const loadInventoryData = async () => {
    setLoading(true);
    try {
      const [prodData, catData, movData] = await Promise.all([
        inventoryService.getProducts(),
        inventoryService.getCategories(),
        inventoryService.getInventoryMovements()
      ]);

      setProducts(Array.isArray(prodData) ? prodData : []);
      setCategories(Array.isArray(catData) ? catData : []);
      setStockMovements(Array.isArray(movData) ? movData : []);
    } catch (err: any) {
      console.error("Erro ao carregar dados do módulo de estoque:", err);
    } finally {
      setLoading(false);
    }
  };

  // Geração Automática Inteligente de SKU
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

  // Ações de Categorias
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
      subtitle: 'Esta ação removerá a categoria do catálogo de produtos.',
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
          await loadInventoryData();
          closeConfirmModal();
        } catch (err: any) {
          setConfirmModal(prev => ({
            ...prev,
            isLoading: false,
            errorMessage: err?.response?.data?.detail || 'Erro ao excluir categoria. Verifique se há produtos vinculados.'
          }));
        }
      }
    });
  };

  // Ações de Produtos
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
            <strong>Atenção:</strong> Se o produto constar em Ordens de Compra, Cotações ou Solicitações, a exclusão será bloqueada para manter o histórico.
          </div>
        </>
      ),
      confirmText: 'Excluir Produto',
      onConfirm: async () => {
        setConfirmModal(prev => ({ ...prev, isLoading: true, errorMessage: null }));
        try {
          await inventoryService.deleteProduct(prod.id);
          await loadInventoryData();
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


  // Modal de Criação
  const handleOpenCreateModal = () => {
    setEditingProduct(null);
    setEditingCategory(null);
    setModalError(null);

    if (activeMenu === 'categorias') {
      setCategoryName('');
      setCategoryCode('');
      setCategoryDesc('');
    } else if (activeMenu === 'produtos') {
      setProductName('');
      setProductSku('');
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
      setProductMinStock('10');
      setProductMaxStock('50');
      setProductStorageLocation('');
    }
    setIsModalOpen(true);
  };

  // Salvar Produto ou Categoria
  const handleSaveModal = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setModalError(null);

    try {
      if (activeMenu === 'categorias') {
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
      }

      await loadInventoryData();
      setIsModalOpen(false);
      setEditingProduct(null);
      setEditingCategory(null);
    } catch (err: any) {
      setModalError(formatApiError(err, "Erro ao salvar dados."));
    } finally {
      setIsSaving(false);
    }
  };

  // Movimentação & Auditoria de Estoque
  const handleOpenStockAdjustModal = (
    prod: Product, 
    type: 'invoice_entry' | 'manual_loss' | 'reconciliation' = 'invoice_entry'
  ) => {
    setStockAdjustProduct(prod);
    setStockAdjustType(type);
    setStockAdjustCost((prod.reference_price || 0).toString());
    setStockAdjustInvoice('');
    setStockAdjustAttachment(null);
    setStockAdjustAttachmentName(null);
    setStockAdjustSupplier('');
    setStockAdjustBatch('');
    setStockAdjustExpiry('');
    setStockAdjustReason(
      type === 'invoice_entry' ? 'Entrada por Nota Fiscal' :
      type === 'manual_loss' ? 'Avaria / Quebra de Produto' : 'Contagem Cíclica de Inventário'
    );
    setStockAdjustNotes('');
    setStockAdjustAuditor('');
    setModalError(null);

    if (type === 'reconciliation') {
      setStockAdjustQty((prod.current_stock || 0).toString());
    } else {
      setStockAdjustQty('1');
    }
    setIsStockAdjustModalOpen(true);
  };

  const handleStockAdjustInvoiceFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 10 * 1024 * 1024) {
      setModalError("O arquivo da Nota Fiscal não pode exceder 10 MB.");
      return;
    }

    setStockAdjustAttachmentName(`${file.name} (${(file.size / 1024).toFixed(1)} KB)`);
    const reader = new FileReader();
    reader.onload = () => {
      setStockAdjustAttachment(reader.result as string);
    };
    reader.readAsDataURL(file);
  };

  const handleSaveStockAdjustment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!stockAdjustProduct) return;

    const qty = parseFloat(stockAdjustQty);
    if (isNaN(qty) || (qty <= 0 && stockAdjustType !== 'reconciliation')) {
      setModalError("Informe uma quantidade válida maior que zero.");
      return;
    }

    if (stockAdjustType === 'invoice_entry' && !stockAdjustInvoice.trim()) {
      setModalError("O número da Nota Fiscal (NF-e) é obrigatório para registrar a entrada.");
      return;
    }

    if (stockAdjustType === 'manual_loss') {
      const curStock = Number(stockAdjustProduct.current_stock || 0);
      if (qty > curStock) {
        setModalError(`A quantidade a baixar (${qty}) não pode exceder o saldo atual em estoque (${curStock} ${stockAdjustProduct.unit_of_measure}).`);
        return;
      }
      if (!stockAdjustNotes.trim()) {
        setModalError("A justificativa detalhada é obrigatória para registrar a baixa técnica.");
        return;
      }
    }

    if (stockAdjustType === 'reconciliation' && !stockAdjustAuditor.trim()) {
      setModalError("Informe o nome do responsável / auditor pela contagem física.");
      return;
    }

    try {
      setIsSaving(true);
      await inventoryService.adjustInventoryStock({
        product_id: stockAdjustProduct.id,
        adjustment_type: stockAdjustType,
        quantity: qty,
        unit_cost: parseFloat(stockAdjustCost) || 0,
        invoice_number: stockAdjustInvoice.trim() || undefined,
        invoice_attachment: stockAdjustAttachment || undefined,
        supplier_name: stockAdjustSupplier.trim() || undefined,
        batch_number: stockAdjustBatch.trim() || undefined,
        expiry_date: stockAdjustExpiry || undefined,
        reason: stockAdjustReason || undefined,
        notes: stockAdjustNotes.trim() || undefined,
        auditor_name: stockAdjustAuditor.trim() || undefined
      });

      await loadInventoryData();
      setIsStockAdjustModalOpen(false);
    } catch (err: any) {
      setModalError(formatApiError(err, "Erro ao registrar movimentação de estoque."));
    } finally {
      setIsSaving(false);
    }
  };



  const formatCurrency = (val: number | string | undefined) => {
    const num = typeof val === 'string' ? parseFloat(val) : (val || 0);
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(num);
  };

  // Cálculos de Métricas
  const totalStockValue = (products || []).reduce((acc, p) => acc + ((p.current_stock || 0) * (p.reference_price || 0)), 0);
  const belowMinStockItems = (products || []).filter(p => (p.current_stock || 0) <= (p.min_stock || 0));
  const zeroStockItems = (products || []).filter(p => (p.current_stock || 0) <= 0);

  const auditedProductsCount = (products || []).filter(p =>
    stockMovements.some(m => m.product_id === p.id && (m.movement_type === 'in_reconciliation' || m.movement_type === 'out_reconciliation' || m.movement_type === 'in_adjustment' || m.movement_type === 'out_adjustment'))
  ).length;

  const totalDivergenceMovements = (stockMovements || []).filter(m =>
    m.movement_type === 'in_reconciliation' || m.movement_type === 'out_reconciliation' || m.movement_type === 'out_loss'
  );

  const accuracyRate = products.length > 0 ? Math.round((auditedProductsCount / products.length) * 100) : 100;

  // Filtros Avançados
  const filteredProducts = (products || []).filter(p => {
    const matchesSearch = p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.sku.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (p.brand && p.brand.toLowerCase().includes(searchTerm.toLowerCase()));
    const matchesCategory = selectedCategoryFilter ? p.category_id === selectedCategoryFilter : true;

    let matchesStatus = true;
    const cur = Number(p.current_stock || 0);
    const min = Number(p.min_stock || 0);
    if (stockStatusFilter === 'criticos') {
      matchesStatus = cur <= min;
    } else if (stockStatusFilter === 'zerados') {
      matchesStatus = cur <= 0;
    } else if (stockStatusFilter === 'regulares') {
      matchesStatus = cur > min;
    }

    return matchesSearch && matchesCategory && matchesStatus;
  });

  const filteredCategories = (categories || []).filter(c =>
    c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (c.code && c.code.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  const filteredMovements = (stockMovements || []).filter(m =>
    (m.product_name && m.product_name.toLowerCase().includes(searchTerm.toLowerCase())) ||
    (m.sku && m.sku.toLowerCase().includes(searchTerm.toLowerCase())) ||
    (m.reference_doc && m.reference_doc.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  return (
    <div className="inventory-page">
      <div className="inventory-layout">

        {/* ================================================================= */}
        {/* 1. SIDEBAR LATERAL ESQUERDA (Alinhada ao Design System ControlB) */}
        {/* ================================================================= */}
        <aside className="sidebar-left">
          <div className="sidebar-header">
            <Package className="brand-icon" size={20} />
            <div className="sidebar-title-wrap">
              <span className="sidebar-title"><strong>ESTOQUE</strong></span>
              <span className="sidebar-subtitle">Gestão de Almoxarifado</span>
            </div>
          </div>

          <nav className="nav-menu">
            <span className="menu-group-label">Almoxarifado & Catálogo</span>

            <button
              className={`nav-item ${activeMenu === 'produtos' ? 'active' : ''}`}
              onClick={() => { setActiveMenu('produtos'); setSearchTerm(''); }}
            >
              <div className="nav-item-content">
                <Package size={16} />
                <span>Catálogo de Produtos</span>
              </div>
              <span className={`nav-badge ${belowMinStockItems.length > 0 ? 'critical-badge' : ''}`}>
                {products.length}
              </span>
            </button>

            <button
              className={`nav-item ${activeMenu === 'categorias' ? 'active' : ''}`}
              onClick={() => { setActiveMenu('categorias'); setSearchTerm(''); }}
            >
              <div className="nav-item-content">
                <Tags size={16} />
                <span>Categorias de Produtos</span>
              </div>
              <span className="nav-badge">{categories.length}</span>
            </button>

            <button
              className={`nav-item ${activeMenu === 'movimentacoes' ? 'active' : ''}`}
              onClick={() => { setActiveMenu('movimentacoes'); setSearchTerm(''); }}
            >
              <div className="nav-item-content">
                <History size={16} />
                <span>Movimentações (Kardex)</span>
              </div>
              <span className="nav-badge">{stockMovements.length}</span>
            </button>

            <button
              className={`nav-item ${activeMenu === 'auditoria' ? 'active' : ''}`}
              onClick={() => { setActiveMenu('auditoria'); setSearchTerm(''); }}
            >
              <div className="nav-item-content">
                <ShieldCheck size={16} />
                <span>Auditoria & Inventário</span>
              </div>
              <span className={`nav-badge ${totalDivergenceMovements.length > 0 ? 'critical-badge' : ''}`}>
                {totalDivergenceMovements.length > 0 ? `${totalDivergenceMovements.length} div.` : '100%'}
              </span>
            </button>
          </nav>

          {/* Footer com Resumo de Métricas de Almoxarifado */}
          <div className="sidebar-footer-stats">
            <div className="stat-card">
              <span className="stat-label">Valor Total em Estoque</span>
              <strong className="stat-value">{formatCurrency(totalStockValue)}</strong>
            </div>
            {belowMinStockItems.length > 0 && (
              <div className="stat-card warning">
                <span className="stat-label">Itens em Ponto de Pedido</span>
                <strong className="stat-value warning">{belowMinStockItems.length} produtos</strong>
              </div>
            )}
          </div>
        </aside>

        {/* ================================================================= */}
        {/* 2. ÁREA DE CONTEÚDO PRINCIPAL                                    */}
        {/* ================================================================= */}
        <main className="content-right">
          <div className="content-header">
            <div className="header-info">
              <div className="breadcrumb">
                <span>Controle Operacional</span>
                <ChevronRight size={12} />
                <span className="current">
                  {activeMenu === 'produtos' && 'Catálogo de Produtos & Insumos'}
                  {activeMenu === 'categorias' && 'Categorias de Produtos'}
                  {activeMenu === 'movimentacoes' && 'Histórico de Movimentações de Estoque'}
                  {activeMenu === 'auditoria' && 'Auditoria & Inventário Físico'}
                </span>
              </div>
              <h1 className="section-title">
                {activeMenu === 'produtos' && 'Catálogo de Produtos, Insumos & Almoxarifado'}
                {activeMenu === 'categorias' && 'Categorias e Grupos de Produtos'}
                {activeMenu === 'movimentacoes' && 'Extrato & Auditoria de Movimentações de Estoque'}
                {activeMenu === 'auditoria' && 'Painel de Auditoria & Balanço Físico de Estoque'}
              </h1>
            </div>

            <div className="header-actions">
              <button
                className="btn-refresh"
                onClick={loadInventoryData}
                disabled={loading}
                title="Recarregar Dados"
              >
                <RefreshCw size={15} className={loading ? 'spinning' : ''} />
              </button>

              {activeMenu !== 'movimentacoes' && activeMenu !== 'auditoria' && (
                <button className="btn-primary" onClick={handleOpenCreateModal}>
                  <Plus size={16} />
                  <span>
                    {activeMenu === 'produtos' && 'Novo Produto'}
                    {activeMenu === 'categorias' && 'Nova Categoria'}
                  </span>
                </button>
              )}
            </div>
          </div>

          {/* DASHBOARD KPIS (Cards de Resumo no topo) */}
          {activeMenu === 'auditoria' ? (
            <div className="inventory-kpis-grid">
              <div className="kpi-card total-items">
                <div className="kpi-icon" style={{ background: 'rgba(16, 185, 129, 0.12)', color: '#10b981' }}><ShieldCheck size={18} /></div>
                <div className="kpi-info">
                  <span className="kpi-label">Acuracidade do Inventário</span>
                  <strong className="kpi-value">{accuracyRate}%</strong>
                  <span className="kpi-sub">{auditedProductsCount} de {products.length} itens auditados</span>
                </div>
              </div>

              <div className={`kpi-card ${totalDivergenceMovements.length > 0 ? 'critical' : 'ok'}`}>
                <div className="kpi-icon" style={{ background: 'rgba(239, 68, 68, 0.12)', color: '#ef4444' }}><AlertTriangle size={18} /></div>
                <div className="kpi-info">
                  <span className="kpi-label">Divergências Físicas</span>
                  <strong className="kpi-value">{totalDivergenceMovements.length}</strong>
                  <span className="kpi-sub">Sobras, quebras e avarias registradas</span>
                </div>
              </div>

              <div className="kpi-card stock-value">
                <div className="kpi-icon" style={{ background: 'rgba(59, 130, 246, 0.12)', color: '#3b82f6' }}><DollarSign size={18} /></div>
                <div className="kpi-info">
                  <span className="kpi-label">Patrimônio em Almoxarifado</span>
                  <strong className="kpi-value">{formatCurrency(totalStockValue)}</strong>
                  <span className="kpi-sub">Saldo contábil avaliado em estoque</span>
                </div>
              </div>

              <div className="kpi-card movements">
                <div className="kpi-icon" style={{ background: 'rgba(245, 158, 11, 0.12)', color: '#f59e0b' }}><Scale size={18} /></div>
                <div className="kpi-info">
                  <span className="kpi-label">Pendentes de Contagem</span>
                  <strong className="kpi-value">{products.length - auditedProductsCount}</strong>
                  <span className="kpi-sub">Itens sem aferição física</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="inventory-kpis-grid">
              <div className="kpi-card total-items">
                <div className="kpi-icon"><Package size={18} /></div>
                <div className="kpi-info">
                  <span className="kpi-label">Total de SKUs Cadastrados</span>
                  <strong className="kpi-value">{products.length}</strong>
                  <span className="kpi-sub">{categories.length} categorias ativas</span>
                </div>
              </div>

              <div className="kpi-card stock-value">
                <div className="kpi-icon"><DollarSign size={18} /></div>
                <div className="kpi-info">
                  <span className="kpi-label">Valor Total Avaliado em Estoque</span>
                  <strong className="kpi-value">{formatCurrency(totalStockValue)}</strong>
                  <span className="kpi-sub">Custo de referência multiplicado pelo saldo</span>
                </div>
              </div>

              <div className={`kpi-card ${belowMinStockItems.length > 0 ? 'critical' : 'ok'}`}>
                <div className="kpi-icon">
                  {belowMinStockItems.length > 0 ? <AlertTriangle size={18} /> : <CheckCircle2 size={18} />}
                </div>
                <div className="kpi-info">
                  <span className="kpi-label">Ponto de Pedido / Reposição</span>
                  <strong className="kpi-value">{belowMinStockItems.length} itens</strong>
                  <span className="kpi-sub">
                    {belowMinStockItems.length > 0 ? `${zeroStockItems.length} itens com estoque zerado` : 'Todos os estoques saudáveis'}
                  </span>
                </div>
              </div>

              <div className="kpi-card movements">
                <div className="kpi-icon"><History size={18} /></div>
                <div className="kpi-info">
                  <span className="kpi-label">Movimentações Registradas</span>
                  <strong className="kpi-value">{stockMovements.length}</strong>
                  <span className="kpi-sub">Trilha de auditoria e entradas por compras</span>
                </div>
              </div>
            </div>
          )}

          {/* TOOLBAR DE FILTROS & PESQUISA */}
          <div className="search-toolbar">
            <div className="search-box">
              <Search className="search-icon" size={16} />
              <input
                type="text"
                placeholder={`Pesquisar em ${activeMenu}... (nome, SKU, marca)`}
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>

            {activeMenu === 'produtos' && (
              <div className="filter-group">
                {/* Filtro por Status de Estoque */}
                <div className="status-pills">
                  <button
                    className={`pill ${stockStatusFilter === 'todos' ? 'active' : ''}`}
                    onClick={() => setStockStatusFilter('todos')}
                  >
                    Todos ({products.length})
                  </button>
                  <button
                    className={`pill warning ${stockStatusFilter === 'criticos' ? 'active' : ''}`}
                    onClick={() => setStockStatusFilter('criticos')}
                  >
                    Críticos ({belowMinStockItems.length})
                  </button>
                  <button
                    className={`pill danger ${stockStatusFilter === 'zerados' ? 'active' : ''}`}
                    onClick={() => setStockStatusFilter('zerados')}
                  >
                    Zerados ({zeroStockItems.length})
                  </button>
                  <button
                    className={`pill success ${stockStatusFilter === 'regulares' ? 'active' : ''}`}
                    onClick={() => setStockStatusFilter('regulares')}
                  >
                    Regulares ({products.length - belowMinStockItems.length})
                  </button>
                </div>

                {/* Filtro por Categoria */}
                <select
                  value={selectedCategoryFilter}
                  onChange={(e) => setSelectedCategoryFilter(e.target.value)}
                  className="category-select"
                >
                  <option value="">Todas as Categorias</option>
                  {categories.map(c => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>
            )}

            <div className="results-count">
              {activeMenu === 'produtos' && `${filteredProducts.length} produtos listados`}
              {activeMenu === 'categorias' && `${filteredCategories.length} categorias listadas`}
              {activeMenu === 'movimentacoes' && `${filteredMovements.length} movimentações listadas`}
            </div>
          </div>

          {/* =============================================================== */}
          {/* 3. TABELAS DE DADOS                                             */}
          {/* =============================================================== */}
          <div className="data-table-container">
            {/* TABELA DE PRODUTOS */}
            {activeMenu === 'produtos' && (
              <>
                {loading ? (
                  <div className="table-empty">
                    <Loader2 size={32} className="spinning" />
                    <p>Carregando catálogo de produtos...</p>
                  </div>
                ) : filteredProducts.length === 0 ? (
                  <div className="table-empty">
                    <Package size={48} />
                    <h3>Nenhum produto encontrado</h3>
                    <p>Cadastre novos produtos ou altere os filtros de pesquisa acima.</p>
                    <button className="btn-primary" onClick={handleOpenCreateModal}>
                      <Plus size={16} /> Cadastrar Produto
                    </button>
                  </div>
                ) : (
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Produto & SKU</th>
                        <th>Categoria</th>
                        <th>Preço Ref.</th>
                        <th>Nível de Estoque (Físico)</th>
                        <th>Localização</th>
                        <th>Rastreabilidade</th>
                        <th className="th-actions">Ações</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredProducts.map((prod) => {
                        const cur = Number(prod.current_stock || 0);
                        const min = Number(prod.min_stock || 0);
                        const max = prod.max_stock ? Number(prod.max_stock) : Math.max(min * 2, cur * 1.5, 50);
                        const isZero = cur <= 0;
                        const isLow = cur <= min && !isZero;
                        const stockPercent = Math.min(100, Math.max(0, (cur / max) * 100));

                        return (
                          <tr key={prod.id} className={isZero ? 'row-zero' : isLow ? 'row-low' : ''}>
                            <td>
                              <div className="product-title-cell">
                                <strong className="product-name">{prod.name}</strong>
                                <div className="tags-row">
                                  <span className="sku-tag">SKU: {prod.sku}</span>
                                  {prod.brand && <span className="brand-tag">{prod.brand}</span>}
                                </div>
                              </div>
                            </td>
                            <td>
                              <span className="category-pill">
                                {prod.category?.name || 'Geral'}
                              </span>
                            </td>
                            <td><strong>{formatCurrency(prod.reference_price)}</strong></td>
                            <td>
                              <div className="stock-visual-cell">
                                <div className="stock-header-info">
                                  <span className={`stock-status-badge ${isZero ? 'danger' : isLow ? 'warning' : 'ok'}`}>
                                    {isZero ? 'ZERADO' : isLow ? 'CRÍTICO' : 'REGULAR'}
                                  </span>
                                  <span className="stock-numbers">
                                    <strong>{cur}</strong> / {min} {prod.unit_of_measure}
                                  </span>
                                </div>
                                <div className="stock-progress-bar">
                                  <div
                                    className={`progress-fill ${isZero ? 'danger' : isLow ? 'warning' : 'ok'}`}
                                    style={{ width: `${isZero ? 5 : stockPercent}%` }}
                                  />
                                </div>
                                <button
                                  className="btn-quick-adjust"
                                  onClick={() => handleOpenStockAdjustModal(prod)}
                                  title="Ajustar Saldo Físico / Inventário"
                                >
                                  <SlidersHorizontal size={12} /> Ajustar
                                </button>
                              </div>
                            </td>
                            <td>
                              <span className="location-cell">
                                {prod.storage_location ? prod.storage_location : <span className="empty-text">Não informada</span>}
                              </span>
                            </td>
                            <td>
                              <div className="tag-cluster">
                                {prod.is_perishable && <span className="tag per">Perecível</span>}
                                {prod.requires_batch && <span className="tag bat">Exige Lote</span>}
                                {!prod.is_perishable && !prod.requires_batch && <span className="tag std">Padrão</span>}
                              </div>
                            </td>
                            <td>
                              <div className="actions-cell">
                                <button
                                  className="action-btn edit"
                                  onClick={() => handleEditProduct(prod)}
                                  title="Editar produto"
                                >
                                  <Edit size={14} />
                                </button>
                                <button
                                  className="action-btn delete"
                                  onClick={() => handleDeleteProduct(prod)}
                                  title="Excluir produto"
                                >
                                  <Trash2 size={14} />
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </>
            )}

            {/* TABELA DE CATEGORIAS */}
            {activeMenu === 'categorias' && (
              <>
                {loading ? (
                  <div className="table-empty">
                    <Loader2 size={32} className="spinning" />
                    <p>Carregando categorias...</p>
                  </div>
                ) : filteredCategories.length === 0 ? (
                  <div className="table-empty">
                    <Tags size={48} />
                    <h3>Nenhuma categoria cadastrada</h3>
                    <p>Crie categorias para organizar seus itens em grupos (Medicamentos, Perfumaria, Insumos, etc.).</p>
                    <button className="btn-primary" onClick={handleOpenCreateModal}>
                      <Plus size={16} /> Nova Categoria
                    </button>
                  </div>
                ) : (
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Código / Prefixo</th>
                        <th>Nome da Categoria</th>
                        <th>Descrição</th>
                        <th className="th-actions">Ações</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredCategories.map((cat) => (
                        <tr key={cat.id}>
                          <td><span className="code-tag">{cat.code || '-'}</span></td>
                          <td><strong>{cat.name}</strong></td>
                          <td>{cat.description || '-'}</td>
                          <td>
                            <div className="actions-cell">
                              <button
                                className="action-btn edit"
                                onClick={() => handleEditCategory(cat)}
                                title="Editar categoria"
                              >
                                <Edit size={14} />
                              </button>
                              <button
                                className="action-btn delete"
                                onClick={() => handleDeleteCategory(cat)}
                                title="Excluir categoria"
                              >
                                <Trash2 size={14} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </>
            )}

            {/* TABELA DE MOVIMENTAÇÕES (KARDEX) */}
            {activeMenu === 'movimentacoes' && (
              <>
                {loading ? (
                  <div className="table-empty">
                    <Loader2 size={32} className="spinning" />
                    <p>Carregando extrato de movimentações...</p>
                  </div>
                ) : filteredMovements.length === 0 ? (
                  <div className="table-empty">
                    <History size={48} />
                    <h3>Nenhuma movimentação registrada</h3>
                    <p>As entradas e saídas físicas do almoxarifado serão registradas aqui automaticamente conforme compras e ajustes ocorrem.</p>
                  </div>
                ) : (
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Data / Hora</th>
                        <th>Produto</th>
                        <th>Tipo de Movimentação</th>
                        <th>Qtd</th>
                        <th>Custo Unit.</th>
                        <th>Saldo Resultante</th>
                        <th>Documento de Referência</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredMovements.map((mov) => {
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
                              <strong>{mov.product_name || mov.product?.name || 'Produto'}</strong>
                              <span className="sub-label">SKU: {mov.sku || mov.product?.sku || '-'}</span>
                            </td>
                            <td>
                              {mov.movement_type === 'in_purchase' && (
                                <span className="movement-badge in-purchase">
                                  <ArrowDownRight size={13} /> Entrada por Compra (PO)
                                </span>
                              )}
                              {mov.movement_type === 'in_invoice' && (
                                <span className="movement-badge in-purchase">
                                  <ArrowDownRight size={13} /> Entrada por NF-e
                                </span>
                              )}
                              {mov.movement_type === 'in_adjustment' && (
                                <span className="movement-badge in-adj">
                                  <ArrowDownRight size={13} /> Entrada (Ajuste Balanço)
                                </span>
                              )}
                              {mov.movement_type === 'in_reconciliation' && (
                                <span className="movement-badge in-adj" style={{ background: 'rgba(16, 185, 129, 0.12)', color: '#10b981', borderColor: 'rgba(16, 185, 129, 0.3)' }}>
                                  <Check size={13} /> Sobra de Inventário (+)
                                </span>
                              )}
                              {mov.movement_type === 'out_sale' && (
                                <span className="movement-badge out-sale">
                                  <ArrowUpRight size={13} /> Saída por Venda
                                </span>
                              )}
                              {mov.movement_type === 'out_adjustment' && (
                                <span className="movement-badge out-adj">
                                  <ArrowUpRight size={13} /> Baixa (Ajuste Balanço)
                                </span>
                              )}
                              {mov.movement_type === 'out_reconciliation' && (
                                <span className="movement-badge out-adj" style={{ background: 'rgba(239, 68, 68, 0.12)', color: '#ef4444', borderColor: 'rgba(239, 68, 68, 0.3)' }}>
                                  <AlertTriangle size={13} /> Falta de Inventário (-)
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
                                {isPositive ? '+' : '-'}{Number(mov.quantity)} {mov.unit_of_measure || mov.product?.unit_of_measure || 'UN'}
                              </strong>
                            </td>
                            <td>{formatCurrency(mov.unit_cost)}</td>
                            <td>
                              <span className="balance-tag">
                                {Number(mov.balance_after)} {mov.unit_of_measure || mov.product?.unit_of_measure || 'UN'}
                              </span>
                            </td>
                            <td>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                                <span className="code-tag">{mov.reference_doc || '-'}</span>
                                {mov.invoice_attachment && (
                                  <a
                                    href={mov.invoice_attachment}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    download={`NF_${mov.reference_doc || 'Doc'}`}
                                    title="Baixar Nota Fiscal Anexada"
                                    style={{ color: 'var(--primary-color)', display: 'inline-flex' }}
                                  >
                                    <Paperclip size={13} />
                                  </a>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </>
            )}

            {/* ================================================================= */}
            {/* VIEW: AUDITORIA & INVENTÁRIO FÍSICO                              */}
            {/* ================================================================= */}
            {activeMenu === 'auditoria' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                {/* SEÇÃO 1: PAINEL DE BALANÇO & AFERIÇÃO FÍSICO-SISTÊMICA */}
                <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: '8px', overflow: 'hidden' }}>
                  <div style={{ padding: '0.85rem 1.25rem', borderBottom: '1px solid var(--border-subtle)', background: 'var(--bg-surface-elevated)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <h3 style={{ fontSize: '0.95rem', fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-primary)' }}>
                        <Scale size={16} style={{ color: '#10b981' }} />
                        Balanço Físico e Aferição de Saldo por SKU
                      </h3>
                      <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: '0.15rem 0 0' }}>
                        Realize contagens cíclicas, conciliações de prateleira e apuração de quebras/sobras com auditoria formal.
                      </p>
                    </div>
                    <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)' }}>
                      {filteredProducts.length} itens cadastrados
                    </span>
                  </div>

                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Produto / SKU</th>
                        <th>Categoria</th>
                        <th>Localização</th>
                        <th>Saldo Sistema</th>
                        <th>Status Auditoria</th>
                        <th>Última Auditoria</th>
                        <th style={{ textAlign: 'right' }}>Ação de Auditoria</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredProducts.length === 0 ? (
                        <tr>
                          <td colSpan={7} className="state-empty" style={{ textAlign: 'center', padding: '2rem' }}>
                            Nenhum produto localizado para os filtros informados.
                          </td>
                        </tr>
                      ) : (
                        filteredProducts.map(prod => {
                          const prodCat = categories.find(c => c.id === prod.category_id);
                          const lastReconcil = stockMovements.find(
                            m => m.product_id === prod.id && (m.movement_type === 'in_reconciliation' || m.movement_type === 'out_reconciliation' || m.movement_type === 'in_adjustment' || m.movement_type === 'out_adjustment')
                          );
                          const isAudited = Boolean(lastReconcil);

                          return (
                            <tr key={prod.id}>
                              <td>
                                <div className="product-title-cell">
                                  <span className="product-name" style={{ fontWeight: 600 }}>{prod.name}</span>
                                  <div className="tags-row">
                                    <span className="sku-tag">{prod.sku}</span>
                                    {prod.brand && <span className="brand-tag">{prod.brand}</span>}
                                  </div>
                                </div>
                              </td>
                              <td>
                                <span className="category-pill">{prodCat?.name || 'Geral'}</span>
                              </td>
                              <td>
                                <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                                  {prod.storage_location || 'Almoxarifado Central'}
                                </span>
                              </td>
                              <td>
                                <strong style={{ fontSize: '0.9rem', color: Number(prod.current_stock || 0) <= 0 ? '#ef4444' : 'var(--text-primary)' }}>
                                  {Number(prod.current_stock || 0)} {prod.unit_of_measure}
                                </strong>
                              </td>
                              <td>
                                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', padding: '0.2rem 0.55rem', borderRadius: '4px', fontSize: '0.725rem', fontWeight: 600, background: isAudited ? 'rgba(16, 185, 129, 0.12)' : 'rgba(245, 158, 11, 0.12)', color: isAudited ? '#10b981' : '#f59e0b', border: isAudited ? '1px solid rgba(16, 185, 129, 0.25)' : '1px solid rgba(245, 158, 11, 0.25)' }}>
                                  {isAudited ? <CheckCircle2 size={12} /> : <AlertTriangle size={12} />}
                                  <span>{isAudited ? 'Auditado' : 'Pendente'}</span>
                                </span>
                              </td>
                              <td>
                                {lastReconcil ? (
                                  <div style={{ display: 'flex', flexDirection: 'column', fontSize: '0.75rem' }}>
                                    <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{new Date(lastReconcil.created_at).toLocaleDateString('pt-BR')}</span>
                                    <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>{lastReconcil.notes ? lastReconcil.notes.substring(0, 30) : 'Contagem física'}</span>
                                  </div>
                                ) : (
                                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Sem histórico</span>
                                )}
                              </td>
                              <td style={{ textAlign: 'right' }}>
                                <button
                                  type="button"
                                  style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', padding: '0.4rem 0.8rem', fontSize: '0.78rem', fontWeight: 600, borderRadius: '6px', background: 'linear-gradient(135deg, #10b981, #059669)', color: '#fff', border: 'none', cursor: 'pointer', boxShadow: '0 1px 2px rgba(0,0,0,0.08)' }}
                                  title="Realizar Contagem e Conciliação de Saldo"
                                  onClick={() => handleOpenStockAdjustModal(prod, 'reconciliation')}
                                >
                                  <ShieldCheck size={14} />
                                  <span>Auditar Saldo</span>
                                </button>
                              </td>
                            </tr>
                          );
                        })
                      )}
                    </tbody>
                  </table>
                </div>

                {/* SEÇÃO 2: HISTÓRICO DE PARECERES & CONCILIAÇÕES */}
                <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: '8px', overflow: 'hidden' }}>
                  <div style={{ padding: '0.85rem 1.25rem', borderBottom: '1px solid var(--border-subtle)', background: 'var(--bg-surface-elevated)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <h3 style={{ fontSize: '0.95rem', fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-primary)' }}>
                        <FileText size={16} style={{ color: '#3b82f6' }} />
                        Extrato de Pareceres e Divergências de Auditoria
                      </h3>
                      <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: '0.15rem 0 0' }}>
                        Histórico auditável e imutável de todas as contagens, baixas técnicas e ajustes fiscais.
                      </p>
                    </div>
                    <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)' }}>
                      {totalDivergenceMovements.length} pareceres registrados
                    </span>
                  </div>

                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Data / Hora</th>
                        <th>Produto</th>
                        <th>Tipo de Divergência</th>
                        <th>Qtd Ajustada</th>
                        <th>Saldo Resultante</th>
                        <th>Parecer & Justificativa Registrada</th>
                        <th>Documento</th>
                      </tr>
                    </thead>
                    <tbody>
                      {totalDivergenceMovements.length === 0 ? (
                        <tr>
                          <td colSpan={7} className="state-empty" style={{ textAlign: 'center', padding: '2rem' }}>
                            Nenhum parecer de auditoria física registrado até o momento.
                          </td>
                        </tr>
                      ) : (
                        totalDivergenceMovements.map(mov => {
                          const isPositive = mov.movement_type.startsWith('in_');
                          return (
                            <tr key={mov.id}>
                              <td>
                                <div style={{ display: 'flex', flexDirection: 'column' }}>
                                  <strong style={{ fontSize: '0.8rem', color: 'var(--text-primary)' }}>{new Date(mov.created_at).toLocaleDateString('pt-BR')}</strong>
                                  <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{new Date(mov.created_at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}</span>
                                </div>
                              </td>
                              <td>
                                <div className="product-title-cell">
                                  <span className="product-name" style={{ fontWeight: 600 }}>{mov.product_name || mov.product?.name || 'Produto'}</span>
                                  <div className="tags-row">
                                    <span className="sku-tag">{mov.sku || mov.product?.sku || '-'}</span>
                                  </div>
                                </div>
                              </td>
                              <td>
                                {mov.movement_type === 'in_reconciliation' && (
                                  <span className="movement-badge in-adj" style={{ background: 'rgba(16, 185, 129, 0.12)', color: '#10b981', borderColor: 'rgba(16, 185, 129, 0.3)' }}>
                                    <Check size={13} /> Sobra de Inventário (+)
                                  </span>
                                )}
                                {mov.movement_type === 'out_reconciliation' && (
                                  <span className="movement-badge out-adj" style={{ background: 'rgba(239, 68, 68, 0.12)', color: '#ef4444', borderColor: 'rgba(239, 68, 68, 0.3)' }}>
                                    <AlertTriangle size={13} /> Quebra / Falta (-)
                                  </span>
                                )}
                                {mov.movement_type === 'out_loss' && (
                                  <span className="movement-badge out-loss">
                                    <AlertTriangle size={13} /> Perda / Avaria (-)
                                  </span>
                                )}
                              </td>
                              <td>
                                <strong className={isPositive ? 'qty-pos' : 'qty-neg'}>
                                  {isPositive ? '+' : '-'}{Number(mov.quantity)} {mov.unit_of_measure || mov.product?.unit_of_measure || 'UN'}
                                </strong>
                              </td>
                              <td>
                                <span className="balance-tag">
                                  {Number(mov.balance_after)} {mov.unit_of_measure || mov.product?.unit_of_measure || 'UN'}
                                </span>
                              </td>
                              <td>
                                <div style={{ maxWidth: '320px', fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.3 }}>
                                  {mov.notes || 'Ajuste de inventário físico'}
                                </div>
                              </td>
                              <td>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                                  <span className="code-tag">{mov.reference_doc || '-'}</span>
                                  {mov.invoice_attachment && (
                                    <a
                                      href={mov.invoice_attachment}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      download={`NF_${mov.reference_doc || 'Doc'}`}
                                      title="Baixar Nota Fiscal Anexada"
                                      style={{ color: 'var(--primary-color)', display: 'inline-flex' }}
                                    >
                                      <Paperclip size={13} />
                                    </a>
                                  )}
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
          </div>
        </main>
      </div>

      {/* ================================================================= */}
      {/* 4. MODAL DE CRIAÇÃO / EDIÇÃO (PRODUTO & CATEGORIA)               */}
      {/* ================================================================= */}
      {/* ================================================================= */}
      {/* 4. MODAL DE CRIAÇÃO / EDIÇÃO (PRODUTO & CATEGORIA)               */}
      {/* ================================================================= */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
          setEditingProduct(null);
          setEditingCategory(null);
        }}
        title={
          activeMenu === 'categorias' ? (editingCategory ? 'Editar Categoria' : 'Nova Categoria') :
            activeMenu === 'produtos' ? (editingProduct ? 'Editar Produto / Insumo' : 'Novo Produto / Insumo') : ''
        }
        size={activeMenu === 'produtos' ? 'lg' : 'md'}
      >
        <form onSubmit={handleSaveModal} className="wizard-form">
          {modalError && (
            <div className="modal-alert-error">
              <AlertTriangle size={16} />
              <span>{modalError}</span>
            </div>
          )}

          {activeMenu === 'categorias' && (
            <>
              <div className="form-group">
                <label>Nome da Categoria <span className="req">*</span></label>
                <input
                  type="text"
                  value={categoryName}
                  onChange={(e) => setCategoryName(e.target.value)}
                  placeholder="Ex: Medicamentos, Perfumaria, Insumos"
                  required
                />
              </div>
              <div className="form-group">
                <label>Código da Categoria (Opcional - Prefixo de SKU)</label>
                <input
                  type="text"
                  value={categoryCode}
                  onChange={(e) => setCategoryCode(e.target.value)}
                  placeholder="Ex: MED, PERF, INS"
                  maxLength={10}
                />
              </div>
              <div className="form-group">
                <label>Descrição</label>
                <textarea
                  value={categoryDesc}
                  onChange={(e) => setCategoryDesc(e.target.value)}
                  placeholder="Observações sobre este grupo de itens..."
                  rows={3}
                />
              </div>
            </>
          )}

          {activeMenu === 'produtos' && (
            <>
              {/* Seção 1: Identificação & Classificação */}
              <div className="form-section-divider">
                <Package size={14} />
                <span>1. Identificação Básica & Classificação</span>
              </div>

              <div className="form-row cols-2-1">
                <div className="form-group">
                  <label>Nome do Produto / Insumo <span className="req">*</span></label>
                  <input
                    type="text"
                    value={productName}
                    onChange={(e) => {
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
                  <label>Categoria</label>
                  <select
                    value={productCategoryId}
                    onChange={(e) => {
                      setProductCategoryId(e.target.value);
                      if (!editingProduct) {
                        setProductSku(generateAutomaticSku(productName, e.target.value, productIsPerishable));
                      }
                    }}
                  >
                    <option value="">Selecione a categoria...</option>
                    {categories.map(c => (
                      <option key={c.id} value={c.id}>{c.code ? `[${c.code}] ` : ''}{c.name}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="form-row cols-3">
                <div className="form-group">
                  <label>SKU (Código Interno)</label>
                  <div className="input-with-button">
                    <input
                      type="text"
                      value={productSku}
                      onChange={(e) => setProductSku(e.target.value)}
                      placeholder="Deixe em branco para auto"
                    />
                    <button
                      type="button"
                      className="btn-inline-action"
                      onClick={() => setProductSku(generateAutomaticSku(productName, productCategoryId, productIsPerishable))}
                      title="Gerar SKU automático inteligente"
                    >
                      <Sparkles size={13} /> Auto
                    </button>
                  </div>
                </div>

                <div className="form-group">
                  <label>Unidade de Medida</label>
                  <select
                    value={productUnit}
                    onChange={(e) => setProductUnit(e.target.value)}
                  >
                    <option value="UN">Unidade (UN)</option>
                    <option value="CX">Caixa (CX)</option>
                    <option value="FR">Frasco (FR)</option>
                    <option value="AMP">Ampola (AMP)</option>
                    <option value="KG">Quilograma (KG)</option>
                    <option value="L">Litro (L)</option>
                    <option value="M">Metro (M)</option>
                  </select>
                </div>

                <div className="form-group">
                  <label>Preço de Referência (R$)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={productPrice}
                    onChange={(e) => setProductPrice(e.target.value)}
                    placeholder="0,00"
                  />
                </div>
              </div>

              {/* Seção 2: Saldo Físico & Parâmetros de Ressuprimento */}
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
                    🔒 O saldo físico é imutável via cadastro. Para alterar, utilize a <strong>Movimentação Auditada</strong>.
                  </div>
                </div>
              ) : (
                <div className="form-row cols-3">
                  <div className="form-group">
                    <label>Estoque Inicial de Implantação</label>
                    <input
                      type="number"
                      step="any"
                      min="0"
                      value={productCurrentStock}
                      onChange={(e) => setProductCurrentStock(e.target.value)}
                      placeholder="0"
                    />
                  </div>
                  <div className="form-group">
                    <label>Estoque Mínimo (Ponto de Pedido)</label>
                    <input
                      type="number"
                      step="any"
                      min="0"
                      value={productMinStock}
                      onChange={(e) => setProductMinStock(e.target.value)}
                      placeholder="0"
                    />
                  </div>
                  <div className="form-group">
                    <label>Estoque Alvo (Máximo)</label>
                    <input
                      type="number"
                      step="any"
                      min="0"
                      value={productMaxStock}
                      onChange={(e) => setProductMaxStock(e.target.value)}
                      placeholder="Ex: 50"
                    />
                  </div>
                </div>
              )}

              {editingProduct && (
                <div className="form-row cols-2">
                  <div className="form-group">
                    <label>Estoque Mínimo (Ponto de Pedido)</label>
                    <input
                      type="number"
                      step="any"
                      min="0"
                      value={productMinStock}
                      onChange={(e) => setProductMinStock(e.target.value)}
                      placeholder="0"
                    />
                  </div>
                  <div className="form-group">
                    <label>Estoque Alvo (Máximo)</label>
                    <input
                      type="number"
                      step="any"
                      min="0"
                      value={productMaxStock}
                      onChange={(e) => setProductMaxStock(e.target.value)}
                      placeholder="Ex: 50"
                    />
                  </div>
                </div>
              )}

              <div className="form-row cols-2">
                <div className="form-group">
                  <label>Localização Almoxarifado / Prateleira</label>
                  <input
                    type="text"
                    value={productStorageLocation}
                    onChange={(e) => setProductStorageLocation(e.target.value)}
                    placeholder="Ex: Corredor B - Prateleira 04"
                  />
                </div>
                <div className="form-group">
                  <label>Fabricante / Marca</label>
                  <input
                    type="text"
                    value={productBrand}
                    onChange={(e) => setProductBrand(e.target.value)}
                    placeholder="Ex: Medley, EMS, Eurofarma"
                  />
                </div>
              </div>

              {/* Seção 3: Rastreabilidade & Fiscal */}
              <div className="form-section-divider">
                <Tags size={14} />
                <span>3. Rastreabilidade & Tributário (Opcional)</span>
              </div>

              <div className="form-row cols-2">
                <div className="form-group">
                  <label>Código de Barras / EAN-13</label>
                  <input
                    type="text"
                    value={productBarcode}
                    onChange={(e) => setProductBarcode(e.target.value)}
                    placeholder="Ex: 7891234567890"
                  />
                </div>
                <div className="form-group">
                  <label>Classificação Fiscal (NCM)</label>
                  <input
                    type="text"
                    value={productNcm}
                    onChange={(e) => setProductNcm(e.target.value)}
                    placeholder="Ex: 3004.90.99"
                  />
                </div>
              </div>

              <div className="form-group">
                <label>Descrição Técnica & Observações</label>
                <textarea
                  value={productDesc}
                  onChange={(e) => setProductDesc(e.target.value)}
                  placeholder="Informações técnicas adicionais sobre dosagem, forma farmacêutica ou aplicação..."
                  rows={2}
                />
              </div>
            </>
          )}

          <div className="modal-footer">
            <button
              type="button"
              className="btn-cancel"
              onClick={() => setIsModalOpen(false)}
            >
              Cancelar
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={isSaving}
            >
              {isSaving ? <Loader2 size={16} className="spinning" /> : <Check size={16} />}
              <span>{editingProduct || editingCategory ? 'Salvar Alterações' : 'Cadastrar'}</span>
            </button>
          </div>
        </form>
      </Modal>

      {/* ================================================================= */}
      {/* 5. MODAL DE MOVIMENTAÇÃO & AUDITORIA DE ESTOQUE (WIZARD)          */}
      {/* ================================================================= */}
      <Modal
        isOpen={isStockAdjustModalOpen}
        onClose={() => setIsStockAdjustModalOpen(false)}
        title={`📦 Movimentação Auditada de Estoque • ${stockAdjustProduct?.name || ''}`}
        size="lg"
      >
        <form onSubmit={handleSaveStockAdjustment} className="wizard-form">
          {modalError && (
            <div className="modal-alert-error">
              <AlertTriangle size={16} />
              <span>{modalError}</span>
            </div>
          )}

          {/* Cabeçalho com dados de Saldo Atual do Item */}
          <div className="stock-balance-badge-card" style={{ marginBottom: '0.25rem' }}>
            <div className="stock-balance-info">
              <span className="badge-label">Saldo Físico no Sistema:</span>
              <strong className="badge-value">
                {Number(stockAdjustProduct?.current_stock || 0)} {stockAdjustProduct?.unit_of_measure}
              </strong>
            </div>
            <div className="stock-balance-hint">
              SKU: <strong>{stockAdjustProduct?.sku}</strong> | Ref: <strong>{formatCurrency(stockAdjustProduct?.reference_price)}</strong>
            </div>
          </div>

          {/* Abas de Operação */}
          <div className="movement-tabs-row">
            <button
              type="button"
              className={`tab-btn ${stockAdjustType === 'invoice_entry' ? 'active' : ''}`}
              onClick={() => {
                setStockAdjustType('invoice_entry');
                setStockAdjustReason('Entrada por Nota Fiscal');
                setStockAdjustQty('1');
                setModalError(null);
              }}
            >
              <ArrowUpRight size={15} />
              <span>1. Entrada por NF</span>
            </button>

            <button
              type="button"
              className={`tab-btn ${stockAdjustType === 'manual_loss' ? 'active danger' : ''}`}
              onClick={() => {
                setStockAdjustType('manual_loss');
                setStockAdjustReason('Avaria / Quebra de Produto');
                setStockAdjustQty('1');
                setModalError(null);
              }}
            >
              <ArrowDownRight size={15} />
              <span>2. Baixa Justificada</span>
            </button>

            <button
              type="button"
              className={`tab-btn ${stockAdjustType === 'reconciliation' ? 'active blue' : ''}`}
              onClick={() => {
                setStockAdjustType('reconciliation');
                setStockAdjustReason('Contagem Cíclica de Inventário');
                setStockAdjustQty(String(stockAdjustProduct?.current_stock || 0));
                setModalError(null);
              }}
            >
              <SlidersHorizontal size={15} />
              <span>3. Conciliação Físico</span>
            </button>
          </div>

          {/* ===============================================================
              ABA 1: ENTRADA POR NOTA FISCAL (COMPRA OU TRANSFERÊNCIA)
          =============================================================== */}
          {stockAdjustType === 'invoice_entry' && (
            <>
              <div className="form-section-divider">
                <ArrowUpRight size={14} />
                <span>Dados do Documento Fiscal & Fornecedor</span>
              </div>

              <div className="form-row cols-2">
                <div className="form-group">
                  <label>Número da Nota Fiscal (NF-e) <span className="req">*</span></label>
                  <input
                    type="text"
                    value={stockAdjustInvoice}
                    onChange={(e) => setStockAdjustInvoice(e.target.value)}
                    placeholder="Ex: NF-e 004.892 - Série 1"
                    required
                  />
                </div>
                <div className="form-group">
                  <label>Fornecedor / Emitente da NF</label>
                  <input
                    type="text"
                    value={stockAdjustSupplier}
                    onChange={(e) => setStockAdjustSupplier(e.target.value)}
                    placeholder="Ex: EMS Farmacêutica Ltda"
                  />
                </div>
              </div>

              <div className="form-group">
                <label>Anexo da Nota Fiscal (PDF, XML ou Imagem)</label>
                {stockAdjustAttachmentName ? (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.65rem 0.85rem', background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', overflow: 'hidden' }}>
                      <Paperclip size={16} style={{ color: '#10b981', flexShrink: 0 }} />
                      <span style={{ fontSize: '0.85rem', fontWeight: 500, textOverflow: 'ellipsis', whiteSpace: 'nowrap', overflow: 'hidden' }}>{stockAdjustAttachmentName}</span>
                    </div>
                    <button
                      type="button"
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444', padding: '0.2rem' }}
                      onClick={() => { setStockAdjustAttachment(null); setStockAdjustAttachmentName(null); }}
                      title="Remover anexo"
                    >
                      <X size={15} />
                    </button>
                  </div>
                ) : (
                  <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', padding: '0.85rem', border: '1.5px dashed var(--border-subtle)', borderRadius: '8px', cursor: 'pointer', background: 'var(--bg-app)' }}>
                    <UploadCloud size={18} style={{ color: '#10b981' }} />
                    <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Selecionar ou arrastar NF-e (.pdf, .xml, imagem)</span>
                    <input
                      type="file"
                      accept=".pdf,.xml,image/*"
                      onChange={handleStockAdjustInvoiceFileChange}
                      style={{ display: 'none' }}
                    />
                  </label>
                )}
              </div>

              <div className="form-row cols-2">
                <div className="form-group">
                  <label>Quantidade Recebida (+) <span className="req">*</span></label>
                  <input
                    type="number"
                    step="any"
                    min="0.01"
                    value={stockAdjustQty}
                    onChange={(e) => setStockAdjustQty(e.target.value)}
                    required
                  />
                </div>
                <div className="form-group">
                  <label>Custo Unitário da NF (R$)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={stockAdjustCost}
                    onChange={(e) => setStockAdjustCost(e.target.value)}
                    placeholder="0,00"
                  />
                </div>
              </div>

              <div className="form-row cols-2">
                <div className="form-group">
                  <label>Número do Lote (Rastreabilidade)</label>
                  <input
                    type="text"
                    value={stockAdjustBatch}
                    onChange={(e) => setStockAdjustBatch(e.target.value)}
                    placeholder="Ex: LT-2026-904"
                  />
                </div>
                <div className="form-group">
                  <label>Data de Validade</label>
                  <input
                    type="date"
                    value={stockAdjustExpiry}
                    onChange={(e) => setStockAdjustExpiry(e.target.value)}
                  />
                </div>
              </div>

              <div className="form-group">
                <label>Observações / Relatório da Conferência</label>
                <textarea
                  value={stockAdjustNotes}
                  onChange={(e) => setStockAdjustNotes(e.target.value)}
                  placeholder="Ex: Mercadoria recebida em perfeito estado e conferida no almoxarifado central..."
                  rows={2}
                />
              </div>
            </>
          )}

          {/* ===============================================================
              ABA 2: BAIXA TÉCNICA JUSTIFICADA (AVARIA / VALIDADE / CONSUMO)
          =============================================================== */}
          {stockAdjustType === 'manual_loss' && (
            <>
              <div className="form-section-divider">
                <ArrowDownRight size={14} />
                <span>Motivo & Justificativa da Baixa</span>
              </div>

              <div className="form-row cols-2">
                <div className="form-group">
                  <label>Motivo Padronizado da Baixa <span className="req">*</span></label>
                  <select
                    value={stockAdjustReason}
                    onChange={(e) => setStockAdjustReason(e.target.value)}
                    required
                  >
                    <option value="Avaria / Quebra de Produto">Avaria / Quebra de Produto</option>
                    <option value="Vencimento / Validade Expirada">Vencimento / Validade Expirada</option>
                    <option value="Consumo Interno / Uso Operacional">Consumo Interno / Uso Operacional</option>
                    <option value="Descarte Técnico / Quarentena">Descarte Técnico / Quarentena</option>
                    <option value="Extravio / Divergência de Transporte">Extravio / Divergência de Transporte</option>
                    <option value="Outro Motivo Operacional">Outro Motivo Operacional</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Quantidade a Dar Baixa (-) <span className="req">*</span></label>
                  <input
                    type="number"
                    step="any"
                    min="0.01"
                    max={Number(stockAdjustProduct?.current_stock || 0)}
                    value={stockAdjustQty}
                    onChange={(e) => setStockAdjustQty(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div className="form-group">
                <label>Justificativa Formal Obrigatória <span className="req">*</span></label>
                <textarea
                  value={stockAdjustNotes}
                  onChange={(e) => setStockAdjustNotes(e.target.value)}
                  placeholder="Descreva detalhadamente o ocorrido (Ex: Caixa molhada no transporte, frasco trincado ou autorização de descarte)..."
                  rows={3}
                  required
                />
              </div>
            </>
          )}

          {/* ===============================================================
              ABA 3: CONCILIAÇÃO DE INVENTÁRIO FÍSICO (BALANÇO COM DIVERGÊNCIA)
          =============================================================== */}
          {stockAdjustType === 'reconciliation' && (() => {
            const curBal = Number(stockAdjustProduct?.current_stock || 0);
            const countedBal = parseFloat(stockAdjustQty) || 0;
            const diff = countedBal - curBal;

            return (
              <>
                <div className="form-section-divider">
                  <SlidersHorizontal size={14} />
                  <span>Conferência Física & Cálculo de Divergência</span>
                </div>

                {/* Card de Divergência em Tempo Real */}
                <div className="reconciliation-summary-card">
                  <div className="metric-box">
                    <span className="label">Saldo Sistema</span>
                    <span className="val">{curBal} {stockAdjustProduct?.unit_of_measure}</span>
                  </div>
                  <div className="metric-box">
                    <span className="label">Saldo Contado</span>
                    <span className="val">{countedBal} {stockAdjustProduct?.unit_of_measure}</span>
                  </div>
                  <div className="metric-box divergence">
                    <span className="label">Divergência Física</span>
                    <span className={`val ${diff > 0 ? 'surplus' : diff < 0 ? 'deficit' : 'matched'}`}>
                      {diff > 0 ? `+${diff} (Sobra)` : diff < 0 ? `${diff} (Quebra/Falta)` : '0 (Sem Divergência)'}
                    </span>
                  </div>
                </div>

                <div className="form-row cols-2">
                  <div className="form-group">
                    <label>Quantidade Física Contada no Almoxarifado <span className="req">*</span></label>
                    <input
                      type="number"
                      step="any"
                      min="0"
                      value={stockAdjustQty}
                      onChange={(e) => setStockAdjustQty(e.target.value)}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label>Tipo de Auditoria / Balanço <span className="req">*</span></label>
                    <select
                      value={stockAdjustReason}
                      onChange={(e) => setStockAdjustReason(e.target.value)}
                      required
                    >
                      <option value="Contagem Cíclica de Inventário">Contagem Cíclica de Inventário</option>
                      <option value="Balanço Físico Mensal/Anual">Balanço Físico Mensal/Anual</option>
                      <option value="Correção de Divergência de Lançamento">Correção de Divergência de Lançamento</option>
                      <option value="Inventário de Implantação de Almoxarifado">Inventário de Implantação</option>
                    </select>
                  </div>
                </div>

                <div className="form-row cols-1">
                  <div className="form-group">
                    <label>Nome do Auditor / Responsável pela Contagem <span className="req">*</span></label>
                    <input
                      type="text"
                      value={stockAdjustAuditor}
                      onChange={(e) => setStockAdjustAuditor(e.target.value)}
                      placeholder="Ex: Auditor João Silva - Almoxarifado Central"
                      required
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label>Parecer da Auditoria & Justificativa</label>
                  <textarea
                    value={stockAdjustNotes}
                    onChange={(e) => setStockAdjustNotes(e.target.value)}
                    placeholder="Observações do auditor sobre a contagem física e verificação de prateleiras..."
                    rows={2}
                  />
                </div>
              </>
            );
          })()}

          <div className="modal-footer">
            <button
              type="button"
              className="btn-cancel"
              onClick={() => setIsStockAdjustModalOpen(false)}
            >
              Cancelar
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={isSaving}
            >
              {isSaving ? <Loader2 size={16} className="spinning" /> : <Check size={16} />}
              <span>
                {stockAdjustType === 'invoice_entry' && 'Registrar Entrada com NF'}
                {stockAdjustType === 'manual_loss' && 'Registrar Baixa Técnica'}
                {stockAdjustType === 'reconciliation' && 'Salvar Conciliação de Inventário'}
              </span>
            </button>
          </div>
        </form>
      </Modal>


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

export default Inventory;

