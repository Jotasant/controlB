"""
modules/purchasing/repository.py - Camada de Persistência e Consultas (SQLAlchemy 2.0)

Isola todas as operações de banco de dados (CRUD) para:
1. Fornecedores (Supplier)
2. Centros de Custo (CostCenter)
3. Categorias de Produtos (ProductCategory)
4. Produtos & Insumos (Product)
5. Solicitações de Compra (PurchaseRequest & PurchaseRequestItem)
6. Eventos de Aprovação (ApprovalEvent)
7. Ordens de Compra (PurchaseOrder & PurchaseOrderItem)
"""

import uuid
from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from controlb.modules.purchasing.models import (
    Supplier, CostCenter, ProductCategory, Product, 
    PurchaseRequest, PurchaseRequestItem, ApprovalEvent, 
    PurchaseOrder, PurchaseOrderItem,
    QuotationProcess, SupplierQuote, SupplierQuoteItem
)
from controlb.modules.purchasing.schemas import (
    SupplierCreate, SupplierUpdate,
    CostCenterCreate, CostCenterUpdate,
    ProductCategoryCreate, ProductCategoryUpdate,
    ProductCreate, ProductUpdate,
    PurchaseRequestCreate, PurchaseRequestUpdate,
    PurchaseOrderCreate, PurchaseOrderUpdate,
    SupplierQuoteCreate, QuotationProcessCreate
)


# ==============================================================================
# 1. CONSULTAS E OPERAÇÕES DE FORNECEDORES (Supplier)
# ==============================================================================

def get_all_suppliers(db: Session, organization_id: uuid.UUID) -> list[Supplier]:
    """Retorna todos os fornecedores da organização ordenados por nome."""
    stmt = select(Supplier).where(
        Supplier.organization_id == organization_id
    ).order_by(Supplier.name)
    return db.execute(stmt).scalars().all()


def get_supplier_by_id(db: Session, supplier_id: uuid.UUID, organization_id: uuid.UUID) -> Supplier | None:
    """Busca um fornecedor pelo ID e organização."""
    stmt = select(Supplier).where(
        Supplier.id == supplier_id, 
        Supplier.organization_id == organization_id
    )
    return db.execute(stmt).scalar_one_or_none()


def get_supplier_by_cnpj(db: Session, cnpj_cpf: str, organization_id: uuid.UUID) -> Supplier | None:
    """Busca um fornecedor pelo CNPJ/CPF na organização."""
    stmt = select(Supplier).where(
        Supplier.cnpj_cpf == cnpj_cpf, 
        Supplier.organization_id == organization_id
    )
    return db.execute(stmt).scalar_one_or_none()


def create_supplier(db: Session, supplier_data: SupplierCreate) -> Supplier:
    """Cria e persiste um novo fornecedor no banco."""
    db_supplier = Supplier(
        organization_id=supplier_data.organization_id,
        name=supplier_data.name,
        trade_name=supplier_data.trade_name,
        cnpj_cpf=supplier_data.cnpj_cpf,
        email=supplier_data.email,
        phone=supplier_data.phone,
        address=supplier_data.address,
        city=supplier_data.city,
        state=supplier_data.state,
        zip_code=supplier_data.zip_code,
        country=supplier_data.country or "BR",
    )
    db.add(db_supplier)
    db.commit()
    db.refresh(db_supplier)
    return db_supplier


def update_supplier(db: Session, db_supplier: Supplier, supplier_data: SupplierUpdate) -> Supplier:
    """Atualiza dados do fornecedor utilizando model_dump(exclude_unset=True)."""
    update_data = supplier_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_supplier, field, value)
    
    db.commit()
    db.refresh(db_supplier)
    return db_supplier


def delete_supplier(db: Session, db_supplier: Supplier) -> None:
    """Remove permanentemente o fornecedor do banco."""
    db.delete(db_supplier)
    db.commit()


