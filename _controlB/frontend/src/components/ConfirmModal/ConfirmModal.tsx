import React from 'react';
import { AlertTriangle, Trash2, Info, CheckCircle, X, Loader2 } from 'lucide-react';
import './ConfirmModal.scss';

export type ConfirmModalType = 'danger' | 'warning' | 'info' | 'success';

export interface ConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void | Promise<void>;
  title: string;
  subtitle?: string;
  message: React.ReactNode;
  confirmText?: string;
  cancelText?: string;
  type?: ConfirmModalType;
  isLoading?: boolean;
  errorMessage?: string | null;
}

export const ConfirmModal: React.FC<ConfirmModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  title,
  subtitle,
  message,
  confirmText = 'Confirmar Exclusão',
  cancelText = 'Cancelar',
  type = 'danger',
  isLoading = false,
  errorMessage = null,
}) => {
  if (!isOpen) return null;

  const renderIcon = () => {
    switch (type) {
      case 'danger':
        return <Trash2 className="icon-main danger" size={24} />;
      case 'warning':
        return <AlertTriangle className="icon-main warning" size={24} />;
      case 'success':
        return <CheckCircle className="icon-main success" size={24} />;
      case 'info':
      default:
        return <Info className="icon-main info" size={24} />;
    }
  };

  return (
    <div className="confirm-modal-backdrop" onClick={isLoading ? undefined : onClose}>
      <div className={`confirm-modal-card type-${type}`} onClick={(e) => e.stopPropagation()}>
        {/* Cabeçalho */}
        <div className="confirm-modal-header">
          <div className={`icon-container ${type}`}>
            {renderIcon()}
          </div>
          <div className="title-wrap">
            <h3>{title}</h3>
            {subtitle && <p className="subtitle">{subtitle}</p>}
          </div>
          {!isLoading && (
            <button className="btn-close-confirm" onClick={onClose} title="Fechar">
              <X size={16} />
            </button>
          )}
        </div>

        {/* Mensagem e Detalhes */}
        <div className="confirm-modal-body">
          <div className="message-content">{message}</div>

          {errorMessage && (
            <div className="confirm-modal-error-banner">
              <AlertTriangle size={15} />
              <span>{errorMessage}</span>
            </div>
          )}
        </div>

        {/* Rodapé / Ações */}
        <div className="confirm-modal-footer">
          <button
            type="button"
            className="btn-confirm-cancel"
            onClick={onClose}
            disabled={isLoading}
          >
            {cancelText}
          </button>
          <button
            type="button"
            className={`btn-confirm-action ${type}`}
            onClick={onConfirm}
            disabled={isLoading}
          >
            {isLoading ? (
              <>
                <Loader2 size={16} className="spinning" />
                <span>Processando...</span>
              </>
            ) : (
              <>
                {type === 'danger' && <Trash2 size={15} />}
                <span>{confirmText}</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
