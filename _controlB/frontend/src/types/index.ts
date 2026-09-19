/**
 * types/index.ts - Tipos e Interfaces TypeScript do ControlB (Identity & Purchasing)
 * 
 * Espelha os schemas do backend FastAPI (Pydantic) garantindo
 * auto-complete, tipagem estrita e segurança no frontend.
 */

// ==============================================================================
// 1. IDENTITY & ACESSO (RBAC)
// ==============================================================================

// Cadeia documental transversal (CRM, Vendas, Estoque, Fiscal e Financeiro).
export interface BusinessDocumentNode {
  id: string;
  category: string;
  document_type: string;
  native_id: string;
  document_number: string;
  title: string;
  current_status: string;
  priority: string;
  origin_module: string;
  issued_at?: string | null;
  created_at: string;
}

export interface BusinessDocument extends BusinessDocumentNode {
  organization_id: string;
  description?: string | null;
  tags: string[];
  responsible_id?: string | null;
  payload: Record<string, unknown>;
  completed_at?: string | null;
  created_by_id?: string | null;
  updated_at: string;
}

export interface BusinessDocumentFilters {
  category?: string;
  origin_module?: string;
  current_status?: string;
  search?: string;
  responsible_id?: string;
  limit?: number;
  offset?: number;
}

export interface BusinessDocumentRelation {
  id: string;
  parent_document_id: string;
  child_document_id: string;
  relation_type: string;
  relation_metadata: Record<string, unknown>;
  created_at: string;
}

export interface BusinessDocumentEvent {
  id: string;
  document_id: string;
  event_type: string;
  previous_status?: string | null;
  new_status?: string | null;
  event_metadata: Record<string, unknown>;
  created_by_id?: string | null;
  created_at: string;
}

export interface BusinessDocumentChain {
  root_document_id: string;
  documents: BusinessDocumentNode[];
  relations: BusinessDocumentRelation[];
  events: BusinessDocumentEvent[];
}

