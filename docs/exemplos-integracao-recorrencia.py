"""
EXEMPLOS DE INTEGRAÇÃO — Módulo de Recorrência

Demonstra como integrar o módulo de recorrência com outros módulos do ControlB.
"""

# ==============================================================================
# EXEMPLO 1: Registrar Compra ao Finalizar SalesOrder
# ==============================================================================
"""
Integração: Módulo Sales → Módulo Recurrence

Quando uma venda é finalizada, registrar automaticamente no histórico de recorrência.
"""

from fastapi import APIRouter
from sqlalchemy.orm import Session
from controlb.modules.recurrence.service import PurchaseHistoryService

router = APIRouter()

@router.post("/sales-orders", response_model=dict)
def create_sales_order(data: dict, db: Session, current_user):
    """
    Criar SalesOrder e registrar no histórico de recorrência.
    """
    # 1. Lógica existente de criar SalesOrder
    sales_order = SalesOrder(
        customer_id=data["customer_id"],
        organization_id=current_user.organization_id,
        # ... mais campos
    )
    db.add(sales_order)
    db.flush()
    
    # 2. NOVO: Registrar no histórico de recorrência
    history_service = PurchaseHistoryService(db)
    
    for item in data["items"]:
        history, recurrence = history_service.record_purchase(
            organization_id=str(current_user.organization_id),
            customer_id=str(data["customer_id"]),
            product_id=str(item["product_id"]),
            purchase_date=date.today(),
            quantity=item["quantity"],
            unit_price=item["unit_price"],
            total_amount=item["quantity"] * item["unit_price"],
            sales_channel="SALES",
            sales_order_id=str(sales_order.id),
            salesman_id=str(current_user.id),
        )
        print(f"✓ Compra registrada: {item['product_id']}")
        print(f"  Status recorrência: {recurrence.recurrence_status}")
        print(f"  Próxima compra prevista: {recurrence.predicted_next_purchase_date}")
    
    db.commit()
    return {"id": str(sales_order.id), "status": "created"}


# ==============================================================================
# EXEMPLO 2: Criar Oportunidade no CRM Automaticamente
# ==============================================================================
"""
Integração: Módulo Recurrence → Módulo CRM

Quando um alerta de recorrência é gerado, criar automaticamente uma oportunidade no CRM.
"""

from controlb.modules.crm.models import Opportunity, CRMStage
from controlb.modules.recurrence.service import RecurrenceAlertService

def generate_daily_alerts():
    """
    Job que executa diariamente para gerar alertas e opportunities.
    """
    db = SessionLocal()
    try:
        from controlb.modules.recurrence.repository import RecurrenceRepository
        from controlb.modules.inventory.models import Product
        
        recurrence_repo = RecurrenceRepository(db)
        alert_service = RecurrenceAlertService(db)
        
        # Obter todas as recorrências ativas com previsão nos próximos 7 dias
        organizations = db.query(Organization.id).distinct().all()
        
        for org_tuple in organizations:
            organization_id = org_tuple[0]
            recurrences = recurrence_repo.get_due_for_purchase(organization_id, days_ahead=7)
            
            for recurrence in recurrences:
                # 1. Gerar alerta
                alert = alert_service.generate_alert(
                    organization_id=str(organization_id),
                    customer_id=str(recurrence.customer_id),
                    product_id=str(recurrence.product_id),
                    recurrence_id=str(recurrence.id),
                    days_before_alert=7,
                )
                
                if alert:
                    # 2. Criar opportunity no CRM
                    product = db.query(Product).filter(
                        Product.id == recurrence.product_id
                    ).first()
                    
                    # Obter stage "Prospection"
                    stage = db.query(CRMStage).filter(
                        CRMStage.organization_id == organization_id,
                        CRMStage.code == "PROSPECTION"
                    ).first()
                    
                    if stage:
                        opportunity = Opportunity(
                            organization_id=organization_id,
                            customer_id=recurrence.customer_id,
                            stage_id=stage.id,
                            title=f"Recompra: {product.name}",
                            expected_close_date=recurrence.predicted_next_purchase_date,
                            estimated_value=recurrence.average_quantity_per_purchase * product.current_price,
                            probability_percent=75,  # Alto porque é padrão recorrente
                            recurrence_source=True,  # Marcar como de recorrência
                        )
                        db.add(opportunity)
                        db.flush()
                        
                        # Linkar alerta à opportunity
                        alert.opportunity_id = opportunity.id
                        
                        print(f"✓ Opportunity criada: {opportunity.title}")
        
        db.commit()
    finally:
        db.close()


