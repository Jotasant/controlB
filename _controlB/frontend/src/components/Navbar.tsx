/**
 * components/Navbar.tsx - Barra de Navegação Superior
 * 
 * Exibe o logotipo do ControlB, os menus de navegação rápida
 * e o botão de Logout integrado ao estado de autenticação.
 */

import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { LogOut, LayoutDashboard, Users, Building2, Settings } from 'lucide-react';
import { authService } from '@/services/api';
import './Navbar.scss';

export const Navbar: React.FC = () => {
  const navigate = useNavigate();

  const handleLogout = () => {
    authService.logout();
    navigate('/login');
  };

  return (
    <header className="navbar">
      <div className="navbar-logo" onClick={() => navigate('/dashboard')}>
        <span>Control</span>B
      </div>

      <nav className="navbar-menu">
        <NavLink to="/dashboard" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
          <LayoutDashboard size={18} />
          <span>Dashboard</span>
        </NavLink>
        <a href="#usuarios" className="nav-item">
          <Users size={18} />
          <span>Usuários</span>
        </a>
        <a href="#organizacoes" className="nav-item">
          <Building2 size={18} />
          <span>Organizações</span>
        </a>
        <a href="#configuracoes" className="nav-item">
          <Settings size={18} />
          <span>Configurações</span>
        </a>
      </nav>

      <button className="btn-logout" onClick={handleLogout} title="Encerrar Sessão">
        <LogOut size={16} />
        <span>Sair</span>
      </button>
    </header>
  );
};
