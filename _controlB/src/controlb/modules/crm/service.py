"""
modules/crm/service.py - Regras de Negócio e Serviços do CRM
"""

import uuid
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from controlb.modules.identity.models import User
from controlb.modules.crm import models, repository, schemas


DEFAULT_STAGES = [
    {"code": "PROSPECTING", "name": "Prospecção", "color": "#10b981", "order": 0, "is_won": False, "is_lost": False, "is_system": True},
    {"code": "QUALIFICATION", "name": "Qualificação", "color": "#3b82f6", "order": 1, "is_won": False, "is_lost": False, "is_system": True},
    {"code": "PROPOSAL", "name": "Proposta Comercial", "color": "#f59e0b", "order": 2, "is_won": False, "is_lost": False, "is_system": True},
    {"code": "NEGOTIATION", "name": "Negociação", "color": "#8b5cf6", "order": 3, "is_won": False, "is_lost": False, "is_system": True},
    {"code": "WON", "name": "Ganho / Fechado", "color": "#10b981", "order": 4, "is_won": True, "is_lost": False, "is_system": True},
    {"code": "LOST", "name": "Perdido", "color": "#ef4444", "order": 5, "is_won": False, "is_lost": True, "is_system": True},
]


def list_stages(db: Session, organization_id: uuid.UUID) -> list[models.CRMStage]:
    stages = repository.list_stages(db, organization_id)
    if not stages:
        # Seed inicial automático para organizações existentes
        for stg_data in DEFAULT_STAGES:
            stage_obj = models.CRMStage(
                organization_id=organization_id,
                code=stg_data["code"],
                name=stg_data["name"],
                color=stg_data["color"],
                order=stg_data["order"],
                is_won=stg_data["is_won"],
                is_lost=stg_data["is_lost"],
                is_system=stg_data["is_system"]
            )
            repository.create_stage(db, stage_obj)
        stages = repository.list_stages(db, organization_id)
    return stages


def create_stage(db: Session, organization_id: uuid.UUID, payload: schemas.CRMStageCreate) -> models.CRMStage:
    code_norm = payload.code.strip().upper().replace(" ", "_")
    existing = repository.get_stage_by_code(db, code_norm, organization_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Já existe uma etapa com o código '{code_norm}' nesta organização."
        )

    current_stages = repository.list_stages(db, organization_id)
    calculated_order = payload.order if payload.order > 0 else len(current_stages)

    stage = models.CRMStage(
        organization_id=organization_id,
        code=code_norm,
        name=payload.name.strip(),
        color=payload.color.strip() or "#10b981",
        order=calculated_order,
        is_won=payload.is_won,
        is_lost=payload.is_lost,
        is_system=payload.is_system
    )
    return repository.create_stage(db, stage)


def update_stage(
    db: Session,
    stage_id: uuid.UUID,
    organization_id: uuid.UUID,
    payload: schemas.CRMStageUpdate
) -> models.CRMStage:
    stage = repository.get_stage_by_id(db, stage_id, organization_id)
    if not stage:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Etapa não encontrada.")

    if payload.name is not None:
        stage.name = payload.name.strip()
    if payload.color is not None:
        stage.color = payload.color.strip()
    if payload.order is not None:
        stage.order = payload.order
    if payload.is_won is not None:
        stage.is_won = payload.is_won
    if payload.is_lost is not None:
        stage.is_lost = payload.is_lost

    return repository.update_stage(db, stage)


def delete_stage(db: Session, stage_id: uuid.UUID, organization_id: uuid.UUID) -> dict:
    stage = repository.get_stage_by_id(db, stage_id, organization_id)
    if not stage:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Etapa não encontrada.")

    # Validação de integridade referencial: não deletar etapas que possuem oportunidades ativas
    opp_count = repository.count_opportunities_in_stage(db, stage.code, organization_id)
    if opp_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não é possível excluir a etapa '{stage.name}' pois existem {opp_count} oportunidade(s) associadas a ela."
        )

    repository.delete_stage(db, stage)
    return {"message": f"Etapa '{stage.name}' excluída com sucesso."}


def _get_lead_document(
    db: Session,
    lead: models.Lead,
    organization_id: uuid.UUID,
):
    """Resolve e valida o cabeçalho canônico vinculado ao Lead."""
    from controlb.modules.documents import service as documents_service

    if not lead.document_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O Lead não possui identidade documental e requer saneamento.",
        )

    document = documents_service.get_document(db, lead.document_id, organization_id)
    if document.document_type != "LEAD" or document.native_id != lead.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O cabeçalho documental vinculado ao Lead é inconsistente.",
        )

    lead.name = document.title
    lead.status = document.current_status
    lead.assigned_to_id = document.responsible_id
    return document