# ==============================================================================
# 2. CONSULTAS E OPERAÇÕES DE CENTROS DE CUSTO (CostCenter)
# ==============================================================================

def get_all_cost_centers(db: Session, organization_id: uuid.UUID) -> list[CostCenter]:
    """Retorna todos os centros de custo da organização."""
    stmt = select(CostCenter).where(
        CostCenter.organization_id == organization_id
    ).order_by(CostCenter.code)
    return db.execute(stmt).scalars().all()


def get_cost_center_by_id(db: Session, cost_center_id: uuid.UUID, organization_id: uuid.UUID) -> CostCenter | None:
    """Busca um centro de custo pelo ID e organização."""
    stmt = select(CostCenter).where(
        CostCenter.id == cost_center_id, 
        CostCenter.organization_id == organization_id
    )
    return db.execute(stmt).scalar_one_or_none()


def get_cost_center_by_code(db: Session, code: str, organization_id: uuid.UUID) -> CostCenter | None:
    """Busca um centro de custo pelo código (ex: CC-001)."""
    stmt = select(CostCenter).where(
        CostCenter.code == code, 
        CostCenter.organization_id == organization_id
    )
    return db.execute(stmt).scalar_one_or_none()


def create_cost_center(db: Session, cost_center_data: CostCenterCreate) -> CostCenter:
    """Cria e persiste um novo centro de custo."""
    db_cost_center = CostCenter(
        organization_id=cost_center_data.organization_id,
        code=cost_center_data.code,
        name=cost_center_data.name,
        description=cost_center_data.description,
        manager_id=cost_center_data.manager_id,
    )
    db.add(db_cost_center)
    db.commit()
    db.refresh(db_cost_center)
    return db_cost_center


def update_cost_center(db: Session, db_cost_center: CostCenter, cost_center_data: CostCenterUpdate) -> CostCenter:
    """Atualiza dados do centro de custo."""
    update_data = cost_center_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_cost_center, field, value)
    
    db.commit()
    db.refresh(db_cost_center)
    return db_cost_center


def delete_cost_center(db: Session, db_cost_center: CostCenter) -> None:
    """Remove o centro de custo."""
    db.delete(db_cost_center)
    db.commit()


# ==============================================================================
# 3. CONSULTAS E OPERAÇÕES DE CATEGORIAS (ProductCategory)
# ==============================================================================

def get_all_product_categories(db: Session, organization_id: uuid.UUID) -> list[ProductCategory]:
    """Retorna todas as categorias de produtos da organização."""
    stmt = select(ProductCategory).where(
        ProductCategory.organization_id == organization_id
    ).order_by(ProductCategory.name)
    return db.execute(stmt).scalars().all()


def get_product_category_by_id(db: Session, category_id: uuid.UUID, organization_id: uuid.UUID) -> ProductCategory | None:
    """Busca uma categoria pelo ID."""
    stmt = select(ProductCategory).where(
        ProductCategory.id == category_id, 
        ProductCategory.organization_id == organization_id
    )
    return db.execute(stmt).scalar_one_or_none()


def create_product_category(db: Session, category_data: ProductCategoryCreate) -> ProductCategory:
    """Cria e persiste uma nova categoria de produto."""
    db_category = ProductCategory(
        organization_id=category_data.organization_id,
        name=category_data.name,
        code=category_data.code,
        description=category_data.description,
    )
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category


def update_product_category(db: Session, db_category: ProductCategory, category_data: ProductCategoryUpdate) -> ProductCategory:
    """Atualiza dados da categoria."""
    update_data = category_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_category, field, value)
    
    db.commit()
    db.refresh(db_category)
    return db_category


def delete_product_category(db: Session, db_category: ProductCategory) -> None:
    """Remove a categoria de produto."""
    db.delete(db_category)
    db.commit()


# ==============================================================================
# 4. CONSULTAS E OPERAÇÕES DE PRODUTOS/INSUMOS (Product)
# ==============================================================================

