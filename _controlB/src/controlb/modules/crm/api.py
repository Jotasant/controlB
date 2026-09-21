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
# ETAPAS DO FUNIL (CRM STAGES)
# ==============================================================================

@router.get("/stages", response_model=list[schemas.CRMStageResponse], summary="Listar Etapas do Funil de CRM")
def list_stages(
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.list_stages(db, current_user.organization_id)


@router.post("/stages", response_model=schemas.CRMStageResponse, status_code=status.HTTP_201_CREATED, summary="Criar Etapa do Funil")
def create_stage(
    payload: schemas.CRMStageCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    # Permite criação para quem possui permissão crm:stages:manage, crm:manage ou admin
    return service.create_stage(db, current_user.organization_id, payload)


@router.put("/stages/{stage_id}", response_model=schemas.CRMStageResponse, summary="Atualizar Etapa do Funil")
def update_stage(
    stage_id: uuid.UUID,
    payload: schemas.CRMStageUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.update_stage(db, stage_id, current_user.organization_id, payload)


@router.delete("/stages/{stage_id}", status_code=status.HTTP_200_OK, summary="Excluir Etapa do Funil")
def delete_stage(
    stage_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.delete_stage(db, stage_id, current_user.organization_id)


# ==============================================================================
# LEADS
# ==============================================================================

@router.get("/leads", response_model=list[schemas.LeadResponse], summary="Listar Leads")
def list_leads(
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.list_leads(db, current_user.organization_id, status, current_user=current_user)


@router.post("/leads", response_model=schemas.LeadResponse, status_code=status.HTTP_201_CREATED, summary="Cadastrar Lead")
def create_lead(
    payload: schemas.LeadCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.create_lead(
        db, current_user.organization_id, payload, current_user=current_user
    )


@router.put("/leads/{lead_id}", response_model=schemas.LeadResponse, summary="Atualizar Lead")
def update_lead(
    lead_id: uuid.UUID,
    payload: schemas.LeadUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.update_lead(
        db,
        lead_id,
        current_user.organization_id,
        payload,
        current_user=current_user,
    )


@router.delete("/leads/{lead_id}", status_code=status.HTTP_200_OK, summary="Excluir Lead")
def delete_lead(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.delete_lead(
        db, lead_id, current_user.organization_id, current_user=current_user
    )


# ==============================================================================
# OPORTUNIDADES (PIPELINE)
# ==============================================================================

@router.get("/opportunities", response_model=list[schemas.OpportunityResponse], summary="Listar Oportunidades do Pipeline")
def list_opportunities(
    stage: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.list_opportunities(db, current_user.organization_id, stage, current_user=current_user)


@router.get("/opportunities/{opp_id}", response_model=schemas.OpportunityResponse, summary="Obter Oportunidade por ID")
def get_opportunity(
    opp_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.get_opportunity(db, opp_id, current_user.organization_id)


@router.post("/opportunities", response_model=schemas.OpportunityResponse, status_code=status.HTTP_201_CREATED, summary="Criar Oportunidade")
def create_opportunity(
    payload: schemas.OpportunityCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.create_opportunity(
        db, current_user.organization_id, payload, current_user=current_user
    )


@router.put("/opportunities/{opp_id}", response_model=schemas.OpportunityResponse, summary="Atualizar Oportunidade")
def update_opportunity(
    opp_id: uuid.UUID,
    payload: schemas.OpportunityUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.update_opportunity(
        db,
        opp_id,
        current_user.organization_id,
        payload,
        current_user=current_user,
    )


@router.patch("/opportunities/{opp_id}/stage", response_model=schemas.OpportunityResponse, summary="Mover Oportunidade no Funil")
def update_opportunity_stage(
    opp_id: uuid.UUID,
    stage: str = Query(..., description="PROSPECTING, QUALIFICATION, PROPOSAL, NEGOTIATION, WON, LOST"),
    loss_reason: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.update_opportunity_stage(
        db,
        opp_id,
        current_user.organization_id,
        stage,
        loss_reason,
        current_user=current_user,
    )


@router.delete("/opportunities/{opp_id}", status_code=status.HTTP_200_OK, summary="Excluir Oportunidade")
def delete_opportunity(
    opp_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.delete_opportunity(
        db, opp_id, current_user.organization_id, current_user=current_user
    )


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


@router.patch(
    "/interactions/{interaction_id}",
    response_model=schemas.CustomerInteractionResponse,
    summary="Atualizar Nota ou Atividade",
)
def update_interaction(
    interaction_id: uuid.UUID,
    payload: schemas.CustomerInteractionUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user),
):
    return service.update_interaction(
        db,
        interaction_id,
        current_user.organization_id,
        current_user,
        payload,
    )


# ==============================================================================
# INTEGRAÇÃO COM MÓDULO DE VENDAS
# ==============================================================================

@router.post("/leads/{lead_id}/convert-customer", summary="Converter Lead em Cliente no Módulo de Vendas")
def convert_lead_to_customer(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.convert_lead_to_customer(db, lead_id, current_user.organization_id, current_user)


@router.post("/leads/{lead_id}/convert-opportunity", summary="Converter Lead em Oportunidade no Funil de Vendas")
def convert_lead_to_opportunity(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.convert_lead_to_opportunity(db, lead_id, current_user.organization_id, current_user)


@router.post("/contacts/{contact_id}/convert-lead", summary="Converter Contato (ex: WhatsApp) em Lead no CRM")
def convert_contact_to_lead(
    contact_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.convert_contact_to_lead(db, contact_id, current_user.organization_id, current_user)


@router.post("/contacts/{contact_id}/convert-opportunity", response_model=schemas.OpportunityResponse, status_code=status.HTTP_201_CREATED, summary="Converter Contato (ex: WhatsApp) em Oportunidade no CRM")
def convert_contact_to_opportunity(
    contact_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.convert_contact_to_opportunity(db, contact_id, current_user.organization_id, current_user=current_user)


@router.get("/opportunities/{opp_id}/quotations", summary="Listar Cotações Vinculadas à Oportunidade")
def list_opportunity_quotations(
    opp_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.list_opportunity_quotations(db, current_user.organization_id, opp_id)


@router.post("/opportunities/{opp_id}/create-quote", summary="Gerar Cotação/Orçamento no Módulo de Vendas a partir de Oportunidade")
def create_quote_from_opportunity(
    opp_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.create_quote_from_opportunity(db, opp_id, current_user.organization_id, current_user)
