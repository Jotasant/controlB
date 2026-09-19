import React, { FormEvent, useEffect, useState } from 'react';
import { AlertCircle, Save, Barcode, Upload, X, Download, RotateCcw } from 'lucide-react';
import { Modal } from '@/components/Modal/Modal';
import { financeService, formatApiError } from '@/services/api';
import type {
  BankAccount,
  BankTransaction,
  CostCenter,
  Customer,
  FinancialCategory,
  FiscalDocument,
  Payable,
  Receivable,
  Supplier
} from '@/types';

export type EditableFinanceRecord =
  | { kind: 'payable'; value: Payable }
  | { kind: 'receivable'; value: Receivable }
  | { kind: 'fiscal'; value: FiscalDocument }
  | { kind: 'bank'; value: BankAccount }
  | { kind: 'transaction'; value: BankTransaction }
  | { kind: 'category'; value: FinancialCategory };

interface Props {
  record: EditableFinanceRecord | null;
  categories: FinancialCategory[];
  costCenters: CostCenter[];
  suppliers: Supplier[];
  customers?: Customer[];
  bankAccounts?: BankAccount[];
  onClose: () => void;
  onSaved: () => void;
}

const titles: Record<EditableFinanceRecord['kind'], string> = {
  payable: 'Editar Conta a Pagar',
  receivable: 'Editar Conta a Receber',
  fiscal: 'Editar Documento Fiscal',
  bank: 'Editar Conta Bancária',
  transaction: 'Editar Movimentação Bancária',
  category: 'Editar Categoria Financeira'
};

