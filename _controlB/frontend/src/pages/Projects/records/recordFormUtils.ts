export const toDateInput = (value?: string | null): string => value ? value.slice(0, 10) : '';

export const toDateTimeInput = (value?: string | null): string => value ? value.slice(0, 16) : '';

export const emptyToUndefined = (value?: string | null): string | undefined => value?.trim() || undefined;

export const serializeForm = (value: unknown): string => JSON.stringify(value);

export const statusLabel = (value?: string | null): string => {
  if (!value) return 'Novo';
  const labels: Record<string, string> = {
    draft: 'Rascunho',
    planning: 'Planejamento',
    scheduled: 'Agendada',
    open: 'Aberta',
    todo: 'A fazer',
    in_progress: 'Em andamento',
    in_review: 'Em revisão',
    review: 'Em revisão',
    blocked: 'Bloqueada',
    on_hold: 'Em espera',
    completed: 'Concluída',
    done: 'Concluída',
    resolved: 'Resolvida',
    closed: 'Encerrada',
    cancelled: 'Cancelada',
  };
  return labels[value.toLowerCase()] || value.replaceAll('_', ' ');
};
