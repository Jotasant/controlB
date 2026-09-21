/**
 * services/api.ts - Cliente HTTP Centralizado com Axios e Cache Inteligente em Memória
 * 
 * Responsabilidades:
 * 1. Gerenciador de Cache em Memória com retenção configurável (SWR / TTL) e invalidação reativa em mutações.
 * 2. Interceptar todas as requisições HTTP e anexar automaticamente o Bearer Token JWT.
 * 3. Tratar respostas de erro 401 (token expirado) limpando a sessão e o cache, redirecionando para /login.
 * 4. Exportar métodos tipados com suporte a carregamento instantâneo e recarregamento forçado (forceRefresh).
 */

import axios from 'axios';
import { createRequestId } from '@/utils/requestId';
import { 
  User, UserMe, Role, Organization, Permission, TokenResponse,
  Supplier, CostCenter, ProductCategory, Product, PurchaseRequest, PurchaseOrder,
  PurchaseOrderReceivePayload
} from '@/types';

// Cria a instância do Axios
export const api = axios.create({
  baseURL: (import.meta.env.VITE_API_BASE_URL as string) || '', // Vazio para rotas relativas (proxy Nginx/Vite) ou URL configurada via env
  headers: {
    'Content-Type': 'application/json',
  },
});

// Chaves de armazenamento na sessão
const TOKEN_KEY = 'controlb_token';
const USER_EMAIL_KEY = 'controlb_user_email';

// ==============================================================================
// 0. GERENCIADOR DE CACHE EM MEMÓRIA (SWR / Client-Side State Retention)
// ==============================================================================

interface CacheEntry<T> {
  data: T;
  timestamp: number;
}

const memoryCache = new Map<string, CacheEntry<any>>();
const DEFAULT_CACHE_TTL = 3 * 60 * 1000; // 3 minutos de retenção padrão para leitura instantânea (0ms)

export const cacheManager = {
  /**
   * Obtém dado em cache ou busca na API renovando o cache.
   * Se forceRefresh = true, ignora o cache e busca diretamente na rede.
   */
  async fetchWithCache<T>(
    key: string,
    fetcher: () => Promise<T>,
    ttlMs: number = DEFAULT_CACHE_TTL,
    forceRefresh: boolean = false
  ): Promise<T> {
    const cached = memoryCache.get(key);
    const now = Date.now();

    if (!forceRefresh && cached && (now - cached.timestamp < ttlMs)) {
      return cached.data;
    }

    const freshData = await fetcher();
    memoryCache.set(key, { data: freshData, timestamp: now });
    return freshData;
  },

  /**
   * Retorna os dados síncronos se já existirem em memória.
   */
  get<T>(key: string): T | undefined {
    return memoryCache.get(key)?.data;
  },

  /**
   * Invalida chaves específicas ou por prefixo (ex: 'inventory', 'purchasing', 'finance').
   */
  invalidate(keyPrefix?: string) {
    if (!keyPrefix) {
      memoryCache.clear();
      return;
    }
    for (const key of Array.from(memoryCache.keys())) {
      if (key.startsWith(keyPrefix)) {
        memoryCache.delete(key);
      }
    }
  },

  /**
   * Limpa todo o cache (ao deslogar).
   */
  clear() {
    memoryCache.clear();
  }
};

// ==============================================================================
// 1. INTERCEPTORS AXIOS (JWT & 401 Handler)
// ==============================================================================

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
}, (error) => {
  return Promise.reject(error);
});

let isRedirectingToLogin = false;

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401 && !error.config?.url?.includes('/identity/token')) {
      if (!isRedirectingToLogin) {
        isRedirectingToLogin = true;
        authService.logout();
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
        setTimeout(() => {
          isRedirectingToLogin = false;
        }, 2000);
      }
    }
    return Promise.reject(error);
  }
);

/**
 * Sanitiza e formata de maneira robusta os erros retornados pela API (FastAPI / Pydantic v2).
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

// ==============================================================================
// 2. AUTENTICAÇÃO E SESSÃO (Auth)
// ==============================================================================

/**
 * Consulta somente leitura da cadeia transversal de um documento de negócio.
 * O tipo permanece aberto para que novos módulos reutilizem o mesmo contrato.
 */
