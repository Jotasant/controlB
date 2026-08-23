"""
modules/crm/security.py - Permissões do Módulo CRM
"""

from typing import List, Dict, Any

MODULE_PERMISSIONS: List[Dict[str, Any]] = [
    {
        "code": "crm:view",
        "name": "Visualizar CRM & Leads",
        "module": "CRM",
        "description": "Visualizar leads, oportunidades de negócio e pipeline de vendas"
    },
    {
        "code": "crm:manage",
        "name": "Gerenciar CRM & Oportunidades",
        "module": "CRM",
        "description": "Criar leads, mover oportunidades no funil e registrar interações com clientes"
    },
    {
        "code": "crm:stages:manage",
        "name": "Configurar Etapas do Funil de CRM",
        "module": "CRM",
        "description": "Criar, ordenar, editar e excluir etapas personalizadas do pipeline / Kanban do CRM"
    },
]
