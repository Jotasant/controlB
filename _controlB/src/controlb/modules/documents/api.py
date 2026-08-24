"""API transversal de consulta, pesquisa, árvore e timeline de documentos de negócio."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from controlb.db import get_db
from controlb.modules.documents import schemas, service
from controlb.modules.identity import service as identity_service
from controlb.modules.identity.models import User

router = APIRouter(prefix="/documents", tags=["Documentos & Rastreabilidade Transversal"])

DOCUMENT_VIEW_PERMISSIONS = {
    "SALES_QUOTE": "sales:view",
    "SALES_ORDER": "sales:view",
    "STOCK_RESERVATION": "products:view",
    "OPPORTUNITY": "crm:view",
    "LEAD": "crm:view",
    "PURCHASE_REQUEST": "purchasing:view",
    "PURCHASE_ORDER": "purchasing:view",
    "FISCAL_DOCUMENT": "billing:view",
    "PAYABLE": "finance:payables",
    "RECEIVABLE": "finance:receivables",
}


@router.get(
    "",
    response_model=list[schemas.DocumentResponse],
    summary="Pesquisa transversal de documentos com filtros",
)
def list_documents(
    category: str | None = Query(None, description="Filtro por categoria (ex: crm.lead, sales.order)"),
    origin_module: str | None = Query(None, description="Filtro por módulo originador"),
    current_status: str | None = Query(None, description="Filtro por status"),
    search: str | None = Query(None, description="Busca textual por número, título ou descrição"),
    responsible_id: uuid.UUID | None = Query(None, description="Filtro por usuário responsável"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(identity_service.get_current_user),
):
    params = schemas.DocumentFilterParams(
        category=category,
        origin_module=origin_module,
        current_status=current_status,
        search=search,
        responsible_id=responsible_id,
        limit=limit,
        offset=offset,
    )
    return service.list_documents(db, current_user.organization_id, params)


@router.get(
    "/{document_id}",
    response_model=schemas.DocumentResponse,
    summary="Obter detalhes de um documento por ID global",
)
def get_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(identity_service.get_current_user),
):
    return service.get_document(db, document_id, current_user.organization_id)


@router.get(
    "/{document_id}/tree",
    response_model=schemas.DocumentTreeResponse,
    summary="Consultar árvore estruturada de rastreabilidade (Origem, Anteriores, Derivados, Dependências e Timeline)",
)
def get_document_tree(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(identity_service.get_current_user),
):
    return service.get_document_tree(db, current_user.organization_id, document_id)


@router.get(
    "/{document_type}/{native_id}/chain",
    response_model=schemas.DocumentChainResponse,
    summary="Consultar cadeia e timeline de um documento pelo identificador nativo (Compatibilidade)",
)
def get_document_chain(
    document_type: str,
    native_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(identity_service.get_current_user)],
):
    normalized_type = document_type.strip().upper()
    required_permission = DOCUMENT_VIEW_PERMISSIONS.get(normalized_type, "documents:view")
    user_perms = identity_service.get_user_permissions(current_user)
    if required_permission != "documents:view" and required_permission not in user_perms:
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
