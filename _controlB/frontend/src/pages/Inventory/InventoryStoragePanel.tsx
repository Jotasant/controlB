import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  ArrowRightLeft,
  Boxes,
  Check,
  CheckCircle2,
  FileText,
  Loader2,
  MapPin,
  Package,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  Warehouse,
} from 'lucide-react';

import { Can } from '@/components/Can';
import { Modal } from '@/components/Modal/Modal';
import { ListPagination } from '@/components/ListPagination';
import { DocumentLink, RecordLink, useRecordDeepLink } from '@/components/RecordLink';
import { useListPagination } from '@/hooks/useListPagination';
import { formatApiError, inventoryService } from '@/services/api';
import type {
  InventoryBalance,
  InventoryLocation,
  InventoryTransfer,
  Product,
} from '@/types';
import { formatQuantity } from '@/utils/formatters';
import './InventoryStoragePanel.scss';

type StorageTab = 'balances' | 'locations' | 'transfers';
type TransferLine = { productId: string; quantity: string };

interface InventoryStoragePanelProps {
  products: Product[];
}

const emptyTransferLine = (): TransferLine => ({ productId: '', quantity: '1' });

export const InventoryStoragePanel: React.FC<InventoryStoragePanelProps> = ({ products }) => {
  const [activeTab, setActiveTab] = useState<StorageTab>('balances');
  const [locations, setLocations] = useState<InventoryLocation[]>([]);
  const [balances, setBalances] = useState<InventoryBalance[]>([]);
  const [transfers, setTransfers] = useState<InventoryTransfer[]>([]);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [locationFilter, setLocationFilter] = useState('');

  const [locationModalOpen, setLocationModalOpen] = useState(false);
  const [locationCode, setLocationCode] = useState('');
  const [locationName, setLocationName] = useState('');
  const [locationDescription, setLocationDescription] = useState('');

  const [transferModalOpen, setTransferModalOpen] = useState(false);
  const [selectedTransfer, setSelectedTransfer] = useState<InventoryTransfer | null>(null);
  const [transferStep, setTransferStep] = useState(1);
  const [sourceLocationId, setSourceLocationId] = useState('');
  const [destinationLocationId, setDestinationLocationId] = useState('');
  const [transferLines, setTransferLines] = useState<TransferLine[]>([emptyTransferLine()]);
  const [transferNotes, setTransferNotes] = useState('');
  const [modalError, setModalError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const loadStorageData = useCallback(async (forceRefresh = false) => {
    setLoading(true);
    setPageError(null);
    try {
      const [locationData, balanceData, transferData] = await Promise.all([
        inventoryService.getInventoryLocations(forceRefresh),
        inventoryService.getInventoryBalances(undefined, forceRefresh),
        inventoryService.getInventoryTransfers(forceRefresh),
      ]);
      setLocations(locationData);
      setBalances(balanceData);
      setTransfers(transferData);
    } catch (error) {
      setPageError(formatApiError(error, 'Não foi possível carregar a armazenagem física.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStorageData();
  }, [loadStorageData]);

  const productById = useMemo(
    () => new Map(products.map((product) => [product.id, product])),
    [products],
  );
  const locationById = useMemo(
    () => new Map(locations.map((location) => [location.id, location])),
    [locations],
  );
  const balancesByProduct = useMemo(() => {
    const grouped = new Map<string, InventoryBalance[]>();
    balances.forEach((balance) => {
      const current = grouped.get(balance.product_id) || [];
      current.push(balance);
      grouped.set(balance.product_id, current);
    });
    return grouped;
  }, [balances]);

  const balanceAt = (productId: string, locationId: string) =>
    Number(
      balances.find(
        (balance) => balance.product_id === productId && balance.location_id === locationId,
      )?.quantity || 0,
    );

  const filteredProducts = useMemo(() => {
    const normalized = searchTerm.trim().toLocaleLowerCase('pt-BR');
    return products.filter((product) => {
      const productBalances = balancesByProduct.get(product.id) || [];
      const matchesLocation = !locationFilter
        || productBalances.some(
          (balance) => balance.location_id === locationFilter && Number(balance.quantity) > 0,
        );
      const matchesSearch = !normalized || [product.name, product.sku, product.brand]
        .filter(Boolean)
        .some((value) => String(value).toLocaleLowerCase('pt-BR').includes(normalized));
      return matchesLocation && matchesSearch;
    });
  }, [balancesByProduct, locationFilter, products, searchTerm]);
  const balancePagination = useListPagination(filteredProducts);
  const locationPagination = useListPagination(locations);
  const transferPagination = useListPagination(transfers);

  useRecordDeepLink({
    types: 'INVENTORY_TRANSFER',
    records: transfers,
    onOpen: (transfer) => {
      setActiveTab('transfers');
      setSelectedTransfer(transfer);
    },
  });

  const totalLocalQuantity = balances.reduce(
    (total, balance) => total + Number(balance.quantity || 0),
    0,
  );
  const divergenceCount = products.filter((product) => {
    const localTotal = (balancesByProduct.get(product.id) || []).reduce(
      (total, balance) => total + Number(balance.quantity || 0),
      0,
    );
    return Math.abs(localTotal - Number(product.current_stock || 0)) > 0.0001;
  }).length;

  const openLocationModal = () => {
    setLocationCode('');
    setLocationName('');
    setLocationDescription('');
    setModalError(null);
    setLocationModalOpen(true);
  };

  const saveLocation = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!locationCode.trim() || !locationName.trim()) {
      setModalError('Informe o código e o nome da localização.');
      return;
    }
    setSaving(true);
    setModalError(null);
    try {
      const created = await inventoryService.createInventoryLocation({
        code: locationCode.trim().toUpperCase(),
        name: locationName.trim(),
        description: locationDescription.trim() || null,
      });
      setLocationModalOpen(false);
      setSuccessMessage(`Localização ${created.code} cadastrada com sucesso.`);
      await loadStorageData(true);
    } catch (error) {
      setModalError(formatApiError(error, 'Erro ao cadastrar a localização.'));
    } finally {
      setSaving(false);
    }
  };

  const openTransferModal = () => {
    const defaultLocation = locations.find((location) => location.is_default);
    setTransferStep(1);
    setSourceLocationId(defaultLocation?.id || locations[0]?.id || '');
    setDestinationLocationId('');
    setTransferLines([emptyTransferLine()]);
    setTransferNotes('');
    setModalError(null);
    setTransferModalOpen(true);
  };

  const updateTransferLine = (index: number, patch: Partial<TransferLine>) => {
    setTransferLines((current) => current.map(
      (line, lineIndex) => lineIndex === index ? { ...line, ...patch } : line,
    ));
  };

  const validateTransferStep = (step = transferStep) => {
    if (step === 1) {
      if (!sourceLocationId || !destinationLocationId) {
        return 'Selecione a localização de origem e a localização de destino.';
      }
      if (sourceLocationId === destinationLocationId) {
        return 'A origem e o destino precisam ser diferentes.';
      }
    }
    if (step === 2) {
      if (!transferLines.length || transferLines.some((line) => !line.productId)) {
        return 'Selecione um produto em todas as linhas da transferência.';
      }
      if (new Set(transferLines.map((line) => line.productId)).size !== transferLines.length) {
        return 'Cada produto deve aparecer apenas uma vez na transferência.';
      }
      for (const line of transferLines) {
        const quantity = Number(line.quantity);
        const available = balanceAt(line.productId, sourceLocationId);
        if (!Number.isFinite(quantity) || quantity <= 0) {
          return 'Informe quantidades maiores que zero.';
        }
        if (quantity > available) {
          const product = productById.get(line.productId);
          return `A quantidade de ${product?.name || 'um produto'} excede o saldo disponível na origem.`;
        }
      }
    }
    return null;
  };

  const nextTransferStep = () => {
    const validationError = validateTransferStep();
    if (validationError) {
      setModalError(validationError);
      return;
    }
    setModalError(null);
    setTransferStep((step) => Math.min(step + 1, 3));
  };

  const submitTransfer = async () => {
    const validationError = validateTransferStep(1) || validateTransferStep(2);
    if (validationError) {
      setModalError(validationError);
      return;
    }
    setSaving(true);
    setModalError(null);
    try {
      const transfer = await inventoryService.createInventoryTransfer({
        source_location_id: sourceLocationId,
        destination_location_id: destinationLocationId,
        notes: transferNotes.trim() || null,
        items: transferLines.map((line) => ({
          product_id: line.productId,
          quantity: Number(line.quantity),
        })),
      });
      setTransferModalOpen(false);
      setActiveTab('transfers');
      setSuccessMessage(`Transferência ${transfer.transfer_number} concluída e registrada em Documents.`);
      await loadStorageData(true);
    } catch (error) {
      setModalError(formatApiError(error, 'Erro ao concluir a transferência.'));
    } finally {
      setSaving(false);
    }
  };

  const sourceLocation = locationById.get(sourceLocationId);
  const destinationLocation = locationById.get(destinationLocationId);

  if (loading && !locations.length) {
    return (
      <div className="storage-state-card">
        <Loader2 size={30} className="spinning" />
        <strong>Carregando localizações e saldos...</strong>
      </div>
    );
  }

  return (
    <section className="inventory-storage-panel">
      {pageError && (
        <div className="storage-alert storage-alert--error" role="alert">
          <AlertTriangle size={17} />
          <span>{pageError}</span>
        </div>
      )}
      {successMessage && (
        <div className="storage-alert storage-alert--success" role="status">
          <CheckCircle2 size={17} />
          <span>{successMessage}</span>
          <button type="button" onClick={() => setSuccessMessage(null)}>Fechar</button>
        </div>
      )}

      <div className="storage-summary-grid">
        <article className="storage-summary-card">
          <div className="storage-summary-icon"><Warehouse size={19} /></div>
          <div><span>Localizações ativas</span><strong>{locations.length}</strong></div>
        </article>
        <article className="storage-summary-card">
          <div className="storage-summary-icon"><Boxes size={19} /></div>
          <div><span>Saldo físico distribuído</span><strong>{formatQuantity(totalLocalQuantity)}</strong></div>
        </article>
        <article className={`storage-summary-card ${divergenceCount ? 'is-warning' : 'is-ok'}`}>
          <div className="storage-summary-icon">
            {divergenceCount ? <AlertTriangle size={19} /> : <CheckCircle2 size={19} />}
          </div>
          <div><span>Conciliação dos saldos</span><strong>{divergenceCount ? `${divergenceCount} divergências` : 'Conferido'}</strong></div>
        </article>
        <article className="storage-summary-card">
          <div className="storage-summary-icon"><ArrowRightLeft size={19} /></div>
          <div><span>Transferências registradas</span><strong>{transfers.length}</strong></div>
        </article>
      </div>

      <div className="storage-card">
        <div className="storage-tabs" role="tablist" aria-label="Operações de armazenagem">
          <button type="button" className={activeTab === 'balances' ? 'active' : ''} onClick={() => setActiveTab('balances')}>
            <Boxes size={16} /> Saldos por localização
          </button>
          <button type="button" className={activeTab === 'locations' ? 'active' : ''} onClick={() => setActiveTab('locations')}>
            <MapPin size={16} /> Localizações
          </button>
          <button type="button" className={activeTab === 'transfers' ? 'active' : ''} onClick={() => setActiveTab('transfers')}>
            <ArrowRightLeft size={16} /> Transferências
          </button>
          <button type="button" className="storage-refresh" onClick={() => loadStorageData(true)} disabled={loading} title="Atualizar armazenagem">
            <RefreshCw size={15} className={loading ? 'spinning' : ''} />
          </button>
        </div>

        {activeTab === 'balances' && (
          <div className="storage-pane">
            <div className="storage-pane-header">
              <div>
                <h2>Distribuição física do estoque</h2>
                <p>O total consolidado do produto deve corresponder à soma de suas localizações.</p>
              </div>
            </div>
            <div className="storage-filters">
              <label className="storage-search">
                <Search size={15} />
                <input value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} placeholder="Buscar produto, SKU ou marca..." />
              </label>
              <select value={locationFilter} onChange={(event) => setLocationFilter(event.target.value)}>
                <option value="">Todas as localizações</option>
                {locations.map((location) => <option key={location.id} value={location.id}>{location.code} — {location.name}</option>)}
              </select>
            </div>
            <div className="storage-table-wrap">
              <table className="storage-table">
                <thead><tr><th>Produto</th><th>Total consolidado</th><th>Distribuição por localização</th><th>Conciliação</th></tr></thead>
                <tbody>
                  {balancePagination.pageItems.map((product) => {
                    const productBalances = (balancesByProduct.get(product.id) || []).filter((balance) => Number(balance.quantity) > 0);
                    const localTotal = productBalances.reduce((total, balance) => total + Number(balance.quantity), 0);
                    const isBalanced = Math.abs(localTotal - Number(product.current_stock || 0)) <= 0.0001;
                    return (
                      <tr key={product.id}>
                        <td><div className="storage-product"><Package size={16} /><div><strong>{product.name}</strong><span>{product.sku} · {product.unit_of_measure}</span></div></div></td>
                        <td><strong>{formatQuantity(Number(product.current_stock || 0))} {product.unit_of_measure}</strong></td>
                        <td><div className="location-balance-list">
                          {productBalances.length ? productBalances.map((balance) => {
                            const location = locationById.get(balance.location_id);
                            return <span key={balance.id} className="location-balance-chip"><b>{location?.code || 'LOCAL'}</b>{formatQuantity(Number(balance.quantity))} {product.unit_of_measure}</span>;
                          }) : <span className="storage-muted">Sem saldo físico</span>}
                        </div></td>
                        <td><span className={`conciliation-badge ${isBalanced ? 'ok' : 'warning'}`}>{isBalanced ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}{isBalanced ? 'Conferido' : `Diferença: ${formatQuantity(localTotal - Number(product.current_stock || 0))}`}</span></td>
                      </tr>
                    );
                  })}
                  {!filteredProducts.length && <tr><td colSpan={4} className="storage-empty">Nenhum produto atende aos filtros.</td></tr>}
                </tbody>
              </table>
              <ListPagination {...balancePagination} onPageChange={balancePagination.setPage} onPageSizeChange={balancePagination.setPageSize} />
            </div>
          </div>
        )}

        {activeTab === 'locations' && (
          <div className="storage-pane">
            <div className="storage-pane-header">
              <div><h2>Localizações físicas</h2><p>Cadastre depósitos, lojas, áreas de separação ou outras posições de saldo.</p></div>
              <Can permission="inventory:move"><button type="button" className="storage-primary-button" onClick={openLocationModal}><Plus size={16} /> Nova localização</button></Can>
            </div>
            <div className="location-card-grid">
              {locationPagination.pageItems.map((location) => {
                const locationBalances = balances.filter((balance) => balance.location_id === location.id && Number(balance.quantity) > 0);
                const locationTotal = locationBalances.reduce((total, balance) => total + Number(balance.quantity), 0);
                return (
                  <article key={location.id} className={`location-card ${location.is_default ? 'is-default' : ''}`}>
                    <div className="location-card-heading"><div className="location-card-icon"><Warehouse size={20} /></div><div><strong>{location.name}</strong><span>{location.code}</span></div>{location.is_default && <em>Principal</em>}</div>
                    <p>{location.description || 'Sem descrição operacional.'}</p>
                    <div className="location-card-metrics"><div><span>Produtos com saldo</span><strong>{locationBalances.length}</strong></div><div><span>Quantidade total</span><strong>{formatQuantity(locationTotal)}</strong></div></div>
                  </article>
                );
              })}
            </div>
            <ListPagination {...locationPagination} onPageChange={locationPagination.setPage} onPageSizeChange={locationPagination.setPageSize} />
          </div>
        )}

        {activeTab === 'transfers' && (
          <div className="storage-pane">
            <div className="storage-pane-header">
              <div><h2>Transferências internas</h2><p>Cada operação conserva o saldo total e gera rastreabilidade em Documents.</p></div>
              <Can permission="inventory:move"><button type="button" className="storage-primary-button" onClick={openTransferModal} disabled={locations.length < 2}><ArrowRightLeft size={16} /> Nova transferência</button></Can>
            </div>
            {locations.length < 2 && <div className="storage-inline-hint"><AlertTriangle size={16} /> Cadastre ao menos duas localizações para transferir estoque.</div>}
            <div className="storage-table-wrap">
              <table className="storage-table">
                <thead><tr><th>Documento</th><th>Data</th><th>Origem</th><th>Destino</th><th>Itens</th><th>Status</th></tr></thead>
                <tbody>
                  {transferPagination.pageItems.map((transfer) => (
                    <tr
                      key={transfer.id}
                      className="ui-record-row"
                      role="button"
                      tabIndex={0}
                      onClick={() => setSelectedTransfer(transfer)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault();
                          setSelectedTransfer(transfer);
                        }
                      }}
                    >
                      <td>
                        <DocumentLink documentId={transfer.document_id} showIcon={false}>
                          <span className="storage-document-ref"><FileText size={14} /> {transfer.transfer_number}</span>
                        </DocumentLink>
                      </td>
                      <td>{new Date(transfer.completed_at).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })}</td>
                      <td>{locationById.get(transfer.source_location_id)?.name || 'Local removido'}</td>
                      <td>{locationById.get(transfer.destination_location_id)?.name || 'Local removido'}</td>
                      <td><strong>{transfer.items.length}</strong> {transfer.items.length === 1 ? 'produto' : 'produtos'}</td>
                      <td><span className="conciliation-badge ok"><CheckCircle2 size={14} /> Concluída</span></td>
                    </tr>
                  ))}
                  {!transfers.length && <tr><td colSpan={6} className="storage-empty">Nenhuma transferência registrada.</td></tr>}
                </tbody>
              </table>
              <ListPagination {...transferPagination} onPageChange={transferPagination.setPage} onPageSizeChange={transferPagination.setPageSize} />
            </div>
          </div>
        )}
      </div>

      <Modal
        isOpen={Boolean(selectedTransfer)}
        onClose={() => setSelectedTransfer(null)}
        title={`Transferência ${selectedTransfer?.transfer_number || ''}`}
        subtitle="Registro concluído e imutável, com vínculo ao documento canônico e ao Kardex."
        size="lg"
      >
        {selectedTransfer && (
          <div className="wizard-form ui-form">
            <div className="form-row cols-2">
              <div className="form-group"><label>Origem</label><strong>{locationById.get(selectedTransfer.source_location_id)?.name || 'Local removido'}</strong></div>
              <div className="form-group"><label>Destino</label><strong>{locationById.get(selectedTransfer.destination_location_id)?.name || 'Local removido'}</strong></div>
            </div>
            <div className="form-section-divider"><Boxes size={15} /><span>Itens transferidos</span></div>
            <div className="storage-table-wrap">
              <table className="storage-table">
                <thead><tr><th>Produto</th><th>Quantidade</th></tr></thead>
                <tbody>
                  {selectedTransfer.items.map((item) => {
                    const product = item.product || productById.get(item.product_id);
                    return (
                      <tr key={item.id}>
                        <td><RecordLink type="PRODUCT" id={item.product_id}>{product?.sku || 'Produto'} — {product?.name || item.product_id}</RecordLink></td>
                        <td><strong>{formatQuantity(Number(item.quantity))} {product?.unit_of_measure || ''}</strong></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {selectedTransfer.notes && <div className="form-group"><label>Observações</label><p>{selectedTransfer.notes}</p></div>}
            <div className="storage-modal-footer">
              <DocumentLink documentId={selectedTransfer.document_id}>Abrir na Central de Documentos</DocumentLink>
              <button type="button" className="storage-secondary-button" onClick={() => setSelectedTransfer(null)}>Fechar</button>
            </div>
          </div>
        )}
      </Modal>

      <Modal isOpen={locationModalOpen} onClose={() => setLocationModalOpen(false)} title="Nova localização de estoque" subtitle="Cadastre uma posição física para distribuição e transferência de saldos." size="md">
        <form className="wizard-form" onSubmit={saveLocation}>
          {modalError && <div className="modal-alert-error"><AlertTriangle size={16} /> {modalError}</div>}
          <div className="form-section-divider"><MapPin size={15} /><span>Identificação da localização</span></div>
          <div className="form-row cols-2">
            <div className="form-group"><label>Código <span className="req">*</span></label><input value={locationCode} onChange={(event) => setLocationCode(event.target.value.toUpperCase())} maxLength={50} placeholder="Ex: LOJA-01" autoFocus /></div>
            <div className="form-group"><label>Nome <span className="req">*</span></label><input value={locationName} onChange={(event) => setLocationName(event.target.value)} maxLength={150} placeholder="Ex: Loja Centro" /></div>
          </div>
          <div className="form-group"><label>Descrição operacional</label><textarea value={locationDescription} onChange={(event) => setLocationDescription(event.target.value)} rows={3} placeholder="Informe a finalidade ou referência física desta localização." /></div>
          <div className="storage-modal-footer"><button type="button" className="storage-secondary-button" onClick={() => setLocationModalOpen(false)}>Cancelar</button><button type="submit" className="storage-primary-button" disabled={saving}>{saving ? <Loader2 size={16} className="spinning" /> : <Check size={16} />} Cadastrar localização</button></div>
        </form>
      </Modal>

      <Modal isOpen={transferModalOpen} onClose={() => !saving && setTransferModalOpen(false)} title="Nova transferência de estoque" subtitle="Movimente saldos entre localizações sem alterar o estoque total da organização." size="lg">
        <div className="storage-transfer-wizard">
          <div className="storage-stepper" role="navigation" aria-label="Etapas da transferência">
            {['Origem & destino', 'Itens & quantidades', 'Revisão'].map((label, index) => {
              const step = index + 1;
              return <React.Fragment key={label}><div className={`storage-step ${transferStep === step ? 'active' : ''} ${transferStep > step ? 'completed' : ''}`}><span>{transferStep > step ? <Check size={14} /> : step}</span><strong>{label}</strong></div>{step < 3 && <div className="storage-step-line" />}</React.Fragment>;
            })}
          </div>
          {modalError && <div className="storage-alert storage-alert--error"><AlertTriangle size={17} /><span>{modalError}</span></div>}

          {transferStep === 1 && <div className="storage-wizard-pane"><div className="storage-wizard-heading"><MapPin size={18} /><div><h3>Defina o trajeto físico</h3><p>A origem precisa possuir saldo disponível; o destino receberá a quantidade transferida.</p></div></div><div className="transfer-location-grid"><label><span>Localização de origem</span><select value={sourceLocationId} onChange={(event) => setSourceLocationId(event.target.value)}><option value="">Selecione a origem</option>{locations.map((location) => <option key={location.id} value={location.id}>{location.code} — {location.name}</option>)}</select></label><div className="transfer-direction"><ArrowRight size={20} /></div><label><span>Localização de destino</span><select value={destinationLocationId} onChange={(event) => setDestinationLocationId(event.target.value)}><option value="">Selecione o destino</option>{locations.filter((location) => location.id !== sourceLocationId).map((location) => <option key={location.id} value={location.id}>{location.code} — {location.name}</option>)}</select></label></div></div>}

          {transferStep === 2 && <div className="storage-wizard-pane"><div className="storage-wizard-heading"><Boxes size={18} /><div><h3>Informe os produtos e quantidades</h3><p>Os saldos apresentados pertencem exclusivamente à localização de origem.</p></div></div><div className="transfer-line-list">{transferLines.map((line, index) => { const available = line.productId ? balanceAt(line.productId, sourceLocationId) : 0; const selectedElsewhere = new Set(transferLines.filter((_, lineIndex) => lineIndex !== index).map((item) => item.productId)); return <div className="transfer-line" key={index}><div className="transfer-line-product"><label>Produto</label><select value={line.productId} onChange={(event) => updateTransferLine(index, { productId: event.target.value })}><option value="">Selecione um produto com saldo</option>{products.filter((product) => balanceAt(product.id, sourceLocationId) > 0 && !selectedElsewhere.has(product.id)).map((product) => <option key={product.id} value={product.id}>{product.sku} — {product.name}</option>)}</select></div><div className="transfer-line-quantity"><label>Quantidade</label><input type="number" min="0.0001" step="0.0001" value={line.quantity} onChange={(event) => updateTransferLine(index, { quantity: event.target.value })} /><span>Disponível: {formatQuantity(available)} {productById.get(line.productId)?.unit_of_measure || ''}</span></div><button type="button" onClick={() => setTransferLines((current) => current.filter((_, lineIndex) => lineIndex !== index))} disabled={transferLines.length === 1} title="Remover item"><Trash2 size={16} /></button></div>; })}</div><button type="button" className="storage-add-line" onClick={() => setTransferLines((current) => [...current, emptyTransferLine()])}><Plus size={15} /> Adicionar produto</button></div>}

          {transferStep === 3 && <div className="storage-wizard-pane"><div className="storage-wizard-heading"><CheckCircle2 size={18} /><div><h3>Revise antes de concluir</h3><p>A confirmação gera o documento de transferência e as duas movimentações do Kardex.</p></div></div><div className="transfer-review-route"><div><span>Origem</span><strong>{sourceLocation?.code} — {sourceLocation?.name}</strong></div><ArrowRight size={20} /><div><span>Destino</span><strong>{destinationLocation?.code} — {destinationLocation?.name}</strong></div></div><div className="transfer-review-items">{transferLines.map((line) => { const product = productById.get(line.productId); return <div key={line.productId}><span>{product?.sku} — {product?.name}</span><strong>{formatQuantity(Number(line.quantity))} {product?.unit_of_measure}</strong></div>; })}</div><label className="transfer-notes"><span>Observações operacionais</span><textarea value={transferNotes} onChange={(event) => setTransferNotes(event.target.value)} rows={3} placeholder="Ex: Reposição semanal da loja, separação autorizada pelo responsável..." /></label><div className="storage-inline-hint"><FileText size={16} /> Será criado um documento <strong>INVENTORY_TRANSFER</strong> com numeração TRF.</div></div>}

          <div className="storage-modal-footer"><button type="button" className="storage-secondary-button" onClick={() => transferStep === 1 ? setTransferModalOpen(false) : setTransferStep((step) => step - 1)} disabled={saving}>{transferStep === 1 ? 'Cancelar' : <><ArrowLeft size={15} /> Voltar</>}</button>{transferStep < 3 ? <button type="button" className="storage-primary-button" onClick={nextTransferStep}>Próximo <ArrowRight size={15} /></button> : <button type="button" className="storage-primary-button" onClick={submitTransfer} disabled={saving}>{saving ? <Loader2 size={16} className="spinning" /> : <Check size={16} />} Confirmar transferência</button>}</div>
        </div>
      </Modal>
    </section>
  );
};
