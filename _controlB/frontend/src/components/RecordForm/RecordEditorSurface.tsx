import { useEffect, useState, type ComponentProps } from 'react';
import { useLocation } from 'react-router-dom';
import { FileText } from 'lucide-react';
import { Modal } from '@/components/Modal/Modal';
import { RecordFormPage, type RecordFormTab } from './RecordFormPage';
import { UnsavedChangesGuard } from './UnsavedChangesGuard';
import './RecordEditorSurface.scss';

type Props = ComponentProps<typeof Modal> & {
  page?: boolean;
  saving?: boolean;
  tabs?: RecordFormTab[];
  activeTab?: string;
  onTabChange?: (id: string) => void;
  resetKey?: unknown;
};

/** Reuses the editor's business rules, without mounting a dialog or locking body scroll. */
export function RecordEditorSurface({ page, saving, tabs, activeTab, onTabChange, resetKey, ...props }: Props) {
  const [dirty, setDirty] = useState(false);
  useEffect(() => setDirty(false), [resetKey]);
  const location = useLocation();
  if (!page) return <Modal {...props} />;
  if (!props.isOpen) return null;
  const moduleName = location.pathname.startsWith('/crm') ? 'CRM' : 'Vendas';
  return <div className="commercial-record-editor" onChangeCapture={() => setDirty(true)}
    onClickCapture={(event) => { if ((event.target as HTMLElement).closest('[data-record-change]')) setDirty(true); }}
    onInvalidCapture={(event) => {
      const panel = (event.target as HTMLElement).closest<HTMLElement>('[data-record-tab]');
      if (panel?.dataset.recordTab && panel.hidden) {
        event.preventDefault();
        onTabChange?.(panel.dataset.recordTab);
        requestAnimationFrame(() => (event.target as HTMLElement).focus());
      }
    }}>
    <RecordFormPage title={props.title} description={props.subtitle} eyebrow={moduleName} icon={FileText}
      onBack={props.onClose} breadcrumbs={[{ label: moduleName }, { label: props.title }]}
      tabs={tabs} activeTab={activeTab} onTabChange={onTabChange}>
      <div className="commercial-record-editor__body ui-form">{props.children}</div>
    </RecordFormPage>
    <UnsavedChangesGuard when={dirty && !saving} />
  </div>;
}
