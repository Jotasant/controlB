/**
 * pages/Login/Login.tsx - Tela de Autenticação Ultra-Slim & Executiva
 * 
 * Integrada com o Logotipo Oficial ControlB, suporte a Dark / Light Mode
 * e validação reativa com Axios.
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Mail, Lock, LogIn, Loader2, AlertCircle, Sun, Moon } from 'lucide-react';
import { authService, formatApiError } from '@/services/api';
import { useTheme } from '@/context/ThemeContext';
import { Logo } from '@/components/Logo';
import './Login.scss';

export const Login: React.FC = () => {
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSuccess, setIsSuccess] = useState(false);
  const [shake, setShake] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isLoading) return;

    setIsLoading(true);
    setErrorMessage(null);

    try {
      await authService.login(email.trim(), password);
      setIsSuccess(true);
      setTimeout(() => {
        navigate('/dashboard');
      }, 400);
    } catch (err: any) {
      setErrorMessage(
        formatApiError(err, 'Credenciais inválidas ou servidor indisponível.')
      );
      setShake(true);
      setTimeout(() => setShake(false), 500);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-page">
      {/* Botão de Tema no Topo Direito */}
      <button 
        className="login-theme-btn" 
        onClick={toggleTheme}
        title={`Alternar para tema ${theme === 'dark' ? 'Claro' : 'Escuro'}`}
      >
        {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
      </button>

      <div className="login-container">
        <div className={`login-card ${shake ? 'shake' : ''}`}>
          
          {/* Cabeçalho com Logotipo Oficial */}
          <div className="logo-header">
            <div className="logo-wrap">
              <Logo size={42} showText={false} />
            </div>
            <h1>Control<span className="brand-dot">B</span></h1>
            <p>Plataforma de Gestão Empresarial</p>
          </div>

          <form onSubmit={handleSubmit} className="login-form">
            <div className="form-group">
              <label htmlFor="email">E-mail Corporativo</label>
              <div className="input-wrapper">
                <Mail className="input-icon" size={15} />
                <input
                  type="email"
                  id="email"
                  placeholder="nome@empresa.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoComplete="email"
                  disabled={isLoading || isSuccess}
                />
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="password">Senha de Acesso</label>
              <div className="input-wrapper">
                <Lock className="input-icon" size={15} />
                <input
                  type="password"
                  id="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                  disabled={isLoading || isSuccess}
                />
              </div>
            </div>

            {errorMessage && (
              <div className="error-alert">
                <AlertCircle size={15} />
                <span>{errorMessage}</span>
              </div>
            )}

            <button
              type="submit"
              className={`btn-submit ${isSuccess ? 'success' : ''}`}
              disabled={isLoading || isSuccess}
            >
              {isLoading ? (
                <>
                  <Loader2 className="spinner" size={15} />
                  <span>Autenticando...</span>
                </>
              ) : isSuccess ? (
                <span>Acesso Autorizado!</span>
              ) : (
                <>
                  <LogIn size={15} />
                  <span>Acessar Painel</span>
                </>
              )}
            </button>
          </form>

          <footer className="login-footer">
            <span>Ambiente seguro protegido por criptografia</span>
          </footer>
        </div>
      </div>
    </div>
  );
};