export const documentService = {
  async get(documentId: string, forceRefresh = false): Promise<import('@/types').BusinessDocument> {
    return cacheManager.fetchWithCache(
      `documents:item:${documentId}`,
      async () => {
        const response = await api.get<import('@/types').BusinessDocument>(
          `/documents/${encodeURIComponent(documentId)}`
        );
        return response.data;
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async list(
    filters: import('@/types').BusinessDocumentFilters = {},
    forceRefresh = false
  ): Promise<import('@/types').BusinessDocument[]> {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        params.set(key, String(value));
      }
    });
    const query = params.toString();
    const cacheKey = `documents:list:${query}`;

    return cacheManager.fetchWithCache(
      cacheKey,
      async () => {
        const response = await api.get<import('@/types').BusinessDocument[]>(
          `/documents/${query ? `?${query}` : ''}`
        );
        return response.data;
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async getChain(
    documentType: string,
    nativeId: string,
    forceRefresh = false
  ): Promise<import('@/types').BusinessDocumentChain> {
    const normalizedType = documentType.trim().toUpperCase();
    const cacheKey = `documents:chain:${normalizedType}:${nativeId}`;

    return cacheManager.fetchWithCache(
      cacheKey,
      async () => {
        const response = await api.get<import('@/types').BusinessDocumentChain>(
          `/documents/${encodeURIComponent(normalizedType)}/${encodeURIComponent(nativeId)}/chain`
        );
        return response.data;
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  }
};

export const authService = {
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
      cacheManager.clear();
    }
    return response.data;
  },

  logout(): void {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_EMAIL_KEY);
    cacheManager.clear();
  },

  getToken(): string | null {
    return localStorage.getItem(TOKEN_KEY);
  },

  getUserEmail(): string {
    return localStorage.getItem(USER_EMAIL_KEY) || 'admin@controlb.com';
  },

  isAuthenticated(): boolean {
    return !!localStorage.getItem(TOKEN_KEY);
  },
};

// ==============================================================================
// 3. IDENTIDADE, USUÁRIOS E PERMISSÕES (Identity)
// ==============================================================================

export const identityService = {
  async getMe(forceRefresh = false): Promise<UserMe> {
    return cacheManager.fetchWithCache(
      'identity:me',
      async () => {
        const response = await api.get<UserMe>('/identity/users/me');
        return response.data;
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async getPermissions(forceRefresh = false): Promise<Permission[]> {
    return cacheManager.fetchWithCache(
      'identity:permissions',
      async () => {
        const response = await api.get<Permission[]>('/identity/permissions');
        return response.data;
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async getUsers(forceRefresh = false): Promise<User[]> {
    return cacheManager.fetchWithCache(
      'identity:users',
      async () => {
        const response = await api.get<User[]>('/identity/users');
        return response.data;
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async getUser(userId: string, forceRefresh = false): Promise<User> {
    return cacheManager.fetchWithCache(
      `identity:users:item:${userId}`,
      async () => {
        const response = await api.get<User>(`/identity/users/${encodeURIComponent(userId)}`);
        return response.data;
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async createUser(data: { full_name: string; email: string; password: string; organization_id: string; role_id?: string | null; is_seller?: boolean }): Promise<User> {
    const response = await api.post<User>('/identity/users', data);
    cacheManager.invalidate('identity:users');
    cacheManager.invalidate('identity:teams:candidates');
    cacheManager.invalidate('sales:sellers');
    return response.data;
  },

  async updateUser(userId: string, data: { full_name?: string; email?: string; password?: string; organization_id?: string; role_id?: string | null; is_active?: boolean; is_seller?: boolean }): Promise<User> {
    const response = await api.put<User>(`/identity/users/${userId}`, data);
    cacheManager.invalidate('identity:users');
    cacheManager.invalidate('identity:teams:candidates');
    cacheManager.invalidate('identity:me');
    cacheManager.invalidate('sales:sellers');
    cacheManager.invalidate(`identity:users:item:${userId}`);
    return response.data;
  },

  async deleteUser(userId: string): Promise<{ message: string }> {
    const response = await api.delete<{ message: string }>(`/identity/users/${userId}`);
    cacheManager.invalidate('identity:users');
    cacheManager.invalidate('identity:teams:candidates');
    cacheManager.invalidate(`identity:users:item:${userId}`);
    return response.data;
  },

  async bulkDeleteUsers(userIds: string[]): Promise<{ message: string; deleted_count: number }> {
    const response = await api.delete<{ message: string; deleted_count: number }>('/identity/users', {
      data: { user_ids: userIds }
    });
    cacheManager.invalidate('identity:users');
    cacheManager.invalidate('identity:teams:candidates');
    return response.data;
  },

  async getOrganizations(forceRefresh = false): Promise<Organization[]> {
    return cacheManager.fetchWithCache(
      'identity:orgs',
      async () => {
        const response = await api.get<Organization[]>('/identity/organization');
        return response.data;
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async getOrganization(orgId: string, forceRefresh = false): Promise<Organization> {
    return cacheManager.fetchWithCache(
      `identity:orgs:item:${orgId}`,
      async () => {
        const response = await api.get<Organization>(`/identity/organization/${encodeURIComponent(orgId)}`);
        return response.data;
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async createOrganization(name: string): Promise<Organization> {
    const response = await api.post<Organization>('/identity/organization', { name });
    cacheManager.invalidate('identity:orgs');
    return response.data;
  },

  async updateOrganization(orgId: string, data: { name?: string; is_active?: boolean }): Promise<Organization> {
    const response = await api.put<Organization>(`/identity/organization/${orgId}`, data);
    cacheManager.invalidate('identity:orgs');
    cacheManager.invalidate(`identity:orgs:item:${orgId}`);
    return response.data;
  },

  async deleteOrganization(orgId: string): Promise<{ message: string }> {
    const response = await api.delete<{ message: string }>(`/identity/organization/${orgId}`);
    cacheManager.invalidate('identity:orgs');
    cacheManager.invalidate(`identity:orgs:item:${orgId}`);
    return response.data;
  },

  async bulkDeleteOrganizations(orgIds: string[]): Promise<{ message: string; deleted_count: number }> {
    const response = await api.delete<{ message: string; deleted_count: number }>('/identity/organization', {
      data: { org_ids: orgIds }
    });
    cacheManager.invalidate('identity:orgs');
    return response.data;
  },

  async getRoles(forceRefresh = false): Promise<Role[]> {
    return cacheManager.fetchWithCache(
      'identity:roles',
      async () => {
        const response = await api.get<Role[]>('/identity/role');
        return response.data;
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async getRole(roleId: string, forceRefresh = false): Promise<Role> {
    return cacheManager.fetchWithCache(
      `identity:roles:item:${roleId}`,
      async () => {
        const response = await api.get<Role>(`/identity/role/${encodeURIComponent(roleId)}`);
        return response.data;
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async createRole(name: string, description: string, organizationId: string, permissionIds: string[] = []): Promise<Role> {
    const response = await api.post<Role>('/identity/role', { 
      name, 
      description,
      organization_id: organizationId,
      permission_ids: permissionIds
    });
    cacheManager.invalidate('identity:roles');
    return response.data;
  },

  async updateRole(roleId: string, data: { name?: string; description?: string; is_active?: boolean; permission_ids?: string[] }): Promise<Role> {
    const response = await api.put<Role>(`/identity/role/${roleId}`, data);
    cacheManager.invalidate('identity:roles');
    cacheManager.invalidate('identity:users');
    cacheManager.invalidate(`identity:roles:item:${roleId}`);
    return response.data;
  },

  async deleteRole(roleId: string): Promise<{ message: string }> {
    const response = await api.delete<{ message: string }>(`/identity/role/${roleId}`);
    cacheManager.invalidate('identity:roles');
    cacheManager.invalidate('identity:users');
    cacheManager.invalidate(`identity:roles:item:${roleId}`);
    return response.data;
  },

  async bulkDeleteRoles(roleIds: string[]): Promise<{ message: string; deleted_count: number }> {
    const response = await api.delete<{ message: string; deleted_count: number }>('/identity/role', {
      data: { role_ids: roleIds }
    });
    cacheManager.invalidate('identity:roles');
    cacheManager.invalidate('identity:users');
    return response.data;
  },

  async getContacts(
    options?: { search?: string; is_customer?: boolean; is_supplier?: boolean; is_carrier?: boolean } | string | boolean,
    forceRefresh = false
  ): Promise<import('@/types').Contact[]> {
    let search: string | undefined;
    let is_customer: boolean | undefined;
    let is_supplier: boolean | undefined;
    let is_carrier: boolean | undefined;
    let force = forceRefresh;

    if (typeof options === 'string') {
      search = options;
    } else if (typeof options === 'boolean') {
      force = options;
    } else if (options && typeof options === 'object') {
      search = options.search;
      is_customer = options.is_customer;
      is_supplier = options.is_supplier;
      is_carrier = options.is_carrier;
    }

    const key = `identity:contacts:${search || 'all'}:${is_customer ?? 'all'}:${is_supplier ?? 'all'}:${is_carrier ?? 'all'}`;
    return cacheManager.fetchWithCache(
      key,
      async () => {
        const params: Record<string, any> = {};
        if (search) params.search = search;
        if (is_customer !== undefined) params.is_customer = is_customer;
        if (is_supplier !== undefined) params.is_supplier = is_supplier;
        if (is_carrier !== undefined) params.is_carrier = is_carrier;
        const response = await api.get<import('@/types').Contact[]>('/identity/contacts', { params });
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      force
    );
  },

  async getContact(id: string): Promise<import('@/types').Contact> {
    const response = await api.get(`/identity/contacts/${id}`);
    return response.data;
  },

  async getContactDirectory(params: { search?: string; connection_id?: string; contact_id?: string; origin_module?: string; is_active?: boolean; page?: number; page_size?: number } = {}): Promise<{ items: import('@/types').ContactDirectoryEntry[]; total: number; page: number }> {
    const response = await api.get('/identity/contact-directory', { params });
    return response.data;
  },

  async createContact(data: Partial<import('@/types').Contact>): Promise<import('@/types').Contact> {
    const response = await api.post<import('@/types').Contact>('/identity/contacts', data);
    cacheManager.invalidate('identity:contacts');
    return response.data;
  },

  async updateContact(contactId: string, data: Partial<import('@/types').Contact>): Promise<import('@/types').Contact> {
    const response = await api.put<import('@/types').Contact>(`/identity/contacts/${contactId}`, data);
    cacheManager.invalidate('identity:contacts');
    return response.data;
  },

  async deleteContact(contactId: string): Promise<{ message: string }> {
    const response = await api.delete<{ message: string }>(`/identity/contacts/${contactId}`);
    cacheManager.invalidate('identity:contacts');
    return response.data;
  },

  async bulkDeleteContacts(contactIds: string[]): Promise<{ message: string; deleted_count: number }> {
    const response = await api.post<{ message: string; deleted_count: number }>('/identity/contacts/bulk-delete', { contact_ids: contactIds });
    cacheManager.invalidate('identity:contacts');
    return response.data;
  },

  // --- EQUIPES / GRUPOS DE TRABALHO (TEAMS) ---
  async getTeams(moduleCategory?: string, forceRefresh = false): Promise<import('@/types').Team[]> {
    const key = `identity:teams:${moduleCategory || 'all'}`;
    return cacheManager.fetchWithCache(
      key,
      async () => {
        const response = await api.get<import('@/types').Team[]>('/identity/teams', {
          params: moduleCategory ? { module_category: moduleCategory } : undefined
        });
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async getTeamCandidates(forceRefresh = false): Promise<import('@/types').TeamMemberInfo[]> {
    return cacheManager.fetchWithCache(
      'identity:teams:candidates',
      async () => {
        const response = await api.get<import('@/types').TeamMemberInfo[]>('/identity/teams/candidates');
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async createTeam(data: { name: string; code?: string; module_category?: string; description?: string; leader_id?: string; member_ids?: string[]; is_active?: boolean }): Promise<import('@/types').Team> {
    const response = await api.post<import('@/types').Team>('/identity/teams', data);
    cacheManager.invalidate('identity:teams');
    return response.data;
  },

  async updateTeam(teamId: string, data: { name?: string; code?: string | null; module_category?: string; description?: string | null; leader_id?: string | null; is_active?: boolean; member_ids?: string[] }): Promise<import('@/types').Team> {
    const response = await api.put<import('@/types').Team>(`/identity/teams/${teamId}`, data);
    cacheManager.invalidate('identity:teams');
    return response.data;
  },

  async deleteTeam(teamId: string): Promise<{ message: string }> {
    const response = await api.delete<{ message: string }>(`/identity/teams/${teamId}`);
    cacheManager.invalidate('identity:teams');
    return response.data;
  },

  async addTeamMembers(teamId: string, userIds: string[]): Promise<import('@/types').Team> {
    const response = await api.post<import('@/types').Team>(`/identity/teams/${teamId}/members`, { user_ids: userIds });
    cacheManager.invalidate('identity:teams');
    return response.data;
  },

  async removeTeamMember(teamId: string, userId: string): Promise<import('@/types').Team> {
    const response = await api.delete<import('@/types').Team>(`/identity/teams/${teamId}/members/${userId}`);
    cacheManager.invalidate('identity:teams');
    return response.data;
  }
};


// ==============================================================================
// 4. ESTOQUE E INVENTÁRIO FÍSICO (Inventory)
// ==============================================================================

export const inventoryService = {
  async getCategories(forceRefresh = false): Promise<ProductCategory[]> {
    return cacheManager.fetchWithCache(
      'inventory:categories',
      async () => {
        const response = await api.get<ProductCategory[]>('/inventory/categories');
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async createCategory(data: { name: string; code?: string; description?: string }): Promise<ProductCategory> {
    const response = await api.post<ProductCategory>('/inventory/categories', data);
    cacheManager.invalidate('inventory:categories');
    return response.data;
  },

  async updateCategory(categoryId: string, data: { name?: string; code?: string; description?: string; is_active?: boolean }): Promise<ProductCategory> {
    const response = await api.put<ProductCategory>(`/inventory/categories/${categoryId}`, data);
    cacheManager.invalidate('inventory:categories');
    cacheManager.invalidate('inventory:products');
    return response.data;
  },

  async deleteCategory(categoryId: string): Promise<void> {
    await api.delete(`/inventory/categories/${categoryId}`);
    cacheManager.invalidate('inventory:categories');
    cacheManager.invalidate('inventory:products');
  },

  async getProducts(categoryId?: string, forceRefresh = false): Promise<Product[]> {
    const key = `inventory:products:${categoryId || 'all'}`;
    return cacheManager.fetchWithCache(
      key,
      async () => {
        const params = categoryId ? { category_id: categoryId } : {};
        const response = await api.get<Product[]>('/inventory/products', { params });
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async getProduct(productId: string, forceRefresh = false): Promise<Product> {
    return cacheManager.fetchWithCache(
      `inventory:product:${productId}`,
      async () => {
        const response = await api.get<Product>(`/inventory/products/${productId}`);
        return response.data;
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async createProduct(data: {
    sku?: string;
    name: string;
    description?: string;
    unit_of_measure?: string;
    reference_price?: number;
    cost_price?: number;
    sale_price?: number;
    external_code?: string;
    toolspharma_code?: string;
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
    cacheManager.invalidate('inventory:products');
    cacheManager.invalidate('purchasing:replenishment');
    return response.data;
  },

  async updateProduct(productId: string, data: Partial<Product>): Promise<Product> {
    const response = await api.put<Product>(`/inventory/products/${productId}`, data);
    cacheManager.invalidate('inventory:products');
    cacheManager.invalidate(`inventory:product:${productId}`);
    cacheManager.invalidate('purchasing:replenishment');
    return response.data;
  },

  async deleteProduct(productId: string): Promise<void> {
    await api.delete(`/inventory/products/${productId}`);
    cacheManager.invalidate('inventory:products');
    cacheManager.invalidate(`inventory:product:${productId}`);
    cacheManager.invalidate('purchasing:replenishment');
  },

  async adjustInventoryStock(payload: import('@/types').StockAdjustmentPayload): Promise<import('@/types').StockMovement> {
    const response = await api.post<import('@/types').StockMovement>('/inventory/adjust', payload);
    cacheManager.invalidate('inventory');
    cacheManager.invalidate('purchasing:replenishment');
    return response.data;
  },

  async reserveSalesOrderStock(orderId: string): Promise<import('@/types').StockReservation> {
    const response = await api.post<import('@/types').StockReservation>(
      `/inventory/reservations/sales-orders/${orderId}`
    );
    cacheManager.invalidate('inventory');
    cacheManager.invalidate('sales:orders');
    cacheManager.invalidate(`sales:order:${orderId}`);
    cacheManager.invalidate(`documents:chain:SALES_ORDER:${orderId}`);
    return response.data;
  },

  async getSalesOrderDelivery(orderId: string): Promise<import('@/types').InventoryDelivery> {
    const response = await api.get<import('@/types').InventoryDelivery>(
      `/inventory/deliveries/sales-orders/${orderId}`
    );
    return response.data;
  },

  async getInventoryDelivery(deliveryId: string): Promise<import('@/types').InventoryDelivery> {
    const response = await api.get<import('@/types').InventoryDelivery>(
      `/inventory/deliveries/${deliveryId}`
    );
    return response.data;
  },

  async getStockReservation(reservationId: string): Promise<import('@/types').StockReservation> {
    const response = await api.get<import('@/types').StockReservation>(
      `/inventory/reservations/${reservationId}`
    );
    return response.data;
  },

  async getInventoryLocations(forceRefresh = false): Promise<import('@/types').InventoryLocation[]> {
    return cacheManager.fetchWithCache(
      'inventory:locations',
      async () => {
        const response = await api.get<import('@/types').InventoryLocation[]>('/inventory/locations');
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async createInventoryLocation(data: {
    code: string;
    name: string;
    description?: string | null;
  }): Promise<import('@/types').InventoryLocation> {
    const response = await api.post<import('@/types').InventoryLocation>('/inventory/locations', data);
    cacheManager.invalidate('inventory:locations');
    return response.data;
  },

  async getInventoryBalances(productId?: string, forceRefresh = false): Promise<import('@/types').InventoryBalance[]> {
    const key = `inventory:balances:${productId || 'all'}`;
    return cacheManager.fetchWithCache(
      key,
      async () => {
        const params = productId ? { product_id: productId } : {};
        const response = await api.get<import('@/types').InventoryBalance[]>('/inventory/balances', { params });
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async createInventoryTransfer(payload: import('@/types').InventoryTransferPayload): Promise<import('@/types').InventoryTransfer> {
    const response = await api.post<import('@/types').InventoryTransfer>('/inventory/transfers', payload);
    cacheManager.invalidate('inventory');
    cacheManager.invalidate('inventory:balances');
    cacheManager.invalidate('inventory:movements');
    cacheManager.invalidate('documents');
    return response.data;
  },

  async getInventoryTransfers(forceRefresh = false): Promise<import('@/types').InventoryTransfer[]> {
    return cacheManager.fetchWithCache(
      'inventory:transfers',
      async () => {
        const response = await api.get<import('@/types').InventoryTransfer[]>('/inventory/transfers');
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async getInventoryTransfer(transferId: string, forceRefresh = false): Promise<import('@/types').InventoryTransfer> {
    return cacheManager.fetchWithCache(
      `inventory:transfer:${transferId}`,
      async () => {
        const response = await api.get<import('@/types').InventoryTransfer>(`/inventory/transfers/${transferId}`);
        return response.data;
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async getInventoryMovements(productId?: string, limit?: number, forceRefresh = false): Promise<import('@/types').StockMovement[]> {
    const key = `inventory:movements:${productId || 'all'}:${limit || 0}`;
    return cacheManager.fetchWithCache(
      key,
      async () => {
        const params = new URLSearchParams();
        if (productId) params.append('product_id', productId);
        if (limit) params.append('limit', limit.toString());
        const response = await api.get<import('@/types').StockMovement[]>(`/inventory/movements?${params.toString()}`);
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async importInventorySpreadsheet(file: File): Promise<import('@/types').InventoryImportSummaryResponse> {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post<import('@/types').InventoryImportSummaryResponse>(
      '/inventory/import-spreadsheet',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    cacheManager.invalidate('inventory');
    cacheManager.invalidate('purchasing:replenishment');
    return response.data;
  },

  async importToolsPharma(file: File): Promise<import('@/types').InventoryImportSummaryResponse> {
    return this.importInventorySpreadsheet(file);
  },

  async getImportBatches(limit = 50, offset = 0, forceRefresh = false): Promise<import('@/types').InventoryImportBatchListItem[]> {
    return cacheManager.fetchWithCache(
      `inventory:import_batches:${limit}:${offset}`,
      async () => {
        const response = await api.get<import('@/types').InventoryImportBatchListItem[]>(
          `/inventory/import-batches?limit=${limit}&offset=${offset}`
        );
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async getImportBatchDetail(batchId: string, forceRefresh = false): Promise<import('@/types').InventoryImportBatch> {
    return cacheManager.fetchWithCache(
      `inventory:import_batch:${batchId}`,
      async () => {
        const response = await api.get<import('@/types').InventoryImportBatch>(
          `/inventory/import-batches/${batchId}`
        );
        return response.data;
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async getStagnantInventoryReport(forceRefresh = false): Promise<import('@/types').StagnantInventoryReport> {
    return cacheManager.fetchWithCache(
      'inventory:stagnant_report',
      async () => {
        const response = await api.get<import('@/types').StagnantInventoryReport>(
          '/inventory/reports/stagnation'
        );
        return response.data;
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  }
};

// ==============================================================================
// 5. COMPRAS, FORNECEDORES E ORDENS (Purchasing / Procure-to-Pay)
// ==============================================================================

export const purchasingService = {
  async getSuppliers(forceRefresh = false): Promise<Supplier[]> {
    return cacheManager.fetchWithCache(
      'purchasing:suppliers',
      async () => {
        const response = await api.get<Supplier[]>('/purchasing/suppliers');
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async createSupplier(data: {
    name: string;
    trade_name?: string;
    cnpj_cpf: string;
    state_registration?: string;
    contact_name?: string;
    contact_id?: string | null;
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
    cacheManager.invalidate('purchasing:suppliers');
    return response.data;
  },

  async updateSupplier(supplierId: string, data: Partial<Supplier>): Promise<Supplier> {
    const response = await api.put<Supplier>(`/purchasing/suppliers/${supplierId}`, data);
    cacheManager.invalidate('purchasing:suppliers');
    return response.data;
  },

  async deleteSupplier(supplierId: string): Promise<{ detail: string }> {
    const response = await api.delete<{ detail: string }>(`/purchasing/suppliers/${supplierId}`);
    cacheManager.invalidate('purchasing:suppliers');
    return response.data;
  },

  async getCostCenters(forceRefresh = false): Promise<CostCenter[]> {
    return cacheManager.fetchWithCache(
      'purchasing:cost_centers',
      async () => {
        const response = await api.get<CostCenter[]>('/purchasing/cost-centers');
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async createCostCenter(data: { code: string; name: string; description?: string; manager_id?: string }): Promise<CostCenter> {
    const response = await api.post<CostCenter>('/purchasing/cost-centers', {
      ...data,
      organization_id: '00000000-0000-0000-0000-000000000000'
    });
    cacheManager.invalidate('purchasing:cost_centers');
    return response.data;
  },

  async updateCostCenter(costCenterId: string, data: Partial<CostCenter>): Promise<CostCenter> {
    const response = await api.put<CostCenter>(`/purchasing/cost-centers/${costCenterId}`, data);
    cacheManager.invalidate('purchasing:cost_centers');
    return response.data;
  },

  async deleteCostCenter(costCenterId: string): Promise<{ detail: string }> {
    const response = await api.delete<{ detail: string }>(`/purchasing/cost-centers/${costCenterId}`);
    cacheManager.invalidate('purchasing:cost_centers');
    return response.data;
  },

  // Delegação para Inventory
  getCategories: (forceRefresh = false) => inventoryService.getCategories(forceRefresh),
  createCategory: (data: any) => inventoryService.createCategory(data),
  updateCategory: (id: string, data: any) => inventoryService.updateCategory(id, data),
  deleteCategory: (id: string) => inventoryService.deleteCategory(id),

  getProducts: (categoryId?: string, forceRefresh = false) => inventoryService.getProducts(categoryId, forceRefresh),
  getProduct: (id: string, forceRefresh = false) => inventoryService.getProduct(id, forceRefresh),
  createProduct: (data: any) => inventoryService.createProduct(data),
  updateProduct: (id: string, data: any) => inventoryService.updateProduct(id, data),
  deleteProduct: (id: string) => inventoryService.deleteProduct(id),

  adjustInventoryStock: (payload: any) => inventoryService.adjustInventoryStock(payload),
  getInventoryMovements: (productId?: string, limit?: number, forceRefresh = false) => inventoryService.getInventoryMovements(productId, limit, forceRefresh),

  // --- SOLICITAÇÕES DE COMPRA (PR) ---
  async getPurchaseRequests(forceRefresh = false): Promise<PurchaseRequest[]> {
    return cacheManager.fetchWithCache(
      'purchasing:requests',
      async () => {
        const response = await api.get<PurchaseRequest[]>('/purchasing/requests');
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async createPurchaseRequest(data: {
    justification: string;
    cost_center_id?: string;
    required_date?: string;
    items: Array<{ product_id: string; quantity: number; estimated_unit_price: number; notes?: string }>;
  }): Promise<PurchaseRequest> {
    const response = await api.post<PurchaseRequest>('/purchasing/requests', data);
    cacheManager.invalidate('purchasing:requests');
    return response.data;
  },

  async updatePurchaseRequest(requestId: string, data: { justification?: string; cost_center_id?: string | null; required_date?: string | null }): Promise<PurchaseRequest> {
    const response = await api.put<PurchaseRequest>(`/purchasing/requests/${requestId}`, data);
    cacheManager.invalidate('purchasing:requests');
    return response.data;
  },

  async deletePurchaseRequest(requestId: string): Promise<void> {
    await api.delete(`/purchasing/requests/${requestId}`);
    cacheManager.invalidate('purchasing:requests');
  },

  async purgePurchaseRequests(requestIds?: string[]): Promise<{ detail: string; deleted_count: number }> {
    const params = requestIds && requestIds.length > 0 ? { request_ids: requestIds } : {};
    const response = await api.delete<{ detail: string; deleted_count: number }>('/purchasing/requests', { params });
    cacheManager.invalidate('purchasing:requests');
    return response.data;
  },

  async submitRequestForApproval(requestId: string): Promise<PurchaseRequest> {
    const response = await api.post<PurchaseRequest>(`/purchasing/requests/${requestId}/submit`);
    cacheManager.invalidate('purchasing:requests');
    return response.data;
  },

  async approveOrRejectRequest(requestId: string, action: 'approved' | 'rejected', comments?: string): Promise<PurchaseRequest> {
    const response = await api.post<PurchaseRequest>(`/purchasing/requests/${requestId}/approve`, {
      action,
      comments
    });
    cacheManager.invalidate('purchasing:requests');
    return response.data;
  },

  // --- ORDENS DE COMPRA (PO) ---
  async getPurchaseOrders(status?: string, forceRefresh = false): Promise<PurchaseOrder[]> {
    const key = `purchasing:orders:${status || 'all'}`;
    return cacheManager.fetchWithCache(
      key,
      async () => {
        const params = status ? { status } : {};
        const response = await api.get<PurchaseOrder[]>('/purchasing/orders', { params });
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async getPurchaseOrder(orderId: string, forceRefresh = false): Promise<PurchaseOrder> {
    return cacheManager.fetchWithCache(
      `purchasing:order:${orderId}`,
      async () => {
        const response = await api.get<PurchaseOrder>(`/purchasing/orders/${orderId}`);
        return response.data;
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
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
    cacheManager.invalidate('purchasing:orders');
    cacheManager.invalidate('purchasing:requests');
    cacheManager.invalidate('purchasing:replenishment');
    return response.data;
  },

  async receivePurchaseOrder(orderId: string, data: PurchaseOrderReceivePayload): Promise<PurchaseOrder> {
    const response = await api.post<PurchaseOrder>(`/purchasing/orders/${orderId}/receive`, data);
    cacheManager.invalidate('purchasing:orders');
    cacheManager.invalidate('inventory');
    cacheManager.invalidate('finance');
    cacheManager.invalidate('documents');
    cacheManager.invalidate('purchasing:replenishment');
    return response.data;
  },

  async cancelPurchaseOrder(orderId: string): Promise<PurchaseOrder> {
    const response = await api.post<PurchaseOrder>(`/purchasing/orders/${orderId}/cancel`);
    cacheManager.invalidate('purchasing:orders');
    return response.data;
  },

  async deletePurchaseOrder(orderId: string): Promise<{ detail: string }> {
    const response = await api.delete<{ detail: string }>(`/purchasing/orders/${orderId}`);
    cacheManager.invalidate('purchasing:orders');
    return response.data;
  },

  async purgePurchaseOrders(orderIds?: string[]): Promise<{ detail: string; deleted_count: number }> {
    const params = orderIds && orderIds.length > 0 ? { order_ids: orderIds } : {};
    const response = await api.delete<{ detail: string; deleted_count: number }>('/purchasing/orders', { params });
    cacheManager.invalidate('purchasing:orders');
    return response.data;
  },

  // --- PROCESSOS DE COTAÇÃO (RFQ) ---
  async openQuotationProcess(requestId: string, notes?: string): Promise<import('@/types').QuotationProcess> {
    const response = await api.post<import('@/types').QuotationProcess>(`/purchasing/requests/${requestId}/quotations`, {
      purchase_request_id: requestId,
      notes
    });
    cacheManager.invalidate('purchasing:quotations');
    cacheManager.invalidate('purchasing:requests');
    return response.data;
  },

  async deleteQuotation(quotationId: string): Promise<{ detail: string }> {
    const response = await api.delete<{ detail: string }>(`/purchasing/quotations/${quotationId}`);
    cacheManager.invalidate('purchasing:quotations');
    return response.data;
  },

  async purgeQuotations(quotationIds?: string[]): Promise<{ detail: string; deleted_count: number }> {
    const params = quotationIds && quotationIds.length > 0 ? { quotation_ids: quotationIds } : {};
    const response = await api.delete<{ detail: string; deleted_count: number }>('/purchasing/quotations', { params });
    cacheManager.invalidate('purchasing:quotations');
    return response.data;
  },

  async getQuotationProcesses(status?: string, forceRefresh = false): Promise<import('@/types').QuotationProcess[]> {
    const key = `purchasing:quotations:${status || 'all'}`;
    return cacheManager.fetchWithCache(
      key,
      async () => {
        const params = status ? { status } : {};
        const response = await api.get<import('@/types').QuotationProcess[]>('/purchasing/quotations', { params });
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async getQuotationProcess(quotationId: string, forceRefresh = false): Promise<import('@/types').QuotationProcess> {
    return cacheManager.fetchWithCache(
      `purchasing:quotation:${quotationId}`,
      async () => {
        const response = await api.get<import('@/types').QuotationProcess>(`/purchasing/quotations/${quotationId}`);
        return response.data;
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async addSupplierQuote(
    quotationId: string, 
    data: import('@/types').SupplierQuotePayload
  ): Promise<import('@/types').SupplierQuote> {
    const response = await api.post<import('@/types').SupplierQuote>(`/purchasing/quotations/${quotationId}/quotes`, data);
    cacheManager.invalidate('purchasing:quotations');
    cacheManager.invalidate(`purchasing:quotation:${quotationId}`);
    return response.data;
  },

  async getQuotationComparison(quotationId: string, forceRefresh = false): Promise<import('@/types').QuotationComparisonMatrix> {
    return cacheManager.fetchWithCache(
      `purchasing:quotation_comparison:${quotationId}`,
      async () => {
        const response = await api.get<import('@/types').QuotationComparisonMatrix>(`/purchasing/quotations/${quotationId}/comparison`);
        return response.data;
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async selectWinnerQuote(
    quotationId: string, 
    quoteId: string, 
    notes?: string
  ): Promise<PurchaseOrder> {
    const response = await api.post<PurchaseOrder>(`/purchasing/quotations/${quotationId}/select-winner/${quoteId}`, {
      notes
    });
    cacheManager.invalidate('purchasing:quotations');
    cacheManager.invalidate('purchasing:orders');
    cacheManager.invalidate('purchasing:requests');
    return response.data;
  },

  async cancelPurchaseRequest(requestId: string): Promise<PurchaseRequest> {
    const response = await api.post<PurchaseRequest>(`/purchasing/requests/${requestId}/cancel`);
    cacheManager.invalidate('purchasing:requests');
    return response.data;
  },

  async cancelQuotation(quotationId: string): Promise<import('@/types').QuotationProcess> {
    const response = await api.post<import('@/types').QuotationProcess>(`/purchasing/quotations/${quotationId}/cancel`);
    cacheManager.invalidate('purchasing:quotations');
    return response.data;
  },

  async reopenQuotation(quotationId: string): Promise<import('@/types').QuotationProcess> {
    const response = await api.post<import('@/types').QuotationProcess>(`/purchasing/quotations/${quotationId}/reopen`);
    cacheManager.invalidate('purchasing:quotations');
    return response.data;
  },

  async deleteSupplierQuote(quotationId: string, quoteId: string): Promise<{ detail: string }> {
    const response = await api.delete<{ detail: string }>(`/purchasing/quotations/${quotationId}/quotes/${quoteId}`);
    cacheManager.invalidate('purchasing:quotations');
    return response.data;
  },

  // --- REPOSIÇÃO ÁGIL (ASSISTENTE DE COMPRAS & PO DIRETA) ---
  async getInventoryReplenishments(forceRefresh = false): Promise<import('@/types').InventoryReplenishment[]> {
    return cacheManager.fetchWithCache(
      'purchasing:replenishment-documents',
      async () => {
        const response = await api.get<import('@/types').InventoryReplenishment[]>('/purchasing/replenishments');
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async getReplenishmentSuggestions(forceRefresh = false): Promise<import('@/types').PurchaseSuggestionsSummary> {
    return cacheManager.fetchWithCache(
      'purchasing:replenishment',
      async () => {
        const response = await api.get<import('@/types').PurchaseSuggestionsSummary>('/purchasing/suggestions');
        return response.data;
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async createQuickReplenishmentOrder(payload: import('@/types').QuickReplenishmentOrderPayload): Promise<PurchaseOrder> {
    const response = await api.post<PurchaseOrder>('/purchasing/orders/quick-replenishment', payload);
    cacheManager.invalidate('purchasing:orders');
    cacheManager.invalidate('purchasing:replenishment');
    cacheManager.invalidate('purchasing:replenishment-documents');
    cacheManager.invalidate('inventory');
    return response.data;
  },

  async createFormalReplenishmentRequest(payload: {
    justification: string;
    cost_center_id?: string;
    required_date?: string;
    items: Array<{
      product_id: string;
      quantity: number;
      estimated_unit_price: number;
      notes?: string;
    }>;
  }): Promise<PurchaseRequest> {
    const response = await api.post<PurchaseRequest>('/purchasing/replenishments/requests', payload);
    cacheManager.invalidate('purchasing:requests');
    cacheManager.invalidate('purchasing:replenishment');
    cacheManager.invalidate('purchasing:replenishment-documents');
    return response.data;
  }
};

// ==============================================================================
// 6. GESTÃO FINANCEIRA (Finance)
// ==============================================================================

export const financeService = {
  async getDashboard(forceRefresh = false): Promise<import('@/types').FinanceDashboardSummary> {
    return cacheManager.fetchWithCache(
      'finance:dashboard',
      async () => {
        const response = await api.get<import('@/types').FinanceDashboardSummary>('/finance/dashboard');
        return response.data;
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async getCategories(type?: 'EXPENSE' | 'REVENUE', forceRefresh = false): Promise<import('@/types').FinancialCategory[]> {
    const key = `finance:categories:${type || 'all'}`;
    return cacheManager.fetchWithCache(
      key,
      async () => {
        const params = type ? { category_type: type } : {};
        const response = await api.get<import('@/types').FinancialCategory[]>('/finance/categories', { params });
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async createCategory(data: { name: string; code?: string; category_type?: string; description?: string }): Promise<import('@/types').FinancialCategory> {
    const response = await api.post<import('@/types').FinancialCategory>('/finance/categories', data);
    cacheManager.invalidate('finance:categories');
    return response.data;
  },

  async updateCategory(id: string, data: Partial<import('@/types').FinancialCategory>): Promise<import('@/types').FinancialCategory> {
    const response = await api.patch<import('@/types').FinancialCategory>(`/finance/categories/${id}`, data);
    cacheManager.invalidate('finance:categories');
    return response.data;
  },

  async getBankAccounts(forceRefresh = false): Promise<import('@/types').BankAccount[]> {
    return cacheManager.fetchWithCache(
      'finance:bank_accounts',
      async () => {
        const response = await api.get<import('@/types').BankAccount[]>('/finance/bank-accounts');
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async createBankAccount(data: { bank_name: string; bank_code?: string; agency?: string; account_number?: string; account_type?: string; opening_balance?: number }): Promise<import('@/types').BankAccount> {
    const response = await api.post<import('@/types').BankAccount>('/finance/bank-accounts', data);
    cacheManager.invalidate('finance:bank_accounts');
    cacheManager.invalidate('finance:dashboard');
    return response.data;
  },

  async updateBankAccount(id: string, data: Partial<import('@/types').BankAccount>): Promise<import('@/types').BankAccount> {
    const response = await api.patch<import('@/types').BankAccount>(`/finance/bank-accounts/${id}`, data);
    cacheManager.invalidate('finance:bank_accounts');
    return response.data;
  },

  async getFiscalDocuments(direction?: string, documentType?: string, forceRefresh = false): Promise<import('@/types').FiscalDocument[]> {
    const key = `finance:fiscal:${direction || 'all'}:${documentType || 'all'}`;
    return cacheManager.fetchWithCache(
      key,
      async () => {
        const params: Record<string, string> = {};
        if (direction) params.direction = direction;
        if (documentType) params.document_type = documentType;
        const response = await api.get<import('@/types').FiscalDocument[]>('/finance/fiscal-documents', { params });
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async createFiscalDocument(data: Partial<import('@/types').FiscalDocument>): Promise<import('@/types').FiscalDocument> {
    const response = await api.post<import('@/types').FiscalDocument>('/finance/fiscal-documents', data);
    cacheManager.invalidate('finance:fiscal');
    return response.data;
  },

  async updateFiscalDocument(id: string, data: Partial<import('@/types').FiscalDocument>): Promise<import('@/types').FiscalDocument> {
    const response = await api.patch<import('@/types').FiscalDocument>(`/finance/fiscal-documents/${id}`, data);
    cacheManager.invalidate('finance:fiscal');
    cacheManager.invalidate('billing:fiscal');
    cacheManager.invalidate('documents');
    return response.data;
  },

  async getPayables(
    status?: string,
    expenseNature?: string,
    forceRefresh = false,
    obligationType?: string,
    businessOrigin?: string
  ): Promise<import('@/types').Payable[]> {
    const key = `finance:payables:${status || 'all'}:${expenseNature || 'all'}:${obligationType || 'all'}:${businessOrigin || 'all'}`;
    return cacheManager.fetchWithCache(
      key,
      async () => {
        const params: Record<string, string> = {};
        if (status) params.status = status;
        if (expenseNature) params.expense_nature = expenseNature;
        if (obligationType) params.obligation_type = obligationType;
        if (businessOrigin) params.business_origin = businessOrigin;
        const response = await api.get<import('@/types').Payable[]>('/finance/payables', { params });
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async createPayable(data: {
    description: string;
    favored_name: string;
    original_amount: number;
    issue_date: string;
    due_date: string;
    expense_nature?: 'OPEX' | 'CAPEX' | 'FINANCIAL' | 'TAX' | 'PAYROLL' | 'TRANSFER' | 'NOT_APPLICABLE';
    obligation_type?: 'GOODS_SUPPLIER' | 'SERVICE_PROVIDER' | 'TAX' | 'PAYROLL' | 'RENT_LEASE' | 'FINANCING' | 'REIMBURSEMENT' | 'INVESTMENT' | 'OTHER';
    business_origin?: 'PURCHASE' | 'REPLENISHMENT' | 'INVESTMENT' | 'CONTRACT' | 'FISCAL_DOCUMENT' | 'MANUAL' | 'OTHER';
    payment_method_expected?: string;
    cost_center_id?: string;
    financial_category_id?: string;
    supplier_id?: string;
    purchase_order_id?: string;
    fiscal_document_id?: string;
    installments_count?: number;
    installment_frequency_days?: number;
    instrument?: {
      instrument_type: string;
      barcode?: string;
      digitable_line?: string;
      pix_code?: string;
      due_date?: string;
      amount?: number;
      file_attachment?: string;
    };
    new_fiscal_document?: {
      document_type: string;
      document_number: string;
      series?: string;
      access_key?: string;
      file_attachment?: string;
    };
    notes?: string;
  }): Promise<import('@/types').Payable[]> {
    const response = await api.post<import('@/types').Payable[]>('/finance/payables', data);
    cacheManager.invalidate('finance:payables');
    cacheManager.invalidate('finance:dashboard');
    return response.data;
  },

  async updatePayable(id: string, data: Partial<import('@/types').Payable>): Promise<import('@/types').Payable> {
    const response = await api.patch<import('@/types').Payable>(`/finance/payables/${id}`, data);
    cacheManager.invalidate('finance:payables');
    cacheManager.invalidate('finance:dashboard');
    cacheManager.invalidate('documents');
    return response.data;
  },

  async reopenPayable(id: string): Promise<import('@/types').Payable> {
    const response = await api.post<import('@/types').Payable>(`/finance/payables/${id}/reopen`);
    cacheManager.invalidate('finance:payables');
    cacheManager.invalidate('finance:dashboard');
    cacheManager.invalidate('documents');
    return response.data;
  },

  async deletePayable(id: string): Promise<void> {
    await api.delete(`/finance/payables/${id}`);
    cacheManager.invalidate('finance:payables');
    cacheManager.invalidate('finance:dashboard');
    cacheManager.invalidate('documents');
  },

  async createOrUpdatePayableInstrument(payableId: string, data: {
    instrument_type?: string;
    barcode?: string;
    digitable_line?: string;
    pix_code?: string;
    document_number?: string;
    due_date?: string;
    amount?: number;
    file_attachment?: string;
  }): Promise<import('@/types').PaymentInstrument> {
    const response = await api.post<import('@/types').PaymentInstrument>(`/finance/payables/${payableId}/instruments`, data);
    cacheManager.invalidate('finance:payables');
    return response.data;
  },

  async deletePayableInstrument(payableId: string, instrumentId: string): Promise<void> {
    await api.delete(`/finance/payables/${payableId}/instruments/${instrumentId}`);
    cacheManager.invalidate('finance:payables');
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
    cacheManager.invalidate('finance:payables');
    cacheManager.invalidate('finance:bank_accounts');
    cacheManager.invalidate('finance:dashboard');
    cacheManager.invalidate('finance:transactions');
    return response.data;
  },

  async getBankTransactions(bankAccountId?: string, status?: string, forceRefresh = false): Promise<import('@/types').BankTransaction[]> {
    const key = `finance:transactions:${bankAccountId || 'all'}:${status || 'all'}`;
    return cacheManager.fetchWithCache(
      key,
      async () => {
        const params: Record<string, string> = {};
        if (bankAccountId) params.bank_account_id = bankAccountId;
        if (status) params.status = status;
        const response = await api.get<import('@/types').BankTransaction[]>('/finance/transactions', { params });
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
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
    cacheManager.invalidate('finance:transactions');
    cacheManager.invalidate('finance:bank_accounts');
    cacheManager.invalidate('finance:dashboard');
    return response.data;
  },

  async updateBankTransaction(id: string, data: Partial<{
    bank_account_id: string;
    transaction_date: string;
    description: string;
    amount: number;
    transaction_type: 'CREDIT' | 'DEBIT';
    external_id: string | null;
    document_number: string | null;
  }>): Promise<import('@/types').BankTransaction> {
    const response = await api.patch<import('@/types').BankTransaction>(`/finance/transactions/${id}`, data);
    cacheManager.invalidate('finance:transactions');
    cacheManager.invalidate('finance:bank_accounts');
    cacheManager.invalidate('finance:dashboard');
    return response.data;
  },

  async linkTransactionFiscalDocument(transactionId: string, data: {
    fiscal_document_id?: string;
    new_fiscal_document?: any;
  }): Promise<import('@/types').BankTransaction> {
    const response = await api.post<import('@/types').BankTransaction>(`/finance/transactions/${transactionId}/fiscal-document`, data);
    cacheManager.invalidate('finance:transactions');
    cacheManager.invalidate('finance:fiscal');
    cacheManager.invalidate('finance:dashboard');
    cacheManager.invalidate('documents');
    return response.data;
  },

  async unlinkTransactionFiscalDocument(transactionId: string): Promise<import('@/types').BankTransaction> {
    const response = await api.delete<import('@/types').BankTransaction>(`/finance/transactions/${transactionId}/fiscal-document`);
    cacheManager.invalidate('finance:transactions');
    cacheManager.invalidate('finance:fiscal');
    cacheManager.invalidate('finance:dashboard');
    cacheManager.invalidate('documents');
    return response.data;
  },

  async attachTransactionReceipt(transactionId: string, data: {
    file_name: string;
    file_url: string;
    mime_type?: string;
    payable_id?: string;
  }): Promise<import('@/types').BankTransaction> {
    const response = await api.post<import('@/types').BankTransaction>(`/finance/transactions/${transactionId}/receipt`, data);
    cacheManager.invalidate('finance:transactions');
    cacheManager.invalidate('finance:payables');
    cacheManager.invalidate('finance:dashboard');
    cacheManager.invalidate('documents');
    return response.data;
  },

  async removeTransactionReceipt(transactionId: string): Promise<import('@/types').BankTransaction> {
    const response = await api.delete<import('@/types').BankTransaction>(`/finance/transactions/${transactionId}/receipt`);
    cacheManager.invalidate('finance:transactions');
    cacheManager.invalidate('finance:payables');
    cacheManager.invalidate('finance:dashboard');
    cacheManager.invalidate('documents');
    return response.data;
  },

  async reconcileTransaction(data: {
    bank_transaction_id: string;
    payment_id?: string;
    receipt_id?: string;
    notes?: string;
  }): Promise<import('@/types').Reconciliation> {
    const response = await api.post<import('@/types').Reconciliation>('/finance/reconciliations', data);
    cacheManager.invalidate('finance:transactions');
    cacheManager.invalidate('finance:dashboard');
    return response.data;
  },

  async getReceivables(status?: string, forceRefresh = false): Promise<import('@/types').Receivable[]> {
    const key = `finance:receivables:${status || 'all'}`;
    return cacheManager.fetchWithCache(
      key,
      async () => {
        const params = status ? { status } : {};
        const response = await api.get<import('@/types').Receivable[]>('/finance/receivables', { params });
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async createReceivable(data: {
    customer_id?: string;
    customer_name: string;
    customer_document?: string;
    description: string;
    original_amount: number;
    issue_date: string;
    due_date: string;
    payment_method_expected?: string;
    cost_center_id?: string;
    financial_category_id?: string;
    fiscal_document_id?: string;
    notes?: string;
  }): Promise<import('@/types').Receivable> {
    const response = await api.post<import('@/types').Receivable>('/finance/receivables', data);
    cacheManager.invalidate('finance:receivables');
    cacheManager.invalidate('finance:dashboard');
    return response.data;
  },

  async updateReceivable(id: string, data: Partial<import('@/types').Receivable>): Promise<import('@/types').Receivable> {
    const response = await api.patch<import('@/types').Receivable>(`/finance/receivables/${id}`, data);
    cacheManager.invalidate('finance:receivables');
    cacheManager.invalidate('finance:dashboard');
    cacheManager.invalidate('documents');
    return response.data;
  },

  async reopenReceivable(id: string): Promise<import('@/types').Receivable> {
    const response = await api.post<import('@/types').Receivable>(`/finance/receivables/${id}/reopen`);
    cacheManager.invalidate('finance:receivables');
    cacheManager.invalidate('finance:dashboard');
    cacheManager.invalidate('documents');
    return response.data;
  },

  async deleteReceivable(id: string): Promise<void> {
    await api.delete(`/finance/receivables/${id}`);
    cacheManager.invalidate('finance:receivables');
    cacheManager.invalidate('finance:dashboard');
    cacheManager.invalidate('documents');
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
    cacheManager.invalidate('finance:receivables');
    cacheManager.invalidate('finance:bank_accounts');
    cacheManager.invalidate('finance:dashboard');
    cacheManager.invalidate('finance:transactions');
    return response.data;
  }
};

// ==============================================================================
// 7. FATURAMENTO (Billing)
// ==============================================================================

export const billingService = {
  async getRequests(forceRefresh = false): Promise<import('@/types').BusinessDocument[]> {
    return cacheManager.fetchWithCache(
      'billing:requests',
      async () => {
        const response = await api.get<import('@/types').BusinessDocument[]>('/billing/requests');
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async getInvoices(forceRefresh = false): Promise<import('@/types').Invoice[]> {
    return cacheManager.fetchWithCache(
      'billing:invoices',
      async () => {
        const response = await api.get<import('@/types').Invoice[]>('/billing/invoices');
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async getInvoice(id: string): Promise<import('@/types').Invoice> {
    const response = await api.get<import('@/types').Invoice>(`/billing/invoices/${id}`);
    return response.data;
  },

  async issueRequest(requestId: string, data: {
    issue_date: string;
    due_date: string;
    installments_count?: number;
    tax_amount?: number;
    notes?: string;
    generate_receivables_in_finance?: boolean;
    generate_outbound_fiscal_document?: boolean;
    fiscal_document_type?: 'NFE' | 'NFSE' | 'NFCE' | 'OUTRO';
    fiscal_document_number?: string;
    fiscal_series?: string;
    fiscal_access_key?: string;
    fiscal_file_attachment?: string;
    boleto_file_attachment?: string;
    boleto_digitable_line?: string;
    items?: Array<{ sales_order_item_id: string; quantity: number }>;
  }): Promise<import('@/types').Invoice> {
    const response = await api.post<import('@/types').Invoice>(`/billing/requests/${requestId}/issue`, data);
    cacheManager.invalidate('billing:requests');
    cacheManager.invalidate('billing:invoices');
    cacheManager.invalidate('sales:orders');
    cacheManager.invalidate('sales:order:');
    cacheManager.invalidate('finance:receivables');
    cacheManager.invalidate('finance:dashboard');
    cacheManager.invalidate('finance:fiscal');
    cacheManager.invalidate('documents');
    return response.data;
  },

  async cancelRequest(requestId: string, reason: string): Promise<import('@/types').BusinessDocument> {
    const response = await api.post<import('@/types').BusinessDocument>(`/billing/requests/${requestId}/cancel`, { reason });
    cacheManager.invalidate('billing:requests');
    cacheManager.invalidate('sales:orders');
    cacheManager.invalidate('sales:order:');
    cacheManager.invalidate('documents');
    return response.data;
  },

  async updateInvoice(id: string, data: {
    customer_name?: string;
    customer_document?: string | null;
    issue_date?: string;
    due_date?: string;
    notes?: string | null;
  }): Promise<import('@/types').Invoice> {
    const response = await api.patch<import('@/types').Invoice>(`/billing/invoices/${id}`, data);
    cacheManager.invalidate('billing:invoices');
    cacheManager.invalidate('finance:receivables');
    cacheManager.invalidate('documents');
    return response.data;
  },

  async cancelInvoice(id: string, reason: string): Promise<import('@/types').Invoice> {
    const response = await api.post<import('@/types').Invoice>(`/billing/invoices/${id}/cancel`, { reason });
    cacheManager.invalidate('billing:invoices');
    cacheManager.invalidate('billing:requests');
    cacheManager.invalidate('billing:fiscal');
    cacheManager.invalidate('sales:orders');
    cacheManager.invalidate('sales:order:');
    cacheManager.invalidate('finance:receivables');
    cacheManager.invalidate('finance:fiscal');
    cacheManager.invalidate('documents');
    return response.data;
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
    generate_outbound_fiscal_document?: boolean;
    fiscal_document_type?: 'NFE' | 'NFSE' | 'NFCE' | 'OUTRO';
    fiscal_document_number?: string;
    fiscal_series?: string;
    fiscal_access_key?: string;
    fiscal_file_attachment?: string;
    boleto_file_attachment?: string;
    boleto_digitable_line?: string;
    items?: Array<{ sales_order_item_id: string; quantity: number }>;
  }): Promise<import('@/types').Invoice> {
    const response = await api.post<import('@/types').Invoice>('/billing/invoices', data);
    cacheManager.invalidate('billing:invoices');
    cacheManager.invalidate('finance:receivables');
    cacheManager.invalidate('finance:dashboard');
    cacheManager.invalidate('finance:fiscal');
    cacheManager.invalidate('billing:fiscal');
    return response.data;
  },

  async getFiscalDocuments(type?: 'INBOUND' | 'OUTBOUND', forceRefresh = false): Promise<import('@/types').FiscalDocument[]> {
    return cacheManager.fetchWithCache(
      `billing:fiscal:${type || 'all'}`,
      async () => {
        const params = type ? { type } : {};
        const response = await api.get<import('@/types').FiscalDocument[]>('/finance/fiscal-documents', { params });
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  }
};

// ==============================================================================
// 8. CRM & RELACIONAMENTO COM CLIENTES (CRM)
// ==============================================================================

export const crmService = {
  async getStages(forceRefresh = false): Promise<import('@/types').CRMStage[]> {
    return cacheManager.fetchWithCache(
      'crm:stages',
      async () => {
        const response = await api.get<import('@/types').CRMStage[]>('/crm/stages');
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async createStage(data: {
    name: string;
    code: string;
    color?: string;
    order?: number;
    is_won?: boolean;
    is_lost?: boolean;
  }): Promise<import('@/types').CRMStage> {
    const response = await api.post<import('@/types').CRMStage>('/crm/stages', data);
    cacheManager.invalidate('crm:stages');
    return response.data;
  },

  async updateStage(stageId: string, data: Partial<import('@/types').CRMStage>): Promise<import('@/types').CRMStage> {
    const response = await api.put<import('@/types').CRMStage>(`/crm/stages/${stageId}`, data);
    cacheManager.invalidate('crm:stages');
    return response.data;
  },

  async deleteStage(stageId: string): Promise<{ message: string }> {
    const response = await api.delete<{ message: string }>(`/crm/stages/${stageId}`);
    cacheManager.invalidate('crm:stages');
    return response.data;
  },

  async getLeads(status?: string, forceRefresh = false): Promise<import('@/types').Lead[]> {
    const key = `crm:leads:${status || 'all'}`;
    return cacheManager.fetchWithCache(
      key,
      async () => {
        const params = status ? { status } : {};
        const response = await api.get<import('@/types').Lead[]>('/crm/leads', { params });
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async createLead(data: {
    name: string;
    company_name?: string;
    email?: string;
    phone?: string;
    secondary_phone?: string;
    position?: string;
    segment?: string;
    address_city?: string;
    address_state?: string;
    annual_revenue?: number;
    source?: string;
    contact_origin_id?: string;
    status?: string;
    notes?: string;
    assigned_to_id?: string;
    customer_id?: string;
    contact_id?: string;
    document?: string;
    person_type?: string;
  }): Promise<import('@/types').Lead> {
    const response = await api.post<import('@/types').Lead>('/crm/leads', data);
    cacheManager.invalidate('crm:leads');
    return response.data;
  },

  async updateLead(leadId: string, data: Partial<import('@/types').Lead>): Promise<import('@/types').Lead> {
    const response = await api.put<import('@/types').Lead>(`/crm/leads/${leadId}`, data);
    cacheManager.invalidate('crm:leads');
    return response.data;
  },

  async deleteLead(leadId: string): Promise<{ message: string }> {
    const response = await api.delete<{ message: string }>(`/crm/leads/${leadId}`);
    cacheManager.invalidate('crm:leads');
    return response.data;
  },

  async convertLeadToCustomer(leadId: string): Promise<import('@/types').Customer> {
    const response = await api.post<import('@/types').Customer>(`/crm/leads/${leadId}/convert-customer`);
    cacheManager.invalidate('crm:leads');
    cacheManager.invalidate('sales:customers');
    return response.data;
  },

  async convertLeadToOpportunity(leadId: string): Promise<import('@/types').Opportunity> {
    const response = await api.post<import('@/types').Opportunity>(`/crm/leads/${leadId}/convert-opportunity`);
    cacheManager.invalidate('crm:leads');
    cacheManager.invalidate('crm:opportunities');
    cacheManager.invalidate('sales:customers');
    return response.data;
  },

  async convertContactToLead(contactId: string): Promise<import('@/types').Lead> {
    const response = await api.post<import('@/types').Lead>(`/crm/contacts/${contactId}/convert-lead`);
    cacheManager.invalidate('crm:leads');
    return response.data;
  },

  async convertContactToOpportunity(contactId: string): Promise<import('@/types').Opportunity> {
    const response = await api.post<import('@/types').Opportunity>(`/crm/contacts/${contactId}/convert-opportunity`);
    cacheManager.invalidate('crm:opportunities');
    cacheManager.invalidate('crm:interactions');
    cacheManager.invalidate('sales:customers');
    return response.data;
  },

  async getOpportunities(stage?: string, forceRefresh = false): Promise<import('@/types').Opportunity[]> {
    const key = `crm:opportunities:${stage || 'all'}`;
    return cacheManager.fetchWithCache(
      key,
      async () => {
        const params = stage ? { stage } : {};
        const response = await api.get<import('@/types').Opportunity[]>('/crm/opportunities', { params });
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async getOpportunity(oppId: string, forceRefresh = false): Promise<import('@/types').Opportunity> {
    return cacheManager.fetchWithCache(
      `crm:opportunity:${oppId}`,
      async () => {
        const response = await api.get<import('@/types').Opportunity>(`/crm/opportunities/${oppId}`);
        return response.data;
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async createOpportunity(data: {
    title: string;
    customer_name: string;
    customer_id?: string;
    contact_id?: string;
    estimated_amount: number;
    probability_percent?: number;
    expected_closing_date?: string;
    stage?: string;
    priority?: 'LOW' | 'MEDIUM' | 'HIGH';
    lead_id?: string;
    loss_reason?: string;
    assigned_to_id?: string;
  }): Promise<import('@/types').Opportunity> {
    const response = await api.post<import('@/types').Opportunity>('/crm/opportunities', data);
    cacheManager.invalidate('crm:opportunities');
    return response.data;
  },

  async updateOpportunity(oppId: string, data: Partial<import('@/types').Opportunity>): Promise<import('@/types').Opportunity> {
    const response = await api.put<import('@/types').Opportunity>(`/crm/opportunities/${oppId}`, data);
    cacheManager.invalidate('crm:opportunities');
    cacheManager.invalidate(`crm:opportunity:${oppId}`);
    return response.data;
  },

  async updateOpportunityStage(oppId: string, stage: string, loss_reason?: string): Promise<import('@/types').Opportunity> {
    const response = await api.patch<import('@/types').Opportunity>(`/crm/opportunities/${oppId}/stage`, null, {
      params: { stage, loss_reason }
    });
    cacheManager.invalidate('crm:opportunities');
    cacheManager.invalidate(`crm:opportunity:${oppId}`);
    return response.data;
  },

  async deleteOpportunity(oppId: string): Promise<{ message: string }> {
    const response = await api.delete<{ message: string }>(`/crm/opportunities/${oppId}`);
    cacheManager.invalidate('crm:opportunities');
    return response.data;
  },

  async getOpportunityQuotations(oppId: string, forceRefresh = false): Promise<import('@/types').SalesQuote[]> {
    return cacheManager.fetchWithCache(
      `crm:opportunity:${oppId}:quotes`,
      async () => {
        const response = await api.get<import('@/types').SalesQuote[]>(`/crm/opportunities/${oppId}/quotations`);
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async getInteractions(leadId?: string, oppId?: string, forceRefresh = false): Promise<import('@/types').CustomerInteraction[]> {
    const key = `crm:interactions:${leadId || 'all'}:${oppId || 'all'}`;
    return cacheManager.fetchWithCache(
      key,
      async () => {
        const params: any = {};
        if (leadId) params.lead_id = leadId;
        if (oppId) params.opportunity_id = oppId;
        const response = await api.get<import('@/types').CustomerInteraction[]>('/crm/interactions', { params });
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async createInteraction(data: {
    lead_id?: string;
    opportunity_id?: string;
    interaction_type: string;
    summary: string;
    details?: string;
    interaction_date?: string;
    status?: 'SCHEDULED' | 'COMPLETED' | 'CANCELLED';
    responsible_id?: string;
  }): Promise<import('@/types').CustomerInteraction> {
    const response = await api.post<import('@/types').CustomerInteraction>('/crm/interactions', data);
    cacheManager.invalidate('crm:interactions');
    return response.data;
  },

  async updateInteraction(
    interactionId: string,
    data: {
      interaction_type?: 'CALL' | 'MEETING' | 'EMAIL' | 'WHATSAPP' | 'NOTE';
      summary?: string;
      details?: string | null;
      interaction_date?: string;
      status?: 'SCHEDULED' | 'COMPLETED' | 'CANCELLED' | null;
      responsible_id?: string | null;
    }
  ): Promise<import('@/types').CustomerInteraction> {
    const response = await api.patch<import('@/types').CustomerInteraction>(
      `/crm/interactions/${interactionId}`,
      data
    );
    cacheManager.invalidate('crm:interactions');
    return response.data;
  },


  async createQuoteFromOpportunity(oppId: string, items?: any[]): Promise<import('@/types').SalesQuote> {
    const response = await api.post<import('@/types').SalesQuote>(`/crm/opportunities/${oppId}/create-quote`, items ? { items } : {});
    cacheManager.invalidate('crm:opportunities');
    cacheManager.invalidate(`crm:opportunity:${oppId}`);
    cacheManager.invalidate('sales:quotes');
    return response.data;
  },

  async convertQuoteToOrder(quoteId: string): Promise<import('@/types').SalesOrder> {
    return salesService.convertQuoteToOrder(quoteId);
  }
};

// ==============================================================================
// 9. VENDAS & FRENTE DE CAIXA (Sales / POS)
// ==============================================================================

export const salesService = {
  async getCustomerCredit(
    customerId: string,
    proposedOrderAmount = 0,
    excludeOrderId?: string
  ): Promise<import('@/types').CustomerCreditAnalysis> {
    const response = await api.get<import('@/types').CustomerCreditAnalysis>(
      `/sales/customers/${customerId}/credit`,
      {
        params: {
          proposed_order_amount: proposedOrderAmount,
          ...(excludeOrderId ? { exclude_order_id: excludeOrderId } : {})
        }
      }
    );
    return response.data;
  },

  async getCreditApprovals(
    status?: string,
    forceRefresh = false
  ): Promise<import('@/types').CreditApprovalRequest[]> {
    const key = `sales:credit-approvals:${status || 'all'}`;
    return cacheManager.fetchWithCache(
      key,
      async () => {
        const response = await api.get<import('@/types').CreditApprovalRequest[]>(
          '/sales/credit-approvals',
          { params: status ? { status } : {} }
        );
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async requestCreditApproval(
    orderId: string,
    reason: string
  ): Promise<import('@/types').CreditApprovalRequest> {
    const response = await api.post<import('@/types').CreditApprovalRequest>(
      `/sales/orders/${orderId}/credit-approval`,
      { reason }
    );
    cacheManager.invalidate('sales:orders');
    cacheManager.invalidate('sales:credit-approvals');
    return response.data;
  },

  async decideCreditApproval(
    approvalId: string,
    approved: boolean,
    reason: string
  ): Promise<import('@/types').CreditApprovalRequest> {
    const response = await api.post<import('@/types').CreditApprovalRequest>(
      `/sales/credit-approvals/${approvalId}/decision`,
      { approved, reason }
    );
    cacheManager.invalidate('sales:orders');
    cacheManager.invalidate('sales:credit-approvals');
    return response.data;
  },

  async getCommercialApprovals(
    status?: string,
    forceRefresh = false
  ): Promise<import('@/types').CommercialApprovalRequest[]> {
    const key = `sales:commercial-approvals:${status || 'all'}`;
    return cacheManager.fetchWithCache(
      key,
      async () => {
        const response = await api.get<import('@/types').CommercialApprovalRequest[]>(
          '/sales/commercial-approvals',
          { params: status ? { status } : {} }
        );
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async decideCommercialApproval(
    approvalId: string,
    approved: boolean,
    reason: string
  ): Promise<import('@/types').CommercialApprovalRequest> {
    const response = await api.post<import('@/types').CommercialApprovalRequest>(
      `/sales/commercial-approvals/${approvalId}/decision`,
      { approved, reason }
    );
    cacheManager.invalidate('sales:quotes');
    cacheManager.invalidate('sales:orders');
    cacheManager.invalidate('sales:commercial-approvals');
    return response.data;
  },

  async getCommercialSettings(forceRefresh = false): Promise<import('@/types').CommercialSettings> {
    return cacheManager.fetchWithCache(
      'sales:settings',
      async () => {
        const response = await api.get<import('@/types').CommercialSettings>('/sales/settings');
        return response.data;
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async updateCommercialSettings(
    data: Partial<import('@/types').CommercialSettings>
  ): Promise<import('@/types').CommercialSettings> {
    const response = await api.put<import('@/types').CommercialSettings>('/sales/settings', data);
    cacheManager.invalidate('sales:settings');
    return response.data;
  },

  async getQuotes(opportunityIdOrForce?: string | boolean, forceRefresh = false): Promise<import('@/types').SalesQuote[]> {
    const oppId = typeof opportunityIdOrForce === 'string' ? opportunityIdOrForce : undefined;
    const force = typeof opportunityIdOrForce === 'boolean' ? opportunityIdOrForce : forceRefresh;
    const key = `sales:quotes:${oppId || 'all'}`;
    return cacheManager.fetchWithCache(
      key,
      async () => {
        const params = oppId ? { opportunity_id: oppId } : {};
        const response = await api.get<import('@/types').SalesQuote[]>('/sales/quotes', { params });
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      force
    );
  },

  async getQuote(quoteId: string, forceRefresh = false): Promise<import('@/types').SalesQuote> {
    return cacheManager.fetchWithCache(
      `sales:quote:${quoteId}`,
      async () => {
        const response = await api.get<import('@/types').SalesQuote>(`/sales/quotes/${quoteId}`);
        return response.data;
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async createQuote(data: {
    customer_id?: string;
    opportunity_id?: string;
    customer_name: string;
    customer_document?: string;
    customer_email?: string;
    customer_phone?: string;
    payment_terms?: string;
    valid_until?: string;
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
    cacheManager.invalidate('sales:quotes');
    cacheManager.invalidate('crm:opportunities');
    return response.data;
  },

  async updateQuote(quoteId: string, data: Partial<import('@/types').SalesQuote>): Promise<import('@/types').SalesQuote> {
    const response = await api.put<import('@/types').SalesQuote>(`/sales/quotes/${quoteId}`, data);
    cacheManager.invalidate('sales:quotes');
    cacheManager.invalidate(`sales:quote:${quoteId}`);
    cacheManager.invalidate('crm:opportunities');
    return response.data;
  },

  async updateQuoteStatus(quoteId: string, status: string): Promise<import('@/types').SalesQuote> {
    const response = await api.patch<import('@/types').SalesQuote>(`/sales/quotes/${quoteId}/status`, null, {
      params: { new_status: status }
    });
    cacheManager.invalidate('sales:quotes');
    cacheManager.invalidate(`sales:quote:${quoteId}`);
    cacheManager.invalidate('crm:opportunities');
    return response.data;
  },

  async convertQuoteToOrder(quoteId: string): Promise<import('@/types').SalesOrder> {
    const response = await api.post<import('@/types').SalesOrder>(`/sales/quotes/${quoteId}/convert`);
    cacheManager.invalidate('sales:quotes');
    cacheManager.invalidate(`sales:quote:${quoteId}`);
    cacheManager.invalidate('sales:orders');
    cacheManager.invalidate('crm:opportunities');
    return response.data;
  },

  async cancelQuote(quoteId: string, reason: string): Promise<import('@/types').SalesQuote> {
    const response = await api.post<import('@/types').SalesQuote>(`/sales/quotes/${quoteId}/cancel`, { reason });
    cacheManager.invalidate('sales:quotes');
    cacheManager.invalidate(`sales:quote:${quoteId}`);
    cacheManager.invalidate('crm:opportunities');
    cacheManager.invalidate(`documents:chain:SALES_QUOTE:${quoteId}`);
    return response.data;
  },

  async deleteQuote(quoteId: string, permanent: boolean = true): Promise<{ message: string }> {
    const response = await api.delete<{ message: string }>(`/sales/quotes/${quoteId}`, {
      params: { permanent }
    });
    cacheManager.invalidate('sales:quotes');
    cacheManager.invalidate(`sales:quote:${quoteId}`);
    cacheManager.invalidate('crm:opportunities');
    cacheManager.invalidate(`documents:chain:SALES_QUOTE:${quoteId}`);
    return response.data;
  },

  async getOrders(forceRefresh = false): Promise<import('@/types').SalesOrder[]> {
    return cacheManager.fetchWithCache(
      'sales:orders',
      async () => {
        const response = await api.get<import('@/types').SalesOrder[]>('/sales/orders');
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async getOrder(orderId: string, forceRefresh = false): Promise<import('@/types').SalesOrder> {
    return cacheManager.fetchWithCache(
      `sales:order:${orderId}`,
      async () => {
        const response = await api.get<import('@/types').SalesOrder>(`/sales/orders/${orderId}`);
        return response.data;
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async createOrder(data: {
    customer_id?: string;
    sales_quote_id?: string;
    opportunity_id?: string;
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
    cacheManager.invalidate('sales:orders');
    cacheManager.invalidate('crm:opportunities');
    cacheManager.invalidate('sales:quotes');
    cacheManager.invalidate('inventory');
    cacheManager.invalidate('sales:analytics');
    return response.data;
  },

  async updateOrderStatus(orderId: string, data: Partial<import('@/types').SalesOrder>): Promise<import('@/types').SalesOrder> {
    const response = await api.patch<import('@/types').SalesOrder>(`/sales/orders/${orderId}/status`, data);
    cacheManager.invalidate('sales:orders');
    cacheManager.invalidate(`sales:order:${orderId}`);
    cacheManager.invalidate('sales:analytics');
    cacheManager.invalidate(`documents:chain:SALES_ORDER:${orderId}`);
    return response.data;
  },

  async requestOrderBilling(orderId: string): Promise<import('@/types').SalesOrder> {
    const response = await api.post<import('@/types').SalesOrder>(`/sales/orders/${orderId}/request-billing`);
    cacheManager.invalidate('sales:orders');
    cacheManager.invalidate(`sales:order:${orderId}`);
    cacheManager.invalidate('billing:requests');
    cacheManager.invalidate('sales:analytics');
    cacheManager.invalidate(`documents:chain:SALES_ORDER:${orderId}`);
    return response.data;
  },

  async deleteOrder(orderId: string, reason?: string, permanent: boolean = false): Promise<{ message: string }> {
    const response = await api.delete<{ message: string }>(`/sales/orders/${orderId}`, {
      params: { ...(reason ? { reason } : {}), permanent },
    });
    cacheManager.invalidate('sales:orders');
    cacheManager.invalidate(`sales:order:${orderId}`);
    cacheManager.invalidate('inventory');
    cacheManager.invalidate('sales:analytics');
    cacheManager.invalidate(`documents:chain:SALES_ORDER:${orderId}`);
    return response.data;
  },

  async getPOSSessions(forceRefresh = false): Promise<import('@/types').POSSession[]> {
    return cacheManager.fetchWithCache(
      'sales:pos:sessions',
      async () => {
        const response = await api.get<import('@/types').POSSession[]>('/sales/pos/sessions');
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async getActivePOSSession(): Promise<import('@/types').POSSession | null> {
    const response = await api.get<import('@/types').POSSession | null>('/sales/pos/sessions/active');
    return response.data || null;
  },

  async openPOSSession(data: {
    pos_terminal?: string;
    opening_cash?: number;
  }): Promise<import('@/types').POSSession> {
    const response = await api.post<import('@/types').POSSession>('/sales/pos/sessions', data);
    cacheManager.invalidate('sales:pos:sessions');
    return response.data;
  },

  async closePOSSession(sessionId: string, data: { closing_cash?: number }): Promise<import('@/types').POSSession> {
    const response = await api.post<import('@/types').POSSession>(`/sales/pos/sessions/${sessionId}/close`, data);
    cacheManager.invalidate('sales:pos:sessions');
    return response.data;
  },

  async getPOSSales(forceRefresh = false): Promise<import('@/types').POSSale[]> {
    return cacheManager.fetchWithCache(
      'sales:pos:sales',
      async () => {
        const response = await api.get<import('@/types').POSSale[]>('/sales/pos/sales');
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async processPOSSale(data: {
    pos_session_id?: string;
    customer_id?: string;
    customer_name?: string;
    customer_document?: string;
    discount_amount?: number;
    payment_method: string;
    total_amount?: number;
    items: {
      product_id: string;
      quantity: number;
      unit_price: number;
    }[];
  }): Promise<import('@/types').POSSale> {
    const response = await api.post<import('@/types').POSSale>('/sales/pos/sales', data);
    cacheManager.invalidate('sales:pos:sales');
    cacheManager.invalidate('sales:orders');
    cacheManager.invalidate('inventory');
    cacheManager.invalidate('sales:analytics');
    return response.data;
  },

  async recordPOSSale(data: any): Promise<import('@/types').POSSale> {
    return this.processPOSSale(data);
  },

  async recordCashMovement(data: {
    pos_session_id: string;
    movement_type: 'SANGRIA' | 'SUPRIMENTO';
    amount: number;
    reason: string;
  }): Promise<import('@/types').POSCashMovement> {
    const response = await api.post<import('@/types').POSCashMovement>('/sales/pos/cash-movements', data);
    cacheManager.invalidate('sales:pos:cash-movements');
    cacheManager.invalidate('sales:pos:sessions');
    return response.data;
  },

  async getCashMovements(sessionId?: string, forceRefresh = false): Promise<import('@/types').POSCashMovement[]> {
    const key = `sales:pos:cash-movements:${sessionId || 'all'}`;
    return cacheManager.fetchWithCache(
      key,
      async () => {
        const params = sessionId ? { session_id: sessionId } : {};
        const response = await api.get<import('@/types').POSCashMovement[]>('/sales/pos/cash-movements', { params });
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  // --- CLIENTES ---
  async getCustomers(searchOrForce?: string | boolean, forceRefresh = false): Promise<import('@/types').Customer[]> {
    const search = typeof searchOrForce === 'string' ? searchOrForce : undefined;
    const force = typeof searchOrForce === 'boolean' ? searchOrForce : forceRefresh;
    const key = `sales:customers:${search || 'all'}`;
    return cacheManager.fetchWithCache(
      key,
      async () => {
        const params = search ? { search } : {};
        const response = await api.get<import('@/types').Customer[]>('/sales/customers', { params });
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      force
    );
  },

  async getCustomer(customerId: string, forceRefresh = false): Promise<import('@/types').Customer> {
    return cacheManager.fetchWithCache(
      `sales:customer:${customerId}`,
      async () => {
        const response = await api.get<import('@/types').Customer>(`/sales/customers/${customerId}`);
        return response.data;
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async createCustomer(data: Partial<import('@/types').Customer>): Promise<import('@/types').Customer> {
    const response = await api.post<import('@/types').Customer>('/sales/customers', data);
    cacheManager.invalidate('sales:customers');
    return response.data;
  },

  async updateCustomer(customerId: string, data: Partial<import('@/types').Customer>): Promise<import('@/types').Customer> {
    const response = await api.put<import('@/types').Customer>(`/sales/customers/${customerId}`, data);
    cacheManager.invalidate('sales:customers');
    cacheManager.invalidate(`sales:customer:${customerId}`);
    return response.data;
  },

  async deleteCustomer(customerId: string): Promise<{ message: string }> {
    const response = await api.delete<{ message: string }>(`/sales/customers/${customerId}`);
    cacheManager.invalidate('sales:customers');
    return response.data;
  },


  // --- METAS COMERCIAIS ---
  async getSalesGoals(year?: number, forceRefresh = false): Promise<import('@/types').SalesGoal[]> {
    const key = `sales:goals:${year || 'current'}`;
    return cacheManager.fetchWithCache(
      key,
      async () => {
        const params = year ? { year } : {};
        const response = await api.get<import('@/types').SalesGoal[]>('/sales/goals', { params });
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async createSalesGoal(data: { user_id?: string; seller_name?: string; month: number; year: number; target_amount: number; commission_percent?: number }): Promise<import('@/types').SalesGoal> {
    const response = await api.post<import('@/types').SalesGoal>('/sales/goals', data);
    cacheManager.invalidate('sales:goals');
    cacheManager.invalidate('sales:analytics');
    return response.data;
  },

  async deleteSalesGoal(goalId: string): Promise<{ message: string }> {
    const response = await api.delete<{ message: string }>(`/sales/goals/${goalId}`);
    cacheManager.invalidate('sales:goals');
    cacheManager.invalidate('sales:analytics');
    return response.data;
  },

  // --- TABELAS DE PREÇOS ---
  async getPriceTables(forceRefresh = false): Promise<import('@/types').PriceTable[]> {
    return cacheManager.fetchWithCache(
      'sales:price-tables',
      async () => {
        const response = await api.get<import('@/types').PriceTable[]>('/sales/price-tables');
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async createPriceTable(data: Partial<import('@/types').PriceTable>): Promise<import('@/types').PriceTable> {
    const response = await api.post<import('@/types').PriceTable>('/sales/price-tables', data);
    cacheManager.invalidate('sales:price-tables');
    return response.data;
  },

  async deletePriceTable(tableId: string): Promise<{ message: string }> {
    const response = await api.delete<{ message: string }>(`/sales/price-tables/${tableId}`);
    cacheManager.invalidate('sales:price-tables');
    return response.data;
  },

  // --- PÓS-VENDA / DEVOLUÇÕES ---
  async getSalesReturns(forceRefresh = false): Promise<import('@/types').SalesReturn[]> {
    return cacheManager.fetchWithCache(
      'sales:returns',
      async () => {
        const response = await api.get<import('@/types').SalesReturn[]>('/sales/returns');
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async processSalesReturn(data: {
    sales_order_id?: string;
    pos_sale_id?: string;
    customer_id?: string;
    customer_name: string;
    return_type: string;
    reason: string;
    restock_items?: boolean;
    items: {
      product_id: string;
      quantity: number;
      unit_price: number;
      condition?: 'GOOD' | 'DAMAGED';
    }[];
  }): Promise<import('@/types').SalesReturn> {
    const response = await api.post<import('@/types').SalesReturn>('/sales/returns', data);
    cacheManager.invalidate('sales:returns');
    cacheManager.invalidate('inventory');
    cacheManager.invalidate('sales:analytics');
    return response.data;
  },

  async createSalesReturn(data: any): Promise<import('@/types').SalesReturn> {
    return this.processSalesReturn(data);
  },

  async deleteSalesReturn(returnId: string): Promise<{ message: string }> {
    const response = await api.delete<{ message: string }>(`/sales/returns/${returnId}`);
    cacheManager.invalidate('sales:returns');
    cacheManager.invalidate('inventory');
    cacheManager.invalidate('sales:analytics');
    return response.data;
  },

  // --- INDICADORES / ANALYTICS ---
  async getSalesAnalytics(forceRefresh = false): Promise<import('@/types').SalesAnalytics> {
    return cacheManager.fetchWithCache(
      'sales:analytics',
      async () => {
        const response = await api.get<import('@/types').SalesAnalytics>('/sales/analytics');
        return response.data;
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  },

  async getAnalytics(forceRefresh = false): Promise<import('@/types').SalesAnalytics> {
    return this.getSalesAnalytics(forceRefresh);
  },

  // --- FORÇA DE VENDAS / VENDEDORES ---
  async getSellers(forceRefresh = false): Promise<import('@/types').SellerResponse[]> {
    return cacheManager.fetchWithCache(
      'sales:sellers',
      async () => {
        const response = await api.get<import('@/types').SellerResponse[]>('/sales/sellers');
        return Array.isArray(response.data) ? response.data : [];
      },
      DEFAULT_CACHE_TTL,
      forceRefresh
    );
  }
};

// ==============================================================================
// 12. PROJETOS & OPERAÇÕES SERVICE
// Função utilitária para extrair listas tanto de arrays diretos quanto de PaginatedResponse ({ items: [...] })
const unwrapProjectsList = (data: any): any[] => {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.items)) return data.items;
  return [];
};

export const projectsService = {
  // --- PROJETOS ---
  async getProjects(params?: import('@/types').ProjectsFilterParams, forceRefresh = false): Promise<import('@/types').Project[]> {
    const key = `projects:list:${JSON.stringify(params || {})}`;
    return cacheManager.fetchWithCache(
      key,
      async () => {
        const response = await api.get('/projects/', { params });
        return unwrapProjectsList(response.data);
      },
      30 * 1000, // 30s cache
      forceRefresh
    );
  },

  async getProject(id: string): Promise<import('@/types').Project> {
    const response = await api.get<import('@/types').Project>(`/projects/${id}`);
    return response.data;
  },

  async createProject(payload: import('@/types').ProjectCreatePayload): Promise<import('@/types').Project> {
    const response = await api.post<import('@/types').Project>('/projects/', payload);
    cacheManager.invalidate('projects:');
    return response.data;
  },

  async updateProject(id: string, payload: Partial<import('@/types').ProjectCreatePayload>): Promise<import('@/types').Project> {
    const response = await api.put<import('@/types').Project>(`/projects/${id}`, payload);
    cacheManager.invalidate('projects:');
    return response.data;
  },

  async changeProjectStage(id: string, stage_id: string, notes?: string): Promise<import('@/types').Project> {
    const response = await api.post<import('@/types').Project>(`/projects/${id}/stage`, { stage_id, to_stage_id: stage_id, notes });
    cacheManager.invalidate('projects:');
    return response.data;
  },

  async addProjectMember(id: string, payload: { user_id: string; role: string }): Promise<import('@/types').ProjectMember> {
    const response = await api.post<import('@/types').ProjectMember>(`/projects/${id}/members`, payload);
    cacheManager.invalidate('projects:');
    return response.data;
  },

  async removeProjectMember(id: string, member_id: string): Promise<void> {
    await api.delete(`/projects/${id}/members/${member_id}`);
    cacheManager.invalidate('projects:');
  },

  async deleteProject(id: string): Promise<void> {
    await api.delete(`/projects/${id}`);
    cacheManager.invalidate('projects:');
  },

  // --- ORDENS DE SERVIÇO ---
  async getWorkOrders(params?: import('@/types').WorkOrdersFilterParams, forceRefresh = false): Promise<import('@/types').WorkOrder[]> {
    const key = `projects:work_orders:${JSON.stringify(params || {})}`;
    return cacheManager.fetchWithCache(
      key,
      async () => {
        const response = await api.get('/projects/orders', { params });
        return unwrapProjectsList(response.data);
      },
      30 * 1000,
      forceRefresh
    );
  },

  async getWorkOrder(id: string): Promise<import('@/types').WorkOrder> {
    const response = await api.get<import('@/types').WorkOrder>(`/projects/orders/${id}`);
    return response.data;
  },

  async createWorkOrder(payload: import('@/types').WorkOrderCreatePayload): Promise<import('@/types').WorkOrder> {
    const response = await api.post<import('@/types').WorkOrder>('/projects/orders', payload);
    cacheManager.invalidate('projects:');
    return response.data;
  },

  async updateWorkOrder(id: string, payload: Partial<import('@/types').WorkOrderCreatePayload>): Promise<import('@/types').WorkOrder> {
    const response = await api.put<import('@/types').WorkOrder>(`/projects/orders/${id}`, payload);
    cacheManager.invalidate('projects:');
    return response.data;
  },

  async changeWorkOrderStatus(id: string, status: string): Promise<import('@/types').WorkOrder> {
    const response = await api.post<import('@/types').WorkOrder>(`/projects/orders/${id}/status`, { status });
    cacheManager.invalidate('projects:');
    return response.data;
  },

  async deleteWorkOrder(id: string): Promise<void> {
    await api.delete(`/projects/orders/${id}`);
    cacheManager.invalidate('projects:');
  },

  // --- TAREFAS ---
  async getTasks(params?: import('@/types').TasksFilterParams, forceRefresh = false): Promise<import('@/types').Task[]> {
    const key = `projects:tasks:${JSON.stringify(params || {})}`;
    return cacheManager.fetchWithCache(
      key,
      async () => {
        const response = await api.get('/projects/tasks/list', { params });
        return unwrapProjectsList(response.data);
      },
      30 * 1000,
      forceRefresh
    );
  },

  async getTask(id: string): Promise<import('@/types').Task> {
    const response = await api.get<import('@/types').Task>(`/projects/tasks/${id}`);
    return response.data;
  },

  async createTask(payload: import('@/types').TaskCreatePayload): Promise<import('@/types').Task> {
    const response = await api.post<import('@/types').Task>('/projects/tasks', payload);
    cacheManager.invalidate('projects:');
    return response.data;
  },

  async updateTask(id: string, payload: Partial<import('@/types').TaskCreatePayload>): Promise<import('@/types').Task> {
    const response = await api.put<import('@/types').Task>(`/projects/tasks/${id}`, payload);
    cacheManager.invalidate('projects:');
    return response.data;
  },

  async changeTaskStatus(id: string, status: string): Promise<import('@/types').Task> {
    const response = await api.post<import('@/types').Task>(`/projects/tasks/${id}/status`, { status });
    cacheManager.invalidate('projects:');
    return response.data;
  },

  async deleteTask(id: string): Promise<void> {
    await api.delete(`/projects/tasks/${id}`);
    cacheManager.invalidate('projects:');
  },

  // --- OCORRÊNCIAS / ISSUES ---
  async getIssues(params?: { project_id?: string; work_order_id?: string; status?: string }, forceRefresh = false): Promise<import('@/types').Issue[]> {
    const key = `projects:issues:${JSON.stringify(params || {})}`;
    return cacheManager.fetchWithCache(
      key,
      async () => {
        const response = await api.get('/projects/issues/list', { params });
        return unwrapProjectsList(response.data);
      },
      30 * 1000,
      forceRefresh
    );
  },

  async getIssue(id: string): Promise<import('@/types').Issue> {
    const response = await api.get<import('@/types').Issue>(`/projects/issues/${id}`);
    return response.data;
  },

  async createIssue(payload: import('@/types').IssueCreatePayload): Promise<import('@/types').Issue> {
    const response = await api.post<import('@/types').Issue>('/projects/issues', payload);
    cacheManager.invalidate('projects:');
    return response.data;
  },

  async updateIssue(id: string, payload: Partial<import('@/types').IssueCreatePayload>): Promise<import('@/types').Issue> {
    const response = await api.put<import('@/types').Issue>(`/projects/issues/${id}`, payload);
    cacheManager.invalidate('projects:');
    return response.data;
  },

  async resolveIssue(id: string, resolution_notes: string): Promise<import('@/types').Issue> {
    const response = await api.post<import('@/types').Issue>(`/projects/issues/${id}/resolve`, { resolution_notes });
    cacheManager.invalidate('projects:');
    return response.data;
  },

  async deleteIssue(id: string): Promise<void> {
    await api.delete(`/projects/issues/${id}`);
    cacheManager.invalidate('projects:');
  },

  // --- CHECKLISTS ---
  async getChecklists(params?: { project_id?: string; work_order_id?: string; task_id?: string }): Promise<import('@/types').Checklist[]> {
    const response = await api.get('/projects/checklists', { params });
    return unwrapProjectsList(response.data);
  },

  async toggleChecklistItem(checklist_id: string, item_id: string, is_checked: boolean): Promise<import('@/types').ChecklistItem> {
    const response = await api.post<import('@/types').ChecklistItem>(`/projects/checklists/${checklist_id}/items/${item_id}/toggle`, { is_checked });
    return response.data;
  },

  // --- CONFIGURAÇÕES ---
  async getProjectTypes(forceRefresh = false, activeOnly = true): Promise<import('@/types').ProjectType[]> {
    return cacheManager.fetchWithCache(
      `projects:types:${activeOnly}`,
      async () => {
        const response = await api.get('/projects/types', { params: { active_only: activeOnly } });
        return unwrapProjectsList(response.data);
      },
      60 * 1000,
      forceRefresh
    );
  },

  async getProjectType(id: string): Promise<import('@/types').ProjectType> {
    const response = await api.get<import('@/types').ProjectType>(`/projects/types/${id}`);
    return response.data;
  },

  async createProjectType(payload: { name: string; code: string; prefix?: string; description?: string | null; color?: string; default_workflow_id?: string | null }): Promise<import('@/types').ProjectType> {
    const response = await api.post<import('@/types').ProjectType>('/projects/types', payload);
    cacheManager.invalidate('projects:types');
    return response.data;
  },

  async updateProjectType(id: string, payload: Partial<{ name: string; code: string; prefix?: string; description?: string | null; color?: string; default_workflow_id?: string | null; is_active?: boolean }>): Promise<import('@/types').ProjectType> {
    const response = await api.put<import('@/types').ProjectType>(`/projects/types/${id}`, payload);
    cacheManager.invalidate('projects:types');
    return response.data;
  },

  async deleteProjectType(id: string): Promise<void> {
    await api.delete(`/projects/types/${id}`);
    cacheManager.invalidate('projects:types');
  },

  async getWorkOrderTypes(forceRefresh = false, activeOnly = true): Promise<import('@/types').WorkOrderType[]> {
    return cacheManager.fetchWithCache(
      `projects:wo_types:${activeOnly}`,
      async () => {
        const response = await api.get('/projects/order-types', { params: { active_only: activeOnly } });
        return unwrapProjectsList(response.data);
      },
      60 * 1000,
      forceRefresh
    );
  },

  async getWorkOrderType(id: string): Promise<import('@/types').WorkOrderType> {
    const response = await api.get<import('@/types').WorkOrderType>(`/projects/order-types/${id}`);
    return response.data;
  },

  async createWorkOrderType(payload: { name: string; code: string; prefix?: string; description?: string | null; color?: string; default_workflow_id?: string | null }): Promise<import('@/types').WorkOrderType> {
    const response = await api.post<import('@/types').WorkOrderType>('/projects/order-types', payload);
    cacheManager.invalidate('projects:wo_types');
    return response.data;
  },

  async updateWorkOrderType(id: string, payload: Partial<{ name: string; code: string; prefix?: string; description?: string | null; color?: string; default_workflow_id?: string | null; is_active?: boolean }>): Promise<import('@/types').WorkOrderType> {
    const response = await api.put<import('@/types').WorkOrderType>(`/projects/order-types/${id}`, payload);
    cacheManager.invalidate('projects:wo_types');
    return response.data;
  },

  async deleteWorkOrderType(id: string): Promise<void> {
    await api.delete(`/projects/order-types/${id}`);
    cacheManager.invalidate('projects:wo_types');
  },

  async getWorkflowTemplates(forceRefresh = false, activeOnly = true): Promise<import('@/types').WorkflowTemplate[]> {
    return cacheManager.fetchWithCache(
      `projects:workflows:${activeOnly}`,
      async () => {
        const response = await api.get('/projects/workflows', { params: { active_only: activeOnly } });
        return unwrapProjectsList(response.data);
      },
      60 * 1000,
      forceRefresh
    );
  },

  async getWorkflowTemplate(id: string): Promise<import('@/types').WorkflowTemplate> {
    const response = await api.get<import('@/types').WorkflowTemplate>(`/projects/workflows/${id}`);
    return response.data;
  },

  async createWorkflowTemplate(payload: { name: string; description?: string | null; target_entity?: string; stages?: any[] }): Promise<import('@/types').WorkflowTemplate> {
    const response = await api.post<import('@/types').WorkflowTemplate>('/projects/workflows', payload);
    cacheManager.invalidate('projects:workflows');
    return response.data;
  },

  async updateWorkflowTemplate(id: string, payload: Partial<{ name: string; description?: string | null; target_entity?: string; is_active?: boolean }>): Promise<import('@/types').WorkflowTemplate> {
    const response = await api.put<import('@/types').WorkflowTemplate>(`/projects/workflows/${id}`, payload);
    cacheManager.invalidate('projects:workflows');
    return response.data;
  },

  async addWorkflowStage(
    workflowId: string,
    payload: {
      name: string;
      position: number;
      color?: string;
      description?: string | null;
      is_initial?: boolean;
      is_terminal?: boolean;
      allowed_transitions?: string[];
    }
  ): Promise<import('@/types').WorkflowStage> {
    const response = await api.post<import('@/types').WorkflowStage>(`/projects/workflows/${workflowId}/stages`, payload);
    cacheManager.invalidate('projects:workflows');
    return response.data;
  },

  async updateWorkflowStage(
    stageId: string,
    payload: Partial<{
      name: string;
      position: number;
      color: string;
      description: string | null;
      is_initial: boolean;
      is_terminal: boolean;
      allowed_transitions: string[];
    }>
  ): Promise<import('@/types').WorkflowStage> {
    const response = await api.put<import('@/types').WorkflowStage>(`/projects/workflows/stages/${stageId}`, payload);
    cacheManager.invalidate('projects:workflows');
    return response.data;
  },

  async deleteWorkflowTemplate(id: string): Promise<void> {
    await api.delete(`/projects/workflows/${id}`);
    cacheManager.invalidate('projects:workflows');
  },

  async deleteWorkflowStage(stageId: string): Promise<void> {
    await api.delete(`/projects/workflows/stages/${stageId}`);
    cacheManager.invalidate('projects:workflows');
  },

  async getChecklistTemplates(forceRefresh = false): Promise<import('@/types').ChecklistTemplate[]> {
    return cacheManager.fetchWithCache(
      'projects:checklist_templates',
      async () => {
        const response = await api.get('/projects/checklists/templates');
        return unwrapProjectsList(response.data);
      },
      60 * 1000,
      forceRefresh
    );
  }
};

export const chatService = {
  async refreshContact(conversationId: string): Promise<import('@/types/chat').ChatConversation> {
    return (await api.post(`/chat/conversations/${conversationId}/refresh-contact`)).data;
  },
  async openGroupParticipant(conversationId: string, messageId: string): Promise<import('@/types/chat').ChatConversation> {
    const { data } = await api.post(`/chat/conversations/${conversationId}/participants/${messageId}/direct`);
    return data;
  },

  async startConversation(connectionId: string, contactId: string): Promise<import('@/types/chat').ChatConversation> {
    return (await api.post('/chat/conversations/start', { connection_id: connectionId, contact_id: contactId })).data;
  },
  async getAudioRuntime(): Promise<{ configured: boolean; worker_enabled: boolean }> {
    return (await api.get('/chat/audio/runtime')).data;
  },

  async getAudio(id: string): Promise<Blob> {
    return (await api.get(`/chat/messages/${id}/audio`, { responseType: 'blob' })).data;
  },

  async transcribe(id: string): Promise<import('@/types/chat').ChatMessage> {
    return (await api.post(`/chat/messages/${id}/transcribe`)).data;
  },

  async getTranscription(id: string): Promise<import('@/types/chat').ChatMessage> {
    return (await api.get(`/chat/messages/${id}/transcription`)).data;
  },
  async getEligibleUsers(): Promise<{ id: string; full_name: string }[]> {
    const response = await api.get('/chat/eligible-users');
    return response.data;
  },
  async updateConversation(id: string, payload: import('@/types/chat').ChatConversationUpdate): Promise<import('@/types/chat').ChatConversation> {
    const response = await api.patch(`/chat/conversations/${id}`, payload);
    cacheManager.invalidate('chat:');
    return response.data;
  },

  async getConversationContact(id: string): Promise<import('@/types/chat').ChatContact> {
    const response = await api.get(`/chat/conversations/${id}/contact`);
    return response.data;
  },

  async getContactOrigins(): Promise<import('@/types/chat').ContactOrigin[]> {
    const response = await api.get('/identity/contact-origins');
    return response.data;
  },

  async createContactOrigin(payload: { name: string; description?: string | null; channel_type?: string; is_active?: boolean }): Promise<import('@/types/chat').ContactOrigin> {
    const response = await api.post('/identity/contact-origins', payload);
    return response.data;
  },

  async updateContactOriginRecord(id: string, payload: { name?: string; description?: string | null; channel_type?: string; is_active?: boolean }): Promise<import('@/types/chat').ContactOrigin> {
    const response = await api.patch(`/identity/contact-origins/${id}`, payload);
    return response.data;
  },

  async updateContactOrigin(id: string, payload: { origin_id?: string | null; name?: string }): Promise<import('@/types/chat').ChatContact> {
    const response = await api.patch(`/chat/conversations/${id}/contact-origin`, payload);
    cacheManager.invalidate('identity:contacts');
    return response.data;
  },
  async getTeams(): Promise<{ id: string; name: string }[]> {
    const response = await api.get<{ id: string; name: string }[]>('/chat/teams');
    return response.data;
  },
  async getInstanceDetails(id: string): Promise<import('@/types/chat').ChatInstanceDetails> {
    const response = await api.get(`/chat/connections/${id}/details`);
    return response.data;
  },

  async syncHistory(id: string, page = 1, snapshotAt?: string): Promise<import('@/types/chat').ChatHistoryResult> {
    const response = await api.post(`/chat/connections/${id}/sync`, {
      page, page_size: 100, ...(snapshotAt ? { snapshot_at: snapshotAt } : {}),
    });
    return response.data;
  },

  async getProviders(): Promise<import('@/types/chat').ChatProvider[]> {
    const response = await api.get<import('@/types/chat').ChatProvider[]>('/chat/providers');
    return response.data;
  },

  async getChannels(): Promise<import('@/types/chat').ChatChannel[]> {
    const response = await api.get<import('@/types/chat').ChatChannel[]>('/chat/channels');
    return response.data;
  },

  async getMedia(id: string): Promise<Blob> {
    return (await api.get(`/chat/messages/${id}/media`, { responseType: 'blob', timeout: 60000 })).data;
  },
  async getGallery(id: string, params: { page?: number; page_size?: number; search?: string; kind?: string }): Promise<import('@/types/chat').ChatMessagePage> {
    return (await api.get(`/chat/conversations/${id}/media`, { params })).data;
  },
  async sendAttachment(id: string, file: File, caption: string, requestId: string): Promise<import('@/types/chat').ChatMessage> {
    return (await api.post(`/chat/conversations/${id}/media`, file, { params: { client_request_id: requestId, filename: file.name, caption }, headers: { 'Content-Type': file.type || 'application/octet-stream' }, timeout: 90000 })).data;
  },
  async deleteMessage(id: string, everyone = false): Promise<{ deleted: boolean; error?: string }> {
    return (await (everyone ? api.post(`/chat/messages/${id}/delete-for-everyone`) : api.delete(`/chat/messages/${id}`))).data;
  },
  async deleteChannel(id: string): Promise<void> {
    await api.delete(`/chat/conversations/${id}`);
  },
  async replaceContactName(id: string): Promise<import('@/types/chat').ChatConversation> {
    return (await api.post(`/chat/conversations/${id}/refresh-contact`, null, { params: { replace_manual: true } })).data;
  },

  async getNotifications(params: { since?: string; until?: string; page?: number } = {}): Promise<import('@/types/chat').ChatNotificationPage> {
    return (await api.get('/chat/notifications', { params })).data;
  },

  async configureGroups(id: string): Promise<{ groups_enabled: boolean; synced: number }> {
    return (await api.post(`/chat/connections/${id}/groups`)).data;
  },

  async getConnections(forceRefresh = false): Promise<import('@/types/chat').ChatConnection[]> {
    return cacheManager.fetchWithCache(
      'chat:connections',
      async () => {
        const response = await api.get<import('@/types/chat').ChatConnection[]>('/chat/connections');
        return response.data;
      },
      30 * 1000,
      forceRefresh,
    );
  },

  async getConnection(id: string): Promise<import('@/types/chat').ChatConnection> {
    const response = await api.get<import('@/types/chat').ChatConnection>(`/chat/connections/${id}`);
    return response.data;
  },

  async createConnection(payload: import('@/types/chat').ChatConnectionCreatePayload): Promise<import('@/types/chat').ChatConnection> {
    const response = await api.post<import('@/types/chat').ChatConnection>('/chat/connections', payload);
    cacheManager.invalidate('chat:');
    return response.data;
  },

  async updateConnection(id: string, payload: import('@/types/chat').ChatConnectionUpdatePayload): Promise<import('@/types/chat').ChatConnection> {
    const response = await api.patch<import('@/types/chat').ChatConnection>(`/chat/connections/${id}`, payload);
    cacheManager.invalidate('chat:');
    return response.data;
  },

  async checkConnection(id: string): Promise<import('@/types/chat').ChatConnection> {
    const response = await api.post<import('@/types/chat').ChatConnection>(`/chat/connections/${id}/check`);
    cacheManager.invalidate('chat:');
    return response.data;
  },

  async provisionInstance(id: string): Promise<import('@/types/chat').ChatInstanceProvision> {
    const response = await api.post<import('@/types/chat').ChatInstanceProvision>(`/chat/connections/${id}/instance`);
    cacheManager.invalidate('chat:');
    return response.data;
  },

  async getPairing(id: string): Promise<import('@/types/chat').ChatPairing> {
    const response = await api.post<import('@/types/chat').ChatPairing>(`/chat/connections/${id}/pairing`);
    cacheManager.invalidate('chat:');
    return response.data;
  },

  async configureWebhook(id: string): Promise<{ configured: boolean; url: string }> {
    const response = await api.post<{ configured: boolean; url: string }>(`/chat/connections/${id}/webhook`);
    return response.data;
  },

  async getConversations(params?: import('@/types/chat').ChatConversationFilters): Promise<import('@/types/chat').ChatConversationPage> {
    const response = await api.get<import('@/types/chat').ChatConversationPage>('/chat/conversations', { params });
    return response.data;
  },

  async getConversation(id: string): Promise<import('@/types/chat').ChatConversation> {
    const response = await api.get<import('@/types/chat').ChatConversation>(`/chat/conversations/${id}`);
    return response.data;
  },

  async markRead(id: string): Promise<import('@/types/chat').ChatConversation> {
    const response = await api.post<import('@/types/chat').ChatConversation>(`/chat/conversations/${id}/read`);
    cacheManager.invalidate('chat:');
    return response.data;
  },

  async getAvatar(conversationId: string): Promise<Blob> {
    return (await api.get(`/chat/conversations/${conversationId}/avatar`, { responseType: 'blob' })).data;
  },

  async getMessages(conversationId: string, page = 1, pageSize = 50): Promise<import('@/types/chat').ChatMessagePage> {
    const response = await api.get<import('@/types/chat').ChatMessagePage>(
      `/chat/conversations/${conversationId}/messages`,
      { params: { page, page_size: pageSize } },
    );
    return response.data;
  },

  async sendMessage(conversationId: string, text: string, clientRequestId?: string, replyToMessageId?: string | null): Promise<import('@/types/chat').ChatMessage> {
    const response = await api.post<import('@/types/chat').ChatMessage>(
      `/chat/conversations/${conversationId}/messages`,
      {
        client_request_id: clientRequestId || createRequestId(),
        text,
        ...(replyToMessageId ? { reply_to_message_id: replyToMessageId } : {}),
      },
    );
    cacheManager.invalidate('chat:');
    return response.data;
  },

  async sendReaction(messageId: string, emoji: string, clientRequestId?: string): Promise<import('@/types/chat').ChatMessage> {
    const response = await api.post<import('@/types/chat').ChatMessage>(
      `/chat/messages/${messageId}/reactions`,
      { client_request_id: clientRequestId || createRequestId(), emoji },
    );
    cacheManager.invalidate('chat:');
    return response.data;
  },
};
