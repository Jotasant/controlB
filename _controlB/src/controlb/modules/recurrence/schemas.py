"""
modules/recurrence/schemas.py - Schemas Pydantic para Recorrência

Define os modelos de serialização/deserialização para as APIs.
"""

from __future__ import annotations

import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


# ==============================================================================
# Histórico de Compras
# ==============================================================================

class PurchaseHistoryCreate(BaseModel):
    """Schema para criar novo registro de histórico de compra."""
    customer_id: uuid.UUID
    product_id: uuid.UUID
    purchase_date: date
    quantity: Decimal
    unit_price: Decimal
    total_amount: Decimal
    sales_channel: str = "MANUAL_ENTRY"
    salesman_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None


class PurchaseHistoryResponse(BaseModel):
    """Schema de resposta para histórico de compra."""
    id: uuid.UUID
    organization_id: uuid.UUID
    customer_id: uuid.UUID
    product_id: uuid.UUID
    purchase_date: date
    quantity: Decimal
    unit_price: Decimal
    total_amount: Decimal
    sales_channel: str
    salesman_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==============================================================================
# Recorrência de Cliente e Produto
# ==============================================================================

class CustomerProductRecurrenceResponse(BaseModel):
    """Schema de resposta para análise de recorrência."""
    id: uuid.UUID
    organization_id: uuid.UUID
    customer_id: uuid.UUID
    product_id: uuid.UUID
    
    # Histórico
    total_purchases: int
    last_purchase_date: Optional[date] = None
    first_purchase_date: Optional[date] = None
    
    # Análise
    average_days_between_purchases: Optional[Decimal] = None
    last_interval_days: Optional[int] = None
    purchase_frequency_type: str
    
    # Previsão
    predicted_next_purchase_date: Optional[date] = None
    confidence_score: Decimal
    
    # Quantidade
    average_quantity_per_purchase: Optional[Decimal] = None
    last_purchase_quantity: Optional[Decimal] = None
    
    # Status
    recurrence_status: str
    is_critical_for_retention: bool
    relevance_score: Decimal
    
    custom_recurrence_interval_days: Optional[int] = None
    notes: Optional[str] = None
    
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CustomerAnalysisResponse(BaseModel):
    """Schema para análise completa de um cliente."""
    customer_id: uuid.UUID
    customer_name: str
    total_purchases: int
    last_purchase_date: Optional[date] = None
    products: list[CustomerProductRecurrenceResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


# ==============================================================================
# Alertas de Recorrência
# ==============================================================================

class RecurrenceAlertUpdate(BaseModel):
    """Schema para atualizar status de alerta."""
    status: str
    contact_result: Optional[str] = None
    contact_date: Optional[datetime] = None
    notes: Optional[str] = None


class RecurrenceAlertResponse(BaseModel):
    """Schema de resposta para alerta de recorrência."""
    id: uuid.UUID
    organization_id: uuid.UUID
    customer_id: uuid.UUID
    product_id: uuid.UUID
    recurrence_id: uuid.UUID
    
    alert_type: str
    expected_purchase_date: date
    days_until_purchase: Optional[int] = None
    
    status: str
    contact_result: Optional[str] = None
    contact_date: Optional[datetime] = None
    contacted_by_id: Optional[uuid.UUID] = None
    
    opportunity_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RecurrenceAlertDetailedResponse(RecurrenceAlertResponse):
    """Schema detalhado com informações do cliente e produto."""
    customer_name: Optional[str] = None
    product_name: Optional[str] = None
    product_sku: Optional[str] = None
    salesman_name: Optional[str] = None
    last_purchase_date: Optional[date] = None
    last_purchase_quantity: Optional[Decimal] = None


# ==============================================================================
# Consolidação de Demanda
# ==============================================================================

class ProductDemandDetailResponse(BaseModel):
    """Schema para detalhe de demanda por cliente."""
    customer_id: uuid.UUID
    customer_name: Optional[str] = None
    predicted_quantity: Decimal
    predicted_purchase_date: Optional[date] = None
    relevance_score: Optional[Decimal] = None

    class Config:
        from_attributes = True


class ProductDemandForecastResponse(BaseModel):
    """Schema para previsão de demanda consolidada."""
    id: uuid.UUID
    organization_id: uuid.UUID
    product_id: uuid.UUID
    product_name: Optional[str] = None
    product_sku: Optional[str] = None
    
    forecast_start_date: date
    forecast_end_date: date
    forecast_window_days: Optional[int] = None
    
    total_customers_with_recurrence: int
    predicted_total_quantity: Decimal
    predicted_total_revenue: Decimal
    
    number_of_critical_customers: int
    risk_score: Decimal
    
    last_calculated_at: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    
    details_by_customer: list[ProductDemandDetailResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


# ==============================================================================
# Sugestões de Reposição
# ==============================================================================

class ReplenishmentSuggestionResponse(BaseModel):
    """Schema para sugestão de reposição inteligente."""
    id: uuid.UUID
    organization_id: uuid.UUID
    product_id: uuid.UUID
    product_name: Optional[str] = None
    product_sku: Optional[str] = None
    
    # Estoque
    current_stock_quantity: Decimal
    minimum_stock_level: Optional[Decimal] = None
    safety_stock_level: Optional[Decimal] = None
    
    # Demanda
    predicted_demand_quantity: Decimal
    demand_forecast_window_days: int
    pending_purchase_orders_quantity: Decimal
    
    # Sugestão
    suggested_order_quantity: Decimal
    suggested_reorder_point: Optional[Decimal] = None
    
    # Indicadores
    urgency_level: str
    stock_out_risk_days: Optional[int] = None
    
    # Estado
    status: str
    purchase_request_id: Optional[uuid.UUID] = None
    
    justification: Optional[dict] = None
    notes: Optional[str] = None
    
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ReplenishmentSuggestionApproveRequest(BaseModel):
    """Schema para aprovar sugestão de reposição."""
    suggested_order_quantity: Optional[Decimal] = None
    notes: Optional[str] = None
    supplier_id: Optional[uuid.UUID] = None
    create_purchase_request: bool = True


# ==============================================================================
# Dashboard
# ==============================================================================

class DashboardMetricsResponse(BaseModel):
    """Schema com métricas resumidas do dashboard."""
    total_customers_with_recurrence: int
    total_alerts_open: int
    total_alerts_overdue: int
    critical_alerts_count: int
    high_risk_products_count: int
    
    replenishment_suggestions_open: int
    replenishment_suggestions_critical: int
    
    total_predicted_revenue_30_days: Decimal
    total_predicted_quantity_30_days: Decimal


class DashboardResponse(BaseModel):
    """Schema completo do dashboard."""
    metrics: DashboardMetricsResponse
    alerts_due_soon: list[RecurrenceAlertDetailedResponse] = Field(default_factory=list)
    alerts_overdue: list[RecurrenceAlertDetailedResponse] = Field(default_factory=list)
    high_risk_replenishments: list[ReplenishmentSuggestionResponse] = Field(default_factory=list)
    critical_products: list[ProductDemandForecastResponse] = Field(default_factory=list)
