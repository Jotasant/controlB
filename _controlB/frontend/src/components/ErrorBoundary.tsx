/**
 * components/ErrorBoundary.tsx - Capturador Global de Erros de Renderização (React)
 * 
 * Evita a famosa 'tela branca' no frontend ao capturar exceções JavaScript
 * não tratadas durante o ciclo de vida e renderização dos componentes,
 * exibindo uma interface amigável de recuperação e diagnóstico.
 */

import { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('🔴 ErrorBoundary capturou uma falha de renderização:', error, errorInfo);
    this.setState({ errorInfo });
  }

  private handleReload = () => {
    window.location.reload();
  };

  private handleGoHome = () => {
    window.location.href = '/dashboard';
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div style={{
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'var(--bg-app, #0f172a)',
          color: 'var(--text-primary, #f8fafc)',
          padding: '2rem',
          fontFamily: 'Inter, system-ui, sans-serif'
        }}>
          <div style={{
            background: 'var(--bg-surface, #1e293b)',
            border: '1px solid var(--border-subtle, rgba(255, 255, 255, 0.1))',
            borderRadius: '12px',
            padding: '2.5rem',
            maxWidth: '520px',
            width: '100%',
            textAlign: 'center',
            boxShadow: '0 8px 30px rgba(0,0,0,0.3)'
          }}>
            <div style={{
              width: '56px',
              height: '56px',
              borderRadius: '50%',
              background: 'rgba(239, 68, 68, 0.15)',
              color: '#ef4444',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: '1.25rem'
            }}>
              <AlertTriangle size={28} />
            </div>

            <h2 style={{ fontSize: '1.25rem', fontWeight: 700, margin: '0 0 0.5rem 0' }}>
              Ops! Algo inesperado aconteceu
            </h2>
            
            <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary, #94a3b8)', margin: '0 0 1.5rem 0', lineHeight: 1.5 }}>
              Ocorreu um erro durante a renderização deste componente. Seus dados continuam seguros.
            </p>

            {this.state.error && (
              <pre style={{
                background: 'var(--bg-app, #0f172a)',
                padding: '0.85rem',
                borderRadius: '6px',
                fontSize: '0.75rem',
                color: '#f87171',
                textAlign: 'left',
                overflowX: 'auto',
                marginBottom: '1.5rem',
                maxHeight: '120px'
              }}>
                {this.state.error.toString()}
              </pre>
            )}

            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center' }}>
              <button
                onClick={this.handleGoHome}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  background: 'transparent',
                  border: '1px solid var(--border-subtle, rgba(255, 255, 255, 0.2))',
                  color: 'var(--text-primary, #f8fafc)',
                  padding: '0.6rem 1.1rem',
                  borderRadius: '6px',
                  fontSize: '0.825rem',
                  fontWeight: 600,
                  cursor: 'pointer'
                }}
              >
                <Home size={14} />
                <span>Ir para Início</span>
              </button>

              <button
                onClick={this.handleReload}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  background: 'var(--accent-brand, #ff5500)',
                  border: 'none',
                  color: '#ffffff',
                  padding: '0.6rem 1.1rem',
                  borderRadius: '6px',
                  fontSize: '0.825rem',
                  fontWeight: 600,
                  cursor: 'pointer'
                }}
              >
                <RefreshCw size={14} />
                <span>Recarregar Página</span>
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
