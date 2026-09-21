export interface MessagePart { text: string; href?: string }

// Somente URLs HTTP(S). O conteúdo nunca é interpretado como HTML.
export function linkify(text: string): MessagePart[] {
  const parts: MessagePart[] = [];
  let cursor = 0;
  for (const match of text.matchAll(/\b(?:https?:\/\/|www\.)[^\s<>"']+/gi)) {
    const start = match.index;
    const value = match[0].replace(/[.,;:!?\])}]+$/, '');
    if (start > cursor) parts.push({ text: text.slice(cursor, start) });
    let href: string | undefined;
    try {
      const parsed = new URL(/^www\./i.test(value) ? `https://${value}` : value);
      if (['http:', 'https:'].includes(parsed.protocol) && !parsed.username && !parsed.password) href = parsed.href;
    } catch { /* URLs incompletas permanecem como texto. */ }
    parts.push({ text: value, href });
    cursor = start + value.length;
  }
  if (cursor < text.length) parts.push({ text: text.slice(cursor) });
  return parts;
}
