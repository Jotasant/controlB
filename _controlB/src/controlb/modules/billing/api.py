"""
modules/billing/api.py - Roteador de Endpoints REST do Módulo de Faturamento (Billing Domain)
"""

import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from controlb.db import get_db
from controlb.modules.identity import service as identity_service
from controlb.modules.billing import service, schemas

router = APIRouter(prefix="/billing", tags=["Billing / Faturamento"])


@router.get("/invoices", response_model=list[schemas.InvoiceResponse], summary="Listar Faturas Comerciais")
def list_invoices(
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.list_invoices(db, current_user.organization_id)


@router.post("/invoices", response_model=schemas.InvoiceResponse, status_code=status.HTTP_201_CREATED, summary="Emitir Fatura Comercial")
def create_invoice(
    payload: schemas.InvoiceCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.create_invoice(db, current_user.organization_id, current_user, payload)
