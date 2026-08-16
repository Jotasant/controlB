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


@router.delete("/cost-centers/{cost_center_id}", status_code=status.HTTP_200_OK)
def delete_cost_center(
    cost_center_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Remove o centro de custo do sistema."""
    return service.delete_cost_center_record(
        db, 
        cost_center_id=cost_center_id, 
        organization_id=current_user.organization_id
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


@router.put("/categories/{category_id}", response_model=schemas.ProductCategoryResponse)
def update_category(
    category_id: uuid.UUID,
    category_data: schemas.ProductCategoryUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Atualiza dados da categoria de produto."""
    return service.update_category_data(
        db,
        category_id=category_id,
        organization_id=current_user.organization_id,
        category_data=category_data
    )


@router.delete("/categories/{category_id}", status_code=status.HTTP_200_OK)
def delete_category(
    category_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Remove a categoria de produto do sistema."""
    return service.delete_category_record(
        db,
        category_id=category_id,
        organization_id=current_user.organization_id
    )



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


@router.delete("/products/{product_id}", status_code=status.HTTP_200_OK)
def delete_product(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Remove o produto do catálogo."""
    return service.delete_product_record(
        db, 
        product_id=product_id, 
        organization_id=current_user.organization_id
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


@router.put("/requests/{request_id}", response_model=schemas.PurchaseRequestResponse)
def update_purchase_request(
    request_id: uuid.UUID,
    request_data: schemas.PurchaseRequestUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Atualiza dados de uma solicitação de compra em rascunho ou pendente."""
    return service.update_purchase_request_data(
        db,
        request_id=request_id,
        organization_id=current_user.organization_id,
        request_data=request_data
    )


@router.delete("/requests/{request_id}", status_code=status.HTTP_200_OK)
def delete_purchase_request(
    request_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Exclui permanentemente uma solicitação de compra em qualquer etapa."""
    return service.delete_purchase_request_record(
        db,
        request_id=request_id,
        organization_id=current_user.organization_id
    )


@router.delete("/requests", status_code=status.HTTP_200_OK)
def purge_all_purchase_requests(
    request_ids: list[uuid.UUID] | None = Query(None, description="Lista opcional de IDs para remoção"),
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Rotina de desenvolvimento para limpar solicitações de teste."""
    return service.purge_purchase_requests(
        db,
        organization_id=current_user.organization_id,
        request_ids=request_ids
    )



@router.post("/requests/{request_id}/cancel", response_model=schemas.PurchaseRequestResponse)
def cancel_purchase_request(
    request_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Cancela uma solicitação de compra e quaisquer cotações abertas vinculadas."""
    return service.cancel_purchase_request(
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


@router.post("/requests/{request_id}/generate-order", response_model=schemas.PurchaseOrderResponse, status_code=status.HTTP_201_CREATED)
def generate_purchase_order_from_request(
    request_id: uuid.UUID,
    data: schemas.GeneratePOFromRequest,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Gera uma Ordem de Compra oficial a partir de uma solicitação de compra aprovada."""
    return service.generate_po_from_request(
        db,
        request_id=request_id,
        current_user=current_user,
        data=data
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


@router.post("/orders/{order_id}/receive", response_model=schemas.PurchaseOrderResponse)
def receive_purchase_order(
    order_id: uuid.UUID,
    data: schemas.PurchaseOrderReceive,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Registra a conferência física e faturamento/recebimento de mercadorias no almoxarifado."""
    return service.receive_purchase_order_shipment(
        db,
        order_id=order_id,
        current_user=current_user,
        data=data
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


@router.delete("/orders/{order_id}", status_code=status.HTTP_200_OK)
def delete_purchase_order(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Exclui permanentemente uma ordem de compra."""
    return service.delete_purchase_order_record(
        db,
        order_id=order_id,
        organization_id=current_user.organization_id
    )


@router.delete("/orders", status_code=status.HTTP_200_OK)
def purge_all_purchase_orders(
    order_ids: list[uuid.UUID] | None = Query(None, description="Lista opcional de IDs de ordens para remoção"),
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Rotina de desenvolvimento para limpar ordens de compra de teste."""
    return service.purge_purchase_orders(
        db,
        organization_id=current_user.organization_id,
        order_ids=order_ids
    )


# ==============================================================================
# 6. ENDPOINTS DE PROCESSOS DE COTAÇÃO (RFQ) E MAPA COMPARATIVO
# ==============================================================================

@router.delete("/quotations/{quotation_id}", status_code=status.HTTP_200_OK)
def delete_quotation(
    quotation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Exclui permanentemente um processo de cotação e propostas vinculadas."""
    return service.delete_quotation_record(
        db,
        quotation_id=quotation_id,
        organization_id=current_user.organization_id
    )


@router.delete("/quotations", status_code=status.HTTP_200_OK)
def purge_all_quotations(
    quotation_ids: list[uuid.UUID] | None = Query(None, description="Lista opcional de IDs de cotações para remoção"),
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Rotina de desenvolvimento para limpar cotações de teste."""
    return service.purge_quotations(
        db,
        organization_id=current_user.organization_id,
        quotation_ids=quotation_ids
    )


@router.post("/requests/{request_id}/quotations", response_model=schemas.QuotationProcessResponse, status_code=status.HTTP_201_CREATED)
def open_quotation_for_request(
    request_id: uuid.UUID,
    data: schemas.QuotationProcessCreate | None = None,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Abre formalmente um Processo de Cotação de Fornecedores (RFQ) a partir de uma SC aprovada."""
    notes = data.notes if data else None
    return service.open_quotation_process(
        db, 
        current_user=current_user, 
        request_id=request_id, 
        notes=notes
    )


@router.get("/quotations", response_model=list[schemas.QuotationProcessResponse])
def get_quotation_processes(
    status: str | None = Query(None, description="Filtro opcional por status"),
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Lista todos os processos de cotação abertos na organização."""
    return service.list_quotation_processes(
        db, 
        organization_id=current_user.organization_id, 
        status_filter=status
    )


@router.get("/quotations/{quotation_id}", response_model=schemas.QuotationProcessResponse)
def get_quotation_process(
    quotation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Retorna os dados completos do processo de cotação com todas as propostas concorrentes."""
    return service.get_quotation_process_details(
        db, 
        quotation_id=quotation_id, 
        organization_id=current_user.organization_id
    )


@router.post("/quotations/{quotation_id}/quotes", response_model=schemas.SupplierQuoteResponse, status_code=status.HTTP_201_CREATED)
def add_supplier_quote(
    quotation_id: uuid.UUID,
    quote_data: schemas.SupplierQuoteCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Registra uma proposta comercial de fornecedor concorrente em uma cotação aberta."""
    return service.add_supplier_quote_to_process(
        db, 
        current_user=current_user, 
        quotation_id=quotation_id, 
        quote_data=quote_data
    )


@router.get("/quotations/{quotation_id}/comparison", response_model=schemas.QuotationComparisonMatrix)
def get_quotation_comparison(
    quotation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Gera o Mapa Comparativo de Cotações destacando menor preço por item, menor total e prazo de entrega."""
    return service.get_quotation_comparison_matrix(
        db, 
        current_user=current_user, 
        quotation_id=quotation_id
    )


@router.post("/quotations/{quotation_id}/select-winner/{quote_id}", response_model=schemas.PurchaseOrderResponse)
def select_winner_and_generate_po(
    quotation_id: uuid.UUID,
    quote_id: uuid.UUID,
    data: schemas.SelectWinnerQuoteRequest | None = None,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Homologa a proposta vencedora de um fornecedor e gera automaticamente a Ordem de Compra oficial."""
    notes = data.notes if data else None
    return service.select_winner_and_generate_order(
        db,
        current_user=current_user,
        quotation_id=quotation_id,
        quote_id=quote_id,
        notes=notes
    )


@router.post("/quotations/{quotation_id}/cancel", response_model=schemas.QuotationProcessResponse)
def cancel_quotation(
    quotation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Cancela um processo de cotação e reverte a Solicitação de Compra vinculada para 'approved'."""
    return service.cancel_quotation_process(
        db,
        current_user=current_user,
        quotation_id=quotation_id
    )


@router.post("/quotations/{quotation_id}/reopen", response_model=schemas.QuotationProcessResponse)
def reopen_quotation(
    quotation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Reabre uma cotação homologada ou cancelada, desfazendo a homologação para nova análise."""
    return service.reopen_quotation_process(
        db,
        current_user=current_user,
        quotation_id=quotation_id
    )


@router.delete("/quotations/{quotation_id}/quotes/{quote_id}", status_code=status.HTTP_200_OK)
def delete_supplier_quote(
    quotation_id: uuid.UUID,
    quote_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """Remove uma proposta comercial de fornecedor lançada na cotação."""
    return service.delete_supplier_quote(
        db,
        current_user=current_user,
        quotation_id=quotation_id,
        quote_id=quote_id
    )


# ==============================================================================
# 9. ENDPOINTS DE REPOSIÇÃO ÁGIL & CONTROLE DE INVENTÁRIO (ESTOQUE)
# ==============================================================================

@router.get("/suggestions", response_model=schemas.PurchaseSuggestionsSummary)
def get_replenishment_suggestions(
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """
    Motor de Sugestões de Compra (Replenishment Engine):
    Retorna todos os produtos com estoque abaixo ou igual ao ponto de pedido (mínimo).
    """
    return service.generate_replenishment_suggestions(
        db,
        organization_id=current_user.organization_id
    )


@router.post("/orders/quick-replenishment", response_model=schemas.PurchaseOrderResponse, status_code=status.HTTP_201_CREATED)
def create_quick_replenishment_order(
    data: schemas.QuickReplenishmentOrderCreate,
    db: Session = Depends(get_db),
    current_user = Depends(identity_service.get_current_user)
):
    """
    Emite diretamente uma Ordem de Compra oficial a partir de itens selecionados da sugestão de reposição.
    """
    return service.create_quick_replenishment_order(
        db,
        current_user=current_user,
        data=data
    )



