"""
modules/recurrence/repository.py - Repositórios para Acesso aos Dados de Recorrência

Implementa o padrão Repository para centralizar operações de banco de dados.
"""

import uuid
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional, List

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func

from controlb.modules.recurrence.models import (
    CustomerPurchaseHistory,
    CustomerProductRecurrence,
    RecurrenceAlert,
    ProductDemandForecast,
    ProductDemandDetail,
    IntelligentReplenishmentSuggestion,
)


class PurchaseHistoryRepository:
    """Repositório para histórico de compras."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(
        self,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID,
        product_id: uuid.UUID,
        purchase_date: date,
        quantity: Decimal,
        unit_price: Decimal,
        total_amount: Decimal,
        sales_channel: str = "SALES",
        salesman_id: Optional[uuid.UUID] = None,
        sales_order_id: Optional[uuid.UUID] = None,
        notes: Optional[str] = None,
    ) -> CustomerPurchaseHistory:
        """Registra uma nova compra no histórico."""
        history = CustomerPurchaseHistory(
            organization_id=organization_id,
            customer_id=customer_id,
            product_id=product_id,
            purchase_date=purchase_date,
            quantity=quantity,
            unit_price=unit_price,
            total_amount=total_amount,
            sales_channel=sales_channel,
            salesman_id=salesman_id,
            sales_order_id=sales_order_id,
            notes=notes,
        )
        self.db.add(history)
        return history
    
    def get_customer_product_history(
        self,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID,
        product_id: uuid.UUID,
        limit: int = 100,
        days_back: Optional[int] = None,
    ) -> List[CustomerPurchaseHistory]:
        """Obtém histórico de compras de um cliente para um produto."""
        query = self.db.query(CustomerPurchaseHistory).filter(
            CustomerPurchaseHistory.organization_id == organization_id,
            CustomerPurchaseHistory.customer_id == customer_id,
            CustomerPurchaseHistory.product_id == product_id,
        )
        
        if days_back:
            cutoff_date = date.today() - timedelta(days=days_back)
            query = query.filter(CustomerPurchaseHistory.purchase_date >= cutoff_date)
        
        return query.order_by(desc(CustomerPurchaseHistory.purchase_date)).limit(limit).all()
    
    def get_customer_all_products_history(
        self,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID,
        days_back: Optional[int] = None,
    ) -> List[CustomerPurchaseHistory]:
        """Obtém histórico de compras de um cliente (todos os produtos)."""
        query = self.db.query(CustomerPurchaseHistory).filter(
            CustomerPurchaseHistory.organization_id == organization_id,
            CustomerPurchaseHistory.customer_id == customer_id,
        )
        
        if days_back:
            cutoff_date = date.today() - timedelta(days=days_back)
            query = query.filter(CustomerPurchaseHistory.purchase_date >= cutoff_date)
        
        return query.order_by(desc(CustomerPurchaseHistory.purchase_date)).all()


class RecurrenceRepository:
    """Repositório para análise de recorrência."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_or_create(
        self,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID,
        product_id: uuid.UUID,
    ) -> CustomerProductRecurrence:
        """Obtém ou cria um registro de recorrência."""
        recurrence = self.db.query(CustomerProductRecurrence).filter(
            CustomerProductRecurrence.organization_id == organization_id,
            CustomerProductRecurrence.customer_id == customer_id,
            CustomerProductRecurrence.product_id == product_id,
        ).first()
        
        if not recurrence:
            recurrence = CustomerProductRecurrence(
                organization_id=organization_id,
                customer_id=customer_id,
                product_id=product_id,
            )
            self.db.add(recurrence)
        
        return recurrence
    
    def update(self, recurrence: CustomerProductRecurrence) -> CustomerProductRecurrence:
        """Atualiza um registro de recorrência."""
        self.db.add(recurrence)
        return recurrence
    
    def get_active_recurrences(
        self,
        organization_id: uuid.UUID,
        product_id: Optional[uuid.UUID] = None,
        customer_id: Optional[uuid.UUID] = None,
    ) -> List[CustomerProductRecurrence]:
        """Obtém recorrências ativas."""
        query = self.db.query(CustomerProductRecurrence).filter(
            CustomerProductRecurrence.organization_id == organization_id,
            CustomerProductRecurrence.recurrence_status == "ACTIVE",
        )
        
        if product_id:
            query = query.filter(CustomerProductRecurrence.product_id == product_id)
        
        if customer_id:
            query = query.filter(CustomerProductRecurrence.customer_id == customer_id)
        
        return query.all()
    
    def get_due_for_purchase(
        self,
        organization_id: uuid.UUID,
        days_ahead: int = 7,
    ) -> List[CustomerProductRecurrence]:
        """Obtém recorrências vencidas ou próximas de vencer."""
        cutoff_date = date.today() + timedelta(days=days_ahead)
        
        return self.db.query(CustomerProductRecurrence).filter(
            CustomerProductRecurrence.organization_id == organization_id,
            CustomerProductRecurrence.recurrence_status == "ACTIVE",
            CustomerProductRecurrence.predicted_next_purchase_date.isnot(None),
            CustomerProductRecurrence.predicted_next_purchase_date <= cutoff_date,
        ).order_by(CustomerProductRecurrence.predicted_next_purchase_date).all()
    
    def get_overdue_purchases(
        self,
        organization_id: uuid.UUID,
    ) -> List[CustomerProductRecurrence]:
        """Obtém compras que já venceram."""
        return self.db.query(CustomerProductRecurrence).filter(
            CustomerProductRecurrence.organization_id == organization_id,
            CustomerProductRecurrence.recurrence_status == "ACTIVE",
            CustomerProductRecurrence.predicted_next_purchase_date.isnot(None),
            CustomerProductRecurrence.predicted_next_purchase_date < date.today(),
        ).order_by(CustomerProductRecurrence.predicted_next_purchase_date).all()


