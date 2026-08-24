"""
modules/sales/api.py - Roteador de Endpoints REST do Módulo de Vendas & PDV (Sales Domain)
"""

import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from controlb.db import get_db
from controlb.modules.identity import service as identity_service
from controlb.modules.sales import service, schemas

router = APIRouter(prefix="/sales", tags=["Sales & POS / Vendas e Frente de Caixa"])


# ==============================================================================
# ORÇAMENTOS (QUOTES)
# ==============================================================================

@router.get("/quotes", response_model=list[schemas.SalesQuoteResponse], summary="Listar Orçamentos")
def list_sales_quotes(
    opportunity_id: uuid.UUID | None = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.require_permission("sales:view"))
):
    return service.list_sales_quotes(db, current_user.organization_id, opportunity_id)


@router.get("/quotes/{quote_id}", response_model=schemas.SalesQuoteResponse, summary="Obter Orçamento por ID")
def get_sales_quote(
    quote_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.require_permission("sales:view"))
):
    return service.get_sales_quote(db, quote_id, current_user.organization_id)


@router.post("/quotes", response_model=schemas.SalesQuoteResponse, status_code=status.HTTP_201_CREATED, summary="Criar Orçamento")
def create_sales_quote(
    payload: schemas.SalesQuoteCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.require_permission("sales:manage"))
):
    return service.create_sales_quote(db, current_user.organization_id, current_user, payload)


@router.put("/quotes/{quote_id}", response_model=schemas.SalesQuoteResponse, summary="Atualizar Orçamento")
def update_sales_quote(
    quote_id: uuid.UUID,
    payload: schemas.SalesQuoteUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.require_permission("sales:manage"))
):
    return service.update_sales_quote(db, quote_id, current_user.organization_id, payload)


@router.patch("/quotes/{quote_id}/status", response_model=schemas.SalesQuoteResponse, summary="Atualizar Status do Orçamento")
def update_sales_quote_status(
    quote_id: uuid.UUID,
    new_status: str = Query(..., description="DRAFT, SENT, APPROVED, REJECTED, CONVERTED, EXPIRED, CANCELLED"),
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.require_permission("sales:manage"))
):
    return service.update_sales_quote_status(
        db,
        quote_id,
        current_user.organization_id,
        new_status,
        current_user,
    )


@router.post("/quotes/{quote_id}/cancel", response_model=schemas.SalesQuoteResponse, summary="Cancelar Cotação com Justificativa")
def cancel_sales_quote(
    quote_id: uuid.UUID,
    payload: schemas.SalesQuoteCancelRequest,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.require_permission("sales:manage"))
):
    return service.cancel_sales_quote(
        db,
        quote_id,
        current_user.organization_id,
        payload.reason,
        current_user,
    )


@router.post("/quotes/{quote_id}/convert", response_model=schemas.SalesOrderResponse, summary="Converter Orçamento em Pedido de Venda")
def convert_quote_to_order(
    quote_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.require_permission("sales:manage"))
):
    return service.convert_quote_to_order(db, quote_id, current_user.organization_id, current_user)


@router.delete("/quotes/{quote_id}", status_code=status.HTTP_200_OK, summary="Cancelar Orçamento")
def delete_sales_quote(
    quote_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.require_permission("sales:manage"))
):
    return service.delete_sales_quote(db, quote_id, current_user.organization_id, current_user)


# ==============================================================================
# PEDIDOS DE VENDA
# ==============================================================================

@router.get("/orders", response_model=list[schemas.SalesOrderResponse], summary="Listar Pedidos de Venda")
def list_sales_orders(
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.require_permission("sales:view"))
):
    return service.list_sales_orders(db, current_user.organization_id)


@router.get("/orders/{order_id}", response_model=schemas.SalesOrderResponse, summary="Obter Pedido de Venda por ID")
def get_sales_order(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.require_permission("sales:view"))
):
    return service.get_sales_order(db, order_id, current_user.organization_id)