def get_all_products(db: Session, organization_id: uuid.UUID) -> list[Product]:
    """Retorna todos os produtos cadastrados na organização."""
    stmt = select(Product).where(
        Product.organization_id == organization_id
    ).order_by(Product.name)
    return db.execute(stmt).scalars().all()


def get_product_by_id(db: Session, product_id: uuid.UUID, organization_id: uuid.UUID) -> Product | None:
    """Busca um produto pelo ID."""
    stmt = select(Product).where(
        Product.id == product_id, 
        Product.organization_id == organization_id
    )
    return db.execute(stmt).scalar_one_or_none()


def get_product_by_sku(db: Session, sku: str, organization_id: uuid.UUID) -> Product | None:
    """Busca um produto pelo SKU único na organização."""
    stmt = select(Product).where(
        Product.sku == sku, 
        Product.organization_id == organization_id
    )
    return db.execute(stmt).scalar_one_or_none()


def create_product(db: Session, product_data: ProductCreate) -> Product:
    """Cria e persiste um novo produto no catálogo."""
    db_product = Product(
        organization_id=product_data.organization_id,
        category_id=product_data.category_id,
        sku=product_data.sku,
        name=product_data.name,
        description=product_data.description,
        unit_of_measure=product_data.unit_of_measure,
        reference_price=product_data.reference_price,
        brand=product_data.brand,
        barcode=product_data.barcode,
        ncm=product_data.ncm,
        is_perishable=product_data.is_perishable,
        requires_batch=product_data.requires_batch,
        shelf_life_days=product_data.shelf_life_days,
        min_stock=product_data.min_stock,
        max_stock=product_data.max_stock,
        storage_location=product_data.storage_location,
    )
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product


def update_product(db: Session, db_product: Product, product_data: ProductUpdate) -> Product:
    """Atualiza dados cadastrais do produto."""
    update_data = product_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_product, field, value)
    
    db.commit()
    db.refresh(db_product)
    return db_product


def delete_product(db: Session, db_product: Product) -> None:
    """Remove o produto do catálogo."""
    db.delete(db_product)
    db.commit()


# ==============================================================================
# 5. CONSULTAS E OPERAÇÕES DE SOLICITAÇÃO DE COMPRA (PurchaseRequest)
# ==============================================================================

def get_all_purchase_requests(
    db: Session, 
    organization_id: uuid.UUID, 
    status: str | None = None
) -> list[PurchaseRequest]:
    """Retorna todas as solicitações de compra com filtro opcional de status."""
    stmt = select(PurchaseRequest).where(PurchaseRequest.organization_id == organization_id)
    if status:
        stmt = stmt.where(PurchaseRequest.status == status)
    stmt = stmt.order_by(PurchaseRequest.created_at.desc())
    return db.execute(stmt).scalars().all()


def get_purchase_request_by_id(
    db: Session, 
    request_id: uuid.UUID, 
    organization_id: uuid.UUID
) -> PurchaseRequest | None:
    """Busca uma solicitação de compra pelo ID com itens e histórico carregados."""
    stmt = select(PurchaseRequest).where(
        PurchaseRequest.id == request_id, 
        PurchaseRequest.organization_id == organization_id
    )
    return db.execute(stmt).scalar_one_or_none()


def count_purchase_requests_in_year(db: Session, organization_id: uuid.UUID, year: int) -> int:
    """Retorna o total de solicitações no ano para geração do número sequencial."""
    stmt = select(func.count(PurchaseRequest.id)).where(
        PurchaseRequest.organization_id == organization_id,
        func.extract("year", PurchaseRequest.created_at) == year
    )
    return db.execute(stmt).scalar() or 0


