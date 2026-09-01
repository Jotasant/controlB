import React from 'react';
import { CheckSquare, Trash2, X, Loader2 } from 'lucide-react';
import './BulkActionsBar.scss';

export interface BulkActionsBarProps {
  selectedCount: number;
  resourceName?: {
    singular: string;
    plural: string;
  };
  onClear: () => void;
  onDelete?: () => void;
  deleteLabel?: string;
  isDeleting?: boolean;
  children?: React.ReactNode;
}

export const BulkActionsBar: React.FC<BulkActionsBarProps> = ({
  selectedCount,
  resourceName = { singular: 'item', plural: 'itens' },
  onClear,
  onDelete,
  deleteLabel = 'Excluir Selecionados',
  isDeleting = false,
  children,
}) => {
  if (selectedCount <= 0) return null;

  return (
    <div className="bulk-actions-bar" role="region" aria-label="Ações em massa">
      <div className="bulk-actions-info">
        <span className="bulk-icon-wrapper">
          <CheckSquare size={16} />
        </span>
        <span className="bulk-count-label">
          <strong>{selectedCount}</strong> {selectedCount === 1 ? resourceName.singular : resourceName.plural} {selectedCount === 1 ? 'selecionado' : 'selecionados'}
        </span>
      </div>

      <div className="bulk-actions-buttons">
        {children}

        {onDelete && (
          <button
            type="button"
            className="bulk-btn bulk-btn--danger"
            onClick={onDelete}
            disabled={isDeleting}
            title={deleteLabel}
          >
            {isDeleting ? (
              <>
                <Loader2 size={14} className="spinning" />
                <span>Excluindo...</span>
              </>
            ) : (
              <>
                <Trash2 size={14} />
                <span>{deleteLabel}</span>
              </>
            )}
          </button>
        )}

        <button
          type="button"
          className="bulk-btn bulk-btn--clear"
          onClick={onClear}
          disabled={isDeleting}
          title="Desmarcar todos os registros"
        >
          <X size={14} />
          <span>Desmarcar</span>
        </button>
      </div>
    </div>
  );
};

export default BulkActionsBar;
