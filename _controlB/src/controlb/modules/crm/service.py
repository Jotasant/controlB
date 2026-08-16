"""
modules/crm/service.py - Regras de Negócio e Serviços do CRM
"""

import uuid
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from controlb.modules.identity.models import User
from controlb.modules.crm import models, repository, schemas


def create_lead(db: Session, organization_id: uuid.UUID, payload: schemas.LeadCreate) -> models.Lead:
    lead = models.Lead(
        organization_id=organization_id,
        name=payload.name.strip(),
        company_name=payload.company_name.strip() if payload.company_name else None,
        email=payload.email.strip() if payload.email else None,
        phone=payload.phone.strip() if payload.phone else None,
        source=payload.source,
        status=payload.status,
        notes=payload.notes,
        assigned_to_id=payload.assigned_to_id
    )
    return repository.create_lead(db, lead)


def list_leads(db: Session, organization_id: uuid.UUID, status: str | None = None) -> list[models.Lead]:
    return repository.list_leads(db, organization_id, status)


def update_lead(db: Session, lead_id: uuid.UUID, organization_id: uuid.UUID, payload: schemas.LeadUpdate) -> models.Lead:
    lead = repository.get_lead_by_id(db, lead_id, organization_id)
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead não encontrado.")
    
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

    return repository.update_lead(db, lead)


def create_opportunity(db: Session, organization_id: uuid.UUID, payload: schemas.OpportunityCreate) -> models.Opportunity:
    opp = models.Opportunity(
        organization_id=organization_id,
        lead_id=payload.lead_id,
        title=payload.title.strip(),
        customer_name=payload.customer_name.strip(),
        estimated_amount=payload.estimated_amount,
        probability_percent=payload.probability_percent,
        expected_closing_date=payload.expected_closing_date,
        stage=payload.stage.upper(),
        loss_reason=payload.loss_reason,
        assigned_to_id=payload.assigned_to_id
    )
    return repository.create_opportunity(db, opp)


def list_opportunities(db: Session, organization_id: uuid.UUID, stage: str | None = None) -> list[models.Opportunity]:
    return repository.list_opportunities(db, organization_id, stage)


def update_opportunity_stage(db: Session, opp_id: uuid.UUID, organization_id: uuid.UUID, stage: str, loss_reason: str | None = None) -> models.Opportunity:
    opp = repository.get_opportunity_by_id(db, opp_id, organization_id)
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oportunidade não encontrada.")
    opp.stage = stage.upper()
    if loss_reason:
        opp.loss_reason = loss_reason
    return repository.update_opportunity(db, opp)


def register_interaction(
    db: Session,
    organization_id: uuid.UUID,
    current_user: User,
    payload: schemas.CustomerInteractionCreate
) -> models.CustomerInteraction:
    interaction = models.CustomerInteraction(
        organization_id=organization_id,
        lead_id=payload.lead_id,
        opportunity_id=payload.opportunity_id,
        interaction_type=payload.interaction_type.upper(),
        summary=payload.summary.strip(),
        details=payload.details,
        interaction_date=payload.interaction_date,
        created_by_id=current_user.id
    )
    return repository.create_interaction(db, interaction)


def list_interactions(
    db: Session,
    organization_id: uuid.UUID,
    lead_id: uuid.UUID | None = None,
    opportunity_id: uuid.UUID | None = None
) -> list[models.CustomerInteraction]:
    return repository.list_interactions(db, organization_id, lead_id, opportunity_id)
