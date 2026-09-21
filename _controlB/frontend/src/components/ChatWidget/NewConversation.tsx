import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { chatService, identityService, formatApiError } from '@/services/api';
import type { ContactDirectoryEntry } from '@/types';
import type { ChatChannel, ChatConversation } from '@/types/chat';
import { useChatUi } from './ChatContext';

export function NewConversation({ initialContactId, onStarted, onCancel }: {
  initialContactId?: string; onStarted: (conversation: ChatConversation) => void; onCancel: () => void;
}) {
  const chat = useChatUi();
  const [channels, setChannels] = useState<ChatChannel[]>([]);
  const [contacts, setContacts] = useState<ContactDirectoryEntry[]>([]);
  const [connectionId, setConnectionId] = useState('');
  const [contactId, setContactId] = useState(initialContactId || '');
  const [search, setSearch] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pending = useRef(false);
  const request = useRef(0);
  const invalidate = useCallback(() => { ++request.current; }, []);
  useEffect(() => {
    let cancelled = false;
    void chatService.getChannels().then((items) => {
      if (!cancelled) { setChannels(items); if (items.length === 1) setConnectionId(items[0].id); }
    }).catch((err) => { if (!cancelled) setError(formatApiError(err, 'Não foi possível carregar as instâncias.')); });
    return () => { cancelled = true; invalidate(); };
  }, [invalidate]);
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const timer = window.setTimeout(() => {
      void identityService.getContactDirectory({ is_active: true, page_size: 50,
        ...(initialContactId && !search ? { contact_id: initialContactId } : { search }) })
        .then((page) => { if (!cancelled) { setContacts(page.items); setLoading(false); } })
        .catch((err) => { if (!cancelled) { setLoading(false); setError(formatApiError(err, 'Não foi possível carregar os contatos.')); } });
    }, 200);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [initialContactId, search]);
  const start = async () => {
    if (pending.current || !connectionId || !contactId) return;
    const version = ++request.current;
    pending.current = true; setBusy(true); setError(null);
    try {
      const conversation = await chatService.startConversation(connectionId, contactId);
      if (version === request.current) onStarted(conversation);
    } catch (err) {
      if (version === request.current) setError(formatApiError(err, 'Não foi possível iniciar a conversa.'));
    } finally {
      if (version === request.current) { pending.current = false; setBusy(false); }
    }
  };
  return <form className="chat-widget__new ui-form" onSubmit={(event) => { event.preventDefault(); event.stopPropagation(); void start(); }}>
    <h3>Nova conversa</h3>
    <label>Instância de atendimento<select value={connectionId} disabled={busy} onChange={(event) => setConnectionId(event.target.value)}>
      <option value="">Selecione a instância</option>{channels.map((channel) => <option value={channel.id} key={channel.id}>{channel.name} · {channel.instance_phone ? `+${channel.instance_phone}` : 'Número não confirmado'}</option>)}
    </select></label>
    <label>Buscar contato<input value={search} disabled={busy} placeholder="Nome ou telefone" onChange={(event) => { setSearch(event.target.value); setContactId(''); }} /></label>
    <label>Contato da organização<select value={contactId} disabled={busy || loading} onChange={(event) => setContactId(event.target.value)}>
      <option value="">{loading ? 'Carregando…' : 'Selecione um contato'}</option>{contacts.map((contact) => <option value={contact.id} key={contact.id}>{contact.name} · {contact.phone || contact.mobile || 'Sem telefone'}</option>)}
    </select></label>
    <small>Busque pelo nome para localizar outros contatos. O número deve incluir DDI e DDD. Nenhuma mensagem será enviada automaticamente.</small>
    <Link to="/contatos/novo" onClick={(event) => { if (busy) event.preventDefault(); else chat.close(); }}>Cadastrar um novo contato</Link>
    {error && <p role="alert">{error}</p>}
    <div className="chat-widget__actions">
      <button type="button" disabled={busy} onClick={onCancel}>Voltar</button>
      <button type="submit" disabled={busy || loading || !contactId || !connectionId}>{busy ? 'Abrindo…' : 'Iniciar conversa'}</button>
    </div>
  </form>;
}
