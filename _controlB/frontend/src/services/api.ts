/**
 * services/api.ts - Cliente HTTP Centralizado com Axios (Identity & Purchasing)
 * 
 * Responsabilidades:
 * 1. Interceptar todas as requisições HTTP e anexar automaticamente o Bearer Token JWT.
 * 2. Tratar respostas de erro 401 (token expirado) limpando a sessão e redirecionando para o /login.
 * 3. Exportar métodos tipados para consumo direto pelos componentes React.
 */

import axios from 'axios';
import { 
  User, UserMe, Role, Organization, Permission, TokenResponse,
  Supplier, CostCenter, ProductCategory, Product, PurchaseRequest, PurchaseOrder 
} from '@/types';

// Cria a instância do Axios
export const api = axios.create({
  baseURL: '', // Vazio para usar rotas relativas que passam pelo proxy Nginx na porta 80
  headers: {
    'Content-Type': 'application/json',
  },
});

// Chaves de armazenamento na sessão
const TOKEN_KEY = 'controlb_token';
const USER_EMAIL_KEY = 'controlb_user_email';

// 1. Interceptor de Requisição: Injeta o JWT no cabeçalho Authorization se existir
api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
}, (error) => {
  return Promise.reject(error);
});

// 2. Interceptor de Resposta: Trata erros de autenticação (401)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Se a API retornar 401 e não for a rota de login, desloga o usuário
    if (error.response && error.response.status === 401 && !error.config.url?.includes('/identity/token')) {
      authService.logout();
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

/**
 * Sanitiza e formata de maneira robusta os erros retornados pela API (FastAPI / Pydantic v2).
 * Trata strings, arrays de validação 422 [{type, loc, msg}] e objetos JSON, evitando
 * o erro 'Objects are not valid as a React child' no React.
 */
export const formatApiError = (err: any, fallback: string = 'Ocorreu um erro ao processar a operação.'): string => {
  if (!err) return fallback;
  const detail = err?.response?.data?.detail;
  if (!detail) {
    return err?.message || fallback;
  }
  if (typeof detail === 'string') {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail
      .map((item: any) => {
        if (typeof item === 'string') return item;
        const field = item.loc ? item.loc.filter((l: any) => l !== 'body').join('.') : '';
        const msg = item.msg || item.message || JSON.stringify(item);
        return field ? `${field}: ${msg}` : msg;
      })
      .join(' | ');
  }
  if (typeof detail === 'object') {
    return detail.msg || detail.message || JSON.stringify(detail);
  }
  return String(detail);
};

// 3. Funções de Autenticação e Sessão

export const authService = {
  // Realiza login no padrão OAuth2 Form Data
  async login(email: string, password: string): Promise<TokenResponse> {
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    const response = await api.post<TokenResponse>('/identity/token', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });

    if (response.data.access_token) {
      localStorage.setItem(TOKEN_KEY, response.data.access_token);
      localStorage.setItem(USER_EMAIL_KEY, email);
    }
    return response.data;
  },

  // Remove o token e dados da sessão
  logout(): void {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_EMAIL_KEY);
  },

  // Retorna o token atual ou null
  getToken(): string | null {
    return localStorage.getItem(TOKEN_KEY);
  },

  // Retorna o e-mail do usuário logado
  getUserEmail(): string {
    return localStorage.getItem(USER_EMAIL_KEY) || 'admin@controlb.com';
  },

  // Verifica se o usuário possui sessão ativa
  isAuthenticated(): boolean {
    return !!localStorage.getItem(TOKEN_KEY);
  },
};

