"""
security.py - Definição de Permissões e Segurança do Módulo de Estoque & Almoxarifado

Responsabilidades:
1. Declarar as permissões de acesso específicas deste módulo (MODULE_PERMISSIONS).
2. Facilitar a descoberta automática (auto-discovery) pelo motor central de segurança RBAC.
"""

from typing import List, Dict, Any

MODULE_PERMISSIONS: List[Dict[str, Any]] = [
    {
        "code": "products:view",
        "name": "Visualizar Catálogo de Produtos",
        "module": "Estoque",
        "description": "Consultar catálogo de produtos, insumos, categorias e saldos físicos em prateleira"
    },
    {
        "code": "products:manage",
        "name": "Gerenciar Catálogo de Produtos",
        "module": "Estoque",
        "description": "Cadastrar, editar e inativar produtos, categorias, marcas e especificações técnicas"
    },
    {
        "code": "inventory:move",
        "name": "Registrar Movimentações de Estoque",
        "module": "Estoque",
        "description": "Lançar entradas manuais por NF, saídas por consumo/transferência e baixas de estoque"
    },
    {
        "code": "inventory:audit",
        "name": "Auditoria & Balanço Físico",
        "module": "Estoque",
        "description": "Realizar contagens cíclicas, aferição de prateleira e conciliação de sobras, faltas e perdas"
    },
]
