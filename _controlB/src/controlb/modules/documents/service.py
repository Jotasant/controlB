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


def _auto_ensure_native_document(
    db: Session,
    organization_id: uuid.UUID,
    document_type: str,
    native_id: uuid.UUID,
) -> BusinessDocument | None:
    norm_type = document_type.strip().upper()
    
    if norm_type == "SALES_QUOTE":
        from controlb.modules.sales.models import SalesQuote, SalesOrder
        from controlb.modules.crm.models import Opportunity
        from controlb.modules.inventory.models import StockReservation
        quote = db.query(SalesQuote).filter(
            SalesQuote.id == native_id,
            SalesQuote.organization_id == organization_id
        ).first()
        if quote:
            doc = ensure_document(
                db,
                organization_id=organization_id,
                document_type="SALES_QUOTE",
                native_id=quote.id,
                document_number=quote.quote_number,
                current_status=quote.status,
                created_by_id=quote.created_by_id,
                issued_at=quote.created_at,
            )
            record_event(
                db,
                organization_id=organization_id,
                document=doc,
                event_type="CREATED",
                new_status=quote.status,
                created_by_id=quote.created_by_id,
                idempotency_key=f"sales-quote:{quote.id}:created",
            )
            if quote.opportunity_id:
                opp = db.query(Opportunity).filter(
                    Opportunity.id == quote.opportunity_id,
                    Opportunity.organization_id == organization_id
                ).first()
                if opp:
                    opp_doc = ensure_document(
                        db,
                        organization_id=organization_id,
                        document_type="OPPORTUNITY",
                        native_id=opp.id,
                        document_number=opp.title,
                        current_status=opp.stage,
                        created_by_id=opp.created_by_id,
                        issued_at=opp.created_at,
                    )
                    relate_documents(
                        db,
                        organization_id=organization_id,
                        parent_document=opp_doc,
                        child_document=doc,
                        relation_type="GENERATED_QUOTE",
                    )
            orders = db.query(SalesOrder).filter(
                SalesOrder.sales_quote_id == quote.id,
                SalesOrder.organization_id == organization_id
            ).all()
            for ord_item in orders:
                ord_doc = ensure_document(
                    db,
                    organization_id=organization_id,
                    document_type="SALES_ORDER",
                    native_id=ord_item.id,
                    document_number=ord_item.order_number,
                    current_status=ord_item.status,
                    created_by_id=ord_item.created_by_id,
                    issued_at=ord_item.created_at,
                )
                relate_documents(
                    db,
                    organization_id=organization_id,
                    parent_document=doc,
                    child_document=ord_doc,
                    relation_type="CONVERTED_TO",
                )
                reservations = db.query(StockReservation).filter(
                    StockReservation.sales_order_id == ord_item.id,
                    StockReservation.organization_id == organization_id
                ).all()
                for res in reservations:
                    res_doc = ensure_document(
                        db,
                        organization_id=organization_id,
                        document_type="STOCK_RESERVATION",
                        native_id=res.id,
                        document_number=f"RES-{str(res.id)[:8].upper()}",
                        current_status=res.status,
                        created_by_id=res.created_by_id,
                        issued_at=res.created_at,
                    )
                    relate_documents(
                        db,
                        organization_id=organization_id,
                        parent_document=ord_doc,
                        child_document=res_doc,
                        relation_type="RESERVED_STOCK",
                    )
            return doc

    elif norm_type == "SALES_ORDER":
        from controlb.modules.sales.models import SalesOrder, SalesQuote
        from controlb.modules.inventory.models import StockReservation
        order = db.query(SalesOrder).filter(
            SalesOrder.id == native_id,
            SalesOrder.organization_id == organization_id
        ).first()
        if order:
            doc = ensure_document(
                db,
                organization_id=organization_id,
                document_type="SALES_ORDER",
                native_id=order.id,
                document_number=order.order_number,
                current_status=order.status,
                created_by_id=order.created_by_id,
                issued_at=order.created_at,
            )
            record_event(
                db,
                organization_id=organization_id,
                document=doc,
                event_type="CREATED",
                new_status=order.status,
                created_by_id=order.created_by_id,
                idempotency_key=f"sales-order:{order.id}:created",
            )
            if order.sales_quote_id:
                quote = db.query(SalesQuote).filter(
                    SalesQuote.id == order.sales_quote_id,
                    SalesQuote.organization_id == organization_id
                ).first()
                if quote:
                    q_doc = ensure_document(
                        db,
                        organization_id=organization_id,
                        document_type="SALES_QUOTE",
                        native_id=quote.id,
                        document_number=quote.quote_number,
                        current_status=quote.status,
                        created_by_id=quote.created_by_id,
                        issued_at=quote.created_at,
                    )
                    relate_documents(
                        db,
                        organization_id=organization_id,
                        parent_document=q_doc,
                        child_document=doc,
                        relation_type="CONVERTED_TO",
                    )
            reservations = db.query(StockReservation).filter(
                StockReservation.sales_order_id == order.id,
                StockReservation.organization_id == organization_id
            ).all()
            for res in reservations:
                res_doc = ensure_document(
                    db,
                    organization_id=organization_id,
                    document_type="STOCK_RESERVATION",
                    native_id=res.id,
                    document_number=f"RES-{str(res.id)[:8].upper()}",
                    current_status=res.status,
                    created_by_id=res.created_by_id,
                    issued_at=res.created_at,
                )
            invoices = db.query(Invoice).filter(
                Invoice.sales_order_id == order.id,
                Invoice.organization_id == organization_id
            ).all()
            for inv in invoices:
                inv_doc = ensure_document(
                    db,
                    organization_id=organization_id,
                    document_type="INVOICE",
                    native_id=inv.id,
                    document_number=inv.invoice_number,
                    current_status=inv.status,
                    created_by_id=inv.created_by_id,
                    issued_at=inv.created_at,
                )
                relate_documents(
                    db,
                    organization_id=organization_id,
                    parent_document=doc,
                    child_document=inv_doc,
                    relation_type="INVOICED_BY",
                )
            return doc

    elif norm_type == "INVOICE":
        from controlb.modules.billing.models import Invoice
        from controlb.modules.sales.models import SalesOrder
        inv = db.query(Invoice).filter(
            Invoice.id == native_id,
            Invoice.organization_id == organization_id
        ).first()
        if inv:
            doc = ensure_document(
                db,
                organization_id=organization_id,
                document_type="INVOICE",
                native_id=inv.id,
                document_number=inv.invoice_number,
                current_status=inv.status,
                created_by_id=inv.created_by_id,
                issued_at=inv.created_at,
            )
            record_event(
                db,
                organization_id=organization_id,
                document=doc,
                event_type="CREATED",
                new_status=inv.status,
                created_by_id=inv.created_by_id,
                idempotency_key=f"invoice:{inv.id}:created",
            )
            if inv.sales_order_id:
                order = db.query(SalesOrder).filter(
                    SalesOrder.id == inv.sales_order_id,
                    SalesOrder.organization_id == organization_id
                ).first()
                if order:
                    ord_doc = ensure_document(
                        db,
                        organization_id=organization_id,
                        document_type="SALES_ORDER",
                        native_id=order.id,
                        document_number=order.order_number,
                        current_status=order.status,
                        created_by_id=order.created_by_id,
                        issued_at=order.created_at,
                    )
                    relate_documents(
                        db,
                        organization_id=organization_id,
                        parent_document=ord_doc,
                        child_document=doc,
                        relation_type="INVOICED_BY",
                    )
            return doc

    elif norm_type == "STOCK_RESERVATION":
        from controlb.modules.inventory.models import StockReservation
        from controlb.modules.sales.models import SalesOrder
        res = db.query(StockReservation).filter(
            StockReservation.id == native_id,
            StockReservation.organization_id == organization_id
        ).first()
        if res:
            doc = ensure_document(
                db,
                organization_id=organization_id,
                document_type="STOCK_RESERVATION",
                native_id=res.id,
                document_number=f"RES-{str(res.id)[:8].upper()}",
                current_status=res.status,
                created_by_id=res.created_by_id,
                issued_at=res.created_at,
            )
            record_event(
                db,
                organization_id=organization_id,
                document=doc,
                event_type="CREATED",
                new_status=res.status,
                created_by_id=res.created_by_id,
                idempotency_key=f"stock-reservation:{res.id}:created",
            )
            if res.sales_order_id:
                order = db.query(SalesOrder).filter(
                    SalesOrder.id == res.sales_order_id,
                    SalesOrder.organization_id == organization_id
                ).first()
                if order:
                    ord_doc = ensure_document(
                        db,
                        organization_id=organization_id,
                        document_type="SALES_ORDER",
                        native_id=order.id,
                        document_number=order.order_number,
                        current_status=order.status,
                        created_by_id=order.created_by_id,
                        issued_at=order.created_at,
                    )
                    relate_documents(
                        db,
                        organization_id=organization_id,
                        parent_document=ord_doc,
                        child_document=doc,
                        relation_type="RESERVED_STOCK",
                    )
            return doc

    elif norm_type == "OPPORTUNITY":
        from controlb.modules.crm.models import Opportunity
        from controlb.modules.sales.models import SalesQuote
        opp = db.query(Opportunity).filter(
            Opportunity.id == native_id,
            Opportunity.organization_id == organization_id
        ).first()
        if opp:
            doc = ensure_document(
                db,
                organization_id=organization_id,
                document_type="OPPORTUNITY",
                native_id=opp.id,
                document_number=opp.title,
                current_status=opp.stage,
                created_by_id=opp.created_by_id,
                issued_at=opp.created_at,
            )
            record_event(
                db,
                organization_id=organization_id,
                document=doc,
                event_type="CREATED",
                new_status=opp.stage,
                created_by_id=opp.created_by_id,
                idempotency_key=f"opportunity:{opp.id}:created",
            )
            quotes = db.query(SalesQuote).filter(
                SalesQuote.opportunity_id == opp.id,
                SalesQuote.organization_id == organization_id
            ).all()
            for q in quotes:
                q_doc = ensure_document(
                    db,
                    organization_id=organization_id,
                    document_type="SALES_QUOTE",
                    native_id=q.id,
                    document_number=q.quote_number,
                    current_status=q.status,
                    created_by_id=q.created_by_id,
                    issued_at=q.created_at,
                )
                relate_documents(
                    db,
                    organization_id=organization_id,
                    parent_document=doc,
                    child_document=q_doc,
                    relation_type="GENERATED_QUOTE",
                )
            return doc

    return None


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
        root = _auto_ensure_native_document(db, organization_id, document_type, native_id)

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