// 4. Funções de Usuários, Organizações e Perfis (Identity)
export const identityService = {
  // --- PERFIL DO USUÁRIO LOGADO COM PERMISSÕES ---
  async getMe(): Promise<UserMe> {
    const response = await api.get<UserMe>('/identity/users/me');
    return response.data;
  },

  // --- PERMISSÕES (Catálogo) ---
  async getPermissions(): Promise<Permission[]> {
    const response = await api.get<Permission[]>('/identity/permissions');
    return response.data;
  },

  // --- USUÁRIOS ---
  async getUsers(): Promise<User[]> {
    const response = await api.get<User[]>('/identity/users');
    return response.data;
  },

  async createUser(data: { full_name: string; email: string; password: string; organization_id?: string; role_id?: string }): Promise<User> {
    const response = await api.post<User>('/identity/users', data);
    return response.data;
  },

  async updateUser(userId: string, data: { full_name?: string; email?: string; password?: string; organization_id?: string; role_id?: string; is_active?: boolean }): Promise<User> {
    const response = await api.put<User>(`/identity/users/${userId}`, data);
    return response.data;
  },

  async deleteUser(userId: string): Promise<{ message: string }> {
    const response = await api.delete<{ message: string }>(`/identity/users/${userId}`);
    return response.data;
  },

  // --- ORGANIZAÇÕES ---
  async getOrganizations(): Promise<Organization[]> {
    const response = await api.get<Organization[]>('/identity/organization');
    return response.data;
  },

  async createOrganization(name: string): Promise<Organization> {
    const response = await api.post<Organization>('/identity/organization', { name });
    return response.data;
  },

  async deleteOrganization(orgId: string): Promise<{ message: string }> {
    const response = await api.delete<{ message: string }>(`/identity/organization/${orgId}`);
    return response.data;
  },

  // --- CARGOS E PERMISSÕES ---
  async getRoles(): Promise<Role[]> {
    const response = await api.get<Role[]>('/identity/role');
    return response.data;
  },

  async createRole(name: string, description: string, organizationId: string, permissionIds: string[] = []): Promise<Role> {
    const response = await api.post<Role>('/identity/role', { 
      name, 
      description,
      organization_id: organizationId,
      permission_ids: permissionIds
    });
    return response.data;
  },

  async updateRole(roleId: string, data: { name?: string; description?: string; is_active?: boolean; permission_ids?: string[] }): Promise<Role> {
    const response = await api.put<Role>(`/identity/role/${roleId}`, data);
    return response.data;
  },

  async deleteRole(roleId: string): Promise<{ message: string }> {
    const response = await api.delete<{ message: string }>(`/identity/role/${roleId}`);
    return response.data;
  }
};

// 5. Funções de Estoque e Inventário Físico (Inventory)
export const inventoryService = {
  // --- CATEGORIAS DE PRODUTOS ---
  async getCategories(): Promise<ProductCategory[]> {
    const response = await api.get<ProductCategory[]>('/inventory/categories');
    return Array.isArray(response.data) ? response.data : [];
  },

  async createCategory(data: { name: string; code?: string; description?: string }): Promise<ProductCategory> {
    const response = await api.post<ProductCategory>('/inventory/categories', data);
    return response.data;
  },

  async updateCategory(categoryId: string, data: { name?: string; code?: string; description?: string; is_active?: boolean }): Promise<ProductCategory> {
    const response = await api.put<ProductCategory>(`/inventory/categories/${categoryId}`, data);
    return response.data;
  },

  async deleteCategory(categoryId: string): Promise<void> {
    await api.delete(`/inventory/categories/${categoryId}`);
  },

  // --- CATÁLOGO DE PRODUTOS & SALDO FÍSICO ---
  async getProducts(categoryId?: string): Promise<Product[]> {
    const params = categoryId ? { category_id: categoryId } : {};
    const response = await api.get<Product[]>('/inventory/products', { params });
    return Array.isArray(response.data) ? response.data : [];
  },

  async getProduct(productId: string): Promise<Product> {
    const response = await api.get<Product>(`/inventory/products/${productId}`);
    return response.data;
  },

  async createProduct(data: {
    sku?: string;
    name: string;
    description?: string;
    unit_of_measure?: string;
    reference_price?: number;
    category_id?: string;
    brand?: string;
    barcode?: string;
    ncm?: string;
    is_perishable?: boolean;
    requires_batch?: boolean;
    shelf_life_days?: number | null;
    current_stock?: number;
    min_stock?: number;
    max_stock?: number | null;
    storage_location?: string;
  }): Promise<Product> {
    const response = await api.post<Product>('/inventory/products', data);
    return response.data;
  },

  async updateProduct(productId: string, data: Partial<Product>): Promise<Product> {
    const response = await api.put<Product>(`/inventory/products/${productId}`, data);
    return response.data;
  },

  async deleteProduct(productId: string): Promise<void> {
    await api.delete(`/inventory/products/${productId}`);
  },

  // --- GESTÃO DE ESTOQUE & INVENTÁRIO FÍSICO ---
  async adjustInventoryStock(payload: import('@/types').StockAdjustmentPayload): Promise<import('@/types').StockMovement> {
    const response = await api.post<import('@/types').StockMovement>('/inventory/adjust', payload);
    return response.data;
  },

  async getInventoryMovements(productId?: string, limit?: number): Promise<import('@/types').StockMovement[]> {
    const params = new URLSearchParams();
    if (productId) params.append('product_id', productId);
    if (limit) params.append('limit', limit.toString());
    const response = await api.get<import('@/types').StockMovement[]>(`/inventory/movements?${params.toString()}`);
    return Array.isArray(response.data) ? response.data : [];
  }
};


