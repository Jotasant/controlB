import { useCallback, useEffect, useRef, useState } from 'react';
import { chatService, formatApiError } from '@/services/api';
import type { ChatContact } from '@/types/chat';

export function ContactOriginSelector({ conversationId, canEdit }: { conversationId: string; canEdit: boolean }) {
  const [contact, setContact] = useState<ChatContact | null>(null);
  const [origins, setOrigins] = useState<{ id: string; name: string }[]>([]);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const generation = useRef(0);
  const invalidate = useCallback(() => { ++generation.current; }, []);
  const saving = useRef(false);

  useEffect(() => {
    const version = ++generation.current;
    void Promise.all([chatService.getConversationContact(conversationId), chatService.getContactOrigins()])
      .then(([value, options]) => {
        if (version !== generation.current) return;
        setContact(value); setOrigins(options);
      }).catch((err) => {
        if (version === generation.current) setError(formatApiError(err, 'Não foi possível carregar a origem.'));
      });
    return invalidate;
  }, [conversationId, invalidate]);

  const save = async (payload: { origin_id?: string | null; name?: string }) => {
    if (!canEdit || saving.current) return;
    const version = generation.current;
    saving.current = true; setBusy(true); setError(null);
    try {
      const value = await chatService.updateContactOrigin(conversationId, payload);
      if (version !== generation.current) return;
      setContact(value); setCreating(false); setName('');
      if (value.origin_id && value.origin_name) {
        setOrigins((items) => items.some((item) => item.id === value.origin_id)
          ? items : [...items, { id: value.origin_id!, name: value.origin_name! }]);
      }
    } catch (err) {
      if (version === generation.current) setError(formatApiError(err, 'Não foi possível salvar a origem.'));
    } finally {
      saving.current = false;
      if (version === generation.current) setBusy(false);
    }
  };

  return <div className="chat-widget__origin">
    <label htmlFor={`chat-origin-${conversationId}`}>Canal de aquisição</label>
    <div className="chat-widget__origin-controls">
      <select id={`chat-origin-${conversationId}`} value={contact?.origin_id || ''} disabled={!contact || !canEdit || busy}
        onChange={(event) => void save(event.target.value.startsWith('suggested:')
          ? { name: event.target.value.slice(10) } : { origin_id: event.target.value || null })}>
        <option value="">Não informado</option>
        {origins.map((origin) => <option key={origin.id} value={origin.id}>{origin.name}</option>)}
        {['Instagram', 'Google', 'Lead', 'Facebook', 'Indicação', 'Site'].filter((name) => !origins.some((origin) => origin.name.toLocaleLowerCase() === name.toLocaleLowerCase()))
          .map((name) => <option key={name} value={`suggested:${name}`}>{name}</option>)}
      </select>
      {canEdit && !creating && <button type="button" disabled={busy || !contact} onClick={() => setCreating(true)}>Nova origem</button>}
    </div>
    {creating && <form className="chat-widget__origin-controls" onSubmit={(event) => { event.preventDefault(); if (name.trim()) void save({ name: name.trim() }); }}>
      <input aria-label="Nome da nova origem" maxLength={100} value={name} onChange={(event) => setName(event.target.value)} disabled={busy} placeholder="Ex.: Instagram, Google, campanha" />
      <button type="submit" disabled={busy || !name.trim()}>Salvar</button>
      <button type="button" disabled={busy} onClick={() => setCreating(false)}>Cancelar</button>
    </form>}
    <small>Como este contato chegou até você. Não é o aplicativo usado na conversa. Vale para todas as conversas do contato.</small>
    {error && <p role="alert">{error}</p>}
  </div>;
}
