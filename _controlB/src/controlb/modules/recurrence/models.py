"""
modules/recurrence/models.py - Modelos ORM para Análise de Recorrência de Compras

Define a estrutura de dados relacional para:
1. Histórico consolidado de compras por cliente-produto
2. Análise de recorrência e previsão de próxima compra
3. Alertas de oportunidades de recompra
4. Consolidação de demanda por produto
5. Sugestões inteligentes de reposição de estoque
"""

import uuid
from datetime import datetime, timezone, date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    String, Text, Boolean, DateTime, Date, Numeric, ForeignKey, Integer, JSON,
    Index, UniqueConstraint, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from controlb.db import Base

if TYPE_CHECKING:
    from controlb.modules.identity.models import Organization, User
    from controlb.modules.sales.models import Customer, SalesOrder
    from controlb.modules.inventory.models import Product
    from controlb.modules.crm.models import Opportunity
    from controlb.modules.purchasing.models import PurchaseRequest


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ==============================================================================
# 1. HISTÓRICO CONSOLIDADO DE COMPRAS POR CLIENTE E PRODUTO
# ==============================================================================

class CustomerPurchaseHistory(Base):
    """
    Tabela 'customer_purchase_history' - Histórico consolidado de compras.
    
    Alimentada automaticamente por:
    - Vendas registradas no módulo Sales (via SalesOrder)
    - Importações manuais (Arquivo/Planilha)
    - Registros manuais diretos (via API/UI)
    
    Serve como fonte de dados para análise de recorrência.
    """
    __tablename__ = "customer_purchase_history"
    __table_args__ = (
        Index("ix_purchase_history_customer_product_date", 
              "organization_id", "customer_id", "product_id", "purchase_date"),
        Index("ix_purchase_history_date_range",
              "organization_id", "purchase_date"),
        Index("ix_purchase_history_customer_date",
              "customer_id", "purchase_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customer.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sales_order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sales_order.id", ondelete="SET NULL"), nullable=True
    )

    # Dados da compra
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    # Contexto da compra
    sales_channel: Mapped[str] = mapped_column(
        String(50), default="SALES", nullable=False
    )  # SALES, POS, MANUAL_ENTRY, IMPORT
    salesman_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamentos
    sales_order: Mapped["SalesOrder | None"] = relationship(foreign_keys=[sales_order_id], lazy="select")
    salesman: Mapped["User | None"] = relationship(foreign_keys=[salesman_id], lazy="select")


# ==============================================================================
# 2. ANÁLISE DE RECORRÊNCIA POR CLIENTE E PRODUTO
# ==============================================================================

class CustomerProductRecurrence(Base):
    """
    Tabela 'customer_product_recurrence' - Análise de padrão recorrente.
    
    Calculada a partir do histórico de compras (customer_purchase_history).
    Armazena resultado da análise: frequência, intervalo médio, próxima compra prevista.
    
    Atualizada:
    - Automaticamente após registrar nova compra
    - Sob demanda via API
    - Periodicamente via job assíncrono
    """
    __tablename__ = "customer_product_recurrence"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "customer_id", "product_id",
            name="uq_recurrence_org_customer_product"
        ),
        Index("ix_recurrence_predicted_date",
              "organization_id", "predicted_next_purchase_date"),
        Index("ix_recurrence_status_date",
              "organization_id", "recurrence_status", "predicted_next_purchase_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customer.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Histórico
    total_purchases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    first_purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Análise de frequência
    average_days_between_purchases: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2), nullable=True
    )  # Intervalo médio em dias
    last_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Dias desde última compra
    purchase_frequency_type: Mapped[str] = mapped_column(
        String(50), default="IRREGULAR", nullable=False
    )
    # DAILY, WEEKLY, BIWEEKLY, MONTHLY, QUARTERLY, YEARLY, IRREGULAR

    # Previsão de recompra
    predicted_next_purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    confidence_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0.00"), nullable=False,
        info={"description": "Confiança 0-100 baseada em consistência histórica"}
    )

    # Quantidade média
    average_quantity_per_purchase: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    last_purchase_quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)

    # Status e priorização
    recurrence_status: Mapped[str] = mapped_column(
        String(50), default="INACTIVE", nullable=False, index=True
    )
    # ACTIVE, INACTIVE, IRREGULAR, DORMANT (sem compra há muito tempo)

    is_critical_for_retention: Mapped[bool] = mapped_column(Boolean, default=False)
    relevance_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("50.00"), nullable=False
    )  # 0-100, baseado em frequência, valor, importância

    # Override manual
    custom_recurrence_interval_days: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        info={"description": "Override manual do intervalo calculado"}
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamentos
    alerts: Mapped[list["RecurrenceAlert"]] = relationship(
        back_populates="recurrence", cascade="all, delete-orphan"
    )


