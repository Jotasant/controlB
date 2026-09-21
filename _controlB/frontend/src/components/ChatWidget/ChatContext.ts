import { createContext, useContext } from 'react';

interface ChatUiValue {
  canAccess: boolean;
  isOpen: boolean;
  unreadCount: number;
  open: () => void;
  startConversation: (contactId?: string) => void;
  close: () => void;
  toggle: () => void;
}

export const ChatUiContext = createContext<ChatUiValue | null>(null);

export function useChatUi() {
  const value = useContext(ChatUiContext);
  if (!value) throw new Error('useChatUi deve ser usado dentro de ChatShell.');
  return value;
}
