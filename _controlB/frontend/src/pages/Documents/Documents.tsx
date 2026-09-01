import React, { FormEvent, useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  AlertCircle,
  FileSearch,
  Filter,
  LoaderCircle,
  RefreshCw,
  Search,
  Waypoints
} from 'lucide-react';
import { DocumentTimeline } from '@/components/DocumentTimeline/DocumentTimeline';
import { RecordLink } from '@/components/RecordLink';
import { documentService, formatApiError } from '@/services/api';
import type { BusinessDocument, BusinessDocumentChain } from '@/types';
import './Documents.scss';

const moduleLabels: Record<string, string> = {
  CRM: 'CRM',
  SALES: 'Vendas',
  BILLING: 'Faturamento',
  FINANCE: 'Financeiro',
  INVENTORY: 'Estoque',
  PURCHASING: 'Compras',
  DOCUMENTS: 'Documents'
};

const documentLabels: Record<string, string> = {
  LEAD: 'Lead',
  OPPORTUNITY: 'Oportunidade',
  CRM_INTERACTION: 'Interação CRM',
  SALES_QUOTE: 'Cotação',
  SALES_ORDER: 'Pedido de venda',
  BILLING_REQUEST: 'Solicitação de faturamento',
  INVOICE: 'Fatura',
  FISCAL_DOCUMENT: 'Documento fiscal',
  RECEIVABLE: 'Conta a receber',
  PAYABLE: 'Conta a pagar',
  PURCHASE_REQUEST: 'Solicitação de compra',
  PURCHASE_ORDER: 'Pedido de compra',
  INVENTORY_RECEIPT: 'Recebimento de estoque',
  INVENTORY_TRANSFER: 'Transferência de estoque',
  REPLENISHMENT: 'Reposição',
  STOCK_RESERVATION: 'Reserva de estoque',
  DELIVERY: 'Entrega',
  SALES_RETURN: 'Devolução / troca',
  POS_SALE: 'Venda de PDV',
  INVENTORY_IMPORT_BATCH: 'Lote de importação',
  STOCK_MOVEMENT: 'Movimentação de estoque',
  PURCHASE_QUOTATION: 'Cotação de compra'
};

const humanize = (value: string): string => value
  .replace(/[_.-]+/g, ' ')
  .toLocaleLowerCase('pt-BR')
  .replace(/(^|\s)\S/g, letter => letter.toLocaleUpperCase('pt-BR'));

const statusTone = (status: string): 'success' | 'info' | 'warning' | 'danger' => {
  if (/(CANCEL|REJECT|LOST|FAILED)/i.test(status)) return 'danger';
  if (/(OVERDUE|EXPIRED)/i.test(status)) return 'warning';
  if (/(APPROVED|COMPLETED|DELIVERED|ISSUED|PAID|WON)/i.test(status)) return 'success';
  return /(DRAFT|PENDING|REQUESTED)/i.test(status) ? 'warning' : 'info';
};

const formatDate = (value: string): string => new Date(value).toLocaleString('pt-BR', {
  dateStyle: 'short',
  timeStyle: 'short'
});

