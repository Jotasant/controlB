import type { ChatNotificationItem } from '../../types/chat.ts';

/** A sobreposição entre polls captura commits tardios; IDs evitam alertas repetidos. */
export function unseenNotifications(items: ChatNotificationItem[], baseline: string, seen: Map<string, string>) {
  const fresh = items.filter((item) => {
    if (Date.parse(item.received_at) < Date.parse(baseline) || seen.has(item.id)) return false;
    seen.set(item.id, item.received_at);
    return true;
  });
  return fresh;
}
