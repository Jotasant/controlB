"""
modules/billing/service.py - Regras de Negócio do Módulo de Faturamento
"""

import uuid
from datetime import datetime, timezone, date, timedelta
from decimal import Decimal
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from controlb.logger import logger
from controlb.modules.identity.models import User
from controlb.modules.billing import models, repository, schemas
from controlb.modules.finance import service as finance_service, schemas as finance_schemas


def create_invoice(
    db: Session,
    organization_id: uuid.UUID,
    current_user: User,
    payload: schemas.InvoiceCreate
) -> models.Invoice:
    inv_num = f"FAT-{date.today().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
    
    invoice = models.Invoice(
        organization_id=organization_id,
        sales_order_id=payload.sales_order_id,
        invoice_number=inv_num,
        customer_name=payload.customer_name.strip(),
        customer_document=payload.customer_document.strip() if payload.customer_document else None,
        total_amount=payload.total_amount,
        tax_amount=payload.tax_amount,
        net_amount=payload.total_amount + payload.tax_amount,
        issue_date=payload.issue_date,
        due_date=payload.due_date,
        notes=payload.notes,
        created_by_id=current_user.id
    )

    inst_count = payload.installments_count or 1
    total_net = invoice.net_amount
    inst_val = (total_net / Decimal(str(inst_count))).quantize(Decimal("0.01"))

    for i in range(1, inst_count + 1):
        if i == inst_count:
            part_amt = total_net - (inst_val * Decimal(str(inst_count - 1)))
        else:
            part_amt = inst_val

        due = payload.due_date + timedelta(days=(i - 1) * 30)

        inst = models.InvoiceInstallment(
            installment_number=i,
            total_installments=inst_count,
            amount=part_amt,
            due_date=due,
            status="PENDING"
        )
        invoice.installments.append(inst)

        # Alimenta o Contas a Receber no Financeiro
        if payload.generate_receivables_in_finance:
            finance_service.create_receivable(
                db,
                organization_id,
                finance_schemas.ReceivableCreate(
                    customer_name=payload.customer_name.strip(),
                    customer_document=payload.customer_document,
                    description=f"Fatura {inv_num} (Parcela {i}/{inst_count})",
                    original_amount=part_amt,
                    issue_date=payload.issue_date,
                    due_date=due,
                    payment_method_expected="BOLETO",
                    notes=f"Originado da Fatura Comercial #{inv_num}"
                )
            )

    saved_invoice = repository.create_invoice(db, invoice)
    logger.info(f"🧾 [INVOICE CREATED] Fatura #{inv_num} emitida para '{payload.customer_name}': {total_net} R$ em {inst_count} parcela(s)")
    return saved_invoice


def list_invoices(db: Session, organization_id: uuid.UUID) -> list[models.Invoice]:
    return repository.list_invoices(db, organization_id)
