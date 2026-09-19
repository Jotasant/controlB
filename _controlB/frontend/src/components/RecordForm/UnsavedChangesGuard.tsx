import { useCallback } from 'react';
import { useBeforeUnload, useBlocker } from 'react-router-dom';
import type { BlockerFunction } from 'react-router-dom';

import { ConfirmModal } from '@/components/ConfirmModal/ConfirmModal';

interface UnsavedChangesGuardProps {
  when: boolean;
  title?: string;
  message?: string;
}

export function UnsavedChangesGuard({
  when,
  title = 'Descartar alterações?',
  message = 'Existem alterações não salvas neste formulário. Se você sair agora, elas serão perdidas.',
}: UnsavedChangesGuardProps) {
  const shouldBlock = useCallback<BlockerFunction>(
    ({ currentLocation, nextLocation }) => (
      when &&
      currentLocation.pathname !== nextLocation.pathname
    ),
    [when],
  );

  const blocker = useBlocker(shouldBlock);

  useBeforeUnload(
    useCallback((event: BeforeUnloadEvent) => {
      if (!when) return;
      event.preventDefault();
      event.returnValue = '';
    }, [when]),
  );

  return (
    <ConfirmModal
      isOpen={blocker.state === 'blocked'}
      onClose={() => {
        if (blocker.state === 'blocked') blocker.reset();
      }}
      onConfirm={() => {
        if (blocker.state === 'blocked') blocker.proceed();
      }}
      title={title}
      subtitle="As informações ainda não foram gravadas"
      message={message}
      confirmText="Sair sem salvar"
      cancelText="Continuar editando"
      type="warning"
    />
  );
}
