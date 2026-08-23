import React, { useMemo, useState } from 'react';
import {
  ArrowDownAZ,
  ArrowUpAZ,
  ChevronDown,
  Filter,
  Plus,
  Search,
  X,
} from 'lucide-react';

import './DataExplorer.scss';

export type DataExplorerFieldType = 'text' | 'number' | 'date' | 'select' | 'boolean';
export type DataExplorerOperator =
  | 'contains'
  | 'equals'
  | 'not_equals'
  | 'greater_than'
  | 'less_than'
  | 'before'
  | 'after'
  | 'is_empty'
  | 'is_not_empty';

export interface DataExplorerOption {
  value: string;
  label: string;
}

export interface DataExplorerField<T> {
  key: string;
  label: string;
  type: DataExplorerFieldType;
  getValue: (item: T) => unknown;
  options?: DataExplorerOption[];
  searchable?: boolean;
  sortable?: boolean;
}

export interface DataExplorerFilter {
  id: string;
  field: string;
  operator: DataExplorerOperator;
  value: string;
}

export interface DataExplorerState {
  query: string;
  filters: DataExplorerFilter[];
  sortBy: string;
  sortOrder: 'asc' | 'desc';
}

interface DataExplorerProps<T> {
  value: DataExplorerState;
  onChange: (state: DataExplorerState) => void;
  fields: DataExplorerField<T>[];
  resultCount?: number;
  placeholder?: string;
  actions?: React.ReactNode;
}

const OPERATOR_LABELS: Record<DataExplorerOperator, string> = {
  contains: 'contém',
  equals: 'é igual a',
  not_equals: 'é diferente de',
  greater_than: 'maior que',
  less_than: 'menor que',
  before: 'antes de',
  after: 'depois de',
  is_empty: 'está vazio',
  is_not_empty: 'não está vazio',
};

const newFilterId = () =>
  globalThis.crypto?.randomUUID?.() ?? `filter-${Date.now()}-${Math.random()}`;

const operatorsFor = (type: DataExplorerFieldType): DataExplorerOperator[] => {
  if (type === 'text') return ['contains', 'equals', 'not_equals', 'is_empty', 'is_not_empty'];
  if (type === 'date') return ['equals', 'before', 'after', 'is_empty', 'is_not_empty'];
  if (type === 'number') {
    return ['equals', 'not_equals', 'greater_than', 'less_than', 'is_empty', 'is_not_empty'];
  }
  return ['equals', 'not_equals', 'is_empty', 'is_not_empty'];
};

const normalize = (value: unknown) => String(value ?? '').trim().toLocaleLowerCase('pt-BR');

const compareFilter = (rawValue: unknown, filter: DataExplorerFilter, field: DataExplorerField<unknown>) => {
  const empty = rawValue === null || rawValue === undefined || String(rawValue).trim() === '';
  if (filter.operator === 'is_empty') return empty;
  if (filter.operator === 'is_not_empty') return !empty;
  if (empty) return false;

  if (field.type === 'number') {
    const left = Number(rawValue);
    const right = Number(filter.value);
    if (!Number.isFinite(left) || !Number.isFinite(right)) return false;
    if (filter.operator === 'greater_than') return left > right;
    if (filter.operator === 'less_than') return left < right;
    if (filter.operator === 'not_equals') return left !== right;
    return left === right;
  }

  if (field.type === 'date') {
    const left = String(rawValue).slice(0, 10);
    const right = filter.value.slice(0, 10);
    if (filter.operator === 'before') return left < right;
    if (filter.operator === 'after') return left > right;
    if (filter.operator === 'not_equals') return left !== right;
    return left === right;
  }

  const left = normalize(rawValue);
  const right = normalize(filter.value);
  if (filter.operator === 'contains') return left.includes(right);
  if (filter.operator === 'not_equals') return left !== right;
  return left === right;
};

