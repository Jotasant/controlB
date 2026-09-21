import { useEffect, useRef, useState } from 'react';
import { Download, RefreshCw } from 'lucide-react';
import { chatService, formatApiError } from '@/services/api';
import type { ChatMessage } from '@/types/chat';

export function MediaMessage({ message }: { message: ChatMessage }) {
  const [media, setMedia] = useState<{ url: string; type: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const container = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  const autoPreview = ['IMAGE', 'STICKER'].includes(message.message_type);
  useEffect(() => {
    if (!autoPreview || !container.current) return;
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) { setVisible(true); observer.disconnect(); }
    });
    observer.observe(container.current);
    return () => observer.disconnect();
  }, [autoPreview]);
  useEffect(() => {
    if (!visible) return;
    let cancelled = false; let resource: string | null = null;
    setBusy(true); setError(null);
    void chatService.getMedia(message.id).then((blob) => {
      if (cancelled) return;
      resource = URL.createObjectURL(blob); setMedia({ url: resource, type: blob.type });
    }).catch((err) => { if (!cancelled) setError(formatApiError(err, 'Mídia indisponível. Ela pode ter expirado no WhatsApp.')); })
      .finally(() => { if (!cancelled) setBusy(false); });
    return () => { cancelled = true; if (resource) URL.revokeObjectURL(resource); };
  }, [message.id, visible, attempt]);
  const filename = message.media_filename || `${message.message_type.toLowerCase()}-${message.id}`;
  const isSticker = message.message_type === 'STICKER';
  return <div ref={container} className={`chat-media${isSticker ? ' is-sticker' : ''}`}>
    {media && (isSticker ? (
      <img className="chat-media__sticker-img" src={media.url} alt="Figurinha" />
    ) : media.type.startsWith('image/') ? (
      <a href={media.url} target="_blank" rel="noopener noreferrer"><img src={media.url} alt={message.content || filename} /></a>
    ) : media.type.startsWith('video/') ? (
      <video controls preload="metadata" src={media.url} />
    ) : media.type.startsWith('audio/') ? (
      <audio controls preload="metadata" src={media.url} />
    ) : (
      <span>{filename}</span>
    ))}
    {!media && <button type="button" className="ui-button ui-button--secondary" disabled={busy}
      onClick={() => { setVisible(true); setAttempt((n) => n + 1); }}>{busy ? <RefreshCw size={14} /> : <Download size={14} />}
      {busy ? 'Carregando…' : isSticker ? 'Carregar figurinha' : message.message_type === 'VIDEO' ? 'Carregar vídeo' : filename}</button>}
    {media && !isSticker && <a href={media.url} download={filename}><Download size={13} /> Baixar arquivo</a>}
    {error && <small role="alert">{error}</small>}
  </div>;
}
