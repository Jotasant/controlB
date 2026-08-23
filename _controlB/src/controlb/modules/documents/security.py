"""Permissões da infraestrutura de documentos relacionados."""

from typing import Any

MODULE_PERMISSIONS: list[dict[str, Any]] = [
    {
        "code": "documents:view",
        "name": "Visualizar cadeia documental",
        "module": "Documents",
        "description": "Consultar relações e eventos entre documentos de negócio.",
    }
]
