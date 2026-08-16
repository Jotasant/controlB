"""
modules/inventory/service.py - Camada de Regras de Negócio do Módulo de Estoque e Inventário (Inventory Domain)

Contém a lógica de:
1. Gestão do Catálogo de Produtos e Categorias.
2. Ajuste manual de estoque e contagens físicas de inventário.
3. Extrato e auditoria de movimentações de estoque.
4. Integração desacoplada para entrada de compras e consulta de ponto de ressuprimento.
"""

import uuid
from decimal import Decimal
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from controlb.logger import logger
from controlb.modules.inventory import repository
from controlb.modules.inventory.models import ProductCategory, Product, StockMovement
from controlb.modules.inventory.schemas import (
    ProductCategoryCreate, ProductCategoryUpdate,
    ProductCreate, ProductUpdate,
    StockAdjustmentCreate, StockMovementResponse
)


# ==============================================================================
# 1. SERVIÇOS DE CATEGORIAS DE PRODUTOS
# ==============================================================================

def create_category(db: Session, organization_id: uuid.UUID, payload: ProductCategoryCreate) -> ProductCategory:
    existing = repository.get_category_by_name(db, payload.name, organization_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Já existe uma categoria cadastrada com o nome '{payload.name}'."
        )

    cat = ProductCategory(
        organization_id=organization_id,
        name=payload.name.strip(),
        code=payload.code.strip().upper() if payload.code else None,
        description=payload.description.strip() if payload.description else None
    )
    return repository.create_category(db, cat)


def update_category(
    db: Session, 
    category_id: uuid.UUID, 
    organization_id: uuid.UUID, 
    payload: ProductCategoryUpdate
) -> ProductCategory:
    cat = repository.get_category_by_id(db, category_id, organization_id)
    if not cat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoria não encontrada.")

    if payload.name is not None and payload.name.strip().lower() != cat.name.lower():
        existing = repository.get_category_by_name(db, payload.name, organization_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Já existe outra categoria com o nome '{payload.name}'."
            )
        cat.name = payload.name.strip()

    if payload.code is not None:
        cat.code = payload.code.strip().upper() if payload.code else None
    if payload.description is not None:
        cat.description = payload.description.strip() if payload.description else None
    if payload.is_active is not None:
        cat.is_active = payload.is_active

    return repository.update_category(db, cat)


def delete_category(db: Session, category_id: uuid.UUID, organization_id: uuid.UUID) -> None:
    cat = repository.get_category_by_id(db, category_id, organization_id)
    if not cat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoria não encontrada.")

    prod_count = repository.count_products_in_category(db, category_id, organization_id)
    if prod_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não é possível excluir a categoria '{cat.name}' pois existem {prod_count} produto(s) vinculado(s)."
        )

    repository.delete_category(db, cat)


def list_categories(db: Session, organization_id: uuid.UUID) -> list[ProductCategory]:
    return repository.list_categories(db, organization_id)


# ==============================================================================
# 2. SERVIÇOS DO CATÁLOGO DE PRODUTOS
# ==============================================================================

