import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Building2, Check, ChevronDown, Loader2, Plus, Search, UserRound, X } from 'lucide-react';

import { Modal } from '@/components/Modal/Modal';
import { useToast } from '@/components/Toast/ToastContext';
import { formatApiError, salesService } from '@/services/api';
import type { Customer } from '@/types';

import './CustomerPicker.scss';

export interface CustomerPickerProps {
  value?: string | null;
  onChange: (customer: Customer | null) => void;
  disabled?: boolean;
  allowCreate?: boolean;
  label?: string;
  placeholder?: string;
  initialCustomer?: Customer | null;
}

interface CustomerDraft {
  person_type: 'PJ' | 'PF';
  document: string;
  name: string;
  trade_name: string;
  email: string;
  phone: string;
}

const EMPTY_DRAFT: CustomerDraft = {
  person_type: 'PJ',
  document: '',
  name: '',
  trade_name: '',
  email: '',
  phone: '',
};

const displayName = (customer: Customer) => customer.trade_name || customer.name;

export const CustomerPicker: React.FC<CustomerPickerProps> = ({
  value,
  onChange,
  disabled = false,
  allowCreate = true,
  label = 'Cliente vinculado',
  placeholder = 'Pesquisar por nome, documento, e-mail ou telefone...',
  initialCustomer = null,
}) => {
  const toast = useToast();
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [customers, setCustomers] = useState<Customer[]>(initialCustomer ? [initialCustomer] : []);
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState<CustomerDraft>(EMPTY_DRAFT);

  const selected = customers.find((customer) => customer.id === value) ?? initialCustomer;

  const loadCustomers = async (search?: string, force = false) => {
    setLoading(true);
    setError(null);
    try {
      const loaded = await salesService.getCustomers(search || undefined, force);
      setCustomers((current) => {
        const merged = new Map(current.map((customer) => [customer.id, customer]));
        loaded.forEach((customer) => merged.set(customer.id, customer));
        return Array.from(merged.values());
      });
    } catch (requestError) {
      setError(formatApiError(requestError, 'Não foi possível carregar os clientes.'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadCustomers();
  }, []);

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  useEffect(() => {
    if (!open || query.trim().length < 2) return;
    const timer = window.setTimeout(() => void loadCustomers(query.trim()), 280);
    return () => window.clearTimeout(timer);
  }, [open, query]);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase('pt-BR');
    if (!normalized) return customers.slice(0, 20);
    return customers.filter((customer) => [
      customer.name,
      customer.trade_name,
      customer.document,
      customer.email,
      customer.phone,
    ].some((item) => String(item ?? '').toLocaleLowerCase('pt-BR').includes(normalized))).slice(0, 20);
  }, [customers, query]);

  const createCustomer = async (event?: React.SyntheticEvent) => {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }
    if (!draft.name.trim() || !draft.document.trim()) {
      toast.warning('Informe o nome e o CPF/CNPJ do cliente.', 'Campos obrigatórios');
      return;
    }

    setCreating(true);
    try {
      const created = await salesService.createCustomer({
        person_type: draft.person_type,
        document: draft.document.trim(),
        name: draft.name.trim(),
        trade_name: draft.trade_name.trim() || undefined,
        email: draft.email.trim() || undefined,
        phone: draft.phone.trim() || undefined,
        credit_limit: 0,
        is_active: true,
      });
      setCustomers((current) => [created, ...current.filter((customer) => customer.id !== created.id)]);
      onChange(created);
      setDraft(EMPTY_DRAFT);
      setCreateOpen(false);
      setOpen(false);
      toast.success('Cliente criado e vinculado ao registro comercial.', 'Cliente cadastrado');
    } catch (requestError) {
      toast.error(formatApiError(requestError, 'Não foi possível cadastrar o cliente.'));
    } finally {
      setCreating(false);
    }
  };

  return (
    <>
      <div className="customer-picker" ref={wrapperRef}>
        <label>{label}</label>
        <button
          type="button"
          className={`customer-picker__value ${open ? 'active' : ''}`}
          onClick={() => !disabled && setOpen((current) => !current)}
          disabled={disabled}
          aria-haspopup="listbox"
          aria-expanded={open}
        >
          <span className="customer-picker__avatar">
            {selected?.person_type === 'PF' ? <UserRound size={15} /> : <Building2 size={15} />}
          </span>
          <span className="customer-picker__selected">
            {selected ? (
              <>
                <strong>{displayName(selected)}</strong>
                <small>{selected.document} · {selected.name}</small>
              </>
            ) : (
              <span>Selecionar cliente existente</span>
            )}
          </span>
          {selected && !disabled && (
            <span
              role="button"
              tabIndex={0}
              className="customer-picker__clear"
              aria-label="Remover cliente vinculado"
              onClick={(event) => {
                event.stopPropagation();
                onChange(null);
              }}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') onChange(null);
              }}
            >
              <X size={14} />
            </span>
          )}
          <ChevronDown size={14} />
        </button>

        {open && (
          <div className="customer-picker__popover">
            <div className="customer-picker__search">
              <Search size={14} />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={placeholder}
                autoFocus
              />
              {loading && <Loader2 size={14} className="spinning" />}
            </div>

            <div className="customer-picker__options" role="listbox">
              {error ? (
                <button type="button" className="customer-picker__message error" onClick={() => void loadCustomers(query, true)}>
                  {error} Clique para tentar novamente.
                </button>
              ) : filtered.length === 0 && !loading ? (
                <p className="customer-picker__message">Nenhum cliente encontrado.</p>
              ) : filtered.map((customer) => (
                <button
                  type="button"
                  role="option"
                  aria-selected={customer.id === value}
                  key={customer.id}
                  onClick={() => {
                    onChange(customer);
                    setOpen(false);
                    setQuery('');
                  }}
                >
                  <span className="customer-picker__avatar">
                    {customer.person_type === 'PF' ? <UserRound size={14} /> : <Building2 size={14} />}
                  </span>
                  <span>
                    <strong>{displayName(customer)}</strong>
                    <small>{customer.document} · {customer.email || customer.phone || customer.name}</small>
                  </span>
                  {customer.id === value && <Check size={14} />}
                </button>
              ))}
            </div>

            {allowCreate && (
              <button
                type="button"
                className="customer-picker__new"
                onClick={() => {
                  setDraft({ ...EMPTY_DRAFT, name: query.trim() });
                  setCreateOpen(true);
                  setOpen(false);
                }}
              >
                <Plus size={14} /> Cadastrar novo cliente
              </button>
            )}
          </div>
        )}
      </div>

      <Modal
        isOpen={createOpen}
        onClose={() => !creating && setCreateOpen(false)}
        title="Novo cliente"
        subtitle="O cadastro será compartilhado com CRM, Vendas e os demais módulos."
        size="md"
      >
        <div
          className="ui-form customer-picker__form"
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault();
              event.stopPropagation();
              void createCustomer(event);
            }
          }}
        >
          <div className="ui-form__row">
            <div className="ui-form__group">
              <label htmlFor="customer-person-type">Tipo de pessoa</label>
              <select
                id="customer-person-type"
                value={draft.person_type}
                onChange={(event) => setDraft({ ...draft, person_type: event.target.value as 'PJ' | 'PF' })}
              >
                <option value="PJ">Pessoa jurídica</option>
                <option value="PF">Pessoa física</option>
              </select>
            </div>
            <div className="ui-form__group">
              <label htmlFor="customer-document">{draft.person_type === 'PJ' ? 'CNPJ' : 'CPF'} *</label>
              <input
                id="customer-document"
                value={draft.document}
                onChange={(event) => setDraft({ ...draft, document: event.target.value })}
                placeholder={draft.person_type === 'PJ' ? '00.000.000/0000-00' : '000.000.000-00'}
                required
              />
            </div>
          </div>

          <div className="ui-form__group">
            <label htmlFor="customer-name">{draft.person_type === 'PJ' ? 'Razão social' : 'Nome completo'} *</label>
            <input
              id="customer-name"
              value={draft.name}
              onChange={(event) => setDraft({ ...draft, name: event.target.value })}
              required
            />
          </div>

          {draft.person_type === 'PJ' && (
            <div className="ui-form__group">
              <label htmlFor="customer-trade-name">Nome fantasia</label>
              <input
                id="customer-trade-name"
                value={draft.trade_name}
                onChange={(event) => setDraft({ ...draft, trade_name: event.target.value })}
              />
            </div>
          )}

          <div className="ui-form__row">
            <div className="ui-form__group">
              <label htmlFor="customer-email">E-mail</label>
              <input
                id="customer-email"
                type="email"
                value={draft.email}
                onChange={(event) => setDraft({ ...draft, email: event.target.value })}
              />
            </div>
            <div className="ui-form__group">
              <label htmlFor="customer-phone">Telefone / WhatsApp</label>
              <input
                id="customer-phone"
                value={draft.phone}
                onChange={(event) => setDraft({ ...draft, phone: event.target.value })}
              />
            </div>
          </div>

          <div className="ui-form__actions">
            <button
              type="button"
              className="ui-button ui-button--secondary"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setCreateOpen(false);
              }}
              disabled={creating}
            >
              Cancelar
            </button>
            <button
              type="button"
              className="ui-button ui-button--primary"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                void createCustomer(e);
              }}
              disabled={creating}
            >
              {creating ? <Loader2 size={14} className="spinning" /> : <Plus size={14} />}
              {creating ? 'Cadastrando...' : 'Cadastrar e vincular'}
            </button>
          </div>
        </div>
      </Modal>
    </>
  );
};

