"""
modules/inventory/schemas.py - Schemas Pydantic do Módulo de Estoque e Inventário (Inventory Domain)

Define contratos de validação e serialização para:
1. Categorias de Produtos (ProductCategoryCreate, ProductCategoryUpdate, ProductCategoryResponse).
2. Catálogo de Produtos (ProductCreate, ProductUpdate, ProductResponse).
3. Ajustes Manuais de Inventário (StockAdjustmentCreate).
4. Auditoria de Movimentações de Estoque (StockMovementResponse).
"""

import uuid
from decimal import Decimal
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


# ==============================================================================
# 1. CATEGORIAS DE PRODUTOS
# ==============================================================================

class ProductCategoryBase(BaseModel):
    name: str = Field(..., max_length=500, description="Nome da categoria (ex: Medicamentos, Perfumaria)")
    code: str | None = Field(None, max_length=100, description="Código de referência ou prefixo de SKU")
    description: str | None = Field(None, max_length=500, description="Descrição detalhada do grupo")


class ProductCategoryCreate(ProductCategoryBase):
    pass


class ProductCategoryUpdate(BaseModel):
    name: str | None = Field(None, max_length=500)
    code: str | None = Field(None, max_length=100)
    description: str | None = Field(None, max_length=500)
    is_active: bool | None = None


