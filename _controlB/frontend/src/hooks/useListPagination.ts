import { useEffect, useMemo, useState } from 'react';

export interface UseListPaginationReturn<T> {
  page: number;
  pageSize: number;
  pageCount: number;
  totalItems: number;
  firstItem: number;
  lastItem: number;
  pageItems: T[];
  setPage: (page: number) => void;
  setPageSize: (pageSize: number) => void;
}

/**
 * Pagina uma coleção que já foi filtrada pela tela. O valor 0 representa
 * "todos" e é útil em cadastros pequenos sem perder a escolha do usuário.
 */
export function useListPagination<T>(
  items: T[],
  initialPageSize = 25,
): UseListPaginationReturn<T> {
  const [page, setCurrentPage] = useState(1);
  const [pageSize, setCurrentPageSize] = useState(initialPageSize);
  const totalItems = items.length;
  const effectivePageSize = pageSize === 0 ? Math.max(totalItems, 1) : pageSize;
  const pageCount = Math.max(1, Math.ceil(totalItems / effectivePageSize));

  useEffect(() => {
    setCurrentPage((current) => Math.min(current, pageCount));
  }, [pageCount]);

  const setPage = (nextPage: number) => {
    setCurrentPage(Math.min(Math.max(nextPage, 1), pageCount));
  };

  const setPageSize = (nextPageSize: number) => {
    setCurrentPageSize(nextPageSize);
    setCurrentPage(1);
  };

  const pageItems = useMemo(() => {
    if (pageSize === 0) return items;
    const start = (page - 1) * pageSize;
    return items.slice(start, start + pageSize);
  }, [items, page, pageSize]);

  const firstItem = totalItems === 0 ? 0 : (page - 1) * effectivePageSize + 1;
  const lastItem = Math.min(page * effectivePageSize, totalItems);

  return {
    page,
    pageSize,
    pageCount,
    totalItems,
    firstItem,
    lastItem,
    pageItems,
    setPage,
    setPageSize,
  };
}

