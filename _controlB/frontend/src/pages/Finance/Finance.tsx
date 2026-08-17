/**
 * pages/Finance/Finance.tsx - Central de Gestão Financeira (ControlB)
 */

import React, { useState, useEffect } from 'react';
import {
  Landmark, ArrowUpRight, ArrowDownLeft, DollarSign, Plus,
  RefreshCw, CheckCircle2, Calendar, Search,
  FileText, Tag,
  Building2, Wallet, ArrowRightLeft, TrendingUp, BarChart3
} from 'lucide-react';
import { financeService, purchasingService } from '@/services/api';
import {
  Payable, Receivable, BankAccount, BankTransaction,
  FiscalDocument, FinancialCategory, FinanceDashboardSummary, CostCenter
} from '@/types';
import { Modal } from '@/components/Modal/Modal';
import './Finance.scss';

export const Finance: React.FC = () => {
  // Controle de Abas
  const [activeTab, setActiveTab] = useState<
    'payables' | 'receivables' | 'treasury' | 'reconciliation' | 'fiscal-documents' | 'categories' | 'reports'
  >('payables');

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

  // Filtros
  const [payableStatusFilter, setPayableStatusFilter] = useState<string>('ALL');
  const [payableNatureFilter, setPayableNatureFilter] = useState<string>('ALL');
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

  // Seleções para Ações
  const [selectedPayable, setSelectedPayable] = useState<Payable | null>(null);
  const [selectedReceivable, setSelectedReceivable] = useState<Receivable | null>(null);

  // Forms de Nova Despesa Avulsa
  const [expenseForm, setExpenseForm] = useState({
    description: '',
    favored_name: '',
    original_amount: '',
    issue_date: new Date().toISOString().split('T')[0],
    due_date: new Date().toISOString().split('T')[0],
    expense_nature: 'OPEX' as 'CAPEX' | 'OPEX',
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
        costCentersRes
      ] = await Promise.all([
        financeService.getDashboard().catch(() => null),
        financeService.getPayables().catch(() => []),
        financeService.getReceivables().catch(() => []),
        financeService.getBankAccounts().catch(() => []),
        financeService.getBankTransactions().catch(() => []),
        financeService.getFiscalDocuments().catch(() => []),
        financeService.getCategories().catch(() => []),
        purchasingService.getCostCenters().catch(() => [])
      ]);

      setDashboard(dashRes);
      setPayables(payablesRes);
      setReceivables(receivablesRes);
      setBankAccounts(accountsRes);
      setTransactions(txRes);
      setFiscalDocs(fiscalRes);
      setCategories(categoriesRes);
      setCostCenters(costCentersRes);
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
  const handleCreateExpense = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await financeService.createPayable({
        description: expenseForm.description,
        favored_name: expenseForm.favored_name,
        original_amount: parseFloat(expenseForm.original_amount),
        issue_date: expenseForm.issue_date,
        due_date: expenseForm.due_date,
        expense_nature: expenseForm.expense_nature,
        payment_method_expected: expenseForm.payment_method_expected || undefined,
        financial_category_id: expenseForm.financial_category_id || undefined,
        cost_center_id: expenseForm.cost_center_id || undefined,
        installments_count: Number(expenseForm.installments_count) || 1,
        installment_frequency_days: Number(expenseForm.installment_frequency_days) || 30,
        instrument: expenseForm.digitable_line ? {
          instrument_type: 'BOLETO',
          digitable_line: expenseForm.digitable_line,
          pix_code: expenseForm.pix_code || undefined
        } : undefined,
        notes: expenseForm.notes || undefined
      });
      setIsExpenseModalOpen(false);
      setExpenseForm({
        description: '',
        favored_name: '',
        original_amount: '',
        issue_date: new Date().toISOString().split('T')[0],
        due_date: new Date().toISOString().split('T')[0],
        expense_nature: 'OPEX',
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
    } catch (err: any) {
      alert(err.response?.data?.detail || "Erro ao criar despesa.");
    }
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
    if (!selectedPayable) return;
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
    } catch (err: any) {
      alert(err.response?.data?.detail || "Erro ao registrar pagamento.");
    }
  };

  const handleCreateReceivable = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await financeService.createReceivable({
        customer_name: receivableForm.customer_name,
        customer_document: receivableForm.customer_document || undefined,
        description: receivableForm.description,
        original_amount: parseFloat(receivableForm.original_amount),
        issue_date: receivableForm.issue_date,
        due_date: receivableForm.due_date,
        payment_method_expected: receivableForm.payment_method_expected || undefined,
        notes: receivableForm.notes || undefined
      });
      setIsReceivableModalOpen(false);
      setReceivableForm({
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
    } catch (err: any) {
      alert(err.response?.data?.detail || "Erro ao criar título a receber.");
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
    if (!selectedReceivable) return;
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
    } catch (err: any) {
      alert(err.response?.data?.detail || "Erro ao registrar recebimento.");
    }
  };

  const handleCreateAccount = async (e: React.FormEvent) => {
    e.preventDefault();
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
    } catch (err: any) {
      alert(err.response?.data?.detail || "Erro ao cadastrar conta bancária.");
    }
  };

  const handleCreateCategory = async (e: React.FormEvent) => {
    e.preventDefault();
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
    } catch (err: any) {
      alert(err.response?.data?.detail || "Erro ao criar categoria.");
    }
  };

  const handleCreateTx = async (e: React.FormEvent) => {
    e.preventDefault();
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
    } catch (err: any) {
      alert(err.response?.data?.detail || "Erro ao lançar movimentação.");
    }
  };

  // Filtragem
  const filteredPayables = payables.filter(p => {
    const matchesStatus = payableStatusFilter === 'ALL' || p.status === payableStatusFilter;
    const matchesNature = payableNatureFilter === 'ALL' || p.expense_nature === payableNatureFilter;
    const matchesSearch = searchTerm === '' ||
      p.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.favored_name.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesStatus && matchesNature && matchesSearch;
  });

  const filteredReceivables = receivables.filter(r => {
    const matchesStatus = receivableStatusFilter === 'ALL' || r.status === receivableStatusFilter;
    const matchesSearch = searchTerm === '' ||
      r.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.customer_name.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesStatus && matchesSearch;
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
                  </select>

                  <select
                    value={payableNatureFilter}
                    onChange={(e) => setPayableNatureFilter(e.target.value)}
                  >
                    <option value="ALL">Todas as Naturezas</option>
                    <option value="OPEX">OPEX (Operacional)</option>
                    <option value="CAPEX">CAPEX (Investimento)</option>
                  </select>
                </div>
              </div>

              <div className="table-responsive">
                <table className="finance-table">
                  <thead>
                    <tr>
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
                        <td colSpan={8} className="empty-state">
                          Nenhuma conta a pagar encontrada com os filtros selecionados.
                        </td>
                      </tr>
                    ) : (
                      filteredPayables.map((p) => (
                        <tr key={p.id} className={p.status === 'OVERDUE' ? 'row-overdue' : ''}>
                          <td>
                            <div className="favored-cell">
                              <span className="favored-name">{p.favored_name}</span>
                              <span className="desc-text">{p.description}</span>
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
                            {p.status !== 'PAID' && p.status !== 'CANCELLED' ? (
                              <button
                                className="btn-action-pay"
                                onClick={() => handleOpenPaymentModal(p)}
                                title="Efetuar Baixa / Pagamento"
                              >
                                <DollarSign size={13} />
                                <span>Pagar</span>
                              </button>
                            ) : (
                              <span className="paid-icon" title="Conta Liquidada">
                                <CheckCircle2 size={16} />
                              </span>
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
                  </select>
                </div>
              </div>

              <div className="table-responsive">
                <table className="finance-table">
                  <thead>
                    <tr>
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
                        <td colSpan={7} className="empty-state">
                          Nenhum título a receber registrado.
                        </td>
                      </tr>
                    ) : (
                      filteredReceivables.map((r) => (
                        <tr key={r.id}>
                          <td>
                            <strong>{r.customer_name}</strong>
                            {r.customer_document && <span className="doc-sub"> ({r.customer_document})</span>}
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
                            {r.status !== 'RECEIVED' && r.status !== 'CANCELLED' && (
                              <button
                                className="btn-action-receive"
                                onClick={() => handleOpenReceiptModal(r)}
                                title="Registrar Recebimento"
                              >
                                <CheckCircle2 size={13} />
                                <span>Receber</span>
                              </button>
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

          {/* ABA 3: TESOURARIA & EXTRATOS */}
          {activeTab === 'treasury' && (
            <div className="tab-pane">
              <div className="treasury-cards-row">
                {bankAccounts.map((acc) => (
                  <div key={acc.id} className="bank-account-card">
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
                      <th>Status Conciliação</th>
                    </tr>
                  </thead>
                  <tbody>
                    {transactions.length === 0 ? (
                      <tr>
                        <td colSpan={8} className="empty-state">
                          Nenhuma movimentação bancária registrada.
                        </td>
                      </tr>
                    ) : (
                      transactions.map((tx) => (
                        <tr key={tx.id}>
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
                            <span className={`reconcile-badge ${tx.status}`}>
                              {tx.status === 'reconciled' ? 'Conciliado' : 'Pendente'}
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
              <div className="table-responsive">
                <table className="finance-table">
                  <thead>
                    <tr>
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
                        <td colSpan={8} className="empty-state">
                          Nenhum documento fiscal registrado.
                        </td>
                      </tr>
                    ) : (
                      fiscalDocs.map((doc) => (
                        <tr key={doc.id}>
                          <td>
                            <span className={`direction-badge ${doc.direction.toLowerCase()}`}>
                              {doc.direction === 'INBOUND' ? 'Entrada' : 'Saída'}
                            </span>
                          </td>
                          <td>{doc.document_type}</td>
                          <td><strong>{doc.document_number}</strong> {doc.series && `(Série ${doc.series})`}</td>
                          <td>{doc.issuer_name}</td>
                          <td>{fmtDate(doc.issue_date)}</td>
                          <td>{fmtCurrency(doc.total_amount)}</td>
                          <td>{fmtCurrency(doc.tax_amount)}</td>
                          <td><span className="badge-approved">{doc.status}</span></td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ABA 6: CATEGORIAS & CONTAS */}
          {activeTab === 'categories' && (
            <div className="tab-pane">
              <div className="table-responsive">
                <table className="finance-table">
                  <thead>
                    <tr>
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
                        <td colSpan={5} className="empty-state">
                          Nenhuma categoria cadastrada.
                        </td>
                      </tr>
                    ) : (
                      categories.map((c) => (
                        <tr key={c.id}>
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
              <label>Classificação *</label>
              <select
                value={expenseForm.expense_nature}
                onChange={(e) => setExpenseForm({ ...expenseForm, expense_nature: e.target.value as any })}
              >
                <option value="OPEX">OPEX (Despesa Operacional)</option>
                <option value="CAPEX">CAPEX (Investimento em Ativos)</option>
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

          <div className="modal-footer">
            <button type="button" className="btn-secondary" onClick={() => setIsExpenseModalOpen(false)}>
              Cancelar (ESC)
            </button>
            <button type="submit" className="btn-primary">
              Confirmar Lançamento
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
                <strong>{selectedPayable.favored_name}</strong>
                <span>{selectedPayable.description}</span>
              </div>
              <div className="banner-val">
                Saldo Devedor: {fmtCurrency(selectedPayable.outstanding_amount)}
              </div>
            </div>

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
              <button type="submit" className="btn-primary">
                Confirmar Pagamento
              </button>
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
            <div className="form-group flex-2">
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

          <div className="modal-footer">
            <button type="button" className="btn-secondary" onClick={() => setIsReceivableModalOpen(false)}>
              Cancelar (ESC)
            </button>
            <button type="submit" className="btn-primary">
              Salvar Título a Receber
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
                <strong>{selectedReceivable.customer_name}</strong>
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
              <button type="submit" className="btn-primary">
                Confirmar Recebimento
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
            <button type="submit" className="btn-primary">
              Salvar Conta
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
            <button type="submit" className="btn-primary">
              Salvar Categoria
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
            <button type="submit" className="btn-primary">
              Registrar Movimentação
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

export default Finance;