def create_lead(
    db: Session,
    organization_id: uuid.UUID,
    payload: schemas.LeadCreate,
    current_user: User | None = None,
) -> models.Lead:
    from controlb.modules.identity import service as identity_service, schemas as identity_schemas
    from controlb.modules.sales import service as sales_service, schemas as sales_schemas, repository as sales_repo

    customer_id = payload.customer_id
    if customer_id:
        cust = sales_repo.get_customer_by_id(db, customer_id, organization_id)
        if not cust:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente especificado não encontrado no módulo de Vendas.")
    else:
        customer_name = payload.company_name.strip() if payload.company_name else payload.name.strip()
        person_type = payload.person_type or ("PJ" if payload.company_name else "PF")

        # Criação obrigatória/automática do Cliente em Vendas e Contato no Identity (Odoo Partner Pattern)
        contact = identity_service.create_contact(
            db,
            organization_id,
            identity_schemas.ContactCreate(
                person_type=person_type,
                name=customer_name,
                trade_name=payload.name.strip() if payload.company_name else None,
                full_name=payload.name.strip(),
                document=payload.document.strip() if payload.document else None,
                email=payload.email.strip() if payload.email else None,
                phone=payload.phone.strip() if payload.phone else None,
                position="Contato Comercial (Lead)",
                is_customer=True,
                origin_module="CRM",
                notes=f"Origem Lead CRM: {payload.source}"
            )
        )
        doc = payload.document.strip() if payload.document else f"LEAD-{uuid.uuid4().hex[:8].upper()}"

        cust = sales_service.create_customer(
            db,
            organization_id,
            sales_schemas.CustomerCreate(
                person_type=person_type,
                document=doc,
                name=customer_name,
                trade_name=payload.name.strip() if payload.company_name else None,
                email=payload.email.strip() if payload.email else None,
                phone=payload.phone.strip() if payload.phone else None,
                contact_id=contact.id,
                notes=f"Criado automaticamente a partir de Lead CRM ({payload.source})"
            )
        )
        customer_id = cust.id

    from controlb.modules.documents import schemas as document_schemas
    from controlb.modules.documents import service as documents_service

    lead_id = uuid.uuid4()
    lead_document = documents_service.create_document(
        db,
        organization_id=organization_id,
        payload=document_schemas.DocumentCreate(
            category="crm.lead",
            document_type="LEAD",
            native_id=lead_id,
            title=payload.name.strip(),
            current_status=payload.status,
            description=payload.notes,
            origin_module="CRM",
            responsible_id=payload.assigned_to_id,
        ),
        current_user=current_user,
    )

    lead = models.Lead(
        id=lead_id,
        organization_id=organization_id,
        document_id=lead_document.id,
        customer_id=customer_id,
        name=lead_document.title,
        company_name=payload.company_name.strip() if payload.company_name else None,
        email=payload.email.strip() if payload.email else None,
        phone=payload.phone.strip() if payload.phone else None,
        source=payload.source,
        status=lead_document.current_status,
        notes=payload.notes,
        assigned_to_id=payload.assigned_to_id
    )
    return repository.create_lead(db, lead)


def list_leads(db: Session, organization_id: uuid.UUID, status: str | None = None, current_user: User | None = None) -> list[models.Lead]:
    user_ids = None
    if current_user:
        from controlb.modules.identity import service as identity_service
        user_ids = identity_service.get_accessible_user_ids(db, current_user, module_category="SALES")
    leads = repository.list_leads(db, organization_id, status, user_ids=user_ids)
    for lead in leads:
        _get_lead_document(db, lead, organization_id)
    return leads


