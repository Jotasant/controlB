/**
 * pages/Login/Login.tsx - Página de Login do ControlB
 * 
 * Implementada em React com estado reativo, validação controlada,
 * design Glassmorphism e integração com o backend FastAPI via Axios.
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Mail, Lock, LogIn, Loader2, AlertCircle } from 'lucide-react';
import { authService } from '@/services/api';
import './Login.scss';

export const Login: React.FC = () => {
  const navigate = useNavigate();

  // Estados do Formulário
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSuccess, setIsSuccess] = useState(false);
  const [shake, setShake] = useState(false);

  // Manipulador de Envio do Formulário
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isLoading) return;

    setIsLoading(true);
    setErrorMessage(null);

    try {
      // Chama o serviço de autenticação
      await authService.login(email.trim(), password);

      // Sucesso
      setIsSuccess(true);
      setTimeout(() => {
        navigate('/dashboard');
      }, 500);

    } catch (err: any) {
      // Falha de autenticação ou conexão
      setErrorMessage(
        err.response?.data?.detail || 'Credenciais inválidas ou servidor indisponível.'
      );
      setShake(true);
      setTimeout(() => setShake(false), 500);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-page">
      {/* Luzes / Formas difusas animadas de fundo */}
      <div className="bg-shapes">
        <div className="shape shape-1" />
        <div className="shape shape-2" />
      </div>

      <div className="login-container">
        <div className={`glass-panel ${shake ? 'shake' : ''}`}>
          <div className="logo-header">
            <h1><span>Control</span>B</h1>
            <p>Acesse sua conta para continuar</p>
          </div>

          <form onSubmit={handleSubmit} className="login-form">
            {/* Campo E-mail */}
            <div className="form-group">
              <label htmlFor="email">E-mail Corporativo</label>
              <div className="input-wrapper">
                <Mail className="input-icon" size={18} />
                <input
                  type="email"
                  id="email"
                  placeholder="voce@empresa.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoComplete="email"
                  disabled={isLoading || isSuccess}
                />
              </div>
            </div>

            {/* Campo Senha */}
            <div className="form-group">
              <label htmlFor="password">Senha</label>
              <div className="input-wrapper">
                <Lock className="input-icon" size={18} />
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

            {/* Mensagem de Erro */}
            {errorMessage && (
              <div className="error-alert">
                <AlertCircle size={18} />
                <span>{errorMessage}</span>
              </div>
            )}

            {/* Botão Entrar */}
            <button
              type="submit"
              className={`btn-submit ${isSuccess ? 'success' : ''}`}
              disabled={isLoading || isSuccess}
            >
              {isLoading ? (
                <>
                  <Loader2 className="spinner" size={20} />
                  <span>Autenticando...</span>
                </>
              ) : isSuccess ? (
                <span>Sucesso! Entrando...</span>
              ) : (
                <>
                  <LogIn size={20} />
                  <span>Entrar</span>
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
