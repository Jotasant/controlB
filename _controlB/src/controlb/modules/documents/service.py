"""Regras transversais de identidade, vínculo e timeline documental."""

import uuid
from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from controlb.modules.documents import repository, schemas
from controlb.modules.documents.models import BusinessDocument, DocumentEvent, DocumentRelation


def ensure_document(
    db: Session,
    *,
    organization_id: uuid.UUID,
    document_type: str,
    native_id: uuid.UUID,
    document_number: str,
    current_status: str,
    created_by_id: uuid.UUID | None = None,
    issued_at: datetime | None = None,
) -> BusinessDocument:
    """Obtém ou registra a identidade global sem encerrar a transação do caso de uso."""
    normalized_type = document_type.strip().upper()
    normalized_status = current_status.strip().upper()
    document = repository.get_document_by_native(
        db, organization_id, normalized_type, native_id
    )
    if document:
        document.document_number = document_number.strip()
        document.current_status = normalized_status
        if issued_at is not None:
            document.issued_at = issued_at
        return document

    document = BusinessDocument(
        organization_id=organization_id,
        document_type=normalized_type,
        native_id=native_id,
        document_number=document_number.strip(),
        current_status=normalized_status,
        issued_at=issued_at,
        created_by_id=created_by_id,
    )
    db.add(document)
    db.flush()
    return document


def relate_documents(
    db: Session,
    *,
    organization_id: uuid.UUID,
    parent_document: BusinessDocument,
    child_document: BusinessDocument,
    relation_type: str,
    created_by_id: uuid.UUID | None = None,
    relation_metadata: dict[str, Any] | None = None,
) -> DocumentRelation:
    """Cria uma relação idempotente entre documentos da mesma organização."""
    if (
        parent_document.organization_id != organization_id
        or child_document.organization_id != organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é permitido relacionar documentos de organizações diferentes.",
        )
    if parent_document.id == child_document.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Um documento não pode ser relacionado a ele mesmo.",
        )

    normalized_type = relation_type.strip().upper()
    existing = repository.get_relation(
        db, parent_document.id, child_document.id, normalized_type
    )
    if existing:
        return existing

    relation = DocumentRelation(
        organization_id=organization_id,
        parent_document_id=parent_document.id,
        child_document_id=child_document.id,
        relation_type=normalized_type,
        relation_metadata=relation_metadata or {},
        created_by_id=created_by_id,
    )
    db.add(relation)
    db.flush()
    return relation


def record_event(
    db: Session,
    *,
    organization_id: uuid.UUID,
    document: BusinessDocument,
    event_type: str,
    previous_status: str | None = None,
    new_status: str | None = None,
    created_by_id: uuid.UUID | None = None,
    event_metadata: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> DocumentEvent:
    """Acrescenta um evento à timeline sem alterar eventos já gravados."""
    if document.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O documento não pertence à organização informada.",
        )
    if idempotency_key:
        existing = repository.get_event_by_idempotency_key(
            db, organization_id, idempotency_key
        )
        if existing:
            return existing

    event = DocumentEvent(
        organization_id=organization_id,
        document_id=document.id,
        event_type=event_type.strip().upper(),
        previous_status=previous_status.upper() if previous_status else None,
        new_status=new_status.upper() if new_status else None,
        event_metadata=event_metadata or {},
        idempotency_key=idempotency_key,
        created_by_id=created_by_id,
    )
    db.add(event)
    db.flush()
    if new_status:
        document.current_status = new_status.upper()
    return event


def get_document_chain(
    db: Session,
    *,
    organization_id: uuid.UUID,
    document_type: str,
    native_id: uuid.UUID,
    max_depth: int = 12,
) -> schemas.DocumentChainResponse:
    """Percorre relações de entrada e saída para montar a cadeia documental completa."""
    root = repository.get_document_by_native(
        db, organization_id, document_type.strip().upper(), native_id
    )
    if not root:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento relacionado não encontrado.",
        )

    visited = {root.id}
    frontier = {root.id}
    relations_by_id: dict[uuid.UUID, DocumentRelation] = {}

    for _ in range(max_depth):
        touching = repository.list_relations_touching(db, organization_id, frontier)
        next_frontier: set[uuid.UUID] = set()
        for relation in touching:
            relations_by_id[relation.id] = relation
            for document_id in (relation.parent_document_id, relation.child_document_id):
                if document_id not in visited:
                    visited.add(document_id)
                    next_frontier.add(document_id)
        if not next_frontier:
            break
        frontier = next_frontier

    documents = repository.list_documents_by_ids(db, organization_id, visited)
    events = repository.list_events_by_document_ids(db, organization_id, visited)
    documents.sort(key=lambda item: item.created_at)
    relations = sorted(relations_by_id.values(), key=lambda item: item.created_at)

    return schemas.DocumentChainResponse(
        root_document_id=root.id,
        documents=[schemas.DocumentNodeResponse.model_validate(item) for item in documents],
        relations=[
            schemas.DocumentRelationResponse.model_validate(item) for item in relations
        ],
        events=[schemas.DocumentEventResponse.model_validate(item) for item in events],
    )
