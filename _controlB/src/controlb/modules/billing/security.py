"""
modules/billing/security.py - Permissões do Módulo de Faturamento
"""

from typing import List, Dict, Any

MODULE_PERMISSIONS: List[Dict[str, Any]] = [
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
        "description": "Emitir faturas comerciais, gerar notas fiscais (NF-e/NFC-e) e parcelamento"
    },
]