@router.post("/orders", response_model=schemas.SalesOrderResponse, status_code=status.HTTP_201_CREATED, summary="Criar Pedido de Venda")
def create_sales_order(
    payload: schemas.SalesOrderCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.require_permission("sales:manage"))
):
    return service.create_sales_order(db, current_user.organization_id, current_user, payload)


@router.patch("/orders/{order_id}/status", response_model=schemas.SalesOrderResponse, summary="Atualizar Status do Pedido de Venda")
def update_sales_order_status(
    order_id: uuid.UUID,
    payload: schemas.SalesOrderUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.require_permission("sales:manage"))
):
    return service.update_sales_order_status(db, order_id, current_user.organization_id, payload, current_user)


@router.post("/orders/{order_id}/request-billing", response_model=schemas.SalesOrderResponse, summary="Solicitar Faturamento do Pedido")
def request_order_billing(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.require_permission("sales:manage"))
):
    return service.request_order_billing(db, order_id, current_user.organization_id, current_user)


@router.delete("/orders/{order_id}", status_code=status.HTTP_200_OK, summary="Cancelar Pedido de Venda")
def delete_sales_order(
    order_id: uuid.UUID,
    reason: str | None = Query(None, description="Motivo do cancelamento"),
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.require_permission("sales:manage"))
):
    return service.delete_sales_order(db, order_id, current_user.organization_id, current_user, reason=reason)



# ==============================================================================
# FRENTE DE CAIXA / PDV BALCÃO
# ==============================================================================

