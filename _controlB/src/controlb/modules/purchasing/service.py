"""
modules/purchasing/service.py - Camada de Regras de Negócio e Casos de Uso (Purchasing)

Contém a lógica de domínio para:
1. Gestão de Cadastros de Apoio (Fornecedores, Centros de Custo, Categorias, Produtos).
2. Criação, Cálculo e Numeração Sequencial de Solicitações de Compra.
3. Máquina de Estados e Trilha de Auditoria de Aprovações por Alçada.
4. Emissão e Cancelamento de Ordens de Compra Oficiais.
"""

import re
import uuid
import unicodedata
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from controlb.modules.purchasing import models, schemas, repository
from controlb.modules.identity.models import User
from controlb.modules.inventory import service as inventory_service



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


def delete_cost_center_record(db: Session, cost_center_id: uuid.UUID, organization_id: uuid.UUID) -> dict:
    """Remove um centro de custo."""
    db_cost_center = repository.get_cost_center_by_id(db, cost_center_id=cost_center_id, organization_id=organization_id)
    if not db_cost_center:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Centro de custo não encontrado."
        )

    repository.delete_cost_center(db, db_cost_center=db_cost_center)
    return {"detail": "Centro de custo excluído com sucesso."}


# ==============================================================================
# 3. REGRAS DE NEGÓCIO DE CATEGORIAS E PRODUTOS (Product & Category)
# ==============================================================================

def list_categories(db: Session, organization_id: uuid.UUID) -> list[models.ProductCategory]:
    """Retorna todas as categorias da organização."""
    return repository.get_all_product_categories(db, organization_id=organization_id)


def create_new_category(db: Session, category_data: schemas.ProductCategoryCreate) -> models.ProductCategory:
    """Cria uma nova categoria de produto."""
    return repository.create_product_category(db, category_data=category_data)


def update_category_data(
    db: Session,
    category_id: uuid.UUID,
    organization_id: uuid.UUID,
    category_data: schemas.ProductCategoryUpdate
) -> models.ProductCategory:
    """Atualiza dados cadastrais da categoria de produto."""
    db_cat = repository.get_product_category_by_id(db, category_id=category_id, organization_id=organization_id)
    if not db_cat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoria de produto não encontrada."
        )
    return repository.update_product_category(db, db_category=db_cat, category_data=category_data)


def delete_category_record(
    db: Session,
    category_id: uuid.UUID,
    organization_id: uuid.UUID
) -> dict:
    """Exclui uma categoria de produto se não houver produtos vinculados."""
    db_cat = repository.get_product_category_by_id(db, category_id=category_id, organization_id=organization_id)
    if not db_cat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoria de produto não encontrada."
        )
    if db_cat.products and len(db_cat.products) > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não é possível excluir esta categoria pois ela possui {len(db_cat.products)} produto(s) vinculado(s)."
        )
    repository.delete_product_category(db, db_category=db_cat)
    return {"detail": "Categoria de produto excluída com sucesso."}



def list_products(db: Session, organization_id: uuid.UUID) -> list[models.Product]:
    """Retorna o catálogo de produtos da organização."""
    return repository.get_all_products(db, organization_id=organization_id)


def generate_product_sku(
    db: Session,
    organization_id: uuid.UUID,
    name: str,
    category_id: uuid.UUID | None = None,
    unit_of_measure: str = "UN"
) -> str:
    """
    Gera automaticamente um código SKU semântico e livre de colisões.
    
    Estrutura: [CATEGORIA]-[SLUG_DO_PRODUTO]-[UNIDADE]-[SEQUENCIAL]
    Exemplo: MED-PARACETAMOL-500MG-CX-0001
    """
    # 1. Determina o prefixo da categoria (3 a 4 letras maiúsculas)
    cat_prefix = "GEN"
    if category_id:
        category = repository.get_product_category_by_id(db, category_id=category_id, organization_id=organization_id)
        if category and category.code:
            cat_prefix = re.sub(r'[^A-Z0-9]', '', category.code.upper())[:4] or "GEN"
        elif category and category.name:
            norm_cat = unicodedata.normalize('NFKD', category.name).encode('ASCII', 'ignore').decode('utf-8').upper()
            clean_cat = re.sub(r'[^A-Z0-9]', '', norm_cat)
            cat_prefix = clean_cat[:3] if len(clean_cat) >= 3 else clean_cat or "GEN"

    # 2. Higieniza e extrai palavras-chave do nome do item
    norm_name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('utf-8').upper()
    clean_name = re.sub(r'[^A-Z0-9\s]', ' ', norm_name)
    
    # Remove stopwords comuns em língua portuguesa
    stopwords = {"DE", "DA", "DO", "DOS", "DAS", "E", "EM", "COM", "PARA", "POR", "C", "P", "A", "O", "OS", "AS", "AO", "AOS"}
    tokens = [token for token in clean_name.split() if token and token not in stopwords]

    if tokens:
        # Pega até 3 palavras principais e trunca se forem excessivamente longas
        body_parts = [t[:12] for t in tokens[:3]]
        name_slug = "-".join(body_parts)
    else:
        name_slug = "ITEM"

    # 3. Normaliza a unidade de medida
    unit_clean = re.sub(r'[^A-Z0-9]', '', unit_of_measure.upper())[:4] or "UN"

    # 4. Monta a base do SKU
    base_sku = f"{cat_prefix}-{name_slug}-{unit_clean}"

    # 5. Garante unicidade gerando sufixo sequencial
    seq = 1
    candidate_sku = f"{base_sku}-{seq:04d}"
    while repository.get_product_by_sku(db, sku=candidate_sku, organization_id=organization_id):
        seq += 1
        candidate_sku = f"{base_sku}-{seq:04d}"

    return candidate_sku


