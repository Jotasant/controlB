import { useEffect, useRef, useState } from 'react';
import { chatService, formatApiError } from '@/services/api';
import type { ChatMessage } from '@/types/chat';
import { MessageText } from './MessageText';

const STATUS: Record<ChatMessage['transcription_status'], string> = {
  NOT_REQUESTED: 'Transcrição não solicitada.',
  NOT_CONFIGURED: 'Transcrição pendente de configuração no servidor.',
  PENDING: 'Áudio na fila de transcrição…',
  DONE: 'Transcrição automática — pode conter imprecisões.',
  FAILED: 'Não foi possível transcrever este áudio.',
};

export function AudioMessage({ message, canTranscribe, onUpdate }: {
  message: ChatMessage; canTranscribe: boolean; onUpdate: (message: ChatMessage) => void;
}) {
  const [url, setUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const resource = useRef<string | null>(null);
  const request = useRef(0);
  const busyRef = useRef(false);
  const updateRef = useRef(onUpdate);
  useEffect(() => { updateRef.current = onUpdate; }, [onUpdate]);

  // Também atualiza áudios antigos, fora da primeira página de mensagens.
  useEffect(() => {
    if (message.transcription_status !== 'PENDING') return;
    let cancelled = false;
    let timer: number;
    const poll = async () => {
      try {
        if (document.visibilityState === 'visible') {
          const updated = await chatService.getTranscription(message.id);
          if (!cancelled) updateRef.current(updated);
          if (updated.transcription_status !== 'PENDING') return;
        }
      } catch { /* A atualização principal do chat verifica perda de acesso. */ }
      if (!cancelled) timer = window.setTimeout(() => void poll(), 5000);
    };
    timer = window.setTimeout(() => void poll(), 5000);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [message.id, message.transcription_status]);

  useEffect(() => () => {
    ++request.current;
    if (resource.current) URL.revokeObjectURL(resource.current);
  }, []);

  const perform = async (transcribe = false) => {
    if (busyRef.current) return;
    const version = ++request.current;
    busyRef.current = true; setBusy(true); setError(null);
    try {
      if (transcribe) {
        const result = await chatService.transcribe(message.id);
        if (version === request.current) onUpdate(result);
      } else {
        const blob = await chatService.getAudio(message.id);
        if (version !== request.current) return;
        if (resource.current) URL.revokeObjectURL(resource.current);
        resource.current = URL.createObjectURL(blob);
        setUrl(resource.current);
      }
    } catch (err) {
      if (version === request.current) setError(formatApiError(err, transcribe
        ? 'Não foi possível solicitar a transcrição.'
        : 'Áudio indisponível. Verifique seu acesso ou tente novamente; a mídia pode ter expirado.'));
    } finally {
      if (version === request.current) { busyRef.current = false; setBusy(false); }
    }
  };

  return <div className="chat-widget__audio">
    {url ? <audio controls preload="none" src={url} aria-label="Mensagem de áudio"
      onError={() => setError('Este navegador não conseguiu reproduzir o formato do áudio.')} />
      : <button type="button" className="ui-button ui-button--secondary" disabled={busy}
        onClick={() => void perform()}>{busy ? 'Aguarde…' : 'Carregar áudio'}</button>}
    {message.transcription && <MessageText text={message.transcription} />}
    <small role="status">{message.transcription_status === 'DONE' && !message.transcription
      ? 'Nenhuma fala identificada.' : STATUS[message.transcription_status]}</small>
    {canTranscribe && !['PENDING', 'DONE'].includes(message.transcription_status) &&
      <button type="button" className="ui-button ui-button--secondary" disabled={busy}
        onClick={() => void perform(true)}>{message.transcription_status === 'FAILED' ? 'Tentar transcrever novamente' : 'Transcrever'}</button>}
    {error && <small role="alert">{error}</small>}
  </div>;
}
