/**
 * pages/Finance/Finance.tsx - Central de Gestão Financeira (ControlB)
 */

import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Landmark, ArrowUpRight, ArrowDownLeft, DollarSign, Plus,
  RefreshCw, CheckCircle2, Calendar, Search,
  FileText, Tag,
  Building2, Wallet, ArrowRightLeft, TrendingUp, BarChart3, Ban, Power,
  Paperclip, Upload, X, ExternalLink, FileCheck,
  RotateCcw, Trash2, Copy, Barcode, Download
} from 'lucide-react';
import { financeService, purchasingService, salesService, formatApiError } from '@/services/api';
import {
  Payable, Receivable, BankAccount, BankTransaction,
  FiscalDocument, FinancialCategory, FinanceDashboardSummary, CostCenter,
  Supplier, PurchaseOrder, Customer
} from '@/types';
import { Modal } from '@/components/Modal/Modal';
import { ConfirmModal } from '@/components/ConfirmModal/ConfirmModal';
import {
  EditableFinanceRecord,
  FinanceRecordEditModal
} from '@/components/FinanceRecordEditModal/FinanceRecordEditModal';
import { BulkActionsBar } from '@/components/BulkActionsBar';
import { ListPagination } from '@/components/ListPagination';
import { useBulkSelection } from '@/hooks/useBulkSelection';
import { useListPagination } from '@/hooks/useListPagination';
import { RecordLink, useRecordDeepLink, isRequestedView } from '@/components/RecordLink';
import { useToast } from '@/components/Toast/ToastContext';
import './Finance.scss';

const ALLOWED_FINANCE_TABS = [
  'payables', 'receivables', 'treasury', 'reconciliation', 'fiscal-documents', 'categories', 'reports'
] as const;
type FinanceTab = typeof ALLOWED_FINANCE_TABS[number];

const payableTypeLabels: Record<Payable['obligation_type'], string> = {
  GOODS_SUPPLIER: 'Fornecedor', SERVICE_PROVIDER: 'Prestador', TAX: 'Tributo',
  PAYROLL: 'Folha', RENT_LEASE: 'Aluguel', FINANCING: 'Financiamento',
  REIMBURSEMENT: 'Reembolso', INVESTMENT: 'Investimento', OTHER: 'Outro'
};

const payableOriginLabels: Record<Payable['business_origin'], string> = {
  PURCHASE: 'Compra', REPLENISHMENT: 'Reposição', INVESTMENT: 'Investimento',
  CONTRACT: 'Contrato', FISCAL_DOCUMENT: 'Documento fiscal', MANUAL: 'Manual', OTHER: 'Outra'
};

