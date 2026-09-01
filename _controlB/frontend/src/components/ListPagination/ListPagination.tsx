import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import './ListPagination.scss';

export interface ListPaginationProps {
  page: number;
  pageSize: number;
  pageCount: number;
  totalItems: number;
  firstItem: number;
  lastItem: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  pageSizeOptions?: number[];
}

export const ListPagination: React.FC<ListPaginationProps> = ({
  page,
  pageSize,
  pageCount,
  totalItems,
  firstItem,
  lastItem,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [10, 25, 50, 100, 0],
}) => (
  <div className="list-pagination" role="navigation" aria-label="Paginação dos registros">
    <label className="list-pagination__size">
      <span>Registros por página</span>
      <select
        value={pageSize}
        onChange={(event) => onPageSizeChange(Number(event.target.value))}
        aria-label="Quantidade de registros por página"
      >
        {pageSizeOptions.map((option) => (
          <option key={option} value={option}>{option === 0 ? 'Todos' : option}</option>
        ))}
      </select>
    </label>

    <span className="list-pagination__summary" aria-live="polite">
      {totalItems === 0 ? 'Nenhum registro' : `${firstItem}–${lastItem} de ${totalItems}`}
    </span>

    <div className="list-pagination__buttons">
      <button type="button" onClick={() => onPageChange(page - 1)} disabled={page <= 1} aria-label="Página anterior">
        <ChevronLeft size={16} />
      </button>
      <span>Página {page} de {pageCount}</span>
      <button type="button" onClick={() => onPageChange(page + 1)} disabled={page >= pageCount} aria-label="Próxima página">
        <ChevronRight size={16} />
      </button>
    </div>
  </div>
);

export default ListPagination;

