/**
 * App.tsx - Roteamento Central da Aplicação SPA (React Router DOM)
 * 
 * Gerencia as rotas públicas (Login) e privadas (Dashboard)
 * com proteção de autenticação e redirecionamentos automáticos.
 */

import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Login } from '@/pages/Login/Login';
import { Dashboard } from '@/pages/Dashboard/Dashboard';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { PublicRoute } from '@/components/PublicRoute';

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        {/* 1. Rota de Login (Pública - se já logado, vai direto pro Dashboard) */}
        <Route
          path="/login"
          element={
            <PublicRoute>
              <Login />
            </PublicRoute>
          }
        />

        {/* 2. Rotas Protegidas (Exigem Token JWT válido) */}
        <Route element={<ProtectedRoute />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
        </Route>

        {/* 3. Fallback: Qualquer rota desconhecida redireciona para o Dashboard */}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
};

export default App;
