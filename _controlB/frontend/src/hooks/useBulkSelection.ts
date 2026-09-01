/**
 * hooks/useBulkSelection.ts - Gerenciador de Estado de Seleção em Lote (Bulk Actions)
 * 
 * Abstração reutilizável com estrutura Set<string> para operações O(1) de seleção unitária,
 * seleção em massa de itens visíveis/filtrados, estado indeterminado e desmarcação global.
 */

import { useState, useCallback, useMemo } from 'react';

export interface Identifiable {
  id: string;
}

export interface UseBulkSelectionReturn<T extends Identifiable> {
  selectedIds: Set<string>;
  selectedIdList: string[];
  selectedCount: number;
  isSelected: (id: string) => boolean;
  toggleSelect: (id: string) => void;
  select: (id: string) => void;
  deselect: (id: string) => void;
  toggleSelectAll: (items: T[]) => void;
  selectAll: (items: T[]) => void;
  deselectAll: () => void;
  clearSelection: () => void;
  isAllSelected: (items: T[]) => boolean;
  isIndeterminate: (items: T[]) => boolean;
  getSelectedItems: (items: T[]) => T[];
}

export function useBulkSelection<T extends Identifiable>(
  initialSelectedIds: string[] = []
): UseBulkSelectionReturn<T> {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(
    () => new Set(initialSelectedIds)
  );

  const isSelected = useCallback(
    (id: string) => selectedIds.has(id),
    [selectedIds]
  );

  const toggleSelect = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const select = useCallback((id: string) => {
    setSelectedIds((prev) => {
      if (prev.has(id)) return prev;
      const next = new Set(prev);
      next.add(id);
      return next;
    });
  }, []);

  const deselect = useCallback((id: string) => {
    setSelectedIds((prev) => {
      if (!prev.has(id)) return prev;
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  }, []);

  const isAllSelected = useCallback(
    (items: T[]) => {
      if (items.length === 0) return false;
      return items.every((item) => selectedIds.has(item.id));
    },
    [selectedIds]
  );

  const isIndeterminate = useCallback(
    (items: T[]) => {
      if (items.length === 0) return false;
      const count = items.filter((item) => selectedIds.has(item.id)).length;
      return count > 0 && count < items.length;
    },
    [selectedIds]
  );

  const selectAll = useCallback((items: T[]) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      items.forEach((item) => next.add(item.id));
      return next;
    });
  }, []);

  const deselectAll = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  const toggleSelectAll = useCallback(
    (items: T[]) => {
      if (isAllSelected(items)) {
        // Se todos os itens visíveis já estão selecionados, desmarca apenas eles (ou limpa tudo)
        setSelectedIds((prev) => {
          const next = new Set(prev);
          items.forEach((item) => next.delete(item.id));
          return next;
        });
      } else {
        // Marca todos os itens visíveis
        selectAll(items);
      }
    },
    [isAllSelected, selectAll]
  );

  const clearSelection = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  const getSelectedItems = useCallback(
    (items: T[]) => items.filter((item) => selectedIds.has(item.id)),
    [selectedIds]
  );

  const selectedIdList = useMemo(() => Array.from(selectedIds), [selectedIds]);
  const selectedCount = selectedIds.size;

  return {
    selectedIds,
    selectedIdList,
    selectedCount,
    isSelected,
    toggleSelect,
    select,
    deselect,
    toggleSelectAll,
    selectAll,
    deselectAll,
    clearSelection,
    isAllSelected,
    isIndeterminate,
    getSelectedItems,
  };
}
