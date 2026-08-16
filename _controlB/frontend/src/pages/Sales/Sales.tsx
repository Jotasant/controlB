/**
 * pages/Sales/Sales.tsx - Módulo de Vendas, Orçamentos & Frente de Caixa PDV (ControlB)
 */

import React, { useState, useEffect } from 'react';
import {
  ShoppingBag, Store, FileText, RefreshCw, Search,
  CheckCircle2, Trash2, X
} from 'lucide-react';
import { salesService, inventoryService } from '@/services/api';
import { SalesOrder, SalesQuote, Product } from '@/types';
import './Sales.scss';

export const Sales: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'pos' | 'orders' | 'quotes'>('pos');
  const [loading, setLoading] = useState<boolean>(true);

  // Dados
  const [orders, setOrders] = useState<SalesOrder[]>([]);
  const [quotes, setQuotes] = useState<SalesQuote[]>([]);
  const [products, setProducts] = useState<Product[]>([]);

  // PDV State
  const [productSearch, setProductSearch] = useState<string>('');
  const [cart, setCart] = useState<Array<{
    product: Product;
    quantity: number;
    unit_price: number;
    discount_amount: number;
  }>>([]);
  const [customerName, setCustomerName] = useState<string>('Consumidor Final');
  const [paymentMethod, setPaymentMethod] = useState<string>('DINHEIRO');
  const [generalDiscount, setGeneralDiscount] = useState<string>('0.00');

  // Modais
  const [isSessionModalOpen, setIsSessionModalOpen] = useState<boolean>(false);
  const [openingCash, setOpeningCash] = useState<string>('100.00');

  const loadAllSalesData = async () => {
    setLoading(true);
    try {
      const [ordersRes, quotesRes, prodsRes] = await Promise.all([
        salesService.getOrders().catch(() => []),
        salesService.getQuotes().catch(() => []),
        inventoryService.getProducts().catch(() => [])
      ]);
      setOrders(ordersRes);
      setQuotes(quotesRes);
      setProducts(prodsRes);
    } catch (err) {
      console.error("Erro ao carregar dados de vendas:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAllSalesData();
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

  // --- PDV: Adicionar Produto ao Carrinho ---
  const handleAddToCart = (prod: Product) => {
    const existing = cart.find(item => item.product.id === prod.id);
    const salePrice = (prod as any).selling_price || 25.00;

    if (existing) {
      setCart(cart.map(item =>
        item.product.id === prod.id
          ? { ...item, quantity: item.quantity + 1 }
          : item
      ));
    } else {
      setCart([...cart, {
        product: prod,
        quantity: 1,
        unit_price: salePrice,
        discount_amount: 0
      }]);
    }
  };

  const handleUpdateQty = (prodId: string, newQty: number) => {
    if (newQty <= 0) {
      setCart(cart.filter(item => item.product.id !== prodId));
    } else {
      setCart(cart.map(item =>
        item.product.id === prodId ? { ...item, quantity: newQty } : item
      ));
    }
  };

  const handleRemoveFromCart = (prodId: string) => {
    setCart(cart.filter(item => item.product.id !== prodId));
  };

  // Cálculos do Carrinho
  const cartSubtotal = cart.reduce((acc, it) => acc + (it.quantity * it.unit_price), 0);
  const discountVal = parseFloat(generalDiscount) || 0;
  const cartFinalTotal = Math.max(0, cartSubtotal - discountVal);

  const handleFinalizePOSSale = async () => {
    if (cart.length === 0) {
      alert("Adicione produtos ao carrinho antes de finalizar.");
      return;
    }

    try {
      await salesService.processPOSSale({
        customer_name: customerName,
        payment_method: paymentMethod,
        discount_amount: discountVal,
        items: cart.map(item => ({
          product_id: item.product.id,
          quantity: item.quantity,
          unit_price: item.unit_price
        }))
      });

      alert("🎉 Venda de balcão finalizada e estoque baixado com sucesso!");
      setCart([]);
      setGeneralDiscount('0.00');
      setCustomerName('Consumidor Final');
      loadAllSalesData();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Erro ao registrar venda.");
    }
  };

  const handleOpenPOSSession = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await salesService.openPOSSession({
        pos_terminal: 'CAIXA-01',
        opening_cash: parseFloat(openingCash || '0')
      });
      alert("✅ Turno de caixa aberto com sucesso!");
      setIsSessionModalOpen(false);
      loadAllSalesData();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Erro ao abrir caixa.");
    }
  };

  const filteredProducts = products.filter(p =>
    p.name.toLowerCase().includes(productSearch.toLowerCase()) ||
    (p.sku && p.sku.toLowerCase().includes(productSearch.toLowerCase()))
  );

  return (
    <div className="sales-page">
      <div className="sales-layout">
        {/* 1. SIDEBAR LATERAL ESQUERDA */}
        <aside className="sidebar-left">
          <div className="sidebar-header">
            <ShoppingBag className="brand-icon" size={20} />
            <div className="sidebar-title-wrap">
              <span className="sidebar-title"><strong>Vendas & PDV</strong></span>
              <span className="sidebar-subtitle">Operação Comercial</span>
            </div>
          </div>

          <nav className="nav-menu">
            <span className="menu-group-label">Canais de Venda</span>

            <button
              className={`nav-item ${activeTab === 'pos' ? 'active' : ''}`}
              onClick={() => setActiveTab('pos')}
            >
              <div className="nav-item-content">
                <Store size={16} />
                <span>Frente de Caixa (PDV)</span>
              </div>
            </button>

            <button
              className={`nav-item ${activeTab === 'orders' ? 'active' : ''}`}
              onClick={() => setActiveTab('orders')}
            >
              <div className="nav-item-content">
                <ShoppingBag size={16} />
                <span>Pedidos de Venda</span>
              </div>
              <span className="nav-badge">{orders.length}</span>
            </button>

            <button
              className={`nav-item ${activeTab === 'quotes' ? 'active' : ''}`}
              onClick={() => setActiveTab('quotes')}
            >
              <div className="nav-item-content">
                <FileText size={16} />
                <span>Orçamentos Comerciais</span>
              </div>
              <span className="nav-badge">{quotes.length}</span>
            </button>
          </nav>
        </aside>

        {/* 2. CONTEÚDO PRINCIPAL */}
        <main className="main-content">
          <div className="content-header">
            <div className="header-titles">
              <h1>
                {activeTab === 'pos' && 'Frente de Caixa (PDV Balcão Ágil)'}
                {activeTab === 'orders' && 'Pedidos de Venda Formalizados'}
                {activeTab === 'quotes' && 'Orçamentos & Propostas Comerciais'}
              </h1>
              <p className="subtitle">Gestão de vendas no balcão e pedidos corporativos</p>
            </div>

            <div className="header-actions">
              <button className="btn-refresh" onClick={loadAllSalesData} title="Atualizar Dados">
                <RefreshCw size={15} className={loading ? 'spinning' : ''} />
              </button>

              <button className="btn-secondary" onClick={() => setIsSessionModalOpen(true)}>
                <Store size={16} />
                <span>Abrir Turno de Caixa</span>
              </button>
            </div>
          </div>

          {/* ABA PDV */}
          {activeTab === 'pos' && (
            <div className="pos-workspace">
              {/* Catálogo de Produtos */}
              <div className="pos-catalog-panel">
                <div className="catalog-search-bar">
                  <Search size={16} />
                  <input
                    type="text"
                    placeholder="Buscar produto por nome ou código SKU..."
                    value={productSearch}
                    onChange={(e) => setProductSearch(e.target.value)}
                  />
                </div>

                <div className="products-grid">
                  {filteredProducts.length === 0 ? (
                    <div className="empty-catalog">Nenhum produto encontrado.</div>
                  ) : (
                    filteredProducts.map((prod) => (
                      <div
                        key={prod.id}
                        className="product-card-pos"
                        onClick={() => handleAddToCart(prod)}
                      >
                        <span className="p-sku">{prod.sku || 'SKU-AUTO'}</span>
                        <span className="p-name">{prod.name}</span>
                        <div className="p-bottom">
                          <span className="p-price">{fmtCurrency((prod as any).selling_price || 25.00)}</span>
                          <span className="p-stock">{prod.current_stock || 0} {prod.unit_of_measure}</span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Carrinho de Compras */}
              <div className="pos-cart-panel">
                <div className="cart-header">
                  <h3>Cupom de Venda</h3>
                  {cart.length > 0 && (
                    <button className="btn-clear-cart" onClick={() => setCart([])}>
                      Limpar
                    </button>
                  )}
                </div>

                <div className="cart-items-list">
                  {cart.length === 0 ? (
                    <div className="empty-cart-msg">Nenhum item adicionado ao carrinho.</div>
                  ) : (
                    cart.map((item) => (
                      <div key={item.product.id} className="cart-item">
                        <div className="item-info">
                          <div className="item-title">{item.product.name}</div>
                          <div className="item-price">{fmtCurrency(item.unit_price)} un</div>
                        </div>

                        <div className="item-qty-controls">
                          <button onClick={() => handleUpdateQty(item.product.id, item.quantity - 1)}>-</button>
                          <span>{item.quantity}</span>
                          <button onClick={() => handleUpdateQty(item.product.id, item.quantity + 1)}>+</button>
                        </div>

                        <div className="item-subtotal">
                          {fmtCurrency(item.quantity * item.unit_price)}
                        </div>

                        <button className="btn-remove-item" onClick={() => handleRemoveFromCart(item.product.id)}>
                          <Trash2 size={13} />
                        </button>
                      </div>
                    ))
                  )}
                </div>

                <div className="pos-checkout-section">
                  <div className="field-row">
                    <label>Cliente / Consumidor</label>
                    <input
                      type="text"
                      value={customerName}
                      onChange={(e) => setCustomerName(e.target.value)}
                    />
                  </div>

                  <div className="field-row">
                    <label>Forma de Pagamento</label>
                    <select
                      value={paymentMethod}
                      onChange={(e) => setPaymentMethod(e.target.value)}
                    >
                      <option value="DINHEIRO">Dinheiro (Espécie)</option>
                      <option value="PIX">PIX Instantâneo</option>
                      <option value="DEBIT_CARD">Cartão de Débito</option>
                      <option value="CREDIT_CARD">Cartão de Crédito</option>
                    </select>
                  </div>

                  <div className="field-row">
                    <label>Desconto Geral (R$)</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={generalDiscount}
                      onChange={(e) => setGeneralDiscount(e.target.value)}
                    />
                  </div>

                  <div className="total-breakdown">
                    <div className="breakdown-row">
                      <span>Subtotal:</span>
                      <span>{fmtCurrency(cartSubtotal)}</span>
                    </div>
                    {discountVal > 0 && (
                      <div className="breakdown-row">
                        <span>Desconto:</span>
                        <span>- {fmtCurrency(discountVal)}</span>
                      </div>
                    )}
                    <div className="breakdown-row final-total">
                      <span>Total a Pagar:</span>
                      <span>{fmtCurrency(cartFinalTotal)}</span>
                    </div>
                  </div>

                  <button
                    className="btn-finalize-pos"
                    onClick={handleFinalizePOSSale}
                    disabled={cart.length === 0}
                  >
                    <CheckCircle2 size={18} />
                    <span>Finalizar Venda ({fmtCurrency(cartFinalTotal)})</span>
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* ABA PEDIDOS */}
          {activeTab === 'orders' && (
            <div className="table-card">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Número do Pedido</th>
                    <th>Cliente</th>
                    <th>Data Emissão</th>
                    <th>Total dos Itens</th>
                    <th>Desconto</th>
                    <th>Total Líquido</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="empty-row">
                        Nenhum pedido de venda formalizado no período.
                      </td>
                    </tr>
                  ) : (
                    orders.map((o) => (
                      <tr key={o.id}>
                        <td><strong>{o.order_number}</strong></td>
                        <td>{o.customer_name}</td>
                        <td>{fmtDate(o.created_at)}</td>
                        <td>{fmtCurrency(o.total_amount)}</td>
                        <td>{fmtCurrency(o.discount_amount)}</td>
                        <td className="net-val">{fmtCurrency(o.net_amount)}</td>
                        <td><span className="status-badge">{o.status}</span></td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* ABA ORÇAMENTOS */}
          {activeTab === 'quotes' && (
            <div className="table-card">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Número da Proposta</th>
                    <th>Cliente</th>
                    <th>Validade</th>
                    <th>Total dos Itens</th>
                    <th>Desconto</th>
                    <th>Total Líquido</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {quotes.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="empty-row">
                        Nenhum orçamento comercial registrado.
                      </td>
                    </tr>
                  ) : (
                    quotes.map((q) => (
                      <tr key={q.id}>
                        <td><strong>{q.quote_number}</strong></td>
                        <td>{q.customer_name}</td>
                        <td>{fmtDate(q.valid_until)}</td>
                        <td>{fmtCurrency(q.total_amount)}</td>
                        <td>{fmtCurrency(q.discount_amount)}</td>
                        <td className="net-val">{fmtCurrency(q.net_amount)}</td>
                        <td><span className="status-badge">{q.status}</span></td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </main>
      </div>

      {/* Modal Abertura de Caixa */}
      {isSessionModalOpen && (
        <div className="modal-overlay">
          <div className="modal-box">
            <div className="modal-head">
              <h3>Abertura de Turno / Caixa PDV</h3>
              <button className="btn-close-modal" onClick={() => setIsSessionModalOpen(false)}>
                <X size={18} />
              </button>
            </div>
            <form onSubmit={handleOpenPOSSession}>
              <div className="modal-content-body">
                <div className="form-field">
                  <label>Identificação do Terminal / Caixa</label>
                  <input type="text" value="CAIXA-01 (Balcão Principal)" disabled />
                </div>

                <div className="form-field">
                  <label>Fundo de Troco Inicial (R$) *</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    required
                    value={openingCash}
                    onChange={(e) => setOpeningCash(e.target.value)}
                  />
                </div>
              </div>

              <div className="modal-foot">
                <button type="button" className="btn-cancel" onClick={() => setIsSessionModalOpen(false)}>
                  Cancelar
                </button>
                <button type="submit" className="btn-submit">
                  Abrir Caixa
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Sales;
