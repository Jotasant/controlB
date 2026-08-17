"""
modules/inventory/api.py - Roteador de Endpoints REST do Módulo de Estoque e Inventário (Inventory Domain)

Disponibiliza rotas HTTP para:
1. Categorias de Produtos (/inventory/categories).
2. Catálogo de Produtos e Saldo Físico (/inventory/products).
3. Ajuste Manual de Inventário e Contagem (/inventory/adjust).
4. Extrato e Auditoria de Movimentações (/inventory/movements).
"""

import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from controlb.db import get_db
from controlb.modules.identity import service as identity_service
from controlb.modules.inventory import service
from controlb.modules.inventory.schemas import (
    ProductCategoryCreate, ProductCategoryUpdate, ProductCategoryResponse,
    ProductCreate, ProductUpdate, ProductResponse,
    StockAdjustmentCreate, StockMovementResponse
)

router = APIRouter(prefix="", tags=["Inventory / Estoque"])


# ==============================================================================
# 1. CATEGORIAS DE PRODUTOS
# ==============================================================================

@router.get("/categories", response_model=list[ProductCategoryResponse], summary="Listar Categorias de Produtos")
def list_categories(
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.list_categories(db, current_user.organization_id)


@router.post("/categories", response_model=ProductCategoryResponse, status_code=status.HTTP_201_CREATED, summary="Criar Categoria de Produto")
def create_category(
    payload: ProductCategoryCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.create_category(db, current_user.organization_id, payload)


@router.put("/categories/{category_id}", response_model=ProductCategoryResponse, summary="Atualizar Categoria de Produto")
def update_category(
    category_id: uuid.UUID,
    payload: ProductCategoryUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.update_category(db, category_id, current_user.organization_id, payload)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir Categoria de Produto")
def delete_category(
    category_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    service.delete_category(db, category_id, current_user.organization_id)
    return None


# ==============================================================================
# 2. CATÁLOGO DE PRODUTOS & SALDO DE ESTOQUE
# ==============================================================================

@router.get("/products", response_model=list[ProductResponse], summary="Listar Produtos e Insumos")
def list_products(
    category_id: uuid.UUID | None = Query(None, description="Filtrar por categoria"),
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.list_products(db, current_user.organization_id, category_id)


@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED, summary="Cadastrar Produto")
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.create_product(db, current_user.organization_id, payload)


@router.get("/products/{product_id}", response_model=ProductResponse, summary="Obter Detalhes do Produto")
def get_product(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.get_product(db, product_id, current_user.organization_id)


@router.put("/products/{product_id}", response_model=ProductResponse, summary="Atualizar Produto")
def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.update_product(db, product_id, current_user.organization_id, payload)


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir Produto")
def delete_product(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    service.delete_product(db, product_id, current_user.organization_id)
    return None


# ==============================================================================
# 3. GESTÃO DE INVENTÁRIO FÍSICO & AUDITORIA DE MOVIMENTAÇÕES
# ==============================================================================

@router.post("/adjust", response_model=StockMovementResponse, status_code=status.HTTP_200_OK, summary="Ajustar Saldo Físico / Inventário")
def adjust_inventory_stock(
    payload: StockAdjustmentCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.adjust_stock(db, current_user.organization_id, current_user.id, payload)


@router.get("/movements", response_model=list[StockMovementResponse], summary="Consultar Extrato de Movimentações de Estoque")
def list_inventory_movements(
    product_id: uuid.UUID | None = Query(None, description="Filtrar por produto"),
    limit: int = Query(100, ge=1, le=500, description="Limite de registros"),
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    return service.list_movements(db, current_user.organization_id, product_id, limit)


# ==============================================================================
# 4. IMPORTAÇÃO E SINCRONIZAÇÃO DE PLANILHA DE ESTOQUE
# ==============================================================================

from fastapi import File, UploadFile
from controlb.modules.inventory.schemas import InventoryImportSummaryResponse

@router.post("/import-spreadsheet", response_model=InventoryImportSummaryResponse, summary="Importar Planilha de Inventário / Estoque")
@router.post("/import-toolspharma", response_model=InventoryImportSummaryResponse, summary="Importar Planilha (Alias)")
async def import_inventory_spreadsheet(
    file: UploadFile = File(..., description="Arquivo .xlsx de inventário e estoque"),
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """
    Recebe e processa a planilha de inventário e estoque (.xlsx).
    Identifica novos produtos, atualiza saldos, cria categorias e detecta vendas e reposições diárias.
    """
    file_bytes = await file.read()
    return service.import_inventory_spreadsheet(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        file_bytes=file_bytes
    )


