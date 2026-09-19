"""
modules/recurrence/service.py - Serviços de Lógica de Negócio para Recorrência

Implementa os algoritmos de análise, previsão e consolidação de recorrência.
"""

import json
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from statistics import mean, stdev
from typing import Optional, List, Tuple, Dict, Any

from sqlalchemy.orm import Session

from controlb.modules.recurrence.repository import (
    PurchaseHistoryRepository,
    RecurrenceRepository,
    AlertRepository,
    DemandForecastRepository,
    DemandDetailRepository,
    ReplenishmentSuggestionRepository,
)
from controlb.modules.recurrence.models import (
    CustomerProductRecurrence,
    RecurrenceAlert,
    ProductDemandForecast,
    IntelligentReplenishmentSuggestion,
)


class RecurrenceAnalysisService:
    """
    Serviço para análise de recorrência de compras.
    
    Responsabilidades:
    - Detectar padrões de frequência no histórico de compras
    - Calcular intervalo médio entre compras
    - Prever próxima data de compra
    - Calcular relevância/importância da recorrência
    - Atualizar status de atividade
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.history_repo = PurchaseHistoryRepository(db)
        self.recurrence_repo = RecurrenceRepository(db)
    
    def calculate_recurrence(
        self,
        organization_id: str,
        customer_id: str,
        product_id: str,
        days_back: int = 365,
    ) -> CustomerProductRecurrence:
        """
        Calcula recorrência para combinação cliente + produto.
        
        Args:
            organization_id: ID da organização
            customer_id: ID do cliente
            product_id: ID do produto
            days_back: Número de dias de histórico a considerar
        
        Returns:
            Registro atualizado de recorrência
        """
        import uuid
        
        # Converter strings para UUIDs se necessário
        org_id = uuid.UUID(organization_id) if isinstance(organization_id, str) else organization_id
        cust_id = uuid.UUID(customer_id) if isinstance(customer_id, str) else customer_id
        prod_id = uuid.UUID(product_id) if isinstance(product_id, str) else product_id
        
        # Obter histórico de compras
        history = self.history_repo.get_customer_product_history(
            org_id, cust_id, prod_id, limit=100, days_back=days_back
        )
        
        # Obter ou criar registro de recorrência
        recurrence = self.recurrence_repo.get_or_create(org_id, cust_id, prod_id)
        
        # Se menos de 2 compras, marcar como inativo
        if len(history) < 2:
            recurrence.total_purchases = len(history)
            if history:
                recurrence.last_purchase_date = history[0].purchase_date
                recurrence.first_purchase_date = history[0].purchase_date
                recurrence.last_purchase_quantity = history[0].quantity
                recurrence.average_quantity_per_purchase = history[0].quantity
            recurrence.recurrence_status = "INACTIVE"
            recurrence.confidence_score = Decimal("0.00")
            self.recurrence_repo.update(recurrence)
            self.db.flush()
            return recurrence
        
        # Ordenar histórico por data (mais recente primeiro)
        history_sorted = sorted(history, key=lambda x: x.purchase_date, reverse=True)
        
        # Análise básica
        recurrence.total_purchases = len(history_sorted)
        recurrence.last_purchase_date = history_sorted[0].purchase_date
        recurrence.first_purchase_date = history_sorted[-1].purchase_date
        recurrence.last_purchase_quantity = history_sorted[0].quantity
        
        # Calcular intervalo médio entre compras
        pattern = self._detect_frequency_pattern(history_sorted)
        recurrence.purchase_frequency_type = pattern["type"]
        recurrence.average_days_between_purchases = Decimal(str(pattern["average_days"]))
        recurrence.last_interval_days = pattern["last_interval_days"]
        recurrence.confidence_score = Decimal(str(pattern["confidence_score"]))
        
        # Calcular quantidade média
        quantities = [Decimal(str(h.quantity)) for h in history_sorted]
        recurrence.average_quantity_per_purchase = sum(quantities) / len(quantities)
        
        # Prever próxima compra
        predicted_date, updated_confidence = self._predict_next_purchase_date(
            recurrence.last_purchase_date,
            recurrence.average_days_between_purchases,
            recurrence.custom_recurrence_interval_days,
        )
        recurrence.predicted_next_purchase_date = predicted_date
        recurrence.confidence_score = Decimal(str(updated_confidence))
        
        # Determinar status
        if pattern["confidence_score"] >= 60 and len(history_sorted) >= 2:
            recurrence.recurrence_status = "ACTIVE"
        elif pattern["type"] == "IRREGULAR":
            recurrence.recurrence_status = "IRREGULAR"
        else:
            recurrence.recurrence_status = "INACTIVE"
        
        # Calcular relevância (score 0-100)
        relevance = self._calculate_relevance_score(
            len(history_sorted),
            sum(Decimal(str(h.total_amount)) for h in history_sorted),
            pattern["confidence_score"],
        )
        recurrence.relevance_score = Decimal(str(relevance))
        
        # Atualizar
        self.recurrence_repo.update(recurrence)
        self.db.flush()
        
        return recurrence
    
    def _detect_frequency_pattern(self, history: List) -> Dict[str, Any]:
        """
        Detecta padrão de frequência analisando histórico de compras.
        
        Returns:
            Dict com: type, average_days, std_dev, confidence_score, last_interval_days, sample_size
        """
        if len(history) < 2:
            return {
                "type": "IRREGULAR",
                "average_days": 0,
                "std_dev": 0,
                "confidence_score": 0,
                "last_interval_days": 0,
                "sample_size": len(history),
            }
        
        # Calcular intervalos entre compras consecutivas
        intervals = []
        for i in range(len(history) - 1):
            days = (history[i].purchase_date - history[i + 1].purchase_date).days
            intervals.append(days)
        
        avg_interval = mean(intervals)
        std_dev_val = stdev(intervals) if len(intervals) > 1 else 0
        coef_variation = (std_dev_val / avg_interval * 100) if avg_interval > 0 else 0
        last_interval = intervals[0] if intervals else 0
        
        # Classificar padrão
        if coef_variation > 50:  # Variação muito alta = irregular
            pattern_type = "IRREGULAR"
        elif avg_interval <= 1:
            pattern_type = "DAILY"
        elif avg_interval <= 7:
            pattern_type = "WEEKLY"
        elif avg_interval <= 14:
            pattern_type = "BIWEEKLY"
        elif avg_interval <= 30:
            pattern_type = "MONTHLY"
        elif avg_interval <= 90:
            pattern_type = "QUARTERLY"
        else:
            pattern_type = "YEARLY"
        
        # Calcular confiança (0-100)
        confidence = max(0, 100 - (coef_variation))
        confidence = min(100, confidence)  # Garantir máximo de 100
        
        return {
            "type": pattern_type,
            "average_days": round(avg_interval, 2),
            "std_dev": round(std_dev_val, 2),
            "confidence_score": round(confidence, 2),
            "last_interval_days": last_interval,
            "sample_size": len(history),
        }
    
    def _predict_next_purchase_date(
        self,
        last_purchase_date: date,
        average_interval_days: Decimal,
        custom_interval_days: Optional[int] = None,
    ) -> Tuple[date, float]:
        """
        Estima data da próxima compra.
        
        Returns:
            Tupla (predicted_date, confidence_score)
        """
        interval_days = float(custom_interval_days or average_interval_days or 0)
        
        if interval_days <= 0:
            return date.today(), 0.0
        
        predicted_date = last_purchase_date + timedelta(days=interval_days)
        
        # Se há override manual, confiança é maior
        confidence = 95.0 if custom_interval_days else 75.0
        
        return predicted_date, confidence
    
    def _calculate_relevance_score(
        self,
        total_purchases: int,
        total_value: Decimal,
        confidence: float,
    ) -> float:
        """
        Calcula score de relevância (0-100).
        
        Fatores:
        - Número de compras (frequência)
        - Valor total gasto
        - Confiança do padrão
        """
        # Peso para número de compras (até 40 pontos)
        purchases_score = min(40, total_purchases * 5)
        
        # Peso para valor total (até 35 pontos)
        value_score = min(35, float(total_value) / 100)
        
        # Peso para confiança (até 25 pontos)
        confidence_score = confidence * 0.25
        
        relevance = purchases_score + value_score + confidence_score
        
        return min(100, round(relevance, 2))


class PurchaseHistoryService:
    """Serviço para gerenciar histórico de compras."""
    
    def __init__(self, db: Session):
        self.db = db
        self.history_repo = PurchaseHistoryRepository(db)
        self.recurrence_service = RecurrenceAnalysisService(db)
    
    def record_purchase(
        self,
        organization_id: str,
        customer_id: str,
        product_id: str,
        purchase_date: date,
        quantity: Decimal,
        unit_price: Decimal,
        total_amount: Decimal,
        sales_channel: str = "SALES",
        salesman_id: Optional[str] = None,
        sales_order_id: Optional[str] = None,
        notes: Optional[str] = None,
    ):
        """
        Registra uma nova compra e recalcula recorrência.
        
        Fluxo:
        1. Registrar no histórico
        2. Recalcular recorrência
        3. Gerar alerta se aplicável
        """
        import uuid
        
        org_id = uuid.UUID(organization_id) if isinstance(organization_id, str) else organization_id
        cust_id = uuid.UUID(customer_id) if isinstance(customer_id, str) else customer_id
        prod_id = uuid.UUID(product_id) if isinstance(product_id, str) else product_id
        salesman_uuid = uuid.UUID(salesman_id) if salesman_id and isinstance(salesman_id, str) else salesman_id
        sales_order_uuid = uuid.UUID(sales_order_id) if sales_order_id and isinstance(sales_order_id, str) else sales_order_id
        
        # 1. Registrar no histórico
        history = self.history_repo.create(
            organization_id=org_id,
            customer_id=cust_id,
            product_id=prod_id,
            purchase_date=purchase_date,
            quantity=quantity,
            unit_price=unit_price,
            total_amount=total_amount,
            sales_channel=sales_channel,
            salesman_id=salesman_uuid,
            sales_order_id=sales_order_uuid,
            notes=notes,
        )
        self.db.flush()
        
        # 2. Recalcular recorrência
        recurrence = self.recurrence_service.calculate_recurrence(
            org_id, cust_id, prod_id
        )
        
        return history, recurrence


class RecurrenceAlertService:
    """Serviço para gerenciar alertas de recorrência."""
    
    def __init__(self, db: Session):
        self.db = db
        self.alert_repo = AlertRepository(db)
        self.recurrence_repo = RecurrenceRepository(db)
    
    def generate_alert(
        self,
        organization_id: str,
        customer_id: str,
        product_id: str,
        recurrence_id: str,
        days_before_alert: int = 7,
    ) -> Optional[RecurrenceAlert]:
        """
        Gera alerta se recorrência está ativa e próxima da data prevista.
        
        Returns:
            RecurrenceAlert criado ou None se condições não foram atendidas
        """
        import uuid
        
        org_id = uuid.UUID(organization_id) if isinstance(organization_id, str) else organization_id
        cust_id = uuid.UUID(customer_id) if isinstance(customer_id, str) else customer_id
        prod_id = uuid.UUID(product_id) if isinstance(product_id, str) else product_id
        rec_id = uuid.UUID(recurrence_id) if isinstance(recurrence_id, str) else recurrence_id
        
        # Verificar se já existe alerta aberto
        existing = self.alert_repo.get_existing_alert(
            org_id, cust_id, prod_id,
            status_filter=["OPEN", "ACKNOWLEDGED"]
        )
        if existing:
            return None  # Alerta já existe
        
        # Criar novo alerta
        today = date.today()
        cutoff_date = today + timedelta(days=days_before_alert)
        
        alert = self.alert_repo.create(
            organization_id=org_id,
            customer_id=cust_id,
            product_id=prod_id,
            recurrence_id=rec_id,
            alert_type="REPURCHASE_DUE",
            expected_purchase_date=today,  # Será atualizado abaixo
            days_until_purchase=days_before_alert,
        )
        
        return alert
    
    def update_alert_status(
        self,
        alert_id: str,
        status: str,
        contact_result: Optional[str] = None,
        contact_date: Optional[datetime] = None,
        contacted_by_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> RecurrenceAlert:
        """Atualiza status de um alerta."""
        import uuid
        
        alert_uuid = uuid.UUID(alert_id) if isinstance(alert_id, str) else alert_id
        alert = self.alert_repo.get_by_id(alert_uuid)
        
        if not alert:
            raise ValueError(f"Alerta não encontrado: {alert_id}")
        
        alert.status = status
        if contact_result:
            alert.contact_result = contact_result
        if contact_date:
            alert.contact_date = contact_date
        if contacted_by_id:
            contacted_by_uuid = uuid.UUID(contacted_by_id) if isinstance(contacted_by_id, str) else contacted_by_id
            alert.contacted_by_id = contacted_by_uuid
        if notes:
            alert.notes = notes
        
        return self.alert_repo.update(alert)


class DemandForecastService:
    """Serviço para consolidar demanda e criar previsões."""
    
    def __init__(self, db: Session):
        self.db = db
        self.forecast_repo = DemandForecastRepository(db)
        self.detail_repo = DemandDetailRepository(db)
        self.recurrence_repo = RecurrenceRepository(db)
    
    def consolidate_product_demand(
        self,
        organization_id: str,
        product_id: str,
        forecast_window_days: int = 15,
    ) -> ProductDemandForecast:
        """
        Consolida demanda recorrente de todos os clientes para um produto.
        
        Args:
            organization_id: ID da organização
            product_id: ID do produto
            forecast_window_days: Número de dias para prever
        
        Returns:
            ProductDemandForecast com demanda consolidada
        """
        import uuid
        from controlb.modules.inventory.models import InventoryBalance
        
        org_id = uuid.UUID(organization_id) if isinstance(organization_id, str) else organization_id
        prod_id = uuid.UUID(product_id) if isinstance(product_id, str) else product_id
        
        # Obter todas as recorrências ativas para o produto
        recurrences = self.recurrence_repo.get_active_recurrences(
            org_id, product_id=prod_id
        )
        
        total_quantity = Decimal("0.0000")
        total_revenue = Decimal("0.00")
        critical_customers = 0
        forecast_start = date.today()
        forecast_end = forecast_start + timedelta(days=forecast_window_days)
        
        # Criar forecast
        forecast = self.forecast_repo.create(
            organization_id=org_id,
            product_id=prod_id,
            forecast_start_date=forecast_start,
            forecast_end_date=forecast_end,
            total_customers_with_recurrence=len(recurrences),
        )
        
        # Processar cada recorrência
        for recurrence in recurrences:
            # Verificar se previsão cai na janela
            if recurrence.predicted_next_purchase_date and \
               recurrence.predicted_next_purchase_date <= forecast_end:
                
                qty = recurrence.average_quantity_per_purchase or Decimal("0.0000")
                # Nota: Aqui seria necessário buscar o preço do produto
                # Por enquanto, assumindo valor unitário de 0
                price = Decimal("0.00")
                
                total_quantity += qty
                total_revenue += qty * price
                
                if recurrence.is_critical_for_retention:
                    critical_customers += 1
                
                # Criar detalhe
                self.detail_repo.create(
                    demand_forecast_id=forecast.id,
                    customer_id=recurrence.customer_id,
                    product_id=prod_id,
                    predicted_quantity=qty,
                    predicted_purchase_date=recurrence.predicted_next_purchase_date,
                    relevance_score=recurrence.relevance_score,
                )
        
        # Atualizar totais na forecast
        forecast.predicted_total_quantity = total_quantity
        forecast.predicted_total_revenue = total_revenue
        forecast.number_of_critical_customers = critical_customers
        
        # Calcular risco (necessita integração com estoque)
        risk_score = self._calculate_risk_score(total_quantity, critical_customers, len(recurrences))
        forecast.risk_score = Decimal(str(risk_score))
        
        self.forecast_repo.update(forecast)
        self.db.flush()
        
        return forecast
    
    def _calculate_risk_score(
        self,
        predicted_demand: Decimal,
        critical_customers: int,
        total_customers: int,
    ) -> float:
        """Calcula score de risco (0-100)."""
        # Fator 1: Demanda elevada (até 40 pontos)
        demand_score = min(40, float(predicted_demand) * 5)
        
        # Fator 2: Clientes críticos (até 35 pontos)
        critical_score = (critical_customers / max(total_customers, 1)) * 35 if total_customers > 0 else 0
        
        # Fator 3: Número de clientes (até 25 pontos)
        customers_score = min(25, total_customers * 2.5)
        
        risk = demand_score + critical_score + customers_score
        
        return min(100, round(risk, 2))


class ReplenishmentSuggestionService:
    """Serviço para gerar sugestões de reposição inteligente."""
    
    def __init__(self, db: Session):
        self.db = db
        self.suggestion_repo = ReplenishmentSuggestionRepository(db)
        self.forecast_service = DemandForecastService(db)
    
    def generate_suggestions(
        self,
        organization_id: str,
    ) -> List[IntelligentReplenishmentSuggestion]:
        """Gera sugestões de reposição para todos os produtos."""
        # TODO: Implementar lógica para varrer todos os produtos com recorrência
        return []
    
    def assess_product_gap(
        self,
        organization_id: str,
        product_id: str,
        current_stock: Decimal,
        minimum_stock: Optional[Decimal],
        safety_stock: Optional[Decimal],
        pending_orders: Decimal = Decimal("0.0000"),
        forecast_window_days: int = 15,
    ) -> Optional[IntelligentReplenishmentSuggestion]:
        """
        Avalia gap entre estoque disponível e demanda prevista.
        
        Returns:
            IntelligentReplenishmentSuggestion se há gap, None caso contrário
        """
        import uuid
        
        org_id = uuid.UUID(organization_id) if isinstance(organization_id, str) else organization_id
        prod_id = uuid.UUID(product_id) if isinstance(product_id, str) else product_id
        
        # Consolidar demanda
        forecast = self.forecast_service.consolidate_product_demand(
            org_id, prod_id, forecast_window_days
        )
        
        available_stock = current_stock + pending_orders
        predicted_demand = forecast.predicted_total_quantity
        
        # Calcular gap
        gap = predicted_demand - available_stock
        
        if gap <= 0:
            return None  # Estoque suficiente
        
        # Calcular quantidade sugerida
        safety = safety_stock or Decimal("0.0000")
        suggested_qty = gap + max(Decimal("0.0000"), safety - current_stock)
        
        # Calcular urgência
        consumption_rate = predicted_demand / max(forecast_window_days, 1)
        if consumption_rate > 0:
            days_to_stockout = int(current_stock / consumption_rate)
        else:
            days_to_stockout = 999
        
        if days_to_stockout < 3:
            urgency = "CRITICAL"
        elif days_to_stockout < 7:
            urgency = "HIGH"
        elif days_to_stockout < 15:
            urgency = "MEDIUM"
        else:
            urgency = "LOW"
        
        # Montar justificativa
        justification = {
            "current_stock": float(current_stock),
            "pending_purchase_orders": float(pending_orders),
            "available_stock": float(available_stock),
            "predicted_demand": float(predicted_demand),
            "gap": float(gap),
            "safety_stock": float(safety),
            "minimum_stock": float(minimum_stock or 0),
            "number_of_customers": forecast.total_customers_with_recurrence,
            "critical_customers": forecast.number_of_critical_customers,
            "forecast_window_days": forecast_window_days,
            "days_to_stockout": days_to_stockout,
            "consumption_rate_per_day": float(consumption_rate),
        }
        
        # Criar sugestão
        suggestion = self.suggestion_repo.create(
            organization_id=org_id,
            product_id=prod_id,
            current_stock_quantity=current_stock,
            minimum_stock_level=minimum_stock,
            safety_stock_level=safety_stock,
            predicted_demand_quantity=predicted_demand,
            suggested_order_quantity=suggested_qty,
            demand_forecast_window_days=forecast_window_days,
            urgency_level=urgency,
            stock_out_risk_days=days_to_stockout if days_to_stockout < 999 else None,
            demand_forecast_id=forecast.id,
            justification=justification,
        )
        
        self.db.flush()
        
        return suggestion
