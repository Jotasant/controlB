/**
 * components/Navbar.tsx - Barra Superior Ultra-Slim com Controle Dinâmico de Acesso (RBAC)
 * 
 * Renderiza menus condicionalmente com base nas permissões do usuário logado:
 * 1. Dashboard (/dashboard) - se dashboard:view
 * 2. Compras (/compras) - Central Operacional de Compras e Catálogo
 * 3. Configurações (/cadastros) - SOMENTE se possuir permissão para módulos de cadastro administrativo
 * 4. Alternador de Tema (Dark / Light)
 * 5. Perfil do Usuário com Cargo Real e Logout
 */

import React, { useState, useRef, useEffect } from 'react';
import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import {
  LogOut, Sun, Moon, ChevronDown, User,
  LayoutDashboard, Building2, Settings, UserCheck, ShoppingCart, Package,
  Layers, Landmark, ReceiptText, Users, ShoppingBag, Store
} from 'lucide-react';
import { authService } from '@/services/api';
import { useTheme } from '@/context/ThemeContext';
import { usePermissions } from '@/hooks/usePermissions';
import { Logo } from '@/components/Logo';
import './Navbar.scss';

export const Navbar: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { theme, toggleTheme } = useTheme();
  const { user, hasPermission, hasAnyPermission } = usePermissions();

  // Estado do menu de perfil, configurações e módulos
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [isConfigOpen, setIsConfigOpen] = useState(false);
  const [isModulesOpen, setIsModulesOpen] = useState(false);

  const profileRef = useRef<HTMLDivElement>(null);
  const configRef = useRef<HTMLDivElement>(null);
  const modulesRef = useRef<HTMLDivElement>(null);

  // Fecha menus ao clicar fora ou mudar de rota
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (profileRef.current && !profileRef.current.contains(event.target as Node)) {
        setIsProfileOpen(false);
      }
      if (configRef.current && !configRef.current.contains(event.target as Node)) {
        setIsConfigOpen(false);
      }
      if (modulesRef.current && !modulesRef.current.contains(event.target as Node)) {
        setIsModulesOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    setIsProfileOpen(false);
    setIsConfigOpen(false);
    setIsModulesOpen(false);
  }, [location.pathname]);

  const handleLogout = () => {
    authService.logout();
    navigate('/login');
  };

  const userEmail = user?.email || authService.getUserEmail();
  const userName = user?.full_name || userEmail.split('@')[0] || 'Usuário';
  const userInitial = (userName || 'U').charAt(0).toUpperCase();
  const roleName = user?.role_name || 'Colaborador';

  // 🛡️ Regra RBAC: O menu "Configurações" só aparece se o usuário tiver acesso a Cadastros Administrativos
  const canAccessSettings = hasAnyPermission([
    'organizations:view', 
    'users:view', 
    'roles:view',
    'organizations:manage',
    'users:create',
    'roles:manage'
  ]);

  // Verifica se está dentro de alguma rota de módulo para destacar o menu "Módulos"
  const isModuleActive = ['/crm', '/vendas', '/pdv', '/faturamento', '/financeiro', '/estoque', '/compras'].some(path => 
    location.pathname.startsWith(path)
  );

  return (
    <header className="slim-navbar">
      {/* 1. Logotipo Oficial */}
      <div className="navbar-brand" onClick={() => navigate('/dashboard')} title="Ir para o Dashboard">
        <Logo size={24} showText={true} />
      </div>

      {/* 2. Links Principais Diretos e Menus Suspensos */}
      <nav className="navbar-links">
        {/* Link direto para o Dashboard */}
        {hasPermission('dashboard:view') && (
          <NavLink
            to="/dashboard"
            className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}
          >
            <LayoutDashboard size={14} />
            <span>Dashboard</span>
          </NavLink>
        )}

        {/* 🗂️ Menu Principal: Módulos (CRM, Vendas, PDV, Faturamento, Financeiro, Estoque, Compras) */}
        <div className="dropdown-wrapper" ref={modulesRef}>
          <button
            type="button"
            className={`nav-link dropdown-btn ${isModulesOpen || isModuleActive ? 'active' : ''}`}
            onClick={() => setIsModulesOpen(!isModulesOpen)}
          >
            <Layers size={14} />
            <span>Módulos</span>
            <ChevronDown size={12} className={`arrow-icon ${isModulesOpen ? 'rotated' : ''}`} />
          </button>

          {isModulesOpen && (
            <div className="dropdown-popover modules-popover">
              {/* 👥 Módulo de CRM */}
              <NavLink
                to="/crm"
                className={({ isActive }) => isActive ? 'popover-item active' : 'popover-item'}
                onClick={() => setIsModulesOpen(false)}
              >
                <Users size={16} className="icon-module icon-crm" />
                <div className="item-text">
                  <span className="title">CRM & Relacionamento</span>
                  <span className="desc">Leads, oportunidades e pipeline</span>
                </div>
              </NavLink>

              {/* 🛍️ Módulo de Vendas */}
              <NavLink
                to="/vendas"
                className={({ isActive }) => isActive ? 'popover-item active' : 'popover-item'}
                onClick={() => setIsModulesOpen(false)}
              >
                <ShoppingBag size={16} className="icon-module icon-sales" />
                <div className="item-text">
                  <span className="title">Vendas & Cotações</span>
                  <span className="desc">Orçamentos, propostas e pedidos</span>
                </div>
              </NavLink>

              {/* 🏪 Frente de Caixa (PDV) */}
              <NavLink
                to="/pdv"
                className={({ isActive }) => isActive ? 'popover-item active' : 'popover-item'}
                onClick={() => setIsModulesOpen(false)}
              >
                <Store size={16} className="icon-module icon-pos" />
                <div className="item-text">
                  <span className="title">Frente de Caixa (PDV)</span>
                  <span className="desc">Venda balcão e cupom não-fiscal</span>
                </div>
              </NavLink>

              {/* 🧾 Módulo de Faturamento */}
              <NavLink
                to="/faturamento"
                className={({ isActive }) => isActive ? 'popover-item active' : 'popover-item'}
                onClick={() => setIsModulesOpen(false)}
              >
                <ReceiptText size={16} className="icon-module icon-billing" />
                <div className="item-text">
                  <span className="title">Faturamento & Notas</span>
                  <span className="desc">Faturas comerciais e NF-e/NFC-e</span>
                </div>
              </NavLink>

              {/* 💰 Módulo Financeiro */}
              <NavLink
                to="/financeiro"
                className={({ isActive }) => isActive ? 'popover-item active' : 'popover-item'}
                onClick={() => setIsModulesOpen(false)}
              >
                <Landmark size={16} className="icon-module icon-finance" />
                <div className="item-text">
                  <span className="title">Gestão Financeira</span>
                  <span className="desc">Contas a pagar/receber e bancos</span>
                </div>
              </NavLink>

              {/* 📦 Módulo de Estoque */}
              <NavLink
                to="/estoque"
                className={({ isActive }) => isActive ? 'popover-item active' : 'popover-item'}
                onClick={() => setIsModulesOpen(false)}
              >
                <Package size={16} className="icon-module icon-inventory" />
                <div className="item-text">
                  <span className="title">Estoque & Almoxarifado</span>
                  <span className="desc">Saldos físicos e movimentações</span>
                </div>
              </NavLink>

              {/* 🛒 Módulo de Compras */}
              <NavLink
                to="/compras"
                className={({ isActive }) => isActive ? 'popover-item active' : 'popover-item'}
                onClick={() => setIsModulesOpen(false)}
              >
                <ShoppingCart size={16} className="icon-module icon-purchasing" />
                <div className="item-text">
                  <span className="title">Compras & Suprimentos</span>
                  <span className="desc">Solicitações, cotações e ordens</span>
                </div>
              </NavLink>
            </div>
          )}
        </div>

        {/* Menu Pai: Configurações com Dropdown (Ocultado se o usuário não tiver permissão) */}
        {canAccessSettings && (
          <div className="dropdown-wrapper" ref={configRef}>
            <button
              type="button"
              className={`nav-link dropdown-btn ${isConfigOpen ? 'open' : ''}`}
              onClick={() => setIsConfigOpen(!isConfigOpen)}
            >
              <Settings size={14} />
              <span>Configurações</span>
              <ChevronDown size={12} className={`arrow-icon ${isConfigOpen ? 'rotated' : ''}`} />
            </button>

            {/* Submenu Suspenso */}
            {isConfigOpen && (
              <div className="dropdown-popover">
                <NavLink
                  to="/cadastros"
                  className={({ isActive }) => isActive ? 'popover-item active' : 'popover-item'}
                  onClick={() => setIsConfigOpen(false)}
                >
                  <Building2 size={14} className="icon-org" />
                  <div className="item-text">
                    <span className="title">Identidade & Acessos</span>
                    <span className="desc">Usuários, Organizações e Cargos</span>
                  </div>
                </NavLink>

                <div className="popover-item disabled">
                  <Settings size={14} />
                  <div className="item-text">
                    <span className="title">Parâmetros Gerais</span>
                    <span className="desc">Preferências da aplicação</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </nav>

      {/* 3. Ações da Direita (Tema + Perfil do Usuário) */}
      <div className="navbar-actions">
        {/* Alternador de Tema (Dark / Light) */}
        <button
          type="button"
          className="btn-theme-toggle"
          onClick={toggleTheme}
          title={`Alternar para tema ${theme === 'dark' ? 'Claro' : 'Escuro'}`}
        >
          {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
        </button>

        <div className="action-divider" />

        {/* Menu Dropdown de Perfil do Usuário */}
        <div className="profile-dropdown-wrapper" ref={profileRef}>
          <button
            type="button"
            className={`btn-profile-trigger ${isProfileOpen ? 'active' : ''}`}
            onClick={() => setIsProfileOpen(!isProfileOpen)}
            title="Menu do Usuário"
          >
            <div className="avatar-circle">
              {userInitial}
            </div>
            <span className="profile-username">{userName}</span>
            <ChevronDown size={12} className={`arrow-icon ${isProfileOpen ? 'rotated' : ''}`} />
          </button>

          {isProfileOpen && (
            <div className="profile-popover">
              <div className="profile-header">
                <div className="avatar-large">{userInitial}</div>
                <div className="profile-info">
                  <span className="name">{userName}</span>
                  <span className="email">{userEmail}</span>
                  <span className="badge-role">
                    <UserCheck size={10} />
                    {roleName}
                  </span>
                </div>
              </div>

              <div className="popover-divider" />

              <div className="profile-menu-items">
                <button type="button" className="menu-item" onClick={() => setIsProfileOpen(false)}>
                  <User size={14} />
                  <span>Meu Perfil</span>
                </button>

                <button type="button" className="menu-item" onClick={() => setIsProfileOpen(false)}>
                  <Settings size={14} />
                  <span>Configurações da Conta</span>
                </button>
              </div>

              <div className="popover-divider" />

              <button type="button" className="menu-item item-logout" onClick={handleLogout}>
                <LogOut size={14} />
                <span>Sair da Conta</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
