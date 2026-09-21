import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Archive, ArchiveRestore, ArrowLeft, Check, Image as ImageIcon, MessageCircle, Mic, MoreHorizontal, PanelLeftClose, PanelLeftOpen, Paperclip, Pencil, Pin, Plus, RefreshCw, Reply, Send, Target, Trash2, UserPlus, Users, X } from 'lucide-react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { ConfirmModal } from '@/components/ConfirmModal/ConfirmModal';
import { useToast } from '@/components/Toast/ToastContext';

import { usePermissions } from '@/hooks/usePermissions';
import { chatService, crmService, formatApiError } from '@/services/api';
import type { ChatChannel, ChatConversation, ChatConversationUpdate, ChatMessage } from '@/types/chat';
import { ChatUiContext, useChatUi } from './ChatContext';
import { ContactOriginSelector } from './ContactOriginSelector';
import { AudioMessage } from './AudioMessage';
import { MessageText } from './MessageText';
import { createRequestId } from '@/utils/requestId';
import { NewConversation } from './NewConversation';
import { ChatNotifications } from './ChatNotifications';
import { MediaMessage } from './MediaMessage';
import { MediaGallery } from './MediaGallery';
import { attachmentError, readImagePaste } from './clipboard';

import './ChatWidget.scss';

const avatarBlobCache = new Map<string, string>();

function ConversationAvatar({ conversation }: { conversation?: ChatConversation | null }) {
  const convId = conversation?.id;
  const [url, setUrl] = useState<string | null>(() => (convId ? avatarBlobCache.get(convId) || null : null));
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!convId) {
      setUrl(null);
      setFailed(false);
      return;
    }
    const cached = avatarBlobCache.get(convId);
    if (cached) {
      setUrl(cached);
      setFailed(false);
      return;
    }
    setUrl(null);
    setFailed(false);
    let cancelled = false;
    chatService.getAvatar(convId)
      .then((blob) => {
        if (cancelled) return;
        const objectUrl = URL.createObjectURL(blob);
        avatarBlobCache.set(convId, objectUrl);
        setUrl(objectUrl);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => { cancelled = true; };
  }, [convId]);

  if (url && !failed) {
    return (
      <img
        className="chat-widget__avatar-img"
        src={url}
        alt={conversation?.display_name || conversation?.remote_phone || 'Avatar'}
        onError={() => setFailed(true)}
      />
    );
  }

  return (
    <span className="chat-widget__avatar">
      {conversation?.is_group ? <Users size={17} /> : (conversation?.display_name || conversation?.remote_phone || '?').charAt(0)}
    </span>
  );
}

