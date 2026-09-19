"""
modules/projects/security.py - Permissões RBAC do Módulo de Projetos & Operações

Define as permissões granulares que serão auto-descobertas pelo motor de
segurança em identity/security.py (discover_system_permissions).

Não é necessário registro manual: o auto-discovery escaneia todos os módulos
e importa MODULE_PERMISSIONS automaticamente.
"""

from typing import Any, Dict, List

MODULE_PERMISSIONS: List[Dict[str, Any]] = [
    # ── Projetos ──────────────────────────────────────────────
    {
        "code": "projects:view",
        "name": "Visualizar Projetos",
        "module": "Projetos",
        "description": "Consultar a listagem, detalhes e indicadores de projetos operacionais",
    },
    {
        "code": "projects:create",
        "name": "Criar Projetos",
        "module": "Projetos",
        "description": "Criar novos projetos operacionais, inclusive a partir de pedidos ou oportunidades",
    },
    {
        "code": "projects:update",
        "name": "Editar Projetos",
        "module": "Projetos",
        "description": "Editar dados, alterar etapas e atualizar status de projetos",
    },
    {
        "code": "projects:delete",
        "name": "Excluir/Arquivar Projetos",
        "module": "Projetos",
        "description": "Cancelar, arquivar ou excluir projetos operacionais",
    },
    {
        "code": "projects:manage_members",
        "name": "Gerenciar Membros do Projeto",
        "module": "Projetos",
        "description": "Adicionar, remover e alterar papéis dos membros de um projeto",
    },

    # ── Ordens de Trabalho ────────────────────────────────────
    {
        "code": "work_orders:view",
        "name": "Visualizar Ordens de Trabalho",
        "module": "Projetos",
        "description": "Consultar ordens de trabalho, serviço e produção",
    },
    {
        "code": "work_orders:create",
        "name": "Criar Ordens de Trabalho",
        "module": "Projetos",
        "description": "Abrir novas ordens de trabalho vinculadas a projetos",
    },
    {
        "code": "work_orders:update",
        "name": "Editar Ordens de Trabalho",
        "module": "Projetos",
        "description": "Alterar dados, status e etapas de ordens de trabalho",
    },
    {
        "code": "work_orders:complete",
        "name": "Concluir Ordens de Trabalho",
        "module": "Projetos",
        "description": "Marcar ordens de trabalho como concluídas",
    },

    # ── Tarefas ───────────────────────────────────────────────
    {
        "code": "tasks:view",
        "name": "Visualizar Tarefas",
        "module": "Projetos",
        "description": "Consultar tarefas de projetos e ordens de trabalho",
    },
    {
        "code": "tasks:create",
        "name": "Criar Tarefas",
        "module": "Projetos",
        "description": "Criar novas tarefas vinculadas a projetos ou ordens",
    },
    {
        "code": "tasks:update",
        "name": "Editar Tarefas",
        "module": "Projetos",
        "description": "Alterar dados, status e progresso de tarefas",
    },
    {
        "code": "tasks:assign",
        "name": "Atribuir Tarefas",
        "module": "Projetos",
        "description": "Designar responsáveis para tarefas operacionais",
    },
    {
        "code": "tasks:complete",
        "name": "Concluir Tarefas",
        "module": "Projetos",
        "description": "Marcar tarefas como concluídas e registrar apontamentos",
    },

    # ── Ocorrências ───────────────────────────────────────────
    {
        "code": "issues:manage",
        "name": "Gerenciar Ocorrências",
        "module": "Projetos",
        "description": "Criar, editar, resolver e fechar ocorrências e pendências de projetos",
    },

    # ── Apontamento de Horas ──────────────────────────────────
    {
        "code": "time_entries:create",
        "name": "Apontar Horas",
        "module": "Projetos",
        "description": "Registrar apontamentos de horas trabalhadas em tarefas e ordens",
    },
    {
        "code": "time_entries:manage",
        "name": "Gerenciar Apontamentos",
        "module": "Projetos",
        "description": "Visualizar, editar e excluir apontamentos de horas de qualquer membro",
    },

    # ── Custos e Orçamento ────────────────────────────────────
    {
        "code": "project_costs:view",
        "name": "Visualizar Custos de Projetos",
        "module": "Projetos",
        "description": "Consultar orçamentos, custos reais e análises financeiras de projetos",
    },
    {
        "code": "project_costs:manage",
        "name": "Gerenciar Custos de Projetos",
        "module": "Projetos",
        "description": "Registrar despesas, ajustar orçamentos e aprovar custos de projetos",
    },

    # ── Workflows e Configurações ─────────────────────────────
    {
        "code": "workflows:manage",
        "name": "Gerenciar Workflows",
        "module": "Projetos",
        "description": "Criar, editar e excluir templates de fluxo de trabalho e suas etapas",
    },

    # ── Relatórios Operacionais ───────────────────────────────
    {
        "code": "project_reports:view",
        "name": "Relatórios Operacionais",
        "module": "Projetos",
        "description": "Acessar relatórios consolidados de performance, prazos e custos de projetos",
    },

    # ── Produção (Fase 4) ─────────────────────────────────────
    {
        "code": "production:manage",
        "name": "Gerenciar Produção",
        "module": "Projetos",
        "description": "Controlar ordens de produção, operações, saídas e perdas",
    },
]
