export type RecordReferenceType =
  | 'CUSTOMER'
  | 'SUPPLIER'
  | 'PRODUCT'
  | 'LEAD'
  | 'OPPORTUNITY'
  | 'CRM_INTERACTION'
  | 'SALES_QUOTE'
  | 'SALES_ORDER'
  | 'POS_SALE'
  | 'DELIVERY'
  | 'SALES_RETURN'
  | 'BILLING_REQUEST'
  | 'INVOICE'
  | 'FISCAL_DOCUMENT'
  | 'RECEIVABLE'
  | 'PAYABLE'
  | 'PURCHASE_REQUEST'
  | 'PURCHASE_QUOTATION'
  | 'PURCHASE_ORDER'
  | 'INVENTORY_RECEIPT'
  | 'INVENTORY_TRANSFER'
  | 'INVENTORY_IMPORT_BATCH'
  | 'STOCK_MOVEMENT'
  | 'REPLENISHMENT'
  | 'STOCK_RESERVATION';

export interface RecordReference {
  type: RecordReferenceType;
  id: string;
  view?: string;
}

interface RecordTarget {
  path: string;
  view: string;
}

const TARGETS: Record<RecordReferenceType, RecordTarget> = {
  CUSTOMER: { path: '/vendas', view: 'customers' },
  SUPPLIER: { path: '/compras', view: 'fornecedores' },
  PRODUCT: { path: '/estoque', view: 'produtos' },
  LEAD: { path: '/crm', view: 'leads' },
  OPPORTUNITY: { path: '/crm', view: 'pipeline' },
  CRM_INTERACTION: { path: '/crm', view: 'activities' },
  SALES_QUOTE: { path: '/vendas', view: 'quotes' },
  SALES_ORDER: { path: '/vendas', view: 'orders' },
  POS_SALE: { path: '/pdv', view: 'sales' },
  DELIVERY: { path: '/vendas', view: 'deliveries' },
  SALES_RETURN: { path: '/vendas', view: 'post_sales' },
  BILLING_REQUEST: { path: '/faturamento', view: 'requests' },
  INVOICE: { path: '/faturamento', view: 'invoices' },
  FISCAL_DOCUMENT: { path: '/financeiro', view: 'fiscal-documents' },
  RECEIVABLE: { path: '/financeiro', view: 'receivables' },
  PAYABLE: { path: '/financeiro', view: 'payables' },
  PURCHASE_REQUEST: { path: '/compras', view: 'solicitacoes' },
  PURCHASE_QUOTATION: { path: '/compras', view: 'cotacoes' },
  PURCHASE_ORDER: { path: '/compras', view: 'ordens' },
  INVENTORY_RECEIPT: { path: '/estoque', view: 'movimentacoes' },
  INVENTORY_TRANSFER: { path: '/estoque', view: 'armazenagem' },
  INVENTORY_IMPORT_BATCH: { path: '/estoque', view: 'auditoria' },
  STOCK_MOVEMENT: { path: '/estoque', view: 'movimentacoes' },
  REPLENISHMENT: { path: '/compras', view: 'sugestoes' },
  STOCK_RESERVATION: { path: '/estoque', view: 'movimentacoes' },
};

const ALIASES: Record<string, RecordReferenceType> = {
  CLIENT: 'CUSTOMER',
  CLIENTE: 'CUSTOMER',
  CUSTOMER: 'CUSTOMER',
  QUOTE: 'SALES_QUOTE',
  ORDER: 'SALES_ORDER',
  PURCHASE_QUOTE: 'PURCHASE_QUOTATION',
  CRM_ACTIVITY: 'CRM_INTERACTION',
};

export const normalizeRecordType = (value: string): RecordReferenceType | null => {
  const normalized = value.trim().toUpperCase().replace(/[.-]+/g, '_');
  if (normalized in TARGETS) return normalized as RecordReferenceType;
  return ALIASES[normalized] || null;
};

export const buildRecordHref = (type: string, id: string, view?: string): string | null => {
  const normalizedType = normalizeRecordType(type);
  if (!normalizedType || !id) return null;

  const target = TARGETS[normalizedType];
  const params = new URLSearchParams({
    view: view || target.view,
    recordType: normalizedType,
    recordId: id,
  });
  return `${target.path}?${params.toString()}`;
};

export const buildDocumentHref = (documentId: string): string => {
  const params = new URLSearchParams({ documentId });
  return `/documentos?${params.toString()}`;
};

export const parseRecordReference = (params: URLSearchParams): RecordReference | null => {
  const type = normalizeRecordType(params.get('recordType') || '');
  const id = params.get('recordId')?.trim();
  if (!type || !id) return null;
  return { type, id, view: params.get('view') || undefined };
};

export const isRequestedView = <T extends string>(
  params: URLSearchParams,
  allowed: readonly T[],
  fallback: T,
): T => {
  const requested = params.get('view') as T | null;
  return requested && allowed.includes(requested) ? requested : fallback;
};
