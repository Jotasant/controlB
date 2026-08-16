"""
modules/crm/repository.py - Camada de Acesso a Dados do Módulo CRM
"""

import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from controlb.modules.crm.models import Lead, Opportunity, CustomerInteraction


# ==============================================================================
# LEADS
# ==============================================================================

def get_lead_by_id(db: Session, lead_id: uuid.UUID, organization_id: uuid.UUID) -> Lead | None:
    stmt = select(Lead).where(Lead.id == lead_id, Lead.organization_id == organization_id)
    return db.scalars(stmt).first()


def list_leads(db: Session, organization_id: uuid.UUID, status: str | None = None) -> list[Lead]:
    stmt = select(Lead).where(Lead.organization_id == organization_id)
    if status:
        stmt = stmt.where(Lead.status == status)
    stmt = stmt.order_by(Lead.created_at.desc())
    return list(db.scalars(stmt).all())


def create_lead(db: Session, lead: Lead) -> Lead:
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def update_lead(db: Session, lead: Lead) -> Lead:
    db.commit()
    db.refresh(lead)
    return lead


def delete_lead(db: Session, lead: Lead) -> None:
    db.delete(lead)
    db.commit()


# ==============================================================================
# OPORTUNIDADES & FUNIL (PIPELINE)
# ==============================================================================

def get_opportunity_by_id(db: Session, opp_id: uuid.UUID, organization_id: uuid.UUID) -> Opportunity | None:
    stmt = select(Opportunity).where(Opportunity.id == opp_id, Opportunity.organization_id == organization_id)
    return db.scalars(stmt).first()


def list_opportunities(db: Session, organization_id: uuid.UUID, stage: str | None = None) -> list[Opportunity]:
    stmt = select(Opportunity).where(Opportunity.organization_id == organization_id)
    if stage:
        stmt = stmt.where(Opportunity.stage == stage)
    stmt = stmt.order_by(Opportunity.created_at.desc())
    return list(db.scalars(stmt).all())


def create_opportunity(db: Session, opp: Opportunity) -> Opportunity:
    db.add(opp)
    db.commit()
    db.refresh(opp)
    return opp


def update_opportunity(db: Session, opp: Opportunity) -> Opportunity:
    db.commit()
    db.refresh(opp)
    return opp


def delete_opportunity(db: Session, opp: Opportunity) -> None:
    db.delete(opp)
    db.commit()


# ==============================================================================
# INTERAÇÕES
# ==============================================================================

def create_interaction(db: Session, interaction: CustomerInteraction) -> CustomerInteraction:
    db.add(interaction)
    db.commit()
    db.refresh(interaction)
    return interaction


def list_interactions(
    db: Session,
    organization_id: uuid.UUID,
    lead_id: uuid.UUID | None = None,
    opportunity_id: uuid.UUID | None = None
) -> list[CustomerInteraction]:
    stmt = select(CustomerInteraction).where(CustomerInteraction.organization_id == organization_id)
    if lead_id:
        stmt = stmt.where(CustomerInteraction.lead_id == lead_id)
    if opportunity_id:
        stmt = stmt.where(CustomerInteraction.opportunity_id == opportunity_id)
    stmt = stmt.order_by(CustomerInteraction.interaction_date.desc())
    return list(db.scalars(stmt).all())
