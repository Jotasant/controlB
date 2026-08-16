/**
 * types/index.ts - Tipos e Interfaces TypeScript do ControlB (Identity & Purchasing)
 * 
 * Espelha os schemas do backend FastAPI (Pydantic) garantindo
 * auto-complete, tipagem estrita e segurança no frontend.
 */

// ==============================================================================
// 1. IDENTITY & ACESSO (RBAC)
// ==============================================================================

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
  created_at: string;
  updated_at: string;
}

export interface UserMe extends User {
  role_name: string | null;
  permissions: string[];  // Lista de códigos: ["users:view", "dashboard:view", ...]
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

  // Rastreabilidade & Validade
  brand?: string | null;
  barcode?: string | null;
  ncm?: string | null;
  is_perishable: boolean;
  requires_batch: boolean;
  shelf_life_days?: number | null;

  // Parâmetros de Estoque
  min_stock: number;
  max_stock?: number | null;
  storage_location?: string | null;

  is_active: boolean;
  category?: ProductCategory | null;
  created_at: string;
  updated_at: string;
}


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
  purchase_request_id: string | null;
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
  received_at?: string | null;
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