def update_lead(
    db: Session,
    lead_id: uuid.UUID,
    organization_id: uuid.UUID,
    payload: schemas.LeadUpdate,
    current_user: User | None = None,
) -> models.Lead:
    lead = repository.get_lead_by_id(db, lead_id, organization_id)
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead não encontrado.")
    
    lead_document = _get_lead_document(db, lead, organization_id)
    if payload.name is not None:
        lead.name = payload.name.strip()
    if payload.company_name is not None:
        lead.company_name = payload.company_name.strip()
    if payload.email is not None:
        lead.email = payload.email.strip()
    if payload.phone is not None:
        lead.phone = payload.phone.strip()
    if payload.source is not None:
        lead.source = payload.source
    if payload.status is not None:
        lead.status = payload.status
    if payload.notes is not None:
        lead.notes = payload.notes
    if payload.assigned_to_id is not None:
        lead.assigned_to_id = payload.assigned_to_id
    if payload.customer_id is not None:
        lead.customer_id = payload.customer_id

    from controlb.modules.documents import schemas as document_schemas
    from controlb.modules.documents import service as documents_service

    document_changes: dict = {}
    if payload.name is not None:
        document_changes["title"] = lead.name
    if payload.status is not None:
        document_changes["current_status"] = lead.status
    if payload.notes is not None:
        document_changes["description"] = lead.notes
    if payload.assigned_to_id is not None:
        document_changes["responsible_id"] = lead.assigned_to_id

    if document_changes:
        documents_service.update_document(
            db,
            lead_document.id,
            organization_id,
            document_schemas.DocumentUpdate(**document_changes),
            current_user=current_user,
        )

    lead.name = lead_document.title
    lead.status = lead_document.current_status
    lead.assigned_to_id = lead_document.responsible_id
    return repository.update_lead(db, lead)


def get_opportunity_document(
    db: Session,
    opportunity: models.Opportunity,
    organization_id: uuid.UUID,
):
    """Resolve o cabeçalho canônico sem expor a persistência de Documents."""
    from controlb.modules.documents import service as documents_service

    if not opportunity.document_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A Oportunidade não possui identidade documental e requer saneamento.",
        )

    document = documents_service.get_document(
        db, opportunity.document_id, organization_id
    )
    if document.document_type != "OPPORTUNITY" or document.native_id != opportunity.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O cabeçalho documental vinculado à Oportunidade é inconsistente.",
        )

    opportunity.title = document.title
    opportunity.stage = document.current_status
    opportunity.assigned_to_id = document.responsible_id
    return document


def transition_opportunity_stage(
    db: Session,
    opportunity: models.Opportunity,
    organization_id: uuid.UUID,
    new_stage: str,
    *,
    current_user: User | None = None,
    event_type: str = "STAGE_CHANGED",
    event_metadata: dict | None = None,
    idempotency_key: str | None = None,
    record_if_unchanged: bool = False,
) -> models.Opportunity:
    """Única porta para transições do funil, inclusive quando iniciadas por Vendas."""
    from controlb.modules.documents import service as documents_service

    document = get_opportunity_document(db, opportunity, organization_id)
    previous_stage = document.current_status
    normalized_stage = new_stage.strip().upper()
    if normalized_stage == previous_stage and not record_if_unchanged:
        return opportunity

    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=document,
        event_type=event_type,
        previous_status=previous_stage,
        new_status=normalized_stage,
        created_by_id=current_user.id if current_user else None,
        event_metadata=event_metadata,
        idempotency_key=idempotency_key,
    )
    opportunity.stage = document.current_status
    db.add(opportunity)
    db.flush()
    return opportunity


def create_opportunity(
    db: Session,
    organization_id: uuid.UUID,
    payload: schemas.OpportunityCreate,
    current_user: User | None = None,
) -> models.Opportunity:
    customer_id = payload.customer_id
    customer_name = payload.customer_name.strip() if payload.customer_name else ""
    contact_id = payload.contact_id
    source_lead = None

    if payload.lead_id:
        source_lead = repository.get_lead_by_id(db, payload.lead_id, organization_id)
        if not source_lead:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O Lead de origem não pertence à organização.",
            )

    if customer_id:
        from controlb.modules.sales import repository as sales_repo
        cust = sales_repo.get_customer_by_id(db, customer_id, organization_id)
        if cust:
            if not customer_name:
                customer_name = cust.trade_name or cust.name
            if not contact_id and cust.contact_id:
                contact_id = cust.contact_id

    from controlb.modules.documents import schemas as document_schemas
    from controlb.modules.documents import service as documents_service

    opportunity_id = uuid.uuid4()
    created_at = models.utcnow()
    opportunity_document = documents_service.create_document(
        db,
        organization_id=organization_id,
        payload=document_schemas.DocumentCreate(
            category="crm.opportunity",
            document_type="OPPORTUNITY",
            native_id=opportunity_id,
            title=payload.title.strip(),
            current_status=payload.stage,
            priority=payload.priority,
            description=payload.loss_reason,
            origin_module="CRM",
            responsible_id=payload.assigned_to_id,
            issued_at=created_at,
        ),
        current_user=current_user,
    )

    opp = models.Opportunity(
        id=opportunity_id,
        organization_id=organization_id,
        document_id=opportunity_document.id,
        lead_id=payload.lead_id,
        customer_id=customer_id,
        contact_id=contact_id,
        title=opportunity_document.title,
        customer_name=customer_name or "Cliente Não Identificado",
        estimated_amount=payload.estimated_amount,
        probability_percent=payload.probability_percent,
        expected_closing_date=payload.expected_closing_date,
        stage=opportunity_document.current_status,
        loss_reason=payload.loss_reason,
        assigned_to_id=opportunity_document.responsible_id,
        created_at=created_at,
        updated_at=created_at,
    )

    if source_lead:
        lead_doc = _get_lead_document(db, source_lead, organization_id)
        documents_service.relate_documents(
            db,
            organization_id=organization_id,
            parent_document=lead_doc,
            child_document=opportunity_document,
            relation_type="originated_from",
            created_by_id=current_user.id if current_user else None,
        )

    return repository.create_opportunity(db, opp)


