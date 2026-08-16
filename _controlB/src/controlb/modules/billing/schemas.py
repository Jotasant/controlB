"""
modules/billing/schemas.py - Schemas Pydantic do Módulo de Faturamento
"""

import uuid
from datetime import datetime, date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class InvoiceInstallmentBase(BaseModel):
    installment_number: int
    total_installments: int
    amount: Decimal
    due_date: date
    status: str = "PENDING"


class InvoiceInstallmentResponse(InvoiceInstallmentBase):
    id: uuid.UUID
    invoice_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)


class InvoiceBase(BaseModel):
    sales_order_id: uuid.UUID | None = None
    customer_name: str = Field(..., max_length=255)
    customer_document: str | None = None
    total_amount: Decimal = Field(..., gt=0)
    tax_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    issue_date: date
    due_date: date
    installments_count: int = Field(default=1, ge=1, le=48)
    notes: str | None = None


class InvoiceCreate(InvoiceBase):
    generate_receivables_in_finance: bool = Field(default=True, description="Alimenta automaticamente o Contas a Receber no Financeiro")


class InvoiceResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    invoice_number: str
    sales_order_id: uuid.UUID | None = None
    customer_name: str
    customer_document: str | None = None
    total_amount: Decimal
    tax_amount: Decimal
    net_amount: Decimal
    issue_date: date
    due_date: date
    status: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    installments: list[InvoiceInstallmentResponse] = []

    model_config = ConfigDict(from_attributes=True)
