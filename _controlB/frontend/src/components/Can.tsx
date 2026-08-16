/**
 * components/Can.tsx - Componente Declarativo de Controle de Acesso (RBAC)
 * 
 * Uso:
 * <Can permission="users:create">
 *   <button>Novo Usuário</button>
 * </Can>
 * 
 * Ou com fallback:
 * <Can permission="dashboard:export" fallback={<span>Sem permissão</span>}>
 *   <button>Exportar Dados</button>
 * </Can>
 */

import React from 'react';
import { usePermissions } from '@/hooks/usePermissions';

interface CanProps {
  permission?: string;
  anyOf?: string[];
  allOf?: string[];
  fallback?: React.ReactNode;
  children: React.ReactNode;
}

export const Can: React.FC<CanProps> = ({
  permission,
  anyOf,
  allOf,
  fallback = null,
  children
}) => {
  const { hasPermission, hasAnyPermission, hasAllPermissions, loading } = usePermissions();

  if (loading) return null;

  let isAuthorized = false;

  if (permission) {
    isAuthorized = hasPermission(permission);
  } else if (anyOf && anyOf.length > 0) {
    isAuthorized = hasAnyPermission(anyOf);
  } else if (allOf && allOf.length > 0) {
    isAuthorized = hasAllPermissions(allOf);
  } else {
    isAuthorized = true;
  }

  if (!isAuthorized) {
    return <>{fallback}</>;
  }

  return <>{children}</>;
};