def get_opportunity(db: Session, opp_id: uuid.UUID, organization_id: uuid.UUID) -> models.Opportunity:
    opp = repository.get_opportunity_by_id(db, opp_id, organization_id)
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oportunidade não encontrada.")
    get_opportunity_document(db, opp, organization_id)
    return opp


def list_opportunities(db: Session, organization_id: uuid.UUID, stage: str | None = None, current_user: User | None = None) -> list[models.Opportunity]:
    user_ids = None
    if current_user:
        from controlb.modules.identity import service as identity_service
        user_ids = identity_service.get_accessible_user_ids(db, current_user, module_category="SALES")
    opportunities = repository.list_opportunities(
        db, organization_id, stage, user_ids=user_ids
    )
    for opportunity in opportunities:
        get_opportunity_document(db, opportunity, organization_id)
    return opportunities


def update_opportunity(
    db: Session,
    opp_id: uuid.UUID,
    organization_id: uuid.UUID,
    payload: schemas.OpportunityUpdate,
    current_user: User | None = None,
) -> models.Opportunity:
    opp = repository.get_opportunity_by_id(db, opp_id, organization_id)
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oportunidade não encontrada.")
    
    opportunity_document = get_opportunity_document(db, opp, organization_id)
    if payload.title is not None:
        opp.title = payload.title.strip()
    if payload.customer_name is not None:
        opp.customer_name = payload.customer_name.strip()
    if payload.customer_id is not None:
        opp.customer_id = payload.customer_id
    if payload.contact_id is not None:
        opp.contact_id = payload.contact_id
    if payload.estimated_amount is not None:
        opp.estimated_amount = payload.estimated_amount
    if payload.probability_percent is not None:
        opp.probability_percent = payload.probability_percent
    if payload.expected_closing_date is not None:
        opp.expected_closing_date = payload.expected_closing_date
    if payload.loss_reason is not None:
        opp.loss_reason = payload.loss_reason
    if payload.assigned_to_id is not None:
        opp.assigned_to_id = payload.assigned_to_id

    from controlb.modules.documents import schemas as document_schemas
    from controlb.modules.documents import service as documents_service

    document_changes: dict = {}
    if payload.title is not None:
        document_changes["title"] = opp.title
    if payload.loss_reason is not None:
        document_changes["description"] = opp.loss_reason
    if payload.assigned_to_id is not None:
        document_changes["responsible_id"] = opp.assigned_to_id
    if payload.priority is not None:
        document_changes["priority"] = payload.priority
    if document_changes:
        documents_service.update_document(
            db,
            opportunity_document.id,
            organization_id,
            document_schemas.DocumentUpdate(**document_changes),
            current_user=current_user,
        )

    if payload.stage is not None:
        transition_opportunity_stage(
            db,
            opp,
            organization_id,
            payload.stage,
            current_user=current_user,
            event_metadata=(
                {"loss_reason": payload.loss_reason} if payload.loss_reason else None
            ),
        )

    opp.title = opportunity_document.title
    opp.stage = opportunity_document.current_status
    opp.assigned_to_id = opportunity_document.responsible_id
    return repository.update_opportunity(db, opp)


