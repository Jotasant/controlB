"""Consultas sem commit para a infraestrutura de documentos relacionados."""

import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from controlb.modules.documents.models import BusinessDocument, DocumentEvent, DocumentRelation


def get_document_by_id(
    db: Session, document_id: uuid.UUID, organization_id: uuid.UUID
) -> BusinessDocument | None:
    stmt = select(BusinessDocument).where(
        BusinessDocument.id == document_id,
        BusinessDocument.organization_id == organization_id,
    )
    return db.scalars(stmt).first()


def get_document_by_native(
    db: Session,
    organization_id: uuid.UUID,
    document_type: str,
    native_id: uuid.UUID,
) -> BusinessDocument | None:
    stmt = select(BusinessDocument).where(
        BusinessDocument.organization_id == organization_id,
        BusinessDocument.document_type == document_type.upper(),
        BusinessDocument.native_id == native_id,
    )
    return db.scalars(stmt).first()


def get_relation(
    db: Session,
    parent_document_id: uuid.UUID,
    child_document_id: uuid.UUID,
    relation_type: str,
) -> DocumentRelation | None:
    stmt = select(DocumentRelation).where(
        DocumentRelation.parent_document_id == parent_document_id,
        DocumentRelation.child_document_id == child_document_id,
        DocumentRelation.relation_type == relation_type.upper(),
    )
    return db.scalars(stmt).first()


def get_event_by_idempotency_key(
    db: Session, organization_id: uuid.UUID, idempotency_key: str
) -> DocumentEvent | None:
    stmt = select(DocumentEvent).where(
        DocumentEvent.organization_id == organization_id,
        DocumentEvent.idempotency_key == idempotency_key,
    )
    return db.scalars(stmt).first()


def list_relations_touching(
    db: Session, organization_id: uuid.UUID, document_ids: set[uuid.UUID]
) -> list[DocumentRelation]:
    if not document_ids:
        return []
    stmt = select(DocumentRelation).where(
        DocumentRelation.organization_id == organization_id,
        or_(
            DocumentRelation.parent_document_id.in_(document_ids),
            DocumentRelation.child_document_id.in_(document_ids),
        ),
    )
    return list(db.scalars(stmt).all())


def list_documents_by_ids(
    db: Session, organization_id: uuid.UUID, document_ids: set[uuid.UUID]
) -> list[BusinessDocument]:
    if not document_ids:
        return []
    stmt = select(BusinessDocument).where(
        BusinessDocument.organization_id == organization_id,
        BusinessDocument.id.in_(document_ids),
    )
    return list(db.scalars(stmt).all())


def list_events_by_document_ids(
    db: Session, organization_id: uuid.UUID, document_ids: set[uuid.UUID]
) -> list[DocumentEvent]:
    if not document_ids:
        return []
    stmt = (
        select(DocumentEvent)
        .where(
            DocumentEvent.organization_id == organization_id,
            DocumentEvent.document_id.in_(document_ids),
        )
        .order_by(DocumentEvent.created_at)
    )
    return list(db.scalars(stmt).all())
