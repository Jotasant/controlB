"""
modules/finance/models.py - Modelos ORM do Módulo de Gestão Financeira e Faturamento (Finance & Billing Domain)

Princípio Fundamental:
- Compra ≠ Nota Fiscal ≠ Conta a Pagar ≠ Boleto/PIX ≠ Pagamento ≠ Movimentação Bancária
- Venda ≠ Faturamento ≠ Conta a Receber ≠ Recebimento ≠ Movimentação Bancária
"""

import uuid
from datetime import datetime, timezone, date
from decimal import Decimal
from sqlalchemy import (
    String, Text, Boolean, DateTime, Date, Numeric, ForeignKey, ForeignKeyConstraint,
    Index, Integer, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from controlb.db import Base
from controlb.modules.documents.models import BusinessDocument


def utcnow() -> datetime:
    """Helper para timestamps com fuso horário UTC consistente."""
    return datetime.now(timezone.utc)


# ==============================================================================
# 1. CADASTROS FINANCEIROS & CLASSIFICAÇÃO
# ==============================================================================

class FinancialCategory(Base):
    """
    Tabela 'financial_category' - Plano de Contas / Categorias Financeiras.
    Exemplos: Medicamentos, Energia, Aluguel, Folha de Pagamento, Vendas PDV.
    """
    __tablename__ = "financial_category"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)  # ex: "1.01.01"
    category_type: Mapped[str] = mapped_column(String(50), nullable=False, default="EXPENSE")  # EXPENSE ou REVENUE
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamentos
    payables: Mapped[list["Payable"]] = relationship(back_populates="financial_category")
    receivables: Mapped[list["Receivable"]] = relationship(back_populates="financial_category")


class BankAccount(Base):
    """
    Tabela 'bank_account' - Contas Correntes, Poupança, Caixa Físico e Carteiras Digitais.
    """
    __tablename__ = "bank_account"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    
    bank_name: Mapped[str] = mapped_column(String(150), nullable=False)  # ex: "Banco do Brasil", "Itaú", "Caixa Geral"
    bank_code: Mapped[str | None] = mapped_column(String(20), nullable=True)  # ex: "001", "341"
    agency: Mapped[str | None] = mapped_column(String(50), nullable=True)
    account_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    account_type: Mapped[str] = mapped_column(String(50), nullable=False, default="CHECKING")  # CHECKING, SAVINGS, CASH, DIGITAL_WALLET
    
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    current_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamentos
    transactions: Mapped[list["BankTransaction"]] = relationship(back_populates="bank_account", cascade="all, delete-orphan")
    payments: Mapped[list["Payment"]] = relationship(back_populates="bank_account")
    receipts: Mapped[list["Receipt"]] = relationship(back_populates="bank_account")


# ==============================================================================
# 2. DOCUMENTOS FISCAIS (FiscalDocument)
# ==============================================================================

class FiscalDocument(Base):
    """
    Tabela 'fiscal_document' - Registro de Documentos Fiscais emitidos ou recebidos (NF-e, NFS-e, NFC-e, CT-e).
    """
    __tablename__ = "fiscal_document"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["business_document.id", "business_document.organization_id"],
            name="fk_fiscal_document_document_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["purchase_order_id", "organization_id"],
            ["purchase_order.id", "purchase_order.organization_id"],
            name="fk_fiscal_document_purchase_order_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("document_id", name="uq_fiscal_document_document"),
        UniqueConstraint("id", "organization_id", name="uq_fiscal_document_id_org"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    
    direction: Mapped[str] = mapped_column(String(20), nullable=False, default="INBOUND")  # INBOUND (Entrada) ou OUTBOUND (Saída)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False, default="NFE")  # NFE, NFSE, NFCE, CTE, OUTRO
    document_number: Mapped[str] = mapped_column(String(100), nullable=False)
    series: Mapped[str | None] = mapped_column(String(20), nullable=True)
    access_key: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)  # Chave de 44 dígitos
    
    issuer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    issuer_cnpj_cpf: Mapped[str | None] = mapped_column(String(30), nullable=True)
    recipient_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recipient_cnpj_cpf: Mapped[str | None] = mapped_column(String(30), nullable=True)
    
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    
    purchase_order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("supplier.id", ondelete="SET NULL"), nullable=True)
    
    file_attachment: Mapped[str | None] = mapped_column(Text, nullable=True)  # Arquivo XML/PDF em base64 ou URL
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="authorized")  # authorized, cancelled, draft
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamentos
    document: Mapped["BusinessDocument"] = relationship(lazy="select")
    payables: Mapped[list["Payable"]] = relationship(
        back_populates="fiscal_document", overlaps="document"
    )
    receivables: Mapped[list["Receivable"]] = relationship(back_populates="fiscal_document")


