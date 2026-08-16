"""
modules/sales/schemas.py - Schemas Pydantic do Módulo de Vendas & PDV
"""

import uuid
from datetime import datetime, date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


# ==============================================================================
# ORÇAMENTOS (QUOTES)
# ==============================================================================

class SalesQuoteItemBase(BaseModel):
    product_id: uuid.UUID
    quantity: Decimal = Field(..., gt=0)
    unit_price: Decimal = Field(..., gt=0)
    discount_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    notes: str | None = None


class SalesQuoteItemCreate(SalesQuoteItemBase):
    pass


class SalesQuoteItemResponse(SalesQuoteItemBase):
    id: uuid.UUID
    total_price: Decimal

    model_config = ConfigDict(from_attributes=True)


class SalesQuoteBase(BaseModel):
    customer_name: str = Field(..., max_length=255)
    customer_document: str | None = None
    customer_email: str | None = None
    customer_phone: str | None = None
    valid_until: date
    notes: str | None = None


class SalesQuoteCreate(SalesQuoteBase):
    items: list[SalesQuoteItemCreate]


class SalesQuoteResponse(SalesQuoteBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    quote_number: str
    total_amount: Decimal
    discount_amount: Decimal
    net_amount: Decimal
    status: str
    created_at: datetime
    updated_at: datetime
    items: list[SalesQuoteItemResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# PEDIDOS DE VENDA (SALES ORDERS)
# ==============================================================================

class SalesOrderItemBase(BaseModel):
    product_id: uuid.UUID
    quantity: Decimal = Field(..., gt=0)
    unit_price: Decimal = Field(..., gt=0)
    discount_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    notes: str | None = None


class SalesOrderItemCreate(SalesOrderItemBase):
    pass


class SalesOrderItemResponse(SalesOrderItemBase):
    id: uuid.UUID
    total_price: Decimal

    model_config = ConfigDict(from_attributes=True)


class SalesOrderBase(BaseModel):
    customer_name: str = Field(..., max_length=255)
    customer_document: str | None = None
    payment_terms: str | None = "À Vista"
    delivery_status: str = "PENDING"
    notes: str | None = None


class SalesOrderCreate(SalesOrderBase):
    items: list[SalesOrderItemCreate]


class SalesOrderResponse(SalesOrderBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    order_number: str
    total_amount: Decimal
    discount_amount: Decimal
    net_amount: Decimal
    billing_status: str
    status: str
    created_at: datetime
    updated_at: datetime
    items: list[SalesOrderItemResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# FRENTE DE CAIXA (PDV BALCÃO)
# ==============================================================================

class POSSaleItemCreate(BaseModel):
    product_id: uuid.UUID
    quantity: Decimal = Field(..., gt=0)
    unit_price: Decimal = Field(..., gt=0)


class POSSaleItemResponse(POSSaleItemCreate):
    id: uuid.UUID
    total_price: Decimal

    model_config = ConfigDict(from_attributes=True)


class POSSaleCreate(BaseModel):
    pos_session_id: uuid.UUID | None = None
    customer_name: str = "Consumidor Final"
    customer_document: str | None = None
    discount_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    payment_method: str = "DINHEIRO"  # DINHEIRO, PIX, DEBITO, CREDITO
    items: list[POSSaleItemCreate]


class POSSaleResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    pos_session_id: uuid.UUID | None = None
    customer_name: str
    customer_document: str | None = None
    total_amount: Decimal
    discount_amount: Decimal
    net_amount: Decimal
    payment_method: str
    status: str
    created_at: datetime
    items: list[POSSaleItemResponse] = []

    model_config = ConfigDict(from_attributes=True)


class POSSessionCreate(BaseModel):
    pos_terminal: str = "Caixa 01"
    opening_cash: Decimal = Field(default=Decimal("0.00"), ge=0)


class POSSessionResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    pos_terminal: str
    opening_cash: Decimal
    closing_cash: Decimal | None = None
    status: str
    opened_at: datetime
    closed_at: datetime | None = None
    sales: list[POSSaleResponse] = []

    model_config = ConfigDict(from_attributes=True)
