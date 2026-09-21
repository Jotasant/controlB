export const MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024;

export function attachmentError(file: Pick<File, 'size'>): string | null {
  return !file.size || file.size > MAX_ATTACHMENT_BYTES
    ? 'Selecione um arquivo não vazio de até 20 MiB.' : null;
}

type ImagePaste = { kind: 'text' } | { kind: 'error'; message: string } | { kind: 'image'; file: File };

// Use the paste event, not navigator.clipboard: no extra permission or HTTPS requirement.
export function readImagePaste(data: Pick<DataTransfer, 'items' | 'files'> | null): ImagePaste {
  if (!data) return { kind: 'text' };
  const items = Array.from(data.items).filter((item) => item.kind === 'file' && item.type.startsWith('image/'));
  const images = items.length
    ? items.map((item) => item.getAsFile())
    : Array.from(data.files).filter((file) => file.type.startsWith('image/'));
  if (!images.length) return { kind: 'text' };
  if (images.length > 1) return { kind: 'error', message: 'Cole uma imagem por vez.' };
  const file = images[0];
  if (!file) return { kind: 'error', message: 'Não foi possível ler a imagem copiada. Tente copiar novamente.' };
  const error = attachmentError(file);
  return error ? { kind: 'error', message: error } : { kind: 'image', file };
}
