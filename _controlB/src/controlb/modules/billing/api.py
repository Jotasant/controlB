"""
modules/billing/api.py - Roteador de Endpoints REST do Módulo de Faturamento (Billing Domain)
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from controlb.db import get_db
from controlb.modules.billing import schemas, service
from controlb.modules.documents import schemas as document_schemas
from controlb.modules.identity import service as identity_service

router = APIRouter(prefix="/billing", tags=["Billing / Faturamento"])


@router.get("/invoices", response_model=list[schemas.InvoiceResponse], summary="Listar Faturas Comerciais")
def list_invoices(
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.require_permission("billing:view"))
):
    return service.list_invoices(db, current_user.organization_id)


@router.post("/invoices", response_model=schemas.InvoiceResponse, status_code=status.HTTP_201_CREATED, summary="Emitir Fatura Comercial")
def create_invoice(
    payload: schemas.InvoiceCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.require_permission("billing:manage"))
):
    return service.create_invoice(db, current_user.organization_id, current_user, payload)


@router.get("/requests", response_model=list[document_schemas.DocumentResponse], summary="Listar solicitações de faturamento")
def list_billing_requests(
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.require_permission("billing:view")),
):
    return service.list_billing_requests(db, current_user.organization_id)


@router.post(
    "/requests/{request_id}/issue",
    response_model=schemas.InvoiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Processar solicitação e emitir faturamento",
)
def issue_billing_request(
    request_id: uuid.UUID,
    payload: schemas.BillingRequestIssue,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.require_permission("billing:manage")),
):
    return service.process_billing_request(
        db, current_user.organization_id, request_id, current_user, payload
    )


@router.post(
    "/requests/{request_id}/cancel",
    response_model=document_schemas.DocumentResponse,
    summary="Cancelar solicitação de faturamento pendente",
)
def cancel_billing_request(
    request_id: uuid.UUID,
    payload: schemas.BillingRequestCancel,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.require_permission("billing:manage")),
):
    return service.cancel_billing_request(
        db, current_user.organization_id, request_id, current_user, payload
    )


@router.get("/invoices/{invoice_id}", response_model=schemas.InvoiceResponse, summary="Detalhar Fatura Comercial")
def get_invoice(
    invoice_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.require_permission("billing:view")),
):
    return service.get_invoice(db, current_user.organization_id, invoice_id)


@router.patch("/invoices/{invoice_id}", response_model=schemas.InvoiceResponse, summary="Editar Fatura Comercial")
def update_invoice(
    invoice_id: uuid.UUID,
    payload: schemas.InvoiceUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.require_permission("billing:manage")),
):
    return service.update_invoice(
        db, current_user.organization_id, invoice_id, current_user, payload
    )


@router.post("/invoices/{invoice_id}/cancel", response_model=schemas.InvoiceResponse, summary="Cancelar Fatura Comercial")
def cancel_invoice(
    invoice_id: uuid.UUID,
    payload: schemas.InvoiceCancel,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.require_permission("billing:manage")),
):
    return service.cancel_invoice(
        db, current_user.organization_id, invoice_id, current_user, payload
    )
