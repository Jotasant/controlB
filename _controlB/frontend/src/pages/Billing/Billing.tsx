import React, { FormEvent, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  AlertCircle, Ban, Building2, ClipboardList, DollarSign, Eye,
  FileText, Layers, Plus, ReceiptText, RefreshCw, TrendingUp
} from 'lucide-react';
import { billingService, financeService, formatApiError } from '@/services/api';
import type { BusinessDocument, FiscalDocument, Invoice } from '@/types';
import { Modal } from '@/components/Modal/Modal';
import { BulkActionsBar } from '@/components/BulkActionsBar';
import { ListPagination } from '@/components/ListPagination';
import {
  FinanceRecordEditModal,
  type EditableFinanceRecord
} from '@/components/FinanceRecordEditModal/FinanceRecordEditModal';
import { useBulkSelection } from '@/hooks/useBulkSelection';
import { useListPagination } from '@/hooks/useListPagination';
import { usePermissions } from '@/hooks/usePermissions';
import { RecordLink, useRecordDeepLink, isRequestedView } from '@/components/RecordLink';
import './Billing.scss';

const ALLOWED_BILLING_TABS = ['requests', 'invoices', 'outbound-nfe'] as const;
type BillingTab = typeof ALLOWED_BILLING_TABS[number];

type BillingRequestItem = {
  sales_order_item_id: string;
  product_id: string;
  product_name: string;
  product_sku?: string | null;
  quantity: string | number;
  unit_price: string | number;
  discount_amount: string | number;
  total_price: string | number;
};

const today = () => new Date().toISOString().split('T')[0];
const defaultDueDate = () => new Date(Date.now() + 30 * 86400000).toISOString().split('T')[0];
const emptyInvoiceForm = () => ({
  customer_name: '', customer_document: '', total_amount: '', tax_amount: '0.00',
  issue_date: today(), due_date: defaultDueDate(), installments_count: '1', notes: '',
  generate_receivables_in_finance: true, generate_outbound_fiscal_document: true,
  fiscal_document_type: 'NFE' as 'NFE' | 'NFSE' | 'NFCE' | 'OUTRO',
  fiscal_document_number: '', fiscal_series: '', fiscal_access_key: ''
});
const emptyRequestIssueForm = () => ({
  issue_date: today(), due_date: defaultDueDate(), installments_count: '1', tax_amount: '0.00', notes: '',
  generate_receivables_in_finance: true, generate_outbound_fiscal_document: true,
  fiscal_document_type: 'NFE' as 'NFE' | 'NFSE' | 'NFCE' | 'OUTRO',
  fiscal_document_number: '', fiscal_series: '', fiscal_access_key: ''
});

