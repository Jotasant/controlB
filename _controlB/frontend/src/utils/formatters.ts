/**
 * utils/formatters.ts - Central de Formatação Numérica e Monetária do ControlB
 * 
 * Regras de Apresentação:
 * 1. Moeda (BRL): Formata valores monetários sempre com 2 casas decimais (ex: R$ 25,12).
 * 2. Quantidade/Estoque: Omite zeros decimais desnecessários (ex: 1.0000 -> "1", 2.5000 -> "2,5").
 * 3. Inputs Numéricos: Sanitiza números para preenchimento de campos HTML input type="number".
 */

/**
 * Formata valores monetários no padrão Real Brasileiro (R$ 0,00).
 */
export const formatCurrency = (val: number | string | undefined | null): string => {
  if (val === undefined || val === null || val === '') return 'R$ 0,00';
  const num = typeof val === 'string' ? parseFloat(val) : Number(val);
  if (isNaN(num)) return 'R$ 0,00';
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(num);
};

/**
 * Formata quantidades de estoque e unidades de medida de forma inteligente:
 * - Se for número inteiro (ex: 1.0000, 21.0000), retorna "1", "21".
 * - Se tiver decimais reais (ex: 2.5000, 0.7500), retorna "2,5", "0,75" (até no máximo 3 casas decimais).
 */
export const formatQuantity = (val: number | string | undefined | null): string => {
  if (val === undefined || val === null || val === '') return '0';
  const num = typeof val === 'string' ? parseFloat(val) : Number(val);
  if (isNaN(num)) return '0';
  return num.toLocaleString('pt-BR', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 3
  });
};

/**
 * Prepara valores monetários para inputs HTML (<input type="number" step="0.01" />):
 * Converte "25.1200" ou 25.1200 para "25.12".
 */
export const formatPriceInput = (val: number | string | undefined | null): string => {
  if (val === undefined || val === null || val === '') return '0.00';
  const num = typeof val === 'string' ? parseFloat(val) : Number(val);
  if (isNaN(num)) return '0.00';
  return num.toFixed(2);
};

/**
 * Prepara quantidades para inputs HTML (<input type="number" step="any" />):
 * Converte "1.0000" para "1" ou "2.5000" para "2.5".
 */
export const formatQuantityInput = (val: number | string | undefined | null): string => {
  if (val === undefined || val === null || val === '') return '0';
  const num = typeof val === 'string' ? parseFloat(val) : Number(val);
  if (isNaN(num)) return '0';
  return String(Number(num.toFixed(3)));
};
