"""
modules/finance/schemas.py - Schemas Pydantic para Validação e Serialização da Gestão Financeira e Faturamento
"""

import uuid
from datetime import datetime, date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, field_validator


PAYABLE_ACCOUNTING_NATURES = {
    "OPEX", "CAPEX", "FINANCIAL", "TAX", "PAYROLL", "TRANSFER", "NOT_APPLICABLE"
}
PAYABLE_OBLIGATION_TYPES = {
    "GOODS_SUPPLIER", "SERVICE_PROVIDER", "TAX", "PAYROLL", "RENT_LEASE",
    "FINANCING", "REIMBURSEMENT", "INVESTMENT", "OTHER"
}
PAYABLE_BUSINESS_ORIGINS = {
    "PURCHASE", "REPLENISHMENT", "INVESTMENT", "CONTRACT",
    "FISCAL_DOCUMENT", "MANUAL", "OTHER"
}


def _normalize_payable_classification(
    value: str | None,
    allowed: set[str],
    label: str,
) -> str | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    if normalized not in allowed:
        choices = ", ".join(sorted(allowed))
        raise ValueError(f"{label} inválida. Valores aceitos: {choices}.")
    return normalized


# ==============================================================================
# 1. CATEGORIAS FINANCEIRAS
# ==============================================================================

class FinancialCategoryBase(BaseModel):
    name: str = Field(..., max_length=200, description="Nome da categoria (ex: Medicamentos, Aluguel, Energia)")
    code: str | None = Field(None, max_length=50, description="Código contábil/estruturado (ex: 1.01.01)")
    category_type: str = Field("EXPENSE", description="EXPENSE (Despesa) ou REVENUE (Receita)")
    description: str | None = None
    is_active: bool = True


class FinancialCategoryCreate(FinancialCategoryBase):
    pass


class FinancialCategoryUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    category_type: str | None = None
    description: str | None = None
    is_active: bool | None = None


