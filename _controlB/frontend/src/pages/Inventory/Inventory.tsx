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
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  Package, Tags, History, Plus, Search, RefreshCw,
  Trash2, SlidersHorizontal, AlertTriangle, ArrowDownRight,
  ArrowUpRight, Check, Loader2, Sparkles, DollarSign,
  ChevronRight, CheckCircle2, ShieldCheck, FileText, Paperclip,
  UploadCloud, X, Scale, FileSpreadsheet, TrendingUp, TrendingDown,
  CheckCircle, ArrowUpDown, ArrowUp, ArrowDown, Download,
  CheckSquare, Warehouse, Zap
} from 'lucide-react';

import { inventoryService, cacheManager, formatApiError } from '@/services/api';
import {
  Product,
  ProductCategory,
  StockMovement,
  InventoryImportSummaryResponse,
  InventoryImportBatch,
  InventoryImportBatchListItem,
  StagnantInventoryReport
} from '@/types';
import { formatCurrency, formatQuantity, formatPriceInput, formatQuantityInput } from '@/utils/formatters';
import { Modal } from '@/components/Modal/Modal';
import { ConfirmModal } from '@/components/ConfirmModal/ConfirmModal';
import { InventoryStoragePanel } from './InventoryStoragePanel';
import { BulkActionsBar } from '@/components/BulkActionsBar';
import { ListPagination } from '@/components/ListPagination';
import { useBulkSelection } from '@/hooks/useBulkSelection';
import { useListPagination } from '@/hooks/useListPagination';
import { DocumentLink, RecordLink, useRecordDeepLink, isRequestedView } from '@/components/RecordLink';
import { useToast } from '@/components/Toast/ToastContext';
import './Inventory.scss';

const ALLOWED_INVENTORY_MENUS = ['produtos', 'categorias', 'armazenagem', 'movimentacoes', 'auditoria', 'integracoes'] as const;
type InventoryMenuOption = typeof ALLOWED_INVENTORY_MENUS[number];
type StockStatusFilter = 'todos' | 'criticos' | 'zerados' | 'regulares';

