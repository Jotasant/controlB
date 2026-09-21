import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { Link2, QrCode, Save, Settings, Users, Wifi } from 'lucide-react';
import { InstanceTeamEditor } from './InstanceTeamEditor';

import { RecordFormGrid, RecordFormPage, RecordFormSection, UnsavedChangesGuard } from '@/components/RecordForm';
import { useToast } from '@/components/Toast/ToastContext';
import { usePermissions } from '@/hooks/usePermissions';
import { useRecordFormNavigation } from '@/hooks/useRecordFormNavigation';
import { useRecordFormTab } from '@/hooks/useRecordFormTab';
import { buildRecordFormPath, isNewRecordSegment } from '@/routing/recordRoutes';
import { chatService, formatApiError } from '@/services/api';
import type { ChatConnection, ChatConnectionStatus, ChatProvider, ChatInstanceDetails, ChatHistoryResult } from '@/types/chat';

import '../../pages/Projects/records/OperationalRecordForm.scss';
import './ChatConnectionForm.scss';

type TabId = 'configuracao' | 'equipe' | 'conexao';
const TABS: TabId[] = ['configuracao', 'equipe', 'conexao'];

interface FormState {
  transcription_enabled: boolean;
  groups_enabled: boolean;
  member_ids: string[];
  name: string;
  provider: string;
  base_url: string;
  external_instance_id: string;
  api_key: string;
  is_active: boolean;
}

const EMPTY_FORM: FormState = {
  transcription_enabled: false,
  groups_enabled: true,
  member_ids: [],
  name: '',
  provider: 'EVOLUTION',
  base_url: '',
  external_instance_id: '',
  api_key: '',
  is_active: true,
};

const STATUS_LABEL: Record<ChatConnectionStatus, string> = {
  CONNECTED: 'Conectada',
  CONNECTING: 'Pareando',
  DISCONNECTED: 'Desconectada',
  ERROR: 'Erro',
};

function serialize(form: FormState) {
  return JSON.stringify({ ...form, api_key: form.api_key ? '***' : '' });
}

function slugFromName(name: string) {
  const slug = name
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 200);
  return slug || 'whatsapp';
}

