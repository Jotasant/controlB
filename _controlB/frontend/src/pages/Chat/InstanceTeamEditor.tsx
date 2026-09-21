import { useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';

export function InstanceTeamEditor({ users, memberIds, currentUserId, disabled, onChange }: {
  users: { id: string; full_name: string }[]; memberIds: string[]; currentUserId?: string;
  disabled: boolean; onChange: (ids: string[]) => void;
}) {
  const [adding, setAdding] = useState(false);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState('');
  const candidates = users.filter((user) => !memberIds.includes(user.id) && user.full_name.toLocaleLowerCase().includes(search.toLocaleLowerCase()));
  return <div className="chat-team-editor">
    <p>Somente participantes desta organização podem acessar a instância. As alterações são aplicadas ao salvar.</p>
    <button type="button" className="ui-button ui-button--secondary" disabled={disabled} onClick={() => setAdding(true)}><Plus size={15} /> Adicionar participante</button>
    {adding && <div className="ui-form chat-team-editor__add">
      <input aria-label="Buscar usuário da organização" placeholder="Buscar usuário da organização" value={search} disabled={disabled} onChange={(e) => { setSearch(e.target.value); setSelected(''); }} />
      <select aria-label="Usuário para adicionar" value={selected} disabled={disabled} onChange={(e) => setSelected(e.target.value)}>
        <option value="">Selecione um usuário</option>{candidates.map((user) => <option key={user.id} value={user.id}>{user.full_name}</option>)}
      </select>
      <button type="button" className="ui-button ui-button--primary" disabled={disabled || !selected || !candidates.some((user) => user.id === selected)} onClick={() => {
        onChange([...memberIds, selected]); setSelected(''); setSearch(''); setAdding(false);
      }}>Adicionar</button>
      <button type="button" className="ui-button ui-button--secondary" onClick={() => setAdding(false)}>Cancelar</button>
    </div>}
    <ul>{memberIds.map((id) => <li key={id}>
      <span>{users.find((user) => user.id === id)?.full_name || 'Usuário indisponível'}{id === currentUserId ? ' (você)' : ''}</span>
      <button type="button" className="ui-button ui-button--secondary" disabled={disabled || id === currentUserId}
        title={id === currentUserId ? 'Mantenha seu acesso para gerenciar a instância' : 'Remover participante'}
        onClick={() => onChange(memberIds.filter((value) => value !== id))}><Trash2 size={14} /> Remover</button>
    </li>)}</ul>
  </div>;
}
