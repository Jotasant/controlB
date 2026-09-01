"""Consultas e persistência sem commit para a infraestrutura transversal de documentos."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import false, or_, select
from sqlalchemy.orm import Session

from controlb.modules.documents.models import (
    BusinessDocument,
    DocumentEvent,
    DocumentRelation,
    DocumentSequence,
)
from controlb.modules.documents.schemas import DocumentCreate, DocumentUpdate

# Mapeamento de prefixos padronizados por categoria de negócio
DEFAULT_PREFIXES = {
    "crm.lead": "LEAD",
    "crm.opportunity": "OPP",
    "crm.proposal": "PROP",
    "sales.quotation": "ORC",
    "sales.order": "PV",
    "sales.pos_sale": "PDV",
    "sales.return": "DEV",
    "purchase.request": "SC",
    "purchase.quotation": "RFQ",
    "purchase.order": "PC",
    "purchase.replenishment": "REP",
    "inventory.transfer": "TRF",
    "inventory.movement": "MOVE",
    "inventory.import_batch": "IMPO",
    "inventory.receipt": "REC",
    "inventory.reservation": "RSV",
    "inventory.delivery": "ENT",
    "inventory.replenishment": "REP",
    "billing.request": "FAT",
    "billing.invoice": "FAT",
    "finance.fiscal_document": "DFE",
    "finance.payable": "PAG",
    "finance.receivable": "REC",
}


def next_document_number(
    db: Session,
    organization_id: uuid.UUID,
    category: str,
    prefix: str | None = None,
) -> str:
    """Gera número sequencial padronizado por organização, categoria e ano (ex: PV-2026-0001)."""
    current_year = datetime.now(UTC).year
    norm_cat = category.strip().lower()
    doc_prefix = prefix or DEFAULT_PREFIXES.get(norm_cat, norm_cat.split(".")[-1].upper()[:4])

    stmt = (
        select(DocumentSequence)
        .where(
            DocumentSequence.organization_id == organization_id,
            DocumentSequence.category == norm_cat,
            DocumentSequence.year == current_year,
        )
        .with_for_update()
    )
    seq = db.scalars(stmt).first()
    if not seq:
        seq = DocumentSequence(
            organization_id=organization_id,
            category=norm_cat,
            year=current_year,
            current_value=1,
            prefix=doc_prefix,
        )
        db.add(seq)
        db.flush()
        seq_val = 1
    else:
        seq.current_value += 1
        seq_val = seq.current_value
        db.flush()

    return f"{doc_prefix}-{current_year}-{seq_val:04d}"


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


def get_document_by_number(
    db: Session, organization_id: uuid.UUID, document_number: str
) -> BusinessDocument | None:
    stmt = select(BusinessDocument).where(
        BusinessDocument.organization_id == organization_id,
        BusinessDocument.document_number == document_number.strip(),
    )
    return db.scalars(stmt).first()


def create_document(
    db: Session,
    organization_id: uuid.UUID,
    data: DocumentCreate,
    created_by_id: uuid.UUID | None = None,
) -> BusinessDocument:
    doc_number = data.document_number
    if not doc_number:
        doc_number = next_document_number(db, organization_id, data.category)

    doc = BusinessDocument(
        organization_id=organization_id,
        category=data.category.strip().lower(),
        document_type=data.document_type.strip().upper(),
        native_id=data.native_id or uuid.uuid4(),
        document_number=doc_number.strip(),
        title=data.title.strip(),
        current_status=data.current_status.strip().upper(),
        priority=data.priority.strip().upper(),
        description=data.description,
        tags=data.tags,
        origin_module=data.origin_module.strip().upper(),
        responsible_id=data.responsible_id,
        payload=data.payload or {},
        issued_at=data.issued_at,
        completed_at=data.completed_at,
        created_by_id=created_by_id,
    )
    db.add(doc)
    db.flush()
    return doc


def update_document(
    db: Session,
    document: BusinessDocument,
    data: DocumentUpdate,
) -> BusinessDocument:
    for field, val in data.model_dump(exclude_unset=True).items():
        if val is not None:
            if field == "current_status":
                setattr(document, field, val.strip().upper())
            elif field == "priority":
                setattr(document, field, val.strip().upper())
            else:
                setattr(document, field, val)
    db.flush()
    return document


def delete_document(db: Session, document: BusinessDocument) -> None:
    db.delete(document)
    db.flush()


def list_documents(
    db: Session,
    organization_id: uuid.UUID,
    category: str | None = None,
    origin_module: str | None = None,
    current_status: str | None = None,
    responsible_id: uuid.UUID | None = None,
    search: str | None = None,
    authorized_document_types: set[str] | None = None,
    mapped_document_types: set[str] | None = None,
    allow_unmapped_document_types: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> list[BusinessDocument]:
    stmt = select(BusinessDocument).where(BusinessDocument.organization_id == organization_id)
    if mapped_document_types is not None:
        permission_conditions = []
        if authorized_document_types:
            permission_conditions.append(
                BusinessDocument.document_type.in_(authorized_document_types)
            )
        if allow_unmapped_document_types:
            permission_conditions.append(
                BusinessDocument.document_type.not_in(mapped_document_types)
            )
        stmt = stmt.where(
            or_(*permission_conditions) if permission_conditions else false()
        )
    if category:
        stmt = stmt.where(BusinessDocument.category == category.strip().lower())
    if origin_module:
        stmt = stmt.where(BusinessDocument.origin_module == origin_module.strip().upper())
    if current_status:
        stmt = stmt.where(BusinessDocument.current_status == current_status.strip().upper())
    if responsible_id:
        stmt = stmt.where(BusinessDocument.responsible_id == responsible_id)
    if search:
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                BusinessDocument.document_number.ilike(term),
                BusinessDocument.title.ilike(term),
                BusinessDocument.description.ilike(term),
            )
        )
    stmt = stmt.order_by(BusinessDocument.created_at.desc()).offset(offset).limit(limit)
    return list(db.scalars(stmt).all())


def get_relation(
    db: Session,
    parent_document_id: uuid.UUID,
    child_document_id: uuid.UUID,
    relation_type: str,
) -> DocumentRelation | None:
    stmt = select(DocumentRelation).where(
        DocumentRelation.parent_document_id == parent_document_id,
        DocumentRelation.child_document_id == child_document_id,
        DocumentRelation.relation_type == relation_type.strip().upper(),
    )
    return db.scalars(stmt).first()


def create_relation(
    db: Session,
    organization_id: uuid.UUID,
    parent_document_id: uuid.UUID,
    child_document_id: uuid.UUID,
    relation_type: str,
    relation_metadata: dict[str, Any] | None = None,
    created_by_id: uuid.UUID | None = None,
) -> DocumentRelation:
    relation = DocumentRelation(
        organization_id=organization_id,
        parent_document_id=parent_document_id,
        child_document_id=child_document_id,
        relation_type=relation_type.strip().upper(),
        relation_metadata=relation_metadata or {},
        created_by_id=created_by_id,
    )
    db.add(relation)
    db.flush()
    return relation


def delete_relation(db: Session, relation: DocumentRelation) -> None:
    db.delete(relation)
    db.flush()


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


def list_relations_by_parent(
    db: Session, parent_id: uuid.UUID, organization_id: uuid.UUID
) -> list[DocumentRelation]:
    stmt = select(DocumentRelation).where(
        DocumentRelation.organization_id == organization_id,
        DocumentRelation.parent_document_id == parent_id,
    )
    return list(db.scalars(stmt).all())


def list_relations_by_child(
    db: Session, child_id: uuid.UUID, organization_id: uuid.UUID
) -> list[DocumentRelation]:
    stmt = select(DocumentRelation).where(
        DocumentRelation.organization_id == organization_id,
        DocumentRelation.child_document_id == child_id,
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


def get_event_by_idempotency_key(
    db: Session, organization_id: uuid.UUID, idempotency_key: str
) -> DocumentEvent | None:
    stmt = select(DocumentEvent).where(
        DocumentEvent.organization_id == organization_id,
        DocumentEvent.idempotency_key == idempotency_key,
    )
    return db.scalars(stmt).first()


def create_event(
    db: Session,
    organization_id: uuid.UUID,
    document_id: uuid.UUID,
    event_type: str,
    previous_status: str | None = None,
    new_status: str | None = None,
    event_metadata: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
    created_by_id: uuid.UUID | None = None,
) -> DocumentEvent:
    event = DocumentEvent(
        organization_id=organization_id,
        document_id=document_id,
        event_type=event_type.strip().upper(),
        previous_status=previous_status.upper() if previous_status else None,
        new_status=new_status.upper() if new_status else None,
        event_metadata=event_metadata or {},
        idempotency_key=idempotency_key,
        created_by_id=created_by_id,
    )
    db.add(event)
    db.flush()
    return event


def list_events_by_document(
    db: Session, document_id: uuid.UUID, organization_id: uuid.UUID
) -> list[DocumentEvent]:
    stmt = (
        select(DocumentEvent)
        .where(
            DocumentEvent.organization_id == organization_id,
            DocumentEvent.document_id == document_id,
        )
        .order_by(DocumentEvent.created_at)
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
