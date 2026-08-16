"""
modules/purchasing/api.py - Controladores e Rotas HTTP do Módulo de Compras (FastAPI)

Disponibiliza os endpoints RESTful para:
1. Fornecedores (/purchasing/suppliers)
2. Centros de Custo (/purchasing/cost-centers)
3. Categorias de Produtos (/purchasing/categories)
4. Produtos & Insumos (/purchasing/products)
5. Solicitações de Compra (/purchasing/requests)
6. Decisões de Aprovação por Alçada (/purchasing/requests/{id}/approve)
7. Ordens de Compra (/purchasing/orders)
"""

import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from controlb.db import get_db
from controlb.modules.identity import service as identity_service
from controlb.modules.purchasing import schemas, service

router = APIRouter(prefix="/purchasing", tags=["Purchasing"])


# ==============================================================================
# 1. ENDPOINTS DE FORNECEDORES (Supplier)
# ==============================================================================

@router.get("/suppliers", response_model=list[schemas.SupplierResponse])
def get_suppliers(
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Retorna a lista de fornecedores da organização do usuário logado."""
    return service.list_suppliers(db, organization_id=current_user.organization_id)


@router.post("/suppliers", response_model=schemas.SupplierResponse, status_code=status.HTTP_201_CREATED)
def create_supplier(
    supplier_data: schemas.SupplierCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Cadastra um novo fornecedor homologado."""
    supplier_data.organization_id = current_user.organization_id
    return service.create_new_supplier(db, supplier_data=supplier_data)


@router.put("/suppliers/{supplier_id}", response_model=schemas.SupplierResponse)
def update_supplier(
    supplier_id: uuid.UUID,
    supplier_data: schemas.SupplierUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Atualiza dados cadastrais do fornecedor."""
    return service.update_supplier_data(
        db, 
        supplier_id=supplier_id, 
        organization_id=current_user.organization_id, 
        supplier_data=supplier_data
    )


@router.delete("/suppliers/{supplier_id}", status_code=status.HTTP_200_OK)
def delete_supplier(
    supplier_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Remove o fornecedor do sistema."""
    return service.delete_supplier_record(db, supplier_id=supplier_id, organization_id=current_user.organization_id)


# ==============================================================================
# 2. ENDPOINTS DE CENTROS DE CUSTO (CostCenter)
# ==============================================================================

@router.get("/cost-centers", response_model=list[schemas.CostCenterResponse])
def get_cost_centers(
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Retorna os centros de custo da organização."""
    return service.list_cost_centers(db, organization_id=current_user.organization_id)


@router.post("/cost-centers", response_model=schemas.CostCenterResponse, status_code=status.HTTP_201_CREATED)
def create_cost_center(
    cost_center_data: schemas.CostCenterCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Cadastra um novo centro de custo / unidade orçamentária."""
    cost_center_data.organization_id = current_user.organization_id
    return service.create_new_cost_center(db, cost_center_data=cost_center_data)


@router.put("/cost-centers/{cost_center_id}", response_model=schemas.CostCenterResponse)
def update_cost_center(
    cost_center_id: uuid.UUID,
    cost_center_data: schemas.CostCenterUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Atualiza dados do centro de custo."""
    return service.update_cost_center_data(
        db, 
        cost_center_id=cost_center_id, 
        organization_id=current_user.organization_id, 
        cost_center_data=cost_center_data
    )


# ==============================================================================
# 3. ENDPOINTS DE CATEGORIAS E PRODUTOS (Product & Category)
# ==============================================================================

@router.get("/categories", response_model=list[schemas.ProductCategoryResponse])
def get_categories(
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Retorna as categorias de produtos da organização."""
    return service.list_categories(db, organization_id=current_user.organization_id)


@router.post("/categories", response_model=schemas.ProductCategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    category_data: schemas.ProductCategoryCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Cadastra uma nova categoria de produto."""
    category_data.organization_id = current_user.organization_id
    return service.create_new_category(db, category_data=category_data)


@router.get("/products", response_model=list[schemas.ProductResponse])
def get_products(
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Retorna o catálogo de produtos e insumos da organização."""
    return service.list_products(db, organization_id=current_user.organization_id)


@router.post("/products", response_model=schemas.ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    product_data: schemas.ProductCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Cadastra um novo produto/insumo no catálogo."""
    product_data.organization_id = current_user.organization_id
    return service.create_new_product(db, product_data=product_data)


@router.put("/products/{product_id}", response_model=schemas.ProductResponse)
def update_product(
    product_id: uuid.UUID,
    product_data: schemas.ProductUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Atualiza dados cadastrais do produto."""
    return service.update_product_data(
        db, 
        product_id=product_id, 
        organization_id=current_user.organization_id, 
        product_data=product_data
    )


# ==============================================================================
# 4. ENDPOINTS DE SOLICITAÇÃO DE COMPRA (PurchaseRequest & Approval)
# ==============================================================================

@router.get("/requests", response_model=list[schemas.PurchaseRequestResponse])
def get_purchase_requests(
    status: str | None = Query(None, description="Filtro opcional por status (pending_approval, approved, etc.)"),
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Retorna todas as solicitações de compra da organização."""
    return service.list_purchase_requests(
        db, 
        organization_id=current_user.organization_id, 
        status_filter=status
    )


@router.post("/requests", response_model=schemas.PurchaseRequestResponse, status_code=status.HTTP_201_CREATED)
def create_purchase_request(
    request_data: schemas.PurchaseRequestCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Emite uma nova solicitação de compra com cálculo automático de totais."""
    request_data.organization_id = current_user.organization_id
    return service.create_purchase_request(db, current_user=current_user, request_data=request_data)


@router.get("/requests/{request_id}", response_model=schemas.PurchaseRequestResponse)
def get_purchase_request(
    request_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Retorna os detalhes completos de uma solicitação (incluindo linhas e histórico de aprovação)."""
    return service.get_purchase_request_details(
        db, 
        request_id=request_id, 
        organization_id=current_user.organization_id
    )


@router.post("/requests/{request_id}/approve", response_model=schemas.PurchaseRequestResponse)
def approve_or_reject_request(
    request_id: uuid.UUID,
    action_data: schemas.ApprovalActionRequest,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Decisão do aprovador: Aprova ou Rejeita a solicitação com parecer na trilha de auditoria."""
    return service.process_approval_action(
        db, 
        request_id=request_id, 
        current_user=current_user, 
        action_data=action_data
    )


# ==============================================================================
# 5. ENDPOINTS DE ORDENS DE COMPRA (PurchaseOrder)
# ==============================================================================

@router.get("/orders", response_model=list[schemas.PurchaseOrderResponse])
def get_purchase_orders(
    status: str | None = Query(None, description="Filtro opcional por status"),
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Retorna as ordens de compra emitidas na organização."""
    return service.list_purchase_orders(
        db, 
        organization_id=current_user.organization_id, 
        status_filter=status
    )


@router.post("/orders", response_model=schemas.PurchaseOrderResponse, status_code=status.HTTP_201_CREATED)
def create_purchase_order(
    order_data: schemas.PurchaseOrderCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Emite uma nova ordem de compra oficial."""
    order_data.organization_id = current_user.organization_id
    order_data.buyer_id = current_user.id
    return service.create_purchase_order(db, current_user=current_user, order_data=order_data)


@router.get("/orders/{order_id}", response_model=schemas.PurchaseOrderResponse)
def get_purchase_order(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Retorna os detalhes de uma ordem de compra específica."""
    return service.get_purchase_order_details(
        db, 
        order_id=order_id, 
        organization_id=current_user.organization_id
    )


@router.post("/orders/{order_id}/cancel", response_model=schemas.PurchaseOrderResponse)
def cancel_purchase_order(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Cancela de forma controlada uma ordem de compra emitida."""
    return service.cancel_purchase_order(
        db, 
        order_id=order_id, 
        organization_id=current_user.organization_id
    )
