/**
 * services/api.ts - Cliente HTTP Centralizado com Axios
 * 
 * Responsabilidades:
 * 1. Interceptar todas as requisições HTTP e anexar automaticamente o Bearer Token JWT.
 * 2. Tratar respostas de erro 401 (token expirado) limpando a sessão e redirecionando para o /login.
 * 3. Exportar métodos tipados para consumo direto pelos componentes React.
 */

import axios from 'axios';
import { User, Role, Organization, TokenResponse } from '@/types';

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

// 3. Funções de Serviços Autenticados
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

// 4. Funções de Consulta e Manipulação de Dados
export const identityService = {
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

  // --- CARGOS ---
  async getRoles(): Promise<Role[]> {
    const response = await api.get<Role[]>('/identity/role');
    return response.data;
  },

  async createRole(name: string, description: string, organizationId?: string): Promise<Role> {
    const response = await api.post<Role>('/identity/role', { 
      name, 
      description,
      organization_id: organizationId || '00000000-0000-0000-0000-000000000000' 
    });
    return response.data;
  },

  async deleteRole(roleId: string): Promise<{ message: string }> {
    const response = await api.delete<{ message: string }>(`/identity/role/${roleId}`);
    return response.data;
  }
};
