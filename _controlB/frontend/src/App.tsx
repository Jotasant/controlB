/**
 * App.tsx - Roteamento Central da Aplicação SPA (React Router DOM)
 * 
 * Gerencia as rotas públicas (Login) e privadas (Dashboard, Compras, Cadastros)
 * com proteção de autenticação, redirecionamentos e ThemeProvider (Dark / Light).
 */

import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from '@/context/ThemeContext';
import { Login } from '@/pages/Login/Login';
import { Dashboard } from '@/pages/Dashboard/Dashboard';
import { Purchasing } from '@/pages/Purchasing/Purchasing';
import { Inventory } from '@/pages/Inventory/Inventory';
import { CRM } from '@/pages/CRM/CRM';
import { Sales } from '@/pages/Sales/Sales';
import { POS } from '@/pages/POS/POS';
import { Finance } from '@/pages/Finance/Finance';
import { Billing } from '@/pages/Billing/Billing';
import { Cadastros } from '@/pages/Cadastros/Cadastros';
import { Organizations } from '@/pages/Organizations/Organizations';
import { Users } from '@/pages/Users/Users';
import { Roles } from '@/pages/Roles/Roles';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { PublicRoute } from '@/components/PublicRoute';
import { AppLayout } from '@/components/AppLayout';
import { ToastProvider } from '@/components/Toast/ToastProvider';

export const App: React.FC = () => {
  return (
    <ThemeProvider>
      <ToastProvider>
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

          {/* 2. Rotas Protegidas com Layout Persistente (Exigem Token JWT) */}
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/crm" element={<CRM />} />
              <Route path="/vendas" element={<Sales />} />
              <Route path="/pdv" element={<POS />} />
              <Route path="/faturamento" element={<Billing />} />
              <Route path="/financeiro" element={<Finance />} />
              <Route path="/estoque" element={<Inventory />} />
              <Route path="/compras" element={<Purchasing />} />
              <Route path="/cadastros" element={<Cadastros />} />
              <Route path="/organizacoes" element={<Organizations />} />
              <Route path="/usuarios" element={<Users />} />
              <Route path="/cargos" element={<Roles />} />
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
            </Route>
          </Route>



          {/* 3. Fallback */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </ThemeProvider>
  );
};

export default App;
