/**
 * context/ThemeContext.tsx - Gerenciador Global de Temas (Dark / Light)
 * 
 * Permite alternar entre o tema Escuro (Dark) e Claro (Light),
 * persistindo a preferência do usuário no localStorage e
 * aplicando o atributo data-theme no <html> do documento.
 */

import React, { createContext, useContext, useEffect, useState } from 'react';

type Theme = 'dark' | 'light';

interface ThemeContextType {
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // Lê do localStorage ou usa 'dark' como padrão
  const [theme, setThemeState] = useState<Theme>(() => {
    const saved = localStorage.getItem('controlb_theme') as Theme | null;
    return saved === 'light' ? 'light' : 'dark';
  });

  const setTheme = (newTheme: Theme) => {
    setThemeState(newTheme);
    localStorage.setItem('controlb_theme', newTheme);
    document.documentElement.setAttribute('data-theme', newTheme);
  };

  const toggleTheme = () => {
    setTheme(theme === 'dark' ? 'light' : 'dark');
  };

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = (): ThemeContextType => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme deve ser utilizado dentro de um ThemeProvider');
  }
  return context;
};
