/**
 * pages/POS/POS.tsx - Frente de Caixa & Ponto de Venda Balcão (ControlB ERP)
 * 
 * Módulo operacional independente para Frente de Caixa:
 * 1. 🟢 Abertura e Fechamento de Caixa / Turno Operacional
 * 2. 💸 Movimentações Financeiras de Caixa (Sangria e Suprimento com Histórico)
 * 3. 🛒 Venda Balcão Ágil (Busca por SKU/Nome, Leitor de Código de Barras, Carrinho)
 * 4. 💵 Pagamento com Múltiplas Formas (Dinheiro, PIX, Cartão Débito/Crédito) e Troco
 * 5. 🖨️ Emissão e Impressão de Cupom Térmico Não-Fiscal
 * 6. 📜 Histórico das Vendas Realizadas no Turno
 */

import React, { useState, useEffect, useMemo } from 'react';
import {
  Store, ShoppingCart, DollarSign, Lock, Unlock,
  Printer, Trash2, Plus, Search, CheckCircle2,
  RefreshCw, Package, Users, Receipt, CreditCard
} from 'lucide-react';
import { salesService, inventoryService, formatApiError } from '@/services/api';
import { POSSession, POSSale, POSCashMovement, Product, Customer } from '@/types';
import { Modal } from '@/components/Modal/Modal';
import { RecordLink, useRecordDeepLink } from '@/components/RecordLink';
import { formatCurrency } from '@/utils/formatters';
import './POS.scss';

