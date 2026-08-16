"""
modules/sales/security.py - Permissões do Módulo de Vendas & PDV
"""

from typing import List, Dict, Any

MODULE_PERMISSIONS: List[Dict[str, Any]] = [
    {
        "code": "sales:view",
        "name": "Visualizar Vendas & Orçamentos",
        "module": "Vendas",
        "description": "Consultar pedidos de venda, propostas comerciais e orçamentos"
    },
    {
        "code": "sales:manage",
        "name": "Gerenciar Pedidos & Orçamentos",
        "module": "Vendas",
        "description": "Elaborar orçamentos, aprovar pedidos de venda e gerenciar descontos comerciais"
    },
    {
        "code": "sales:pos",
        "name": "Operar Frente de Caixa (PDV)",
        "module": "Vendas",
        "description": "Abrir turno de caixa, realizar vendas de balcão no PDV e sangria de caixa"
    },
]