def update_opportunity_stage(
    db: Session,
    opp_id: uuid.UUID,
    organization_id: uuid.UUID,
    stage: str,
    loss_reason: str | None = None,
    current_user: User | None = None,
) -> models.Opportunity:
    opp = repository.get_opportunity_by_id(db, opp_id, organization_id)
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oportunidade não encontrada.")
    opportunity_document = get_opportunity_document(db, opp, organization_id)
    if loss_reason:
        opp.loss_reason = loss_reason
        from controlb.modules.documents import schemas as document_schemas
        from controlb.modules.documents import service as documents_service

        documents_service.update_document(
            db,
            opportunity_document.id,
            organization_id,
            document_schemas.DocumentUpdate(description=loss_reason),
            current_user=current_user,
        )
    transition_opportunity_stage(
        db,
        opp,
        organization_id,
        stage,
        current_user=current_user,
        event_metadata={"loss_reason": loss_reason} if loss_reason else None,
    )
    return repository.update_opportunity(db, opp)


def delete_opportunity(
    db: Session,
    opp_id: uuid.UUID,
    organization_id: uuid.UUID,
    current_user: User | None = None,
):
    opp = repository.get_opportunity_by_id(db, opp_id, organization_id)
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oportunidade não encontrada.")
    opportunity_document = get_opportunity_document(db, opp, organization_id)
    from controlb.modules.documents import service as documents_service

    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=opportunity_document,
        event_type="DELETED",
        previous_status=opp.stage,
        new_status="DELETED",
        created_by_id=current_user.id if current_user else None,
    )
    repository.delete_opportunity(db, opp)
    return {"message": "Oportunidade excluída com sucesso."}


def delete_lead(
    db: Session,
    lead_id: uuid.UUID,
    organization_id: uuid.UUID,
    current_user: User | None = None,
):
    lead = repository.get_lead_by_id(db, lead_id, organization_id)
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead não encontrado.")
    lead_document = _get_lead_document(db, lead, organization_id)
    from controlb.modules.documents import service as documents_service

    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=lead_document,
        event_type="DELETED",
        previous_status=lead.status,
        new_status="DELETED",
        created_by_id=current_user.id if current_user else None,
    )
    repository.delete_lead(db, lead)
    return {"message": "Lead excluído com sucesso."}


def register_interaction(
    db: Session,
    organization_id: uuid.UUID,
    current_user: User,
    payload: schemas.CustomerInteractionCreate
) -> models.CustomerInteraction:
    if payload.lead_id and not repository.get_lead_by_id(db, payload.lead_id, organization_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead não encontrado.")
    if payload.opportunity_id and not repository.get_opportunity_by_id(
        db, payload.opportunity_id, organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Oportunidade não encontrada.",
        )

    interaction_type = payload.interaction_type.upper()
    is_note = interaction_type == "NOTE"
    if is_note and payload.status is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Notas não possuem status de execução.",
        )

    responsible_id = None
    if not is_note and payload.responsible_id:
        responsible = db.get(User, payload.responsible_id)
        if not responsible or responsible.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Responsável não encontrado na organização atual.",
            )
        responsible_id = responsible.id

    summary = payload.summary.strip()
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O resumo da interação não pode ser vazio.",
        )

    interaction = models.CustomerInteraction(
        organization_id=organization_id,
        lead_id=payload.lead_id,
        opportunity_id=payload.opportunity_id,
        interaction_type=interaction_type,
        summary=summary,
        details=payload.details.strip() if payload.details else None,
        interaction_date=payload.interaction_date,
        status=None if is_note else payload.status or "SCHEDULED",
        responsible_id=responsible_id,
        created_by_id=current_user.id,
    )
    return repository.create_interaction(db, interaction)


def list_interactions(
    db: Session,
    organization_id: uuid.UUID,
    lead_id: uuid.UUID | None = None,
    opportunity_id: uuid.UUID | None = None
) -> list[models.CustomerInteraction]:
    return repository.list_interactions(db, organization_id, lead_id, opportunity_id)


