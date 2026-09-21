import React, { useState, useEffect, useMemo } from 'react';
import {
  User, Check, ChevronRight, ChevronLeft,
  Package, Truck, AlertTriangle, ShieldCheck, Plus, Trash2,
  FileText
} from 'lucide-react';
import { RecordEditorSurface } from '@/components/RecordForm/RecordEditorSurface';
import { useNavigate, useLocation } from 'react-router-dom';
import { CustomerPicker } from '@/components/CustomerPicker/CustomerPicker';
import { CustomerModal } from '@/components/CustomerModal/CustomerModal';
import { useToast } from '@/components/Toast/ToastContext';
import { salesService, inventoryService, formatApiError } from '@/services/api';
import type { SalesOrder, Product, Customer, CustomerCreditAnalysis } from '@/types';
import { formatCurrency } from '@/utils/formatters';
import './OrderModal.scss';

export interface OrderModalProps {
  page?: boolean;
  isOpen: boolean;
  onClose: () => void;
  order?: SalesOrder | null;
  onSuccess?: (order: SalesOrder) => void | Promise<void>;
}

interface FormOrderItem {
  id?: string;
  product_id: string;
  product_name: string;
  sku?: string;
  current_stock: number;
  reserved_stock: number;
  available_stock: number;
  quantity: number;
  unit_price: number;
  discount_amount: number;
  cost_price: number;
  notes?: string;
}

