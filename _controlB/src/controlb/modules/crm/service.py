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
        customer_id=payload.customer_id,
        contact_id=payload.contact_id,
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

    # 1. Cria Contato no Identity
    contact = identity_service.create_contact(
        db,
        organization_id,
        identity_schemas.ContactCreate(
            full_name=lead.name,
            email=lead.email,
            phone=lead.phone,
            position="Contato Comercial (Lead)",
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
            notes=f"Convertido a partir do Lead CRM #{str(lead.id)[:8]} ({lead.source})"
        )
    )

    lead.status = "CONVERTED"
    db.commit()
    return customer


def list_opportunity_quotations(
    db: Session,
    opp_id: uuid.UUID,
    organization_id: uuid.UUID
):
    opp = repository.get_opportunity_by_id(db, opp_id, organization_id)
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oportunidade não encontrada.")
    from controlb.modules.sales import repository as sales_repo
    return sales_repo.list_quotes(db, organization_id)


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
    db.commit()
    return quote

