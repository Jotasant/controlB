import React, { useCallback, useEffect, useState } from 'react';
import {
  BadgePercent,
  CalendarDays,
  CreditCard,
  RefreshCw,
  Save,
  ShieldAlert,
  SlidersHorizontal,
} from 'lucide-react';

import { usePermissions } from '@/hooks/usePermissions';
import { formatApiError, salesService } from '@/services/api';
import type { CommercialSettings } from '@/types';
import { useToast } from '@/components/Toast/ToastContext';

import './CommercialPoliciesSettings.scss';

const MANAGE_PERMISSIONS = [
  'sales:settings:manage',
  'sales:manage',
  'crm:manage',
];

const DEFAULT_SETTINGS: CommercialSettings = {
  organization_id: '',
  default_payment_terms: '30 DDL',
  quote_validity_days: 15,
  maximum_discount_percent: 100,
  default_commission_percent: 2,
  automatic_discount_limit_percent: 5,
  minimum_margin_percent: 0,
  maximum_payment_term_days_without_approval: 0,
};

export const CommercialPoliciesSettings: React.FC = () => {
  const toast = useToast();
  const { hasAnyPermission } = usePermissions();
  const [settings, setSettings] = useState<CommercialSettings>(DEFAULT_SETTINGS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const canManage = hasAnyPermission(MANAGE_PERMISSIONS);

  const loadSettings = useCallback(async (forceRefresh = false) => {
    setLoading(true);
    try {
      setSettings(await salesService.getCommercialSettings(forceRefresh));
    } catch (error) {
      toast.error(formatApiError(error, 'Não foi possível carregar as políticas comerciais.'));
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void loadSettings();
  }, [loadSettings]);

  const updateNumber = (
    field: 'quote_validity_days' | 'maximum_discount_percent' | 'default_commission_percent'
      | 'automatic_discount_limit_percent' | 'minimum_margin_percent'
      | 'maximum_payment_term_days_without_approval',
    value: string,
  ) => {
    setSettings((current) => ({
      ...current,
      [field]: Number(value),
    }));
  };

  const handleSave = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      const updated = await salesService.updateCommercialSettings({
        default_payment_terms: settings.default_payment_terms.trim(),
        quote_validity_days: settings.quote_validity_days,
        maximum_discount_percent: settings.maximum_discount_percent,
        default_commission_percent: settings.default_commission_percent,
        automatic_discount_limit_percent: settings.automatic_discount_limit_percent,
        minimum_margin_percent: settings.minimum_margin_percent,
        maximum_payment_term_days_without_approval: settings.maximum_payment_term_days_without_approval,
      });
      setSettings(updated);
      toast.success('Políticas comerciais atualizadas.');
    } catch (error) {
      toast.error(formatApiError(error, 'Não foi possível salvar as políticas comerciais.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="commercial-policies-settings" aria-labelledby="commercial-policies-title">
      <div className="commercial-policies-header">
        <div className="commercial-policies-title-wrap">
          <div className="commercial-policies-icon"><SlidersHorizontal size={21} /></div>
          <div>
            <h2 id="commercial-policies-title">Políticas comerciais</h2>
            <p>Parâmetros únicos utilizados por CRM, Vendas e PDV.</p>
          </div>
        </div>
        <button
          type="button"
          className="commercial-policies-refresh"
          onClick={() => void loadSettings(true)}
          disabled={loading}
          aria-label="Atualizar políticas"
          title="Atualizar políticas"
        >
          <RefreshCw size={16} className={loading ? 'spinning' : ''} />
        </button>
      </div>

      {loading ? (
        <div className="commercial-policies-loading">
          <RefreshCw size={20} className="spinning" /> Carregando políticas...
        </div>
      ) : (
        <form onSubmit={handleSave}>
          <fieldset disabled={!canManage || saving}>
            <div className="commercial-policy-grid">
              <label className="commercial-policy-card">
                <span className="commercial-policy-card-icon"><CreditCard size={18} /></span>
                <span className="commercial-policy-card-copy">
                  <strong>Condição de pagamento padrão</strong>
                  <small>Preenchida em novos orçamentos e pedidos.</small>
                </span>
                <input
                  type="text"
                  required
                  maxLength={100}
                  value={settings.default_payment_terms}
                  onChange={(event) => setSettings({
                    ...settings,
                    default_payment_terms: event.target.value,
                  })}
                  placeholder="Ex: 30 DDL"
                />
              </label>

              <label className="commercial-policy-card">
                <span className="commercial-policy-card-icon"><CalendarDays size={18} /></span>
                <span className="commercial-policy-card-copy">
                  <strong>Validade padrão do orçamento</strong>
                  <small>Quantidade de dias a partir da emissão.</small>
                </span>
                <div className="commercial-policy-number-input">
                  <input
                    type="number"
                    required
                    min={1}
                    max={365}
                    value={settings.quote_validity_days}
                    onChange={(event) => updateNumber('quote_validity_days', event.target.value)}
                  />
                  <span>dias</span>
                </div>
              </label>

              <label className="commercial-policy-card">
                <span className="commercial-policy-card-icon warning"><BadgePercent size={18} /></span>
                <span className="commercial-policy-card-copy">
                  <strong>Desconto máximo permitido</strong>
                  <small>Bloqueia valores superiores em orçamento, pedido e PDV.</small>
                </span>
                <div className="commercial-policy-number-input">
                  <input
                    type="number"
                    required
                    min={0}
                    max={100}
                    step="0.01"
                    value={settings.maximum_discount_percent}
                    onChange={(event) => updateNumber('maximum_discount_percent', event.target.value)}
                  />
                  <span>%</span>
                </div>
              </label>

              <label className="commercial-policy-card">
                <span className="commercial-policy-card-icon"><BadgePercent size={18} /></span>
                <span className="commercial-policy-card-copy">
                  <strong>Comissão padrão</strong>
                  <small>Aplicada quando uma nova meta não informa percentual próprio.</small>
                </span>
                <div className="commercial-policy-number-input">
                  <input
                    type="number"
                    required
                    min={0}
                    max={100}
                    step="0.01"
                    value={settings.default_commission_percent}
                    onChange={(event) => updateNumber('default_commission_percent', event.target.value)}
                  />
                  <span>%</span>
                </div>
              </label>
              <label className="commercial-policy-card">
                <span className="commercial-policy-card-icon warning"><ShieldAlert size={18} /></span>
                <span className="commercial-policy-card-copy">
                  <strong>Desconto sem aprovação</strong>
                  <small>Acima deste percentual, cria uma solicitação comercial.</small>
                </span>
                <div className="commercial-policy-number-input">
                  <input
                    type="number"
                    required
                    min={0}
                    max={settings.maximum_discount_percent}
                    step="0.01"
                    value={settings.automatic_discount_limit_percent}
                    onChange={(event) => updateNumber('automatic_discount_limit_percent', event.target.value)}
                  />
                  <span>%</span>
                </div>
              </label>

              <label className="commercial-policy-card">
                <span className="commercial-policy-card-icon warning"><ShieldAlert size={18} /></span>
                <span className="commercial-policy-card-copy">
                  <strong>Margem mínima</strong>
                  <small>Abaixo desta margem, exige aprovação. Zero desativa a regra.</small>
                </span>
                <div className="commercial-policy-number-input">
                  <input
                    type="number"
                    required
                    min={0}
                    max={100}
                    step="0.01"
                    value={settings.minimum_margin_percent}
                    onChange={(event) => updateNumber('minimum_margin_percent', event.target.value)}
                  />
                  <span>%</span>
                </div>
              </label>

              <label className="commercial-policy-card">
                <span className="commercial-policy-card-icon warning"><CalendarDays size={18} /></span>
                <span className="commercial-policy-card-copy">
                  <strong>Prazo sem aprovação</strong>
                  <small>Maior prazo da condição. Zero desativa a regra.</small>
                </span>
                <div className="commercial-policy-number-input">
                  <input
                    type="number"
                    required
                    min={0}
                    max={3650}
                    value={settings.maximum_payment_term_days_without_approval}
                    onChange={(event) => updateNumber('maximum_payment_term_days_without_approval', event.target.value)}
                  />
                  <span>dias</span>
                </div>
              </label>
            </div>
          </fieldset>

          <div className="commercial-policies-footer">
            <span>
              {canManage
                ? 'As alterações passam a valer para novos documentos.'
                : 'Você possui acesso somente para consulta.'}
            </span>
            {canManage && (
              <button type="submit" disabled={saving || !settings.default_payment_terms.trim()}>
                <Save size={16} /> {saving ? 'Salvando...' : 'Salvar políticas'}
              </button>
            )}
          </div>
        </form>
      )}
    </section>
  );
};
