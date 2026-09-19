"""
modules/billing/schemas.py - Schemas Pydantic do Módulo de Faturamento
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class InvoiceItemCreate(BaseModel):
    sales_order_item_id: uuid.UUID
    quantity: Decimal = Field(..., gt=0)


class InvoiceItemResponse(BaseModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    sales_order_item_id: uuid.UUID
    product_id: uuid.UUID
    description: str
    product_sku: str | None = None
    quantity: Decimal
    unit_price: Decimal
    discount_amount: Decimal
    total_amount: Decimal

    model_config = ConfigDict(from_attributes=True)


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
    items: list[InvoiceItemCreate] = Field(default_factory=list)
    generate_receivables_in_finance: bool = Field(default=True, description="Alimenta automaticamente o Contas a Receber no Financeiro")
    generate_outbound_fiscal_document: bool = Field(
        default=True,
        description="Cria o registro fiscal de saída em rascunho vinculado à fatura",
    )
    fiscal_document_type: Literal["NFE", "NFSE", "NFCE", "OUTRO"] = "OUTRO"
    fiscal_document_number: str | None = Field(default=None, max_length=100)
    fiscal_series: str | None = Field(default=None, max_length=20)
    fiscal_access_key: str | None = Field(default=None, max_length=100)
    fiscal_file_attachment: str | None = Field(default=None, description="Anexo em Base64 da nota fiscal (PDF/XML)")
    boleto_file_attachment: str | None = Field(default=None, description="Anexo em Base64 do boleto bancário (PDF)")
    boleto_digitable_line: str | None = Field(default=None, description="Linha digitável do boleto bancário")


class InvoiceUpdate(BaseModel):
    """Campos comerciais editáveis sem reescrever valores já contabilizados."""

    customer_name: str | None = Field(default=None, min_length=1, max_length=255)
    customer_document: str | None = Field(default=None, max_length=30)
    issue_date: date | None = None
    due_date: date | None = None
    notes: str | None = None


class InvoiceCancel(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


class BillingRequestIssue(BaseModel):
    """Parâmetros operacionais definidos pelo Faturamento ao atender Vendas."""

    issue_date: date
    due_date: date
    installments_count: int = Field(default=1, ge=1, le=48)
    tax_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    notes: str | None = None
    generate_receivables_in_finance: bool = True
    generate_outbound_fiscal_document: bool = True
    fiscal_document_type: Literal["NFE", "NFSE", "NFCE", "OUTRO"] = "NFE"
    fiscal_document_number: str | None = Field(default=None, max_length=100)
    fiscal_series: str | None = Field(default=None, max_length=20)
    fiscal_access_key: str | None = Field(default=None, max_length=100)
    items: list[InvoiceItemCreate] = Field(default_factory=list)
    fiscal_file_attachment: str | None = Field(
        default=None, description="Anexo em Base64 da nota fiscal (PDF/XML)"
    )
    boleto_file_attachment: str | None = Field(
        default=None, description="Anexo em Base64 do boleto bancário (PDF)"
    )
    boleto_digitable_line: str | None = Field(
        default=None, description="Linha digitável do boleto bancário"
    )


class BillingRequestCancel(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


class InvoiceResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    document_id: uuid.UUID
    fiscal_document_id: uuid.UUID | None = None
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
    installments: list[InvoiceInstallmentResponse] = Field(default_factory=list)
    items: list[InvoiceItemResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