export function ChatConnectionFormPage() {
  const { recordId } = useParams<{ recordId: string }>();
  const isNew = isNewRecordSegment(recordId);
  const location = useLocation();
  const navigate = useNavigate();
  const goBack = useRecordFormNavigation('/chat/conexoes');
  const toast = useToast();
  const { user, hasPermission, loading: permissionsLoading } = usePermissions();
  const canManage = hasPermission('chat:manage_connectors');
  const [activeTab, setActiveTab] = useRecordFormTab(TABS, 'configuracao');

  const [record, setRecord] = useState<ChatConnection | null>(null);
  const [providers, setProviders] = useState<ChatProvider[]>([]);
  const [eligibleUsers, setEligibleUsers] = useState<{ id: string; full_name: string }[]>([]);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [initialForm, setInitialForm] = useState(serialize(EMPTY_FORM));
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [qrCode, setQrCode] = useState<string | null>(null);
  const [pairingCode, setPairingCode] = useState<string | null>(null);
  const [webhookUrl, setWebhookUrl] = useState<string | null>(null);
  const [details, setDetails] = useState<ChatInstanceDetails | null>(null);
  const [detailsError, setDetailsError] = useState<string | null>(null);
  const [history, setHistory] = useState<ChatHistoryResult | null>(null);
  const [audioRuntime, setAudioRuntime] = useState<{ configured: boolean; worker_enabled: boolean } | null>(null);

  const refreshDetails = useCallback(async () => {
    if (!recordId || isNew) return;
    try {
      setDetails(await chatService.getInstanceDetails(recordId));
      setDetailsError(null);
    } catch (err) {
      setDetailsError(formatApiError(err, 'Não foi possível consultar os dados da instância.'));
    }
  }, [isNew, recordId]);

  useEffect(() => {
    setDetails(null);
    setHistory(null);
    setDetailsError(null);
  }, [recordId]);

  useEffect(() => {
    if (canManage && record?.is_active && activeTab === 'conexao') void refreshDetails();
  }, [canManage, record?.is_active, activeTab, refreshDetails]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const available = await chatService.getProviders().catch(() => [{ code: 'EVOLUTION', name: 'Evolution API' }]);
      setProviders(available);
      setEligibleUsers(await chatService.getEligibleUsers());
      setAudioRuntime(await chatService.getAudioRuntime().catch(() => null));
      const connection = isNew || !recordId ? null : await chatService.getConnection(recordId);
      const next: FormState = connection
        ? {
            member_ids: connection.member_ids,
            transcription_enabled: connection.transcription_enabled,
            groups_enabled: connection.groups_enabled,
            name: connection.name,
            provider: connection.provider,
            base_url: connection.base_url,
            external_instance_id: connection.external_instance_id,
            api_key: '',
            is_active: connection.is_active,
          }
        : { ...EMPTY_FORM, member_ids: user ? [user.id] : [], provider: available[0]?.code || 'EVOLUTION' };
      setRecord(connection);
      setForm(next);
      setInitialForm(serialize(next));
      setQrCode(null);
      setPairingCode(null);
    } catch (loadError) {
      setError(formatApiError(loadError, 'Não foi possível carregar a conexão.'));
    } finally {
      setLoading(false);
    }
  }, [isNew, recordId, user]);

  useEffect(() => {
    if (!permissionsLoading && canManage) void load();
  }, [load, permissionsLoading, canManage]);

  const dirty = !loading && serialize(form) !== initialForm;
  const title = isNew ? 'Nova conexão' : record?.name || 'Conexão';
  const status = (record?.status || 'DISCONNECTED') as ChatConnectionStatus;

  const save = async () => {
    if (saving || busyAction || !canManage) return;
    if (!form.member_ids.length || !user || !form.member_ids.includes(user.id)) {
      toast.error('Selecione os participantes da instância, incluindo seu usuário.');
      return;
    }
    if (!form.name.trim() || form.name.trim().length < 2) {
      toast.error('Informe o nome da conexão.');
      return;
    }
    if (!form.base_url.trim()) {
      toast.error('Informe a URL do servidor.');
      return;
    }
    if (!form.external_instance_id.trim()) {
      toast.error('Informe o identificador da instância.');
      return;
    }
    if ((isNew || form.api_key) && form.api_key.trim().length < 16) {
      toast.error('A credencial deve ter pelo menos 16 caracteres.');
      return;
    }
    setSaving(true);
    try {
      const payload = {
        member_ids: form.member_ids,
        transcription_enabled: form.transcription_enabled,
        groups_enabled: form.groups_enabled,
        name: form.name.trim(),
        ...(isNew ? { provider: form.provider } : {}),
        base_url: form.base_url.trim(),
        external_instance_id: form.external_instance_id.trim(),
        is_active: form.is_active,
        ...(form.api_key.trim() ? { api_key: form.api_key.trim() } : {}),
      };
      const saved = isNew || !recordId
        ? await chatService.createConnection(payload as import('@/types/chat').ChatConnectionCreatePayload)
        : await chatService.updateConnection(recordId, payload);
      const next: FormState = {
        member_ids: saved.member_ids,
        transcription_enabled: saved.transcription_enabled,
        groups_enabled: saved.groups_enabled,
        name: saved.name,
        provider: saved.provider,
        base_url: saved.base_url,
        external_instance_id: saved.external_instance_id,
        api_key: '',
        is_active: saved.is_active,
      };
      setRecord(saved);
      setForm(next);
      setInitialForm(serialize(next));
      toast.success(isNew ? 'Conexão cadastrada. Crie a instância na aba Conexão.' : 'Conexão atualizada.');
      if (isNew) {
        navigate(`${buildRecordFormPath('chat', 'conexoes', saved.id)}?tab=conexao`, {
          replace: true,
          state: location.state,
        });
      }
    } catch (saveError) {
      toast.error(formatApiError(saveError, 'Não foi possível salvar a conexão.'));
    } finally {
      setSaving(false);
    }
  };

  const runAction = async (action: string, runner: () => Promise<void>) => {
    if (!recordId || isNew || busyAction || saving || !canManage || !record?.is_active) return;
    if (dirty) {
      toast.warning('Salve as alterações na aba Configuração antes de executar ações.');
      return;
    }
    setBusyAction(action);
    try {
      await runner();
    } catch (actionError) {
      toast.error(formatApiError(actionError, 'Não foi possível concluir a operação.'));
    } finally {
      setBusyAction(null);
    }
  };

  const createInstance = () =>
    runAction('instance', async () => {
      const result = await chatService.provisionInstance(recordId!);
      setRecord(result.connection);
      setQrCode(result.qr_code_base64);
      setPairingCode(result.pairing_code);
      toast.success(
        result.already_existed
          ? 'A instância já existia no servidor. Siga para o pareamento.'
          : 'Instância criada no provedor.',
      );
    });

  const connectWhatsApp = () =>
    runAction('pairing', async () => {
      const result = await chatService.getPairing(recordId!);
      setRecord(result.connection);
      setQrCode(result.qr_code_base64);
      setPairingCode(result.pairing_code);
      if (result.state === 'CONNECTED') {
        toast.success('WhatsApp já está pareado.');
      } else if (!result.qr_code_base64 && !result.pairing_code) {
        toast.warning('O provedor não devolveu o QR Code. Atualize o status e tente novamente.');
      }
    });

  const refreshStatus = () =>
    runAction('check', async () => {
      const connection = await chatService.checkConnection(recordId!);
      setRecord(connection);
      await refreshDetails();
      if (connection.status === 'CONNECTED') {
        setQrCode(null);
        toast.success('Canal conectado.');
      }
    });

  const configureWebhook = () =>
    runAction('webhook', async () => {
      const result = await chatService.configureWebhook(recordId!);
      setWebhookUrl(result.url);
      toast.success('Webhook configurado no provedor.');
    });

  const syncHistory = (more = false) => runAction('sync', async () => {
    const result = await chatService.syncHistory(recordId!, more ? history?.next_page || 1 : 1,
      more ? history?.snapshot_at : undefined);
    setHistory(result);
    await refreshDetails();
    window.dispatchEvent(new Event('controlb:chat-refresh'));
    toast.success(`${result.imported} mensagens importadas; ${result.existing} já existentes; ${result.skipped} fora do escopo.`);
  });

  useEffect(() => {
    if (!canManage || !record?.is_active || busyAction || dirty || !recordId || isNew ||
        status === 'CONNECTED' || activeTab !== 'conexao' || (!qrCode && !pairingCode)) return;
    let cancelled = false;
    let timer: number;
    const poll = async () => {
      try {
        const connection = await chatService.checkConnection(recordId);
        if (cancelled) return;
        setRecord(connection);
        if (connection.status === 'CONNECTED') {
          setQrCode(null);
          setPairingCode(null);
          return;
        }
      } catch { /* a atualização manual informa erros ao operador */ }
      if (!cancelled) timer = window.setTimeout(() => void poll(), 5000);
    };
    timer = window.setTimeout(() => void poll(), 5000);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [activeTab, isNew, recordId, status, canManage, record?.is_active, busyAction, dirty, qrCode, pairingCode]);

  const tabs = useMemo(
    () => [
      { id: 'configuracao', label: 'Configuração', icon: Settings },
      { id: 'equipe', label: 'Equipe', icon: Users },
      { id: 'conexao', label: 'Conexão', icon: QrCode, disabled: isNew },
    ],
    [isNew],
  );

  if (permissionsLoading) return <p role="status">Carregando permissões...</p>;
  if (!canManage) return <p role="alert">Sem permissão para gerenciar conexões do Chat.</p>;

  const actionsDisabled = Boolean(busyAction) || saving || dirty || !record?.is_active;

  return (
    <div className="chat-connection-form operational-record-form">
      <RecordFormPage
        title={title}
        eyebrow="Chat"
        description="Cadastre o servidor e a credencial, crie a instância e pareie o WhatsApp neste formulário."
        icon={Wifi}
        status={<span className={`record-status-pill is-${status.toLowerCase()}`}>{STATUS_LABEL[status]}</span>}
        breadcrumbs={[
          { label: 'Conexões', to: '/chat/conexoes' },
          { label: isNew ? 'Nova' : title },
        ]}
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={(tabId) => setActiveTab(tabId as TabId)}
        onBack={goBack}
        isLoading={loading}
        error={error}
        onRetry={() => void load()}
        footer={
          activeTab !== 'conexao' ? (
            <>
              <span className={`record-form-footer-message${dirty ? ' is-dirty' : ''}`}>
                {dirty ? 'Existem alterações não salvas.' : 'Todas as alterações estão salvas.'}
              </span>
              <button type="button" className="ui-button ui-button--secondary" onClick={goBack} disabled={saving}>
                Cancelar
              </button>
              <button
                type="button"
                className="ui-button ui-button--primary"
                onClick={() => void save()}
                disabled={saving || !dirty || !canManage}
              >
                <Save size={16} /> {saving ? 'Salvando...' : 'Salvar'}
              </button>
            </>
          ) : undefined
        }
      >
        {activeTab === 'configuracao' && (
          <RecordFormSection
            title="Dados do canal"
            description="Nome de exibição, servidor Evolution e credencial. A instância será criada na aba Conexão."
            icon={Settings}
          >
            <div className="ui-form">
              <RecordFormGrid columns={2}>
                <div className="form-group">
                  <label>Nome *</label>
                  <input
                    value={form.name}
                    onChange={(event) => setForm({ ...form, name: event.target.value })}
                    onBlur={() => {
                      if (isNew && form.name.trim() && !form.external_instance_id) {
                        setForm((current) => ({ ...current, external_instance_id: slugFromName(current.name) }));
                      }
                    }}
                    disabled={!canManage}
                    placeholder="Ex.: WhatsApp Comercial"
                  />
                </div>
                <div className="form-group">
                  <label>Provedor</label>
                  <select
                    value={form.provider}
                    onChange={(event) => setForm({ ...form, provider: event.target.value })}
                    disabled={!canManage || !isNew}
                  >
                    {(providers.length ? providers : [{ code: 'EVOLUTION', name: 'Evolution API' }]).map((provider) => (
                      <option key={provider.code} value={provider.code}>
                        {provider.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-group is-full-width">
                  <label>Servidor *</label>
                  <input
                    value={form.base_url}
                    onChange={(event) => setForm({ ...form, base_url: event.target.value })}
                    disabled={!canManage}
                    placeholder="https://evolution.suaempresa.com"
                  />
                  <span className="field-help">A URL precisa estar em CHAT_ALLOWED_BASE_URLS no servidor ControlB.</span>
                </div>
                <div className="form-group">
                  <label>Identificador da instância *</label>
                  <input
                    value={form.external_instance_id}
                    onChange={(event) => setForm({ ...form, external_instance_id: event.target.value })}
                    disabled={!canManage}
                    placeholder="whatsapp-comercial"
                  />
                  {record?.instance_phone && (
                    <span className="field-help">
                      Número vinculado: +{record.instance_phone}. Para substituir a instância técnica e manter os chats,
                      informe aqui uma instância já pareada com esse mesmo número. O webhook será atualizado ao salvar.
                    </span>
                  )}
                </div>
                <div className="form-group">
                  <label>{isNew ? 'Credencial (API key) *' : 'Nova credencial'}</label>
                  <input
                    type="password"
                    value={form.api_key}
                    onChange={(event) => setForm({ ...form, api_key: event.target.value })}
                    disabled={!canManage}
                    placeholder={isNew ? 'Chave da Evolution API' : 'Deixe em branco para manter'}
                    autoComplete="new-password"
                  />
                  <span className="field-help">Mínimo de 16 caracteres. O valor nunca é exibido depois de salvo.</span>
                </div>
                  <label className="record-form-checkbox is-full-width">
                    <input type="checkbox" checked={form.groups_enabled} disabled={!canManage || saving || Boolean(busyAction)}
                      onChange={(event) => setForm({ ...form, groups_enabled: event.target.checked })} />
                    Receber e responder mensagens de grupos
                  </label>
                  <span className="field-help">Salve e aplique no provedor. Os grupos ficam separados dos contatos; cada mensagem identifica seu remetente.</span>
                  {!isNew && <button type="button" className="ui-button ui-button--secondary" disabled={!canManage || saving || Boolean(busyAction) || dirty}
                    onClick={() => void runAction('groups', async () => {
                      const result = await chatService.configureGroups(recordId!);
                      window.dispatchEvent(new Event('controlb:chat-refresh'));
                      toast.success(result.groups_enabled ? `${result.synced} grupos sincronizados. Recebimento habilitado.` : 'Recebimento de grupos desabilitado no provedor. Histórico preservado.');
                    })}>{busyAction === 'groups' ? 'Aplicando…' : 'Aplicar configuração e sincronizar grupos'}</button>}
                  <label className="record-form-checkbox is-full-width">
                    <input type="checkbox" checked={form.transcription_enabled}
                      disabled={!canManage || saving || Boolean(busyAction)}
                      onChange={(event) => setForm({ ...form, transcription_enabled: event.target.checked })} />
                    Transcrever áudios automaticamente (processamento local)
                  </label>
                  <span className="field-help">{audioRuntime?.configured && audioRuntime.worker_enabled
                    ? 'Motor local disponível. Novos áudios desta instância serão transcritos em segundo plano.'
                    : 'Motor local indisponível. Instale o pacote speech, configure CHAT_STT_MODEL_PATH e habilite o worker no servidor. A opção pode ser salva, mas os áudios ainda não serão transcritos.'}</span>
                {!isNew && (
                  <label className="record-form-checkbox is-full-width">
                    <input
                      type="checkbox"
                      checked={form.is_active}
                      onChange={(event) => setForm({ ...form, is_active: event.target.checked })}
                      disabled={!canManage}
                    />
                    Conexão ativa
                  </label>
                )}
              </RecordFormGrid>
            </div>
          </RecordFormSection>
        )}

        {activeTab === 'equipe' && <RecordFormSection title="Equipe da instância" icon={Users} description="Grupo próprio, independente das equipes de Vendas.">
          <InstanceTeamEditor users={eligibleUsers} memberIds={form.member_ids} currentUserId={user?.id}
            disabled={!canManage || saving || Boolean(busyAction)} onChange={(member_ids) => setForm((value) => ({ ...value, member_ids }))} />
        </RecordFormSection>}
        {activeTab === 'conexao' && record && (
          <RecordFormSection
            title="Pareamento WhatsApp"
            description="Crie a instância no servidor, leia o QR Code neste formulário e acompanhe o status."
            icon={QrCode}
          >
            <div className="chat-pairing">
              {detailsError && <p role="alert">{detailsError}</p>}
              {details && (
                <dl className="chat-instance-details">
                  <div><dt>Telefone conectado</dt><dd>{details.phone ? `+${details.phone}` : 'Não informado pelo provedor'}</dd></div>
                  <div><dt>Nome do perfil</dt><dd>{details.profile_name || 'Não informado pelo provedor'}</dd></div>
                  <div><dt>ID na Evolution</dt><dd>{details.instance_id || 'Não informado'}</dd></div>
                  <div><dt>Instância / integração</dt><dd>{details.instance_name} · {details.integration || record.provider}</dd></div>
                  <div><dt>Histórico na Evolution</dt><dd>{details.message_count?.toLocaleString('pt-BR') ?? '—'} mensagens · {details.chat_count?.toLocaleString('pt-BR') ?? '—'} conversas</dd></div>
                  <div><dt>Importado no ControlB</dt><dd>{details.local_message_count.toLocaleString('pt-BR')} mensagens · {details.local_conversation_count.toLocaleString('pt-BR')} conversas</dd></div>
                  <div><dt>Último webhook recebido</dt><dd>{details.last_webhook_at ? new Date(details.last_webhook_at).toLocaleString('pt-BR') : 'Nenhum evento recebido'}</dd></div>
                </dl>
              )}
              {record.last_error && <div className="record-form-notice">{record.last_error}</div>}
              {dirty && <p role="status">Salve as alterações na aba Configuração para executar ações.</p>}
              {!record.is_active && <p role="status">Reative e salve a conexão para iniciar o pareamento.</p>}
              <div className="chat-pairing__actions">
                <button
                  type="button"
                  className="ui-button ui-button--primary"
                  onClick={() => void createInstance()}
                  disabled={actionsDisabled || status === 'CONNECTED'}
                >
                  <Wifi size={16} /> {busyAction === 'instance' ? 'Criando...' : 'Criar instância'}
                </button>
                <button
                  type="button"
                  className="ui-button ui-button--secondary"
                  onClick={() => void connectWhatsApp()}
                  disabled={actionsDisabled || status === 'CONNECTED'}
                >
                  <QrCode size={16} /> {busyAction === 'pairing' ? 'Gerando QR...' : 'Conectar WhatsApp'}
                </button>
                <button
                  type="button"
                  className="ui-button ui-button--secondary"
                  onClick={() => void refreshStatus()}
                  disabled={actionsDisabled}
                >
                  {busyAction === 'check' ? 'Consultando...' : 'Atualizar status'}
                </button>
                <button
                  type="button"
                  className="ui-button ui-button--secondary"
                  onClick={() => void configureWebhook()}
                  disabled={actionsDisabled || status !== 'CONNECTED'}
                >
                  <Link2 size={16} /> {busyAction === 'webhook' ? 'Configurando...' : 'Configurar webhook'}
                </button>
              </div>

              <div className="chat-history-sync">
                <strong>Sincronização do histórico</strong>
                <p>Importe até 100 registros por vez, começando pelos mais recentes. Não envia mensagens nem marca o histórico como não lido. Conversas sem documento ficam na triagem.</p>
                <div className="chat-pairing__actions">
                  <button type="button" className="ui-button ui-button--secondary"
                    disabled={actionsDisabled || status !== 'CONNECTED' || !hasPermission('chat:link') || !hasPermission('chat:view')}
                    onClick={() => void syncHistory()}>{busyAction === 'sync' ? 'Sincronizando...' : 'Sincronizar recentes'}</button>
                  {history?.next_page && <button type="button" className="ui-button ui-button--secondary"
                    disabled={actionsDisabled || status !== 'CONNECTED'} onClick={() => void syncHistory(true)}>Importar próximo lote</button>}
                </div>
                {history && <p role="status">Último lote: {history.scanned} examinadas, {history.imported} novas, {history.existing} já existentes, {history.skipped} ignoradas (grupos ou contatos sem telefone resolvido). {history.next_page ? 'Há mais histórico disponível.' : 'Fim do histórico disponível nesta consulta.'}</p>}
              </div>

              <div className="chat-pairing__stage">
                {status === 'CONNECTED' ? (
                  <div className="chat-pairing__connected">
                    <strong>WhatsApp conectado</strong>
                    <span>O canal {record.external_instance_id} está pareado. Configure o webhook para receber mensagens.</span>
                    {webhookUrl && <code>{webhookUrl}</code>}
                  </div>
                ) : qrCode || pairingCode ? (
                  <div className="chat-pairing__qr">
                    {qrCode && <img src={qrCode} alt="QR Code para parear o WhatsApp" />}
                    <p>Abra o WhatsApp no celular e toque em Aparelhos conectados. Se o QR Code expirar, clique em Conectar WhatsApp para gerar outro.</p>
                    {pairingCode && (
                      <p className="chat-pairing__code">
                        Código de pareamento: <strong>{pairingCode}</strong>
                      </p>
                    )}
                  </div>
                ) : (
                  <div className="chat-pairing__empty">
                    Salve a configuração, crie a instância e depois gere o QR Code para conectar o WhatsApp.
                  </div>
                )}
              </div>
            </div>
          </RecordFormSection>
        )}
      </RecordFormPage>
      <UnsavedChangesGuard when={dirty && !saving} />
    </div>
  );
}

export default ChatConnectionFormPage;