export const POS: React.FC = () => {
  const [activeSession, setActiveSession] = useState<POSSession | null>(null);
  const [posSales, setPosSales] = useState<POSSale[]>([]);
  const [cashMovements, setCashMovements] = useState<POSCashMovement[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Estados do Carrinho do PDV
  const [posCart, setPosCart] = useState<Array<{
    product: Product;
    quantity: number;
    unit_price: number;
    total_price: number;
  }>>([]);
  const [productSearch, setProductSearch] = useState<string>('');
  const [selectedCustomerId, setSelectedCustomerId] = useState<string>('');
  const [customerNameInput, setCustomerNameInput] = useState<string>('Consumidor Final');
  const [customerDocInput, setCustomerDocInput] = useState<string>('');
  const [paymentMethod, setPaymentMethod] = useState<string>('DINHEIRO');
  const [discountAmount, setDiscountAmount] = useState<string>('0.00');
  const [amountPaid, setAmountPaid] = useState<string>('');

  // Modais do PDV
  const [isOpenSessionModal, setIsOpenSessionModal] = useState<boolean>(false);
  const [isCloseSessionModal, setIsCloseSessionModal] = useState<boolean>(false);
  const [isCashMovementModal, setIsCashMovementModal] = useState<boolean>(false);
  const [isReceiptModalOpen, setIsReceiptModalOpen] = useState<boolean>(false);
  const [lastCompletedSale, setLastCompletedSale] = useState<POSSale | null>(null);

  // Formulários auxiliares
  const [openingCashInput, setOpeningCashInput] = useState<string>('100.00');
  const [closingCashInput, setClosingCashInput] = useState<string>('0.00');
  const [movementType, setMovementType] = useState<'SANGRIA' | 'SUPRIMENTO'>('SANGRIA');
  const [movementAmount, setMovementAmount] = useState<string>('50.00');
  const [movementReason, setMovementReason] = useState<string>('');

  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [modalError, setModalError] = useState<string | null>(null);

  const triggerFeedback = (type: 'success' | 'error', message: string) => {
    setFeedback({ type, message });
    setTimeout(() => setFeedback(null), 5000);
  };

  const safeNumber = (val: any): number => {
    if (val === undefined || val === null) return 0;
    const n = typeof val === 'string' ? parseFloat(val) : Number(val);
    return isNaN(n) ? 0 : n;
  };

  const loadData = async (force = false) => {
    setIsLoading(true);
    try {
      const [sess, salesList, prods, custs] = await Promise.all([
        salesService.getActivePOSSession(),
        salesService.getPOSSales(force),
        inventoryService.getProducts(undefined, force),
        salesService.getCustomers('', force)
      ]);
      setActiveSession(sess);
      setPosSales(salesList || []);
      setProducts(prods || []);
      setCustomers(custs || []);

      if (sess?.id) {
        const movs = await salesService.getCashMovements(sess.id, force);
        setCashMovements(movs || []);
      } else {
        setCashMovements([]);
      }
    } catch (err: any) {
      triggerFeedback('error', formatApiError(err, 'Erro ao carregar dados do PDV.'));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  useRecordDeepLink({
    types: ['POS_SALE'],
    records: posSales,
    onOpen: (sale) => {
      setLastCompletedSale(sale);
      setIsReceiptModalOpen(true);
    },
  });

  // Cálculos do Carrinho
  const cartSubtotal = useMemo(() => {
    return posCart.reduce((acc, it) => acc + it.total_price, 0);
  }, [posCart]);

  const numDiscount = useMemo(() => {
    return Math.max(0, safeNumber(discountAmount));
  }, [discountAmount]);

  const cartTotal = useMemo(() => {
    return Math.max(0, cartSubtotal - numDiscount);
  }, [cartSubtotal, numDiscount]);

  const numAmountPaid = useMemo(() => {
    return safeNumber(amountPaid);
  }, [amountPaid]);

  const changeDue = useMemo(() => {
    if (paymentMethod !== 'DINHEIRO' || numAmountPaid <= cartTotal) return 0;
    return numAmountPaid - cartTotal;
  }, [paymentMethod, numAmountPaid, cartTotal]);

  // Filtro rápido de produtos
  const filteredProducts = useMemo(() => {
    if (!productSearch.trim()) return products.slice(0, 12);
    const q = productSearch.toLowerCase();
    return products.filter(p =>
      p.name.toLowerCase().includes(q) ||
      (p.sku && p.sku.toLowerCase().includes(q)) ||
      (p.barcode && p.barcode.toLowerCase().includes(q))
    ).slice(0, 20);
  }, [products, productSearch]);

  const handleAddToCart = (product: Product) => {
    const existingIndex = posCart.findIndex(it => it.product.id === product.id);
    const price = safeNumber(product.reference_price) || 10.00;

    if (existingIndex >= 0) {
      const updated = [...posCart];
      updated[existingIndex].quantity += 1;
      updated[existingIndex].total_price = updated[existingIndex].quantity * updated[existingIndex].unit_price;
      setPosCart(updated);
    } else {
      setPosCart([
        ...posCart,
        {
          product,
          quantity: 1,
          unit_price: price,
          total_price: price
        }
      ]);
    }
  };

  const handleUpdateQuantity = (index: number, newQty: number) => {
    if (newQty <= 0) {
      handleRemoveItem(index);
      return;
    }
    const updated = [...posCart];
    updated[index].quantity = newQty;
    updated[index].total_price = newQty * updated[index].unit_price;
    setPosCart(updated);
  };

  const handleRemoveItem = (index: number) => {
    setPosCart(posCart.filter((_, idx) => idx !== index));
  };

  const handleClearCart = () => {
    setPosCart([]);
    setDiscountAmount('0.00');
    setAmountPaid('');
  };

  // Finalizar Venda Balcão
  const handleCheckout = async () => {
    if (!activeSession) {
      triggerFeedback('error', 'O caixa precisa estar aberto para registrar vendas.');
      return;
    }
    if (posCart.length === 0) {
      triggerFeedback('error', 'O carrinho de compras está vazio.');
      return;
    }
    if (paymentMethod === 'DINHEIRO' && numAmountPaid < cartTotal) {
      triggerFeedback('error', 'O valor pago em dinheiro é insuficiente para cobrir o total da venda.');
      return;
    }

    setIsSubmitting(true);
    try {
      const sale = await salesService.recordPOSSale({
        pos_session_id: activeSession.id,
        customer_id: selectedCustomerId || undefined,
        customer_name: customerNameInput.trim() || 'Consumidor Final',
        customer_document: customerDocInput.trim() || undefined,
        total_amount: cartSubtotal,
        discount_amount: numDiscount,
        payment_method: paymentMethod,
        items: posCart.map(it => ({
          product_id: it.product.id,
          quantity: it.quantity,
          unit_price: it.unit_price
        }))
      });

      setLastCompletedSale(sale);
      setIsReceiptModalOpen(true);
      handleClearCart();
      triggerFeedback('success', `Venda #${sale.id.substring(0, 8).toUpperCase()} finalizada com sucesso!`);
      loadData(true);
    } catch (err: any) {
      triggerFeedback('error', formatApiError(err, 'Erro ao finalizar venda balcão.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  // Abertura de Caixa
  const handleOpenSession = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setModalError(null);
    try {
      const sess = await salesService.openPOSSession({
        pos_terminal: 'Caixa Principal 01',
        opening_cash: safeNumber(openingCashInput)
      });
      setActiveSession(sess);
      setIsOpenSessionModal(false);
      triggerFeedback('success', 'Turno de caixa aberto com sucesso!');
      loadData(true);
    } catch (err: any) {
      setModalError(formatApiError(err, 'Erro ao abrir caixa.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  // Fechamento de Caixa
  const handleCloseSession = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeSession) return;
    setIsSubmitting(true);
    setModalError(null);
    try {
      await salesService.closePOSSession(activeSession.id, {
        closing_cash: safeNumber(closingCashInput)
      });
      setActiveSession(null);
      setIsCloseSessionModal(false);
      triggerFeedback('success', 'Caixa encerrado com sucesso!');
      loadData(true);
    } catch (err: any) {
      setModalError(formatApiError(err, 'Erro ao encerrar caixa.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  // Sangria e Suprimento
  const handleSaveMovement = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeSession) return;
    if (!movementReason.trim()) {
      setModalError('Informe o motivo da movimentação de caixa.');
      return;
    }
    setIsSubmitting(true);
    setModalError(null);
    try {
      await salesService.recordCashMovement({
        pos_session_id: activeSession.id,
        movement_type: movementType,
        amount: safeNumber(movementAmount),
        reason: movementReason.trim()
      });
      setIsCashMovementModal(false);
      setMovementReason('');
      triggerFeedback('success', `${movementType === 'SANGRIA' ? 'Sangria' : 'Suprimento'} registrado com sucesso!`);
      loadData(true);
    } catch (err: any) {
      setModalError(formatApiError(err, 'Erro ao registrar movimentação.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="pos-page-wrapper">
      {/* Feedback Toast */}
      {feedback && (
        <div className={`feedback-toast ${feedback.type}`}>
          {feedback.message}
        </div>
      )}

      {/* Top Bar de Status do Caixa */}
      <header className="pos-header">
        <div className="header-left">
          <div className="icon-badge">
            <Store size={22} />
          </div>
          <div>
            <h1>Frente de Caixa (PDV)</h1>
            <p className="subtitle">Operação de Venda Balcão, Abertura/Fechamento e Emissão Térmica</p>
          </div>
        </div>

        <div className="header-right">
          {activeSession ? (
            <div className="session-status-badge open">
              <span className="pulse-dot"></span>
              <span>Caixa Aberto (Fundo: {formatCurrency(activeSession.opening_cash)})</span>
            </div>
          ) : (
            <div className="session-status-badge closed">
              <span className="dot-closed"></span>
              <span>Caixa Fechado</span>
            </div>
          )}

          <button
            type="button"
            className="btn-refresh"
            onClick={() => loadData(true)}
            title="Recarregar dados"
            disabled={isLoading}
          >
            <RefreshCw size={15} className={isLoading ? 'spinning' : ''} />
          </button>

          {activeSession ? (
            <>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setIsCashMovementModal(true)}
              >
                <DollarSign size={15} /> Sangria / Suprimento
              </button>
              <button
                type="button"
                className="btn-danger"
                onClick={() => {
                  setClosingCashInput(String(activeSession.opening_cash || '0.00'));
                  setIsCloseSessionModal(true);
                }}
              >
                <Lock size={15} /> Fechar Caixa
              </button>
            </>
          ) : (
            <button
              type="button"
              className="btn-primary"
              onClick={() => setIsOpenSessionModal(true)}
            >
              <Unlock size={15} /> Abrir Caixa
            </button>
          )}
        </div>
      </header>

      {/* Grade Principal do PDV: Catálogo à Esquerda + Carrinho/Checkout à Direita */}
      <div className="pos-grid">
        {/* LADO ESQUERDO: Catálogo & Busca Rápida */}
        <div className="pos-catalog-panel">
          <div className="catalog-search-bar">
            <Search size={18} className="search-icon" />
            <input
              type="text"
              placeholder="Buscar produto por Nome, Código SKU ou Código de Barras (F3)..."
              value={productSearch}
              onChange={(e) => setProductSearch(e.target.value)}
              disabled={!activeSession}
            />
          </div>

          {!activeSession && (
            <div className="session-blocked-warning">
              <Lock size={32} />
              <h3>Caixa Fechado</h3>
              <p>Abra o caixa no topo da página para iniciar a registrar vendas balcão.</p>
              <button className="btn-primary" onClick={() => setIsOpenSessionModal(true)}>
                <Unlock size={16} /> Abrir Caixa Agora
              </button>
            </div>
          )}

          {activeSession && (
            <div className="product-cards-grid">
              {filteredProducts.length === 0 ? (
                <div className="no-products">
                  <Package size={36} />
                  <p>Nenhum produto encontrado para a busca "{productSearch}".</p>
                </div>
              ) : (
                filteredProducts.map(p => (
                  <div
                    key={p.id}
                    className="product-card"
                    onClick={() => handleAddToCart(p)}
                  >
                    <div className="product-info">
                      <span className="sku">{p.sku || 'SEM-SKU'}</span>
                      <h4 className="title">{p.name}</h4>
                      <span className="category">{p.category?.name || 'Geral'}</span>
                    </div>
                    <div className="product-bottom">
                      <span className="price">{formatCurrency(safeNumber(p.reference_price) || 10.00)}</span>
                      <button type="button" className="btn-add-cart" title="Adicionar ao Carrinho">
                        <Plus size={16} />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        {/* LADO DIREITO: Carrinho & Painel de Pagamento */}
        <div className="pos-checkout-panel">
          <div className="checkout-header">
            <h3><ShoppingCart size={18} /> Carrinho de Compras</h3>
            {posCart.length > 0 && (
              <button type="button" className="btn-clear" onClick={handleClearCart}>
                Limpar
              </button>
            )}
          </div>

          {/* Identificação do Cliente */}
          <div className="customer-selector-box">
            <div className="selector-row">
              <label><Users size={14} /> Cliente:</label>
              <select
                value={selectedCustomerId}
                onChange={(e) => {
                  const cid = e.target.value;
                  setSelectedCustomerId(cid);
                  const cust = customers.find(c => c.id === cid);
                  if (cust) {
                    setCustomerNameInput(cust.name);
                    setCustomerDocInput(cust.document || '');
                  } else {
                    setCustomerNameInput('Consumidor Final');
                    setCustomerDocInput('');
                  }
                }}
              >
                <option value="">Consumidor Final (Sem Cadastro)</option>
                {customers.map(c => (
                  <option key={c.id} value={c.id}>{c.name} ({c.document || 'S/ Doc'})</option>
                ))}
              </select>
            </div>
            {!selectedCustomerId && (
              <div className="manual-customer-inputs">
                <input
                  type="text"
                  placeholder="Nome do Cliente"
                  value={customerNameInput}
                  onChange={(e) => setCustomerNameInput(e.target.value)}
                />
                <input
                  type="text"
                  placeholder="CPF/CNPJ na Nota (Opcional)"
                  value={customerDocInput}
                  onChange={(e) => setCustomerDocInput(e.target.value)}
                />
              </div>
            )}
          </div>

          {/* Lista de Itens do Carrinho */}
          <div className="cart-items-container">
            {posCart.length === 0 ? (
              <div className="empty-cart-message">
                <ShoppingCart size={40} />
                <p>Nenhum item no carrinho.</p>
                <span>Clique nos produtos do catálogo para adicionar.</span>
              </div>
            ) : (
              posCart.map((item, idx) => (
                <div key={idx} className="cart-item-row">
                  <div className="item-details">
                    <span className="item-name">{item.product.name}</span>
                    <span className="item-unit-price">{formatCurrency(item.unit_price)} un.</span>
                  </div>

                  <div className="item-controls">
                    <div className="qty-picker">
                      <button
                        type="button"
                        onClick={() => handleUpdateQuantity(idx, item.quantity - 1)}
                      >
                        -
                      </button>
                      <input
                        type="number"
                        min="1"
                        value={item.quantity}
                        onChange={(e) => handleUpdateQuantity(idx, parseInt(e.target.value) || 1)}
                      />
                      <button
                        type="button"
                        onClick={() => handleUpdateQuantity(idx, item.quantity + 1)}
                      >
                        +
                      </button>
                    </div>

                    <span className="item-total-price">{formatCurrency(item.total_price)}</span>

                    <button
                      type="button"
                      className="btn-del-item"
                      onClick={() => handleRemoveItem(idx)}
                      title="Remover Item"
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Resumo de Valores e Forma de Pagamento */}
          <div className="checkout-summary-box">
            <div className="summary-line">
              <span>Subtotal:</span>
              <span>{formatCurrency(cartSubtotal)}</span>
            </div>

            <div className="summary-line discount-line">
              <span>Desconto (R$):</span>
              <input
                type="number"
                step="0.01"
                min="0"
                value={discountAmount}
                onChange={(e) => setDiscountAmount(e.target.value)}
                disabled={posCart.length === 0}
              />
            </div>

            <div className="summary-line total-line">
              <span>Total a Pagar:</span>
              <span className="total-val">{formatCurrency(cartTotal)}</span>
            </div>

            {/* Forma de Pagamento */}
            <div className="payment-options">
              <label><CreditCard size={14} /> Forma de Pagamento:</label>
              <div className="payment-buttons">
                {['DINHEIRO', 'PIX', 'CARTAO_DEBITO', 'CARTAO_CREDITO'].map(method => (
                  <button
                    key={method}
                    type="button"
                    className={`btn-pay-method ${paymentMethod === method ? 'active' : ''}`}
                    onClick={() => setPaymentMethod(method)}
                  >
                    {method.replace('_', ' ')}
                  </button>
                ))}
              </div>
            </div>

            {paymentMethod === 'DINHEIRO' && (
              <div className="cash-payment-details">
                <div className="summary-line">
                  <span>Valor Entregue (R$):</span>
                  <input
                    type="number"
                    step="0.01"
                    placeholder="0.00"
                    value={amountPaid}
                    onChange={(e) => setAmountPaid(e.target.value)}
                  />
                </div>
                {changeDue > 0 && (
                  <div className="summary-line change-line">
                    <span>Troco:</span>
                    <span className="change-val">{formatCurrency(changeDue)}</span>
                  </div>
                )}
              </div>
            )}

            <button
              type="button"
              className="btn-checkout-now"
              onClick={handleCheckout}
              disabled={!activeSession || posCart.length === 0 || isSubmitting}
            >
              {isSubmitting ? (
                'Processando Venda...'
              ) : (
                <>
                  <CheckCircle2 size={18} /> Finalizar Venda ({formatCurrency(cartTotal)})
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Histórico das Vendas do Turno */}
      {activeSession && (
        <section className="pos-history-section">
          <div className="history-header">
            <h3><Receipt size={18} /> Vendas e Movimentações Recentes do Caixa</h3>
          </div>

          <div className="history-tables-grid">
            <div className="history-card">
              <h4>Últimas Vendas</h4>
              {posSales.length === 0 ? (
                <p className="empty-hint">Nenhuma venda registrada ainda no turno.</p>
              ) : (
                <table className="mini-table">
                  <thead>
                    <tr>
                      <th>Venda</th>
                      <th>Cliente</th>
                      <th>Pagamento</th>
                      <th>Total</th>
                      <th>Ação</th>
                    </tr>
                  </thead>
                  <tbody>
                    {posSales.slice(0, 5).map(s => (
                      <tr
                        key={s.id}
                        className="ui-record-row"
                        role="button"
                        tabIndex={0}
                        onClick={() => {
                          setLastCompletedSale(s);
                          setIsReceiptModalOpen(true);
                        }}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter' || event.key === ' ') {
                            event.preventDefault();
                            setLastCompletedSale(s);
                            setIsReceiptModalOpen(true);
                          }
                        }}
                      >
                        <td>#{s.id.substring(0, 8).toUpperCase()}</td>
                        <td>
                          <RecordLink type="CUSTOMER" id={s.customer_id} showIcon={false}>
                            {s.customer_name}
                          </RecordLink>
                        </td>
                        <td>{s.payment_method}</td>
                        <td>{formatCurrency(s.net_amount)}</td>
                        <td>
                          <button
                            type="button"
                            className="btn-print-sm"
                            onClick={(event) => {
                              event.stopPropagation();
                              setLastCompletedSale(s);
                              setIsReceiptModalOpen(true);
                            }}
                          >
                            <Printer size={13} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            <div className="history-card">
              <h4>Sangrias & Suprimentos</h4>
              {cashMovements.length === 0 ? (
                <p className="empty-hint">Nenhuma sangria ou suprimento no turno.</p>
              ) : (
                <table className="mini-table">
                  <thead>
                    <tr>
                      <th>Tipo</th>
                      <th>Valor</th>
                      <th>Motivo</th>
                      <th>Horário</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cashMovements.slice(0, 5).map(m => (
                      <tr key={m.id}>
                        <td>
                          <span className={`pill-mov ${m.movement_type === 'SANGRIA' ? 'danger' : 'success'}`}>
                            {m.movement_type}
                          </span>
                        </td>
                        <td>{formatCurrency(m.amount)}</td>
                        <td>{m.reason}</td>
                        <td>{new Date(m.created_at).toLocaleTimeString('pt-BR')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </section>
      )}

      {/* MODAL 1: Abertura de Caixa */}
      <Modal
        isOpen={isOpenSessionModal}
        onClose={() => setIsOpenSessionModal(false)}
        title="Abertura de Caixa / Turno"
        subtitle="Inicie um novo turno para registrar vendas balcão"
        size="sm"
      >
        <form onSubmit={handleOpenSession} className="wizard-form">
          {modalError && <div className="form-error-callout">{modalError}</div>}
          <div className="form-group">
            <label>Fundo de Troco Inicial (R$) *</label>
            <input
              type="number"
              step="0.01"
              required
              value={openingCashInput}
              onChange={(e) => setOpeningCashInput(e.target.value)}
            />
          </div>
          <div className="modal-footer">
            <button type="button" className="btn-secondary" onClick={() => setIsOpenSessionModal(false)}>
              Cancelar
            </button>
            <button type="submit" className="btn-primary" disabled={isSubmitting}>
              {isSubmitting ? 'Abrindo...' : 'Confirmar Abertura'}
            </button>
          </div>
        </form>
      </Modal>

      {/* MODAL 2: Fechamento de Caixa */}
      <Modal
        isOpen={isCloseSessionModal}
        onClose={() => setIsCloseSessionModal(false)}
        title="Fechamento de Caixa"
        subtitle="Informe a contagem física em dinheiro para encerramento do turno"
        size="sm"
      >
        <form onSubmit={handleCloseSession} className="wizard-form">
          {modalError && <div className="form-error-callout">{modalError}</div>}
          <div className="form-group">
            <label>Valor Total em Dinheiro na Gaveta (R$) *</label>
            <input
              type="number"
              step="0.01"
              required
              value={closingCashInput}
              onChange={(e) => setClosingCashInput(e.target.value)}
            />
          </div>
          <div className="modal-footer">
            <button type="button" className="btn-secondary" onClick={() => setIsCloseSessionModal(false)}>
              Cancelar
            </button>
            <button type="submit" className="btn-danger" disabled={isSubmitting}>
              {isSubmitting ? 'Encerrando...' : 'Encerrar Caixa'}
            </button>
          </div>
        </form>
      </Modal>

      {/* MODAL 3: Sangria / Suprimento */}
      <Modal
        isOpen={isCashMovementModal}
        onClose={() => setIsCashMovementModal(false)}
        title="Movimentação de Caixa"
        subtitle="Retirada (Sangria) ou Entrada (Suprimento) de numerário"
        size="sm"
      >
        <form onSubmit={handleSaveMovement} className="wizard-form">
          {modalError && <div className="form-error-callout">{modalError}</div>}
          <div className="form-group">
            <label>Tipo de Movimentação *</label>
            <select value={movementType} onChange={(e) => setMovementType(e.target.value as any)}>
              <option value="SANGRIA">Sangria (Retirada de Dinheiro)</option>
              <option value="SUPRIMENTO">Suprimento (Entrada de Dinheiro)</option>
            </select>
          </div>
          <div className="form-group">
            <label>Valor (R$) *</label>
            <input
              type="number"
              step="0.01"
              required
              value={movementAmount}
              onChange={(e) => setMovementAmount(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label>Motivo da Operação *</label>
            <input
              type="text"
              required
              placeholder="Ex: Pagamento de frete / Aporte de moedas"
              value={movementReason}
              onChange={(e) => setMovementReason(e.target.value)}
            />
          </div>
          <div className="modal-footer">
            <button type="button" className="btn-secondary" onClick={() => setIsCashMovementModal(false)}>
              Cancelar
            </button>
            <button type="submit" className="btn-primary" disabled={isSubmitting}>
              {isSubmitting ? 'Gravando...' : 'Registrar Movimentação'}
            </button>
          </div>
        </form>
      </Modal>

      {/* MODAL 4: Cupom Térmico Não-Fiscal */}
      <Modal
        isOpen={isReceiptModalOpen}
        onClose={() => setIsReceiptModalOpen(false)}
        title="Comprovante de Venda Balcão"
        subtitle="Cupom não-fiscal gerado com sucesso"
        size="sm"
      >
        <div className="thermal-receipt">
          <div className="receipt-header">
            <h3>CONTROLB ERP</h3>
            <p>Comprovante Não-Fiscal de Venda</p>
            <p>Data: {new Date().toLocaleString('pt-BR')}</p>
            {lastCompletedSale && <p>Cupom #{lastCompletedSale.id.substring(0, 8).toUpperCase()}</p>}
          </div>

          <div className="receipt-divider">--------------------------------</div>

          <div className="receipt-customer">
            <p>
              <strong>Cliente:</strong>{' '}
              <RecordLink type="CUSTOMER" id={lastCompletedSale?.customer_id} showIcon={false}>
                {lastCompletedSale?.customer_name || 'Consumidor Final'}
              </RecordLink>
            </p>
            {lastCompletedSale?.customer_document && (
              <p><strong>Doc:</strong> {lastCompletedSale.customer_document}</p>
            )}
            <p><strong>Pagamento:</strong> {lastCompletedSale?.payment_method}</p>
          </div>

          <div className="receipt-divider">--------------------------------</div>

          <div className="receipt-items">
            {lastCompletedSale?.items?.map((it, idx) => (
              <div key={idx} className="receipt-line">
                <span>{it.quantity}x {formatCurrency(it.unit_price)}</span>
                <span>{formatCurrency(it.total_price)}</span>
              </div>
            ))}
          </div>

          <div className="receipt-divider">--------------------------------</div>

          <div className="receipt-totals">
            <div className="line">
              <span>Subtotal:</span>
              <span>{formatCurrency(lastCompletedSale?.total_amount || 0)}</span>
            </div>
            {safeNumber(lastCompletedSale?.discount_amount) > 0 && (
              <div className="line">
                <span>Desconto:</span>
                <span>- {formatCurrency(lastCompletedSale?.discount_amount || 0)}</span>
              </div>
            )}
            <div className="line total">
              <span>TOTAL PAGO:</span>
              <span>{formatCurrency(lastCompletedSale?.net_amount || 0)}</span>
            </div>
          </div>

          <div className="receipt-footer">
            <p>Obrigado pela preferência!</p>
            <p>ControlB Software ERP</p>
          </div>

          <div className="receipt-actions no-print">
            <button type="button" className="btn-print" onClick={() => window.print()}>
              <Printer size={15} /> Imprimir Cupom Térmico
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default POS;