class FinancialCategoryResponse(FinancialCategoryBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 2. CONTAS BANCÁRIAS / CAIXA
# ==============================================================================

class BankAccountBase(BaseModel):
    bank_name: str = Field(..., max_length=150, description="Nome da instituição (ex: Banco do Brasil, Caixa Geral)")
    bank_code: str | None = Field(None, max_length=20, description="Código COMPE (ex: 001)")
    agency: str | None = Field(None, max_length=50)
    account_number: str | None = Field(None, max_length=50)
    account_type: str = Field("CHECKING", description="CHECKING, SAVINGS, CASH, DIGITAL_WALLET")
    opening_balance: Decimal = Field(default=Decimal("0.00"), description="Saldo inicial de implantação")
    current_balance: Decimal = Field(default=Decimal("0.00"), description="Saldo atual disponível")
    is_active: bool = True


class BankAccountCreate(BankAccountBase):
    pass


class BankAccountUpdate(BaseModel):
    bank_name: str | None = None
    bank_code: str | None = None
    agency: str | None = None
    account_number: str | None = None
    account_type: str | None = None
    current_balance: Decimal | None = None
    is_active: bool | None = None


class BankAccountResponse(BankAccountBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 3. DOCUMENTOS FISCAIS (FiscalDocument)
# ==============================================================================

class FiscalDocumentBase(BaseModel):
    direction: str = Field("INBOUND", description="INBOUND (Entrada) ou OUTBOUND (Saída)")
    document_type: str = Field("NFE", description="NFE, NFSE, NFCE, CTE, OUTRO")
    document_number: str = Field(..., max_length=100)
    series: str | None = None
    access_key: str | None = None
    issuer_name: str = Field(..., max_length=255)
    issuer_cnpj_cpf: str | None = None
    recipient_name: str | None = None
    recipient_cnpj_cpf: str | None = None
    issue_date: date
    total_amount: Decimal = Field(..., gt=0)
    tax_amount: Decimal = Field(default=Decimal("0.00"))
    purchase_order_id: uuid.UUID | None = None
    supplier_id: uuid.UUID | None = None
    file_attachment: str | None = None
    notes: str | None = None
    status: str = "authorized"


class FiscalDocumentCreate(FiscalDocumentBase):
    pass


class FiscalDocumentUpdate(BaseModel):
    direction: str | None = None
    document_type: str | None = None
    document_number: str | None = Field(None, max_length=100)
    series: str | None = None
    access_key: str | None = None
    issuer_name: str | None = Field(None, max_length=255)
    issuer_cnpj_cpf: str | None = None
    recipient_name: str | None = None
    recipient_cnpj_cpf: str | None = None
    issue_date: date | None = None
    total_amount: Decimal | None = Field(None, gt=0)
    tax_amount: Decimal | None = Field(None, ge=0)
    file_attachment: str | None = None
    notes: str | None = None
    status: str | None = None


class FiscalDocumentResponse(FiscalDocumentBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    document_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 4. CONTAS A PAGAR (Payable) & INSTRUMENTOS
# ==============================================================================

class PaymentInstrumentCreate(BaseModel):
    instrument_type: str = Field("BOLETO", description="BOLETO, PIX, BANK_TRANSFER, DEBIT, OTHER")
    barcode: str | None = None
    digitable_line: str | None = None
    pix_code: str | None = None
    document_number: str | None = None
    due_date: date | None = None
    amount: Decimal | None = None
    file_attachment: str | None = None


class PaymentInstrumentUpdate(BaseModel):
    instrument_type: str | None = None
    barcode: str | None = None
    digitable_line: str | None = None
    pix_code: str | None = None
    document_number: str | None = None
    due_date: date | None = None
    amount: Decimal | None = None
    file_attachment: str | None = None


class PaymentInstrumentResponse(PaymentInstrumentCreate):
    id: uuid.UUID
    payable_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PayableBase(BaseModel):
    supplier_id: uuid.UUID | None = None
    purchase_order_id: uuid.UUID | None = None
    fiscal_document_id: uuid.UUID | None = None
    inventory_receipt_id: uuid.UUID | None = None
    cost_center_id: uuid.UUID | None = None
    financial_category_id: uuid.UUID | None = None
    description: str = Field(..., max_length=500)
    favored_name: str = Field(..., max_length=255)
    original_amount: Decimal = Field(..., gt=0)
    issue_date: date
    due_date: date
    expense_nature: str = Field(
        "NOT_APPLICABLE",
        description="Natureza contábil: OPEX, CAPEX, FINANCIAL, TAX, PAYROLL, TRANSFER ou NOT_APPLICABLE",
    )
    obligation_type: str = Field(
        "OTHER",
        description="Tipo da obrigação: fornecedor, prestador, tributo, folha, aluguel, financiamento etc.",
    )
    business_origin: str = Field(
        "MANUAL",
        description="Origem do negócio: compra, reposição, investimento, contrato, documento fiscal ou manual.",
    )
    payment_method_expected: str | None = Field("BOLETO", description="BOLETO, PIX, TRANSFERENCIA, CARTAO")
    installment_number: int = 1
    total_installments: int = 1
    notes: str | None = None

    @field_validator("expense_nature")
    @classmethod
    def validate_expense_nature(cls, value: str) -> str:
        return _normalize_payable_classification(
            value, PAYABLE_ACCOUNTING_NATURES, "Natureza contábil"
        ) or "NOT_APPLICABLE"

    @field_validator("obligation_type")
    @classmethod
    def validate_obligation_type(cls, value: str) -> str:
        return _normalize_payable_classification(
            value, PAYABLE_OBLIGATION_TYPES, "Tipo de obrigação"
        ) or "OTHER"

    @field_validator("business_origin")
    @classmethod
    def validate_business_origin(cls, value: str) -> str:
        return _normalize_payable_classification(
            value, PAYABLE_BUSINESS_ORIGINS, "Origem de negócio"
        ) or "MANUAL"


class PayableCreate(PayableBase):
    # Opcional: já cadastrar meio de pagamento (boleto/PIX), parcelas e nota fiscal anexada
    instrument: PaymentInstrumentCreate | None = None
    instruments: list[PaymentInstrumentCreate] | None = None
    new_fiscal_document: FiscalDocumentCreate | None = None
    installments_count: int | None = Field(default=1, ge=1, le=48, description="Gerar parcelas automáticas")
    installment_frequency_days: int | None = Field(default=30, description="Dias entre parcelas")


class PayableUpdate(BaseModel):
    supplier_id: uuid.UUID | None = None
    inventory_receipt_id: uuid.UUID | None = None
    description: str | None = None
    favored_name: str | None = None
    cost_center_id: uuid.UUID | None = None
    financial_category_id: uuid.UUID | None = None
    original_amount: Decimal | None = Field(None, gt=0)
    issue_date: date | None = None
    expense_nature: str | None = None
    obligation_type: str | None = None
    business_origin: str | None = None
    due_date: date | None = None
    payment_method_expected: str | None = None
    status: str | None = None
    notes: str | None = None

    @field_validator("expense_nature")
    @classmethod
    def validate_expense_nature(cls, value: str | None) -> str | None:
        return _normalize_payable_classification(
            value, PAYABLE_ACCOUNTING_NATURES, "Natureza contábil"
        )

    @field_validator("obligation_type")
    @classmethod
    def validate_obligation_type(cls, value: str | None) -> str | None:
        return _normalize_payable_classification(
            value, PAYABLE_OBLIGATION_TYPES, "Tipo de obrigação"
        )

    @field_validator("business_origin")
    @classmethod
    def validate_business_origin(cls, value: str | None) -> str | None:
        return _normalize_payable_classification(
            value, PAYABLE_BUSINESS_ORIGINS, "Origem de negócio"
        )


class PaymentAttachmentCreate(BaseModel):
    file_name: str
    file_url: str
    mime_type: str | None = None


class PaymentAttachmentResponse(PaymentAttachmentCreate):
    id: uuid.UUID
    payment_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaymentCreate(BaseModel):
    amount: Decimal = Field(..., gt=0)
    discount_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    interest_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    payment_date: date
    payment_method: str = Field("PIX", description="PIX, BOLETO, TRANSFERENCIA, DEBITO, DINHEIRO")
    bank_account_id: uuid.UUID | None = None
    reference: str | None = None
    notes: str | None = None
    attachments: list[PaymentAttachmentCreate] = []


class PaymentResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    payable_id: uuid.UUID
    bank_account_id: uuid.UUID | None = None
    amount: Decimal
    discount_amount: Decimal
    interest_amount: Decimal
    payment_date: date
    payment_method: str
    reference: str | None = None
    notes: str | None = None
    created_at: datetime
    attachments: list[PaymentAttachmentResponse] = []

    model_config = ConfigDict(from_attributes=True)


class PayableResponse(PayableBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    document_id: uuid.UUID
    payable_number: str
    outstanding_amount: Decimal
    status: str
    created_at: datetime
    updated_at: datetime
    financial_category: FinancialCategoryResponse | None = None
    fiscal_document: FiscalDocumentResponse | None = None
    instruments: list[PaymentInstrumentResponse] = []
    payments: list[PaymentResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 5. TESOURARIA & CONCILIAÇÃO
# ==============================================================================

class BankTransactionBase(BaseModel):
    bank_account_id: uuid.UUID
    transaction_date: date
    description: str = Field(..., max_length=500)
    amount: Decimal = Field(..., gt=0)
    transaction_type: str = Field(..., description="CREDIT (Entrada) ou DEBIT (Saída)")
    external_id: str | None = None
    document_number: str | None = None
    balance_after: Decimal | None = None
    fiscal_document_id: uuid.UUID | None = None
    payment_attachment_id: uuid.UUID | None = None
    receipt_url: str | None = None
    receipt_filename: str | None = None
    status: str = "pending"


class BankTransactionCreate(BankTransactionBase):
    pass


class BankTransactionUpdate(BaseModel):
    bank_account_id: uuid.UUID | None = None
    transaction_date: date | None = None
    description: str | None = Field(None, min_length=1, max_length=500)
    amount: Decimal | None = Field(None, gt=0)
    transaction_type: str | None = None
    external_id: str | None = None
    document_number: str | None = None
    fiscal_document_id: uuid.UUID | None = None
    receipt_url: str | None = None
    receipt_filename: str | None = None


class BankTransactionLinkFiscalRequest(BaseModel):
    fiscal_document_id: uuid.UUID | None = None
    new_fiscal_document: FiscalDocumentCreate | None = None


class BankTransactionAttachReceiptRequest(BaseModel):
    file_name: str
    file_url: str
    mime_type: str | None = None
    payable_id: uuid.UUID | None = None


class ReconciliationCreate(BaseModel):
    bank_transaction_id: uuid.UUID
    payment_id: uuid.UUID | None = None
    receipt_id: uuid.UUID | None = None
    notes: str | None = None


class ReconciliationResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    bank_transaction_id: uuid.UUID
    payment_id: uuid.UUID | None = None
    receipt_id: uuid.UUID | None = None
    reconciled_at: datetime
    status: str
    notes: str | None = None

    model_config = ConfigDict(from_attributes=True)


class BankTransactionResponse(BankTransactionBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    created_at: datetime
    fiscal_document: FiscalDocumentResponse | None = None
    payment_attachment: PaymentAttachmentResponse | None = None
    reconciliation: ReconciliationResponse | None = None

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 6. CONTAS A RECEBER (Receivable) & RECEBIMENTOS (Receipt)
# ==============================================================================

class ReceivableBase(BaseModel):
    customer_id: uuid.UUID | None = None
    customer_name: str = Field(..., max_length=255)
    customer_document: str | None = None
    fiscal_document_id: uuid.UUID | None = None
    cost_center_id: uuid.UUID | None = None
    financial_category_id: uuid.UUID | None = None
    description: str = Field(..., max_length=500)
    original_amount: Decimal = Field(..., gt=0)
    issue_date: date
    due_date: date
    payment_method_expected: str | None = "PIX"
    notes: str | None = None


class ReceivableCreate(ReceivableBase):
    pass


class ReceivableUpdate(BaseModel):
    customer_id: uuid.UUID | None = None
    customer_name: str | None = Field(None, max_length=255)
    customer_document: str | None = None
    cost_center_id: uuid.UUID | None = None
    financial_category_id: uuid.UUID | None = None
    description: str | None = Field(None, max_length=500)
    original_amount: Decimal | None = Field(None, gt=0)
    issue_date: date | None = None
    due_date: date | None = None
    payment_method_expected: str | None = None
    status: str | None = None
    notes: str | None = None


class ReceiptCreate(BaseModel):
    amount: Decimal = Field(..., gt=0)
    receipt_date: date
    payment_method: str = "PIX"
    bank_account_id: uuid.UUID | None = None
    reference: str | None = None
    notes: str | None = None


class ReceiptResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    receivable_id: uuid.UUID
    bank_account_id: uuid.UUID | None = None
    amount: Decimal
    receipt_date: date
    payment_method: str
    reference: str | None = None
    notes: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReceivableResponse(ReceivableBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    document_id: uuid.UUID
    receivable_number: str
    invoice_installment_id: uuid.UUID | None = None
    outstanding_amount: Decimal
    status: str
    created_at: datetime
    updated_at: datetime
    financial_category: FinancialCategoryResponse | None = None
    receipts: list[ReceiptResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 7. FATURAMENTO & RELATÓRIOS DE VENDAS DO PDV
# ==============================================================================

class SalesReportBase(BaseModel):
    report_date: date
    gross_sales: Decimal = Field(..., ge=0)
    discounts: Decimal = Field(default=Decimal("0.00"), ge=0)
    returns: Decimal = Field(default=Decimal("0.00"), ge=0)
    net_sales: Decimal = Field(..., ge=0)
    cash_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    pix_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    debit_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    credit_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    other_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    source: str = "PDV Balcão"
    notes: str | None = None


class SalesReportCreate(SalesReportBase):
    generate_receivables: bool = Field(default=True, description="Gera títulos a receber automaticamente por forma de pagamento")


class SalesReportResponse(SalesReportBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 8. DASHBOARD & FLUXO DE CAIXA
# ==============================================================================

class FinanceDashboardSummary(BaseModel):
    total_available_balance: Decimal = Decimal("0.00")
    payables_today: Decimal = Decimal("0.00")
    payables_month: Decimal = Decimal("0.00")
    payables_overdue: Decimal = Decimal("0.00")
    receivables_today: Decimal = Decimal("0.00")
    receivables_month: Decimal = Decimal("0.00")
    receivables_overdue: Decimal = Decimal("0.00")
    projected_net_cashflow: Decimal = Decimal("0.00")
    capex_month: Decimal = Decimal("0.00")
    opex_month: Decimal = Decimal("0.00")
    unreconciled_transactions_count: int = 0
