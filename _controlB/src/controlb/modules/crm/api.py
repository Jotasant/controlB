"""
modules/crm/api.py - Roteador de Endpoints REST do Módulo CRM (CRM Domain)
"""

import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from controlb.db import get_db
from controlb.modules.identity import service as identity_service
from controlb.modules.crm import service, schemas

router = APIRouter(prefix="/crm", tags=["CRM / Gestão de Relacionamento"])


# ==============================================================================
# LEADS
# ==============================================================================

@router.get("/leads", response_model=list[schemas.LeadResponse], summary="Listar Leads")
def list_leads(
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.list_leads(db, current_user.organization_id, status)


@router.post("/leads", response_model=schemas.LeadResponse, status_code=status.HTTP_201_CREATED, summary="Cadastrar Lead")
def create_lead(
    payload: schemas.LeadCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.create_lead(db, current_user.organization_id, payload)


@router.put("/leads/{lead_id}", response_model=schemas.LeadResponse, summary="Atualizar Lead")
def update_lead(
    lead_id: uuid.UUID,
    payload: schemas.LeadUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.update_lead(db, lead_id, current_user.organization_id, payload)


# ==============================================================================
# OPORTUNIDADES (PIPELINE)
# ==============================================================================

@router.get("/opportunities", response_model=list[schemas.OpportunityResponse], summary="Listar Oportunidades do Pipeline")
def list_opportunities(
    stage: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.list_opportunities(db, current_user.organization_id, stage)


@router.post("/opportunities", response_model=schemas.OpportunityResponse, status_code=status.HTTP_201_CREATED, summary="Criar Oportunidade")
def create_opportunity(
    payload: schemas.OpportunityCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.create_opportunity(db, current_user.organization_id, payload)


@router.patch("/opportunities/{opp_id}/stage", response_model=schemas.OpportunityResponse, summary="Mover Oportunidade no Funil")
def update_opportunity_stage(
    opp_id: uuid.UUID,
    stage: str = Query(..., description="PROSPECTING, QUALIFICATION, PROPOSAL, NEGOTIATION, WON, LOST"),
    loss_reason: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.update_opportunity_stage(db, opp_id, current_user.organization_id, stage, loss_reason)


# ==============================================================================
# INTERAÇÕES
# ==============================================================================

@router.get("/interactions", response_model=list[schemas.CustomerInteractionResponse], summary="Listar Interações")
def list_interactions(
    lead_id: uuid.UUID | None = Query(None),
    opportunity_id: uuid.UUID | None = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.list_interactions(db, current_user.organization_id, lead_id, opportunity_id)


@router.post("/interactions", response_model=schemas.CustomerInteractionResponse, status_code=status.HTTP_201_CREATED, summary="Registrar Interação")
def create_interaction(
    payload: schemas.CustomerInteractionCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.register_interaction(db, current_user.organization_id, current_user, payload)