def create_new_product(db: Session, product_data: schemas.ProductCreate) -> models.Product:
    """Cadastra um novo produto gerando o SKU automaticamente se não informado."""
    if not product_data.sku or not product_data.sku.strip():
        product_data.sku = generate_product_sku(
            db,
            organization_id=product_data.organization_id,
            name=product_data.name,
            category_id=product_data.category_id,
            unit_of_measure=product_data.unit_of_measure
        )
    else:
        product_data.sku = product_data.sku.strip().upper()
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


def update_purchase_request_data(
    db: Session, 
    request_id: uuid.UUID, 
    organization_id: uuid.UUID, 
    request_data: schemas.PurchaseRequestUpdate
) -> models.PurchaseRequest:
    """Atualiza dados cadastrais da solicitação (apenas se em rascunho ou pendente de aprovação)."""
    db_request = repository.get_purchase_request_by_id(db, request_id=request_id, organization_id=organization_id)
    if not db_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Solicitação de compra não encontrada."
        )
    
    if db_request.status not in ("draft", "pending_approval"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não é permitido editar uma solicitação no status '{db_request.status}'."
        )

    return repository.update_purchase_request(db, db_request=db_request, request_data=request_data)


def delete_purchase_request_record(db: Session, request_id: uuid.UUID, organization_id: uuid.UUID) -> dict:
    """
    Exclui permanentemente uma solicitação de compra em qualquer status,
    limpando vínculos de ordens de compra e disparando deleção em cascata
    de itens, processos de cotação e eventos de aprovação.
    """
    db_request = repository.get_purchase_request_by_id(db, request_id=request_id, organization_id=organization_id)
    if not db_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Solicitação de compra não encontrada."
        )

    # 1. Desvincula ordens de compra para evitar conflito de chave estrangeira
    orders = repository.get_purchase_orders_by_request_id(db, request_id=request_id, organization_id=organization_id)
    for o in orders:
        o.purchase_request_id = None
        o.supplier_quote_id = None

    # 2. Remove a solicitação (itens, aprovações e cotação são removidos em cascata)
    req_number = db_request.request_number
    repository.delete_purchase_request(db, db_request=db_request)
    return {"detail": f"Solicitação {req_number} excluída com sucesso."}


def purge_purchase_requests(db: Session, organization_id: uuid.UUID, request_ids: list[uuid.UUID] | None = None) -> dict:
    """
    Rotina de limpeza de desenvolvimento: exclui múltiplas ou todas as solicitações de compra.
    """
    query = db.query(models.PurchaseRequest).filter(models.PurchaseRequest.organization_id == organization_id)
    if request_ids:
        query = query.filter(models.PurchaseRequest.id.in_(request_ids))
    
    requests = query.all()
    count = len(requests)
    
    for r in requests:
        orders = repository.get_purchase_orders_by_request_id(db, request_id=r.id, organization_id=organization_id)
        for o in orders:
            o.purchase_request_id = None
            o.supplier_quote_id = None
        db.delete(r)
    
    db.commit()
    return {"detail": f"{count} solicitação(ões) de compra excluída(s) com sucesso.", "deleted_count": count}