export interface Permission {
  id: string;
  code: string;           // Ex: "users:create"
  name: string;           // Ex: "Cadastrar Usuários"
  module: string;         // Ex: "Usuários", "Dashboard"
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface User {
  id: string;
  organization_id: string;
  role_id: string | null;
  email: string;
  full_name: string;
  is_active: boolean;
  is_seller?: boolean;
  teams?: Team[];
  created_at: string;
  updated_at: string;
}

export interface UserMe extends User {
  role_name: string | null;
  permissions: string[];  // Lista de códigos: ["users:view", "dashboard:view", ...]
}

export interface TeamMemberInfo {
  id: string;
  full_name: string;
  email: string;
  is_seller?: boolean;
  is_active?: boolean;
}

export interface Team {
  id: string;
  organization_id: string;
  name: string;
  code?: string | null;
  module_category: string; // SALES e compartilhado por CRM e Vendas
  description?: string | null;
  leader_id?: string | null;
  leader_name?: string | null;
  is_active: boolean;
  members: TeamMemberInfo[];
  created_at: string;
  updated_at: string;
}

export interface SellerResponse {
  id: string;
  full_name: string;
  email: string;
  is_seller: boolean;
  sales_team_id?: string | null;
  sales_team_name?: string | null;
}

export interface Organization {
  id: string;
  name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Role {
  id: string;
  organization_id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  permissions: Permission[];
  created_at: string;
  updated_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}


// ==============================================================================
// 2. PURCHASING - CATÁLOGO E APOIO (Supplier, Product, CostCenter)
// ==============================================================================

export interface Supplier {
  id: string;
  organization_id: string;
  name: string;
  trade_name: string | null;
  cnpj_cpf: string;
  state_registration?: string | null;
  contact_name?: string | null;
  segments?: string | null;
  payment_terms?: string | null;
  min_order_amount?: number;
  anvisa_license?: string | null;
  notes?: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
  city: string | null;
  state: string | null;
  zip_code: string | null;
  country: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CostCenter {
  id: string;
  organization_id: string;
  code: string;
  name: string;
  description: string | null;
  manager_id: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProductCategory {
  id: string;
  organization_id: string;
  name: string;
  code: string | null;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Product {
  id: string;
  organization_id: string;
  category_id: string | null;
  sku: string;
  name: string;
  description: string | null;
  unit_of_measure: string;
  reference_price: number;
  cost_price?: number;
  sale_price?: number;

  // Rastreabilidade, Integrações & Validade
  external_code?: string | null;
  toolspharma_code?: string | null;
  brand?: string | null;
  barcode?: string | null;
  ncm?: string | null;
  is_perishable: boolean;
  requires_batch: boolean;
  shelf_life_days?: number | null;

  // Parâmetros de Estoque & Saldo Físico
  current_stock?: number;
  min_stock: number;
  max_stock?: number | null;
  storage_location?: string | null;

  is_active: boolean;
  category?: ProductCategory | null;
  created_at: string;
  updated_at: string;
}

export type ToolsPharmaImportItemDetail = InventoryImportItemDetail;
export type ToolsPharmaImportSummaryResponse = InventoryImportSummaryResponse;

// ==============================================================================
// 3. PURCHASING - SOLICITAÇÃO DE COMPRA & APROVAÇÃO
// ==============================================================================

export interface PurchaseRequestItem {
  id: string;
  purchase_request_id: string;
  product_id: string;
  quantity: number;
  estimated_unit_price: number;
  total_estimated_price: number;
  notes: string | null;
  product?: Product | null;
  created_at: string;
  updated_at: string;
}

export interface ApprovalEvent {
  id: string;
  purchase_request_id: string;
  approver_id: string;
  action: 'approved' | 'rejected';
  comments: string | null;
  created_at: string;
}

export interface PurchaseRequest {
  id: string;
  organization_id: string;
  document_id: string;
  replenishment_id: string | null;
  requester_id: string;
  cost_center_id: string | null;
  request_number: string;
  justification: string;
  status: 'draft' | 'pending_approval' | 'approved' | 'rejected' | 'ordered' | 'cancelled';
  total_estimated_amount: number;
  required_date: string | null;
  items: PurchaseRequestItem[];
  approval_events: ApprovalEvent[];
  created_at: string;
  updated_at: string;
}


// ==============================================================================
// 4. PURCHASING - ORDEM DE COMPRA (PurchaseOrder)
// ==============================================================================

export interface PurchaseOrderItem {
  id: string;
  purchase_order_id: string;
  product_id: string;
  quantity: number;
  unit_price: number;
  total_price: number;
  product?: Product | null;
  created_at: string;
  updated_at: string;
}

export interface PurchaseOrder {
  id: string;
  organization_id: string;
  document_id: string;
  purchase_request_id: string | null;
  replenishment_id: string | null;
  supplier_id: string;
  buyer_id: string;
  cost_center_id: string | null;
  order_number: string;
  status: 'draft' | 'issued' | 'partially_received' | 'received' | 'closed' | 'cancelled';
  payment_terms: string | null;
  freight_type: string | null;
  freight_amount: number;
  discount_amount: number;
  expected_delivery_date: string | null;
  notes: string | null;
  total_amount: number;
  invoice_number: string | null;
  invoice_attachment?: string | null;
  received_at: string | null;
  received_by_id: string | null;
  is_active: boolean;
  items: PurchaseOrderItem[];
  supplier?: Supplier | null;
  purchase_request?: PurchaseRequest | null;
  created_at: string;
  updated_at: string;
}

export interface GeneratePOFromRequestPayload {
  supplier_id: string;
  cost_center_id?: string | null;
  payment_terms?: string | null;
  freight_type?: string | null;
  freight_amount?: number;
  discount_amount?: number;
  expected_delivery_date?: string | null;
  notes?: string | null;
  items: {
    product_id: string;
    quantity: number;
    unit_price: number;
  }[];
}

export interface PurchaseOrderReceivePayload {
  invoice_number: string;
  invoice_type?: 'NFE' | 'NFSE' | 'NFCE' | 'CTE' | 'OUTRO';
  invoice_series?: string | null;
  invoice_access_key?: string | null;
  invoice_issue_date?: string | null;
  invoice_tax_amount?: number;
  invoice_attachment?: string | null;
  received_at?: string | null;
  generate_payable?: boolean;
  payable_due_date?: string | null;
  installments_count?: number;
  installment_frequency_days?: number;
  expense_nature?: 'OPEX' | 'CAPEX';
  payment_method_expected?: string | null;
  financial_category_id?: string | null;
  digitable_line?: string | null;
  barcode?: string | null;
  pix_code?: string | null;
  notes?: string | null;
}

// ==========================================
// 4. TIPAGEM DE COTAÇÃO (RFQ) E MAPA COMPARATIVO
// ==========================================

export interface SupplierQuoteItem {
  id: string;
  supplier_quote_id: string;
  product_id: string;
  quantity: number;
  unit_price: number;
  total_price: number;
  brand_offered?: string | null;
  notes?: string | null;
  product?: Product | null;
  created_at: string;
  updated_at: string;
}

export interface SupplierQuote {
  id: string;
  organization_id: string;
  quotation_process_id: string;
  supplier_id: string;
  quote_reference?: string | null;
  status: 'pending' | 'selected' | 'rejected';
  payment_terms?: string | null;
  freight_type?: string | null;
  freight_amount: number;
  discount_amount: number;
  lead_time_days?: number | null;
  valid_until?: string | null;
  total_amount: number;
  notes?: string | null;
  is_active: boolean;
  items: SupplierQuoteItem[];
  supplier?: Supplier | null;
  created_at: string;
  updated_at: string;
}

export interface QuotationProcess {
  id: string;
  organization_id: string;
  purchase_request_id: string;
  quotation_number: string;
  status: 'open' | 'analyzing' | 'completed' | 'cancelled';
  notes?: string | null;
  is_active: boolean;
  quotes: SupplierQuote[];
  purchase_request?: PurchaseRequest | null;
  created_at: string;
  updated_at: string;
}

export interface SupplierQuotePayload {
  supplier_id: string;
  quote_reference?: string | null;
  payment_terms?: string | null;
  freight_type?: string | null;
  freight_amount?: number;
  discount_amount?: number;
  lead_time_days?: number | null;
  valid_until?: string | null;
  notes?: string | null;
  items: {
    product_id: string;
    quantity: number;
    unit_price: number;
    brand_offered?: string | null;
    notes?: string | null;
  }[];
}

export interface QuotationComparisonItem {
  product_id: string;
  product_name: string;
  sku: string;
  unit_of_measure: string;
  requested_quantity: number;
  reference_unit_price: number;
  supplier_prices: Record<string, number>;
  lowest_unit_price: number | null;
  lowest_supplier_id: string | null;
}

export interface QuotationComparisonMatrix {
  quotation_id: string;
  quotation_number: string;
  purchase_request_number: string;
  status: string;
  items_comparison: QuotationComparisonItem[];
  quotes_summary: SupplierQuote[];
  best_total_quote_id: string | null;
  best_lead_time_quote_id: string | null;
}

// ==============================================================================
// 6. PURCHASING - REPOSIÇÃO ÁGIL & INVENTÁRIO (Suggestions & Stock Movements)
// ==============================================================================

export interface PurchaseSuggestionItem {
  product_id: string;
  product_name: string;
  sku: string;
  category_name?: string | null;
  brand?: string | null;
  unit_of_measure: string;
  current_stock: number;
  min_stock: number;
  max_stock?: number | null;
  suggested_quantity: number;
  reference_price: number;
  estimated_total: number;
  urgency_level: 'critical' | 'high' | 'medium';
  storage_location?: string | null;
}

export interface PurchaseSuggestionsSummary {
  total_suggestions: number;
  critical_count: number;
  estimated_total_cost: number;
  items: PurchaseSuggestionItem[];
}

export interface QuickReplenishmentOrderPayload {
  supplier_id: string;
  cost_center_id?: string | null;
  payment_terms?: string | null;
  freight_type?: string | null;
  freight_amount?: number;
  discount_amount?: number;
  expected_delivery_date?: string | null;
  notes?: string | null;
  items: {
    product_id: string;
    quantity: number;
    unit_price: number;
    notes?: string | null;
  }[];
}

export interface InventoryReplenishmentItem {
  id: string;
  organization_id: string;
  replenishment_id: string;
  product_id: string;
  current_stock: number;
  min_stock: number;
  target_stock: number;
  requested_quantity: number;
  estimated_unit_price: number;
  created_at: string;
  product?: Product | null;
}

export interface InventoryReplenishment {
  id: string;
  organization_id: string;
  document_id: string;
  replenishment_number: string;
  status: 'OPEN' | 'REQUESTED' | 'ORDERED' | 'CANCELLED';
  estimated_total_amount: number;
  created_by_id?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
  items: InventoryReplenishmentItem[];
}

export interface StockAdjustmentPayload {
  product_id: string;
  adjustment_type: 'invoice_entry' | 'manual_loss' | 'reconciliation' | 'set_balance' | 'add_stock' | 'remove_stock';
  outbound_reason?: 'loss_damage' | 'internal_consumption' | 'supplier_return' | 'inventory_adjustment' | null;
  quantity: number;
  unit_cost?: number;
  invoice_number?: string | null;
  supplier_name?: string | null;
  invoice_attachment?: string | null;
  batch_number?: string | null;
  expiry_date?: string | null;
  reason?: string | null;
  notes?: string | null;
  auditor_name?: string | null;
  fiscal_document_id?: string | null;
}


export interface StockMovement {
  id: string;
  organization_id: string;
  document_id: string;
  product_id: string;
  receipt_id?: string | null;
  delivery_id?: string | null;
  transfer_id?: string | null;
  fiscal_document_id?: string | null;
  payable_id?: string | null;
  location_id?: string | null;
  source_location_id?: string | null;
  destination_location_id?: string | null;
  product_name?: string | null;
  sku?: string | null;
  product?: Product | null;
  unit_of_measure?: string | null;
  movement_type: string;
  quantity: number;
  unit_cost: number;
  balance_after: number;
  location_balance_after?: number | null;
  reference_doc?: string | null;
  invoice_attachment?: string | null;
  notes?: string | null;
  created_at: string;
}

export interface InventoryLocation {
  id: string;
  organization_id: string;
  code: string;
  name: string;
  description?: string | null;
  is_default: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface InventoryBalance {
  id: string;
  organization_id: string;
  product_id: string;
  location_id: string;
  quantity: number;
  updated_at: string;
}

export interface InventoryTransferItem {
  id: string;
  organization_id: string;
  transfer_id: string;
  product_id: string;
  quantity: number;
  created_at: string;
  product?: Product | null;
}

export interface InventoryTransfer {
  id: string;
  organization_id: string;
  document_id: string;
  transfer_number: string;
  source_location_id: string;
  destination_location_id: string;
  status: 'COMPLETED' | 'CANCELLED';
  completed_by_id?: string | null;
  completed_at: string;
  notes?: string | null;
  created_at: string;
  updated_at: string;
  items: InventoryTransferItem[];
}

export interface InventoryTransferPayload {
  source_location_id: string;
  destination_location_id: string;
  notes?: string | null;
  items: Array<{ product_id: string; quantity: number }>;
}

export interface StockReservationItem {
  id: string;
  organization_id: string;
  reservation_id: string;
  product_id: string;
  quantity: number;
  created_at: string;
  product?: Product | null;
}

export interface StockReservation {
  id: string;
  organization_id: string;
  sales_order_id: string;
  document_id: string;
  reservation_number: string;
  status: 'RESERVED' | 'RELEASED' | 'CONSUMED';
  status_version: number;
  created_by_id?: string | null;
  released_by_id?: string | null;
  released_at?: string | null;
  consumed_by_id?: string | null;
  consumed_at?: string | null;
  created_at: string;
  updated_at: string;
  items: StockReservationItem[];
}

export interface InventoryDeliveryItem {
  id: string;
  organization_id: string;
  delivery_id: string;
  product_id: string;
  quantity: number;
  created_at: string;
  product?: Product | null;
}

export interface InventoryDelivery {
  id: string;
  organization_id: string;
  sales_order_id: string;
  reservation_id?: string | null;
  document_id: string;
  fiscal_document_id?: string | null;
  delivery_number: string;
  status: 'DISPATCHED' | 'DELIVERED' | 'CANCELLED';
  stock_posted: boolean;
  dispatched_at: string;
  delivered_at?: string | null;
  created_by_id?: string | null;
  delivered_by_id?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
  items: InventoryDeliveryItem[];
}


// ==============================================================================
// 4. GESTÃO FINANCEIRA (FINANCE) & FATURAMENTO (BILLING)
// ==============================================================================

export interface FinancialCategory {
  id: string;
  organization_id: string;
  name: string;
  code?: string | null;
  category_type: 'EXPENSE' | 'REVENUE';
  description?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface BankAccount {
  id: string;
  organization_id: string;
  bank_name: string;
  bank_code?: string | null;
  agency?: string | null;
  account_number?: string | null;
  account_type: 'CHECKING' | 'SAVINGS' | 'CASH' | 'DIGITAL_WALLET';
  opening_balance: number;
  current_balance: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface FiscalDocument {
  id: string;
  organization_id: string;
  document_id: string;
  direction: 'INBOUND' | 'OUTBOUND';
  document_type: 'NFE' | 'NFSE' | 'NFCE' | 'CTE' | 'OUTRO';
  document_number: string;
  series?: string | null;
  access_key?: string | null;
  issuer_name: string;
  issuer_cnpj_cpf?: string | null;
  recipient_name?: string | null;
  recipient_cnpj_cpf?: string | null;
  issue_date: string;
  total_amount: number;
  tax_amount: number;
  purchase_order_id?: string | null;
  sales_order_id?: string | null;
  customer_id?: string | null;
  supplier_id?: string | null;
  file_attachment?: string | null;
  notes?: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface PaymentInstrument {
  id: string;
  payable_id: string;
  instrument_type: 'BOLETO' | 'PIX' | 'BANK_TRANSFER' | 'DEBIT' | 'OTHER';
  barcode?: string | null;
  digitable_line?: string | null;
  pix_code?: string | null;
  document_number?: string | null;
  due_date?: string | null;
  amount?: number | null;
  file_attachment?: string | null;
  created_at: string;
}

export interface PaymentAttachment {
  id: string;
  payment_id: string;
  file_name: string;
  file_url: string;
  mime_type?: string | null;
  created_at: string;
}

export interface Payment {
  id: string;
  organization_id: string;
  payable_id: string;
  bank_account_id?: string | null;
  amount: number;
  discount_amount: number;
  interest_amount: number;
  payment_date: string;
  payment_method: string;
  reference?: string | null;
  notes?: string | null;
  created_at: string;
  attachments?: PaymentAttachment[];
}

export interface Payable {
  id: string;
  organization_id: string;
  document_id: string;
  payable_number: string;
  supplier_id?: string | null;
  purchase_order_id?: string | null;
  fiscal_document_id?: string | null;
  inventory_receipt_id?: string | null;
  cost_center_id?: string | null;
  financial_category_id?: string | null;
  description: string;
  favored_name: string;
  original_amount: number;
  outstanding_amount: number;
  issue_date: string;
  due_date: string;
  expense_nature: 'OPEX' | 'CAPEX' | 'FINANCIAL' | 'TAX' | 'PAYROLL' | 'TRANSFER' | 'NOT_APPLICABLE';
  obligation_type: 'GOODS_SUPPLIER' | 'SERVICE_PROVIDER' | 'TAX' | 'PAYROLL' | 'RENT_LEASE' | 'FINANCING' | 'REIMBURSEMENT' | 'INVESTMENT' | 'OTHER';
  business_origin: 'PURCHASE' | 'REPLENISHMENT' | 'INVESTMENT' | 'CONTRACT' | 'FISCAL_DOCUMENT' | 'MANUAL' | 'OTHER';
  payment_method_expected?: string | null;
  installment_number: number;
  total_installments: number;
  status: 'DRAFT' | 'PENDING_APPROVAL' | 'APPROVED' | 'SCHEDULED' | 'PARTIALLY_PAID' | 'PAID' | 'OVERDUE' | 'CANCELLED' | 'RECONCILED';
  notes?: string | null;
  created_at: string;
  updated_at: string;
  financial_category?: FinancialCategory | null;
  fiscal_document?: FiscalDocument | null;
  instruments?: PaymentInstrument[];
  payments?: Payment[];
}

export interface BankTransaction {
  id: string;
  organization_id: string;
  bank_account_id: string;
  transaction_date: string;
  description: string;
  amount: number;
  transaction_type: 'CREDIT' | 'DEBIT';
  external_id?: string | null;
  document_number?: string | null;
  balance_after?: number | null;
  fiscal_document_id?: string | null;
  payment_attachment_id?: string | null;
  receipt_url?: string | null;
  receipt_filename?: string | null;
  status: 'pending' | 'reconciled' | 'ignored';
  created_at: string;
  fiscal_document?: FiscalDocument | null;
  payment_attachment?: PaymentAttachment | null;
  reconciliation?: Reconciliation | null;
}

export interface Reconciliation {
  id: string;
  organization_id: string;
  bank_transaction_id: string;
  payment_id?: string | null;
  receipt_id?: string | null;
  reconciled_at: string;
  status: string;
  notes?: string | null;
}

export interface Receivable {
  id: string;
  organization_id: string;
  document_id: string;
  receivable_number: string;
  invoice_installment_id?: string | null;
  sales_order_id?: string | null;
  customer_id?: string | null;
  customer_name: string;
  customer_document?: string | null;
  fiscal_document_id?: string | null;
  cost_center_id?: string | null;
  financial_category_id?: string | null;
  description: string;
  original_amount: number;
  outstanding_amount: number;
  issue_date: string;
  due_date: string;
  payment_method_expected?: string | null;
  status: 'PENDING' | 'PARTIALLY_RECEIVED' | 'RECEIVED' | 'OVERDUE' | 'CANCELLED';
  notes?: string | null;
  created_at: string;
  updated_at: string;
  financial_category?: FinancialCategory | null;
  receipts?: Receipt[];
}

export interface Receipt {
  id: string;
  organization_id: string;
  receivable_id: string;
  bank_account_id?: string | null;
  amount: number;
  receipt_date: string;
  payment_method: string;
  reference?: string | null;
  notes?: string | null;
  created_at: string;
}

export interface SalesReport {
  id: string;
  organization_id: string;
  report_date: string;
  gross_sales: number;
  discounts: number;
  returns: number;
  net_sales: number;
  cash_amount: number;
  pix_amount: number;
  debit_amount: number;
  credit_amount: number;
  other_amount: number;
  source: string;
  notes?: string | null;
  created_at: string;
}

export interface FinanceDashboardSummary {
  total_available_balance: number;
  payables_today: number;
  payables_month: number;
  payables_overdue: number;
  receivables_today: number;
  receivables_month: number;
  receivables_overdue: number;
  projected_net_cashflow: number;
  capex_month: number;
  opex_month: number;
  unreconciled_transactions_count: number;
}

// ==============================================================================
// 7. CRM & GESTÃO DE RELACIONAMENTO
// ==============================================================================

export interface CRMStage {
  id: string;
  organization_id: string;
  code: string;
  name: string;
  color: string;
  order: number;
  is_won: boolean;
  is_lost: boolean;
  is_system: boolean;
  created_at: string;
  updated_at: string;
}

export interface Lead {
  id: string;
  organization_id: string;
  customer_id?: string | null;
  name: string;
  company_name?: string | null;
  email?: string | null;
  phone?: string | null;
  source: string;
  status: 'NEW' | 'CONTACTED' | 'QUALIFIED' | 'DISQUALIFIED' | 'CONVERTED';
  notes?: string | null;
  assigned_to_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface OpportunityQuoteSummary {
  id: string;
  quote_number: string;
  total_amount: number;
  net_amount: number;
  status: string;
  valid_until: string;
  created_at: string;
}

export interface Opportunity {
  id: string;
  organization_id: string;
  lead_id?: string | null;
  customer_id?: string | null;
  contact_id?: string | null;
  title: string;
  customer_name: string;
  estimated_amount: number;
  probability_percent: number;
  expected_closing_date?: string | null;
  stage: string;
  priority: 'LOW' | 'MEDIUM' | 'HIGH';
  loss_reason?: string | null;
  assigned_to_id?: string | null;
  created_at: string;
  updated_at: string;
  lead?: Lead | null;
  quotes?: OpportunityQuoteSummary[];
}

export interface CustomerInteraction {
  id: string;
  organization_id: string;
  lead_id?: string | null;
  opportunity_id?: string | null;
  interaction_type: 'CALL' | 'MEETING' | 'EMAIL' | 'WHATSAPP' | 'NOTE';
  summary: string;
  details?: string | null;
  interaction_date: string;
  status?: 'SCHEDULED' | 'COMPLETED' | 'CANCELLED' | null;
  responsible_id?: string | null;
  created_by_id?: string | null;
  updated_by_id?: string | null;
  created_at: string;
  updated_at: string;
}

// ==============================================================================
// 8. VENDAS & FRENTE DE CAIXA (PDV), CLIENTES, GESTÃO COMERCIAL E PÓS-VENDA
// ==============================================================================

export interface Contact {
  id: string;
  organization_id: string;
  person_type?: 'PJ' | 'PF';
  document?: string | null;
  name?: string;
  trade_name?: string | null;
  state_registration?: string | null;
  full_name?: string | null;
  position?: string | null;
  email?: string | null;
  phone?: string | null;
  mobile?: string | null;
  address_street?: string | null;
  address_number?: string | null;
  address_neighborhood?: string | null;
  address_city?: string | null;
  address_state?: string | null;
  address_zip_code?: string | null;
  is_customer: boolean;
  is_supplier: boolean;
  is_carrier: boolean;
  credit_limit?: number;
  origin_module?: string;
  is_active: boolean;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Customer {
  id: string;
  organization_id: string;
  contact_id?: string | null;
  person_type: 'PJ' | 'PF';
  document: string;
  name: string;
  trade_name?: string | null;
  state_registration?: string | null;
  email?: string | null;
  phone?: string | null;
  address_street?: string | null;
  address_number?: string | null;
  address_neighborhood?: string | null;
  address_city?: string | null;
  address_state?: string | null;
  address_zip_code?: string | null;
  credit_limit: number;
  origin_module?: string;
  is_active: boolean;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface SalesQuoteItem {
  id: string;
  product_id: string;
  quantity: number;
  unit_price: number;
  discount_amount: number;
  total_price: number;
  notes?: string | null;
  product?: Product | null;
}

export interface SalesQuote {
  id: string;
  organization_id: string;
  customer_id?: string | null;
  opportunity_id?: string | null;
  quote_number: string;
  customer_name: string;
  customer_document?: string | null;
  customer_email?: string | null;
  customer_phone?: string | null;
  contact_person?: string | null;
  responsible_name?: string | null;
  priority?: 'LOW' | 'MEDIUM' | 'HIGH';
  tags?: string[];
  payment_terms?: string | null;
  installment_terms?: string | null;
  delivery_deadline?: string | null;
  warranty_terms?: string | null;
  sla_support?: string | null;
  special_conditions?: string | null;
  digital_acceptance?: boolean;
  total_amount: number;
  discount_amount: number;
  tax_amount?: number;
  freight_amount?: number;
  net_amount: number;
  valid_until: string;
  status: 'DRAFT' | 'SENT' | 'APPROVED' | 'REJECTED' | 'CONVERTED' | 'EXPIRED' | 'CANCELLED';
  commercial_approval_status: ApprovalStatus | 'NOT_REQUIRED';
  commercial_approvals: CommercialApprovalSummary[];
  cancellation_reason?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
  items: SalesQuoteItem[];
}

export interface SalesOrderItem {
  id: string;
  product_id: string;
  quantity: number;
  unit_price: number;
  discount_amount: number;
  total_price: number;
  notes?: string | null;
  product?: Product | null;
}

export interface SalesOrder {
  id: string;
  organization_id: string;
  customer_id?: string | null;
  sales_quote_id?: string | null;
  opportunity_id?: string | null;
  order_number: string;
  customer_name: string;
  customer_document?: string | null;
  total_amount: number;
  discount_amount: number;
  net_amount: number;
  payment_terms?: string | null;
  delivery_status: 'PENDING' | 'RESERVED' | 'DISPATCHED' | 'DELIVERED' | 'CANCELLED';
  billing_status: 'PENDING' | 'REQUESTED' | 'PARTIALLY_INVOICED' | 'INVOICED';
  status: 'DRAFT' | 'CONFIRMED' | 'COMPLETED' | 'CANCELLED';
  credit_status: 'NOT_REQUIRED' | 'APPROVED' | 'PENDING' | 'REJECTED';
  credit_limit_snapshot: number;
  credit_exposure_snapshot: number;
  credit_excess_amount: number;
  credit_approval?: CreditApprovalSummary | null;
  commercial_approval_status: ApprovalStatus | 'NOT_REQUIRED';
  commercial_approvals: CommercialApprovalSummary[];
  cancellation_reason?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
  items: SalesOrderItem[];
}

export interface CreditApprovalSummary {
  id: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'CANCELLED';
  request_reason?: string | null;
  decision_reason?: string | null;
  credit_limit: number;
  exposure_before_order: number;
  order_amount: number;
  excess_amount: number;
  requested_by_id?: string | null;
  decided_by_id?: string | null;
  decided_at?: string | null;
  created_at: string;
  updated_at: string;
}

export type ApprovalStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'CANCELLED';
export type CommercialApprovalType = 'DISCOUNT' | 'MARGIN' | 'PAYMENT_TERM';

export interface CommercialApprovalSummary {
  id: string;
  approval_type: CommercialApprovalType;
  status: ApprovalStatus;
  metric_value: number;
  threshold_value: number;
  request_reason: string;
  decision_reason?: string | null;
  requested_by_id?: string | null;
  decided_by_id?: string | null;
  decided_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CommercialApprovalRequest extends CommercialApprovalSummary {
  organization_id: string;
  sales_quote_id?: string | null;
  sales_order_id?: string | null;
  quote?: Pick<SalesQuote, 'id' | 'quote_number' | 'customer_id' | 'customer_name' | 'net_amount' | 'commercial_approval_status'> | null;
  order?: Pick<SalesOrder, 'id' | 'order_number' | 'customer_id' | 'customer_name' | 'net_amount' | 'commercial_approval_status'> | null;
}

export interface CreditApprovalRequest extends CreditApprovalSummary {
  organization_id: string;
  sales_order_id: string;
  customer_id: string;
  order: Pick<SalesOrder, 'id' | 'order_number' | 'customer_id' | 'customer_name' | 'net_amount' | 'credit_status'>;
}

export interface CustomerCreditAnalysis {
  customer_id: string;
  customer_name: string;
  credit_limit: number;
  unbilled_orders_amount: number;
  open_receivables_amount: number;
  utilized_amount: number;
  available_amount: number;
  proposed_order_amount: number;
  projected_exposure: number;
  excess_amount: number;
  requires_approval: boolean;
}

export interface POSSaleItem {
  id: string;
  product_id: string;
  quantity: number;
  unit_price: number;
  total_price: number;
  product?: Product | null;
}

export interface POSSale {
  id: string;
  organization_id: string;
  document_id: string;
  pos_session_id?: string | null;
  customer_id?: string | null;
  customer_name: string;
  customer_document?: string | null;
  total_amount: number;
  discount_amount: number;
  net_amount: number;
  payment_method: string;
  status: string;
  created_at: string;
  items: POSSaleItem[];
}

export interface POSCashMovement {
  id: string;
  organization_id: string;
  pos_session_id: string;
  movement_type: 'SANGRIA' | 'SUPRIMENTO';
  amount: number;
  reason: string;
  created_at: string;
}

export interface POSSession {
  id: string;
  organization_id: string;
  pos_terminal: string;
  opening_cash: number;
  closing_cash?: number | null;
  status: 'OPEN' | 'CLOSED';
  opened_at: string;
  closed_at?: string | null;
  sales?: POSSale[];
  cash_movements?: POSCashMovement[];
}

export interface SalesGoal {
  id: string;
  organization_id: string;
  user_id: string;
  seller_name?: string | null;
  month: number;
  year: number;
  target_amount: number;
  commission_percent: number;
  created_at: string;
  updated_at: string;
}

export interface PriceTableItem {
  id?: string;
  price_table_id?: string;
  product_id: string;
  price: number;
  discount_percent: number;
  product?: Product | null;
}

export interface PriceTable {
  id: string;
  organization_id: string;
  name: string;
  description?: string | null;
  is_default: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  items?: PriceTableItem[];
}

export interface CommercialSettings {
  organization_id: string;
  default_payment_terms: string;
  quote_validity_days: number;
  maximum_discount_percent: number;
  default_commission_percent: number;
  automatic_discount_limit_percent: number;
  minimum_margin_percent: number;
  maximum_payment_term_days_without_approval: number;
  updated_at?: string | null;
}

export interface SalesReturnItem {
  id: string;
  sales_return_id: string;
  product_id: string;
  quantity: number;
  unit_price: number;
  total_price: number;
  condition: 'GOOD' | 'DAMAGED';
  product?: Product | null;
}

export interface SalesReturn {
  id: string;
  organization_id: string;
  document_id: string;
  sales_order_id?: string | null;
  pos_sale_id?: string | null;
  customer_id?: string | null;
  customer_name: string;
  return_type: 'DEVOLUCAO' | 'TROCA' | 'CANCELAMENTO';
  status: 'PENDING' | 'COMPLETED' | 'REJECTED';
  total_amount: number;
  reason: string;
  restock_items: boolean;
  created_at: string;
  items: SalesReturnItem[];
}

export interface TopProductMetric {
  product_id: string;
  product_name: string;
  total_quantity_sold: number;
  total_revenue: number;
}

export interface SellerPerformanceMetric {
  seller_name: string;
  total_sales_amount: number;
  sales_count: number;
  target_amount: number;
  achievement_percent: number;
}

export interface SalesAnalytics {
  total_revenue: number;
  total_orders_count: number;
  total_pos_sales_count: number;
  average_ticket: number;
  quote_conversion_rate: number;
  top_selling_products: TopProductMetric[];
  seller_performance: SellerPerformanceMetric[];
}

// ==============================================================================
// 9. FATURAMENTO (BILLING)
// ==============================================================================

export interface InvoiceInstallment {
  id: string;
  invoice_id: string;
  installment_number: number;
  total_installments: number;
  amount: number;
  due_date: string;
  status: 'PENDING' | 'PARTIALLY_RECEIVED' | 'PAID' | 'OVERDUE' | 'CANCELLED';
}

export interface InvoiceItem {
  id: string;
  invoice_id: string;
  sales_order_item_id: string;
  product_id: string;
  description: string;
  product_sku?: string | null;
  quantity: number;
  unit_price: number;
  discount_amount: number;
  total_amount: number;
}

export interface Invoice {
  id: string;
  organization_id: string;
  document_id: string;
  fiscal_document_id?: string | null;
  invoice_number: string;
  sales_order_id?: string | null;
  customer_id?: string | null;
  customer_name: string;
  customer_document?: string | null;
  total_amount: number;
  tax_amount: number;
  net_amount: number;
  issue_date: string;
  due_date: string;
  status: 'DRAFT' | 'ISSUED' | 'PARTIALLY_RECEIVED' | 'OVERDUE' | 'PAID' | 'CANCELLED';
  notes?: string | null;
  created_at: string;
  updated_at: string;
  installments: InvoiceInstallment[];
  items: InvoiceItem[];
}

// ==============================================================================
// 12. AUDITORIA DE IMPORTAÇÕES DE ESTOQUE & CAPITAL ESTAGNADO
// ==============================================================================

export interface InventoryImportItemDetail {
  id?: string | null;
  code: string;
  name: string;
  barcode?: string | null;
  sku?: string | null;
  ncm?: string | null;
  unit_of_measure: string;
  previous_stock: number;
  new_stock: number;
  delta_stock: number;
  action_type: 'created' | 'sale_detected' | 'entry_detected' | 'stagnant_unchanged' | 'zero_stock_unchanged' | string;
  previous_cost_price?: number | null;
  new_cost_price: number;
  cost_variation_amount: number | null;
  cost_variation_percent?: number | null;
  previous_sale_price?: number | null;
  new_sale_price: number;
  sale_variation_amount: number | null;
  sale_variation_percent?: number | null;
  stagnant_value: number;
  estimated_sales_revenue: number;
}

export interface InventoryImportSummaryResponse {
  batch_id?: string | null;
  batch_number?: string | null;
  total_products_read: number;
  created_products_count: number;
  updated_products_count: number;
  created_categories_count: number;
  sales_identified_count: number;
  total_sales_quantity: number;
  total_sales_estimated_revenue: number;
  entries_identified_count: number;
  total_entries_quantity: number;
  total_entries_cost: number;
  cost_increases_count: number;
  cost_decreases_count: number;
  stagnant_products_count: number;
  total_stagnant_capital: number;
  total_cost_value: number;
  total_sale_value: number;
  inventory_date?: string | null;
  message: string;
  sample_items: InventoryImportItemDetail[];
}

export interface InventoryImportBatchListItem {
  id: string;
  organization_id: string;
  document_id?: string | null;
  batch_number: string;
  filename?: string | null;
  inventory_date?: string | null;
  total_products_read: number;
  created_products_count: number;
  updated_products_count: number;
  sales_identified_count: number;
  total_sales_quantity: number;
  total_sales_estimated_revenue: number;
  entries_identified_count: number;
  total_entries_quantity: number;
  cost_increases_count: number;
  cost_decreases_count: number;
  stagnant_products_count: number;
  total_stagnant_capital: number;
  total_inventory_cost: number;
  total_inventory_sale: number;
  created_at: string;
}

export interface InventoryImportBatch extends InventoryImportBatchListItem {
  created_categories_count: number;
  total_entries_cost: number;
  imported_by_id?: string | null;
  notes?: string | null;
  items: InventoryImportItemDetail[];
}

export interface StagnantProductItem {
  product_id: string;
  code?: string | null;
  sku?: string | null;
  name: string;
  category_name?: string | null;
  current_stock: number;
  unit_of_measure: string;
  cost_price: number;
  sale_price: number;
  stagnant_capital: number;
  last_movement_date?: string | null;
  days_without_sale?: number | null;
}

export interface StagnantCategorySummary {
  category_name: string;
  products_count: number;
  total_units: number;
  total_capital: number;
}

export interface StagnantInventoryReport {
  total_stagnant_products: number;
  total_stagnant_units: number;
  total_stagnant_capital: number;
  stagnant_by_category: StagnantCategorySummary[];
  top_stagnant_products: StagnantProductItem[];
}

// ==============================================================================
// 12. PROJETOS & OPERAÇÕES
// ==============================================================================
export * from './projects';

