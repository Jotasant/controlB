import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import ts from 'typescript';

function source(path: string) {
  return ts.createSourceFile(path, readFileSync(new URL(path, import.meta.url), 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
}
function tags(file: ts.SourceFile, tag: string) {
  const result: string[] = [];
  function visit(node: ts.Node) {
    if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) && node.tagName.getText(file) === tag) result.push(node.getText(file));
    ts.forEachChild(node, visit);
  }
  visit(file); return result;
}

test('listas de CRM e Vendas não montam editores de cliente, cotação e pedido em popup', () => {
  for (const path of ['./CRM/CRM.tsx', './Sales/Sales.tsx']) {
    const file = source(path);
    for (const tag of ['CustomerModal', 'QuoteModal', 'OrderModal']) assert.equal(tags(file, tag).length, 0);
    assert.ok(tags(file, 'RecordEditorSurface').every(node => /\bpage\b/.test(node)));
  }
});

test('rota de vendas ativa explicitamente o modo página dos três editores', () => {
  const file = source('./Sales/SalesRecordFormPage.tsx');
  for (const tag of ['CustomerModal', 'QuoteModal', 'OrderModal']) {
    const editors = tags(file, tag); assert.equal(editors.length, 1); assert.match(editors[0], /\bpage\b/);
  }
});

test('rotas por ID estão registradas para todos os formulários comerciais', () => {
  const file = source('../App.tsx');
  for (const path of ['/vendas/clientes/:recordId', '/vendas/cotacoes/:recordId', '/vendas/pedidos/:recordId', '/crm/:resource/:recordId', '/vendas/:resource/:recordId', '/crm/equipes/:recordId', '/vendas/equipes/:recordId']) assert.ok(file.text.includes(`path: '${path}'`), path);
});
