import React, { useEffect } from 'react';
import { X } from 'lucide-react';
import './Modal.scss';

interface ModalProps {
    isOpen: boolean;
    onClose: () => void;
    title: string;
    subtitle?: string;
    children: React.ReactNode;
}

export const Modal: React.FC<ModalProps> = ({ isOpen, onClose, title, subtitle, children }) => {
    // Fecha ao apertar a tecla ESC
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        if (isOpen) {
            document.addEventListener('keydown', handleKeyDown);
            document.body.style.overflow = 'hidden'; // Trava a rolagem de fundo
        }
        return () => {
            document.removeEventListener('keydown', handleKeyDown);
            document.body.style.overflow = 'unset';
        };
    }, [isOpen, onClose]);

    if (!isOpen) return null;

    return (
        <div className="modal-backdrop" onClick={onClose}>
            <div className="modal-card" onClick={(e) => e.stopPropagation()}>
                {/* Cabeçalho do Modal */}
                <header className="modal-header">
                    <div>
                        <h2>{title}</h2>
                        {subtitle && <p>{subtitle}</p>}
                    </div>
                    <button className="btn-close" onClick={onClose} title="Fechar">
                        <X size={16} />
                    </button>
                </header>
                {/* Corpo do Formulário */}
                <div className="modal-body">
                    {children}
                </div>
            </div>
        </div>
    );
};