def create_purchase_request(
    db: Session, 
    requester_id: uuid.UUID,
    request_number: str,
    total_estimated: Decimal,
    request_data: PurchaseRequestCreate
) -> PurchaseRequest:
    """Cria o cabeçalho da solicitação de compra e persiste suas linhas de itens."""
    db_request = PurchaseRequest(
        organization_id=request_data.organization_id,
        requester_id=requester_id,
        cost_center_id=request_data.cost_center_id,
        request_number=request_number,
        justification=request_data.justification,
        status="pending_approval",
        total_estimated_amount=total_estimated,
        required_date=request_data.required_date,
    )
    db.add(db_request)
    db.flush()  # Gera o ID da solicitação sem commitar ainda

    # Cria cada linha de item da solicitação
    for item in request_data.items:
        total_item_price = Decimal(str(item.quantity)) * Decimal(str(item.estimated_unit_price))
        db_item = PurchaseRequestItem(
            purchase_request_id=db_request.id,
            product_id=item.product_id,
            quantity=item.quantity,
            estimated_unit_price=item.estimated_unit_price,
            total_estimated_price=total_item_price,
            notes=item.notes
        )
        db.add(db_item)

    db.commit()
    db.refresh(db_request)
    return db_request


def update_purchase_request_status(
    db: Session, 
    db_request: PurchaseRequest, 
    new_status: str
) -> PurchaseRequest:
    """Atualiza o status da solicitação de compra."""
    db_request.status = new_status
    db.commit()
    db.refresh(db_request)
    return db_request


def update_purchase_request(
    db: Session,
    db_request: PurchaseRequest,
    request_data: PurchaseRequestUpdate
) -> PurchaseRequest:
    """Atualiza dados cadastrais da solicitação de compra."""
    update_data = request_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_request, field, value)
    db.commit()
    db.refresh(db_request)
    return db_request


def delete_purchase_request(db: Session, db_request: PurchaseRequest) -> None:
    """Remove a solicitação de compra e itens em cascata."""
    db.delete(db_request)
    db.commit()


# ==============================================================================
# 6. CONSULTAS E OPERAÇÕES DE EVENTOS DE APROVAÇÃO (ApprovalEvent)
# ==============================================================================