# ==============================================================================
# 3. CONTAS A PAGAR (Payable), INSTRUMENTOS E PAGAMENTOS
# ==============================================================================

class Payable(Base):
    """
    Tabela 'payable' - Obrigações Financeiras / Contas a Pagar.
    Suporta compras formais (com purchase_order_id) e despesas avulsas (purchase_order_id=NULL).
    """
    __tablename__ = "payable"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["business_document.id", "business_document.organization_id"],
            name="fk_payable_document_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["purchase_order_id", "organization_id"],
            ["purchase_order.id", "purchase_order.organization_id"],
            name="fk_payable_purchase_order_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["fiscal_document_id", "organization_id"],
            ["fiscal_document.id", "fiscal_document.organization_id"],
            name="fk_payable_fiscal_document_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["inventory_receipt_id", "organization_id"],
            ["inventory_receipt.id", "inventory_receipt.organization_id"],
            name="fk_payable_inventory_receipt_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("document_id", name="uq_payable_document"),
        UniqueConstraint(
            "organization_id", "payable_number", name="uq_payable_org_number"
        ),
        UniqueConstraint("id", "organization_id", name="uq_payable_id_org"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    payable_number: Mapped[str] = mapped_column(String(100), nullable=False)
    
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("supplier.id", ondelete="SET NULL"), nullable=True)
    purchase_order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    fiscal_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    inventory_receipt_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    cost_center_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cost_center.id", ondelete="SET NULL"), nullable=True)
    financial_category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("financial_category.id", ondelete="SET NULL"), nullable=True)
    
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    favored_name: Mapped[str] = mapped_column(String(255), nullable=False)  # Razão Social / Favorecido
    
    original_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    outstanding_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)  # Saldo a pagar
    
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    # Dimensões independentes da obrigação. OPEX/CAPEX não define quem
    # recebe nem qual processo de negócio originou o título.
    expense_nature: Mapped[str] = mapped_column(String(30), nullable=False, default="OPEX")
    obligation_type: Mapped[str] = mapped_column(String(40), nullable=False, default="OTHER")
    business_origin: Mapped[str] = mapped_column(String(40), nullable=False, default="MANUAL")
    payment_method_expected: Mapped[str | None] = mapped_column(String(50), nullable=True)  # BOLETO, PIX, TRANSFERENCIA, CARTAO
    
    installment_number: Mapped[int] = mapped_column(Integer, default=1)
    total_installments: Mapped[int] = mapped_column(Integer, default=1)
    
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_APPROVAL", index=True)
    # Status: DRAFT, PENDING_APPROVAL, APPROVED, SCHEDULED, PARTIALLY_PAID, PAID, OVERDUE, CANCELLED, RECONCILED
    
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamentos
    document: Mapped["BusinessDocument"] = relationship(
        lazy="select", overlaps="fiscal_document,payables"
    )
    financial_category: Mapped["FinancialCategory | None"] = relationship(back_populates="payables", lazy="selectin")
    fiscal_document: Mapped["FiscalDocument | None"] = relationship(
        back_populates="payables", lazy="selectin", overlaps="document"
    )
    instruments: Mapped[list["PaymentInstrument"]] = relationship(back_populates="payable", cascade="all, delete-orphan", lazy="selectin")
    payments: Mapped[list["Payment"]] = relationship(back_populates="payable", cascade="all, delete-orphan", lazy="selectin")