# ==============================================================================
# 3. ALERTAS DE OPORTUNIDADE DE RECOMPRA
# ==============================================================================

class RecurrenceAlert(Base):
    """
    Tabela 'recurrence_alert' - Alertas de oportunidade de recompra.
    
    Gerada automaticamente quando:
    - Data prevista de recompra está próxima (configurável, ex: 7 dias)
    - Recorrência é marcada como ACTIVE
    - Alerta não existe ou foi resolvido
    
    Estados:
    OPEN → Alerta gerado, aguardando ação
    ACKNOWLEDGED → Vendedor viu e vai agir
    CONTACTED → Contato realizado com cliente
    OPPORTUNITY_CREATED → Oportunidade CRM criada
    CONVERTED → Cliente realizou compra (novo ciclo iniciado)
    DISMISSED → Descartado por inatividade ou cancelamento
    CANCELLED → Cancelado manualmente
    """
    __tablename__ = "recurrence_alert"
    __table_args__ = (
        Index("ix_alert_status_date",
              "organization_id", "status", "expected_purchase_date"),
        Index("ix_alert_customer_status",
              "customer_id", "status"),
        Index("ix_alert_opportunity",
              "opportunity_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customer.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recurrence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customer_product_recurrence.id", ondelete="CASCADE"), nullable=False
    )

    # Dados do alerta
    alert_type: Mapped[str] = mapped_column(String(50), default="REPURCHASE_DUE", nullable=False)
    # REPURCHASE_DUE, REPURCHASE_OVERDUE, STOCK_INSUFFICIENT
    
    expected_purchase_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    days_until_purchase: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Calculado, pode ser negativo se atrasado

    # Estado
    status: Mapped[str] = mapped_column(String(50), default="OPEN", nullable=False, index=True)
    # OPEN, ACKNOWLEDGED, OPPORTUNITY_CREATED, CONTACTED, CONVERTED, DISMISSED, CANCELLED

    # Resultado do contato
    contact_result: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # PURCHASED, INTERESTED, NOT_NEEDED, NOT_RESPONDED, DECLINED, RESCHEDULE

    contact_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    contacted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )

    # Linkagem com CRM
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("opportunity.id", ondelete="SET NULL"), nullable=True, index=True
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamentos
    recurrence: Mapped["CustomerProductRecurrence"] = relationship(back_populates="alerts", lazy="select")
    contacted_by: Mapped["User | None"] = relationship(foreign_keys=[contacted_by_id], lazy="select")


# ==============================================================================
# 4. CONSOLIDAÇÃO DE DEMANDA POR PRODUTO
# ==============================================================================

