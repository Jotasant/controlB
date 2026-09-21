import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowUpDown,
  Building2,
  Check,
  MessageSquare,
  Plus,
  RefreshCw,
  Trash2,
  UserPlus,
  Users
} from 'lucide-react';
import { RecordFormPage } from '@/components/RecordForm';
import { usePermissions } from '@/hooks/usePermissions';
import { useBulkSelection } from '@/hooks/useBulkSelection';
import { BulkActionsBar } from '@/components/BulkActionsBar';
import { ConfirmModal } from '@/components/ConfirmModal/ConfirmModal';
import { Modal } from '@/components/Modal/Modal';
import { CustomerPicker } from '@/components/CustomerPicker';
import { CustomerModal } from '@/components/CustomerModal/CustomerModal';
import { useToast } from '@/components/Toast/ToastContext';
import { useChatUi } from '@/components/ChatWidget/ChatContext';
import { chatService, crmService, formatApiError, identityService, salesService } from '@/services/api';
import type { ContactDirectoryEntry, Customer } from '@/types';
import type { ChatChannel } from '@/types/chat';
import './Contacts.scss';

type SortField = 'name' | 'phone' | 'last_contact' | 'status';
type SortOrder = 'asc' | 'desc';

export function Contacts() {
  const { hasPermission } = usePermissions();
  const canViewChat = hasPermission('chat:view');
  const toast = useToast();
  const chatUi = useChatUi();

  const [items, setItems] = useState<ContactDirectoryEntry[]>([]);
  const [channels, setChannels] = useState<ChatChannel[]>([]);
  const [search, setSearch] = useState('');
  const [connectionId, setConnectionId] = useState('');
  const [origin, setOrigin] = useState('');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Ordenação
  const [sortField, setSortField] = useState<SortField>('name');
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc');

  // Seleção em lote
  const contactSelection = useBulkSelection<ContactDirectoryEntry>();

  // Modais de ação
  const [confirmModal, setConfirmModal] = useState<{
    isOpen: boolean;
    title: string;
    subtitle?: string;
    message: string;
    confirmText?: string;
    type?: 'danger' | 'warning' | 'info';
    isLoading?: boolean;
    onConfirm: () => Promise<void>;
  }>({
    isOpen: false,
    title: '',
    message: '',
    onConfirm: async () => {},
  });

  const [linkCustomerModal, setLinkCustomerModal] = useState<{
    isOpen: boolean;
    contact: ContactDirectoryEntry | null;
    selectedCustomerId: string;
    loading: boolean;
  }>({
    isOpen: false,
    contact: null,
    selectedCustomerId: '',
    loading: false,
  });

  const [newCustomerModalContact, setNewCustomerModalContact] = useState<ContactDirectoryEntry | null>(null);
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    if (canViewChat) {
      void chatService.getChannels()
        .then((rows) => { if (active) setChannels(rows); })
        .catch(() => { if (active) setChannels([]); });
    }
    return () => { active = false; };
  }, [canViewChat, refresh]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    const timer = window.setTimeout(() => {
      void identityService.getContactDirectory({
        search,
        page,
        page_size: 30,
        ...(connectionId ? { connection_id: connectionId } : {}),
        ...(origin ? { origin_module: origin } : {}),
        ...(status ? { is_active: status === 'active' } : {})
      })
        .then((result) => {
          if (active) {
            setItems(result.items);
            setTotal(result.total);
          }
        })
        .catch((err) => {
          if (active) {
            setItems([]);
            setError(formatApiError(err, 'Não foi possível carregar os contatos.'));
          }
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    }, 200);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [search, connectionId, origin, status, page, refresh]);

  // Itens ordenados em memória
  const sortedItems = useMemo(() => {
    return [...items].sort((a, b) => {
      let valA = '';
      let valB = '';
      if (sortField === 'name') {
        valA = (a.name || a.full_name || '').toLowerCase();
        valB = (b.name || b.full_name || '').toLowerCase();
      } else if (sortField === 'phone') {
        valA = (a.phone || a.mobile || '').toLowerCase();
        valB = (b.phone || b.mobile || '').toLowerCase();
      } else if (sortField === 'last_contact') {
        valA = a.last_contact_at || '';
        valB = b.last_contact_at || '';
      } else if (sortField === 'status') {
        valA = a.is_active ? '1' : '0';
        valB = b.is_active ? '1' : '0';
      }
      const cmp = valA.localeCompare(valB);
      return sortOrder === 'asc' ? cmp : -cmp;
    });
  }, [items, sortField, sortOrder]);

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortOrder('asc');
    }
  };

  // Exclusão individual
  const handleDeleteContact = (contact: ContactDirectoryEntry) => {
    setConfirmModal({
      isOpen: true,
      title: 'Excluir Contato',
      subtitle: contact.name || contact.full_name || contact.phone || undefined,
      message: `Tem certeza que deseja excluir permanentemente o contato "${contact.name || contact.full_name || contact.phone}"? Esta ação removerá os vínculos diretos no ControlB.`,
      confirmText: 'Excluir permanentemente',
      type: 'danger',
      onConfirm: async () => {
        try {
          await identityService.deleteContact(contact.id);
          toast.success(`Contato "${contact.name || contact.phone}" excluído com sucesso.`, 'Contato Excluído');
          setConfirmModal((prev) => ({ ...prev, isOpen: false }));
          contactSelection.clearSelection();
          setRefresh((v) => v + 1);
        } catch (err) {
          toast.error(formatApiError(err, 'Erro ao excluir contato.'));
        }
      },
    });
  };

  // Exclusão em lote
  const handleBulkDelete = () => {
    const count = contactSelection.selectedCount;
    if (count === 0) return;

    setConfirmModal({
      isOpen: true,
      title: 'Excluir Contatos Selecionados',
      message: `Tem certeza que deseja excluir os ${count} contatos selecionados? Esta operação é irreversível.`,
      confirmText: `Excluir ${count} contatos`,
      type: 'danger',
      onConfirm: async () => {
        try {
          const res = await identityService.bulkDeleteContacts(contactSelection.selectedIdList);
          toast.success(`${res.deleted_count} contato(s) excluído(s) com sucesso.`, 'Exclusão em Lote Concluída');
          setConfirmModal((prev) => ({ ...prev, isOpen: false }));
          contactSelection.clearSelection();
          setRefresh((v) => v + 1);
        } catch (err) {
          toast.error(formatApiError(err, 'Erro ao excluir contatos selecionados.'));
        }
      },
    });
  };

  // Ação rápida: Criar Lead no CRM
  const handleCreateLeadFromContact = async (contact: ContactDirectoryEntry) => {
    setActionLoadingId(contact.id);
    try {
      const lead = await crmService.convertContactToLead(contact.id);
      toast.success(`Lead "${lead.name}" criado com sucesso no CRM!`, 'Lead Criado');
    } catch (err) {
      toast.error(formatApiError(err, 'Erro ao criar lead a partir do contato.'));
    } finally {
      setActionLoadingId(null);
    }
  };

  // Ação rápida: WhatsApp
  const handleOpenWhatsApp = (contact: ContactDirectoryEntry) => {
    if (chatUi.canAccess) {
      chatUi.startConversation(contact.id);
    } else if (contact.phone || contact.mobile) {
      const cleanPhone = (contact.phone || contact.mobile || '').replace(/\D/g, '');
      if (cleanPhone) {
        window.open(`https://wa.me/${cleanPhone}`, '_blank');
      }
    }
  };

  // Ação rápida: Vincular contato a cliente existente
  const handleConfirmLinkCustomer = async () => {
    if (!linkCustomerModal.contact || !linkCustomerModal.selectedCustomerId) return;
    setLinkCustomerModal((prev) => ({ ...prev, loading: true }));
    try {
      await salesService.updateCustomer(linkCustomerModal.selectedCustomerId, {
        contact_id: linkCustomerModal.contact.id,
      });
      toast.success('Contato vinculado ao Cliente com sucesso!', 'Vínculo Estabelecido');
      setLinkCustomerModal({ isOpen: false, contact: null, selectedCustomerId: '', loading: false });
      setRefresh((v) => v + 1);
    } catch (err) {
      toast.error(formatApiError(err, 'Falha ao vincular contato ao cliente.'));
      setLinkCustomerModal((prev) => ({ ...prev, loading: false }));
    }
  };

  return (
    <div className="contacts-page">
      <RecordFormPage
        title="Contatos"
        eyebrow="IDENTITY"
        icon={Users}
        description="Todos os contatos da sua organização, incluindo cadastros existentes e contatos recebidos pelo WhatsApp."
        breadcrumbs={[{ label: 'Módulos' }, { label: 'Contatos' }]}
        actions={
          <>
            <button
              type="button"
              className="ui-button ui-button--secondary"
              onClick={() => setRefresh((value) => value + 1)}
              disabled={loading}
            >
              <RefreshCw size={15} /> Atualizar
            </button>
            <Link className="ui-button ui-button--primary" to="/contatos/novo">
              <Plus size={15} /> Novo contato
            </Link>
          </>
        }
        error={error}
        onRetry={() => setRefresh((value) => value + 1)}
      >
        <div className="contacts-filters">
          <label>
            Buscar
            <input
              value={search}
              placeholder="Nome, telefone ou e-mail..."
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
            />
          </label>
          <label>
            Instância
            <select
              value={connectionId}
              onChange={(event) => {
                setConnectionId(event.target.value);
                setPage(1);
              }}
            >
              <option value="">Todas</option>
              {channels.map((channel) => (
                <option key={channel.id} value={channel.id}>
                  {channel.name}
                  {channel.instance_phone ? ` · +${channel.instance_phone}` : ''}
                </option>
              ))}
            </select>
          </label>
          <label>
            Cadastro de origem
            <select
              value={origin}
              onChange={(event) => {
                setOrigin(event.target.value);
                setPage(1);
              }}
            >
              <option value="">Todos</option>
              <option value="CHAT">WhatsApp</option>
              <option value="IDENTITY">Identity</option>
              <option value="CRM">CRM</option>
            </select>
          </label>
          <label>
            Status
            <select
              value={status}
              onChange={(event) => {
                setStatus(event.target.value);
                setPage(1);
              }}
            >
              <option value="">Todos</option>
              <option value="active">Ativos</option>
              <option value="inactive">Inativos</option>
            </select>
          </label>
        </div>

        <BulkActionsBar
          selectedCount={contactSelection.selectedCount}
          resourceName={{ singular: 'contato', plural: 'contatos' }}
          onClear={contactSelection.clearSelection}
          onDelete={handleBulkDelete}
          deleteLabel="Excluir selecionados"
        />

        <div className="contacts-table-wrap" aria-busy={loading}>
          <table className="contacts-table">
            <thead>
              <tr>
                <th className="ui-selection-cell">
                  <input
                    className="ui-selection-checkbox"
                    type="checkbox"
                    aria-label="Selecionar contatos desta página"
                    checked={contactSelection.isAllSelected(items)}
                    onChange={() => contactSelection.toggleSelectAll(items)}
                  />
                </th>
                <th className="sortable-th" onClick={() => toggleSort('name')}>
                  <div className="th-content">
                    <span>Contato</span>
                    <ArrowUpDown size={13} className={sortField === 'name' ? 'active-sort' : ''} />
                  </div>
                </th>
                <th className="sortable-th" onClick={() => toggleSort('phone')}>
                  <div className="th-content">
                    <span>Telefone</span>
                    <ArrowUpDown size={13} className={sortField === 'phone' ? 'active-sort' : ''} />
                  </div>
                </th>
                <th>Canal de aquisição</th>
                <th>Instâncias acessíveis</th>
                <th>Vínculos Comerciais</th>
                <th className="sortable-th" onClick={() => toggleSort('last_contact')}>
                  <div className="th-content">
                    <span>Último contato</span>
                    <ArrowUpDown size={13} className={sortField === 'last_contact' ? 'active-sort' : ''} />
                  </div>
                </th>
                <th className="sortable-th" onClick={() => toggleSort('status')}>
                  <div className="th-content">
                    <span>Status</span>
                    <ArrowUpDown size={13} className={sortField === 'status' ? 'active-sort' : ''} />
                  </div>
                </th>
                <th style={{ textAlign: 'center' }}>Ações Rápidas</th>
              </tr>
            </thead>
            <tbody>
              {!loading &&
                sortedItems.map((item) => {
                  const isSelected = contactSelection.isSelected(item.id);
                  const isBusy = actionLoadingId === item.id;
                  const hasCustomer = item.customers.length > 0;

                  return (
                    <tr key={item.id} className={isSelected ? 'is-selected' : ''}>
                      <td className="ui-selection-cell">
                        <input
                          className="ui-selection-checkbox"
                          type="checkbox"
                          aria-label={`Selecionar contato ${item.name || item.phone}`}
                          checked={isSelected}
                          onChange={() => contactSelection.toggleSelect(item.id)}
                        />
                      </td>
                      <td>
                        <Link to={`/contatos/${item.id}`}>
                          {item.name || item.full_name || 'Sem nome'}
                        </Link>
                        <small>{item.email || 'Sem e-mail'}</small>
                      </td>
                      <td>{item.phone || item.mobile || '—'}</td>
                      <td>
                        {item.origin_name || 'Não informado'}
                        <small>
                          Origem: {item.origin_module === 'CHAT' ? 'WhatsApp' : item.origin_module || 'Identity'}
                        </small>
                      </td>
                      <td>
                        {[...new Set(item.channels.map((channel) => channel.name))].join(', ') || '—'}
                      </td>
                      <td>
                        {hasCustomer && (
                          <span className="contact-badge contact-badge--customer" title="Possui cadastro de cliente">
                            Cliente: {item.customers.map((c) => c.name).join(', ')}
                          </span>
                        )}
                        {item.suppliers.length > 0 && (
                          <span className="contact-badge contact-badge--supplier">
                            Fornecedor
                          </span>
                        )}
                        {!hasCustomer && !item.suppliers.length && (
                          <span className="text-muted">Sem vínculo comercial</span>
                        )}
                      </td>
                      <td>
                        {item.last_contact_at
                          ? new Date(item.last_contact_at).toLocaleString('pt-BR')
                          : '—'}
                      </td>
                      <td>
                        <span className={`status-pill ${item.is_active ? 'is-active' : 'is-inactive'}`}>
                          {item.is_active ? 'Ativo' : 'Inativo'}
                        </span>
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <div className="contacts-quick-actions">
                          {/* WhatsApp */}
                          {(item.phone || item.mobile || item.channels.length > 0) && (
                            <button
                              type="button"
                              className="btn-quick-icon btn-wa"
                              onClick={() => handleOpenWhatsApp(item)}
                              title="Abrir no Chat / WhatsApp"
                            >
                              <MessageSquare size={14} />
                            </button>
                          )}

                          {/* Criar Lead */}
                          <button
                            type="button"
                            className="btn-quick-icon btn-lead"
                            disabled={isBusy}
                            onClick={() => void handleCreateLeadFromContact(item)}
                            title="Transformar em Lead no CRM"
                          >
                            <UserPlus size={14} />
                          </button>

                          {/* Vincular Cliente */}
                          {!hasCustomer && (
                            <button
                              type="button"
                              className="btn-quick-icon btn-link"
                              onClick={() =>
                                setLinkCustomerModal({
                                  isOpen: true,
                                  contact: item,
                                  selectedCustomerId: '',
                                  loading: false,
                                })
                              }
                              title="Vincular a um Cliente de Vendas"
                            >
                              <Building2 size={14} />
                            </button>
                          )}

                          {/* Excluir individual */}
                          <button
                            type="button"
                            className="btn-quick-icon btn-danger"
                            onClick={() => handleDeleteContact(item)}
                            title="Excluir Contato"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              {(loading || !items.length) && (
                <tr>
                  <td colSpan={9} style={{ textAlign: 'center', padding: '2rem' }}>
                    {loading ? 'Carregando contatos...' : 'Nenhum contato encontrado.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <footer className="contacts-pagination">
          <span>{total} contato(s)</span>
          <button
            type="button"
            className="ui-button ui-button--secondary"
            disabled={loading || page <= 1}
            onClick={() => setPage((value) => value - 1)}
          >
            Anterior
          </button>
          <span>
            {page} / {Math.max(1, Math.ceil(total / 30))}
          </span>
          <button
            type="button"
            className="ui-button ui-button--secondary"
            disabled={loading || page * 30 >= total}
            onClick={() => setPage((value) => value + 1)}
          >
            Próxima
          </button>
        </footer>
      </RecordFormPage>

      {/* Modal de Confirmação (Exclusão Individual e em Lote) */}
      <ConfirmModal
        isOpen={confirmModal.isOpen}
        title={confirmModal.title}
        subtitle={confirmModal.subtitle}
        message={confirmModal.message}
        confirmText={confirmModal.confirmText}
        type={confirmModal.type}
        isLoading={confirmModal.isLoading}
        onClose={() => setConfirmModal((prev) => ({ ...prev, isOpen: false }))}
        onConfirm={confirmModal.onConfirm}
      />

      {/* Modal Vincular Contato a Cliente Existente */}
      {linkCustomerModal.isOpen && (
        <Modal
          isOpen={true}
          onClose={() =>
            setLinkCustomerModal({ isOpen: false, contact: null, selectedCustomerId: '', loading: false })
          }
          title="Vincular Contato a um Cliente"
          subtitle={`Selecione um cliente existente para associar o contato "${linkCustomerModal.contact?.name || linkCustomerModal.contact?.phone}".`}
          size="md"
        >
          <div style={{ display: 'grid', gap: '1.25rem', padding: '0.5rem 0' }}>
            <CustomerPicker
              value={linkCustomerModal.selectedCustomerId}
              onChange={(customer: Customer | null) => {
                setLinkCustomerModal((prev) => ({
                  ...prev,
                  selectedCustomerId: customer?.id || '',
                }));
              }}
              label="Cliente da Base de Vendas *"
              placeholder="Pesquise por nome, CNPJ ou e-mail..."
            />

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1rem' }}>
              <button
                type="button"
                className="ui-button ui-button--secondary"
                onClick={() => {
                  const currentContact = linkCustomerModal.contact;
                  setLinkCustomerModal({ isOpen: false, contact: null, selectedCustomerId: '', loading: false });
                  if (currentContact) {
                    setNewCustomerModalContact(currentContact);
                  }
                }}
              >
                <Plus size={14} /> Cadastrar Novo Cliente
              </button>

              <div style={{ display: 'flex', gap: '0.6rem' }}>
                <button
                  type="button"
                  className="ui-button ui-button--secondary"
                  onClick={() =>
                    setLinkCustomerModal({ isOpen: false, contact: null, selectedCustomerId: '', loading: false })
                  }
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  className="ui-button ui-button--primary"
                  disabled={!linkCustomerModal.selectedCustomerId || linkCustomerModal.loading}
                  onClick={() => void handleConfirmLinkCustomer()}
                >
                  <Check size={14} />
                  {linkCustomerModal.loading ? 'Vinculando...' : 'Confirmar Vínculo'}
                </button>
              </div>
            </div>
          </div>
        </Modal>
      )}

      {/* Modal Criar Novo Cliente a partir do Contato */}
      {newCustomerModalContact && (
        <CustomerModal
          isOpen={true}
          onClose={() => setNewCustomerModalContact(null)}
          customer={
            {
              name: newCustomerModalContact.name || newCustomerModalContact.full_name || '',
              trade_name: newCustomerModalContact.trade_name || '',
              phone: newCustomerModalContact.phone || newCustomerModalContact.mobile || '',
              email: newCustomerModalContact.email || '',
              contact_id: newCustomerModalContact.id,
            } as any
          }
          onSuccess={async (createdCust) => {
            toast.success(`Cliente "${createdCust.name}" cadastrado e vinculado ao contato!`, 'Cliente Cadastrado');
            setNewCustomerModalContact(null);
            setRefresh((v) => v + 1);
          }}
        />
      )}
    </div>
  );
}
