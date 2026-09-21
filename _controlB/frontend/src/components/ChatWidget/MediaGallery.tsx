import { useEffect, useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import { chatService, formatApiError } from '@/services/api';
import type { ChatMessagePage } from '@/types/chat';
import { MediaMessage } from './MediaMessage';

export function MediaGallery({ conversationId, onBack }: { conversationId: string; onBack: () => void }) {
  const [search, setSearch] = useState(''); const [kind, setKind] = useState('');
  const [page, setPage] = useState(1); const [result, setResult] = useState<ChatMessagePage | null>(null);
  const [busy, setBusy] = useState(false); const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    setBusy(true); setResult(null); setError(null);
    const timer = window.setTimeout(() => {
      void chatService.getGallery(conversationId, { page, page_size: 12, search: search || undefined, kind: kind || undefined })
        .then((data) => { if (!cancelled) setResult(data); })
        .catch((err) => { if (!cancelled) setError(formatApiError(err, 'Não foi possível carregar as mídias.')); })
        .finally(() => { if (!cancelled) setBusy(false); });
    }, 250);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [conversationId, page, kind, search]);
  return <section className="chat-gallery" aria-label="Mídias do canal">
    <button type="button" className="ui-button ui-button--secondary" onClick={onBack}><ArrowLeft size={14} /> Voltar à conversa</button>
    <strong>Mídias e arquivos</strong>
    <input aria-label="Buscar mídias" placeholder="Nome do arquivo, legenda ou remetente" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
    <select aria-label="Tipo de mídia" value={kind} onChange={(e) => { setKind(e.target.value); setPage(1); }}><option value="">Todos os tipos</option><option value="IMAGE">Imagens</option><option value="VIDEO">Vídeos</option><option value="DOCUMENT">Documentos</option><option value="AUDIO">Áudios</option><option value="STICKER">Figurinhas</option></select>
    {error && <small role="alert">{error}</small>}
    {busy ? <p>Carregando…</p> : <div className="chat-gallery__grid">{result?.items.map((message) => <article key={message.id}>
      <MediaMessage message={message} /><small>{message.sender_name || message.author_name || 'WhatsApp'} · {new Date(message.occurred_at).toLocaleDateString('pt-BR')}</small>
      {message.content && <p>{message.content}</p>}
    </article>)}</div>}
    {!busy && result?.total === 0 && <p>Nenhuma mídia encontrada.</p>}
    <div className="chat-widget__pagination"><button type="button" disabled={busy || page === 1} onClick={() => setPage((n) => n - 1)}>Anterior</button>
      <span>{page} / {Math.max(1, Math.ceil((result?.total || 0) / 12))}</span><button type="button" disabled={busy || !result || page * 12 >= result.total} onClick={() => setPage((n) => n + 1)}>Próxima</button></div>
  </section>;
}
