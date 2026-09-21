import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const source = (path: string) => readFileSync(new URL(path, import.meta.url), 'utf8');

test('todos os cadastros comerciais selecionam Identity em vez de editar contato local', () => {
  for (const path of ['./CustomerModal/CustomerModal.tsx', './CustomerPicker/CustomerPicker.tsx', '../pages/Purchasing/Purchasing.tsx']) {
    const code = source(path);
    assert.ok(code.includes('<IdentityContactField'), path);
    assert.doesNotMatch(code, /(?:email|phone|contact_name):\s*(?:draft\.|supplierEmail|supplierPhone|supplierContactName)/);
  }
});

test('criar/editar contato usa páginas e preserva o formulário de origem', () => {
  const code = source('./IdentityContactField.tsx');
  assert.ok(code.includes('identityService.getContacts()'));
  assert.ok(code.includes('href="/contatos/novo"'));
  assert.ok(code.includes('target="_blank"'));
  assert.ok(code.includes("window.addEventListener('focus', load)"));
});

test('participante sem telefone não dispara abertura e troca de canal limpa resposta/anexo', () => {
  const code = source('./ChatWidget/ChatWidget.tsx');
  assert.ok(code.includes('disabled={!message.sender_phone || !canSend'));
  assert.ok(code.includes('chatService.openGroupParticipant(active.id, message.id)'));
  assert.ok(code.includes('invalidateRequests(); clearSelection(); setShowDetails(false); setNewConversation(null)'));
});
