"""Permissões e política de leitura da infraestrutura documental."""

from typing import Any

DOCUMENT_VIEW_PERMISSIONS: dict[str, str] = {
    "SALES_QUOTE": "sales:view",
    "SALES_ORDER": "sales:view",
    "POS_SALE": "sales:view",
    "SALES_RETURN": "sales:view",
    "STOCK_RESERVATION": "products:view",
    "DELIVERY": "products:view",
    "INVENTORY_TRANSFER": "products:view",
    "INVENTORY_IMPORT_BATCH": "products:view",
    "STOCK_MOVEMENT": "products:view",
    "REPLENISHMENT": "purchasing:view",
    "INVENTORY_RECEIPT": "products:view",
    "OPPORTUNITY": "crm:view",
    "LEAD": "crm:view",
    "CRM_INTERACTION": "crm:view",
    "PURCHASE_REQUEST": "purchasing:view",
    "PURCHASE_ORDER": "purchasing:view",
    "PURCHASE_QUOTATION": "purchasing:view",
    "INVOICE": "billing:view",
    "BILLING_REQUEST": "billing:view",
    "FISCAL_DOCUMENT": "billing:view",
    "PAYABLE": "finance:payables",
    "RECEIVABLE": "finance:receivables",
}


def required_view_permission(document_type: str) -> str:
    """Retorna a permissão funcional exigida pelo tipo documental."""
    normalized_type = document_type.strip().upper()
    return DOCUMENT_VIEW_PERMISSIONS.get(normalized_type, "documents:view")


def can_view_document_type(document_type: str, user_permissions: set[str]) -> bool:
    """Autoriza um tipo sem permitir que o grafo contorne o RBAC dos módulos."""
    if "*:*" in user_permissions:
        return True
    return required_view_permission(document_type) in user_permissions


def authorized_mapped_document_types(user_permissions: set[str]) -> set[str] | None:
    """Tipos conhecidos liberados; ``None`` representa acesso administrativo total."""
    if "*:*" in user_permissions:
        return None
    return {
        document_type
        for document_type, permission in DOCUMENT_VIEW_PERMISSIONS.items()
        if permission in user_permissions
    }

MODULE_PERMISSIONS: list[dict[str, Any]] = [
    {
        "code": "documents:view",
        "name": "Visualizar cadeia documental",
        "module": "Documents",
        "description": "Consultar relações e eventos entre documentos de negócio.",
    }
]