# ==============================================================================
# EXEMPLO 3: Verificar Estoque e Sugerir Reposição
# ==============================================================================
"""
Integração: Módulo Recurrence + Inventory → Sugestão Automática

Quando há demanda recorrente prevista, verificar estoque e sugerir reposição.
"""

from controlb.modules.inventory.models import Product, InventoryBalance, InventoryLocation
from controlb.modules.recurrence.service import ReplenishmentSuggestionService

def generate_daily_replenishment_suggestions():
    """
    Job que executa diariamente para gerar sugestões de reposição.
    """
    db = SessionLocal()
    try:
        suggestion_service = ReplenishmentSuggestionService(db)
        
        organizations = db.query(Organization.id).distinct().all()
        
        for org_tuple in organizations:
            organization_id = org_tuple[0]
            
            # Obter todos os produtos que têm recorrência ativa
            products_with_recurrence = db.query(Product).filter(
                Product.organization_id == organization_id,
                Product.has_recurrence_demand == True
            ).all()
            
            for product in products_with_recurrence:
                # Obter estoque atual
                default_location = db.query(InventoryLocation).filter(
                    InventoryLocation.organization_id == organization_id,
                    InventoryLocation.is_default == True
                ).first()
                
                balance = db.query(InventoryBalance).filter(
                    InventoryBalance.product_id == product.id,
                    InventoryBalance.location_id == default_location.id
                ).first()
                
                current_stock = balance.quantity if balance else Decimal("0.0000")
                
                # Gerar sugestão se necessário
                suggestion = suggestion_service.assess_product_gap(
                    organization_id=str(organization_id),
                    product_id=str(product.id),
                    current_stock=current_stock,
                    minimum_stock=product.minimum_stock_level,
                    safety_stock=product.safety_stock_level,
                    forecast_window_days=15,
                )
                
                if suggestion:
                    print(f"⚠️  Sugestão criada: {product.name}")
                    print(f"   Urgência: {suggestion.urgency_level}")
                    print(f"   Riscos em {suggestion.stock_out_risk_days} dias")
        
        db.commit()
    finally:
        db.close()


# ==============================================================================
# EXEMPLO 4: Criar Solicitação de Compra Automaticamente
# ==============================================================================
"""
Integração: Sugestão de Reposição → PurchaseRequest

Quando uma sugestão é aprovada, criar automaticamente uma solicitação de compra.
"""

from controlb.modules.purchasing.models import PurchaseRequest, PurchaseRequestItem
from controlb.modules.recurrence.repository import ReplenishmentSuggestionRepository
import json

@router.post("/replenishment-suggestions/{suggestion_id}/approve-and-request")
def approve_suggestion_and_create_purchase_request(
    suggestion_id: str,
    db: Session,
    current_user,
):
    """
    Aprova sugestão e cria solicitação de compra automaticamente.
    """
    suggestion_repo = ReplenishmentSuggestionRepository(db)
    suggestion = suggestion_repo.get_by_id(suggestion_id)
    
    if not suggestion:
        raise HTTPException(status_code=404, detail="Sugestão não encontrada")
    
    # 1. Atualizar sugestão como aprovada
    suggestion.status = "APPROVED"
    suggestion_repo.update(suggestion)
    db.flush()
    
    # 2. Criar PurchaseRequest
    purchase_request = PurchaseRequest(
        organization_id=suggestion.organization_id,
        requester_id=current_user.id,
        request_number=generate_purchase_request_number(),
        justification=json.dumps(suggestion.justification),
        status="draft",
        total_estimated_amount=Decimal("0.00"),
        required_date=date.today() + timedelta(days=3),  # ASAP
    )
    db.add(purchase_request)
    db.flush()
    
    # 3. Criar item(s) na solicitação
    product = db.query(Product).filter(
        Product.id == suggestion.product_id
    ).first()
    
    # TODO: Buscar preço do fornecedor
    estimated_unit_price = Decimal("100.00")
    
    item = PurchaseRequestItem(
        purchase_request_id=purchase_request.id,
        product_id=suggestion.product_id,
        quantity=suggestion.suggested_order_quantity,
        estimated_unit_price=estimated_unit_price,
        total_estimated_amount=suggestion.suggested_order_quantity * estimated_unit_price,
    )
    db.add(item)
    db.flush()
    
    # 4. Atualizar sugestão com linkagem
    suggestion.status = "PURCHASE_REQUEST_CREATED"
    suggestion.purchase_request_id = purchase_request.id
    suggestion_repo.update(suggestion)
    
    db.commit()
    
    print(f"✓ Solicitação de compra criada: {purchase_request.request_number}")
    print(f"  Produto: {product.name}")
    print(f"  Quantidade: {suggestion.suggested_order_quantity}")
    print(f"  Motivo: Demanda recorrente prevista")
    
    return {
        "purchase_request_id": str(purchase_request.id),
        "purchase_request_number": purchase_request.request_number,
    }


