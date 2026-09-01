import React from 'react';
import { ExternalLink } from 'lucide-react';
import { Link } from 'react-router-dom';

import { buildDocumentHref, buildRecordHref } from './recordNavigation';
import './RecordLink.scss';

interface RecordLinkProps {
  type: string;
  id?: string | null;
  children: React.ReactNode;
  className?: string;
  title?: string;
  view?: string;
  showIcon?: boolean;
}

export const RecordLink: React.FC<RecordLinkProps> = ({
  type,
  id,
  children,
  className = '',
  title,
  view,
  showIcon = true,
}) => {
  const href = id ? buildRecordHref(type, id, view) : null;
  if (!href) return <span className={className}>{children}</span>;

  return (
    <Link
      to={href}
      className={`ui-record-link ${className}`.trim()}
      title={title || 'Abrir registro vinculado'}
      onClick={(event) => event.stopPropagation()}
    >
      <span>{children}</span>
      {showIcon && <ExternalLink size={12} aria-hidden="true" />}
    </Link>
  );
};

interface DocumentLinkProps {
  documentId?: string | null;
  children: React.ReactNode;
  className?: string;
  title?: string;
  showIcon?: boolean;
}

/** Abre o cabeçalho canônico na Central quando só o ID global está disponível. */
export const DocumentLink: React.FC<DocumentLinkProps> = ({
  documentId,
  children,
  className = '',
  title,
  showIcon = true,
}) => {
  if (!documentId) return <span className={className}>{children}</span>;

  return (
    <Link
      to={buildDocumentHref(documentId)}
      className={`ui-record-link ${className}`.trim()}
      title={title || 'Abrir documento de origem'}
      onClick={(event) => event.stopPropagation()}
    >
      <span>{children}</span>
      {showIcon && <ExternalLink size={12} aria-hidden="true" />}
    </Link>
  );
};