export function ChatShell({ children }: { children: ReactNode }) {
  const { hasPermission, loading, user } = usePermissions();
  const canView = hasPermission('chat:view');
  const [isOpen, setIsOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [channels, setChannels] = useState<ChatChannel[]>([]);
  const [startRequest, setStartRequest] = useState<{ key: number; contactId?: string } | null>(null);
  const accessRequest = useRef(0);
  const viewing = useRef<string | null>(null);
  const [focusRequest, setFocusRequest] = useState<{ id: string; key: number } | null>(null);
  const onViewing = useCallback((id: string | null) => { viewing.current = id; }, []);
  const isViewing = useCallback((id: string) => viewing.current === id && document.visibilityState === 'visible' && document.hasFocus(), []);
  const openConversation = useCallback((id: string) => { setFocusRequest({ id, key: Date.now() }); setIsOpen(true); }, []);
  const invalidateAccess = useCallback(() => { ++accessRequest.current; }, []);
  const canAccess = !loading && canView && channels.length > 0;

  const refreshUnread = useCallback(async () => {
    if (!canView) return;
    const version = ++accessRequest.current;
    try {
      const available = await chatService.getChannels();
      if (version !== accessRequest.current) return;
      setChannels(available);
      if (!available.length) { setUnreadCount(0); setIsOpen(false); return; }
    } catch {
      if (version !== accessRequest.current) return;
      setChannels([]); setUnreadCount(0); setIsOpen(false);
    }
  }, [canView]);

  useEffect(() => {
    if (!canView) return undefined;
    void refreshUnread();
    const timer = window.setInterval(() => void refreshUnread(), 20000);
    const refresh = () => { void refreshUnread(); };
    window.addEventListener('controlb:chat-refresh', refresh);
    return () => { invalidateAccess(); window.clearInterval(timer); window.removeEventListener('controlb:chat-refresh', refresh); };
  }, [canView, refreshUnread, invalidateAccess]);

  const value = useMemo(
    () => ({
      canAccess,
      isOpen,
      unreadCount,
      open: () => { if (canAccess) setIsOpen(true); },
      startConversation: (contactId?: string) => { if (canAccess) { setStartRequest((value) => ({ key: (value?.key || 0) + 1, contactId })); setIsOpen(true); } },
      close: () => setIsOpen(false),
      toggle: () => { if (canAccess) setIsOpen((current) => !current); },
    }),
    [canAccess, isOpen, unreadCount],
  );

  return (
    <ChatUiContext.Provider value={value}>
      {children}
      {canAccess && <ChatWidget key={channels.map((channel) => channel.id).sort().join(',')} onConversationsChange={refreshUnread} startRequest={startRequest} focusRequest={focusRequest} onViewing={onViewing} />}
      {canAccess && user && <ChatNotifications key={`${user.organization_id}:${user.id}:${channels.map((c) => c.id).sort().join(',')}`} userKey={`${user.organization_id}:${user.id}`} onUnread={setUnreadCount} openConversation={openConversation} isViewing={isViewing} />}
    </ChatUiContext.Provider>
  );
}

function ChatWidget({ onConversationsChange, startRequest, focusRequest, onViewing }: { onConversationsChange: () => Promise<void>; startRequest: { key: number; contactId?: string } | null; focusRequest: { id: string; key: number } | null; onViewing: (id: string | null) => void }) {
  const { isOpen, unreadCount, toggle, close } = useChatUi();
  const { hasPermission, user } = usePermissions();
  const canSend = hasPermission('chat:send');
  const navigate = useNavigate();
  const toast = useToast();
  const [creatingLead, setCreatingLead] = useState(false);
  const [creatingOpp, setCreatingOpp] = useState(false);
  const [gallery, setGallery] = useState(false);
  const [attachment, setAttachment] = useState<File | null>(null);
  const [attachmentPreview, setAttachmentPreview] = useState<string | null>(null);
  useEffect(() => {
    if (!attachment || !/^image\/(png|jpeg|gif|webp)$/.test(attachment.type)) {
      setAttachmentPreview(null);
      return;
    }
    const url = URL.createObjectURL(attachment);
    setAttachmentPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [attachment]);
  const uploadInput = useRef<HTMLInputElement>(null);
  const [confirmation, setConfirmation] = useState<{ action: 'channel' | 'local' | 'everyone' | 'name'; id: string } | null>(null);
  const attemptedGroups = useRef(new Set<string>());
  const groupLookupCount = useRef(0);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const [conversations, setConversations] = useState<ChatConversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [selectedConversation, setSelectedConversation] = useState<ChatConversation | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState('');
  const [loadingList, setLoadingList] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [listPage, setListPage] = useState(1);
  const [listTotal, setListTotal] = useState(0);
  const [messagePage, setMessagePage] = useState(1);
  const [messageTotal, setMessageTotal] = useState(0);
  const [filter, setFilter] = useState<'OPEN' | 'MINE' | 'CLOSED' | 'ARCHIVED'>('OPEN');
  const [pinnedIds, setPinnedIds] = useState<Set<string>>(() => {
    try {
      const key = `controlb:chat_pinned_${user?.id || 'default'}`;
      const raw = localStorage.getItem(key);
      return raw ? new Set(JSON.parse(raw)) : new Set<string>();
    } catch {
      return new Set<string>();
    }
  });

  const togglePin = useCallback((id: string) => {
    setPinnedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      try {
        const key = `controlb:chat_pinned_${user?.id || 'default'}`;
        localStorage.setItem(key, JSON.stringify([...next]));
      } catch { /* noop */ }
      return next;
    });
  }, [user?.id]);
  const [updating, setUpdating] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [newConversation, setNewConversation] = useState<{ key: number; contactId?: string } | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  const [replyingTo, setReplyingTo] = useState<ChatMessage | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [recordingDuration, setRecordingDuration] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const recordTimerRef = useRef<number | null>(null);
  const updatingRef = useRef(false);
  const activeRef = useRef<string | null>(null);
  const listRequest = useRef(0);
  const messageRequest = useRef(0);
  const sendRequest = useRef<{ conversationId: string; text: string; id: string; file: File | null } | null>(null);
  const sendingRef = useRef(false);
  const invalidateRequests = useCallback(() => {
    ++listRequest.current;
    ++messageRequest.current;
  }, []);
  const clearSelection = useCallback(() => {
    ++messageRequest.current;
    activeRef.current = null;
    setSelectedConversation(null);
    setActiveId(null); setMessages([]); setDraft(''); setMessagePage(1); setMessageTotal(0); setLoadingMessages(false);
    setIsSidebarCollapsed(false);
    setGallery(false); setAttachment(null); setReplyingTo(null);
    if (recordTimerRef.current) { clearInterval(recordTimerRef.current); recordTimerRef.current = null; }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') { mediaRecorderRef.current.stop(); }
    setIsRecording(false); setRecordingDuration(0); audioChunksRef.current = [];
  }, []);

  useEffect(() => {
    if (startRequest) { clearSelection(); setNewConversation(startRequest); }
  }, [startRequest, clearSelection]);

  useEffect(() => {
    onViewing(isOpen ? activeId : null);
    return () => onViewing(null);
  }, [isOpen, activeId, onViewing]);

  useEffect(() => {
    if (!focusRequest) return;
    let cancelled = false;
    void chatService.getConversation(focusRequest.id).then((item) => {
      if (cancelled) return;
      invalidateRequests(); clearSelection(); setNewConversation(null); setShowDetails(false);
      setFilter(item.is_archived ? 'ARCHIVED' : item.status); setListPage(1);
      setSelectedConversation(item); activeRef.current = item.id; setActiveId(item.id);
    }).catch((err) => { if (!cancelled) setError(formatApiError(err, 'Conversa indisponível.')); });
    return () => { cancelled = true; };
  }, [focusRequest, invalidateRequests, clearSelection]);

  const loadConversations = useCallback(async (quiet = false) => {
    const version = ++listRequest.current;
    if (!quiet) setLoadingList(true);
    try {
      const isMine = filter === 'MINE';
      const page = await chatService.getConversations({
        page: listPage,
        page_size: 50,
        archived: filter === 'ARCHIVED',
        ...(filter === 'OPEN' ? { status: 'OPEN' } : filter === 'CLOSED' ? { status: 'CLOSED' } : isMine ? { status: 'OPEN', mine: true } : {}),
      });
      if (version !== listRequest.current) return;
      setConversations(page.items);
      setListTotal(page.total);
      const selectedId = activeRef.current;
      if (selectedId && !page.items.some((item) => item.id === selectedId)) {
        // Um canal recém-criado (ainda sem mensagens) pode estar fora da página atual.
        const selected = await chatService.getConversation(selectedId);
        if (version !== listRequest.current || activeRef.current !== selectedId) return;
        if (selected.is_archived !== (filter === 'ARCHIVED') || (filter !== 'ARCHIVED' && filter !== 'MINE' && selected.status !== filter) || (filter === 'MINE' && (selected.assigned_user_id !== user?.id || selected.status !== 'OPEN'))) clearSelection();
        else setSelectedConversation(selected);
      }
    } catch (loadError) {
      if (version === listRequest.current) {
        setConversations([]); clearSelection();
        setError(formatApiError(loadError, 'Não foi possível carregar as conversas.'));
      }
    } finally {
      if (version === listRequest.current) setLoadingList(false);
    }
  }, [listPage, filter, clearSelection, user?.id]);

  const loadMessages = useCallback(async (conversationId: string, quiet = false, pageNumber = 1) => {
    const version = ++messageRequest.current;
    if (!quiet) setLoadingMessages(true);
    try {
      const page = await chatService.getMessages(conversationId, pageNumber, 50);
      if (version !== messageRequest.current || activeRef.current !== conversationId) return;
      setMessageTotal(page.total);
      setMessages((current) => {
        const byId = new Map(current.map((item) => [item.id, item]));
        page.items.forEach((item) => byId.set(item.id, item));
        return [...byId.values()].sort((a, b) => a.occurred_at.localeCompare(b.occurred_at) || a.id.localeCompare(b.id));
      });
      if (pageNumber > 1) setMessagePage(pageNumber);
      if (pageNumber === 1 && document.visibilityState === 'visible') await chatService.markRead(conversationId);
      await onConversationsChange();
    } catch (loadError) {
      if (version === messageRequest.current && activeRef.current === conversationId) {
        setMessages([]);
        setError(formatApiError(loadError, 'Não foi possível carregar as mensagens.'));
      }
    } finally {
      if (version === messageRequest.current) setLoadingMessages(false);
    }
  }, [onConversationsChange]);

  useEffect(() => {
    if (!isOpen) return;
    void loadConversations();
    let cancelled = false;
    let timer: number;
    const refresh = async () => {
      if (document.visibilityState === 'visible') {
        await loadConversations(true);
        const id = activeRef.current;
        if (!cancelled && id && !sendingRef.current && !updatingRef.current) await loadMessages(id, true);
      }
      if (!cancelled) timer = window.setTimeout(() => void refresh(), 5000);
    };
    const requestRefresh = () => { void loadConversations(true); };
    window.addEventListener('controlb:chat-refresh', requestRefresh);
    timer = window.setTimeout(() => void refresh(), 5000);
    return () => {
      cancelled = true;
      invalidateRequests();
      window.clearTimeout(timer);
      window.removeEventListener('controlb:chat-refresh', requestRefresh);
    };
  }, [isOpen, loadConversations, loadMessages, invalidateRequests]);

  useEffect(() => {
    if (!isOpen || !activeId) return;
    void loadMessages(activeId);
  }, [activeId, isOpen, loadMessages]);

  const send = async () => {
    if (!activeId || (!draft.trim() && !attachment) || !canSend || sendingRef.current || updatingRef.current || active?.status !== 'OPEN' || active.is_archived) return;
    const conversationId = activeId;
    const text = draft.trim();
    const replyId = replyingTo?.id;
    sendingRef.current = true;
    setSending(true); setError(null);
    try {
      if (sendRequest.current?.conversationId !== conversationId || sendRequest.current.text !== text || sendRequest.current.file !== attachment) {
        sendRequest.current = { conversationId, text, id: createRequestId(), file: attachment };
      }
      const message = attachment ? await chatService.sendAttachment(conversationId, attachment, text, sendRequest.current.id) : await chatService.sendMessage(conversationId, text, sendRequest.current.id, replyId);
      if (activeRef.current === conversationId) {
        setMessages((current) => [...current.filter((item) => item.id !== message.id), message]);
        if (message.status !== 'FAILED' && !message.error_message) { setDraft(''); setAttachment(null); setReplyingTo(null); }
        setError(message.error_message);
      }
      // Falha definitiva permite corrigir e tentar de novo; envio incerto mantém a chave.
      if (message.status === 'FAILED' || !message.error_message) sendRequest.current = null;
      void loadConversations(true);
    } catch (sendError) {
      setError(formatApiError(sendError, 'Não foi possível enviar a mensagem.'));
    } finally {
      sendingRef.current = false;
      setSending(false);
    }
  };

  const toggleReaction = async (message: ChatMessage, emoji: string) => {
    if (!canReply || sendingRef.current || updatingRef.current) return;
    const userReaction = (message.reactions || []).find(
      (r) => r.from_me || (user && r.user_id === user.id)
    );
    const nextEmoji = userReaction?.emoji === emoji ? '' : emoji;
    try {
      const updated = await chatService.sendReaction(message.id, nextEmoji);
      setMessages((items) => items.map((item) => (item.id === updated.id ? updated : item)));
    } catch (err) {
      setError(formatApiError(err, 'Não foi possível reagir à mensagem.'));
    }
  };

  const startRecording = async () => {
    if (!canReply || sendingRef.current || updatingRef.current) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')
        ? 'audio/ogg;codecs=opus'
        : 'audio/mp4';
      const recorder = new MediaRecorder(stream, { mimeType });
      audioChunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) audioChunksRef.current.push(event.data);
      };
      recorder.start(200);
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
      setRecordingDuration(0);
      recordTimerRef.current = window.setInterval(() => {
        setRecordingDuration((prev) => prev + 1);
      }, 1000);
    } catch {
      setError('Não foi possível acessar o microfone. Verifique as permissões do navegador.');
    }
  };

  const cancelRecording = () => {
    if (recordTimerRef.current) {
      clearInterval(recordTimerRef.current);
      recordTimerRef.current = null;
    }
    if (mediaRecorderRef.current) {
      try {
        mediaRecorderRef.current.stream.getTracks().forEach((t) => t.stop());
        if (mediaRecorderRef.current.state !== 'inactive') mediaRecorderRef.current.stop();
      } catch { /* noop */ }
    }
    setIsRecording(false);
    setRecordingDuration(0);
    audioChunksRef.current = [];
  };

  const stopAndSendRecording = () => {
    if (!mediaRecorderRef.current || !activeId) return;
    if (recordTimerRef.current) {
      clearInterval(recordTimerRef.current);
      recordTimerRef.current = null;
    }
    const recorder = mediaRecorderRef.current;
    recorder.onstop = async () => {
      try {
        recorder.stream.getTracks().forEach((t) => t.stop());
      } catch { /* noop */ }
      const mimeType = recorder.mimeType || 'audio/webm';
      const ext = mimeType.includes('ogg') ? 'ogg' : mimeType.includes('mp4') ? 'm4a' : 'webm';
      const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
      setIsRecording(false);
      setRecordingDuration(0);
      audioChunksRef.current = [];
      if (!audioBlob.size) {
        setError('Áudio vazio.');
        return;
      }
      const file = new File([audioBlob], `audio_${Date.now()}.${ext}`, { type: mimeType });
      const conversationId = activeId;
      sendingRef.current = true;
      setSending(true);
      setError(null);
      try {
        const reqId = createRequestId();
        const message = await chatService.sendAttachment(conversationId, file, '', reqId);
        if (activeRef.current === conversationId) {
          setMessages((current) => [...current.filter((item) => item.id !== message.id), message]);
          setError(message.error_message);
        }
        void loadConversations(true);
      } catch (err) {
        setError(formatApiError(err, 'Não foi possível enviar o áudio.'));
      } finally {
        sendingRef.current = false;
        setSending(false);
      }
    };
    try {
      recorder.stop();
    } catch {
      cancelRecording();
    }
  };

  const active = conversations.find((item) => item.id === activeId) || (selectedConversation?.id === activeId ? selectedConversation : undefined);
  const canReply = canSend && active?.status === 'OPEN' && !active.is_archived;
  useEffect(() => {
    if (!isOpen || !canSend) return;
    const pending = conversations.filter((item) => item.is_group && (!item.display_name || item.display_name === `Grupo ${item.external_chat_id}`) && !attemptedGroups.current.has(item.id));
    const resolve = async () => {
      for (const item of pending) {
        if (!mounted.current || attemptedGroups.current.has(item.id)) continue;
        if (groupLookupCount.current >= 3) return;
        attemptedGroups.current.add(item.id);
        ++groupLookupCount.current;
        try {
          const updated = await chatService.refreshContact(item.id);
          if (mounted.current) {
            setConversations((items) => items.map((row) => row.id === updated.id ? updated : row));
            if (activeRef.current === updated.id) setSelectedConversation(updated);
          }
        } catch { /* Botão explícito permite tentar novamente sem bloquear o chat. */ }
        finally { --groupLookupCount.current; }
      }
    };
    void resolve();
  }, [conversations, isOpen, canSend]);

  const confirmAction = async () => {
    if (!confirmation || updatingRef.current || sendingRef.current) return;
    updatingRef.current = true; setUpdating(true); setError(null);
    try {
      if (confirmation.action === 'channel') { await chatService.deleteChannel(confirmation.id); clearSelection(); }
      else if (confirmation.action === 'name') {
        const updated = await chatService.replaceContactName(confirmation.id);
        setSelectedConversation(updated);
      } else {
        const result = await chatService.deleteMessage(confirmation.id, confirmation.action === 'everyone');
        if (!result.deleted) throw new Error(result.error || 'Exclusão não confirmada pelo provedor.');
        ++messageRequest.current;
        setMessages((items) => items.map((item) => item.id === confirmation.id ? { ...item, deleted_at: new Date().toISOString(), content: null } : item));
      }
      setConfirmation(null); await loadConversations(true); await onConversationsChange();
    } catch (err) { setError(formatApiError(err, 'Não foi possível concluir a operação.')); }
    finally { updatingRef.current = false; setUpdating(false); }
  };
  const refreshContact = async () => {
    if (!activeId || updatingRef.current || sendingRef.current) return;
    const id = activeId;
    updatingRef.current = true; setUpdating(true); setError(null);
    try {
      const updated = await chatService.refreshContact(id);
      if (activeRef.current === id) {
        setSelectedConversation(updated);
        setConversations((items) => items.map((item) => item.id === id ? updated : item));
      }
    } catch (err) { setError(formatApiError(err, 'Não foi possível atualizar o contato.')); }
    finally { updatingRef.current = false; setUpdating(false); }
  };
  const handleCreateLeadFromContact = async (contactId: string) => {
    if (updatingRef.current || sendingRef.current || creatingLead) return;
    setCreatingLead(true);
    try {
      const lead = await crmService.convertContactToLead(contactId);
      toast.success(`Lead "${lead.name}" criado com sucesso no CRM!`, 'Lead Criado');
    } catch (err: unknown) {
      toast.error(formatApiError(err, 'Não foi possível converter o contato em lead.'));
    } finally {
      setCreatingLead(false);
    }
  };
  const handleCreateOppFromContact = async (contactId: string) => {
    if (updatingRef.current || sendingRef.current || creatingOpp) return;
    setCreatingOpp(true);
    try {
      const opp = await crmService.convertContactToOpportunity(contactId);
      toast.success(`Oportunidade "${opp.title}" criada com sucesso no CRM!`, 'Oportunidade Criada');
    } catch (err: unknown) {
      toast.error(formatApiError(err, 'Não foi possível criar oportunidade para o contato.'));
    } finally {
      setCreatingOpp(false);
    }
  };
  const updateConversation = async (payload: ChatConversationUpdate) => {
    if (!activeId || !canSend || updatingRef.current || sendingRef.current) return;
    const id = activeId;
    updatingRef.current = true; setUpdating(true); setError(null); ++listRequest.current;
    try {
      const updated = await chatService.updateConversation(id, payload);
      setSelectedConversation(updated);
      setConversations((items) => items.map((item) => item.id === updated.id ? updated : item));
      await loadConversations(true);
      await onConversationsChange();
    } catch (err) {
      setError(formatApiError(err, 'Não foi possível atualizar a conversa.'));
    } finally {
      updatingRef.current = false; setUpdating(false);
    }
  };

  return createPortal(
    <div className="chat-widget">
      <ConfirmModal isOpen={Boolean(confirmation)} onClose={() => { if (!updating) { setConfirmation(null); setError(null); } }} onConfirm={confirmAction} isLoading={updating} errorMessage={error}
        title={confirmation?.action === 'everyone' ? 'Apagar para todos no WhatsApp?' : confirmation?.action === 'channel' ? 'Excluir canal do ControlB?' : confirmation?.action === 'name' ? 'Usar o nome do WhatsApp?' : 'Excluir mensagem do ControlB?'}
        confirmText={confirmation?.action === 'everyone' ? 'Apagar no WhatsApp' : confirmation?.action === 'name' ? 'Atualizar nome' : 'Excluir só no ControlB'}
        message={confirmation?.action === 'everyone' ? 'Esta ação afeta o WhatsApp dos participantes. Está sujeita ao prazo e às permissões do WhatsApp.' : confirmation?.action === 'channel' ? 'O conteúdo e os arquivos deste canal serão removidos do ControlB para toda a equipe. Nada será apagado no WhatsApp. Novas mensagens podem abrir o canal novamente.' : confirmation?.action === 'name' ? 'O nome atual será substituído pelo nome identificado no WhatsApp. Depois disso, continuará protegido contra alterações automáticas.' : 'O conteúdo e o arquivo desta mensagem serão removidos do ControlB para toda a equipe, sem apagar no WhatsApp.'} />
      {isOpen && (
        <aside className="chat-widget__drawer" aria-label="Painel de conversas">
          <header className="chat-widget__header">
            <div>
              <strong>Chat</strong>
              <span>Conversas e triagem · atualização automática a cada 5 segundos</span>
            </div>
            <div className="chat-widget__header-actions">
              {canSend && <button type="button" className="chat-widget__icon-btn" title="Nova conversa" aria-label="Nova conversa"
                disabled={sending || updating} onClick={() => { clearSelection(); setNewConversation({ key: Date.now() }); }}><Plus size={17} /></button>}
              <button type="button" className="chat-widget__icon-btn" title="Atualizar conversas"
                onClick={() => { setError(null); void loadConversations(); if (activeId) void loadMessages(activeId); }}>
                <RefreshCw size={16} />
              </button>
              <button type="button" className="chat-widget__icon-btn" onClick={close} title="Fechar">
                <X size={16} />
              </button>
            </div>
          </header>
          {error && <div className="chat-widget__error" role="alert">{error}</div>}
          {!newConversation && <div className="chat-widget__filters" role="group" aria-label="Filtrar conversas">
            {(['OPEN', 'MINE', 'CLOSED', 'ARCHIVED'] as const).map((value) => <button type="button" key={value}
              aria-pressed={filter === value} disabled={sending || updating}
              onClick={() => { if (value === filter) return; invalidateRequests(); clearSelection(); setListPage(1); setConversations([]); setError(null); setFilter(value); }}>
              {value === 'OPEN' ? 'Abertas' : value === 'MINE' ? 'Meus atendimentos' : value === 'CLOSED' ? 'Fechadas' : 'Arquivadas'}
            </button>)}
          </div>}
          {newConversation ? <NewConversation key={newConversation.key} initialContactId={newConversation.contactId} onCancel={() => setNewConversation(null)} onStarted={(conversation) => {
            invalidateRequests(); clearSelection(); setError(null); setNewConversation(null); setShowDetails(false);
            setListPage(1); setFilter(conversation.is_archived ? 'ARCHIVED' : conversation.status);
            setConversations((items) => [conversation, ...items.filter((item) => item.id !== conversation.id)]);
            activeRef.current = conversation.id; setActiveId(conversation.id);
            setSelectedConversation(conversation);
            void onConversationsChange();
          }} /> : <div className={`chat-widget__body${activeId ? ' has-selection' : ''}${isSidebarCollapsed ? ' is-sidebar-collapsed' : ''}`}>
            <section className="chat-widget__list">
              {loadingList ? (
                <p className="chat-widget__empty">Carregando conversas...</p>
              ) : conversations.length === 0 ? (
                <p className="chat-widget__empty">Nenhuma conversa neste filtro.</p>
              ) : (
                [...conversations].sort((a, b) => {
                  const aPinned = pinnedIds.has(a.id) ? 1 : 0;
                  const bPinned = pinnedIds.has(b.id) ? 1 : 0;
                  return bPinned - aPinned;
                }).map((item) => {
                  const isPinned = pinnedIds.has(item.id);
                  return (
                    <button
                      key={item.id}
                      type="button"
                      className={`chat-widget__item${item.id === activeId ? ' is-active' : ''}${isPinned ? ' is-pinned' : ''}`}
                      disabled={sending || updating}
                      onClick={() => {
                        if (activeRef.current === item.id) return;
                        ++messageRequest.current;
                        activeRef.current = item.id;
                        setMessages([]); setMessagePage(1); setMessageTotal(0); setDraft(''); setError(null);
                        setGallery(false); setAttachment(null);
                        setActiveId(item.id);
                        setSelectedConversation(item);
                        setShowDetails(false);
                      }}
                    >
                      <ConversationAvatar conversation={item} />
                      <span>
                        <strong>
                          {isPinned && <Pin size={11} className="chat-widget__pin-badge" />}
                          {item.display_name || item.remote_phone}
                        </strong>
                        <small>{item.last_message_preview || 'Sem mensagens'}</small>
                        {item.assigned_user_id && <span className="chat-widget__assignee" title="Responsável pelo atendimento">{item.assigned_user_name || 'Atendente indisponível'}</span>}
                      </span>
                      {item.unread_count > 0 && <em>{item.unread_count}</em>}
                    </button>
                  );
                })
              )}
              {listTotal > 50 && <div className="chat-widget__pagination">
                <button type="button" disabled={listPage === 1 || loadingList || sending || updating} onClick={() => { clearSelection(); setListPage((page) => page - 1); }}>Anterior</button>
                <span>{listPage} / {Math.ceil(listTotal / 50)}</span>
                <button type="button" disabled={listPage * 50 >= listTotal || loadingList || sending || updating} onClick={() => { clearSelection(); setListPage((page) => page + 1); }}>Próxima</button>
              </div>}
            </section>
            <section className="chat-widget__thread">
              {!activeId ? (
                <p className="chat-widget__empty">Selecione uma conversa para ver as mensagens.</p>
              ) : (
                <>
                  <header>
                    <div className="chat-widget__thread-heading">
                      <div className="chat-widget__thread-title-wrap">
                        <button type="button" className="chat-widget__back" disabled={sending || updating} onClick={() => { if (isSidebarCollapsed) setIsSidebarCollapsed(false); else clearSelection(); }}><ArrowLeft size={14} /> Conversas</button>
                        <div className="chat-widget__thread-title">
                          <ConversationAvatar key={active?.id} conversation={active} />
                          <div>
                            <strong>{active?.display_name || active?.remote_phone}</strong>
                            {active?.assigned_user_id && <span className="chat-widget__assignee">{active.assigned_user_name || 'Atendente indisponível'}</span>}
                          </div>
                        </div>
                      </div>
                      <div className="chat-widget__thread-controls">
                        {active && (
                          <button
                            type="button"
                            className={`chat-widget__icon-btn${isSidebarCollapsed ? ' is-active' : ''}`}
                            title={isSidebarCollapsed ? 'Mostrar lista de conversas' : 'Recolher lista e focar na conversa'}
                            aria-label={isSidebarCollapsed ? 'Mostrar lista de conversas' : 'Recolher barra lateral'}
                            onClick={() => setIsSidebarCollapsed((prev) => !prev)}
                          >
                            {isSidebarCollapsed ? <PanelLeftOpen size={15} /> : <PanelLeftClose size={15} />}
                          </button>
                        )}
                        {active && (
                          <button
                            type="button"
                            className={`chat-widget__icon-btn${pinnedIds.has(active.id) ? ' is-pinned' : ''}`}
                            title={pinnedIds.has(active.id) ? 'Desafixar canal dos favoritos' : 'Fixar canal como favorito'}
                            aria-label={pinnedIds.has(active.id) ? 'Desafixar canal' : 'Fixar canal'}
                            onClick={() => togglePin(active.id)}
                          >
                            <Pin size={15} />
                          </button>
                        )}
                        <button type="button" className="chat-widget__icon-btn" aria-label="Ações e dados da conversa" aria-expanded={showDetails}
                          onClick={() => setShowDetails((value) => !value)}><MoreHorizontal size={18} /></button>
                      </div>
                    </div>
                    <small>Instância: {active?.instance_phone ? `+${active.instance_phone}` : 'Não confirmada'} · {active?.status === 'CLOSED' ? 'Fechada' : 'Aberta'}{active?.is_archived ? ' · Arquivada' : ''}</small>
                  </header>
                  {showDetails && (
                    <>
                      <div className="chat-widget__floating-menu-backdrop" onClick={() => setShowDetails(false)} />
                      <div className="chat-widget__floating-menu">
                        <div className="chat-widget__floating-menu-header">
                          <strong>Detalhes e Ações da Conversa</strong>
                          <button
                            type="button"
                            className="chat-widget__floating-menu-close"
                            title="Fechar menu"
                            onClick={() => setShowDetails(false)}
                          >
                            <X size={15} />
                          </button>
                        </div>
                        <div className="chat-widget__floating-menu-meta">
                          <span>{active?.is_group ? `Grupo: ${active.external_chat_id}` : `Contato: ${active?.remote_phone}`}</span>
                          {active?.closed_at && <span>Fechada em {new Date(active.closed_at).toLocaleString('pt-BR')}{active.closed_by_id === user?.id ? ' por você' : ''}</span>}
                        </div>
                        {canSend && active && (
                          <div className="chat-widget__actions-section">
                            <div className="chat-widget__actions-row">
                              {user && (
                                <button
                                  type="button"
                                  className={active.assigned_user_id === user.id ? 'chat-widget__btn--active' : !active.assigned_user_id ? 'chat-widget__btn--primary' : ''}
                                  disabled={updating || sending}
                                  onClick={() => void updateConversation({ assigned_user_id: active.assigned_user_id === user.id ? null : user.id })}
                                >
                                  {active.assigned_user_id === user.id ? 'Liberar atendimento' : active.assigned_user_id ? 'Assumir atendimento' : 'Atender'}
                                </button>
                              )}
                              <button type="button" disabled={updating || sending} onClick={() => void updateConversation({ status: active.status === 'OPEN' ? 'CLOSED' : 'OPEN' })}>
                                <Check size={14} /> {active.status === 'OPEN' ? 'Fechar conversa' : 'Reabrir conversa'}
                              </button>
                              <button type="button" disabled={updating || sending} onClick={() => void updateConversation({ is_archived: !active.is_archived })}>
                                {active.is_archived ? <ArchiveRestore size={14} /> : <Archive size={14} />} {active.is_archived ? 'Desarquivar' : 'Arquivar'}
                              </button>
                              <button type="button" disabled={updating || sending} onClick={() => active && togglePin(active.id)}>
                                <Pin size={14} /> {active && pinnedIds.has(active.id) ? 'Desafixar canal' : 'Fixar canal'}
                              </button>
                            </div>
                            <div className="chat-widget__actions-row chat-widget__actions-row--split">
                              {active.contact_id && !active.is_group && (
                                <>
                                  <button type="button" disabled={updating || sending} onClick={() => { close(); navigate(`/contatos/${active.contact_id}`); }}>
                                    <Pencil size={14} /> Editar contato
                                  </button>
                                  <button type="button" disabled={updating || sending || creatingLead} onClick={() => void handleCreateLeadFromContact(active.contact_id!)}>
                                    <UserPlus size={14} /> Criar Lead no CRM
                                  </button>
                                  <button type="button" disabled={updating || sending || creatingOpp} onClick={() => void handleCreateOppFromContact(active.contact_id!)}>
                                    <Target size={14} /> Criar Oportunidade
                                  </button>
                                </>
                              )}
                              <button type="button" disabled={updating || sending} onClick={() => active.is_group ? void refreshContact() : setConfirmation({ action: 'name', id: active.id })}>
                                <RefreshCw size={14} /> {active.is_group ? 'Atualizar nome do grupo' : 'Usar nome do WhatsApp'}
                              </button>
                              <button type="button" className="chat-widget__btn--danger" disabled={updating || sending} onClick={() => setConfirmation({ action: 'channel', id: active.id })}>
                                <Trash2 size={14} /> Excluir canal só no ControlB
                              </button>
                            </div>
                          </div>
                        )}
                        {active?.contact_id && <ContactOriginSelector key={active.id} conversationId={active.id} canEdit={canSend && !updating} />}
                      </div>
                    </>
                  )}
                  <button type="button" className="chat-widget__media-tab" onClick={() => setGallery((value) => !value)}><ImageIcon size={14} /> {gallery ? 'Voltar à conversa' : 'Mídias e arquivos'}</button>
                  {gallery ? <MediaGallery key={activeId} conversationId={activeId} onBack={() => setGallery(false)} /> : <>
                  <div className="chat-widget__messages">
                    {messageTotal > messages.length && <button type="button" className="ui-button ui-button--secondary"
                      disabled={loadingMessages} onClick={() => void loadMessages(activeId, false, messagePage + 1)}>Carregar anteriores</button>}
                    {loadingMessages ? (
                      <p className="chat-widget__empty">Carregando mensagens...</p>
                    ) : (
                      messages.filter((message) => !message.deleted_at).map((message) => {
                        const isSticker = message.message_type === 'STICKER';
                        return (
                          <div
                            key={message.id}
                            className={`chat-widget__bubble is-${message.direction.toLowerCase()}${isSticker ? ' is-sticker' : ''}`}
                          >
                            {message.direction === 'OUTBOUND' && <span className="chat-widget__author" title="Identificação interna; não é enviada ao destinatário">
                              {message.author_name || (message.client_request_id ? 'Usuário indisponível' : 'WhatsApp · envio externo')}
                            </span>}
                            {active?.is_group && message.direction === 'INBOUND' && <button type="button"
                              className="chat-widget__participant"
                              disabled={!message.sender_phone || !canSend || updating || sending || isRecording}
                              title={message.sender_phone ? 'Abrir conversa direta sem cadastrar contato' : 'Telefone indisponível: WhatsApp informou somente o ID interno'}
                              onClick={() => {
                                setUpdating(true);
                                void chatService.openGroupParticipant(active.id, message.id).then((channel) => {
                                  if (!mounted.current) return;
                                  invalidateRequests(); clearSelection(); setShowDetails(false); setNewConversation(null);
                                  setFilter(channel.is_archived ? 'ARCHIVED' : channel.status); setListPage(1);
                                  activeRef.current = channel.id;
                                  setSelectedConversation(channel);
                                  setActiveId(channel.id);
                                  setConversations((items) => items.some((item) => item.id === channel.id) ? items : [channel, ...items]);
                                }).catch((err) => toast.error(formatApiError(err, 'Não foi possível abrir a conversa.')))
                                  .finally(() => setUpdating(false));
                              }}>
                              {message.sender_name || message.sender_phone || 'Participante não identificado'}
                              {message.sender_name && message.sender_phone && <small>+{message.sender_phone}</small>}
                            </button>}
                            {message.reply_snapshot && (
                              <div className="chat-widget__quoted-block">
                                <strong>{message.reply_snapshot.sender_name || 'Mensagem'}</strong>
                                <span>{message.reply_snapshot.text || (message.reply_snapshot.message_type === 'STICKER' ? 'Figurinha' : message.reply_snapshot.message_type === 'IMAGE' ? 'Foto' : `[${message.reply_snapshot.message_type || 'Mídia'}]`)}</span>
                              </div>
                            )}
                            {message.message_type === 'AUDIO'
                              ? <AudioMessage message={message} canTranscribe={canSend} onUpdate={(updated) => {
                                if (activeRef.current === updated.conversation_id) setMessages((items) => items.map((item) => item.id === updated.id ? updated : item));
                              }} />
                              : ['IMAGE', 'VIDEO', 'DOCUMENT', 'STICKER'].includes(message.message_type) ? <><MediaMessage message={message} />{message.content && <MessageText text={message.content} />}</>
                              : <MessageText text={message.content || `[${message.message_type}]`} />}
                            <small>
                              {new Date(message.occurred_at).toLocaleTimeString('pt-BR', {
                                hour: '2-digit',
                                minute: '2-digit',
                              })}
                              {message.direction === 'OUTBOUND' && ` · ${message.status === 'FAILED' ? 'Falhou' : message.status === 'PENDING' ? 'Sem confirmação do provedor' : message.status === 'READ' ? 'Lida' : message.status === 'DELIVERED' ? 'Entregue' : 'Enviada'}`}
                            </small>
                            {message.error_message && <small role="alert">{message.error_message}</small>}
                            {message.reactions && message.reactions.length > 0 && (
                              <div className="chat-widget__reactions">
                                {(() => {
                                  const map = new Map<string, { count: number; users: string[]; hasMine: boolean }>();
                                  message.reactions.forEach((r) => {
                                    if (!r.emoji) return;
                                    const entry = map.get(r.emoji) || { count: 0, users: [], hasMine: false };
                                    entry.count += 1;
                                    const who = r.user_name || r.sender;
                                    if (who) entry.users.push(who);
                                    if (r.from_me || (user && r.user_id === user.id)) entry.hasMine = true;
                                    map.set(r.emoji, entry);
                                  });
                                  return Array.from(map.entries()).map(([emoji, data]) => (
                                    <button
                                      type="button"
                                      key={emoji}
                                      className={`chat-widget__reaction-badge${data.hasMine ? ' is-mine' : ''}`}
                                      title={data.users.join(', ')}
                                      disabled={!canReply || sending || updating}
                                      onClick={() => void toggleReaction(message, emoji)}
                                    >
                                      <span>{emoji}</span>
                                      {data.count > 1 && <small>{data.count}</small>}
                                    </button>
                                  ));
                                })()}
                              </div>
                            )}
                            {canSend && <details className="chat-message-actions"><summary aria-label="Ações da mensagem"><MoreHorizontal size={14} /></summary>
                              {canReply && (
                                <div className="chat-message-reactions-picker">
                                  {['👍', '❤️', '😂', '😮', '😢', '🙏'].map((emoji) => (
                                    <button
                                      key={emoji}
                                      type="button"
                                      className="chat-message-reaction-btn"
                                      disabled={sending || updating}
                                      onClick={() => void toggleReaction(message, emoji)}
                                    >
                                      {emoji}
                                    </button>
                                  ))}
                                </div>
                              )}
                              {canReply && (
                                <button type="button" disabled={sending || updating} onClick={() => setReplyingTo(message)}>
                                  <Reply size={13} /> Responder
                                </button>
                              )}
                              <button type="button" disabled={updating || sending} onClick={() => setConfirmation({ action: 'local', id: message.id })}>Excluir só no ControlB</button>
                              {message.direction === 'OUTBOUND' && message.external_message_id && (message.created_by_id === user?.id || hasPermission('chat:manage_connectors')) && <button type="button" disabled={updating || sending || message.revoke_status === 'PENDING'} onClick={() => setConfirmation({ action: 'everyone', id: message.id })}>Apagar para todos no WhatsApp</button>}
                            </details>}
                          </div>
                        );
                      })
                    )}
                  </div>
                  {replyingTo && (
                    <div className="chat-widget__reply-bar">
                      <div className="chat-widget__reply-bar-content">
                        <strong>Respondendo a {replyingTo.sender_name || (replyingTo.direction === 'OUTBOUND' ? 'Você' : 'Mensagem')}:</strong>
                        <span>{replyingTo.content || (replyingTo.message_type === 'STICKER' ? 'Figurinha' : replyingTo.message_type === 'IMAGE' ? 'Foto' : `[${replyingTo.message_type}]`)}</span>
                      </div>
                      <button type="button" className="chat-widget__reply-bar-close" onClick={() => setReplyingTo(null)} title="Cancelar resposta">
                        <X size={14} />
                      </button>
                    </div>
                  )}
                  {attachment && <div className="chat-widget__attachment" role="status">{attachmentPreview && <img className="chat-widget__attachment-preview" src={attachmentPreview} alt="Prévia da imagem anexada" />}<span>{attachment.name} · {(attachment.size / 1024 / 1024).toFixed(1)} MiB</span><button type="button" disabled={sending} aria-label="Remover anexo" onClick={() => setAttachment(null)}><X size={14} /></button></div>}
                  {isRecording ? (
                    <div className="chat-widget__recording">
                      <div className="chat-widget__recording-indicator">
                        <span className="chat-widget__recording-dot" />
                        <span className="chat-widget__recording-timer">
                          {Math.floor(recordingDuration / 60).toString().padStart(2, '0')}:{(recordingDuration % 60).toString().padStart(2, '0')}
                        </span>
                        <span className="chat-widget__recording-text">Gravando áudio…</span>
                      </div>
                      <div className="chat-widget__recording-actions">
                        <button
                          type="button"
                          className="chat-widget__recording-btn chat-widget__recording-btn--cancel"
                          title="Cancelar gravação"
                          aria-label="Cancelar gravação"
                          onClick={cancelRecording}
                        >
                          <Trash2 size={16} />
                        </button>
                        <button
                          type="button"
                          className="chat-widget__recording-btn chat-widget__recording-btn--send"
                          title="Enviar áudio"
                          aria-label="Enviar áudio"
                          disabled={sending}
                          onClick={stopAndSendRecording}
                        >
                          <Send size={15} />
                        </button>
                      </div>
                    </div>
                  ) : (
                    <form
                      className="chat-widget__composer"
                      onPaste={(event) => {
                        if (!canReply || sendingRef.current || updatingRef.current) return;
                        const pasted = readImagePaste(event.clipboardData);
                        if (pasted.kind === 'text') return;
                        event.preventDefault();
                        if (pasted.kind === 'error') { setError(pasted.message); return; }
                        if (attachment) { setError('Remova o anexo atual antes de colar outra imagem.'); return; }
                        setError(null);
                        setAttachment(pasted.file);
                      }}
                      onSubmit={(event) => {
                        event.preventDefault();
                        event.stopPropagation();
                        void send();
                      }}
                    >
                      <input type="file" hidden ref={uploadInput} onChange={(e) => {
                        const file = e.target.files?.[0]; e.target.value = '';
                        if (!file) return;
                        const error = attachmentError(file);
                        if (error) { setError(error); return; }
                        setError(null); setAttachment(file);
                      }} />
                      <button type="button" aria-label="Anexar arquivo" title="Anexar arquivo (até 20 MiB)" disabled={!canReply || sending || updating} onClick={() => uploadInput.current?.click()}><Paperclip size={15} /></button>
                      <input
                        value={draft}
                        onChange={(event) => setDraft(event.target.value)}
                        placeholder={!canSend ? 'Sem permissão para enviar' : active?.is_archived ? 'Desarquive para responder' : active?.status === 'CLOSED' ? 'Reabra a conversa para responder' : 'Escreva uma mensagem'}
                        disabled={!canReply || sending || updating}
                      />
                      {canReply && !draft.trim() && !attachment ? (
                        <button
                          type="button"
                          aria-label="Gravar áudio"
                          title="Gravar áudio"
                          disabled={sending || updating}
                          onClick={() => void startRecording()}
                        >
                          <Mic size={15} />
                        </button>
                      ) : (
                        <button type="submit" aria-label="Enviar mensagem" title={sending ? 'Enviando…' : 'Enviar mensagem'} disabled={!canReply || sending || updating || (!draft.trim() && !attachment)}>
                          {sending ? <RefreshCw size={15} className="chat-widget__sending" /> : <Send size={15} />}
                        </button>
                      )}
                    </form>
                  )}
                </>}
              </>
            )}
          </section>
        </div>}
      </aside>
    )}
    <button
      type="button"
      className={`chat-widget__fab${isOpen ? ' is-open' : ''}`}
      onClick={toggle}
      title="Abrir chat"
    >
      {isOpen ? <X size={22} /> : <MessageCircle size={22} />}
      {!isOpen && unreadCount > 0 && <span>{unreadCount > 99 ? '99+' : unreadCount}</span>}
    </button>
  </div>,
  document.body
);
}