class ProductDemandForecast(Base):
    """
    Tabela 'product_demand_forecast' - Previsão consolidada de demanda por produto.
    
    Calcula a demanda total prevista de TODOS os clientes para um produto.
    Janela de previsão: configurável (ex: próximos 15 dias).
    
    Atualizada periodicamente via job ou sob demanda.
    """
    __tablename__ = "product_demand_forecast"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "product_id", "forecast_start_date", "forecast_end_date",
            name="uq_demand_forecast_org_product_window"
        ),
        Index("ix_demand_forecast_risk",
              "organization_id", "risk_score"),
        Index("ix_demand_forecast_valid",
              "organization_id", "valid_until"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Janela de previsão
    forecast_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    forecast_end_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Demanda consolidada
    total_customers_with_recurrence: Mapped[int] = mapped_column(Integer, default=0)
    predicted_total_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("0.0000"), nullable=False
    )
    predicted_total_revenue: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )

    # Risco
    number_of_critical_customers: Mapped[int] = mapped_column(Integer, default=0)
    risk_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0.00"), nullable=False
    )  # 0-100, risco de indisponibilidade impactar vendas

    last_calculated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamentos
    details: Mapped[list["ProductDemandDetail"]] = relationship(
        back_populates="forecast", cascade="all, delete-orphan"
    )
    suggestions: Mapped[list["IntelligentReplenishmentSuggestion"]] = relationship(
        back_populates="demand_forecast", cascade="all, delete-orphan"
    )


class ProductDemandDetail(Base):
    """
    Tabela 'product_demand_detail' - Composição da previsão por cliente.
    
    Detalha quais clientes contribuem para a demanda total de um produto.
    """
    __tablename__ = "product_demand_detail"
    __table_args__ = (
        Index("ix_demand_detail_forecast_customer",
              "demand_forecast_id", "customer_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    demand_forecast_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_demand_forecast.id", ondelete="CASCADE"), nullable=False
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customer.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product.id", ondelete="CASCADE"), nullable=False
    )

    predicted_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    predicted_purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    relevance_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relacionamentos
    forecast: Mapped["ProductDemandForecast"] = relationship(back_populates="details", lazy="select")


# ==============================================================================
# 5. SUGESTÕES INTELIGENTES DE REPOSIÇÃO
# ==============================================================================

class IntelligentReplenishmentSuggestion(Base):
    """
    Tabela 'intelligent_replenishment_suggestion' - Sugestão de reposição baseada em recorrência.
    
    Gerada quando:
    - Demanda prevista > Estoque disponível
    - Produto possui alertas de recorrência ativos
    - Configuração permite sugestões automáticas
    
    Estados:
    OPEN → Sugestão gerada, aguardando revisão
    ACKNOWLEDGED → Comprador revisou
    APPROVED → Comprador aprovou
    PURCHASE_REQUEST_CREATED → Solicitação de compra criada
    DISMISSED → Descartado por comprador
    """
    __tablename__ = "intelligent_replenishment_suggestion"
    __table_args__ = (
        Index("ix_replenishment_urgency_status",
              "organization_id", "urgency_level", "status"),
        Index("ix_replenishment_risk_days",
              "stock_out_risk_days"),
        Index("ix_replenishment_product",
              "product_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product.id", ondelete="CASCADE"), nullable=False, index=True
    )
    demand_forecast_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_demand_forecast.id", ondelete="SET NULL"), nullable=True
    )

    # Situação do estoque (snapshot no momento da sugestão)
    current_stock_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    minimum_stock_level: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    safety_stock_level: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)

    # Previsão de demanda
    predicted_demand_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    demand_forecast_window_days: Mapped[int] = mapped_column(Integer, nullable=False)

    # Pedidos em andamento
    pending_purchase_orders_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("0.0000")
    )

    # Sugestão
    suggested_order_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    suggested_reorder_point: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)

    # Justificativa estruturada (JSON)
    justification: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
    )

    # Indicadores
    urgency_level: Mapped[str] = mapped_column(String(50), default="MEDIUM", nullable=False, index=True)
    # LOW, MEDIUM, HIGH, CRITICAL

    stock_out_risk_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Estado
    status: Mapped[str] = mapped_column(String(50), default="OPEN", nullable=False, index=True)
    # OPEN, ACKNOWLEDGED, APPROVED, PURCHASE_REQUEST_CREATED, DISMISSED

    # Linkagem com compras
    purchase_request_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("purchase_request.id", ondelete="SET NULL"), nullable=True
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamentos
    demand_forecast: Mapped["ProductDemandForecast | None"] = relationship(
        back_populates="suggestions", lazy="select"
    )
