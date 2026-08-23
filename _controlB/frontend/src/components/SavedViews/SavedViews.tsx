import { useEffect, useMemo, useState } from 'react';
import { Bookmark, Check, ChevronDown, Plus, Star, Trash2, X } from 'lucide-react';

import './SavedViews.scss';

export interface SavedView<TState> {
  id: string;
  name: string;
  state: TState;
  isDefault: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface SavedViewRepository<TState> {
  list(scope: string): Promise<SavedView<TState>[]>;
  save(scope: string, view: SavedView<TState>): Promise<SavedView<TState>>;
  remove(scope: string, id: string): Promise<void>;
  setDefault(scope: string, id: string | null): Promise<void>;
}

const makeId = () =>
  globalThis.crypto?.randomUUID?.() ?? `view-${Date.now()}-${Math.random()}`;

export class LocalSavedViewRepository<TState> implements SavedViewRepository<TState> {
  private readonly prefix: string;

  constructor(prefix = 'controlb:saved-views') {
    this.prefix = prefix;
  }

  private key(scope: string) {
    return `${this.prefix}:${scope}`;
  }

  async list(scope: string): Promise<SavedView<TState>[]> {
    try {
      const raw = localStorage.getItem(this.key(scope));
      return raw ? JSON.parse(raw) as SavedView<TState>[] : [];
    } catch {
      return [];
    }
  }

  private async write(scope: string, views: SavedView<TState>[]) {
    localStorage.setItem(this.key(scope), JSON.stringify(views));
  }

  async save(scope: string, view: SavedView<TState>): Promise<SavedView<TState>> {
    const views = await this.list(scope);
    const normalized = view.isDefault
      ? views.map((item) => ({ ...item, isDefault: false }))
      : views;
    const index = normalized.findIndex((item) => item.id === view.id);
    if (index >= 0) normalized[index] = view;
    else normalized.push(view);
    await this.write(scope, normalized);
    return view;
  }

  async remove(scope: string, id: string): Promise<void> {
    const views = await this.list(scope);
    await this.write(scope, views.filter((view) => view.id !== id));
  }

  async setDefault(scope: string, id: string | null): Promise<void> {
    const views = await this.list(scope);
    await this.write(scope, views.map((view) => ({ ...view, isDefault: view.id === id })));
  }
}

interface SavedViewsProps<TState> {
  scope: string;
  currentState: TState;
  onApply: (state: TState) => void;
  repository?: SavedViewRepository<TState>;
  onDefaultLoaded?: (state: TState) => void;
}

export const SavedViews = <TState,>({
  scope,
  currentState,
  onApply,
  repository,
  onDefaultLoaded,
}: SavedViewsProps<TState>) => {
  const localRepository = useMemo(() => new LocalSavedViewRepository<TState>(), []);
  const store = repository ?? localRepository;
  const [views, setViews] = useState<SavedView<TState>[]>([]);
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState('');

  useEffect(() => {
    let active = true;
    store.list(scope).then((loaded) => {
      if (!active) return;
      setViews(loaded);
      const defaultView = loaded.find((view) => view.isDefault);
      if (defaultView) onDefaultLoaded?.(defaultView.state);
    });
    return () => { active = false; };
  }, [onDefaultLoaded, scope, store]);

  const refresh = async () => setViews(await store.list(scope));

  const saveCurrent = async () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    const now = new Date().toISOString();
    await store.save(scope, {
      id: makeId(),
      name: trimmed,
      state: JSON.parse(JSON.stringify(currentState)) as TState,
      isDefault: false,
      createdAt: now,
      updatedAt: now,
    });
    setName('');
    setCreating(false);
    await refresh();
  };

  const remove = async (id: string) => {
    await store.remove(scope, id);
    await refresh();
  };

  const toggleDefault = async (view: SavedView<TState>) => {
    await store.setDefault(scope, view.isDefault ? null : view.id);
    await refresh();
  };

  return (
    <div className="saved-views">
      <button
        type="button"
        className={`saved-views__trigger ${open ? 'active' : ''}`}
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <Bookmark size={14} />
        Favoritos
        {views.length > 0 && <span>{views.length}</span>}
        <ChevronDown size={13} />
      </button>

      {open && (
        <div className="saved-views__popover" role="menu">
          <header>
            <strong>Visualizações salvas</strong>
            <button type="button" onClick={() => setOpen(false)} aria-label="Fechar favoritos">
              <X size={14} />
            </button>
          </header>

          <div className="saved-views__list">
            {views.length === 0 ? (
              <p>Nenhum favorito salvo.</p>
            ) : views.map((view) => (
              <div className="saved-views__item" key={view.id}>
                <button
                  type="button"
                  className="saved-views__apply"
                  onClick={() => {
                    onApply(JSON.parse(JSON.stringify(view.state)) as TState);
                    setOpen(false);
                  }}
                  role="menuitem"
                >
                  {view.isDefault ? <Star size={13} fill="currentColor" /> : <Bookmark size={13} />}
                  <span>{view.name}</span>
                </button>
                <button
                  type="button"
                  className={view.isDefault ? 'default' : ''}
                  onClick={() => void toggleDefault(view)}
                  title={view.isDefault ? 'Remover como padrão' : 'Usar ao abrir esta tela'}
                  aria-label={view.isDefault ? 'Remover favorito padrão' : 'Definir como favorito padrão'}
                >
                  <Star size={13} fill={view.isDefault ? 'currentColor' : 'none'} />
                </button>
                <button
                  type="button"
                  onClick={() => void remove(view.id)}
                  title="Excluir favorito"
                  aria-label={`Excluir favorito ${view.name}`}
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
          </div>

          {creating ? (
            <div className="saved-views__create">
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') void saveCurrent();
                  if (event.key === 'Escape') setCreating(false);
                }}
                placeholder="Nome da visualização"
                autoFocus
              />
              <button type="button" onClick={() => void saveCurrent()} disabled={!name.trim()}>
                <Check size={14} />
              </button>
              <button type="button" onClick={() => setCreating(false)}>
                <X size={14} />
              </button>
            </div>
          ) : (
            <button type="button" className="saved-views__new" onClick={() => setCreating(true)}>
              <Plus size={14} /> Salvar pesquisa atual
            </button>
          )}
        </div>
      )}
    </div>
  );
};

