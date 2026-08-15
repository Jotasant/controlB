/**
 * types/index.ts - Tipos e Interfaces TypeScript do ControlB
 * 
 * Espelha os schemas do backend FastAPI (Pydantic) garantindo
 * auto-complete, tipagem estrita e segurança no frontend.
 */

// Interface do Usuário retornado pela API (/identity/users)
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

// Interface da Organização (/identity/organization)
export interface Organization {
  id: string;
  name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// Interface do Cargo / Papel (/identity/role)
export interface Role {
  id: string;
  organization_id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// Resposta do endpoint de login (/identity/token)
export interface TokenResponse {
  access_token: string;
  token_type: string;
}
