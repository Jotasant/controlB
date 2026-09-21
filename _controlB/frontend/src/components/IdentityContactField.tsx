import { useEffect, useState } from 'react';
import { identityService, formatApiError } from '@/services/api';
import type { Contact } from '@/types';
import './IdentityContactField.scss';

/** Full Identity pages open separately so unsaved commercial fields stay intact. */
export function IdentityContactField({ value, onChange }: { value: string; onChange: (id: string) => void }) {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [error, setError] = useState('');
  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const items = await identityService.getContacts();
        if (mounted) { setContacts(items); setError(''); }
      } catch (err) { if (mounted) setError(formatApiError(err, 'Não foi possível carregar os contatos.')); }
    };
    void load();
    window.addEventListener('focus', load);
    return () => { mounted = false; window.removeEventListener('focus', load); };
  }, []);
  const contact = contacts.find((item) => item.id === value);
  return <div className="form-group identity-contact-field">
    <label>Contato do Identity</label>
    <select className="ui-input" aria-label="Contato do Identity" value={value} onChange={(event) => onChange(event.target.value)}>
      <option value="">Sem contato vinculado</option>
      {contacts.map((item) => <option key={item.id} value={item.id}>{item.name || item.full_name}{item.email ? ` — ${item.email}` : ''}</option>)}
    </select>
    {error && <small role="alert">{error}</small>}
    {contact && <dl className="identity-contact-field__details">
      <div><dt>E-mail</dt><dd>{contact.email || 'Não informado'}</dd></div>
      <div><dt>Telefone</dt><dd>{contact.phone || contact.mobile || 'Não informado'}</dd></div>
    </dl>}
    <div className="identity-contact-field__actions">
      <a className="ui-button ui-button--secondary" href="/contatos/novo" target="_blank" rel="noopener noreferrer">Novo contato no Identity ↗</a>
      {value && <a className="ui-button ui-button--secondary" href={`/contatos/${value}`} target="_blank" rel="noopener noreferrer">Editar contato ↗</a>}
    </div>
    <small>Abre uma página do Identity em outra aba, preservando este formulário. A lista atualiza ao retornar.</small>
  </div>;
}
