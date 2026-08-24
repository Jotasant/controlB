"""Regras transversais de identidade, ciclo de vida, vínculos e timeline documental."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from controlb.modules.documents import repository, schemas
from controlb.modules.documents.models import BusinessDocument, DocumentEvent, DocumentRelation
from controlb.modules.identity.models import User


# ==============================================================================
# 1. GESTÃO CENTRALIZADA DE DOCUMENTOS TRANSACIONAIS (CRUD & Ciclo de Vida)
# ==============================================================================

def create_document(
    db: Session,
    organization_id: uuid.UUID,
    payload: schemas.DocumentCreate,
    current_user: User | None = None,
) -> BusinessDocument:
    """Cria um documento transacional centralizado com numeração padronizada e evento de criação."""
    user_id = current_user.id if current_user else None

    # Se não foi fornecido número legível, gera sequência atômica por categoria
    if not payload.document_number:
        payload.document_number = repository.next_document_number(
            db, organization_id, payload.category
        )

    document = repository.create_document(
        db, organization_id, payload, created_by_id=user_id
    )

    # Registra evento inicial CREATED na timeline
    repository.create_event(
        db,
        organization_id=organization_id,
        document_id=document.id,
        event_type="CREATED",
        previous_status=None,
        new_status=document.current_status,
        event_metadata={"origin_module": document.origin_module, "title": document.title},
        created_by_id=user_id,
    )

    return document


def update_document(
    db: Session,
    document_id: uuid.UUID,
    organization_id: uuid.UUID,
    payload: schemas.DocumentUpdate,
    current_user: User | None = None,
) -> BusinessDocument:
    """Atualiza metadados ou status do documento registrando eventos de transição."""
    document = get_document(db, document_id, organization_id)
    prev_status = document.current_status
    user_id = current_user.id if current_user else None

    updated = repository.update_document(db, document, payload)

    # Se houve alteração de status, grava evento na timeline
    if payload.current_status and payload.current_status.strip().upper() != prev_status:
        repository.create_event(
            db,
            organization_id=organization_id,
            document_id=document.id,
            event_type="STATUS_CHANGED",
            previous_status=prev_status,
            new_status=updated.current_status,
            event_metadata={"updated_fields": list(payload.model_dump(exclude_unset=True).keys())},
            created_by_id=user_id,
        )

    return updated


def change_document_status(
    db: Session,
    document_id: uuid.UUID,
    organization_id: uuid.UUID,
    new_status: str,
    reason: str | None = None,
    current_user: User | None = None,
) -> BusinessDocument:
    """Altera o status formal do documento com registro de justificativa/motivo na timeline."""
    document = get_document(db, document_id, organization_id)
    prev_status = document.current_status
    norm_status = new_status.strip().upper()
    user_id = current_user.id if current_user else None

    document.current_status = norm_status
    if norm_status in ("COMPLETED", "DELIVERED", "INVOICED", "CLOSED"):
        document.completed_at = datetime.now(UTC)

    meta: dict[str, Any] = {}
    if reason:
        meta["reason"] = reason

    repository.create_event(
        db,
        organization_id=organization_id,
        document_id=document.id,
        event_type="STATUS_CHANGED" if norm_status != "CANCELLED" else "CANCELLED",
        previous_status=prev_status,
        new_status=norm_status,
        event_metadata=meta,
        created_by_id=user_id,
    )
    db.flush()
    return document


def get_document(
    db: Session,
    document_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> BusinessDocument:
    """Obtém documento por ID garantindo isolamento multitenant."""
    document = repository.get_document_by_id(db, document_id, organization_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento não encontrado na organização.",
        )
    return document


def get_document_by_number(
    db: Session,
    organization_id: uuid.UUID,
    document_number: str,
) -> BusinessDocument:
    document = repository.get_document_by_number(db, organization_id, document_number)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento com número '{document_number}' não encontrado.",
        )
    return document


def list_documents(
    db: Session,
    organization_id: uuid.UUID,
    params: schemas.DocumentFilterParams | None = None,
) -> list[BusinessDocument]:
    """Consulta transversal com filtros de categoria, módulo, status, responsável e busca textual."""
    p = params or schemas.DocumentFilterParams()
    return repository.list_documents(
        db,
        organization_id=organization_id,
        category=p.category,
        origin_module=p.origin_module,
        current_status=p.current_status,
        responsible_id=p.responsible_id,
        search=p.search,
        limit=p.limit,
        offset=p.offset,
    )


# ==============================================================================
# 2. GRAFO DE RELACIONAMENTOS & RASTREABILIDADE (Directed Acyclic Graph)
# ==============================================================================

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
    """Cria uma aresta tipada e idempotente entre dois documentos da mesma organização."""
    if (
        isinstance(parent_document.organization_id, uuid.UUID)
        and parent_document.organization_id != organization_id
    ) or (
        isinstance(child_document.organization_id, uuid.UUID)
        and child_document.organization_id != organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é permitido relacionar documentos de organizações diferentes.",
        )
    if (
        isinstance(parent_document.id, uuid.UUID)
        and isinstance(child_document.id, uuid.UUID)
        and parent_document.id == child_document.id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Um documento não pode ser relacionado a ele mesmo.",
        )

    norm_type = relation_type.strip().upper()
    existing = repository.get_relation(
        db, parent_document.id, child_document.id, norm_type
    )
    if existing:
        return existing

    return repository.create_relation(
        db,
        organization_id=organization_id,
        parent_document_id=parent_document.id,
        child_document_id=child_document.id,
        relation_type=norm_type,
        relation_metadata=relation_metadata or {},
        created_by_id=created_by_id,
    )


def get_document_tree(
    db: Session,
    organization_id: uuid.UUID,
    document_id: uuid.UUID,
) -> schemas.DocumentTreeResponse:
    """Retorna a visão em árvore de um documento: Origem, Anteriores, Derivados e Timeline."""
    doc = get_document(db, document_id, organization_id)

    # Busca relações em que o documento é filho (antecessores)
    parent_relations = repository.list_relations_by_child(db, doc.id, organization_id)
    parent_ids = {r.parent_document_id for r in parent_relations}
    parent_docs = {d.id: d for d in repository.list_documents_by_ids(db, organization_id, parent_ids)}

    # Busca relações em que o documento é pai (sucessores / derivados)
    child_relations = repository.list_relations_by_parent(db, doc.id, organization_id)
    child_ids = {r.child_document_id for r in child_relations}
    child_docs = {d.id: d for d in repository.list_documents_by_ids(db, organization_id, child_ids)}

    # Timeline de eventos
    events = repository.list_events_by_document(db, doc.id, organization_id)

    origin_nodes: list[schemas.DocumentNodeResponse] = []
    previous_nodes: list[schemas.DocumentNodeResponse] = []
    derived_nodes: list[schemas.DocumentNodeResponse] = []
    related_nodes: list[schemas.DocumentNodeResponse] = []
    dep_nodes: list[schemas.DocumentNodeResponse] = []

    for rel in parent_relations:
        parent = parent_docs.get(rel.parent_document_id)
        if parent:
            node = schemas.DocumentNodeResponse.model_validate(parent)
            rel_type = rel.relation_type.upper()
            if rel_type in ("ORIGINATED_FROM", "ORIGIN"):
                origin_nodes.append(node)
            elif rel_type in ("DEPENDS_ON", "DEPENDENCY"):
                dep_nodes.append(node)
            else:
                previous_nodes.append(node)

    for rel in child_relations:
        child = child_docs.get(rel.child_document_id)
        if child:
            node = schemas.DocumentNodeResponse.model_validate(child)
            rel_type = rel.relation_type.upper()
            if rel_type in ("GENERATED", "DERIVED", "CONVERTED_TO"):
                derived_nodes.append(node)
            else:
                related_nodes.append(node)

    return schemas.DocumentTreeResponse(
        document=schemas.DocumentResponse.model_validate(doc),
        origin=origin_nodes,
        previous=previous_nodes,
        derived=derived_nodes,
        related=related_nodes,
        dependencies=dep_nodes,
        timeline=[schemas.DocumentEventResponse.model_validate(e) for e in events],
    )


# ==============================================================================
# 3. MÉTODOS DE COMPATIBILIDADE RETROATIVA (Legacy ensure_document & get_chain)
# ==============================================================================

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
    category: str | None = None,
    title: str | None = None,
    origin_module: str | None = None,
) -> BusinessDocument:
    """Obtém ou registra a identidade global sem quebrar código legado."""
    norm_type = document_type.strip().upper()
    norm_status = current_status.strip().upper()
    norm_cat = category or norm_type.lower()

    document = repository.get_document_by_native(
        db, organization_id, norm_type, native_id
    )
    if document:
        document.document_number = document_number.strip()
        document.current_status = norm_status
        if title:
            document.title = title.strip()
        if issued_at is not None:
            document.issued_at = issued_at
        return document

    document = BusinessDocument(
        organization_id=organization_id,
        category=norm_cat,
        document_type=norm_type,
        native_id=native_id,
        document_number=document_number.strip(),
        title=title.strip() if title else document_number.strip(),
        current_status=norm_status,
        origin_module=origin_module or "DOCUMENTS",
        issued_at=issued_at,
        created_by_id=created_by_id,
    )
    db.add(document)
    db.flush()
    return document


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
    """Acrescenta um evento à timeline imutável."""
    if (
        isinstance(document.organization_id, uuid.UUID)
        and document.organization_id != organization_id
    ):
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

    event = repository.create_event(
        db,
        organization_id=organization_id,
        document_id=document.id,
        event_type=event_type,
        previous_status=previous_status,
        new_status=new_status,
        event_metadata=event_metadata,
        idempotency_key=idempotency_key,
        created_by_id=created_by_id,
    )
    if new_status:
        document.current_status = new_status.upper()
    return event


def _auto_ensure_native_document(
    db: Session,
    organization_id: uuid.UUID,
    document_type: str,
    native_id: uuid.UUID,
) -> BusinessDocument | None:
    """Reconstrói sob demanda nós e arestas nativas para visualização no grafo."""
    norm_type = document_type.strip().upper()

    if norm_type == "SALES_QUOTE":
        from controlb.modules.crm.models import Opportunity
        from controlb.modules.sales.models import SalesOrder, SalesQuote
        quote = db.query(SalesQuote).filter(
            SalesQuote.id == native_id,
            SalesQuote.organization_id == organization_id,
        ).first()
        if quote:
            doc = ensure_document(
                db,
                organization_id=organization_id,
                category="sales.quotation",
                document_type="SALES_QUOTE",
                native_id=quote.id,
                document_number=quote.quote_number,
                title=f"Cotação {quote.quote_number} - {quote.customer_name}",
                current_status=quote.status,
                origin_module="SALES",
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
                    Opportunity.organization_id == organization_id,
                ).first()
                if opp:
                    opp_doc = ensure_document(
                        db,
                        organization_id=organization_id,
                        category="crm.opportunity",
                        document_type="OPPORTUNITY",
                        native_id=opp.id,
                        document_number=opp.title,
                        title=opp.title,
                        current_status=opp.stage,
                        origin_module="CRM",
                        created_by_id=opp.assigned_to_id,
                        issued_at=opp.created_at,
                    )
                    relate_documents(
                        db,
                        organization_id=organization_id,
                        parent_document=opp_doc,
                        child_document=doc,
                        relation_type="generated",
                    )
            return doc

    elif norm_type == "SALES_ORDER":
        from controlb.modules.sales.models import SalesOrder, SalesQuote
        order = db.query(SalesOrder).filter(
            SalesOrder.id == native_id,
            SalesOrder.organization_id == organization_id,
        ).first()
        if order:
            doc = ensure_document(
                db,
                organization_id=organization_id,
                category="sales.order",
                document_type="SALES_ORDER",
                native_id=order.id,
                document_number=order.order_number,
                title=f"Pedido {order.order_number} - {order.customer_name}",
                current_status=order.status,
                origin_module="SALES",
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
                    SalesQuote.organization_id == organization_id,
                ).first()
                if quote:
                    quote_doc = ensure_document(
                        db,
                        organization_id=organization_id,
                        category="sales.quotation",
                        document_type="SALES_QUOTE",
                        native_id=quote.id,
                        document_number=quote.quote_number,
                        title=f"Cotação {quote.quote_number} - {quote.customer_name}",
                        current_status=quote.status,
                        origin_module="SALES",
                        created_by_id=quote.created_by_id,
                        issued_at=quote.created_at,
                    )
                    relate_documents(
                        db,
                        organization_id=organization_id,
                        parent_document=quote_doc,
                        child_document=doc,
                        relation_type="generated",
                    )
            return doc

    elif norm_type == "OPPORTUNITY":
        from controlb.modules.crm.models import Lead, Opportunity
        opp = db.query(Opportunity).filter(
            Opportunity.id == native_id,
            Opportunity.organization_id == organization_id,
        ).first()
        if opp:
            doc = ensure_document(
                db,
                organization_id=organization_id,
                category="crm.opportunity",
                document_type="OPPORTUNITY",
                native_id=opp.id,
                document_number=opp.title,
                title=opp.title,
                current_status=opp.stage,
                origin_module="CRM",
                created_by_id=opp.assigned_to_id,
                issued_at=opp.created_at,
            )
            if opp.lead_id:
                lead = db.query(Lead).filter(
                    Lead.id == opp.lead_id,
                    Lead.organization_id == organization_id,
                ).first()
                if lead:
                    lead_doc = ensure_document(
                        db,
                        organization_id=organization_id,
                        category="crm.lead",
                        document_type="LEAD",
                        native_id=lead.id,
                        document_number=lead.name,
                        title=lead.name,
                        current_status=lead.status,
                        origin_module="CRM",
                        created_by_id=lead.assigned_to_id,
                        issued_at=lead.created_at,
                    )
                    relate_documents(
                        db,
                        organization_id=organization_id,
                        parent_document=lead_doc,
                        child_document=doc,
                        relation_type="originated_from",
                    )
            return doc

    elif norm_type == "PURCHASE_REQUEST":
        from controlb.modules.purchasing.models import PurchaseRequest
        pr = db.query(PurchaseRequest).filter(
            PurchaseRequest.id == native_id,
            PurchaseRequest.organization_id == organization_id,
        ).first()
        if pr:
            doc = ensure_document(
                db,
                organization_id=organization_id,
                category="purchase.request",
                document_type="PURCHASE_REQUEST",
                native_id=pr.id,
                document_number=pr.request_number,
                title=f"Solicitação {pr.request_number}",
                current_status=pr.status,
                origin_module="PURCHASING",
                created_by_id=pr.requester_id,
                issued_at=pr.created_at,
            )
            return doc

    elif norm_type == "PURCHASE_ORDER":
        from controlb.modules.purchasing.models import PurchaseOrder, PurchaseRequest
        po = db.query(PurchaseOrder).filter(
            PurchaseOrder.id == native_id,
            PurchaseOrder.organization_id == organization_id,
        ).first()
        if po:
            doc = ensure_document(
                db,
                organization_id=organization_id,
                category="purchase.order",
                document_type="PURCHASE_ORDER",
                native_id=po.id,
                document_number=po.order_number,
                title=f"Ordem de Compra {po.order_number}",
                current_status=po.status,
                origin_module="PURCHASING",
                created_by_id=po.buyer_id,
                issued_at=po.created_at,
            )
            if po.purchase_request_id:
                pr = db.query(PurchaseRequest).filter(
                    PurchaseRequest.id == po.purchase_request_id,
                    PurchaseRequest.organization_id == organization_id,
                ).first()
                if pr:
                    pr_doc = ensure_document(
                        db,
                        organization_id=organization_id,
                        category="purchase.request",
                        document_type="PURCHASE_REQUEST",
                        native_id=pr.id,
                        document_number=pr.request_number,
                        title=f"Solicitação {pr.request_number}",
                        current_status=pr.status,
                        origin_module="PURCHASING",
                        created_by_id=pr.requester_id,
                        issued_at=pr.created_at,
                    )
                    relate_documents(
                        db,
                        organization_id=organization_id,
                        parent_document=pr_doc,
                        child_document=doc,
                        relation_type="generated",
                    )
            return doc

    return None


def get_document_chain(
    db: Session,
    *,
    organization_id: uuid.UUID,
    document_type: str,
    native_id: uuid.UUID,
) -> schemas.DocumentChainResponse:
    """Busca BFS completa do grafo documental em torno de um documento raiz."""
    normalized_type = document_type.strip().upper()
    root = repository.get_document_by_native(
        db, organization_id, normalized_type, native_id
    )
    if not root:
        root = _auto_ensure_native_document(
            db, organization_id, normalized_type, native_id
        )
    if not root:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento raiz {normalized_type}:{native_id} não encontrado.",
        )

    visited_document_ids: set[uuid.UUID] = {root.id}
    visited_relations: dict[tuple[uuid.UUID, uuid.UUID, str], DocumentRelation] = {}
    frontier: set[uuid.UUID] = {root.id}

    while frontier:
        next_frontier: set[uuid.UUID] = set()
        relations = repository.list_relations_touching(db, organization_id, frontier)
        for relation in relations:
            key = (
                relation.parent_document_id,
                relation.child_document_id,
                relation.relation_type,
            )
            if key not in visited_relations:
                visited_relations[key] = relation

            for doc_id in (relation.parent_document_id, relation.child_document_id):
                if doc_id not in visited_document_ids:
                    visited_document_ids.add(doc_id)
                    next_frontier.add(doc_id)

        frontier = next_frontier

    documents = repository.list_documents_by_ids(
        db, organization_id, visited_document_ids
    )
    events = repository.list_events_by_document_ids(
        db, organization_id, visited_document_ids
    )

    return schemas.DocumentChainResponse(
        root_document_id=root.id,
        documents=[schemas.DocumentNodeResponse.model_validate(doc) for doc in documents],
        relations=[
            schemas.DocumentRelationResponse.model_validate(rel)
            for rel in visited_relations.values()
        ],
        events=[schemas.DocumentEventResponse.model_validate(event) for event in events],
    )
