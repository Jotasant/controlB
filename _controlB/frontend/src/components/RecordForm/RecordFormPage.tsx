import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowLeft,
  ChevronRight,
  Loader2,
  type LucideIcon,
} from 'lucide-react';

import './RecordFormPage.scss';

export interface RecordFormBreadcrumb {
  label: string;
  to?: string;
}

export interface RecordFormTab {
  id: string;
  label: string;
  icon?: LucideIcon;
  badge?: number | string;
  disabled?: boolean;
}

interface RecordFormPageProps {
  title: string;
  eyebrow?: string;
  description?: string;
  recordCode?: string;
  icon?: LucideIcon;
  status?: ReactNode;
  breadcrumbs?: RecordFormBreadcrumb[];
  actions?: ReactNode;
  footer?: ReactNode;
  aside?: ReactNode;
  tabs?: RecordFormTab[];
  activeTab?: string;
  onTabChange?: (tabId: string) => void;
  onBack?: () => void;
  backLabel?: string;
  isLoading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  children?: ReactNode;
}

export function RecordFormPage({
  title,
  eyebrow,
  description,
  recordCode,
  icon: Icon,
  status,
  breadcrumbs = [],
  actions,
  footer,
  aside,
  tabs = [],
  activeTab,
  onTabChange,
  onBack,
  backLabel = 'Voltar',
  isLoading = false,
  error,
  onRetry,
  children,
}: RecordFormPageProps) {
  return (
    <main className="record-form-page" aria-busy={isLoading}>
      <div className="record-form-page__container">
        {breadcrumbs.length > 0 && (
          <nav className="record-form-page__breadcrumbs" aria-label="Navegação estrutural">
            {breadcrumbs.map((item, index) => (
              <span key={`${item.label}-${index}`} className="record-form-page__breadcrumb-item">
                {index > 0 && <ChevronRight size={13} aria-hidden="true" />}
                {item.to ? <Link to={item.to}>{item.label}</Link> : <span aria-current="page">{item.label}</span>}
              </span>
            ))}
          </nav>
        )}

        <header className="record-form-page__header">
          <div className="record-form-page__identity">
            {onBack && (
              <button
                type="button"
                className="record-form-page__back"
                onClick={onBack}
                aria-label={backLabel}
                title={backLabel}
              >
                <ArrowLeft size={18} />
              </button>
            )}

            {Icon && (
              <span className="record-form-page__icon" aria-hidden="true">
                <Icon size={22} />
              </span>
            )}

            <div className="record-form-page__heading">
              {(eyebrow || recordCode) && (
                <div className="record-form-page__eyebrow">
                  {eyebrow && <span>{eyebrow}</span>}
                  {eyebrow && recordCode && <span aria-hidden="true">•</span>}
                  {recordCode && <strong>{recordCode}</strong>}
                </div>
              )}
              <div className="record-form-page__title-row">
                <h1>{title}</h1>
                {status && <div className="record-form-page__status">{status}</div>}
              </div>
              {description && <p>{description}</p>}
            </div>
          </div>

          {actions && <div className="record-form-page__header-actions">{actions}</div>}
        </header>

        {tabs.length > 0 && (
          <div className="record-form-tabs" role="tablist" aria-label="Seções do formulário">
            {tabs.map((tab) => {
              const TabIcon = tab.icon;
              const selected = tab.id === activeTab;
              return (
                <button
                  key={tab.id}
                  type="button"
                  id={`record-form-tab-${tab.id}`}
                  className={`record-form-tabs__button${selected ? ' is-active' : ''}`}
                  role="tab"
                  aria-selected={selected}
                  aria-controls={`record-form-panel-${tab.id}`}
                  tabIndex={selected ? 0 : -1}
                  disabled={tab.disabled}
                  onClick={() => onTabChange?.(tab.id)}
                >
                  {TabIcon && <TabIcon size={16} aria-hidden="true" />}
                  <span>{tab.label}</span>
                  {tab.badge !== undefined && <span className="record-form-tabs__badge">{tab.badge}</span>}
                </button>
              );
            })}
          </div>
        )}

        {isLoading ? (
          <section className="record-form-page__state" aria-live="polite">
            <Loader2 size={24} className="record-form-page__spinner" />
            <strong>Carregando registro...</strong>
            <span>Estamos preparando os dados do formulário.</span>
          </section>
        ) : error ? (
          <section className="record-form-page__state record-form-page__state--error" role="alert">
            <AlertTriangle size={26} />
            <strong>Não foi possível abrir o registro</strong>
            <span>{error}</span>
            {onRetry && (
              <button type="button" className="ui-button ui-button--secondary" onClick={onRetry}>
                Tentar novamente
              </button>
            )}
          </section>
        ) : (
          <div className={`record-form-page__layout${aside ? ' has-aside' : ''}`}>
            <section
              className="record-form-page__content"
              role={tabs.length > 0 ? 'tabpanel' : undefined}
              id={activeTab ? `record-form-panel-${activeTab}` : undefined}
              aria-labelledby={activeTab ? `record-form-tab-${activeTab}` : undefined}
            >
              {children}
            </section>
            {aside && <aside className="record-form-page__aside">{aside}</aside>}
          </div>
        )}
      </div>

      {!isLoading && !error && footer && (
        <footer className="record-form-page__footer">
          <div className="record-form-page__footer-inner">{footer}</div>
        </footer>
      )}
    </main>
  );
}

interface RecordFormSectionProps {
  title?: string;
  description?: string;
  icon?: LucideIcon;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function RecordFormSection({
  title,
  description,
  icon: Icon,
  actions,
  children,
  className = '',
}: RecordFormSectionProps) {
  return (
    <section className={`record-form-section ${className}`.trim()}>
      {(title || description || actions) && (
        <header className="record-form-section__header">
          <div className="record-form-section__heading">
            {Icon && <Icon size={17} aria-hidden="true" />}
            <div>
              {title && <h2>{title}</h2>}
              {description && <p>{description}</p>}
            </div>
          </div>
          {actions && <div className="record-form-section__actions">{actions}</div>}
        </header>
      )}
      <div className="record-form-section__body">{children}</div>
    </section>
  );
}

interface RecordFormGridProps {
  children: ReactNode;
  columns?: 1 | 2 | 3 | 4;
  className?: string;
}

export function RecordFormGrid({ children, columns = 2, className = '' }: RecordFormGridProps) {
  return (
    <div className={`record-form-grid record-form-grid--${columns} ${className}`.trim()}>
      {children}
    </div>
  );
}
