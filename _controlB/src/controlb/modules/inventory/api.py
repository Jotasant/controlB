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
    ProductAvailabilityResponse,
    StockAdjustmentCreate, StockMovementResponse,
    StockReservationResponse,
    InventoryDeliveryResponse,
    InventoryLocationCreate,
    InventoryLocationResponse,
    InventoryBalanceResponse,
    InventoryTransferCreate,
    InventoryTransferResponse,
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


@router.get(
    "/products/{product_id}/availability",
    response_model=ProductAvailabilityResponse,
    summary="Consultar Saldo Disponível",
)
def get_product_availability(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(identity_service.require_permission("products:view")),
):
    return service.get_product_availability(
        db, current_user.organization_id, product_id
    )


# ==============================================================================
# 3. RESERVAS INTEGRAIS POR PEDIDO DE VENDA
# ==============================================================================

@router.get(
    "/reservations/sales-orders/{sales_order_id}",
    response_model=StockReservationResponse,
    summary="Consultar Reserva do Pedido",
)
def get_sales_order_reservation(
    sales_order_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(identity_service.require_permission("products:view")),
):
    return service.get_sales_order_reservation(
        db, current_user.organization_id, sales_order_id
    )


@router.post(
    "/reservations/sales-orders/{sales_order_id}",
    response_model=StockReservationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Reservar Integralmente um Pedido Confirmado",
)
def reserve_sales_order(
    sales_order_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(identity_service.require_permission("inventory:move")),
):
    return service.reserve_sales_order(
        db,
        current_user.organization_id,
        current_user.id,
        sales_order_id,
    )


@router.post(
    "/reservations/{reservation_id}/release",
    response_model=StockReservationResponse,
    summary="Liberar Reserva de Estoque",
)
def release_stock_reservation(
    reservation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(identity_service.require_permission("inventory:move")),
):
    return service.release_stock_reservation(
        db,
        current_user.organization_id,
        current_user.id,
        reservation_id,
    )


@router.get(
    "/reservations/{reservation_id}",
    response_model=StockReservationResponse,
    summary="Consultar Reserva de Estoque",
)
def get_stock_reservation(
    reservation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(identity_service.require_permission("products:view")),
):
    return service.get_stock_reservation(
        db, current_user.organization_id, reservation_id
    )


@router.get(
    "/deliveries/sales-orders/{sales_order_id}",
    response_model=InventoryDeliveryResponse,
    summary="Consultar Entrega do Pedido de Venda",
)
def get_sales_order_delivery(
    sales_order_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(identity_service.require_permission("products:view")),
):
    return service.get_sales_order_delivery(
        db, current_user.organization_id, sales_order_id
    )


@router.get(
    "/deliveries/{delivery_id}",
    response_model=InventoryDeliveryResponse,
    summary="Consultar Entrega por ID",
)
def get_inventory_delivery(
    delivery_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(identity_service.require_permission("products:view")),
):
    return service.get_inventory_delivery(
        db, current_user.organization_id, delivery_id
    )


@router.get(
    "/locations",
    response_model=list[InventoryLocationResponse],
    summary="Listar Localizações de Estoque",
)
def list_inventory_locations(
    db: Session = Depends(get_db),
    current_user=Depends(identity_service.require_permission("products:view")),
):
    return service.list_inventory_locations(db, current_user.organization_id)


@router.post(
    "/locations",
    response_model=InventoryLocationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar Localização de Estoque",
)
def create_inventory_location(
    payload: InventoryLocationCreate,
    db: Session = Depends(get_db),
    current_user=Depends(identity_service.require_permission("inventory:move")),
):
    return service.create_inventory_location(
        db, current_user.organization_id, payload
    )


@router.get(
    "/balances",
    response_model=list[InventoryBalanceResponse],
    summary="Listar Saldos por Localização",
)
def list_inventory_balances(
    product_id: uuid.UUID | None = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(identity_service.require_permission("products:view")),
):
    return service.list_inventory_balances(
        db, current_user.organization_id, product_id
    )


@router.post(
    "/transfers",
    response_model=InventoryTransferResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Transferir Estoque entre Localizações",
)
def create_inventory_transfer(
    payload: InventoryTransferCreate,
    db: Session = Depends(get_db),
    current_user=Depends(identity_service.require_permission("inventory:move")),
):
    return service.create_inventory_transfer(
        db, current_user.organization_id, current_user, payload
    )


@router.get(
    "/transfers",
    response_model=list[InventoryTransferResponse],
    summary="Listar Transferências de Estoque",
)
def list_inventory_transfers(
    db: Session = Depends(get_db),
    current_user=Depends(identity_service.require_permission("products:view")),
):
    return service.list_inventory_transfers(db, current_user.organization_id)


@router.get(
    "/transfers/{transfer_id}",
    response_model=InventoryTransferResponse,
    summary="Consultar Transferência de Estoque",
)
def get_inventory_transfer(
    transfer_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(identity_service.require_permission("products:view")),
):
    return service.get_inventory_transfer(
        db, current_user.organization_id, transfer_id
    )


# ==============================================================================
# 4. GESTÃO DE INVENTÁRIO FÍSICO & AUDITORIA DE MOVIMENTAÇÕES
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
from controlb.modules.inventory.schemas import (
    InventoryImportSummaryResponse,
    InventoryImportBatchResponse,
    InventoryImportBatchListItem,
    StagnantInventoryReportResponse,
)

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
        file_bytes=file_bytes,
        filename=file.filename
    )


@router.get("/import-batches", response_model=list[InventoryImportBatchListItem], summary="Listar Lotes de Importação de Estoque")
def list_import_batches(
    limit: int = Query(50, ge=1, le=200, description="Limite de registros"),
    offset: int = Query(0, ge=0, description="Offset de paginação"),
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Retorna o histórico cronológico de lotes de importação de planilhas de estoque."""
    return service.list_inventory_import_batches(
        db=db,
        organization_id=current_user.organization_id,
        limit=limit,
        offset=offset
    )


@router.get("/import-batches/{batch_id}", response_model=InventoryImportBatchResponse, summary="Detalhar Lote de Importação com Auditoria de Itens")
def get_import_batch_detail(
    batch_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Retorna o raio-X completo do lote com todos os itens auditados, variações de preço, vendas e estagnação."""
    return service.get_inventory_import_batch_detail(
        db=db,
        organization_id=current_user.organization_id,
        batch_id=batch_id
    )


@router.get("/reports/stagnation", response_model=StagnantInventoryReportResponse, summary="Relatório de Estoque Estagnado e Capital Imobilizado")
def get_stagnation_report(
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Retorna análise de produtos parados sem giro de vendas e o valor financeiro imobilizado."""
    return service.get_stagnant_inventory_report(
        db=db,
        organization_id=current_user.organization_id
    )