def cancel_purchase_request(db: Session, request_id: uuid.UUID, organization_id: uuid.UUID) -> models.PurchaseRequest:
    """
    Cancela uma solicitação de compra e quaisquer cotações/processos ativos associados.
    """
    db_request = repository.get_purchase_request_by_id(db, request_id=request_id, organization_id=organization_id)
    if not db_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Solicitação de compra não encontrada."
        )

    if db_request.status == "cancelled":
        return db_request

    # Se houver ordens de compra associadas, verifica se não foram recebidas
    orders = repository.get_purchase_orders_by_request_id(db, request_id=request_id, organization_id=organization_id)
    if any(o.status in ["received", "partially_received"] for o in orders):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível cancelar uma solicitação que possui ordens de compra já recebidas no almoxarifado."
        )

    # Cancela ordens emitidas
    for o in orders:
        if o.status in ["draft", "issued"]:
            repository.update_purchase_order_status(db, db_order=o, new_status="cancelled")

    # Cancela processo de cotação se houver
    if db_request.quotation_process and db_request.quotation_process.status != "cancelled":
        repository.update_quotation_process_status(db, db_process=db_request.quotation_process, new_status="cancelled")

    return repository.update_purchase_request_status(db, db_request=db_request, new_status="cancelled")


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
    2. Calcula o total da ordem a partir dos itens negociados + frete - desconto.
    3. Gera o número sequencial (OC-2026-0001).
    4. Persiste a ordem de compra com status inicial 'issued'.
    5. Se vinculada a uma solicitação, atualiza a solicitação para 'ordered'.
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

    items_total = sum(Decimal(str(item.quantity)) * Decimal(str(item.unit_price)) for item in order_data.items)
    freight = Decimal(str(order_data.freight_amount or 0))
    discount = Decimal(str(order_data.discount_amount or 0))
    total_order = items_total + freight - discount
    if total_order < Decimal("0.00"):
        total_order = Decimal("0.00")

    order_number = generate_order_number(db, organization_id=order_data.organization_id)

    db_order = repository.create_purchase_order(
        db=db,
        order_number=order_number,
        total_amount=total_order,
        order_data=order_data
    )

    if order_data.purchase_request_id:
        db_request = repository.get_purchase_request_by_id(
            db, 
            request_id=order_data.purchase_request_id, 
            organization_id=order_data.organization_id
        )
        if db_request:
            repository.update_purchase_request_status(db, db_request=db_request, new_status="ordered")

    return db_order


def generate_po_from_request(
    db: Session,
    request_id: uuid.UUID,
    current_user: User,
    data: schemas.GeneratePOFromRequest
) -> models.PurchaseOrder:
    """
    Gera uma Ordem de Compra oficial diretamente a partir de uma Solicitação de Compra aprovada.
    1. Valida se a solicitação existe e está 'approved'.
    2. Valida o fornecedor homologado.
    3. Calcula o total líquido = sum(itens) + frete - desconto.
    4. Gera o sequencial OC-YYYY-XXXX.
    5. Persiste a PO com purchase_request_id preenchido.
    6. Atualiza o status da Solicitação de Compra para 'ordered'.
    """
    db_request = repository.get_purchase_request_by_id(db, request_id=request_id, organization_id=current_user.organization_id)
    if not db_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitação de compra não encontrada."
        )

    if db_request.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Apenas solicitações com status 'Aprovada' podem gerar ordens de compra. Status atual: '{db_request.status}'."
        )

    supplier = repository.get_supplier_by_id(db, supplier_id=data.supplier_id, organization_id=current_user.organization_id)
    if not supplier or not supplier.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O fornecedor selecionado não existe ou está inativo."
        )

    if not data.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A ordem de compra precisa conter pelo menos um item negociado."
        )

    # 1. Calcula o total dos itens negociados
    items_total = sum(Decimal(str(item.quantity)) * Decimal(str(item.unit_price)) for item in data.items)
    freight = Decimal(str(data.freight_amount or 0))
    discount = Decimal(str(data.discount_amount or 0))
    total_net = items_total + freight - discount

    if total_net < Decimal("0.00"):
        total_net = Decimal("0.00")

    # 2. Gera sequencial e payload da PO
    order_number = generate_order_number(db, organization_id=current_user.organization_id)
    order_create_payload = schemas.PurchaseOrderCreate(
        organization_id=current_user.organization_id,
        buyer_id=current_user.id,
        purchase_request_id=db_request.id,
        supplier_id=data.supplier_id,
        cost_center_id=data.cost_center_id or db_request.cost_center_id,
        payment_terms=data.payment_terms,
        freight_type=data.freight_type,
        freight_amount=freight,
        discount_amount=discount,
        expected_delivery_date=data.expected_delivery_date,
        notes=data.notes,
        items=data.items
    )

    db_order = repository.create_purchase_order(
        db=db,
        order_number=order_number,
        total_amount=total_net,
        order_data=order_create_payload
    )

    # 3. Atualiza o status da solicitação para 'ordered'
    repository.update_purchase_request_status(db, db_request=db_request, new_status="ordered")

    return db_order