def update_interaction(
    db: Session,
    interaction_id: uuid.UUID,
    organization_id: uuid.UUID,
    current_user: User,
    payload: schemas.CustomerInteractionUpdate,
) -> models.CustomerInteraction:
    interaction = repository.get_interaction_by_id(db, interaction_id, organization_id)
    if not interaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nota ou atividade não encontrada.",
        )

    from controlb.modules.identity import service as identity_service

    permissions = set(identity_service.get_user_permissions(current_user))
    can_manage = bool(
        permissions.intersection({"crm:manage", "crm:manage_all", "*:*"})
    )
    if interaction.created_by_id != current_user.id and not can_manage:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente o autor ou um gestor do CRM pode editar esta interação.",
        )

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return interaction

    previous_values = {
        "interaction_type": interaction.interaction_type,
        "summary": interaction.summary,
        "details": interaction.details,
        "interaction_date": interaction.interaction_date.isoformat(),
        "status": interaction.status,
        "responsible_id": (
            str(interaction.responsible_id) if interaction.responsible_id else None
        ),
    }
    updated_fields: list[str] = []

    target_type = changes.get("interaction_type", interaction.interaction_type)
    is_note = target_type == "NOTE"

    if "summary" in changes:
        summary = changes["summary"].strip()
        if not summary:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O resumo da interação não pode ser vazio.",
            )
        if summary != interaction.summary:
            interaction.summary = summary
            updated_fields.append("summary")

    if "details" in changes:
        details = changes["details"].strip() if changes["details"] else None
        if details != interaction.details:
            interaction.details = details
            updated_fields.append("details")

    if "interaction_date" in changes and changes["interaction_date"] != interaction.interaction_date:
        interaction.interaction_date = changes["interaction_date"]
        updated_fields.append("interaction_date")

    if target_type != interaction.interaction_type:
        interaction.interaction_type = target_type
        updated_fields.append("interaction_type")

    if is_note:
        if changes.get("status") is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Notas não possuem status de execução.",
            )
        if interaction.status is not None:
            interaction.status = None
            updated_fields.append("status")
        if interaction.responsible_id is not None:
            interaction.responsible_id = None
            updated_fields.append("responsible_id")
    else:
        target_status = changes.get("status") or interaction.status or "SCHEDULED"
        if target_status != interaction.status:
            interaction.status = target_status
            updated_fields.append("status")

        if "responsible_id" in changes:
            responsible_id = changes["responsible_id"]
            if responsible_id:
                responsible = db.get(User, responsible_id)
                if not responsible or responsible.organization_id != organization_id:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Responsável não encontrado na organização atual.",
                    )
            if responsible_id != interaction.responsible_id:
                interaction.responsible_id = responsible_id
                updated_fields.append("responsible_id")

    if not updated_fields:
        return interaction

    interaction.updated_by_id = current_user.id
    interaction.updated_at = models.utcnow()
    repository.update_interaction(db, interaction)

    from controlb.modules.documents import service as documents_service

    if interaction.opportunity_id:
        opportunity = repository.get_opportunity_by_id(
            db, interaction.opportunity_id, organization_id
        )
        document = documents_service.ensure_document(
            db,
            organization_id=organization_id,
            category="crm.opportunity",
            document_type="OPPORTUNITY",
            native_id=opportunity.id,
            document_number=opportunity.title,
            title=opportunity.title,
            current_status=opportunity.stage,
            origin_module="CRM",
        )
    elif interaction.lead_id:
        lead = repository.get_lead_by_id(db, interaction.lead_id, organization_id)
        document = documents_service.ensure_document(
            db,
            organization_id=organization_id,
            category="crm.lead",
            document_type="LEAD",
            native_id=lead.id,
            document_number=lead.name,
            title=f"Lead: {lead.name}",
            current_status=lead.status,
            origin_module="CRM",
        )
    else:
        document = documents_service.ensure_document(
            db,
            organization_id=organization_id,
            category="crm.interaction",
            document_type="CRM_INTERACTION",
            native_id=interaction.id,
            document_number=f"Interação #{str(interaction.id)[:8]}",
            title=interaction.summary,
            current_status=interaction.status or "RECORDED",
            origin_module="CRM",
        )

    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=document,
        event_type="INTERACTION_UPDATED",
        created_by_id=current_user.id,
        event_metadata={
            "interaction_id": str(interaction.id),
            "updated_fields": updated_fields,
            "previous_values": previous_values,
        },
        idempotency_key=f"crm:interaction:{interaction.id}:update:{uuid.uuid4().hex}",
    )
    db.commit()
    db.refresh(interaction)
    return interaction


# ==============================================================================
# INTEGRAÇÃO CRM -> MÓDULO DE VENDAS
# ==============================================================================

