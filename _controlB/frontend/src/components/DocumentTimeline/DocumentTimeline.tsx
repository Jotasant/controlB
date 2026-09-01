import React from 'react';
import { AlertTriangle, CheckCircle2, ExternalLink, FileText, Link2, LoaderCircle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { buildRecordHref } from '@/components/RecordLink';
import { BusinessDocumentChain, BusinessDocumentNode } from '@/types';
import './DocumentTimeline.scss';

interface DocumentTimelineProps {
  chain: BusinessDocumentChain;
}

const labels: Record<string, string> = {
  LEAD: 'Lead',
  OPPORTUNITY: 'Oportunidade',
  SALES_QUOTE: 'Cotação',
  SALES_ORDER: 'Pedido de venda',
  POS_SALE: 'Venda de PDV',
  STOCK_RESERVATION: 'Reserva de estoque',
  PICKING: 'Separação',
  SHIPMENT: 'Expedição',
  DELIVERY: 'Entrega',
  BILLING_REQUEST: 'Solicitação de faturamento',
  INVOICE: 'Fatura',
  FISCAL_DOCUMENT: 'Documento fiscal',
  RECEIVABLE: 'Conta a receber',
  RECEIPT: 'Recebimento',
  INVENTORY_RECEIPT: 'Recebimento de estoque',
  INVENTORY_IMPORT_BATCH: 'Lote de importação',
  INVENTORY_TRANSFER: 'Transferência de estoque',
  STOCK_MOVEMENT: 'Movimentação de estoque',
  REPLENISHMENT: 'Reposição',
  PURCHASE_REQUEST: 'Solicitação de compra',
  PURCHASE_QUOTATION: 'Cotação de compra',
  PURCHASE_ORDER: 'Pedido de compra',
  PAYABLE: 'Conta a pagar',
  SALES_RETURN: 'Devolução'
};

const humanize = (value: string): string => value
  .replace(/[_-]+/g, ' ')
  .toLocaleLowerCase('pt-BR')
  .replace(/(^|\s)\S/g, letter => letter.toLocaleUpperCase('pt-BR'));

const formatDate = (value?: string | null): string => {
  if (!value) return 'Data não informada';
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? 'Data não informada'
    : date.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
};

const tone = (status: string): 'success' | 'info' | 'warning' | 'danger' => {
  if (/(CANCEL|REJECT|LOST|FAILED)/i.test(status)) return 'danger';
  if (/(OVERDUE|EXPIRED)/i.test(status)) return 'warning';
  if (/(APPROVED|CONVERTED|COMPLETED|DELIVERED|ISSUED|PAID|RESERVED|WON)/i.test(status)) return 'success';
  return /(DRAFT|PENDING)/i.test(status) ? 'warning' : 'info';
};

const byDate = (left: BusinessDocumentNode, right: BusinessDocumentNode): number =>
  new Date(left.issued_at || left.created_at).getTime() -
  new Date(right.issued_at || right.created_at).getTime();

export const DocumentTimeline: React.FC<DocumentTimelineProps> = ({ chain }) => {
  const documents = [...(chain.documents || [])].sort(byDate);

  if (documents.length === 0) {
    return (
      <div className="ui-document-timeline__empty ui-empty-state">
        <FileText size={26} />
        <strong>Nenhum documento relacionado.</strong>
        <span>A cadeia aparecerá conforme os módulos gerarem novos documentos.</span>
      </div>
    );
  }

  return (
    <section className="ui-document-timeline" aria-label="Cadeia e eventos do documento">
      <div className="ui-document-timeline__summary">
        <span><Link2 size={14} /> {documents.length} documento(s)</span>
        <span>{(chain.relations || []).length} vínculo(s)</span>
        <span>{(chain.events || []).length} evento(s)</span>
      </div>
      <ol className="ui-document-timeline__list">
        {documents.map(document => (
          <DocumentTimelineItem key={document.id} document={document} chain={chain} />
        ))}
      </ol>
    </section>
  );
};

interface DocumentTimelineItemProps {
  document: BusinessDocumentNode;
  chain: BusinessDocumentChain;
}

const DocumentTimelineItem: React.FC<DocumentTimelineItemProps> = ({ document, chain }) => {
  const navigate = useNavigate();
  const documentTone = tone(document.current_status);
  const isRoot = document.id === chain.root_document_id;
  const relations = (chain.relations || []).filter(item => item.child_document_id === document.id);
  const events = (chain.events || [])
    .filter(item => item.document_id === document.id)
    .sort((left, right) => new Date(left.created_at).getTime() - new Date(right.created_at).getTime());

  const target = buildRecordHref(document.document_type, document.native_id);
  const isNavigable = Boolean(target);

  const handleNavigate = () => {
    if (target) navigate(target);
  };

  return (
    <li className={`ui-document-timeline__item is-${documentTone}${isRoot ? ' is-root' : ''}`}>
      <span className="ui-document-timeline__marker" aria-hidden="true">
        {documentTone === 'success' ? <CheckCircle2 size={17} /> :
         documentTone === 'danger' ? <AlertTriangle size={17} /> : <FileText size={17} />}
      </span>
      <article
        className={`ui-document-timeline__card${isNavigable ? ' is-navigable' : ''}`}
        onClick={isNavigable ? handleNavigate : undefined}
        role={isNavigable ? 'button' : undefined}
        tabIndex={isNavigable ? 0 : undefined}
        onKeyDown={isNavigable ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleNavigate(); } } : undefined}
        title={isNavigable ? `Abrir ${labels[document.document_type] || humanize(document.document_type)} #${document.document_number}` : undefined}
      >
        {relations.length > 0 && (
          <span className="ui-document-timeline__relation">
            <Link2 size={12} /> {relations.map(item => humanize(item.relation_type)).join(' · ')}
          </span>
        )}
        <header>
          <div>
            <span>{labels[document.document_type] || humanize(document.document_type)}</span>
            <strong>#{document.document_number}</strong>
            {isRoot && <small>Documento consultado</small>}
            {isNavigable && <ExternalLink size={13} className="ui-document-timeline__nav-icon" />}
          </div>
          <span className={`ui-status ${documentTone}`}>{humanize(document.current_status)}</span>
        </header>
        <time dateTime={document.issued_at || document.created_at}>
          {formatDate(document.issued_at || document.created_at)}
        </time>
        {events.length > 0 && (
          <ul className="ui-document-timeline__events">
            {events.map(event => (
              <li key={event.id}>
                <LoaderCircle size={11} aria-hidden="true" />
                <div>
                  <strong>{humanize(event.event_type)}</strong>
                  {(event.previous_status || event.new_status) && (
                    <span>
                      {humanize(event.previous_status || 'início')} → {humanize(event.new_status || 'sem alteração')}
                    </span>
                  )}
                </div>
                <time dateTime={event.created_at}>{formatDate(event.created_at)}</time>
              </li>
            ))}
          </ul>
        )}
      </article>
    </li>
  );
};