def receive_purchase_order_shipment(
    db: Session,
    order_id: uuid.UUID,
    current_user: User,
    data: schemas.PurchaseOrderReceive
) -> models.PurchaseOrder:
    """Registra o recebimento físico dos itens no almoxarifado com conferência e nota fiscal."""
    db_order = repository.get_purchase_order_by_id(db, order_id=order_id, organization_id=current_user.organization_id)
    if not db_order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ordem de compra não encontrada."
        )

    if db_order.status not in ["issued", "partially_received"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não é possível receber uma ordem que se encontra no status '{db_order.status}'."
        )

    received_order = repository.receive_purchase_order(
        db=db,
        db_order=db_order,
        invoice_number=data.invoice_number.strip(),
        received_by_id=current_user.id,
        invoice_attachment=data.invoice_attachment,
        received_at=data.received_at,
        notes=data.notes
    )

    # Notifica o módulo de Inventário para dar entrada física nos produtos recebidos
    for item in received_order.items:
        inventory_service.register_purchase_receipt(
            db=db,
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            product_id=item.product_id,
            quantity=item.quantity,
            unit_cost=item.unit_price,
            reference_doc=f"{received_order.order_number} / NF {data.invoice_number.strip()}",
            invoice_attachment=data.invoice_attachment,
            notes=f"Entrada por recebimento de Ordem de Compra. Fornecedor: {received_order.supplier.name if received_order.supplier else ''}"
        )

    db.commit()
    db.refresh(received_order)
    return received_order




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


def delete_purchase_order_record(db: Session, order_id: uuid.UUID, organization_id: uuid.UUID) -> dict:
    """Exclui permanentemente uma ordem de compra e seus itens vinculados."""
    db_order = repository.get_purchase_order_by_id(db, order_id=order_id, organization_id=organization_id)
    if not db_order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ordem de compra não encontrada."
        )

    num = db_order.order_number
    repository.delete_purchase_order(db, db_order=db_order)
    return {"detail": f"Ordem de compra {num} excluída com sucesso."}


def purge_purchase_orders(db: Session, organization_id: uuid.UUID, order_ids: list[uuid.UUID] | None = None) -> dict:
    """Rotina de limpeza de desenvolvimento: exclui ordens de compra de teste."""
    query = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.organization_id == organization_id)
    if order_ids:
        query = query.filter(models.PurchaseOrder.id.in_(order_ids))
    
    orders = query.all()
    count = len(orders)
    for o in orders:
        db.delete(o)
    db.commit()
    return {"detail": f"{count} ordem(ns) de compra excluída(s) com sucesso.", "deleted_count": count}


def delete_quotation_record(db: Session, quotation_id: uuid.UUID, organization_id: uuid.UUID) -> dict:
    """Exclui permanentemente um processo de cotação e propostas vinculadas."""
    quot = repository.get_quotation_process_by_id(db, quotation_id=quotation_id, organization_id=organization_id)
    if not quot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo de cotação não encontrado."
        )

    # Desvincula ordens de compra que apontavam para propostas desta cotação
    for q in quot.quotes:
        orders = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.supplier_quote_id == q.id).all()
        for o in orders:
            o.supplier_quote_id = None

    num = quot.quotation_number
    repository.delete_quotation_process(db, quotation=quot)
    return {"detail": f"Cotação {num} excluída com sucesso."}


def purge_quotations(db: Session, organization_id: uuid.UUID, quotation_ids: list[uuid.UUID] | None = None) -> dict:
    """Rotina de limpeza de desenvolvimento: exclui cotações de teste."""
    query = db.query(models.QuotationProcess).filter(models.QuotationProcess.organization_id == organization_id)
    if quotation_ids:
        query = query.filter(models.QuotationProcess.id.in_(quotation_ids))
    
    quots = query.all()
    count = len(quots)
    for quot in quots:
        for q in quot.quotes:
            orders = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.supplier_quote_id == q.id).all()
            for o in orders:
                o.supplier_quote_id = None
        db.delete(quot)
    db.commit()
    return {"detail": f"{count} cotação(ões) excluída(s) com sucesso.", "deleted_count": count}


# ==============================================================================
# 6. SERVIÇOS DE PROCESSOS DE COTAÇÃO (RFQ) E MAPA COMPARATIVO
# ==============================================================================


def generate_quotation_number(db: Session, organization_id: uuid.UUID) -> str:
    """Gera o próximo número sequencial da Cotação (Ex: COT-2026-0001)."""
    current_year = datetime.now(timezone.utc).year
    count = repository.count_quotation_processes_in_year(db, organization_id=organization_id, year=current_year)
    return f"COT-{current_year}-{(count + 1):04d}"


