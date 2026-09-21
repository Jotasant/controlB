import { test } from 'node:test';
import assert from 'node:assert/strict';
import { unseenNotifications } from './notifications.ts';

const item = (id: string, received_at: string) => ({ id, conversation_id: 'channel', title: 'Grupo', sender_name: 'Maria', received_at });
test('ignora mensagens anteriores à abertura e deduplica polls sobrepostos', () => {
  const seen = new Map<string, string>();
  const baseline = '2026-09-20T10:00:00Z';
  const items = [item('old', '2026-09-20T09:59:00Z'), item('new', '2026-09-20T10:00:01Z')];
  assert.deepEqual(unseenNotifications(items, baseline, seen).map((i) => i.id), ['new']);
  assert.deepEqual(unseenNotifications(items, baseline, seen), []);
  assert.deepEqual(unseenNotifications([item('late-commit', '2026-09-20T10:00:00Z')], baseline, seen).map((i) => i.id), ['late-commit']);
});