class AlertRepository:
    """Repositório para alertas de recorrência."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(
        self,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID,
        product_id: uuid.UUID,
        recurrence_id: uuid.UUID,
        alert_type: str,
        expected_purchase_date: date,
        days_until_purchase: Optional[int] = None,
    ) -> RecurrenceAlert:
        """Cria um novo alerta."""
        alert = RecurrenceAlert(
            organization_id=organization_id,
            customer_id=customer_id,
            product_id=product_id,
            recurrence_id=recurrence_id,
            alert_type=alert_type,
            expected_purchase_date=expected_purchase_date,
            days_until_purchase=days_until_purchase,
        )
        self.db.add(alert)
        return alert
    
    def get_by_id(self, alert_id: uuid.UUID) -> Optional[RecurrenceAlert]:
        """Obtém alerta por ID."""
        return self.db.query(RecurrenceAlert).filter(
            RecurrenceAlert.id == alert_id
        ).first()
    
    def get_open_alerts(
        self,
        organization_id: uuid.UUID,
        customer_id: Optional[uuid.UUID] = None,
    ) -> List[RecurrenceAlert]:
        """Obtém alertas abertos."""
        query = self.db.query(RecurrenceAlert).filter(
            RecurrenceAlert.organization_id == organization_id,
            RecurrenceAlert.status == "OPEN",
        )
        
        if customer_id:
            query = query.filter(RecurrenceAlert.customer_id == customer_id)
        
        return query.order_by(RecurrenceAlert.expected_purchase_date).all()
    
    def get_alerts_by_status(
        self,
        organization_id: uuid.UUID,
        status: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[RecurrenceAlert]:
        """Obtém alertas por status e intervalo de datas."""
        query = self.db.query(RecurrenceAlert).filter(
            RecurrenceAlert.organization_id == organization_id,
            RecurrenceAlert.status == status,
        )
        
        if start_date:
            query = query.filter(RecurrenceAlert.expected_purchase_date >= start_date)
        
        if end_date:
            query = query.filter(RecurrenceAlert.expected_purchase_date <= end_date)
        
        return query.order_by(RecurrenceAlert.expected_purchase_date).all()
    
    def get_alerts_due_soon(
        self,
        organization_id: uuid.UUID,
        days_ahead: int = 7,
    ) -> List[RecurrenceAlert]:
        """Obtém alertas vencidos ou próximos de vencer."""
        cutoff_date = date.today() + timedelta(days=days_ahead)
        
        return self.db.query(RecurrenceAlert).filter(
            RecurrenceAlert.organization_id == organization_id,
            RecurrenceAlert.status.in_(["OPEN", "ACKNOWLEDGED"]),
            RecurrenceAlert.expected_purchase_date <= cutoff_date,
        ).order_by(RecurrenceAlert.expected_purchase_date).all()
    
    def get_overdue_alerts(
        self,
        organization_id: uuid.UUID,
    ) -> List[RecurrenceAlert]:
        """Obtém alertas vencidos (data passou)."""
        return self.db.query(RecurrenceAlert).filter(
            RecurrenceAlert.organization_id == organization_id,
            RecurrenceAlert.status.in_(["OPEN", "ACKNOWLEDGED"]),
            RecurrenceAlert.expected_purchase_date < date.today(),
        ).order_by(RecurrenceAlert.expected_purchase_date).all()
    
    def get_existing_alert(
        self,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID,
        product_id: uuid.UUID,
        status_filter: Optional[List[str]] = None,
    ) -> Optional[RecurrenceAlert]:
        """Obtém alerta existente para cliente + produto."""
        query = self.db.query(RecurrenceAlert).filter(
            RecurrenceAlert.organization_id == organization_id,
            RecurrenceAlert.customer_id == customer_id,
            RecurrenceAlert.product_id == product_id,
        )
        
        if status_filter:
            query = query.filter(RecurrenceAlert.status.in_(status_filter))
        
        return query.order_by(desc(RecurrenceAlert.created_at)).first()
    
    def update(self, alert: RecurrenceAlert) -> RecurrenceAlert:
        """Atualiza um alerta."""
        self.db.add(alert)
        return alert


class DemandForecastRepository:
    """Repositório para previsão de demanda consolidada."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(
        self,
        organization_id: uuid.UUID,
        product_id: uuid.UUID,
        forecast_start_date: date,
        forecast_end_date: date,
        total_customers_with_recurrence: int = 0,
        predicted_total_quantity: Decimal = Decimal("0.0000"),
        predicted_total_revenue: Decimal = Decimal("0.00"),
        number_of_critical_customers: int = 0,
        risk_score: Decimal = Decimal("0.00"),
    ) -> ProductDemandForecast:
        """Cria uma previsão de demanda."""
        forecast = ProductDemandForecast(
            organization_id=organization_id,
            product_id=product_id,
            forecast_start_date=forecast_start_date,
            forecast_end_date=forecast_end_date,
            total_customers_with_recurrence=total_customers_with_recurrence,
            predicted_total_quantity=predicted_total_quantity,
            predicted_total_revenue=predicted_total_revenue,
            number_of_critical_customers=number_of_critical_customers,
            risk_score=risk_score,
            last_calculated_at=datetime.now(timezone.utc),
            valid_until=datetime.now(timezone.utc) + timedelta(days=1),
        )
        self.db.add(forecast)
        return forecast
    
    def get_latest_forecast(
        self,
        organization_id: uuid.UUID,
        product_id: uuid.UUID,
    ) -> Optional[ProductDemandForecast]:
        """Obtém previsão mais recente para um produto."""
        return self.db.query(ProductDemandForecast).filter(
            ProductDemandForecast.organization_id == organization_id,
            ProductDemandForecast.product_id == product_id,
        ).order_by(desc(ProductDemandForecast.created_at)).first()
    
    def get_high_risk_forecasts(
        self,
        organization_id: uuid.UUID,
        risk_score_threshold: Decimal = Decimal("70.00"),
    ) -> List[ProductDemandForecast]:
        """Obtém previsões com alto risco."""
        return self.db.query(ProductDemandForecast).filter(
            ProductDemandForecast.organization_id == organization_id,
            ProductDemandForecast.risk_score >= risk_score_threshold,
        ).order_by(desc(ProductDemandForecast.risk_score)).all()
    
    def get_valid_forecasts(
        self,
        organization_id: uuid.UUID,
    ) -> List[ProductDemandForecast]:
        """Obtém previsões ainda válidas (não expiradas)."""
        now = datetime.now(timezone.utc)
        return self.db.query(ProductDemandForecast).filter(
            ProductDemandForecast.organization_id == organization_id,
            ProductDemandForecast.valid_until > now,
        ).all()
    
    def update(self, forecast: ProductDemandForecast) -> ProductDemandForecast:
        """Atualiza uma previsão."""
        self.db.add(forecast)
        return forecast