def open_quotation_process(
    db: Session,
    current_user,
    request_id: uuid.UUID,
    notes: str | None = None
) -> models.QuotationProcess:
    """
    Abre formalmente um Processo de Cotação (RFQ) para uma Solicitação de Compra aprovada.
    """
    db_request = repository.get_purchase_request_by_id(db, request_id=request_id, organization_id=current_user.organization_id)
    if not db_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitação de compra não encontrada."
        )

    if db_request.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Apenas solicitações com status 'approved' podem iniciar cotação. Status atual: '{db_request.status}'."
        )

    # Verifica se já existe processo de cotação para esta requisição
    existing_proc = repository.get_quotation_process_by_request_id(db, request_id=request_id, organization_id=current_user.organization_id)
    if existing_proc:
        return existing_proc

    quotation_number = generate_quotation_number(db, organization_id=current_user.organization_id)

    return repository.create_quotation_process(
        db=db,
        organization_id=current_user.organization_id,
        purchase_request_id=request_id,
        quotation_number=quotation_number,
        notes=notes
    )


def list_quotation_processes(
    db: Session,
    organization_id: uuid.UUID,
    status_filter: str | None = None
) -> list[models.QuotationProcess]:
    """Lista todos os processos de cotação abertos na organização."""
    return repository.get_all_quotation_processes(db, organization_id=organization_id, status=status_filter)


def get_quotation_process_details(
    db: Session,
    quotation_id: uuid.UUID,
    organization_id: uuid.UUID
) -> models.QuotationProcess:
    """Retorna detalhes de um processo de cotação com todas as propostas."""
    db_process = repository.get_quotation_process_by_id(db, quotation_id=quotation_id, organization_id=organization_id)
    if not db_process:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo de cotação não encontrado."
        )
    return db_process


def add_supplier_quote_to_process(
    db: Session,
    current_user,
    quotation_id: uuid.UUID,
    quote_data: schemas.SupplierQuoteCreate
) -> models.SupplierQuote:
    """
    Adiciona a proposta comercial de um fornecedor específico concorrente à cotação.
    """
    db_process = repository.get_quotation_process_by_id(db, quotation_id=quotation_id, organization_id=current_user.organization_id)
    if not db_process:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo de cotação não encontrado."
        )

    if db_process.status in ["completed", "cancelled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não é possível adicionar propostas a uma cotação com status '{db_process.status}'."
        )

    db_supplier = repository.get_supplier_by_id(db, supplier_id=quote_data.supplier_id, organization_id=current_user.organization_id)
    if not db_supplier or not db_supplier.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fornecedor selecionado é inválido ou está inativo."
        )

    # Calcula total da proposta: (soma dos itens) + frete - desconto
    items_sum = sum(
        Decimal(str(it.quantity)) * Decimal(str(it.unit_price)) 
        for it in quote_data.items
    )
    freight = Decimal(str(quote_data.freight_amount or 0))
    discount = Decimal(str(quote_data.discount_amount or 0))
    total_amount = max(Decimal("0.00"), items_sum + freight - discount)

    quote = repository.create_supplier_quote(
        db=db,
        organization_id=current_user.organization_id,
        quotation_process_id=quotation_id,
        total_amount=total_amount,
        quote_data=quote_data
    )

    # Transiciona processo para 'analyzing' se estava 'open'
    if db_process.status == "open":
        repository.update_quotation_process_status(db, db_process=db_process, new_status="analyzing")

    return quote


def get_quotation_comparison_matrix(
    db: Session,
    current_user,
    quotation_id: uuid.UUID
) -> schemas.QuotationComparisonMatrix:
    """
    Gera o Mapa Comparativo analítico de cotações com melhor preço por item e total.
    """
    db_process = repository.get_quotation_process_by_id(db, quotation_id=quotation_id, organization_id=current_user.organization_id)
    if not db_process:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo de cotação não encontrado."
        )

    purchase_request = db_process.purchase_request
    quotes = db_process.quotes

    items_comparison: list[schemas.QuotationComparisonItem] = []
    
    for req_item in purchase_request.items:
        supplier_prices: dict[str, Decimal] = {}
        lowest_price: Decimal | None = None
        lowest_sup_id: str | None = None

        for quote in quotes:
            for q_item in quote.items:
                if q_item.product_id == req_item.product_id:
                    u_price = Decimal(str(q_item.unit_price))
                    supplier_prices[str(quote.supplier_id)] = u_price
                    if lowest_price is None or u_price < lowest_price:
                        lowest_price = u_price
                        lowest_sup_id = str(quote.supplier_id)

        prod_name = req_item.product.name if req_item.product else "Item Solicitado"
        prod_sku = req_item.product.sku if req_item.product else "N/A"
        prod_unit = req_item.product.unit_of_measure if req_item.product else "UN"

        items_comparison.append(
            schemas.QuotationComparisonItem(
                product_id=req_item.product_id,
                product_name=prod_name,
                sku=prod_sku,
                unit_of_measure=prod_unit,
                requested_quantity=req_item.quantity,
                reference_unit_price=req_item.estimated_unit_price,
                supplier_prices=supplier_prices,
                lowest_unit_price=lowest_price,
                lowest_supplier_id=lowest_sup_id
            )
        )

    # Identifica melhor preço total e menor lead time global
    best_total_id: uuid.UUID | None = None
    best_total_val: Decimal | None = None
    best_lead_id: uuid.UUID | None = None
    best_lead_val: int | None = None

    for quote in quotes:
        tot = Decimal(str(quote.total_amount))
        if best_total_val is None or tot < best_total_val:
            best_total_val = tot
            best_total_id = quote.id

        if quote.lead_time_days is not None:
            if best_lead_val is None or quote.lead_time_days < best_lead_val:
                best_lead_val = quote.lead_time_days
                best_lead_id = quote.id

    return schemas.QuotationComparisonMatrix(
        quotation_id=db_process.id,
        quotation_number=db_process.quotation_number,
        purchase_request_number=purchase_request.request_number,
        status=db_process.status,
        items_comparison=items_comparison,
        quotes_summary=[schemas.SupplierQuoteResponse.model_validate(q) for q in quotes],
        best_total_quote_id=best_total_id,
        best_lead_time_quote_id=best_lead_id
    )


