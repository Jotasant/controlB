import { linkify } from './linkify';

export function MessageText({ text }: { text: string }) {
  return <p>{linkify(text).map((part, index) => part.href
    ? <a key={index} href={part.href} target="_blank" rel="noopener noreferrer">{part.text}</a>
    : part.text)}</p>;
}
