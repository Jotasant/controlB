/**
 * hooks/usePermissions.ts - Hook customizado para controle de acesso no Frontend
 * 
 * Permite que qualquer componente React verifique de forma simples:
 * const { hasPermission, permissions, user, loading } = usePermissions();
 * 
 * if (hasPermission('users:delete')) { ... }
 */

import { useState, useEffect } from 'react';
import { identityService, authService } from '@/services/api';
import { UserMe } from '@/types';

export const usePermissions = () => {
  const [user, setUser] = useState<UserMe | null>(null);
  const [permissions, setPermissions] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!authService.isAuthenticated()) {
      setLoading(false);
      return;
    }

    identityService.getMe()
      .then((data) => {
        setUser(data);
        setPermissions(data.permissions || []);
      })
      .catch((err) => {
        console.error('Erro ao carregar permissões do usuário logado:', err);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  // Usuário administrador possui acesso total por definição
  const isAdmin = user?.role_name?.toLowerCase() === 'administrador' || 
                  user?.role_name?.toLowerCase() === 'admin' || 
                  permissions.includes('*:*');

  // Função utilitária para checar uma ou mais permissões
  const hasPermission = (code: string): boolean => {
    return isAdmin || permissions.includes(code);
  };

  const hasAnyPermission = (codes: string[]): boolean => {
    return isAdmin || codes.some(code => permissions.includes(code));
  };

  const hasAllPermissions = (codes: string[]): boolean => {
    return isAdmin || codes.every(code => permissions.includes(code));
  };

  return {
    user,
    permissions,
    loading,
    hasPermission,
    hasAnyPermission,
    hasAllPermissions
  };
};