export const FinanceRecordEditModal: React.FC<Props> = ({
  record,
  categories,
  costCenters,
  suppliers,
  customers = [],
  bankAccounts = [],
  onClose,
  onSaved
}) => {
  const [form, setForm] = useState<Record<string, string | boolean>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!record) return;
    const value = record.value as unknown as Record<string, unknown>;
    const next: Record<string, string | boolean> = {};
    Object.entries(value).forEach(([key, item]) => {
      if (typeof item === 'boolean') next[key] = item;
      else if (item !== null && item !== undefined && typeof item !== 'object') next[key] = String(item);
      else next[key] = '';
    });
    if (record.kind === 'payable') {
      const inst = record.value.instruments?.find(i => i.instrument_type === 'BOLETO') || record.value.instruments?.[0];
      if (inst) {
        next['digitable_line'] = inst.digitable_line || '';
        next['barcode'] = inst.barcode || '';
        next['pix_code'] = inst.pix_code || '';
        next['file_attachment'] = inst.file_attachment || '';
      }
    }
    setForm(next);
    setError(null);
  }, [record]);

  if (!record) return null;

  const field = (name: string) => String(form[name] ?? '');
  const set = (name: string, value: string | boolean) => setForm(current => ({ ...current, [name]: value }));
  const isFiscalLocked = record.kind === 'fiscal' && record.value.status.toUpperCase() === 'AUTHORIZED';

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      if (record.kind === 'payable') {
        await financeService.updatePayable(record.value.id, {
          supplier_id: field('supplier_id') || null,
          favored_name: field('favored_name'),
          description: field('description'),
          original_amount: Number(field('original_amount')),
          issue_date: field('issue_date'),
          due_date: field('due_date'),
          expense_nature: field('expense_nature') as Payable['expense_nature'],
          obligation_type: field('obligation_type') as Payable['obligation_type'],
          business_origin: field('business_origin') as Payable['business_origin'],
          payment_method_expected: field('payment_method_expected'),
          financial_category_id: field('financial_category_id') || null,
          cost_center_id: field('cost_center_id') || null,
          status: field('status') as Payable['status'],
          notes: field('notes') || null
        });

        if (field('digitable_line') || field('barcode') || field('file_attachment')) {
          await financeService.createOrUpdatePayableInstrument(record.value.id, {
            instrument_type: 'BOLETO',
            digitable_line: field('digitable_line') || undefined,
            barcode: field('barcode') || undefined,
            pix_code: field('pix_code') || undefined,
            due_date: field('due_date') || undefined,
            amount: Number(field('original_amount')) || undefined,
            file_attachment: field('file_attachment') || undefined
          });
        }
      } else if (record.kind === 'receivable') {
        await financeService.updateReceivable(record.value.id, {
          customer_id: field('customer_id') || null,
          customer_name: field('customer_name'),
          customer_document: field('customer_document') || null,
          description: field('description'),
          original_amount: Number(field('original_amount')),
          issue_date: field('issue_date'),
          due_date: field('due_date'),
          payment_method_expected: field('payment_method_expected'),
          financial_category_id: field('financial_category_id') || null,
          cost_center_id: field('cost_center_id') || null,
          status: field('status') as Receivable['status'],
          notes: field('notes') || null
        });
      } else if (record.kind === 'fiscal') {
        const common = {
          notes: field('notes') || null,
          file_attachment: field('file_attachment') || null,
          status: field('status')
        };
        await financeService.updateFiscalDocument(record.value.id, isFiscalLocked ? common : {
          ...common,
          direction: field('direction') as FiscalDocument['direction'],
          document_type: field('document_type') as FiscalDocument['document_type'],
          document_number: field('document_number'),
          series: field('series') || null,
          access_key: field('access_key') || null,
          issuer_name: field('issuer_name'),
          issuer_cnpj_cpf: field('issuer_cnpj_cpf') || null,
          recipient_name: field('recipient_name') || null,
          recipient_cnpj_cpf: field('recipient_cnpj_cpf') || null,
          issue_date: field('issue_date'),
          total_amount: Number(field('total_amount')),
          tax_amount: Number(field('tax_amount') || 0)
        });
      } else if (record.kind === 'bank') {
        await financeService.updateBankAccount(record.value.id, {
          bank_name: field('bank_name'),
          bank_code: field('bank_code') || null,
          agency: field('agency') || null,
          account_number: field('account_number') || null,
          account_type: field('account_type') as BankAccount['account_type'],
          is_active: Boolean(form.is_active)
        });
      } else if (record.kind === 'transaction') {
        await financeService.updateBankTransaction(record.value.id, {
          bank_account_id: field('bank_account_id'),
          transaction_date: field('transaction_date'),
          description: field('description'),
          amount: Number(field('amount')),
          transaction_type: field('transaction_type') as BankTransaction['transaction_type'],
          external_id: field('external_id') || null,
          document_number: field('document_number') || null
        });
      } else {
        await financeService.updateCategory(record.value.id, {
          name: field('name'),
          code: field('code') || null,
          category_type: field('category_type') as FinancialCategory['category_type'],
          description: field('description') || null,
          is_active: Boolean(form.is_active)
        });
      }
      onSaved();
      onClose();
    } catch (err) {
      setError(formatApiError(err, 'Não foi possível editar o registro.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      isOpen={!!record}
      onClose={onClose}
      title={titles[record.kind]}
      subtitle="Alterações ficam registradas no histórico operacional"
      size="lg"
    >
      <form onSubmit={submit} className="wizard-form">
        {error && <div className="ui-inline-feedback ui-inline-feedback--error"><AlertCircle size={15} /> {error}</div>}

        {record.kind === 'payable' && <>
          {record.value.status === 'CANCELLED' && (
            <div className="ui-inline-feedback ui-inline-feedback--warning" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <span>Conta atualmente <strong>CANCELADA</strong>. Clique para reabrir para tramitação e pagamento.</span>
              <button
                type="button"
                className="btn-secondary"
                style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}
                onClick={() => set('status', 'PENDING_APPROVAL')}
              >
                <RotateCcw size={13} /> Reabrir Conta
              </button>
            </div>
          )}
          {(record.value.purchase_order_id || record.value.fiscal_document_id) && (
            <div className="ui-inline-feedback">
              Origem documental preservada: {record.value.purchase_order_id ? 'pedido de compra' : 'documento fiscal'}.
            </div>
          )}
          <div className="form-row">
            <div className="form-group flex-1"><label>Fornecedor cadastrado</label><select value={field('supplier_id')} onChange={e => set('supplier_id', e.target.value)}><option value="">Sem fornecedor vinculado</option>{suppliers.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div>
            <div className="form-group flex-1"><label>Favorecido *</label><input required value={field('favored_name')} onChange={e => set('favored_name', e.target.value)} /></div>
          </div>
          <div className="form-group"><label>Descrição *</label><input required value={field('description')} onChange={e => set('description', e.target.value)} /></div>
          <div className="form-row">
            <div className="form-group flex-1"><label>Valor original *</label><input required type="number" min="0.01" step="0.01" value={field('original_amount')} onChange={e => set('original_amount', e.target.value)} /></div>
            <div className="form-group flex-1"><label>Emissão</label><input type="date" value={field('issue_date')} onChange={e => set('issue_date', e.target.value)} /></div>
            <div className="form-group flex-1"><label>Vencimento</label><input type="date" value={field('due_date')} onChange={e => set('due_date', e.target.value)} /></div>
          </div>
          <div className="form-row">
            <div className="form-group flex-1"><label>Natureza contábil</label><select value={field('expense_nature') || 'NOT_APPLICABLE'} onChange={e => set('expense_nature', e.target.value)}>{[['NOT_APPLICABLE', 'Não Aplicável'], ['FINANCIAL', 'Financeira'], ['TAX', 'Tributária'], ['PAYROLL', 'Folha'], ['TRANSFER', 'Transferência'], ['OPEX', 'OPEX (Despesa Operacional)'], ['CAPEX', 'CAPEX (Investimento em Ativos)']].map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
            <div className="form-group flex-1"><label>Tipo da obrigação</label><select value={field('obligation_type')} onChange={e => set('obligation_type', e.target.value)}>{[['GOODS_SUPPLIER', 'Fornecedor de mercadoria'], ['SERVICE_PROVIDER', 'Prestador de serviço'], ['TAX', 'Tributo'], ['PAYROLL', 'Folha'], ['RENT_LEASE', 'Aluguel/arrendamento'], ['FINANCING', 'Financiamento'], ['REIMBURSEMENT', 'Reembolso'], ['INVESTMENT', 'Investimento'], ['OTHER', 'Outro']].map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
            <div className="form-group flex-1"><label>Origem</label><select disabled={!!(record.value.purchase_order_id || record.value.fiscal_document_id)} value={field('business_origin')} onChange={e => set('business_origin', e.target.value)}>{[['PURCHASE', 'Compra'], ['REPLENISHMENT', 'Reposição'], ['INVESTMENT', 'Investimento'], ['CONTRACT', 'Contrato'], ['FISCAL_DOCUMENT', 'Documento fiscal'], ['MANUAL', 'Manual'], ['OTHER', 'Outra']].map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
          </div>
          <div className="form-row">
            <div className="form-group flex-1"><label>Categoria</label><select value={field('financial_category_id')} onChange={e => set('financial_category_id', e.target.value)}><option value="">Sem categoria</option>{categories.filter(item => item.category_type === 'EXPENSE').map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div>
            <div className="form-group flex-1"><label>Centro de custo</label><select value={field('cost_center_id')} onChange={e => set('cost_center_id', e.target.value)}><option value="">Sem centro</option>{costCenters.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div>
            <div className="form-group flex-1"><label>Status</label><select value={field('status')} onChange={e => set('status', e.target.value)}><option value="PENDING_APPROVAL">Pendente aprovação</option><option value="APPROVED">Aprovada</option><option value="SCHEDULED">Agendada</option><option value="OVERDUE">Vencida</option><option value="CANCELLED">Cancelada</option></select></div>
          </div>

          <div style={{ background: 'rgba(139, 92, 246, 0.05)', padding: '0.75rem', borderRadius: 6, margin: '0.75rem 0', border: '1px solid rgba(139, 92, 246, 0.2)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#a78bfa', fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.5rem' }}>
              <Barcode size={15} />
              <span>Boleto Bancário / Instrumento de Cobrança</span>
            </div>
            <div className="form-row">
              <div className="form-group flex-2">
                <label>Linha Digitável</label>
                <input
                  placeholder="34191.79001 01043.510047..."
                  value={field('digitable_line')}
                  onChange={e => set('digitable_line', e.target.value)}
                />
              </div>
              <div className="form-group flex-1">
                <label>Código de Barras</label>
                <input
                  placeholder="44 dígitos numéricos"
                  value={field('barcode')}
                  onChange={e => set('barcode', e.target.value)}
                />
              </div>
            </div>
            <div className="form-group">
              <label>Anexo do Boleto (PDF)</label>
              {field('file_attachment') ? (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.4rem 0.6rem', background: 'rgba(139, 92, 246, 0.1)', border: '1px solid rgba(139, 92, 246, 0.3)', borderRadius: 6 }}>
                  <span style={{ color: '#c4b5fd', fontSize: '0.8rem' }}>📄 Boleto PDF Anexado</span>
                  <div style={{ display: 'flex', gap: '0.3rem' }}>
                    <a
                      href={field('file_attachment')}
                      download={`boleto_${record.value.payable_number}.pdf`}
                      target="_blank"
                      rel="noreferrer"
                      className="btn-secondary"
                      style={{ padding: '0.2rem 0.4rem', fontSize: '0.75rem' }}
                    >
                      <Download size={12} /> Baixar
                    </a>
                    <button
                      type="button"
                      className="btn-danger"
                      style={{ padding: '0.2rem 0.4rem', fontSize: '0.75rem' }}
                      onClick={() => set('file_attachment', '')}
                    >
                      <X size={12} /> Remover
                    </button>
                  </div>
                </div>
              ) : (
                <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem', padding: '0.5rem', border: '1px dashed rgba(255,255,255,0.2)', borderRadius: 6, cursor: 'pointer', background: 'rgba(255,255,255,0.02)', fontSize: '0.8rem' }}>
                  <Upload size={14} />
                  <span>Selecionar ou Substituir Boleto PDF</span>
                  <input
                    type="file"
                    accept=".pdf,application/pdf"
                    style={{ display: 'none' }}
                    onChange={e => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      const reader = new FileReader();
                      reader.onload = ev => {
                        const dataUrl = ev.target?.result as string;
                        set('file_attachment', dataUrl);
                      };
                      reader.readAsDataURL(file);
                    }}
                  />
                </label>
              )}
            </div>
          </div>
        </>}

        {record.kind === 'receivable' && <>
          {record.value.status === 'CANCELLED' && (
            <div className="ui-inline-feedback ui-inline-feedback--warning" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <span>Título atualmente <strong>CANCELADO</strong>. Clique para reabrir para cobrança/recebimento.</span>
              <button
                type="button"
                className="btn-secondary"
                style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}
                onClick={() => set('status', 'PENDING')}
              >
                <RotateCcw size={13} /> Reabrir Título
              </button>
            </div>
          )}
          <div className="form-row">
            <div className="form-group flex-1">
              <label>Cliente cadastrado</label>
              <select
                value={field('customer_id')}
                onChange={e => {
                  const selectedId = e.target.value;
                  const selectedCustomer = customers.find(c => c.id === selectedId);
                  if (selectedCustomer) {
                    setForm(prev => ({
                      ...prev,
                      customer_id: selectedId,
                      customer_name: selectedCustomer.name,
                      customer_document: selectedCustomer.document || ''
                    }));
                  } else {
                    set('customer_id', '');
                  }
                }}
              >
                <option value="">Sem cliente vinculado (Avulso)</option>
                {customers.map(item => (
                  <option key={item.id} value={item.id}>
                    {item.name} {item.document ? `(${item.document})` : ''}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group flex-1">
              <label>Cliente / Sacado *</label>
              <input required value={field('customer_name')} onChange={e => set('customer_name', e.target.value)} />
            </div>
            <div className="form-group flex-1">
              <label>CNPJ/CPF</label>
              <input value={field('customer_document')} onChange={e => set('customer_document', e.target.value)} />
            </div>
          </div>
          <div className="form-group"><label>Descrição *</label><input required value={field('description')} onChange={e => set('description', e.target.value)} /></div>
          <div className="form-row"><div className="form-group flex-1"><label>Valor original *</label><input required type="number" min="0.01" step="0.01" value={field('original_amount')} onChange={e => set('original_amount', e.target.value)} /></div><div className="form-group flex-1"><label>Emissão</label><input type="date" value={field('issue_date')} onChange={e => set('issue_date', e.target.value)} /></div><div className="form-group flex-1"><label>Vencimento</label><input type="date" value={field('due_date')} onChange={e => set('due_date', e.target.value)} /></div></div>
          <div className="form-row"><div className="form-group flex-1"><label>Categoria</label><select value={field('financial_category_id')} onChange={e => set('financial_category_id', e.target.value)}><option value="">Sem categoria</option>{categories.filter(item => item.category_type === 'REVENUE').map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div><div className="form-group flex-1"><label>Centro de custo</label><select value={field('cost_center_id')} onChange={e => set('cost_center_id', e.target.value)}><option value="">Sem centro</option>{costCenters.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div><div className="form-group flex-1"><label>Status</label><select value={field('status')} onChange={e => set('status', e.target.value)}><option value="PENDING">Pendente</option><option value="OVERDUE">Vencida</option><option value="CANCELLED">Cancelada</option></select></div></div>
        </>}

        {record.kind === 'fiscal' && <>
          {isFiscalLocked && <div className="ui-inline-feedback">Documento autorizado: somente observações, anexo e cancelamento podem ser alterados.</div>}
          <div className="form-row"><div className="form-group flex-1"><label>Direção</label><select disabled={isFiscalLocked} value={field('direction')} onChange={e => set('direction', e.target.value)}><option value="INBOUND">Entrada</option><option value="OUTBOUND">Saída</option></select></div><div className="form-group flex-1"><label>Tipo</label><select disabled={isFiscalLocked} value={field('document_type')} onChange={e => set('document_type', e.target.value)}>{['NFE', 'NFSE', 'NFCE', 'CTE', 'OUTRO'].map(item => <option key={item}>{item}</option>)}</select></div><div className="form-group flex-1"><label>Status</label><select value={field('status').toLowerCase()} onChange={e => set('status', e.target.value)}>{!isFiscalLocked && <option value="draft">Rascunho</option>}<option value="authorized">Autorizado</option><option value="cancelled">Cancelado</option></select></div></div>
          <div className="form-row"><div className="form-group flex-1"><label>Número *</label><input disabled={isFiscalLocked} required value={field('document_number')} onChange={e => set('document_number', e.target.value)} /></div><div className="form-group flex-1"><label>Série</label><input disabled={isFiscalLocked} value={field('series')} onChange={e => set('series', e.target.value)} /></div><div className="form-group flex-1"><label>Emissão</label><input disabled={isFiscalLocked} type="date" value={field('issue_date')} onChange={e => set('issue_date', e.target.value)} /></div></div>
          <div className="form-row"><div className="form-group flex-2"><label>Emissor *</label><input disabled={isFiscalLocked} required value={field('issuer_name')} onChange={e => set('issuer_name', e.target.value)} /></div><div className="form-group flex-1"><label>Valor total</label><input disabled={isFiscalLocked} type="number" step="0.01" value={field('total_amount')} onChange={e => set('total_amount', e.target.value)} /></div><div className="form-group flex-1"><label>Impostos</label><input disabled={isFiscalLocked} type="number" step="0.01" value={field('tax_amount')} onChange={e => set('tax_amount', e.target.value)} /></div></div>
        </>}

        {record.kind === 'bank' && <>
          <div className="form-group"><label>Instituição/descrição *</label><input required value={field('bank_name')} onChange={e => set('bank_name', e.target.value)} /></div>
          <div className="form-row"><div className="form-group flex-1"><label>Tipo</label><select value={field('account_type')} onChange={e => set('account_type', e.target.value)}><option value="CHECKING">Conta corrente</option><option value="SAVINGS">Poupança</option><option value="CASH">Caixa</option><option value="DIGITAL_WALLET">Carteira digital</option></select></div><div className="form-group flex-1"><label>Agência</label><input value={field('agency')} onChange={e => set('agency', e.target.value)} /></div><div className="form-group flex-1"><label>Conta</label><input value={field('account_number')} onChange={e => set('account_number', e.target.value)} /></div></div>
          <label className="checkbox-label"><input type="checkbox" checked={Boolean(form.is_active)} onChange={e => set('is_active', e.target.checked)} /> Conta ativa</label>
        </>}

        {record.kind === 'transaction' && <>
          <div className="ui-inline-feedback">Somente lançamentos manuais pendentes podem ser corrigidos. Movimentações conciliadas exigem estorno.</div>
          <div className="form-row"><div className="form-group flex-2"><label>Conta *</label><select required value={field('bank_account_id')} onChange={e => set('bank_account_id', e.target.value)}>{bankAccounts.map(item => <option key={item.id} value={item.id}>{item.bank_name}</option>)}</select></div><div className="form-group flex-1"><label>Data *</label><input required type="date" value={field('transaction_date')} onChange={e => set('transaction_date', e.target.value)} /></div></div>
          <div className="form-group"><label>Descrição *</label><input required value={field('description')} onChange={e => set('description', e.target.value)} /></div>
          <div className="form-row"><div className="form-group flex-1"><label>Tipo</label><select value={field('transaction_type')} onChange={e => set('transaction_type', e.target.value)}><option value="CREDIT">Crédito / entrada</option><option value="DEBIT">Débito / saída</option></select></div><div className="form-group flex-1"><label>Valor *</label><input required type="number" min="0.01" step="0.01" value={field('amount')} onChange={e => set('amount', e.target.value)} /></div><div className="form-group flex-1"><label>Documento</label><input value={field('document_number')} onChange={e => set('document_number', e.target.value)} /></div></div>
        </>}

        {record.kind === 'category' && <>
          <div className="form-row"><div className="form-group flex-1"><label>Código</label><input value={field('code')} onChange={e => set('code', e.target.value)} /></div><div className="form-group flex-2"><label>Nome *</label><input required value={field('name')} onChange={e => set('name', e.target.value)} /></div><div className="form-group flex-1"><label>Tipo</label><select value={field('category_type')} onChange={e => set('category_type', e.target.value)}><option value="EXPENSE">Despesa</option><option value="REVENUE">Receita</option></select></div></div>
          <div className="form-group"><label>Descrição</label><input value={field('description')} onChange={e => set('description', e.target.value)} /></div>
          <label className="checkbox-label"><input type="checkbox" checked={Boolean(form.is_active)} onChange={e => set('is_active', e.target.checked)} /> Categoria ativa</label>
        </>}

        {(record.kind === 'payable' || record.kind === 'receivable' || record.kind === 'fiscal') && (
          <div className="form-group"><label>Observações</label><textarea rows={3} value={field('notes')} onChange={e => set('notes', e.target.value)} /></div>
        )}

        <div className="modal-footer"><button type="button" className="btn-secondary" onClick={onClose}>Cancelar</button><button type="submit" className="btn-primary" disabled={saving}><Save size={14} /> {saving ? 'Salvando...' : 'Salvar alterações'}</button></div>
      </form>
    </Modal>
  );
};
