import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from 'lucide-react';
import {
  ToastContext,
  ToastInput,
  ToastItemData,
  ToastType
} from './ToastContext';
import './Toast.scss';

interface ToastProviderProps {
  children: React.ReactNode;
}

interface ToastItemProps {
  toast: ToastItemData;
  onDismiss: (id: string) => void;
}

const DEFAULT_DURATION = 5000;
const MAX_VISIBLE_TOASTS = 4;

const defaultTitles: Record<ToastType, string> = {
  success: 'Concluído',
  error: 'Não foi possível concluir',
  warning: 'Atenção',
  info: 'Informação'
};

const icons: Record<ToastType, React.ReactNode> = {
  success: <CheckCircle2 size={19} />,
  error: <XCircle size={19} />,
  warning: <AlertTriangle size={19} />,
  info: <Info size={19} />
};

const ToastItem: React.FC<ToastItemProps> = ({ toast, onDismiss }) => {
  useEffect(() => {
    if (toast.duration === 0) return undefined;

    const timer = window.setTimeout(
      () => onDismiss(toast.id),
      toast.duration ?? DEFAULT_DURATION
    );

    return () => window.clearTimeout(timer);
  }, [onDismiss, toast.duration, toast.id]);

  return (
    <article
      className={`ui-toast ui-toast--${toast.type}`}
      role={toast.type === 'error' ? 'alert' : 'status'}
      aria-atomic="true"
    >
      <div className="ui-toast__icon" aria-hidden="true">
        {icons[toast.type]}
      </div>

      <div className="ui-toast__content">
        <strong>{toast.title || defaultTitles[toast.type]}</strong>
        <p>{toast.message}</p>
      </div>

      <button
        type="button"
        className="ui-toast__close"
        onClick={() => onDismiss(toast.id)}
        aria-label="Fechar notificação"
      >
        <X size={16} />
      </button>
    </article>
  );
};

export const ToastProvider: React.FC<ToastProviderProps> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastItemData[]>([]);
  const nextId = useRef(0);

  const dismissToast = useCallback((id: string) => {
    setToasts(current => current.filter(toast => toast.id !== id));
  }, []);

  const showToast = useCallback((toast: ToastInput): string => {
    nextId.current += 1;
    const id = `toast-${Date.now()}-${nextId.current}`;

    setToasts(current => [
      ...current.slice(-(MAX_VISIBLE_TOASTS - 1)),
      { ...toast, id }
    ]);

    return id;
  }, []);

  const value = useMemo(() => ({
    showToast,
    dismissToast,
    success: (message: string, title?: string) => showToast({ type: 'success', message, title }),
    error: (message: string, title?: string) => showToast({ type: 'error', message, title }),
    warning: (message: string, title?: string) => showToast({ type: 'warning', message, title }),
    info: (message: string, title?: string) => showToast({ type: 'info', message, title })
  }), [dismissToast, showToast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="ui-toast-region" aria-live="polite" aria-relevant="additions">
        {toasts.map(toast => (
          <ToastItem key={toast.id} toast={toast} onDismiss={dismissToast} />
        ))}
      </div>
    </ToastContext.Provider>
  );
};