// 6. Funções de Compras, Fornecedores e Ordens (Purchasing / Procure-to-Pay)
export const purchasingService = {
  // --- FORNECEDORES ---
  async getSuppliers(): Promise<Supplier[]> {
    const response = await api.get<Supplier[]>('/purchasing/suppliers');
    return Array.isArray(response.data) ? response.data : [];
  },

  async createSupplier(data: {
    name: string;
    trade_name?: string;
    cnpj_cpf: string;
    state_registration?: string;
    contact_name?: string;
    segments?: string;
    payment_terms?: string;
    min_order_amount?: number;
    anvisa_license?: string;
    notes?: string;
    email?: string;
    phone?: string;
    address?: string;
    city?: string;
    state?: string;
    zip_code?: string;
    country?: string;
  }): Promise<Supplier> {
    const response = await api.post<Supplier>('/purchasing/suppliers', {
      ...data,
      organization_id: '00000000-0000-0000-0000-000000000000'
    });
    return response.data;
  },

  async updateSupplier(supplierId: string, data: Partial<Supplier>): Promise<Supplier> {
    const response = await api.put<Supplier>(`/purchasing/suppliers/${supplierId}`, data);
    return response.data;
  },

  async deleteSupplier(supplierId: string): Promise<{ detail: string }> {
    const response = await api.delete<{ detail: string }>(`/purchasing/suppliers/${supplierId}`);
    return response.data;
  },

  // --- CENTROS DE CUSTO ---
  async getCostCenters(): Promise<CostCenter[]> {
    const response = await api.get<CostCenter[]>('/purchasing/cost-centers');
    return Array.isArray(response.data) ? response.data : [];
  },

  async createCostCenter(data: { code: string; name: string; description?: string; manager_id?: string }): Promise<CostCenter> {
    const response = await api.post<CostCenter>('/purchasing/cost-centers', {
      ...data,
      organization_id: '00000000-0000-0000-0000-000000000000'
    });
    return response.data;
  },

  async updateCostCenter(costCenterId: string, data: Partial<CostCenter>): Promise<CostCenter> {
    const response = await api.put<CostCenter>(`/purchasing/cost-centers/${costCenterId}`, data);
    return response.data;
  },

  async deleteCostCenter(costCenterId: string): Promise<{ detail: string }> {
    const response = await api.delete<{ detail: string }>(`/purchasing/cost-centers/${costCenterId}`);
    return response.data;
  },

  // --- COMPATIBILIDADE / DELEGAÇÃO DE PRODUTOS & CATEGORIAS (MÓDULO INVENTORY) ---
  getCategories: () => inventoryService.getCategories(),
  createCategory: (data: any) => inventoryService.createCategory(data),
  updateCategory: (id: string, data: any) => inventoryService.updateCategory(id, data),
  deleteCategory: (id: string) => inventoryService.deleteCategory(id),

  getProducts: (categoryId?: string) => inventoryService.getProducts(categoryId),
  getProduct: (id: string) => inventoryService.getProduct(id),
  createProduct: (data: any) => inventoryService.createProduct(data),
  updateProduct: (id: string, data: any) => inventoryService.updateProduct(id, data),
  deleteProduct: (id: string) => inventoryService.deleteProduct(id),

  adjustInventoryStock: (payload: any) => inventoryService.adjustInventoryStock(payload),
  getInventoryMovements: (productId?: string, limit?: number) => inventoryService.getInventoryMovements(productId, limit),

  // --- SOLICITAÇÕES DE COMPRA ---
  async getPurchaseRequests(): Promise<PurchaseRequest[]> {
    const response = await api.get<PurchaseRequest[]>('/purchasing/requests');
    return Array.isArray(response.data) ? response.data : [];
  },

  async createPurchaseRequest(data: {
    justification: string;
    cost_center_id?: string;
    required_date?: string;
    items: Array<{ product_id: string; quantity: number; estimated_unit_price: number; notes?: string }>;
  }): Promise<PurchaseRequest> {
    const response = await api.post<PurchaseRequest>('/purchasing/requests', data);
    return response.data;
  },

  async updatePurchaseRequest(requestId: string, data: { justification?: string; cost_center_id?: string | null; required_date?: string | null }): Promise<PurchaseRequest> {
    const response = await api.put<PurchaseRequest>(`/purchasing/requests/${requestId}`, data);
    return response.data;
  },

  async deletePurchaseRequest(requestId: string): Promise<void> {
    await api.delete(`/purchasing/requests/${requestId}`);
  },

  async purgePurchaseRequests(requestIds?: string[]): Promise<{ detail: string; deleted_count: number }> {
    const params = requestIds && requestIds.length > 0 ? { request_ids: requestIds } : {};
    const response = await api.delete<{ detail: string; deleted_count: number }>('/purchasing/requests', { params });
    return response.data;
  },


  async submitRequestForApproval(requestId: string): Promise<PurchaseRequest> {
    const response = await api.post<PurchaseRequest>(`/purchasing/requests/${requestId}/submit`);
    return response.data;
  },

  async approveOrRejectRequest(requestId: string, action: 'approved' | 'rejected', comments?: string): Promise<PurchaseRequest> {
    const response = await api.post<PurchaseRequest>(`/purchasing/requests/${requestId}/approve`, {
      action,
      comments
    });
    return response.data;
  },

  // --- ORDENS DE COMPRA (PURCHASE ORDERS) ---
  async getPurchaseOrders(status?: string): Promise<PurchaseOrder[]> {
    const params = status ? { status } : {};
    const response = await api.get<PurchaseOrder[]>('/purchasing/orders', { params });
    return Array.isArray(response.data) ? response.data : [];
  },

  async getPurchaseOrder(orderId: string): Promise<PurchaseOrder> {
    const response = await api.get<PurchaseOrder>(`/purchasing/orders/${orderId}`);
    return response.data;
  },

  async createPurchaseOrderFromRequest(
    requestId: string, 
    data: { 
      supplier_id: string; 
      cost_center_id?: string;
      payment_terms?: string; 
      freight_type?: string; 
      freight_amount?: number; 
      discount_amount?: number; 
      expected_delivery_date?: string; 
      notes?: string; 
      items: Array<{ product_id: string; quantity: number; unit_price: number }> 
    }
  ): Promise<PurchaseOrder> {
    const response = await api.post<PurchaseOrder>(`/purchasing/requests/${requestId}/generate-order`, data);
    return response.data;
  },

  async receivePurchaseOrder(orderId: string, data: { invoice_number: string; invoice_attachment?: string | null; notes?: string }): Promise<PurchaseOrder> {
    const response = await api.post<PurchaseOrder>(`/purchasing/orders/${orderId}/receive`, data);
    return response.data;
  },

  async cancelPurchaseOrder(orderId: string): Promise<PurchaseOrder> {
    const response = await api.post<PurchaseOrder>(`/purchasing/orders/${orderId}/cancel`);
    return response.data;
  },

  async deletePurchaseOrder(orderId: string): Promise<{ detail: string }> {
    const response = await api.delete<{ detail: string }>(`/purchasing/orders/${orderId}`);
    return response.data;
  },

  async purgePurchaseOrders(orderIds?: string[]): Promise<{ detail: string; deleted_count: number }> {
    const params = orderIds && orderIds.length > 0 ? { order_ids: orderIds } : {};
    const response = await api.delete<{ detail: string; deleted_count: number }>('/purchasing/orders', { params });
    return response.data;
  },

  // --- PROCESSOS DE COTAÇÃO (RFQ) E MAPA COMPARATIVO ---
  async openQuotationProcess(requestId: string, notes?: string): Promise<import('@/types').QuotationProcess> {
    const response = await api.post<import('@/types').QuotationProcess>(`/purchasing/requests/${requestId}/quotations`, {
      purchase_request_id: requestId,
      notes
    });
    return response.data;
  },

  async deleteQuotation(quotationId: string): Promise<{ detail: string }> {
    const response = await api.delete<{ detail: string }>(`/purchasing/quotations/${quotationId}`);
    return response.data;
  },

  async purgeQuotations(quotationIds?: string[]): Promise<{ detail: string; deleted_count: number }> {
    const params = quotationIds && quotationIds.length > 0 ? { quotation_ids: quotationIds } : {};
    const response = await api.delete<{ detail: string; deleted_count: number }>('/purchasing/quotations', { params });
    return response.data;
  },


  async getQuotationProcesses(status?: string): Promise<import('@/types').QuotationProcess[]> {
    const params = status ? { status } : {};
    const response = await api.get<import('@/types').QuotationProcess[]>('/purchasing/quotations', { params });
    return Array.isArray(response.data) ? response.data : [];
  },


  async getQuotationProcess(quotationId: string): Promise<import('@/types').QuotationProcess> {
    const response = await api.get<import('@/types').QuotationProcess>(`/purchasing/quotations/${quotationId}`);
    return response.data;
  },

  async addSupplierQuote(
    quotationId: string, 
    data: import('@/types').SupplierQuotePayload
  ): Promise<import('@/types').SupplierQuote> {
    const response = await api.post<import('@/types').SupplierQuote>(`/purchasing/quotations/${quotationId}/quotes`, data);
    return response.data;
  },

  async getQuotationComparison(quotationId: string): Promise<import('@/types').QuotationComparisonMatrix> {
    const response = await api.get<import('@/types').QuotationComparisonMatrix>(`/purchasing/quotations/${quotationId}/comparison`);
    return response.data;
  },

  async selectWinnerQuote(
    quotationId: string, 
    quoteId: string, 
    notes?: string
  ): Promise<PurchaseOrder> {
    const response = await api.post<PurchaseOrder>(`/purchasing/quotations/${quotationId}/select-winner/${quoteId}`, {
      notes
    });
    return response.data;
  },

  async cancelPurchaseRequest(requestId: string): Promise<PurchaseRequest> {
    const response = await api.post<PurchaseRequest>(`/purchasing/requests/${requestId}/cancel`);
    return response.data;
  },

  async cancelQuotation(quotationId: string): Promise<import('@/types').QuotationProcess> {
    const response = await api.post<import('@/types').QuotationProcess>(`/purchasing/quotations/${quotationId}/cancel`);
    return response.data;
  },

  async reopenQuotation(quotationId: string): Promise<import('@/types').QuotationProcess> {
    const response = await api.post<import('@/types').QuotationProcess>(`/purchasing/quotations/${quotationId}/reopen`);
    return response.data;
  },

  async deleteSupplierQuote(quotationId: string, quoteId: string): Promise<{ detail: string }> {
    const response = await api.delete<{ detail: string }>(`/purchasing/quotations/${quotationId}/quotes/${quoteId}`);
    return response.data;
  },

  // --- REPOSIÇÃO ÁGIL (ASSISTENTE DE COMPRAS & PO DIRETA) ---
  async getReplenishmentSuggestions(): Promise<import('@/types').PurchaseSuggestionsSummary> {
    const response = await api.get<import('@/types').PurchaseSuggestionsSummary>('/purchasing/suggestions');
    return response.data;
  },

  async createQuickReplenishmentOrder(payload: import('@/types').QuickReplenishmentOrderPayload): Promise<PurchaseOrder> {
    const response = await api.post<PurchaseOrder>('/purchasing/orders/quick-replenishment', payload);
    return response.data;
  }
};


