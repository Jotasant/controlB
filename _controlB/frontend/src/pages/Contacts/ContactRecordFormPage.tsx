import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { CalendarDays, Link2, MessageCircle, Save, Users, Wifi } from 'lucide-react';
import { useChatUi } from '@/components/ChatWidget/ChatContext';
import { usePermissions } from '@/hooks/usePermissions';
import { RecordFormGrid, RecordFormPage, RecordFormSection, UnsavedChangesGuard } from '@/components/RecordForm';
import { useToast } from '@/components/Toast/ToastContext';
import { useRecordFormNavigation } from '@/hooks/useRecordFormNavigation';
import { isNewRecordSegment } from '@/routing/recordRoutes';
import { formatApiError, identityService } from '@/services/api';
import type { ContactDirectoryEntry } from '@/types';
import '../Cadastros/records/IdentityRecordForm.scss';
import './Contacts.scss';

const EMPTY = { name: '', person_type: 'PF' as 'PF' | 'PJ', document: '', email: '', phone: '', notes: '', is_active: true };

export function ContactRecordFormPage() {
  const { recordId } = useParams<{ recordId: string }>();
  const isNew = isNewRecordSegment(recordId);
  const navigate = useNavigate();
  const goBack = useRecordFormNavigation('/contatos');
  const toast = useToast();
  const chat = useChatUi();
  const { hasPermission } = usePermissions();
  const canStartChat = chat.canAccess && hasPermission('chat:send');
  const [record, setRecord] = useState<ContactDirectoryEntry | null>(null);
  const [form, setForm] = useState(EMPTY);
  const [initial, setInitial] = useState(JSON.stringify(EMPTY));
  const [tab, setTab] = useState('dados');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const dirty = !loading && JSON.stringify(form) !== initial;

  useEffect(() => {
    let active = true;
    setLoading(true); setError(null);
    const load = async () => {
      try {
        const result = isNew || !recordId ? null : (await identityService.getContactDirectory({ contact_id: recordId })).items[0];
        if (!active) return;
        if (!isNew && !result) throw new Error('Contato não encontrado na sua organização.');
        const next = result ? { name: result.name || '', person_type: result.person_type || 'PF', document: result.document || '', email: result.email || '', phone: result.phone || result.mobile || '', notes: result.notes || '', is_active: result.is_active } : EMPTY;
        setRecord(result || null); setForm(next); setInitial(JSON.stringify(next));
      } catch (err) { if (active) setError(formatApiError(err, 'Não foi possível carregar o contato.')); }
      finally { if (active) setLoading(false); }
    };
    void load();
    return () => { active = false; };
  }, [isNew, recordId, refresh]);

  const save = async (startChat = false) => {
    if (saving || !form.name.trim()) { if (!form.name.trim()) toast.error('Informe o nome do contato.'); return; }
    setSaving(true);
    try {
      const { phone, ...fields } = form;
      const payload = { ...fields, name: form.name.trim(), email: form.email.trim(), document: form.document.trim(),
        ...(record?.first_contact_at ? {} : { phone: phone.trim() }), notes: form.notes };
      const saved = isNew || !recordId ? await identityService.createContact(payload) : await identityService.updateContact(recordId, payload);
      setInitial(JSON.stringify(form)); toast.success('Contato salvo.');
      if (isNew) navigate(`/contatos/${saved.id}`, { replace: true }); else setRefresh((value) => value + 1);
      if (startChat) chat.startConversation(saved.id);
    } catch (err) { toast.error(formatApiError(err, 'Não foi possível salvar o contato.')); }
    finally { setSaving(false); }
  };

  return <div className="identity-record-page contacts-page">
    <RecordFormPage title={isNew ? 'Novo contato' : record?.name || 'Contato'} eyebrow="IDENTITY" icon={Users}
      breadcrumbs={[{ label: 'Contatos', to: '/contatos' }, { label: isNew ? 'Novo' : record?.name || 'Registro' }]}
      description="Cadastro único da organização. Clientes e fornecedores permanecem registros independentes."
      tabs={[{ id: 'dados', label: 'Dados do contato', icon: Users }, { id: 'vinculos', label: 'Origens e vínculos', icon: Link2, disabled: isNew }]}
      activeTab={tab} onTabChange={setTab} onBack={goBack} isLoading={loading} error={error} onRetry={() => setRefresh((value) => value + 1)}
      footer={<><span>{dirty ? 'Alterações não salvas' : 'Registro atualizado'}</span><button type="button" className="ui-button ui-button--secondary" onClick={goBack} disabled={saving}>Voltar</button>
        {canStartChat && <button type="button" className="ui-button ui-button--secondary" disabled={saving || Boolean(error) || loading}
          onClick={() => { if (dirty || isNew) void save(true); else if (recordId) chat.startConversation(recordId); }}><MessageCircle size={15} /> {dirty || isNew ? 'Salvar e conversar' : 'Conversar no WhatsApp'}</button>}
        <button type="button" className="ui-button ui-button--primary" onClick={() => void save()} disabled={saving || !dirty || Boolean(error)}><Save size={15} /> {saving ? 'Salvando...' : 'Salvar'}</button></>}>
      {tab === 'dados' && <RecordFormSection title="Identificação" icon={Users}><div className="ui-form"><RecordFormGrid columns={2}>
        <div className="form-group"><label>Nome *</label><input value={form.name} disabled={saving} onChange={(event) => setForm({ ...form, name: event.target.value })} /></div>
        <div className="form-group"><label>Tipo</label><select value={form.person_type} disabled={saving} onChange={(event) => setForm({ ...form, person_type: event.target.value as 'PF' | 'PJ' })}><option value="PF">Pessoa física</option><option value="PJ">Pessoa jurídica</option></select></div>
        <div className="form-group"><label>CPF / CNPJ</label><input value={form.document} disabled={saving} onChange={(event) => setForm({ ...form, document: event.target.value })} /></div>
        <div className="form-group"><label>E-mail</label><input type="email" value={form.email} disabled={saving} onChange={(event) => setForm({ ...form, email: event.target.value })} /></div>
        <div className="form-group"><label>Telefone</label><input value={form.phone} disabled={saving || Boolean(record?.first_contact_at)} onChange={(event) => setForm({ ...form, phone: event.target.value })} />{record?.first_contact_at && <small>Telefone vinculado ao WhatsApp. Outro número deve ter outro contato.</small>}</div>
        <label className="record-form-checkbox"><input type="checkbox" checked={form.is_active} disabled={saving} onChange={(event) => setForm({ ...form, is_active: event.target.checked })} /> Contato ativo</label>
        <div className="form-group is-full-width"><label>Observações</label><textarea rows={4} value={form.notes} disabled={saving} onChange={(event) => setForm({ ...form, notes: event.target.value })} /></div>
      </RecordFormGrid></div></RecordFormSection>}
      {tab === 'vinculos' && record && <div className="contact-links-layout">
        <RecordFormSection title="Origem do relacionamento" icon={Link2} description="Aquisição comercial e fonte do cadastro são informações distintas.">
          <dl className="contact-facts">
            <div><dt>Canal de aquisição</dt><dd>{record.origin_name || 'Não informado'}</dd></div>
            <div><dt>Cadastro de origem</dt><dd><span className="contact-tag">{record.origin_module === 'CHAT' ? 'WhatsApp' : record.origin_module || 'Identity'}</span></dd></div>
          </dl>
        </RecordFormSection>
        <RecordFormSection title="Histórico de contato" icon={CalendarDays}>
          <dl className="contact-facts">
            <div><dt>Primeiro contato</dt><dd>{record.first_contact_at ? new Date(record.first_contact_at).toLocaleString('pt-BR') : 'Ainda não registrado'}</dd></div>
            <div><dt>Último contato</dt><dd>{record.last_contact_at ? new Date(record.last_contact_at).toLocaleString('pt-BR') : 'Ainda não registrado'}</dd></div>
          </dl>
        </RecordFormSection>
        <RecordFormSection title="Vínculos comerciais" icon={Users} description="Clientes e fornecedores mantêm cadastros independentes.">
          <dl className="contact-facts">
            <div><dt>Clientes</dt><dd>{record.customers.length ? record.customers.map((item) => <span className="contact-tag" key={item.id}>{item.name}</span>) : <span className="contact-empty">Nenhum cliente vinculado</span>}</dd></div>
            <div><dt>Fornecedores</dt><dd>{record.suppliers.length ? record.suppliers.map((item) => <span className="contact-tag" key={item.id}>{item.name}</span>) : <span className="contact-empty">Nenhum fornecedor vinculado</span>}</dd></div>
          </dl>
        </RecordFormSection>
        <RecordFormSection title="Canais de atendimento" icon={Wifi} description="Somente instâncias às quais você tem acesso.">
          {record.channels.length ? <ul className="contact-channel-list">{record.channels.map((channel) => <li key={channel.id}>
            <span className="contact-channel-icon"><MessageCircle size={18} /></span>
            <div><strong>{channel.name}</strong><span>{channel.instance_phone ? `+${channel.instance_phone}` : 'Número não confirmado'}</span></div>
          </li>)}</ul> : <p className="contact-empty">Nenhuma instância vinculada acessível ao seu usuário.</p>}
        </RecordFormSection>
      </div>}
    </RecordFormPage><UnsavedChangesGuard when={dirty && !saving} />
  </div>;
}
