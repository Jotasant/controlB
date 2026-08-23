"""API transversal de consulta da cadeia documental."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from controlb.db import get_db
from controlb.modules.documents import schemas, service
from controlb.modules.identity import service as identity_service
from controlb.modules.identity.models import User

router = APIRouter(prefix="/documents", tags=["Documentos Relacionados"])

DOCUMENT_VIEW_PERMISSIONS = {
    "SALES_QUOTE": "sales:view",
    "SALES_ORDER": "sales:view",
    "STOCK_RESERVATION": "products:view",
    "OPPORTUNITY": "crm:view",
    "PURCHASE_REQUEST": "purchasing:view",
    "PURCHASE_ORDER": "purchasing:view",
    "FISCAL_DOCUMENT": "billing:view",
    "PAYABLE": "finance:payables",
    "RECEIVABLE": "finance:receivables",
}


@router.get(
    "/{document_type}/{native_id}/chain",
    response_model=schemas.DocumentChainResponse,
    summary="Consultar cadeia e timeline de um documento",
)
def get_document_chain(
    document_type: str,
    native_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(identity_service.get_current_user)],
):
    normalized_type = document_type.strip().upper()
    required_permission = DOCUMENT_VIEW_PERMISSIONS.get(normalized_type, "documents:view")
    if required_permission not in identity_service.get_user_permissions(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Acesso negado: permissão '{required_permission}' necessária.",
        )
    return service.get_document_chain(
        db,
        organization_id=current_user.organization_id,
        document_type=normalized_type,
        native_id=native_id,
    )
