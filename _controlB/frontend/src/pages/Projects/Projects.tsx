/**
 * pages/Projects/Projects.tsx - Central Operacional de Projetos, Serviços e Produção
 * 
 * Padrão Oficial ControlB ERP:
 * 1. Arquitetura 2 Colunas: Sidebar Lateral Esquerda (.sidebar-left) + Painel de Conteúdo (.content-right).
 * 2. Navegação Canônica:
 *    - VISÃO GERAL: Dashboard Operacional
 *    - EXECUÇÃO: Projetos, Ordens de Trabalho, Tarefas & Atividades, Quadro Kanban
 *    - CONTROLE: Pendências & Ocorrências
 *    - CONFIGURAÇÕES: Tipos de Projeto, Tipos de Ordem, Fluxos & Workflows
 * 3. Abas Horizontais reservadas para a visualização interna/detalhada de Projetos (Visão Geral, OSs, Tarefas, Checklists, Linha do Tempo).
 * 4. Modais completos de parametrização e criação (inclusive Tipos de Projeto, Tipos de OS e Workflows).
 * 5. Integração com a Cadeia Documental Transversal do ControlB (DocumentTimeline).
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  FolderKanban, Kanban, ClipboardList, AlertTriangle, Plus, RefreshCw,
  Search, CheckCircle2, Clock, Calendar, DollarSign,
  Layers, ArrowRight, X, CheckSquare, Settings2,
  Briefcase, Check, ShieldAlert, GitBranch, Trash2, LayoutGrid, Table as TableIcon,
  Pencil, User as UserIcon, Users, MapPin, Building, Eye, GripVertical
} from 'lucide-react';
import { projectsService, salesService, identityService, formatApiError } from '@/services/api';
import { BulkActionsBar } from '@/components/BulkActionsBar/BulkActionsBar';
import { ConfirmModal } from '@/components/ConfirmModal/ConfirmModal';
import { useBulkSelection } from '@/hooks/useBulkSelection';
import { useToast } from '@/components/Toast/ToastContext';
import { buildRecordFormPath } from '@/routing/recordRoutes';
import type {
  Project, WorkOrder, Task, Issue, ProjectType, WorkOrderType, WorkflowTemplate,
  TaskStatus, Customer, User, Team
} from '@/types';
import './Projects.scss';

type ActiveMenu =
  | 'dashboard'
  | 'projects'
  | 'work_orders'
  | 'tasks'
  | 'kanban'
  | 'issues'
  | 'project_types'
  | 'wo_types'
  | 'workflows';

const hasStatus = (value: string, ...expected: string[]) => expected.includes(value.toUpperCase());

export const Projects: React.FC = () => {
  // ----------------------------------------------------------------------------
  // ESTADOS PRINCIPAIS
  // ----------------------------------------------------------------------------
  const location = useLocation();
  const navigate = useNavigate();
  const requestedView = new URLSearchParams(location.search).get('view') as ActiveMenu | null;
  const validViews: ActiveMenu[] = ['dashboard', 'projects', 'work_orders', 'tasks', 'kanban', 'issues', 'project_types', 'wo_types', 'workflows'];
  const [activeMenu, setActiveMenu] = useState<ActiveMenu>(requestedView && validViews.includes(requestedView) ? requestedView : 'dashboard');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Listagens de dados operacionais e de configuração
  const [projects, setProjects] = useState<Project[]>([]);
  const [workOrders, setWorkOrders] = useState<WorkOrder[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [issues, setIssues] = useState<Issue[]>([]);
  const [projectTypes, setProjectTypes] = useState<ProjectType[]>([]);
  const [workOrderTypes, setWorkOrderTypes] = useState<WorkOrderType[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowTemplate[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);

  // Filtros de busca
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [typeFilter, setTypeFilter] = useState<string>('ALL');

  // Modo de visualização de projetos (Cards vs Tabela)
  const [projectViewMode, setProjectViewMode] = useState<'grid' | 'table'>('table');

  // Gerenciadores de Seleção em Massa (Bulk Actions)
  const projectSelection = useBulkSelection<Project>();
  const workOrderSelection = useBulkSelection<WorkOrder>();
  const taskSelection = useBulkSelection<Task>();
  const issueSelection = useBulkSelection<Issue>();
  const projectTypeSelection = useBulkSelection<ProjectType>();
  const workOrderTypeSelection = useBulkSelection<WorkOrderType>();
  const workflowSelection = useBulkSelection<WorkflowTemplate>();

  const toast = useToast();

  const openRecordForm = useCallback((resource: string, recordId?: string, search = '') => {
    navigate(`${buildRecordFormPath('projetos', resource, recordId)}${search}`, {
      state: { returnTo: `/projetos?view=${activeMenu}` },
    });
  }, [activeMenu, navigate]);

  const openNewProject = () => openRecordForm('projetos');
  const openNewWorkOrder = (projectId?: string) => openRecordForm('ordens-de-trabalho', undefined, projectId ? `?projectId=${encodeURIComponent(projectId)}` : '');
  const openNewTask = (projectId?: string, workOrderId?: string) => {
    const params = new URLSearchParams();
    if (projectId) params.set('projectId', projectId);
    if (workOrderId) params.set('workOrderId', workOrderId);
    openRecordForm('tarefas', undefined, params.size ? `?${params.toString()}` : '');
  };
  const openNewIssue = (projectId?: string) => openRecordForm('ocorrencias', undefined, projectId ? `?projectId=${encodeURIComponent(projectId)}` : '');
  const openNewProjectType = () => openRecordForm('tipos-de-projeto');
  const openNewWorkOrderType = () => openRecordForm('tipos-de-ordem');
  const openNewWorkflow = () => openRecordForm('workflows');

  // Estado do Modal de Confirmação Unificado
  const [confirmModal, setConfirmModal] = useState<{
    isOpen: boolean;
    title: string;
    subtitle?: string;
    message: React.ReactNode;
    confirmText?: string;
    cancelText?: string;
    type?: 'danger' | 'warning' | 'info' | 'success';
    isLoading?: boolean;
    errorMessage?: string | null;
    onConfirm: () => Promise<void>;
  }>({
    isOpen: false,
    title: '',
    message: '',
    onConfirm: async () => {},
  });

  const openConfirmModal = (config: {
    title: string;
    subtitle?: string;
    message: React.ReactNode;
    confirmText?: string;
    cancelText?: string;
    type?: 'danger' | 'warning' | 'info' | 'success';
    onConfirm: () => Promise<void>;
  }) => {
    setConfirmModal({
      isOpen: true,
      title: config.title,
      subtitle: config.subtitle,
      message: config.message,
      confirmText: config.confirmText || 'Confirmar Exclusão',
      cancelText: config.cancelText || 'Cancelar',
      type: config.type || 'danger',
      isLoading: false,
      errorMessage: null,
      onConfirm: config.onConfirm,
    });
  };

  const closeConfirmModal = () => {
    setConfirmModal(prev => ({ ...prev, isOpen: false, errorMessage: null, isLoading: false }));
  };

  const runProjectsBulkAction = (
    ids: string[],
    label: string,
    action: (id: string) => Promise<unknown>,
    clearSelection: () => void,
    resourceName = 'registro(s)'
  ) => {
    if (ids.length === 0) return;
    openConfirmModal({
      title: `${label} em Lote`,
      subtitle: `${ids.length} ${ids.length === 1 ? 'registro selecionado' : 'registros selecionados'}`,
      message: `Deseja realmente executar a ação "${label}" para os ${ids.length} ${resourceName} selecionado(s)?`,
      confirmText: `Confirmar (${ids.length})`,
      type: 'danger',
      onConfirm: async () => {
        setConfirmModal(prev => ({ ...prev, isLoading: true, errorMessage: null }));
        try {
          const results = await Promise.allSettled(ids.map(action));
          const succeeded = results.filter(result => result.status === 'fulfilled').length;
          const failed = results.length - succeeded;
          clearSelection();
          closeConfirmModal();
          await loadData(true);
          if (failed > 0) {
            toast.warning(`${succeeded} ${resourceName} processado(s); ${failed} falharam ou possuem vínculos.`);
          } else {
            toast.success(`${succeeded} ${resourceName} processado(s) com sucesso.`);
          }
        } catch (err: any) {
          setConfirmModal(prev => ({
            ...prev,
            isLoading: false,
            errorMessage: formatApiError(err, 'Erro ao executar ação em lote')
          }));
        }
      }
    });
  };

  // Handlers de exclusão individual com Modal de Confirmação
  const handleDeleteProject = (proj: Project) => {
    openConfirmModal({
      title: 'Excluir Projeto',
      subtitle: 'Esta ação excluirá o projeto e removerá suas alocações.',
      type: 'danger',
      message: (
        <>
          Deseja realmente excluir o projeto <strong>{proj.name}</strong> ({proj.code})?
        </>
      ),
      confirmText: 'Excluir Projeto',
      onConfirm: async () => {
        setConfirmModal(prev => ({ ...prev, isLoading: true, errorMessage: null }));
        try {
          await projectsService.deleteProject(proj.id);
          projectSelection.clearSelection();
          closeConfirmModal();
          await loadData(true);
          toast.success('Projeto excluído com sucesso.');
        } catch (err: any) {
          setConfirmModal(prev => ({
            ...prev,
            isLoading: false,
            errorMessage: formatApiError(err, 'Erro ao excluir projeto')
          }));
        }
      }
    });
  };

  const handleDeleteWorkOrder = (wo: WorkOrder) => {
    openConfirmModal({
      title: 'Excluir Ordem de Trabalho',
      subtitle: 'Esta ação removerá a OS e suas atividades.',
      type: 'danger',
      message: (
        <>
          Deseja realmente excluir a ordem <strong>{wo.title}</strong> ({wo.code})?
        </>
      ),
      confirmText: 'Excluir Ordem',
      onConfirm: async () => {
        setConfirmModal(prev => ({ ...prev, isLoading: true, errorMessage: null }));
        try {
          await projectsService.deleteWorkOrder(wo.id);
          workOrderSelection.clearSelection();
          closeConfirmModal();
          await loadData(true);
          toast.success('Ordem de trabalho excluída com sucesso.');
        } catch (err: any) {
          setConfirmModal(prev => ({
            ...prev,
            isLoading: false,
            errorMessage: formatApiError(err, 'Erro ao excluir ordem')
          }));
        }
      }
    });
  };

  const handleDeleteTask = (task: Task) => {
    openConfirmModal({
      title: 'Excluir Tarefa',
      subtitle: 'Esta ação removerá a tarefa permanentemente.',
      type: 'danger',
      message: (
        <>
          Deseja realmente excluir a tarefa <strong>{task.title}</strong>?
        </>
      ),
      confirmText: 'Excluir Tarefa',
      onConfirm: async () => {
        setConfirmModal(prev => ({ ...prev, isLoading: true, errorMessage: null }));
        try {
          await projectsService.deleteTask(task.id);
          taskSelection.clearSelection();
          closeConfirmModal();
          await loadData(true);
          toast.success('Tarefa excluída com sucesso.');
        } catch (err: any) {
          setConfirmModal(prev => ({
            ...prev,
            isLoading: false,
            errorMessage: formatApiError(err, 'Erro ao excluir tarefa')
          }));
        }
      }
    });
  };

  const handleDeleteIssue = (iss: Issue) => {
    openConfirmModal({
      title: 'Excluir Ocorrência',
      subtitle: 'Esta ação removerá o registro da ocorrência.',
      type: 'danger',
      message: (
        <>
          Deseja realmente excluir a ocorrência <strong>{iss.title}</strong> ({iss.issue_number || iss.code})?
        </>
      ),
      confirmText: 'Excluir Ocorrência',
      onConfirm: async () => {
        setConfirmModal(prev => ({ ...prev, isLoading: true, errorMessage: null }));
        try {
          await projectsService.deleteIssue(iss.id);
          issueSelection.clearSelection();
          closeConfirmModal();
          await loadData(true);
          toast.success('Ocorrência excluída com sucesso.');
        } catch (err: any) {
          setConfirmModal(prev => ({
            ...prev,
            isLoading: false,
            errorMessage: formatApiError(err, 'Erro ao excluir ocorrência')
          }));
        }
      }
    });
  };

  const handleDeleteProjectType = (pt: ProjectType) => {
    openConfirmModal({
      title: 'Excluir Tipo de Projeto',
      subtitle: 'Certifique-se de que nenhum projeto ativo utilize esta categoria.',
      type: 'danger',
      message: (
        <>
          Deseja realmente excluir o tipo de projeto <strong>{pt.name}</strong> ({pt.code})?
        </>
      ),
      confirmText: 'Excluir Tipo',
      onConfirm: async () => {
        setConfirmModal(prev => ({ ...prev, isLoading: true, errorMessage: null }));
        try {
          await projectsService.deleteProjectType(pt.id);
          projectTypeSelection.clearSelection();
          closeConfirmModal();
          await loadData(true);
          toast.success('Tipo de projeto excluído com sucesso.');
        } catch (err: any) {
          setConfirmModal(prev => ({
            ...prev,
            isLoading: false,
            errorMessage: formatApiError(err, 'Erro ao excluir tipo de projeto')
          }));
        }
      }
    });
  };

  const handleDeleteWorkOrderType = (wt: WorkOrderType) => {
    openConfirmModal({
      title: 'Excluir Tipo de Ordem',
      subtitle: 'Certifique-se de que nenhuma ordem utilize este tipo.',
      type: 'danger',
      message: (
        <>
          Deseja realmente excluir o tipo de ordem <strong>{wt.name}</strong> ({wt.code})?
        </>
      ),
      confirmText: 'Excluir Tipo',
      onConfirm: async () => {
        setConfirmModal(prev => ({ ...prev, isLoading: true, errorMessage: null }));
        try {
          await projectsService.deleteWorkOrderType(wt.id);
          workOrderTypeSelection.clearSelection();
          closeConfirmModal();
          await loadData(true);
          toast.success('Tipo de ordem excluído com sucesso.');
        } catch (err: any) {
          setConfirmModal(prev => ({
            ...prev,
            isLoading: false,
            errorMessage: formatApiError(err, 'Erro ao excluir tipo de ordem')
          }));
        }
      }
    });
  };

  const handleDeleteWorkflow = (wf: WorkflowTemplate) => {
    openConfirmModal({
      title: 'Excluir Modelo de Fluxo (Workflow)',
      subtitle: 'Esta ação excluirá o template de workflow e todas as suas etapas associadas.',
      type: 'danger',
      message: (
        <>
          Deseja realmente excluir o workflow <strong>{wf.name}</strong>?
        </>
      ),
      confirmText: 'Excluir Workflow',
      onConfirm: async () => {
        setConfirmModal(prev => ({ ...prev, isLoading: true, errorMessage: null }));
        try {
          await projectsService.deleteWorkflowTemplate(wf.id);
          workflowSelection.clearSelection();
          closeConfirmModal();
          await loadData(true);
          toast.success('Workflow excluído com sucesso.');
        } catch (err: any) {
          setConfirmModal(prev => ({
            ...prev,
            isLoading: false,
            errorMessage: formatApiError(err, 'Erro ao excluir workflow')
          }));
        }
      }
    });
  };

  const handleDeleteStage = (stageId: string, stageName: string) => {
    openConfirmModal({
      title: 'Excluir Etapa do Workflow',
      subtitle: 'A remoção da etapa afetará transições de projetos neste estágio.',
      type: 'danger',
      message: (
        <>
          Deseja realmente remover a etapa <strong>{stageName}</strong> deste workflow?
        </>
      ),
      confirmText: 'Excluir Etapa',
      onConfirm: async () => {
        setConfirmModal(prev => ({ ...prev, isLoading: true, errorMessage: null }));
        try {
          await projectsService.deleteWorkflowStage(stageId);
          closeConfirmModal();
          await loadData(true);
          toast.success('Etapa removida com sucesso.');
        } catch (err: any) {
          setConfirmModal(prev => ({
            ...prev,
            isLoading: false,
            errorMessage: formatApiError(err, 'Erro ao excluir etapa')
          }));
        }
      }
    });
  };

  // A resolução é uma ação rápida; por isso permanece em modal.
  const [showResolveIssueModal, setShowResolveIssueModal] = useState<Issue | null>(null);
  const [resolutionNotes, setResolutionNotes] = useState('');

  // Adicionar uma etapa permanece como ação rápida no contexto do Kanban.
  const [showStageModal, setShowStageModal] = useState(false);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string>('');
  const [kanbanMode, setKanbanMode] = useState<'projects' | 'tasks'>('projects');
  const [draggedProjectId, setDraggedProjectId] = useState<string | null>(null);
  const [draggedTaskId, setDraggedTaskId] = useState<string | null>(null);
  const [draggedStageId, setDraggedStageId] = useState<string | null>(null);
  const [kanbanDropTarget, setKanbanDropTarget] = useState<string | null>(null);

  const [stageForm, setStageForm] = useState({
    name: '',
    color: '#6366f1',
    position: 1,
    is_initial: false,
    is_terminal: false,
    description: ''
  });

  // ----------------------------------------------------------------------------
  // CARREGAMENTO DE DADOS
  // ----------------------------------------------------------------------------
  const loadData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setErrorMessage(null);

    try {
      const [
        projectsData,
        woData,
        tasksData,
        issuesData,
        pTypes,
        woTypes,
        wfs,
        custs,
        usrs,
        tms
      ] = await Promise.all([
        projectsService.getProjects(undefined, isRefresh),
        projectsService.getWorkOrders(undefined, isRefresh),
        projectsService.getTasks(undefined, isRefresh),
        projectsService.getIssues(undefined, isRefresh),
        projectsService.getProjectTypes(isRefresh, false),
        projectsService.getWorkOrderTypes(isRefresh, false),
        projectsService.getWorkflowTemplates(isRefresh, false),
        salesService.getCustomers(undefined, isRefresh).catch(() => []),
        identityService.getUsers(isRefresh).catch(() => []),
        identityService.getTeams(undefined, isRefresh).catch(() => []),
      ]);

      setProjects(projectsData);
      setWorkOrders(woData);
      setTasks(tasksData);
      setIssues(issuesData);
      setProjectTypes(pTypes);
      setWorkOrderTypes(woTypes);
      setWorkflows(wfs);
      setCustomers(custs || []);
      setUsers(usrs || []);
      setTeams(tms || []);

      if (!selectedWorkflowId || !wfs.some((workflow) => workflow.is_active && workflow.id === selectedWorkflowId)) {
        setSelectedWorkflowId(wfs.find((workflow) => workflow.is_active)?.id || '');
      }
    } catch (err: any) {
      console.error('Erro ao carregar dados do módulo de projetos:', err);
      setErrorMessage(formatApiError ? formatApiError(err) : (err.message || 'Erro de comunicação'));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [selectedWorkflowId]);

  // Funções utilitárias de resolução de nomes
  const getCustomerName = useCallback((customerId?: string | null) => {
    if (!customerId) return null;
    const c = customers.find(item => item.id === customerId);
    return c ? (c.trade_name || c.name || 'Cliente') : null;
  }, [customers]);

  const getUserName = useCallback((userId?: string | null) => {
    if (!userId) return null;
    const u = users.find(item => item.id === userId);
    return u ? (u.full_name || u.email || 'Usuário') : null;
  }, [users]);

  const getTeamName = useCallback((teamId?: string | null) => {
    if (!teamId) return null;
    const t = teams.find(item => item.id === teamId);
    return t ? t.name : null;
  }, [teams]);

  const activeWorkflow = useMemo(() => {
    const activeWorkflows = workflows.filter((workflow) => workflow.is_active);
    if (activeWorkflows.length === 0) return null;
    if (selectedWorkflowId) {
      const found = activeWorkflows.find(w => w.id === selectedWorkflowId);
      if (found) return found;
    }
    return activeWorkflows[0];
  }, [workflows, selectedWorkflowId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Registros completos são abertos em páginas próprias, preservando a lista de origem.
  const handleSelectProject = (proj: Project) => openRecordForm('projetos', proj.id);

  // ----------------------------------------------------------------------------
  // CÁLCULOS E KPIS
  // ----------------------------------------------------------------------------
  const kpis = useMemo(() => {
    const activeProjects = projects.filter(p => hasStatus(p.status, 'IN_PROGRESS', 'PLANNING')).length;
    const completedProjects = projects.filter(p => hasStatus(p.status, 'COMPLETED')).length;
    const openWOs = workOrders.filter(w => hasStatus(w.status, 'OPEN', 'IN_PROGRESS')).length;
    const pendingTasks = tasks.filter(t => hasStatus(t.status, 'TODO', 'IN_PROGRESS')).length;
    const criticalIssues = issues.filter(i => (i.severity === 'CRITICAL' || i.severity === 'HIGH') && !hasStatus(i.status, 'RESOLVED', 'CLOSED')).length;
    const totalBudget = projects.reduce((acc, p) => acc + (Number(p.estimated_budget) || 0), 0);
    const totalRealized = projects.reduce((acc, p) => acc + (Number(p.realized_cost) || 0), 0);

    return {
      activeProjects,
      completedProjects,
      openWOs,
      pendingTasks,
      criticalIssues,
      totalBudget,
      totalRealized
    };
  }, [projects, workOrders, tasks, issues]);

  // ----------------------------------------------------------------------------
  // FILTRAGEM DE DADOS
  // ----------------------------------------------------------------------------
  const filteredProjects = useMemo(() => {
    return projects.filter(p => {
      const matchesSearch = !searchTerm || 
        p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        p.code.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesStatus = statusFilter === 'ALL' || hasStatus(p.status, statusFilter);
      const matchesType = typeFilter === 'ALL' || p.project_type?.id === typeFilter;
      return matchesSearch && matchesStatus && matchesType;
    });
  }, [projects, searchTerm, statusFilter, typeFilter]);

  // ----------------------------------------------------------------------------
  // GESTÃO DE EDIÇÃO DE REGISTROS
  // ----------------------------------------------------------------------------
  const handleEditProject = (proj: Project) => openRecordForm('projetos', proj.id);

  const handleEditWorkOrder = (wo: WorkOrder) => openRecordForm('ordens-de-trabalho', wo.id);

  const handleEditTask = (task: Task) => openRecordForm('tarefas', task.id);

  const handleEditIssue = (issue: Issue) => openRecordForm('ocorrencias', issue.id);

  const handleEditProjectType = (pt: ProjectType) => openRecordForm('tipos-de-projeto', pt.id);

  const handleEditWorkOrderType = (wot: WorkOrderType) => openRecordForm('tipos-de-ordem', wot.id);

  const handleEditWorkflow = (wf: WorkflowTemplate) => openRecordForm('workflows', wf.id);

  // Criar Novo Estágio no Workflow do Kanban
  const handleCreateStage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!stageForm.name.trim()) return;
    try {
      let targetWfId = selectedWorkflowId || activeWorkflow?.id;

      // Se a organização não tem nenhum workflow criado ainda, cria o fluxo padrão automaticamente
      if (!targetWfId) {
        const newWf = await projectsService.createWorkflowTemplate({
          name: 'Fluxo Operacional Principal',
          description: 'Fluxo de trabalho padrão da organização',
          target_entity: 'PROJECT',
          stages: []
        });
        targetWfId = newWf.id;
        setSelectedWorkflowId(newWf.id);
      }

      await projectsService.addWorkflowStage(targetWfId, {
        name: stageForm.name.trim(),
        color: stageForm.color || '#6366f1',
        position: Number(stageForm.position) || 1,
        is_initial: Boolean(stageForm.is_initial),
        is_terminal: Boolean(stageForm.is_terminal),
        description: stageForm.description?.trim() || undefined
      });

      setShowStageModal(false);
      setStageForm({
        name: '',
        color: '#6366f1',
        position: (activeWorkflow?.stages?.length || 0) + 2,
        is_initial: false,
        is_terminal: false,
        description: ''
      });
      await loadData(true);
      toast.success('Estágio adicionado ao Kanban.');
    } catch (err: any) {
      console.error('Erro ao adicionar estágio ao Kanban:', err);
      toast.error(formatApiError(err, 'Erro ao criar estágio'));
    }
  };

  // Inicializar Fluxo Padrão da Organização (caso esteja vazio)
  const handleInitDefaultWorkflow = async () => {
    try {
      setLoading(true);
      const newWf = await projectsService.createWorkflowTemplate({
        name: 'Fluxo Padrão de Projetos & Serviços',
        description: 'Workflow operacional inicial com etapas recomendadas',
        target_entity: 'PROJECT',
        stages: [
          { name: 'Planejamento', position: 1, color: '#3b82f6', is_initial: true, is_terminal: false },
          { name: 'Execução / Obra', position: 2, color: '#f59e0b', is_initial: false, is_terminal: false },
          { name: 'Revisão / Vistoria', position: 3, color: '#8b5cf6', is_initial: false, is_terminal: false },
          { name: 'Concluído', position: 4, color: '#10b981', is_initial: false, is_terminal: true }
        ]
      });
      setSelectedWorkflowId(newWf.id);
      await loadData(true);
      toast.success('Fluxo padrão inicializado com sucesso.');
    } catch (err: any) {
      console.error('Erro ao inicializar fluxo padrão:', err);
      toast.error(formatApiError(err, 'Erro ao inicializar fluxo'));
    } finally {
      setLoading(false);
    }
  };

  // Mover projeto para outro estágio via Kanban
  const handleMoveProjectStage = async (projectId: string, targetStageId: string) => {
    try {
      await projectsService.changeProjectStage(projectId, targetStageId);
      await loadData(true);
      toast.success('Projeto movido para a nova etapa.');
    } catch (err: any) {
      console.error('Erro ao mover projeto de estágio:', err);
      toast.error(formatApiError(err, 'Não foi possível mover o projeto'));
    }
  };

  const handleReorderStages = async (sourceStageId: string, targetStageId: string) => {
    if (!activeWorkflow?.stages || sourceStageId === targetStageId) return;

    const reorderedStages = [...activeWorkflow.stages].sort((a, b) => a.position - b.position);
    const sourceIndex = reorderedStages.findIndex(stage => stage.id === sourceStageId);
    const targetIndex = reorderedStages.findIndex(stage => stage.id === targetStageId);
    if (sourceIndex < 0 || targetIndex < 0) return;

    const [movedStage] = reorderedStages.splice(sourceIndex, 1);
    reorderedStages.splice(targetIndex, 0, movedStage);

    try {
      await Promise.all(
        reorderedStages.map((stage, index) =>
          projectsService.updateWorkflowStage(stage.id, { position: index + 1 })
        )
      );
      await loadData(true);
      toast.success('Ordem das etapas atualizada.');
    } catch (err: any) {
      toast.error(formatApiError(err, 'Não foi possível reordenar as etapas'));
    } finally {
      setDraggedStageId(null);
      setKanbanDropTarget(null);
    }
  };

  // Ações de Mudança de Status
  const handleTaskStatusChange = async (taskId: string, newStatus: string) => {
    try {
      const taskStatusMap: Record<string, string> = {
        TODO: 'todo',
        IN_PROGRESS: 'in_progress',
        REVIEW: 'in_review',
        BLOCKED: 'blocked',
        DONE: 'done',
        CANCELLED: 'cancelled'
      };
      await projectsService.changeTaskStatus(taskId, taskStatusMap[newStatus] || newStatus.toLowerCase());
      await loadData(true);
      toast.success('Status da tarefa atualizado.');
    } catch (err: any) {
      toast.error(formatApiError(err, 'Erro ao atualizar status da tarefa'));
    }
  };

  const handleWorkOrderStatusChange = async (woId: string, newStatus: string) => {
    try {
      await projectsService.changeWorkOrderStatus(woId, newStatus.toLowerCase());
      await loadData(true);
      toast.success('Status da OS atualizado.');
    } catch (err: any) {
      toast.error(formatApiError(err, 'Erro ao atualizar status da OS'));
    }
  };

  const handleResolveIssue = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!showResolveIssueModal || !resolutionNotes.trim()) return;
    try {
      await projectsService.resolveIssue(showResolveIssueModal.id, resolutionNotes);
      setShowResolveIssueModal(null);
      setResolutionNotes('');
      await loadData(true);
      toast.success('Ocorrência resolvida com sucesso.');
    } catch (err: any) {
      toast.error(formatApiError(err, 'Erro ao resolver ocorrência'));
    }
  };

  // Informações de cabeçalho contextuais
  const sectionMeta = useMemo(() => {
    switch (activeMenu) {
      case 'dashboard':
        return {
          title: 'Dashboard Operacional',
          description: 'Visão executiva e controle em tempo real da camada operacional do ERP',
          icon: <Layers size={22} color="var(--accent-brand)" />
        };
      case 'projects':
        return {
          title: 'Projetos Operacionais',
          description: 'Gerenciamento estruturado de projetos, contratos técnicos e produções',
          icon: <FolderKanban size={22} color="var(--accent-brand)" />
        };
      case 'work_orders':
        return {
          title: 'Ordens de Trabalho & Serviço',
          description: 'Unidades operacionais de execução técnica e produção em campo',
          icon: <ClipboardList size={22} color="#f59e0b" />
        };
      case 'tasks':
        return {
          title: 'Tarefas & Atividades',
          description: 'Controle analítico de ações executáveis com estimativa e prazos',
          icon: <CheckSquare size={22} color="#3b82f6" />
        };
      case 'kanban':
        return {
          title: 'Quadro Ágil (Kanban)',
          description: 'Fluxo visual de trabalho contínuo dividido por etapas de execução',
          icon: <Kanban size={22} color="#8b5cf6" />
        };
      case 'issues':
        return {
          title: 'Pendências & Ocorrências',
          description: 'Registro de impedimentos, desvios, falhas técnicas e atrasos operacionais',
          icon: <AlertTriangle size={22} color="#f43f5e" />
        };
      case 'project_types':
        return {
          title: 'Tipos de Projeto',
          description: 'Parametrização de categorias, prefixos e fluxos padrão para projetos',
          icon: <Settings2 size={22} color="#ec4899" />
        };
      case 'wo_types':
        return {
          title: 'Tipos de Ordem de Trabalho',
          description: 'Classificação de ordens de serviço, produção, montagem e manutenção',
          icon: <Settings2 size={22} color="#60a5fa" />
        };
      case 'workflows':
        return {
          title: 'Fluxos & Workflows',
          description: 'Templates de etapas operacionais padronizadas com transições configuráveis',
          icon: <GitBranch size={22} color="#10b981" />
        };
    }
  }, [activeMenu]);

  return (
    <div className="projects-page">
      <div className="projects-layout">
        {/* ==================================================================== */}
        {/* 1. SIDEBAR LATERAL ESQUERDA (PADRÃO CANÔNICO CONTROLB) */}
        {/* ==================================================================== */}
        <aside className="sidebar-left">
          <div className="sidebar-header">
            <FolderKanban className="brand-icon" size={20} />
            <div className="sidebar-title-wrap">
              <span className="sidebar-title"><strong>Projetos & Operações</strong></span>
              <span className="sidebar-subtitle">Camada Operacional ERP</span>
            </div>
          </div>

          <nav className="nav-menu">
            {/* GRUPO: VISÃO GERAL */}
            <span className="menu-group-label">Visão Geral</span>
            <button
              type="button"
              className={`nav-item ${activeMenu === 'dashboard' ? 'active' : ''}`}
              onClick={() => setActiveMenu('dashboard')}
            >
              <div className="nav-item-content">
                <Layers size={16} />
                <span>Dashboard Operacional</span>
              </div>
            </button>

            {/* GRUPO: EXECUÇÃO */}
            <span className="menu-group-label">Execução</span>
            <button
              type="button"
              className={`nav-item ${activeMenu === 'projects' ? 'active' : ''}`}
              onClick={() => setActiveMenu('projects')}
            >
              <div className="nav-item-content">
                <FolderKanban size={16} />
                <span>Projetos</span>
              </div>
              <span className="nav-badge">{projects.length}</span>
            </button>

            <button
              type="button"
              className={`nav-item ${activeMenu === 'work_orders' ? 'active' : ''}`}
              onClick={() => setActiveMenu('work_orders')}
            >
              <div className="nav-item-content">
                <ClipboardList size={16} />
                <span>Ordens de Trabalho</span>
              </div>
              <span className="nav-badge">{workOrders.length}</span>
            </button>

            <button
              type="button"
              className={`nav-item ${activeMenu === 'tasks' ? 'active' : ''}`}
              onClick={() => setActiveMenu('tasks')}
            >
              <div className="nav-item-content">
                <CheckSquare size={16} />
                <span>Tarefas & Atividades</span>
              </div>
              <span className="nav-badge">{tasks.length}</span>
            </button>

            <button
              type="button"
              className={`nav-item ${activeMenu === 'kanban' ? 'active' : ''}`}
              onClick={() => setActiveMenu('kanban')}
            >
              <div className="nav-item-content">
                <Kanban size={16} />
                <span>Quadro Kanban</span>
              </div>
            </button>

            {/* GRUPO: CONTROLE */}
            <span className="menu-group-label">Controle</span>
            <button
              type="button"
              className={`nav-item ${activeMenu === 'issues' ? 'active' : ''}`}
              onClick={() => setActiveMenu('issues')}
            >
              <div className="nav-item-content">
                <AlertTriangle size={16} />
                <span>Pendências & Ocorrências</span>
              </div>
              <span className={`nav-badge ${kpis.criticalIssues > 0 ? 'critical-badge' : ''}`}>
                {issues.filter(i => !hasStatus(i.status, 'RESOLVED', 'CLOSED')).length}
              </span>
            </button>

            {/* GRUPO: CONFIGURAÇÕES */}
            <span className="menu-group-label">Configurações</span>
            <button
              type="button"
              className={`nav-item ${activeMenu === 'project_types' ? 'active' : ''}`}
              onClick={() => setActiveMenu('project_types')}
            >
              <div className="nav-item-content">
                <Settings2 size={16} />
                <span>Tipos de Projeto</span>
              </div>
              <span className="nav-badge">{projectTypes.length}</span>
            </button>

            <button
              type="button"
              className={`nav-item ${activeMenu === 'wo_types' ? 'active' : ''}`}
              onClick={() => setActiveMenu('wo_types')}
            >
              <div className="nav-item-content">
                <Settings2 size={16} />
                <span>Tipos de Ordem</span>
              </div>
              <span className="nav-badge">{workOrderTypes.length}</span>
            </button>

            <button
              type="button"
              className={`nav-item ${activeMenu === 'workflows' ? 'active' : ''}`}
              onClick={() => setActiveMenu('workflows')}
            >
              <div className="nav-item-content">
                <GitBranch size={16} />
                <span>Fluxos & Workflows</span>
              </div>
              <span className="nav-badge">{workflows.length}</span>
            </button>
          </nav>
        </aside>

        {/* ==================================================================== */}
        {/* 2. ÁREA DE TRABALHO PRINCIPAL (.content-right) */}
        {/* ==================================================================== */}
        <main className="content-right">
          {/* CABEÇALHO DO CONTEÚDO */}
          <div className="content-header">
            <div className="header-info">
              <div className="badge-module">
                <Briefcase size={12} />
                <span>Camada Operacional ERP</span>
              </div>
              <h1>
                {sectionMeta.icon}
                <span>{sectionMeta.title}</span>
              </h1>
              <p>{sectionMeta.description}</p>
            </div>

            <div className="header-actions">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => loadData(true)}
                disabled={refreshing}
                title="Atualizar dados"
              >
                <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
                <span>Atualizar</span>
              </button>

              {/* Botões Contextuais por Seção */}
              {activeMenu === 'dashboard' && (
                <>
                  <button
                    type="button"
                    className="btn btn-outline"
                    onClick={() => openNewIssue()}
                  >
                    <AlertTriangle size={14} color="#f43f5e" />
                    <span>Ocorrência</span>
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => openNewWorkOrder()}
                  >
                    <ClipboardList size={14} color="#f59e0b" />
                    <span>Nova OS</span>
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={openNewProject}
                  >
                    <Plus size={14} />
                    <span>Novo Projeto</span>
                  </button>
                </>
              )}

              {activeMenu === 'projects' && (
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={openNewProject}
                >
                  <Plus size={14} />
                  <span>Novo Projeto</span>
                </button>
              )}

              {activeMenu === 'work_orders' && (
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => openNewWorkOrder()}
                >
                  <Plus size={14} />
                  <span>Nova Ordem de Trabalho</span>
                </button>
              )}

              {(activeMenu === 'tasks' || activeMenu === 'kanban') && (
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => openNewTask()}
                >
                  <Plus size={14} />
                  <span>Nova Tarefa</span>
                </button>
              )}

              {activeMenu === 'issues' && (
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => openNewIssue()}
                >
                  <Plus size={14} />
                  <span>Registrar Ocorrência</span>
                </button>
              )}

              {activeMenu === 'project_types' && (
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={openNewProjectType}
                >
                  <Plus size={14} />
                  <span>Novo Tipo de Projeto</span>
                </button>
              )}

              {activeMenu === 'wo_types' && (
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={openNewWorkOrderType}
                >
                  <Plus size={14} />
                  <span>Novo Tipo de Ordem</span>
                </button>
              )}

              {activeMenu === 'workflows' && (
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={openNewWorkflow}
                >
                  <Plus size={14} />
                  <span>Novo Workflow</span>
                </button>
              )}
            </div>
          </div>

          {/* BANNER DE ERRO SE HOUVER */}
          {errorMessage && (
            <div style={{
              padding: '0.75rem 1rem',
              background: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid rgba(239, 68, 68, 0.25)',
              borderRadius: '8px',
              color: '#ef4444',
              fontSize: '0.85rem',
              fontWeight: 500
            }}>
              {errorMessage}
            </div>
          )}

          {/* ESTADO DE CARREGAMENTO */}
          {loading ? (
            <div style={{ padding: '4rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
              <RefreshCw size={28} className="animate-spin" style={{ margin: '0 auto 0.75rem auto', color: 'var(--accent-brand)' }} />
              <p>Carregando dados operacionais do ControlB...</p>
            </div>
          ) : (
            <>
              {/* -------------------------------------------------------------- */}
              {/* SEÇÃO 1: DASHBOARD OPERACIONAL */}
              {/* -------------------------------------------------------------- */}
              {activeMenu === 'dashboard' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                  {/* KPI Cards Operacionais */}
                  <section className="kpi-grid">
                    <div className="kpi-card">
                      <div className="kpi-icon pink">
                        <FolderKanban size={20} />
                      </div>
                      <div className="kpi-content">
                        <span className="kpi-value">{kpis.activeProjects}</span>
                        <span className="kpi-label">Projetos Ativos</span>
                      </div>
                    </div>

                    <div className="kpi-card">
                      <div className="kpi-icon amber">
                        <ClipboardList size={20} />
                      </div>
                      <div className="kpi-content">
                        <span className="kpi-value">{kpis.openWOs}</span>
                        <span className="kpi-label">Ordens de Serviço Abertas</span>
                      </div>
                    </div>

                    <div className="kpi-card">
                      <div className="kpi-icon blue">
                        <CheckSquare size={20} />
                      </div>
                      <div className="kpi-content">
                        <span className="kpi-value">{kpis.pendingTasks}</span>
                        <span className="kpi-label">Tarefas em Execução</span>
                      </div>
                    </div>

                    <div className="kpi-card">
                      <div className="kpi-icon rose">
                        <ShieldAlert size={20} />
                      </div>
                      <div className="kpi-content">
                        <span className="kpi-value">{kpis.criticalIssues}</span>
                        <span className="kpi-label">Ocorrências Críticas</span>
                      </div>
                    </div>

                    <div className="kpi-card">
                      <div className="kpi-icon emerald">
                        <DollarSign size={20} />
                      </div>
                      <div className="kpi-content">
                        <span className="kpi-value">
                          R$ {kpis.totalBudget.toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                        </span>
                        <span className="kpi-label">Orçamento Previsto</span>
                      </div>
                    </div>
                  </section>

                  {/* Quadros de Acompanhamento Executivo */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '1.25rem' }}>
                    {/* Projetos em Andamento Recentes */}
                    <div className="data-table-container" style={{ padding: '1.25rem' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                        <h3 style={{ fontSize: '0.95rem', fontWeight: 600, margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <FolderKanban size={16} color="var(--accent-brand)" />
                          <span>Projetos com Execução Prioritária</span>
                        </h3>
                        <button
                          type="button"
                          className="btn btn-outline"
                          style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                          onClick={() => setActiveMenu('projects')}
                        >
                          Ver Todos
                        </button>
                      </div>

                      {projects.length === 0 ? (
                        <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Nenhum projeto cadastrado no momento.</p>
                      ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                          {projects.slice(0, 5).map(proj => (
                            <div
                              key={proj.id}
                              onClick={() => handleSelectProject(proj)}
                              style={{
                                padding: '0.75rem',
                                background: 'var(--bg-surface-elevated)',
                                border: '1px solid var(--border-subtle)',
                                borderRadius: '8px',
                                cursor: 'pointer',
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                                transition: 'all 0.15s ease'
                              }}
                            >
                              <div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                  <span style={{ fontFamily: 'monospace', fontSize: '0.75rem', color: 'var(--accent-brand)', fontWeight: 700 }}>
                                    {proj.code}
                                  </span>
                                  <strong style={{ fontSize: '0.875rem' }}>{proj.name}</strong>
                                </div>
                                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
                                  Progresso: {proj.progress_percent}% • Orçamento: R$ {Number(proj.estimated_budget || 0).toLocaleString('pt-BR')}
                                </div>
                              </div>
                              <span className={`status-badge ${proj.status}`} style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem', borderRadius: '12px' }}>
                                {proj.status}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Ocorrências Recentes */}
                    <div className="data-table-container" style={{ padding: '1.25rem' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                        <h3 style={{ fontSize: '0.95rem', fontWeight: 600, margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <AlertTriangle size={16} color="#f43f5e" />
                          <span>Ocorrências & Bloqueios Recentes</span>
                        </h3>
                        <button
                          type="button"
                          className="btn btn-outline"
                          style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                          onClick={() => setActiveMenu('issues')}
                        >
                          Ver Todas
                        </button>
                      </div>

                      {issues.length === 0 ? (
                        <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Nenhum bloqueio ou ocorrência em aberto. Operação fluida!</p>
                      ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                          {issues.slice(0, 5).map(iss => (
                            <div
                              key={iss.id}
                              style={{
                                padding: '0.75rem',
                                background: 'var(--bg-surface-elevated)',
                                border: '1px solid var(--border-subtle)',
                                borderRadius: '8px',
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center'
                              }}
                            >
                              <div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                  <span style={{
                                    padding: '0.15rem 0.4rem',
                                    borderRadius: '4px',
                                    fontSize: '0.65rem',
                                    fontWeight: 700,
                                    background: iss.severity === 'CRITICAL' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(245, 158, 11, 0.2)',
                                    color: iss.severity === 'CRITICAL' ? '#fca5a5' : '#fcd34d'
                                  }}>
                                    {iss.severity}
                                  </span>
                                  <strong style={{ fontSize: '0.875rem' }}>{iss.title}</strong>
                                </div>
                                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
                                  Tipo: {iss.issue_type} • Status: {iss.status}
                                </div>
                              </div>
                              {!hasStatus(iss.status, 'RESOLVED', 'CLOSED') && (
                                <button
                                  type="button"
                                  className="btn btn-outline"
                                  style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }}
                                  onClick={() => setShowResolveIssueModal(iss)}
                                >
                                  Resolver
                                </button>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* -------------------------------------------------------------- */}
              {/* SEÇÃO 2: PROJETOS OPERACIONAIS */}
              {/* -------------------------------------------------------------- */}
              {activeMenu === 'projects' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                  <BulkActionsBar
                    selectedCount={projectSelection.selectedCount}
                    resourceName={{ singular: 'projeto', plural: 'projetos' }}
                    onClear={projectSelection.clearSelection}
                    onDelete={() => void runProjectsBulkAction(projectSelection.selectedIdList, 'Excluir', projectsService.deleteProject, projectSelection.clearSelection, 'projeto(s)')}
                    deleteLabel="Excluir selecionados"
                  />

                  <div className="filter-bar">
                    <div className="search-input-wrapper">
                      <Search size={15} />
                      <input
                        type="text"
                        placeholder="Buscar projeto por código ou nome..."
                        value={searchTerm}
                        onChange={e => setSearchTerm(e.target.value)}
                      />
                    </div>

                    <div className="filter-controls">
                      <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
                        <option value="ALL">Todos os Status</option>
                        <option value="DRAFT">Rascunho</option>
                        <option value="PLANNING">Planejamento</option>
                        <option value="IN_PROGRESS">Em Andamento</option>
                        <option value="ON_HOLD">Em Pausa</option>
                        <option value="COMPLETED">Concluído</option>
                        <option value="CANCELLED">Cancelado</option>
                      </select>

                      <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)}>
                        <option value="ALL">Todos os Tipos</option>
                        {projectTypes.map(pt => (
                          <option key={pt.id} value={pt.id}>{pt.name}</option>
                        ))}
                      </select>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', borderLeft: '1px solid var(--border-subtle)', paddingLeft: '0.6rem' }}>
                        <button
                          type="button"
                          className={`btn ${projectViewMode === 'table' ? 'btn-primary' : 'btn-outline'}`}
                          style={{ padding: '0.35rem 0.6rem', fontSize: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}
                          onClick={() => setProjectViewMode('table')}
                          title="Visualização em Lista / Tabela"
                        >
                          <TableIcon size={14} />
                          <span>Tabela</span>
                        </button>
                        <button
                          type="button"
                          className={`btn ${projectViewMode === 'grid' ? 'btn-primary' : 'btn-outline'}`}
                          style={{ padding: '0.35rem 0.6rem', fontSize: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}
                          onClick={() => setProjectViewMode('grid')}
                          title="Visualização em Grade / Cards"
                        >
                          <LayoutGrid size={14} />
                          <span>Cards</span>
                        </button>
                      </div>
                    </div>
                  </div>

                  {filteredProjects.length === 0 ? (
                    <div className="empty-state">
                      <FolderKanban size={48} />
                      <h3>Nenhum projeto encontrado</h3>
                      <p>Cadastre um novo projeto operacional para iniciar o controle de serviços e equipes.</p>
                      <button
                        type="button"
                        className="btn btn-primary"
                        onClick={openNewProject}
                      >
                        <Plus size={15} />
                        <span>Criar Primeiro Projeto</span>
                      </button>
                    </div>
                  ) : projectViewMode === 'table' ? (
                    <div className="data-table-container">
                      <table>
                        <thead>
                          <tr>
                            <th className="ui-selection-cell">
                              <input
                                className="ui-selection-checkbox"
                                type="checkbox"
                                aria-label="Selecionar todos os projetos"
                                checked={projectSelection.isAllSelected(filteredProjects)}
                                onChange={() => projectSelection.toggleSelectAll(filteredProjects)}
                              />
                            </th>
                            <th>Código</th>
                            <th>Nome do Projeto</th>
                            <th>Status</th>
                            <th>Prioridade</th>
                            <th>Orçamento</th>
                            <th>Progresso</th>
                            <th>Prazo</th>
                            <th style={{ textAlign: 'right' }}>Ações</th>
                          </tr>
                        </thead>
                        <tbody>
                          {filteredProjects.map(proj => (
                            <tr
                              key={proj.id}
                              className={`clickable-row ui-record-row ${projectSelection.isSelected(proj.id) ? 'ui-record-row--selected' : ''}`}
                              role="button"
                              tabIndex={0}
                              onClick={(e) => {
                                if (!(e.target as HTMLElement).closest('button, a, input, label, .btn-action-icon')) {
                                  handleEditProject(proj);
                                }
                              }}
                              onKeyDown={(e) => {
                                if (['Enter', ' '].includes(e.key)) {
                                  e.preventDefault();
                                  handleEditProject(proj);
                                }
                              }}
                            >
                              <td className="ui-selection-cell">
                                <input
                                  className="ui-selection-checkbox"
                                  type="checkbox"
                                  aria-label={`Selecionar projeto ${proj.name}`}
                                  checked={projectSelection.isSelected(proj.id)}
                                  onClick={e => e.stopPropagation()}
                                  onChange={() => projectSelection.toggleSelect(proj.id)}
                                />
                              </td>
                              <td style={{ fontFamily: 'monospace', fontWeight: 600, color: 'var(--accent-brand)' }}>
                                {proj.code}
                              </td>
                              <td>
                                <strong
                                  className="record-title-link"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleEditProject(proj);
                                  }}
                                >
                                  {proj.name}
                                </strong>
                                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '0.6rem', marginTop: '0.2rem' }}>
                                  {proj.customer_id && (
                                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', color: 'var(--text-muted)' }}>
                                      <Building size={11} /> {getCustomerName(proj.customer_id)}
                                    </span>
                                  )}
                                  {proj.manager_id && (
                                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', color: 'var(--text-muted)' }}>
                                      <UserIcon size={11} /> {getUserName(proj.manager_id)}
                                    </span>
                                  )}
                                </div>
                                {proj.description && (
                                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>
                                    {proj.description}
                                  </div>
                                )}
                              </td>
                              <td>
                                <span className={`status-badge ${proj.status}`} style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem', borderRadius: '12px' }}>
                                  {proj.status}
                                </span>
                              </td>
                              <td>
                                <span style={{
                                  padding: '0.2rem 0.5rem',
                                  borderRadius: '4px',
                                  fontSize: '0.7rem',
                                  fontWeight: 700,
                                  background: 'var(--bg-surface-elevated)',
                                  border: '1px solid var(--border-subtle)',
                                  color: 'var(--text-secondary)'
                                }}>
                                  {proj.priority}
                                </span>
                              </td>
                              <td>R$ {Number(proj.estimated_budget || 0).toLocaleString('pt-BR')}</td>
                              <td>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                  <div style={{ width: '60px', height: '6px', background: 'var(--bg-surface-elevated)', borderRadius: '3px', overflow: 'hidden' }}>
                                    <div style={{ width: `${proj.progress_percent || 0}%`, height: '100%', background: 'var(--accent-brand)' }} />
                                  </div>
                                  <span style={{ fontSize: '0.75rem' }}>{proj.progress_percent || 0}%</span>
                                </div>
                              </td>
                              <td>{proj.planned_end_date ? new Date(proj.planned_end_date).toLocaleDateString('pt-BR') : '-'}</td>
                              <td>
                                <div style={{ display: 'flex', gap: '0.4rem', justifyContent: 'flex-end', alignItems: 'center' }}>
                                  <button
                                    type="button"
                                    className="btn btn-outline"
                                    style={{ padding: '0.25rem 0.55rem', fontSize: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleSelectProject(proj);
                                    }}
                                  >
                                    <Eye size={12} />
                                    <span>Detalhes</span>
                                  </button>
                                  <button
                                    type="button"
                                    className="btn-action-icon"
                                    title="Editar Projeto"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleEditProject(proj);
                                    }}
                                  >
                                    <Pencil size={14} />
                                  </button>
                                  <button
                                    type="button"
                                    className="btn-action-icon delete"
                                    title="Excluir Projeto"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleDeleteProject(proj);
                                    }}
                                  >
                                    <Trash2 size={14} />
                                  </button>
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="projects-cards-grid">
                      {filteredProjects.map(proj => (
                        <div
                          key={proj.id}
                          className={`project-card clickable-row ui-record-row ${projectSelection.isSelected(proj.id) ? 'selected' : ''}`}
                          role="button"
                          tabIndex={0}
                          onClick={(e) => {
                            if (!(e.target as HTMLElement).closest('button, a, input, label, .btn-action-icon')) {
                              handleEditProject(proj);
                            }
                          }}
                          onKeyDown={(e) => {
                            if (['Enter', ' '].includes(e.key)) {
                              e.preventDefault();
                              handleEditProject(proj);
                            }
                          }}
                          style={{ position: 'relative', cursor: 'pointer' }}
                        >
                          <div className="card-accent-bar" />
                          <div className="card-header-row" style={{ alignItems: 'center' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                              <input
                                className="ui-selection-checkbox"
                                type="checkbox"
                                aria-label={`Selecionar projeto ${proj.name}`}
                                checked={projectSelection.isSelected(proj.id)}
                                onClick={e => e.stopPropagation()}
                                onChange={() => projectSelection.toggleSelect(proj.id)}
                              />
                              <span className="code-tag">{proj.code}</span>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                              <span className={`status-badge ${proj.status}`}>
                                {proj.status}
                              </span>
                              <button
                                type="button"
                                className="btn-action-icon"
                                title="Editar Projeto"
                                onClick={e => {
                                  e.stopPropagation();
                                  handleEditProject(proj);
                                }}
                              >
                                <Pencil size={13} />
                              </button>
                              <button
                                type="button"
                                className="btn-action-icon delete"
                                title="Excluir Projeto"
                                onClick={e => {
                                  e.stopPropagation();
                                  handleDeleteProject(proj);
                                }}
                              >
                                <Trash2 size={13} />
                              </button>
                            </div>
                          </div>

                          <h3
                            className="project-title record-title-link"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleEditProject(proj);
                            }}
                          >
                            {proj.name}
                          </h3>

                          {proj.customer_id && (
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.35rem', marginBottom: '0.35rem' }}>
                              <Building size={12} />
                              <span>{getCustomerName(proj.customer_id)}</span>
                            </div>
                          )}

                          {proj.description && <p className="project-desc">{proj.description}</p>}

                          <div className="progress-section">
                            <div className="progress-labels">
                              <span>Progresso da Operação</span>
                              <span className="percent">{proj.progress_percent}%</span>
                            </div>
                            <div className="progress-track">
                              <div className="progress-fill" style={{ width: `${proj.progress_percent}%` }} />
                            </div>
                          </div>

                          <div className="meta-grid">
                            <div className="meta-item">
                              <DollarSign size={13} />
                              <span>R$ {Number(proj.estimated_budget || 0).toLocaleString('pt-BR')}</span>
                            </div>
                            <div className="meta-item">
                              <Calendar size={13} />
                              <span>{proj.planned_end_date ? new Date(proj.planned_end_date).toLocaleDateString('pt-BR') : 'Sem prazo'}</span>
                            </div>
                            {proj.manager_id && (
                              <div className="meta-item" style={{ gridColumn: 'span 2' }}>
                                <UserIcon size={12} />
                                <span>Gerente: {getUserName(proj.manager_id)}</span>
                              </div>
                            )}
                          </div>

                          <div style={{ marginTop: '0.75rem', display: 'flex', justifyContent: 'flex-end', borderTop: '1px solid var(--border-subtle)', paddingTop: '0.5rem' }}>
                            <button
                              type="button"
                              className="btn btn-outline"
                              style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}
                              onClick={(e) => {
                                e.stopPropagation();
                                handleSelectProject(proj);
                              }}
                            >
                              <Eye size={12} />
                              <span>Ver Detalhes</span>
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* -------------------------------------------------------------- */}
              {/* SEÇÃO 3: ORDENS DE TRABALHO & SERVIÇO */}
              {/* -------------------------------------------------------------- */}
              {activeMenu === 'work_orders' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                  <BulkActionsBar
                    selectedCount={workOrderSelection.selectedCount}
                    resourceName={{ singular: 'ordem de trabalho', plural: 'ordens de trabalho' }}
                    onClear={workOrderSelection.clearSelection}
                    onDelete={() => void runProjectsBulkAction(workOrderSelection.selectedIdList, 'Excluir', projectsService.deleteWorkOrder, workOrderSelection.clearSelection, 'ordem(ns)')}
                    deleteLabel="Excluir selecionadas"
                  />

                  {workOrders.length === 0 ? (
                    <div className="empty-state">
                      <ClipboardList size={48} />
                      <h3>Nenhuma ordem de trabalho cadastrada</h3>
                      <p>Abra uma ordem de serviço para despachar atividades para equipes em campo ou produção.</p>
                      <button
                        type="button"
                        className="btn btn-primary"
                        onClick={() => openNewWorkOrder()}
                      >
                        <Plus size={15} />
                        <span>Criar Primeira OS</span>
                      </button>
                    </div>
                  ) : (
                    <div className="data-table-container">
                      <table>
                        <thead>
                          <tr>
                            <th className="ui-selection-cell">
                              <input
                                className="ui-selection-checkbox"
                                type="checkbox"
                                aria-label="Selecionar todas as OSs"
                                checked={workOrderSelection.isAllSelected(workOrders)}
                                onChange={() => workOrderSelection.toggleSelectAll(workOrders)}
                              />
                            </th>
                            <th>Código</th>
                            <th>Título da OS</th>
                            <th>Prioridade</th>
                            <th>Status</th>
                            <th>Horas Estimadas</th>
                            <th>Ações Rápidas</th>
                          </tr>
                        </thead>
                        <tbody>
                          {workOrders.map(wo => (
                            <tr
                              key={wo.id}
                              className={`clickable-row ui-record-row ${workOrderSelection.isSelected(wo.id) ? 'ui-record-row--selected' : ''}`}
                              role="button"
                              tabIndex={0}
                              onClick={(e) => {
                                if (!(e.target as HTMLElement).closest('button, a, input, label, .btn-action-icon')) {
                                  handleEditWorkOrder(wo);
                                }
                              }}
                              onKeyDown={(e) => {
                                if (['Enter', ' '].includes(e.key)) {
                                  e.preventDefault();
                                  handleEditWorkOrder(wo);
                                }
                              }}
                            >
                              <td className="ui-selection-cell">
                                <input
                                  className="ui-selection-checkbox"
                                  type="checkbox"
                                  aria-label={`Selecionar OS ${wo.code}`}
                                  checked={workOrderSelection.isSelected(wo.id)}
                                  onClick={e => e.stopPropagation()}
                                  onChange={() => workOrderSelection.toggleSelect(wo.id)}
                                />
                              </td>
                              <td style={{ fontFamily: 'monospace', fontWeight: 600, color: 'var(--accent-brand)' }}>
                                {wo.code}
                              </td>
                              <td>
                                <strong
                                  className="record-title-link"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleEditWorkOrder(wo);
                                  }}
                                >
                                  {wo.title}
                                </strong>
                                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '0.6rem', marginTop: '0.2rem' }}>
                                  {wo.responsible_id && (
                                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', color: 'var(--text-muted)' }}>
                                      <UserIcon size={11} /> {getUserName(wo.responsible_id)}
                                    </span>
                                  )}
                                  {wo.team_id && (
                                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', color: 'var(--text-muted)' }}>
                                      <Users size={11} /> {getTeamName(wo.team_id)}
                                    </span>
                                  )}
                                  {wo.address && (
                                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', color: 'var(--text-muted)' }}>
                                      <MapPin size={11} /> {wo.address}
                                    </span>
                                  )}
                                </div>
                                {wo.description && (
                                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>
                                    {wo.description}
                                  </div>
                                )}
                              </td>
                              <td>
                                <span style={{
                                  padding: '0.2rem 0.5rem',
                                  borderRadius: '4px',
                                  fontSize: '0.7rem',
                                  fontWeight: 700,
                                  background: 'var(--bg-surface-elevated)',
                                  border: '1px solid var(--border-subtle)',
                                  color: 'var(--text-secondary)'
                                }}>
                                  {wo.priority}
                                </span>
                              </td>
                              <td>
                                <span className={`status-badge ${wo.status}`} style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem', borderRadius: '12px' }}>
                                  {wo.status}
                                </span>
                              </td>
                              <td>{wo.estimated_hours}h</td>
                              <td>
                                <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
                                  {hasStatus(wo.status, 'DRAFT') && (
                                    <button
                                      type="button"
                                      className="btn btn-outline"
                                      style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }}
                                      onClick={() => handleWorkOrderStatusChange(wo.id, 'OPEN')}
                                    >
                                      Abrir OS
                                    </button>
                                  )}
                                  {hasStatus(wo.status, 'OPEN') && (
                                    <button
                                      type="button"
                                      className="btn btn-outline"
                                      style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }}
                                      onClick={() => handleWorkOrderStatusChange(wo.id, 'IN_PROGRESS')}
                                    >
                                      Iniciar
                                    </button>
                                  )}
                                  {!hasStatus(wo.status, 'COMPLETED', 'CANCELLED') && (
                                    <button
                                      type="button"
                                      className="btn btn-secondary"
                                      style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem', borderColor: '#10b981', color: '#34d399' }}
                                      onClick={() => handleWorkOrderStatusChange(wo.id, 'COMPLETED')}
                                    >
                                      Concluir
                                    </button>
                                  )}
                                  <button
                                    type="button"
                                    className="btn-action-icon"
                                    title="Editar Ordem de Trabalho"
                                    onClick={() => handleEditWorkOrder(wo)}
                                  >
                                    <Pencil size={14} />
                                  </button>
                                  <button
                                    type="button"
                                    className="btn-action-icon delete"
                                    title="Excluir Ordem de Trabalho"
                                    onClick={() => handleDeleteWorkOrder(wo)}
                                  >
                                    <Trash2 size={14} />
                                  </button>
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {/* -------------------------------------------------------------- */}
              {/* SEÇÃO 4: TAREFAS & ATIVIDADES */}
              {/* -------------------------------------------------------------- */}
              {activeMenu === 'tasks' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                  <BulkActionsBar
                    selectedCount={taskSelection.selectedCount}
                    resourceName={{ singular: 'tarefa', plural: 'tarefas' }}
                    onClear={taskSelection.clearSelection}
                    onDelete={() => void runProjectsBulkAction(taskSelection.selectedIdList, 'Excluir', projectsService.deleteTask, taskSelection.clearSelection, 'tarefa(s)')}
                    deleteLabel="Excluir selecionadas"
                  />

                  {tasks.length === 0 ? (
                    <div className="empty-state">
                      <CheckSquare size={48} />
                      <h3>Nenhuma tarefa cadastrada</h3>
                      <p>Cadastre tarefas operacionais para acompanhar prazos e horas executadas.</p>
                      <button
                        type="button"
                        className="btn btn-primary"
                        onClick={() => openNewTask()}
                      >
                        <Plus size={15} />
                        <span>Criar Primeira Tarefa</span>
                      </button>
                    </div>
                  ) : (
                    <div className="data-table-container">
                      <table>
                        <thead>
                          <tr>
                            <th className="ui-selection-cell">
                              <input
                                className="ui-selection-checkbox"
                                type="checkbox"
                                aria-label="Selecionar todas as tarefas"
                                checked={taskSelection.isAllSelected(tasks)}
                                onChange={() => taskSelection.toggleSelectAll(tasks)}
                              />
                            </th>
                            <th>Código</th>
                            <th>Título da Tarefa</th>
                            <th>Prioridade</th>
                            <th>Status</th>
                            <th>Horas</th>
                            <th>Prazo</th>
                            <th>Ações</th>
                          </tr>
                        </thead>
                        <tbody>
                          {tasks.map(task => (
                            <tr
                              key={task.id}
                              className={`clickable-row ui-record-row ${taskSelection.isSelected(task.id) ? 'ui-record-row--selected' : ''}`}
                              role="button"
                              tabIndex={0}
                              onClick={(e) => {
                                if (!(e.target as HTMLElement).closest('button, a, input, label, .btn-action-icon')) {
                                  handleEditTask(task);
                                }
                              }}
                              onKeyDown={(e) => {
                                if (['Enter', ' '].includes(e.key)) {
                                  e.preventDefault();
                                  handleEditTask(task);
                                }
                              }}
                            >
                              <td className="ui-selection-cell">
                                <input
                                  className="ui-selection-checkbox"
                                  type="checkbox"
                                  aria-label={`Selecionar tarefa ${task.title}`}
                                  checked={taskSelection.isSelected(task.id)}
                                  onClick={e => e.stopPropagation()}
                                  onChange={() => taskSelection.toggleSelect(task.id)}
                                />
                              </td>
                              <td style={{ fontFamily: 'monospace', fontWeight: 600, color: 'var(--accent-brand)' }}>
                                TSK-{task.id.slice(0, 6).toUpperCase()}
                              </td>
                              <td>
                                <strong
                                  className="record-title-link"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleEditTask(task);
                                  }}
                                >
                                  {task.title}
                                </strong>
                                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.2rem' }}>
                                  {task.assignments?.[0]?.user_id && (
                                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', color: 'var(--text-muted)' }}>
                                      <UserIcon size={11} /> {getUserName(task.assignments[0].user_id)}
                                    </span>
                                  )}
                                </div>
                                {task.description && (
                                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>
                                    {task.description}
                                  </div>
                                )}
                              </td>
                              <td>
                                <span className={`task-priority-tag ${task.priority}`}>
                                  {task.priority}
                                </span>
                              </td>
                              <td>
                                <span className={`status-badge ${task.status}`}>
                                  {task.status}
                                </span>
                              </td>
                              <td>{task.estimated_hours}h</td>
                              <td>{task.due_date ? new Date(task.due_date).toLocaleDateString('pt-BR') : '-'}</td>
                              <td>
                                <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
                                  {!hasStatus(task.status, 'DONE') && (
                                    <button
                                      type="button"
                                      className="btn btn-secondary"
                                      style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem', borderColor: '#10b981', color: '#10b981' }}
                                      onClick={() => handleTaskStatusChange(task.id, 'DONE')}
                                    >
                                      Concluir
                                    </button>
                                  )}
                                  <button
                                    type="button"
                                    className="btn-action-icon"
                                    title="Editar Tarefa"
                                    onClick={() => handleEditTask(task)}
                                  >
                                    <Pencil size={14} />
                                  </button>
                                  <button
                                    type="button"
                                    className="btn-action-icon delete"
                                    title="Excluir Tarefa"
                                    onClick={() => handleDeleteTask(task)}
                                  >
                                    <Trash2 size={14} />
                                  </button>
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {/* -------------------------------------------------------------- */}
              {/* SEÇÃO 5: QUADRO KANBAN */}
              {/* -------------------------------------------------------------- */}
              {activeMenu === 'kanban' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                  {/* BARRA SUPERIOR DO KANBAN */}
                  <div className="filter-bar" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                        <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Fluxo / Workflow:</span>
                        {workflows.length > 0 ? (
                          <select
                            value={selectedWorkflowId || activeWorkflow?.id || ''}
                            onChange={e => setSelectedWorkflowId(e.target.value)}
                            style={{ padding: '0.35rem 0.65rem', borderRadius: '6px', fontSize: '0.8rem' }}
                          >
                            {workflows.filter((workflow) => workflow.is_active).map(wf => (
                              <option key={wf.id} value={wf.id}>{wf.name} ({wf.stages?.length || 0} etapas)</option>
                            ))}
                          </select>
                        ) : (
                          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Nenhum fluxo cadastrado na organização</span>
                        )}
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', background: 'var(--bg-surface-elevated)', borderRadius: '6px', padding: '0.2rem', border: '1px solid var(--border-subtle)' }}>
                        <button
                          type="button"
                          className={`btn ${kanbanMode === 'projects' ? 'btn-primary' : 'btn-outline'}`}
                          style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem', border: 'none' }}
                          onClick={() => setKanbanMode('projects')}
                        >
                          <FolderKanban size={13} />
                          <span>Projetos ({projects.length})</span>
                        </button>
                        <button
                          type="button"
                          className={`btn ${kanbanMode === 'tasks' ? 'btn-primary' : 'btn-outline'}`}
                          style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem', border: 'none' }}
                          onClick={() => setKanbanMode('tasks')}
                        >
                          <CheckSquare size={13} />
                          <span>Tarefas ({tasks.length})</span>
                        </button>
                      </div>
                    </div>

                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      {(!workflows || workflows.length === 0) && (
                        <button
                          type="button"
                          className="btn btn-secondary"
                          onClick={handleInitDefaultWorkflow}
                        >
                          <GitBranch size={14} />
                          <span>Inicializar Fluxo Padrão</span>
                        </button>
                      )}
                      <button
                        type="button"
                        className="btn btn-primary"
                        onClick={() => {
                          setStageForm({
                            name: '',
                            color: '#6366f1',
                            position: (activeWorkflow?.stages?.length || 0) + 1,
                            is_initial: (activeWorkflow?.stages?.length || 0) === 0,
                            is_terminal: false,
                            description: ''
                          });
                          setShowStageModal(true);
                        }}
                      >
                        <Plus size={14} />
                        <span>Adicionar Estágio</span>
                      </button>
                    </div>
                  </div>

                  <div className="kanban-drag-guide">
                    <GripVertical size={14} />
                    <span>Arraste os cards entre as colunas. Para reorganizar o fluxo, arraste o cabeçalho de uma etapa.</span>
                  </div>

                  {/* TABULEIRO KANBAN */}
                  <div className="kanban-board">
                    {kanbanMode === 'projects' ? (
                      // VISUALIZAÇÃO POR PROJETOS E ESTÁGIOS DA ORGANIZAÇÃO
                      activeWorkflow && activeWorkflow.stages && activeWorkflow.stages.length > 0 ? (
                        <>
                          {[...(activeWorkflow.stages || [])]
                            .sort((a, b) => a.position - b.position)
                            .map((stage, stageIdx, sortedStages) => {
                              const stageProjects = projects.filter(p =>
                                p.current_stage?.id === stage.id ||
                                (!p.current_stage?.id && (stage.is_initial || stageIdx === 0))
                              );

                              return (
                                <div
                                  key={stage.id}
                                  className={`kanban-column ${kanbanDropTarget === `stage:${stage.id}` ? 'is-drop-target' : ''}`}
                                  onDragOver={e => {
                                    if (!draggedProjectId && !draggedStageId) return;
                                    e.preventDefault();
                                    e.dataTransfer.dropEffect = 'move';
                                  }}
                                  onDragEnter={() => {
                                    if (draggedProjectId || draggedStageId) setKanbanDropTarget(`stage:${stage.id}`);
                                  }}
                                  onDragLeave={e => {
                                    if (!e.currentTarget.contains(e.relatedTarget as Node)) setKanbanDropTarget(null);
                                  }}
                                  onDrop={e => {
                                    e.preventDefault();
                                    if (draggedStageId) {
                                      void handleReorderStages(draggedStageId, stage.id);
                                    } else if (draggedProjectId) {
                                      void handleMoveProjectStage(draggedProjectId, stage.id);
                                      setDraggedProjectId(null);
                                      setKanbanDropTarget(null);
                                    }
                                  }}
                                >
                                  <div
                                    className={`col-header project-stage-header ${draggedStageId === stage.id ? 'is-dragging' : ''}`}
                                    draggable
                                    title="Arraste para reordenar esta etapa"
                                    onDragStart={e => {
                                      e.stopPropagation();
                                      e.dataTransfer.effectAllowed = 'move';
                                      e.dataTransfer.setData('text/plain', stage.id);
                                      setDraggedStageId(stage.id);
                                      setDraggedProjectId(null);
                                    }}
                                    onDragEnd={() => {
                                      setDraggedStageId(null);
                                      setKanbanDropTarget(null);
                                    }}
                                  >
                                    <div className="col-title">
                                      <GripVertical className="stage-drag-handle" size={14} />
                                      <span
                                        className="dot"
                                        style={{ backgroundColor: stage.color || '#6366f1' }}
                                      />
                                      <span>{stage.name}</span>
                                      {stage.is_initial && (
                                        <span style={{ fontSize: '0.62rem', background: 'rgba(59, 130, 246, 0.15)', color: '#60a5fa', padding: '0.1rem 0.35rem', borderRadius: '4px', fontWeight: 600 }}>
                                          Inicial
                                        </span>
                                      )}
                                      {stage.is_terminal && (
                                        <span style={{ fontSize: '0.62rem', background: 'rgba(16, 185, 129, 0.15)', color: '#34d399', padding: '0.1rem 0.35rem', borderRadius: '4px', fontWeight: 600 }}>
                                          Final
                                        </span>
                                      )}
                                    </div>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                                      <span className="col-count">{stageProjects.length}</span>
                                      <button
                                        type="button"
                                        className="btn-action-icon delete"
                                        style={{ width: '22px', height: '22px', padding: 0 }}
                                        title={`Excluir etapa ${stage.name}`}
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          handleDeleteStage(stage.id, stage.name);
                                        }}
                                      >
                                        <Trash2 size={12} />
                                      </button>
                                    </div>
                                  </div>

                                  <div className="col-cards">
                                    {stageProjects.length === 0 ? (
                                      <div style={{ padding: '1.5rem 0.5rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                                        Nenhum projeto nesta etapa
                                      </div>
                                    ) : (
                                      stageProjects.map(proj => (
                                        <div
                                          key={proj.id}
                                          className={`kanban-project-card clickable-row ${draggedProjectId === proj.id ? 'is-dragging' : ''}`}
                                          draggable
                                          onClick={() => handleEditProject(proj)}
                                          onDragStart={e => {
                                            e.stopPropagation();
                                            e.dataTransfer.effectAllowed = 'move';
                                            e.dataTransfer.setData('text/plain', proj.id);
                                            setDraggedProjectId(proj.id);
                                            setDraggedStageId(null);
                                          }}
                                          onDragEnd={() => {
                                            setDraggedProjectId(null);
                                            setKanbanDropTarget(null);
                                          }}
                                        >
                                          <div className="project-card-header">
                                            <span className="code-pill">{proj.code}</span>
                                            <span className={`priority-badge ${proj.priority}`}>
                                              {proj.priority}
                                            </span>
                                          </div>

                                          <h4 className="project-card-title">{proj.name}</h4>

                                          <div className="project-progress-mini">
                                            <div className="progress-mini-bar">
                                              <div
                                                className="fill"
                                                style={{ width: `${proj.progress_percent}%` }}
                                              />
                                            </div>
                                            <div className="progress-mini-text">
                                              <span>Progresso</span>
                                              <span>{proj.progress_percent}%</span>
                                            </div>
                                          </div>

                                          <div className="project-card-footer">
                                            <span className="budget-tag">
                                              R$ {Number(proj.estimated_budget || 0).toLocaleString('pt-BR')}
                                            </span>
                                            <div className="card-actions-nav" onClick={e => e.stopPropagation()}>
                                              {stageIdx > 0 && (
                                                <button
                                                  type="button"
                                                  title={`Retroceder para ${sortedStages[stageIdx - 1].name}`}
                                                  onClick={() => handleMoveProjectStage(proj.id, sortedStages[stageIdx - 1].id)}
                                                >
                                                  ←
                                                </button>
                                              )}
                                              {stageIdx < sortedStages.length - 1 && (
                                                <button
                                                  type="button"
                                                  title={`Avançar para ${sortedStages[stageIdx + 1].name}`}
                                                  onClick={() => handleMoveProjectStage(proj.id, sortedStages[stageIdx + 1].id)}
                                                >
                                                  →
                                                </button>
                                              )}
                                            </div>
                                          </div>
                                        </div>
                                      ))
                                    )}
                                  </div>
                                </div>
                              );
                            })}

                          {/* COLUNA PONTILHADA PARA CRIAR NOVO ESTÁGIO */}
                          <div
                            className="kanban-add-column"
                            onClick={() => {
                              setStageForm({
                                name: '',
                                color: '#6366f1',
                                position: (activeWorkflow?.stages?.length || 0) + 1,
                                is_initial: false,
                                is_terminal: false,
                                description: ''
                              });
                              setShowStageModal(true);
                            }}
                          >
                            <div className="add-icon-wrap">
                              <Plus size={22} />
                            </div>
                            <span>Adicionar Estágio</span>
                            <p>Personalizar as etapas do fluxo da sua organização</p>
                          </div>
                        </>
                      ) : (
                        <div className="empty-state" style={{ margin: '2rem auto', maxWidth: '500px' }}>
                          <FolderKanban size={48} />
                          <h3>Nenhum estágio configurado</h3>
                          <p>Crie os estágios personalizados para a sua organização ou inicialize o fluxo padrão de projetos com 1 clique.</p>
                          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
                            <button type="button" className="btn btn-secondary" onClick={handleInitDefaultWorkflow}>
                              <GitBranch size={14} />
                              <span>Inicializar Fluxo Padrão</span>
                            </button>
                            <button
                              type="button"
                              className="btn btn-primary"
                              onClick={() => {
                                setStageForm({
                                  name: '',
                                  color: '#6366f1',
                                  position: 1,
                                  is_initial: true,
                                  is_terminal: false,
                                  description: ''
                                });
                                setShowStageModal(true);
                              }}
                            >
                              <Plus size={14} />
                              <span>Criar Primeiro Estágio</span>
                            </button>
                          </div>
                        </div>
                      )
                    ) : (
                      // VISUALIZAÇÃO POR TAREFAS
                      (['TODO', 'IN_PROGRESS', 'REVIEW', 'BLOCKED', 'DONE'] as TaskStatus[]).map(colStatus => {
                        const colTasks = tasks.filter(t => {
                          const normalizedStatus = String(t.status).toUpperCase();
                          return (normalizedStatus === 'IN_REVIEW' ? 'REVIEW' : normalizedStatus) === colStatus;
                        });
                        const colLabels: Record<TaskStatus, { title: string; dot: string }> = {
                          TODO: { title: 'A Fazer', dot: 'todo' },
                          IN_PROGRESS: { title: 'Em Execução', dot: 'inprogress' },
                          REVIEW: { title: 'Revisão / Inspeção', dot: 'review' },
                          BLOCKED: { title: 'Impedidas / Bloqueadas', dot: 'blocked' },
                          DONE: { title: 'Concluídas', dot: 'done' },
                          CANCELLED: { title: 'Canceladas', dot: 'todo' }
                        };

                        return (
                          <div
                            key={colStatus}
                            className={`kanban-column ${kanbanDropTarget === `task:${colStatus}` ? 'is-drop-target' : ''}`}
                            onDragOver={e => {
                              if (!draggedTaskId) return;
                              e.preventDefault();
                              e.dataTransfer.dropEffect = 'move';
                            }}
                            onDragEnter={() => {
                              if (draggedTaskId) setKanbanDropTarget(`task:${colStatus}`);
                            }}
                            onDragLeave={e => {
                              if (!e.currentTarget.contains(e.relatedTarget as Node)) setKanbanDropTarget(null);
                            }}
                            onDrop={e => {
                              e.preventDefault();
                              if (draggedTaskId) void handleTaskStatusChange(draggedTaskId, colStatus);
                              setDraggedTaskId(null);
                              setKanbanDropTarget(null);
                            }}
                          >
                            <div className="col-header">
                              <div className="col-title">
                                <span className={`dot ${colLabels[colStatus].dot}`} />
                                <span>{colLabels[colStatus].title}</span>
                              </div>
                              <span className="col-count">{colTasks.length}</span>
                            </div>

                            <div className="col-cards">
                              {colTasks.map(task => (
                                <div
                                  key={task.id}
                                  className={`kanban-task-card clickable-row ${draggedTaskId === task.id ? 'is-dragging' : ''}`}
                                  draggable
                                  onClick={() => handleEditTask(task)}
                                  onDragStart={e => {
                                    e.stopPropagation();
                                    e.dataTransfer.effectAllowed = 'move';
                                    e.dataTransfer.setData('text/plain', task.id);
                                    setDraggedTaskId(task.id);
                                  }}
                                  onDragEnd={() => {
                                    setDraggedTaskId(null);
                                    setKanbanDropTarget(null);
                                  }}
                                >
                                  <span className={`task-priority-tag ${task.priority}`}>
                                    {task.priority}
                                  </span>
                                  <h4 className="task-title">{task.title}</h4>
                                  {task.description && (
                                    <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', margin: 0 }}>
                                      {task.description}
                                    </p>
                                  )}
                                  <div className="task-footer">
                                    <span className="task-hours">
                                      <Clock size={12} />
                                      <span>{task.estimated_hours}h</span>
                                    </span>
                                    <div className="task-actions" onClick={e => e.stopPropagation()}>
                                      {colStatus !== 'IN_PROGRESS' && colStatus !== 'DONE' && (
                                        <button
                                          type="button"
                                          title="Mover para Em Execução"
                                          onClick={() => handleTaskStatusChange(task.id, 'IN_PROGRESS')}
                                        >
                                          <ArrowRight size={14} />
                                        </button>
                                      )}
                                      {colStatus !== 'DONE' && (
                                        <button
                                          type="button"
                                          title="Concluir Tarefa"
                                          onClick={() => handleTaskStatusChange(task.id, 'DONE')}
                                        >
                                          <Check size={14} />
                                        </button>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              )}

              {/* -------------------------------------------------------------- */}
              {/* SEÇÃO 6: PENDÊNCIAS & OCORRÊNCIAS */}
              {/* -------------------------------------------------------------- */}
              {activeMenu === 'issues' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                  <BulkActionsBar
                    selectedCount={issueSelection.selectedCount}
                    resourceName={{ singular: 'ocorrência', plural: 'ocorrências' }}
                    onClear={issueSelection.clearSelection}
                    onDelete={() => void runProjectsBulkAction(issueSelection.selectedIdList, 'Excluir', projectsService.deleteIssue, issueSelection.clearSelection, 'ocorrência(s)')}
                    deleteLabel="Excluir selecionadas"
                  />

                  {issues.length === 0 ? (
                    <div className="empty-state">
                      <CheckCircle2 size={48} color="#10b981" />
                      <h3>Nenhuma ocorrência ou bloqueio</h3>
                      <p>Todas as operações estão correndo dentro do planejado, sem impedimentos registrados.</p>
                      <button
                        type="button"
                        className="btn btn-primary"
                        onClick={() => openNewIssue()}
                      >
                        <Plus size={15} />
                        <span>Registrar Ocorrência</span>
                      </button>
                    </div>
                  ) : (
                    <div className="data-table-container">
                      <table>
                        <thead>
                          <tr>
                            <th className="ui-selection-cell">
                              <input
                                className="ui-selection-checkbox"
                                type="checkbox"
                                aria-label="Selecionar todas as ocorrências"
                                checked={issueSelection.isAllSelected(issues)}
                                onChange={() => issueSelection.toggleSelectAll(issues)}
                              />
                            </th>
                            <th>Código</th>
                            <th>Título / Descrição</th>
                            <th>Tipo</th>
                            <th>Gravidade</th>
                            <th>Impacto</th>
                            <th>Status</th>
                            <th>Ações</th>
                          </tr>
                        </thead>
                        <tbody>
                          {issues.map(iss => (
                            <tr
                              key={iss.id}
                              className={`clickable-row ui-record-row ${issueSelection.isSelected(iss.id) ? 'ui-record-row--selected' : ''}`}
                              role="button"
                              tabIndex={0}
                              onClick={(e) => {
                                if (!(e.target as HTMLElement).closest('button, a, input, label, .btn-action-icon')) {
                                  handleEditIssue(iss);
                                }
                              }}
                              onKeyDown={(e) => {
                                if (['Enter', ' '].includes(e.key)) {
                                  e.preventDefault();
                                  handleEditIssue(iss);
                                }
                              }}
                            >
                              <td className="ui-selection-cell">
                                <input
                                  className="ui-selection-checkbox"
                                  type="checkbox"
                                  aria-label={`Selecionar ocorrência ${iss.title}`}
                                  checked={issueSelection.isSelected(iss.id)}
                                  onClick={e => e.stopPropagation()}
                                  onChange={() => issueSelection.toggleSelect(iss.id)}
                                />
                              </td>
                              <td style={{ fontFamily: 'monospace', fontWeight: 600, color: '#f43f5e' }}>
                                {iss.issue_number || iss.code}
                              </td>
                              <td>
                                <strong
                                  className="record-title-link"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleEditIssue(iss);
                                  }}
                                >
                                  {iss.title}
                                </strong>
                                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                                  {iss.description}
                                </div>
                              </td>
                              <td>{iss.issue_type}</td>
                              <td>
                                <span style={{
                                  padding: '0.2rem 0.5rem',
                                  borderRadius: '4px',
                                  fontSize: '0.7rem',
                                  fontWeight: 700,
                                  background: iss.severity === 'CRITICAL' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(245, 158, 11, 0.2)',
                                  color: iss.severity === 'CRITICAL' ? '#fca5a5' : '#fcd34d'
                                }}>
                                  {iss.severity}
                                </span>
                              </td>
                              <td>
                                <div style={{ fontSize: '0.75rem' }}>
                                  +{iss.impact_days} dias • R$ {Number(iss.impact_cost || 0).toLocaleString('pt-BR')}
                                </div>
                              </td>
                              <td>
                                <span style={{
                                  padding: '0.2rem 0.5rem',
                                  borderRadius: '12px',
                                  fontSize: '0.7rem',
                                  fontWeight: 600,
                                  background: hasStatus(iss.status, 'RESOLVED') ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                                  color: hasStatus(iss.status, 'RESOLVED') ? '#34d399' : '#fca5a5'
                                }}>
                                  {iss.status}
                                </span>
                              </td>
                              <td>
                                <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
                                  {!hasStatus(iss.status, 'RESOLVED', 'CLOSED') && (
                                    <button
                                      type="button"
                                      className="btn btn-secondary"
                                      style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem', borderColor: '#10b981', color: '#34d399' }}
                                      onClick={() => setShowResolveIssueModal(iss)}
                                    >
                                      Resolver
                                    </button>
                                  )}
                                  <button
                                    type="button"
                                    className="btn-action-icon"
                                    title="Editar Ocorrência"
                                    onClick={() => handleEditIssue(iss)}
                                  >
                                    <Pencil size={14} />
                                  </button>
                                  <button
                                    type="button"
                                    className="btn-action-icon delete"
                                    title="Excluir Ocorrência"
                                    onClick={() => handleDeleteIssue(iss)}
                                  >
                                    <Trash2 size={14} />
                                  </button>
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {/* -------------------------------------------------------------- */}
              {/* SEÇÃO 7: CONFIGURAÇÕES - TIPOS DE PROJETO */}
              {/* -------------------------------------------------------------- */}
              {activeMenu === 'project_types' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                  <BulkActionsBar
                    selectedCount={projectTypeSelection.selectedCount}
                    resourceName={{ singular: 'tipo de projeto', plural: 'tipos de projeto' }}
                    onClear={projectTypeSelection.clearSelection}
                    onDelete={() => void runProjectsBulkAction(projectTypeSelection.selectedIdList, 'Excluir', projectsService.deleteProjectType, projectTypeSelection.clearSelection, 'tipo(s) de projeto')}
                    deleteLabel="Excluir selecionados"
                  />

                  <div className="filter-bar">
                    <span style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                      Categorias de execução com seus workflows e prefixos automáticos
                    </span>
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={openNewProjectType}
                    >
                      <Plus size={14} />
                      <span>Novo Tipo de Projeto</span>
                    </button>
                  </div>

                  {projectTypes.length === 0 ? (
                    <div className="empty-state">
                      <Settings2 size={48} />
                      <h3>Nenhum tipo de projeto configurado</h3>
                      <p>Cadastre tipos como Instalação Solar, CFTV, Confecção ou Manutenção para classificar seus projetos.</p>
                      <button
                        type="button"
                        className="btn btn-primary"
                        onClick={openNewProjectType}
                      >
                        <Plus size={15} />
                        <span>Criar Primeiro Tipo</span>
                      </button>
                    </div>
                  ) : (
                    <div className="data-table-container">
                      <table>
                        <thead>
                          <tr>
                            <th className="ui-selection-cell">
                              <input
                                className="ui-selection-checkbox"
                                type="checkbox"
                                aria-label="Selecionar todos os tipos"
                                checked={projectTypeSelection.isAllSelected(projectTypes)}
                                onChange={() => projectTypeSelection.toggleSelectAll(projectTypes)}
                              />
                            </th>
                            <th>Cor</th>
                            <th>Nome do Tipo</th>
                            <th>Código</th>
                            <th>Prefixo de Numeração</th>
                            <th>Descrição</th>
                            <th>Status</th>
                            <th>Ações</th>
                          </tr>
                        </thead>
                        <tbody>
                          {projectTypes.map(pt => (
                            <tr
                              key={pt.id}
                              className={`clickable-row ui-record-row ${projectTypeSelection.isSelected(pt.id) ? 'ui-record-row--selected' : ''}`}
                              role="button"
                              tabIndex={0}
                              onClick={(e) => {
                                if (!(e.target as HTMLElement).closest('button, a, input, label, .btn-action-icon')) {
                                  handleEditProjectType(pt);
                                }
                              }}
                              onKeyDown={(e) => {
                                if (['Enter', ' '].includes(e.key)) {
                                  e.preventDefault();
                                  handleEditProjectType(pt);
                                }
                              }}
                            >
                              <td className="ui-selection-cell">
                                <input
                                  className="ui-selection-checkbox"
                                  type="checkbox"
                                  aria-label={`Selecionar tipo ${pt.name}`}
                                  checked={projectTypeSelection.isSelected(pt.id)}
                                  onClick={e => e.stopPropagation()}
                                  onChange={() => projectTypeSelection.toggleSelect(pt.id)}
                                />
                              </td>
                              <td style={{ width: '40px' }}>
                                <span style={{
                                  display: 'inline-block',
                                  width: '16px',
                                  height: '16px',
                                  borderRadius: '50%',
                                  backgroundColor: pt.color || '#6366f1'
                                }} />
                              </td>
                              <td>
                                <strong
                                  className="record-title-link"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleEditProjectType(pt);
                                  }}
                                >
                                  {pt.name}
                                </strong>
                              </td>
                              <td>
                                <span style={{ fontFamily: 'monospace', color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                                  {pt.code}
                                </span>
                              </td>
                              <td>
                                <span style={{
                                  padding: '0.2rem 0.5rem',
                                  borderRadius: '4px',
                                  fontSize: '0.75rem',
                                  fontWeight: 700,
                                  background: 'var(--bg-surface-elevated)',
                                  border: '1px solid var(--border-subtle)',
                                  color: 'var(--accent-brand)',
                                  fontFamily: 'monospace'
                                }}>
                                  {pt.prefix}-*
                                </span>
                              </td>
                              <td>
                                <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                                  {pt.description || '-'}
                                </span>
                              </td>
                              <td>
                                <span style={{
                                  padding: '0.2rem 0.5rem',
                                  borderRadius: '12px',
                                  fontSize: '0.7rem',
                                  fontWeight: 600,
                                  background: pt.is_active ? 'rgba(16, 185, 129, 0.15)' : 'rgba(100, 116, 139, 0.2)',
                                  color: pt.is_active ? '#34d399' : '#94a3b8'
                                }}>
                                  {pt.is_active ? 'Ativo' : 'Inativo'}
                                </span>
                              </td>
                              <td>
                                <div style={{ display: 'flex', gap: '0.4rem', justifyContent: 'flex-end' }}>
                                  <button
                                    type="button"
                                    className="btn-action-icon"
                                    title="Editar Tipo de Projeto"
                                    onClick={() => handleEditProjectType(pt)}
                                  >
                                    <Pencil size={14} />
                                  </button>
                                  <button
                                    type="button"
                                    className="btn-action-icon delete"
                                    title="Excluir Tipo de Projeto"
                                    onClick={() => handleDeleteProjectType(pt)}
                                  >
                                    <Trash2 size={14} />
                                  </button>
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {/* -------------------------------------------------------------- */}
              {/* SEÇÃO 8: CONFIGURAÇÕES - TIPOS DE ORDEM DE TRABALHO */}
              {/* -------------------------------------------------------------- */}
              {activeMenu === 'wo_types' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                  <BulkActionsBar
                    selectedCount={workOrderTypeSelection.selectedCount}
                    resourceName={{ singular: 'tipo de ordem', plural: 'tipos de ordem' }}
                    onClear={workOrderTypeSelection.clearSelection}
                    onDelete={() => void runProjectsBulkAction(workOrderTypeSelection.selectedIdList, 'Excluir', projectsService.deleteWorkOrderType, workOrderTypeSelection.clearSelection, 'tipo(s) de ordem')}
                    deleteLabel="Excluir selecionados"
                  />

                  <div className="filter-bar">
                    <span style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                      Especializações operacionais (Ordem de Serviço, Produção, Manutenção, etc.)
                    </span>
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={openNewWorkOrderType}
                    >
                      <Plus size={14} />
                      <span>Novo Tipo de Ordem</span>
                    </button>
                  </div>

                  {workOrderTypes.length === 0 ? (
                    <div className="empty-state">
                      <Settings2 size={48} />
                      <h3>Nenhum tipo de ordem configurado</h3>
                      <p>Cadastre tipos de ordem de trabalho para diferenciar serviços técnicos de ordens de produção ou manutenção.</p>
                      <button
                        type="button"
                        className="btn btn-primary"
                        onClick={openNewWorkOrderType}
                      >
                        <Plus size={15} />
                        <span>Criar Primeiro Tipo de OS</span>
                      </button>
                    </div>
                  ) : (
                    <div className="data-table-container">
                      <table>
                        <thead>
                          <tr>
                            <th className="ui-selection-cell">
                              <input
                                className="ui-selection-checkbox"
                                type="checkbox"
                                aria-label="Selecionar todos os tipos"
                                checked={workOrderTypeSelection.isAllSelected(workOrderTypes)}
                                onChange={() => workOrderTypeSelection.toggleSelectAll(workOrderTypes)}
                              />
                            </th>
                            <th>Cor</th>
                            <th>Nome do Tipo</th>
                            <th>Código</th>
                            <th>Prefixo</th>
                            <th>Descrição</th>
                            <th>Status</th>
                            <th>Ações</th>
                          </tr>
                        </thead>
                        <tbody>
                          {workOrderTypes.map(wt => (
                            <tr
                              key={wt.id}
                              className={`clickable-row ui-record-row ${workOrderTypeSelection.isSelected(wt.id) ? 'ui-record-row--selected' : ''}`}
                              role="button"
                              tabIndex={0}
                              onClick={(e) => {
                                if (!(e.target as HTMLElement).closest('button, a, input, label, .btn-action-icon')) {
                                  handleEditWorkOrderType(wt);
                                }
                              }}
                              onKeyDown={(e) => {
                                if (['Enter', ' '].includes(e.key)) {
                                  e.preventDefault();
                                  handleEditWorkOrderType(wt);
                                }
                              }}
                            >
                              <td className="ui-selection-cell">
                                <input
                                  className="ui-selection-checkbox"
                                  type="checkbox"
                                  aria-label={`Selecionar tipo ${wt.name}`}
                                  checked={workOrderTypeSelection.isSelected(wt.id)}
                                  onClick={e => e.stopPropagation()}
                                  onChange={() => workOrderTypeSelection.toggleSelect(wt.id)}
                                />
                              </td>
                              <td style={{ width: '40px' }}>
                                <span style={{
                                  display: 'inline-block',
                                  width: '16px',
                                  height: '16px',
                                  borderRadius: '50%',
                                  backgroundColor: wt.color || '#8b5cf6'
                                }} />
                              </td>
                              <td>
                                <strong
                                  className="record-title-link"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleEditWorkOrderType(wt);
                                  }}
                                >
                                  {wt.name}
                                </strong>
                              </td>
                              <td>
                                <span style={{ fontFamily: 'monospace', color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                                  {wt.code}
                                </span>
                              </td>
                              <td>
                                <span style={{
                                  padding: '0.2rem 0.5rem',
                                  borderRadius: '4px',
                                  fontSize: '0.75rem',
                                  fontWeight: 700,
                                  background: 'var(--bg-surface-elevated)',
                                  border: '1px solid var(--border-subtle)',
                                  color: '#60a5fa',
                                  fontFamily: 'monospace'
                                }}>
                                  {wt.prefix}-*
                                </span>
                              </td>
                              <td>
                                <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                                  {wt.description || '-'}
                                </span>
                              </td>
                              <td>
                                <span style={{
                                  padding: '0.2rem 0.5rem',
                                  borderRadius: '12px',
                                  fontSize: '0.7rem',
                                  fontWeight: 600,
                                  background: wt.is_active ? 'rgba(16, 185, 129, 0.15)' : 'rgba(100, 116, 139, 0.2)',
                                  color: wt.is_active ? '#34d399' : '#94a3b8'
                                }}>
                                  {wt.is_active ? 'Ativo' : 'Inativo'}
                                </span>
                              </td>
                              <td>
                                <div style={{ display: 'flex', gap: '0.4rem', justifyContent: 'flex-end' }}>
                                  <button
                                    type="button"
                                    className="btn-action-icon"
                                    title="Editar Tipo de Ordem"
                                    onClick={() => handleEditWorkOrderType(wt)}
                                  >
                                    <Pencil size={14} />
                                  </button>
                                  <button
                                    type="button"
                                    className="btn-action-icon delete"
                                    title="Excluir Tipo de Ordem"
                                    onClick={() => handleDeleteWorkOrderType(wt)}
                                  >
                                    <Trash2 size={14} />
                                  </button>
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {/* -------------------------------------------------------------- */}
              {/* SEÇÃO 9: CONFIGURAÇÕES - FLUXOS & WORKFLOWS */}
              {/* -------------------------------------------------------------- */}
              {activeMenu === 'workflows' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                  <BulkActionsBar
                    selectedCount={workflowSelection.selectedCount}
                    resourceName={{ singular: 'workflow', plural: 'workflows' }}
                    onClear={workflowSelection.clearSelection}
                    onDelete={() => void runProjectsBulkAction(workflowSelection.selectedIdList, 'Excluir', projectsService.deleteWorkflowTemplate, workflowSelection.clearSelection, 'workflow(s)')}
                    deleteLabel="Excluir selecionados"
                  />

                  <div className="filter-bar">
                    <span style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                      Modelos de fluxo de trabalho configuráveis sem etapas fixas no código
                    </span>
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={openNewWorkflow}
                    >
                      <Plus size={14} />
                      <span>Novo Workflow</span>
                    </button>
                  </div>

                  {workflows.length === 0 ? (
                    <div className="empty-state">
                      <GitBranch size={48} />
                      <h3>Nenhum workflow cadastrado</h3>
                      <p>Crie workflows para modelar o ciclo de vida dos seus projetos ou ordens de trabalho.</p>
                      <button
                        type="button"
                        className="btn btn-primary"
                        onClick={openNewWorkflow}
                      >
                        <Plus size={15} />
                        <span>Criar Primeiro Workflow</span>
                      </button>
                    </div>
                  ) : (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.25rem' }}>
                      {workflows.map(wf => (
                        <div
                          key={wf.id}
                          className="data-table-container"
                          style={{
                            padding: '1.25rem',
                            border: workflowSelection.isSelected(wf.id) ? '2px solid var(--accent-brand)' : undefined,
                            background: workflowSelection.isSelected(wf.id) ? 'rgba(255, 85, 0, 0.04)' : undefined
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
                            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.6rem' }}>
                              <input
                                className="ui-selection-checkbox"
                                type="checkbox"
                                aria-label={`Selecionar workflow ${wf.name}`}
                                checked={workflowSelection.isSelected(wf.id)}
                                onChange={() => workflowSelection.toggleSelect(wf.id)}
                                style={{ marginTop: '0.2rem' }}
                              />
                              <div>
                                <h3 style={{ fontSize: '1rem', fontWeight: 600, margin: 0 }}>{wf.name}</h3>
                                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                                  Alvo: {wf.target_entity === 'PROJECT' ? 'Projetos' : 'Ordens de Trabalho'}
                                </span>
                              </div>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                              <span style={{
                                padding: '0.2rem 0.5rem',
                                borderRadius: '12px',
                                fontSize: '0.7rem',
                                fontWeight: 600,
                                background: wf.is_active ? 'rgba(16, 185, 129, 0.15)' : 'rgba(100, 116, 139, 0.2)',
                                color: wf.is_active ? '#34d399' : '#94a3b8'
                              }}>
                                {wf.is_active ? 'Ativo' : 'Inativo'}
                              </span>
                              <button
                                type="button"
                                className="btn-action-icon"
                                title="Editar Workflow"
                                onClick={() => handleEditWorkflow(wf)}
                              >
                                <Pencil size={14} />
                              </button>
                              <button
                                type="button"
                                className="btn-action-icon delete"
                                title="Excluir Workflow"
                                onClick={() => handleDeleteWorkflow(wf)}
                              >
                                <Trash2 size={14} />
                              </button>
                            </div>
                          </div>

                          {wf.description && (
                            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                              {wf.description}
                            </p>
                          )}

                          <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '0.75rem' }}>
                            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                              Etapas do Fluxo ({wf.stages?.length || 0})
                            </span>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginTop: '0.5rem' }}>
                              {wf.stages?.map(st => (
                                <span
                                  key={st.id}
                                  style={{
                                    fontSize: '0.75rem',
                                    padding: '0.25rem 0.6rem',
                                    borderRadius: '4px',
                                    background: 'var(--bg-surface-elevated)',
                                    border: `1px solid ${st.color || 'var(--border-subtle)'}`,
                                    color: 'var(--text-primary)',
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: '0.35rem'
                                  }}
                                >
                                  <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: st.color || '#6366f1' }} />
                                  <span>{st.name}</span>
                                  <button
                                    type="button"
                                    style={{
                                      background: 'none',
                                      border: 'none',
                                      cursor: 'pointer',
                                      padding: 0,
                                      marginLeft: '0.2rem',
                                      display: 'inline-flex',
                                      alignItems: 'center',
                                      color: 'var(--text-secondary)'
                                    }}
                                    title={`Excluir etapa ${st.name}`}
                                    onClick={() => handleDeleteStage(st.id, st.name)}
                                  >
                                    <X size={12} />
                                  </button>
                                </span>
                              ))}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </main>
      </div>

      {/* MODAL RESOLVER OCORRÊNCIA */}
      {showResolveIssueModal && (
        <div className="modal-backdrop" onClick={() => setShowResolveIssueModal(null)}>
          <div className="modal-box" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Resolver Ocorrência: {showResolveIssueModal.issue_number || showResolveIssueModal.code}</h2>
              <button type="button" className="btn-close" onClick={() => setShowResolveIssueModal(null)}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleResolveIssue}>
              <div className="modal-body">
                <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', margin: 0 }}>
                  Informe as ações corretivas tomadas para sanar o impedimento:
                </p>
                <div className="form-group">
                  <label>Justificativa / Solução Aplicada *</label>
                  <textarea
                    required
                    placeholder="Ex: Fornecedor realizou entrega expressa de lote emergencial. Equipe liberada."
                    value={resolutionNotes}
                    onChange={e => setResolutionNotes(e.target.value)}
                  />
                </div>
              </div>

              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setShowResolveIssueModal(null)}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn-primary">
                  Confirmar Resolução
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL NOVO ESTÁGIO DO KANBAN */}
      {showStageModal && (
        <div className="modal-backdrop" onClick={() => setShowStageModal(false)}>
          <div className="modal-box" onClick={e => e.stopPropagation()} style={{ maxWidth: '480px' }}>
            <div className="modal-header">
              <h2>Novo Estágio do Kanban</h2>
              <button type="button" className="btn-close" onClick={() => setShowStageModal(false)}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleCreateStage}>
              <div className="modal-body">
                <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: 0 }}>
                  Personalize as etapas operacionais da sua organização. O estágio será vinculado ao fluxo ativo e salvo imediatamente.
                </p>

                <div className="form-group">
                  <label>Nome do Estágio *</label>
                  <input
                    type="text"
                    required
                    placeholder="Ex: Em Compras, Instalação Técnica, Homologação..."
                    value={stageForm.name}
                    onChange={e => setStageForm(prev => ({ ...prev, name: e.target.value }))}
                  />
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>Cor do Estágio</label>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <input
                        type="color"
                        value={stageForm.color}
                        onChange={e => setStageForm(prev => ({ ...prev, color: e.target.value }))}
                        style={{ width: '40px', height: '36px', padding: '2px', cursor: 'pointer', borderRadius: '4px' }}
                      />
                      <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
                        {['#6366f1', '#3b82f6', '#10b981', '#f59e0b', '#f43f5e', '#8b5cf6', '#06b6d4'].map(c => (
                          <button
                            key={c}
                            type="button"
                            onClick={() => setStageForm(prev => ({ ...prev, color: c }))}
                            style={{
                              width: '22px',
                              height: '22px',
                              borderRadius: '50%',
                              backgroundColor: c,
                              border: stageForm.color === c ? '2px solid #ffffff' : '1px solid transparent',
                              cursor: 'pointer',
                              boxShadow: stageForm.color === c ? '0 0 0 2px var(--accent-brand)' : 'none'
                            }}
                          />
                        ))}
                      </div>
                    </div>
                  </div>

                  <div className="form-group">
                    <label>Ordem / Posição</label>
                    <input
                      type="number"
                      min={1}
                      value={stageForm.position}
                      onChange={e => setStageForm(prev => ({ ...prev, position: Number(e.target.value) }))}
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label>Descrição / Instruções da Etapa</label>
                  <textarea
                    rows={2}
                    placeholder="O que deve ser realizado nesta etapa..."
                    value={stageForm.description}
                    onChange={e => setStageForm(prev => ({ ...prev, description: e.target.value }))}
                  />
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '0.5rem', padding: '0.75rem', background: 'var(--bg-surface-elevated)', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.8rem' }}>
                    <input
                      type="checkbox"
                      checked={stageForm.is_initial}
                      onChange={e => setStageForm(prev => ({ ...prev, is_initial: e.target.checked }))}
                    />
                    <span><strong>Etapa Inicial:</strong> Novos projetos começam diretamente neste estágio</span>
                  </label>

                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.8rem' }}>
                    <input
                      type="checkbox"
                      checked={stageForm.is_terminal}
                      onChange={e => setStageForm(prev => ({ ...prev, is_terminal: e.target.checked }))}
                    />
                    <span><strong>Etapa de Conclusão (Terminal):</strong> Projetos nesta etapa são finalizados</span>
                  </label>
                </div>
              </div>

              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setShowStageModal(false)}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn-primary">
                  Criar Estágio
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL DE CONFIRMAÇÃO UNIFICADO (EXCLUSÃO / AÇÕES CRÍTICAS) */}
      <ConfirmModal
        isOpen={confirmModal.isOpen}
        onClose={closeConfirmModal}
        onConfirm={confirmModal.onConfirm}
        title={confirmModal.title}
        subtitle={confirmModal.subtitle}
        message={confirmModal.message}
        confirmText={confirmModal.confirmText}
        cancelText={confirmModal.cancelText}
        type={confirmModal.type}
        isLoading={confirmModal.isLoading}
        errorMessage={confirmModal.errorMessage}
      />
    </div>
  );
};

export default Projects;