# ==============================================================================
# EXEMPLO 5: Dashboard CRM com Alertas de Recorrência
# ==============================================================================
"""
Integração: Recurrence → CRM Dashboard

Frontend do CRM mostra alertas de recorrência para o vendedor.
"""

from controlb.modules.recurrence.repository import AlertRepository

@router.get("/crm/dashboard")
def get_crm_dashboard(db: Session, current_user):
    """
    Dashboard do CRM com alertas de recorrência.
    """
    alert_repo = AlertRepository(db)
    
    # Obter alertas vencidos ou próximos
    alerts_due_soon = alert_repo.get_alerts_due_soon(
        organization_id=current_user.organization_id,
        days_ahead=7,
    )
    
    alerts_overdue = alert_repo.get_overdue_alerts(
        organization_id=current_user.organization_id,
    )
    
    # Montar dashboard
    dashboard = {
        "summary": {
            "total_alerts_open": len(alert_repo.get_open_alerts(current_user.organization_id)),
            "total_alerts_due_soon": len(alerts_due_soon),
            "total_alerts_overdue": len(alerts_overdue),
        },
        "alerts": {
            "due_soon": [
                {
                    "id": str(alert.id),
                    "customer_name": db.query(Customer).filter(
                        Customer.id == alert.customer_id
                    ).first().name,
                    "product_name": db.query(Product).filter(
                        Product.id == alert.product_id
                    ).first().name,
                    "expected_purchase_date": alert.expected_purchase_date,
                    "days_until": (alert.expected_purchase_date - date.today()).days,
                    "status": alert.status,
                    "actions": ["Contact", "Reschedule", "Dismiss"],
                }
                for alert in alerts_due_soon
            ],
            "overdue": [
                {
                    "id": str(alert.id),
                    "customer_name": db.query(Customer).filter(
                        Customer.id == alert.customer_id
                    ).first().name,
                    "product_name": db.query(Product).filter(
                        Product.id == alert.product_id
                    ).first().name,
                    "days_overdue": (date.today() - alert.expected_purchase_date).days,
                    "status": alert.status,
                }
                for alert in alerts_overdue
            ],
        },
    }
    
    return dashboard


# ==============================================================================
# EXEMPLO 6: Registrar Contato e Resultado de Alerta
# ==============================================================================
"""
Integração: CRM → Recurrence

Vendedor registra que contatou cliente e qual foi o resultado.
"""

@router.put("/recurrence/alerts/{alert_id}/contact")
def register_alert_contact(
    alert_id: str,
    data: dict,  # {"contact_result": "PURCHASED", "notes": "Cliente comprou 2 caixas"}
    db: Session,
    current_user,
):
    """
    Registra contato realizado com cliente e seu resultado.
    """
    from controlb.modules.recurrence.service import RecurrenceAlertService
    
    alert_service = RecurrenceAlertService(db)
    
    # Atualizar alerta
    alert = alert_service.update_alert_status(
        alert_id=alert_id,
        status="CONTACTED",
        contact_result=data.get("contact_result"),
        contact_date=datetime.now(timezone.utc),
        contacted_by_id=str(current_user.id),
        notes=data.get("notes"),
    )
    
    db.commit()
    
    print(f"✓ Contato registrado: {alert.contact_result}")
    
    # Se cliente comprou, o histórico será atualizado quando a venda for registrada
    if data.get("contact_result") == "PURCHASED":
        print("  → Aguardando registro de nova venda para atualizar ciclo de recorrência")
    
    return {"alert_id": str(alert.id), "status": alert.status}


