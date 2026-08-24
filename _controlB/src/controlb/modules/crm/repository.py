"""
modules/crm/repository.py - Camada de Acesso a Dados do Módulo CRM
"""

import uuid
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from controlb.modules.crm.models import Lead, Opportunity, CustomerInteraction, CRMStage


# ==============================================================================
# ETAPAS DO FUNIL (CRM STAGES)
# ==============================================================================

def list_stages(db: Session, organization_id: uuid.UUID) -> list[CRMStage]:
    stmt = select(CRMStage).where(CRMStage.organization_id == organization_id).order_by(CRMStage.order.asc(), CRMStage.created_at.asc())
    return list(db.scalars(stmt).all())


def get_stage_by_id(db: Session, stage_id: uuid.UUID, organization_id: uuid.UUID) -> CRMStage | None:
    stmt = select(CRMStage).where(CRMStage.id == stage_id, CRMStage.organization_id == organization_id)
    return db.scalars(stmt).first()


def get_stage_by_code(db: Session, code: str, organization_id: uuid.UUID) -> CRMStage | None:
    stmt = select(CRMStage).where(CRMStage.code == code.upper(), CRMStage.organization_id == organization_id)
    return db.scalars(stmt).first()


def create_stage(db: Session, stage: CRMStage) -> CRMStage:
    db.add(stage)
    db.commit()
    db.refresh(stage)
    return stage


def update_stage(db: Session, stage: CRMStage) -> CRMStage:
    db.commit()
    db.refresh(stage)
    return stage


def delete_stage(db: Session, stage: CRMStage) -> None:
    db.delete(stage)
    db.commit()


def count_opportunities_in_stage(db: Session, stage_code: str, organization_id: uuid.UUID) -> int:
    stmt = select(func.count(Opportunity.id)).where(
        Opportunity.organization_id == organization_id,
        Opportunity.stage == stage_code.upper()
    )
    return db.scalar(stmt) or 0


# ==============================================================================
# LEADS
# ==============================================================================

def get_lead_by_id(db: Session, lead_id: uuid.UUID, organization_id: uuid.UUID) -> Lead | None:
    stmt = select(Lead).where(Lead.id == lead_id, Lead.organization_id == organization_id)
    return db.scalars(stmt).first()


def list_leads(
    db: Session,
    organization_id: uuid.UUID,
    status: str | None = None,
    user_ids: set[uuid.UUID] | None = None
) -> list[Lead]:
    stmt = select(Lead).where(Lead.organization_id == organization_id)
    if status:
        stmt = stmt.where(Lead.status == status)
    if user_ids is not None:
        stmt = stmt.where((Lead.assigned_to_id.in_(user_ids)) | (Lead.assigned_to_id.is_(None)))
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


def list_opportunities(
    db: Session,
    organization_id: uuid.UUID,
    stage: str | None = None,
    user_ids: set[uuid.UUID] | None = None
) -> list[Opportunity]:
    stmt = select(Opportunity).where(Opportunity.organization_id == organization_id)
    if stage:
        stmt = stmt.where(Opportunity.stage == stage)
    if user_ids is not None:
        stmt = stmt.where((Opportunity.assigned_to_id.in_(user_ids)) | (Opportunity.assigned_to_id.is_(None)))
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

def get_interaction_by_id(db: Session, interaction_id: uuid.UUID, organization_id: uuid.UUID) -> CustomerInteraction | None:
    stmt = select(CustomerInteraction).where(CustomerInteraction.id == interaction_id, CustomerInteraction.organization_id == organization_id)
    return db.scalars(stmt).first()


def update_interaction(db: Session, interaction: CustomerInteraction) -> CustomerInteraction:
    db.add(interaction)
    db.flush()
    return interaction
    
