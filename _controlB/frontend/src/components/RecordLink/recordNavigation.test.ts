import assert from 'node:assert/strict';
import { test } from 'node:test';
import { buildRecordHref, buildDocumentHref, parseRecordReference } from './recordNavigation.ts';

test('registros de CRM e Vendas abrem páginas canônicas por ID', () => {
  const paths = {
    CUSTOMER: '/vendas/clientes', SALES_QUOTE: '/vendas/cotacoes', SALES_ORDER: '/vendas/pedidos',
    SALES_RETURN: '/vendas/devolucoes', LEAD: '/crm/leads', OPPORTUNITY: '/crm/oportunidades', CRM_INTERACTION: '/crm/atividades',
  };
  for (const [type, path] of Object.entries(paths)) assert.equal(buildRecordHref(type, 'registro-123'), `${path}/registro-123`);
});

test('aliases comerciais apontam para as mesmas páginas', () => {
  assert.equal(buildRecordHref('CLIENTE', '123'), '/vendas/clientes/123');
  assert.equal(buildRecordHref('QUOTE', '123'), '/vendas/cotacoes/123');
  assert.equal(buildRecordHref('ORDER', '123'), '/vendas/pedidos/123');
  assert.equal(buildRecordHref('CRM_ACTIVITY', '123'), '/crm/atividades/123');
});

test('ID não pode acrescentar rota ou query à URL gerada', () => {
  assert.equal(buildRecordHref('LEAD', '../x?a=b'), '/crm/leads/..%2Fx%3Fa%3Db');
  assert.equal(buildRecordHref('LEAD', ''), null);
  assert.equal(buildRecordHref('UNKNOWN', '123'), null);
});

test('referências antigas continuam reconhecidas e conversíveis para páginas', () => {
  const ref = parseRecordReference(new URLSearchParams('recordType=QUOTE&recordId=123&view=quotes'))!;
  assert.equal(buildRecordHref(ref.type, ref.id), '/vendas/cotacoes/123');
});

test('links de outros módulos e documentos mantêm seu contrato', () => {
  assert.equal(buildRecordHref('PRODUCT', '123'), '/estoque?view=produtos&recordType=PRODUCT&recordId=123');
  assert.equal(buildDocumentHref('123'), '/documentos?documentId=123');
});
