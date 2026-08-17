/**
 * pages/Billing/Billing.tsx - Módulo de Faturamento & Documentos Fiscais de Saída (ControlB)
 */

import React, { useState, useEffect } from 'react';
import {
  ReceiptText, DollarSign, Plus, RefreshCw,
  TrendingUp, FileText, Building2, Layers
} from 'lucide-react';
import { billingService, financeService } from '@/services/api';
import { Invoice, FiscalDocument } from '@/types';
import { Modal } from '@/components/Modal/Modal';
import './Billing.scss';

export const Billing: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'invoices' | 'outbound-nfe'>('invoices');
  const [loading, setLoading] = useState<boolean>(true);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [fiscalDocs, setFiscalDocs] = useState<FiscalDocument[]>([]);

  // Modal Nova Fatura
  const [isInvoiceModalOpen, setIsInvoiceModalOpen] = useState<boolean>(false);
  const [invoiceForm, setInvoiceForm] = useState({
    customer_name: '',
    customer_document: '',
    total_amount: '',
    tax_amount: '0.00',
    issue_date: new Date().toISOString().split('T')[0],
    due_date: new Date(Date.now() + 30 * 86400000).toISOString().split('T')[0],
    installments_count: '1',
    notes: '',
    generate_receivables_in_finance: true
  });

  const loadBillingData = async () => {
    setLoading(true);
    try {
      const [invRes, docsRes] = await Promise.all([
        billingService.getInvoices().catch(() => []),
        financeService.getFiscalDocuments('OUTBOUND').catch(() => [])
      ]);
      setInvoices(invRes);
      setFiscalDocs(docsRes);
    } catch (err) {
      console.error("Erro ao carregar dados de faturamento:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadBillingData();
  }, []);

  const fmtCurrency = (val: number | undefined | null) => {
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val || 0);
  };

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

  const handleCreateInvoice = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await billingService.createInvoice({
        customer_name: invoiceForm.customer_name,
        customer_document: invoiceForm.customer_document || undefined,
        total_amount: parseFloat(invoiceForm.total_amount || '0'),
        tax_amount: parseFloat(invoiceForm.tax_amount || '0'),
        issue_date: invoiceForm.issue_date,
        due_date: invoiceForm.due_date,
        installments_count: parseInt(invoiceForm.installments_count || '1', 10),
        notes: invoiceForm.notes || undefined,
        generate_receivables_in_finance: invoiceForm.generate_receivables_in_finance
      });

      alert("✅ Fatura emitida com sucesso e obrigações a receber geradas no Financeiro!");
      setIsInvoiceModalOpen(false);
      setInvoiceForm({
        customer_name: '',
        customer_document: '',
        total_amount: '',
        tax_amount: '0.00',
        issue_date: new Date().toISOString().split('T')[0],
        due_date: new Date(Date.now() + 30 * 86400000).toISOString().split('T')[0],
        installments_count: '1',
        notes: '',
        generate_receivables_in_finance: true
      });
      loadBillingData();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Erro ao emitir fatura.");
    }
  };

  const totalInvoiced = invoices.reduce((acc, inv) => acc + (inv.net_amount || 0), 0);
  const totalTax = invoices.reduce((acc, inv) => acc + (inv.tax_amount || 0), 0);

  return (
    <div className="billing-page">
      <div className="billing-layout">
        {/* 1. SIDEBAR LATERAL ESQUERDA */}
        <aside className="sidebar-left">
          <div className="sidebar-header">
            <ReceiptText className="brand-icon" size={20} />
            <div className="sidebar-title-wrap">
              <span className="sidebar-title"><strong>Faturamento</strong></span>
              <span className="sidebar-subtitle">Documentos Fiscais</span>
            </div>
          </div>

          <nav className="nav-menu">
            <span className="menu-group-label">Documentos de Venda</span>

            <button
              className={`nav-item ${activeTab === 'invoices' ? 'active' : ''}`}
              onClick={() => setActiveTab('invoices')}
            >
              <div className="nav-item-content">
                <ReceiptText size={16} />
                <span>Faturas Comerciais</span>
              </div>
              <span className="nav-badge">{invoices.length}</span>
            </button>

            <button
              className={`nav-item ${activeTab === 'outbound-nfe' ? 'active' : ''}`}
              onClick={() => setActiveTab('outbound-nfe')}
            >
              <div className="nav-item-content">
                <FileText size={16} />
                <span>Notas Fiscais (NF-e/NFC-e)</span>
              </div>
              <span className="nav-badge">{fiscalDocs.length}</span>
            </button>
          </nav>
        </aside>

        {/* 2. CONTEÚDO PRINCIPAL */}
        <main className="main-content">
          <div className="content-header">
            <div className="header-titles">
              <h1>
                {activeTab === 'invoices' && 'Faturas Comerciais Emitidas'}
                {activeTab === 'outbound-nfe' && 'Notas Fiscais de Saída (NF-e / NFC-e)'}
              </h1>
              <p className="subtitle">Gestão fiscal e comercial de faturamento de vendas</p>
            </div>

            <div className="header-actions">
              <button className="btn-refresh" onClick={loadBillingData} title="Atualizar Dados">
                <RefreshCw size={15} className={loading ? 'spinning' : ''} />
              </button>

              <button className="btn-primary" onClick={() => setIsInvoiceModalOpen(true)}>
                <Plus size={16} />
                <span>Emitir Nova Fatura</span>
              </button>
            </div>
          </div>

          {/* Cards de Métricas Principais */}
          <div className="kpi-grid">
            <div className="kpi-card">
              <div className="kpi-top">
                <span className="kpi-label">Total Faturado Líquido</span>
                <TrendingUp size={18} />
              </div>
              <div className="kpi-value">{fmtCurrency(totalInvoiced)}</div>
              <div className="kpi-sub">{invoices.length} faturas emitidas</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-top">
                <span className="kpi-label">Impostos Incidentes</span>
                <DollarSign size={18} />
              </div>
              <div className="kpi-value">{fmtCurrency(totalTax)}</div>
              <div className="kpi-sub">ICMS, PIS, COFINS, ISS</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-top">
                <span className="kpi-label">Notas Fiscais de Saída</span>
                <ReceiptText size={18} />
              </div>
              <div className="kpi-value">{fiscalDocs.length}</div>
              <div className="kpi-sub">NF-e e NFC-e registradas</div>
            </div>
          </div>

          {/* Tabelas de Conteúdo */}
          {activeTab === 'invoices' && (
            <div className="table-card">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Número Fatura</th>
                    <th>Cliente</th>
                    <th>Emissão</th>
                    <th>Vencimento</th>
                    <th>Valor Faturado</th>
                    <th>Impostos</th>
                    <th>Total Líquido</th>
                    <th>Parcelas</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {invoices.length === 0 ? (
                    <tr>
                      <td colSpan={9} className="empty-row">
                        Nenhuma fatura emitida no período.
                      </td>
                    </tr>
                  ) : (
                    invoices.map((inv) => (
                      <tr key={inv.id}>
                        <td><strong>{inv.invoice_number}</strong></td>
                        <td>
                          <div className="customer-cell">
                            <Building2 size={13} />
                            <span>{inv.customer_name}</span>
                          </div>
                        </td>
                        <td>{fmtDate(inv.issue_date)}</td>
                        <td>{fmtDate(inv.due_date)}</td>
                        <td>{fmtCurrency(inv.total_amount)}</td>
                        <td>{fmtCurrency(inv.tax_amount)}</td>
                        <td className="net-val">{fmtCurrency(inv.net_amount)}</td>
                        <td>
                          <span className="badge-pill">
                            <Layers size={11} /> {inv.installments?.length || 1}x
                          </span>
                        </td>
                        <td><span className="badge-approved">{inv.status}</span></td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}

          {activeTab === 'outbound-nfe' && (
            <div className="table-card">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Tipo</th>
                    <th>Número</th>
                    <th>Data Emissão</th>
                    <th>Destinatário</th>
                    <th>Valor Total</th>
                    <th>Impostos</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {fiscalDocs.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="empty-row">
                        Nenhum documento fiscal de saída registrado.
                      </td>
                    </tr>
                  ) : (
                    fiscalDocs.map((doc) => (
                      <tr key={doc.id}>
                        <td><span className="doc-badge">{doc.document_type}</span></td>
                        <td><strong>{doc.document_number}</strong></td>
                        <td>{fmtDate(doc.issue_date)}</td>
                        <td>{doc.recipient_name || 'Consumidor Final'}</td>
                        <td className="net-val">{fmtCurrency(doc.total_amount)}</td>
                        <td>{fmtCurrency(doc.tax_amount)}</td>
                        <td><span className="badge-approved">{doc.status}</span></td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </main>
      </div>

      {/* Modal Emitir Fatura (com suporte a ESC) */}
      <Modal
        isOpen={isInvoiceModalOpen}
        onClose={() => setIsInvoiceModalOpen(false)}
        title="Emitir Fatura Comercial"
        subtitle="Geração de faturamento e obrigações a receber"
        size="md"
      >
        <form onSubmit={handleCreateInvoice} className="wizard-form">
          <div className="form-group">
            <label>Razão Social / Cliente *</label>
            <input
              type="text"
              required
              placeholder="Ex: Farmácia Central Ltda"
              value={invoiceForm.customer_name}
              onChange={(e) => setInvoiceForm({ ...invoiceForm, customer_name: e.target.value })}
            />
          </div>

          <div className="form-group">
            <label>CNPJ / CPF do Cliente</label>
            <input
              type="text"
              placeholder="00.000.000/0001-00"
              value={invoiceForm.customer_document}
              onChange={(e) => setInvoiceForm({ ...invoiceForm, customer_document: e.target.value })}
            />
          </div>

          <div className="form-row">
            <div className="form-group flex-1">
              <label>Valor dos Produtos (R$) *</label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                required
                placeholder="0,00"
                value={invoiceForm.total_amount}
                onChange={(e) => setInvoiceForm({ ...invoiceForm, total_amount: e.target.value })}
              />
            </div>

            <div className="form-group flex-1">
              <label>Impostos (R$)</label>
              <input
                type="number"
                step="0.01"
                value={invoiceForm.tax_amount}
                onChange={(e) => setInvoiceForm({ ...invoiceForm, tax_amount: e.target.value })}
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group flex-1">
              <label>Data de Emissão *</label>
              <input
                type="date"
                required
                value={invoiceForm.issue_date}
                onChange={(e) => setInvoiceForm({ ...invoiceForm, issue_date: e.target.value })}
              />
            </div>

            <div className="form-group flex-1">
              <label>Vencimento 1ª Parcela *</label>
              <input
                type="date"
                required
                value={invoiceForm.due_date}
                onChange={(e) => setInvoiceForm({ ...invoiceForm, due_date: e.target.value })}
              />
            </div>
          </div>

          <div className="form-group">
            <label>Condição de Parcelamento</label>
            <select
              value={invoiceForm.installments_count}
              onChange={(e) => setInvoiceForm({ ...invoiceForm, installments_count: e.target.value })}
            >
              <option value="1">1x (À Vista / 30 dias)</option>
              <option value="2">2x (30/60 dias)</option>
              <option value="3">3x (30/60/90 dias)</option>
              <option value="4">4x (30/60/90/120 dias)</option>
              <option value="6">6x (Mensal)</option>
              <option value="12">12x (Mensal)</option>
            </select>
          </div>

          <div className="checkbox-field" style={{ padding: '0.4rem 0' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8rem', color: 'var(--text-secondary)', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={invoiceForm.generate_receivables_in_finance}
                onChange={(e) => setInvoiceForm({ ...invoiceForm, generate_receivables_in_finance: e.target.checked })}
              />
              <span>Alimentar automaticamente o Contas a Receber no Financeiro</span>
            </label>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn-secondary" onClick={() => setIsInvoiceModalOpen(false)}>
              Cancelar (ESC)
            </button>
            <button type="submit" className="btn-primary">
              Emitir Fatura
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

export default Billing;
