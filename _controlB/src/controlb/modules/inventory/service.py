"""
modules/inventory/service.py - Camada de Regras de Negócio do Módulo de Estoque e Inventário (Inventory Domain)

Contém a lógica de:
1. Gestão do Catálogo de Produtos e Categorias.
2. Ajuste manual de estoque e contagens físicas de inventário.
3. Extrato e auditoria de movimentações de estoque.
4. Integração desacoplada para entrada de compras e consulta de ponto de ressuprimento.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from controlb.logger import logger
from controlb.modules.documents import schemas as document_schemas
from controlb.modules.documents import service as documents_service
from controlb.modules.inventory import repository
from controlb.modules.inventory.models import (
    InventoryReceipt,
    InventoryDelivery,
    InventoryDeliveryItem,
    InventoryLocation,
    InventoryBalance,
    InventoryTransfer,
    InventoryTransferItem,
    Product,
    ProductCategory,
    StockMovement,
    StockReservation,
    StockReservationItem,
    InventoryImportBatch,
    InventoryImportItem,
)
from controlb.modules.inventory.schemas import (
    ProductAvailabilityResponse,
    ProductCategoryCreate,
    ProductCategoryUpdate,
    ProductCreate,
    ProductUpdate,
    StockAdjustmentCreate,
    StockMovementResponse,
    InventoryLocationCreate,
    InventoryTransferCreate,
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


def ensure_default_location(
    db: Session, organization_id: uuid.UUID
) -> InventoryLocation:
    location = repository.get_default_location(db, organization_id)
    if location:
        return location
    return repository.create_location(
        db,
        InventoryLocation(
            organization_id=organization_id,
            code="PRINCIPAL",
            name="Estoque Principal",
            description="Localização padrão para compatibilidade com o saldo global legado.",
            is_default=True,
            is_active=True,
        ),
    )


def sync_default_location_balance(
    db: Session,
    organization_id: uuid.UUID,
    product: Product,
) -> InventoryBalance:
    """Mantém a projeção por localização alinhada aos fluxos legados de saldo global."""
    location = ensure_default_location(db, organization_id)
    other_quantity = sum(
        (
            Decimal(str(item.quantity or 0))
            for item in repository.list_balances(db, organization_id, product.id)
            if item.location_id != location.id
        ),
        Decimal("0"),
    )
    projected_default = Decimal(str(product.current_stock or 0)) - other_quantity
    if projected_default < 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Os saldos por localização excedem o saldo global do produto.",
        )
    balance = repository.get_balance_for_update(
        db, organization_id, product.id, location.id
    )
    if not balance:
        balance = InventoryBalance(
            organization_id=organization_id,
            product_id=product.id,
            location_id=location.id,
            quantity=projected_default,
        )
        db.add(balance)
    else:
        balance.quantity = projected_default
    db.flush()
    return balance


def record_stock_movement(
    db: Session,
    organization_id: uuid.UUID,
    *,
    product_id: uuid.UUID,
    movement_type: str,
    quantity: Decimal,
    balance_after: Decimal,
    unit_cost: Decimal = Decimal("0.0000"),
    location_id: uuid.UUID | None = None,
    source_location_id: uuid.UUID | None = None,
    destination_location_id: uuid.UUID | None = None,
    location_balance_after: Decimal | None = None,
    receipt_id: uuid.UUID | None = None,
    delivery_id: uuid.UUID | None = None,
    transfer_id: uuid.UUID | None = None,
    fiscal_document_id: uuid.UUID | None = None,
    payable_id: uuid.UUID | None = None,
    source_document_id: uuid.UUID | None = None,
    reference_doc: str | None = None,
    invoice_attachment: str | None = None,
    notes: str | None = None,
    created_by_id: uuid.UUID | None = None,
    current_user: Any = None,
) -> StockMovement:
    """
    Cria a movimentação de estoque (Kardex) e a vincula ao documento que a
    originou. Quando se trata de um ajuste avulso, sem documento de origem, é
    criado um cabeçalho STOCK_MOVEMENT próprio.
    """
    movement_id = uuid.uuid4()
    prod = repository.get_product_by_id(db, product_id, organization_id)
    prod_label = f"{prod.name} ({prod.sku})" if prod else str(product_id)
    resp_id = created_by_id or (getattr(current_user, "id", None) if current_user else None)

    if source_document_id:
        doc = documents_service.get_document(
            db, source_document_id, organization_id
        )
    else:
        doc = documents_service.create_document(
            db,
            organization_id=organization_id,
            payload=document_schemas.DocumentCreate(
                category="inventory.movement",
                document_type="STOCK_MOVEMENT",
                native_id=movement_id,
                title=f"Movimentação de Estoque: {movement_type} - {prod_label}",
                current_status="POSTED",
                description=notes or f"Movimentação {movement_type} de {quantity} un em {prod_label}",
                origin_module="INVENTORY",
                responsible_id=resp_id,
                payload={
                    "product_id": str(product_id),
                    "movement_type": movement_type,
                    "quantity": str(quantity),
                    "unit_cost": str(unit_cost),
                    "balance_after": str(balance_after),
                    "location_id": str(location_id) if location_id else None,
                    "source_location_id": str(source_location_id) if source_location_id else None,
                    "destination_location_id": str(destination_location_id) if destination_location_id else None,
                    "receipt_id": str(receipt_id) if receipt_id else None,
                    "delivery_id": str(delivery_id) if delivery_id else None,
                    "transfer_id": str(transfer_id) if transfer_id else None,
                    "fiscal_document_id": str(fiscal_document_id) if fiscal_document_id else None,
                    "payable_id": str(payable_id) if payable_id else None,
                },
            ),
            current_user=current_user,
        )

    # Persiste o evento apontando para o documento canônico de origem.
    movement = StockMovement(
        id=movement_id,
        organization_id=organization_id,
        product_id=product_id,
        document_id=doc.id,
        receipt_id=receipt_id,
        delivery_id=delivery_id,
        transfer_id=transfer_id,
        location_id=location_id,
        source_location_id=source_location_id,
        destination_location_id=destination_location_id,
        location_balance_after=location_balance_after,
        fiscal_document_id=fiscal_document_id,
        payable_id=payable_id,
        movement_type=movement_type,
        quantity=quantity,
        unit_cost=unit_cost,
        balance_after=balance_after,
        reference_doc=reference_doc or doc.document_number,
        invoice_attachment=invoice_attachment,
        notes=notes,
        created_by_id=resp_id,
    )
    return repository.create_stock_movement(db, movement)


def list_inventory_locations(
    db: Session, organization_id: uuid.UUID
) -> list[InventoryLocation]:
    ensure_default_location(db, organization_id)
    return repository.list_locations(db, organization_id)


def create_inventory_location(
    db: Session,
    organization_id: uuid.UUID,
    payload: InventoryLocationCreate,
) -> InventoryLocation:
    code = payload.code.strip().upper()
    if any(location.code == code for location in repository.list_locations(db, organization_id)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe uma localização de estoque com este código.",
        )
    return repository.create_location(
        db,
        InventoryLocation(
            organization_id=organization_id,
            code=code,
            name=payload.name.strip(),
            description=payload.description,
            is_default=False,
            is_active=True,
        ),
    )


def list_inventory_balances(
    db: Session,
    organization_id: uuid.UUID,
    product_id: uuid.UUID | None = None,
) -> list[InventoryBalance]:
    ensure_default_location(db, organization_id)
    return repository.list_balances(db, organization_id, product_id)


def create_inventory_transfer(
    db: Session,
    organization_id: uuid.UUID,
    current_user,
    payload: InventoryTransferCreate,
) -> InventoryTransfer:
    """Move saldos entre localizações sem alterar o saldo agregado do produto."""
    if payload.source_location_id == payload.destination_location_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A origem e o destino da transferência devem ser diferentes.",
        )
    source = repository.get_location(
        db, payload.source_location_id, organization_id, for_update=True
    )
    destination = repository.get_location(
        db, payload.destination_location_id, organization_id, for_update=True
    )
    if not source or not destination:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A localização de origem ou destino é inválida.",
        )

    requested: dict[uuid.UUID, Decimal] = {}
    for item in payload.items:
        requested[item.product_id] = requested.get(
            item.product_id, Decimal("0")
        ) + Decimal(str(item.quantity))
    products = repository.lock_products_by_ids(
        db, list(requested), organization_id
    )
    products_by_id = {product.id: product for product in products}
    if set(products_by_id) != set(requested):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Um dos produtos da transferência não foi encontrado.",
        )

    source_balances: dict[uuid.UUID, InventoryBalance] = {}
    destination_balances: dict[uuid.UUID, InventoryBalance] = {}
    for product_id in sorted(requested, key=str):
        product = products_by_id[product_id]
        if source.is_default:
            sync_default_location_balance(db, organization_id, product)
        source_balance = repository.get_balance_for_update(
            db, organization_id, product_id, source.id
        )
        if not source_balance or source_balance.quantity < requested[product_id]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Saldo insuficiente de {product.sku} na localização {source.code}.",
            )
        destination_balance = repository.get_balance_for_update(
            db, organization_id, product_id, destination.id
        )
        if not destination_balance:
            destination_balance = InventoryBalance(
                organization_id=organization_id,
                product_id=product_id,
                location_id=destination.id,
                quantity=Decimal("0"),
            )
            db.add(destination_balance)
            db.flush()
        source_balances[product_id] = source_balance
        destination_balances[product_id] = destination_balance

    transfer_id = uuid.uuid4()
    completed_at = _utcnow()
    document = documents_service.create_document(
        db,
        organization_id=organization_id,
        payload=document_schemas.DocumentCreate(
            category="inventory.transfer",
            document_type="INVENTORY_TRANSFER",
            native_id=transfer_id,
            title="Transferência de Estoque",
            current_status="COMPLETED",
            description=payload.notes,
            origin_module="INVENTORY",
            responsible_id=current_user.id,
            payload={
                "source_location_id": str(source.id),
                "destination_location_id": str(destination.id),
            },
            issued_at=completed_at,
            completed_at=completed_at,
        ),
        current_user=current_user,
    )
    document.title = f"Transferência {document.document_number}"
    transfer = InventoryTransfer(
        id=transfer_id,
        organization_id=organization_id,
        document_id=document.id,
        transfer_number=document.document_number,
        source_location_id=source.id,
        destination_location_id=destination.id,
        status="COMPLETED",
        completed_by_id=current_user.id,
        completed_at=completed_at,
        notes=payload.notes,
    )
    for product_id in sorted(requested, key=str):
        quantity = requested[product_id]
        source_balance = source_balances[product_id]
        destination_balance = destination_balances[product_id]
        source_balance.quantity -= quantity
        destination_balance.quantity += quantity
        transfer.items.append(
            InventoryTransferItem(
                organization_id=organization_id,
                product_id=product_id,
                quantity=quantity,
            )
        )
    repository.create_transfer(db, transfer)

    for item in transfer.items:
        product = products_by_id[item.product_id]
        source_balance = source_balances[item.product_id]
        destination_balance = destination_balances[item.product_id]
        record_stock_movement(
            db,
            organization_id,
            product_id=product.id,
            transfer_id=transfer.id,
            source_document_id=transfer.document_id,
            source_location_id=source.id,
            destination_location_id=destination.id,
            location_id=source.id,
            movement_type="transfer_out",
            quantity=item.quantity,
            unit_cost=Decimal(str(product.cost_price or 0)),
            balance_after=Decimal(str(product.current_stock or 0)),
            location_balance_after=source_balance.quantity,
            reference_doc=transfer.transfer_number,
            notes=payload.notes,
            created_by_id=current_user.id,
            current_user=current_user,
        )
        record_stock_movement(
            db,
            organization_id,
            product_id=product.id,
            transfer_id=transfer.id,
            source_document_id=transfer.document_id,
            source_location_id=source.id,
            destination_location_id=destination.id,
            location_id=destination.id,
            movement_type="transfer_in",
            quantity=item.quantity,
            unit_cost=Decimal(str(product.cost_price or 0)),
            balance_after=Decimal(str(product.current_stock or 0)),
            location_balance_after=destination_balance.quantity,
            reference_doc=transfer.transfer_number,
            notes=payload.notes,
            created_by_id=current_user.id,
            current_user=current_user,
        )
    db.flush()
    return transfer


def list_inventory_transfers(
    db: Session, organization_id: uuid.UUID
) -> list[InventoryTransfer]:
    return repository.list_transfers(db, organization_id)


def get_inventory_transfer(
    db: Session, organization_id: uuid.UUID, transfer_id: uuid.UUID
) -> InventoryTransfer:
    transfer = repository.get_transfer(db, transfer_id, organization_id)
    if not transfer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transferência de estoque não encontrada.",
        )
    return transfer


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
    default_balance = sync_default_location_balance(db, organization_id, created_prod)

    # Se foi iniciado com saldo positivo, registra movimentação inicial de inventário
    if payload.current_stock > 0:
        record_stock_movement(
            db,
            organization_id,
            product_id=created_prod.id,
            location_id=default_balance.location_id,
            movement_type="in_adjustment",
            quantity=payload.current_stock,
            unit_cost=payload.reference_price,
            balance_after=payload.current_stock,
            location_balance_after=default_balance.quantity,
            reference_doc="Saldo Inicial de Cadastro",
            notes="Registro de implantação de saldo inicial do produto.",
        )

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

    updated = repository.update_product(db, prod)
    if payload.current_stock is not None:
        sync_default_location_balance(db, organization_id, updated)
    return updated


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
        
        # Mapeamento do tipo de saída explícito
        if payload.outbound_reason == "loss_damage":
            movement_type = "out_loss"
        elif payload.outbound_reason == "internal_consumption":
            movement_type = "out_internal_consumption"
        elif payload.outbound_reason == "supplier_return":
            movement_type = "out_return_supplier"
        elif payload.outbound_reason == "inventory_adjustment":
            movement_type = "out_adjustment"
        else:
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
    default_balance = sync_default_location_balance(db, organization_id, prod)

    # 2. Registra o evento no histórico de auditoria com documento canônico
    saved_movement = record_stock_movement(
        db,
        organization_id,
        product_id=prod.id,
        location_id=default_balance.location_id,
        fiscal_document_id=payload.fiscal_document_id,
        movement_type=movement_type,
        quantity=movement_qty,
        unit_cost=unit_cost,
        balance_after=new_balance,
        location_balance_after=default_balance.quantity,
        reference_doc=reference_doc,
        invoice_attachment=payload.invoice_attachment,
        notes=notes_detail,
        created_by_id=user_id,
    )
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

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aggregate_order_items(order) -> dict[uuid.UUID, Decimal]:
    requested: dict[uuid.UUID, Decimal] = {}
    for item in order.items:
        quantity = Decimal(str(item.quantity))
        if quantity <= 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="O pedido possui item com quantidade inválida para reserva.",
            )
        requested[item.product_id] = requested.get(
            item.product_id, Decimal("0.0000")
        ) + quantity
    if not requested:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Não é possível reservar um pedido sem itens.",
        )
    return requested


def lock_products_and_get_availability(
    db: Session,
    organization_id: uuid.UUID,
    product_ids: list[uuid.UUID],
) -> tuple[list[Product], dict[uuid.UUID, Decimal], dict[uuid.UUID, Decimal]]:
    """Bloqueia produtos em ordem estável e calcula físico - reservas RESERVED."""
    stable_ids = sorted(set(product_ids), key=str)
    products = repository.lock_products_by_ids(db, stable_ids, organization_id)
    products_by_id = {product.id: product for product in products}
    missing = [product_id for product_id in stable_ids if product_id not in products_by_id]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Um dos produtos não foi encontrado na organização.",
        )
    inactive = [product.sku for product in products if not product.is_active]
    if inactive:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Produtos inativos não podem ser reservados ou vendidos: {', '.join(inactive)}.",
        )

    reserved = repository.get_reserved_quantities(db, organization_id, stable_ids)
    available = {
        product.id: Decimal(str(product.current_stock or 0))
        - reserved.get(product.id, Decimal("0.0000"))
        for product in products
    }
    return products, available, reserved


def get_product_availability(
    db: Session,
    organization_id: uuid.UUID,
    product_id: uuid.UUID,
) -> ProductAvailabilityResponse:
    product = repository.get_product_by_id(db, product_id, organization_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Produto não encontrado.",
        )
    reserved = repository.get_reserved_quantities(db, organization_id, [product.id]).get(
        product.id, Decimal("0.0000")
    )
    current = Decimal(str(product.current_stock or 0))
    return ProductAvailabilityResponse(
        product_id=product.id,
        sku=product.sku,
        product_name=product.name,
        current_stock=current,
        reserved_stock=reserved,
        available_stock=current - reserved,
    )


def get_stock_reservation(
    db: Session,
    organization_id: uuid.UUID,
    reservation_id: uuid.UUID,
) -> StockReservation:
    reservation = repository.get_reservation_by_id(db, reservation_id, organization_id)
    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reserva de estoque não encontrada.",
        )
    return reservation


def get_sales_order_reservation(
    db: Session,
    organization_id: uuid.UUID,
    sales_order_id: uuid.UUID,
) -> StockReservation:
    reservation = repository.get_reservation_by_sales_order(
        db, sales_order_id, organization_id
    )
    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="O pedido ainda não possui reserva de estoque.",
        )
    return reservation


def _ensure_order_document(db: Session, order, organization_id: uuid.UUID):
    if order.document_id:
        document = documents_service.get_document(db, order.document_id, organization_id)
        if document.document_type != "SALES_ORDER" or document.native_id != order.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="O cabeçalho documental vinculado ao pedido é inconsistente.",
            )
    else:
        document = documents_service.ensure_document(
            db,
            organization_id=organization_id,
            category="sales.order",
            document_type="SALES_ORDER",
            native_id=order.id,
            document_number=order.order_number,
            current_status=order.status,
            origin_module="SALES",
            created_by_id=order.created_by_id,
            issued_at=order.created_at,
        )
    document.category = "sales.order"
    document.origin_module = "SALES"
    order.document_id = document.id
    order.order_number = document.document_number
    order.status = document.current_status
    return document


def _record_reserved_events(
    db: Session,
    *,
    organization_id: uuid.UUID,
    order,
    reservation: StockReservation,
    actor_id: uuid.UUID | None,
) -> None:
    order_document = _ensure_order_document(db, order, organization_id)
    reservation_document = documents_service.ensure_document(
        db,
        organization_id=organization_id,
        category="inventory.reservation",
        document_type="STOCK_RESERVATION",
        native_id=reservation.id,
        document_number=reservation.reservation_number,
        current_status=reservation.status,
        created_by_id=reservation.created_by_id,
        issued_at=reservation.created_at,
    )
    reservation.document_id = reservation_document.id
    reservation_document.category = "inventory.reservation"
    reservation_document.origin_module = "INVENTORY"
    reservation.reservation_number = reservation_document.document_number
    documents_service.relate_documents(
        db,
        organization_id=organization_id,
        parent_document=order_document,
        child_document=reservation_document,
        relation_type="RESERVED_BY",
        created_by_id=actor_id,
        relation_metadata={"sales_order_id": str(order.id)},
    )
    metadata = {
        "sales_order_id": str(order.id),
        "reservation_id": str(reservation.id),
        "status_version": reservation.status_version,
    }
    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=reservation_document,
        event_type="RESERVED",
        previous_status="RELEASED" if reservation.status_version > 1 else None,
        new_status="RESERVED",
        created_by_id=actor_id,
        event_metadata=metadata,
        idempotency_key=(
            f"stock-reservation:{reservation.id}:status:"
            f"{reservation.status_version}:reserved"
        ),
    )
    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=order_document,
        event_type="STOCK_RESERVED",
        created_by_id=actor_id,
        event_metadata=metadata,
        idempotency_key=(
            f"sales-order:{order.id}:stock-reservation:{reservation.id}:"
            f"status:{reservation.status_version}:reserved"
        ),
    )


def reserve_sales_order(
    db: Session,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    sales_order_id: uuid.UUID,
) -> StockReservation:
    """Reserva todos os itens ou não reserva nenhum; nunca baixa current_stock."""
    order = repository.get_sales_order_for_update(db, sales_order_id, organization_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pedido de venda não encontrado.",
        )
    _ensure_order_document(db, order, organization_id)
    if order.status != "CONFIRMED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Somente pedidos CONFIRMED podem reservar estoque.",
        )
    if order.credit_status in {"PENDING", "REJECTED"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O pedido aguarda liberação de crédito antes da reserva de estoque.",
        )
    if order.commercial_approval_status in {"PENDING", "REJECTED"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O pedido aguarda aprovação comercial antes da reserva de estoque.",
        )
    if order.delivery_status not in {"PENDING", "RESERVED"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O pedido já avançou para separação, expedição ou entrega.",
        )

    existing = repository.get_reservation_by_sales_order(
        db, sales_order_id, organization_id, for_update=True
    )
    if existing and existing.status == "RESERVED":
        order.delivery_status = "RESERVED"
        db.flush()
        return existing

    requested = _aggregate_order_items(order)
    products, available, _ = lock_products_and_get_availability(
        db, organization_id, list(requested)
    )
    products_by_id = {product.id: product for product in products}
    shortages = [
        (
            products_by_id[product_id],
            quantity,
            available[product_id],
        )
        for product_id, quantity in sorted(requested.items(), key=lambda item: str(item[0]))
        if quantity > available[product_id]
    ]
    if shortages:
        details = "; ".join(
            f"{product.sku}: solicitado {quantity}, disponível {available_quantity}"
            for product, quantity, available_quantity in shortages
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Estoque disponível insuficiente para reserva integral. {details}.",
        )

    if existing:
        existing.items.clear()
        db.flush()
        existing.status = "RESERVED"
        existing.status_version += 1
        existing.released_by_id = None
        existing.released_at = None
        existing.updated_at = _utcnow()
        reservation = existing
    else:
        reservation_id = uuid.uuid4()
        reservation_document = documents_service.create_document(
            db,
            organization_id=organization_id,
            payload=document_schemas.DocumentCreate(
                category="inventory.reservation",
                document_type="STOCK_RESERVATION",
                native_id=reservation_id,
                title="Reserva de Estoque",
                current_status="RESERVED",
                origin_module="INVENTORY",
                responsible_id=actor_id,
                payload={"sales_order_id": str(order.id)},
            ),
        )
        reservation_document.title = (
            f"Reserva de Estoque {reservation_document.document_number}"
        )
        reservation = StockReservation(
            id=reservation_id,
            organization_id=organization_id,
            sales_order_id=order.id,
            document_id=reservation_document.id,
            reservation_number=reservation_document.document_number,
            status="RESERVED",
            status_version=1,
            created_by_id=actor_id,
        )

    for product_id, quantity in sorted(requested.items(), key=lambda item: str(item[0])):
        reservation.items.append(
            StockReservationItem(
                organization_id=organization_id,
                product_id=product_id,
                quantity=quantity,
                product=products_by_id[product_id],
            )
        )

    repository.save_reservation(db, reservation)
    order.delivery_status = "RESERVED"
    _record_reserved_events(
        db,
        organization_id=organization_id,
        order=order,
        reservation=reservation,
        actor_id=actor_id,
    )
    db.flush()
    return reservation


def _release_locked_reservation(
    db: Session,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    order,
    reservation: StockReservation,
    delivery_status_after: str,
) -> StockReservation:
    if reservation.status == "RELEASED":
        order.delivery_status = delivery_status_after
        db.flush()
        return reservation

    reservation.status = "RELEASED"
    reservation.status_version += 1
    reservation.released_by_id = actor_id
    reservation.released_at = _utcnow()
    reservation.updated_at = reservation.released_at
    order.delivery_status = delivery_status_after

    order_document = _ensure_order_document(db, order, organization_id)
    reservation_document = documents_service.ensure_document(
        db,
        organization_id=organization_id,
        category="inventory.reservation",
        document_type="STOCK_RESERVATION",
        native_id=reservation.id,
        document_number=reservation.reservation_number,
        current_status="RELEASED",
        created_by_id=reservation.created_by_id,
        issued_at=reservation.created_at,
    )
    reservation_document.category = "inventory.reservation"
    reservation_document.origin_module = "INVENTORY"
    reservation.reservation_number = reservation_document.document_number
    metadata = {
        "sales_order_id": str(order.id),
        "reservation_id": str(reservation.id),
        "status_version": reservation.status_version,
    }
    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=reservation_document,
        event_type="RELEASED",
        previous_status="RESERVED",
        new_status="RELEASED",
        created_by_id=actor_id,
        event_metadata=metadata,
        idempotency_key=(
            f"stock-reservation:{reservation.id}:status:"
            f"{reservation.status_version}:released"
        ),
    )
    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=order_document,
        event_type="STOCK_RESERVATION_RELEASED",
        created_by_id=actor_id,
        event_metadata=metadata,
        idempotency_key=(
            f"sales-order:{order.id}:stock-reservation:{reservation.id}:"
            f"status:{reservation.status_version}:released"
        ),
    )
    repository.save_reservation(db, reservation)
    return reservation


def release_stock_reservation(
    db: Session,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    reservation_id: uuid.UUID,
) -> StockReservation:
    peek = repository.get_reservation_by_id(db, reservation_id, organization_id)
    if not peek:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reserva de estoque não encontrada.",
        )
    order = repository.get_sales_order_for_update(
        db, peek.sales_order_id, organization_id
    )
    if not order:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O pedido vinculado à reserva não está disponível.",
        )
    _ensure_order_document(db, order, organization_id)
    reservation = repository.get_reservation_by_id(
        db, reservation_id, organization_id, for_update=True
    )
    if not reservation or reservation.sales_order_id != order.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A reserva mudou durante a operação; tente novamente.",
        )
    if reservation.status == "RELEASED":
        return reservation
    if order.status != "CONFIRMED" or order.delivery_status != "RESERVED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A liberação manual exige pedido CONFIRMED com entrega RESERVED; "
                "pedidos em separação, expedição ou entrega não podem retroceder."
            ),
        )
    return _release_locked_reservation(
        db,
        organization_id=organization_id,
        actor_id=actor_id,
        order=order,
        reservation=reservation,
        delivery_status_after="PENDING",
    )


def release_sales_order_reservation(
    db: Session,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    sales_order_id: uuid.UUID,
    *,
    locked_order=None,
    delivery_status_after: str = "PENDING",
) -> StockReservation | None:
    """Integração interna idempotente usada pelo cancelamento do pedido."""
    order = locked_order or repository.get_sales_order_for_update(
        db, sales_order_id, organization_id
    )
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pedido de venda não encontrado.",
        )
    _ensure_order_document(db, order, organization_id)
    reservation = repository.get_reservation_by_sales_order(
        db, sales_order_id, organization_id, for_update=True
    )
    if not reservation:
        order.delivery_status = delivery_status_after
        db.flush()
        return None
    return _release_locked_reservation(
        db,
        organization_id=organization_id,
        actor_id=actor_id,
        order=order,
        reservation=reservation,
        delivery_status_after=delivery_status_after,
    )


def _relate_delivery_to_fiscal_document(
    db: Session,
    *,
    organization_id: uuid.UUID,
    delivery: InventoryDelivery,
    fiscal_document,
    actor_id: uuid.UUID | None,
) -> None:
    from controlb.modules.finance.service import get_fiscal_document_header

    delivery_document = documents_service.get_document(
        db, delivery.document_id, organization_id
    )
    fiscal_header = get_fiscal_document_header(
        db, fiscal_document, organization_id
    )
    delivery.fiscal_document_id = fiscal_document.id
    documents_service.relate_documents(
        db,
        organization_id=organization_id,
        parent_document=delivery_document,
        child_document=fiscal_header,
        relation_type="DOCUMENTED_BY",
        created_by_id=actor_id,
        relation_metadata={"sales_order_id": str(delivery.sales_order_id)},
    )


def link_sales_order_delivery_to_fiscal_document(
    db: Session,
    *,
    organization_id: uuid.UUID,
    sales_order_id: uuid.UUID,
    fiscal_document,
    actor_id: uuid.UUID | None,
) -> InventoryDelivery | None:
    """Completa o elo fiscal quando o faturamento ocorre depois da expedição."""
    delivery = repository.get_delivery_by_sales_order(
        db, sales_order_id, organization_id, for_update=True
    )
    if not delivery:
        return None
    _relate_delivery_to_fiscal_document(
        db,
        organization_id=organization_id,
        delivery=delivery,
        fiscal_document=fiscal_document,
        actor_id=actor_id,
    )
    db.flush()
    return delivery


def get_sales_order_delivery(
    db: Session,
    organization_id: uuid.UUID,
    sales_order_id: uuid.UUID,
) -> InventoryDelivery:
    delivery = repository.get_delivery_by_sales_order(
        db, sales_order_id, organization_id
    )
    if not delivery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entrega do pedido de venda não encontrada.",
        )
    return delivery


def get_inventory_delivery(
    db: Session,
    organization_id: uuid.UUID,
    delivery_id: uuid.UUID,
) -> InventoryDelivery:
    delivery = repository.get_delivery_by_id(db, delivery_id, organization_id)
    if not delivery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entrega não encontrada.",
        )
    return delivery


def dispatch_sales_order(
    db: Session,
    organization_id: uuid.UUID,
    current_user,
    sales_order_id: uuid.UUID,
    *,
    locked_order=None,
) -> InventoryDelivery:
    """Consome a reserva e registra a saída física integral uma única vez."""
    order = locked_order or repository.get_sales_order_for_update(
        db, sales_order_id, organization_id
    )
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pedido de venda não encontrado.",
        )
    order_document = _ensure_order_document(db, order, organization_id)
    existing = repository.get_delivery_by_sales_order(
        db, sales_order_id, organization_id, for_update=True
    )
    if existing:
        if existing.status in {"DISPATCHED", "DELIVERED"}:
            order.delivery_status = existing.status
            return existing
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A entrega existente não pode ser novamente despachada.",
        )
    if order.status != "CONFIRMED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Somente pedidos confirmados podem ser despachados.",
        )
    if order.delivery_status == "PENDING":
        reserve_sales_order(db, organization_id, current_user.id, order.id)
    if order.delivery_status != "RESERVED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O pedido precisa possuir uma reserva ativa antes do despacho.",
        )

    reservation = repository.get_reservation_by_sales_order(
        db, order.id, organization_id, for_update=True
    )
    if not reservation or reservation.status != "RESERVED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A reserva ativa do pedido não foi encontrada.",
        )

    products = repository.lock_products_by_ids(
        db, [item.product_id for item in reservation.items], organization_id
    )
    products_by_id = {product.id: product for product in products}
    default_balances: dict[uuid.UUID, InventoryBalance] = {}
    for item in reservation.items:
        product = products_by_id.get(item.product_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Um produto reservado não está mais disponível.",
            )
        default_balance = sync_default_location_balance(
            db, organization_id, product
        )
        default_balances[product.id] = default_balance
        if default_balance.quantity < item.quantity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "O Estoque Principal não comporta mais a expedição integral; "
                    "transfira o saldo necessário antes de despachar."
                ),
            )

    fiscal_document = None
    from controlb.modules.billing.models import Invoice
    from controlb.modules.finance.models import FiscalDocument

    invoice = db.scalar(
        select(Invoice)
        .where(
            Invoice.sales_order_id == order.id,
            Invoice.organization_id == organization_id,
            Invoice.fiscal_document_id.is_not(None),
        )
        .order_by(Invoice.created_at.desc())
    )
    if invoice and invoice.fiscal_document_id:
        fiscal_document = db.scalar(
            select(FiscalDocument).where(
                FiscalDocument.id == invoice.fiscal_document_id,
                FiscalDocument.organization_id == organization_id,
            )
        )

    dispatched_at = _utcnow()
    delivery_id = uuid.uuid4()
    delivery_document = documents_service.create_document(
        db,
        organization_id=organization_id,
        payload=document_schemas.DocumentCreate(
            category="inventory.delivery",
            document_type="DELIVERY",
            native_id=delivery_id,
            title="Entrega de Venda",
            current_status="DISPATCHED",
            description=order.notes,
            origin_module="INVENTORY",
            responsible_id=current_user.id,
            payload={
                "sales_order_id": str(order.id),
                "reservation_id": str(reservation.id),
                "customer_name": order.customer_name,
            },
            issued_at=dispatched_at,
        ),
        current_user=current_user,
    )
    delivery_document.title = f"Entrega {delivery_document.document_number}"
    delivery = InventoryDelivery(
        id=delivery_id,
        organization_id=organization_id,
        sales_order_id=order.id,
        reservation_id=reservation.id,
        document_id=delivery_document.id,
        fiscal_document_id=(fiscal_document.id if fiscal_document else None),
        delivery_number=delivery_document.document_number,
        status="DISPATCHED",
        stock_posted=True,
        dispatched_at=dispatched_at,
        created_by_id=current_user.id,
        notes=order.notes,
    )
    for item in reservation.items:
        delivery.items.append(
            InventoryDeliveryItem(
                organization_id=organization_id,
                product_id=item.product_id,
                quantity=item.quantity,
            )
        )
    repository.create_delivery(db, delivery)

    for item in reservation.items:
        product = products_by_id[item.product_id]
        new_balance = Decimal(str(product.current_stock or 0)) - item.quantity
        product.current_stock = new_balance
        default_balance = default_balances[product.id]
        default_balance.quantity -= item.quantity
        record_stock_movement(
            db,
            organization_id,
            product_id=product.id,
            delivery_id=delivery.id,
            source_document_id=delivery.document_id,
            location_id=default_balance.location_id,
            movement_type="out_sale",
            quantity=item.quantity,
            unit_cost=Decimal(str(product.cost_price or 0)),
            balance_after=new_balance,
            location_balance_after=default_balance.quantity,
            reference_doc=f"{delivery.delivery_number} / {order.order_number}",
            notes=f"Saída física do pedido {order.order_number}",
            created_by_id=current_user.id,
            current_user=current_user,
        )

    reservation.status = "CONSUMED"
    reservation.status_version += 1
    reservation.consumed_by_id = current_user.id
    reservation.consumed_at = dispatched_at
    reservation.updated_at = dispatched_at
    reservation_document = documents_service.get_document(
        db, reservation.document_id, organization_id
    )
    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=reservation_document,
        event_type="CONSUMED_BY_DISPATCH",
        previous_status="RESERVED",
        new_status="CONSUMED",
        created_by_id=current_user.id,
        event_metadata={"delivery_id": str(delivery.id)},
        idempotency_key=f"stock-reservation:{reservation.id}:consumed:{delivery.id}",
    )
    documents_service.relate_documents(
        db,
        organization_id=organization_id,
        parent_document=order_document,
        child_document=delivery_document,
        relation_type="FULFILLED_BY",
        created_by_id=current_user.id,
    )
    documents_service.relate_documents(
        db,
        organization_id=organization_id,
        parent_document=reservation_document,
        child_document=delivery_document,
        relation_type="FULFILLED_BY",
        created_by_id=current_user.id,
    )
    if fiscal_document:
        _relate_delivery_to_fiscal_document(
            db,
            organization_id=organization_id,
            delivery=delivery,
            fiscal_document=fiscal_document,
            actor_id=current_user.id,
        )

    order.delivery_status = "DISPATCHED"
    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=order_document,
        event_type="DISPATCHED",
        created_by_id=current_user.id,
        event_metadata={
            "delivery_id": str(delivery.id),
            "delivery_number": delivery.delivery_number,
        },
        idempotency_key=f"sales-order:{order.id}:dispatched:{delivery.id}",
    )
    db.flush()
    return delivery


def confirm_sales_order_delivery(
    db: Session,
    organization_id: uuid.UUID,
    current_user,
    sales_order_id: uuid.UUID,
    *,
    locked_order=None,
) -> InventoryDelivery:
    """Confirma o recebimento pelo cliente sem repetir a saída do estoque."""
    order = locked_order or repository.get_sales_order_for_update(
        db, sales_order_id, organization_id
    )
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pedido de venda não encontrado.",
        )
    delivery = repository.get_delivery_by_sales_order(
        db, sales_order_id, organization_id, for_update=True
    )
    if not delivery:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O pedido ainda não possui uma expedição registrada.",
        )
    if delivery.status == "DELIVERED":
        order.delivery_status = "DELIVERED"
        return delivery
    if delivery.status != "DISPATCHED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A expedição não está disponível para confirmação.",
        )

    delivered_at = _utcnow()
    delivery.status = "DELIVERED"
    delivery.delivered_at = delivered_at
    delivery.delivered_by_id = current_user.id
    delivery.updated_at = delivered_at
    order.delivery_status = "DELIVERED"
    delivery_document = documents_service.get_document(
        db, delivery.document_id, organization_id
    )
    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=delivery_document,
        event_type="DELIVERED",
        previous_status="DISPATCHED",
        new_status="DELIVERED",
        created_by_id=current_user.id,
        event_metadata={"sales_order_id": str(order.id)},
        idempotency_key=f"inventory-delivery:{delivery.id}:delivered",
    )
    order_document = _ensure_order_document(db, order, organization_id)
    documents_service.record_event(
        db,
        organization_id=organization_id,
        document=order_document,
        event_type="DELIVERED",
        created_by_id=current_user.id,
        event_metadata={"delivery_id": str(delivery.id)},
        idempotency_key=f"sales-order:{order.id}:delivered:{delivery.id}",
    )
    db.flush()
    return delivery


def record_purchase_order_receipt(
    db: Session,
    *,
    organization_id: uuid.UUID,
    current_user,
    purchase_order_id: uuid.UUID,
    purchase_order_document,
    purchase_order_number: str,
    supplier_name: str,
    invoice_number: str,
    received_at: datetime,
    items: list,
    invoice_attachment: str | None = None,
    notes: str | None = None,
    fiscal_document_id: uuid.UUID | None = None,
) -> InventoryReceipt:
    """Materializa um recebimento e suas entradas como uma única unidade rastreável."""
    from controlb.modules.documents import schemas as document_schemas

    existing = repository.get_inventory_receipt_by_purchase_order(
        db, purchase_order_id, organization_id
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A Ordem de Compra já possui um recebimento registrado.",
        )

    receipt_id = uuid.uuid4()
    receipt_document = documents_service.create_document(
        db,
        organization_id=organization_id,
        payload=document_schemas.DocumentCreate(
            category="inventory.receipt",
            document_type="INVENTORY_RECEIPT",
            native_id=receipt_id,
            title="Recebimento de Estoque",
            current_status="RECEIVED",
            description=notes,
            origin_module="INVENTORY",
            responsible_id=current_user.id,
            payload={
                "purchase_order_id": str(purchase_order_id),
                "purchase_order_number": purchase_order_number,
                "invoice_number": invoice_number,
                "supplier_name": supplier_name,
                "fiscal_document_id": str(fiscal_document_id) if fiscal_document_id else None,
            },
            issued_at=received_at,
            completed_at=received_at,
        ),
        current_user=current_user,
    )
    receipt_document.title = f"Recebimento {receipt_document.document_number}"

    receipt = repository.create_inventory_receipt(
        db,
        InventoryReceipt(
            id=receipt_id,
            organization_id=organization_id,
            purchase_order_id=purchase_order_id,
            fiscal_document_id=fiscal_document_id,
            document_id=receipt_document.id,
            receipt_number=receipt_document.document_number,
            invoice_number=invoice_number,
            invoice_attachment=invoice_attachment,
            received_by_id=current_user.id,
            received_at=received_at,
            notes=notes,
        ),
    )

    documents_service.relate_documents(
        db,
        organization_id=organization_id,
        parent_document=purchase_order_document,
        child_document=receipt_document,
        relation_type="FULFILLED_BY",
        created_by_id=current_user.id,
        relation_metadata={"invoice_number": invoice_number},
    )

    product_ids = [item.product_id for item in items]
    products = repository.lock_products_by_ids(db, product_ids, organization_id)
    products_by_id = {product.id: product for product in products}
    missing_ids = sorted(set(product_ids) - products_by_id.keys(), key=str)
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Produto {missing_ids[0]} não encontrado no estoque.",
        )

    reference = (
        f"{receipt.receipt_number} / {purchase_order_number} / NF {invoice_number}"
    )
    for item in items:
        product = products_by_id[item.product_id]
        entry_quantity = Decimal(str(item.quantity))
        new_balance = Decimal(str(product.current_stock or 0)) + entry_quantity
        product.current_stock = new_balance
        default_balance = sync_default_location_balance(
            db, organization_id, product
        )
        record_stock_movement(
            db,
            organization_id,
            product_id=product.id,
            receipt_id=receipt.id,
            source_document_id=receipt.document_id,
            fiscal_document_id=fiscal_document_id,
            location_id=default_balance.location_id,
            movement_type="in_purchase",
            quantity=entry_quantity,
            unit_cost=Decimal(str(item.unit_price)),
            balance_after=new_balance,
            location_balance_after=default_balance.quantity,
            reference_doc=reference,
            invoice_attachment=invoice_attachment,
            notes=notes or f"Entrada recebida do fornecedor {supplier_name}",
            created_by_id=current_user.id,
            current_user=current_user,
        )

    db.flush()
    logger.info(
        f"🚚 [INVENTORY RECEIPT] {receipt.receipt_number}: "
        f"{len(items)} item(ns) da ordem {purchase_order_number}"
    )
    return receipt


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
    default_balance = sync_default_location_balance(db, organization_id, prod)

    # Cria movimentação de entrada com documento canônico
    saved_movement = record_stock_movement(
        db,
        organization_id,
        product_id=prod.id,
        location_id=default_balance.location_id,
        movement_type="in_purchase",
        quantity=entry_qty,
        unit_cost=Decimal(str(unit_cost)),
        balance_after=new_balance,
        location_balance_after=default_balance.quantity,
        reference_doc=reference_doc,
        invoice_attachment=invoice_attachment,
        notes=notes or f"Entrada de mercadoria recebida via {reference_doc}",
        created_by_id=user_id,
    )
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


# ==============================================================================
# 5. IMPORTAÇÃO E SINCRONIZAÇÃO DE PLANILHA DE ESTOQUE
# ==============================================================================

def import_inventory_spreadsheet(
    db: Session,
    organization_id: uuid.UUID,
    user_id: uuid.UUID | None,
    file_bytes: bytes,
    filename: str | None = None
) -> dict:
    """
    Processa e sincroniza a planilha de inventário e estoque com auditoria completa:
    1. Lê todos os produtos e metadados via spreadsheet_parser.
    2. Identifica ou cria categorias automaticamente com base no NCM.
    3. Compara o estoque e preços atuais com os da planilha:
       - Variações de quantidade: Vendas (saídas) e Reposições (entradas) com geração no Kardex.
       - Variações de preço: Aumentos/quedas de custo e de preço de venda com percentual de variação.
       - Auditoria de estagnação: Produtos com estoque parado (sem giro) e cálculo do capital imobilizado.
    4. Persiste o lote de importação (InventoryImportBatch) e as linhas individuais auditadas (InventoryImportItem).
    5. Integra com o ciclo de documentos canônicos (BusinessDocument).
    """
    from controlb.modules.inventory.spreadsheet_parser import parse_inventory_xlsx

    try:
        parsed_data = parse_inventory_xlsx(file_bytes)
    except Exception as exc:
        logger.error(f"❌ Erro ao realizar parsing do XLSX de estoque: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não foi possível processar a planilha de estoque. Verifique se o formato do arquivo é válido. Erro: {exc}"
        )

    products_list = parsed_data.get("products", [])
    if not products_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhum produto válido foi encontrado na planilha informada."
        )

    # 1. Carrega categorias existentes da organização
    categories_map: dict[str, ProductCategory] = {
        c.name.strip().lower(): c for c in repository.list_categories(db, organization_id)
    }

    # 2. Carrega produtos existentes da organização em mapas de alta performance O(1)
    existing_prods = repository.list_products(db, organization_id)
    prod_by_external_code: dict[str, Product] = {
        p.external_code: p for p in existing_prods if p.external_code
    }
    prod_by_barcode: dict[str, Product] = {
        p.barcode.strip(): p for p in existing_prods if p.barcode and p.barcode.strip()
    }
    prod_by_sku: dict[str, Product] = {
        p.sku.strip().upper(): p for p in existing_prods if p.sku
    }
    prod_by_name: dict[str, Product] = {
        p.name.strip().upper(): p for p in existing_prods if p.name
    }

    created_products_count = 0
    updated_products_count = 0
    created_categories_count = 0

    sales_identified_count = 0
    total_sales_quantity = Decimal("0.0000")
    total_sales_estimated_revenue = Decimal("0.00")

    entries_identified_count = 0
    total_entries_quantity = Decimal("0.0000")
    total_entries_cost = Decimal("0.00")

    cost_increases_count = 0
    cost_decreases_count = 0

    stagnant_products_count = 0
    total_stagnant_capital = Decimal("0.00")

    sample_items = []
    batch_items_to_create: list[InventoryImportItem] = []
    batch_id = uuid.uuid4()
    inv_date = parsed_data.get("inventory_date") or "Diário"
    doc_header = documents_service.create_document(
        db,
        organization_id=organization_id,
        payload=document_schemas.DocumentCreate(
            category="inventory.import_batch",
            document_type="INVENTORY_IMPORT_BATCH",
            native_id=batch_id,
            title=f"Lote de Importação de Estoque {inv_date}",
            current_status="PROCESSING",
            description=f"Processando a planilha {filename or 'estoque.xlsx'}",
            origin_module="INVENTORY",
            responsible_id=user_id,
            payload={"filename": filename, "inventory_date": inv_date},
        ),
        current_user=None,
    )

    for item in products_list:
        # A. Categoria: Identifica ou cria
        cat_name = item["suggested_category_name"]
        cat_key = cat_name.strip().lower()

        if cat_key not in categories_map:
            new_cat = ProductCategory(
                organization_id=organization_id,
                name=cat_name.strip(),
                code=cat_name[:4].upper()
            )
            db.add(new_cat)
            db.flush()
            categories_map[cat_key] = new_cat
            created_categories_count += 1

        category_id = categories_map[cat_key].id

        # B. Localiza o produto existente
        code = item["code"]
        barcode = item["barcode"].strip() if item.get("barcode") else None
        name_upper = item["name"].strip().upper()

        prod = None
        if code in prod_by_external_code:
            prod = prod_by_external_code[code]
        elif barcode and barcode in prod_by_barcode:
            prod = prod_by_barcode[barcode]
        elif code in prod_by_sku or f"IMP-{code}".upper() in prod_by_sku or f"TP-{code}".upper() in prod_by_sku:
            prod = prod_by_sku.get(code) or prod_by_sku.get(f"IMP-{code}".upper()) or prod_by_sku.get(f"TP-{code}".upper())
        elif name_upper in prod_by_name:
            prod = prod_by_name[name_upper]

        new_stock = item["quantity"]
        cost_price = item["cost_price"]
        sale_price = item["sale_price"]

        if prod:
            # Produto já existe: reconciliação diária de saldo e auditoria de preços
            previous_stock = Decimal(str(prod.current_stock or 0))
            previous_cost = Decimal(str(prod.cost_price or 0)) if prod.cost_price is not None else None
            previous_sale = Decimal(str(prod.sale_price or 0)) if prod.sale_price is not None else None
            delta = new_stock - previous_stock

            # Auditoria de Preço de Custo
            # CORREÇÃO: Quando não há variação real (delta == 0), define-se None para
            # evitar que o frontend interprete "0.00" (string) como truthy e acumule
            # contagens de variações entre lotes consecutivos.
            raw_cost_diff = cost_price - (previous_cost if previous_cost is not None else Decimal("0.0000"))
            cost_var_amount = raw_cost_diff if raw_cost_diff != Decimal("0.0000") else None
            cost_var_percent = None
            if previous_cost is not None and previous_cost > 0 and raw_cost_diff != Decimal("0.0000"):
                cost_var_percent = round(((cost_price - previous_cost) / previous_cost) * Decimal("100.00"), 2)
                if cost_price > previous_cost:
                    cost_increases_count += 1
                elif cost_price < previous_cost:
                    cost_decreases_count += 1

            # Auditoria de Preço de Venda
            raw_sale_diff = sale_price - (previous_sale if previous_sale is not None else Decimal("0.0000"))
            sale_var_amount = raw_sale_diff if raw_sale_diff != Decimal("0.0000") else None
            sale_var_percent = None
            if previous_sale is not None and previous_sale > 0 and raw_sale_diff != Decimal("0.0000"):
                sale_var_percent = round(((sale_price - previous_sale) / previous_sale) * Decimal("100.00"), 2)

            # Atualiza dados cadastrais e preços no produto
            prod.external_code = code
            if barcode:
                prod.barcode = barcode
            if item.get("ncm"):
                prod.ncm = item["ncm"]
            prod.cost_price = cost_price
            prod.sale_price = sale_price
            prod.reference_price = cost_price
            prod.unit_of_measure = item["unit_of_measure"]
            prod.current_stock = new_stock
            if not prod.category_id:
                prod.category_id = category_id

            action_type = "unchanged"
            stagnant_value = Decimal("0.00")
            estimated_sales_revenue = Decimal("0.00")

            # Detecta Venda / Saída Diária
            if delta < 0:
                abs_delta = abs(delta)
                sales_identified_count += 1
                total_sales_quantity += abs_delta
                action_type = "sale_detected"
                item_rev = abs_delta * sale_price
                estimated_sales_revenue = item_rev
                total_sales_estimated_revenue += item_rev

                record_stock_movement(
                    db,
                    organization_id,
                    product_id=prod.id,
                    source_document_id=doc_header.id,
                    movement_type="out_sale",
                    quantity=abs_delta,
                    unit_cost=cost_price,
                    balance_after=new_stock,
                    reference_doc=f"Sync Inventário - Venda ({inv_date})",
                    notes=f"Saída/Venda de {abs_delta} {prod.unit_of_measure} apurada na importação da planilha de estoque",
                    created_by_id=user_id,
                )

            # Detecta Entrada / Reposição Diária
            elif delta > 0:
                entries_identified_count += 1
                total_entries_quantity += delta
                action_type = "entry_detected"
                item_cost = delta * cost_price
                total_entries_cost += item_cost

                record_stock_movement(
                    db,
                    organization_id,
                    product_id=prod.id,
                    source_document_id=doc_header.id,
                    movement_type="in_purchase_sync",
                    quantity=delta,
                    unit_cost=cost_price,
                    balance_after=new_stock,
                    reference_doc=f"Sync Inventário - Entrada ({inv_date})",
                    notes=f"Entrada/Reposição de {delta} {prod.unit_of_measure} apurada na importação da planilha de estoque",
                    created_by_id=user_id,
                )

            # Detecta Estagnação (Saldo > 0 e sem movimentação no período)
            else:
                if new_stock > 0:
                    action_type = "stagnant_unchanged"
                    stagnant_products_count += 1
                    stagnant_val = new_stock * cost_price
                    stagnant_value = stagnant_val
                    total_stagnant_capital += stagnant_val
                else:
                    action_type = "zero_stock_unchanged"

            updated_products_count += 1

            audit_item = InventoryImportItem(
                id=uuid.uuid4(),
                organization_id=organization_id,
                batch_id=batch_id,
                product_id=prod.id,
                code=code,
                barcode=barcode,
                sku=prod.sku,
                name=item["name"],
                ncm=item.get("ncm"),
                unit_of_measure=item["unit_of_measure"],
                action_type=action_type,
                previous_stock=previous_stock,
                new_stock=new_stock,
                delta_stock=delta,
                previous_cost_price=previous_cost,
                new_cost_price=cost_price,
                cost_variation_amount=cost_var_amount,
                cost_variation_percent=cost_var_percent,
                previous_sale_price=previous_sale,
                new_sale_price=sale_price,
                sale_variation_amount=sale_var_amount,
                sale_variation_percent=sale_var_percent,
                stagnant_value=stagnant_value,
                estimated_sales_revenue=estimated_sales_revenue
            )
            batch_items_to_create.append(audit_item)

            if len(sample_items) < 30:
                sample_items.append({
                    "code": code,
                    "name": item["name"],
                    "barcode": barcode,
                    "sku": prod.sku,
                    "ncm": item["ncm"],
                    "previous_stock": previous_stock,
                    "new_stock": new_stock,
                    "delta_stock": delta,
                    "action_type": action_type,
                    "previous_cost_price": previous_cost,
                    "new_cost_price": cost_price,
                    "cost_variation_amount": cost_var_amount,
                    "cost_variation_percent": cost_var_percent,
                    "previous_sale_price": previous_sale,
                    "new_sale_price": sale_price,
                    "sale_variation_amount": sale_var_amount,
                    "sale_variation_percent": sale_var_percent,
                    "stagnant_value": stagnant_value,
                    "estimated_sales_revenue": estimated_sales_revenue
                })

        else:
            # Produto novo: cadastra e registra abertura de estoque se houver saldo
            sku_val = f"IMP-{code}"
            new_prod = Product(
                organization_id=organization_id,
                category_id=category_id,
                sku=sku_val,
                external_code=code,
                name=item["name"],
                barcode=barcode,
                ncm=item["ncm"],
                unit_of_measure=item["unit_of_measure"],
                cost_price=cost_price,
                sale_price=sale_price,
                reference_price=cost_price,
                current_stock=new_stock,
                min_stock=Decimal("2.00"),
                is_active=True
            )
            db.add(new_prod)
            db.flush()

            # Registra nos mapas em memória para evitar duplicações na mesma planilha
            prod_by_external_code[code] = new_prod
            if barcode:
                prod_by_barcode[barcode] = new_prod
            prod_by_sku[sku_val.upper()] = new_prod
            prod_by_name[name_upper] = new_prod

            if new_stock > 0:
                record_stock_movement(
                    db,
                    organization_id,
                    product_id=new_prod.id,
                    source_document_id=doc_header.id,
                    movement_type="in_initial_inventory",
                    quantity=new_stock,
                    unit_cost=cost_price,
                    balance_after=new_stock,
                    reference_doc=f"Carga Inicial de Inventário ({inv_date})",
                    notes="Saldo de abertura importado da planilha de estoque",
                    created_by_id=user_id,
                )
                total_entries_cost += new_stock * cost_price

            created_products_count += 1

            audit_item = InventoryImportItem(
                id=uuid.uuid4(),
                organization_id=organization_id,
                batch_id=batch_id,
                product_id=new_prod.id,
                code=code,
                barcode=barcode,
                sku=sku_val,
                name=item["name"],
                ncm=item["ncm"],
                unit_of_measure=item["unit_of_measure"],
                action_type="created",
                previous_stock=Decimal("0.0000"),
                new_stock=new_stock,
                delta_stock=new_stock,
                previous_cost_price=None,
                new_cost_price=cost_price,
                cost_variation_amount=Decimal("0.0000"),
                cost_variation_percent=None,
                previous_sale_price=None,
                new_sale_price=sale_price,
                sale_variation_amount=Decimal("0.0000"),
                sale_variation_percent=None,
                stagnant_value=Decimal("0.00"),
                estimated_sales_revenue=Decimal("0.00")
            )
            batch_items_to_create.append(audit_item)

            if len(sample_items) < 30:
                sample_items.append({
                    "code": code,
                    "name": item["name"],
                    "barcode": barcode,
                    "sku": sku_val,
                    "ncm": item["ncm"],
                    "previous_stock": Decimal("0.0000"),
                    "new_stock": new_stock,
                    "delta_stock": new_stock,
                    "action_type": "created",
                    "previous_cost_price": None,
                    "new_cost_price": cost_price,
                    "cost_variation_amount": Decimal("0.0000"),
                    "cost_variation_percent": None,
                    "previous_sale_price": None,
                    "new_sale_price": sale_price,
                    "sale_variation_amount": Decimal("0.0000"),
                    "sale_variation_percent": None,
                    "stagnant_value": Decimal("0.00"),
                    "estimated_sales_revenue": Decimal("0.00")
                })

    for synchronized_product in repository.list_products(db, organization_id):
        sync_default_location_balance(
            db, organization_id, synchronized_product
        )

    # Conclui o mesmo documento que acompanhou todas as movimentações do lote.
    doc_header = documents_service.update_document(
        db,
        doc_header.id,
        organization_id,
        document_schemas.DocumentUpdate(
            current_status="PROCESSED",
            description=f"Importação de {len(products_list)} itens da planilha {filename or 'estoque.xlsx'}",
            completed_at=datetime.now(timezone.utc),
            payload={
                "filename": filename,
                "inventory_date": inv_date,
                "total_products_read": len(products_list),
                "created_products_count": created_products_count,
                "updated_products_count": updated_products_count,
                "sales_identified_count": sales_identified_count,
                "total_sales_quantity": str(total_sales_quantity),
                "total_sales_estimated_revenue": str(total_sales_estimated_revenue),
                "entries_identified_count": entries_identified_count,
                "total_entries_quantity": str(total_entries_quantity),
                "cost_increases_count": cost_increases_count,
                "cost_decreases_count": cost_decreases_count,
                "stagnant_products_count": stagnant_products_count,
                "total_stagnant_capital": str(total_stagnant_capital),
            },
        ),
        current_user=None,
    )

    batch = InventoryImportBatch(
        id=batch_id,
        organization_id=organization_id,
        document_id=doc_header.id,
        batch_number=doc_header.document_number,
        filename=filename,
        inventory_date=inv_date,
        total_products_read=len(products_list),
        created_products_count=created_products_count,
        updated_products_count=updated_products_count,
        created_categories_count=created_categories_count,
        sales_identified_count=sales_identified_count,
        total_sales_quantity=total_sales_quantity,
        total_sales_estimated_revenue=total_sales_estimated_revenue,
        entries_identified_count=entries_identified_count,
        total_entries_quantity=total_entries_quantity,
        total_entries_cost=total_entries_cost,
        cost_increases_count=cost_increases_count,
        cost_decreases_count=cost_decreases_count,
        stagnant_products_count=stagnant_products_count,
        total_stagnant_capital=total_stagnant_capital,
        total_inventory_cost=parsed_data.get("total_cost", Decimal("0.00")),
        total_inventory_sale=parsed_data.get("total_sale", Decimal("0.00")),
        imported_by_id=user_id,
        notes=f"Lote processado com {len(batch_items_to_create)} itens auditados."
    )
    try:
        db.add(batch)
        db.add_all(batch_items_to_create)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception(f"❌ Erro ao persistir lote de importação de estoque no banco de dados: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao salvar os dados da importação no banco de dados: {exc}"
        )

    logger.info(
        f"✅ [INVENTORY IMPORT] Concluído com sucesso (Lote #{doc_header.document_number}): {len(products_list)} itens lidos, "
        f"{created_products_count} criados, {updated_products_count} atualizados, "
        f"{sales_identified_count} vendas identificadas ({total_sales_quantity} un, R$ {total_sales_estimated_revenue}), "
        f"{cost_increases_count} aumentos de custo, {stagnant_products_count} itens estagnados (R$ {total_stagnant_capital} parados)."
    )

    return {
        "batch_id": batch_id,
        "batch_number": doc_header.document_number,
        "total_products_read": len(products_list),
        "created_products_count": created_products_count,
        "updated_products_count": updated_products_count,
        "created_categories_count": created_categories_count,
        "sales_identified_count": sales_identified_count,
        "total_sales_quantity": total_sales_quantity,
        "total_sales_estimated_revenue": total_sales_estimated_revenue,
        "entries_identified_count": entries_identified_count,
        "total_entries_quantity": total_entries_quantity,
        "total_entries_cost": total_entries_cost,
        "cost_increases_count": cost_increases_count,
        "cost_decreases_count": cost_decreases_count,
        "stagnant_products_count": stagnant_products_count,
        "total_stagnant_capital": total_stagnant_capital,
        "total_cost_value": parsed_data.get("total_cost", Decimal("0.00")),
        "total_sale_value": parsed_data.get("total_sale", Decimal("0.00")),
        "inventory_date": inv_date,
        "message": f"Sincronização de estoque concluída com auditoria: {len(products_list)} produtos processados no Lote {doc_header.document_number}.",
        "sample_items": sample_items
    }


def list_inventory_import_batches(
    db: Session,
    organization_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0
) -> list[InventoryImportBatch]:
    """Retorna o histórico de lotes de importação de planilhas ordenados por data."""
    return repository.list_import_batches(db, organization_id, limit, offset)


def get_inventory_import_batch_detail(
    db: Session,
    organization_id: uuid.UUID,
    batch_id: uuid.UUID
) -> InventoryImportBatch:
    """Retorna o lote completo com todas as suas linhas auditadas."""
    batch = repository.get_import_batch(db, organization_id, batch_id)
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lote de importação de estoque não localizado."
        )
    return batch


def get_stagnant_inventory_report(
    db: Session,
    organization_id: uuid.UUID
) -> dict:
    """
    Gera relatório consolidado de produtos estagnados (capital imobilizado) na organização.
    Cruza produtos com saldo físico > 0 com a data da última saída/venda no Kardex.
    """
    products = repository.list_products(db, organization_id)
    categories = {c.id: c.name for c in repository.list_categories(db, organization_id)}

    stagnant_items = []
    total_stagnant_units = Decimal("0.0000")
    total_stagnant_capital = Decimal("0.00")
    category_summary: dict[str, dict[str, Any]] = {}

    now = datetime.now(timezone.utc)

    for p in products:
        stock = Decimal(str(p.current_stock or 0))
        if stock <= 0:
            continue

        cost = Decimal(str(p.cost_price or 0))
        sale = Decimal(str(p.sale_price or 0))
        stagnant_cap = stock * cost

        # Busca última saída
        last_out = (
            db.query(StockMovement)
            .filter(
                StockMovement.product_id == p.id,
                StockMovement.organization_id == organization_id,
                StockMovement.movement_type.in_(["out_sale", "out_loss", "out_adjustment", "out_reconciliation"])
            )
            .order_by(StockMovement.created_at.desc())
            .first()
        )

        last_date = last_out.created_at if last_out else p.created_at
        if last_date:
            if last_date.tzinfo is None:
                last_date = last_date.replace(tzinfo=timezone.utc)
            days_without_sale = (now - last_date).days
        else:
            days_without_sale = None

        cat_name = categories.get(p.category_id, "Sem Categoria") if p.category_id else "Sem Categoria"

        if cat_name not in category_summary:
            category_summary[cat_name] = {
                "category_name": cat_name,
                "products_count": 0,
                "total_units": Decimal("0.0000"),
                "total_capital": Decimal("0.00")
            }

        category_summary[cat_name]["products_count"] += 1
        category_summary[cat_name]["total_units"] += stock
        category_summary[cat_name]["total_capital"] += stagnant_cap

        total_stagnant_units += stock
        total_stagnant_capital += stagnant_cap

        stagnant_items.append({
            "product_id": p.id,
            "code": p.external_code,
            "sku": p.sku,
            "name": p.name,
            "category_name": cat_name,
            "current_stock": stock,
            "unit_of_measure": p.unit_of_measure,
            "cost_price": cost,
            "sale_price": sale,
            "stagnant_capital": stagnant_cap,
            "last_movement_date": last_date,
            "days_without_sale": days_without_sale
        })

    # Ordena por maior capital parado
    stagnant_items.sort(key=lambda x: x["stagnant_capital"], reverse=True)

    return {
        "total_stagnant_products": len(stagnant_items),
        "total_stagnant_units": total_stagnant_units,
        "total_stagnant_capital": total_stagnant_capital,
        "stagnant_by_category": list(category_summary.values()),
        "top_stagnant_products": stagnant_items
    }


# Alias para retrocompatibilidade
import_toolspharma_inventory = import_inventory_spreadsheet