def select_winner_and_generate_order(
    db: Session,
    current_user,
    quotation_id: uuid.UUID,
    quote_id: uuid.UUID,
    notes: str | None = None
) -> models.PurchaseOrder:
    """
    Homologa a proposta vencedora de uma cotação e gera a Ordem de Compra oficial.
    """
    db_process = repository.get_quotation_process_by_id(db, quotation_id=quotation_id, organization_id=current_user.organization_id)
    if not db_process:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo de cotação não encontrado."
        )

    winning_quote = repository.get_supplier_quote_by_id(db, quote_id=quote_id, organization_id=current_user.organization_id)
    if not winning_quote or winning_quote.quotation_process_id != quotation_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposta comercial não encontrada nesta cotação."
        )

    # Se a cotação já estiver como 'completed', verifica se já existe uma Ordem de Compra emitida
    if db_process.status == "completed":
        existing_orders = repository.get_purchase_orders_by_request_id(
            db, request_id=db_process.purchase_request_id, organization_id=current_user.organization_id
        )
        if existing_orders:
            return existing_orders[0]

    # Marca a proposta vencedora como 'selected' e as demais como 'rejected'
    for q in db_process.quotes:
        if q.id == winning_quote.id:
            repository.update_supplier_quote_status(db, db_quote=q, new_status="selected")
        else:
            repository.update_supplier_quote_status(db, db_quote=q, new_status="rejected")

    # Marca processo de cotação como 'completed'
    repository.update_quotation_process_status(db, db_process=db_process, new_status="completed")

    # Transiciona a solicitação de compra para 'ordered'
    db_request = db_process.purchase_request
    repository.update_purchase_request_status(db, db_request=db_request, new_status="ordered")

    # Calcula data de entrega estimada com base no lead time prometido
    delivery_date = None
    if winning_quote.lead_time_days:
        from datetime import timedelta
        delivery_date = datetime.now(timezone.utc) + timedelta(days=winning_quote.lead_time_days)

    # Gera número da PO
    order_number = generate_order_number(db, organization_id=current_user.organization_id)

    # Monta os itens da PO a partir dos itens cotados na proposta vencedora
    po_items: list[schemas.PurchaseOrderItemCreate] = []
    for q_item in winning_quote.items:
        po_items.append(
            schemas.PurchaseOrderItemCreate(
                product_id=q_item.product_id,
                quantity=q_item.quantity,
                unit_price=q_item.unit_price
            )
        )

    po_data = schemas.PurchaseOrderCreate(
        organization_id=current_user.organization_id,
        purchase_request_id=db_request.id,
        supplier_id=winning_quote.supplier_id,
        buyer_id=current_user.id,
        cost_center_id=db_request.cost_center_id,
        supplier_quote_id=winning_quote.id,
        payment_terms=winning_quote.payment_terms,
        freight_type=winning_quote.freight_type or "CIF",
        freight_amount=winning_quote.freight_amount,
        discount_amount=winning_quote.discount_amount,
        expected_delivery_date=delivery_date,
        notes=f"Gerada automaticamente a partir da Cotação {db_process.quotation_number} (Proposta {winning_quote.quote_reference or winning_quote.id}).\n{notes or ''}".strip(),
        items=po_items
    )

    created_order = repository.create_purchase_order(
        db=db,
        order_number=order_number,
        total_amount=winning_quote.total_amount,
        order_data=po_data
    )

    return created_order


