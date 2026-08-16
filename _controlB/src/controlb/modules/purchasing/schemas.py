"""
modules/purchasing/schemas.py - Contratos de Dados e Validações Pydantic V2 (Purchasing)

Define os schemas para validação de entrada (Create/Update) e serialização de saída (Response) para:
1. Cadastros de Apoio: Fornecedores (Supplier), Centros de Custo (CostCenter), 
   Categorias (ProductCategory) e Produtos (Product).
2. Solicitações de Compra: PurchaseRequest, PurchaseRequestItem e Eventos de Aprovação (ApprovalEvent).
3. Ordens de Compra: PurchaseOrder e PurchaseOrderItem.
"""

import uuid
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ==============================================================================
# 1. ESQUEMAS DE FORNECEDORES (Supplier)
# ==============================================================================

class SupplierBase(BaseModel):
    """Atributos base do Fornecedor."""
    name: str = Field(..., min_length=2, max_length=500, description="Razão Social / Nome Oficial")
    trade_name: str | None = Field(None, max_length=500, description="Nome Fantasia")
    cnpj_cpf: str = Field(..., min_length=11, max_length=100, description="CNPJ ou CPF do Fornecedor")
    state_registration: str | None = Field(None, max_length=100, description="Inscrição Estadual")
    contact_name: str | None = Field(None, max_length=200, description="Nome do Vendedor / Representante")
    segments: str | None = Field(None, max_length=500, description="Categorias/Segmentos atendidos (ex: Medicamentos, Perfumaria)")
    payment_terms: str | None = Field(None, max_length=200, description="Condição de Pagamento Padrão (ex: 30 DDL)")
    min_order_amount: Decimal = Field(Decimal("0.00"), description="Valor Mínimo de Pedido (R$)")
    anvisa_license: str | None = Field(None, max_length=200, description="AFE Anvisa / Alvará Sanitário")
    notes: str | None = Field(None, description="Observações comerciais gerais")
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=100)
    address: str | None = Field(None, max_length=500)
    city: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=100)
    zip_code: str | None = Field(None, max_length=100)
    country: str | None = Field("BR", max_length=100)


class SupplierCreate(SupplierBase):
    """Payload para cadastro de um novo Fornecedor."""
    organization_id: uuid.UUID | None = None


class SupplierUpdate(BaseModel):
    """Payload para atualização parcial de um Fornecedor."""
    name: str | None = None
    trade_name: str | None = None
    cnpj_cpf: str | None = None
    state_registration: str | None = None
    contact_name: str | None = None
    segments: str | None = None
    payment_terms: str | None = None
    min_order_amount: Decimal | None = None
    anvisa_license: str | None = None
    notes: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    country: str | None = None
    is_active: bool | None = None


class SupplierResponse(SupplierBase):
    """Schema de resposta com dados do Fornecedor persistido."""
    id: uuid.UUID
    organization_id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 2. ESQUEMAS DE CENTROS DE CUSTO (CostCenter)
# ==============================================================================

class CostCenterBase(BaseModel):
    """Atributos base do Centro de Custo."""
    code: str = Field(..., min_length=1, max_length=100, description="Código contábil/operacional (ex: CC-001)")
    name: str = Field(..., min_length=2, max_length=500, description="Nome do Centro de Custo")
    description: str | None = None
    manager_id: uuid.UUID | None = None


class CostCenterCreate(CostCenterBase):
    """Payload para criação de Centro de Custo."""
    organization_id: uuid.UUID | None = None


class CostCenterUpdate(BaseModel):
    """Payload para atualização de Centro de Custo."""
    code: str | None = None
    name: str | None = None
    description: str | None = None
    manager_id: uuid.UUID | None = None
    is_active: bool | None = None


class CostCenterResponse(CostCenterBase):
    """Schema de resposta do Centro de Custo."""
    id: uuid.UUID
    organization_id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 3. ESQUEMAS DE CATEGORIAS DE PRODUTOS (ProductCategory)
# ==============================================================================

class ProductCategoryBase(BaseModel):
    """Atributos base da Categoria."""
    name: str = Field(..., min_length=2, max_length=500)
    code: str | None = Field(None, max_length=100)
    description: str | None = None