def create_product(db: Session, organization_id: uuid.UUID, payload: ProductCreate) -> Product:
    existing = repository.get_product_by_sku(db, payload.sku, organization_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Já existe um produto com o SKU '{payload.sku}' nesta organização."
        )

    if payload.category_id:
        cat = repository.get_category_by_id(db, payload.category_id, organization_id)
        if not cat:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Categoria informada não existe.")

    prod = Product(
        organization_id=organization_id,
        sku=payload.sku.strip().upper(),
        name=payload.name.strip(),
        description=payload.description.strip() if payload.description else None,
        unit_of_measure=payload.unit_of_measure.strip().upper(),
        reference_price=payload.reference_price,
        category_id=payload.category_id,
        brand=payload.brand.strip() if payload.brand else None,
        barcode=payload.barcode.strip() if payload.barcode else None,
        ncm=payload.ncm.strip() if payload.ncm else None,
        is_perishable=payload.is_perishable,
        requires_batch=payload.requires_batch,
        shelf_life_days=payload.shelf_life_days,
        current_stock=payload.current_stock,
        min_stock=payload.min_stock,
        max_stock=payload.max_stock,
        storage_location=payload.storage_location.strip() if payload.storage_location else None
    )
    created_prod = repository.create_product(db, prod)

    # Se foi iniciado com saldo positivo, registra movimentação inicial de inventário
    if payload.current_stock > 0:
        mov = StockMovement(
            organization_id=organization_id,
            product_id=created_prod.id,
            movement_type="in_adjustment",
            quantity=payload.current_stock,
            unit_cost=payload.reference_price,
            balance_after=payload.current_stock,
            reference_doc="Saldo Inicial de Cadastro",
            notes="Registro de implantação de saldo inicial do produto."
        )
        repository.create_stock_movement(db, mov)

    return created_prod


def update_product(
    db: Session, 
    product_id: uuid.UUID, 
    organization_id: uuid.UUID, 
    payload: ProductUpdate
) -> Product:
    prod = repository.get_product_by_id(db, product_id, organization_id)
    if not prod:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado.")

    if payload.sku is not None and payload.sku.strip().upper() != prod.sku:
        existing = repository.get_product_by_sku(db, payload.sku, organization_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Já existe outro produto com o SKU '{payload.sku}'."
            )
        prod.sku = payload.sku.strip().upper()

    if payload.category_id is not None:
        if payload.category_id:
            cat = repository.get_category_by_id(db, payload.category_id, organization_id)
            if not cat:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Categoria informada não existe.")
        prod.category_id = payload.category_id

    for field, val in payload.model_dump(exclude_unset=True).items():
        if field not in ("sku", "category_id") and hasattr(prod, field):
            setattr(prod, field, val)

    return repository.update_product(db, prod)


from sqlalchemy.exc import IntegrityError
from controlb.modules.purchasing import models as purchasing_models


def delete_product(db: Session, product_id: uuid.UUID, organization_id: uuid.UUID) -> None:
    prod = repository.get_product_by_id(db, product_id, organization_id)
    if not prod:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado.")

    # 1. Verifica vínculos em Ordens de Compra
    po_items_count = db.query(purchasing_models.PurchaseOrderItem).filter(
        purchasing_models.PurchaseOrderItem.product_id == product_id
    ).count()
    if po_items_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não é possível excluir o produto '{prod.name}' ({prod.sku}) pois ele está registrado em {po_items_count} item(ns) de Ordem de Compra (PO). Exclua as ordens de teste vinculadas primeiro ou inative o produto."
        )

    # 2. Verifica vínculos em Cotações (RFQ)
    quote_items_count = db.query(purchasing_models.SupplierQuoteItem).filter(
        purchasing_models.SupplierQuoteItem.product_id == product_id
    ).count()
    if quote_items_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não é possível excluir o produto '{prod.name}' ({prod.sku}) pois ele possui propostas de fornecedores vinculadas em Cotações (RFQ). Exclua as cotações primeiro ou inative o produto."
        )

    # 3. Verifica vínculos em Solicitações de Compra
    pr_items_count = db.query(purchasing_models.PurchaseRequestItem).filter(
        purchasing_models.PurchaseRequestItem.product_id == product_id
    ).count()
    if pr_items_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não é possível excluir o produto '{prod.name}' ({prod.sku}) pois ele consta em {pr_items_count} Solicitação(ões) de Compra. Exclua as solicitações primeiro ou inative o produto."
        )

    try:
        repository.delete_product(db, prod)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não foi possível excluir o produto '{prod.name}' devido a restrições relacionais com outros registros."
        )



def list_products(
    db: Session, 
    organization_id: uuid.UUID, 
    category_id: uuid.UUID | None = None
) -> list[Product]:
    return repository.list_products(db, organization_id, category_id)


