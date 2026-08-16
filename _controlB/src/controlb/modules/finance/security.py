"""
security.py - Definição de Permissões e Segurança do Módulo Financeiro e Faturamento

Responsabilidades:
1. Declarar as permissões de acesso específicas deste módulo (MODULE_PERMISSIONS).
2. Facilitar a descoberta automática (auto-discovery) pelo motor central de segurança RBAC.
"""

from typing import List, Dict, Any

MODULE_PERMISSIONS: List[Dict[str, Any]] = [
    {
        "code": "finance:view",
        "name": "Visualizar Módulo Financeiro",
        "module": "Financeiro",
        "description": "Visualizar painel financeiro, fluxo de caixa, contas e relatórios gerenciais"
    },
    {
        "code": "finance:payables",
        "name": "Gerenciar Contas a Pagar",
        "module": "Financeiro",
        "description": "Cadastrar despesas avulsas, aprovar títulos, programar vencimentos e liquidar pagamentos"
    },
    {
        "code": "finance:receivables",
        "name": "Gerenciar Contas a Receber",
        "module": "Financeiro",
        "description": "Controlar títulos a receber, baixas de recebimento e cobranças de clientes"
    },
    {
        "code": "finance:treasury",
        "name": "Gestão de Tesouraria & Bancos",
        "module": "Financeiro",
        "description": "Gerenciar contas bancárias, caixas físicos e importar/lançar extratos bancários"
    },
    {
        "code": "finance:reconcile",
        "name": "Conciliação Bancária",
        "module": "Financeiro",
        "description": "Realizar conciliação entre movimentações de extrato e pagamentos/recebimentos"
    },
    {
        "code": "billing:view",
        "name": "Visualizar Faturamento & PDV",
        "module": "Faturamento",
        "description": "Acompanhar faturamento diário, vendas e integração com PDV"
    },
    {
        "code": "billing:manage",
        "name": "Gerenciar Faturamento & Vendas",
        "module": "Faturamento",
        "description": "Emitir documentos fiscais de saída, faturar pedidos e fechar caixas de PDV"
    },
]