class ProductCategoryCreate(ProductCategoryBase):
    """Payload para cadastro de Categoria."""
    organization_id: uuid.UUID | None = None


class ProductCategoryUpdate(BaseModel):
    """Payload para edição de Categoria."""
    name: str | None = None
    code: str | None = None
    description: str | None = None
    is_active: bool | None = None


class ProductCategoryResponse(ProductCategoryBase):
    """Schema de resposta da Categoria."""
    id: uuid.UUID
    organization_id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 4. ESQUEMAS DE PRODUTOS & INSUMOS (Product)
# ==============================================================================

class ProductBase(BaseModel):
    """Atributos base do Produto."""
    sku: str | None = Field(None, max_length=100, description="Código SKU único interno (gerado automaticamente se omitido)")
    name: str = Field(..., min_length=2, max_length=500, description="Nome do Produto / Insumo")
    description: str | None = None
    unit_of_measure: str = Field("UN", max_length=50, description="Unidade de Medida (UN, KG, L, CX, M)")
    reference_price: Decimal = Field(default=Decimal("0.0000"), ge=0, description="Preço unitário base/referência")
    category_id: uuid.UUID | None = None

    # Rastreabilidade & Validade
    brand: str | None = None
    barcode: str | None = None
    ncm: str | None = None
    is_perishable: bool = False
    requires_batch: bool = False
    shelf_life_days: int | None = Field(None, ge=1, description="Prazo de validade padrão em dias")

    # Parâmetros de Estoque & Saldo Atual
    current_stock: Decimal = Field(default=Decimal("0.0000"), ge=0, description="Saldo físico atual em estoque")
    min_stock: Decimal = Field(default=Decimal("0.00"), ge=0, description="Estoque mínimo de segurança")
    max_stock: Decimal | None = Field(None, ge=0, description="Estoque máximo / Alvo de reposição")
    storage_location: str | None = None


class ProductCreate(ProductBase):
    """Payload para cadastro de Produto."""
    organization_id: uuid.UUID | None = None


class ProductUpdate(BaseModel):
    """Payload para edição de Produto."""
    sku: str | None = None
    name: str | None = None
    description: str | None = None
    unit_of_measure: str | None = None
    reference_price: Decimal | None = None
    category_id: uuid.UUID | None = None
    brand: str | None = None
    barcode: str | None = None
    ncm: str | None = None
    is_perishable: bool | None = None
    requires_batch: bool | None = None
    shelf_life_days: int | None = None
    current_stock: Decimal | None = None
    min_stock: Decimal | None = None
    max_stock: Decimal | None = None
    storage_location: str | None = None
    is_active: bool | None = None


class ProductResponse(ProductBase):
    """Schema de resposta do Produto."""
    id: uuid.UUID
    organization_id: uuid.UUID
    is_active: bool
    category: ProductCategoryResponse | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 5. ESQUEMAS DE ITENS DE SOLICITAÇÃO DE COMPRA (PurchaseRequestItem)
# ==============================================================================

class PurchaseRequestItemBase(BaseModel):
    """Atributos do item solicitado."""
    product_id: uuid.UUID
    quantity: Decimal = Field(..., gt=0, description="Quantidade requisitada")
    estimated_unit_price: Decimal = Field(default=Decimal("0.0000"), ge=0, description="Preço unitário estimado")
    notes: str | None = None


class PurchaseRequestItemCreate(PurchaseRequestItemBase):
    """Payload para criação de item da solicitação."""
    pass


class PurchaseRequestItemResponse(PurchaseRequestItemBase):
    """Schema de resposta da linha de item da solicitação."""
    id: uuid.UUID
    purchase_request_id: uuid.UUID
    total_estimated_price: Decimal
    product: ProductResponse | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class PurchaseRequstItemUpdate(BaseModel):
    """Payload para edição de item da solicitação."""
    product_id: uuid.UUID | None = None
    quantity: Decimal | None = Field(None, gt=0, description="Quantidade requisitada")
    estimated_unit_price: Decimal | None = Field(None, ge=0, description="Preço unitário estimado")
    notes: str | None = None
    is_active: bool | None = None



# ==============================================================================
# 6. ESQUEMAS DE EVENTO DE APROVAÇÃO (ApprovalEvent)
# ==============================================================================