// ==============================================================================
// 7. SERVIÇOS DE GESTÃO FINANCEIRA (FINANCE)
// ==============================================================================
export const financeService = {
  // --- DASHBOARD ---
  async getDashboard(): Promise<import('@/types').FinanceDashboardSummary> {
    const response = await api.get<import('@/types').FinanceDashboardSummary>('/finance/dashboard');
    return response.data;
  },

  // --- CATEGORIAS FINANCEIRAS ---
  async getCategories(type?: 'EXPENSE' | 'REVENUE'): Promise<import('@/types').FinancialCategory[]> {
    const params = type ? { category_type: type } : {};
    const response = await api.get<import('@/types').FinancialCategory[]>('/finance/categories', { params });
    return Array.isArray(response.data) ? response.data : [];
  },

  async createCategory(data: { name: string; code?: string; category_type?: string; description?: string }): Promise<import('@/types').FinancialCategory> {
    const response = await api.post<import('@/types').FinancialCategory>('/finance/categories', data);
    return response.data;
  },

  // --- CONTAS BANCÁRIAS ---
  async getBankAccounts(): Promise<import('@/types').BankAccount[]> {
    const response = await api.get<import('@/types').BankAccount[]>('/finance/bank-accounts');
    return Array.isArray(response.data) ? response.data : [];
  },

  async createBankAccount(data: { bank_name: string; bank_code?: string; agency?: string; account_number?: string; account_type?: string; opening_balance?: number }): Promise<import('@/types').BankAccount> {
    const response = await api.post<import('@/types').BankAccount>('/finance/bank-accounts', data);
    return response.data;
  },

  // --- DOCUMENTOS FISCAIS ---
  async getFiscalDocuments(direction?: string, documentType?: string): Promise<import('@/types').FiscalDocument[]> {
    const params: Record<string, string> = {};
    if (direction) params.direction = direction;
    if (documentType) params.document_type = documentType;
    const response = await api.get<import('@/types').FiscalDocument[]>('/finance/fiscal-documents', { params });
    return Array.isArray(response.data) ? response.data : [];
  },

  async createFiscalDocument(data: Partial<import('@/types').FiscalDocument>): Promise<import('@/types').FiscalDocument> {
    const response = await api.post<import('@/types').FiscalDocument>('/finance/fiscal-documents', data);
    return response.data;
  },

  // --- CONTAS A PAGAR (PAYABLES) ---
  async getPayables(status?: string, expenseNature?: string): Promise<import('@/types').Payable[]> {
    const params: Record<string, string> = {};
    if (status) params.status = status;
    if (expenseNature) params.expense_nature = expenseNature;
    const response = await api.get<import('@/types').Payable[]>('/finance/payables', { params });
    return Array.isArray(response.data) ? response.data : [];
  },

  async createPayable(data: {
    description: string;
    favored_name: string;
    original_amount: number;
    issue_date: string;
    due_date: string;
    expense_nature?: 'CAPEX' | 'OPEX';
    payment_method_expected?: string;
    cost_center_id?: string;
    financial_category_id?: string;
    supplier_id?: string;
    installments_count?: number;
    installment_frequency_days?: number;
    instrument?: {
      instrument_type: string;
      barcode?: string;
      digitable_line?: string;
      pix_code?: string;
    };
    notes?: string;
  }): Promise<import('@/types').Payable[]> {
    const response = await api.post<import('@/types').Payable[]>('/finance/payables', data);
    return response.data;
  },

  async registerPayment(payableId: string, data: {
    amount: number;
    payment_date: string;
    payment_method?: string;
    bank_account_id?: string;
    reference?: string;
    notes?: string;
    attachments?: { file_name: string; file_url: string; mime_type?: string }[];
  }): Promise<import('@/types').Payment> {
    const response = await api.post<import('@/types').Payment>(`/finance/payables/${payableId}/payments`, data);
    return response.data;
  },

  // --- TESOURARIA & EXTRATOS ---
  async getBankTransactions(bankAccountId?: string, status?: string): Promise<import('@/types').BankTransaction[]> {
    const params: Record<string, string> = {};
    if (bankAccountId) params.bank_account_id = bankAccountId;
    if (status) params.status = status;
    const response = await api.get<import('@/types').BankTransaction[]>('/finance/transactions', { params });
    return Array.isArray(response.data) ? response.data : [];
  },

  async createBankTransaction(data: {
    bank_account_id: string;
    transaction_date: string;
    description: string;
    amount: number;
    transaction_type: 'CREDIT' | 'DEBIT';
    document_number?: string;
  }): Promise<import('@/types').BankTransaction> {
    const response = await api.post<import('@/types').BankTransaction>('/finance/transactions', data);
    return response.data;
  },

  async reconcileTransaction(data: {
    bank_transaction_id: string;
    payment_id?: string;
    receipt_id?: string;
    notes?: string;
  }): Promise<import('@/types').Reconciliation> {
    const response = await api.post<import('@/types').Reconciliation>('/finance/reconciliations', data);
    return response.data;
  },

  // --- CONTAS A RECEBER (RECEIVABLES) ---
  async getReceivables(status?: string): Promise<import('@/types').Receivable[]> {
    const params = status ? { status } : {};
    const response = await api.get<import('@/types').Receivable[]>('/finance/receivables', { params });
    return Array.isArray(response.data) ? response.data : [];
  },

  async createReceivable(data: {
    customer_name: string;
    customer_document?: string;
    description: string;
    original_amount: number;
    issue_date: string;
    due_date: string;
    payment_method_expected?: string;
    notes?: string;
  }): Promise<import('@/types').Receivable> {
    const response = await api.post<import('@/types').Receivable>('/finance/receivables', data);
    return response.data;
  },

  async registerReceipt(receivableId: string, data: {
    amount: number;
    receipt_date: string;
    payment_method?: string;
    bank_account_id?: string;
    reference?: string;
    notes?: string;
  }): Promise<import('@/types').Receipt> {
    const response = await api.post<import('@/types').Receipt>(`/finance/receivables/${receivableId}/receipts`, data);
    return response.data;
  }
};