class ProductCategoryResponse(ProductCategoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ==============================================================================
# 2. CATÁLOGO DE PRODUTOS & CONTROLE DE ESTOQUE
# ==============================================================================

class ProductBase(BaseModel):
    sku: str = Field(..., max_length=100, description="Código único de identificação de estoque (SKU)")
    name: str = Field(..., max_length=500, description="Descrição / Nome do produto ou medicamento")
    description: str | None = Field(None, description="Especificação técnica detalhada")
    unit_of_measure: str = Field("UN", max_length=50, description="Unidade (UN, CX, FR, AMP, KG, L)")
    reference_price: Decimal = Field(default=Decimal("0.0000"), description="Preço de referência")
    cost_price: Decimal = Field(default=Decimal("0.0000"), description="Preço de custo unitário")
    sale_price: Decimal = Field(default=Decimal("0.0000"), description="Preço de venda unitário ao consumidor")
    category_id: uuid.UUID | None = Field(None, description="ID da categoria vinculada")
    
    # Rastreabilidade, Integrações & Validade
    external_code: str | None = Field(None, max_length=100, description="Código do produto em sistema externo / legado")
    brand: str | None = Field(None, max_length=200, description="Marca, Fabricante ou Laboratório")
    barcode: str | None = Field(None, max_length=100, description="Código de barras EAN/GTIN")
    ncm: str | None = Field(None, max_length=50, description="Nomenclatura Comum do Mercosul")
    is_perishable: bool = Field(default=False, description="Indica se é item perecível com validade estrita")
    requires_batch: bool = Field(default=False, description="Exige controle de número de lote")
    shelf_life_days: int | None = Field(None, description="Prazo de validade padrão em dias")

    # Parâmetros de Estoque Físico & Ponto de Ressuprimento
    current_stock: Decimal = Field(default=Decimal("0.0000"), description="Saldo físico atual em estoque")
    min_stock: Decimal = Field(default=Decimal("0.00"), description="Estoque mínimo de segurança (Ponto de Pedido)")
    max_stock: Decimal | None = Field(None, description="Estoque máximo ou alvo desejado de reposição")
    storage_location: str | None = Field(None, max_length=200, description="Endereçamento físico no almoxarifado")


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    sku: str | None = Field(None, max_length=100)
    name: str | None = Field(None, max_length=500)
    description: str | None = None
    unit_of_measure: str | None = Field(None, max_length=50)
    reference_price: Decimal | None = None
    cost_price: Decimal | None = None
    sale_price: Decimal | None = None
    category_id: uuid.UUID | None = None
    external_code: str | None = Field(None, max_length=100)
    brand: str | None = Field(None, max_length=200)
    barcode: str | None = Field(None, max_length=100)
    ncm: str | None = Field(None, max_length=50)
    is_perishable: bool | None = None
    requires_batch: bool | None = None
    shelf_life_days: int | None = None
    current_stock: Decimal | None = None
    min_stock: Decimal | None = None
    max_stock: Decimal | None = None
    storage_location: str | None = Field(None, max_length=200)
    is_active: bool | None = None


class ProductResponse(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    category: ProductCategoryResponse | None = None


# ==============================================================================
# 3. AJUSTE DE INVENTÁRIO FÍSICO & MOVIMENTAÇÕES DE ESTOQUE
# ==============================================================================

class StockAdjustmentCreate(BaseModel):
    product_id: uuid.UUID = Field(..., description="ID do produto a ter o saldo movimentado")
    adjustment_type: str = Field(
        ..., 
        description="Tipo: 'invoice_entry' (entrada por NF), 'manual_loss' (baixa/perda), 'reconciliation' (inventário físico), 'add_stock', 'remove_stock', 'set_balance'"
    )
    quantity: Decimal = Field(..., description="Quantidade a movimentar ou novo saldo contado")
    unit_cost: Decimal = Field(default=Decimal("0.0000"), description="Custo unitário do item")
    
    # Documentação Fiscal & Fornecedor (Para Entrada por Nota)
    invoice_number: str | None = Field(None, max_length=100, description="Número da Nota Fiscal (NF-e)")
    supplier_name: str | None = Field(None, max_length=200, description="Fornecedor / Emitente da NF")
    invoice_attachment: str | None = Field(None, description="Arquivo anexado da NF-e (PDF/XML/Imagem em base64 ou URL)")
    
    # Rastreabilidade
    batch_number: str | None = Field(None, max_length=100, description="Número do Lote")
    expiry_date: str | None = Field(None, description="Data de Validade (YYYY-MM-DD)")
    
    # Justificativa & Auditoria
    reason: str | None = Field(None, description="Motivo padronizado da movimentação")
    notes: str | None = Field(None, description="Justificativa formal ou observações detalhadas da conferência")
    auditor_name: str | None = Field(None, description="Nome do responsável / auditor pela contagem física")


class StockMovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    product_id: uuid.UUID
    movement_type: str
    quantity: Decimal
    unit_cost: Decimal
    balance_after: Decimal
    reference_doc: str | None = None
    invoice_attachment: str | None = None
    notes: str | None = None
    created_by_id: uuid.UUID | None = None
    created_at: datetime
    
    product_name: str | None = None
    sku: str | None = None
    product: ProductResponse | None = None


class StockReservationItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    reservation_id: uuid.UUID
    product_id: uuid.UUID
    quantity: Decimal
    created_at: datetime
    product: ProductResponse | None = None


class StockReservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    sales_order_id: uuid.UUID
    document_id: uuid.UUID
    reservation_number: str
    status: Literal["RESERVED", "RELEASED"]
    status_version: int
    created_by_id: uuid.UUID | None = None
    released_by_id: uuid.UUID | None = None
    released_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    items: list[StockReservationItemResponse]


class ProductAvailabilityResponse(BaseModel):
    product_id: uuid.UUID
    sku: str
    product_name: str
    current_stock: Decimal
    reserved_stock: Decimal
    available_stock: Decimal


# ==============================================================================
# 4. SCHEMAS DE IMPORTAÇÃO E SINCRONIZAÇÃO DE ESTOQUE
# ==============================================================================

class InventoryImportItemDetail(BaseModel):
    code: str
    name: str
    barcode: str | None = None
    ncm: str | None = None
    previous_stock: Decimal
    new_stock: Decimal
    delta_stock: Decimal
    action_type: str  # 'created', 'sale_detected', 'entry_detected', 'unchanged'
    cost_price: Decimal
    sale_price: Decimal


class InventoryImportSummaryResponse(BaseModel):
    total_products_read: int
    created_products_count: int
    updated_products_count: int
    created_categories_count: int
    
    sales_identified_count: int
    total_sales_quantity: Decimal
    entries_identified_count: int
    total_entries_quantity: Decimal
    
    total_cost_value: Decimal
    total_sale_value: Decimal
    inventory_date: str | None = None
    message: str
    sample_items: list[InventoryImportItemDetail] = []


# Aliases para compatibilidade
ToolsPharmaImportItemDetail = InventoryImportItemDetail
ToolsPharmaImportSummaryResponse = InventoryImportSummaryResponse