class ApprovalEventResponse(BaseModel):
    """Schema de resposta do evento de aprovação / rejeição."""
    id: uuid.UUID
    purchase_request_id: uuid.UUID
    approver_id: uuid.UUID
    action: str  # approved, rejected
    comments: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApprovalActionRequest(BaseModel):
    """Payload enviado pelo aprovador para decidir sobre uma solicitação."""
    action: str = Field(..., pattern="^(approved|rejected)$", description="'approved' ou 'rejected'")
    comments: str | None = Field(None, description="Justificativa ou parecer do aprovador")


# ==============================================================================
# 7. ESQUEMAS DE SOLICITAÇÃO DE COMPRA (PurchaseRequest)
# ==============================================================================

class PurchaseRequestBase(BaseModel):
    """Atributos centrais da Solicitação de Compra."""
    cost_center_id: uuid.UUID | None = None
    justification: str = Field(..., min_length=1, description="Motivo / justificativa da aquisição")
    required_date: datetime | str | None = None


class PurchaseRequestCreate(PurchaseRequestBase):
    """Payload para emissão de nova Solicitação de Compra com seus itens."""
    organization_id: uuid.UUID | None = None
    items: list[PurchaseRequestItemCreate] = Field(..., min_length=1, description="Lista de itens solicitados")


class PurchaseRequestUpdate(BaseModel):
    """Payload para edição da solicitação em estado de rascunho."""
    cost_center_id: uuid.UUID | None = None
    justification: str | None = None
    required_date: datetime | str | None = None