const compareSortValues = (left: unknown, right: unknown) => {
  if (left === null || left === undefined || left === '') return 1;
  if (right === null || right === undefined || right === '') return -1;
  if (typeof left === 'number' && typeof right === 'number') return left - right;
  return String(left).localeCompare(String(right), 'pt-BR', {
    numeric: true,
    sensitivity: 'base',
  });
};

export const applyDataExplorer = <T,>(
  items: T[],
  state: DataExplorerState,
  fields: DataExplorerField<T>[],
): T[] => {
  const byKey = new Map(fields.map((field) => [field.key, field]));
  const query = normalize(state.query);

  const filtered = items.filter((item) => {
    const matchesQuery = !query || fields
      .filter((field) => field.searchable !== false)
      .some((field) => normalize(field.getValue(item)).includes(query));
    if (!matchesQuery) return false;

    return state.filters.every((filter) => {
      const field = byKey.get(filter.field);
      if (!field) return true;
      return compareFilter(
        field.getValue(item),
        filter,
        field as DataExplorerField<unknown>,
      );
    });
  });

  const sortField = byKey.get(state.sortBy);
  if (!sortField) return filtered;

  return [...filtered].sort((left, right) => {
    const compared = compareSortValues(sortField.getValue(left), sortField.getValue(right));
    return state.sortOrder === 'asc' ? compared : -compared;
  });
};

