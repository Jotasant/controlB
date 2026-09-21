import assert from 'node:assert/strict';
import { test } from 'node:test';
import { linkify } from './linkify.ts';

test('preserva o texto e torna HTTP(S) e www clicáveis', () => {
  const text = 'Veja https://exemplo.test/p?a=1&b=2. Também www.exemplo.test!';
  const parts = linkify(text);
  assert.equal(parts.map((p) => p.text).join(''), text);
  assert.deepEqual(parts.filter((p) => p.href).map((p) => p.href), [
    'https://exemplo.test/p?a=1&b=2', 'https://www.exemplo.test/',
  ]);
});

test('não interpreta HTML, javascript, data URLs ou credenciais como links', () => {
  const text = '<script>alert(1)</script> javascript:alert(1) data:text/html,oi https://user:password@exemplo.test';
  const parts = linkify(text);
  assert.equal(parts.map((p) => p.text).join(''), text);
  assert.equal(parts.some((p) => p.href), false);
});

test('preserva espaços, linhas e URLs incompletas', () => {
  for (const text of ['', 'https://', 'texto\n\n  texto', '(https://exemplo.test). https://?']) {
    assert.equal(linkify(text).map((p) => p.text).join(''), text);
  }
});
