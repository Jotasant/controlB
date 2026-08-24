import React, { useEffect, useId, useRef } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import './Modal.scss';

interface ModalProps {
    isOpen: boolean;
    onClose: () => void;
    title: string;
    subtitle?: string;
    size?: 'sm' | 'md' | 'lg' | 'xl';
    children: React.ReactNode;
}

export const Modal: React.FC<ModalProps> = ({ 
    isOpen, 
    onClose, 
    title, 
    subtitle, 
    size = 'md',
    children 
}) => {
    const dialogRef = useRef<HTMLDivElement>(null);
    const onCloseRef = useRef(onClose);
    const titleId = useId();
    const subtitleId = useId();

    useEffect(() => {
        onCloseRef.current = onClose;
    }, [onClose]);

    useEffect(() => {
        if (!isOpen) return;

        const previouslyFocusedElement = document.activeElement as HTMLElement | null;
        const previousBodyOverflow = document.body.style.overflow;
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onCloseRef.current();
        };

        document.addEventListener('keydown', handleKeyDown);
        document.body.style.overflow = 'hidden';
        dialogRef.current?.focus();

        return () => {
            document.removeEventListener('keydown', handleKeyDown);
            document.body.style.overflow = previousBodyOverflow;
            previouslyFocusedElement?.focus();
        };
    }, [isOpen]);

    if (!isOpen) return null;

    return createPortal(
        <div className="modal-backdrop" onClick={onClose}>
            <div
                ref={dialogRef}
                className={`modal-card size-${size}`}
                role="dialog"
                aria-modal="true"
                aria-labelledby={titleId}
                aria-describedby={subtitle ? subtitleId : undefined}
                tabIndex={-1}
                onClick={(e) => e.stopPropagation()}
            >
                {/* Cabeçalho do Modal */}
                <header className="modal-header">
                    <div>
                        <h2 id={titleId}>{title}</h2>
                        {subtitle && <p id={subtitleId}>{subtitle}</p>}
                    </div>
                    <button
                        type="button"
                        className="btn-close"
                        onClick={onClose}
                        title="Fechar"
                        aria-label="Fechar modal"
                    >
                        <X size={16} />
                    </button>
                </header>
                {/* Corpo do Formulário */}
                <div className="modal-body">
                    {children}
                </div>
            </div>
        </div>,
        document.body,
    );
};
