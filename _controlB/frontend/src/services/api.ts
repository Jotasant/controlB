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

// Chave onde o token é armazenado no navegador
const TOKEN_KEY = 'controlb_token';

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
    }
    return response.data;
  },

  // Remove o token da sessão
  logout(): void {
    localStorage.removeItem(TOKEN_KEY);
  },

  // Retorna o token atual ou null
  getToken(): string | null {
    return localStorage.getItem(TOKEN_KEY);
  },

  // Verifica se o usuário possui sessão ativa
  isAuthenticated(): boolean {
    return !!localStorage.getItem(TOKEN_KEY);
  },
};

// 4. Funções de Consulta de Dados
export const identityService = {
  // Lista todos os usuários
  async getUsers(): Promise<User[]> {
    const response = await api.get<User[]>('/identity/users');
    return response.data;
  },

  // Lista todos os cargos
  async getRoles(): Promise<Role[]> {
    const response = await api.get<Role[]>('/identity/role');
    return response.data;
  },

  // Lista todas as organizações
  async getOrganizations(): Promise<Organization[]> {
    const response = await api.get<Organization[]>('/identity/organization');
    return response.data;
  },
};
