/**
 * components/ProtectedRoute.tsx - Guarda de Rotas Privadas
 * 
 * Se o usuário não possui token JWT no localStorage, é redirecionado
 * imediatamente para o /login, bloqueando o acesso indevido ao dashboard.
 */

import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { authService } from '@/services/api';

export const ProtectedRoute: React.FC = () => {
  const isAuth = authService.isAuthenticated();

  if (!isAuth) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
};
