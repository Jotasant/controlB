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
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=100)
    address: str | None = Field(None, max_length=500)
    city: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=100)
    zip_code: str | None = Field(None, max_length=100)
    country: str | None = Field("BR", max_length=100)


class SupplierCreate(SupplierBase):
    """Payload para cadastro de um novo Fornecedor."""
    organization_id: uuid.UUID


class SupplierUpdate(BaseModel):
    """Payload para atualização parcial de um Fornecedor."""
    name: str | None = None
    trade_name: str | None = None
    cnpj_cpf: str | None = None
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
    organization_id: uuid.UUID


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
    organization_id: uuid.UUID


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
    sku: str = Field(..., min_length=1, max_length=100, description="Código SKU único interno")
    name: str = Field(..., min_length=2, max_length=500, description="Nome do Produto / Insumo")
    description: str | None = None
    unit_of_measure: str = Field("UN", max_length=50, description="Unidade de Medida (UN, KG, L, CX, M)")
    reference_price: Decimal = Field(default=Decimal("0.0000"), ge=0, description="Preço unitário base/referência")
    category_id: uuid.UUID | None = None


class ProductCreate(ProductBase):
    """Payload para cadastro de Produto."""
    organization_id: uuid.UUID


class ProductUpdate(BaseModel):
    """Payload para edição de Produto."""
    sku: str | None = None
    name: str | None = None
    description: str | None = None
    unit_of_measure: str | None = None
    reference_price: Decimal | None = None
    category_id: uuid.UUID | None = None
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
    justification: str = Field(..., min_length=5, description="Motivo / justificativa da aquisição")
    required_date: datetime | None = None


class PurchaseRequestCreate(PurchaseRequestBase):
    """Payload para emissão de nova Solicitação de Compra com seus itens."""
    organization_id: uuid.UUID
    items: list[PurchaseRequestItemCreate] = Field(..., min_length=1, description="Lista de itens solicitados")


class PurchaseRequestUpdate(BaseModel):
    """Payload para edição da solicitação em estado de rascunho."""
    cost_center_id: uuid.UUID | None = None
    justification: str | None = None
    required_date: datetime | None = None


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
    payment_terms: str | None = Field(None, description="Ex: 30 dias, À vista, 3x")
    freight_type: str | None = Field("CIF", description="CIF, FOB ou Sem Frete")
    expected_delivery_date: datetime | None = None
    notes: str | None = None


class PurchaseOrderCreate(PurchaseOrderBase):
    """Payload para emissão de Ordem de Compra."""
    organization_id: uuid.UUID
    buyer_id: uuid.UUID
    items: list[PurchaseOrderItemCreate] = Field(..., min_length=1, description="Itens negociados")


class PurchaseOrderUpdate(BaseModel):
    """Payload para atualização de Ordem de Compra."""
    supplier_id: uuid.UUID | None = None
    payment_terms: str | None = None
    freight_type: str | None = None
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
    is_active: bool
    created_at: datetime
    updated_at: datetime
    items: list[PurchaseOrderItemResponse] = []
    supplier: SupplierResponse | None = None

    model_config = ConfigDict(from_attributes=True)