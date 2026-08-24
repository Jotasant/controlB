"""
modules/sales/schemas.py - Schemas Pydantic do Módulo de Vendas & PDV
"""

import uuid
from datetime import datetime, date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


# ==============================================================================
# 1. CADASTRO CENTRALIZADO DE CLIENTES (CUSTOMER)
# ==============================================================================

class CustomerBase(BaseModel):
    person_type: str = "PJ"  # "PJ" ou "PF"
    document: str = Field(..., min_length=11, max_length=30)  # CNPJ ou CPF
    name: str = Field(..., max_length=255)
    trade_name: str | None = None
    state_registration: str | None = None
    email: str | None = None
    phone: str | None = None
    address_street: str | None = None
    address_number: str | None = None
    address_neighborhood: str | None = None
    address_city: str | None = None
    address_state: str | None = None
    address_zip_code: str | None = None
    credit_limit: Decimal = Field(default=Decimal("0.00"), ge=0)
    contact_id: uuid.UUID | None = None
    origin_module: str = "SALES"
    is_active: bool = True
    notes: str | None = None


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    person_type: str | None = None
    document: str | None = None
    name: str | None = None
    trade_name: str | None = None
    state_registration: str | None = None
    email: str | None = None
    phone: str | None = None
    address_street: str | None = None
    address_number: str | None = None
    address_neighborhood: str | None = None
    address_city: str | None = None
    address_state: str | None = None
    address_zip_code: str | None = None
    credit_limit: Decimal | None = None
    contact_id: uuid.UUID | None = None
    origin_module: str | None = None
    is_active: bool | None = None
    notes: str | None = None