export const Documents: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [documents, setDocuments] = useState<BusinessDocument[]>([]);
  const [selected, setSelected] = useState<BusinessDocument | null>(null);
  const [chain, setChain] = useState<BusinessDocumentChain | null>(null);
  const [searchDraft, setSearchDraft] = useState('');
  const [search, setSearch] = useState('');
  const [originModule, setOriginModule] = useState('');
  const [currentStatus, setCurrentStatus] = useState('');
  const [loading, setLoading] = useState(true);
  const [chainLoading, setChainLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chainError, setChainError] = useState<string | null>(null);

  const loadDocuments = useCallback(async (forceRefresh = false) => {
    setLoading(true);
    setError(null);
    try {
      const data = await documentService.list({
        search: search || undefined,
        origin_module: originModule || undefined,
        current_status: currentStatus || undefined,
        limit: 100
      }, forceRefresh);
      setDocuments(data);
    } catch (err) {
      setError(formatApiError(err, 'Não foi possível consultar os documentos.'));
    } finally {
      setLoading(false);
    }
  }, [currentStatus, originModule, search]);

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  const selectDocument = async (document: BusinessDocument) => {
    setSelected(document);
    setChain(null);
    setChainError(null);
    setChainLoading(true);
    try {
      setChain(await documentService.getChain(document.document_type, document.native_id, true));
    } catch (err) {
      setChainError(formatApiError(err, 'Não foi possível carregar a cadeia documental.'));
    } finally {
      setChainLoading(false);
    }
  };

  useEffect(() => {
    const documentId = searchParams.get('documentId');
    if (documentId) {
      const found = documents.find(doc => doc.id === documentId);
      if (found) {
        void selectDocument(found);
      } else if (!loading) {
        setChainError(null);
        documentService.get(documentId, true)
          .then(document => selectDocument(document))
          .catch(err => setChainError(formatApiError(err, 'Não foi possível abrir o documento informado.')));
      }
      return;
    }

    const recordType = searchParams.get('recordType') || searchParams.get('documentType');
    const recordId = searchParams.get('recordId') || searchParams.get('nativeId');
    if (!recordType || !recordId) return;

    const found = documents.find(doc =>
      (doc.document_type.toUpperCase() === recordType.toUpperCase() && doc.native_id === recordId) ||
      doc.id === recordId
    );

    if (found) {
      void selectDocument(found);
    } else if (!loading) {
      setChainLoading(true);
      documentService.getChain(recordType, recordId, true)
        .then(chainData => setChain(chainData))
        .catch(err => setChainError(formatApiError(err, 'Não foi possível carregar a cadeia documental.')))
        .finally(() => setChainLoading(false));
    }
  }, [documents, loading, searchParams]);

  const submitSearch = (event: FormEvent) => {
    event.preventDefault();
    setSearch(searchDraft.trim());
  };

  return (
    <main className="documents-page">
      <header className="ui-page-header">
        <div className="ui-page-header__info">
          <div className="ui-page-header__breadcrumb">
            <span>Módulos</span><span>/</span><span className="current">Documents</span>
          </div>
          <h1 className="ui-page-header__title">Central de Documentos</h1>
          <p>Localize registros e acompanhe a cadeia entre os módulos sem duplicar os dados operacionais.</p>
        </div>
        <div className="ui-page-header__actions">
          <button
            type="button"
            className="ui-button ui-button--secondary"
            onClick={() => void loadDocuments(true)}
            disabled={loading}
          >
            <RefreshCw size={15} className={loading ? 'is-spinning' : ''} /> Atualizar
          </button>
        </div>
      </header>

      <form className="ui-toolbar documents-page__toolbar" onSubmit={submitSearch}>
        <div className="ui-search-box">
          <Search size={15} />
          <input
            value={searchDraft}
            onChange={event => setSearchDraft(event.target.value)}
            placeholder="Buscar por número, título ou descrição"
            aria-label="Buscar documentos"
          />
        </div>
        <button type="submit" className="ui-button ui-button--primary">Buscar</button>
        <div className="ui-filter-group">
          <Filter size={14} />
          <select value={originModule} onChange={event => setOriginModule(event.target.value)} aria-label="Filtrar por módulo">
            <option value="">Todos os módulos</option>
            {Object.entries(moduleLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
          <select value={currentStatus} onChange={event => setCurrentStatus(event.target.value)} aria-label="Filtrar por status">
            <option value="">Todos os status</option>
            <option value="DRAFT">Rascunho</option>
            <option value="PENDING">Pendente</option>
            <option value="REQUESTED">Solicitado</option>
            <option value="APPROVED">Aprovado</option>
            <option value="ISSUED">Emitido</option>
            <option value="COMPLETED">Concluído</option>
            <option value="PAID">Pago</option>
            <option value="CANCELLED">Cancelado</option>
          </select>
        </div>
      </form>

      {error && <div className="documents-page__alert"><AlertCircle size={17} /> {error}</div>}

      <div className="documents-page__workspace">
        <section className="documents-page__results" aria-label="Resultados da pesquisa">
          <header>
            <div><FileSearch size={17} /><strong>Documentos encontrados</strong></div>
            <span>{documents.length}{documents.length === 100 ? '+' : ''} registro(s)</span>
          </header>

          {loading ? (
            <div className="documents-page__state"><LoaderCircle className="is-spinning" size={24} /> Consultando documentos...</div>
          ) : documents.length === 0 ? (
            <div className="documents-page__state"><FileSearch size={28} /><strong>Nenhum documento encontrado</strong><span>Ajuste os filtros ou pesquise outro termo.</span></div>
          ) : (
            <div className="documents-page__list">
              {documents.map(document => (
                <button
                  type="button"
                  key={document.id}
                  className={`documents-page__document${selected?.id === document.id ? ' is-selected' : ''}`}
                  onClick={() => void selectDocument(document)}
                >
                  <span className="documents-page__document-icon"><FileSearch size={16} /></span>
                  <span className="documents-page__document-main">
                    <span>{documentLabels[document.document_type] || humanize(document.document_type)}</span>
                    <strong>{document.title || `#${document.document_number}`}</strong>
                    <small>#{document.document_number} · {moduleLabels[document.origin_module] || humanize(document.origin_module)}</small>
                  </span>
                  <span className="documents-page__document-meta">
                    <span className={`ui-status ${statusTone(document.current_status)}`}>{humanize(document.current_status)}</span>
                    <time>{formatDate(document.issued_at || document.created_at)}</time>
                  </span>
                </button>
              ))}
            </div>
          )}
        </section>

        <aside className="documents-page__trace" aria-label="Rastreabilidade do documento selecionado">
          <header>
            <div><Waypoints size={17} /><strong>Cadeia e eventos</strong></div>
            {selected && <div className="documents-page__trace-actions">
              <span>#{selected.document_number}</span>
              <RecordLink type={selected.document_type} id={selected.native_id}>Abrir registro</RecordLink>
            </div>}
          </header>
          {!selected ? (
            <div className="documents-page__state"><Waypoints size={28} /><strong>Selecione um documento</strong><span>A rastreabilidade completa será exibida aqui.</span></div>
          ) : chainLoading ? (
            <div className="documents-page__state"><LoaderCircle className="is-spinning" size={24} /> Carregando cadeia...</div>
          ) : chainError ? (
            <div className="documents-page__alert"><AlertCircle size={17} /> {chainError}</div>
          ) : chain ? (
            <DocumentTimeline chain={chain} />
          ) : null}
        </aside>
      </div>
    </main>
  );
};

export default Documents;