export const DataExplorer = <T,>({
  value,
  onChange,
  fields,
  resultCount,
  placeholder = 'Pesquisar registros...',
  actions,
}: DataExplorerProps<T>) => {
  const [filtersOpen, setFiltersOpen] = useState(false);
  const sortableFields = useMemo(
    () => fields.filter((field) => field.sortable !== false),
    [fields],
  );

  const updateFilter = (id: string, patch: Partial<DataExplorerFilter>) => {
    onChange({
      ...value,
      filters: value.filters.map((filter) => filter.id === id ? { ...filter, ...patch } : filter),
    });
  };

  const addFilter = () => {
    const field = fields[0];
    if (!field) return;
    onChange({
      ...value,
      filters: [
        ...value.filters,
        {
          id: newFilterId(),
          field: field.key,
          operator: operatorsFor(field.type)[0],
          value: '',
        },
      ],
    });
    setFiltersOpen(true);
  };

  const removeFilter = (id: string) => {
    onChange({ ...value, filters: value.filters.filter((filter) => filter.id !== id) });
  };

  return (
    <section className="data-explorer" aria-label="Pesquisa, filtros e ordenação">
      <div className="data-explorer__main">
        <label className="data-explorer__search">
          <Search size={15} aria-hidden="true" />
          <span className="sr-only">Pesquisar</span>
          <input
            type="search"
            value={value.query}
            onChange={(event) => onChange({ ...value, query: event.target.value })}
            placeholder={placeholder}
          />
          {value.query && (
            <button
              type="button"
              onClick={() => onChange({ ...value, query: '' })}
              aria-label="Limpar pesquisa"
            >
              <X size={14} />
            </button>
          )}
        </label>

        <div className="data-explorer__controls">
          <button
            type="button"
            className={`data-explorer__control ${filtersOpen ? 'active' : ''}`}
            onClick={() => setFiltersOpen((open) => !open)}
            aria-expanded={filtersOpen}
          >
            <Filter size={14} />
            Filtros
            {value.filters.length > 0 && <span>{value.filters.length}</span>}
            <ChevronDown size={13} />
          </button>

          <label className="data-explorer__sort">
            <span className="sr-only">Ordenar por</span>
            <select
              value={value.sortBy}
              onChange={(event) => onChange({ ...value, sortBy: event.target.value })}
            >
              <option value="">Ordenação padrão</option>
              {sortableFields.map((field) => (
                <option key={field.key} value={field.key}>{field.label}</option>
              ))}
            </select>
          </label>

          <button
            type="button"
            className="data-explorer__direction"
            onClick={() => onChange({
              ...value,
              sortOrder: value.sortOrder === 'asc' ? 'desc' : 'asc',
            })}
            aria-label={value.sortOrder === 'asc' ? 'Ordenação crescente' : 'Ordenação decrescente'}
            title={value.sortOrder === 'asc' ? 'Crescente' : 'Decrescente'}
          >
            {value.sortOrder === 'asc' ? <ArrowDownAZ size={15} /> : <ArrowUpAZ size={15} />}
          </button>

          {actions}
        </div>
      </div>

      {filtersOpen && (
        <div className="data-explorer__filter-builder">
          {value.filters.length === 0 ? (
            <p>Nenhum filtro aplicado. Adicione uma regra usando os campos disponíveis.</p>
          ) : (
            value.filters.map((filter) => {
              const field = fields.find((candidate) => candidate.key === filter.field) ?? fields[0];
              if (!field) return null;
              const noValue = filter.operator === 'is_empty' || filter.operator === 'is_not_empty';
              return (
                <div className="data-explorer__filter-row" key={filter.id}>
                  <select
                    value={field.key}
                    aria-label="Campo do filtro"
                    onChange={(event) => {
                      const nextField = fields.find((candidate) => candidate.key === event.target.value);
                      updateFilter(filter.id, {
                        field: event.target.value,
                        operator: nextField ? operatorsFor(nextField.type)[0] : 'equals',
                        value: '',
                      });
                    }}
                  >
                    {fields.map((candidate) => (
                      <option key={candidate.key} value={candidate.key}>{candidate.label}</option>
                    ))}
                  </select>

                  <select
                    value={filter.operator}
                    aria-label="Operador do filtro"
                    onChange={(event) => updateFilter(filter.id, {
                      operator: event.target.value as DataExplorerOperator,
                    })}
                  >
                    {operatorsFor(field.type).map((operator) => (
                      <option key={operator} value={operator}>{OPERATOR_LABELS[operator]}</option>
                    ))}
                  </select>

                  {!noValue && field.options ? (
                    <select
                      value={filter.value}
                      aria-label="Valor do filtro"
                      onChange={(event) => updateFilter(filter.id, { value: event.target.value })}
                    >
                      <option value="">Selecione...</option>
                      {field.options.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                  ) : !noValue ? (
                    <input
                      type={field.type === 'date' ? 'date' : field.type === 'number' ? 'number' : 'text'}
                      value={filter.value}
                      aria-label="Valor do filtro"
                      onChange={(event) => updateFilter(filter.id, { value: event.target.value })}
                      placeholder="Valor"
                    />
                  ) : <span className="data-explorer__no-value">Sem valor adicional</span>}

                  <button
                    type="button"
                    onClick={() => removeFilter(filter.id)}
                    aria-label={`Remover filtro de ${field.label}`}
                  >
                    <X size={14} />
                  </button>
                </div>
              );
            })
          )}

          <div className="data-explorer__filter-actions">
            <button type="button" onClick={addFilter}>
              <Plus size={14} /> Nova regra
            </button>
            {(value.filters.length > 0 || value.query) && (
              <button
                type="button"
                onClick={() => onChange({ ...value, query: '', filters: [] })}
              >
                Limpar tudo
              </button>
            )}
          </div>
        </div>
      )}

      <div className="data-explorer__summary" aria-live="polite">
        {typeof resultCount === 'number' && `${resultCount} registro${resultCount === 1 ? '' : 's'}`}
        {value.filters.map((filter) => {
          const field = fields.find((candidate) => candidate.key === filter.field);
          if (!field) return null;
          const suffix = ['is_empty', 'is_not_empty'].includes(filter.operator) ? '' : ` ${filter.value}`;
          return (
            <button key={filter.id} type="button" onClick={() => removeFilter(filter.id)}>
              {field.label} {OPERATOR_LABELS[filter.operator]}{suffix}
              <X size={11} />
            </button>
          );
        })}
      </div>
    </section>
  );
};