class CustomerResponse(CustomerBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 2. ORÇAMENTOS E PROPOSTAS (SALES QUOTES)
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
    customer_id: uuid.UUID | None = None
    opportunity_id: uuid.UUID | None = None
    customer_name: str = Field(..., max_length=255)
    customer_document: str | None = None
    customer_email: str | None = None
    customer_phone: str | None = None
    payment_terms: str | None = "À Vista"
    valid_until: date | None = None
    notes: str | None = None


class SalesQuoteCreate(SalesQuoteBase):
    items: list[SalesQuoteItemCreate]


class SalesQuoteUpdate(BaseModel):
    customer_id: uuid.UUID | None = None
    opportunity_id: uuid.UUID | None = None
    customer_name: str | None = None
    customer_document: str | None = None
    customer_email: str | None = None
    customer_phone: str | None = None
    payment_terms: str | None = None
    valid_until: date | None = None
    status: str | None = None
    notes: str | None = None
    items: list[SalesQuoteItemCreate] | None = None


class SalesQuoteCancelRequest(BaseModel):
    reason: str = Field(..., min_length=2, max_length=1000, description="Motivo do cancelamento / desistência")


class SalesQuoteResponse(SalesQuoteBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    quote_number: str
    total_amount: Decimal
    discount_amount: Decimal
    net_amount: Decimal
    status: str
    cancellation_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    items: list[SalesQuoteItemResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 3. PEDIDOS DE VENDA (SALES ORDERS)
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
    customer_id: uuid.UUID | None = None
    sales_quote_id: uuid.UUID | None = None
    opportunity_id: uuid.UUID | None = None
    customer_name: str = Field(..., max_length=255)
    customer_document: str | None = None
    payment_terms: str | None = "À Vista"
    delivery_status: str = "PENDING"
    notes: str | None = None


class SalesOrderCreate(SalesOrderBase):
    items: list[SalesOrderItemCreate]


class SalesOrderUpdate(BaseModel):
    customer_id: uuid.UUID | None = None
    customer_name: str | None = None
    customer_document: str | None = None
    payment_terms: str | None = None
    delivery_status: str | None = None
    status: str | None = None
    notes: str | None = None

    model_config = ConfigDict(extra="forbid")


class SalesOrderResponse(SalesOrderBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    order_number: str
    total_amount: Decimal
    discount_amount: Decimal
    net_amount: Decimal
    billing_status: str
    status: str
    cancellation_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    items: list[SalesOrderItemResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 4. FRENTE DE CAIXA (PDV BALCÃO) & SANGRIA / SUPRIMENTO
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
    customer_id: uuid.UUID | None = None
    customer_name: str = "Consumidor Final"
    customer_document: str | None = None
    discount_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    payment_method: str = "DINHEIRO"  # DINHEIRO, PIX, DEBITO, CREDITO, FATURADO
    items: list[POSSaleItemCreate]


class POSSaleResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    pos_session_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
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


class POSCashMovementCreate(BaseModel):
    pos_session_id: uuid.UUID
    movement_type: str = "SANGRIA"  # "SANGRIA" ou "SUPRIMENTO"
    amount: Decimal = Field(..., gt=0)
    reason: str = Field(..., max_length=255)


class POSCashMovementResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    pos_session_id: uuid.UUID
    movement_type: str
    amount: Decimal
    reason: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class POSSessionCreate(BaseModel):
    pos_terminal: str = "Caixa 01"
    opening_cash: Decimal = Field(default=Decimal("0.00"), ge=0)


class POSSessionClose(BaseModel):
    closing_cash: Decimal = Field(default=Decimal("0.00"), ge=0)


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
    cash_movements: list[POSCashMovementResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 5. GESTÃO COMERCIAL (METAS, COMISSÕES E TABELAS DE PREÇOS)
# ==============================================================================

class SalesGoalBase(BaseModel):
    user_id: uuid.UUID
    seller_name: str | None = None
    month: int = Field(..., ge=1, le=12)
    year: int = Field(..., ge=2020)
    target_amount: Decimal = Field(..., gt=0)
    commission_percent: Decimal = Field(default=Decimal("2.00"), ge=0)


class SalesGoalCreate(SalesGoalBase):
    pass


class SalesGoalUpdate(BaseModel):
    target_amount: Decimal | None = None
    commission_percent: Decimal | None = None


class SalesGoalResponse(SalesGoalBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PriceTableItemBase(BaseModel):
    product_id: uuid.UUID
    price: Decimal = Field(..., gt=0)
    discount_percent: Decimal = Field(default=Decimal("0.00"), ge=0)


class PriceTableItemCreate(PriceTableItemBase):
    pass


class PriceTableItemResponse(PriceTableItemBase):
    id: uuid.UUID
    price_table_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)


class PriceTableBase(BaseModel):
    name: str = Field(..., max_length=100)
    description: str | None = None
    is_default: bool = False
    is_active: bool = True


class PriceTableCreate(PriceTableBase):
    items: list[PriceTableItemCreate] = []


class PriceTableUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_default: bool | None = None
    is_active: bool | None = None
    items: list[PriceTableItemCreate] | None = None


class PriceTableResponse(PriceTableBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    items: list[PriceTableItemResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 6. PÓS-VENDA (DEVOLUÇÕES, TROCAS E CANCELAMENTOS)
# ==============================================================================

class SalesReturnItemBase(BaseModel):
    product_id: uuid.UUID
    quantity: Decimal = Field(..., gt=0)
    unit_price: Decimal = Field(..., gt=0)
    condition: str = "GOOD"  # "GOOD" (retorna ao estoque) ou "DAMAGED" (avaria)


class SalesReturnItemCreate(SalesReturnItemBase):
    pass


class SalesReturnItemResponse(SalesReturnItemBase):
    id: uuid.UUID
    total_price: Decimal

    model_config = ConfigDict(from_attributes=True)


class SalesReturnCreate(BaseModel):
    sales_order_id: uuid.UUID | None = None
    pos_sale_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    customer_name: str
    return_type: str = "DEVOLUCAO"  # "DEVOLUCAO", "TROCA", "CANCELAMENTO"
    reason: str
    restock_items: bool = True
    items: list[SalesReturnItemCreate]


class SalesReturnResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    sales_order_id: uuid.UUID | None = None
    pos_sale_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    customer_name: str
    return_type: str
    status: str
    total_amount: Decimal
    reason: str
    restock_items: bool
    created_at: datetime
    items: list[SalesReturnItemResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 7. INDICADORES E BI ANALÍTICO
# ==============================================================================

class TopProductMetric(BaseModel):
    product_id: uuid.UUID
    product_name: str
    total_quantity_sold: Decimal
    total_revenue: Decimal


class SellerPerformanceMetric(BaseModel):
    seller_name: str
    total_sales_amount: Decimal
    sales_count: int
    target_amount: Decimal
    achievement_percent: Decimal


class SalesAnalyticsResponse(BaseModel):
    total_revenue: Decimal
    total_orders_count: int
    total_pos_sales_count: int
    average_ticket: Decimal
    quote_conversion_rate: Decimal  # %
    top_selling_products: list[TopProductMetric] = []
    seller_performance: list[SellerPerformanceMetric] = []


# ==============================================================================
# 8. VENDEDORES E FORÇA DE VENDAS
# ==============================================================================

class SellerResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    is_seller: bool = True
    sales_team_id: uuid.UUID | None = None
    sales_team_name: str | None = None

    model_config = ConfigDict(from_attributes=True)

