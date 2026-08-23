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


def create_lead(db: Session, organization_id: uuid.UUID, payload: schemas.LeadCreate) -> models.Lead:
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

    lead = models.Lead(
        organization_id=organization_id,
        customer_id=customer_id,
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
    if payload.customer_id is not None:
        lead.customer_id = payload.customer_id

    return repository.update_lead(db, lead)


def create_opportunity(db: Session, organization_id: uuid.UUID, payload: schemas.OpportunityCreate) -> models.Opportunity:
    from controlb.modules.sales import service as sales_service, schemas as sales_schemas, repository as sales_repo

    customer_id = payload.customer_id
    customer_name = payload.customer_name.strip()
    contact_id = payload.contact_id

    if customer_id:
        cust = sales_repo.get_customer_by_id(db, customer_id, organization_id)
        if not cust:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente especificado não encontrado no módulo de Vendas.")
        customer_name = cust.trade_name or cust.name
        if not contact_id and cust.contact_id:
            contact_id = cust.contact_id
    else:
        # Garante criação de cliente em Vendas para eliminar campos desconexos
        doc = f"OPP-{uuid.uuid4().hex[:8].upper()}"
        cust = sales_service.create_customer(
            db,
            organization_id,
            sales_schemas.CustomerCreate(
                person_type="PJ",
                document=doc,
                name=customer_name,
                notes="Criado automaticamente na criação de Oportunidade Comercial"
            )
        )
        customer_id = cust.id

    opp = models.Opportunity(
        organization_id=organization_id,
        lead_id=payload.lead_id,
        customer_id=customer_id,
        contact_id=contact_id,
        title=payload.title.strip(),
        customer_name=customer_name,
        estimated_amount=payload.estimated_amount,
        probability_percent=payload.probability_percent,
        expected_closing_date=payload.expected_closing_date,
        stage=payload.stage.upper(),
        loss_reason=payload.loss_reason,
        assigned_to_id=payload.assigned_to_id
    )
    return repository.create_opportunity(db, opp)


def get_opportunity(db: Session, opp_id: uuid.UUID, organization_id: uuid.UUID) -> models.Opportunity:
    opp = repository.get_opportunity_by_id(db, opp_id, organization_id)
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oportunidade não encontrada.")
    return opp


def list_opportunities(db: Session, organization_id: uuid.UUID, stage: str | None = None) -> list[models.Opportunity]:
    return repository.list_opportunities(db, organization_id, stage)


def update_opportunity(db: Session, opp_id: uuid.UUID, organization_id: uuid.UUID, payload: schemas.OpportunityUpdate) -> models.Opportunity:
    opp = repository.get_opportunity_by_id(db, opp_id, organization_id)
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oportunidade não encontrada.")
    
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
    if payload.stage is not None:
        opp.stage = payload.stage.upper()
    if payload.loss_reason is not None:
        opp.loss_reason = payload.loss_reason
    if payload.assigned_to_id is not None:
        opp.assigned_to_id = payload.assigned_to_id

    return repository.update_opportunity(db, opp)


def update_opportunity_stage(db: Session, opp_id: uuid.UUID, organization_id: uuid.UUID, stage: str, loss_reason: str | None = None) -> models.Opportunity:
    opp = repository.get_opportunity_by_id(db, opp_id, organization_id)
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oportunidade não encontrada.")
    opp.stage = stage.upper()
    if loss_reason:
        opp.loss_reason = loss_reason
    return repository.update_opportunity(db, opp)


def delete_opportunity(db: Session, opp_id: uuid.UUID, organization_id: uuid.UUID):
    opp = repository.get_opportunity_by_id(db, opp_id, organization_id)
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oportunidade não encontrada.")
    repository.delete_opportunity(db, opp)
    return {"message": "Oportunidade excluída com sucesso."}


def delete_lead(db: Session, lead_id: uuid.UUID, organization_id: uuid.UUID):
    lead = repository.get_lead_by_id(db, lead_id, organization_id)
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead não encontrado.")
    repository.delete_lead(db, lead)
    return {"message": "Lead excluído com sucesso."}


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

    lead.status = "CONVERTED"
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
    opp.stage = "PROPOSAL"
    db.flush()
    return quote
