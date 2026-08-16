"""
modules/purchasing/service.py - Camada de Regras de Negócio e Casos de Uso (Purchasing)

Contém a lógica de domínio para:
1. Gestão de Cadastros de Apoio (Fornecedores, Centros de Custo, Categorias, Produtos).
2. Criação, Cálculo e Numeração Sequencial de Solicitações de Compra.
3. Máquina de Estados e Trilha de Auditoria de Aprovações por Alçada.
4. Emissão e Cancelamento de Ordens de Compra Oficiais.
"""

import uuid
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from controlb.modules.purchasing import models, schemas, repository
from controlb.modules.identity.models import User


def utcnow() -> datetime:
    """Retorna o horário atual em UTC."""
    return datetime.now(timezone.utc)


# ==============================================================================
# 1. REGRAS DE NEGÓCIO DE FORNECEDORES (Supplier)
# ==============================================================================

def list_suppliers(db: Session, organization_id: uuid.UUID) -> list[models.Supplier]:
    """Retorna todos os fornecedores da organização."""
    return repository.get_all_suppliers(db, organization_id=organization_id)


def create_new_supplier(db: Session, supplier_data: schemas.SupplierCreate) -> models.Supplier:
    """Valida duplicidade de CNPJ/CPF antes de criar o fornecedor."""
    existing = repository.get_supplier_by_cnpj(
        db, 
        cnpj_cpf=supplier_data.cnpj_cpf, 
        organization_id=supplier_data.organization_id
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Já existe um fornecedor cadastrado com este CNPJ/CPF nesta organização."
        )

    return repository.create_supplier(db, supplier_data=supplier_data)


def update_supplier_data(
    db: Session, 
    supplier_id: uuid.UUID, 
    organization_id: uuid.UUID, 
    supplier_data: schemas.SupplierUpdate
) -> models.Supplier:
    """Atualiza dados cadastrais do fornecedor."""
    db_supplier = repository.get_supplier_by_id(db, supplier_id=supplier_id, organization_id=organization_id)
    if not db_supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fornecedor não encontrado."
        )

    return repository.update_supplier(db, db_supplier=db_supplier, supplier_data=supplier_data)


def delete_supplier_record(db: Session, supplier_id: uuid.UUID, organization_id: uuid.UUID) -> dict:
    """Remove o fornecedor do sistema."""
    db_supplier = repository.get_supplier_by_id(db, supplier_id=supplier_id, organization_id=organization_id)
    if not db_supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fornecedor não encontrado."
        )

    repository.delete_supplier(db, db_supplier=db_supplier)
    return {"detail": "Fornecedor excluído com sucesso."}


# ==============================================================================
# 2. REGRAS DE NEGÓCIO DE CENTROS DE CUSTO (CostCenter)
# ==============================================================================

def list_cost_centers(db: Session, organization_id: uuid.UUID) -> list[models.CostCenter]:
    """Retorna todos os centros de custo da organização."""
    return repository.get_all_cost_centers(db, organization_id=organization_id)


def create_new_cost_center(db: Session, cost_center_data: schemas.CostCenterCreate) -> models.CostCenter:
    """Valida código único antes de criar o centro de custo."""
    existing = repository.get_cost_center_by_code(
        db, 
        code=cost_center_data.code, 
        organization_id=cost_center_data.organization_id
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Já existe um centro de custo com o código '{cost_center_data.code}'."
        )

    return repository.create_cost_center(db, cost_center_data=cost_center_data)


def update_cost_center_data(
    db: Session, 
    cost_center_id: uuid.UUID, 
    organization_id: uuid.UUID, 
    cost_center_data: schemas.CostCenterUpdate
) -> models.CostCenter:
    """Atualiza dados do centro de custo."""
    db_cost_center = repository.get_cost_center_by_id(db, cost_center_id=cost_center_id, organization_id=organization_id)
    if not db_cost_center:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Centro de custo não encontrado."
        )

    return repository.update_cost_center(db, db_cost_center=db_cost_center, cost_center_data=cost_center_data)


# ==============================================================================
# 3. REGRAS DE NEGÓCIO DE CATEGORIAS E PRODUTOS (Product & Category)
# ==============================================================================