export const Inventory: React.FC = () => {
  const toast = useToast();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initialInventoryMenu = isRequestedView(searchParams, ALLOWED_INVENTORY_MENUS, 'produtos');
  const [activeMenu, setActiveMenu] = useState<InventoryMenuOption>(initialInventoryMenu);
  const [searchTerm, setSearchTerm] = useState('');
  const [searchField, setSearchField] = useState<'all' | 'name' | 'sku' | 'external_code' | 'barcode' | 'ncm' | 'brand' | 'location'>('all');
  const [selectedCategoryFilter, setSelectedCategoryFilter] = useState<string>('');
  const [stockStatusFilter, setStockStatusFilter] = useState<StockStatusFilter>('todos');

  // Seleção em Massa & Exportação
  const [selectedProductIds, setSelectedProductIds] = useState<Set<string>>(new Set());
  const categorySelection = useBulkSelection<ProductCategory>();

  // Ordenação Dinâmica (order_by) por Tabela
  const [prodSortField, setProdSortField] = useState<string>('name');
  const [prodSortDir, setProdSortDir] = useState<'asc' | 'desc'>('asc');

  const [catSortField, setCatSortField] = useState<string>('name');
  const [catSortDir, setCatSortDir] = useState<'asc' | 'desc'>('asc');

  const [movSortField, setMovSortField] = useState<string>('created_at');
  const [movSortDir, setMovSortDir] = useState<'asc' | 'desc'>('desc');

  const [auditSortField, setAuditSortField] = useState<string>('name');
  const [auditSortDir, setAuditSortDir] = useState<'asc' | 'desc'>('asc');

  // Estados dos Dados carregados da API
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<ProductCategory[]>([]);
  const [stockMovements, setStockMovements] = useState<StockMovement[]>([]);
  const [focusedMovementId, setFocusedMovementId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Estados de Auditoria de Lotes e Estagnação
  const [auditSubTab, setAuditSubTab] = useState<'balanco' | 'lotes' | 'estagnado'>('balanco');
  const [importBatches, setImportBatches] = useState<InventoryImportBatchListItem[]>([]);
  const [stagnantReport, setStagnantReport] = useState<StagnantInventoryReport | null>(null);
  const [selectedBatchDetail, setSelectedBatchDetail] = useState<InventoryImportBatch | null>(null);
  const [loadingBatchDetail, setLoadingBatchDetail] = useState(false);
  const [batchModalFilter, setBatchModalFilter] = useState<'all' | 'prices' | 'sales' | 'stagnant' | 'entries'>('all');
  const [batchModalSearch, setBatchModalSearch] = useState('');
  const [batchModalPage, setBatchModalPage] = useState(1);
  const batchModalPageSize = 50;

  // Modais de Criação & Edição
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // Modal de Importação de Estoque (.xlsx)
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [selectedImportFile, setSelectedImportFile] = useState<File | null>(null);
  const [isImportingFile, setIsImportingFile] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [importSummary, setImportSummary] = useState<InventoryImportSummaryResponse | null>(null);
  const [importSearchTerm, setImportSearchTerm] = useState('');

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
  const [productCostPrice, setProductCostPrice] = useState('0');
  const [productSalePrice, setProductSalePrice] = useState('0');
  const [productExternalCode, setProductExternalCode] = useState('');
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

  // Carregamento de Lotes e Estagnação
  const loadBatchesAndStagnation = async (forceRefresh = false) => {
    try {
      const [batchesData, stagnantData] = await Promise.all([
        inventoryService.getImportBatches(50, 0, forceRefresh).catch(() => []),
        inventoryService.getStagnantInventoryReport(forceRefresh).catch(() => null)
      ]);
      setImportBatches(Array.isArray(batchesData) ? batchesData : []);
      setStagnantReport(stagnantData);
    } catch (err: any) {
      console.error("Erro ao carregar lotes e relatório de estagnação:", err);
    }
  };

  const handleOpenBatchDetail = async (batchId: string) => {
    setLoadingBatchDetail(true);
    try {
      const detail = await inventoryService.getImportBatchDetail(batchId, true);
      setSelectedBatchDetail(detail);
      setBatchModalFilter('all');
      setBatchModalSearch('');
      setBatchModalPage(1);
    } catch (err: any) {
      toast.error(formatApiError(err, "Erro ao carregar detalhes do lote de importação."));
    } finally {
      setLoadingBatchDetail(false);
    }
  };

  const exportBatchAuditToCsv = (batch: InventoryImportBatch) => {
    const escapeCsvLocal = (val: any) => {
      if (val === null || val === undefined) return '""';
      const str = String(val).replace(/"/g, '""');
      return `"${str}"`;
    };

    const headers = [
      'Código',
      'Código de Barras (EAN)',
      'SKU',
      'Produto',
      'NCM',
      'Unidade',
      'Saldo Anterior',
      'Novo Saldo',
      'Variação Saldo',
      'Preço Custo Ant.',
      'Preço Custo Novo',
      'Variação Custo (%)',
      'Preço Venda Ant.',
      'Preço Venda Novo',
      'Variação Venda (%)',
      'Status Auditoria',
      'Impacto Financeiro (R$)'
    ];

    const rows = batch.items.map(it => [
      escapeCsvLocal(it.code),
      escapeCsvLocal(it.barcode || ''),
      escapeCsvLocal(it.sku || ''),
      escapeCsvLocal(it.name),
      escapeCsvLocal(it.ncm || ''),
      escapeCsvLocal(it.unit_of_measure),
      String(it.previous_stock).replace('.', ','),
      String(it.new_stock).replace('.', ','),
      String(it.delta_stock).replace('.', ','),
      it.previous_cost_price != null ? String(it.previous_cost_price).replace('.', ',') : '',
      String(it.new_cost_price).replace('.', ','),
      it.cost_variation_percent != null ? `${it.cost_variation_percent}%` : '0%',
      it.previous_sale_price != null ? String(it.previous_sale_price).replace('.', ',') : '',
      String(it.new_sale_price).replace('.', ','),
      it.sale_variation_percent != null ? `${it.sale_variation_percent}%` : '0%',
      escapeCsvLocal(
        it.action_type === 'created' ? 'Novo Cadastro' :
        it.action_type === 'sale_detected' ? 'Venda (Saída)' :
        it.action_type === 'entry_detected' ? 'Reposição (Entrada)' :
        it.action_type === 'stagnant_unchanged' ? 'Estoque Estagnado' : 'Saldo Zero'
      ),
      it.action_type === 'sale_detected' ? String(it.estimated_sales_revenue).replace('.', ',') :
      it.action_type === 'stagnant_unchanged' ? String(it.stagnant_value).replace('.', ',') : '0,00'
    ]);

    const csvContent = "\uFEFF" + [headers.join(';'), ...rows.map(r => r.join(';'))].join('\r\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `auditoria_lote_${batch.batch_number}_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleGenerateReplenishmentFromBatch = (batch: InventoryImportBatch) => {
    const itemsToReplenish = batch.items.filter(it => it.action_type === 'sale_detected' || Number(it.new_stock) <= 0);
    if (itemsToReplenish.length === 0) {
      toast.info("Não há itens esgotados ou com vendas apuradas neste lote que necessitem de reposição imediata.");
      return;
    }
    
    openConfirmModal({
      title: 'Gerar Reposição no Compras',
      subtitle: `Lote #${batch.batch_number}`,
      message: `Foram identificados ${itemsToReplenish.length} produto(s) com saída ou estoque zerado neste lote. Deseja abrir o módulo de Compras para gerar a reposição?`,
      confirmText: 'Ir para Compras',
      cancelText: 'Permanecer aqui',
      type: 'info',
      onConfirm: async () => {
        closeConfirmModal();
        navigate(`/compras?view=ordens&origin=audit_batch_${batch.batch_number}`);
      }
    });
  };

  const handleNavigateToKardexForBatch = (batch: InventoryImportBatch) => {
    setSelectedBatchDetail(null);
    setActiveMenu('movimentacoes');
    setSearchTerm(batch.inventory_date || batch.batch_number);
  };

  // Carregamento Inicial
  useEffect(() => {
    loadInventoryData();
  }, []);

  const loadInventoryData = async (forceRefresh = false) => {
    const cachedProds = cacheManager.get<Product[]>('inventory:products:all');
    if (!cachedProds && !products.length) {
      setLoading(true);
    } else if (forceRefresh) {
      setLoading(true);
    }

    try {
      const [prodData, catData, movData] = await Promise.all([
        inventoryService.getProducts(undefined, forceRefresh),
        inventoryService.getCategories(forceRefresh),
        inventoryService.getInventoryMovements(undefined, undefined, forceRefresh)
      ]);

      setProducts(Array.isArray(prodData) ? prodData : []);
      setCategories(Array.isArray(catData) ? catData : []);
      setStockMovements(Array.isArray(movData) ? movData : []);
      void loadBatchesAndStagnation(forceRefresh);
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
    onConfirm: async () => { },
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

  // Ações de Importação de Planilha de Estoque (.xlsx)
  const handleImportFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      if (!file.name.toLowerCase().endsWith('.xlsx')) {
        setImportError("Formato inválido. Por favor, selecione um arquivo Excel (.xlsx).");
        setSelectedImportFile(null);
        return;
      }
      setSelectedImportFile(file);
      setImportError(null);
    }
  };

  const handleProcessImport = async () => {
    if (!selectedImportFile) {
      setImportError("Selecione o arquivo da planilha para iniciar a importação.");
      return;
    }

    setIsImportingFile(true);
    setImportError(null);

    try {
      const summary = await inventoryService.importInventorySpreadsheet(selectedImportFile);
      setImportSummary(summary);
      await loadInventoryData();
    } catch (err: any) {
      console.error("Erro ao importar planilha de estoque:", err);
      setImportError(formatApiError(err));
    } finally {
      setIsImportingFile(false);
    }
  };

  // Ações de Produtos
  const handleEditProduct = (prod: Product) => {
    setEditingProduct(prod);
    setProductName(prod.name);
    setProductSku(prod.sku);
    setProductDesc(prod.description || '');
    setProductUnit(prod.unit_of_measure);
    setProductPrice(formatPriceInput(prod.reference_price));
    setProductCostPrice(formatPriceInput(prod.cost_price ?? prod.reference_price));
    setProductSalePrice(formatPriceInput(prod.sale_price));
    setProductExternalCode(prod.external_code || prod.toolspharma_code || '');
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
      setProductCostPrice('0');
      setProductSalePrice('0');
      setProductExternalCode('');
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
            reference_price: parseFloat(productPrice) || parseFloat(productCostPrice) || 0,
            cost_price: parseFloat(productCostPrice) || 0,
            sale_price: parseFloat(productSalePrice) || 0,
            external_code: productExternalCode || undefined,
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
            reference_price: parseFloat(productPrice) || parseFloat(productCostPrice) || 0,
            cost_price: parseFloat(productCostPrice) || 0,
            sale_price: parseFloat(productSalePrice) || 0,
            external_code: productExternalCode || undefined,
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
      let outboundReason: 'loss_damage' | 'internal_consumption' | 'supplier_return' | 'inventory_adjustment' | undefined;
      if (stockAdjustType === 'manual_loss') {
        if (stockAdjustReason.includes('Consumo Interno')) {
          outboundReason = 'internal_consumption';
        } else if (stockAdjustReason.includes('Devolução')) {
          outboundReason = 'supplier_return';
        } else if (stockAdjustReason.includes('Ajuste') || stockAdjustReason.includes('Operacional') || stockAdjustReason.includes('Descarte')) {
          outboundReason = 'inventory_adjustment';
        } else {
          outboundReason = 'loss_damage';
        }
      }

      await inventoryService.adjustInventoryStock({
        product_id: stockAdjustProduct.id,
        adjustment_type: stockAdjustType,
        outbound_reason: outboundReason,
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

  useRecordDeepLink({
    types: ['PRODUCT'],
    records: products,
    onOpen: (prod) => {
      setActiveMenu('produtos');
      handleEditProduct(prod);
    },
  });

  useRecordDeepLink({
    types: ['STOCK_MOVEMENT'],
    records: stockMovements,
    onOpen: (movement) => {
      setActiveMenu('movimentacoes');
      setSearchTerm('');
      setFocusedMovementId(movement.id);
    },
  });

  useRecordDeepLink({
    types: ['INVENTORY_RECEIPT'],
    records: stockMovements,
    getIds: (movement) => [movement.receipt_id],
    onOpen: (movement) => {
      setActiveMenu('movimentacoes');
      setSearchTerm('');
      setFocusedMovementId(movement.id);
    },
  });

  useRecordDeepLink({
    types: ['INVENTORY_IMPORT_BATCH'],
    records: importBatches,
    onOpen: (batch) => {
      setActiveMenu('auditoria');
      setAuditSubTab('lotes');
      void handleOpenBatchDetail(batch.id);
    },
  });





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

  // Handlers de Ordenação
  const handleProdSort = (field: string) => {
    if (prodSortField === field) {
      setProdSortDir(prev => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setProdSortField(field);
      setProdSortDir('asc');
    }
  };

  const handleCatSort = (field: string) => {
    if (catSortField === field) {
      setCatSortDir(prev => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setCatSortField(field);
      setCatSortDir('asc');
    }
  };

  const handleMovSort = (field: string) => {
    if (movSortField === field) {
      setMovSortDir(prev => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setMovSortField(field);
      setMovSortDir('asc');
    }
  };

  const handleAuditSort = (field: string) => {
    if (auditSortField === field) {
      setAuditSortDir(prev => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setAuditSortField(field);
      setAuditSortDir('asc');
    }
  };

  // Exportação para Planilha CSV formatada
  const exportProductsToCsv = (itemsToExport: Product[] = products, filenameSuffix: string = 'catalogo') => {
    if (!itemsToExport || itemsToExport.length === 0) {
      toast.warning("Nenhum produto disponível para exportação.");
      return;
    }

    const headers = [
      "ID",
      "Código Legado / Externo",
      "SKU",
      "Código de Barras (EAN)",
      "Nome do Produto",
      "Categoria",
      "Marca",
      "NCM",
      "Saldo Físico",
      "Unidade",
      "Preço Custo (R$)",
      "Preço Venda (R$)",
      "Preço Referência (R$)",
      "Estoque Mínimo",
      "Estoque Máximo",
      "Localização",
      "Perecível",
      "Exige Lote",
      "Status Estoque"
    ];

    const escapeCsv = (val: any) => {
      if (val === null || val === undefined) return '';
      const str = String(val).replace(/"/g, '""');
      return `"${str}"`;
    };

    const rows = itemsToExport.map(p => {
      const cur = Number(p.current_stock || 0);
      const min = Number(p.min_stock || 0);
      let statusStr = "Regular";
      if (cur <= 0) statusStr = "Zerado";
      else if (cur <= min) statusStr = "Crítico";

      return [
        escapeCsv(p.id),
        escapeCsv(p.external_code || p.toolspharma_code || ''),
        escapeCsv(p.sku),
        escapeCsv(p.barcode || ''),
        escapeCsv(p.name),
        escapeCsv(p.category?.name || ''),
        escapeCsv(p.brand || ''),
        escapeCsv(p.ncm || ''),
        escapeCsv(cur.toFixed(2).replace('.', ',')),
        escapeCsv(p.unit_of_measure),
        escapeCsv(Number(p.cost_price || p.reference_price || 0).toFixed(2).replace('.', ',')),
        escapeCsv(Number(p.sale_price || 0).toFixed(2).replace('.', ',')),
        escapeCsv(Number(p.reference_price || 0).toFixed(2).replace('.', ',')),
        escapeCsv(min.toFixed(2).replace('.', ',')),
        escapeCsv(p.max_stock ? Number(p.max_stock).toFixed(2).replace('.', ',') : ''),
        escapeCsv(p.storage_location || ''),
        escapeCsv(p.is_perishable ? 'Sim' : 'Não'),
        escapeCsv(p.requires_batch ? 'Sim' : 'Não'),
        escapeCsv(statusStr)
      ].join(';');
    });

    const csvContent = '\uFEFF' + [headers.join(';'), ...rows].join('\r\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    const dateStr = new Date().toISOString().slice(0, 10);
    link.setAttribute('href', url);
    link.setAttribute('download', `controlb_estoque_${filenameSuffix}_${dateStr}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  // Exclusão em Massa de Produtos Selecionados
  const handleBulkDeleteProducts = () => {
    if (selectedProductIds.size === 0) return;
    const count = selectedProductIds.size;

    openConfirmModal({
      title: `Excluir ${count} Produtos Selecionados`,
      subtitle: 'Esta ação removerá permanentemente os produtos selecionados e suas respectivas fichas de estoque.',
      type: 'danger',
      message: (
        <>
          Você selecionou <strong>{count} produtos</strong> para exclusão definitiva.
          <div className="alert-callout" style={{ marginTop: '0.75rem' }}>
            <strong>Atenção:</strong> Esta operação é irreversível e excluirá o histórico direto vinculado a estes produtos.
          </div>
        </>
      ),
      confirmText: `Sim, Excluir ${count} Produtos`,
      onConfirm: async () => {
        setConfirmModal(prev => ({ ...prev, isLoading: true, errorMessage: null }));
        try {
          const ids = Array.from(selectedProductIds);
          for (const id of ids) {
            await inventoryService.deleteProduct(id);
          }
          setSelectedProductIds(new Set());
          await loadInventoryData();
          closeConfirmModal();
        } catch (err: any) {
          setConfirmModal(prev => ({
            ...prev,
            isLoading: false,
            errorMessage: err?.response?.data?.detail || 'Erro ao excluir produtos selecionados.'
          }));
        }
      }
    });
  };

  // Filtros Avançados & Ordenação de Produtos
  const filteredProducts = (products || []).filter(p => {
    const term = searchTerm.trim().toLowerCase();
    let matchesSearch = true;

    if (term) {
      if (searchField === 'all') {
        matchesSearch = (
          p.name.toLowerCase().includes(term) ||
          p.sku.toLowerCase().includes(term) ||
          Boolean(p.external_code && p.external_code.toLowerCase().includes(term)) ||
          Boolean(p.toolspharma_code && p.toolspharma_code.toLowerCase().includes(term)) ||
          Boolean(p.barcode && p.barcode.toLowerCase().includes(term)) ||
          Boolean(p.ncm && p.ncm.toLowerCase().includes(term)) ||
          Boolean(p.brand && p.brand.toLowerCase().includes(term)) ||
          Boolean(p.storage_location && p.storage_location.toLowerCase().includes(term))
        );
      } else if (searchField === 'name') {
        matchesSearch = p.name.toLowerCase().includes(term);
      } else if (searchField === 'sku') {
        matchesSearch = p.sku.toLowerCase().includes(term);
      } else if (searchField === 'external_code') {
        matchesSearch = Boolean(
          (p.external_code && p.external_code.toLowerCase().includes(term)) ||
          (p.toolspharma_code && p.toolspharma_code.toLowerCase().includes(term))
        );
      } else if (searchField === 'barcode') {
        matchesSearch = Boolean(p.barcode && p.barcode.toLowerCase().includes(term));
      } else if (searchField === 'ncm') {
        matchesSearch = Boolean(p.ncm && p.ncm.toLowerCase().includes(term));
      } else if (searchField === 'brand') {
        matchesSearch = Boolean(p.brand && p.brand.toLowerCase().includes(term));
      } else if (searchField === 'location') {
        matchesSearch = Boolean(p.storage_location && p.storage_location.toLowerCase().includes(term));
      }
    }

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
  }).sort((a, b) => {
    let valA: any = '';
    let valB: any = '';

    if (prodSortField === 'name') {
      valA = a.name.toLowerCase();
      valB = b.name.toLowerCase();
    } else if (prodSortField === 'sku') {
      valA = a.sku.toLowerCase();
      valB = b.sku.toLowerCase();
    } else if (prodSortField === 'external_code') {
      valA = a.external_code || a.toolspharma_code || '';
      valB = b.external_code || b.toolspharma_code || '';
    } else if (prodSortField === 'category') {
      valA = a.category?.name?.toLowerCase() || '';
      valB = b.category?.name?.toLowerCase() || '';
    } else if (prodSortField === 'cost_price') {
      valA = Number(a.cost_price || a.reference_price || 0);
      valB = Number(b.cost_price || b.reference_price || 0);
    } else if (prodSortField === 'sale_price') {
      valA = Number(a.sale_price || 0);
      valB = Number(b.sale_price || 0);
    } else if (prodSortField === 'current_stock') {
      valA = Number(a.current_stock || 0);
      valB = Number(b.current_stock || 0);
    } else if (prodSortField === 'storage_location') {
      valA = a.storage_location?.toLowerCase() || '';
      valB = b.storage_location?.toLowerCase() || '';
    }

    if (valA < valB) return prodSortDir === 'asc' ? -1 : 1;
    if (valA > valB) return prodSortDir === 'asc' ? 1 : -1;
    return 0;
  });

  const filteredCategories = (categories || []).filter(c =>
    c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (c.code && c.code.toLowerCase().includes(searchTerm.toLowerCase()))
  ).sort((a, b) => {
    let valA: any = '';
    let valB: any = '';
    if (catSortField === 'name') {
      valA = a.name.toLowerCase();
      valB = b.name.toLowerCase();
    } else if (catSortField === 'code') {
      valA = (a.code || '').toLowerCase();
      valB = (b.code || '').toLowerCase();
    }
    if (valA < valB) return catSortDir === 'asc' ? -1 : 1;
    if (valA > valB) return catSortDir === 'asc' ? 1 : -1;
    return 0;
  });

  const filteredMovements = (stockMovements || []).filter(m => {
    if (focusedMovementId) return m.id === focusedMovementId;
    return (
      (m.product_name && m.product_name.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (m.sku && m.sku.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (m.reference_doc && m.reference_doc.toLowerCase().includes(searchTerm.toLowerCase()))
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
  const productPagination = useListPagination(filteredProducts);
  const categoryPagination = useListPagination(filteredCategories);
  const movementPagination = useListPagination(filteredMovements);
  const auditProductPagination = useListPagination(filteredProducts);
  const divergencePagination = useListPagination(totalDivergenceMovements);
  const arePageProductsSelected = productPagination.pageItems.length > 0 && productPagination.pageItems.every(product => selectedProductIds.has(product.id));

  const handleBulkDeleteCategories = () => {
    const ids = categorySelection.selectedIdList;
    if (ids.length === 0) return;
    openConfirmModal({
      title: 'Excluir Categorias em Lote',
      subtitle: `${ids.length} categoria(s) selecionada(s)`,
      message: `Deseja realmente excluir ${ids.length} categoria(s) selecionada(s)? Categorias vinculadas a produtos serão preservadas pela regra do cadastro.`,
      confirmText: `Excluir (${ids.length})`,
      type: 'danger',
      onConfirm: async () => {
        const results = await Promise.allSettled(ids.map(id => inventoryService.deleteCategory(id)));
        const succeeded = results.filter(result => result.status === 'fulfilled').length;
        const failed = results.length - succeeded;
        categorySelection.clearSelection();
        closeConfirmModal();
        await loadInventoryData(true);
        if (failed > 0) {
          toast.warning(`${succeeded} categoria(s) excluída(s); ${failed} possuem vínculos ou não puderam ser removidas.`);
        } else {
          toast.success(`${succeeded} categoria(s) excluída(s) com sucesso.`);
        }
      }
    });
  };

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
              className={`nav-item ${activeMenu === 'armazenagem' ? 'active' : ''}`}
              onClick={() => { setActiveMenu('armazenagem'); setSearchTerm(''); }}
            >
              <div className="nav-item-content">
                <Warehouse size={16} />
                <span>Armazenagem Física</span>
              </div>
              <span className="nav-badge">Locais</span>
            </button>

            <button
              className={`nav-item ${activeMenu === 'movimentacoes' ? 'active' : ''}`}
              onClick={() => { setActiveMenu('movimentacoes'); setFocusedMovementId(null); setSearchTerm(''); }}
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

            <button
              className={`nav-item ${activeMenu === 'integracoes' ? 'active' : ''}`}
              onClick={() => { setActiveMenu('integracoes'); setSearchTerm(''); }}
            >
              <div className="nav-item-content">
                <RefreshCw size={16} />
                <span>Integrações Diretas</span>
              </div>
              <span className="nav-badge" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', borderColor: 'rgba(16, 185, 129, 0.3)' }}>
                1 ativa
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
                  {activeMenu === 'armazenagem' && 'Localizações, Saldos & Transferências'}
                  {activeMenu === 'movimentacoes' && 'Histórico de Movimentações de Estoque'}
                  {activeMenu === 'auditoria' && 'Auditoria & Inventário Físico'}
                  {activeMenu === 'integracoes' && 'Canais de Integração & Sincronização'}
                </span>
              </div>
              <h1 className="section-title">
                {activeMenu === 'produtos' && 'Catálogo de Produtos, Insumos & Almoxarifado'}
                {activeMenu === 'categorias' && 'Categorias e Grupos de Produtos'}
                {activeMenu === 'armazenagem' && 'Armazenagem Física & Transferências Internas'}
                {activeMenu === 'movimentacoes' && 'Extrato & Auditoria de Movimentações de Estoque'}
                {activeMenu === 'auditoria' && 'Painel de Auditoria & Balanço Físico de Estoque'}
                {activeMenu === 'integracoes' && 'Canais de Integração & Sincronização de Estoque'}
              </h1>
            </div>

            <div className="header-actions">
              <button
                className="btn-refresh"
                onClick={() => loadInventoryData(true)}
                disabled={loading}
                title="Recarregar Dados"
              >
                <RefreshCw size={15} className={loading ? 'spinning' : ''} />
              </button>

              <button
                className="btn-secondary btn-inventory-import"
                onClick={() => {
                  setIsImportModalOpen(true);
                  setSelectedImportFile(null);
                  setImportError(null);
                  setImportSummary(null);
                  setImportSearchTerm('');
                }}
                title="Importar carga de estoque via planilha Excel (.xlsx)"
              >
                <UploadCloud size={16} />
                <span>Importar Planilha</span>
              </button>

              {(activeMenu === 'produtos' || activeMenu === 'categorias') && (
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

          {activeMenu === 'armazenagem' ? (
            <InventoryStoragePanel products={products} />
          ) : (
          <>
          {activeMenu !== 'integracoes' && <>
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
            <div className="search-box-composite">
              <select
                className="search-field-select"
                value={searchField}
                onChange={(e) => setSearchField(e.target.value as any)}
                title="Filtrar pesquisa por campo específico"
              >
                <option value="all">Todos os Campos</option>
                <option value="name">Nome do Produto</option>
                <option value="sku">SKU</option>
                <option value="external_code">Código Legado / Externo</option>
                <option value="barcode">Código de Barras (EAN)</option>
                <option value="ncm">NCM</option>
                <option value="brand">Marca / Fabricante</option>
                <option value="location">Localização Física</option>
              </select>

              <div className="search-box">
                <Search className="search-icon" size={16} />
                <input
                  type="text"
                  placeholder={
                    searchField === 'all' ? `Pesquisar em ${activeMenu}... (nome, SKU, marca, EAN)` :
                    searchField === 'name' ? 'Pesquisar por nome do produto...' :
                    searchField === 'sku' ? 'Pesquisar por código SKU...' :
                    searchField === 'external_code' ? 'Pesquisar por código externo / legado...' :
                    searchField === 'barcode' ? 'Pesquisar por código de barras (EAN-13)...' :
                    searchField === 'ncm' ? 'Pesquisar por classificação fiscal NCM...' :
                    searchField === 'brand' ? 'Pesquisar por marca / fabricante...' :
                    'Pesquisar por localização física...'
                  }
                  value={searchTerm}
                  onChange={(e) => {
                    setFocusedMovementId(null);
                    setSearchTerm(e.target.value);
                  }}
                />
                {searchTerm && (
                  <button type="button" className="btn-clear-search" onClick={() => { setFocusedMovementId(null); setSearchTerm(''); }} title="Limpar busca">
                    <X size={14} />
                  </button>
                )}
              </div>
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

                {/* Botão Exportar Tudo */}
                <button
                  type="button"
                  className="btn-export-all"
                  onClick={() => exportProductsToCsv(filteredProducts, 'filtrado')}
                  title="Exportar produtos listados para CSV / Excel"
                >
                  <Download size={14} />
                  <span>Exportar ({filteredProducts.length})</span>
                </button>
              </div>
            )}

            <div className="results-count">
              {activeMenu === 'produtos' && `${filteredProducts.length} produtos listados`}
              {activeMenu === 'categorias' && `${filteredCategories.length} categorias listadas`}
              {activeMenu === 'movimentacoes' && `${filteredMovements.length} movimentações listadas`}
              {activeMenu === 'auditoria' && `${filteredProducts.length} itens no inventário`}
            </div>
          </div>
          </>}

          {/* BARRA DE AÇÕES EM MASSA FLUTUANTE / INTEGRADA */}
          {activeMenu === 'produtos' && selectedProductIds.size > 0 && (
            <div className="bulk-actions-toolbar">
              <div className="bulk-info">
                <CheckSquare size={16} className="bulk-icon" />
                <span><strong>{selectedProductIds.size}</strong> {selectedProductIds.size === 1 ? 'produto selecionado' : 'produtos selecionados'}</span>
              </div>
              <div className="bulk-buttons">
                <button
                  type="button"
                  className="btn-bulk-export"
                  onClick={() => {
                    const selectedList = products.filter(p => selectedProductIds.has(p.id));
                    exportProductsToCsv(selectedList, 'selecionados');
                  }}
                  title="Exportar itens selecionados para planilha CSV / Excel"
                >
                  <Download size={14} />
                  <span>Exportar Selecionados ({selectedProductIds.size})</span>
                </button>

                <button
                  type="button"
                  className="btn-bulk-delete"
                  onClick={handleBulkDeleteProducts}
                  title="Excluir permanentemente os itens selecionados"
                >
                  <Trash2 size={14} />
                  <span>Excluir Selecionados</span>
                </button>

                <button
                  type="button"
                  className="btn-bulk-clear"
                  onClick={() => setSelectedProductIds(new Set())}
                  title="Desmarcar todos"
                >
                  <X size={14} />
                  <span>Desmarcar</span>
                </button>
              </div>
            </div>
          )}

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
                  <>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th style={{ width: '40px', textAlign: 'center' }}>
                          <input
                            type="checkbox"
                            checked={arePageProductsSelected}
                            onChange={(e) => {
                              setSelectedProductIds(previous => {
                                const next = new Set(previous);
                                productPagination.pageItems.forEach(product => e.target.checked ? next.add(product.id) : next.delete(product.id));
                                return next;
                              });
                            }}
                            title={arePageProductsSelected ? "Desmarcar esta página" : "Selecionar esta página"}
                          />
                        </th>
                        <th className="th-sortable" onClick={() => handleProdSort('name')}>
                          <div className="th-content">
                            <span>Produto & SKU</span>
                            {prodSortField === 'name' ? (prodSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                          </div>
                        </th>
                        <th className="th-sortable" onClick={() => handleProdSort('category')}>
                          <div className="th-content">
                            <span>Categoria</span>
                            {prodSortField === 'category' ? (prodSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                          </div>
                        </th>
                        <th className="th-sortable" onClick={() => handleProdSort('cost_price')}>
                          <div className="th-content">
                            <span>Custo / Venda</span>
                            {prodSortField === 'cost_price' ? (prodSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                          </div>
                        </th>
                        <th className="th-sortable" onClick={() => handleProdSort('current_stock')}>
                          <div className="th-content">
                            <span>Nível de Estoque (Físico)</span>
                            {prodSortField === 'current_stock' ? (prodSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                          </div>
                        </th>
                        <th className="th-sortable" onClick={() => handleProdSort('storage_location')}>
                          <div className="th-content">
                            <span>Localização</span>
                            {prodSortField === 'storage_location' ? (prodSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                          </div>
                        </th>
                        <th>Rastreabilidade</th>
                        <th className="th-actions">Ações</th>
                      </tr>
                    </thead>
                    <tbody>
                      {productPagination.pageItems.map((prod) => {
                        const isSelected = selectedProductIds.has(prod.id);
                        const cur = Number(prod.current_stock || 0);
                        const min = Number(prod.min_stock || 0);
                        const max = prod.max_stock ? Number(prod.max_stock) : Math.max(min * 2, cur * 1.5, 50);
                        const isZero = cur <= 0;
                        const isLow = cur <= min && !isZero;
                        const stockPercent = Math.min(100, Math.max(0, (cur / max) * 100));

                        return (
                          <tr key={prod.id} className={`${isZero ? 'row-zero' : isLow ? 'row-low' : ''} ${isSelected ? 'row-selected' : ''} ui-record-row`} role="button" tabIndex={0} onClick={(event) => { if (!(event.target as HTMLElement).closest('button, a, input, label')) handleEditProduct(prod); }} onKeyDown={(event) => { if (['Enter', ' '].includes(event.key)) { event.preventDefault(); handleEditProduct(prod); } }}>
                            <td style={{ textAlign: 'center' }}>
                              <input
                                type="checkbox"
                                checked={isSelected}
                                onChange={() => {
                                  setSelectedProductIds(prev => {
                                    const next = new Set(prev);
                                    if (next.has(prod.id)) next.delete(prod.id);
                                    else next.add(prod.id);
                                    return next;
                                  });
                                }}
                              />
                            </td>
                            <td>
                              <div className="product-title-cell">
                                <RecordLink type="PRODUCT" id={prod.id}>
                                  <strong className="product-name">{prod.name}</strong>
                                </RecordLink>
                                <div className="tags-row">
                                  <span className="sku-tag">SKU: {prod.sku}</span>
                                  {(prod.external_code || prod.toolspharma_code) && (
                                    <span className="external-code-tag" title="Código de produto no sistema legado / externo">
                                      CÓD: {prod.external_code || prod.toolspharma_code}
                                    </span>
                                  )}
                                  {prod.barcode && <span className="barcode-tag" title="Código de barras EAN-13">EAN: {prod.barcode}</span>}
                                  {prod.brand && <span className="brand-tag">{prod.brand}</span>}
                                </div>
                              </div>
                            </td>
                            <td>
                              <span className="category-pill">
                                {prod.category?.name || 'Geral'}
                              </span>
                            </td>
                            <td>
                              <div className="price-stack">
                                <span className="cost-val" title="Custo Unitário de Aquisição">
                                  Custo: {formatCurrency(prod.cost_price || prod.reference_price)}
                                </span>
                                {Boolean(prod.sale_price && Number(prod.sale_price) > 0) && (
                                  <strong className="sale-val" title="Preço de Venda ao Consumidor">
                                    Venda: {formatCurrency(prod.sale_price!)}
                                  </strong>
                                )}
                              </div>
                            </td>
                            <td>
                              <div className="stock-visual-cell">
                                <div className="stock-header-info">
                                  <span className={`stock-status-badge ${isZero ? 'danger' : isLow ? 'warning' : 'ok'}`}>
                                    {isZero ? 'ZERADO' : isLow ? 'CRÍTICO' : 'REGULAR'}
                                  </span>
                                  <span className="stock-numbers">
                                    <strong>{formatQuantity(cur)}</strong> / {formatQuantity(min)} {prod.unit_of_measure}
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
                  <ListPagination {...productPagination} onPageChange={productPagination.setPage} onPageSizeChange={productPagination.setPageSize} />
                  </>
                )}
              </>
            )}

            {/* TABELA DE CATEGORIAS */}
            {activeMenu === 'categorias' && (
              <>
                <BulkActionsBar selectedCount={categorySelection.selectedCount} resourceName={{ singular: 'categoria', plural: 'categorias' }} onClear={categorySelection.clearSelection} onDelete={() => void handleBulkDeleteCategories()} deleteLabel="Excluir selecionadas" />
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
                  <>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th className="ui-selection-cell"><input className="ui-selection-checkbox" type="checkbox" aria-label="Selecionar categorias desta página" checked={categorySelection.isAllSelected(categoryPagination.pageItems)} onChange={() => categorySelection.toggleSelectAll(categoryPagination.pageItems)} /></th>
                        <th className="th-sortable" onClick={() => handleCatSort('code')}>
                          <div className="th-content">
                            <span>Código / Prefixo</span>
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
                        <th className="th-actions">Ações</th>
                      </tr>
                    </thead>
                    <tbody>
                      {categoryPagination.pageItems.map((cat) => (
                        <tr key={cat.id} className={`ui-record-row ${categorySelection.isSelected(cat.id) ? 'ui-record-row--selected' : ''}`} role="button" tabIndex={0} onClick={(event) => { if (!(event.target as HTMLElement).closest('button, a, input')) handleEditCategory(cat); }} onKeyDown={(event) => { if (['Enter', ' '].includes(event.key)) { event.preventDefault(); handleEditCategory(cat); } }}>
                          <td className="ui-selection-cell"><input className="ui-selection-checkbox" type="checkbox" aria-label={`Selecionar categoria ${cat.name}`} checked={categorySelection.isSelected(cat.id)} onClick={(event) => event.stopPropagation()} onChange={() => categorySelection.toggleSelect(cat.id)} /></td>
                          <td><span className="code-tag">{cat.code || '-'}</span></td>
                          <td><strong>{cat.name}</strong></td>
                          <td>{cat.description || '-'}</td>
                          <td>
                            <div className="actions-cell">
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
                  <ListPagination {...categoryPagination} onPageChange={categoryPagination.setPage} onPageSizeChange={categoryPagination.setPageSize} />
                  </>
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
                  <>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th className="th-sortable" onClick={() => handleMovSort('created_at')}>
                          <div className="th-content">
                            <span>Data / Hora</span>
                            {movSortField === 'created_at' ? (movSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                          </div>
                        </th>
                        <th className="th-sortable" onClick={() => handleMovSort('product')}>
                          <div className="th-content">
                            <span>Produto</span>
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
                            <span>Qtd</span>
                            {movSortField === 'quantity' ? (movSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                          </div>
                        </th>
                        <th className="th-sortable" onClick={() => handleMovSort('unit_cost')}>
                          <div className="th-content">
                            <span>Custo Unit.</span>
                            {movSortField === 'unit_cost' ? (movSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                          </div>
                        </th>
                        <th className="th-sortable" onClick={() => handleMovSort('balance_after')}>
                          <div className="th-content">
                            <span>Saldo Resultante</span>
                            {movSortField === 'balance_after' ? (movSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                          </div>
                        </th>
                        <th>Documento de Referência</th>
                      </tr>
                    </thead>
                    <tbody>
                      {movementPagination.pageItems.map((mov) => {
                        const isPositive = mov.movement_type.startsWith('in_');
                        return (
                          <tr key={mov.id} className={focusedMovementId === mov.id ? 'ui-record-row is-focused' : undefined}>
                            <td>
                              <div className="time-cell">
                                <strong>{new Date(mov.created_at).toLocaleDateString('pt-BR')}</strong>
                                <span className="sub-label">{new Date(mov.created_at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}</span>
                              </div>
                            </td>
                            <td>
                              <RecordLink type="PRODUCT" id={mov.product_id}>
                                <strong>{mov.product_name || mov.product?.name || 'Produto'}</strong>
                              </RecordLink>
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
                              {mov.movement_type === 'in_return_customer' && (
                                <span className="movement-badge in-adj" style={{ background: 'rgba(16, 185, 129, 0.12)', color: '#10b981', borderColor: 'rgba(16, 185, 129, 0.3)' }}>
                                  <ArrowDownRight size={13} /> Devolução de Cliente (+)
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
                              {mov.movement_type === 'out_internal_consumption' && (
                                <span className="movement-badge out-loss" style={{ background: 'rgba(245, 158, 11, 0.12)', color: '#f59e0b', borderColor: 'rgba(245, 158, 11, 0.3)' }}>
                                  <ArrowUpRight size={13} /> Consumo Interno / Uso (-)
                                </span>
                              )}
                              {mov.movement_type === 'out_return_supplier' && (
                                <span className="movement-badge out-adj" style={{ background: 'rgba(99, 102, 241, 0.12)', color: '#6366f1', borderColor: 'rgba(99, 102, 241, 0.3)' }}>
                                  <ArrowUpRight size={13} /> Devolução a Fornecedor (-)
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
                                {isPositive ? '+' : '-'}{formatQuantity(mov.quantity)} {mov.unit_of_measure || mov.product?.unit_of_measure || 'UN'}
                              </strong>
                            </td>
                            <td>{formatCurrency(mov.unit_cost)}</td>
                            <td>
                              <span className="balance-tag">
                                {formatQuantity(mov.balance_after)} {mov.unit_of_measure || mov.product?.unit_of_measure || 'UN'}
                              </span>
                            </td>
                            <td>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                                <DocumentLink documentId={mov.document_id} showIcon={false}>
                                  <span className="code-tag">{mov.reference_doc || 'Abrir origem'}</span>
                                </DocumentLink>
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
                  <ListPagination {...movementPagination} onPageChange={movementPagination.setPage} onPageSizeChange={movementPagination.setPageSize} />
                  </>
                )}
              </>
            )}

            {/* ================================================================= */}
            {/* VIEW: AUDITORIA, LOTES DE IMPORTAÇÃO & CAPITAL ESTAGNADO        */}
            {/* ================================================================= */}
            {activeMenu === 'auditoria' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                {/* SUB-TABS NAVIGATION DE AUDITORIA */}
                <div style={{ display: 'flex', gap: '0.6rem', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.75rem' }}>
                  <button
                    type="button"
                    onClick={() => setAuditSubTab('balanco')}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.45rem',
                      padding: '0.5rem 1rem',
                      borderRadius: '6px',
                      border: '1px solid',
                      borderColor: auditSubTab === 'balanco' ? '#10b981' : 'var(--border-subtle)',
                      background: auditSubTab === 'balanco' ? 'rgba(16, 185, 129, 0.12)' : 'var(--bg-surface)',
                      color: auditSubTab === 'balanco' ? '#10b981' : 'var(--text-secondary)',
                      fontWeight: 600,
                      fontSize: '0.85rem',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    <Scale size={15} />
                    <span>Balanço Físico por SKU</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setAuditSubTab('lotes');
                      void loadBatchesAndStagnation();
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.45rem',
                      padding: '0.5rem 1rem',
                      borderRadius: '6px',
                      border: '1px solid',
                      borderColor: auditSubTab === 'lotes' ? '#3b82f6' : 'var(--border-subtle)',
                      background: auditSubTab === 'lotes' ? 'rgba(59, 130, 246, 0.12)' : 'var(--bg-surface)',
                      color: auditSubTab === 'lotes' ? '#3b82f6' : 'var(--text-secondary)',
                      fontWeight: 600,
                      fontSize: '0.85rem',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    <FileSpreadsheet size={15} />
                    <span>Histórico de Lotes Importados ({importBatches.length})</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setAuditSubTab('estagnado');
                      void loadBatchesAndStagnation();
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.45rem',
                      padding: '0.5rem 1rem',
                      borderRadius: '6px',
                      border: '1px solid',
                      borderColor: auditSubTab === 'estagnado' ? '#f59e0b' : 'var(--border-subtle)',
                      background: auditSubTab === 'estagnado' ? 'rgba(245, 158, 11, 0.12)' : 'var(--bg-surface)',
                      color: auditSubTab === 'estagnado' ? '#f59e0b' : 'var(--text-secondary)',
                      fontWeight: 600,
                      fontSize: '0.85rem',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    <AlertTriangle size={15} />
                    <span>Radar de Estoque Estagnado & Capital Parado</span>
                  </button>
                </div>

                {/* ============================================================= */}
                {/* SUB-ABA 1: BALANÇO FÍSICO POR SKU                             */}
                {/* ============================================================= */}
                {auditSubTab === 'balanco' && (
                  <>
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
                            <th className="th-sortable" onClick={() => handleAuditSort('name')}>
                              <div className="th-content">
                                <span>Produto / SKU</span>
                                {auditSortField === 'name' ? (auditSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                              </div>
                            </th>
                            <th>Categoria</th>
                            <th className="th-sortable" onClick={() => handleAuditSort('storage_location')}>
                              <div className="th-content">
                                <span>Localização</span>
                                {auditSortField === 'storage_location' ? (auditSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                              </div>
                            </th>
                            <th className="th-sortable" onClick={() => handleAuditSort('current_stock')}>
                              <div className="th-content">
                                <span>Saldo Sistema</span>
                                {auditSortField === 'current_stock' ? (auditSortDir === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} className="th-sort-idle" />}
                              </div>
                            </th>
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
                            auditProductPagination.pageItems.map(prod => {
                              const prodCat = categories.find(c => c.id === prod.category_id);
                              const lastReconcil = stockMovements.find(
                                m => m.product_id === prod.id && (m.movement_type === 'in_reconciliation' || m.movement_type === 'out_reconciliation' || m.movement_type === 'in_adjustment' || m.movement_type === 'out_adjustment')
                              );
                              const isAudited = Boolean(lastReconcil);

                              return (
                                <tr key={prod.id}>
                                  <td>
                                    <div className="product-title-cell">
                                      <RecordLink
                                        type="PRODUCT"
                                        id={prod.id}
                                        className="product-name"
                                      >
                                        {prod.name}
                                      </RecordLink>
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
                                      {formatQuantity(prod.current_stock)} {prod.unit_of_measure}
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
                      <ListPagination {...auditProductPagination} onPageChange={auditProductPagination.setPage} onPageSizeChange={auditProductPagination.setPageSize} />
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
                            divergencePagination.pageItems.map(mov => {
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
                                      <DocumentLink documentId={mov.document_id} showIcon={false}>
                                        <span className="code-tag">{mov.reference_doc || 'Abrir origem'}</span>
                                      </DocumentLink>
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
                      <ListPagination {...divergencePagination} onPageChange={divergencePagination.setPage} onPageSizeChange={divergencePagination.setPageSize} />
                    </div>
                  </>
                )}

                {/* ============================================================= */}
                {/* SUB-ABA 2: HISTÓRICO DE LOTES IMPORTADOS                      */}
                {/* ============================================================= */}
                {auditSubTab === 'lotes' && (
                  <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: '8px', overflow: 'hidden' }}>
                    <div style={{ padding: '0.85rem 1.25rem', borderBottom: '1px solid var(--border-subtle)', background: 'var(--bg-surface-elevated)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <h3 style={{ fontSize: '0.95rem', fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-primary)' }}>
                          <FileSpreadsheet size={16} style={{ color: '#3b82f6' }} />
                          Histórico de Cargas & Auditorias de Planilha (.xlsx)
                        </h3>
                        <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: '0.15rem 0 0' }}>
                          Registro cronológico de todas as importações com apuração automática de vendas, variações de preço e capital parado.
                        </p>
                      </div>
                      <button
                        type="button"
                        className="btn btn-primary"
                        onClick={() => setIsImportModalOpen(true)}
                        style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}
                      >
                        <UploadCloud size={14} />
                        <span>Nova Importação</span>
                      </button>
                    </div>

                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Lote / Código</th>
                          <th>Data da Posição</th>
                          <th>Importado em</th>
                          <th>Arquivo</th>
                          <th>Total Lidos</th>
                          <th>Vendas Apuradas</th>
                          <th>Variação de Custos</th>
                          <th>Estoque Estagnado</th>
                          <th style={{ textAlign: 'right' }}>Ação</th>
                        </tr>
                      </thead>
                      <tbody>
                        {importBatches.length === 0 ? (
                          <tr>
                            <td colSpan={9} className="state-empty" style={{ textAlign: 'center', padding: '2.5rem' }}>
                              <FileSpreadsheet size={36} style={{ opacity: 0.3, marginBottom: '0.5rem' }} />
                              <p style={{ margin: 0 }}>Nenhum lote de importação registrado até o momento.</p>
                              <button
                                type="button"
                                className="btn btn-primary"
                                onClick={() => setIsImportModalOpen(true)}
                                style={{ marginTop: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}
                              >
                                <UploadCloud size={14} />
                                <span>Importar Primeira Planilha</span>
                              </button>
                            </td>
                          </tr>
                        ) : (
                          importBatches.map(batch => (
                            <tr
                              key={batch.id}
                              className="clickable-table-row ui-record-row"
                              onClick={() => handleOpenBatchDetail(batch.id)}
                              tabIndex={0}
                              role="button"
                              onKeyDown={(e) => {
                                if (['Enter', ' '].includes(e.key)) {
                                  e.preventDefault();
                                  handleOpenBatchDetail(batch.id);
                                }
                              }}
                            >
                              <td>
                                <strong style={{ color: '#3b82f6', fontFamily: 'monospace' }}>
                                  #{batch.batch_number}
                                </strong>
                              </td>
                              <td>
                                <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>
                                  {batch.inventory_date || '-'}
                                </span>
                              </td>
                              <td>
                                <div style={{ display: 'flex', flexDirection: 'column' }}>
                                  <span style={{ fontSize: '0.8rem', color: 'var(--text-primary)', fontWeight: 500 }}>
                                    {new Date(batch.created_at).toLocaleDateString('pt-BR')}
                                  </span>
                                  <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                                    {new Date(batch.created_at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}
                                  </span>
                                </div>
                              </td>
                              <td>
                                <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                                  {batch.filename || 'estoque.xlsx'}
                                </span>
                              </td>
                              <td>
                                <strong>{batch.total_products_read}</strong>
                                <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'block' }}>
                                  +{batch.created_products_count} novos
                                </span>
                              </td>
                              <td>
                                {batch.sales_identified_count > 0 ? (
                                  <div>
                                    <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#10b981' }}>
                                      {batch.sales_identified_count} itens ({batch.total_sales_quantity} un)
                                    </span>
                                    <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'block' }}>
                                      {formatCurrency(batch.total_sales_estimated_revenue)}
                                    </span>
                                  </div>
                                ) : (
                                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>-</span>
                                )}
                              </td>
                              <td>
                                {batch.cost_increases_count > 0 || batch.cost_decreases_count > 0 ? (
                                  <div style={{ display: 'flex', gap: '0.35rem', alignItems: 'center' }}>
                                    {batch.cost_increases_count > 0 && (
                                      <span style={{ fontSize: '0.72rem', background: 'rgba(239, 68, 68, 0.12)', color: '#ef4444', padding: '0.15rem 0.4rem', borderRadius: '3px', fontWeight: 600 }}>
                                        ↑ {batch.cost_increases_count}
                                      </span>
                                    )}
                                    {batch.cost_decreases_count > 0 && (
                                      <span style={{ fontSize: '0.72rem', background: 'rgba(16, 185, 129, 0.12)', color: '#10b981', padding: '0.15rem 0.4rem', borderRadius: '3px', fontWeight: 600 }}>
                                        ↓ {batch.cost_decreases_count}
                                      </span>
                                    )}
                                  </div>
                                ) : (
                                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Estável</span>
                                )}
                              </td>
                              <td>
                                <div>
                                  <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#f59e0b' }}>
                                    {batch.stagnant_products_count} itens
                                  </span>
                                  <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'block' }}>
                                    {formatCurrency(batch.total_stagnant_capital)} parados
                                  </span>
                                </div>
                              </td>
                              <td style={{ textAlign: 'right' }}>
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleOpenBatchDetail(batch.id);
                                  }}
                                  disabled={loadingBatchDetail}
                                  style={{
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: '0.35rem',
                                    padding: '0.35rem 0.75rem',
                                    fontSize: '0.78rem',
                                    fontWeight: 600,
                                    borderRadius: '5px',
                                    background: 'var(--bg-app)',
                                    color: '#3b82f6',
                                    border: '1px solid rgba(59, 130, 246, 0.3)',
                                    cursor: 'pointer'
                                  }}
                                >
                                  <Search size={13} />
                                  <span>Raio-X do Lote</span>
                                </button>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* ============================================================= */}
                {/* SUB-ABA 3: RADAR DE ESTOQUE ESTAGNADO & CAPITAL PARADO        */}
                {/* ============================================================= */}
                {auditSubTab === 'estagnado' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                    {/* KPI CARDS DO CAPITAL ESTAGNADO */}
                    <div className="summary-kpis-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
                      <div className="summary-card highlight-stagnant" style={{ borderLeft: '4px solid #f59e0b', background: 'var(--bg-surface)' }}>
                        <span className="kpi-title" style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#f59e0b' }}>
                          <AlertTriangle size={15} />
                          Produtos Estagnados (Sem Venda)
                        </span>
                        <strong className="kpi-num" style={{ color: '#f59e0b' }}>
                          {stagnantReport?.total_stagnant_products || 0} SKUs
                        </strong>
                        <span className="kpi-sub">Com saldo positivo em prateleira</span>
                      </div>

                      <div className="summary-card" style={{ borderLeft: '4px solid #3b82f6', background: 'var(--bg-surface)' }}>
                        <span className="kpi-title" style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#3b82f6' }}>
                          <Package size={15} />
                          Unidades Físicas Paradas
                        </span>
                        <strong className="kpi-num" style={{ color: 'var(--text-primary)' }}>
                          {formatQuantity(stagnantReport?.total_stagnant_units || 0)} un
                        </strong>
                        <span className="kpi-sub">Estoque imobilizado</span>
                      </div>

                      <div className="summary-card highlight-values" style={{ borderLeft: '4px solid #ef4444', background: 'var(--bg-surface)' }}>
                        <span className="kpi-title" style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#ef4444' }}>
                          <DollarSign size={15} />
                          Capital Imobilizado Total (Custo)
                        </span>
                        <strong className="kpi-num" style={{ color: '#ef4444' }}>
                          {formatCurrency(stagnantReport?.total_stagnant_capital || 0)}
                        </strong>
                        <span className="kpi-sub">Dinheiro retido sem giro recente</span>
                      </div>
                    </div>

                    {/* AGRUPAMENTO POR CATEGORIA */}
                    {stagnantReport?.stagnant_by_category && stagnantReport.stagnant_by_category.length > 0 && (
                      <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: '8px', overflow: 'hidden' }}>
                        <div style={{ padding: '0.75rem 1.25rem', borderBottom: '1px solid var(--border-subtle)', background: 'var(--bg-surface-elevated)' }}>
                          <h4 style={{ fontSize: '0.9rem', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                            Capital Estagnado por Categoria
                          </h4>
                        </div>
                        <table className="data-table">
                          <thead>
                            <tr>
                              <th>Categoria</th>
                              <th>Qtd de SKUs Parados</th>
                              <th>Unidades Paradas</th>
                              <th>Capital Imobilizado (R$)</th>
                            </tr>
                          </thead>
                          <tbody>
                            {stagnantReport.stagnant_by_category.map((cat, idx) => (
                              <tr key={idx}>
                                <td>
                                  <span className="category-pill">{cat.category_name}</span>
                                </td>
                                <td>{cat.products_count} produtos</td>
                                <td>{formatQuantity(cat.total_units)} un</td>
                                <td>
                                  <strong style={{ color: '#f59e0b' }}>
                                    {formatCurrency(cat.total_capital)}
                                  </strong>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}

                    {/* TOP PRODUTOS MAIS ESTAGNADOS */}
                    <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: '8px', overflow: 'hidden' }}>
                      <div style={{ padding: '0.75rem 1.25rem', borderBottom: '1px solid var(--border-subtle)', background: 'var(--bg-surface-elevated)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div>
                          <h4 style={{ fontSize: '0.9rem', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                            Ranking de Produtos com Maior Capital Retido
                          </h4>
                          <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', margin: '0.1rem 0 0' }}>
                            Produtos ordenados por maior valor financeiro parado sem movimentação de venda.
                          </p>
                        </div>
                      </div>

                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Produto / SKU</th>
                            <th>Categoria</th>
                            <th>Saldo Físico</th>
                            <th>Custo Unit.</th>
                            <th>Preço Venda</th>
                            <th>Capital Imobilizado</th>
                            <th>Dias sem Saída</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(!stagnantReport?.top_stagnant_products || stagnantReport.top_stagnant_products.length === 0) ? (
                            <tr>
                              <td colSpan={7} className="state-empty" style={{ textAlign: 'center', padding: '2rem' }}>
                                Nenhum produto com estoque estagnado identificado.
                              </td>
                            </tr>
                          ) : (
                            stagnantReport.top_stagnant_products.slice(0, 50).map(prod => (
                              <tr key={prod.product_id}>
                                <td>
                                  <div className="product-title-cell">
                                    <RecordLink
                                      type="PRODUCT"
                                      id={prod.product_id}
                                      className="product-name"
                                    >
                                      {prod.name}
                                    </RecordLink>
                                    <div className="tags-row">
                                      <span className="sku-tag">{prod.sku || prod.code || '-'}</span>
                                    </div>
                                  </div>
                                </td>
                                <td>
                                  <span className="category-pill">{prod.category_name || 'Geral'}</span>
                                </td>
                                <td>
                                  <strong>{formatQuantity(prod.current_stock)} {prod.unit_of_measure}</strong>
                                </td>
                                <td>{formatCurrency(prod.cost_price)}</td>
                                <td>{formatCurrency(prod.sale_price)}</td>
                                <td>
                                  <strong style={{ color: '#ef4444', fontSize: '0.9rem' }}>
                                    {formatCurrency(prod.stagnant_capital)}
                                  </strong>
                                </td>
                                <td>
                                  {prod.days_without_sale != null ? (
                                    <span style={{ fontSize: '0.8rem', fontWeight: 600, color: prod.days_without_sale > 30 ? '#ef4444' : '#f59e0b' }}>
                                      {prod.days_without_sale} dias
                                    </span>
                                  ) : (
                                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Sem histórico</span>
                                  )}
                                </td>
                              </tr>
                            ))
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* ============================================================= */}
            {/* 6. HUB DE INTEGRAÇÕES DIRETAS (ERP, VENDAS, FISCAL & API)     */}
            {/* ============================================================= */}
            {activeMenu === 'integracoes' && (
              <div className="inventory-integrations-panel">
                <div className="integrations-header">
                  <div className="integrations-title">
                    <RefreshCw size={20} className="icon-pulse" />
                    <div>
                      <h2>Canais externos e fluxos conectados</h2>
                      <p>
                        Gerencie entradas e saídas de dados do estoque, acompanhe execuções e identifique quais fluxos são externos ou internos.
                      </p>
                    </div>
                  </div>
                  <div className="integrations-badge-status">
                    <span className="dot-pulse"></span>
                    <span>1 canal operacional</span>
                  </div>
                </div>

                <div className="integrations-grid">
                  {/* Canal 1: Planilhas & Auditoria */}
                  <div className="integration-card active-card">
                    <div className="card-top">
                      <div className="card-icon excel-icon">
                        <FileSpreadsheet size={22} />
                      </div>
                      <span className="card-badge connected">Conectado / Ativo</span>
                    </div>
                    <h3>Auditoria por Planilha Excel (.xlsx)</h3>
                    <p>
                      Processamento e apuração de saldos, conciliação automática de vendas diárias e cálculo de impacto financeiro por SKU.
                    </p>
                    <div className="card-metrics">
                      <div className="metric-col">
                        <span>Lotes Processados</span>
                        <strong>{importBatches.length} arquivos</strong>
                      </div>
                      <div className="metric-col">
                        <span>Última Importação</span>
                        <strong>{importBatches[0] ? new Date(importBatches[0].created_at).toLocaleDateString('pt-BR') : 'Nenhuma'}</strong>
                      </div>
                    </div>
                    <div className="card-actions">
                      <button
                        type="button"
                        className="btn-card-action primary"
                        onClick={() => setIsImportModalOpen(true)}
                      >
                        <UploadCloud size={14} />
                        <span>Carregar Nova Planilha</span>
                      </button>
                      <button
                        type="button"
                        className="btn-card-action secondary"
                        onClick={() => { setActiveMenu('auditoria'); setAuditSubTab('lotes'); }}
                      >
                        <History size={14} />
                        <span>Ver Histórico de Lotes</span>
                      </button>
                    </div>
                  </div>

                  {/* Canal 2: Integração com Compras & Fornecedores */}
                  <div className="integration-card internal-flow-card">
                    <div className="card-top">
                      <div className="card-icon purchase-icon">
                        <Package size={22} />
                      </div>
                      <span className="card-badge internal">Fluxo interno</span>
                    </div>
                    <h3>Compras → Estoque</h3>
                    <p>
                      Encaminha itens abaixo do mínimo para reposição e recebe mercadorias de pedidos de compra no Kardex.
                    </p>
                    <div className="card-metrics">
                      <div className="metric-col">
                        <span>Itens Críticos</span>
                        <strong style={{ color: '#ef4444' }}>{belowMinStockItems.length} SKUs</strong>
                      </div>
                      <div className="metric-col">
                        <span>Giro de Reposição</span>
                        <strong>Regra interna</strong>
                      </div>
                    </div>
                    <div className="card-actions">
                      <a
                        href="/compras?view=sugestoes"
                        className="btn-card-action primary"
                      >
                        <Package size={14} />
                        <span>Abrir sugestões de compra</span>
                      </a>
                    </div>
                  </div>

                  {/* Canal 3: Integração Fiscal & Notas Fiscais (NFe / XML) */}
                  <div className="integration-card internal-flow-card">
                    <div className="card-top">
                      <div className="card-icon fiscal-icon">
                        <ShieldCheck size={22} />
                      </div>
                      <span className="card-badge internal">Fluxo interno</span>
                    </div>
                    <h3>Fiscal → Kardex</h3>
                    <p>
                      Vincula documentos fiscais cadastrados, NCM e anexos às entradas de estoque; não representa conexão direta com a SEFAZ.
                    </p>
                    <div className="card-metrics">
                      <div className="metric-col">
                        <span>Itens com NCM</span>
                        <strong>{products.filter(p => Boolean(p.ncm)).length} cadastrados</strong>
                      </div>
                      <div className="metric-col">
                        <span>Anexos no Kardex</span>
                        <strong>Habilitado</strong>
                      </div>
                    </div>
                    <div className="card-actions">
                      <button
                        type="button"
                        className="btn-card-action secondary"
                        onClick={() => { setActiveMenu('movimentacoes'); setSearchTerm(''); }}
                      >
                        <History size={14} />
                        <span>Auditar Movimentações Fiscais</span>
                      </button>
                    </div>
                  </div>

                  {/* Canal 4: API REST & Webhooks Externos */}
                  <div className="integration-card">
                    <div className="card-top">
                      <div className="card-icon api-icon">
                        <Zap size={22} />
                      </div>
                      <span className="card-badge available">Disponível</span>
                    </div>
                    <h3>API REST & exportações</h3>
                    <p>
                      Interface autenticada para sistemas externos consultarem cadastros e executarem operações permitidas.
                    </p>
                    <div className="card-metrics">
                      <div className="metric-col">
                        <span>Contrato</span>
                        <strong style={{ color: '#3b82f6' }}>OpenAPI</strong>
                      </div>
                      <div className="metric-col">
                        <span>Autenticação</span>
                        <strong>Bearer token</strong>
                      </div>
                    </div>
                    <div className="card-actions">
                      <a
                        href="/docs"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="btn-card-action primary"
                      >
                        <FileText size={14} />
                        <span>Abrir documentação</span>
                      </a>
                      <button
                        type="button"
                        className="btn-card-action secondary"
                        onClick={() => exportProductsToCsv(products, 'completo')}
                      >
                        <Download size={14} />
                        <span>Exportar Base de Produtos</span>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
          </>
          )}
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

              <div className="form-row cols-2">
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
              </div>

              <div className="form-row cols-3">
                <div className="form-group">
                  <label>Preço de Custo (R$)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={productCostPrice}
                    onChange={(e) => {
                      setProductCostPrice(e.target.value);
                      if (!productPrice || productPrice === '0') setProductPrice(e.target.value);
                    }}
                    placeholder="0,00"
                  />
                </div>

                <div className="form-group">
                  <label>Preço de Venda (R$)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={productSalePrice}
                    onChange={(e) => setProductSalePrice(e.target.value)}
                    placeholder="0,00"
                  />
                </div>

                <div className="form-group">
                  <label>Preço Ref. / Base (R$)</label>
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
                      {formatQuantity(productCurrentStock)} {productUnit}
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
                <span>3. Rastreabilidade, Integrações & Tributário</span>
              </div>

              <div className="form-row cols-3">
                <div className="form-group">
                  <label>Código Externo / Legado</label>
                  <input
                    type="text"
                    value={productExternalCode}
                    onChange={(e) => setProductExternalCode(e.target.value)}
                    placeholder="Ex: 9353051"
                  />
                </div>
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
                {formatQuantity(stockAdjustProduct?.current_stock)} {stockAdjustProduct?.unit_of_measure}
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
                    <option value="Devolução a Fornecedor">Devolução a Fornecedor</option>
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
          5. MODAL DE IMPORTAÇÃO & SINCRONIZAÇÃO DE PLANILHA DE ESTOQUE (.XLSX)
      ===================================================================== */}
      <Modal
        isOpen={isImportModalOpen}
        onClose={() => {
          if (!isImportingFile) {
            setIsImportModalOpen(false);
          }
        }}
        title="Sincronização & Importação de Estoque"
        size="lg"
      >
        <div className="inventory-import-wizard">
          {importError && (
            <div className="modal-alert-error">
              <AlertTriangle size={16} />
              <span>{importError}</span>
            </div>
          )}

          {!importSummary ? (
            <div className="import-step-upload">
              {/* Card Informativo das Regras de Negócio */}
              <div className="import-guidance-card">
                <div className="guidance-header">
                  <Sparkles size={16} className="sparkle-icon" />
                  <strong>Como funciona a Reconciliação de Estoque via Planilha:</strong>
                </div>
                <div className="guidance-grid">
                  <div className="guidance-item">
                    <CheckCircle2 size={14} className="ok-icon" />
                    <span><strong>Novos Produtos & Categorias:</strong> Itens inexistentes são cadastrados e categorizados automaticamente via NCM.</span>
                  </div>
                  <div className="guidance-item">
                    <TrendingDown size={14} className="sale-icon" />
                    <span><strong>Detecção de Vendas:</strong> Quedas de saldo físico são registradas como saídas por venda no Kardex.</span>
                  </div>
                  <div className="guidance-item">
                    <TrendingUp size={14} className="entry-icon" />
                    <span><strong>Detecção de Reposições:</strong> Aumentos de saldo são registrados como entradas de mercadoria.</span>
                  </div>
                  <div className="guidance-item">
                    <DollarSign size={14} className="price-icon" />
                    <span><strong>Preços de Custo & Venda:</strong> Atualiza os valores unitários e custos médios sem perder dados prévios.</span>
                  </div>
                </div>
              </div>

              {/* Área de Dropzone e Seleção de Arquivo */}
              <div className="file-dropzone-container">
                <input
                  type="file"
                  id="inventory-file-input"
                  accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                  onChange={handleImportFileChange}
                  style={{ display: 'none' }}
                  disabled={isImportingFile}
                />

                <label
                  htmlFor="inventory-file-input"
                  className={`file-dropzone-box ${selectedImportFile ? 'has-file' : ''}`}
                >
                  <div className="dropzone-icon-wrap">
                    <FileSpreadsheet size={36} className="excel-icon" />
                  </div>
                  {selectedImportFile ? (
                    <div className="selected-file-details">
                      <strong className="file-name">{selectedImportFile.name}</strong>
                      <span className="file-meta">
                        {(selectedImportFile.size / 1024).toFixed(1)} KB • Pronto para processamento
                      </span>
                      <span className="file-change-hint">Clique para selecionar outro arquivo</span>
                    </div>
                  ) : (
                    <div className="dropzone-text">
                      <strong>Clique aqui para selecionar a planilha .xlsx de estoque</strong>
                      <span>Relatório de Estoque e Inventário Físico</span>
                    </div>
                  )}
                </label>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn-cancel"
                  onClick={() => setIsImportModalOpen(false)}
                  disabled={isImportingFile}
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={handleProcessImport}
                  disabled={!selectedImportFile || isImportingFile}
                >
                  {isImportingFile ? (
                    <>
                      <Loader2 size={16} className="spinning" />
                      <span>Processando produtos...</span>
                    </>
                  ) : (
                    <>
                      <UploadCloud size={16} />
                      <span>Processar e Sincronizar Estoque</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          ) : (
            <div className="import-step-summary">
              {/* Banner de Sucesso */}
              <div className="import-success-banner">
                <div className="banner-icon-wrap">
                  <CheckCircle size={24} />
                </div>
                <div className="banner-text">
                  <h3>Sincronização Concluída com Sucesso!</h3>
                  <p>{importSummary.message}</p>
                  {importSummary.inventory_date && (
                    <span className="date-tag">Posição de Estoque: {importSummary.inventory_date}</span>
                  )}
                </div>
              </div>

              {/* Grid de KPIs da Carga */}
              <div className="summary-kpis-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))' }}>
                <div className="summary-card">
                  <span className="kpi-title">Itens Processados</span>
                  <strong className="kpi-num">{importSummary.total_products_read}</strong>
                  <span className="kpi-sub">{importSummary.created_categories_count} categorias criadas</span>
                </div>

                <div className="summary-card highlight-created">
                  <span className="kpi-title">Novos Produtos</span>
                  <strong className="kpi-num ok">+{importSummary.created_products_count}</strong>
                  <span className="kpi-sub">{importSummary.updated_products_count} atualizados</span>
                </div>

                <div className="summary-card highlight-sales">
                  <span className="kpi-title">Vendas Identificadas</span>
                  <strong className="kpi-num sale">{importSummary.sales_identified_count} itens</strong>
                  <span className="kpi-sub">
                    {importSummary.total_sales_quantity} un • {formatCurrency(importSummary.total_sales_estimated_revenue)}
                  </span>
                </div>

                <div className="summary-card" style={{ borderLeft: '4px solid #ef4444' }}>
                  <span className="kpi-title">Variações de Custo</span>
                  <strong className="kpi-num" style={{ color: '#ef4444' }}>
                    {importSummary.cost_increases_count > 0 ? `↑ ${importSummary.cost_increases_count} aumentos` : 'Estável'}
                  </strong>
                  <span className="kpi-sub">{importSummary.cost_decreases_count} quedas de preço</span>
                </div>

                <div className="summary-card" style={{ borderLeft: '4px solid #f59e0b' }}>
                  <span className="kpi-title">Estoque Estagnado</span>
                  <strong className="kpi-num" style={{ color: '#f59e0b' }}>
                    {importSummary.stagnant_products_count} itens
                  </strong>
                  <span className="kpi-sub">{formatCurrency(importSummary.total_stagnant_capital)} parados</span>
                </div>

                <div className="summary-card highlight-entries">
                  <span className="kpi-title">Reposições de Estoque</span>
                  <strong className="kpi-num entry">{importSummary.entries_identified_count} itens</strong>
                  <span className="kpi-sub">{importSummary.total_entries_quantity} un adicionadas</span>
                </div>

                <div className="summary-card highlight-values">
                  <span className="kpi-title">Patrimônio em Custo</span>
                  <strong className="kpi-num">{formatCurrency(importSummary.total_cost_value)}</strong>
                  <span className="kpi-sub">Venda: {formatCurrency(importSummary.total_sale_value)}</span>
                </div>
              </div>

              {/* Tabela de Amostra / Divergências Identificadas */}
              {importSummary.sample_items && importSummary.sample_items.length > 0 && (
                <div className="sample-items-section">
                  <div className="sample-header">
                    <h4>Auditoria de Amostra & Movimentações Geradas</h4>
                    <div className="sample-search">
                      <Search size={14} />
                      <input
                        type="text"
                        placeholder="Filtrar nesta auditoria..."
                        value={importSearchTerm}
                        onChange={(e) => setImportSearchTerm(e.target.value)}
                      />
                    </div>
                  </div>

                  <div className="sample-table-wrapper">
                    <table className="sample-table">
                      <thead>
                        <tr>
                          <th>Código / Produto</th>
                          <th>Saldo Anterior</th>
                          <th>Novo Saldo</th>
                          <th>Diferença</th>
                          <th>Ação Registrada</th>
                          <th>Preço Custo</th>
                          <th>Preço Venda</th>
                        </tr>
                      </thead>
                      <tbody>
                        {importSummary.sample_items
                          .filter(it =>
                            it.name.toLowerCase().includes(importSearchTerm.toLowerCase()) ||
                            it.code.toLowerCase().includes(importSearchTerm.toLowerCase())
                          )
                          .map((item, idx) => (
                            <tr key={idx}>
                              <td>
                                <div className="sample-prod-cell">
                                  <strong>{item.name}</strong>
                                  <span className="sample-code">Cód: {item.code} {item.barcode ? `• EAN: ${item.barcode}` : ''}</span>
                                </div>
                              </td>
                              <td>{item.previous_stock}</td>
                              <td><strong>{item.new_stock}</strong></td>
                              <td>
                                <span className={`delta-tag ${item.delta_stock > 0 ? 'pos' : item.delta_stock < 0 ? 'neg' : 'zero'}`}>
                                  {item.delta_stock > 0 ? `+${item.delta_stock}` : item.delta_stock}
                                </span>
                              </td>
                              <td>
                                {item.action_type === 'created' && <span className="action-pill created">Novo Cadastro</span>}
                                {item.action_type === 'sale_detected' && <span className="action-pill sale">Venda (Saída)</span>}
                                {item.action_type === 'entry_detected' && <span className="action-pill entry">Reposição (Entrada)</span>}
                                {item.action_type === 'stagnant_unchanged' && <span className="action-pill" style={{ background: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b' }}>Estoque Estagnado</span>}
                                {(item.action_type === 'zero_stock_unchanged' || item.action_type === 'unchanged') && <span className="action-pill unchanged">Saldo Zero</span>}
                              </td>
                              <td>
                                <div>
                                  <strong>{formatCurrency(item.new_cost_price)}</strong>
                                  {item.cost_variation_percent != null && Number(item.cost_variation_percent) !== 0 ? (
                                    <span style={{ fontSize: '0.7rem', display: 'block', color: item.cost_variation_percent > 0 ? '#ef4444' : '#10b981', fontWeight: 600 }}>
                                      {item.cost_variation_percent > 0 ? `+${item.cost_variation_percent}%` : `${item.cost_variation_percent}%`}
                                    </span>
                                  ) : null}
                                </div>
                              </td>
                              <td>
                                <div>
                                  <strong>{formatCurrency(item.new_sale_price)}</strong>
                                  {item.sale_variation_percent != null && Number(item.sale_variation_percent) !== 0 ? (
                                    <span style={{ fontSize: '0.7rem', display: 'block', color: item.sale_variation_percent > 0 ? '#10b981' : '#ef4444', fontWeight: 600 }}>
                                      {item.sale_variation_percent > 0 ? `+${item.sale_variation_percent}%` : `${item.sale_variation_percent}%`}
                                    </span>
                                  ) : null}
                                </div>
                              </td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => {
                    setIsImportModalOpen(false);
                    setActiveMenu('auditoria');
                    setAuditSubTab('lotes');
                    void loadBatchesAndStagnation(true);
                  }}
                >
                  <Check size={16} />
                  <span>Concluir e Ver Histórico de Auditoria</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </Modal>

      {/* =====================================================================
          MODAL RAIO-X DE AUDITORIA DO LOTE DE IMPORTAÇÃO
      ===================================================================== */}
      {/* =====================================================================
          MODAL RAIO-X DE AUDITORIA DO LOTE DE IMPORTAÇÃO (REDESENHADO)
      ===================================================================== */}
      {selectedBatchDetail && (() => {
        const filteredAuditItems = selectedBatchDetail.items.filter(it => {
          if (batchModalFilter === 'prices') {
            const hasCostVar = it.cost_variation_percent != null && Number(it.cost_variation_percent) !== 0;
            const hasSaleVar = it.sale_variation_percent != null && Number(it.sale_variation_percent) !== 0;
            if (!hasCostVar && !hasSaleVar) return false;
          } else if (batchModalFilter === 'sales') {
            if (it.action_type !== 'sale_detected') return false;
          } else if (batchModalFilter === 'stagnant') {
            if (it.action_type !== 'stagnant_unchanged') return false;
          } else if (batchModalFilter === 'entries') {
            if (it.action_type !== 'entry_detected' && it.action_type !== 'created') return false;
          }
          if (batchModalSearch.trim()) {
            const term = batchModalSearch.toLowerCase();
            return (
              it.name.toLowerCase().includes(term) ||
              it.code.toLowerCase().includes(term) ||
              Boolean(it.barcode && it.barcode.toLowerCase().includes(term)) ||
              Boolean(it.ncm && it.ncm.toLowerCase().includes(term))
            );
          }
          return true;
        });

        const totalAuditPages = Math.max(1, Math.ceil(filteredAuditItems.length / batchModalPageSize));
        const currentAuditPage = Math.min(batchModalPage, totalAuditPages);
        const paginatedAuditItems = filteredAuditItems.slice(
          (currentAuditPage - 1) * batchModalPageSize,
          currentAuditPage * batchModalPageSize
        );

        const pricesVarCount = selectedBatchDetail.items.filter(
          i => (i.cost_variation_percent != null && Number(i.cost_variation_percent) !== 0) || (i.sale_variation_percent != null && Number(i.sale_variation_percent) !== 0)
        ).length;

        return (
          <Modal
            isOpen={Boolean(selectedBatchDetail)}
            onClose={() => setSelectedBatchDetail(null)}
            title={`Raio-X de Auditoria: Lote #${selectedBatchDetail.batch_number}`}
            subtitle={`Arquivo: ${selectedBatchDetail.filename || 'relatorio.xlsx'} • Data do Estoque: ${selectedBatchDetail.inventory_date || 'Geral'} • Processado em: ${new Date(selectedBatchDetail.created_at).toLocaleString('pt-BR')}`}
            size="xl"
          >
            <div className="audit-raiox-container">
              {/* 1. GRID DE KPI CARDS EXECUTIVOS */}
              <div className="audit-kpi-grid">
                <div className="audit-kpi-card sales-card">
                  <div className="kpi-header">
                    <span className="kpi-label"><TrendingDown size={14} /> Vendas Apuradas</span>
                    <div className="kpi-icon-wrap"><TrendingDown size={14} /></div>
                  </div>
                  <div className="kpi-main-val">+{formatCurrency(selectedBatchDetail.total_sales_estimated_revenue)}</div>
                  <div className="kpi-subtitle">
                    <strong>{selectedBatchDetail.sales_identified_count} itens</strong> • {formatQuantity(selectedBatchDetail.total_sales_quantity)} un apuradas
                  </div>
                </div>

                <div className="audit-kpi-card costs-card">
                  <div className="kpi-header">
                    <span className="kpi-label"><AlertTriangle size={14} /> Variações de Custo</span>
                    <div className="kpi-icon-wrap"><ArrowUpDown size={14} /></div>
                  </div>
                  <div className="kpi-main-val">
                    {selectedBatchDetail.cost_increases_count + selectedBatchDetail.cost_decreases_count} reajustes
                  </div>
                  <div className="kpi-subtitle">
                    <span style={{ color: '#ef4444', fontWeight: 700 }}>↑ {selectedBatchDetail.cost_increases_count} aumentos</span>
                    <span>•</span>
                    <span style={{ color: '#10b981', fontWeight: 700 }}>↓ {selectedBatchDetail.cost_decreases_count} quedas</span>
                  </div>
                </div>

                <div className="audit-kpi-card stagnant-card">
                  <div className="kpi-header">
                    <span className="kpi-label"><DollarSign size={14} /> Estoque Estagnado</span>
                    <div className="kpi-icon-wrap"><DollarSign size={14} /></div>
                  </div>
                  <div className="kpi-main-val">{formatCurrency(selectedBatchDetail.total_stagnant_capital)}</div>
                  <div className="kpi-subtitle">
                    <strong>{selectedBatchDetail.stagnant_products_count} itens</strong> imobilizados sem giro
                  </div>
                </div>

                <div className="audit-kpi-card entries-card">
                  <div className="kpi-header">
                    <span className="kpi-label"><TrendingUp size={14} /> Reposições de Saldo</span>
                    <div className="kpi-icon-wrap"><TrendingUp size={14} /></div>
                  </div>
                  <div className="kpi-main-val">+{formatQuantity(selectedBatchDetail.total_entries_quantity)} un</div>
                  <div className="kpi-subtitle">
                    <strong>{selectedBatchDetail.entries_identified_count} itens</strong> adicionados ao físico
                  </div>
                </div>
              </div>

              {/* 2. BARRA DE AÇÕES & INTEGRAÇÕES DIRETAS DO LOTE */}
              <div className="audit-direct-actions-bar">
                <div className="direct-actions-title">
                  <Sparkles size={16} />
                  <span>Ações & Integrações Diretas:</span>
                </div>
                <div className="direct-actions-buttons">
                  <button
                    type="button"
                    className="btn-direct-action btn-replenish"
                    onClick={() => handleGenerateReplenishmentFromBatch(selectedBatchDetail)}
                    title="Abrir módulo de Compras para repor itens vendidos ou zerados neste lote"
                  >
                    <Package size={13} />
                    <span>Reposição em Compras</span>
                  </button>
                  <button
                    type="button"
                    className="btn-direct-action btn-kardex"
                    onClick={() => handleNavigateToKardexForBatch(selectedBatchDetail)}
                    title="Visualizar a trilha de movimentações gerada pelo lote no Kardex"
                  >
                    <History size={13} />
                    <span>Trilha no Kardex</span>
                  </button>
                  <button
                    type="button"
                    className="btn-direct-action btn-export"
                    onClick={() => exportBatchAuditToCsv(selectedBatchDetail)}
                    title="Exportar auditoria analítica completa em formato CSV / Excel"
                  >
                    <Download size={13} />
                    <span>Exportar Auditoria (CSV)</span>
                  </button>
                </div>
              </div>

              {/* 3. FILTROS E BUSCA INTERNA DO LOTE */}
              <div className="audit-controls-bar">
                <div className="audit-filter-pills">
                  <button
                    type="button"
                    className={`audit-pill-btn pill-all ${batchModalFilter === 'all' ? 'active' : ''}`}
                    onClick={() => { setBatchModalFilter('all'); setBatchModalPage(1); }}
                  >
                    <span>Todos</span>
                    <span className="count-badge">{selectedBatchDetail.items.length}</span>
                  </button>

                  <button
                    type="button"
                    className={`audit-pill-btn pill-prices ${batchModalFilter === 'prices' ? 'active' : ''}`}
                    onClick={() => { setBatchModalFilter('prices'); setBatchModalPage(1); }}
                  >
                    <span>🔴 Variações de Preço</span>
                    <span className="count-badge">{pricesVarCount}</span>
                  </button>

                  <button
                    type="button"
                    className={`audit-pill-btn pill-sales ${batchModalFilter === 'sales' ? 'active' : ''}`}
                    onClick={() => { setBatchModalFilter('sales'); setBatchModalPage(1); }}
                  >
                    <span>🟢 Vendas no Período</span>
                    <span className="count-badge">{selectedBatchDetail.sales_identified_count}</span>
                  </button>

                  <button
                    type="button"
                    className={`audit-pill-btn pill-stagnant ${batchModalFilter === 'stagnant' ? 'active' : ''}`}
                    onClick={() => { setBatchModalFilter('stagnant'); setBatchModalPage(1); }}
                  >
                    <span>🟡 Estoque Estagnado</span>
                    <span className="count-badge">{selectedBatchDetail.stagnant_products_count}</span>
                  </button>

                  <button
                    type="button"
                    className={`audit-pill-btn pill-entries ${batchModalFilter === 'entries' ? 'active' : ''}`}
                    onClick={() => { setBatchModalFilter('entries'); setBatchModalPage(1); }}
                  >
                    <span>🔵 Reposições</span>
                    <span className="count-badge">{selectedBatchDetail.entries_identified_count}</span>
                  </button>
                </div>

                <div className="audit-search-input-wrap">
                  <Search size={14} className="search-icon" />
                  <input
                    type="text"
                    placeholder="Buscar por produto, código, EAN..."
                    value={batchModalSearch}
                    onChange={(e) => {
                      setBatchModalSearch(e.target.value);
                      setBatchModalPage(1);
                    }}
                  />
                </div>
              </div>

              {/* 4. TABELA DE ITENS AUDITADOS COM PAGINAÇÃO */}
              <div className="audit-table-wrapper">
                <table className="audit-data-table">
                  <thead>
                    <tr>
                      <th style={{ width: '32%' }}>Código / Produto</th>
                      <th style={{ width: '10%', textAlign: 'center' }}>Saldo Ant.</th>
                      <th style={{ width: '10%', textAlign: 'center' }}>Novo Saldo</th>
                      <th style={{ width: '10%', textAlign: 'center' }}>Variação</th>
                      <th style={{ width: '13%' }}>Preço Custo</th>
                      <th style={{ width: '13%' }}>Preço Venda</th>
                      <th style={{ width: '12%' }}>Status Auditoria</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedAuditItems.length === 0 ? (
                      <tr>
                        <td colSpan={7} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                          Nenhum item corresponde ao filtro ou termo de busca selecionado.
                        </td>
                      </tr>
                    ) : (
                      paginatedAuditItems.map((it, idx) => (
                        <tr key={idx}>
                          <td>
                            <div className="audit-product-cell">
                              <span className="prod-name">{it.name}</span>
                              <div className="prod-tags-row">
                                <span className="code-chip">CÓD: {it.code}</span>
                                {it.barcode && (
                                  <span className="barcode-chip" title="Código de barras EAN">
                                    <Tags size={10} />
                                    <span>EAN: {it.barcode}</span>
                                  </span>
                                )}
                                {it.ncm && (
                                  <span className="ncm-chip" title="NCM Fiscal">
                                    NCM: {it.ncm}
                                  </span>
                                )}
                              </div>
                            </div>
                          </td>
                          <td style={{ textAlign: 'center' }}>
                            <span>{formatQuantity(it.previous_stock)} {it.unit_of_measure}</span>
                          </td>
                          <td style={{ textAlign: 'center' }}>
                            <strong>{formatQuantity(it.new_stock)} {it.unit_of_measure}</strong>
                          </td>
                          <td style={{ textAlign: 'center' }}>
                            <span className={`stock-delta-pill ${Number(it.delta_stock) > 0 ? 'pos' : Number(it.delta_stock) < 0 ? 'neg' : 'zero'}`}>
                              {Number(it.delta_stock) > 0 ? `+${it.delta_stock}` : it.delta_stock}
                            </span>
                          </td>
                          <td>
                            <div className="price-compare-cell">
                              <span className="price-line">
                                {it.previous_cost_price != null ? formatCurrency(it.previous_cost_price) : '-'} → <strong>{formatCurrency(it.new_cost_price)}</strong>
                              </span>
                              {it.cost_variation_percent != null && Number(it.cost_variation_percent) !== 0 ? (
                                <span className={`price-var-pill ${it.cost_variation_percent > 0 ? 'up' : 'down'}`}>
                                  {it.cost_variation_percent > 0 ? `↑ +${it.cost_variation_percent}%` : `↓ ${it.cost_variation_percent}%`}
                                </span>
                              ) : null}
                            </div>
                          </td>
                          <td>
                            <div className="price-compare-cell">
                              <span className="price-line">
                                {it.previous_sale_price != null ? formatCurrency(it.previous_sale_price) : '-'} → <strong>{formatCurrency(it.new_sale_price)}</strong>
                              </span>
                              {it.sale_variation_percent != null && Number(it.sale_variation_percent) !== 0 ? (
                                <span className={`price-var-pill ${it.sale_variation_percent > 0 ? 'sale-up' : 'sale-down'}`}>
                                  {it.sale_variation_percent > 0 ? `↑ +${it.sale_variation_percent}%` : `↓ ${it.sale_variation_percent}%`}
                                </span>
                              ) : null}
                            </div>
                          </td>
                          <td>
                            {it.action_type === 'created' && (
                              <span className="status-audit-badge status-created">
                                <Sparkles size={11} /> Novo Cadastro
                              </span>
                            )}
                            {it.action_type === 'sale_detected' && (
                              <span className="status-audit-badge status-sale" title={`Receita apurada: +${formatCurrency(it.estimated_sales_revenue)}`}>
                                <TrendingDown size={11} /> Venda Apurada
                              </span>
                            )}
                            {it.action_type === 'entry_detected' && (
                              <span className="status-audit-badge status-entry" title={`Entrada física de +${it.delta_stock} un`}>
                                <TrendingUp size={11} /> Reposição (+)
                              </span>
                            )}
                            {it.action_type === 'stagnant_unchanged' && (
                              <span className="status-audit-badge status-stagnant" title={`Capital parado: ${formatCurrency(it.stagnant_value)}`}>
                                <AlertTriangle size={11} /> Estagnado
                              </span>
                            )}
                            {(it.action_type === 'zero_stock_unchanged' || it.action_type === 'unchanged') && (
                              <span className="status-audit-badge status-zero">
                                Saldo Zero
                              </span>
                            )}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {/* 5. BARRA DE PAGINAÇÃO DO MODAL */}
              <div className="audit-pagination-bar">
                <span>
                  Exibindo <strong>{paginatedAuditItems.length > 0 ? (currentAuditPage - 1) * batchModalPageSize + 1 : 0}</strong> a{' '}
                  <strong>{Math.min(currentAuditPage * batchModalPageSize, filteredAuditItems.length)}</strong> de{' '}
                  <strong>{filteredAuditItems.length}</strong> itens auditados
                </span>
                <div className="pagination-buttons">
                  <button
                    type="button"
                    onClick={() => setBatchModalPage(p => Math.max(1, p - 1))}
                    disabled={currentAuditPage <= 1}
                  >
                    ← Anterior
                  </button>
                  <span style={{ alignSelf: 'center', padding: '0 0.5rem', fontWeight: 600 }}>
                    Página {currentAuditPage} de {totalAuditPages}
                  </span>
                  <button
                    type="button"
                    onClick={() => setBatchModalPage(p => Math.min(totalAuditPages, p + 1))}
                    disabled={currentAuditPage >= totalAuditPages}
                  >
                    Próxima →
                  </button>
                </div>
              </div>

              <div className="modal-footer" style={{ display: 'flex', justifyContent: 'flex-end', borderTop: '1px solid var(--border-subtle)', paddingTop: '0.75rem' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setSelectedBatchDetail(null)}
                >
                  Fechar Detalhes
                </button>
              </div>
            </div>
          </Modal>
        );
      })()}

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