// ==============================================================================
// 8. SERVIÇOS DE FATURAMENTO (BILLING)
// ==============================================================================
export const billingService = {
  async getInvoices(): Promise<import('@/types').Invoice[]> {
    const response = await api.get<import('@/types').Invoice[]>('/billing/invoices');
    return Array.isArray(response.data) ? response.data : [];
  },

  async createInvoice(data: {
    sales_order_id?: string;
    customer_name: string;
    customer_document?: string;
    total_amount: number;
    tax_amount?: number;
    issue_date: string;
    due_date: string;
    installments_count?: number;
    notes?: string;
    generate_receivables_in_finance?: boolean;
  }): Promise<import('@/types').Invoice> {
    const response = await api.post<import('@/types').Invoice>('/billing/invoices', data);
    return response.data;
  },

  async getFiscalDocuments(type?: 'INBOUND' | 'OUTBOUND'): Promise<import('@/types').FiscalDocument[]> {
    const params = type ? { type } : {};
    const response = await api.get<import('@/types').FiscalDocument[]>('/finance/fiscal-documents', { params });
    return Array.isArray(response.data) ? response.data : [];
  }
};

// ==============================================================================
// 9. SERVIÇOS DE CRM & RELACIONAMENTO
// ==============================================================================
export const crmService = {
  async getLeads(status?: string): Promise<import('@/types').Lead[]> {
    const params = status ? { status } : {};
    const response = await api.get<import('@/types').Lead[]>('/crm/leads', { params });
    return Array.isArray(response.data) ? response.data : [];
  },

  async createLead(data: {
    name: string;
    company_name?: string;
    email?: string;
    phone?: string;
    source?: string;
    status?: string;
    notes?: string;
  }): Promise<import('@/types').Lead> {
    const response = await api.post<import('@/types').Lead>('/crm/leads', data);
    return response.data;
  },

  async updateLead(leadId: string, data: Partial<import('@/types').Lead>): Promise<import('@/types').Lead> {
    const response = await api.put<import('@/types').Lead>(`/crm/leads/${leadId}`, data);
    return response.data;
  },

  async getOpportunities(stage?: string): Promise<import('@/types').Opportunity[]> {
    const params = stage ? { stage } : {};
    const response = await api.get<import('@/types').Opportunity[]>('/crm/opportunities', { params });
    return Array.isArray(response.data) ? response.data : [];
  },

  async createOpportunity(data: {
    title: string;
    customer_name: string;
    estimated_amount: number;
    probability_percent?: number;
    expected_closing_date?: string;
    stage?: string;
    lead_id?: string;
  }): Promise<import('@/types').Opportunity> {
    const response = await api.post<import('@/types').Opportunity>('/crm/opportunities', data);
    return response.data;
  },

  async updateOpportunityStage(oppId: string, stage: string, loss_reason?: string): Promise<import('@/types').Opportunity> {
    const response = await api.patch<import('@/types').Opportunity>(`/crm/opportunities/${oppId}/stage`, null, {
      params: { stage, loss_reason }
    });
    return response.data;
  },

  async getInteractions(leadId?: string, oppId?: string): Promise<import('@/types').CustomerInteraction[]> {
    const params: any = {};
    if (leadId) params.lead_id = leadId;
    if (oppId) params.opportunity_id = oppId;
    const response = await api.get<import('@/types').CustomerInteraction[]>('/crm/interactions', { params });
    return Array.isArray(response.data) ? response.data : [];
  },

  async createInteraction(data: {
    lead_id?: string;
    opportunity_id?: string;
    interaction_type: string;
    summary: string;
    details?: string;
    interaction_date?: string;
  }): Promise<import('@/types').CustomerInteraction> {
    const response = await api.post<import('@/types').CustomerInteraction>('/crm/interactions', data);
    return response.data;
  }
};

