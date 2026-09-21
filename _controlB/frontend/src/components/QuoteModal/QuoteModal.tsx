import { useNavigate } from 'react-router-dom';
import React, { useState, useEffect } from 'react';
import {
  Plus, Trash2, DollarSign,
  AlertTriangle, Check, Package, Tag, Sparkles
} from 'lucide-react';
import { Modal } from '@/components/Modal/Modal';
import { RecordEditorSurface } from '@/components/RecordForm/RecordEditorSurface';
import { CustomerPicker } from '@/components/CustomerPicker/CustomerPicker';
import { useToast } from '@/components/Toast/ToastContext';
import { salesService, inventoryService, formatApiError } from '@/services/api';
import type { SalesQuote, Product, Customer } from '@/types';
import { formatCurrency } from '@/utils/formatters';
import './QuoteModal.scss';

export interface QuoteModalProps {
  page?: boolean;
  isOpen: boolean;
  onClose: () => void;
  quote?: SalesQuote | null;
  fixedCustomerId?: string | null;
  fixedOpportunityId?: string | null;
  fixedCustomerName?: string | null;
  onSuccess?: (quote: SalesQuote) => void | Promise<void>;
}

interface FormQuoteItem {
  id?: string;
  product_id: string;
  quantity: number;
  unit_price: number;
  discount_amount: number;
  notes?: string;
}