def list_categories(db: Session, organization_id: uuid.UUID) -> list[models.ProductCategory]:
    """Retorna todas as categorias da organização."""
    return repository.get_all_product_categories(db, organization_id=organization_id)


def create_new_category(db: Session, category_data: schemas.ProductCategoryCreate) -> models.ProductCategory:
    """Cria uma nova categoria de produto."""
    return repository.create_product_category(db, category_data=category_data)


def list_products(db: Session, organization_id: uuid.UUID) -> list[models.Product]:
    """Retorna o catálogo de produtos da organização."""
    return repository.get_all_products(db, organization_id=organization_id)


def create_new_product(db: Session, product_data: schemas.ProductCreate) -> models.Product:
    """Valida duplicidade de SKU antes de cadastrar o produto."""
    existing = repository.get_product_by_sku(
        db, 
        sku=product_data.sku, 
        organization_id=product_data.organization_id
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Já existe um produto cadastrado com o SKU '{product_data.sku}'."
        )

    return repository.create_product(db, product_data=product_data)


def update_product_data(
    db: Session, 
    product_id: uuid.UUID, 
    organization_id: uuid.UUID, 
    product_data: schemas.ProductUpdate
) -> models.Product:
    """Atualiza dados cadastrais do produto."""
    db_product = repository.get_product_by_id(db, product_id=product_id, organization_id=organization_id)
    if not db_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Produto não encontrado no catálogo."
        )

    return repository.update_product(db, db_product=db_product, product_data=product_data)


# ==============================================================================
# 4. SOLICITAÇÕES DE COMPRA (PurchaseRequest & Approval Workflow)
# ==============================================================================

def generate_request_number(db: Session, organization_id: uuid.UUID) -> str:
    """Gera número sequencial amigável no formato SC-YYYY-XXXX."""
    current_year = datetime.now(timezone.utc).year
    total_in_year = repository.count_purchase_requests_in_year(db, organization_id, current_year)
    return f"SC-{current_year}-{(total_in_year + 1):04d}"


def create_purchase_request(
    db: Session, 
    current_user: User, 
    request_data: schemas.PurchaseRequestCreate
) -> models.PurchaseRequest:
    """
    Cria uma nova Solicitação de Compra:
    1. Valida existência dos produtos no catálogo.
    2. Calcula os totais de cada item e o valor estimado global.
    3. Gera o número sequencial amigável (SC-2026-0001).
    4. Persiste a solicitação em estado 'pending_approval'.
    """
    if not request_data.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A solicitação de compra deve conter pelo menos um item."
        )

    # 1. Valida produtos e calcula total geral
    total_estimated = Decimal("0.00")
    for item in request_data.items:
        product = repository.get_product_by_id(
            db, 
            product_id=item.product_id, 
            organization_id=request_data.organization_id
        )
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Produto ID '{item.product_id}' não encontrado no catálogo."
            )
        
        item_total = Decimal(str(item.quantity)) * Decimal(str(item.estimated_unit_price))
        total_estimated += item_total

    # 2. Gera número sequencial
    request_number = generate_request_number(db, organization_id=request_data.organization_id)

    # 3. Persiste no banco
    return repository.create_purchase_request(
        db=db,
        requester_id=current_user.id,
        request_number=request_number,
        total_estimated=total_estimated,
        request_data=request_data
    )


def list_purchase_requests(
    db: Session, 
    organization_id: uuid.UUID, 
    status_filter: str | None = None
) -> list[models.PurchaseRequest]:
    """Retorna as solicitações de compra da organização com filtro opcional."""
    return repository.get_all_purchase_requests(db, organization_id=organization_id, status=status_filter)


def get_purchase_request_details(
    db: Session, 
    request_id: uuid.UUID, 
    organization_id: uuid.UUID
) -> models.PurchaseRequest:
    """Busca os detalhes completos de uma solicitação."""
    db_request = repository.get_purchase_request_by_id(db, request_id=request_id, organization_id=organization_id)
    if not db_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitação de compra não encontrada."
        )
    return db_request