def cancel_quotation_process(
    db: Session,
    current_user,
    quotation_id: uuid.UUID
) -> models.QuotationProcess:
    """
    Cancela um processo de cotação e reverte a Solicitação de Compra vinculada para 'approved'.
    """
    db_process = repository.get_quotation_process_by_id(db, quotation_id=quotation_id, organization_id=current_user.organization_id)
    if not db_process:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo de cotação não encontrado."
        )

    if db_process.status == "cancelled":
        return db_process

    # Se já gerou PO e a PO já foi recebida, não pode cancelar
    orders = repository.get_purchase_orders_by_request_id(db, request_id=db_process.purchase_request_id, organization_id=current_user.organization_id)
    if any(o.status in ["received", "partially_received"] for o in orders):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível cancelar uma cotação com ordem de compra já recebida no almoxarifado."
        )

    # Cancela ordens de compra pendentes associadas
    for o in orders:
        if o.status in ["draft", "issued"]:
            repository.update_purchase_order_status(db, db_order=o, new_status="cancelled")

    # Atualiza status de todas as propostas para 'rejected'
    for q in db_process.quotes:
        repository.update_supplier_quote_status(db, db_quote=q, new_status="rejected")

    # Atualiza cotação para 'cancelled'
    repository.update_quotation_process_status(db, db_process=db_process, new_status="cancelled")

    # Reverte solicitação para 'approved'
    db_request = db_process.purchase_request
    if db_request and db_request.status == "ordered":
        repository.update_purchase_request_status(db, db_request=db_request, new_status="approved")

    return db_process


def reopen_quotation_process(
    db: Session,
    current_user,
    quotation_id: uuid.UUID
) -> models.QuotationProcess:
    """
    Reabre uma cotação homologada ou cancelada, desfazendo a homologação e cancelando ordens de compra emitidas não recebidas.
    """
    db_process = repository.get_quotation_process_by_id(db, quotation_id=quotation_id, organization_id=current_user.organization_id)
    if not db_process:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo de cotação não encontrado."
        )

    # Verifica se há ordens já recebidas
    orders = repository.get_purchase_orders_by_request_id(db, request_id=db_process.purchase_request_id, organization_id=current_user.organization_id)
    if any(o.status in ["received", "partially_received"] for o in orders):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível reabrir a cotação pois a ordem de compra vinculada já foi recebida no almoxarifado."
        )

    # Cancela as ordens emitidas não faturadas
    for o in orders:
        if o.status in ["draft", "issued"]:
            repository.update_purchase_order_status(db, db_order=o, new_status="cancelled")

    # Retorna todas as propostas para 'pending'
    for q in db_process.quotes:
        repository.update_supplier_quote_status(db, db_quote=q, new_status="pending")

    # Define status da cotação
    new_status = "analyzing" if len(db_process.quotes) > 0 else "open"
    repository.update_quotation_process_status(db, db_process=db_process, new_status=new_status)

    # Reverte solicitação de compra para 'approved'
    db_request = db_process.purchase_request
    if db_request:
        repository.update_purchase_request_status(db, db_request=db_request, new_status="approved")

    return db_process


def delete_supplier_quote(
    db: Session,
    current_user,
    quotation_id: uuid.UUID,
    quote_id: uuid.UUID
) -> dict:
    """
    Remove uma proposta de fornecedor concorrente de uma cotação.
    """
    db_process = repository.get_quotation_process_by_id(db, quotation_id=quotation_id, organization_id=current_user.organization_id)
    if not db_process:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo de cotação não encontrado."
        )

    if db_process.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível remover propostas de uma cotação homologada. Reabra a cotação primeiro."
        )

    quote = repository.get_supplier_quote_by_id(db, quote_id=quote_id, organization_id=current_user.organization_id)
    if not quote or quote.quotation_process_id != quotation_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposta comercial não encontrada nesta cotação."
        )

    repository.delete_supplier_quote(db, db_quote=quote)

    # Se não restar nenhuma proposta, volta status para 'open'
    remaining_quotes = [q for q in db_process.quotes if q.id != quote_id]
    if len(remaining_quotes) == 0 and db_process.status == "analyzing":
        repository.update_quotation_process_status(db, db_process=db_process, new_status="open")

    return {"detail": "Proposta comercial removida com sucesso."}


# ==============================================================================
# 9. FLUXO ÁGIL: MOTOR DE SUGESTÕES DE COMPRA & CONTROLE DE INVENTÁRIO
# ==============================================================================

