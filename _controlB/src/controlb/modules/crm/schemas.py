"""
modules/crm/schemas.py - Schemas Pydantic do Módulo CRM
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CRMStageBase(BaseModel):
    name: str = Field(..., max_length=100)
    code: str = Field(..., max_length=50)
    color: str = Field(default="#10b981", max_length=20)
    order: int = Field(default=0)
    is_won: bool = False
    is_lost: bool = False
    is_system: bool = False


class CRMStageCreate(CRMStageBase):
    pass


class CRMStageUpdate(BaseModel):
    name: str | None = None
    color: str | None = None
    order: int | None = None
    is_won: bool | None = None
    is_lost: bool | None = None


class CRMStageResponse(CRMStageBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LeadBase(BaseModel):
    name: str = Field(..., max_length=255)
    company_name: str | None = None
    email: str | None = None
    phone: str | None = None
    source: str = "Indicação"
    status: str = "NEW"
    notes: str | None = None
    assigned_to_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None


class LeadCreate(LeadBase):
    document: str | None = None
    person_type: str | None = "PJ"


class LeadUpdate(BaseModel):
    name: str | None = None
    company_name: str | None = None
    email: str | None = None
    phone: str | None = None
    source: str | None = None
    status: str | None = None
    notes: str | None = None
    assigned_to_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None


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


InteractionType = Literal["CALL", "MEETING", "EMAIL", "WHATSAPP", "NOTE"]
ActivityStatus = Literal["SCHEDULED", "COMPLETED", "CANCELLED"]


class CustomerInteractionCreate(BaseModel):
    lead_id: uuid.UUID | None = None
    opportunity_id: uuid.UUID | None = None
    interaction_type: InteractionType = "CALL"
    summary: str = Field(..., min_length=1, max_length=255)
    details: str | None = None
    interaction_date: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: ActivityStatus | None = None
    responsible_id: uuid.UUID | None = None

    model_config = ConfigDict(extra="forbid")


class CustomerInteractionUpdate(BaseModel):
    interaction_type: InteractionType | None = None
    summary: str | None = Field(None, min_length=1, max_length=255)
    details: str | None = None
    interaction_date: datetime | None = None
    status: ActivityStatus | None = None
    responsible_id: uuid.UUID | None = None

    model_config = ConfigDict(extra="forbid")


class CustomerInteractionResponse(CustomerInteractionCreate):
    id: uuid.UUID
    organization_id: uuid.UUID
    created_by_id: uuid.UUID | None = None
    updated_by_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
