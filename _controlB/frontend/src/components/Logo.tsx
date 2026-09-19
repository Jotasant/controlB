/**
 * components/Logo.tsx - Componente de Logotipo Oficial ControlB
 * 
 * Utiliza a imagem oficial anexada em `src/assets/logo.png`.
 */

import React from 'react';
import logoImg from '@/assets/logo.png';

interface LogoProps {
  size?: number;
  showText?: boolean;
  className?: string;
}

export const Logo: React.FC<LogoProps> = ({ size = 26, showText = true, className = '' }) => {
  return (
    <div 
      className={`controlb-brand-logo ${className}`} 
      style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}
    >
      {/* Imagem Oficial da Marca */}
      <img
        src={logoImg}
        alt="ControlB Logo"
        width={size}
        height={size}
        style={{
          width: `${size}px`,
          height: `${size}px`,
          objectFit: 'contain',
          display: 'block',
          flexShrink: 0,
        }}
      />

      {/* Tipografia da Marca */}
      {showText && (
        <span 
          className="brand-title" 
          style={{ 
            fontSize: `${Math.max(size * 0.65, 14)}px`, 
            fontWeight: 700, 
            letterSpacing: '-0.4px',
            color: 'var(--text-primary)',
            lineHeight: 1,
            userSelect: 'none'
          }}
        >
          Control<span style={{ color: 'var(--accent-brand, #ff5500)' }}>B</span>
        </span>
      )}
    </div>
  );
};