export const Finance: React.FC = () => {
  const toast = useToast();
  const [searchParams] = useSearchParams();
  const initialFinanceTab = isRequestedView(searchParams, ALLOWED_FINANCE_TABS, 'payables');

  // Controle de Abas
  const [activeTab, setActiveTab] = useState<FinanceTab>(initialFinanceTab);

  // Estados de Dados
  const [loading, setLoading] = useState<boolean>(true);
  const [dashboard, setDashboard] = useState<FinanceDashboardSummary | null>(null);
  const [payables, setPayables] = useState<Payable[]>([]);
  const [receivables, setReceivables] = useState<Receivable[]>([]);
  const [bankAccounts, setBankAccounts] = useState<BankAccount[]>([]);
  const [transactions, setTransactions] = useState<BankTransaction[]>([]);
  const [fiscalDocs, setFiscalDocs] = useState<FiscalDocument[]>([]);
  const [categories, setCategories] = useState<FinancialCategory[]>([]);
  const [costCenters, setCostCenters] = useState<CostCenter[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [purchaseOrders, setPurchaseOrders] = useState<PurchaseOrder[]>([]);
  const payableSelection = useBulkSelection<Payable>();
  const receivableSelection = useBulkSelection<Receivable>();
  const fiscalSelection = useBulkSelection<FiscalDocument>();
  const categorySelection = useBulkSelection<FinancialCategory>();

  // Filtros
  const [payableStatusFilter, setPayableStatusFilter] = useState<string>('ALL');
  const [payableNatureFilter, setPayableNatureFilter] = useState<string>('ALL');
  const [payableTypeFilter, setPayableTypeFilter] = useState<string>('ALL');
  const [payableOriginFilter, setPayableOriginFilter] = useState<string>('ALL');
  const [receivableStatusFilter, setReceivableStatusFilter] = useState<string>('ALL');
  const [searchTerm, setSearchTerm] = useState<string>('');

  // Modais
  const [isExpenseModalOpen, setIsExpenseModalOpen] = useState<boolean>(false);
  const [isPaymentModalOpen, setIsPaymentModalOpen] = useState<boolean>(false);
  const [isReceivableModalOpen, setIsReceivableModalOpen] = useState<boolean>(false);
  const [isReceiptModalOpen, setIsReceiptModalOpen] = useState<boolean>(false);
  const [isAccountModalOpen, setIsAccountModalOpen] = useState<boolean>(false);
  const [isCategoryModalOpen, setIsCategoryModalOpen] = useState<boolean>(false);
  const [isTxModalOpen, setIsTxModalOpen] = useState<boolean>(false);
  const [isLinkFiscalModalOpen, setIsLinkFiscalModalOpen] = useState<boolean>(false);
  const [isAttachReceiptModalOpen, setIsAttachReceiptModalOpen] = useState<boolean>(false);
  const [isBoletoModalOpen, setIsBoletoModalOpen] = useState<boolean>(false);
  const [selectedPayableForBoleto, setSelectedPayableForBoleto] = useState<Payable | null>(null);
  const [boletoForm, setBoletoForm] = useState({
    instrument_type: 'BOLETO' as const,
    digitable_line: '',
    barcode: '',
    pix_code: '',
    document_number: '',
    due_date: '',
    amount: '',
    file_attachment: ''
  });

  // Anexos em Nova Despesa Avulsa
  const [expenseBoletoFile, setExpenseBoletoFile] = useState<{ name: string; dataUrl: string } | null>(null);
  const [expenseFiscalFile, setExpenseFiscalFile] = useState<{ name: string; dataUrl: string } | null>(null);
  const [expenseNewFiscalDoc, setExpenseNewFiscalDoc] = useState({
    document_type: 'NFE' as 'NFE' | 'NFSE' | 'NFCE' | 'CTE' | 'OUTRO',
    document_number: '',
    series: '',
    access_key: ''
  });
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  // Seleções para Ações
  const [selectedPayable, setSelectedPayable] = useState<Payable | null>(null);
  const [selectedReceivable, setSelectedReceivable] = useState<Receivable | null>(null);
  const [selectedTxForLink, setSelectedTxForLink] = useState<BankTransaction | null>(null);
  const [editingRecord, setEditingRecord] = useState<EditableFinanceRecord | null>(null);

  // Modal de Confirmação Estilizado (Substitui window.confirm e window.alert)
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
      confirmText: config.confirmText || 'Confirmar',
      cancelText: config.cancelText || 'Voltar',
      type: config.type || 'danger',
      isLoading: false,
      errorMessage: null,
      onConfirm: config.onConfirm,
    });
  };

  const closeConfirmModal = () => {
    setConfirmModal(prev => ({ ...prev, isOpen: false, errorMessage: null, isLoading: false }));
  };

  // Form Vínculo de Nota Fiscal
  const [fiscalLinkMode, setFiscalLinkMode] = useState<'EXISTING' | 'NEW'>('EXISTING');
  const [existingFiscalDocId, setExistingFiscalDocId] = useState<string>('');
  const [newFiscalDocForm, setNewFiscalDocForm] = useState({
    direction: 'INBOUND',
    document_type: 'NFE',
    document_number: '',
    series: '',
    access_key: '',
    issuer_name: '',
    issuer_cnpj_cpf: '',
    issue_date: new Date().toISOString().split('T')[0],
    total_amount: '',
    tax_amount: '0.00',
    file_attachment: '',
    notes: ''
  });

  // Form Anexo de Comprovante de Extrato
  const [txReceiptForm, setTxReceiptForm] = useState({
    file_name: '',
    file_url: '',
    mime_type: 'application/pdf',
    payable_id: ''
  });

  // Forms de Nova Despesa Avulsa
  const [expenseForm, setExpenseForm] = useState({
    description: '',
    favored_name: '',
    original_amount: '',
    issue_date: new Date().toISOString().split('T')[0],
    due_date: new Date().toISOString().split('T')[0],
    expense_nature: 'NOT_APPLICABLE' as Payable['expense_nature'],
    obligation_type: 'OTHER' as Payable['obligation_type'],
    business_origin: 'MANUAL' as Payable['business_origin'],
    supplier_id: '',
    purchase_order_id: '',
    fiscal_document_id: '',
    payment_method_expected: 'BOLETO',
    financial_category_id: '',
    cost_center_id: '',
    installments_count: 1,
    installment_frequency_days: 30,
    digitable_line: '',
    pix_code: '',
    notes: ''
  });

  // Form Baixa de Pagamento
  const [paymentForm, setPaymentForm] = useState({
    amount: '',
    discount_amount: '0.00',
    interest_amount: '0.00',
    payment_date: new Date().toISOString().split('T')[0],
    payment_method: 'BOLETO',
    bank_account_id: '',
    reference: '',
    notes: '',
    file_name: '',
    file_url: ''
  });

  // Form Novo Recebível
  const [receivableForm, setReceivableForm] = useState({
    customer_id: '',
    customer_name: '',
    customer_document: '',
    description: '',
    original_amount: '',
    issue_date: new Date().toISOString().split('T')[0],
    due_date: new Date().toISOString().split('T')[0],
    payment_method_expected: 'PIX',
    financial_category_id: '',
    cost_center_id: '',
    notes: ''
  });

  // Form Baixa de Recebimento
  const [receiptForm, setReceiptForm] = useState({
    amount: '',
    receipt_date: new Date().toISOString().split('T')[0],
    payment_method: 'PIX',
    bank_account_id: '',
    reference: '',
    notes: ''
  });

  // Form Nova Conta Bancária
  const [accountForm, setAccountForm] = useState({
    bank_name: '',
    bank_code: '',
    agency: '',
    account_number: '',
    account_type: 'CHECKING' as 'CHECKING' | 'SAVINGS' | 'CASH' | 'DIGITAL_WALLET',
    opening_balance: '0.00'
  });

  // Form Nova Categoria
  const [categoryForm, setCategoryForm] = useState({
    name: '',
    code: '',
    category_type: 'EXPENSE' as 'EXPENSE' | 'REVENUE',
    description: ''
  });

  // Form Lançamento Manual no Extrato
  const [txForm, setTxForm] = useState({
    bank_account_id: '',
    transaction_date: new Date().toISOString().split('T')[0],
    description: '',
    amount: '',
    transaction_type: 'DEBIT',
    document_number: ''
  });

  // Carregar Dados do Módulo Financeiro
  const loadAllFinanceData = async () => {
    setLoading(true);
    try {
      const [
        dashRes,
        payablesRes,
        receivablesRes,
        accountsRes,
        txRes,
        fiscalRes,
        categoriesRes,
        costCentersRes,
        suppliersRes,
        purchaseOrdersRes,
        customersRes
      ] = await Promise.all([
        financeService.getDashboard().catch(() => null),
        financeService.getPayables().catch(() => []),
        financeService.getReceivables().catch(() => []),
        financeService.getBankAccounts().catch(() => []),
        financeService.getBankTransactions().catch(() => []),
        financeService.getFiscalDocuments().catch(() => []),
        financeService.getCategories().catch(() => []),
        purchasingService.getCostCenters().catch(() => []),
        purchasingService.getSuppliers().catch(() => []),
        purchasingService.getPurchaseOrders(undefined, true).catch(() => []),
        salesService.getCustomers(undefined, true).catch(() => [])
      ]);

      setDashboard(dashRes);
      setPayables(payablesRes);
      setReceivables(receivablesRes);
      setBankAccounts(accountsRes);
      setTransactions(txRes);
      setFiscalDocs(fiscalRes);
      setCategories(categoriesRes);
      setCostCenters(costCentersRes);
      setSuppliers(suppliersRes);
      setPurchaseOrders(purchaseOrdersRes);
      setCustomers(customersRes);
    } catch (err) {
      console.error("Erro ao carregar dados financeiros:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAllFinanceData();
  }, []);

  // Formatação de Moeda
  const fmtCurrency = (val: number | undefined | null) => {
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val || 0);
  };

  // Formatação de Data
  const fmtDate = (dStr: string | undefined | null) => {
    if (!dStr) return '-';
    try {
      const parts = dStr.split('-');
      if (parts.length === 3) return `${parts[2]}/${parts[1]}/${parts[0]}`;
      return new Date(dStr).toLocaleDateString('pt-BR');
    } catch {
      return dStr;
    }
  };

  // Status Badge Helper
  const renderStatusBadge = (status: string) => {
    const map: Record<string, { label: string; cls: string }> = {
      PENDING_APPROVAL: { label: 'Pendente Aprovação', cls: 'pending_approval' },
      APPROVED: { label: 'Aprovado', cls: 'approved' },
      PARTIALLY_PAID: { label: 'Parcialmente Pago', cls: 'partially_paid' },
      PAID: { label: 'Pago', cls: 'paid' },
      OVERDUE: { label: 'Vencido', cls: 'overdue' },
      CANCELLED: { label: 'Cancelado', cls: 'cancelled' },
      PENDING: { label: 'Pendente', cls: 'pending_approval' },
      PARTIALLY_RECEIVED: { label: 'Parcialmente Recebido', cls: 'partially_received' },
      RECEIVED: { label: 'Recebido', cls: 'received' }
    };
    const s = map[status] || { label: status, cls: 'pending_approval' };
    return <span className={`status-badge ${s.cls}`}>{s.label}</span>;
  };

  // Handlers de Ações
  const handleCopyText = (text: string, label: string) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    toast.success(`${label} copiado!`);
  };

  const handleCreateExpense = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;
    setIsSubmitting(true);
    try {
      const newFiscalDoc = expenseFiscalFile ? {
        direction: 'INBOUND' as const,
        document_type: expenseNewFiscalDoc.document_type,
        document_number: expenseNewFiscalDoc.document_number || `NF-${Date.now().toString().slice(-6)}`,
        series: expenseNewFiscalDoc.series || undefined,
        access_key: expenseNewFiscalDoc.access_key || undefined,
        issuer_name: expenseForm.favored_name,
        issuer_cnpj_cpf: undefined,
        issue_date: expenseForm.issue_date,
        total_amount: parseFloat(expenseForm.original_amount),
        tax_amount: 0,
        file_attachment: expenseFiscalFile.dataUrl,
        notes: `Documento fiscal anexado no lançamento: ${expenseFiscalFile.name}`
      } : undefined;

      const instrumentData = (expenseForm.digitable_line || expenseBoletoFile) ? {
        instrument_type: 'BOLETO' as const,
        digitable_line: expenseForm.digitable_line || undefined,
        pix_code: expenseForm.pix_code || undefined,
        due_date: expenseForm.due_date,
        amount: parseFloat(expenseForm.original_amount),
        file_attachment: expenseBoletoFile?.dataUrl || undefined
      } : undefined;

      await financeService.createPayable({
        description: expenseForm.description,
        favored_name: expenseForm.favored_name,
        original_amount: parseFloat(expenseForm.original_amount),
        issue_date: expenseForm.issue_date,
        due_date: expenseForm.due_date,
        expense_nature: expenseForm.expense_nature,
        obligation_type: expenseForm.obligation_type,
        business_origin: expenseForm.business_origin,
        supplier_id: expenseForm.supplier_id || undefined,
        purchase_order_id: expenseForm.purchase_order_id || undefined,
        fiscal_document_id: expenseForm.fiscal_document_id || undefined,
        payment_method_expected: expenseForm.payment_method_expected || undefined,
        financial_category_id: expenseForm.financial_category_id || undefined,
        cost_center_id: expenseForm.cost_center_id || undefined,
        installments_count: Number(expenseForm.installments_count) || 1,
        installment_frequency_days: Number(expenseForm.installment_frequency_days) || 30,
        instrument: instrumentData,
        new_fiscal_document: newFiscalDoc,
        notes: expenseForm.notes || undefined
      });
      setIsExpenseModalOpen(false);
      setExpenseBoletoFile(null);
      setExpenseFiscalFile(null);
      setExpenseNewFiscalDoc({
        document_type: 'NFE',
        document_number: '',
        series: '',
        access_key: ''
      });
      setExpenseForm({
        description: '',
        favored_name: '',
        original_amount: '',
        issue_date: new Date().toISOString().split('T')[0],
        due_date: new Date().toISOString().split('T')[0],
        expense_nature: 'NOT_APPLICABLE',
        obligation_type: 'OTHER',
        business_origin: 'MANUAL',
        supplier_id: '',
        purchase_order_id: '',
        fiscal_document_id: '',
        payment_method_expected: 'BOLETO',
        financial_category_id: '',
        cost_center_id: '',
        installments_count: 1,
        installment_frequency_days: 30,
        digitable_line: '',
        pix_code: '',
        notes: ''
      });
      loadAllFinanceData();
      toast.success("Despesa lançada com sucesso!");
    } catch (err: any) {
      toast.error(formatApiError(err, "Erro ao criar despesa."));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReopenPayable = (p: Payable) => {
    openConfirmModal({
      title: 'Reabrir Conta a Pagar',
      subtitle: `Conta ${p.payable_number} · ${p.favored_name}`,
      message: 'Deseja realmente reabrir esta conta a pagar? O status retornará para Pendente de Aprovação, permitindo sua tramitação e pagamento.',
      confirmText: 'Reabrir Conta',
      type: 'info',
      onConfirm: async () => {
        try {
          await financeService.reopenPayable(p.id);
          closeConfirmModal();
          loadAllFinanceData();
          toast.success("Conta a pagar reaberta com sucesso!");
        } catch (err: any) {
          toast.error(formatApiError(err, "Erro ao reabrir conta a pagar."));
        }
      }
    });
  };

  const handleDeletePayable = (p: Payable) => {
    openConfirmModal({
      title: 'Excluir Conta a Pagar',
      subtitle: `Conta ${p.payable_number} · ${p.favored_name}`,
      message: 'Atenção: deseja excluir permanentemente esta conta a pagar? Esta operação removerá o registro e os instrumentos vinculados.',
      confirmText: 'Excluir Definitivamente',
      type: 'danger',
      onConfirm: async () => {
        try {
          await financeService.deletePayable(p.id);
          closeConfirmModal();
          loadAllFinanceData();
          toast.success("Conta a pagar excluída com sucesso!");
        } catch (err: any) {
          toast.error(formatApiError(err, "Erro ao excluir conta a pagar."));
        }
      }
    });
  };

  const handleReopenReceivable = (r: Receivable) => {
    openConfirmModal({
      title: 'Reabrir Título a Receber',
      subtitle: `Título ${r.receivable_number} · ${r.customer_name}`,
      message: 'Deseja reabrir este título a receber? O status retornará para Pendente, permitindo o registro de recebimentos.',
      confirmText: 'Reabrir Título',
      type: 'info',
      onConfirm: async () => {
        try {
          await financeService.reopenReceivable(r.id);
          closeConfirmModal();
          loadAllFinanceData();
          toast.success("Título a receber reaberto com sucesso!");
        } catch (err: any) {
          toast.error(formatApiError(err, "Erro ao reabrir título a receber."));
        }
      }
    });
  };

  const handleDeleteReceivable = (r: Receivable) => {
    openConfirmModal({
      title: 'Excluir Título a Receber',
      subtitle: `Título ${r.receivable_number} · ${r.customer_name}`,
      message: 'Atenção: deseja excluir permanentemente este título a receber? Esta ação não pode ser desfeita.',
      confirmText: 'Excluir Definitivamente',
      type: 'danger',
      onConfirm: async () => {
        try {
          await financeService.deleteReceivable(r.id);
          closeConfirmModal();
          loadAllFinanceData();
          toast.success("Título a receber excluído com sucesso!");
        } catch (err: any) {
          toast.error(formatApiError(err, "Erro ao excluir título a receber."));
        }
      }
    });
  };

  const handleOpenBoletoModal = (p: Payable) => {
    setSelectedPayableForBoleto(p);
    const inst = p.instruments?.find(i => i.instrument_type === 'BOLETO') || p.instruments?.[0];
    setBoletoForm({
      instrument_type: 'BOLETO',
      digitable_line: inst?.digitable_line || '',
      barcode: inst?.barcode || '',
      pix_code: inst?.pix_code || '',
      document_number: inst?.document_number || '',
      due_date: inst?.due_date || p.due_date,
      amount: inst?.amount?.toString() || p.outstanding_amount.toString(),
      file_attachment: inst?.file_attachment || ''
    });
    setIsBoletoModalOpen(true);
  };

  const handleSaveBoleto = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPayableForBoleto || isSubmitting) return;
    setIsSubmitting(true);
    try {
      await financeService.createOrUpdatePayableInstrument(selectedPayableForBoleto.id, {
        instrument_type: 'BOLETO',
        digitable_line: boletoForm.digitable_line || undefined,
        barcode: boletoForm.barcode || undefined,
        pix_code: boletoForm.pix_code || undefined,
        document_number: boletoForm.document_number || undefined,
        due_date: boletoForm.due_date || undefined,
        amount: boletoForm.amount ? parseFloat(boletoForm.amount) : undefined,
        file_attachment: boletoForm.file_attachment || undefined
      });
      setIsBoletoModalOpen(false);
      setSelectedPayableForBoleto(null);
      loadAllFinanceData();
      toast.success("Boleto atualizado com sucesso!");
    } catch (err: any) {
      toast.error(formatApiError(err, "Erro ao salvar boleto."));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteBoleto = () => {
    if (!selectedPayableForBoleto) return;
    const inst = selectedPayableForBoleto.instruments?.find(i => i.instrument_type === 'BOLETO') || selectedPayableForBoleto.instruments?.[0];
    if (!inst) return;
    openConfirmModal({
      title: 'Excluir Boleto da Parcela',
      subtitle: `Conta ${selectedPayableForBoleto.payable_number}`,
      message: 'Deseja remover o boleto cadastrado para esta parcela? A linha digitável e o anexo serão removidos.',
      confirmText: 'Excluir Boleto',
      type: 'danger',
      onConfirm: async () => {
        try {
          await financeService.deletePayableInstrument(selectedPayableForBoleto.id, inst.id);
          setIsBoletoModalOpen(false);
          closeConfirmModal();
          loadAllFinanceData();
          toast.success("Boleto removido com sucesso!");
        } catch (err: any) {
          toast.error(formatApiError(err, "Erro ao remover boleto."));
        }
      }
    });
  };

  const handleExpensePurchaseOrderChange = (purchaseOrderId: string) => {
    const order = purchaseOrders.find(item => item.id === purchaseOrderId);
    const supplier = order
      ? suppliers.find(item => item.id === order.supplier_id) || order.supplier || null
      : null;
    setExpenseForm(current => ({
      ...current,
      purchase_order_id: purchaseOrderId,
      supplier_id: order?.supplier_id || current.supplier_id,
      favored_name: supplier?.name || current.favored_name,
      cost_center_id: order?.cost_center_id || current.cost_center_id,
      business_origin: order?.replenishment_id ? 'REPLENISHMENT' : order ? 'PURCHASE' : current.business_origin,
      obligation_type: order ? 'GOODS_SUPPLIER' : current.obligation_type
    }));
  };

  const handleOpenPaymentModal = (payable: Payable) => {
    setSelectedPayable(payable);
    setPaymentForm({
      amount: payable.outstanding_amount.toString(),
      discount_amount: '0.00',
      interest_amount: '0.00',
      payment_date: new Date().toISOString().split('T')[0],
      payment_method: payable.payment_method_expected || 'PIX',
      bank_account_id: bankAccounts[0]?.id || '',
      reference: '',
      notes: '',
      file_name: '',
      file_url: ''
    });
    setIsPaymentModalOpen(true);
  };

  const handleRegisterPayment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPayable || isSubmitting) return;
    setIsSubmitting(true);
    try {
      await financeService.registerPayment(selectedPayable.id, {
        amount: parseFloat(paymentForm.amount),
        payment_date: paymentForm.payment_date,
        payment_method: paymentForm.payment_method,
        bank_account_id: paymentForm.bank_account_id || undefined,
        reference: paymentForm.reference || undefined,
        notes: paymentForm.notes || undefined,
        attachments: paymentForm.file_name && paymentForm.file_url ? [{
          file_name: paymentForm.file_name,
          file_url: paymentForm.file_url
        }] : []
      });
      setIsPaymentModalOpen(false);
      setSelectedPayable(null);
      loadAllFinanceData();
      toast.success("Pagamento registrado com sucesso!");
    } catch (err: any) {
      toast.error(formatApiError(err, "Erro ao registrar pagamento."));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCreateReceivable = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;
    setIsSubmitting(true);
    try {
      await financeService.createReceivable({
        customer_id: receivableForm.customer_id || undefined,
        customer_name: receivableForm.customer_name,
        customer_document: receivableForm.customer_document || undefined,
        description: receivableForm.description,
        original_amount: parseFloat(receivableForm.original_amount),
        issue_date: receivableForm.issue_date,
        due_date: receivableForm.due_date,
        payment_method_expected: receivableForm.payment_method_expected || undefined,
        financial_category_id: receivableForm.financial_category_id || undefined,
        cost_center_id: receivableForm.cost_center_id || undefined,
        notes: receivableForm.notes || undefined
      });
      setIsReceivableModalOpen(false);
      setReceivableForm({
        customer_id: '',
        customer_name: '',
        customer_document: '',
        description: '',
        original_amount: '',
        issue_date: new Date().toISOString().split('T')[0],
        due_date: new Date().toISOString().split('T')[0],
        payment_method_expected: 'PIX',
        financial_category_id: '',
        cost_center_id: '',
        notes: ''
      });
      loadAllFinanceData();
      toast.success("Título a receber criado com sucesso!");
    } catch (err: any) {
      toast.error(formatApiError(err, "Erro ao criar título a receber."));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleOpenReceiptModal = (receivable: Receivable) => {
    setSelectedReceivable(receivable);
    setReceiptForm({
      amount: receivable.outstanding_amount.toString(),
      receipt_date: new Date().toISOString().split('T')[0],
      payment_method: receivable.payment_method_expected || 'PIX',
      bank_account_id: bankAccounts[0]?.id || '',
      reference: '',
      notes: ''
    });
    setIsReceiptModalOpen(true);
  };

  const handleRegisterReceipt = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedReceivable || isSubmitting) return;
    setIsSubmitting(true);
    try {
      await financeService.registerReceipt(selectedReceivable.id, {
        amount: parseFloat(receiptForm.amount),
        receipt_date: receiptForm.receipt_date,
        payment_method: receiptForm.payment_method,
        bank_account_id: receiptForm.bank_account_id || undefined,
        reference: receiptForm.reference || undefined,
        notes: receiptForm.notes || undefined
      });
      setIsReceiptModalOpen(false);
      setSelectedReceivable(null);
      loadAllFinanceData();
      toast.success("Recebimento registrado com sucesso!");
    } catch (err: any) {
      toast.error(formatApiError(err, "Erro ao registrar recebimento."));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCreateAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;
    setIsSubmitting(true);
    try {
      await financeService.createBankAccount({
        bank_name: accountForm.bank_name,
        bank_code: accountForm.bank_code || undefined,
        agency: accountForm.agency || undefined,
        account_number: accountForm.account_number || undefined,
        account_type: accountForm.account_type,
        opening_balance: parseFloat(accountForm.opening_balance || '0')
      });
      setIsAccountModalOpen(false);
      setAccountForm({
        bank_name: '',
        bank_code: '',
        agency: '',
        account_number: '',
        account_type: 'CHECKING',
        opening_balance: '0.00'
      });
      loadAllFinanceData();
      toast.success("Conta bancária cadastrada com sucesso!");
    } catch (err: any) {
      toast.error(formatApiError(err, "Erro ao cadastrar conta bancária."));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCreateCategory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;
    setIsSubmitting(true);
    try {
      await financeService.createCategory({
        name: categoryForm.name,
        code: categoryForm.code || undefined,
        category_type: categoryForm.category_type,
        description: categoryForm.description || undefined
      });
      setIsCategoryModalOpen(false);
      setCategoryForm({
        name: '',
        code: '',
        category_type: 'EXPENSE',
        description: ''
      });
      loadAllFinanceData();
      toast.success("Categoria criada com sucesso!");
    } catch (err: any) {
      toast.error(formatApiError(err, "Erro ao criar categoria."));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCreateTx = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;
    setIsSubmitting(true);
    try {
      await financeService.createBankTransaction({
        bank_account_id: txForm.bank_account_id,
        transaction_date: txForm.transaction_date,
        description: txForm.description,
        amount: parseFloat(txForm.amount),
        transaction_type: txForm.transaction_type as 'CREDIT' | 'DEBIT',
        document_number: txForm.document_number || undefined
      });
      setIsTxModalOpen(false);
      setTxForm({
        bank_account_id: '',
        transaction_date: new Date().toISOString().split('T')[0],
        description: '',
        amount: '',
        transaction_type: 'DEBIT',
        document_number: ''
      });
      loadAllFinanceData();
      toast.success("Movimentação lançada com sucesso!");
    } catch (err: any) {
      toast.error(formatApiError(err, "Erro ao lançar movimentação."));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleOpenLinkFiscalModal = (tx: BankTransaction) => {
    setSelectedTxForLink(tx);
    setFiscalLinkMode('EXISTING');
    setExistingFiscalDocId('');
    setNewFiscalDocForm({
      direction: tx.transaction_type === 'CREDIT' ? 'INBOUND' : 'OUTBOUND',
      document_type: 'NFE',
      document_number: '',
      series: '',
      access_key: '',
      issuer_name: '',
      issuer_cnpj_cpf: '',
      issue_date: tx.transaction_date,
      total_amount: tx.amount.toString(),
      tax_amount: '0.00',
      file_attachment: '',
      notes: `Vínculo com movimentação bancária #${tx.document_number || tx.id.slice(0, 8)}`
    });
    setIsLinkFiscalModalOpen(true);
  };

  const handleSubmitLinkFiscal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTxForLink || isSubmitting) return;
    setIsSubmitting(true);
    try {
      if (fiscalLinkMode === 'EXISTING') {
        if (!existingFiscalDocId) {
          toast.warning('Selecione uma nota fiscal para vincular.');
          return;
        }
        await financeService.linkTransactionFiscalDocument(selectedTxForLink.id, {
          fiscal_document_id: existingFiscalDocId
        });
      } else {
        if (!newFiscalDocForm.document_number || !newFiscalDocForm.issuer_name) {
          toast.warning('Preencha os campos obrigatórios da nota fiscal.');
          return;
        }
        await financeService.linkTransactionFiscalDocument(selectedTxForLink.id, {
          new_fiscal_document: {
            direction: newFiscalDocForm.direction,
            document_type: newFiscalDocForm.document_type,
            document_number: newFiscalDocForm.document_number,
            series: newFiscalDocForm.series || undefined,
            access_key: newFiscalDocForm.access_key || undefined,
            issuer_name: newFiscalDocForm.issuer_name,
            issuer_cnpj_cpf: newFiscalDocForm.issuer_cnpj_cpf || undefined,
            issue_date: newFiscalDocForm.issue_date,
            total_amount: parseFloat(newFiscalDocForm.total_amount),
            tax_amount: parseFloat(newFiscalDocForm.tax_amount || '0'),
            file_attachment: newFiscalDocForm.file_attachment || undefined,
            notes: newFiscalDocForm.notes || undefined
          }
        });
      }
      setIsLinkFiscalModalOpen(false);
      loadAllFinanceData();
      toast.success("Documento fiscal vinculado com sucesso!");
    } catch (err: any) {
      toast.error(formatApiError(err, 'Erro ao vincular nota fiscal.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUnlinkFiscal = (e: React.MouseEvent, tx: BankTransaction) => {
    e.stopPropagation();
    openConfirmModal({
      title: 'Desvincular Documento Fiscal',
      subtitle: `Transação #${tx.id.slice(0, 8)}`,
      message: 'Deseja realmente desvincular o documento fiscal desta movimentação bancária?',
      confirmText: 'Desvincular',
      type: 'warning',
      onConfirm: async () => {
        try {
          await financeService.unlinkTransactionFiscalDocument(tx.id);
          closeConfirmModal();
          loadAllFinanceData();
          toast.success("Documento fiscal desvinculado com sucesso!");
        } catch (err: any) {
          toast.error(formatApiError(err, 'Erro ao desvincular documento fiscal.'));
        }
      }
    });
  };

  const handleOpenAttachReceiptModal = (tx: BankTransaction) => {
    setSelectedTxForLink(tx);
    setTxReceiptForm({
      file_name: '',
      file_url: '',
      mime_type: 'application/pdf',
      payable_id: ''
    });
    setIsAttachReceiptModalOpen(true);
  };

  const handleSubmitAttachReceipt = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTxForLink || isSubmitting) return;
    if (!txReceiptForm.file_name || !txReceiptForm.file_url) {
      toast.warning('Informe o nome e o arquivo/URL do comprovante.');
      return;
    }
    setIsSubmitting(true);
    try {
      await financeService.attachTransactionReceipt(selectedTxForLink.id, {
        file_name: txReceiptForm.file_name,
        file_url: txReceiptForm.file_url,
        mime_type: txReceiptForm.mime_type,
        payable_id: txReceiptForm.payable_id || undefined
      });
      setIsAttachReceiptModalOpen(false);
      loadAllFinanceData();
      toast.success("Comprovante anexado com sucesso!");
    } catch (err: any) {
      toast.error(formatApiError(err, 'Erro ao anexar comprovante de pagamento.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRemoveReceipt = (e: React.MouseEvent, tx: BankTransaction) => {
    e.stopPropagation();
    openConfirmModal({
      title: 'Remover Comprovante',
      subtitle: `Transação #${tx.id.slice(0, 8)}`,
      message: 'Deseja remover o comprovante de pagamento desta movimentação?',
      confirmText: 'Remover Comprovante',
      type: 'danger',
      onConfirm: async () => {
        try {
          await financeService.removeTransactionReceipt(tx.id);
          closeConfirmModal();
          loadAllFinanceData();
          toast.success("Comprovante removido com sucesso!");
        } catch (err: any) {
          toast.error(formatApiError(err, 'Erro ao remover comprovante.'));
        }
      }
    });
  };

  // Filtragem
  const filteredPayables = payables.filter(p => {
    const matchesStatus = payableStatusFilter === 'ALL' || p.status === payableStatusFilter;
    const matchesNature = payableNatureFilter === 'ALL' || p.expense_nature === payableNatureFilter;
    const matchesType = payableTypeFilter === 'ALL' || p.obligation_type === payableTypeFilter;
    const matchesOrigin = payableOriginFilter === 'ALL' || p.business_origin === payableOriginFilter;
    const matchesSearch = searchTerm === '' ||
      p.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.favored_name.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesStatus && matchesNature && matchesType && matchesOrigin && matchesSearch;
  });

  const filteredReceivables = receivables.filter(r => {
    const matchesStatus = receivableStatusFilter === 'ALL' || r.status === receivableStatusFilter;
    const matchesSearch = searchTerm === '' ||
      r.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.customer_name.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesStatus && matchesSearch;
  });

  const payablePagination = useListPagination(filteredPayables);
  const receivablePagination = useListPagination(filteredReceivables);
  const transactionPagination = useListPagination(transactions);
  const fiscalPagination = useListPagination(fiscalDocs);
  const categoryPagination = useListPagination(categories);
  const selectablePayablesOnPage = payablePagination.pageItems.filter(item => !['PAID', 'RECONCILED'].includes(item.status));
  const selectableReceivablesOnPage = receivablePagination.pageItems.filter(item => !['RECEIVED'].includes(item.status));
  const cancellableFiscalOnPage = fiscalPagination.pageItems.filter(item => ['DRAFT', 'PENDING'].includes(item.status.toUpperCase()));
  const activeCategoriesOnPage = categoryPagination.pageItems.filter(item => item.is_active);

  const runBulkFinanceAction = (
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
        await loadAllFinanceData();
        if (failed > 0) {
          toast.warning(`${succeeded} registro(s) processado(s); ${failed} não puderam ser alterados.`);
        } else {
          toast.success(`${succeeded} registro(s) processado(s) com sucesso.`);
        }
      }
    });
  };

  useRecordDeepLink({
    types: ['PAYABLE'],
    records: payables,
    onOpen: (p) => {
      setActiveTab('payables');
      setEditingRecord({ kind: 'payable', value: p });
    },
  });

  useRecordDeepLink({
    types: ['RECEIVABLE'],
    records: receivables,
    onOpen: (r) => {
      setActiveTab('receivables');
      setEditingRecord({ kind: 'receivable', value: r });
    },
  });

  useRecordDeepLink({
    types: ['FISCAL_DOCUMENT'],
    records: fiscalDocs,
    onOpen: (doc) => {
      setActiveTab('fiscal-documents');
      setEditingRecord({ kind: 'fiscal', value: doc });
    },
  });

  return (
    <div className="finance-page">
      <div className="finance-layout">
        {/* 1. SIDEBAR LATERAL ESQUERDA */}
        <aside className="sidebar-left">
          <div className="sidebar-header">
            <Landmark className="brand-icon" size={20} />
            <div className="sidebar-title-wrap">
              <span className="sidebar-title"><strong>Financeiro</strong></span>
              <span className="sidebar-subtitle">Gestão Financeira</span>
            </div>
          </div>

          <nav className="nav-menu">
            <span className="menu-group-label">Contas & Movimentações</span>

            <button
              className={`nav-item ${activeTab === 'payables' ? 'active' : ''}`}
              onClick={() => setActiveTab('payables')}
            >
              <div className="nav-item-content">
                <ArrowUpRight size={16} />
                <span>Contas a Pagar</span>
              </div>
              <span className="nav-badge">{payables.length}</span>
            </button>

            <button
              className={`nav-item ${activeTab === 'receivables' ? 'active' : ''}`}
              onClick={() => setActiveTab('receivables')}
            >
              <div className="nav-item-content">
                <ArrowDownLeft size={16} />
                <span>Contas a Receber</span>
              </div>
              <span className="nav-badge">{receivables.length}</span>
            </button>

            <button
              className={`nav-item ${activeTab === 'treasury' ? 'active' : ''}`}
              onClick={() => setActiveTab('treasury')}
            >
              <div className="nav-item-content">
                <Landmark size={16} />
                <span>Tesouraria & Extratos</span>
              </div>
              <span className="nav-badge">{bankAccounts.length}</span>
            </button>

            <button
              className={`nav-item ${activeTab === 'reconciliation' ? 'active' : ''}`}
              onClick={() => setActiveTab('reconciliation')}
            >
              <div className="nav-item-content">
                <ArrowRightLeft size={16} />
                <span>Conciliação Bancária</span>
              </div>
              {dashboard?.unreconciled_transactions_count ? (
                <span className="nav-badge">{dashboard.unreconciled_transactions_count}</span>
              ) : null}
            </button>

            <span className="menu-group-label">Documentos & Relatórios</span>

            <button
              className={`nav-item ${activeTab === 'fiscal-documents' ? 'active' : ''}`}
              onClick={() => setActiveTab('fiscal-documents')}
            >
              <div className="nav-item-content">
                <FileText size={16} />
                <span>Documentos Fiscais</span>
              </div>
              <span className="nav-badge">{fiscalDocs.length}</span>
            </button>

            <button
              className={`nav-item ${activeTab === 'reports' ? 'active' : ''}`}
              onClick={() => setActiveTab('reports')}
            >
              <div className="nav-item-content">
                <BarChart3 size={16} />
                <span>Fluxo de Caixa & DRE</span>
              </div>
            </button>

            <button
              className={`nav-item ${activeTab === 'categories' ? 'active' : ''}`}
              onClick={() => setActiveTab('categories')}
            >
              <div className="nav-item-content">
                <Tag size={16} />
                <span>Plano de Contas</span>
              </div>
            </button>
          </nav>
        </aside>

        {/* 2. CONTEÚDO PRINCIPAL */}
        <main className="main-content">
          {/* Header Superior com Ações Dinâmicas */}
          <div className="content-header">
            <div className="header-titles">
              <h1>
                {activeTab === 'payables' && 'Contas a Pagar & Despesas'}
                {activeTab === 'receivables' && 'Contas a Receber & Receitas'}
                {activeTab === 'treasury' && 'Tesouraria, Contas & Extratos'}
                {activeTab === 'reconciliation' && 'Conciliação Bancária'}
                {activeTab === 'fiscal-documents' && 'Documentos Fiscais'}
                {activeTab === 'categories' && 'Categorias & Plano de Contas'}
                {activeTab === 'reports' && 'Fluxo de Caixa & DRE Gerencial'}
              </h1>
              <p className="subtitle">Gestão contábil e financeira integrada do ControlB</p>
            </div>

            <div className="header-actions">
              <button className="btn-refresh" onClick={loadAllFinanceData} title="Atualizar Dados">
                <RefreshCw size={15} className={loading ? 'spinning' : ''} />
              </button>

              {activeTab === 'payables' && (
                <button className="btn-primary" onClick={() => setIsExpenseModalOpen(true)}>
                  <Plus size={16} />
                  <span>Nova Despesa Avulsa</span>
                </button>
              )}

              {activeTab === 'receivables' && (
                <button className="btn-primary" onClick={() => setIsReceivableModalOpen(true)}>
                  <Plus size={16} />
                  <span>Novo Título a Receber</span>
                </button>
              )}

              {activeTab === 'treasury' && (
                <>
                  <button className="btn-secondary" onClick={() => setIsAccountModalOpen(true)}>
                    <Plus size={16} />
                    <span>Nova Conta Bancária</span>
                  </button>
                  <button className="btn-primary" onClick={() => setIsTxModalOpen(true)}>
                    <Plus size={16} />
                    <span>Lançar Movimentação</span>
                  </button>
                </>
              )}

              {activeTab === 'categories' && (
                <button className="btn-primary" onClick={() => setIsCategoryModalOpen(true)}>
                  <Plus size={16} />
                  <span>Nova Categoria</span>
                </button>
              )}
            </div>
          </div>

          {/* Cards de Métricas Principais (Executive Summary) */}
          <div className="kpi-grid">
            <div className="kpi-card">
              <div className="kpi-top">
                <span className="kpi-label">Saldo em Caixa / Bancos</span>
                <Wallet size={18} />
              </div>
              <div className="kpi-value">{fmtCurrency(dashboard?.total_available_balance)}</div>
              <div className="kpi-sub">{bankAccounts.length} conta(s) ativas conectadas</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-top">
                <span className="kpi-label">Contas a Pagar (Mês)</span>
                <ArrowUpRight size={18} />
              </div>
              <div className="kpi-value">{fmtCurrency(dashboard?.payables_month)}</div>
              <div className="kpi-sub">
                {dashboard?.payables_overdue ? `${fmtCurrency(dashboard?.payables_overdue)} vencido` : 'Em dia'}
              </div>
            </div>

            <div className="kpi-card">
              <div className="kpi-top">
                <span className="kpi-label">Contas a Receber (Mês)</span>
                <ArrowDownLeft size={18} />
              </div>
              <div className="kpi-value">{fmtCurrency(dashboard?.receivables_month)}</div>
              <div className="kpi-sub">Hoje: {fmtCurrency(dashboard?.receivables_today)}</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-top">
                <span className="kpi-label">Fluxo Projetado Líquido</span>
                <TrendingUp size={18} />
              </div>
              <div className="kpi-value">{fmtCurrency(dashboard?.projected_net_cashflow)}</div>
              <div className="kpi-sub">OPEX: {fmtCurrency(dashboard?.opex_month)} | CAPEX: {fmtCurrency(dashboard?.capex_month)}</div>
            </div>
          </div>

          {/* ABA 1: CONTAS A PAGAR */}
          {activeTab === 'payables' && (
            <div className="tab-pane">
              <div className="pane-toolbar">
                <div className="search-box">
                  <Search size={15} />
                  <input
                    type="text"
                    placeholder="Buscar por favorecido ou descrição..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>

                <div className="filter-group">
                  <select
                    value={payableStatusFilter}
                    onChange={(e) => setPayableStatusFilter(e.target.value)}
                  >
                    <option value="ALL">Todos os Status</option>
                    <option value="PENDING_APPROVAL">Pendente Aprovação</option>
                    <option value="APPROVED">Aprovados</option>
                    <option value="PARTIALLY_PAID">Parcialmente Pago</option>
                    <option value="PAID">Pagos</option>
                    <option value="OVERDUE">Vencidos</option>
                    <option value="CANCELLED">Cancelados</option>
                  </select>

                  <select
                    value={payableNatureFilter}
                    onChange={(e) => setPayableNatureFilter(e.target.value)}
                  >
                    <option value="ALL">Todas as Naturezas</option>
                    <option value="OPEX">OPEX (Operacional)</option>
                    <option value="CAPEX">CAPEX (Investimento)</option>
                    <option value="FINANCIAL">Financeira</option>
                    <option value="TAX">Tributária</option>
                    <option value="PAYROLL">Folha</option>
                    <option value="TRANSFER">Transferência</option>
                    <option value="NOT_APPLICABLE">Não aplicável</option>
                  </select>

                  <select value={payableTypeFilter} onChange={(e) => setPayableTypeFilter(e.target.value)}>
                    <option value="ALL">Todos os Tipos</option>
                    {Object.entries(payableTypeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                  </select>

                  <select value={payableOriginFilter} onChange={(e) => setPayableOriginFilter(e.target.value)}>
                    <option value="ALL">Todas as Origens</option>
                    {Object.entries(payableOriginLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                  </select>
                </div>
              </div>

              <BulkActionsBar selectedCount={payableSelection.selectedCount} resourceName={{ singular: 'conta', plural: 'contas' }} onClear={payableSelection.clearSelection}>
                <button type="button" className="bulk-btn bulk-btn--danger" onClick={() => void runBulkFinanceAction(payableSelection.selectedIdList, 'Cancelar', (id) => financeService.updatePayable(id, { status: 'CANCELLED' }), payableSelection.clearSelection)}><Ban size={14} /> Cancelar selecionadas</button>
                <button type="button" className="bulk-btn" onClick={() => void runBulkFinanceAction(payableSelection.selectedIdList, 'Reabrir', (id) => financeService.reopenPayable(id), payableSelection.clearSelection)}><RotateCcw size={14} /> Reabrir selecionadas</button>
                <button type="button" className="bulk-btn bulk-btn--danger" onClick={() => void runBulkFinanceAction(payableSelection.selectedIdList, 'Excluir', (id) => financeService.deletePayable(id), payableSelection.clearSelection)}><Trash2 size={14} /> Excluir selecionadas</button>
              </BulkActionsBar>
              <div className="table-responsive">
                <table className="finance-table">
                  <thead>
                    <tr>
                      <th className="ui-selection-cell"><input className="ui-selection-checkbox" type="checkbox" aria-label="Selecionar contas desta página" checked={payableSelection.isAllSelected(selectablePayablesOnPage)} onChange={() => payableSelection.toggleSelectAll(selectablePayablesOnPage)} /></th>
                      <th>Favorecido / Descrição</th>
                      <th>Vencimento</th>
                      <th>Classificação</th>
                      <th>Parcela</th>
                      <th>Valor Original</th>
                      <th>Saldo Devedor</th>
                      <th>Status</th>
                      <th className="th-actions">Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredPayables.length === 0 ? (
                      <tr>
                        <td colSpan={9} className="empty-state">
                          Nenhuma conta a pagar encontrada com os filtros selecionados.
                        </td>
                      </tr>
                    ) : (
                      payablePagination.pageItems.map((p) => {
                        const isClickable = !['PAID', 'RECONCILED'].includes(p.status);
                        const boletoInstrument = p.instruments?.find(i => i.instrument_type === 'BOLETO') || p.instruments?.[0];
                        return (
                          <tr
                            key={p.id}
                            className={`${p.status === 'OVERDUE' ? 'row-overdue' : ''} ${isClickable ? 'ui-record-row' : ''} ${payableSelection.isSelected(p.id) ? 'ui-record-row--selected' : ''}`}
                            role={isClickable ? 'button' : undefined}
                            tabIndex={isClickable ? 0 : undefined}
                            onClick={() => isClickable && setEditingRecord({ kind: 'payable', value: p })}
                            onKeyDown={(event) => { if (['Enter', ' '].includes(event.key) && isClickable) { event.preventDefault(); setEditingRecord({ kind: 'payable', value: p }); } }}
                          >
                            <td className="ui-selection-cell">
                              <input
                                className="ui-selection-checkbox"
                                type="checkbox"
                                aria-label={`Selecionar conta ${p.payable_number}`}
                                disabled={['PAID', 'RECONCILED'].includes(p.status)}
                                checked={payableSelection.isSelected(p.id)}
                                onClick={(event) => event.stopPropagation()}
                                onChange={() => payableSelection.toggleSelect(p.id)}
                              />
                            </td>
                            <td>
                              <div className="favored-cell">
                                <RecordLink type="SUPPLIER" id={p.supplier_id} className="favored-name">
                                  {p.favored_name}
                                </RecordLink>
                                <span className="desc-text">{p.description}</span>
                                <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', marginTop: '0.25rem', alignItems: 'center' }}>
                                  {p.purchase_order_id && (
                                    <RecordLink type="PURCHASE_ORDER" id={p.purchase_order_id}>
                                      PO #{p.purchase_order_id.slice(0, 8)}
                                    </RecordLink>
                                  )}
                                  {p.fiscal_document_id && (
                                    <span className="cat-badge" style={{ background: 'rgba(59, 130, 246, 0.12)', color: '#3b82f6', border: '1px solid rgba(59, 130, 246, 0.3)', display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                                      <FileText size={11} /> NF-e Vinculada
                                    </span>
                                  )}
                                  {p.inventory_receipt_id && (
                                    <span className="cat-badge" style={{ background: 'rgba(16, 185, 129, 0.12)', color: '#10b981', border: '1px solid rgba(16, 185, 129, 0.3)', display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                                      <FileCheck size={11} /> Entrada Física
                                    </span>
                                  )}
                                  {boletoInstrument && (
                                    <span className="boleto-tag" title={boletoInstrument.digitable_line || 'Boleto Cadastrado'}>
                                      <Barcode size={11} />
                                      <span>Boleto: {boletoInstrument.digitable_line ? `${boletoInstrument.digitable_line.slice(0, 15)}...` : 'Cadastrado'}</span>
                                      {boletoInstrument.digitable_line && (
                                        <button
                                          type="button"
                                          className="btn-copy-mini"
                                          title="Copiar Linha Digitável"
                                          onClick={(e) => { e.stopPropagation(); handleCopyText(boletoInstrument.digitable_line!, 'Linha digitável'); }}
                                        >
                                          <Copy size={11} />
                                        </button>
                                      )}
                                      {boletoInstrument.file_attachment && (
                                        <a
                                          href={boletoInstrument.file_attachment}
                                          download={`boleto_${p.payable_number}.pdf`}
                                          target="_blank"
                                          rel="noreferrer"
                                          className="btn-copy-mini"
                                          title="Baixar PDF do Boleto"
                                          onClick={(e) => e.stopPropagation()}
                                        >
                                          <ExternalLink size={11} />
                                        </a>
                                      )}
                                    </span>
                                  )}
                                </div>
                              </div>
                            </td>
                            <td>
                              <span className="date-cell">
                                <Calendar size={12} />
                                {fmtDate(p.due_date)}
                              </span>
                            </td>
                            <td>
                              <div className="classification-pill">
                                <span className={`nature-badge ${p.expense_nature.toLowerCase()}`}>
                                  {p.expense_nature}
                                </span>
                                <span className="cat-badge">{payableTypeLabels[p.obligation_type]}</span>
                                <span className="cat-badge">{payableOriginLabels[p.business_origin]}</span>
                                {p.financial_category && (
                                  <span className="cat-badge">{p.financial_category.name}</span>
                                )}
                              </div>
                            </td>
                            <td>
                              <span className="parcel-tag">
                                {p.installment_number}/{p.total_installments}
                              </span>
                            </td>
                            <td>{fmtCurrency(p.original_amount)}</td>
                            <td className="outstanding-val">{fmtCurrency(p.outstanding_amount)}</td>
                            <td>{renderStatusBadge(p.status)}</td>
                            <td className="td-actions">
                              {p.status === 'CANCELLED' ? (
                                <>
                                  <button
                                    className="btn-action-reopen"
                                    onClick={(event) => { event.stopPropagation(); handleReopenPayable(p); }}
                                    title="Reabrir Conta a Pagar"
                                  >
                                    <RotateCcw size={13} />
                                    <span>Reabrir</span>
                                  </button>
                                  <button
                                    className="btn-action-delete"
                                    onClick={(event) => { event.stopPropagation(); handleDeletePayable(p); }}
                                    title="Excluir Permanentemente"
                                  >
                                    <Trash2 size={13} />
                                    <span>Excluir</span>
                                  </button>
                                </>
                              ) : p.status !== 'PAID' ? (
                                <>
                                  <button
                                    className="btn-action-boleto"
                                    onClick={(event) => { event.stopPropagation(); handleOpenBoletoModal(p); }}
                                    title="Gerenciar Boleto / Anexos da Parcela"
                                  >
                                    <Barcode size={13} />
                                    <span>Boleto</span>
                                  </button>
                                  <button
                                    className="btn-action-pay"
                                    onClick={(event) => { event.stopPropagation(); handleOpenPaymentModal(p); }}
                                    title="Efetuar Baixa / Pagamento"
                                  >
                                    <DollarSign size={13} />
                                    <span>Pagar</span>
                                  </button>
                                </>
                              ) : (
                                <span className="paid-icon" title="Conta Liquidada">
                                  <CheckCircle2 size={16} />
                                </span>
                              )}
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
                <ListPagination {...payablePagination} onPageChange={payablePagination.setPage} onPageSizeChange={payablePagination.setPageSize} />
              </div>
            </div>
          )}

          {/* ABA 2: CONTAS A RECEBER */}
          {activeTab === 'receivables' && (
            <div className="tab-pane">
              <div className="pane-toolbar">
                <div className="search-box">
                  <Search size={15} />
                  <input
                    type="text"
                    placeholder="Buscar por cliente ou descrição..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>

                <div className="filter-group">
                  <select
                    value={receivableStatusFilter}
                    onChange={(e) => setReceivableStatusFilter(e.target.value)}
                  >
                    <option value="ALL">Todos os Status</option>
                    <option value="PENDING">Pendente</option>
                    <option value="PARTIALLY_RECEIVED">Parcialmente Recebido</option>
                    <option value="RECEIVED">Recebido</option>
                    <option value="OVERDUE">Vencido</option>
                    <option value="CANCELLED">Cancelados</option>
                  </select>
                </div>
              </div>

              <BulkActionsBar selectedCount={receivableSelection.selectedCount} resourceName={{ singular: 'título', plural: 'títulos' }} onClear={receivableSelection.clearSelection}>
                <button type="button" className="bulk-btn bulk-btn--danger" onClick={() => void runBulkFinanceAction(receivableSelection.selectedIdList, 'Cancelar', (id) => financeService.updateReceivable(id, { status: 'CANCELLED' }), receivableSelection.clearSelection)}><Ban size={14} /> Cancelar selecionados</button>
                <button type="button" className="bulk-btn" onClick={() => void runBulkFinanceAction(receivableSelection.selectedIdList, 'Reabrir', (id) => financeService.reopenReceivable(id), receivableSelection.clearSelection)}><RotateCcw size={14} /> Reabrir selecionados</button>
                <button type="button" className="bulk-btn bulk-btn--danger" onClick={() => void runBulkFinanceAction(receivableSelection.selectedIdList, 'Excluir', (id) => financeService.deleteReceivable(id), receivableSelection.clearSelection)}><Trash2 size={14} /> Excluir selecionados</button>
              </BulkActionsBar>
              <div className="table-responsive">
                <table className="finance-table">
                  <thead>
                    <tr>
                      <th className="ui-selection-cell"><input className="ui-selection-checkbox" type="checkbox" aria-label="Selecionar títulos desta página" checked={receivableSelection.isAllSelected(selectableReceivablesOnPage)} onChange={() => receivableSelection.toggleSelectAll(selectableReceivablesOnPage)} /></th>
                      <th>Cliente / Devedor</th>
                      <th>Descrição</th>
                      <th>Vencimento</th>
                      <th>Valor Original</th>
                      <th>Saldo a Receber</th>
                      <th>Status</th>
                      <th className="th-actions">Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredReceivables.length === 0 ? (
                      <tr>
                        <td colSpan={8} className="empty-state">
                          Nenhum título a receber registrado.
                        </td>
                      </tr>
                    ) : (
                      receivablePagination.pageItems.map((r) => {
                        const isClickable = r.status !== 'RECEIVED';
                        return (
                          <tr
                            key={r.id}
                            className={`${isClickable ? 'ui-record-row' : ''} ${receivableSelection.isSelected(r.id) ? 'ui-record-row--selected' : ''}`}
                            role={isClickable ? 'button' : undefined}
                            tabIndex={isClickable ? 0 : undefined}
                            onClick={() => isClickable && setEditingRecord({ kind: 'receivable', value: r })}
                            onKeyDown={(event) => { if (['Enter', ' '].includes(event.key) && isClickable) { event.preventDefault(); setEditingRecord({ kind: 'receivable', value: r }); } }}
                          >
                            <td className="ui-selection-cell">
                              <input
                                className="ui-selection-checkbox"
                                type="checkbox"
                                aria-label={`Selecionar título ${r.receivable_number}`}
                                disabled={r.status === 'RECEIVED'}
                                checked={receivableSelection.isSelected(r.id)}
                                onClick={(event) => event.stopPropagation()}
                                onChange={() => receivableSelection.toggleSelect(r.id)}
                              />
                            </td>
                            <td>
                              <RecordLink type="CUSTOMER" id={r.customer_id}>
                                <strong>{r.customer_name}</strong>
                              </RecordLink>
                              {r.customer_document && <span className="doc-sub"> ({r.customer_document})</span>}
                              {r.sales_order_id && (
                                <div style={{ marginTop: '0.2rem' }}>
                                  <RecordLink type="SALES_ORDER" id={r.sales_order_id}>
                                    Pedido #{r.sales_order_id.slice(0, 8)}
                                  </RecordLink>
                                </div>
                              )}
                            </td>
                            <td>{r.description}</td>
                            <td>
                              <span className="date-cell">
                                <Calendar size={12} />
                                {fmtDate(r.due_date)}
                              </span>
                            </td>
                            <td>{fmtCurrency(r.original_amount)}</td>
                            <td className="in-amount">{fmtCurrency(r.outstanding_amount)}</td>
                            <td>{renderStatusBadge(r.status)}</td>
                            <td className="td-actions">
                              {r.status === 'CANCELLED' ? (
                                <>
                                  <button
                                    className="btn-action-reopen"
                                    onClick={(event) => { event.stopPropagation(); handleReopenReceivable(r); }}
                                    title="Reabrir Título"
                                  >
                                    <RotateCcw size={13} />
                                    <span>Reabrir</span>
                                  </button>
                                  <button
                                    className="btn-action-delete"
                                    onClick={(event) => { event.stopPropagation(); handleDeleteReceivable(r); }}
                                    title="Excluir Permanentemente"
                                  >
                                    <Trash2 size={13} />
                                    <span>Excluir</span>
                                  </button>
                                </>
                              ) : r.status !== 'RECEIVED' ? (
                                <button
                                  className="btn-action-receive"
                                  onClick={(event) => { event.stopPropagation(); handleOpenReceiptModal(r); }}
                                  title="Registrar Recebimento"
                                >
                                  <CheckCircle2 size={13} />
                                  <span>Receber</span>
                                </button>
                              ) : (
                                <span className="paid-icon" title="Título Recebido">
                                  <CheckCircle2 size={16} />
                                </span>
                              )}
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
                <ListPagination {...receivablePagination} onPageChange={receivablePagination.setPage} onPageSizeChange={receivablePagination.setPageSize} />
              </div>
            </div>
          )}

          {/* ABA 3: TESOURARIA & EXTRATOS */}
          {activeTab === 'treasury' && (
            <div className="tab-pane">
              <div className="treasury-cards-row">
                {bankAccounts.map((acc) => (
                  <div key={acc.id} className="bank-account-card ui-record-card" role="button" tabIndex={0} onClick={() => setEditingRecord({ kind: 'bank', value: acc })} onKeyDown={(event) => { if (['Enter', ' '].includes(event.key)) { event.preventDefault(); setEditingRecord({ kind: 'bank', value: acc }); } }}>
                    <div className="acc-header">
                      <Building2 size={16} />
                      <span className="acc-type">{acc.account_type}</span>
                    </div>
                    <h3 className="acc-name">{acc.bank_name}</h3>
                    <div className="acc-details">
                      {acc.agency && <span>Ag: {acc.agency}</span>}
                      {acc.account_number && <span>CC: {acc.account_number}</span>}
                    </div>
                    <div className="acc-balance">
                      <span className="label">Saldo Atual</span>
                      <span className="val">{fmtCurrency(acc.current_balance)}</span>
                    </div>
                  </div>
                ))}

                <div className="bank-account-card add-account-card" onClick={() => setIsAccountModalOpen(true)}>
                  <Plus size={24} />
                  <span>Adicionar Conta Bancária / Caixa</span>
                </div>
              </div>

              <div className="pane-section-header">
                <h3>Extrato de Movimentações Bancárias</h3>
                <button onClick={() => setIsTxModalOpen(true)}>
                  <Plus size={14} />
                  <span>Lançar Movimentação Manual</span>
                </button>
              </div>

              <div className="table-responsive">
                <table className="finance-table">
                  <thead>
                    <tr>
                      <th>Data</th>
                      <th>Conta</th>
                      <th>Descrição</th>
                      <th>Documento</th>
                      <th>Tipo</th>
                      <th>Valor</th>
                      <th>Saldo Após</th>
                      <th>Nota Fiscal / Comprovante</th>
                      <th>Status Conciliação</th>
                    </tr>
                  </thead>
                  <tbody>
                    {transactions.length === 0 ? (
                      <tr>
                        <td colSpan={9} className="empty-state">
                          Nenhuma movimentação bancária registrada.
                        </td>
                      </tr>
                    ) : (
                      transactionPagination.pageItems.map((tx) => (
                        <tr key={tx.id} className={tx.status === 'pending' ? 'ui-record-row' : ''} role={tx.status === 'pending' ? 'button' : undefined} tabIndex={tx.status === 'pending' ? 0 : undefined} onClick={() => tx.status === 'pending' && setEditingRecord({ kind: 'transaction', value: tx })} onKeyDown={(event) => { if (['Enter', ' '].includes(event.key) && tx.status === 'pending') { event.preventDefault(); setEditingRecord({ kind: 'transaction', value: tx }); } }}>
                          <td>{fmtDate(tx.transaction_date)}</td>
                          <td>{bankAccounts.find(b => b.id === tx.bank_account_id)?.bank_name || '-'}</td>
                          <td>{tx.description}</td>
                          <td>{tx.document_number || '-'}</td>
                          <td>
                            <span className={`tx-pill ${tx.transaction_type.toLowerCase()}`}>
                              {tx.transaction_type === 'CREDIT' ? 'Crédito (+)' : 'Débito (-)'}
                            </span>
                          </td>
                          <td className={tx.transaction_type === 'CREDIT' ? 'in-amount' : 'out-amount'}>
                            {fmtCurrency(tx.amount)}
                          </td>
                          <td>{tx.balance_after ? fmtCurrency(tx.balance_after) : '-'}</td>
                          <td>
                            {tx.transaction_type === 'CREDIT' ? (
                              tx.fiscal_document_id && tx.fiscal_document ? (
                                <div className="doc-link-pill-wrap" onClick={(e) => e.stopPropagation()}>
                                  <RecordLink type="FISCAL_DOCUMENT" id={tx.fiscal_document_id}>
                                    <span className="doc-pill fiscal-pill">
                                      <FileText size={12} />
                                      <span>{tx.fiscal_document.document_type} {tx.fiscal_document.document_number}</span>
                                    </span>
                                  </RecordLink>
                                  <button
                                    type="button"
                                    className="btn-unlink-icon"
                                    title="Desvincular Nota Fiscal"
                                    onClick={(e) => handleUnlinkFiscal(e, tx)}
                                  >
                                    <X size={11} />
                                  </button>
                                </div>
                              ) : (
                                <button
                                  type="button"
                                  className="btn-quick-link-nf"
                                  onClick={(e) => { e.stopPropagation(); handleOpenLinkFiscalModal(tx); }}
                                  title="Vincular ou Cadastrar Nota Fiscal de Entrada"
                                >
                                  <Plus size={12} />
                                  <span>Vincular NF</span>
                                </button>
                              )
                            ) : (
                              tx.receipt_url ? (
                                <div className="doc-link-pill-wrap" onClick={(e) => e.stopPropagation()}>
                                  <a
                                    href={tx.receipt_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="doc-pill receipt-pill"
                                    title="Visualizar Comprovante de Pagamento"
                                  >
                                    <Paperclip size={12} />
                                    <span>{tx.receipt_filename || 'Comprovante'}</span>
                                    <ExternalLink size={10} />
                                  </a>
                                  <button
                                    type="button"
                                    className="btn-unlink-icon"
                                    title="Remover Comprovante"
                                    onClick={(e) => handleRemoveReceipt(e, tx)}
                                  >
                                    <X size={11} />
                                  </button>
                                </div>
                              ) : (
                                <button
                                  type="button"
                                  className="btn-quick-attach-receipt"
                                  onClick={(e) => { e.stopPropagation(); handleOpenAttachReceiptModal(tx); }}
                                  title="Anexar Comprovante de Pagamento"
                                >
                                  <Paperclip size={12} />
                                  <span>Anexar Comp.</span>
                                </button>
                              )
                            )}
                          </td>
                          <td>
                            <span className={`reconcile-badge ${tx.status}`}>
                              {tx.status === 'reconciled' ? 'Conciliado' : 'Pendente'}
                            </span>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
                <ListPagination {...transactionPagination} onPageChange={transactionPagination.setPage} onPageSizeChange={transactionPagination.setPageSize} />
              </div>
            </div>
          )}

          {/* ABA 4: CONCILIAÇÃO BANCÁRIA */}
          {activeTab === 'reconciliation' && (
            <div className="tab-pane">
              <div className="reconciliation-split-view">
                <div className="split-column">
                  <h3>Movimentações do Extrato (Pendentes)</h3>
                  <div className="item-cards-list">
                    {transactions.filter(t => t.status === 'pending').length === 0 ? (
                      <p className="all-clear">🎉 Todas as movimentações bancárias estão conciliadas!</p>
                    ) : (
                      transactions.filter(t => t.status === 'pending').map(tx => (
                        <div key={tx.id} className="reconcile-card">
                          <div className="r-header">
                            <span className="date">{fmtDate(tx.transaction_date)}</span>
                            <span className={`amount ${tx.transaction_type.toLowerCase()}`}>
                              {tx.transaction_type === 'CREDIT' ? '+' : '-'}{fmtCurrency(tx.amount)}
                            </span>
                          </div>
                          <div className="r-desc">{tx.description}</div>
                        </div>
                      ))
                    )}
                  </div>
                </div>

                <div className="split-column">
                  <h3>Pagamentos & Recebimentos do Sistema</h3>
                  <div className="item-cards-list">
                    <p className="hint-text">
                      Os pagamentos e recebimentos baixados com conta bancária são auto-conciliados no ato da baixa.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ABA 5: DOCUMENTOS FISCAIS */}
          {activeTab === 'fiscal-documents' && (
            <div className="tab-pane">
              <BulkActionsBar selectedCount={fiscalSelection.selectedCount} resourceName={{ singular: 'documento', plural: 'documentos' }} onClear={fiscalSelection.clearSelection}>
                <button type="button" className="bulk-btn bulk-btn--danger" onClick={() => void runBulkFinanceAction(fiscalSelection.selectedIdList, 'Cancelar', (id) => financeService.updateFiscalDocument(id, { status: 'CANCELLED' }), fiscalSelection.clearSelection)}><Ban size={14} /> Cancelar rascunhos</button>
              </BulkActionsBar>
              <div className="table-responsive">
                <table className="finance-table">
                  <thead>
                    <tr>
                      <th className="ui-selection-cell"><input className="ui-selection-checkbox" type="checkbox" aria-label="Selecionar documentos fiscais em rascunho" checked={fiscalSelection.isAllSelected(cancellableFiscalOnPage)} onChange={() => fiscalSelection.toggleSelectAll(cancellableFiscalOnPage)} /></th>
                      <th>Direção</th>
                      <th>Tipo</th>
                      <th>Número / Série</th>
                      <th>Emissor</th>
                      <th>Data Emissão</th>
                      <th>Valor Total</th>
                      <th>Impostos</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {fiscalDocs.length === 0 ? (
                      <tr>
                        <td colSpan={9} className="empty-state">
                          Nenhum documento fiscal registrado.
                        </td>
                      </tr>
                    ) : (
                      fiscalPagination.pageItems.map((doc) => (
                        <tr key={doc.id} className={`${doc.status.toLowerCase() !== 'cancelled' ? 'ui-record-row' : ''} ${fiscalSelection.isSelected(doc.id) ? 'ui-record-row--selected' : ''}`} role={doc.status.toLowerCase() !== 'cancelled' ? 'button' : undefined} tabIndex={doc.status.toLowerCase() !== 'cancelled' ? 0 : undefined} onClick={() => doc.status.toLowerCase() !== 'cancelled' && setEditingRecord({ kind: 'fiscal', value: doc })} onKeyDown={(event) => { if (['Enter', ' '].includes(event.key) && doc.status.toLowerCase() !== 'cancelled') { event.preventDefault(); setEditingRecord({ kind: 'fiscal', value: doc }); } }}>
                          <td className="ui-selection-cell"><input className="ui-selection-checkbox" type="checkbox" aria-label={`Selecionar documento ${doc.document_number}`} disabled={!['DRAFT', 'PENDING'].includes(doc.status.toUpperCase())} checked={fiscalSelection.isSelected(doc.id)} onClick={(event) => event.stopPropagation()} onChange={() => fiscalSelection.toggleSelect(doc.id)} /></td>
                          <td>
                            <span className={`direction-badge ${doc.direction.toLowerCase()}`}>
                              {doc.direction === 'INBOUND' ? 'Entrada' : 'Saída'}
                            </span>
                          </td>
                          <td>{doc.document_type}</td>
                          <td><strong>{doc.document_number}</strong> {doc.series && `(Série ${doc.series})`}</td>
                          <td>
                            {doc.direction === 'INBOUND' ? (
                              <RecordLink type="SUPPLIER" id={doc.supplier_id}>
                                {doc.issuer_name}
                              </RecordLink>
                            ) : (
                              <RecordLink type="CUSTOMER" id={doc.customer_id}>
                                {doc.issuer_name || doc.recipient_name}
                              </RecordLink>
                            )}
                          </td>
                          <td>{fmtDate(doc.issue_date)}</td>
                          <td>{fmtCurrency(doc.total_amount)}</td>
                          <td>{fmtCurrency(doc.tax_amount)}</td>
                          <td><span className="badge-approved">{doc.status}</span></td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
                <ListPagination {...fiscalPagination} onPageChange={fiscalPagination.setPage} onPageSizeChange={fiscalPagination.setPageSize} />
              </div>
            </div>
          )}

          {/* ABA 6: CATEGORIAS & CONTAS */}
          {activeTab === 'categories' && (
            <div className="tab-pane">
              <BulkActionsBar selectedCount={categorySelection.selectedCount} resourceName={{ singular: 'categoria', plural: 'categorias' }} onClear={categorySelection.clearSelection}>
                <button type="button" className="bulk-btn bulk-btn--danger" onClick={() => void runBulkFinanceAction(categorySelection.selectedIdList, 'Inativar', (id) => financeService.updateCategory(id, { is_active: false }), categorySelection.clearSelection)}><Power size={14} /> Inativar selecionadas</button>
              </BulkActionsBar>
              <div className="table-responsive">
                <table className="finance-table">
                  <thead>
                    <tr>
                      <th className="ui-selection-cell"><input className="ui-selection-checkbox" type="checkbox" aria-label="Selecionar categorias ativas desta página" checked={categorySelection.isAllSelected(activeCategoriesOnPage)} onChange={() => categorySelection.toggleSelectAll(activeCategoriesOnPage)} /></th>
                      <th>Código</th>
                      <th>Nome da Categoria</th>
                      <th>Tipo</th>
                      <th>Descrição</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {categories.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="empty-state">
                          Nenhuma categoria cadastrada.
                        </td>
                      </tr>
                    ) : (
                      categoryPagination.pageItems.map((c) => (
                        <tr key={c.id} className={`ui-record-row ${categorySelection.isSelected(c.id) ? 'ui-record-row--selected' : ''}`} role="button" tabIndex={0} onClick={() => setEditingRecord({ kind: 'category', value: c })} onKeyDown={(event) => { if (['Enter', ' '].includes(event.key)) { event.preventDefault(); setEditingRecord({ kind: 'category', value: c }); } }}>
                          <td className="ui-selection-cell"><input className="ui-selection-checkbox" type="checkbox" aria-label={`Selecionar categoria ${c.name}`} disabled={!c.is_active} checked={categorySelection.isSelected(c.id)} onClick={(event) => event.stopPropagation()} onChange={() => categorySelection.toggleSelect(c.id)} /></td>
                          <td><code>{c.code || '-'}</code></td>
                          <td><strong>{c.name}</strong></td>
                          <td>
                            <span className={`nature-badge ${c.category_type === 'EXPENSE' ? 'opex' : 'capex'}`}>
                              {c.category_type === 'EXPENSE' ? 'Despesa' : 'Receita'}
                            </span>
                          </td>
                          <td>{c.description || '-'}</td>
                          <td><span className="badge-approved">{c.is_active ? 'Ativa' : 'Inativa'}</span></td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
                <ListPagination {...categoryPagination} onPageChange={categoryPagination.setPage} onPageSizeChange={categoryPagination.setPageSize} />
              </div>
            </div>
          )}

          {/* ABA 7: FLUXO DE CAIXA & DRE */}
          {activeTab === 'reports' && (
            <div className="tab-pane">
              <div className="dre-card">
                <h3>Demonstrativo de Resultado & Fluxo de Caixa (DRE Simplificado)</h3>
                <div className="dre-row">
                  <span>(+) Receitas Previstas (Mês)</span>
                  <span className="in-amount">{fmtCurrency(dashboard?.receivables_month)}</span>
                </div>
                <div className="dre-row">
                  <span>(-) Despesas Operacionais (OPEX)</span>
                  <span className="out-amount">{fmtCurrency(dashboard?.opex_month)}</span>
                </div>
                <div className="dre-row">
                  <span>(-) Investimentos em Ativos (CAPEX)</span>
                  <span className="out-amount">{fmtCurrency(dashboard?.capex_month)}</span>
                </div>
                <div className="dre-row total-row">
                  <span>(=) Resultado Projetado do Exercício</span>
                  <span className={((dashboard?.receivables_month || 0) - (dashboard?.payables_month || 0)) >= 0 ? 'in-amount' : 'out-amount'}>
                    {fmtCurrency((dashboard?.receivables_month || 0) - (dashboard?.payables_month || 0))}
                  </span>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>

      {/* =====================================================================
          MODAIS DO SISTEMA FINANCEIRO (COM SUPORTE A ESC KEY)
          ===================================================================== */}

      {/* MODAL 1: NOVA DESPESA AVULSA */}
      <Modal
        isOpen={isExpenseModalOpen}
        onClose={() => setIsExpenseModalOpen(false)}
        title="Lançar Nova Despesa Avulsa"
        subtitle="Registro de contas a pagar com classificação orçamentária"
        size="lg"
      >
        <form onSubmit={handleCreateExpense} className="wizard-form">
          <div className="form-row">
            <div className="form-group flex-1">
              <label>Pedido de Compra / Reposição</label>
              <select value={expenseForm.purchase_order_id} onChange={(e) => handleExpensePurchaseOrderChange(e.target.value)}>
                <option value="">Sem pedido vinculado</option>
                {purchaseOrders.map(order => <option key={order.id} value={order.id}>{order.order_number} · {order.replenishment_id ? 'Reposição' : 'Compra'} · {fmtCurrency(order.total_amount)}</option>)}
              </select>
            </div>
            <div className="form-group flex-1">
              <label>Documento Fiscal</label>
              <select value={expenseForm.fiscal_document_id} onChange={(e) => setExpenseForm(current => ({ ...current, fiscal_document_id: e.target.value, business_origin: e.target.value ? 'FISCAL_DOCUMENT' : current.business_origin }))}>
                <option value="">Sem documento fiscal vinculado</option>
                {fiscalDocs.filter(doc => doc.direction === 'INBOUND').map(doc => <option key={doc.id} value={doc.id}>{doc.document_type} {doc.document_number} · {doc.issuer_name}</option>)}
              </select>
            </div>
          </div>

          <div className="form-group">
            <label>Fornecedor Cadastrado</label>
            <select value={expenseForm.supplier_id} onChange={(e) => {
              const supplier = suppliers.find(item => item.id === e.target.value);
              setExpenseForm(current => ({ ...current, supplier_id: e.target.value, favored_name: supplier?.name || current.favored_name, obligation_type: e.target.value ? 'GOODS_SUPPLIER' : current.obligation_type }));
            }}>
              <option value="">Sem fornecedor cadastrado</option>
              {suppliers.filter(item => item.is_active).map(item => <option key={item.id} value={item.id}>{item.name} · {item.cnpj_cpf}</option>)}
            </select>
          </div>

          <div className="form-row">
            <div className="form-group flex-2">
              <label>Favorecido / Fornecedor *</label>
              <input
                type="text"
                required
                placeholder="Ex: Copel Energia, Imobiliária Central, AWS"
                value={expenseForm.favored_name}
                onChange={(e) => setExpenseForm({ ...expenseForm, favored_name: e.target.value })}
              />
            </div>

            <div className="form-group flex-1">
              <label>Valor Total (R$) *</label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                required
                placeholder="0,00"
                value={expenseForm.original_amount}
                onChange={(e) => setExpenseForm({ ...expenseForm, original_amount: e.target.value })}
              />
            </div>
          </div>

          <div className="form-group">
            <label>Descrição da Despesa *</label>
            <input
              type="text"
              required
              placeholder="Ex: Conta de Luz referente ao mês de Agosto/2026"
              value={expenseForm.description}
              onChange={(e) => setExpenseForm({ ...expenseForm, description: e.target.value })}
            />
          </div>

          <div className="form-row">
            <div className="form-group flex-1">
              <label>Data de Emissão *</label>
              <input
                type="date"
                required
                value={expenseForm.issue_date}
                onChange={(e) => setExpenseForm({ ...expenseForm, issue_date: e.target.value })}
              />
            </div>

            <div className="form-group flex-1">
              <label>Data de Vencimento *</label>
              <input
                type="date"
                required
                value={expenseForm.due_date}
                onChange={(e) => setExpenseForm({ ...expenseForm, due_date: e.target.value })}
              />
            </div>

            <div className="form-group flex-1">
              <label>Natureza Contábil *</label>
              <select
                value={expenseForm.expense_nature}
                onChange={(e) => setExpenseForm({ ...expenseForm, expense_nature: e.target.value as any })}
              >
                <option value="NOT_APPLICABLE">Não Aplicável</option>
                <option value="FINANCIAL">Despesa Financeira</option>
                <option value="TAX">Tributária</option>
                <option value="PAYROLL">Folha de Pagamento</option>
                <option value="TRANSFER">Transferência</option>
                <option value="OPEX">OPEX (Despesa Operacional)</option>
                <option value="CAPEX">CAPEX (Investimento em Ativos)</option>
              </select>
            </div>
          </div>

          <div className="form-row">
            <div className="form-group flex-1">
              <label>Tipo da Obrigação *</label>
              <select value={expenseForm.obligation_type} onChange={(e) => setExpenseForm({ ...expenseForm, obligation_type: e.target.value as Payable['obligation_type'] })}>
                {Object.entries(payableTypeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </div>
            <div className="form-group flex-1">
              <label>Origem do Negócio *</label>
              <select disabled={!!(expenseForm.purchase_order_id || expenseForm.fiscal_document_id)} value={expenseForm.business_origin} onChange={(e) => setExpenseForm({ ...expenseForm, business_origin: e.target.value as Payable['business_origin'] })}>
                {Object.entries(payableOriginLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </div>
          </div>

          <div className="form-row">
            <div className="form-group flex-1">
              <label>Categoria Financeira</label>
              <select
                value={expenseForm.financial_category_id}
                onChange={(e) => setExpenseForm({ ...expenseForm, financial_category_id: e.target.value })}
              >
                <option value="">Selecione uma categoria...</option>
                {categories.filter(c => c.category_type === 'EXPENSE').map(c => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>

            <div className="form-group flex-1">
              <label>Centro de Custo</label>
              <select
                value={expenseForm.cost_center_id}
                onChange={(e) => setExpenseForm({ ...expenseForm, cost_center_id: e.target.value })}
              >
                <option value="">Selecione um centro de custo...</option>
                {costCenters.map(cc => (
                  <option key={cc.id} value={cc.id}>{cc.name} ({cc.code})</option>
                ))}
              </select>
            </div>
          </div>

          <div className="form-row">
            <div className="form-group flex-1">
              <label>Parcelamento</label>
              <select
                value={expenseForm.installments_count}
                onChange={(e) => setExpenseForm({ ...expenseForm, installments_count: Number(e.target.value) })}
              >
                <option value={1}>À vista (1x)</option>
                <option value={2}>2 Parcelas</option>
                <option value={3}>3 Parcelas</option>
                <option value={6}>6 Parcelas</option>
                <option value={12}>12 Parcelas</option>
              </select>
            </div>

            <div className="form-group flex-1">
              <label>Forma de Pagamento Prevista</label>
              <select
                value={expenseForm.payment_method_expected}
                onChange={(e) => setExpenseForm({ ...expenseForm, payment_method_expected: e.target.value })}
              >
                <option value="BOLETO">Boleto Bancário</option>
                <option value="PIX">PIX</option>
                <option value="TRANSFERENCIA">Transferência Bancária (TED)</option>
                <option value="CARTAO">Cartão de Crédito</option>
              </select>
            </div>
          </div>

          <div className="form-group">
            <label>Linha Digitável do Boleto / Código de Barras (Opcional)</label>
            <input
              type="text"
              placeholder="34191.79001 01043.510047..."
              value={expenseForm.digitable_line}
              onChange={(e) => setExpenseForm({ ...expenseForm, digitable_line: e.target.value })}
            />
          </div>

          <div className="form-row">
            <div className="form-group flex-1">
              <label>Anexar Boleto Bancário (PDF)</label>
              {expenseBoletoFile ? (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.5rem 0.75rem', background: 'rgba(139, 92, 246, 0.1)', border: '1px solid rgba(139, 92, 246, 0.3)', borderRadius: 6, fontSize: '0.825rem' }}>
                  <span style={{ color: '#c4b5fd', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={expenseBoletoFile.name}>
                    📄 {expenseBoletoFile.name}
                  </span>
                  <button type="button" onClick={() => setExpenseBoletoFile(null)} style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', padding: '0 0.25rem' }}>
                    <X size={14} />
                  </button>
                </div>
              ) : (
                <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem', padding: '0.6rem', border: '1px dashed rgba(255,255,255,0.2)', borderRadius: 6, cursor: 'pointer', background: 'rgba(255,255,255,0.02)', fontSize: '0.8rem' }}>
                  <Upload size={14} />
                  <span>Selecionar Boleto PDF</span>
                  <input
                    type="file"
                    accept=".pdf,application/pdf"
                    style={{ display: 'none' }}
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      const reader = new FileReader();
                      reader.onload = (event) => {
                        const dataUrl = event.target?.result as string;
                        setExpenseBoletoFile({ name: file.name, dataUrl });
                        toast.success("Boleto anexado!");
                      };
                      reader.readAsDataURL(file);
                    }}
                  />
                </label>
              )}
            </div>

            <div className="form-group flex-1">
              <label>Anexar Nota Fiscal (PDF ou XML)</label>
              {expenseFiscalFile ? (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.5rem 0.75rem', background: 'rgba(59, 130, 246, 0.1)', border: '1px solid rgba(59, 130, 246, 0.3)', borderRadius: 6, fontSize: '0.825rem' }}>
                  <span style={{ color: '#93c5fd', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={expenseFiscalFile.name}>
                    📄 {expenseFiscalFile.name}
                  </span>
                  <button type="button" onClick={() => setExpenseFiscalFile(null)} style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', padding: '0 0.25rem' }}>
                    <X size={14} />
                  </button>
                </div>
              ) : (
                <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem', padding: '0.6rem', border: '1px dashed rgba(255,255,255,0.2)', borderRadius: 6, cursor: 'pointer', background: 'rgba(255,255,255,0.02)', fontSize: '0.8rem' }}>
                  <Upload size={14} />
                  <span>Selecionar Nota (PDF/XML)</span>
                  <input
                    type="file"
                    accept=".pdf,.xml,application/pdf,text/xml,application/xml"
                    style={{ display: 'none' }}
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      const reader = new FileReader();
                      reader.onload = (event) => {
                        const dataUrl = event.target?.result as string;
                        setExpenseFiscalFile({ name: file.name, dataUrl });
                        const baseName = file.name.replace(/\.[^/.]+$/, "");
                        setExpenseNewFiscalDoc(prev => ({
                          ...prev,
                          document_number: prev.document_number || baseName
                        }));
                        toast.success("Documento fiscal anexado!");
                      };
                      reader.readAsDataURL(file);
                    }}
                  />
                </label>
              )}
            </div>
          </div>

          {expenseFiscalFile && (
            <div className="form-row" style={{ background: 'rgba(59, 130, 246, 0.05)', padding: '0.5rem', borderRadius: 6, marginBottom: '0.75rem', border: '1px solid rgba(59, 130, 246, 0.2)' }}>
              <div className="form-group flex-1">
                <label style={{ fontSize: '0.75rem' }}>Tipo Documento Fiscal</label>
                <select
                  value={expenseNewFiscalDoc.document_type}
                  onChange={(e) => setExpenseNewFiscalDoc({ ...expenseNewFiscalDoc, document_type: e.target.value as any })}
                >
                  <option value="NFE">NF-e (Mercadorias)</option>
                  <option value="NFSE">NFS-e (Serviços)</option>
                  <option value="NFCE">NFC-e (Consumidor)</option>
                  <option value="CTE">CT-e (Transporte)</option>
                  <option value="OUTRO">Outro</option>
                </select>
              </div>
              <div className="form-group flex-1">
                <label style={{ fontSize: '0.75rem' }}>Número da NF</label>
                <input
                  type="text"
                  placeholder="Ex: 12345"
                  value={expenseNewFiscalDoc.document_number}
                  onChange={(e) => setExpenseNewFiscalDoc({ ...expenseNewFiscalDoc, document_number: e.target.value })}
                />
              </div>
              <div className="form-group flex-1">
                <label style={{ fontSize: '0.75rem' }}>Série (opcional)</label>
                <input
                  type="text"
                  placeholder="1"
                  value={expenseNewFiscalDoc.series}
                  onChange={(e) => setExpenseNewFiscalDoc({ ...expenseNewFiscalDoc, series: e.target.value })}
                />
              </div>
            </div>
          )}

          <div className="form-group"><label>Observações</label><textarea rows={3} value={expenseForm.notes} onChange={(e) => setExpenseForm({ ...expenseForm, notes: e.target.value })} /></div>

          <div className="modal-footer">
            <button type="button" className="btn-secondary" onClick={() => setIsExpenseModalOpen(false)}>
              Cancelar (ESC)
            </button>
            <button type="submit" className="btn-primary" disabled={isSubmitting}>
              {isSubmitting ? 'Salvando...' : 'Confirmar Lançamento'}
            </button>
          </div>
        </form>
      </Modal>

      {/* MODAL 2: BAIXA DE PAGAMENTO */}
      <Modal
        isOpen={isPaymentModalOpen && !!selectedPayable}
        onClose={() => setIsPaymentModalOpen(false)}
        title="Efetuar Pagamento / Baixa"
        subtitle="Registro de liquidação de conta a pagar"
        size="md"
      >
        {selectedPayable && (
          <form onSubmit={handleRegisterPayment} className="wizard-form">
            <div className="payable-summary-banner">
              <div>
                <RecordLink type="SUPPLIER" id={selectedPayable.supplier_id}>
                  <strong>{selectedPayable.favored_name}</strong>
                </RecordLink>
                <span>{selectedPayable.description}</span>
              </div>
              <div className="banner-val">
                Saldo Devedor: {fmtCurrency(selectedPayable.outstanding_amount)}
              </div>
            </div>

            {selectedPayable.instruments?.[0]?.digitable_line && (
              <div style={{ background: 'rgba(139, 92, 246, 0.08)', border: '1px solid rgba(139, 92, 246, 0.25)', borderRadius: 6, padding: '0.75rem', marginBottom: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <div style={{ fontSize: '0.725rem', color: '#a78bfa', fontWeight: 600, textTransform: 'uppercase' }}>Linha Digitável do Boleto</div>
                  <div style={{ fontFamily: 'monospace', fontSize: '0.85rem', color: '#fff', marginTop: '0.2rem' }}>{selectedPayable.instruments[0].digitable_line}</div>
                </div>
                <div style={{ display: 'flex', gap: '0.4rem' }}>
                  <button
                    type="button"
                    className="btn-secondary"
                    style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}
                    onClick={() => handleCopyText(selectedPayable.instruments![0].digitable_line!, 'Linha digitável')}
                    title="Copiar linha digitável"
                  >
                    <Copy size={12} /> Copiar
                  </button>
                  {selectedPayable.instruments[0].file_attachment && (
                    <a
                      href={selectedPayable.instruments[0].file_attachment}
                      download={`boleto_${selectedPayable.payable_number}.pdf`}
                      target="_blank"
                      rel="noreferrer"
                      className="btn-secondary"
                      style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}
                      title="Baixar PDF do Boleto"
                    >
                      <ExternalLink size={12} /> Ver Boleto
                    </a>
                  )}
                </div>
              </div>
            )}

            <div className="form-row">
              <div className="form-group flex-1">
                <label>Valor a Pagar (R$) *</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  max={selectedPayable.outstanding_amount}
                  required
                  value={paymentForm.amount}
                  onChange={(e) => setPaymentForm({ ...paymentForm, amount: e.target.value })}
                />
              </div>

              <div className="form-group flex-1">
                <label>Data do Pagamento *</label>
                <input
                  type="date"
                  required
                  value={paymentForm.payment_date}
                  onChange={(e) => setPaymentForm({ ...paymentForm, payment_date: e.target.value })}
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group flex-1">
                <label>Conta de Débito (Bancária / Caixa)</label>
                <select
                  value={paymentForm.bank_account_id}
                  onChange={(e) => setPaymentForm({ ...paymentForm, bank_account_id: e.target.value })}
                >
                  <option value="">Nenhuma (Não debitar no extrato)</option>
                  {bankAccounts.map(b => (
                    <option key={b.id} value={b.id}>{b.bank_name} - Saldo: {fmtCurrency(b.current_balance)}</option>
                  ))}
                </select>
              </div>

              <div className="form-group flex-1">
                <label>Forma de Pagamento *</label>
                <select
                  value={paymentForm.payment_method}
                  onChange={(e) => setPaymentForm({ ...paymentForm, payment_method: e.target.value })}
                >
                  <option value="BOLETO">Boleto Bancário</option>
                  <option value="PIX">PIX</option>
                  <option value="TRANSFERENCIA">Transferência</option>
                  <option value="DEBIT_CARD">Cartão Débito</option>
                  <option value="CREDIT_CARD">Cartão Crédito</option>
                  <option value="CASH">Dinheiro em Espécie</option>
                </select>
              </div>
            </div>

            <div className="modal-footer">
              <button type="button" className="btn-secondary" onClick={() => setIsPaymentModalOpen(false)}>
                Cancelar (ESC)
              </button>
              <button type="submit" className="btn-primary" disabled={isSubmitting}>
                {isSubmitting ? 'Processando...' : 'Confirmar Pagamento'}
              </button>
            </div>
          </form>
        )}
      </Modal>

      {/* MODAL 2.5: GERENCIAR BOLETO DA PARCELA */}
      <Modal
        isOpen={isBoletoModalOpen && !!selectedPayableForBoleto}
        onClose={() => setIsBoletoModalOpen(false)}
        title={`Boleto Bancário - Conta ${selectedPayableForBoleto?.payable_number}`}
        subtitle={`Parcela ${selectedPayableForBoleto?.installment_number}/${selectedPayableForBoleto?.total_installments} · ${selectedPayableForBoleto?.favored_name}`}
        size="md"
      >
        {selectedPayableForBoleto && (
          <form onSubmit={handleSaveBoleto} className="wizard-form">
            <div className="form-group">
              <label>Linha Digitável</label>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <input
                  type="text"
                  placeholder="00190.00009 01234.567890 12345.678901 1 98760000010000"
                  value={boletoForm.digitable_line}
                  onChange={(e) => setBoletoForm({ ...boletoForm, digitable_line: e.target.value })}
                  style={{ flex: 1 }}
                />
                {boletoForm.digitable_line && (
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => handleCopyText(boletoForm.digitable_line, 'Linha digitável')}
                    title="Copiar Linha Digitável"
                  >
                    <Copy size={14} />
                  </button>
                )}
              </div>
            </div>

            <div className="form-group">
              <label>Código de Barras (opcional)</label>
              <input
                type="text"
                placeholder="44 dígitos numéricos"
                value={boletoForm.barcode}
                onChange={(e) => setBoletoForm({ ...boletoForm, barcode: e.target.value })}
              />
            </div>

            <div className="form-row">
              <div className="form-group flex-1">
                <label>Vencimento do Boleto</label>
                <input
                  type="date"
                  value={boletoForm.due_date}
                  onChange={(e) => setBoletoForm({ ...boletoForm, due_date: e.target.value })}
                />
              </div>
              <div className="form-group flex-1">
                <label>Valor do Boleto (R$)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  value={boletoForm.amount}
                  onChange={(e) => setBoletoForm({ ...boletoForm, amount: e.target.value })}
                />
              </div>
            </div>

            <div className="form-group">
              <label>Anexo do Boleto (PDF)</label>
              {boletoForm.file_attachment ? (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.6rem 0.8rem', background: 'rgba(139, 92, 246, 0.1)', border: '1px solid rgba(139, 92, 246, 0.3)', borderRadius: 6 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#c4b5fd', fontSize: '0.85rem' }}>
                    <FileText size={16} />
                    <span>PDF do boleto anexado</span>
                  </div>
                  <div style={{ display: 'flex', gap: '0.4rem' }}>
                    <a
                      href={boletoForm.file_attachment}
                      download={`boleto_${selectedPayableForBoleto.payable_number}.pdf`}
                      target="_blank"
                      rel="noreferrer"
                      className="btn-secondary"
                      style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}
                    >
                      <Download size={13} /> Baixar
                    </a>
                    <button
                      type="button"
                      className="btn-danger"
                      style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                      onClick={() => setBoletoForm({ ...boletoForm, file_attachment: '' })}
                    >
                      <X size={13} /> Remover
                    </button>
                  </div>
                </div>
              ) : (
                <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', padding: '1rem', border: '1px dashed rgba(255,255,255,0.2)', borderRadius: 6, cursor: 'pointer', background: 'rgba(255,255,255,0.02)' }}>
                  <Upload size={16} />
                  <span style={{ fontSize: '0.85rem' }}>Clique para selecionar o PDF do boleto</span>
                  <input
                    type="file"
                    accept=".pdf,application/pdf"
                    style={{ display: 'none' }}
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      const reader = new FileReader();
                      reader.onload = (event) => {
                        const dataUrl = event.target?.result as string;
                        setBoletoForm(prev => ({ ...prev, file_attachment: dataUrl }));
                        toast.success("PDF do boleto carregado!");
                      };
                      reader.readAsDataURL(file);
                    }}
                  />
                </label>
              )}
            </div>

            <div className="modal-footer" style={{ display: 'flex', justifyContent: 'space-between' }}>
              <div>
                {selectedPayableForBoleto.instruments && selectedPayableForBoleto.instruments.length > 0 && (
                  <button
                    type="button"
                    className="btn-danger"
                    onClick={handleDeleteBoleto}
                    disabled={isSubmitting}
                  >
                    <Trash2 size={14} /> Excluir Boleto
                  </button>
                )}
              </div>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button type="button" className="btn-secondary" onClick={() => setIsBoletoModalOpen(false)}>
                  Cancelar
                </button>
                <button type="submit" className="btn-primary" disabled={isSubmitting}>
                  {isSubmitting ? 'Salvando...' : 'Salvar Boleto'}
                </button>
              </div>
            </div>
          </form>
        )}
      </Modal>

      {/* MODAL 3: NOVO TÍTULO A RECEBER */}
      <Modal
        isOpen={isReceivableModalOpen}
        onClose={() => setIsReceivableModalOpen(false)}
        title="Novo Título a Receber"
        subtitle="Registro de previsão de receita comercial ou financeira"
        size="lg"
      >
        <form onSubmit={handleCreateReceivable} className="wizard-form">
          <div className="form-row">
            <div className="form-group flex-1">
              <label>Cliente Cadastrado</label>
              <select
                value={receivableForm.customer_id}
                onChange={(e) => {
                  const selectedId = e.target.value;
                  const selectedCust = customers.find(c => c.id === selectedId);
                  if (selectedCust) {
                    setReceivableForm({
                      ...receivableForm,
                      customer_id: selectedId,
                      customer_name: selectedCust.name,
                      customer_document: selectedCust.document || ''
                    });
                  } else {
                    setReceivableForm({
                      ...receivableForm,
                      customer_id: ''
                    });
                  }
                }}
              >
                <option value="">-- Selecione um cliente cadastrado ou digite avulso --</option>
                {customers.map(cust => (
                  <option key={cust.id} value={cust.id}>
                    {cust.name} {cust.document ? `(${cust.document})` : ''}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group flex-1">
              <label>Cliente / Sacado *</label>
              <input
                type="text"
                required
                placeholder="Ex: Farmácia Central Ltda"
                value={receivableForm.customer_name}
                onChange={(e) => setReceivableForm({ ...receivableForm, customer_name: e.target.value })}
              />
            </div>

            <div className="form-group flex-1">
              <label>CNPJ / CPF</label>
              <input
                type="text"
                placeholder="00.000.000/0001-00"
                value={receivableForm.customer_document}
                onChange={(e) => setReceivableForm({ ...receivableForm, customer_document: e.target.value })}
              />
            </div>
          </div>

          <div className="form-group">
            <label>Descrição do Recebível *</label>
            <input
              type="text"
              required
              placeholder="Ex: Prestação de Serviços de Consultoria Farmacêutica"
              value={receivableForm.description}
              onChange={(e) => setReceivableForm({ ...receivableForm, description: e.target.value })}
            />
          </div>

          <div className="form-row">
            <div className="form-group flex-1">
              <label>Valor Original (R$) *</label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                required
                placeholder="0,00"
                value={receivableForm.original_amount}
                onChange={(e) => setReceivableForm({ ...receivableForm, original_amount: e.target.value })}
              />
            </div>

            <div className="form-group flex-1">
              <label>Data de Emissão *</label>
              <input
                type="date"
                required
                value={receivableForm.issue_date}
                onChange={(e) => setReceivableForm({ ...receivableForm, issue_date: e.target.value })}
              />
            </div>

            <div className="form-group flex-1">
              <label>Data de Vencimento *</label>
              <input
                type="date"
                required
                value={receivableForm.due_date}
                onChange={(e) => setReceivableForm({ ...receivableForm, due_date: e.target.value })}
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group flex-1"><label>Categoria Financeira</label><select value={receivableForm.financial_category_id} onChange={(e) => setReceivableForm({ ...receivableForm, financial_category_id: e.target.value })}><option value="">Sem categoria</option>{categories.filter(item => item.category_type === 'REVENUE').map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div>
            <div className="form-group flex-1"><label>Centro de Custo</label><select value={receivableForm.cost_center_id} onChange={(e) => setReceivableForm({ ...receivableForm, cost_center_id: e.target.value })}><option value="">Sem centro</option>{costCenters.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div>
            <div className="form-group flex-1"><label>Forma Prevista</label><select value={receivableForm.payment_method_expected} onChange={(e) => setReceivableForm({ ...receivableForm, payment_method_expected: e.target.value })}><option value="PIX">PIX</option><option value="BOLETO">Boleto</option><option value="TRANSFERENCIA">Transferência</option><option value="CARTAO">Cartão</option></select></div>
          </div>

          <div className="form-group"><label>Observações</label><textarea rows={3} value={receivableForm.notes} onChange={(e) => setReceivableForm({ ...receivableForm, notes: e.target.value })} /></div>

          <div className="modal-footer">
            <button type="button" className="btn-secondary" onClick={() => setIsReceivableModalOpen(false)}>
              Cancelar (ESC)
            </button>
            <button type="submit" className="btn-primary" disabled={isSubmitting}>
              {isSubmitting ? 'Salvando...' : 'Salvar Título a Receber'}
            </button>
          </div>
        </form>
      </Modal>

      {/* MODAL 4: BAIXA DE RECEBIMENTO */}
      <Modal
        isOpen={isReceiptModalOpen && !!selectedReceivable}
        onClose={() => setIsReceiptModalOpen(false)}
        title="Registrar Recebimento"
        subtitle="Entrada de recursos no caixa ou conta bancária"
        size="md"
      >
        {selectedReceivable && (
          <form onSubmit={handleRegisterReceipt} className="wizard-form">
            <div className="payable-summary-banner">
              <div>
                <RecordLink type="CUSTOMER" id={selectedReceivable.customer_id}>
                  <strong>{selectedReceivable.customer_name}</strong>
                </RecordLink>
                <span>{selectedReceivable.description}</span>
              </div>
              <div className="banner-val" style={{ color: '#10b981' }}>
                Saldo a Receber: {fmtCurrency(selectedReceivable.outstanding_amount)}
              </div>
            </div>

            <div className="form-row">
              <div className="form-group flex-1">
                <label>Valor Recebido (R$) *</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  max={selectedReceivable.outstanding_amount}
                  required
                  value={receiptForm.amount}
                  onChange={(e) => setReceiptForm({ ...receiptForm, amount: e.target.value })}
                />
              </div>

              <div className="form-group flex-1">
                <label>Data do Recebimento *</label>
                <input
                  type="date"
                  required
                  value={receiptForm.receipt_date}
                  onChange={(e) => setReceiptForm({ ...receiptForm, receipt_date: e.target.value })}
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group flex-1">
                <label>Conta de Crédito (Bancária / Caixa)</label>
                <select
                  value={receiptForm.bank_account_id}
                  onChange={(e) => setReceiptForm({ ...receiptForm, bank_account_id: e.target.value })}
                >
                  <option value="">Nenhuma (Não creditar no extrato)</option>
                  {bankAccounts.map(b => (
                    <option key={b.id} value={b.id}>{b.bank_name} - Saldo: {fmtCurrency(b.current_balance)}</option>
                  ))}
                </select>
              </div>

              <div className="form-group flex-1">
                <label>Forma de Recebimento *</label>
                <select
                  value={receiptForm.payment_method}
                  onChange={(e) => setReceiptForm({ ...receiptForm, payment_method: e.target.value })}
                >
                  <option value="PIX">PIX</option>
                  <option value="BOLETO">Boleto Bancário</option>
                  <option value="TRANSFERENCIA">TED / Transferência</option>
                  <option value="DEBIT_CARD">Cartão Débito</option>
                  <option value="CREDIT_CARD">Cartão Crédito</option>
                  <option value="CASH">Dinheiro em Espécie</option>
                </select>
              </div>
            </div>

            <div className="modal-footer">
              <button type="button" className="btn-secondary" onClick={() => setIsReceiptModalOpen(false)}>
                Cancelar (ESC)
              </button>
              <button type="submit" className="btn-primary" disabled={isSubmitting}>
                {isSubmitting ? 'Processando...' : 'Confirmar Recebimento'}
              </button>
            </div>
          </form>
        )}
      </Modal>

      {/* MODAL 5: NOVA CONTA BANCÁRIA */}
      <Modal
        isOpen={isAccountModalOpen}
        onClose={() => setIsAccountModalOpen(false)}
        title="Cadastrar Nova Conta Bancária / Caixa"
        subtitle="Gerenciamento de contas e tesouraria"
        size="md"
      >
        <form onSubmit={handleCreateAccount} className="wizard-form">
          <div className="form-group">
            <label>Nome da Instituição / Descrição da Conta *</label>
            <input
              type="text"
              required
              placeholder="Ex: Banco Itaú - Conta Operacional"
              value={accountForm.bank_name}
              onChange={(e) => setAccountForm({ ...accountForm, bank_name: e.target.value })}
            />
          </div>

          <div className="form-row">
            <div className="form-group flex-1">
              <label>Tipo de Conta *</label>
              <select
                value={accountForm.account_type}
                onChange={(e) => setAccountForm({ ...accountForm, account_type: e.target.value as any })}
              >
                <option value="CHECKING">Conta Corrente</option>
                <option value="SAVINGS">Conta Poupança</option>
                <option value="CASH">Caixa Físico / Gaveta</option>
                <option value="DIGITAL_WALLET">Carteira Digital</option>
              </select>
            </div>

            <div className="form-group flex-1">
              <label>Saldo Inicial (R$)</label>
              <input
                type="number"
                step="0.01"
                placeholder="0,00"
                value={accountForm.opening_balance}
                onChange={(e) => setAccountForm({ ...accountForm, opening_balance: e.target.value })}
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group flex-1">
              <label>Agência</label>
              <input
                type="text"
                placeholder="0001"
                value={accountForm.agency}
                onChange={(e) => setAccountForm({ ...accountForm, agency: e.target.value })}
              />
            </div>

            <div className="form-group flex-1">
              <label>Número da Conta</label>
              <input
                type="text"
                placeholder="12345-6"
                value={accountForm.account_number}
                onChange={(e) => setAccountForm({ ...accountForm, account_number: e.target.value })}
              />
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn-secondary" onClick={() => setIsAccountModalOpen(false)}>
              Cancelar (ESC)
            </button>
            <button type="submit" className="btn-primary" disabled={isSubmitting}>
              {isSubmitting ? 'Salvando...' : 'Salvar Conta'}
            </button>
          </div>
        </form>
      </Modal>

      {/* MODAL 6: NOVA CATEGORIA FINANCEIRA */}
      <Modal
        isOpen={isCategoryModalOpen}
        onClose={() => setIsCategoryModalOpen(false)}
        title="Nova Categoria no Plano de Contas"
        subtitle="Estruturação contábil de receitas e despesas"
        size="md"
      >
        <form onSubmit={handleCreateCategory} className="wizard-form">
          <div className="form-group">
            <label>Nome da Categoria *</label>
            <input
              type="text"
              required
              placeholder="Ex: Energia Elétrica, Aluguel, Venda de Mercadorias"
              value={categoryForm.name}
              onChange={(e) => setCategoryForm({ ...categoryForm, name: e.target.value })}
            />
          </div>

          <div className="form-row">
            <div className="form-group flex-1">
              <label>Tipo de Categoria *</label>
              <select
                value={categoryForm.category_type}
                onChange={(e) => setCategoryForm({ ...categoryForm, category_type: e.target.value as any })}
              >
                <option value="EXPENSE">Despesa (-)</option>
                <option value="REVENUE">Receita (+)</option>
              </select>
            </div>

            <div className="form-group flex-1">
              <label>Código Contábil (Opcional)</label>
              <input
                type="text"
                placeholder="Ex: 3.1.01.05"
                value={categoryForm.code}
                onChange={(e) => setCategoryForm({ ...categoryForm, code: e.target.value })}
              />
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn-secondary" onClick={() => setIsCategoryModalOpen(false)}>
              Cancelar (ESC)
            </button>
            <button type="submit" className="btn-primary" disabled={isSubmitting}>
              {isSubmitting ? 'Salvando...' : 'Salvar Categoria'}
            </button>
          </div>
        </form>
      </Modal>

      {/* MODAL 7: MOVIMENTAÇÃO MANUAL NO EXTRATO */}
      <Modal
        isOpen={isTxModalOpen}
        onClose={() => setIsTxModalOpen(false)}
        title="Lançar Movimentação Manual no Extrato"
        subtitle="Ajuste direto de saldo ou tarifas bancárias"
        size="md"
      >
        <form onSubmit={handleCreateTx} className="wizard-form">
          <div className="form-group">
            <label>Conta Bancária / Caixa *</label>
            <select
              required
              value={txForm.bank_account_id}
              onChange={(e) => setTxForm({ ...txForm, bank_account_id: e.target.value })}
            >
              <option value="">Selecione a conta...</option>
              {bankAccounts.map(b => (
                <option key={b.id} value={b.id}>{b.bank_name}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>Descrição do Lançamento *</label>
            <input
              type="text"
              required
              placeholder="Ex: Rendimento de Aplicação, Tarifa de Manutenção"
              value={txForm.description}
              onChange={(e) => setTxForm({ ...txForm, description: e.target.value })}
            />
          </div>

          <div className="form-row">
            <div className="form-group flex-1">
              <label>Tipo *</label>
              <select
                value={txForm.transaction_type}
                onChange={(e) => setTxForm({ ...txForm, transaction_type: e.target.value })}
              >
                <option value="DEBIT">Débito (-) Saída de Caixa</option>
                <option value="CREDIT">Crédito (+) Entrada em Conta</option>
              </select>
            </div>

            <div className="form-group flex-1">
              <label>Valor (R$) *</label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                required
                value={txForm.amount}
                onChange={(e) => setTxForm({ ...txForm, amount: e.target.value })}
              />
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn-secondary" onClick={() => setIsTxModalOpen(false)}>
              Cancelar (ESC)
            </button>
            <button type="submit" className="btn-primary" disabled={isSubmitting}>
              {isSubmitting ? 'Registrando...' : 'Registrar Movimentação'}
            </button>
          </div>
        </form>
      </Modal>

      {/* MODAL 8: VINCULAR OU CADASTRAR NOTA FISCAL */}
      <Modal
        isOpen={isLinkFiscalModalOpen}
        onClose={() => setIsLinkFiscalModalOpen(false)}
        title="Vincular Documento Fiscal à Movimentação Bancária"
        subtitle="Rastreabilidade contábil entre extrato e faturamento/compras"
        size="lg"
      >
        {selectedTxForLink && (
          <div className="tx-preview-banner">
            <div className="tx-info">
              <span className="tx-title">{selectedTxForLink.description}</span>
              <span className="tx-sub">Data: {fmtDate(selectedTxForLink.transaction_date)} {selectedTxForLink.document_number && `· Doc: ${selectedTxForLink.document_number}`}</span>
            </div>
            <div className={`tx-val ${selectedTxForLink.transaction_type.toLowerCase()}`}>
              {selectedTxForLink.transaction_type === 'CREDIT' ? '+' : '-'}{fmtCurrency(selectedTxForLink.amount)}
            </div>
          </div>
        )}

        <div className="modal-mode-tabs">
          <button
            type="button"
            className={`mode-tab-btn ${fiscalLinkMode === 'EXISTING' ? 'active' : ''}`}
            onClick={() => setFiscalLinkMode('EXISTING')}
          >
            Vincular Nota Já Cadastrada
          </button>
          <button
            type="button"
            className={`mode-tab-btn ${fiscalLinkMode === 'NEW' ? 'active' : ''}`}
            onClick={() => setFiscalLinkMode('NEW')}
          >
            Cadastrar Nova Nota Fiscal
          </button>
        </div>

        <form onSubmit={handleSubmitLinkFiscal} className="wizard-form">
          {fiscalLinkMode === 'EXISTING' ? (
            <div className="form-group">
              <label>Selecione a Nota Fiscal *</label>
              <select
                required
                value={existingFiscalDocId}
                onChange={(e) => setExistingFiscalDocId(e.target.value)}
              >
                <option value="">Selecione um documento fiscal...</option>
                {fiscalDocs.map(doc => (
                  <option key={doc.id} value={doc.id}>
                    {doc.direction === 'INBOUND' ? 'Entrada' : 'Saída'} · {doc.document_type} {doc.document_number} {doc.series && `(Série ${doc.series})`} · {doc.issuer_name || doc.recipient_name} · {fmtCurrency(doc.total_amount)}
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <>
              <div className="form-row">
                <div className="form-group flex-1">
                  <label>Direção Fiscal *</label>
                  <select
                    value={newFiscalDocForm.direction}
                    onChange={(e) => setNewFiscalDocForm({ ...newFiscalDocForm, direction: e.target.value })}
                  >
                    <option value="INBOUND">Entrada (Compra / Recebimento)</option>
                    <option value="OUTBOUND">Saída (Venda / Faturamento)</option>
                  </select>
                </div>

                <div className="form-group flex-1">
                  <label>Tipo de Documento *</label>
                  <select
                    value={newFiscalDocForm.document_type}
                    onChange={(e) => setNewFiscalDocForm({ ...newFiscalDocForm, document_type: e.target.value })}
                  >
                    <option value="NFE">NF-e (Nota Fiscal Eletrônica)</option>
                    <option value="NFSE">NFS-e (Serviços)</option>
                    <option value="NFCE">NFC-e (Consumidor)</option>
                    <option value="OUTRO">Outro Documento</option>
                  </select>
                </div>
              </div>

              <div className="form-row">
                <div className="form-group flex-2">
                  <label>Número do Documento *</label>
                  <input
                    type="text"
                    required
                    placeholder="Ex: 00012345"
                    value={newFiscalDocForm.document_number}
                    onChange={(e) => setNewFiscalDocForm({ ...newFiscalDocForm, document_number: e.target.value })}
                  />
                </div>

                <div className="form-group flex-1">
                  <label>Série</label>
                  <input
                    type="text"
                    placeholder="Ex: 1"
                    value={newFiscalDocForm.series}
                    onChange={(e) => setNewFiscalDocForm({ ...newFiscalDocForm, series: e.target.value })}
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group flex-2">
                  <label>Emissor / Razão Social *</label>
                  <input
                    type="text"
                    required
                    placeholder="Ex: Fornecedor de Medicamentos Ltda"
                    value={newFiscalDocForm.issuer_name}
                    onChange={(e) => setNewFiscalDocForm({ ...newFiscalDocForm, issuer_name: e.target.value })}
                  />
                </div>

                <div className="form-group flex-1">
                  <label>CNPJ / CPF do Emissor</label>
                  <input
                    type="text"
                    placeholder="00.000.000/0001-00"
                    value={newFiscalDocForm.issuer_cnpj_cpf}
                    onChange={(e) => setNewFiscalDocForm({ ...newFiscalDocForm, issuer_cnpj_cpf: e.target.value })}
                  />
                </div>
              </div>

              <div className="form-group">
                <label>Chave de Acesso (44 dígitos)</label>
                <input
                  type="text"
                  maxLength={44}
                  placeholder="35260800000000000000550010000123451000123456"
                  value={newFiscalDocForm.access_key}
                  onChange={(e) => setNewFiscalDocForm({ ...newFiscalDocForm, access_key: e.target.value })}
                />
              </div>

              <div className="form-row">
                <div className="form-group flex-1">
                  <label>Data de Emissão *</label>
                  <input
                    type="date"
                    required
                    value={newFiscalDocForm.issue_date}
                    onChange={(e) => setNewFiscalDocForm({ ...newFiscalDocForm, issue_date: e.target.value })}
                  />
                </div>

                <div className="form-group flex-1">
                  <label>Valor Total (R$) *</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    required
                    value={newFiscalDocForm.total_amount}
                    onChange={(e) => setNewFiscalDocForm({ ...newFiscalDocForm, total_amount: e.target.value })}
                  />
                </div>

                <div className="form-group flex-1">
                  <label>Valor dos Impostos (R$)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={newFiscalDocForm.tax_amount}
                    onChange={(e) => setNewFiscalDocForm({ ...newFiscalDocForm, tax_amount: e.target.value })}
                  />
                </div>
              </div>

              <div className="form-group">
                <label>Anexo XML / PDF (URL ou Base64)</label>
                <input
                  type="text"
                  placeholder="https://... ou cole o link do arquivo"
                  value={newFiscalDocForm.file_attachment}
                  onChange={(e) => setNewFiscalDocForm({ ...newFiscalDocForm, file_attachment: e.target.value })}
                />
              </div>
            </>
          )}

          <div className="modal-footer">
            <button type="button" className="btn-secondary" onClick={() => setIsLinkFiscalModalOpen(false)}>
              Cancelar (ESC)
            </button>
            <button type="submit" className="btn-primary" disabled={isSubmitting}>
              <FileCheck size={16} />
              <span>{isSubmitting ? 'Vinculando...' : 'Confirmar Vínculo Fiscal'}</span>
            </button>
          </div>
        </form>
      </Modal>

      {/* MODAL 9: ANEXAR COMPROVANTE DE PAGAMENTO */}
      <Modal
        isOpen={isAttachReceiptModalOpen}
        onClose={() => setIsAttachReceiptModalOpen(false)}
        title="Anexar Comprovante de Pagamento"
        subtitle="Vínculo de comprovantes bancários a saídas de caixa"
        size="md"
      >
        {selectedTxForLink && (
          <div className="tx-preview-banner">
            <div className="tx-info">
              <span className="tx-title">{selectedTxForLink.description}</span>
              <span className="tx-sub">Data: {fmtDate(selectedTxForLink.transaction_date)} {selectedTxForLink.document_number && `· Doc: ${selectedTxForLink.document_number}`}</span>
            </div>
            <div className="tx-val debit">
              -{fmtCurrency(selectedTxForLink.amount)}
            </div>
          </div>
        )}

        <form onSubmit={handleSubmitAttachReceipt} className="wizard-form">
          <div className="form-group">
            <label>Nome do Comprovante *</label>
            <input
              type="text"
              required
              placeholder="Ex: comprovante_pix_fornecedor.pdf"
              value={txReceiptForm.file_name}
              onChange={(e) => setTxReceiptForm({ ...txReceiptForm, file_name: e.target.value })}
            />
          </div>

          <div className="form-group">
            <label>Arquivo / URL do Comprovante *</label>
            <input
              type="file"
              accept=".pdf,.png,.jpg,.jpeg"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) {
                  const reader = new FileReader();
                  reader.onload = () => {
                    setTxReceiptForm(current => ({
                      ...current,
                      file_name: file.name,
                      file_url: reader.result as string,
                      mime_type: file.type || 'application/pdf'
                    }));
                  };
                  reader.readAsDataURL(file);
                }
              }}
            />
            {txReceiptForm.file_url && (
              <div style={{ marginTop: '0.4rem', fontSize: '0.75rem', color: '#10b981', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                <CheckCircle2 size={13} />
                <span>Arquivo carregado: <strong>{txReceiptForm.file_name}</strong></span>
              </div>
            )}
          </div>

          <div className="form-group">
            <label>Vincular a Conta a Pagar (Opcional)</label>
            <select
              value={txReceiptForm.payable_id}
              onChange={(e) => setTxReceiptForm({ ...txReceiptForm, payable_id: e.target.value })}
            >
              <option value="">Nenhum título vinculado (anexo avulso de extrato)</option>
              {payables.filter(p => p.status === 'PAID' || p.status === 'PARTIALLY_PAID').map(p => (
                <option key={p.id} value={p.id}>
                  {p.favored_name} · {p.description} · {fmtCurrency(p.original_amount)}
                </option>
              ))}
            </select>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn-secondary" onClick={() => setIsAttachReceiptModalOpen(false)}>
              Cancelar (ESC)
            </button>
            <button type="submit" className="btn-primary" disabled={isSubmitting}>
              <Upload size={16} />
              <span>{isSubmitting ? 'Salvando...' : 'Salvar Comprovante'}</span>
            </button>
          </div>
        </form>
      </Modal>

      <FinanceRecordEditModal
        record={editingRecord}
        categories={categories}
        costCenters={costCenters}
        suppliers={suppliers}
        customers={customers}
        bankAccounts={bankAccounts}
        onClose={() => setEditingRecord(null)}
        onSaved={() => void loadAllFinanceData()}
      />

      <ConfirmModal
        isOpen={confirmModal.isOpen}
        title={confirmModal.title}
        subtitle={confirmModal.subtitle}
        message={confirmModal.message}
        confirmText={confirmModal.confirmText}
        cancelText={confirmModal.cancelText}
        type={confirmModal.type}
        isLoading={confirmModal.isLoading}
        errorMessage={confirmModal.errorMessage}
        onClose={closeConfirmModal}
        onConfirm={confirmModal.onConfirm}
      />
    </div>
  );
};

export default Finance;
