"""
security.py - Definição de Permissões e Segurança do Módulo de Compras & Suprimentos

Responsabilidades:
1. Declarar as permissões de acesso específicas deste módulo (MODULE_PERMISSIONS).
2. Facilitar a descoberta automática (auto-discovery) pelo motor central de segurança RBAC.
"""

from typing import List, Dict, Any

MODULE_PERMISSIONS: List[Dict[str, Any]] = [
    {
        "code": "purchasing:view",
        "name": "Visualizar Compras & Suprimentos",
        "module": "Compras",
        "description": "Consultar solicitações de compra, cotações, fornecedores e ordens de compra"
    },
    {
        "code": "purchasing:request",
        "name": "Criar Solicitações de Compra (SC)",
        "module": "Compras",
        "description": "Emitir novas solicitações de compra e reposição para aprovação"
    },
    {
        "code": "purchasing:quote",
        "name": "Gerenciar Cotações & Tomadas de Preço",
        "module": "Compras",
        "description": "Cadastrar propostas de fornecedores, comparar mapas comparativos e aprovar cotações"
    },
    {
        "code": "purchasing:order",
        "name": "Emitir Ordens de Compra (PO)",
        "module": "Compras",
        "description": "Gerar pedidos formais de compra e emitir contratos aos fornecedores homologados"
    },
    {
        "code": "purchasing:receive",
        "name": "Recebimento Físico & Entrada de NF",
        "module": "Compras",
        "description": "Conferir mercadorias entregues, anexar notas fiscais e dar entrada no almoxarifado"
    },
]
