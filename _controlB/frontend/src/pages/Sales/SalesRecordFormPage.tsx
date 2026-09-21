import { useEffect, useState } from 'react';
import { useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { salesService, crmService, formatApiError } from '@/services/api';
import type { Customer, SalesQuote, SalesOrder } from '@/types';
import { CustomerModal } from '@/components/CustomerModal/CustomerModal';
import { QuoteModal } from '@/components/QuoteModal/QuoteModal';
import { OrderModal } from '@/components/OrderModal/OrderModal';
import { RecordFormPage } from '@/components/RecordForm';
import { useToast } from '@/components/Toast/ToastContext';
import { usePermissions } from '@/hooks/usePermissions';

export function SalesRecordFormPage({ kind }: { kind: 'clientes' | 'cotacoes' | 'pedidos' }) {
  const { recordId = 'novo' } = useParams();
  return <SalesRecordEditor key={`${kind}:${recordId}`} kind={kind} recordId={recordId} />;
}

function SalesRecordEditor({ kind, recordId }: { kind: 'clientes' | 'cotacoes' | 'pedidos'; recordId: string }) {
  const navigate = useNavigate();
  const toast = useToast();
  const location = useLocation();
  const [params] = useSearchParams();
  const { hasPermission, loading: permissionsLoading } = usePermissions();
  const canView = hasPermission('sales:view');
  const [record, setRecord] = useState<Customer | SalesQuote | SalesOrder | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const isNew = recordId === 'novo';
  const view = kind === 'clientes' ? 'customers' : kind === 'cotacoes' ? 'quotes' : 'orders';
  const back = () => {
    const origin = location.state?.returnTo;
    const target = typeof origin === 'string' && /^\/(crm|vendas)(\/|\?|$)/.test(origin) ? origin : `/vendas?view=${view}`;
    if (kind === 'clientes' && record && location.state?.selectCustomerOnReturn) {
      const [path, query] = target.split('?'); const next = new URLSearchParams(query); next.set('selectedCustomer', record.id);
      navigate(path + '?' + next);
    } else navigate(target);
  };
  useEffect(() => {
    let cancelled = false;
    if (permissionsLoading) return;
    if (!canView) { setError('Sem permissão para acessar Vendas.'); setLoading(false); return; }
    const load = async () => {
      setLoading(true); setError(null);
      try {
        const value = isNew ? null : kind === 'clientes' ? await salesService.getCustomer(recordId, true)
          : kind === 'cotacoes' ? await salesService.getQuote(recordId, true) : await salesService.getOrder(recordId, true);
        if (!cancelled) setRecord(value);
      } catch (err) { if (!cancelled) setError(formatApiError(err, 'Não foi possível carregar o registro.')); }
      finally { if (!cancelled) setLoading(false); }
    };
    void load();
    return () => { cancelled = true; };
  }, [recordId, kind, isNew, attempt, permissionsLoading, canView]);
  const saved = async (value: Customer | SalesQuote | SalesOrder) => {
    setRecord(value);
    if (isNew && kind === 'clientes' && location.state?.opportunityId) {
      try { await crmService.updateOpportunity(location.state.opportunityId, { customer_id: value.id, customer_name: (value as Customer).name }); }
      catch (err) { toast.warning(formatApiError(err, 'Cliente salvo, mas não foi possível vinculá-lo à oportunidade. Faça o vínculo pelo formulário do CRM.')); }
    }
    if (isNew) navigate(`/vendas/${kind}/${value.id}`, { replace: true, state: location.state });
  };
  if (loading || error) return <RecordFormPage title="Registro comercial" isLoading={loading} error={error} onBack={back} onRetry={() => setAttempt(n => n + 1)} />;
  if (kind === 'clientes') return <CustomerModal page isOpen onClose={back} customer={record as Customer | null} onSuccess={saved} />;
  if (kind === 'cotacoes') return <QuoteModal page isOpen onClose={back} quote={record as SalesQuote | null} onSuccess={saved}
    fixedOpportunityId={params.get('opportunityId')} fixedCustomerId={params.get('customerId')} fixedCustomerName={params.get('customerName')} />;
  return <OrderModal page isOpen onClose={back} order={record as SalesOrder | null} onSuccess={saved} />;
}
