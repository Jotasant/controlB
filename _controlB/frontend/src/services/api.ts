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

// 5. Funções de Compras, Fornecedores, Produtos e Ordens (Purchasing)
export const purchasingService = {
  // --- FORNECEDORES ---
  async getSuppliers(): Promise<Supplier[]> {
    const response = await api.get<Supplier[]>('/purchasing/suppliers');
    return response.data;
  },

  async createSupplier(data: {
    name: string;
    trade_name?: string;
    cnpj_cpf: string;
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
    return response.data;
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

  // --- CATEGORIAS & PRODUTOS ---
  async getCategories(): Promise<ProductCategory[]> {
    const response = await api.get<ProductCategory[]>('/purchasing/categories');
    return response.data;
  },

  async createCategory(data: { name: string; code?: string; description?: string }): Promise<ProductCategory> {
    const response = await api.post<ProductCategory>('/purchasing/categories', {
      ...data,
      organization_id: '00000000-0000-0000-0000-000000000000'
    });
    return response.data;
  },

  async getProducts(): Promise<Product[]> {
    const response = await api.get<Product[]>('/purchasing/products');
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
    min_stock?: number;
    max_stock?: number | null;
    storage_location?: string;
  }): Promise<Product> {
    const response = await api.post<Product>('/purchasing/products', {
      ...data,
      organization_id: '00000000-0000-0000-0000-000000000000'
    });
    return response.data;
  },

  async updateProduct(productId: string, data: Partial<Product>): Promise<Product> {
    const response = await api.put<Product>(`/purchasing/products/${productId}`, data);
    return response.data;
  },

  async deleteProduct(productId: string): Promise<{ detail: string }> {
    const response = await api.delete<{ detail: string }>(`/purchasing/products/${productId}`);
    return response.data;
  },

  // --- SOLICITAÇÕES DE COMPRA ---
  async getPurchaseRequests(status?: string): Promise<PurchaseRequest[]> {
    const params = status ? { status } : {};
    const response = await api.get<PurchaseRequest[]>('/purchasing/requests', { params });
    return response.data;
  },

  async createPurchaseRequest(data: {
    cost_center_id?: string;
    justification: string;
    required_date?: string;
    items: {
      product_id: string;
      quantity: number;
      estimated_unit_price: number;
      notes?: string;
    }[];
  }): Promise<PurchaseRequest> {
    const response = await api.post<PurchaseRequest>('/purchasing/requests', {
      ...data,
      organization_id: '00000000-0000-0000-0000-000000000000'
    });
    return response.data;
  },

  async updatePurchaseRequest(requestId: string, data: {
    cost_center_id?: string | null;
    justification?: string;
    required_date?: string | null;
  }): Promise<PurchaseRequest> {
    const response = await api.put<PurchaseRequest>(`/purchasing/requests/${requestId}`, data);
    return response.data;
  },

  async deletePurchaseRequest(requestId: string): Promise<{ detail: string }> {
    const response = await api.delete<{ detail: string }>(`/purchasing/requests/${requestId}`);
    return response.data;
  },

  async approveOrRejectRequest(requestId: string, action: 'approved' | 'rejected', comments?: string): Promise<PurchaseRequest> {
    const response = await api.post<PurchaseRequest>(`/purchasing/requests/${requestId}/approve`, {
      action,
      comments
    });
    return response.data;
  },

  // --- ORDENS DE COMPRA ---
  async getPurchaseOrders(status?: string): Promise<PurchaseOrder[]> {
    const params = status ? { status } : {};
    const response = await api.get<PurchaseOrder[]>('/purchasing/orders', { params });
    return response.data;
  },

  async getPurchaseOrder(orderId: string): Promise<PurchaseOrder> {
    const response = await api.get<PurchaseOrder>(`/purchasing/orders/${orderId}`);
    return response.data;
  },

  async createPurchaseOrder(data: {
    supplier_id: string;
    cost_center_id?: string;
    purchase_request_id?: string;
    payment_terms?: string;
    freight_type?: string;
    freight_amount?: number;
    discount_amount?: number;
    expected_delivery_date?: string;
    notes?: string;
    items: {
      product_id: string;
      quantity: number;
      unit_price: number;
    }[];
  }): Promise<PurchaseOrder> {
    const response = await api.post<PurchaseOrder>('/purchasing/orders', {
      ...data,
      organization_id: '00000000-0000-0000-0000-000000000000'
    });
    return response.data;
  },

  async generatePurchaseOrderFromRequest(
    requestId: string,
    data: import('@/types').GeneratePOFromRequestPayload
  ): Promise<PurchaseOrder> {
    const response = await api.post<PurchaseOrder>(`/purchasing/requests/${requestId}/generate-order`, data);
    return response.data;
  },

  async receivePurchaseOrder(
    orderId: string,
    data: import('@/types').PurchaseOrderReceivePayload
  ): Promise<PurchaseOrder> {
    const response = await api.post<PurchaseOrder>(`/purchasing/orders/${orderId}/receive`, data);
    return response.data;
  },

  async cancelPurchaseOrder(orderId: string): Promise<PurchaseOrder> {
    const response = await api.post<PurchaseOrder>(`/purchasing/orders/${orderId}/cancel`);
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

  async getQuotationProcesses(status?: string): Promise<import('@/types').QuotationProcess[]> {
    const params = status ? { status } : {};
    const response = await api.get<import('@/types').QuotationProcess[]>('/purchasing/quotations', { params });
    return response.data;
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
  }
};