class PaymentInstrument(Base):
    """
    Tabela 'payment_instrument' - Meios e Dados de Cobrança vinculados a uma conta a pagar (Boleto, PIX, etc).
    """
    __tablename__ = "payment_instrument"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payable_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payable.id", ondelete="CASCADE"), nullable=False)
    
    instrument_type: Mapped[str] = mapped_column(String(50), nullable=False, default="BOLETO")  # BOLETO, PIX, BANK_TRANSFER, DEBIT, OTHER
    barcode: Mapped[str | None] = mapped_column(String(100), nullable=True)
    digitable_line: Mapped[str | None] = mapped_column(String(150), nullable=True)
    pix_code: Mapped[str | None] = mapped_column(Text, nullable=True)  # Chave ou copia e cola
    document_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    file_attachment: Mapped[str | None] = mapped_column(Text, nullable=True)  # PDF do boleto
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relacionamento
    payable: Mapped["Payable"] = relationship(back_populates="instruments")


class Payment(Base):
    """
    Tabela 'payment' - Baixa e Pagamento efetivamente realizado contra um Payable.
    """
    __tablename__ = "payment"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    payable_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payable.id", ondelete="CASCADE"), nullable=False)
    bank_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bank_account.id", ondelete="SET NULL"), nullable=True)
    
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    interest_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False, default="PIX")  # PIX, BOLETO, TRANSFERENCIA, DEBITO, DINHEIRO
    
    reference: Mapped[str | None] = mapped_column(String(200), nullable=True)  # ex: Autenticação bancária
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relacionamentos
    payable: Mapped["Payable"] = relationship(back_populates="payments")
    bank_account: Mapped["BankAccount | None"] = relationship(back_populates="payments", lazy="selectin")
    attachments: Mapped[list["PaymentAttachment"]] = relationship(back_populates="payment", cascade="all, delete-orphan", lazy="selectin")
    reconciliation: Mapped["Reconciliation | None"] = relationship(back_populates="payment")


class PaymentAttachment(Base):
    """
    Tabela 'payment_attachment' - Comprovantes bancários de pagamento anexados.
    """
    __tablename__ = "payment_attachment"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payment.id", ondelete="CASCADE"), nullable=False)
    
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_url: Mapped[str] = mapped_column(Text, nullable=False)  # Base64 ou URL
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relacionamento
    payment: Mapped["Payment"] = relationship(back_populates="attachments")


# ==============================================================================
# 4. TESOURARIA, EXTRATOS BANCÁRIOS & CONCILIAÇÃO
# ==============================================================================

class BankTransaction(Base):
    """
    Tabela 'bank_transaction' - Registro de Extrato Bancário Real (Créditos e Débitos).
    """
    __tablename__ = "bank_transaction"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    bank_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_account.id", ondelete="CASCADE"), nullable=False)
    
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)  # Positivo
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)  # CREDIT (Entrada) ou DEBIT (Saída)
    
    external_id: Mapped[str | None] = mapped_column(String(100), nullable=True)  # ID do OFX/Open Finance
    document_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    balance_after: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    
    fiscal_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("fiscal_document.id", ondelete="SET NULL"), nullable=True)
    payment_attachment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("payment_attachment.id", ondelete="SET NULL"), nullable=True)
    receipt_url: Mapped[str | None] = mapped_column(Text, nullable=True)  # Anexo direto / Comprovante
    receipt_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, reconciled, ignored
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relacionamento
    bank_account: Mapped["BankAccount"] = relationship(back_populates="transactions", lazy="selectin")
    fiscal_document: Mapped["FiscalDocument | None"] = relationship(lazy="selectin")
    payment_attachment: Mapped["PaymentAttachment | None"] = relationship(lazy="selectin")
    reconciliation: Mapped["Reconciliation | None"] = relationship(back_populates="bank_transaction")


