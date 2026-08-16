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
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.list_sales_quotes(db, current_user.organization_id)


@router.post("/quotes", response_model=schemas.SalesQuoteResponse, status_code=status.HTTP_201_CREATED, summary="Criar Orçamento")
def create_sales_quote(
    payload: schemas.SalesQuoteCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.create_sales_quote(db, current_user.organization_id, current_user, payload)


# ==============================================================================
# PEDIDOS DE VENDA
# ==============================================================================

@router.get("/orders", response_model=list[schemas.SalesOrderResponse], summary="Listar Pedidos de Venda")
def list_sales_orders(
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.list_sales_orders(db, current_user.organization_id)


@router.post("/orders", response_model=schemas.SalesOrderResponse, status_code=status.HTTP_201_CREATED, summary="Criar Pedido de Venda")
def create_sales_order(
    payload: schemas.SalesOrderCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.create_sales_order(db, current_user.organization_id, current_user, payload)


# ==============================================================================
# FRENTE DE CAIXA / PDV BALCÃO
# ==============================================================================

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
