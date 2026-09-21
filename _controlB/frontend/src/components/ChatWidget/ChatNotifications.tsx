import { useEffect, useRef, useState } from 'react';
import { Bell, BellOff, X } from 'lucide-react';
import { createPortal } from 'react-dom';
import { chatService } from '@/services/api';
import type { ChatNotificationItem } from '@/types/chat';
import { unseenNotifications } from './notifications';

type Preferences = { alerts: boolean; sound: boolean; desktop: boolean };
const defaults: Preferences = { alerts: true, sound: false, desktop: false };

export function ChatNotifications({ userKey, onUnread, openConversation, isViewing }: {
  userKey: string; onUnread: (count: number) => void;
  openConversation: (id: string) => void; isViewing: (id: string) => boolean;
}) {
  const storageKey = `controlb:chat-notifications:${userKey}`;
  const [preferences, setPreferences] = useState<Preferences>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || '{}');
      return { alerts: saved.alerts !== false, sound: saved.sound === true, desktop: saved.desktop === true };
    } catch { return defaults; }
  });
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [notice, setNotice] = useState<ChatNotificationItem | null>(null);
  const [permission, setPermission] = useState(typeof Notification === 'undefined' ? 'unsupported' : Notification.permission);
  const [soundError, setSoundError] = useState(false);
  const prefsRef = useRef(preferences);
  const audioRef = useRef<AudioContext | null>(null);
  const latestRef = useRef({ onUnread, openConversation, isViewing });
  useEffect(() => { latestRef.current = { onUnread, openConversation, isViewing }; }, [onUnread, openConversation, isViewing]);
  useEffect(() => {
    prefsRef.current = preferences;
    try { localStorage.setItem(storageKey, JSON.stringify(preferences)); } catch { /* Preferências em memória se armazenamento bloqueado. */ }
  }, [preferences, storageKey]);

  const enableSound = async (enabled: boolean) => {
    setSoundError(false);
    if (enabled) {
      try {
        audioRef.current ||= new AudioContext();
        await audioRef.current.resume();
      } catch { setSoundError(true); return; }
    }
    setPreferences((p) => ({ ...p, sound: enabled }));
  };
  const enableDesktop = async () => {
    if (typeof Notification === 'undefined' || !window.isSecureContext) return;
    try {
      const result = await Notification.requestPermission();
      setPermission(result);
      setPreferences((p) => ({ ...p, desktop: result === 'granted' }));
    } catch { setPermission('denied'); }
  };

  useEffect(() => {
    let stopped = false;
    let timer: number;
    let cursor: string | undefined;
    let baseline = '';
    const seen = new Map<string, string>();
    const desktopNotices = new Set<Notification>();
    const unlockAudio = () => {
      if (!prefsRef.current.sound) return;
      try { audioRef.current ||= new AudioContext(); void audioRef.current.resume().catch(() => {}); } catch { /* Som é opcional. */ }
    };
    window.addEventListener('pointerdown', unlockAudio);
    const poll = async () => {
      try {
        let page: number | null = 1;
        let until: string | undefined;
        let newest: ChatNotificationItem | undefined;
        const since = cursor ? new Date(Date.parse(cursor) - 10000).toISOString() : undefined;
        while (page && !stopped) {
          const data = await chatService.getNotifications({ since, until, page });
          if (stopped) return;
          until = data.until;
          latestRef.current.onUnread(data.unread_count);
          if (!cursor) baseline = data.until;
          for (const item of unseenNotifications(data.items, baseline, seen)) {
            if (!latestRef.current.isViewing(item.conversation_id)) newest = item;
          }
          page = data.next_page;
        }
        cursor = until;
        for (const [id, time] of seen) if (Date.parse(time) < Date.parse(cursor!) - 60000) seen.delete(id);
        if (newest && prefsRef.current.alerts) {
          setNotice(newest);
          if (prefsRef.current.sound && audioRef.current?.state === 'running') {
            const ctx = audioRef.current;
            const oscillator = ctx.createOscillator(); const gain = ctx.createGain();
            oscillator.connect(gain); gain.connect(ctx.destination);
            oscillator.frequency.value = 660; gain.gain.setValueAtTime(0.06, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.2);
            oscillator.start(); oscillator.stop(ctx.currentTime + 0.2);
            oscillator.onended = () => { oscillator.disconnect(); gain.disconnect(); };
          }
          if (prefsRef.current.desktop && typeof Notification !== 'undefined' && Notification.permission === 'granted') {
            try {
              // Não expõe conteúdo nem nomes em notificações da tela bloqueada.
              const notification = new Notification('ControlB · Nova mensagem', { body: 'Há novas mensagens no chat.', tag: 'controlb-chat' });
              const id = newest.conversation_id;
              notification.onclick = () => { window.focus(); latestRef.current.openConversation(id); notification.close(); };
              notification.onclose = () => desktopNotices.delete(notification);
              desktopNotices.add(notification);
            } catch { /* Navegadores móveis podem exigir push/service worker. */ }
          }
        }
      } catch { /* A próxima consulta revalida permissões e recupera o intervalo pendente. */ }
      if (!stopped) timer = window.setTimeout(() => void poll(), 5000);
    };
    void poll();
    return () => {
      stopped = true; window.clearTimeout(timer); window.removeEventListener('pointerdown', unlockAudio);
      desktopNotices.forEach((item) => item.close());
      void audioRef.current?.close().catch(() => {}); audioRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 7000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  return createPortal(<div className="chat-notifications">
    <button type="button" className="chat-notifications__toggle" onClick={() => setSettingsOpen((value) => !value)}
      aria-label="Configurar notificações do chat" title="Notificações do chat" aria-expanded={settingsOpen}>
      {preferences.alerts ? <Bell size={16} /> : <BellOff size={16} />}
    </button>
    {settingsOpen && <section className="chat-notifications__settings" aria-label="Notificações do chat">
      <header><strong>Notificações do chat</strong><button type="button" aria-label="Fechar configurações" onClick={() => setSettingsOpen(false)}><X size={16} /></button></header>
      <label><input type="checkbox" checked={preferences.alerts} onChange={(e) => { setPreferences((p) => ({ ...p, alerts: e.target.checked })); setNotice(null); }} /> Alertas de novas mensagens</label>
      <label><input type="checkbox" disabled={!preferences.alerts} checked={preferences.sound} onChange={(e) => void enableSound(e.target.checked)} /> Aviso sonoro</label>
      {soundError && <small role="alert">O navegador não permitiu ativar o som.</small>}
      <label><input type="checkbox" checked={preferences.desktop} disabled={!preferences.alerts || permission === 'unsupported' || !window.isSecureContext}
        onChange={(e) => { if (e.target.checked) void enableDesktop(); else setPreferences((p) => ({ ...p, desktop: false })); }} /> Avisos do navegador</label>
      <small>{!window.isSecureContext ? 'Avisos do navegador exigem HTTPS ou localhost.' : permission === 'denied' ? 'Permissão bloqueada. Altere nas configurações do navegador.' : 'Os avisos do navegador não mostram o conteúdo das mensagens.'}</small>
      <small>Funciona enquanto o ControlB estiver aberto. Atualização a cada 5 segundos; preferências deste usuário neste navegador.</small>
    </section>}
    {notice && preferences.alerts && <div className="chat-notifications__toast" role="status">
      <button type="button" onClick={() => { openConversation(notice.conversation_id); setNotice(null); }}><strong>{notice.title}</strong><span>Nova mensagem{notice.sender_name ? ` · ${notice.sender_name}` : ''}</span></button>
      <button type="button" aria-label="Dispensar notificação" onClick={() => setNotice(null)}><X size={16} /></button>
    </div>}
  </div>, document.body);
}
