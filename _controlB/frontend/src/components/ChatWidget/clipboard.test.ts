import assert from 'node:assert/strict';
import { test } from 'node:test';
import { attachmentError, MAX_ATTACHMENT_BYTES, readImagePaste } from './clipboard.ts';

function clipboard(files: File[], text = false): Pick<DataTransfer, 'items' | 'files'> {
  return {
    items: [
      ...(text ? [{ kind: 'string', type: 'text/plain', getAsFile: () => null }] : []),
      ...files.map((file) => ({ kind: 'file', type: file.type, getAsFile: () => file })),
    ] as unknown as DataTransferItemList,
    files: files as unknown as FileList,
  };
}

test('preserva colagem normal de texto e clipboard vazio', () => {
  assert.deepEqual(readImagePaste(clipboard([], true)), { kind: 'text' });
  assert.deepEqual(readImagePaste(clipboard([])), { kind: 'text' });
  assert.deepEqual(readImagePaste(null), { kind: 'text' });
});

test('print vira o mesmo File utilizado pelo envio de anexos, sem duplicar items/files', () => {
  const file = new File(['screenshot'], 'image.png', { type: 'image/png' });
  assert.deepEqual(readImagePaste(clipboard([file])), { kind: 'image', file });
  assert.deepEqual(readImagePaste(clipboard([file], true)), { kind: 'image', file });
});

test('aceita navegador que disponibiliza imagem apenas em files', () => {
  const file = new File(['screenshot'], 'image.png', { type: 'image/png' });
  const data = { ...clipboard([file]), items: [] as unknown as DataTransferItemList };
  assert.deepEqual(readImagePaste(data), { kind: 'image', file });
});

test('arquivo que não é imagem não intercepta colagem', () => {
  assert.deepEqual(readImagePaste(clipboard([new File(['pdf'], 'doc.pdf', { type: 'application/pdf' })])), { kind: 'text' });
});

test('rejeita imagem vazia e aplica o mesmo limite do seletor de anexos', () => {
  assert.equal(readImagePaste(clipboard([new File([], 'empty.png', { type: 'image/png' })])).kind, 'error');
  assert.equal(attachmentError({ size: MAX_ATTACHMENT_BYTES }), null);
  assert.match(attachmentError({ size: MAX_ATTACHMENT_BYTES + 1 })!, /20 MiB/);
  const large = new File([new Uint8Array(MAX_ATTACHMENT_BYTES + 1)], 'large.png', { type: 'image/png' });
  assert.equal(readImagePaste(clipboard([large])).kind, 'error');
});

test('não descarta silenciosamente imagens adicionais', () => {
  const file = new File(['img'], 'image.png', { type: 'image/png' });
  assert.deepEqual(readImagePaste(clipboard([file, file])), { kind: 'error', message: 'Cole uma imagem por vez.' });
});

test('informa erro quando o navegador não consegue extrair o arquivo', () => {
  const data = { ...clipboard([]), items: [{ kind: 'file', type: 'image/png', getAsFile: () => null }] as unknown as DataTransferItemList };
  assert.equal(readImagePaste(data).kind, 'error');
});
