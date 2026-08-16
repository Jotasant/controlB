"""
modules/billing/repository.py - Camada de Persistência do Módulo de Faturamento
"""

import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from controlb.modules.billing.models import Invoice, InvoiceInstallment


def get_invoice_by_id(db: Session, invoice_id: uuid.UUID, organization_id: uuid.UUID) -> Invoice | None:
    stmt = select(Invoice).where(Invoice.id == invoice_id, Invoice.organization_id == organization_id)
    return db.scalars(stmt).first()


def list_invoices(db: Session, organization_id: uuid.UUID) -> list[Invoice]:
    stmt = select(Invoice).where(Invoice.organization_id == organization_id).order_by(Invoice.created_at.desc())
    return list(db.scalars(stmt).all())


def create_invoice(db: Session, invoice: Invoice) -> Invoice:
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def update_invoice(db: Session, invoice: Invoice) -> Invoice:
    db.commit()
    db.refresh(invoice)
    return invoice