@router.get("/pos/sessions/active", response_model=schemas.POSSessionResponse | None, summary="Obter Turno / Caixa Ativo do PDV")
def get_active_pos_session(
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.get_active_pos_session(db, current_user.organization_id)


@router.get("/pos/sessions", response_model=list[schemas.POSSessionResponse], summary="Listar Sessões / Turnos do PDV")
def list_pos_sessions(
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.list_pos_sessions(db, current_user.organization_id)


@router.post("/pos/sessions", response_model=schemas.POSSessionResponse, status_code=status.HTTP_201_CREATED, summary="Abrir Turno do PDV")
def open_pos_session(
    payload: schemas.POSSessionCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.open_pos_session(db, current_user.organization_id, current_user, payload)


@router.post("/pos/sessions/{session_id}/close", response_model=schemas.POSSessionResponse, summary="Encerrar Turno / Fechar Caixa PDV")
def close_pos_session(
    session_id: uuid.UUID,
    payload: schemas.POSSessionClose,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.close_pos_session(db, current_user.organization_id, session_id, current_user, payload)


@router.get("/pos/sales", response_model=list[schemas.POSSaleResponse], summary="Listar Vendas do PDV")
def list_pos_sales(
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.list_pos_sales(db, current_user.organization_id)


@router.post("/pos/sales", response_model=schemas.POSSaleResponse, status_code=status.HTTP_201_CREATED, summary="Registrar Venda no PDV")
def process_pos_sale(
    payload: schemas.POSSaleCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.process_pos_sale(db, current_user.organization_id, current_user, payload)


# ==============================================================================
# SANGRIA E SUPRIMENTO DE CAIXA PDV
# ==============================================================================

@router.get("/pos/cash-movements", response_model=list[schemas.POSCashMovementResponse], summary="Listar Sangrias e Suprimentos do PDV")
def list_pos_cash_movements(
    session_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.list_pos_cash_movements(db, current_user.organization_id, session_id)


@router.post("/pos/cash-movements", response_model=schemas.POSCashMovementResponse, status_code=status.HTTP_201_CREATED, summary="Registrar Sangria ou Suprimento no PDV")
def record_pos_cash_movement(
    payload: schemas.POSCashMovementCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.record_pos_cash_movement(db, current_user.organization_id, current_user, payload)


# ==============================================================================
# CADASTRO CENTRALIZADO DE CLIENTES (Customer)
# ==============================================================================

@router.get("/customers", response_model=list[schemas.CustomerResponse], summary="Listar Clientes (PF/PJ)")
def list_customers(
    search: str | None = None,
    is_active: bool | None = None,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.list_customers(db, current_user.organization_id, search, is_active)


@router.get("/customers/{customer_id}", response_model=schemas.CustomerResponse, summary="Obter Cliente por ID")
def get_customer(
    customer_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.get_customer(db, customer_id, current_user.organization_id)


@router.post("/customers", response_model=schemas.CustomerResponse, status_code=status.HTTP_201_CREATED, summary="Cadastrar Cliente")
def create_customer(
    payload: schemas.CustomerCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.create_customer(db, current_user.organization_id, payload)


@router.put("/customers/{customer_id}", response_model=schemas.CustomerResponse, summary="Atualizar Cliente")
def update_customer(
    customer_id: uuid.UUID,
    payload: schemas.CustomerUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.update_customer(db, customer_id, current_user.organization_id, payload)


@router.delete("/customers/{customer_id}", status_code=status.HTTP_200_OK, summary="Excluir Cliente")
def delete_customer(
    customer_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.delete_customer(db, customer_id, current_user.organization_id)


# ==============================================================================
# GESTÃO COMERCIAL (Metas e Tabelas de Preços)
# ==============================================================================

@router.get("/goals", response_model=list[schemas.SalesGoalResponse], summary="Listar Metas Comerciais")
def list_sales_goals(
    year: int | None = None,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.list_sales_goals(db, current_user.organization_id, year)


@router.post("/goals", response_model=schemas.SalesGoalResponse, status_code=status.HTTP_201_CREATED, summary="Cadastrar Meta Comercial")
def create_sales_goal(
    payload: schemas.SalesGoalCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.create_sales_goal(db, current_user.organization_id, current_user, payload)


@router.delete("/goals/{goal_id}", status_code=status.HTTP_200_OK, summary="Excluir Meta Comercial")
def delete_sales_goal(
    goal_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.delete_sales_goal(db, goal_id, current_user.organization_id)


@router.get("/price-tables", response_model=list[schemas.PriceTableResponse], summary="Listar Tabelas de Preços")
def list_price_tables(
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.list_price_tables(db, current_user.organization_id)


@router.post("/price-tables", response_model=schemas.PriceTableResponse, status_code=status.HTTP_201_CREATED, summary="Criar Tabela de Preços")
def create_price_table(
    payload: schemas.PriceTableCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.create_price_table(db, current_user.organization_id, payload)


@router.delete("/price-tables/{table_id}", status_code=status.HTTP_200_OK, summary="Excluir Tabela de Preços")
def delete_price_table(
    table_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.delete_price_table(db, table_id, current_user.organization_id)


# ==============================================================================
# PÓS-VENDA (Devoluções e Trocas)
# ==============================================================================

@router.get("/returns", response_model=list[schemas.SalesReturnResponse], summary="Listar Devoluções e Trocas")
def list_sales_returns(
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.list_sales_returns(db, current_user.organization_id)


@router.post("/returns", response_model=schemas.SalesReturnResponse, status_code=status.HTTP_201_CREATED, summary="Registrar Devolução ou Troca")
def process_sales_return(
    payload: schemas.SalesReturnCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.process_sales_return(db, current_user.organization_id, current_user, payload)


@router.delete("/returns/{return_id}", status_code=status.HTTP_200_OK, summary="Excluir Devolução ou Troca")
def delete_sales_return(
    return_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.delete_sales_return(db, return_id, current_user.organization_id)



# ==============================================================================
# INDICADORES E BI ANALÍTICO
# ==============================================================================

@router.get("/analytics", response_model=schemas.SalesAnalyticsResponse, summary="Obter Métricas e Indicadores Comerciais")
def get_sales_analytics(
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.get_sales_analytics(db, current_user.organization_id)


# ==============================================================================
# VENDEDORES E FORÇA DE VENDAS
# ==============================================================================

@router.get("/sellers", response_model=list[schemas.SellerResponse], summary="Listar Vendedores Ativos da Organização")
def list_sellers(
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Retorna lista de vendedores com equipe comercial associada."""
    return service.list_sellers(db, current_user.organization_id)
