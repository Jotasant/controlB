/**
 * main.tsx - Ponto de Entrada do React (Bootstrap)
 */

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './index.scss';

const rootElement = document.getElementById('root');

if (!rootElement) {
  throw new Error('Elemento raiz #root não foi encontrado no HTML.');
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>
);