def create_approval_event(
    db: Session, 
    purchase_request_id: uuid.UUID,
    approver_id: uuid.UUID,
    action: str,
    comments: str | None = None
) -> ApprovalEvent:
    """Registra uma decisão formal de aprovação ou rejeição na trilha de auditoria."""
    db_event = ApprovalEvent(
        purchase_request_id=purchase_request_id,
        approver_id=approver_id,
        action=action,
        comments=comments
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event


# ==============================================================================
# 7. CONSULTAS E OPERAÇÕES DE ORDENS DE COMPRA (PurchaseOrder)
# ==============================================================================

def get_all_purchase_orders(
    db: Session, 
    organization_id: uuid.UUID, 
    status: str | None = None
) -> list[PurchaseOrder]:
    """Retorna todas as ordens de compra da organização."""
    stmt = select(PurchaseOrder).where(PurchaseOrder.organization_id == organization_id)
    if status:
        stmt = stmt.where(PurchaseOrder.status == status)
    stmt = stmt.order_by(PurchaseOrder.created_at.desc())
    return db.execute(stmt).scalars().all()


def get_purchase_order_by_id(
    db: Session, 
    order_id: uuid.UUID, 
    organization_id: uuid.UUID
) -> PurchaseOrder | None:
    """Busca uma ordem de compra pelo ID."""
    stmt = select(PurchaseOrder).where(
        PurchaseOrder.id == order_id, 
        PurchaseOrder.organization_id == organization_id
    )
    return db.execute(stmt).scalar_one_or_none()


def count_purchase_orders_in_year(db: Session, organization_id: uuid.UUID, year: int) -> int:
    """Retorna o total de ordens no ano para geração do número sequencial."""
    stmt = select(func.count(PurchaseOrder.id)).where(
        PurchaseOrder.organization_id == organization_id,
        func.extract("year", PurchaseOrder.created_at) == year
    )
    return db.execute(stmt).scalar() or 0


def create_purchase_order(
    db: Session, 
    order_number: str,
    total_amount: Decimal,
    order_data: PurchaseOrderCreate
) -> PurchaseOrder:
    """Cria e persiste uma nova ordem de compra oficial com seus itens negociados."""
    db_order = PurchaseOrder(
        organization_id=order_data.organization_id,
        purchase_request_id=order_data.purchase_request_id,
        supplier_quote_id=order_data.supplier_quote_id,
        supplier_id=order_data.supplier_id,
        buyer_id=order_data.buyer_id,
        cost_center_id=order_data.cost_center_id,
        order_number=order_number,
        status="issued",
        payment_terms=order_data.payment_terms,
        freight_type=order_data.freight_type,
        freight_amount=order_data.freight_amount,
        discount_amount=order_data.discount_amount,
        expected_delivery_date=order_data.expected_delivery_date,
        notes=order_data.notes,
        total_amount=total_amount
    )
    db.add(db_order)
    db.flush()

    for item in order_data.items:
        total_item = Decimal(str(item.quantity)) * Decimal(str(item.unit_price))
        db_item = PurchaseOrderItem(
            purchase_order_id=db_order.id,
            product_id=item.product_id,
            quantity=item.quantity,
            unit_price=item.unit_price,
            total_price=total_item
        )
        db.add(db_item)

    db.commit()
    db.refresh(db_order)
    return db_order


def receive_purchase_order(
    db: Session,
    db_order: PurchaseOrder,
    invoice_number: str,
    received_by_id: uuid.UUID,
    received_at: datetime | None = None,
    notes: str | None = None
) -> PurchaseOrder:
    """Registra o recebimento físico e faturamento da ordem de compra."""
    db_order.status = "received"
    db_order.invoice_number = invoice_number
    db_order.received_by_id = received_by_id
    db_order.received_at = received_at or datetime.now(timezone.utc)
    if notes:
        db_order.notes = f"{db_order.notes or ''}\n[Recebimento]: {notes}".strip()

    db.commit()
    db.refresh(db_order)
    return db_order


def get_purchase_orders_by_request_id(
    db: Session, 
    request_id: uuid.UUID, 
    organization_id: uuid.UUID
) -> list[PurchaseOrder]:
    """Retorna todas as ordens vinculadas a uma solicitação de compra."""
    stmt = select(PurchaseOrder).where(
        PurchaseOrder.purchase_request_id == request_id,
        PurchaseOrder.organization_id == organization_id
    )
    return db.execute(stmt).scalars().all()


def update_purchase_order_status(
    db: Session, 
    db_order: PurchaseOrder, 
    new_status: str
) -> PurchaseOrder:
    """Atualiza o status da ordem de compra (ex: cancelled, closed)."""
    db_order.status = new_status
    db.commit()
    db.refresh(db_order)
    return db_order


# ==============================================================================
# 8. PROCESSOS DE COTAÇÃO (RFQ) E PROPOSTAS DE FORNECEDORES
# ==============================================================================

def count_quotation_processes_in_year(db: Session, organization_id: uuid.UUID, year: int) -> int:
    """Retorna o total de cotações abertas no ano para geração do número sequencial (COT-YYYY-XXXX)."""
    stmt = select(func.count(QuotationProcess.id)).where(
        QuotationProcess.organization_id == organization_id,
        func.extract("year", QuotationProcess.created_at) == year
    )
    return db.execute(stmt).scalar() or 0


def get_all_quotation_processes(
    db: Session, 
    organization_id: uuid.UUID,
    status: str | None = None
) -> list[QuotationProcess]:
    """Retorna todos os processos de cotação da organização."""
    stmt = select(QuotationProcess).where(QuotationProcess.organization_id == organization_id)
    if status:
        stmt = stmt.where(QuotationProcess.status == status)
    stmt = stmt.order_by(QuotationProcess.created_at.desc())
    return db.execute(stmt).scalars().all()


def get_quotation_process_by_id(
    db: Session, 
    quotation_id: uuid.UUID, 
    organization_id: uuid.UUID
) -> QuotationProcess | None:
    """Busca um processo de cotação pelo ID."""
    stmt = select(QuotationProcess).where(
        QuotationProcess.id == quotation_id,
        QuotationProcess.organization_id == organization_id
    )
    return db.execute(stmt).scalar_one_or_none()


def get_quotation_process_by_request_id(
    db: Session, 
    request_id: uuid.UUID, 
    organization_id: uuid.UUID
) -> QuotationProcess | None:
    """Busca o processo de cotação vinculado a uma solicitação de compra."""
    stmt = select(QuotationProcess).where(
        QuotationProcess.purchase_request_id == request_id,
        QuotationProcess.organization_id == organization_id
    )
    return db.execute(stmt).scalar_one_or_none()


def create_quotation_process(
    db: Session,
    organization_id: uuid.UUID,
    purchase_request_id: uuid.UUID,
    quotation_number: str,
    notes: str | None = None
) -> QuotationProcess:
    """Cria e abre um novo processo de cotação oficial para uma SC aprovada."""
    db_process = QuotationProcess(
        organization_id=organization_id,
        purchase_request_id=purchase_request_id,
        quotation_number=quotation_number,
        status="open",
        notes=notes
    )
    db.add(db_process)
    db.commit()
    db.refresh(db_process)
    return db_process


def create_supplier_quote(
    db: Session,
    organization_id: uuid.UUID,
    quotation_process_id: uuid.UUID,
    total_amount: Decimal,
    quote_data: SupplierQuoteCreate
) -> SupplierQuote:
    """Registra uma proposta comercial de um fornecedor concorrente em uma cotação."""
    db_quote = SupplierQuote(
        organization_id=organization_id,
        quotation_process_id=quotation_process_id,
        supplier_id=quote_data.supplier_id,
        quote_reference=quote_data.quote_reference,
        status="pending",
        payment_terms=quote_data.payment_terms,
        freight_type=quote_data.freight_type,
        freight_amount=quote_data.freight_amount,
        discount_amount=quote_data.discount_amount,
        lead_time_days=quote_data.lead_time_days,
        valid_until=quote_data.valid_until,
        total_amount=total_amount,
        notes=quote_data.notes
    )
    db.add(db_quote)
    db.flush()

    for item in quote_data.items:
        total_item = Decimal(str(item.quantity)) * Decimal(str(item.unit_price))
        db_item = SupplierQuoteItem(
            supplier_quote_id=db_quote.id,
            product_id=item.product_id,
            quantity=item.quantity,
            unit_price=item.unit_price,
            total_price=total_item,
            brand_offered=item.brand_offered,
            notes=item.notes
        )
        db.add(db_item)

    db.commit()
    db.refresh(db_quote)
    return db_quote


def get_supplier_quote_by_id(
    db: Session,
    quote_id: uuid.UUID,
    organization_id: uuid.UUID
) -> SupplierQuote | None:
    """Busca uma proposta de fornecedor pelo ID."""
    stmt = select(SupplierQuote).where(
        SupplierQuote.id == quote_id,
        SupplierQuote.organization_id == organization_id
    )
    return db.execute(stmt).scalar_one_or_none()


def update_supplier_quote_status(
    db: Session,
    db_quote: SupplierQuote,
    new_status: str
) -> SupplierQuote:
    """Atualiza o status da proposta comercial (selected, rejected, pending)."""
    db_quote.status = new_status
    db.commit()
    db.refresh(db_quote)
    return db_quote


def update_quotation_process_status(
    db: Session,
    db_process: QuotationProcess,
    new_status: str
) -> QuotationProcess:
    """Atualiza o status do processo de cotação (analyzing, completed, cancelled)."""
    db_process.status = new_status
    db.commit()
    db.refresh(db_process)
    return db_process


def delete_supplier_quote(db: Session, db_quote: SupplierQuote) -> None:
    """Exclui permanentemente uma proposta comercial do fornecedor na cotação."""
    db.delete(db_quote)
    db.commit()

