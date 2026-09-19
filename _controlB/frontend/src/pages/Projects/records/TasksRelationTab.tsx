import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { CalendarDays, ClipboardCheck, Plus, RefreshCw, UserRound } from 'lucide-react';

import { RecordFormSection } from '@/components/RecordForm';
import { usePermissions } from '@/hooks/usePermissions';
import { createRecordNavigationState, buildRecordFormPath } from '@/routing/recordRoutes';
import { formatApiError, projectsService } from '@/services/api';
import type { Task } from '@/types';

import { statusLabel } from './recordFormUtils';

interface TasksRelationTabProps {
  context: 'project' | 'work_order';
  recordId?: string;
  onCountChange?: (count: number) => void;
}

const priorityLabel = (priority?: string) => ({
  LOW: 'Baixa', MEDIUM: 'Média', HIGH: 'Alta', CRITICAL: 'Crítica',
}[String(priority || '').toUpperCase()] || priority || '-');

export function TasksRelationTab({ context, recordId, onCountChange }: TasksRelationTabProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { hasPermission } = usePermissions();
  const canCreate = hasPermission('tasks:create');
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!recordId) { setTasks([]); onCountChange?.(0); return; }
    setLoading(true); setError(null);
    try {
      const data = await projectsService.getTasks(
        context === 'project'
          ? { project_id: recordId, page_size: 100 }
          : { work_order_id: recordId, page_size: 100 },
        true,
      );
      setTasks(data); onCountChange?.(data.length);
    } catch (loadError) {
      setError(formatApiError(loadError, 'Não foi possível carregar as tarefas.'));
    } finally { setLoading(false); }
  }, [context, onCountChange, recordId]);

  useEffect(() => { void load(); }, [load]);

  const summary = useMemo(() => ({
    pending: tasks.filter((task) => !['DONE', 'COMPLETED', 'CANCELLED'].includes(task.status.toUpperCase())).length,
    done: tasks.filter((task) => ['DONE', 'COMPLETED'].includes(task.status.toUpperCase())).length,
    blocked: tasks.filter((task) => task.status.toUpperCase() === 'BLOCKED').length,
  }), [tasks]);

  const openTask = (taskId?: string) => {
    const query = !taskId && recordId
      ? `?${context === 'project' ? 'projectId' : 'workOrderId'}=${encodeURIComponent(recordId)}`
      : '';
    navigate(`${buildRecordFormPath('projetos', 'tarefas', taskId)}${query}`, {
      state: createRecordNavigationState(location),
    });
  };

  return <RecordFormSection
    title="Tarefas"
    description={context === 'project'
      ? 'Tarefas diretas e tarefas das ordens de trabalho vinculadas ao projeto.'
      : 'Atividades necessárias para executar esta ordem de trabalho.'}
    icon={ClipboardCheck}
    actions={<div className="record-related-actions"><button type="button" className="ui-button ui-button--secondary" onClick={() => void load()} disabled={loading}><RefreshCw size={14} className={loading ? 'spin' : ''} /> Atualizar</button>{canCreate && <button type="button" className="ui-button ui-button--primary" onClick={() => openTask()} disabled={!recordId}><Plus size={15} /> Nova tarefa</button>}</div>}
  >
    <div className="record-task-summary">
      <span><strong>{tasks.length}</strong> Total</span>
      <span><strong>{summary.pending}</strong> Pendentes</span>
      <span className="is-blocked"><strong>{summary.blocked}</strong> Bloqueadas</span>
      <span className="is-done"><strong>{summary.done}</strong> Concluídas</span>
    </div>

    {loading ? <div className="record-form-empty-state"><RefreshCw size={22} className="spin" /><strong>Carregando tarefas...</strong></div>
      : error ? <div className="record-form-empty-state"><strong>Não foi possível carregar as tarefas</strong><span>{error}</span><button type="button" className="ui-button ui-button--secondary" onClick={() => void load()}>Tentar novamente</button></div>
      : tasks.length === 0 ? <div className="record-form-empty-state"><ClipboardCheck size={26} /><strong>Nenhuma tarefa cadastrada</strong><span>{canCreate ? 'Crie a primeira tarefa mantendo o vínculo com este registro.' : 'Ainda não existem tarefas vinculadas a este registro.'}</span>{canCreate && <button type="button" className="ui-button ui-button--primary" onClick={() => openTask()}><Plus size={15} /> Nova tarefa</button>}</div>
      : <div className="record-task-list">{tasks.map((task) => <button type="button" className="record-task-item" key={task.id} onClick={() => openTask(task.id)}>
        <span className={`record-task-item__status status-${task.status.toLowerCase()}`} aria-hidden="true" />
        <span className="record-task-item__identity"><small>{task.task_number || `TSK-${task.id.slice(0, 6).toUpperCase()}`}</small><strong>{task.title}</strong></span>
        <span className="record-task-item__meta"><span className={`record-task-priority priority-${task.priority.toLowerCase()}`}>{priorityLabel(task.priority)}</span><span>{statusLabel(task.status)}</span>{task.assignments?.length ? <span><UserRound size={12} /> {task.assignments.map((assignment) => assignment.user_name).filter(Boolean).join(', ') || `${task.assignments.length} responsável(is)`}</span> : <span>Sem responsável</span>}{task.due_date && <span><CalendarDays size={12} /> {new Date(task.due_date).toLocaleDateString('pt-BR')}</span>}{context === 'project' && task.work_order_id && <span>Via OS</span>}</span>
      </button>)}</div>}
  </RecordFormSection>;
}