def convert_lead_to_customer(
    db: Session,
    lead_id: uuid.UUID,
    organization_id: uuid.UUID,
    current_user: User
):
    lead = repository.get_lead_by_id(db, lead_id, organization_id)
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead não encontrado.")

    from controlb.modules.identity import service as identity_service, schemas as identity_schemas
    from controlb.modules.sales import service as sales_service, schemas as sales_schemas

    # 1. Cria Contato no Identity (Padrão Odoo Partner)
    contact = identity_service.create_contact(
        db,
        organization_id,
        identity_schemas.ContactCreate(
            person_type="PJ" if lead.company_name else "PF",
            name=lead.company_name or lead.name,
            trade_name=lead.name if lead.company_name else None,
            full_name=lead.name,
            email=lead.email,
            phone=lead.phone,
            position="Contato Comercial (Lead)",
            is_customer=True,
            origin_module="CRM",
            notes=f"Origem Lead CRM: {lead.source}"
        )
    )

    # 2. Cria Cliente no Módulo de Vendas
    doc = f"LEAD-{uuid.uuid4().hex[:8].upper()}"
    customer_name = lead.company_name or lead.name
    person_type = "PJ" if lead.company_name else "PF"

    customer = sales_service.create_customer(
        db,
        organization_id,
        sales_schemas.CustomerCreate(
            person_type=person_type,
            document=doc,
            name=customer_name,
            trade_name=lead.name if lead.company_name else None,
            email=lead.email,
            phone=lead.phone,
            contact_id=contact.id,
            origin_module="CRM",
            notes=f"Convertido a partir do Lead CRM #{str(lead.id)[:8]} ({lead.source})"
        )
    )

    lead_document = _get_lead_document(db, lead, organization_id)
    from controlb.modules.documents import schemas as document_schemas
    from controlb.modules.documents import service as documents_service

    documents_service.update_document(
        db,
        lead_document.id,
        organization_id,
        document_schemas.DocumentUpdate(current_status="CONVERTED"),
        current_user=current_user,
    )
    lead.status = lead_document.current_status
    db.commit()
    return customer


def list_opportunity_quotations(
    db: Session,
    organization_id: uuid.UUID,
    opp_id: uuid.UUID
):
    opp = repository.get_opportunity_by_id(db, opp_id, organization_id)
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oportunidade não encontrada.")
    from controlb.modules.sales import service as sales_service
    return sales_service.list_sales_quotes(db, organization_id, opportunity_id=opp_id)


def create_quote_from_opportunity(
    db: Session,
    opp_id: uuid.UUID,
    organization_id: uuid.UUID,
    current_user: User,
    items: list[dict] | None = None
):
    opp = repository.get_opportunity_by_id(db, opp_id, organization_id)
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oportunidade não encontrada.")

    from controlb.modules.sales import service as sales_service, schemas as sales_schemas
    from controlb.modules.inventory import repository as inv_repo
    from datetime import date, timedelta
    from decimal import Decimal

    quote_items = []
    if items:
        for it in items:
            quote_items.append(
                sales_schemas.SalesQuoteItemCreate(
                    product_id=uuid.UUID(str(it["product_id"])),
                    quantity=Decimal(str(it.get("quantity", 1))),
                    unit_price=Decimal(str(it.get("unit_price", 10.00))),
                    discount_amount=Decimal(str(it.get("discount_amount", 0)))
                )
            )
    else:
        # Se nenhum produto especificado, busca o primeiro produto ou cria com valor estimado
        prods = inv_repo.list_products(db, organization_id)
        if prods:
            p = prods[0]
            quote_items.append(
                sales_schemas.SalesQuoteItemCreate(
                    product_id=p.id,
                    quantity=Decimal("1"),
                    unit_price=opp.estimated_amount if opp.estimated_amount > 0 else (p.reference_price or Decimal("10.00")),
                    discount_amount=Decimal("0.00")
                )
            )

    quote_payload = sales_schemas.SalesQuoteCreate(
        customer_id=opp.customer_id,
        opportunity_id=opp.id,
        customer_name=opp.customer_name,
        valid_until=opp.expected_closing_date or (date.today() + timedelta(days=15)),
        payment_terms="30 DDL",
        notes=f"Cotação originada da Oportunidade CRM '{opp.title}' (Valor Estimado: R$ {opp.estimated_amount})",
        items=quote_items
    )

    quote = sales_service.create_sales_quote(db, organization_id, current_user, quote_payload)
    return quote
