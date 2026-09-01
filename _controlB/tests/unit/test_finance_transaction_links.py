"""
tests/unit/test_finance_transaction_links.py - Testes de Vínculo de Notas Fiscais e Comprovantes em Movimentações Bancárias
"""

import uuid
from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy.orm import Session

from controlb.db import SessionLocal
from controlb.modules.identity import models as id_models
from controlb.modules.finance import service, schemas, models


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def current_org(db: Session):
    org = db.query(id_models.Organization).first()
    if not org:
        org = id_models.Organization(name="Empresa Teste Financeiro")
        db.add(org)
        db.commit()
        db.refresh(org)
    return org


@pytest.fixture
def current_user(db: Session, current_org):
    user = db.query(id_models.User).filter(id_models.User.organization_id == current_org.id).first()
    if not user:
        user = id_models.User(
            organization_id=current_org.id,
            email=f"finance_test_{uuid.uuid4().hex[:6]}@controlb.com",
            full_name="Gestor Financeiro",
            hashed_password="fake_hash_password",
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def test_link_existing_and_new_fiscal_document_to_transaction(db: Session, current_org, current_user):
    # 1. Cria conta bancária
    bank = service.create_bank_account(
        db,
        current_org.id,
        schemas.BankAccountCreate(
            bank_name=f"Banco Teste NF {uuid.uuid4().hex[:4]}",
            account_type="CHECKING",
            opening_balance=Decimal("5000.00")
        )
    )

    # 2. Cria movimentação de entrada (CREDIT)
    tx = service.create_bank_transaction(
        db,
        current_org.id,
        schemas.BankTransactionCreate(
            bank_account_id=bank.id,
            transaction_date=date.today(),
            description="Recebimento de Cliente via PIX",
            amount=Decimal("1500.00"),
            transaction_type="CREDIT",
            document_number="PIX-12345"
        )
    )
    assert tx.fiscal_document_id is None

    # 3. Cria um Documento Fiscal existente
    fiscal = service.create_fiscal_document(
        db,
        current_org.id,
        current_user,
        schemas.FiscalDocumentCreate(
            direction="INBOUND",
            document_type="NFE",
            document_number=f"NF-{uuid.uuid4().hex[:6]}",
            issuer_name="Distribuidora Farma Teste",
            issue_date=date.today(),
            total_amount=Decimal("1500.00")
        )
    )

    # 4. Vincula a NF existente à transação bancária
    linked_tx = service.link_fiscal_document_to_transaction(
        db,
        current_org.id,
        tx.id,
        current_user,
        schemas.BankTransactionLinkFiscalRequest(fiscal_document_id=fiscal.id)
    )
    assert linked_tx.fiscal_document_id == fiscal.id

    # 5. Desvincula a NF
    unlinked_tx = service.unlink_fiscal_document_from_transaction(
        db,
        current_org.id,
        tx.id
    )
    assert unlinked_tx.fiscal_document_id is None

    # 6. Cadastra e vincula uma nova NF na hora
    new_doc_payload = schemas.FiscalDocumentCreate(
        direction="OUTBOUND",
        document_type="NFSE",
        document_number=f"NFS-{uuid.uuid4().hex[:6]}",
        issuer_name="Nossa Empresa",
        recipient_name="Cliente Final",
        issue_date=date.today(),
        total_amount=Decimal("1500.00")
    )
    linked_new_tx = service.link_fiscal_document_to_transaction(
        db,
        current_org.id,
        tx.id,
        current_user,
        schemas.BankTransactionLinkFiscalRequest(new_fiscal_document=new_doc_payload)
    )
    assert linked_new_tx.fiscal_document_id is not None
    assert linked_new_tx.fiscal_document.document_number == new_doc_payload.document_number


def test_attach_and_remove_receipt_from_transaction(db: Session, current_org, current_user):
    # 1. Cria conta bancária
    bank = service.create_bank_account(
        db,
        current_org.id,
        schemas.BankAccountCreate(
            bank_name=f"Banco Teste Comprovante {uuid.uuid4().hex[:4]}",
            account_type="CHECKING",
            opening_balance=Decimal("10000.00")
        )
    )

    # 2. Cria movimentação de saída (DEBIT)
    tx = service.create_bank_transaction(
        db,
        current_org.id,
        schemas.BankTransactionCreate(
            bank_account_id=bank.id,
            transaction_date=date.today(),
            description="Pagamento de Energia Copel",
            amount=Decimal("450.00"),
            transaction_type="DEBIT",
            document_number="DEB-9988"
        )
    )
    assert tx.receipt_url is None

    # 3. Anexa comprovante de pagamento
    attached_tx = service.attach_receipt_to_transaction(
        db,
        current_org.id,
        tx.id,
        current_user,
        schemas.BankTransactionAttachReceiptRequest(
            file_name="comprovante_copel_agosto.pdf",
            file_url="https://storage.controlb.com/receipts/copel_aug.pdf",
            mime_type="application/pdf"
        )
    )
    assert attached_tx.receipt_filename == "comprovante_copel_agosto.pdf"
    assert attached_tx.receipt_url == "https://storage.controlb.com/receipts/copel_aug.pdf"

    # 4. Remove comprovante
    removed_tx = service.remove_receipt_from_transaction(
        db,
        current_org.id,
        tx.id
    )
    assert removed_tx.receipt_url is None
    assert removed_tx.receipt_filename is None
