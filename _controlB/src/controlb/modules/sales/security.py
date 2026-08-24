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
    {
        "code": "sales:settings:view",
        "name": "Visualizar Configurações Comerciais",
        "module": "Vendas",
        "description": "Consultar parâmetros comerciais compartilhados entre CRM e Vendas"
    },
    {
        "code": "sales:settings:manage",
        "name": "Gerenciar Configurações Comerciais",
        "module": "Vendas",
        "description": "Alterar condições padrão, validade, descontos e comissões comerciais"
    },
    {
        "code": "sales:credit:view",
        "name": "Visualizar Análises de Crédito",
        "module": "Vendas",
        "description": "Consultar exposição, limite e solicitações de crédito de clientes"
    },
    {
        "code": "sales:credit:approve",
        "name": "Aprovar Limites de Crédito",
        "module": "Vendas",
        "description": "Aprovar ou rejeitar pedidos que excedem o limite de crédito"
    },
    {
        "code": "sales:approvals:view",
        "name": "Visualizar Aprovações Comerciais",
        "module": "Vendas",
        "description": "Consultar solicitações por desconto, margem e prazo fora da política"
    },
    {
        "code": "sales:approvals:approve",
        "name": "Decidir Aprovações Comerciais",
        "module": "Vendas",
        "description": "Aprovar ou rejeitar exceções comerciais de desconto, margem e prazo"
    },
]