class DemandDetailRepository:
    """Repositório para detalhe de demanda por cliente."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(
        self,
        demand_forecast_id: uuid.UUID,
        customer_id: uuid.UUID,
        product_id: uuid.UUID,
        predicted_quantity: Decimal,
        predicted_purchase_date: Optional[date] = None,
        relevance_score: Optional[Decimal] = None,
    ) -> ProductDemandDetail:
        """Cria detalhe de demanda."""
        detail = ProductDemandDetail(
            demand_forecast_id=demand_forecast_id,
            customer_id=customer_id,
            product_id=product_id,
            predicted_quantity=predicted_quantity,
            predicted_purchase_date=predicted_purchase_date,
            relevance_score=relevance_score,
        )
        self.db.add(detail)
        return detail
    
    def get_by_forecast(
        self,
        demand_forecast_id: uuid.UUID,
    ) -> List[ProductDemandDetail]:
        """Obtém detalhes de uma previsão."""
        return self.db.query(ProductDemandDetail).filter(
            ProductDemandDetail.demand_forecast_id == demand_forecast_id
        ).all()


class ReplenishmentSuggestionRepository:
    """Repositório para sugestões de reposição."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(
        self,
        organization_id: uuid.UUID,
        product_id: uuid.UUID,
        current_stock_quantity: Decimal,
        predicted_demand_quantity: Decimal,
        suggested_order_quantity: Decimal,
        demand_forecast_window_days: int,
        urgency_level: str = "MEDIUM",
        stock_out_risk_days: Optional[int] = None,
        demand_forecast_id: Optional[uuid.UUID] = None,
        justification: Optional[dict] = None,
    ) -> IntelligentReplenishmentSuggestion:
        """Cria uma sugestão de reposição."""
        from timezone import utc
        suggestion = IntelligentReplenishmentSuggestion(
            organization_id=organization_id,
            product_id=product_id,
            demand_forecast_id=demand_forecast_id,
            current_stock_quantity=current_stock_quantity,
            predicted_demand_quantity=predicted_demand_quantity,
            suggested_order_quantity=suggested_order_quantity,
            demand_forecast_window_days=demand_forecast_window_days,
            urgency_level=urgency_level,
            stock_out_risk_days=stock_out_risk_days,
            justification=justification,
        )
        self.db.add(suggestion)
        return suggestion
    
    def get_by_id(self, suggestion_id: uuid.UUID) -> Optional[IntelligentReplenishmentSuggestion]:
        """Obtém sugestão por ID."""
        return self.db.query(IntelligentReplenishmentSuggestion).filter(
            IntelligentReplenishmentSuggestion.id == suggestion_id
        ).first()
    
    def get_open_suggestions(
        self,
        organization_id: uuid.UUID,
        urgency_filter: Optional[List[str]] = None,
    ) -> List[IntelligentReplenishmentSuggestion]:
        """Obtém sugestões abertas."""
        query = self.db.query(IntelligentReplenishmentSuggestion).filter(
            IntelligentReplenishmentSuggestion.organization_id == organization_id,
            IntelligentReplenishmentSuggestion.status == "OPEN",
        )
        
        if urgency_filter:
            query = query.filter(IntelligentReplenishmentSuggestion.urgency_level.in_(urgency_filter))
        
        return query.order_by(
            desc(IntelligentReplenishmentSuggestion.urgency_level),
            IntelligentReplenishmentSuggestion.stock_out_risk_days,
        ).all()
    
    def get_critical_suggestions(
        self,
        organization_id: uuid.UUID,
    ) -> List[IntelligentReplenishmentSuggestion]:
        """Obtém sugestões críticas."""
        return self.db.query(IntelligentReplenishmentSuggestion).filter(
            IntelligentReplenishmentSuggestion.organization_id == organization_id,
            IntelligentReplenishmentSuggestion.urgency_level == "CRITICAL",
            IntelligentReplenishmentSuggestion.status.in_(["OPEN", "ACKNOWLEDGED"]),
        ).order_by(IntelligentReplenishmentSuggestion.stock_out_risk_days).all()
    
    def get_by_product(
        self,
        organization_id: uuid.UUID,
        product_id: uuid.UUID,
        status: Optional[str] = None,
    ) -> List[IntelligentReplenishmentSuggestion]:
        """Obtém sugestões para um produto."""
        query = self.db.query(IntelligentReplenishmentSuggestion).filter(
            IntelligentReplenishmentSuggestion.organization_id == organization_id,
            IntelligentReplenishmentSuggestion.product_id == product_id,
        )
        
        if status:
            query = query.filter(IntelligentReplenishmentSuggestion.status == status)
        
        return query.all()
    
    def update(self, suggestion: IntelligentReplenishmentSuggestion) -> IntelligentReplenishmentSuggestion:
        """Atualiza uma sugestão."""
        self.db.add(suggestion)
        return suggestion
    
    def get_pending_purchase_request(
        self,
        organization_id: uuid.UUID,
    ) -> List[IntelligentReplenishmentSuggestion]:
        """Obtém sugestões com purchase_request criado."""
        return self.db.query(IntelligentReplenishmentSuggestion).filter(
            IntelligentReplenishmentSuggestion.organization_id == organization_id,
            IntelligentReplenishmentSuggestion.purchase_request_id.isnot(None),
        ).all()