def get_product(db: Session, product_id: uuid.UUID, organization_id: uuid.UUID) -> Product:
    prod = repository.get_product_by_id(db, product_id, organization_id)
    if not prod:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado.")
    return prod


# ==============================================================================
# 3. GESTÃO DE ESTOQUE FÍSICO & AJUSTES DE INVENTÁRIO
# ==============================================================================

def adjust_stock(
    db: Session, 
    organization_id: uuid.UUID, 
    user_id: uuid.UUID | None, 
    payload: StockAdjustmentCreate
) -> StockMovement:
    """
    Realiza a movimentação manual auditada de estoque:
    1. Entrada por Nota Fiscal ('invoice_entry')
    2. Baixa por Perda / Avaria / Consumo ('manual_loss' / 'remove_stock')
    3. Conciliação de Inventário Físico ('reconciliation' / 'set_balance')
    4. Entrada Rápida de Ajuste ('add_stock')
    """
    prod = repository.get_product_by_id(db, payload.product_id, organization_id)
    if not prod:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado no catálogo.")

    old_balance = Decimal(str(prod.current_stock or 0))
    adj_qty = Decimal(str(payload.quantity))
    unit_cost = Decimal(str(payload.unit_cost or prod.reference_price or 0))

    if payload.adjustment_type in ["invoice_entry", "add_stock"]:
        if adj_qty <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A quantidade de entrada deve ser maior que zero.")
        new_balance = old_balance + adj_qty
        movement_type = "in_invoice" if payload.adjustment_type == "invoice_entry" else "in_adjustment"
        movement_qty = adj_qty
        
        doc_parts = []
        if payload.invoice_number:
            doc_parts.append(f"NF: {payload.invoice_number.strip()}")
        if payload.supplier_name:
            doc_parts.append(f"Forn: {payload.supplier_name.strip()}")
        if payload.batch_number:
            doc_parts.append(f"Lote: {payload.batch_number.strip()}")
        if payload.expiry_date:
            doc_parts.append(f"Val: {payload.expiry_date.strip()}")
        
        reference_doc = " | ".join(doc_parts) if doc_parts else (payload.reason or "Entrada Avulsa de Mercadoria")
        notes_detail = f"Entrada física (+{adj_qty} {prod.unit_of_measure}). Saldo: {old_balance} -> {new_balance}. {payload.notes or ''}".strip()

    elif payload.adjustment_type in ["manual_loss", "remove_stock"]:
        if adj_qty <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A quantidade a baixar deve ser maior que zero.")
        if adj_qty > old_balance:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail=f"A quantidade a baixar ({adj_qty}) não pode ser maior que o saldo físico atual em estoque ({old_balance} {prod.unit_of_measure})."
            )
        new_balance = max(Decimal("0.0000"), old_balance - adj_qty)
        movement_type = "out_loss" if (payload.reason and any(k in (payload.reason or "").lower() for k in ["avaria", "validade", "perda", "quebra", "descarte"])) else "out_adjustment"
        movement_qty = adj_qty
        reference_doc = payload.reason or "Baixa Técnica de Estoque"
        notes_detail = f"Baixa de estoque (-{adj_qty} {prod.unit_of_measure}). Saldo: {old_balance} -> {new_balance}. Motivo: {payload.reason or 'Não informado'}. Justificativa: {payload.notes or ''}".strip()

    elif payload.adjustment_type in ["reconciliation", "set_balance"]:
        new_balance = max(Decimal("0.0000"), adj_qty)
        diff = new_balance - old_balance
        if diff >= 0:
            movement_type = "in_reconciliation"
            movement_qty = diff
            diff_label = f"+{diff} {prod.unit_of_measure} (Sobra)"
        else:
            movement_type = "out_reconciliation"
            movement_qty = abs(diff)
            diff_label = f"{diff} {prod.unit_of_measure} (Falta/Quebra)"

        auditor_info = f"Auditor: {payload.auditor_name.strip()}" if payload.auditor_name else "Inventário Físico"
        reference_doc = f"Conciliação • {auditor_info}"
        notes_detail = f"Balanço Físico: Saldo anterior {old_balance} -> Contado {new_balance} ({diff_label}). Motivo: {payload.reason or 'Contagem Periódica'}. Justificativa: {payload.notes or ''}".strip()

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de movimentação '{payload.adjustment_type}' inválido. Use 'invoice_entry', 'manual_loss' ou 'reconciliation'."
        )

    # 1. Atualiza o saldo físico do produto
    prod.current_stock = new_balance
    if unit_cost > 0:
        prod.reference_price = unit_cost
    repository.update_product(db, prod)

    # 2. Registra o evento no histórico de auditoria
    movement = StockMovement(
        organization_id=organization_id,
        product_id=prod.id,
        movement_type=movement_type,
        quantity=movement_qty,
        unit_cost=unit_cost,
        balance_after=new_balance,
        reference_doc=reference_doc,
        invoice_attachment=payload.invoice_attachment,
        notes=notes_detail,
        created_by_id=user_id
    )
    saved_movement = repository.create_stock_movement(db, movement)
    logger.info(f"📦 [INVENTORY] Movimentação em '{prod.name}' ({prod.sku}): {old_balance} -> {new_balance} {prod.unit_of_measure} [{movement_type}] por user {user_id}")
    
    return saved_movement