class PurchaseRequestResponse(PurchaseRequestBase):
    """Schema de resposta completo da Solicitação de Compra."""
    id: uuid.UUID
    organization_id: uuid.UUID
    requester_id: uuid.UUID
    request_number: str
    status: str
    total_estimated_amount: Decimal
    created_at: datetime
    updated_at: datetime
    items: list[PurchaseRequestItemResponse] = []
    approval_events: list[ApprovalEventResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 8. ESQUEMAS DE ITENS DA ORDEM DE COMPRA (PurchaseOrderItem)
# ==============================================================================

class PurchaseOrderItemBase(BaseModel):
    """Atributos do item da Ordem de Compra."""
    product_id: uuid.UUID
    quantity: Decimal = Field(..., gt=0)
    unit_price: Decimal = Field(..., ge=0)


class PurchaseOrderItemCreate(PurchaseOrderItemBase):
    """Payload para inclusão de item na Ordem de Compra."""
    pass


class PurchaseOrderItemResponse(PurchaseOrderItemBase):
    """Schema de resposta do item da Ordem de Compra."""
    id: uuid.UUID
    purchase_order_id: uuid.UUID
    total_price: Decimal
    product: ProductResponse | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 9. ESQUEMAS DE ORDEM DE COMPRA OFICIAL (PurchaseOrder)
# ==============================================================================

class PurchaseOrderBase(BaseModel):
    """Atributos centrais da Ordem de Compra."""
    supplier_id: uuid.UUID
    cost_center_id: uuid.UUID | None = None
    purchase_request_id: uuid.UUID | None = None
    supplier_quote_id: uuid.UUID | None = None
    payment_terms: str | None = Field(None, description="Ex: 30 dias, À vista, 3x")
    freight_type: str | None = Field("CIF", description="CIF, FOB ou Sem Frete")
    freight_amount: Decimal = Field(default=Decimal("0.00"), ge=0, description="Valor do frete em R$")
    discount_amount: Decimal = Field(default=Decimal("0.00"), ge=0, description="Desconto negociado em R$")
    expected_delivery_date: datetime | None = None
    notes: str | None = None


class PurchaseOrderCreate(PurchaseOrderBase):
    """Payload para emissão de Ordem de Compra."""
    organization_id: uuid.UUID | None = None
    buyer_id: uuid.UUID | None = None
    items: list[PurchaseOrderItemCreate] = Field(..., min_length=1, description="Itens negociados")


class PurchaseOrderReceive(BaseModel):
    """Payload para registro de recebimento físico de mercadoria."""
    invoice_number: str = Field(..., min_length=1, description="Número da Nota Fiscal / DANFE")
    invoice_attachment: str | None = Field(None, description="Arquivo anexado da NF-e (PDF/XML/Imagem em base64 ou URL)")
    received_at: datetime | None = None
    notes: str | None = None


class GeneratePOFromRequest(BaseModel):
    """Payload para conversão direta de uma Solicitação de Compra aprovada em Ordem de Compra."""
    supplier_id: uuid.UUID
    cost_center_id: uuid.UUID | None = None
    payment_terms: str | None = Field(None, description="Ex: 30 dias, À vista")
    freight_type: str | None = Field("CIF", description="CIF, FOB ou Sem Frete")
    freight_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    discount_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    expected_delivery_date: datetime | None = None
    notes: str | None = None
    items: list[PurchaseOrderItemCreate] = Field(..., min_length=1, description="Linhas de itens com quantidades e preços negociados")


class PurchaseOrderUpdate(BaseModel):
    """Payload para atualização de Ordem de Compra."""
    supplier_id: uuid.UUID | None = None
    payment_terms: str | None = None
    freight_type: str | None = None
    freight_amount: Decimal | None = None
    discount_amount: Decimal | None = None
    expected_delivery_date: datetime | None = None
    notes: str | None = None
    status: str | None = None


class PurchaseOrderResponse(PurchaseOrderBase):
    """Schema de resposta oficial da Ordem de Compra."""
    id: uuid.UUID
    organization_id: uuid.UUID
    buyer_id: uuid.UUID
    order_number: str
    status: str
    total_amount: Decimal
    invoice_number: str | None = None
    invoice_attachment: str | None = None
    received_at: datetime | None = None
    received_by_id: uuid.UUID | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    items: list[PurchaseOrderItemResponse] = []
    supplier: SupplierResponse | None = None
    purchase_request: PurchaseRequestResponse | None = None
    supplier_quote_id: uuid.UUID | None = None

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 10. ESQUEMAS DE COTAÇÃO (RFQ) E PROPOSTAS DE FORNECEDORES
# ==============================================================================

class SupplierQuoteItemBase(BaseModel):
    """Atributos de um item cotado por um fornecedor."""
    product_id: uuid.UUID
    quantity: Decimal = Field(..., gt=0)
    unit_price: Decimal = Field(..., ge=0, description="Preço unitário cotado pelo fornecedor")
    brand_offered: str | None = Field(None, description="Marca ou fabricante ofertado")
    notes: str | None = None


class SupplierQuoteItemCreate(SupplierQuoteItemBase):
    """Payload para envio de item cotado."""
    pass


class SupplierQuoteItemResponse(SupplierQuoteItemBase):
    """Resposta com dados do item cotado."""
    id: uuid.UUID
    supplier_quote_id: uuid.UUID
    total_price: Decimal
    product: ProductResponse | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SupplierQuoteBase(BaseModel):
    """Atributos da proposta comercial enviada por um fornecedor."""
    supplier_id: uuid.UUID
    quote_reference: str | None = Field(None, description="Número da proposta comercial do fornecedor")
    payment_terms: str | None = Field("30 DDL", description="Ex: 30 DDL, À Vista, 30/60 Dias")
    freight_type: str | None = Field("CIF", description="CIF, FOB ou Sem Frete")
    freight_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    discount_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    lead_time_days: int | None = Field(None, ge=0, description="Prazo de entrega em dias úteis")
    valid_until: datetime | None = None
    notes: str | None = None


class SupplierQuoteCreate(SupplierQuoteBase):
    """Payload para registro de proposta de fornecedor em uma cotação."""
    items: list[SupplierQuoteItemCreate] = Field(..., min_length=1, description="Lista de itens e preços cotados")


class SupplierQuoteResponse(SupplierQuoteBase):
    """Schema de resposta da proposta de um fornecedor."""
    id: uuid.UUID
    organization_id: uuid.UUID
    quotation_process_id: uuid.UUID
    status: str  # pending, selected, rejected
    total_amount: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime
    items: list[SupplierQuoteItemResponse] = []
    supplier: SupplierResponse | None = None

    model_config = ConfigDict(from_attributes=True)


class QuotationProcessBase(BaseModel):
    """Atributos centrais do Processo de Cotação."""
    purchase_request_id: uuid.UUID
    notes: str | None = None


class QuotationProcessCreate(QuotationProcessBase):
    """Payload para abertura de processo de cotação a partir de uma SC aprovada."""
    pass


class QuotationProcessResponse(QuotationProcessBase):
    """Schema de resposta do Processo de Cotação com suas propostas concorrentes."""
    id: uuid.UUID
    organization_id: uuid.UUID
    quotation_number: str
    status: str  # open, analyzing, completed, cancelled
    is_active: bool
    created_at: datetime
    updated_at: datetime
    quotes: list[SupplierQuoteResponse] = []
    purchase_request: PurchaseRequestResponse | None = None

    model_config = ConfigDict(from_attributes=True)


class QuotationComparisonItem(BaseModel):
    """Item individual no mapa comparativo."""
    product_id: uuid.UUID
    product_name: str
    sku: str
    unit_of_measure: str
    requested_quantity: Decimal
    reference_unit_price: Decimal
    supplier_prices: dict[str, Decimal]  # supplier_id -> unit_price
    lowest_unit_price: Decimal | None = None
    lowest_supplier_id: str | None = None


class QuotationComparisonMatrix(BaseModel):
    """Estrutura do Mapa Comparativo de Cotações."""
    quotation_id: uuid.UUID
    quotation_number: str
    purchase_request_number: str
    status: str
    items_comparison: list[QuotationComparisonItem]
    quotes_summary: list[SupplierQuoteResponse]
    best_total_quote_id: uuid.UUID | None = None
    best_lead_time_quote_id: uuid.UUID | None = None


class SelectWinnerQuoteRequest(BaseModel):
    """Payload para homologação da proposta vencedora e geração da PO."""
    notes: str | None = None


# ==============================================================================
# 9. ESQUEMAS DE INVENTÁRIO, MOVIMENTAÇÕES E SUGESTÕES DE REPOSIÇÃO (ÁGIL)
# ==============================================================================

class PurchaseSuggestionItem(BaseModel):
    """Item sugerido pelo motor de reposição automática de estoque."""
    product_id: uuid.UUID
    product_name: str
    sku: str
    category_name: str | None = None
    brand: str | None = None
    unit_of_measure: str = "UN"
    current_stock: Decimal
    min_stock: Decimal
    max_stock: Decimal | None = None
    suggested_quantity: Decimal
    reference_price: Decimal
    estimated_total: Decimal
    urgency_level: str  # critical (estoque <= 0), high (estoque <= min/2), medium (estoque <= min)
    storage_location: str | None = None


class PurchaseSuggestionsSummary(BaseModel):
    """Resumo geral de sugestões de reposição ativas."""
    total_suggestions: int
    critical_count: int
    estimated_total_cost: Decimal
    items: list[PurchaseSuggestionItem]


class QuickReplenishmentOrderCreate(BaseModel):
    """Payload para emissão ágil de Ordem de Compra a partir de sugestões de compra."""
    supplier_id: uuid.UUID
    cost_center_id: uuid.UUID | None = None
    payment_terms: str | None = "30 DDL"
    freight_type: str | None = "CIF"
    freight_amount: Decimal = Decimal("0.00")
    discount_amount: Decimal = Decimal("0.00")
    expected_delivery_date: datetime | None = None
    notes: str | None = None
    items: list[PurchaseOrderItemCreate]


class StockAdjustmentCreate(BaseModel):
    """Payload para ajuste manual / contagem de inventário."""
    product_id: uuid.UUID
    adjustment_type: str = Field("set_balance", description="'set_balance' (ajuste para saldo exato), 'add_stock' (incremento), 'remove_stock' (baixa)")
    quantity: Decimal = Field(..., ge=0, description="Quantidade ajustada ou saldo físico contado")
    unit_cost: Decimal | None = Field(default=Decimal("0.0000"), ge=0)
    reason: str | None = "Inventário Físico"
    notes: str | None = None


class StockMovementResponse(BaseModel):
    """Registro no extrato de movimentações de estoque."""
    id: uuid.UUID
    organization_id: uuid.UUID
    product_id: uuid.UUID
    product_name: str | None = None
    sku: str | None = None
    movement_type: str
    quantity: Decimal
    unit_cost: Decimal
    balance_after: Decimal
    reference_doc: str | None = None
    notes: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)