class Reconciliation(Base):
    """
    Tabela 'reconciliation' - Vínculo de Conciliação entre uma BankTransaction e um Payment/Receipt.
    """
    __tablename__ = "reconciliation"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    
    bank_transaction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_transaction.id", ondelete="CASCADE"), nullable=False, unique=True)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("payment.id", ondelete="SET NULL"), nullable=True)
    receipt_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("receipt.id", ondelete="SET NULL"), nullable=True)
    
    reconciled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reconciled_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="reconciled")  # reconciled, manually_adjusted
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relacionamentos
    bank_transaction: Mapped["BankTransaction"] = relationship(back_populates="reconciliation", lazy="selectin")
    payment: Mapped["Payment | None"] = relationship(back_populates="reconciliation", lazy="selectin")
    receipt: Mapped["Receipt | None"] = relationship(back_populates="reconciliation", lazy="selectin")


# ==============================================================================
# 5. CONTAS A RECEBER (Receivable) & RECEBIMENTOS (Receipt)
# ==============================================================================

class Receivable(Base):
    """
    Tabela 'receivable' - Títulos e Valores a Receber (Vendas, Convênios, Faturas).
    """
    __tablename__ = "receivable"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["business_document.id", "business_document.organization_id"],
            name="fk_receivable_document_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["fiscal_document_id", "organization_id"],
            ["fiscal_document.id", "fiscal_document.organization_id"],
            name="fk_receivable_fiscal_document_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("document_id", name="uq_receivable_document"),
        UniqueConstraint(
            "organization_id", "receivable_number", name="uq_receivable_org_number"
        ),
        UniqueConstraint("id", "organization_id", name="uq_receivable_id_org"),
        UniqueConstraint(
            "invoice_installment_id", name="uq_receivable_invoice_installment"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    receivable_number: Mapped[str] = mapped_column(String(100), nullable=False)
    
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("customer.id", ondelete="SET NULL"), nullable=True)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_document: Mapped[str | None] = mapped_column(String(30), nullable=True)
    
    fiscal_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    invoice_installment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "invoice_installment.id",
            name="fk_receivable_invoice_installment",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    cost_center_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cost_center.id", ondelete="SET NULL"), nullable=True)
    financial_category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("financial_category.id", ondelete="SET NULL"), nullable=True)
    
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    original_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    outstanding_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    payment_method_expected: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="PENDING", index=True)  # PENDING, PARTIALLY_RECEIVED, RECEIVED, OVERDUE, CANCELLED
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relacionamentos
    document: Mapped["BusinessDocument"] = relationship(
        lazy="select", overlaps="fiscal_document,receivables"
    )
    financial_category: Mapped["FinancialCategory | None"] = relationship(back_populates="receivables", lazy="selectin")
    fiscal_document: Mapped["FiscalDocument | None"] = relationship(back_populates="receivables", lazy="selectin")
    receipts: Mapped[list["Receipt"]] = relationship(back_populates="receivable", cascade="all, delete-orphan", lazy="selectin")


class Receipt(Base):
    """
    Tabela 'receipt' - Entrada financeira efetivamente recebida.
    """
    __tablename__ = "receipt"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    receivable_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("receivable.id", ondelete="CASCADE"), nullable=False)
    bank_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bank_account.id", ondelete="SET NULL"), nullable=True)
    
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    receipt_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False, default="PIX")
    
    reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    received_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relacionamentos
    receivable: Mapped["Receivable"] = relationship(back_populates="receipts")
    bank_account: Mapped["BankAccount | None"] = relationship(back_populates="receipts", lazy="selectin")
    reconciliation: Mapped["Reconciliation | None"] = relationship(back_populates="receipt")


# ==============================================================================
# 6. FATURAMENTO, PDV & FECHAMENTO DE VENDAS
# ==============================================================================

class SalesReport(Base):
    """
    Tabela 'sales_report' - Fechamento Diário de Vendas e PDV.
    """
    __tablename__ = "sales_report"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    
    report_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    gross_sales: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    discounts: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    returns: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    net_sales: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    
    cash_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    pix_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    debit_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    credit_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    other_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    
    source: Mapped[str] = mapped_column(String(100), default="PDV Balcão")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
