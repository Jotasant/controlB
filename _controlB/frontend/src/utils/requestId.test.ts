import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createRequestId } from './requestId.ts';

test('envio por HTTP sem randomUUID ainda recebe UUID v4 seguro e único', () => {
  const insecureContext = { getRandomValues: globalThis.crypto.getRandomValues.bind(globalThis.crypto) } as Crypto;
  const ids = Array.from({ length: 100 }, () => createRequestId(insecureContext));
  for (const id of ids) assert.match(id, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  assert.equal(new Set(ids).size, ids.length);
});

test('usa randomUUID quando disponível', () => {
  assert.equal(createRequestId({ randomUUID: () => 'identificador' } as unknown as Crypto), 'identificador');
});

test('falha com explicação se o navegador não oferece criptografia', () => {
  assert.throws(() => createRequestId({} as Crypto), /navegador/);
});