export const QuoteModal: React.FC<QuoteModalProps> = ({
  page = false,
  isOpen,
  onClose,
  quote,
  fixedCustomerId,
  fixedOpportunityId,
  fixedCustomerName,
  onSuccess
}) => {
  const toast = useToast();
  const navigate = useNavigate();
  const [formTab, setFormTab] = useState('customer');
  const isEditing = Boolean(quote?.id);

  // Estados de Cabeçalho e Cliente
  const [selectedCustomerId, setSelectedCustomerId] = useState<string | null>(fixedCustomerId || null);
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [customerName, setCustomerName] = useState<string>(fixedCustomerName || '');
  const [customerDocument, setCustomerDocument] = useState<string>('');
  const [customerEmail, setCustomerEmail] = useState<string>('');
  const [customerPhone, setCustomerPhone] = useState<string>('');
  const [opportunityId, setOpportunityId] = useState<string | null>(fixedOpportunityId || null);

  // Condições Comerciais
  const [validUntil, setValidUntil] = useState<string>('');
  const [paymentTerms, setPaymentTerms] = useState<string>('30 DDL');
  const [notes, setNotes] = useState<string>('');

  // Itens da Cotação
  const [items, setItems] = useState<FormQuoteItem[]>([]);
  const [products, setProducts] = useState<Product[]>([]);

  // Estados de Controle
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // Carregar produtos do inventário
  useEffect(() => {
    if (isOpen) {
      inventoryService.getProducts().then((loaded) => {
        const active = Array.isArray(loaded) ? loaded.filter(p => p.is_active !== false) : [];
        setProducts(active);
      }).catch(() => {});
    }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen || quote) return;
    salesService.getCommercialSettings().then((settings) => {
      setPaymentTerms(settings.default_payment_terms);
      const configuredDate = new Date();
      configuredDate.setDate(configuredDate.getDate() + settings.quote_validity_days);
      setValidUntil(configuredDate.toISOString().split('T')[0]);
    }).catch(() => {
      // O backend ainda aplica os mesmos defaults se a leitura antecipada falhar.
    });
  }, [isOpen, quote]);

  // Inicializar formulário ao abrir
  useEffect(() => {
    if (!isOpen) return;

    setModalError(null);
    if (quote) {
      setSelectedCustomerId(quote.customer_id || null);
      setCustomerName(quote.customer_name || '');
      setCustomerDocument(quote.customer_document || '');
      setCustomerEmail(quote.customer_email || '');
      setCustomerPhone(quote.customer_phone || '');
      setOpportunityId(quote.opportunity_id || null);
      setValidUntil(quote.valid_until ? quote.valid_until.split('T')[0] : '');
      setPaymentTerms(quote.payment_terms || '30 DDL');
      setNotes(quote.notes || '');

      if (quote.items && quote.items.length > 0) {
        setItems(quote.items.map(it => ({
          id: it.id,
          product_id: it.product_id,
          quantity: Number(it.quantity) || 1,
          unit_price: Number(it.unit_price) || 0,
          discount_amount: Number(it.discount_amount) || 0,
          notes: it.notes || ''
        })));
      } else {
        setItems([]);
      }
    } else {
      setSelectedCustomerId(fixedCustomerId || null);
      setCustomerName(fixedCustomerName || '');
      setCustomerDocument('');
      setCustomerEmail('');
      setCustomerPhone('');
      setOpportunityId(fixedOpportunityId || null);

      // Validade padrão: 15 dias a partir de hoje
      const defaultDate = new Date();
      defaultDate.setDate(defaultDate.getDate() + 15);
      setValidUntil(defaultDate.toISOString().split('T')[0]);

      setPaymentTerms('30 DDL');
      setNotes('');
      setItems([]);
    }
  }, [isOpen, quote, fixedCustomerId, fixedOpportunityId, fixedCustomerName]);

  // Ao selecionar cliente via CustomerPicker
  const handleCustomerChange = (cust: Customer | null) => {
    setSelectedCustomer(cust);
    if (cust) {
      setSelectedCustomerId(cust.id);
      setCustomerName(cust.trade_name || cust.name);
      setCustomerDocument(cust.document || '');
      setCustomerEmail(cust.email || '');
      setCustomerPhone(cust.phone || '');
    } else {
      setSelectedCustomerId(null);
      if (!fixedCustomerName) setCustomerName('');
      setCustomerDocument('');
      setCustomerEmail('');
      setCustomerPhone('');
    }
  };

  useEffect(() => {
    const id = quote?.customer_id || fixedCustomerId;
    if (!isOpen || !id) return;
    let cancelled = false;
    void salesService.getCustomer(id).then(customer => {
      if (cancelled) return;
      setSelectedCustomer(customer);
      if (!quote) { setCustomerName(customer.trade_name || customer.name); setCustomerDocument(customer.document || ''); setCustomerEmail(customer.email || ''); setCustomerPhone(customer.phone || ''); }
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [isOpen, quote, fixedCustomerId]);

  // Gerenciamento de Itens
  const handleAddItem = () => {
    if (products.length === 0) {
      setItems(prev => [...prev, {
        product_id: '',
        quantity: 1,
        unit_price: 10.00,
        discount_amount: 0
      }]);
      return;
    }

    const firstProduct = products[0];
    setItems(prev => [
      ...prev,
      {
        product_id: firstProduct.id,
        quantity: 1,
        unit_price: Number(firstProduct.reference_price) || 10.00,
        discount_amount: 0
      }
    ]);
  };

  const handleRemoveItem = (index: number) => {
    setItems(prev => prev.filter((_, idx) => idx !== index));
  };

  const handleItemProductChange = (index: number, productId: string) => {
    const prod = products.find(p => p.id === productId);
    setItems(prev => {
      const copy = [...prev];
      copy[index] = {
        ...copy[index],
        product_id: productId,
        unit_price: prod ? (Number(prod.reference_price) || 0) : copy[index].unit_price
      };
      return copy;
    });
  };

  const handleItemFieldChange = (index: number, field: keyof FormQuoteItem, value: any) => {
    setItems(prev => {
      const copy = [...prev];
      copy[index] = {
        ...copy[index],
        [field]: value
      };
      return copy;
    });
  };

  // Cálculos Financeiros em Tempo Real
  const totalGross = items.reduce((acc, it) => acc + (it.quantity * it.unit_price), 0);
  const totalDiscount = items.reduce((acc, it) => acc + Number(it.discount_amount || 0), 0);
  const totalNet = Math.max(0, totalGross - totalDiscount);

  // Submissão do Formulário
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!customerName.trim()) {
      setFormTab('customer');
      setModalError('Informe ou selecione o cliente para a cotação.');
      return;
    }
    if (items.length === 0) {
      setFormTab('items');
      setModalError('Adicione pelo menos um produto ou serviço à cotação.');
      return;
    }

    // Validar se todos os itens têm produto selecionado
    for (let i = 0; i < items.length; i++) {
      if (!items[i].product_id) {
      setFormTab('items');
        setModalError(`Selecione o produto no item #${i + 1}.`);
        return;
      }
      if (items[i].quantity <= 0) {
      setFormTab('items');
        setModalError(`A quantidade no item #${i + 1} deve ser maior que zero.`);
        return;
      }
    }

    setIsSaving(true);
    setModalError(null);

    const payload = {
      customer_id: selectedCustomerId || undefined,
      opportunity_id: opportunityId || undefined,
      customer_name: customerName.trim(),
      customer_document: customerDocument.trim() || undefined,
      customer_email: customerEmail.trim() || undefined,
      customer_phone: customerPhone.trim() || undefined,
      payment_terms: paymentTerms || '30 DDL',
      valid_until: validUntil || undefined,
      notes: notes.trim() || undefined,
      items: items.map(it => ({
        product_id: it.product_id,
        quantity: it.quantity,
        unit_price: it.unit_price,
        discount_amount: it.discount_amount || 0,
        notes: it.notes || undefined
      }))
    };

    try {
      let savedQuote: SalesQuote;
      if (isEditing && quote?.id) {
        savedQuote = await salesService.updateQuote(quote.id, payload as any);
        toast.success(`Cotação #${savedQuote.quote_number} atualizada com sucesso!`);
      } else {
        savedQuote = await salesService.createQuote(payload);
        toast.success(`Cotação #${savedQuote.quote_number} emitida com sucesso!`);
      }

      if (onSuccess) {
        await onSuccess(savedQuote);
      }
      if (!page) onClose();
    } catch (err: unknown) {
      const msg = formatApiError(err, 'Erro ao salvar cotação comercial.');
      setModalError(msg);
      toast.error(msg);
    } finally {
      setIsSaving(false);
    }
  };

  // Estados de Cancelamento
  const [isCancelModalOpen, setIsCancelModalOpen] = useState<boolean>(false);
  const [cancelReason, setCancelReason] = useState<string>('');

  // Ações de Evolução de Cotação
  const handleUpdateStatus = async (newStatus: string) => {
    if (!quote?.id) return;
    setIsSaving(true);
    try {
      const updated = await salesService.updateQuoteStatus(quote.id, newStatus);
      toast.success(`Cotação atualizada para status: ${newStatus}`);
      if (onSuccess) await onSuccess(updated);
      if (!page) onClose();
    } catch (err) {
      const msg = formatApiError(err, 'Erro ao atualizar status da cotação');
      toast.error(msg);
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancelQuote = async () => {
    if (!quote?.id) return;
    if (!cancelReason.trim()) {
      toast.error('Informe o motivo do cancelamento / desistência.');
      return;
    }
    setIsSaving(true);
    try {
      const updated = await salesService.cancelQuote(quote.id, cancelReason.trim());
      toast.success(`Cotação #${updated.quote_number} cancelada com sucesso.`);
      setIsCancelModalOpen(false);
      if (onSuccess) await onSuccess(updated);
      if (!page) onClose();
    } catch (err) {
      const msg = formatApiError(err, 'Erro ao cancelar cotação');
      toast.error(msg);
    } finally {
      setIsSaving(false);
    }
  };

  const handleConvertToOrder = async () => {
    if (!quote?.id) return;
    setIsSaving(true);
    try {
      const createdOrder = await salesService.convertQuoteToOrder(quote.id);
      toast.success(`Cotação convertida com sucesso no Pedido de Venda #${createdOrder.order_number}!`);
      if (page) navigate('/vendas/pedidos/' + createdOrder.id); else onClose();
    } catch (err) {
      const msg = formatApiError(err, 'Erro ao converter cotação em pedido');
      toast.error(msg);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <>
      <RecordEditorSurface
        page={page} saving={isSaving} resetKey={quote} activeTab={formTab} onTabChange={setFormTab}
        tabs={[{"id":"customer","label":"Cliente"},{"id":"items","label":"Itens e valores"},{"id":"terms","label":"Condições comerciais"}]}
        isOpen={isOpen}
        onClose={onClose}
        title={isEditing ? `Cotação #${quote?.quote_number || ''}` : 'Nova Cotação Comercial'}
        subtitle={isEditing ? `Status atual: ${quote?.status}` : 'Elabore uma nova proposta comercial com produtos do catálogo'}
        size="xl"
      >
        <form onSubmit={handleSubmit} className="dedicated-quote-modal-form">
          {modalError && (
            <div className="form-error-callout" role="alert">
              <AlertTriangle size={16} />
              <span>{modalError}</span>
            </div>
          )}

          {opportunityId && (
            <div style={{
              padding: '0.6rem 0.9rem',
              background: 'rgba(59, 130, 246, 0.1)',
              border: '1px solid rgba(59, 130, 246, 0.3)',
              borderRadius: '8px',
              color: '#93c5fd',
              fontSize: '0.85rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '1rem'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Sparkles size={16} />
                <span><strong>Oportunidade CRM Vinculada</strong> (ID: {opportunityId.slice(0, 8)}...)</span>
              </div>
              <span style={{ fontSize: '0.75rem', opacity: 0.8 }}>Amarração automática na rastreabilidade</span>
            </div>
          )}

          {quote?.cancellation_reason && (
            <div style={{
              padding: '0.6rem 0.9rem',
              background: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              borderRadius: '8px',
              color: '#fca5a5',
              fontSize: '0.85rem',
              marginBottom: '1rem'
            }}>
              <strong>Motivo do Cancelamento:</strong> {quote.cancellation_reason}
            </div>
          )}

        {/* 1. SEÇÃO DO CLIENTE */}
        <div data-record-tab="customer" hidden={page && formTab !== 'customer'} className="quote-modal-section">
          <div className="quote-modal-section__header">
            <Tag size={16} className="quote-modal-section__icon" />
            <h4 className="quote-modal-section__title">Dados do Cliente & Contato</h4>
          </div>

          <div className="quote-form-grid-2">
            <div className="form-group" style={{ gridColumn: 'span 2' }}>
              <CustomerPicker
                value={selectedCustomerId}
                onChange={handleCustomerChange}
                placeholder="Pesquise o cliente cadastrado no módulo de vendas..."
                initialCustomer={selectedCustomer}
              />
            </div>
          </div>

          <div className="quote-form-grid-3">
            <div className="form-group">
              <label>Nome / Razão Social *</label>
              <input
                type="text"
                required
                placeholder="Nome do cliente"
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
                className="ui-input"
              />
            </div>

            <div className="form-group">
              <label>CNPJ / CPF</label>
              <input
                type="text"
                placeholder="00.000.000/0000-00"
                value={customerDocument}
                onChange={(e) => setCustomerDocument(e.target.value)}
                className="ui-input"
              />
            </div>

            <div className="form-group">
              <label>E-mail / WhatsApp</label>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                <input
                  type="email"
                  placeholder="E-mail"
                  value={customerEmail}
                  onChange={(e) => setCustomerEmail(e.target.value)}
                  className="ui-input"
                />
                <input
                  type="text"
                  placeholder="Telefone"
                  value={customerPhone}
                  onChange={(e) => setCustomerPhone(e.target.value)}
                  className="ui-input"
                />
              </div>
            </div>
          </div>
        </div>

        {/* 2. SEÇÃO DE ITENS E PRODUTOS */}
        <div data-record-tab="items" hidden={page && formTab !== 'items'} className="quote-modal-section">
          <div className="quote-modal-section__header-row">
            <div className="quote-modal-section__header">
              <Package size={16} className="quote-modal-section__icon" />
              <h4 className="quote-modal-section__title">Itens da Proposta Comercial</h4>
            </div>
            <button
              type="button"
              className="btn-add-item"
              data-record-change onClick={handleAddItem}
            >
              <Plus size={14} /> Adicionar Produto
            </button>
          </div>

          {items.length === 0 ? (
            <div className="empty-items-placeholder">
              <Package size={32} />
              <p>Nenhum item adicionado à proposta.</p>
              <button
                type="button"
                className="btn-add-first-item"
                data-record-change onClick={handleAddItem}
              >
                <Plus size={14} /> Adicionar Primeiro Produto
              </button>
            </div>
          ) : (
            <div className="quote-items-table-container">
              <table className="quote-items-table">
                <thead>
                  <tr>
                    <th style={{ width: '40%' }}>Produto / SKU</th>
                    <th style={{ width: '12%' }}>Qtd</th>
                    <th style={{ width: '18%' }}>Preço Unit. (R$)</th>
                    <th style={{ width: '15%' }}>Desc. (R$)</th>
                    <th style={{ width: '15%' }}>Subtotal</th>
                    <th style={{ width: '5%' }}></th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((it, idx) => {
                    const itemSubtotal = Math.max(0, (it.quantity * it.unit_price) - (it.discount_amount || 0));
                    return (
                      <tr key={idx}>
                        <td>
                          <select
                            value={it.product_id}
                            onChange={(e) => handleItemProductChange(idx, e.target.value)}
                            className="ui-input-table"
                            required
                          >
                            <option value="">Selecione o produto...</option>
                            {products.map(p => (
                              <option key={p.id} value={p.id}>
                                {p.name} {p.sku ? `(${p.sku})` : ''} - {formatCurrency(Number(p.reference_price) || 0)}
                              </option>
                            ))}
                          </select>
                        </td>
                        <td>
                          <input
                            type="number"
                            min="1"
                            value={it.quantity}
                            onChange={(e) => handleItemFieldChange(idx, 'quantity', Math.max(1, parseInt(e.target.value) || 1))}
                            className="ui-input-table text-center"
                            required
                          />
                        </td>
                        <td>
                          <input
                            type="number"
                            step="0.01"
                            min="0"
                            value={it.unit_price}
                            onChange={(e) => handleItemFieldChange(idx, 'unit_price', parseFloat(e.target.value) || 0)}
                            className="ui-input-table text-right"
                            required
                          />
                        </td>
                        <td>
                          <input
                            type="number"
                            step="0.01"
                            min="0"
                            value={it.discount_amount}
                            onChange={(e) => handleItemFieldChange(idx, 'discount_amount', parseFloat(e.target.value) || 0)}
                            className="ui-input-table text-right"
                          />
                        </td>
                        <td className="item-subtotal-cell">
                          {formatCurrency(itemSubtotal)}
                        </td>
                        <td className="text-center">
                          <button
                            type="button"
                            className="btn-remove-row"
                            data-record-change onClick={() => handleRemoveItem(idx)}
                            title="Remover item"
                          >
                            <Trash2 size={15} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* 3. SEÇÃO DE CONDIÇÕES COMERCIAIS & RESUMO */}
        <div data-record-tab="terms" hidden={page && formTab !== 'terms'} className="quote-modal-section">
          <div className="quote-modal-section__header">
            <DollarSign size={16} className="quote-modal-section__icon" />
            <h4 className="quote-modal-section__title">Condições Comerciais & Totais</h4>
          </div>

          <div className="quote-form-grid-2">
            <div className="quote-conditions-col">
              <div className="form-group">
                <label>Validade da Proposta</label>
                <input
                  type="date"
                  value={validUntil}
                  onChange={(e) => setValidUntil(e.target.value)}
                  className="ui-input"
                  required
                />
              </div>

              <div className="form-group">
                <label>Condição de Pagamento</label>
                <select
                  value={paymentTerms}
                  onChange={(e) => setPaymentTerms(e.target.value)}
                  className="ui-input"
                >
                  <option value="À Vista">À Vista (PIX / TED)</option>
                  <option value="30 DDL">30 DDL</option>
                  <option value="30/60 DDL">30/60 DDL</option>
                  <option value="30/60/90 DDL">30/60/90 DDL</option>
                  <option value="Boleto 28D">Boleto 28D</option>
                  <option value="Cartão de Crédito">Cartão de Crédito</option>
                </select>
              </div>

              <div className="form-group">
                <label>Observações / Condições Especiais</label>
                <textarea
                  rows={2}
                  placeholder="Prazo de entrega, frete CIF/FOB, garantia ou observações gerais..."
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  className="ui-input ui-textarea"
                />
              </div>
            </div>

            {/* CARD DE RESUMO FINANCEIRO */}
            <div className="quote-summary-card">
              <h5 className="quote-summary-card__title">Resumo Financeiro</h5>
              
              <div className="quote-summary-card__row">
                <span>Subtotal Bruto:</span>
                <strong>{formatCurrency(totalGross)}</strong>
              </div>

              <div className="quote-summary-card__row discount">
                <span>Descontos Concedidos:</span>
                <strong>- {formatCurrency(totalDiscount)}</strong>
              </div>

              <div className="quote-summary-card__divider" />

              <div className="quote-summary-card__row total">
                <span>Valor Líquido Final:</span>
                <span className="total-highlight">{formatCurrency(totalNet)}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="modal-footer" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div className="footer-evolution-actions" style={{ display: 'flex', gap: '0.5rem' }}>
            {quote?.id && quote.status === 'DRAFT' && (
              <>
                <button
                  type="button"
                  className="ui-button ui-button--secondary"
                  onClick={() => handleUpdateStatus('SENT')}
                  disabled={isSaving}
                  title="Marcar proposta como enviada ao cliente"
                >
                  📤 Marcar Enviada
                </button>
                <button
                  type="button"
                  className="ui-button ui-button--secondary"
                  onClick={() => handleUpdateStatus('APPROVED')}
                  disabled={isSaving}
                  title="Aprovar proposta comercial"
                >
                  ✅ Aprovar Proposta
                </button>
              </>
            )}
            {quote?.id && quote.status === 'SENT' && (
              <>
                <button
                  type="button"
                  className="ui-button ui-button--secondary"
                  style={{ color: '#ef4444' }}
                  onClick={() => handleUpdateStatus('REJECTED')}
                  disabled={isSaving}
                  title="Marcar como recusada"
                >
                  ❌ Recusar
                </button>
                <button
                  type="button"
                  className="ui-button ui-button--secondary"
                  style={{ color: '#10b981' }}
                  onClick={() => handleUpdateStatus('APPROVED')}
                  disabled={isSaving}
                  title="Aprovar proposta"
                >
                  ✅ Aceitar / Aprovar
                </button>
              </>
            )}
            {quote?.id && quote.status === 'APPROVED' && (
              <button
                type="button"
                className="ui-button ui-button--primary"
                onClick={handleConvertToOrder}
                disabled={isSaving}
                title="Gerar Pedido de Venda oficial a partir desta cotação"
              >
                ⚡ Converter em Pedido de Venda
              </button>
            )}

            {quote?.id && ['DRAFT', 'SENT', 'APPROVED'].includes(quote.status) && (
              <button
                type="button"
                className="ui-button ui-button--secondary"
                style={{ color: '#ef4444' }}
                onClick={() => {
                  setCancelReason('');
                  setIsCancelModalOpen(true);
                }}
                disabled={isSaving}
                title="Cancelar cotação por desistência do cliente"
              >
                ❌ Cancelar Cotação
              </button>
            )}
          </div>

          <div className="footer-main-buttons" style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              type="button"
              className="btn-cancel"
              onClick={onClose}
              disabled={isSaving}
            >
              Fechar
            </button>
            {quote?.status !== 'CANCELLED' && quote?.status !== 'CONVERTED' && (
              <button
                type="submit"
                className="btn-save"
                disabled={isSaving}
              >
                {isSaving ? (
                  <span>Salvando...</span>
                ) : (
                  <>
                    <Check size={16} />
                    <span>{isEditing ? 'Salvar Cotação' : 'Emitir Cotação'}</span>
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      </form>
    </RecordEditorSurface>

    {/* SUBMODAL DE JUSTIFICATIVA DE CANCELAMENTO */}
    {isCancelModalOpen && (
      <Modal
        isOpen={isCancelModalOpen}
        onClose={() => setIsCancelModalOpen(false)}
        title="Cancelar Cotação Comercial"
        subtitle={`Informe o motivo do cancelamento / desistência da cotação #${quote?.quote_number || ''}`}
        size="md"
      >
        <div style={{ padding: '0.5rem 0' }}>
          <div className="form-group" style={{ marginBottom: '1.25rem' }}>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600 }}>
              Motivo do Cancelamento / Desistência *
            </label>
            <textarea
              rows={3}
              required
              placeholder="Ex: Cliente desistiu do projeto / Optou por proposta concorrente / Alteração de escopo"
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
              className="ui-input"
              style={{ width: '100%', resize: 'vertical' }}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
            <button
              type="button"
              className="ui-button ui-button--secondary"
              onClick={() => setIsCancelModalOpen(false)}
              disabled={isSaving}
            >
              Voltar
            </button>
            <button
              type="button"
              className="ui-button ui-button--danger"
              style={{ background: '#ef4444', color: '#fff' }}
              onClick={handleCancelQuote}
              disabled={isSaving || !cancelReason.trim()}
            >
              {isSaving ? 'Cancelando...' : 'Confirmar Cancelamento'}
            </button>
          </div>
        </div>
      </Modal>
    )}
  </>
  );
};
