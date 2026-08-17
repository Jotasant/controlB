"""
modules/crm/schemas.py - Schemas Pydantic do Módulo CRM
"""

import uuid
from datetime import datetime, date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class LeadBase(BaseModel):
    name: str = Field(..., max_length=255)
    company_name: str | None = None
    email: str | None = None
    phone: str | None = None
    source: str = "Indicação"
    status: str = "NEW"
    notes: str | None = None
    assigned_to_id: uuid.UUID | None = None


class LeadCreate(LeadBase):
    pass


class LeadUpdate(BaseModel):
    name: str | None = None
    company_name: str | None = None
    email: str | None = None
    phone: str | None = None
    source: str | None = None
    status: str | None = None
    notes: str | None = None
    assigned_to_id: uuid.UUID | None = None


class LeadResponse(LeadBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OpportunityQuoteSummaryResponse(BaseModel):
    id: uuid.UUID
    quote_number: str
    total_amount: Decimal
    net_amount: Decimal
    status: str
    valid_until: date
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OpportunityBase(BaseModel):
    title: str = Field(..., max_length=255)
    customer_name: str = Field(..., max_length=255)
    customer_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    estimated_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    probability_percent: int = Field(default=50, ge=0, le=100)
    expected_closing_date: date | None = None
    stage: str = "PROSPECTING"  # PROSPECTING, QUALIFICATION, PROPOSAL, NEGOTIATION, WON, LOST
    loss_reason: str | None = None
    lead_id: uuid.UUID | None = None
    assigned_to_id: uuid.UUID | None = None


class OpportunityCreate(OpportunityBase):
    pass


class OpportunityUpdate(BaseModel):
    title: str | None = None
    customer_name: str | None = None
    customer_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    estimated_amount: Decimal | None = None
    probability_percent: int | None = None
    expected_closing_date: date | None = None
    stage: str | None = None
    loss_reason: str | None = None
    assigned_to_id: uuid.UUID | None = None


class OpportunityResponse(OpportunityBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    lead: LeadResponse | None = None
    quotes: list[OpportunityQuoteSummaryResponse] = []

    model_config = ConfigDict(from_attributes=True)


class CustomerInteractionCreate(BaseModel):
    lead_id: uuid.UUID | None = None
    opportunity_id: uuid.UUID | None = None
    interaction_type: str = "CALL"  # CALL, MEETING, EMAIL, WHATSAPP, NOTE
    summary: str = Field(..., max_length=255)
    details: str | None = None
    interaction_date: datetime = Field(default_factory=datetime.utcnow)


class CustomerInteractionResponse(CustomerInteractionCreate):
    id: uuid.UUID
    organization_id: uuid.UUID
    created_by_id: uuid.UUID | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