export const OrderModal: React.FC<OrderModalProps> = ({
  page = false,
  isOpen,
  onClose,
  order,
  onSuccess
}) => {
  const toast = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  const isEditing = Boolean(order?.id);

  // Etapa atual do Wizard (1: Cliente, 2: Itens/Estoque, 3: Condições, 4: Resumo)
  const [currentStep, setCurrentStep] = useState<number>(1);

  // Sub-modal para cadastrar novo cliente diretamente sem fechar o wizard
  const [isCustomerModalOpen, setIsCustomerModalOpen] = useState<boolean>(false);

  // Etapa 1: Cliente & Governança
  const [selectedCustomerId, setSelectedCustomerId] = useState<string | null>(null);
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [customerName, setCustomerName] = useState<string>('');
  const [customerDocument, setCustomerDocument] = useState<string>('');
  const [customerEmail, setCustomerEmail] = useState<string>('');
  const [customerPhone, setCustomerPhone] = useState<string>('');
  const [sellerName, setSellerName] = useState<string>('Vendedor Padrão');
  const [creditAnalysis, setCreditAnalysis] = useState<CustomerCreditAnalysis | null>(null);
  const [creditLoading, setCreditLoading] = useState(false);

  // Etapa 2: Itens & Estoque
  const [items, setItems] = useState<FormOrderItem[]>([]);
  const [products, setProducts] = useState<Product[]>([]);

  // Etapa 3: Condições Comerciais & Logística
  const [paymentTerms, setPaymentTerms] = useState<string>('30 DDL');
  const [freightType, setFreightType] = useState<string>('CIF');
  const [deliveryDate, setDeliveryDate] = useState<string>('');
  const [deliveryAddress, setDeliveryAddress] = useState<string>('');
  const [carrierName, setCarrierName] = useState<string>('');
  const [notes, setNotes] = useState<string>('');

  // Controle de submissão
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // Carregar produtos ao abrir
  useEffect(() => {
    if (isOpen) {
      inventoryService.getProducts().then((loaded) => {
        const active = Array.isArray(loaded) ? loaded.filter(p => p.is_active !== false) : [];
        setProducts(active);
      }).catch(() => {});
    }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen || order) return;
    salesService.getCommercialSettings().then((settings) => {
      setPaymentTerms(settings.default_payment_terms);
    }).catch(() => {
      // O backend aplica a condição padrão mesmo sem esta antecipação visual.
    });
  }, [isOpen, order]);

  // Inicializar dados do modal
  useEffect(() => {
    if (!isOpen) return;

    setCurrentStep(1);
    setModalError(null);

    if (order) {
      setSelectedCustomerId(order.customer_id || null);
      setSelectedCustomer(null);
      setCustomerName(order.customer_name || '');
      setCustomerDocument(order.customer_document || '');
      setPaymentTerms(order.payment_terms || '30 DDL');
      setNotes(order.notes || '');

      const defaultDelivery = new Date();
      defaultDelivery.setDate(defaultDelivery.getDate() + 7);
      setDeliveryDate(defaultDelivery.toISOString().split('T')[0]);

      if (order.items && order.items.length > 0) {
        setItems(order.items.map(it => {
          return {
            id: it.id,
            product_id: it.product_id,
            product_name: it.product?.name || 'Produto',
            sku: it.product?.sku || '',
            current_stock: Number(it.product?.current_stock) || 0,
            reserved_stock: 0,
            available_stock: Number(it.product?.current_stock) || 0,
            quantity: Number(it.quantity) || 1,
            unit_price: Number(it.unit_price) || 0,
            discount_amount: Number(it.discount_amount) || 0,
            cost_price: Number(it.product?.cost_price) || 0,
            notes: it.notes || ''
          };
        }));
      } else {
        setItems([]);
      }
    } else {
      setSelectedCustomerId(null);
      setSelectedCustomer(null);
      setCustomerName('');
      setCustomerDocument('');
      setCustomerEmail('');
      setCustomerPhone('');
      setSellerName('Vendedor Padrão');
      setPaymentTerms('30 DDL');
      setFreightType('CIF');
      setCarrierName('');
      setDeliveryAddress('');
      setNotes('');
      setItems([]);

      const defaultDelivery = new Date();
      defaultDelivery.setDate(defaultDelivery.getDate() + 7);
      setDeliveryDate(defaultDelivery.toISOString().split('T')[0]);
    }
  }, [isOpen, order]);

  useEffect(() => {
    if (!isOpen || !selectedCustomerId) {
      setCreditAnalysis(null);
      setCreditLoading(false);
      return;
    }

    let active = true;
    setCreditLoading(true);
    salesService.getCustomerCredit(selectedCustomerId, 0, order?.id)
      .then((analysis) => {
        if (active) setCreditAnalysis(analysis);
      })
      .catch(() => {
        if (active) setCreditAnalysis(null);
      })
      .finally(() => {
        if (active) setCreditLoading(false);
      });

    return () => { active = false; };
  }, [isOpen, selectedCustomerId, order?.id]);

  // Handlers de seleção de cliente
  const handleCustomerSelect = (cust: Customer | null) => {
    setSelectedCustomer(cust);
    if (cust) {
      setSelectedCustomerId(cust.id);
      setCustomerName(cust.trade_name || cust.name);
      setCustomerDocument(cust.document || '');
      setCustomerEmail(cust.email || '');
      setCustomerPhone(cust.phone || '');
      if (cust.address_street) {
        setDeliveryAddress(`${cust.address_street}, ${cust.address_number || 'S/N'} - ${cust.address_city || ''}/${cust.address_state || ''}`);
      }
    } else {
      setSelectedCustomerId(null);
      setCustomerName('');
      setCustomerDocument('');
      setCustomerEmail('');
      setCustomerPhone('');
      setDeliveryAddress('');
    }
  };

  useEffect(() => {
    const customerId = new URLSearchParams(location.search).get('selectedCustomer');
    if (!page || !isOpen || !customerId || order) return;
    let cancelled = false;
    void salesService.getCustomer(customerId).then(customer => { if (!cancelled) handleCustomerSelect(customer); }).catch(err => toast.error(formatApiError(err, 'Não foi possível selecionar o cliente.')));
    return () => { cancelled = true; };
  }, [page, isOpen, location.search, order, toast]);

  const handleCustomerCreated = (newCust: Customer) => {
    setIsCustomerModalOpen(false);
    handleCustomerSelect(newCust);
    toast.success(`Cliente ${newCust.name} criado e selecionado com sucesso!`);
  };

  // Cálculos de Totais e Margem
  const totals = useMemo(() => {
    let gross = 0;
    let discount = 0;
    let cost = 0;

    items.forEach(it => {
      const itemGross = it.quantity * it.unit_price;
      const itemDisc = it.discount_amount || 0;
      const itemCost = it.quantity * (it.cost_price || 0);

      gross += itemGross;
      discount += itemDisc;
      cost += itemCost;
    });

    const net = Math.max(0, gross - discount);
    const profit = net - cost;
    const marginPercent = net > 0 ? (profit / net) * 100 : 0;

    return {
      gross,
      discount,
      net,
      cost,
      profit,
      marginPercent
    };
  }, [items]);

  // Gerenciamento de Itens
  const handleAddItem = () => {
    if (products.length === 0) {
      setItems(prev => [...prev, {
        product_id: '',
        product_name: 'Produto Avulso',
        current_stock: 0,
        reserved_stock: 0,
        available_stock: 0,
        quantity: 1,
        unit_price: 50.00,
        discount_amount: 0,
        cost_price: 30.00
      }]);
      return;
    }

    const first = products[0];
    const curr = Number(first.current_stock) || 0;
    setItems(prev => [
      ...prev,
      {
        product_id: first.id,
        product_name: first.name,
        sku: first.sku,
        current_stock: curr,
        reserved_stock: 0,
        available_stock: curr,
        quantity: 1,
        unit_price: Number(first.reference_price) || 50.00,
        discount_amount: 0,
        cost_price: Number(first.cost_price) || 30.00
      }
    ]);
  };

  const handleProductChange = (index: number, productId: string) => {
    const prod = products.find(p => p.id === productId);
    if (!prod) return;

    setItems(prev => {
      const copy = [...prev];
      const curr = Number(prod.current_stock) || 0;
      copy[index] = {
        ...copy[index],
        product_id: prod.id,
        product_name: prod.name,
        sku: prod.sku,
        current_stock: curr,
        reserved_stock: 0,
        available_stock: curr,
        unit_price: Number(prod.reference_price) || copy[index].unit_price,
        cost_price: Number(prod.cost_price) || copy[index].cost_price
      };
      return copy;
    });
  };

  const handleItemFieldChange = (index: number, field: keyof FormOrderItem, val: any) => {
    setItems(prev => {
      const copy = [...prev];
      copy[index] = { ...copy[index], [field]: val };
      return copy;
    });
  };

  const handleRemoveItem = (index: number) => {
    setItems(prev => prev.filter((_, i) => i !== index));
  };

  // Validação de Avanço de Etapa
  const validateStep = (step: number): boolean => {
    setModalError(null);

    if (step === 1) {
      if (!customerName.trim()) {
        setModalError('Selecione ou informe a Razão Social / Nome do Cliente.');
        return false;
      }
      return true;
    }

    if (step === 2) {
      if (items.length === 0) {
        setModalError('Adicione pelo menos 1 produto ao pedido.');
        return false;
      }
      for (let i = 0; i < items.length; i++) {
        if (!items[i].product_id) {
          setModalError(`Selecione o produto no item #${i + 1}.`);
          return false;
        }
        if (items[i].quantity <= 0) {
          setModalError(`A quantidade do item #${i + 1} deve ser maior que zero.`);
          return false;
        }
        if (items[i].unit_price <= 0) {
          setModalError(`O preço unitário do item #${i + 1} deve ser maior que zero.`);
          return false;
        }
      }
      return true;
    }

    if (step === 3) {
      if (!paymentTerms) {
        setModalError('Selecione a condição de pagamento.');
        return false;
      }
      return true;
    }

    return true;
  };

  const handleNext = () => {
    if (validateStep(currentStep)) {
      setCurrentStep(prev => Math.min(4, prev + 1));
    }
  };

  const handlePrev = () => {
    setModalError(null);
    setCurrentStep(prev => Math.max(1, prev - 1));
  };

  // Submissão Final do Pedido
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    for (const step of [1, 2, 3]) { if (!validateStep(step)) { setCurrentStep(step); return; } }

    setIsSaving(true);
    setModalError(null);

    const payload = {
      customer_id: selectedCustomerId || undefined,
      customer_name: customerName.trim(),
      customer_document: customerDocument.trim() || undefined,
      payment_terms: paymentTerms,
      delivery_status: 'PENDING',
      notes: notes.trim() ? `${notes.trim()} | Frete: ${freightType} | Entrega: ${deliveryAddress || 'Endereço Fiscal'}` : `Frete: ${freightType} | Entrega: ${deliveryAddress || 'Endereço Fiscal'}`,
      items: items.map(it => ({
        product_id: it.product_id,
        quantity: it.quantity,
        unit_price: it.unit_price,
        discount_amount: it.discount_amount || 0,
        notes: it.notes || undefined
      }))
    };

    try {
      if (isEditing && order) {
        const updated = await salesService.updateOrderStatus(order.id, {
          customer_name: payload.customer_name,
          customer_document: payload.customer_document,
          payment_terms: payload.payment_terms,
          notes: payload.notes
        });
        toast.success(`Pedido #${updated.order_number} atualizado com sucesso!`);
        if (onSuccess) await onSuccess(updated);
      } else {
        const created = await salesService.createOrder(payload);
        if (created.credit_status === 'PENDING') {
          toast.warning(
            `Pedido #${created.order_number} emitido e enviado para liberação de crédito.`
          );
        } else {
          toast.success(`Pedido #${created.order_number} emitido com sucesso!`);
        }
        if (onSuccess) await onSuccess(created);
      }
      if (!page) onClose();
    } catch (err: unknown) {
      const msg = formatApiError(err, 'Erro ao salvar pedido de venda.');
      setModalError(msg);
      toast.error(msg);
    } finally {
      setIsSaving(false);
    }
  };

  const creditLimit = Number(creditAnalysis?.credit_limit ?? selectedCustomer?.credit_limit) || 0;
  const utilizedCredit = Number(creditAnalysis?.utilized_amount) || 0;
  const availableCredit = Math.max(creditLimit - utilizedCredit, 0);
  const projectedExposure = utilizedCredit + totals.net;
  const creditExcess = creditLimit > 0 ? Math.max(projectedExposure - creditLimit, 0) : 0;
  const isCreditExceeded = creditExcess > 0;

  return (
    <>
      <RecordEditorSurface
        page={page} saving={isSaving} resetKey={order} activeTab={String(currentStep)} onTabChange={(id) => setCurrentStep(Number(id))}
        tabs={[{ id: '1', label: 'Cliente e crédito' }, { id: '2', label: 'Itens e estoque' }, { id: '3', label: 'Condições e entrega' }, { id: '4', label: 'Resumo' }]}
        isOpen={isOpen}
        onClose={onClose}
        title={isEditing ? `Editar Pedido #${order?.order_number}` : "Novo Pedido de Venda"}
        subtitle="Dados do cliente, itens, condições comerciais e resumo do pedido."
        size="xl"
      >
        <div className="order-wizard">
          {/* STEPPER BAR */}
          <div hidden={page} className="order-wizard__stepper" role="navigation" aria-label="Etapas do Pedido">
            <div className={`step-item ${currentStep === 1 ? 'active' : ''} ${currentStep > 1 ? 'completed' : ''}`}>
              <div className="step-item__number">1</div>
              <span className="step-item__label">Cliente & Crédito</span>
            </div>
            <div className="step-divider" />

            <div className={`step-item ${currentStep === 2 ? 'active' : ''} ${currentStep > 2 ? 'completed' : ''}`}>
              <div className="step-item__number">2</div>
              <span className="step-item__label">Itens & Estoque</span>
            </div>
            <div className="step-divider" />

            <div className={`step-item ${currentStep === 3 ? 'active' : ''} ${currentStep > 3 ? 'completed' : ''}`}>
              <div className="step-item__number">3</div>
              <span className="step-item__label">Condições & Entrega</span>
            </div>
            <div className="step-divider" />

            <div className={`step-item ${currentStep === 4 ? 'active' : ''}`}>
              <div className="step-item__number">4</div>
              <span className="step-item__label">Resumo & Emissão</span>
            </div>
          </div>

          {modalError && (
            <div className="order-wizard__alert" role="alert">
              <AlertTriangle size={18} />
              <span>{modalError}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="order-wizard__body wizard-form ui-form">
            {/* ETAPA 1: CLIENTE & CRÉDITO */}
            {currentStep === 1 && (
              <div className="order-step-pane">
                <div className="order-step-pane__header">
                  <User size={18} className="text-primary" />
                  <h4>1. Identificação do Cliente & Governança de Crédito</h4>
                </div>

                <div className="order-form-grid">
                  <div className="form-group span-2">
                    <label>Buscar Cliente Cadastrado (Razão Social / Fantasia / CNPJ / CPF)</label>
                    <div className="customer-select-row">
                      <div className="flex-1">
                        <CustomerPicker
                          value={selectedCustomerId}
                          onChange={handleCustomerSelect}
                          placeholder="Digite o nome, CNPJ ou CPF do cliente..."
                        />
                      </div>
                      <button
                        type="button"
                        className="btn-new-cust ui-button ui-button--secondary"
                        onClick={() => page ? navigate('/vendas/clientes/novo', { state: { returnTo: location.pathname + location.search, selectCustomerOnReturn: true } }) : setIsCustomerModalOpen(true)}
                        title="Cadastrar Novo Cliente"
                      >
                        <Plus size={15} /> Novo Cliente
                      </button>
                    </div>
                  </div>

                  <div className="form-group">
                    <label>Nome / Razão Social *</label>
                    <input
                      type="text"
                      className="ui-input"
                      value={customerName}
                      onChange={(e) => setCustomerName(e.target.value)}
                      required
                    />
                  </div>

                  <div className="form-group">
                    <label>CNPJ / CPF</label>
                    <input
                      type="text"
                      className="ui-input"
                      value={customerDocument}
                      onChange={(e) => setCustomerDocument(e.target.value)}
                      placeholder="00.000.000/0000-00"
                    />
                  </div>

                  <div className="form-group">
                    <label>E-mail Comercial</label>
                    <input
                      type="email"
                      className="ui-input"
                      value={customerEmail}
                      onChange={(e) => setCustomerEmail(e.target.value)}
                    />
                  </div>

                  <div className="form-group">
                    <label>Telefone / WhatsApp</label>
                    <input
                      type="text"
                      className="ui-input"
                      value={customerPhone}
                      onChange={(e) => setCustomerPhone(e.target.value)}
                    />
                  </div>

                  <div className="form-group span-2">
                    <label>Vendedor Responsável</label>
                    <input
                      type="text"
                      className="ui-input"
                      value={sellerName}
                      onChange={(e) => setSellerName(e.target.value)}
                    />
                  </div>
                </div>

                {/* CARD DE GOVERNANÇA DE CRÉDITO */}
                <div className={`credit-governance-card ${isCreditExceeded ? 'is-warning' : ''}`}>
                  <div className="credit-governance-card__icon">
                    <ShieldCheck size={20} />
                  </div>
                  <div className="credit-governance-card__content">
                    <strong>Análise de Limite de Crédito</strong>
                    <div className="credit-pills">
                      <span>Limite Concedido: <strong>{formatCurrency(creditLimit)}</strong></span>
                      <span>Utilizado: <strong>{formatCurrency(utilizedCredit)}</strong></span>
                      <span>Disponível: <strong>{formatCurrency(availableCredit)}</strong></span>
                      <span>Valor deste Pedido: <strong>{formatCurrency(totals.net)}</strong></span>
                      {creditLimit > 0 && !creditLoading && (
                        <span>Saldo Projetado: <strong className={isCreditExceeded ? 'text-danger' : 'text-success'}>
                          {formatCurrency(availableCredit - totals.net)}
                        </strong></span>
                      )}
                    </div>
                    {creditLoading && (
                      <p className="credit-alert-text">Atualizando exposição de crédito...</p>
                    )}
                    {!creditLoading && selectedCustomerId && creditLimit <= 0 && (
                      <p className="credit-alert-text">
                        Nenhum limite foi configurado para este cliente; a política de crédito não será aplicada.
                      </p>
                    )}
                    {isCreditExceeded && (
                      <p className="credit-alert-text">
                        ⚠ <strong>Liberação necessária:</strong> a exposição projetada será de {formatCurrency(projectedExposure)}, excedendo o limite em {formatCurrency(creditExcess)}. O pedido será criado com execução bloqueada até a decisão.
                      </p>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* ETAPA 2: ITENS & DISPONIBILIDADE DE ESTOQUE EM TEMPO REAL */}
            {currentStep === 2 && (
              <div className="order-step-pane">
                <div className="order-step-pane__header">
                  <Package size={18} className="text-primary" />
                  <h4>2. Itens do Pedido & Disponibilidade de Estoque (Kardex)</h4>
                  <button type="button" className="btn-add-item ui-button ui-button--primary" data-record-change onClick={handleAddItem}>
                    <Plus size={15} /> Adicionar Produto
                  </button>
                </div>

                {items.length === 0 ? (
                  <div className="empty-items-box">
                    <Package size={32} />
                    <p>Nenhum produto adicionado ao pedido.</p>
                    <button type="button" className="btn-secondary ui-button ui-button--secondary" data-record-change onClick={handleAddItem}>
                      <Plus size={15} /> Adicionar Primeiro Item
                    </button>
                  </div>
                ) : (
                  <div className="order-items-table-wrapper">
                    <table className="order-items-table">
                      <thead>
                        <tr>
                          <th style={{ width: '30%' }}>Produto / SKU</th>
                          <th style={{ width: '15%' }} className="text-center">Disp. Estoque</th>
                          <th style={{ width: '12%' }} className="text-center">Qtd</th>
                          <th style={{ width: '15%' }} className="text-right">Unitário (R$)</th>
                          <th style={{ width: '12%' }} className="text-right">Desc. (R$)</th>
                          <th style={{ width: '16%' }} className="text-right">Total Líquido</th>
                          <th style={{ width: '5%' }}></th>
                        </tr>
                      </thead>
                      <tbody>
                        {items.map((it, idx) => {
                          const itemGross = it.quantity * it.unit_price;
                          const itemNet = Math.max(0, itemGross - (it.discount_amount || 0));
                          const isOutOfStock = it.quantity > it.available_stock;

                          return (
                            <tr key={idx} className={isOutOfStock ? 'row-stock-warning' : ''}>
                              <td>
                                <select
                                  value={it.product_id}
                                  onChange={(e) => handleProductChange(idx, e.target.value)}
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
                              <td className="text-center">
                                <div className="stock-badge-cell">
                                  <span className={`stock-badge ${isOutOfStock ? 'danger' : 'success'}`}>
                                    {it.available_stock} un.
                                  </span>
                                  {isOutOfStock && (
                                    <small className="stock-alert-tag">Falta {it.quantity - it.available_stock}</small>
                                  )}
                                </div>
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
                                  min="0.01"
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
                              <td className="text-right">
                                <strong>{formatCurrency(itemNet)}</strong>
                              </td>
                              <td className="text-center">
                                <button
                                  type="button"
                                  className="btn-trash-row"
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
            )}

            {/* ETAPA 3: CONDIÇÕES COMERCIAIS & LOGÍSTICA */}
            {currentStep === 3 && (
              <div className="order-step-pane">
                <div className="order-step-pane__header">
                  <Truck size={18} className="text-primary" />
                  <h4>3. Condições Comerciais, Pagamento & Logística de Entrega</h4>
                </div>

                <div className="order-form-grid">
                  <div className="form-group">
                    <label>Condição de Pagamento *</label>
                    <select
                      className="ui-input"
                      value={paymentTerms}
                      onChange={(e) => setPaymentTerms(e.target.value)}
                    >
                      <option value="À Vista">À Vista (PIX / TED)</option>
                      <option value="15 DDL">15 DDL</option>
                      <option value="28 DDL">Boleto 28 DDL</option>
                      <option value="30 DDL">30 DDL</option>
                      <option value="30/60 DDL">30/60 DDL</option>
                      <option value="30/60/90 DDL">30/60/90 DDL</option>
                      <option value="Cartão de Crédito">Cartão de Crédito</option>
                    </select>
                  </div>

                  <div className="form-group">
                    <label>Modalidade de Frete</label>
                    <select
                      className="ui-input"
                      value={freightType}
                      onChange={(e) => setFreightType(e.target.value)}
                    >
                      <option value="CIF">CIF (Frete por conta do Remetente)</option>
                      <option value="FOB">FOB (Frete por conta do Destinatário)</option>
                      <option value="RETIRA">Retira no Balcão</option>
                    </select>
                  </div>

                  <div className="form-group">
                    <label>Transportadora Indicada</label>
                    <input
                      type="text"
                      className="ui-input"
                      placeholder="Ex: Braspress / Jadlog / Frota Própria"
                      value={carrierName}
                      onChange={(e) => setCarrierName(e.target.value)}
                    />
                  </div>

                  <div className="form-group">
                    <label>Previsão de Entrega</label>
                    <input
                      type="date"
                      className="ui-input"
                      value={deliveryDate}
                      onChange={(e) => setDeliveryDate(e.target.value)}
                    />
                  </div>

                  <div className="form-group span-2">
                    <label>Endereço de Entrega (Se diferente do endereço fiscal)</label>
                    <input
                      type="text"
                      className="ui-input"
                      placeholder="Rua, Número, Bairro, Cidade - UF, CEP..."
                      value={deliveryAddress}
                      onChange={(e) => setDeliveryAddress(e.target.value)}
                    />
                  </div>

                  <div className="form-group span-2">
                    <label>Observações Comerciais & Instruções de Faturamento</label>
                    <textarea
                      rows={3}
                      className="ui-input ui-textarea"
                      placeholder="Instruções para expedição, notas fiscais, horário de recebimento..."
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                    />
                  </div>
                </div>
              </div>
            )}

            {/* ETAPA 4: RESUMO EXECUTIVO & CONFIRMAÇÃO */}
            {currentStep === 4 && (
              <div className="order-step-pane">
                <div className="order-step-pane__header">
                  <FileText size={18} className="text-primary" />
                  <h4>4. Resumo Executivo & Confirmação do Pedido</h4>
                </div>

                <div className="order-summary-grid">
                  <div className="summary-section-box">
                    <h5>Dados do Cliente & Entrega</h5>
                    <p><strong>Cliente:</strong> {customerName}</p>
                    {customerDocument && <p><strong>CNPJ/CPF:</strong> {customerDocument}</p>}
                    <p><strong>Condição:</strong> {paymentTerms} ({freightType})</p>
                    <p><strong>Previsão de Entrega:</strong> {deliveryDate || 'Imediata'}</p>
                    {deliveryAddress && <p><strong>Local de Entrega:</strong> {deliveryAddress}</p>}
                  </div>

                  <div className="summary-section-box">
                    <h5>Resumo Financeiro & Rentabilidade</h5>
                    <div className="summary-kpi-row">
                      <span>Subtotal Bruto:</span>
                      <strong>{formatCurrency(totals.gross)}</strong>
                    </div>
                    <div className="summary-kpi-row text-danger">
                      <span>Descontos:</span>
                      <strong>- {formatCurrency(totals.discount)}</strong>
                    </div>
                    <div className="summary-kpi-row total-highlight">
                      <span>Total Líquido do Pedido:</span>
                      <strong className="text-primary">{formatCurrency(totals.net)}</strong>
                    </div>
                    <div className="summary-divider" />
                    <div className="summary-kpi-row">
                      <span>Margem Bruta Estimada:</span>
                      <span className={`badge-margin ${totals.marginPercent >= 20 ? 'good' : 'warning'}`}>
                        {totals.marginPercent.toFixed(1)}% ({formatCurrency(totals.profit)})
                      </span>
                    </div>
                  </div>
                </div>

                <div className="order-items-preview-box">
                  <h5>Itens a serem Faturados & Reservados ({items.length})</h5>
                  <ul>
                    {items.map((it, idx) => (
                      <li key={idx}>
                        <span>{it.quantity}x {it.product_name}</span>
                        <strong>{formatCurrency(it.quantity * it.unit_price - (it.discount_amount || 0))}</strong>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}

            {/* NAVEGAÇÃO DO WIZARD */}
            <div className="order-wizard__footer">
              <div className="footer-left">
                {!page && currentStep > 1 && (
                  <button type="button" className="btn-wizard-prev ui-button ui-button--secondary" onClick={handlePrev} disabled={isSaving}>
                    <ChevronLeft size={16} /> Voltar
                  </button>
                )}
              </div>

              <div className="footer-right">
                <button type="button" className="btn-wizard-cancel ui-button ui-button--secondary" onClick={onClose} disabled={isSaving}>
                  Cancelar
                </button>

                {!page && currentStep < 4 ? (
                  <button type="button" className="btn-wizard-next ui-button ui-button--primary" onClick={handleNext}>
                    <span>Próximo</span> <ChevronRight size={16} />
                  </button>
                ) : (
                  <button type="submit" className="btn-wizard-submit ui-button ui-button--primary" disabled={isSaving}>
                    {isSaving ? 'Emitindo Pedido...' : (
                      <>
                        <Check size={16} />
                        <span>{isEditing ? 'Salvar Pedido' : isCreditExceeded ? 'Emitir e Solicitar Liberação' : 'Emitir Pedido de Venda'}</span>
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>
          </form>
        </div>
      </RecordEditorSurface>

      {/* Modal Embutido para Cadastrar Novo Cliente sem perder o Wizard */}
      <CustomerModal
        isOpen={isCustomerModalOpen}
        onClose={() => setIsCustomerModalOpen(false)}
        onSuccess={handleCustomerCreated}
      />
    </>
  );
};