def list_movements(
    db: Session, 
    organization_id: uuid.UUID, 
    product_id: uuid.UUID | None = None,
    limit: int = 100
) -> list[StockMovement]:
    return repository.list_stock_movements(db, organization_id, product_id, limit)


# ==============================================================================
# 4. PONTOS DE INTEGRAÇÃO DESACOPLADA (PURCHASING <-> INVENTORY)
# ==============================================================================

def register_purchase_receipt(
    db: Session,
    organization_id: uuid.UUID,
    user_id: uuid.UUID | None,
    product_id: uuid.UUID,
    quantity: Decimal,
    unit_cost: Decimal,
    reference_doc: str,
    invoice_attachment: str | None = None,
    notes: str | None = None
) -> StockMovement:
    """
    Chamado pelo módulo de Compras quando uma Ordem de Compra (PO) é recebida no almoxarifado.
    Incrementa o saldo físico e gera o registro de entrada 'in_purchase'.
    """
    prod = repository.get_product_by_id(db, product_id, organization_id)
    if not prod:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Produto {product_id} não encontrado no estoque.")

    old_balance = Decimal(str(prod.current_stock or 0))
    entry_qty = Decimal(str(quantity))
    new_balance = old_balance + entry_qty

    # Atualiza o saldo físico
    prod.current_stock = new_balance
    repository.update_product(db, prod)

    # Cria movimentação de entrada
    movement = StockMovement(
        organization_id=organization_id,
        product_id=prod.id,
        movement_type="in_purchase",
        quantity=entry_qty,
        unit_cost=Decimal(str(unit_cost)),
        balance_after=new_balance,
        reference_doc=reference_doc,
        invoice_attachment=invoice_attachment,
        notes=notes or f"Entrada de mercadoria recebida via {reference_doc}",
        created_by_id=user_id
    )
    saved_movement = repository.create_stock_movement(db, movement)
    logger.info(f"🚚 [INVENTORY ENTRY] Recebimento de PO em '{prod.name}': +{entry_qty} -> Novo Saldo: {new_balance} {prod.unit_of_measure}")
    return saved_movement


def get_replenishment_candidates(
    db: Session, 
    organization_id: uuid.UUID
) -> list[Product]:
    """
    Chamado pelo motor de sugestões de compra para obter produtos que estão abaixo do estoque mínimo.
    """
    return repository.get_products_below_replenishment_point(db, organization_id)
