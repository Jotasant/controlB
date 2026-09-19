"""
modules/recurrence/api.py - Rotas REST para Módulo de Recorrência

Expõe endpoints para:
- Análise de recorrência por cliente
- Gerenciamento de alertas
- Consolidação de demanda
- Sugestões de reposição
- Dashboard de recorrência
"""

from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from controlb.db import get_db
from controlb.modules.recurrence.schemas import (
    CustomerAnalysisResponse,
    CustomerProductRecurrenceResponse,
    PurchaseHistoryCreate,
    PurchaseHistoryResponse,
    RecurrenceAlertResponse,
    RecurrenceAlertDetailedResponse,
    RecurrenceAlertUpdate,
    ProductDemandForecastResponse,
    ReplenishmentSuggestionResponse,
    ReplenishmentSuggestionApproveRequest,
    DashboardMetricsResponse,
    DashboardResponse,
)
from controlb.modules.recurrence.service import (
    RecurrenceAnalysisService,
    PurchaseHistoryService,
    RecurrenceAlertService,
    DemandForecastService,
    ReplenishmentSuggestionService,
)
from controlb.modules.recurrence.repository import (
    PurchaseHistoryRepository,
    RecurrenceRepository,
    AlertRepository,
    DemandForecastRepository,
    DemandDetailRepository,
    ReplenishmentSuggestionRepository,
)


router = APIRouter(prefix="/api/v1/recurrence", tags=["recurrence"])


# ==============================================================================
# ANÁLISE DE RECORRÊNCIA
# ==============================================================================

@router.get("/customers/{customer_id}/analysis", response_model=CustomerAnalysisResponse)
def get_customer_analysis(
    customer_id: str,
    db: Session = Depends(get_db),
):
    """
    Obtém análise completa de recorrência para um cliente.
    
    Retorna histórico de compras, padrões detectados e previsões.
    """
    service = RecurrenceAnalysisService(db)
    recurrence_repo = RecurrenceRepository(db)
    
    # TODO: Obter customer_name do banco
    
    # Obter todas as recorrências do cliente
    recurrences = recurrence_repo.get_active_recurrences(
        organization_id="",  # TODO: Obter da autenticação
        customer_id=customer_id,
    )
    
    # Converter para schemas
    products = [
        CustomerProductRecurrenceResponse.from_orm(rec)
        for rec in recurrences
    ]
    
    return CustomerAnalysisResponse(
        customer_id=customer_id,
        customer_name="",  # TODO: Obter do banco
        total_purchases=sum(p.total_purchases for p in products),
        products=products,
    )


@router.get("/customers/{customer_id}/products", response_model=List[CustomerProductRecurrenceResponse])
def get_customer_products_recurrence(
    customer_id: str,
    db: Session = Depends(get_db),
):
    """Obtém recorrências de todos os produtos comprados por um cliente."""
    recurrence_repo = RecurrenceRepository(db)
    
    recurrences = recurrence_repo.get_active_recurrences(
        organization_id="",  # TODO: Obter da autenticação
        customer_id=customer_id,
    )
    
    return [
        CustomerProductRecurrenceResponse.from_orm(rec)
        for rec in recurrences
    ]


# ==============================================================================
# HISTÓRICO DE COMPRAS
# ==============================================================================

@router.post("/manual-purchase", response_model=PurchaseHistoryResponse, status_code=status.HTTP_201_CREATED)
def create_manual_purchase(
    data: PurchaseHistoryCreate,
    db: Session = Depends(get_db),
):
    """
    Registra uma compra manual (histórica ou não registrada pelo fluxo normal).
    
    Útil para:
    - Registrar vendas anteriores não capturadas
    - Importar histórico de vendas de outro sistema
    - Registrar vendas em loja física sem PDV integrado
    
    Efeito colateral: Recalcula recorrência automaticamente.
    """
    history_service = PurchaseHistoryService(db)
    
    history, recurrence = history_service.record_purchase(
        organization_id="",  # TODO: Obter da autenticação
        customer_id=str(data.customer_id),
        product_id=str(data.product_id),
        purchase_date=data.purchase_date,
        quantity=data.quantity,
        unit_price=data.unit_price,
        total_amount=data.total_amount,
        sales_channel=data.sales_channel,
        salesman_id=data.salesman_id,
        notes=data.notes,
    )
    
    db.commit()
    
    return PurchaseHistoryResponse.from_orm(history)


# ==============================================================================
# ALERTAS DE RECORRÊNCIA
# ==============================================================================

