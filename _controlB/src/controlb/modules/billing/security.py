"""
modules/billing/security.py - Permissões do Módulo de Faturamento
"""

from typing import Any

MODULE_PERMISSIONS: list[dict[str, Any]] = [
    {
        "code": "billing:view",
        "name": "Visualizar Faturamento & Faturas",
        "module": "Faturamento",
        "description": "Visualizar faturas comerciais, parcelas e documentos fiscais emitidos"
    },
    {
        "code": "billing:manage",
        "name": "Gerenciar Faturamento & Emissão",
        "module": "Faturamento",
        "description": "Processar solicitações, faturamento parcial, notas fiscais e parcelamento"
    },
]
