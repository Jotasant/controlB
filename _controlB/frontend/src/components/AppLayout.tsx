/**
 * components/AppLayout.tsx - Layout Persistente de Aplicação SPA (ControlB)
 * 
 * Mantém a Navbar fixa e montada no topo durante toda a sessão do usuário.
 * Elimina o efeito de "piscar" (flicker) e reconstrução da barra de navegação
 * ao alternar entre páginas (Dashboard, Estoque, Compras, Cadastros, etc.).
 */

import React from 'react';
import { Outlet } from 'react-router-dom';
import { Navbar } from '@/components/Navbar';
import { ChatShell } from '@/components/ChatWidget/ChatWidget';

export const AppLayout: React.FC = () => {
  return (
    <ChatShell>
      <div className="app-root-layout">
        <Navbar />
        <Outlet />
      </div>
    </ChatShell>
  );
};

export default AppLayout;
