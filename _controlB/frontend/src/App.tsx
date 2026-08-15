/**
 * App.tsx - Roteamento Central da Aplicação SPA (React Router DOM)
 * 
 * Gerencia as rotas públicas (Login) e privadas (Dashboard, Organizações, Usuários, Cargos)
 * com proteção de autenticação, redirecionamentos e ThemeProvider (Dark / Light).
 */

import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from '@/context/ThemeContext';
import { Login } from '@/pages/Login/Login';
import { Dashboard } from '@/pages/Dashboard/Dashboard';
import { Organizations } from '@/pages/Organizations/Organizations';
import { Users } from '@/pages/Users/Users';
import { Roles } from '@/pages/Roles/Roles';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { PublicRoute } from '@/components/PublicRoute';
import { Cadastros } from '@/pages/Cadastros/Cadastros';

export const App: React.FC = () => {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          {/* 1. Rota de Login (Pública) */}
          <Route
            path="/login"
            element={
              <PublicRoute>
                <Login />
              </PublicRoute>
            }
          />

          {/* 2. Rotas Protegidas (Exigem Token JWT) */}
          <Route element={<ProtectedRoute />}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/organizacoes" element={<Organizations />} />
            <Route path="/usuarios" element={<Users />} />
            <Route path="/cargos" element={<Roles />} />
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/cadastros" element={<Cadastros />} />
          </Route>

          {/* 3. Fallback */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
};

export default App;
