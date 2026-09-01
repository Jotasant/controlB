"""API transversal de consulta, pesquisa, árvore e timeline de documentos de negócio."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from controlb.db import get_db
from controlb.modules.documents import schemas, security, service
from controlb.modules.identity import service as identity_service
from controlb.modules.identity.models import User

router = APIRouter(prefix="/documents", tags=["Documentos & Rastreabilidade Transversal"])

def _user_permissions(current_user: User) -> set[str]:
    return set(identity_service.get_user_permissions(current_user))


def _require_document_access(document_type: str, user_permissions: set[str]) -> None:
    if security.can_view_document_type(document_type, user_permissions):
        return
    required_permission = security.required_view_permission(document_type)
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Acesso negado: permissão '{required_permission}' necessária.",
    )


def _filter_tree_by_permissions(
    tree: schemas.DocumentTreeResponse,
    user_permissions: set[str],
) -> schemas.DocumentTreeResponse:
    for field in ("origin", "previous", "derived", "related", "dependencies"):
        nodes = getattr(tree, field)
        setattr(
            tree,
            field,
            [
                node
                for node in nodes
                if security.can_view_document_type(node.document_type, user_permissions)
            ],
        )
    return tree


def _filter_chain_by_permissions(
    chain: schemas.DocumentChainResponse,
    user_permissions: set[str],
) -> schemas.DocumentChainResponse:
    visible_documents = [
        document
        for document in chain.documents
        if security.can_view_document_type(document.document_type, user_permissions)
    ]
    visible_ids = {document.id for document in visible_documents}
    return schemas.DocumentChainResponse(
        root_document_id=chain.root_document_id,
        documents=visible_documents,
        relations=[
            relation
            for relation in chain.relations
            if relation.parent_document_id in visible_ids
            and relation.child_document_id in visible_ids
        ],
        events=[event for event in chain.events if event.document_id in visible_ids],
    )


@router.get(
    "/",
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
    user_permissions = _user_permissions(current_user)
    authorized_types = security.authorized_mapped_document_types(user_permissions)
    mapped_types = (
        None if authorized_types is None else set(security.DOCUMENT_VIEW_PERMISSIONS)
    )
    return service.list_documents(
        db,
        current_user.organization_id,
        params,
        authorized_document_types=authorized_types,
        mapped_document_types=mapped_types,
        allow_unmapped_document_types="documents:view" in user_permissions,
    )


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
    document = service.get_document(db, document_id, current_user.organization_id)
    _require_document_access(document.document_type, _user_permissions(current_user))
    return document


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
    tree = service.get_document_tree(db, current_user.organization_id, document_id)
    user_permissions = _user_permissions(current_user)
    _require_document_access(tree.document.document_type, user_permissions)
    return _filter_tree_by_permissions(tree, user_permissions)


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
    user_permissions = _user_permissions(current_user)
    _require_document_access(normalized_type, user_permissions)
    chain = service.get_document_chain(
        db,
        organization_id=current_user.organization_id,
        document_type=normalized_type,
        native_id=native_id,
    )
    return _filter_chain_by_permissions(chain, user_permissions)
