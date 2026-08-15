/**
 * components/PublicRoute.tsx - Guarda de Rotas Públicas (Login)
 * 
 * Se o usuário já possui um token válido ativo no navegador,
 * impede que ele veja a tela de login novamente e o redireciona direto para o /dashboard.
 */

import React from 'react';
import { Navigate } from 'react-router-dom';
import { authService } from '@/services/api';

interface PublicRouteProps {
  children: React.ReactElement;
}

export const PublicRoute: React.FC<PublicRouteProps> = ({ children }) => {
  const isAuth = authService.isAuthenticated();

  if (isAuth) {
    return <Navigate to="/dashboard" replace />;
  }

  return children;
};
