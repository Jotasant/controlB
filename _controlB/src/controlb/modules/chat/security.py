"""Permissões RBAC do módulo Chat."""

from typing import Any

MODULE_PERMISSIONS: list[dict[str, Any]] = [
    {
        "code": "chat:view",
        "name": "Visualizar Chat",
        "module": "Chat",
        "description": "Consultar conversas e mensagens vinculadas aos registros do sistema",
    },
    {
        "code": "chat:send",
        "name": "Enviar Mensagens",
        "module": "Chat",
        "description": "Enviar mensagens pelos conectores habilitados da organização",
    },
    {
        "code": "chat:link",
        "name": "Vincular Conversas",
        "module": "Chat",
        "description": "Relacionar conversas a propostas, projetos e outros documentos",
    },
    {
        "code": "chat:manage_connectors",
        "name": "Gerenciar Conectores do Chat",
        "module": "Chat",
        "description": "Configurar instâncias, credenciais e webhooks dos conectores",
    },
]
