import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { MessageCircle, Plus, RefreshCw, Search, Wifi } from 'lucide-react';

import { useListPagination } from '@/hooks/useListPagination';
import { usePermissions } from '@/hooks/usePermissions';
import { buildRecordFormPath, createRecordNavigationState } from '@/routing/recordRoutes';
import { chatService, formatApiError } from '@/services/api';
import type { ChatConnection, ChatConnectionStatus } from '@/types/chat';
import { useLocation } from 'react-router-dom';

import '../Cadastros/Cadastros.scss';
import './ChatConnections.scss';

const STATUS_LABEL: Record<ChatConnectionStatus, string> = {
  CONNECTED: 'Conectada',
  CONNECTING: 'Pareando',
  DISCONNECTED: 'Desconectada',
  ERROR: 'Erro',
};

export function ChatConnections() {
  const navigate = useNavigate();
  const location = useLocation();
  const { hasPermission, loading: permissionsLoading } = usePermissions();
  const canManage = hasPermission('chat:manage_connectors');
  const [connections, setConnections] = useState<ChatConnection[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setConnections(await chatService.getConnections(true));
    } catch (loadError) {
      setError(formatApiError(loadError, 'Não foi possível carregar as conexões.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!permissionsLoading && canManage) void loadData();
  }, [loadData, permissionsLoading, canManage]);

  const term = searchTerm.toLocaleLowerCase('pt-BR').trim();
  const filtered = useMemo(
    () =>
      connections.filter(
        (item) =>
          item.name.toLocaleLowerCase('pt-BR').includes(term) ||
          item.external_instance_id.toLocaleLowerCase('pt-BR').includes(term) ||
          item.base_url.toLocaleLowerCase('pt-BR').includes(term),
      ),
    [connections, term],
  );
  const pagination = useListPagination(filtered);
  const openRecord = (id?: string) =>
    navigate(buildRecordFormPath('chat', 'conexoes', id), {
      state: createRecordNavigationState(location),
    });

  if (permissionsLoading) return <p role="status">Carregando permissões...</p>;
  if (!canManage) return <p role="alert">Sem permissão para gerenciar conexões do Chat.</p>;

  return (
    <div className="cadastros-page chat-connections-page">
      <div className="cadastros-layout">
        <aside className="sidebar-left">
          <div className="sidebar-header">
            <span className="sidebar-section-title">Chat</span>
          </div>
          <nav className="sidebar-menu-list">
            <button type="button" className="sidebar-menu-btn active">
              <div className="btn-label">
                <Wifi size={16} className="icon-org" />
                <span>Conexões</span>
              </div>
              <div className="btn-meta">
                <span className="count-badge">{connections.length}</span>
              </div>
            </button>
          </nav>
          <p className="chat-sidebar-hint">
            As conversas ficam no painel flutuante. Esta área configura o canal WhatsApp da organização.
          </p>
        </aside>

        <main className="content-right">
          <header className="content-header">
            <div className="titles">
              <h1>Conexões do Chat</h1>
              <p>Cadastre o servidor, crie a instância e pareie o WhatsApp sem o Evolution Manager.</p>
            </div>
            <div className="header-actions">
              <button className="btn-refresh" onClick={() => void loadData()} disabled={loading} title="Atualizar dados">
                <RefreshCw size={13} className={loading ? 'spin' : ''} />
                <span>Atualizar</span>
              </button>
              {canManage && (
                <button className="btn-primary" onClick={() => openRecord()}>
                  <Plus size={14} />
                  <span>Nova conexão</span>
                </button>
              )}
            </div>
          </header>
          {error && <div className="alert-error">{error}</div>}
          <div className="table-card">
            <div className="table-toolbar">
              <div className="search-wrap">
                <Search size={14} />
                <input
                  type="text"
                  placeholder="Buscar conexão, instância ou servidor..."
                  value={searchTerm}
                  onChange={(event) => setSearchTerm(event.target.value)}
                />
              </div>
              <span className="results-count">{filtered.length} conexão(ões)</span>
            </div>
            {loading ? (
              <div className="state-empty">Carregando conexões...</div>
            ) : filtered.length === 0 ? (
              <div className="state-empty">
                Nenhuma conexão cadastrada. Informe nome, servidor e credencial para começar.
              </div>
            ) : (
              <div className="table-responsive">
                <table className="enterprise-table">
                  <thead>
                    <tr>
                      <th>Conexão</th>
                      <th>Instância</th>
                      <th>Servidor</th>
                      <th>Status</th>
                      <th>Atualizado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pagination.pageItems.map((item) => (
                      <tr
                        key={item.id}
                        className="ui-record-row"
                        role="button"
                        tabIndex={0}
                        onClick={() => openRecord(item.id)}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter' || event.key === ' ') {
                            event.preventDefault();
                            openRecord(item.id);
                          }
                        }}
                      >
                        <td>
                          <div className="cell-with-icon clickable">
                            <div className="icon-badge brand-bg">
                              <MessageCircle size={14} />
                            </div>
                            <div>
                              <strong>{item.name}</strong>
                              <div className="chat-provider-label">{item.provider}</div>
                            </div>
                          </div>
                        </td>
                        <td>{item.external_instance_id}</td>
                        <td className="chat-url-cell">{item.base_url}</td>
                        <td>
                          <span className={`badge-pill chat-status-pill is-${item.status.toLowerCase()}`}>
                            {STATUS_LABEL[item.status]}
                          </span>
                        </td>
                        <td>
                          {item.last_synced_at
                            ? new Date(item.last_synced_at).toLocaleString('pt-BR')
                            : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

export default ChatConnections;