def generate_replenishment_suggestions(
    db: Session,
    organization_id: uuid.UUID
) -> schemas.PurchaseSuggestionsSummary:
    """
    Motor de Sugestões de Compra (Replenishment Engine):
    Varre os produtos da organização identificando itens com saldo <= estoque mínimo.
    Calcula a necessidade de reposição = max_stock - current_stock.
    Classifica urgência:
    - 'critical': estoque zerado ou negativo
    - 'high': estoque <= 50% do mínimo
    - 'medium': estoque <= estoque mínimo
    """
    # Consulta os produtos que estão no ponto de reposição diretamente do serviço de Inventário
    products = inventory_service.get_replenishment_candidates(db, organization_id=organization_id)
    
    suggestion_items: list[schemas.PurchaseSuggestionItem] = []
    critical_count = 0
    total_cost = Decimal("0.00")

    for prod in products:
        current = prod.current_stock or Decimal("0.0000")
        min_s = prod.min_stock or Decimal("0.00")
        
        # Se max_stock definido e coerente, usa ele; senão usa dobro do mínimo ou 10
        if prod.max_stock and prod.max_stock > min_s:
            target_stock = prod.max_stock
        elif min_s > Decimal("0.00"):
            target_stock = min_s * Decimal("2.0")
        else:
            target_stock = Decimal("10.00")

        suggested_qty = target_stock - current
        if suggested_qty <= Decimal("0.00"):
            suggested_qty = min_s if min_s > Decimal("0.00") else Decimal("1.00")

        ref_price = prod.reference_price or Decimal("0.0000")
        est_total = suggested_qty * ref_price
        total_cost += est_total

        # Nível de urgência e criticidade de estoque
        if current <= Decimal("0.00"):
            urgency = "critical"  # Estoque zerado / esgotado
            critical_count += 1
        elif min_s > Decimal("0.00") and current < min_s:
            urgency = "high"  # Abaixo do estoque mínimo configurado (Crítico)
            critical_count += 1
        else:
            urgency = "medium"  # No ponto de pedido exato (Saldo == Mínimo)

        suggestion_items.append(
            schemas.PurchaseSuggestionItem(
                product_id=prod.id,
                product_name=prod.name,
                sku=prod.sku,
                category_name=prod.category.name if prod.category else None,
                brand=prod.brand,
                unit_of_measure=prod.unit_of_measure,
                current_stock=current,
                min_stock=min_s,
                max_stock=prod.max_stock,
                suggested_quantity=suggested_qty,
                reference_price=ref_price,
                estimated_total=est_total,
                urgency_level=urgency,
                storage_location=prod.storage_location
            )
        )

    # Ordena: críticos primeiro, depois high, depois medium
    urgency_order = {"critical": 0, "high": 1, "medium": 2}
    suggestion_items.sort(key=lambda item: (urgency_order.get(item.urgency_level, 3), item.product_name))

    return schemas.PurchaseSuggestionsSummary(
        total_suggestions=len(suggestion_items),
        critical_count=critical_count,
        estimated_total_cost=total_cost,
        items=suggestion_items
    )


def create_quick_replenishment_order(
    db: Session,
    current_user: User,
    data: schemas.QuickReplenishmentOrderCreate
) -> models.PurchaseOrder:
    """
    Fluxo Ágil / Enxuto: Emite uma Ordem de Compra direta para um fornecedor
    a partir de múltiplos itens de sugestão de reposição, sem exigir abertura prévia de PR.
    """
    supplier = repository.get_supplier_by_id(db, supplier_id=data.supplier_id, organization_id=current_user.organization_id)
    if not supplier or not supplier.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O fornecedor selecionado não existe ou está inativo."
        )

    if not data.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A ordem de reposição precisa conter pelo menos um produto selecionado."
        )

    items_total = sum(Decimal(str(item.quantity)) * Decimal(str(item.unit_price)) for item in data.items)
    freight = Decimal(str(data.freight_amount or 0))
    discount = Decimal(str(data.discount_amount or 0))
    total_order = items_total + freight - discount
    if total_order < Decimal("0.00"):
        total_order = Decimal("0.00")

    order_number = generate_order_number(db, organization_id=current_user.organization_id)

    order_payload = schemas.PurchaseOrderCreate(
        organization_id=current_user.organization_id,
        buyer_id=current_user.id,
        purchase_request_id=None,  # Ordem direta de reposição
        supplier_id=data.supplier_id,
        cost_center_id=data.cost_center_id,
        payment_terms=data.payment_terms or supplier.payment_terms or "30 DDL",
        freight_type=data.freight_type or "CIF",
        freight_amount=freight,
        discount_amount=discount,
        expected_delivery_date=data.expected_delivery_date,
        notes=data.notes or "Pedido de Reposição Ágil de Estoque (Assistente de Compras)",
        items=data.items
    )

    db_order = repository.create_purchase_order(
        db=db,
        order_number=order_number,
        total_amount=total_order,
        order_data=order_payload
    )

    return db_order