export const Billing: React.FC = () => {
  const { hasPermission } = usePermissions();
  const canManageBilling = hasPermission('billing:manage');
  const [searchParams] = useSearchParams();
  const initialBillingTab = isRequestedView(searchParams, ALLOWED_BILLING_TABS, 'requests');
  const [activeTab, setActiveTab] = useState<BillingTab>(initialBillingTab);
  const [loading, setLoading] = useState(true);
  const [requests, setRequests] = useState<BusinessDocument[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [fiscalDocs, setFiscalDocs] = useState<FiscalDocument[]>([]);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [isInvoiceModalOpen, setIsInvoiceModalOpen] = useState(false);
  const [processingRequest, setProcessingRequest] = useState<BusinessDocument | null>(null);
  const [requestIssueForm, setRequestIssueForm] = useState(emptyRequestIssueForm);
  const [requestItemQuantities, setRequestItemQuantities] = useState<Record<string, string>>({});
  const [cancellingRequest, setCancellingRequest] = useState<BusinessDocument | null>(null);
  const [requestCancelReason, setRequestCancelReason] = useState('');
  const [invoiceForm, setInvoiceForm] = useState(emptyInvoiceForm);
  const [selectedInvoice, setSelectedInvoice] = useState<Invoice | null>(null);
  const [editingInvoice, setEditingInvoice] = useState<Invoice | null>(null);
  const [editForm, setEditForm] = useState({ customer_name: '', customer_document: '', issue_date: '', due_date: '', notes: '' });
  const [cancellingInvoice, setCancellingInvoice] = useState<Invoice | null>(null);
  const [cancelReason, setCancelReason] = useState('');
  const [editingFinanceRecord, setEditingFinanceRecord] = useState<EditableFinanceRecord | null>(null);
  const [saving, setSaving] = useState(false);
  const invoiceSelection = useBulkSelection<Invoice>();
  const fiscalSelection = useBulkSelection<FiscalDocument>();
  const requestSelection = useBulkSelection<BusinessDocument>();

  const loadBillingData = async () => {
    setLoading(true);
    try {
      const [requestResult, invoiceResult, fiscalResult] = await Promise.all([
        billingService.getRequests(true), billingService.getInvoices(true),
        financeService.getFiscalDocuments('OUTBOUND', undefined, true)
      ]);
      setRequests(requestResult);
      setInvoices(invoiceResult);
      setFiscalDocs(fiscalResult);
    } catch (error) {
      setFeedback({ type: 'error', text: formatApiError(error, 'Não foi possível carregar o faturamento.') });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void loadBillingData(); }, []);

  const fmtCurrency = (value: number | undefined | null) =>
    new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value || 0);
  const fmtDate = (value: string | undefined | null) => {
    if (!value) return '-';
    const parts = value.split('T')[0].split('-');
    return parts.length === 3 ? `${parts[2]}/${parts[1]}/${parts[0]}` : value;
  };
  const statusLabel = (value: string) => ({
    REQUESTED: 'Solicitado', COMPLETED: 'Concluído', ISSUED: 'Emitida',
    PARTIALLY_RECEIVED: 'Recebida parcialmente', OVERDUE: 'Vencida', PAID: 'Paga',
    CANCELLED: 'Cancelada', PENDING: 'Pendente', DRAFT: 'Rascunho', AUTHORIZED: 'Autorizada'
  }[value.toUpperCase()] || value);

  const handleCreateInvoice = async (event: FormEvent) => {
    event.preventDefault(); setSaving(true); setFeedback(null);
    try {
      await billingService.createInvoice({
        customer_name: invoiceForm.customer_name,
        customer_document: invoiceForm.customer_document || undefined,
        total_amount: Number(invoiceForm.total_amount), tax_amount: Number(invoiceForm.tax_amount || 0),
        issue_date: invoiceForm.issue_date, due_date: invoiceForm.due_date,
        installments_count: Number(invoiceForm.installments_count), notes: invoiceForm.notes || undefined,
        generate_receivables_in_finance: invoiceForm.generate_receivables_in_finance,
        generate_outbound_fiscal_document: invoiceForm.generate_outbound_fiscal_document,
        fiscal_document_type: invoiceForm.fiscal_document_type,
        fiscal_document_number: invoiceForm.fiscal_document_number || undefined,
        fiscal_series: invoiceForm.fiscal_series || undefined,
        fiscal_access_key: invoiceForm.fiscal_access_key || undefined
      });
      setIsInvoiceModalOpen(false); setInvoiceForm(emptyInvoiceForm());
      setFeedback({ type: 'success', text: 'Fatura emitida e integrações financeiras geradas com sucesso.' });
      await loadBillingData(); setActiveTab('invoices');
    } catch (error) {
      setFeedback({ type: 'error', text: formatApiError(error, 'Erro ao emitir a fatura.') });
    } finally { setSaving(false); }
  };

  const openInvoiceEdit = (invoice: Invoice) => {
    setEditingInvoice(invoice);
    setEditForm({ customer_name: invoice.customer_name, customer_document: invoice.customer_document || '', issue_date: invoice.issue_date, due_date: invoice.due_date, notes: invoice.notes || '' });
  };
  const openInvoiceRecord = (invoice: Invoice) => {
    if (!canManageBilling || ['PAID', 'CANCELLED'].includes(invoice.status)) setSelectedInvoice(invoice);
    else openInvoiceEdit(invoice);
  };
  const handleUpdateInvoice = async (event: FormEvent) => {
    event.preventDefault(); if (!editingInvoice) return; setSaving(true);
    try {
      const partial = editingInvoice.status === 'PARTIALLY_RECEIVED';
      await billingService.updateInvoice(editingInvoice.id, partial ? { notes: editForm.notes || null } : {
        customer_name: editForm.customer_name, customer_document: editForm.customer_document || null,
        issue_date: editForm.issue_date, due_date: editForm.due_date, notes: editForm.notes || null
      });
      setEditingInvoice(null); setFeedback({ type: 'success', text: 'Fatura e títulos em aberto atualizados.' });
      await loadBillingData();
    } catch (error) {
      setFeedback({ type: 'error', text: formatApiError(error, 'Não foi possível editar a fatura.') });
    } finally { setSaving(false); }
  };
  const handleCancelInvoice = async (event: FormEvent) => {
    event.preventDefault(); if (!cancellingInvoice) return; setSaving(true);
    try {
      await billingService.cancelInvoice(cancellingInvoice.id, cancelReason);
      setCancellingInvoice(null); setCancelReason('');
      setFeedback({ type: 'success', text: 'Fatura e registros derivados em aberto foram cancelados.' });
      await loadBillingData();
    } catch (error) {
      setFeedback({ type: 'error', text: formatApiError(error, 'Não foi possível cancelar a fatura.') });
    } finally { setSaving(false); }
  };

  const requestItems = (request: BusinessDocument): BillingRequestItem[] => (
    Array.isArray(request.payload.items) ? request.payload.items as BillingRequestItem[] : []
  );
  const billedQuantity = (request: BusinessDocument, orderItemId: string) => invoices
    .filter(invoice => invoice.sales_order_id === String(request.payload.sales_order_id || '') && invoice.status !== 'CANCELLED')
    .flatMap(invoice => invoice.items || [])
    .filter(item => item.sales_order_item_id === orderItemId)
    .reduce((sum, item) => sum + Number(item.quantity), 0);
  const billedDiscount = (request: BusinessDocument, orderItemId: string) => invoices
    .filter(invoice => invoice.sales_order_id === String(request.payload.sales_order_id || '') && invoice.status !== 'CANCELLED')
    .flatMap(invoice => invoice.items || [])
    .filter(item => item.sales_order_item_id === orderItemId)
    .reduce((sum, item) => sum + Number(item.discount_amount), 0);
  const remainingQuantity = (request: BusinessDocument, item: BillingRequestItem) => Math.max(
    0, Number(item.quantity) - billedQuantity(request, item.sales_order_item_id)
  );
  const estimatedLineTotal = (request: BusinessDocument, item: BillingRequestItem, quantity: number) => {
    const remaining = remainingQuantity(request, item);
    const discount = Math.abs(quantity - remaining) < 0.00001
      ? Math.max(0, Number(item.discount_amount || 0) - billedDiscount(request, item.sales_order_item_id))
      : Number(item.discount_amount || 0) * quantity / Number(item.quantity);
    return Number(item.unit_price) * quantity - discount;
  };

  const requestInvoice = (request: BusinessDocument) => {
    const invoiceId = String(request.payload.invoice_id || '');
    if (invoiceId) return invoices.find(item => item.id === invoiceId);
    if (request.current_status !== 'COMPLETED') return undefined;
    return invoices.find(item => item.sales_order_id === String(request.payload.sales_order_id || ''));
  };
  const openRequestRecord = (request: BusinessDocument) => {
    const invoice = requestInvoice(request);
    if (invoice) { openInvoiceRecord(invoice); return; }
    if (request.current_status === 'REQUESTED' && !canManageBilling) {
      setFeedback({ type: 'error', text: 'Seu perfil possui acesso de consulta, mas não pode processar faturamentos.' });
      return;
    }
    setProcessingRequest(request);
    setRequestIssueForm(emptyRequestIssueForm());
    setRequestItemQuantities(Object.fromEntries(
      requestItems(request).map(item => [
        item.sales_order_item_id,
        String(remainingQuantity(request, item))
      ])
    ));
  };
  const selectedRequestLines = processingRequest ? requestItems(processingRequest)
    .map(item => ({ item, quantity: Number(requestItemQuantities[item.sales_order_item_id] || 0) }))
    .filter(line => line.quantity > 0) : [];
  const selectedRequestSubtotal = selectedRequestLines.reduce((sum, { item, quantity }) => {
    return sum + (processingRequest ? estimatedLineTotal(processingRequest, item, quantity) : 0);
  }, 0);

  const handleIssueRequest = async (event: FormEvent) => {
    event.preventDefault();
    if (!processingRequest || (requestItems(processingRequest).length > 0 && selectedRequestLines.length === 0)) {
      setFeedback({ type: 'error', text: 'Selecione ao menos uma quantidade para faturar.' });
      return;
    }
    setSaving(true); setFeedback(null);
    try {
      const invoice = await billingService.issueRequest(processingRequest.id, {
        issue_date: requestIssueForm.issue_date,
        due_date: requestIssueForm.due_date,
        installments_count: Number(requestIssueForm.installments_count),
        tax_amount: Number(requestIssueForm.tax_amount || 0),
        notes: requestIssueForm.notes || undefined,
        generate_receivables_in_finance: requestIssueForm.generate_receivables_in_finance,
        generate_outbound_fiscal_document: requestIssueForm.generate_outbound_fiscal_document,
        fiscal_document_type: requestIssueForm.fiscal_document_type,
        fiscal_document_number: requestIssueForm.fiscal_document_number || undefined,
        fiscal_series: requestIssueForm.fiscal_series || undefined,
        fiscal_access_key: requestIssueForm.fiscal_access_key || undefined,
        items: requestItems(processingRequest).length > 0 ? selectedRequestLines.map(({ item, quantity }) => ({
          sales_order_item_id: item.sales_order_item_id, quantity
        })) : undefined
      });
      setProcessingRequest(null);
      setFeedback({ type: 'success', text: `Fatura ${invoice.invoice_number}, documento fiscal e títulos financeiros gerados.` });
      await loadBillingData(); setActiveTab('invoices');
    } catch (error) {
      setFeedback({ type: 'error', text: formatApiError(error, 'Não foi possível processar a solicitação.') });
    } finally { setSaving(false); }
  };

  const handleCancelRequest = async (event: FormEvent) => {
    event.preventDefault(); if (!cancellingRequest) return; setSaving(true);
    try {
      await billingService.cancelRequest(cancellingRequest.id, requestCancelReason);
      requestSelection.deselect(cancellingRequest.id);
      setCancellingRequest(null); setRequestCancelReason('');
      setFeedback({ type: 'success', text: 'Solicitação cancelada; o saldo do pedido foi reaberto.' });
      await loadBillingData();
    } catch (error) {
      setFeedback({ type: 'error', text: formatApiError(error, 'Não foi possível cancelar a solicitação.') });
    } finally { setSaving(false); }
  };

  const activeInvoices = useMemo(() => invoices.filter(item => item.status !== 'CANCELLED'), [invoices]);
  const totalInvoiced = activeInvoices.reduce((sum, item) => sum + (item.net_amount || 0), 0);
  const totalTax = activeInvoices.reduce((sum, item) => sum + (item.tax_amount || 0), 0);
  const requestPagination = useListPagination(requests);
  const invoicePagination = useListPagination(invoices);
  const fiscalPagination = useListPagination(fiscalDocs);
  const cancellableInvoices = invoicePagination.pageItems.filter(item => !['PAID', 'CANCELLED'].includes(item.status));
  const cancellableFiscalDocs = fiscalPagination.pageItems.filter(item => ['DRAFT', 'PENDING'].includes(item.status.toUpperCase()));
  const pendingRequests = requestPagination.pageItems.filter(item => item.current_status === 'REQUESTED');

  useRecordDeepLink({
    types: ['INVOICE'],
    records: invoices,
    onOpen: (inv) => {
      setActiveTab('invoices');
      openInvoiceRecord(inv);
    },
  });

  useRecordDeepLink({
    types: ['BILLING_REQUEST'],
    records: requests,
    onOpen: (req) => {
      setActiveTab('requests');
      openRequestRecord(req);
    },
  });

  useRecordDeepLink({
    types: ['FISCAL_DOCUMENT'],
    records: fiscalDocs,
    onOpen: (doc) => {
      setActiveTab('outbound-nfe');
      setEditingFinanceRecord({ kind: 'fiscal', value: doc });
    },
  });

  const handleBulkCancelRequests = async () => {
    const selected = requests.filter(item => requestSelection.isSelected(item.id) && item.current_status === 'REQUESTED');
    if (selected.length === 0) return;
    const reason = window.prompt(`Informe o motivo para cancelar ${selected.length} solicitação(ões):`);
    if (!reason || reason.trim().length < 3) return;
    if (!window.confirm(`Cancelar ${selected.length} solicitação(ões) pendente(s)?`)) return;
    setSaving(true);
    const results = await Promise.allSettled(selected.map(item => billingService.cancelRequest(item.id, reason.trim())));
    const succeeded = results.filter(item => item.status === 'fulfilled').length;
    const failed = results.length - succeeded;
    requestSelection.clearSelection();
    setFeedback({ type: failed ? 'error' : 'success', text: failed ? `${succeeded} solicitação(ões) cancelada(s); ${failed} falharam.` : `${succeeded} solicitação(ões) cancelada(s).` });
    await loadBillingData(); setSaving(false);
  };

  const handleBulkCancelInvoices = async () => {
    const selected = invoices.filter(item => invoiceSelection.isSelected(item.id) && !['PAID', 'CANCELLED'].includes(item.status));
    if (selected.length === 0) return;
    const reason = window.prompt(`Informe o motivo para cancelar ${selected.length} fatura(s):`);
    if (!reason || reason.trim().length < 3) return;
    if (!window.confirm(`Cancelar ${selected.length} fatura(s) e seus registros derivados em aberto?`)) return;
    setSaving(true);
    const results = await Promise.allSettled(selected.map(item => billingService.cancelInvoice(item.id, reason.trim())));
    const succeeded = results.filter(item => item.status === 'fulfilled').length;
    const failed = results.length - succeeded;
    invoiceSelection.clearSelection();
    setFeedback({
      type: failed ? 'error' : 'success',
      text: failed ? `${succeeded} fatura(s) cancelada(s); ${failed} não puderam ser canceladas.` : `${succeeded} fatura(s) cancelada(s) com sucesso.`,
    });
    await loadBillingData();
    setSaving(false);
  };

  const handleBulkCancelFiscalDocs = async () => {
    const selected = fiscalDocs.filter(item => fiscalSelection.isSelected(item.id) && ['DRAFT', 'PENDING'].includes(item.status.toUpperCase()));
    if (selected.length === 0 || !window.confirm(`Cancelar ${selected.length} documento(s) fiscal(is) ainda não autorizado(s)?`)) return;
    setSaving(true);
    const results = await Promise.allSettled(selected.map(item => financeService.updateFiscalDocument(item.id, { status: 'CANCELLED' })));
    const succeeded = results.filter(item => item.status === 'fulfilled').length;
    const failed = results.length - succeeded;
    fiscalSelection.clearSelection();
    setFeedback({ type: failed ? 'error' : 'success', text: failed ? `${succeeded} documento(s) cancelado(s); ${failed} falharam.` : `${succeeded} documento(s) cancelado(s).` });
    await loadBillingData();
    setSaving(false);
  };

  return (
    <div className="billing-page">
      <div className="billing-layout">
        <aside className="sidebar-left">
          <div className="sidebar-header"><ReceiptText className="brand-icon" size={20} /><div className="sidebar-title-wrap"><span className="sidebar-title"><strong>Faturamento</strong></span><span className="sidebar-subtitle">Comercial, fiscal e financeiro</span></div></div>
          <nav className="nav-menu">
            <span className="menu-group-label">Fluxo de faturamento</span>
            <button className={`nav-item ${activeTab === 'requests' ? 'active' : ''}`} onClick={() => setActiveTab('requests')}><div className="nav-item-content"><ClipboardList size={16} /><span>Solicitações de Vendas</span></div><span className="nav-badge">{requests.length}</span></button>
            <button className={`nav-item ${activeTab === 'invoices' ? 'active' : ''}`} onClick={() => setActiveTab('invoices')}><div className="nav-item-content"><ReceiptText size={16} /><span>Faturas Comerciais</span></div><span className="nav-badge">{invoices.length}</span></button>
            <button className={`nav-item ${activeTab === 'outbound-nfe' ? 'active' : ''}`} onClick={() => setActiveTab('outbound-nfe')}><div className="nav-item-content"><FileText size={16} /><span>Documentos Fiscais</span></div><span className="nav-badge">{fiscalDocs.length}</span></button>
          </nav>
        </aside>

        <main className="main-content">
          <div className="content-header">
            <div className="header-titles"><h1>{activeTab === 'requests' ? 'Solicitações de Faturamento de Vendas' : activeTab === 'invoices' ? 'Faturas Comerciais' : 'Documentos Fiscais de Saída'}</h1><p className="subtitle">Rastreabilidade do pedido à nota fiscal e ao contas a receber</p></div>
            <div className="header-actions"><button className="btn-refresh" onClick={() => void loadBillingData()} title="Atualizar dados"><RefreshCw size={15} className={loading ? 'spinning' : ''} /></button>{canManageBilling && <button className="btn-primary" onClick={() => setIsInvoiceModalOpen(true)}><Plus size={16} /><span>Emitir Nova Fatura</span></button>}</div>
          </div>
          {feedback && <div className={`billing-feedback billing-feedback--${feedback.type}`}><AlertCircle size={16} /> {feedback.text}</div>}
          <div className="kpi-grid">
            <div className="kpi-card"><div className="kpi-top"><span className="kpi-label">Faturamento ativo</span><TrendingUp size={18} /></div><div className="kpi-value">{fmtCurrency(totalInvoiced)}</div><div className="kpi-sub">{activeInvoices.length} faturas não canceladas</div></div>
            <div className="kpi-card"><div className="kpi-top"><span className="kpi-label">Impostos</span><DollarSign size={18} /></div><div className="kpi-value">{fmtCurrency(totalTax)}</div><div className="kpi-sub">Valores fiscais informados</div></div>
            <div className="kpi-card"><div className="kpi-top"><span className="kpi-label">Solicitações recebidas</span><ClipboardList size={18} /></div><div className="kpi-value">{requests.length}</div><div className="kpi-sub">{requests.filter(item => item.current_status === 'REQUESTED').length} aguardando</div></div>
            <div className="kpi-card"><div className="kpi-top"><span className="kpi-label">Documentos de saída</span><FileText size={18} /></div><div className="kpi-value">{fiscalDocs.length}</div><div className="kpi-sub">NF-e, NFC-e, NFS-e e outros</div></div>
          </div>

          {activeTab === 'requests' && <>
            <BulkActionsBar selectedCount={requestSelection.selectedCount} resourceName={{ singular: 'solicitação', plural: 'solicitações' }} onClear={requestSelection.clearSelection}>
              <button type="button" className="bulk-btn bulk-btn--danger" disabled={saving} onClick={() => void handleBulkCancelRequests()}><Ban size={14} /> Cancelar pendentes</button>
            </BulkActionsBar>
            <div className="table-card">
              <table className="data-table"><thead><tr><th className="ui-selection-cell"><input className="ui-selection-checkbox" type="checkbox" aria-label="Selecionar solicitações pendentes desta página" checked={requestSelection.isAllSelected(pendingRequests)} onChange={() => requestSelection.toggleSelectAll(pendingRequests)} /></th><th>Solicitação</th><th>Pedido</th><th>Cliente</th><th>Valor solicitado</th><th>Data</th><th>Status</th><th>Fatura</th></tr></thead><tbody>
                {requests.length === 0 ? <tr><td colSpan={8} className="empty-row">Nenhuma solicitação de faturamento recebida.</td></tr> : requestPagination.pageItems.map(request => { const invoice = requestInvoice(request); return <tr key={request.id} className={`ui-record-row ${requestSelection.isSelected(request.id) ? 'ui-record-row--selected' : ''}`} role="button" tabIndex={0} title={request.current_status === 'REQUESTED' && canManageBilling ? 'Clique para processar o faturamento' : 'Clique para visualizar o registro vinculado'} onClick={() => openRequestRecord(request)} onKeyDown={(event) => { if (['Enter', ' '].includes(event.key)) { event.preventDefault(); openRequestRecord(request); } }}><td className="ui-selection-cell"><input className="ui-selection-checkbox" type="checkbox" aria-label={`Selecionar solicitação ${request.document_number}`} disabled={!canManageBilling || request.current_status !== 'REQUESTED'} checked={requestSelection.isSelected(request.id)} onClick={event => event.stopPropagation()} onChange={() => requestSelection.toggleSelect(request.id)} /></td><td><strong>{request.document_number}</strong></td><td>{request.payload.sales_order_id ? <RecordLink type="SALES_ORDER" id={String(request.payload.sales_order_id)}>#{String(request.payload.order_number || request.payload.sales_order_id || '-').slice(0, 18)}</RecordLink> : <span>#{String(request.payload.order_number || '-').slice(0, 18)}</span>}</td><td>{request.payload.customer_id ? <RecordLink type="CUSTOMER" id={String(request.payload.customer_id)}>{String(request.payload.customer_name || '-')}</RecordLink> : <span>{String(request.payload.customer_name || '-')}</span>}</td><td className="net-val">{fmtCurrency(Number(request.payload.amount || 0))}</td><td>{fmtDate(request.issued_at || request.created_at)}</td><td><span className={`status-badge status-badge--${request.current_status.toLowerCase()}`}>{statusLabel(request.current_status)}</span></td><td>{invoice ? <RecordLink type="INVOICE" id={invoice.id}>{invoice.invoice_number}</RecordLink> : String(request.payload.invoice_number || '-')}</td></tr>; })}
              </tbody></table>
              <ListPagination {...requestPagination} onPageChange={requestPagination.setPage} onPageSizeChange={requestPagination.setPageSize} />
            </div>
          </>}

          {activeTab === 'invoices' && <>
            <BulkActionsBar selectedCount={invoiceSelection.selectedCount} resourceName={{ singular: 'fatura', plural: 'faturas' }} onClear={invoiceSelection.clearSelection}>
              <button type="button" className="bulk-btn bulk-btn--danger" disabled={saving} onClick={() => void handleBulkCancelInvoices()}><Ban size={14} /> Cancelar selecionadas</button>
            </BulkActionsBar>
            <div className="table-card"><table className="data-table"><thead><tr><th className="ui-selection-cell"><input className="ui-selection-checkbox" type="checkbox" aria-label="Selecionar faturas desta página" checked={invoiceSelection.isAllSelected(cancellableInvoices)} onChange={() => invoiceSelection.toggleSelectAll(cancellableInvoices)} /></th><th>Fatura</th><th>Cliente</th><th>Emissão</th><th>Vencimento</th><th>Total</th><th>Parcelas</th><th>Status</th><th>Ações</th></tr></thead><tbody>
              {invoices.length === 0 ? <tr><td colSpan={9} className="empty-row">Nenhuma fatura emitida.</td></tr> : invoicePagination.pageItems.map(invoice => <tr key={invoice.id} className={`ui-record-row ${invoiceSelection.isSelected(invoice.id) ? 'ui-record-row--selected' : ''}`} role="button" tabIndex={0} onClick={() => openInvoiceRecord(invoice)} onKeyDown={(event) => { if (['Enter', ' '].includes(event.key)) { event.preventDefault(); openInvoiceRecord(invoice); } }}><td className="ui-selection-cell"><input className="ui-selection-checkbox" type="checkbox" aria-label={`Selecionar fatura ${invoice.invoice_number}`} disabled={!canManageBilling || ['PAID', 'CANCELLED'].includes(invoice.status)} checked={invoiceSelection.isSelected(invoice.id)} onClick={event => event.stopPropagation()} onChange={() => invoiceSelection.toggleSelect(invoice.id)} /></td><td><strong>{invoice.invoice_number}</strong></td><td><div className="customer-cell"><Building2 size={13} /><RecordLink type="CUSTOMER" id={invoice.customer_id}><span>{invoice.customer_name}</span></RecordLink></div></td><td>{fmtDate(invoice.issue_date)}</td><td>{fmtDate(invoice.due_date)}</td><td className="net-val">{fmtCurrency(invoice.net_amount)}</td><td><span className="badge-pill"><Layers size={11} /> {invoice.installments?.length || 1}x</span></td><td><span className={`status-badge status-badge--${invoice.status.toLowerCase()}`}>{statusLabel(invoice.status)}</span></td><td><div className="table-actions"><button className="btn-icon-action" title="Detalhar" onClick={(event) => { event.stopPropagation(); setSelectedInvoice(invoice); }}><Eye size={14} /></button>{canManageBilling && <button className="btn-icon-action btn-icon-action--danger" title="Cancelar" disabled={['PAID', 'CANCELLED'].includes(invoice.status)} onClick={(event) => { event.stopPropagation(); setCancellingInvoice(invoice); setCancelReason(''); }}><Ban size={14} /></button>}</div></td></tr>)}
            </tbody></table><ListPagination {...invoicePagination} onPageChange={invoicePagination.setPage} onPageSizeChange={invoicePagination.setPageSize} /></div>
          </>}

          {activeTab === 'outbound-nfe' && <>
            <BulkActionsBar selectedCount={fiscalSelection.selectedCount} resourceName={{ singular: 'documento', plural: 'documentos' }} onClear={fiscalSelection.clearSelection}>
              <button type="button" className="bulk-btn bulk-btn--danger" disabled={saving} onClick={() => void handleBulkCancelFiscalDocs()}><Ban size={14} /> Cancelar rascunhos</button>
            </BulkActionsBar>
            <div className="table-card"><table className="data-table"><thead><tr><th className="ui-selection-cell"><input className="ui-selection-checkbox" type="checkbox" aria-label="Selecionar documentos desta página" checked={fiscalSelection.isAllSelected(cancellableFiscalDocs)} onChange={() => fiscalSelection.toggleSelectAll(cancellableFiscalDocs)} /></th><th>Tipo</th><th>Número</th><th>Emissão</th><th>Destinatário</th><th>Total</th><th>Impostos</th><th>Status</th></tr></thead><tbody>
              {fiscalDocs.length === 0 ? <tr><td colSpan={8} className="empty-row">Nenhum documento fiscal de saída registrado.</td></tr> : fiscalPagination.pageItems.map(document => <tr key={document.id} className={`${document.status.toLowerCase() !== 'cancelled' ? 'ui-record-row' : ''} ${fiscalSelection.isSelected(document.id) ? 'ui-record-row--selected' : ''}`} role={document.status.toLowerCase() !== 'cancelled' ? 'button' : undefined} tabIndex={document.status.toLowerCase() !== 'cancelled' ? 0 : undefined} onClick={() => document.status.toLowerCase() !== 'cancelled' && setEditingFinanceRecord({ kind: 'fiscal', value: document })} onKeyDown={(event) => { if (['Enter', ' '].includes(event.key) && document.status.toLowerCase() !== 'cancelled') { event.preventDefault(); setEditingFinanceRecord({ kind: 'fiscal', value: document }); } }}><td className="ui-selection-cell"><input className="ui-selection-checkbox" type="checkbox" aria-label={`Selecionar documento ${document.document_number}`} disabled={!['DRAFT', 'PENDING'].includes(document.status.toUpperCase())} checked={fiscalSelection.isSelected(document.id)} onClick={event => event.stopPropagation()} onChange={() => fiscalSelection.toggleSelect(document.id)} /></td><td><span className="doc-badge">{document.document_type}</span></td><td><strong>{document.document_number}</strong></td><td>{fmtDate(document.issue_date)}</td><td>{document.customer_id ? <RecordLink type="CUSTOMER" id={document.customer_id}>{document.recipient_name || 'Consumidor final'}</RecordLink> : (document.recipient_name || 'Consumidor final')}</td><td className="net-val">{fmtCurrency(document.total_amount)}</td><td>{fmtCurrency(document.tax_amount)}</td><td><span className={`status-badge status-badge--${document.status.toLowerCase()}`}>{statusLabel(document.status)}</span></td></tr>)}
            </tbody></table><ListPagination {...fiscalPagination} onPageChange={fiscalPagination.setPage} onPageSizeChange={fiscalPagination.setPageSize} /></div>
          </>}
        </main>
      </div>

      <Modal isOpen={!!processingRequest} onClose={() => setProcessingRequest(null)} title={processingRequest?.current_status === 'REQUESTED' ? `Processar ${processingRequest.document_number}` : `Solicitação ${processingRequest?.document_number || ''}`} subtitle="Conferência comercial, fiscal e financeira antes da emissão" size="xl">
        {processingRequest && processingRequest.current_status === 'REQUESTED' ? <form onSubmit={handleIssueRequest} className="wizard-form">
          <div className="request-summary-grid"><div><span>Pedido</span>{processingRequest.payload.sales_order_id ? <RecordLink type="SALES_ORDER" id={String(processingRequest.payload.sales_order_id)}><strong>#{String(processingRequest.payload.order_number || processingRequest.payload.sales_order_id || '-')}</strong></RecordLink> : <strong>#{String(processingRequest.payload.order_number || '-')}</strong>}</div><div><span>Cliente</span>{processingRequest.payload.customer_id ? <RecordLink type="CUSTOMER" id={String(processingRequest.payload.customer_id)}><strong>{String(processingRequest.payload.customer_name || '-')}</strong></RecordLink> : <strong>{String(processingRequest.payload.customer_name || '-')}</strong>}</div><div><span>Condição</span><strong>{String(processingRequest.payload.payment_terms || '-')}</strong></div><div><span>Saldo solicitado</span><strong>{fmtCurrency(Number(processingRequest.payload.amount || 0))}</strong></div></div>

          {requestItems(processingRequest).length > 0 ? <div className="request-items"><div className="request-items__head"><strong>Itens a faturar</strong><span>Ajuste as quantidades para faturamento parcial</span></div>{requestItems(processingRequest).map(item => { const remaining = remainingQuantity(processingRequest, item); const quantity = requestItemQuantities[item.sales_order_item_id] || '0'; return <div className="request-item-row" key={item.sales_order_item_id}><div className="request-item-product"><strong>{item.product_name}</strong><span>{item.product_sku || String(item.product_id).slice(0, 8)}</span></div><div><span>Pedido</span><strong>{Number(item.quantity).toLocaleString('pt-BR')}</strong></div><div><span>Já faturado</span><strong>{billedQuantity(processingRequest, item.sales_order_item_id).toLocaleString('pt-BR')}</strong></div><div><span>Disponível</span><strong>{remaining.toLocaleString('pt-BR')}</strong></div><label><span>Faturar agora</span><input type="number" min="0" max={remaining} step="0.0001" value={quantity} onChange={event => { const next = Math.min(remaining, Math.max(0, Number(event.target.value))); setRequestItemQuantities(current => ({ ...current, [item.sales_order_item_id]: event.target.value === '' ? '' : String(next) })); }} /></label><div className="request-item-total"><span>Valor estimado</span><strong>{fmtCurrency(estimatedLineTotal(processingRequest, item, Number(quantity || 0)))}</strong></div></div>; })}</div> : <div className="billing-feedback billing-feedback--success">Solicitação legada: o backend calculará todos os itens ainda pendentes do pedido.</div>}

          <div className="form-row"><div className="form-group flex-1"><label>Data de emissão *</label><input type="date" required value={requestIssueForm.issue_date} onChange={event => setRequestIssueForm({ ...requestIssueForm, issue_date: event.target.value })} /></div><div className="form-group flex-1"><label>Vencimento da primeira parcela *</label><input type="date" required value={requestIssueForm.due_date} onChange={event => setRequestIssueForm({ ...requestIssueForm, due_date: event.target.value })} /></div><div className="form-group flex-1"><label>Parcelas</label><select value={requestIssueForm.installments_count} onChange={event => setRequestIssueForm({ ...requestIssueForm, installments_count: event.target.value })}>{[1, 2, 3, 4, 6, 12, 18, 24].map(value => <option key={value} value={value}>{value}x</option>)}</select></div><div className="form-group flex-1"><label>Impostos</label><input type="number" min="0" step="0.01" value={requestIssueForm.tax_amount} onChange={event => setRequestIssueForm({ ...requestIssueForm, tax_amount: event.target.value })} /></div></div>
          <div className="integration-box billing-integration-box"><div className="request-totals"><span>Produtos / serviços: <strong>{fmtCurrency(requestItems(processingRequest).length ? selectedRequestSubtotal : Number(processingRequest.payload.amount || 0))}</strong></span><span>Total com impostos: <strong>{fmtCurrency((requestItems(processingRequest).length ? selectedRequestSubtotal : Number(processingRequest.payload.amount || 0)) + Number(requestIssueForm.tax_amount || 0))}</strong></span></div><label className="checkbox-label"><input type="checkbox" checked={requestIssueForm.generate_receivables_in_finance} onChange={event => setRequestIssueForm({ ...requestIssueForm, generate_receivables_in_finance: event.target.checked })} /> Gerar parcelas no Contas a Receber</label><label className="checkbox-label"><input type="checkbox" checked={requestIssueForm.generate_outbound_fiscal_document} onChange={event => setRequestIssueForm({ ...requestIssueForm, generate_outbound_fiscal_document: event.target.checked })} /> Gerar documento fiscal de saída</label>
            {requestIssueForm.generate_outbound_fiscal_document && <><div className="form-row"><div className="form-group flex-1"><label>Tipo fiscal</label><select value={requestIssueForm.fiscal_document_type} onChange={event => setRequestIssueForm({ ...requestIssueForm, fiscal_document_type: event.target.value as typeof requestIssueForm.fiscal_document_type })}>{['NFE', 'NFSE', 'NFCE', 'OUTRO'].map(value => <option key={value}>{value}</option>)}</select></div><div className="form-group flex-1"><label>Número externo</label><input placeholder="Automático se vazio" value={requestIssueForm.fiscal_document_number} onChange={event => setRequestIssueForm({ ...requestIssueForm, fiscal_document_number: event.target.value })} /></div><div className="form-group flex-1"><label>Série</label><input value={requestIssueForm.fiscal_series} onChange={event => setRequestIssueForm({ ...requestIssueForm, fiscal_series: event.target.value })} /></div></div><div className="form-group"><label>Chave de acesso</label><input maxLength={100} value={requestIssueForm.fiscal_access_key} onChange={event => setRequestIssueForm({ ...requestIssueForm, fiscal_access_key: event.target.value })} /></div></>}
          </div>
          <div className="form-group"><label>Observações da emissão</label><textarea rows={3} value={requestIssueForm.notes} onChange={event => setRequestIssueForm({ ...requestIssueForm, notes: event.target.value })} /></div>
          <div className="modal-footer modal-footer--split"><button type="button" className="btn-danger" disabled={saving} onClick={() => { setCancellingRequest(processingRequest); setRequestCancelReason(''); setProcessingRequest(null); }}>Recusar solicitação</button><div><button type="button" className="btn-secondary" onClick={() => setProcessingRequest(null)}>Voltar</button><button type="submit" className="btn-primary" disabled={saving || (requestItems(processingRequest).length > 0 && selectedRequestLines.length === 0)}>{saving ? 'Processando...' : 'Emitir e integrar'}</button></div></div>
        </form> : processingRequest && <div className="invoice-detail"><div className="detail-grid"><div><span>Pedido</span>{processingRequest.payload.sales_order_id ? <RecordLink type="SALES_ORDER" id={String(processingRequest.payload.sales_order_id)}><strong>#{String(processingRequest.payload.order_number || processingRequest.payload.sales_order_id || '-')}</strong></RecordLink> : <strong>#{String(processingRequest.payload.order_number || '-')}</strong>}</div><div><span>Cliente</span>{processingRequest.payload.customer_id ? <RecordLink type="CUSTOMER" id={String(processingRequest.payload.customer_id)}><strong>{String(processingRequest.payload.customer_name || '-')}</strong></RecordLink> : <strong>{String(processingRequest.payload.customer_name || '-')}</strong>}</div><div><span>Status</span><strong>{statusLabel(processingRequest.current_status)}</strong></div><div><span>Valor solicitado</span><strong>{fmtCurrency(Number(processingRequest.payload.amount || 0))}</strong></div><div><span>Emitida em</span><strong>{fmtDate(processingRequest.issued_at || processingRequest.created_at)}</strong></div><div><span>Motivo</span><strong>{String(processingRequest.payload.cancellation_reason || '-')}</strong></div></div></div>}
      </Modal>

      <Modal isOpen={isInvoiceModalOpen} onClose={() => setIsInvoiceModalOpen(false)} title="Emitir Fatura Comercial" subtitle="Gera a fatura, o documento fiscal e os títulos no Contas a Receber" size="lg">
        <form onSubmit={handleCreateInvoice} className="wizard-form">
          <div className="form-row"><div className="form-group flex-2"><label>Razão Social / Cliente *</label><input required value={invoiceForm.customer_name} onChange={event => setInvoiceForm({ ...invoiceForm, customer_name: event.target.value })} /></div><div className="form-group flex-1"><label>CNPJ / CPF</label><input value={invoiceForm.customer_document} onChange={event => setInvoiceForm({ ...invoiceForm, customer_document: event.target.value })} /></div></div>
          <div className="form-row"><div className="form-group flex-1"><label>Produtos / Serviços *</label><input type="number" required min="0.01" step="0.01" value={invoiceForm.total_amount} onChange={event => setInvoiceForm({ ...invoiceForm, total_amount: event.target.value })} /></div><div className="form-group flex-1"><label>Impostos</label><input type="number" min="0" step="0.01" value={invoiceForm.tax_amount} onChange={event => setInvoiceForm({ ...invoiceForm, tax_amount: event.target.value })} /></div><div className="form-group flex-1"><label>Parcelas</label><select value={invoiceForm.installments_count} onChange={event => setInvoiceForm({ ...invoiceForm, installments_count: event.target.value })}>{[1, 2, 3, 4, 6, 12].map(value => <option key={value} value={value}>{value}x</option>)}</select></div></div>
          <div className="form-row"><div className="form-group flex-1"><label>Data de emissão *</label><input type="date" required value={invoiceForm.issue_date} onChange={event => setInvoiceForm({ ...invoiceForm, issue_date: event.target.value })} /></div><div className="form-group flex-1"><label>Vencimento da primeira parcela *</label><input type="date" required value={invoiceForm.due_date} onChange={event => setInvoiceForm({ ...invoiceForm, due_date: event.target.value })} /></div></div>
          <div className="integration-box billing-integration-box"><label className="checkbox-label"><input type="checkbox" checked={invoiceForm.generate_receivables_in_finance} onChange={event => setInvoiceForm({ ...invoiceForm, generate_receivables_in_finance: event.target.checked })} /> Gerar parcelas no Contas a Receber</label><label className="checkbox-label"><input type="checkbox" checked={invoiceForm.generate_outbound_fiscal_document} onChange={event => setInvoiceForm({ ...invoiceForm, generate_outbound_fiscal_document: event.target.checked })} /> Gerar documento fiscal de saída em rascunho</label>
            {invoiceForm.generate_outbound_fiscal_document && <div className="form-row"><div className="form-group flex-1"><label>Tipo fiscal</label><select value={invoiceForm.fiscal_document_type} onChange={event => setInvoiceForm({ ...invoiceForm, fiscal_document_type: event.target.value as typeof invoiceForm.fiscal_document_type })}>{['NFE', 'NFSE', 'NFCE', 'OUTRO'].map(value => <option key={value}>{value}</option>)}</select></div><div className="form-group flex-1"><label>Número externo</label><input placeholder="Automático se vazio" value={invoiceForm.fiscal_document_number} onChange={event => setInvoiceForm({ ...invoiceForm, fiscal_document_number: event.target.value })} /></div><div className="form-group flex-1"><label>Série</label><input value={invoiceForm.fiscal_series} onChange={event => setInvoiceForm({ ...invoiceForm, fiscal_series: event.target.value })} /></div></div>}
          </div>
          <div className="form-group"><label>Observações</label><textarea rows={3} value={invoiceForm.notes} onChange={event => setInvoiceForm({ ...invoiceForm, notes: event.target.value })} /></div>
          <div className="modal-footer"><button type="button" className="btn-secondary" onClick={() => setIsInvoiceModalOpen(false)}>Cancelar</button><button type="submit" className="btn-primary" disabled={saving}>{saving ? 'Emitindo...' : 'Emitir Fatura'}</button></div>
        </form>
      </Modal>

      <Modal isOpen={!!editingInvoice} onClose={() => setEditingInvoice(null)} title="Editar Fatura Comercial" subtitle="Dados são propagados às parcelas ainda não liquidadas" size="md">
        <form onSubmit={handleUpdateInvoice} className="wizard-form">
          {editingInvoice?.status === 'PARTIALLY_RECEIVED' && <div className="billing-feedback billing-feedback--error">Após um recebimento, somente as observações podem ser alteradas.</div>}
          <div className="form-row"><div className="form-group flex-2"><label>Cliente *</label><input required disabled={editingInvoice?.status === 'PARTIALLY_RECEIVED'} value={editForm.customer_name} onChange={event => setEditForm({ ...editForm, customer_name: event.target.value })} /></div><div className="form-group flex-1"><label>CNPJ / CPF</label><input disabled={editingInvoice?.status === 'PARTIALLY_RECEIVED'} value={editForm.customer_document} onChange={event => setEditForm({ ...editForm, customer_document: event.target.value })} /></div></div>
          <div className="form-row"><div className="form-group flex-1"><label>Emissão</label><input type="date" disabled={editingInvoice?.status === 'PARTIALLY_RECEIVED'} value={editForm.issue_date} onChange={event => setEditForm({ ...editForm, issue_date: event.target.value })} /></div><div className="form-group flex-1"><label>Vencimento</label><input type="date" disabled={editingInvoice?.status === 'PARTIALLY_RECEIVED'} value={editForm.due_date} onChange={event => setEditForm({ ...editForm, due_date: event.target.value })} /></div></div>
          <div className="form-group"><label>Observações</label><textarea rows={4} value={editForm.notes} onChange={event => setEditForm({ ...editForm, notes: event.target.value })} /></div>
          <div className="modal-footer"><button type="button" className="btn-secondary" onClick={() => setEditingInvoice(null)}>Cancelar</button><button type="submit" className="btn-primary" disabled={saving}>{saving ? 'Salvando...' : 'Salvar alterações'}</button></div>
        </form>
      </Modal>

      <Modal isOpen={!!selectedInvoice} onClose={() => setSelectedInvoice(null)} title={`Fatura ${selectedInvoice?.invoice_number || ''}`} subtitle="Detalhes comerciais, fiscais e financeiros" size="lg">
        {selectedInvoice && <div className="invoice-detail"><div className="detail-grid"><div><span>Cliente</span><RecordLink type="CUSTOMER" id={selectedInvoice.customer_id}><strong>{selectedInvoice.customer_name}</strong></RecordLink></div><div><span>Documento</span><strong>{selectedInvoice.customer_document || '-'}</strong></div><div><span>Status</span><strong>{statusLabel(selectedInvoice.status)}</strong></div><div><span>Total líquido</span><strong>{fmtCurrency(selectedInvoice.net_amount)}</strong></div><div><span>Pedido de Venda</span>{selectedInvoice.sales_order_id ? <RecordLink type="SALES_ORDER" id={selectedInvoice.sales_order_id}>Abrir pedido</RecordLink> : <strong>-</strong>}</div><div><span>Documento Fiscal</span>{selectedInvoice.fiscal_document_id ? <RecordLink type="FISCAL_DOCUMENT" id={selectedInvoice.fiscal_document_id}>Abrir documento fiscal</RecordLink> : <strong>-</strong>}</div></div>{selectedInvoice.items?.length > 0 && <><h4>Itens faturados</h4><div className="invoice-item-list">{selectedInvoice.items.map(item => <div key={item.id} className="invoice-item-row"><div><RecordLink type="PRODUCT" id={item.product_id}><strong>{item.description}</strong></RecordLink><span>{item.product_sku || item.product_id.slice(0, 8)}</span></div><span>{Number(item.quantity).toLocaleString('pt-BR')} × {fmtCurrency(item.unit_price)}</span><strong>{fmtCurrency(item.total_amount)}</strong></div>)}</div></>}<h4>Parcelas e recebimentos</h4><div className="installment-list">{selectedInvoice.installments.map(item => <div key={item.id} className="installment-row"><span>{item.installment_number}/{item.total_installments}</span><strong>{fmtCurrency(item.amount)}</strong><span>{fmtDate(item.due_date)}</span><span className={`status-badge status-badge--${item.status.toLowerCase()}`}>{statusLabel(item.status)}</span></div>)}</div>{selectedInvoice.notes && <div className="detail-notes"><span>Observações</span><p>{selectedInvoice.notes}</p></div>}</div>}
      </Modal>

      <Modal isOpen={!!cancellingInvoice} onClose={() => setCancellingInvoice(null)} title="Cancelar Fatura" subtitle="Cancela também parcelas, recebíveis e documento fiscal em rascunho" size="sm">
        <form onSubmit={handleCancelInvoice} className="wizard-form"><div className="billing-feedback billing-feedback--error"><AlertCircle size={16} /> Faturas com recebimentos ou nota autorizada exigem estorno/cancelamento prévio.</div><div className="form-group"><label>Motivo do cancelamento *</label><textarea required minLength={3} rows={4} value={cancelReason} onChange={event => setCancelReason(event.target.value)} /></div><div className="modal-footer"><button type="button" className="btn-secondary" onClick={() => setCancellingInvoice(null)}>Voltar</button><button type="submit" className="btn-danger" disabled={saving}>{saving ? 'Cancelando...' : 'Confirmar cancelamento'}</button></div></form>
      </Modal>

      <Modal isOpen={!!cancellingRequest} onClose={() => setCancellingRequest(null)} title="Cancelar Solicitação" subtitle="O pedido voltará a disponibilizar o saldo para uma nova solicitação" size="sm">
        <form onSubmit={handleCancelRequest} className="wizard-form"><div className="form-group"><label>Motivo do cancelamento *</label><textarea required minLength={3} rows={4} value={requestCancelReason} onChange={event => setRequestCancelReason(event.target.value)} /></div><div className="modal-footer"><button type="button" className="btn-secondary" onClick={() => setCancellingRequest(null)}>Voltar</button><button type="submit" className="btn-danger" disabled={saving}>{saving ? 'Cancelando...' : 'Cancelar solicitação'}</button></div></form>
      </Modal>

      <FinanceRecordEditModal record={editingFinanceRecord} categories={[]} costCenters={[]} suppliers={[]} onClose={() => setEditingFinanceRecord(null)} onSaved={() => void loadBillingData()} />
    </div>
  );
};

export default Billing;