@router.get("/alerts", response_model=List[RecurrenceAlertDetailedResponse])
def get_recurrence_alerts(
    status: Optional[str] = Query(None, description="Filtrar por status"),
    due_in_days: Optional[int] = Query(7, description="Alertas vencidos ou com essa quantidade de dias"),
    customer_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Obtém alertas de recorrência.
    
    Filtros disponíveis:
    - status: OPEN, ACKNOWLEDGED, CONTACTED, CONVERTED, DISMISSED
    - due_in_days: Quantos dias para frente buscar (padrão: 7)
    - customer_id: Filtro por cliente específico
    """
    alert_repo = AlertRepository(db)
    
    if status:
        alerts = alert_repo.get_alerts_by_status(
            organization_id="",  # TODO: Obter da autenticação
            status=status,
        )
    elif due_in_days:
        alerts = alert_repo.get_alerts_due_soon(
            organization_id="",  # TODO: Obter da autenticação
            days_ahead=due_in_days,
        )
    else:
        alerts = alert_repo.get_open_alerts(
            organization_id="",  # TODO: Obter da autenticação
            customer_id=customer_id,
        )
    
    # TODO: Enriquecer com dados de customer, product, salesman
    
    return [
        RecurrenceAlertDetailedResponse.from_orm(alert)
        for alert in alerts
    ]


@router.get("/alerts/overdue", response_model=List[RecurrenceAlertDetailedResponse])
def get_overdue_alerts(
    db: Session = Depends(get_db),
):
    """Obtém alertas vencidos (data prevista já passou)."""
    alert_repo = AlertRepository(db)
    
    alerts = alert_repo.get_overdue_alerts(
        organization_id="",  # TODO: Obter da autenticação
    )
    
    return [
        RecurrenceAlertDetailedResponse.from_orm(alert)
        for alert in alerts
    ]


@router.put("/alerts/{alert_id}", response_model=RecurrenceAlertResponse)
def update_alert_status(
    alert_id: str,
    data: RecurrenceAlertUpdate,
    db: Session = Depends(get_db),
):
    """
    Atualiza status de um alerta.
    
    Estados possíveis:
    - ACKNOWLEDGED: Vendedor viu o alerta
    - CONTACTED: Contato realizado com cliente
    - CONVERTED: Cliente realizou compra
    - DISMISSED: Descartado
    """
    alert_service = RecurrenceAlertService(db)
    
    alert = alert_service.update_alert_status(
        alert_id=alert_id,
        status=data.status,
        contact_result=data.contact_result,
        contact_date=data.contact_date,
        notes=data.notes,
    )
    
    db.commit()
    
    return RecurrenceAlertResponse.from_orm(alert)


# ==============================================================================
# CONSOLIDAÇÃO DE DEMANDA
# ==============================================================================

@router.get("/demand-forecast/{product_id}", response_model=ProductDemandForecastResponse)
def get_product_demand_forecast(
    product_id: str,
    window_days: int = Query(15, ge=1, le=90, description="Janela de previsão em dias"),
    db: Session = Depends(get_db),
):
    """
    Obtém consolidação de demanda prevista para um produto.
    
    Agrupa todas as previsões de compra recorrente de clientes
    e calcula demanda total, risco, etc.
    """
    forecast_service = DemandForecastService(db)
    
    forecast = forecast_service.consolidate_product_demand(
        organization_id="",  # TODO: Obter da autenticação
        product_id=product_id,
        forecast_window_days=window_days,
    )
    
    db.commit()
    
    # TODO: Enriquecer com dados de product
    
    return ProductDemandForecastResponse.from_orm(forecast)


# ==============================================================================
# SUGESTÕES DE REPOSIÇÃO
# ==============================================================================

@router.get("/replenishment-suggestions", response_model=List[ReplenishmentSuggestionResponse])
def get_replenishment_suggestions(
    urgency: Optional[str] = Query(None, description="Filtrar por urgência (CRITICAL,HIGH,MEDIUM,LOW)"),
    status: Optional[str] = Query(None, description="Filtrar por status (OPEN,ACKNOWLEDGED,APPROVED)"),
    db: Session = Depends(get_db),
):
    """
    Obtém sugestões de reposição baseadas em demanda prevista.
    
    Filtros:
    - urgency: CRITICAL, HIGH, MEDIUM, LOW
    - status: OPEN, ACKNOWLEDGED, APPROVED, PURCHASE_REQUEST_CREATED
    """
    suggestion_repo = ReplenishmentSuggestionRepository(db)
    
    urgency_filter = urgency.split(",") if urgency else None
    
    suggestions = suggestion_repo.get_open_suggestions(
        organization_id="",  # TODO: Obter da autenticação
        urgency_filter=urgency_filter,
    )
    
    # TODO: Filtrar por status se fornecido
    
    return [
        ReplenishmentSuggestionResponse.from_orm(sug)
        for sug in suggestions
    ]


@router.get("/replenishment-suggestions/critical", response_model=List[ReplenishmentSuggestionResponse])
def get_critical_replenishment_suggestions(
    db: Session = Depends(get_db),
):
    """Obtém sugestões críticas de reposição."""
    suggestion_repo = ReplenishmentSuggestionRepository(db)
    
    suggestions = suggestion_repo.get_critical_suggestions(
        organization_id="",  # TODO: Obter da autenticação
    )
    
    return [
        ReplenishmentSuggestionResponse.from_orm(sug)
        for sug in suggestions
    ]


@router.post(
    "/replenishment-suggestions/{suggestion_id}/approve",
    response_model=ReplenishmentSuggestionResponse,
)
def approve_replenishment_suggestion(
    suggestion_id: str,
    data: ReplenishmentSuggestionApproveRequest,
    db: Session = Depends(get_db),
):
    """
    Aprova uma sugestão de reposição.
    
    Opcionalmente cria automaticamente uma solicitação de compra (PurchaseRequest)
    se create_purchase_request=true.
    """
    suggestion_repo = ReplenishmentSuggestionRepository(db)
    
    suggestion = suggestion_repo.get_by_id(suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Sugestão não encontrada")
    
    # Atualizar quantidade se fornecida
    if data.suggested_order_quantity:
        suggestion.suggested_order_quantity = data.suggested_order_quantity
    
    suggestion.status = "APPROVED"
    if data.notes:
        suggestion.notes = data.notes
    
    suggestion_repo.update(suggestion)
    db.flush()
    
    # TODO: Se create_purchase_request=True, criar PurchaseRequest
    
    db.commit()
    
    return ReplenishmentSuggestionResponse.from_orm(suggestion)


# ==============================================================================
# DASHBOARD
# ==============================================================================

@router.get("/dashboard", response_model=DashboardResponse)
def get_recurrence_dashboard(
    db: Session = Depends(get_db),
):
    """
    Dashboard resumido com principais indicadores e alertas.
    
    Inclui:
    - Métricas principais (KPIs)
    - Alertas vencidos ou próximos
    - Sugestões críticas de reposição
    - Produtos em risco
    """
    alert_repo = AlertRepository(db)
    suggestion_repo = ReplenishmentSuggestionRepository(db)
    
    org_id = ""  # TODO: Obter da autenticação
    
    # Obter dados
    alerts_due = alert_repo.get_alerts_due_soon(org_id, days_ahead=7)
    alerts_overdue = alert_repo.get_overdue_alerts(org_id)
    critical_replenishments = suggestion_repo.get_critical_suggestions(org_id)
    
    # Montar métricas
    metrics = DashboardMetricsResponse(
        total_customers_with_recurrence=0,  # TODO: Calcular
        total_alerts_open=len(alert_repo.get_open_alerts(org_id)),
        total_alerts_overdue=len(alerts_overdue),
        critical_alerts_count=len([a for a in alerts_overdue if a.is_critical_for_retention]),
        high_risk_products_count=0,  # TODO: Calcular
        replenishment_suggestions_open=len(suggestion_repo.get_open_suggestions(org_id)),
        replenishment_suggestions_critical=len(critical_replenishments),
        total_predicted_revenue_30_days=Decimal("0.00"),
        total_predicted_quantity_30_days=Decimal("0.0000"),
    )
    
    return DashboardResponse(
        metrics=metrics,
        alerts_due_soon=[RecurrenceAlertDetailedResponse.from_orm(a) for a in alerts_due],
        alerts_overdue=[RecurrenceAlertDetailedResponse.from_orm(a) for a in alerts_overdue],
        high_risk_replenishments=[ReplenishmentSuggestionResponse.from_orm(s) for s in critical_replenishments],
        critical_products=[],  # TODO: Carregar
    )


# ==============================================================================
# WEBHOOK / INTEGRAÇÃO COM VENDAS
# ==============================================================================

@router.post("/hooks/sales-order-completed", status_code=status.HTTP_204_NO_CONTENT)
def on_sales_order_completed(
    data: dict,
    db: Session = Depends(get_db),
):
    """
    Webhook chamado quando uma venda é confirmada.
    
    Triggers:
    1. Registra compra no histórico
    2. Recalcula recorrência
    3. Gera alertas se aplicável
    """
    # TODO: Implementar
    pass
