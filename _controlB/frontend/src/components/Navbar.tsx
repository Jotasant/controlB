/**
 * components/Navbar.tsx - Barra Superior Ultra-Slim & Limpa
 * 
 * Links diretos sem submenus duplicados no topo:
 * 1. Dashboard (/dashboard)
 * 2. Cadastros (/cadastros - abre a tela com a barra lateral de opções)
 * 3. Configurações
 * 4. Alternador de Tema (Dark / Light)
 * 5. Menu de Perfil do Usuário com Logout
 */

import React, { useState, useRef, useEffect } from 'react';
import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import {
  LogOut, Sun, Moon, ChevronDown, User,
  LayoutDashboard, Building2, Settings, UserCheck
} from 'lucide-react';
import { authService } from '@/services/api';
import { useTheme } from '@/context/ThemeContext';
import { Logo } from '@/components/Logo';
import './Navbar.scss';

export const Navbar: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { theme, toggleTheme } = useTheme();

  // Estado do menu de perfil
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const profileRef = useRef<HTMLDivElement>(null);

  // Fecha menu de perfil ao clicar fora ou mudar de rota
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (profileRef.current && !profileRef.current.contains(event.target as Node)) {
        setIsProfileOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    setIsProfileOpen(false);
  }, [location.pathname]);

  const handleLogout = () => {
    authService.logout();
    navigate('/login');
  };

  const userEmail = authService.getUserEmail();
  const userName = userEmail.split('@')[0] || 'Usuário';
  const userInitial = userName.charAt(0).toUpperCase();
  const [isConfigOpen, setIsConfigOpen] = useState(false);
  const configRef = useRef<HTMLDivElement>(null);


  return (
    <header className="slim-navbar">
      {/* 1. Logotipo Oficial */}
      <div className="navbar-brand" onClick={() => navigate('/dashboard')} title="Ir para o Dashboard">
        <Logo size={24} showText={true} />
      </div>

      {/* 2. Links Principais Diretos (Sem menus duplicados) */}
      <nav className="navbar-links">
        {/* 1. Link direto para o Dashboard */}
        <NavLink
          to="/dashboard"
          className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}
        >
          <LayoutDashboard size={14} />
          <span>Dashboard</span>
        </NavLink>

        {/* 2. Menu Pai: Configurações com Dropdown */}
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
                  <span className="title">Cadastros</span>
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
                    Administrador
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