# ==============================================================================
# EXEMPLO 7: Testar Sistema Localmente
# ==============================================================================
"""
Script para testar o módulo de recorrência localmente.
"""

def test_recurrence_flow():
    """
    Teste completo do fluxo de recorrência:
    1. Registrar compras
    2. Detectar recorrência
    3. Gerar alerta
    4. Verificar demanda
    5. Sugerir reposição
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from controlb.modules.recurrence.service import (
        PurchaseHistoryService,
        RecurrenceAnalysisService,
        DemandForecastService,
        ReplenishmentSuggestionService,
    )
    
    # Conectar ao BD
    engine = create_engine("postgresql://user:pass@localhost/controlb_dev")
    db = Session(engine)
    
    try:
        # IDs de teste (substituir com valores reais)
        org_id = "550e8400-e29b-41d4-a716-446655440000"
        customer_id = "550e8400-e29b-41d4-a716-446655440001"
        product_id = "550e8400-e29b-41d4-a716-446655440002"
        
        # 1. Registrar compras
        print("\n1️⃣  Registrando compras...")
        history_service = PurchaseHistoryService(db)
        
        for i in range(3):
            purchase_date = date(2024, 10 + i, 15)
            history, recurrence = history_service.record_purchase(
                organization_id=org_id,
                customer_id=customer_id,
                product_id=product_id,
                purchase_date=purchase_date,
                quantity=Decimal("2"),
                unit_price=Decimal("50.00"),
                total_amount=Decimal("100.00"),
            )
            print(f"   ✓ Compra registrada: {purchase_date}")
        
        db.commit()
        
        # 2. Verificar recorrência detectada
        print("\n2️⃣  Verificando recorrência...")
        analysis_service = RecurrenceAnalysisService(db)
        recurrence = analysis_service.calculate_recurrence(org_id, customer_id, product_id)
        
        print(f"   Status: {recurrence.recurrence_status}")
        print(f"   Frequência: {recurrence.purchase_frequency_type}")
        print(f"   Intervalo médio: {recurrence.average_days_between_purchases} dias")
        print(f"   Próxima compra: {recurrence.predicted_next_purchase_date}")
        print(f"   Confiança: {recurrence.confidence_score}%")
        
        # 3. Consolidar demanda
        print("\n3️⃣  Consolidando demanda...")
        forecast_service = DemandForecastService(db)
        forecast = forecast_service.consolidate_product_demand(
            org_id, product_id, forecast_window_days=15
        )
        
        print(f"   Clientes com recorrência: {forecast.total_customers_with_recurrence}")
        print(f"   Demanda prevista: {forecast.predicted_total_quantity} unidades")
        print(f"   Receita prevista: R$ {forecast.predicted_total_revenue}")
        print(f"   Risk score: {forecast.risk_score}%")
        
        # 4. Gerar sugestão de reposição
        print("\n4️⃣  Gerando sugestão de reposição...")
        replenishment_service = ReplenishmentSuggestionService(db)
        suggestion = replenishment_service.assess_product_gap(
            organization_id=org_id,
            product_id=product_id,
            current_stock=Decimal("5"),
            minimum_stock=Decimal("10"),
            safety_stock=Decimal("15"),
        )
        
        if suggestion:
            print(f"   ✓ Sugestão criada!")
            print(f"   Urgência: {suggestion.urgency_level}")
            print(f"   Quantidade sugerida: {suggestion.suggested_order_quantity}")
            print(f"   Risco de ruptura: {suggestion.stock_out_risk_days} dias")
        else:
            print("   ℹ️  Estoque suficiente, nenhuma sugestão")
        
        db.commit()
        
        print("\n✅ Teste concluído com sucesso!")
        
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    test_recurrence_flow()