def process_approval_action(
    db: Session, 
    request_id: uuid.UUID, 
    current_user: User, 
    action_data: schemas.ApprovalActionRequest
) -> models.PurchaseRequest:
    """
    Decisão do Aprovador por Alçada:
    1. Valida se a solicitação está pendente de aprovação.
    2. Se for rejeitada, exige parecer/justificativa.
    3. Registra o evento imutável na trilha de auditoria.
    4. Atualiza o status para 'approved' ou 'rejected'.
    """
    db_request = repository.get_purchase_request_by_id(
        db, 
        request_id=request_id, 
        organization_id=current_user.organization_id
    )
    if not db_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitação de compra não encontrada."
        )

    if db_request.status != "pending_approval":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Esta solicitação não pode ser alterada pois já se encontra no status '{db_request.status}'."
        )

    if action_data.action == "rejected" and not action_data.comments:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="É obrigatório informar uma justificativa ao rejeitar a solicitação."
        )

    # Registra evento na trilha de auditoria
    repository.create_approval_event(
        db=db,
        purchase_request_id=db_request.id,
        approver_id=current_user.id,
        action=action_data.action,
        comments=action_data.comments
    )

    # Atualiza status da solicitação
    new_status = "approved" if action_data.action == "approved" else "rejected"
    return repository.update_purchase_request_status(db, db_request=db_request, new_status=new_status)


# ==============================================================================
# 5. ORDENS DE COMPRA OFICIAIS (PurchaseOrder)
# ==============================================================================

def generate_order_number(db: Session, organization_id: uuid.UUID) -> str:
    """Gera número sequencial no formato OC-YYYY-XXXX."""
    current_year = datetime.now(timezone.utc).year
    total_in_year = repository.count_purchase_orders_in_year(db, organization_id, current_year)
    return f"OC-{current_year}-{(total_in_year + 1):04d}"


def create_purchase_order(
    db: Session, 
    current_user: User, 
    order_data: schemas.PurchaseOrderCreate
) -> models.PurchaseOrder:
    """
    Emite uma nova Ordem de Compra oficial:
    1. Valida existência e status do fornecedor.
    2. Calcula o total da ordem a partir dos itens negociados.
    3. Gera o número sequencial (OC-2026-0001).
    4. Persiste a ordem de compra com status inicial 'issued'.
    """
    supplier = repository.get_supplier_by_id(
        db, 
        supplier_id=order_data.supplier_id, 
        organization_id=order_data.organization_id
    )
    if not supplier or not supplier.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O fornecedor selecionado não existe ou está inativo."
        )

    if not order_data.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A ordem de compra precisa conter pelo menos um item."
        )

    total_order = Decimal("0.00")
    for item in order_data.items:
        item_total = Decimal(str(item.quantity)) * Decimal(str(item.unit_price))
        total_order += item_total

    order_number = generate_order_number(db, organization_id=order_data.organization_id)

    return repository.create_purchase_order(
        db=db,
        order_number=order_number,
        total_amount=total_order,
        order_data=order_data
    )


def list_purchase_orders(
    db: Session, 
    organization_id: uuid.UUID, 
    status_filter: str | None = None
) -> list[models.PurchaseOrder]:
    """Retorna todas as ordens de compra da organização."""
    return repository.get_all_purchase_orders(db, organization_id=organization_id, status=status_filter)


def get_purchase_order_details(
    db: Session, 
    order_id: uuid.UUID, 
    organization_id: uuid.UUID
) -> models.PurchaseOrder:
    """Busca os detalhes completos de uma ordem de compra."""
    db_order = repository.get_purchase_order_by_id(db, order_id=order_id, organization_id=organization_id)
    if not db_order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ordem de compra não encontrada."
        )
    return db_order


def cancel_purchase_order(
    db: Session, 
    order_id: uuid.UUID, 
    organization_id: uuid.UUID
) -> models.PurchaseOrder:
    """Cancela de forma controlada uma ordem de compra emitida."""
    db_order = repository.get_purchase_order_by_id(db, order_id=order_id, organization_id=organization_id)
    if not db_order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ordem de compra não encontrada."
        )

    if db_order.status in ["closed", "cancelled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não é possível cancelar uma ordem com status '{db_order.status}'."
        )

    return repository.update_purchase_order_status(db, db_order=db_order, new_status="cancelled")
