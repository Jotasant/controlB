import React, { useState, useEffect } from 'react';
import {
  Building2, UserRound, Mail, Phone, MapPin, CreditCard,
  FileText, Check, AlertTriangle, Hash, Landmark
} from 'lucide-react';
import { Modal } from '@/components/Modal/Modal';
import { useToast } from '@/components/Toast/ToastContext';
import { salesService, identityService, formatApiError } from '@/services/api';
import type { Customer, Contact } from '@/types';
import './CustomerModal.scss';

export interface CustomerModalProps {
  isOpen: boolean;
  onClose: () => void;
  customer?: Customer | null;
  onSuccess?: (customer: Customer) => void;
  initialPersonType?: 'PJ' | 'PF';
}

export const CustomerModal: React.FC<CustomerModalProps> = ({
  isOpen,
  onClose,
  customer,
  onSuccess,
  initialPersonType = 'PJ'
}) => {
  const toast = useToast();
  const isEditing = Boolean(customer?.id);

  // Estados dos Campos
  const [personType, setPersonType] = useState<'PJ' | 'PF'>(initialPersonType);
  const [name, setName] = useState<string>('');
  const [tradeName, setTradeName] = useState<string>('');
  const [document, setDocument] = useState<string>('');
  const [stateRegistration, setStateRegistration] = useState<string>('');
  const [email, setEmail] = useState<string>('');
  const [phone, setPhone] = useState<string>('');
  const [creditLimit, setCreditLimit] = useState<string>('50000.00');
  const [addressStreet, setAddressStreet] = useState<string>('');
  const [addressNumber, setAddressNumber] = useState<string>('');
  const [addressNeighborhood, setAddressNeighborhood] = useState<string>('');
  const [addressCity, setAddressCity] = useState<string>('');
  const [addressState, setAddressState] = useState<string>('SP');
  const [addressZipCode, setAddressZipCode] = useState<string>('');
  const [contactId, setContactId] = useState<string>('');
  const [notes, setNotes] = useState<string>('');

  const [contacts, setContacts] = useState<Contact[]>([]);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // Carregar contatos para vínculo
  useEffect(() => {
    if (isOpen) {
      identityService.getContacts().then(setContacts).catch(() => {});
    }
  }, [isOpen]);

  // Preencher formulário ao abrir para criação ou edição
  useEffect(() => {
    if (!isOpen) return;

    setModalError(null);
    if (customer) {
      setPersonType(customer.person_type || 'PJ');
      setName(customer.name || '');
      setTradeName(customer.trade_name || '');
      setDocument(customer.document || '');
      setStateRegistration(customer.state_registration || '');
      setEmail(customer.email || '');
      setPhone(customer.phone || '');
      setCreditLimit(String(customer.credit_limit ?? 50000.00));
      setAddressStreet(customer.address_street || '');
      setAddressNumber(customer.address_number || '');
      setAddressNeighborhood(customer.address_neighborhood || '');
      setAddressCity(customer.address_city || '');
      setAddressState(customer.address_state || 'SP');
      setAddressZipCode(customer.address_zip_code || '');
      setContactId(customer.contact_id || '');
      setNotes(customer.notes || '');
    } else {
      setPersonType(initialPersonType);
      setName('');
      setTradeName('');
      setDocument('');
      setStateRegistration('');
      setEmail('');
      setPhone('');
      setCreditLimit('50000.00');
      setAddressStreet('');
      setAddressNumber('');
      setAddressNeighborhood('');
      setAddressCity('');
      setAddressState('SP');
      setAddressZipCode('');
      setContactId('');
      setNotes('');
    }
  }, [isOpen, customer, initialPersonType]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setModalError('Informe a Razão Social ou Nome do cliente.');
      return;
    }
    if (!document.trim()) {
      setModalError(personType === 'PJ' ? 'Informe o CNPJ da empresa.' : 'Informe o CPF do cliente.');
      return;
    }

    setIsSaving(true);
    setModalError(null);

    const payload = {
      person_type: personType,
      name: name.trim(),
      trade_name: tradeName.trim() || undefined,
      document: document.trim(),
      state_registration: stateRegistration.trim() || undefined,
      email: email.trim() || undefined,
      phone: phone.trim() || undefined,
      credit_limit: parseFloat(creditLimit) || 0,
      address_street: addressStreet.trim() || undefined,
      address_number: addressNumber.trim() || undefined,
      address_neighborhood: addressNeighborhood.trim() || undefined,
      address_city: addressCity.trim() || undefined,
      address_state: addressState.trim() || undefined,
      address_zip_code: addressZipCode.trim() || undefined,
      contact_id: contactId.trim() || undefined,
      notes: notes.trim() || undefined,
      is_active: true
    };

    try {
      let saved: Customer;
      if (isEditing && customer?.id) {
        saved = await salesService.updateCustomer(customer.id, payload);
        toast.success(`Cliente '${saved.name}' atualizado com sucesso!`);
      } else {
        saved = await salesService.createCustomer(payload);
        toast.success(`Cliente '${saved.name}' cadastrado com sucesso!`);
      }

      if (onSuccess) {
        onSuccess(saved);
      }
      onClose();
    } catch (err: unknown) {
      const msg = formatApiError(err, 'Erro ao salvar dados do cliente.');
      setModalError(msg);
      toast.error(msg);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEditing ? 'Editar Cliente' : 'Cadastrar Novo Cliente'}
      subtitle={isEditing ? 'Atualize os dados cadastrais e de contato do cliente' : 'Cadastre um novo cliente (PJ ou PF) na base comercial'}
      size="lg"
    >
      <form onSubmit={handleSubmit} className="dedicated-customer-modal-form">
        {modalError && (
          <div className="form-error-callout" role="alert">
            <AlertTriangle size={16} />
            <span>{modalError}</span>
          </div>
        )}

        {/* 1. SEÇÃO DE IDENTIFICAÇÃO */}
        <div className="customer-modal-section">
          <div className="customer-modal-section__header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Building2 size={16} className="customer-modal-section__icon" />
              <h4 className="customer-modal-section__title">Identificação do Cliente / Parceiro</h4>
            </div>
            {isEditing && customer?.origin_module && (
              <span className="customer-origin-badge" style={{
                fontSize: '0.75rem',
                padding: '3px 8px',
                borderRadius: '4px',
                background: 'rgba(255, 107, 0, 0.15)',
                color: '#ff7700',
                border: '1px solid rgba(255, 107, 0, 0.3)',
                fontWeight: 600
              }}>
                Origem: {customer.origin_module === 'SALES' ? 'Módulo de Vendas' : customer.origin_module === 'CRM' ? 'Módulo CRM' : 'Identity'} (Cliente)
              </span>
            )}
          </div>

          <div className="customer-type-selector">
            <button
              type="button"
              className={`customer-type-btn ${personType === 'PJ' ? 'active' : ''}`}
              onClick={() => setPersonType('PJ')}
            >
              <Building2 size={15} /> Pessoa Jurídica (PJ)
            </button>
            <button
              type="button"
              className={`customer-type-btn ${personType === 'PF' ? 'active' : ''}`}
              onClick={() => setPersonType('PF')}
            >
              <UserRound size={15} /> Pessoa Física (PF)
            </button>
          </div>

          <div className="customer-form-grid-2">
            <div className="form-group">
              <label>{personType === 'PJ' ? 'Razão Social *' : 'Nome Completo *'}</label>
              <div className="input-with-icon-box">
                <Building2 size={15} className="input-prefix-icon" />
                <input
                  type="text"
                  required
                  placeholder={personType === 'PJ' ? 'Ex: Tech Solutions Brasil Ltda' : 'Ex: João da Silva Santos'}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="ui-input has-prefix-icon"
                />
              </div>
            </div>

            <div className="form-group">
              <label>{personType === 'PJ' ? 'Nome Fantasia' : 'Apelido / Como Chamar'}</label>
              <div className="input-with-icon-box">
                <FileText size={15} className="input-prefix-icon" />
                <input
                  type="text"
                  placeholder={personType === 'PJ' ? 'Ex: Tech Solutions' : 'Ex: João Santos'}
                  value={tradeName}
                  onChange={(e) => setTradeName(e.target.value)}
                  className="ui-input has-prefix-icon"
                />
              </div>
            </div>
          </div>

          <div className="customer-form-grid-2">
            <div className="form-group">
              <label>{personType === 'PJ' ? 'CNPJ *' : 'CPF *'}</label>
              <div className="input-with-icon-box">
                <Hash size={15} className="input-prefix-icon" />
                <input
                  type="text"
                  required
                  placeholder={personType === 'PJ' ? '00.000.000/0000-00' : '000.000.000-00'}
                  value={document}
                  onChange={(e) => setDocument(e.target.value)}
                  className="ui-input has-prefix-icon"
                />
              </div>
            </div>

            <div className="form-group">
              <label>{personType === 'PJ' ? 'Inscrição Estadual (IE)' : 'RG / Identidade'}</label>
              <div className="input-with-icon-box">
                <Landmark size={15} className="input-prefix-icon" />
                <input
                  type="text"
                  placeholder={personType === 'PJ' ? 'Isento ou nº estadual' : 'Nº do documento'}
                  value={stateRegistration}
                  onChange={(e) => setStateRegistration(e.target.value)}
                  className="ui-input has-prefix-icon"
                />
              </div>
            </div>
          </div>
        </div>

        {/* 2. SEÇÃO DE CONTATO */}
        <div className="customer-modal-section">
          <div className="customer-modal-section__header">
            <Phone size={16} className="customer-modal-section__icon" />
            <h4 className="customer-modal-section__title">Contato Comercial & Representante</h4>
          </div>

          <div className="customer-form-grid-3">
            <div className="form-group">
              <label>E-mail Comercial</label>
              <div className="input-with-icon-box">
                <Mail size={15} className="input-prefix-icon" />
                <input
                  type="email"
                  placeholder="comercial@empresa.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="ui-input has-prefix-icon"
                />
              </div>
            </div>

            <div className="form-group">
              <label>Telefone / WhatsApp</label>
              <div className="input-with-icon-box">
                <Phone size={15} className="input-prefix-icon" />
                <input
                  type="text"
                  placeholder="(11) 99999-9999"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="ui-input has-prefix-icon"
                />
              </div>
            </div>

            <div className="form-group">
              <label>Contato Identity Vinculado</label>
              <select
                value={contactId}
                onChange={(e) => setContactId(e.target.value)}
                className="ui-input"
              >
                <option value="">Nenhum contato vinculado</option>
                {contacts.map((ct) => (
                  <option key={ct.id} value={ct.id}>
                    {ct.full_name} {ct.email ? `(${ct.email})` : ''}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* 3. SEÇÃO DE ENDEREÇO */}
        <div className="customer-modal-section">
          <div className="customer-modal-section__header">
            <MapPin size={16} className="customer-modal-section__icon" />
            <h4 className="customer-modal-section__title">Endereço & Praça de Atendimento</h4>
          </div>

          <div className="customer-form-grid-2">
            <div className="form-group" style={{ gridColumn: 'span 1' }}>
              <label>CEP</label>
              <input
                type="text"
                placeholder="00000-000"
                value={addressZipCode}
                onChange={(e) => setAddressZipCode(e.target.value)}
                className="ui-input"
              />
            </div>
            <div className="form-group" style={{ gridColumn: 'span 1' }}>
              <label>Logradouro / Rua</label>
              <input
                type="text"
                placeholder="Ex: Av. Paulista"
                value={addressStreet}
                onChange={(e) => setAddressStreet(e.target.value)}
                className="ui-input"
              />
            </div>
          </div>

          <div className="customer-form-grid-3">
            <div className="form-group">
              <label>Número / Complemento</label>
              <input
                type="text"
                placeholder="Ex: 1000, Bloco A"
                value={addressNumber}
                onChange={(e) => setAddressNumber(e.target.value)}
                className="ui-input"
              />
            </div>
            <div className="form-group">
              <label>Bairro</label>
              <input
                type="text"
                placeholder="Ex: Bela Vista"
                value={addressNeighborhood}
                onChange={(e) => setAddressNeighborhood(e.target.value)}
                className="ui-input"
              />
            </div>
            <div className="form-group">
              <label>Cidade / UF</label>
              <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '0.5rem' }}>
                <input
                  type="text"
                  placeholder="Cidade"
                  value={addressCity}
                  onChange={(e) => setAddressCity(e.target.value)}
                  className="ui-input"
                />
                <input
                  type="text"
                  maxLength={2}
                  placeholder="UF"
                  value={addressState}
                  onChange={(e) => setAddressState(e.target.value.toUpperCase())}
                  className="ui-input"
                  style={{ textAlign: 'center' }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* 4. SEÇÃO FINANCEIRA & OBSERVAÇÕES */}
        <div className="customer-modal-section">
          <div className="customer-modal-section__header">
            <CreditCard size={16} className="customer-modal-section__icon" />
            <h4 className="customer-modal-section__title">Crédito & Observações Comerciais</h4>
          </div>

          <div className="customer-form-grid-2">
            <div className="form-group">
              <label>Limite de Crédito Concedido (R$)</label>
              <input
                type="number"
                step="0.01"
                min="0"
                placeholder="50000.00"
                value={creditLimit}
                onChange={(e) => setCreditLimit(e.target.value)}
                className="ui-input"
              />
            </div>
            <div className="form-group">
              <label>Observações Internas</label>
              <input
                type="text"
                placeholder="Preferências, restrições ou termos especiais"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="ui-input"
              />
            </div>
          </div>
        </div>

        <div className="modal-footer">
          <button
            type="button"
            className="btn-cancel"
            onClick={onClose}
            disabled={isSaving}
          >
            Cancelar
          </button>
          <button
            type="submit"
            className="btn-save"
            disabled={isSaving}
          >
            {isSaving ? (
              <span>Salvando...</span>
            ) : (
              <>
                <Check size={16} />
                <span>{isEditing ? 'Salvar Alterações' : 'Cadastrar Cliente'}</span>
              </>
            )}
          </button>
        </div>
      </form>
    </Modal>
  );
};