// ==============================================================================
// 10. SERVIÇOS DE VENDAS & FRENTE DE CAIXA (PDV)
// ==============================================================================
export const salesService = {
  async getQuotes(): Promise<import('@/types').SalesQuote[]> {
    const response = await api.get<import('@/types').SalesQuote[]>('/sales/quotes');
    return Array.isArray(response.data) ? response.data : [];
  },

  async createQuote(data: {
    customer_name: string;
    customer_document?: string;
    customer_email?: string;
    customer_phone?: string;
    valid_until: string;
    notes?: string;
    items: {
      product_id: string;
      quantity: number;
      unit_price: number;
      discount_amount?: number;
      notes?: string;
    }[];
  }): Promise<import('@/types').SalesQuote> {
    const response = await api.post<import('@/types').SalesQuote>('/sales/quotes', data);
    return response.data;
  },

  async getOrders(): Promise<import('@/types').SalesOrder[]> {
    const response = await api.get<import('@/types').SalesOrder[]>('/sales/orders');
    return Array.isArray(response.data) ? response.data : [];
  },

  async createOrder(data: {
    customer_name: string;
    customer_document?: string;
    payment_terms?: string;
    delivery_status?: string;
    notes?: string;
    items: {
      product_id: string;
      quantity: number;
      unit_price: number;
      discount_amount?: number;
      notes?: string;
    }[];
  }): Promise<import('@/types').SalesOrder> {
    const response = await api.post<import('@/types').SalesOrder>('/sales/orders', data);
    return response.data;
  },

  async getPOSSessions(): Promise<import('@/types').POSSession[]> {
    const response = await api.get<import('@/types').POSSession[]>('/sales/pos/sessions');
    return Array.isArray(response.data) ? response.data : [];
  },

  async openPOSSession(data: {
    pos_terminal?: string;
    opening_cash?: number;
  }): Promise<import('@/types').POSSession> {
    const response = await api.post<import('@/types').POSSession>('/sales/pos/sessions', data);
    return response.data;
  },

  async getPOSSales(): Promise<import('@/types').POSSale[]> {
    const response = await api.get<import('@/types').POSSale[]>('/sales/pos/sales');
    return Array.isArray(response.data) ? response.data : [];
  },

  async processPOSSale(data: {
    pos_session_id?: string;
    customer_name?: string;
    customer_document?: string;
    discount_amount?: number;
    payment_method: string;
    items: {
      product_id: string;
      quantity: number;
      unit_price: number;
    }[];
  }): Promise<import('@/types').POSSale> {
    const response = await api.post<import('@/types').POSSale>('/sales/pos/sales', data);
    return response.data;
  }
};

