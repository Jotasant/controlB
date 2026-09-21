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

    from controlb.modules.identity.contact_identity import reject_legacy_fields, validate_link
    reject_legacy_fields(supplier_data, ("contact_name", "email", "phone"))
    validate_link(db, supplier_data.organization_id, supplier_data.contact_id)
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

    from controlb.modules.identity.contact_identity import reject_legacy_fields, validate_link
    reject_legacy_fields(supplier_data, ("contact_name", "email", "phone"))
    if "contact_id" in supplier_data.model_fields_set:
        validate_link(db, organization_id, supplier_data.contact_id)
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

def get_purchase_request_document(
    db: Session,
    purchase_request: models.PurchaseRequest,
    organization_id: uuid.UUID,
):
    """Resolve o cabeçalho canônico e atualiza a projeção legada da solicitação."""
    from controlb.modules.documents import service as documents_service

    if not purchase_request.document_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A Solicitação de Compra não possui identidade documental.",
        )
    document = documents_service.get_document(
        db, purchase_request.document_id, organization_id
    )
    if (
        document.document_type != "PURCHASE_REQUEST"
        or document.native_id != purchase_request.id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O cabeçalho documental da Solicitação de Compra é inconsistente.",
        )

    purchase_request.request_number = document.document_number
    purchase_request.status = document.current_status.lower()
    purchase_request.requester_id = document.responsible_id
    return document


def transition_purchase_request_status(
    db: Session,
    purchase_request: models.PurchaseRequest,
    organization_id: uuid.UUID,
    new_status: str,
    *,
    current_user: User | None = None,
    event_type: str = "STATUS_CHANGED",
    event_metadata: dict | None = None,
    idempotency_key: str | None = None,
    record_if_unchanged: bool = False,
) -> models.PurchaseRequest:
    """Única porta para transições, inclusive as iniciadas por cotação ou pedido."""
    normalized_status = new_status.strip().upper()
    document = None
    if purchase_request.document_id:
        document = get_purchase_request_document(
            db, purchase_request, organization_id
        )
        previous_status = document.current_status
    else:
        # Compatibilidade para objetos isolados de testes e bases pré-migração.
        previous_status = purchase_request.status.strip().upper()

    if normalized_status == previous_status and not record_if_unchanged:
        return purchase_request

    purchase_request.status = normalized_status.lower()
    repository.update_purchase_request_status(
        db,
        db_request=purchase_request,
        new_status=purchase_request.status,
    )

    if document is not None:
        from controlb.modules.documents import service as documents_service

        documents_service.record_event(
            db,
            organization_id=organization_id,
            document=document,
            event_type=event_type,
            previous_status=previous_status,
            new_status=normalized_status,
            event_metadata=event_metadata,
            idempotency_key=idempotency_key,
            created_by_id=current_user.id if current_user else None,
        )
        purchase_request.status = document.current_status.lower()

    if (
        purchase_request.replenishment_id
        and normalized_status in {"CANCELLED", "DELETED"}
    ):
        from controlb.modules.documents import service as documents_service

        replenishment = repository.get_inventory_replenishment_by_id(
            db,
            purchase_request.replenishment_id,
            organization_id,
        )
        if replenishment:
            replenishment_document = get_inventory_replenishment_document(
                db, replenishment, organization_id
            )
            if replenishment_document.current_status != "CANCELLED":
                documents_service.record_event(
                    db,
                    organization_id=organization_id,
                    document=replenishment_document,
                    event_type=(
                        "REQUEST_CANCELLED"
                        if normalized_status == "CANCELLED"
                        else "REQUEST_DELETED"
                    ),
                    previous_status=replenishment_document.current_status,
                    new_status="CANCELLED",
                    event_metadata={"purchase_request_id": str(purchase_request.id)},
                    idempotency_key=(
                        f"replenishment:{replenishment.id}:request:"
                        f"{purchase_request.id}:{normalized_status.lower()}"
                    ),
                    created_by_id=current_user.id if current_user else None,
                )
                replenishment.status = replenishment_document.current_status

    db.commit()
    db.refresh(purchase_request)
    return purchase_request


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

    organization_id = request_data.organization_id or current_user.organization_id
    request_data.organization_id = organization_id
    replenishment = None
    replenishment_document = None
    if request_data.replenishment_id:
        replenishment = repository.get_inventory_replenishment_by_id(
            db,
            request_data.replenishment_id,
            organization_id,
        )
        if not replenishment:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A reposição de estoque vinculada é inválida.",
            )
        replenishment_document = get_inventory_replenishment_document(
            db, replenishment, organization_id
        )
        if replenishment_document.current_status != "OPEN":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A reposição selecionada já foi encaminhada ou concluída.",
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

    from controlb.modules.documents import schemas as document_schemas
    from controlb.modules.documents import service as documents_service

    request_id = uuid.uuid4()
    request_document = documents_service.create_document(
        db,
        organization_id=request_data.organization_id,
        payload=document_schemas.DocumentCreate(
            category="purchase.request",
            document_type="PURCHASE_REQUEST",
            native_id=request_id,
            title="Solicitação de Compra",
            current_status="PENDING_APPROVAL",
            description=request_data.justification,
            origin_module="PURCHASING",
            responsible_id=current_user.id,
        ),
        current_user=current_user,
    )
    documents_service.update_document(
        db,
        request_document.id,
        request_data.organization_id,
        document_schemas.DocumentUpdate(
            title=f"Solicitação de Compra {request_document.document_number}"
        ),
        current_user=current_user,
    )

    # 2. Persiste a extensão específica do módulo de Compras.
    created_pr = repository.create_purchase_request(
        db=db,
        request_id=request_id,
        document_id=request_document.id,
        requester_id=current_user.id,
        request_number=request_document.document_number,
        total_estimated=total_estimated,
        request_data=request_data
    )
    request_document.issued_at = created_pr.created_at

    if replenishment is not None and replenishment_document is not None:
        documents_service.relate_documents(
            db,
            organization_id=organization_id,
            parent_document=replenishment_document,
            child_document=request_document,
            relation_type="generated",
            created_by_id=current_user.id,
        )
        documents_service.record_event(
            db,
            organization_id=organization_id,
            document=replenishment_document,
            event_type="PURCHASE_REQUEST_CREATED",
            previous_status=replenishment_document.current_status,
            new_status="REQUESTED",
            event_metadata={"purchase_request_id": str(created_pr.id)},
            idempotency_key=(
                f"replenishment:{replenishment.id}:request:{created_pr.id}"
            ),
            created_by_id=current_user.id,
        )
        replenishment.status = replenishment_document.current_status
    db.commit()
    db.refresh(created_pr)
    return created_pr


def list_purchase_requests(
    db: Session, 
    organization_id: uuid.UUID, 
    status_filter: str | None = None
) -> list[models.PurchaseRequest]:
    """Retorna as solicitações de compra da organização com filtro opcional."""
    requests = repository.get_all_purchase_requests(
        db, organization_id=organization_id, status=status_filter
    )
    for purchase_request in requests:
        get_purchase_request_document(db, purchase_request, organization_id)
    return requests


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
    get_purchase_request_document(db, db_request, organization_id)
    return db_request


def update_purchase_request_data(
    db: Session, 
    request_id: uuid.UUID, 
    organization_id: uuid.UUID, 
    request_data: schemas.PurchaseRequestUpdate,
    current_user: User | None = None,
) -> models.PurchaseRequest:
    """Atualiza dados cadastrais da solicitação (apenas se em rascunho ou pendente de aprovação)."""
    db_request = repository.get_purchase_request_by_id(db, request_id=request_id, organization_id=organization_id)
    if not db_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Solicitação de compra não encontrada."
        )
    
    request_document = get_purchase_request_document(db, db_request, organization_id)
    if db_request.status not in ("draft", "pending_approval"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não é permitido editar uma solicitação no status '{db_request.status}'."
        )

    updated = repository.update_purchase_request(
        db, db_request=db_request, request_data=request_data
    )
    if request_data.justification is not None:
        from controlb.modules.documents import schemas as document_schemas
        from controlb.modules.documents import service as documents_service

        documents_service.update_document(
            db,
            request_document.id,
            organization_id,
            document_schemas.DocumentUpdate(description=updated.justification),
            current_user=current_user,
        )
    db.commit()
    db.refresh(updated)
    return updated


def delete_purchase_request_record(
    db: Session,
    request_id: uuid.UUID,
    organization_id: uuid.UUID,
    current_user: User | None = None,
) -> dict:
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

    request_document = None
    if db_request.document_id:
        request_document = get_purchase_request_document(
            db, db_request, organization_id
        )

    # 1. Desvincula ordens de compra para evitar conflito de chave estrangeira
    orders = repository.get_purchase_orders_by_request_id(db, request_id=request_id, organization_id=organization_id)
    for o in orders:
        o.purchase_request_id = None
        o.supplier_quote_id = None

    # 2. Remove a solicitação (itens, aprovações e cotação são removidos em cascata)
    req_number = db_request.request_number
    if request_document is not None:
        from controlb.modules.documents import service as documents_service

        documents_service.record_event(
            db,
            organization_id=organization_id,
            document=request_document,
            event_type="DELETED",
            previous_status=db_request.status,
            new_status="DELETED",
            created_by_id=current_user.id if current_user else None,
        )
    repository.delete_purchase_request(db, db_request=db_request)
    return {"detail": f"Solicitação {req_number} excluída com sucesso."}


def purge_purchase_requests(
    db: Session,
    organization_id: uuid.UUID,
    request_ids: list[uuid.UUID] | None = None,
    current_user: User | None = None,
) -> dict:
    """
    Rotina de limpeza de desenvolvimento: exclui múltiplas ou todas as solicitações de compra.
    """
    query = db.query(models.PurchaseRequest).filter(models.PurchaseRequest.organization_id == organization_id)
    if request_ids:
        query = query.filter(models.PurchaseRequest.id.in_(request_ids))
    
    requests = query.all()
    count = len(requests)
    
    for r in requests:
        if r.document_id:
            from controlb.modules.documents import service as documents_service

            request_document = get_purchase_request_document(db, r, organization_id)
            documents_service.record_event(
                db,
                organization_id=organization_id,
                document=request_document,
                event_type="DELETED",
                previous_status=r.status,
                new_status="DELETED",
                created_by_id=current_user.id if current_user else None,
            )
        orders = repository.get_purchase_orders_by_request_id(db, request_id=r.id, organization_id=organization_id)
        for o in orders:
            o.purchase_request_id = None
            o.supplier_quote_id = None
        db.delete(r)
    
    db.commit()
    return {"detail": f"{count} solicitação(ões) de compra excluída(s) com sucesso.", "deleted_count": count}



def cancel_purchase_request(
    db: Session,
    request_id: uuid.UUID,
    organization_id: uuid.UUID,
    current_user: User | None = None,
) -> models.PurchaseRequest:
    """
    Cancela uma solicitação de compra e quaisquer cotações/processos ativos associados.
    """
    db_request = repository.get_purchase_request_by_id(db, request_id=request_id, organization_id=organization_id)
    if not db_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Solicitação de compra não encontrada."
        )

    if db_request.document_id:
        get_purchase_request_document(db, db_request, organization_id)
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
            transition_purchase_order_status(
                db,
                o,
                organization_id,
                "CANCELLED",
                current_user=current_user,
                event_type="PURCHASE_REQUEST_CANCELLED",
                event_metadata={"purchase_request_id": str(db_request.id)},
            )

    # Cancela o processo de cotação pela mesma timeline documental.
    if db_request.quotation_process and db_request.quotation_process.status != "cancelled":
        transition_quotation_process_status(
            db,
            db_request.quotation_process,
            organization_id,
            "CANCELLED",
            current_user=current_user,
            event_type="PURCHASE_REQUEST_CANCELLED",
            event_metadata={"purchase_request_id": str(db_request.id)},
        )

    return transition_purchase_request_status(
        db,
        db_request,
        organization_id,
        "CANCELLED",
        current_user=current_user,
        event_type="CANCELLED",
    )


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

    if db_request.document_id:
        get_purchase_request_document(
            db, db_request, current_user.organization_id
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

    # Atualiza status e timeline da solicitação na mesma transação.
    new_status = "approved" if action_data.action == "approved" else "rejected"
    updated_pr = transition_purchase_request_status(
        db,
        db_request,
        current_user.organization_id,
        new_status,
        current_user=current_user,
        event_type="APPROVED" if action_data.action == "approved" else "REJECTED",
        event_metadata={"comments": action_data.comments} if action_data.comments else None,
    )

    return updated_pr


# ==============================================================================
# 5. ORDENS DE COMPRA OFICIAIS (PurchaseOrder)
# ==============================================================================


def get_purchase_order_document(
    db: Session,
    purchase_order: models.PurchaseOrder,
    organization_id: uuid.UUID,
):
    """Resolve o cabeçalho canônico e atualiza a projeção nativa do pedido."""
    from controlb.modules.documents import service as documents_service

    if not purchase_order.document_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A Ordem de Compra não possui identidade documental.",
        )
    document = documents_service.get_document(
        db, purchase_order.document_id, organization_id
    )
    if (
        document.document_type != "PURCHASE_ORDER"
        or document.native_id != purchase_order.id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O cabeçalho documental da Ordem de Compra é inconsistente.",
        )

    purchase_order.order_number = document.document_number
    purchase_order.status = document.current_status.lower()
    purchase_order.buyer_id = document.responsible_id
    purchase_order.notes = document.description
    return document


def get_inventory_replenishment_document(
    db: Session,
    replenishment: models.InventoryReplenishment,
    organization_id: uuid.UUID,
):
    """Resolve e valida a identidade canônica de uma necessidade de reposição."""
    from controlb.modules.documents import service as documents_service

    document = documents_service.get_document(
        db, replenishment.document_id, organization_id
    )
    if (
        document.document_type != "REPLENISHMENT"
        or document.native_id != replenishment.id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O cabeçalho documental da reposição é inconsistente.",
        )
    replenishment.replenishment_number = document.document_number
    replenishment.status = document.current_status
    return document


def transition_purchase_order_status(
    db: Session,
    purchase_order: models.PurchaseOrder,
    organization_id: uuid.UUID,
    new_status: str,
    *,
    current_user: User | None = None,
    event_type: str = "STATUS_CHANGED",
    event_metadata: dict | None = None,
    idempotency_key: str | None = None,
    record_if_unchanged: bool = False,
) -> models.PurchaseOrder:
    """Única porta para transições de estado da Ordem de Compra."""
    normalized_status = new_status.strip().upper()
    document = None
    if purchase_order.document_id:
        document = get_purchase_order_document(
            db, purchase_order, organization_id
        )
        previous_status = document.current_status
    else:
        # Compatibilidade para objetos isolados de testes e bases pré-migração.
        previous_status = purchase_order.status.strip().upper()

    if normalized_status == previous_status and not record_if_unchanged:
        return purchase_order

    purchase_order.status = normalized_status.lower()
    repository.update_purchase_order_status(
        db,
        db_order=purchase_order,
        new_status=purchase_order.status,
    )

    if document is not None:
        from controlb.modules.documents import service as documents_service

        documents_service.record_event(
            db,
            organization_id=organization_id,
            document=document,
            event_type=event_type,
            previous_status=previous_status,
            new_status=normalized_status,
            event_metadata=event_metadata,
            idempotency_key=idempotency_key,
            created_by_id=current_user.id if current_user else None,
        )
        purchase_order.status = document.current_status.lower()

    if (
        purchase_order.replenishment_id
        and normalized_status in {"CANCELLED", "DELETED"}
    ):
        from controlb.modules.documents import service as documents_service

        replenishment = repository.get_inventory_replenishment_by_id(
            db,
            purchase_order.replenishment_id,
            organization_id,
        )
        if replenishment:
            replenishment_document = get_inventory_replenishment_document(
                db, replenishment, organization_id
            )
            documents_service.record_event(
                db,
                organization_id=organization_id,
                document=replenishment_document,
                event_type=(
                    "ORDER_CANCELLED"
                    if normalized_status == "CANCELLED"
                    else "ORDER_DELETED"
                ),
                previous_status=replenishment_document.current_status,
                new_status="CANCELLED",
                event_metadata={"purchase_order_id": str(purchase_order.id)},
                idempotency_key=(
                    f"replenishment:{replenishment.id}:order:{purchase_order.id}:"
                    f"{normalized_status.lower()}"
                ),
                created_by_id=current_user.id if current_user else None,
            )
            replenishment.status = replenishment_document.current_status

    db.commit()
    db.refresh(purchase_order)
    return purchase_order


def persist_purchase_order(
    db: Session,
    *,
    current_user: User,
    total_amount: Decimal,
    order_data: schemas.PurchaseOrderCreate,
) -> models.PurchaseOrder:
    """Cria cabeçalho, extensão nativa e arestas na mesma unidade de trabalho."""
    from controlb.modules.documents import schemas as document_schemas
    from controlb.modules.documents import service as documents_service

    organization_id = order_data.organization_id or current_user.organization_id
    request = None
    if order_data.purchase_request_id:
        request = repository.get_purchase_request_by_id(
            db,
            request_id=order_data.purchase_request_id,
            organization_id=organization_id,
        )
        if not request:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A Solicitação de Compra vinculada é inválida.",
            )

    if request and request.replenishment_id and not order_data.replenishment_id:
        order_data = order_data.model_copy(
            update={"replenishment_id": request.replenishment_id}
        )

    replenishment = None
    if order_data.replenishment_id:
        replenishment = repository.get_inventory_replenishment_by_id(
            db,
            replenishment_id=order_data.replenishment_id,
            organization_id=organization_id,
        )
        if not replenishment:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A reposição de estoque vinculada é inválida.",
            )

    supplier_quote = None
    quotation_process = None
    if order_data.supplier_quote_id:
        supplier_quote = repository.get_supplier_quote_by_id(
            db,
            quote_id=order_data.supplier_quote_id,
            organization_id=organization_id,
        )
        if not supplier_quote:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A proposta de fornecedor vinculada é inválida.",
            )
        quotation_process = supplier_quote.quotation_process

    order_id = uuid.uuid4()
    order_document = documents_service.create_document(
        db,
        organization_id=organization_id,
        payload=document_schemas.DocumentCreate(
            category="purchase.order",
            document_type="PURCHASE_ORDER",
            native_id=order_id,
            title="Ordem de Compra",
            current_status="ISSUED",
            description=order_data.notes,
            origin_module="PURCHASING",
            responsible_id=order_data.buyer_id or current_user.id,
            payload={
                "supplier_id": str(order_data.supplier_id),
                "purchase_request_id": (
                    str(order_data.purchase_request_id)
                    if order_data.purchase_request_id
                    else None
                ),
                "replenishment_id": (
                    str(order_data.replenishment_id)
                    if order_data.replenishment_id
                    else None
                ),
                "supplier_quote_id": (
                    str(order_data.supplier_quote_id)
                    if order_data.supplier_quote_id
                    else None
                ),
            },
            issued_at=utcnow(),
        ),
        current_user=current_user,
    )
    order_document.title = f"Ordem de Compra {order_document.document_number}"

    created_order = repository.create_purchase_order(
        db=db,
        order_id=order_id,
        document_id=order_document.id,
        order_number=order_document.document_number,
        total_amount=total_amount,
        order_data=order_data,
    )
    order_document.issued_at = created_order.created_at

    if request and request.document_id:
        request_document = get_purchase_request_document(
            db, request, organization_id
        )
        documents_service.relate_documents(
            db,
            organization_id=organization_id,
            parent_document=request_document,
            child_document=order_document,
            relation_type="generated",
            created_by_id=current_user.id,
        )

    if quotation_process and quotation_process.document_id:
        quotation_document = get_quotation_process_document(
            db, quotation_process, organization_id
        )
        documents_service.relate_documents(
            db,
            organization_id=organization_id,
            parent_document=quotation_document,
            child_document=order_document,
            relation_type="generated",
            created_by_id=current_user.id,
        )

    if replenishment:
        replenishment_document = get_inventory_replenishment_document(
            db, replenishment, organization_id
        )
        documents_service.relate_documents(
            db,
            organization_id=organization_id,
            parent_document=replenishment_document,
            child_document=order_document,
            relation_type="generated",
            created_by_id=current_user.id,
        )
        documents_service.record_event(
            db,
            organization_id=organization_id,
            document=replenishment_document,
            event_type="ORDER_CREATED",
            previous_status=replenishment_document.current_status,
            new_status="ORDERED",
            event_metadata={"purchase_order_id": str(created_order.id)},
            idempotency_key=(
                f"replenishment:{replenishment.id}:order:{created_order.id}"
            ),
            created_by_id=current_user.id,
        )
        replenishment.status = replenishment_document.current_status

    db.commit()
    db.refresh(created_order)
    return created_order


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

    db_order = persist_purchase_order(
        db,
        current_user=current_user,
        total_amount=total_order,
        order_data=order_data,
    )

    if order_data.purchase_request_id:
        db_request = repository.get_purchase_request_by_id(
            db, 
            request_id=order_data.purchase_request_id, 
            organization_id=order_data.organization_id
        )
        if db_request:
            transition_purchase_request_status(
                db,
                db_request,
                order_data.organization_id,
                "ORDERED",
                current_user=current_user,
                event_type="ORDER_CREATED",
                event_metadata={"purchase_order_id": str(db_order.id)},
                idempotency_key=(
                    f"purchase-request:{db_request.id}:order:{db_order.id}"
                ),
                record_if_unchanged=True,
            )

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

    # 2. Monta a extensão específica; o cabeçalho gerará o sequencial canônico.
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

    db_order = persist_purchase_order(
        db,
        current_user=current_user,
        total_amount=total_net,
        order_data=order_create_payload,
    )

    # 3. Atualiza o status e a timeline canônica da solicitação.
    transition_purchase_request_status(
        db,
        db_request,
        current_user.organization_id,
        "ORDERED",
        current_user=current_user,
        event_type="ORDER_CREATED",
        event_metadata={"purchase_order_id": str(db_order.id)},
        idempotency_key=f"purchase-request:{db_request.id}:order:{db_order.id}",
        record_if_unchanged=True,
    )

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

    order_document = None
    if db_order.document_id:
        order_document = get_purchase_order_document(
            db, db_order, current_user.organization_id
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
    if order_document is not None:
        from controlb.modules.documents import service as documents_service
        from controlb.modules.finance import schemas as finance_schemas
        from controlb.modules.finance import service as finance_service

        supplier_name = (
            received_order.supplier.name if received_order.supplier else "Fornecedor"
        )
        effective_received_at = received_order.received_at or datetime.now(timezone.utc)
        inventory_receipt = inventory_service.record_purchase_order_receipt(
            db=db,
            organization_id=current_user.organization_id,
            current_user=current_user,
            purchase_order_id=received_order.id,
            purchase_order_document=order_document,
            purchase_order_number=received_order.order_number,
            supplier_name=supplier_name,
            invoice_number=data.invoice_number.strip(),
            received_at=effective_received_at,
            items=list(received_order.items),
            invoice_attachment=data.invoice_attachment,
            notes=data.notes,
        )

        receipt_document = documents_service.get_document(
            db, inventory_receipt.document_id, current_user.organization_id
        )

        fiscal_document = finance_service.persist_fiscal_document(
            db,
            current_user.organization_id,
            current_user,
            finance_schemas.FiscalDocumentCreate(
                direction="INBOUND",
                document_type=data.invoice_type,
                document_number=data.invoice_number.strip(),
                series=data.invoice_series,
                access_key=data.invoice_access_key,
                issuer_name=supplier_name,
                issuer_cnpj_cpf=(
                    received_order.supplier.cnpj_cpf
                    if received_order.supplier
                    else None
                ),
                recipient_name=(
                    str(current_user.organization.name)
                    if (current_user.organization and hasattr(current_user.organization, "name") and current_user.organization.name)
                    else "Organização"
                ),
                issue_date=(
                    data.invoice_issue_date
                    or (received_order.received_at.date() if received_order.received_at else datetime.now(timezone.utc).date())
                ),
                total_amount=received_order.total_amount,
                tax_amount=data.invoice_tax_amount,
                purchase_order_id=received_order.id,
                supplier_id=received_order.supplier_id,
                file_attachment=data.invoice_attachment,
                notes=data.notes,
                status="authorized",
            ),
            source_document=receipt_document,
        )

        inventory_receipt.fiscal_document_id = fiscal_document.id
        for mv in inventory_receipt.movements:
            mv.fiscal_document_id = fiscal_document.id
        db.flush()

        if data.generate_payable:
            instrument_payload = None
            if data.digitable_line or data.barcode or data.pix_code:
                instrument_payload = finance_schemas.PaymentInstrumentCreate(
                    instrument_type="BOLETO" if (data.digitable_line or data.barcode) else "PIX",
                    barcode=data.barcode,
                    digitable_line=data.digitable_line,
                    pix_code=data.pix_code,
                )

            created_payables = finance_service.create_payable_expense(
                db,
                current_user.organization_id,
                current_user,
                finance_schemas.PayableCreate(
                    supplier_id=received_order.supplier_id,
                    purchase_order_id=received_order.id,
                    fiscal_document_id=fiscal_document.id,
                    inventory_receipt_id=inventory_receipt.id,
                    cost_center_id=received_order.cost_center_id,
                    financial_category_id=data.financial_category_id,
                    description=(
                        f"Compra {received_order.order_number} • "
                        f"NF {data.invoice_number.strip()}"
                    ),
                    favored_name=supplier_name,
                    original_amount=received_order.total_amount,
                    issue_date=(
                        data.invoice_issue_date
                        or (received_order.received_at.date() if received_order.received_at else datetime.now(timezone.utc).date())
                    ),
                    due_date=data.payable_due_date,
                    expense_nature=data.expense_nature,
                    obligation_type="GOODS_SUPPLIER",
                    business_origin="PURCHASE",
                    payment_method_expected=data.payment_method_expected,
                    installments_count=data.installments_count,
                    installment_frequency_days=data.installment_frequency_days,
                    instrument=instrument_payload,
                    notes=data.notes,
                ),
            )

            if created_payables:
                first_payable = created_payables[0]
                for mv in inventory_receipt.movements:
                    mv.payable_id = first_payable.id
                db.flush()

    if received_order.document_id:
        from controlb.modules.documents import schemas as document_schemas
        from controlb.modules.documents import service as documents_service

        documents_service.update_document(
            db,
            received_order.document_id,
            current_user.organization_id,
            document_schemas.DocumentUpdate(description=received_order.notes),
            current_user=current_user,
        )
    return transition_purchase_order_status(
        db,
        received_order,
        current_user.organization_id,
        "RECEIVED",
        current_user=current_user,
        event_type="RECEIVED",
        event_metadata={
            "invoice_number": data.invoice_number.strip(),
            "received_at": (
                received_order.received_at.isoformat()
                if received_order.received_at
                else None
            ),
        },
        idempotency_key=f"purchase-order:{received_order.id}:received",
    )




def list_purchase_orders(
    db: Session, 
    organization_id: uuid.UUID, 
    status_filter: str | None = None
) -> list[models.PurchaseOrder]:
    """Retorna todas as ordens de compra da organização."""
    orders = repository.get_all_purchase_orders(
        db, organization_id=organization_id, status=status_filter
    )
    for purchase_order in orders:
        get_purchase_order_document(db, purchase_order, organization_id)
    return orders


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
    get_purchase_order_document(db, db_order, organization_id)
    return db_order


def cancel_purchase_order(
    db: Session, 
    order_id: uuid.UUID, 
    organization_id: uuid.UUID,
    current_user: User | None = None,
) -> models.PurchaseOrder:
    """Cancela de forma controlada uma ordem de compra emitida."""
    db_order = repository.get_purchase_order_by_id(db, order_id=order_id, organization_id=organization_id)
    if not db_order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ordem de compra não encontrada."
        )

    if db_order.document_id:
        get_purchase_order_document(db, db_order, organization_id)

    if db_order.status in ["closed", "cancelled", "received", "partially_received"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não é possível cancelar uma ordem com status '{db_order.status}'."
        )

    return transition_purchase_order_status(
        db,
        db_order,
        organization_id,
        "CANCELLED",
        current_user=current_user,
        event_type="CANCELLED",
    )


def delete_purchase_order_record(
    db: Session,
    order_id: uuid.UUID,
    organization_id: uuid.UUID,
    current_user: User | None = None,
) -> dict:
    """Exclui permanentemente uma ordem de compra e seus itens vinculados."""
    db_order = repository.get_purchase_order_by_id(db, order_id=order_id, organization_id=organization_id)
    if not db_order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ordem de compra não encontrada."
        )

    num = db_order.order_number
    if db_order.document_id:
        transition_purchase_order_status(
            db,
            db_order,
            organization_id,
            "DELETED",
            current_user=current_user,
            event_type="DELETED",
        )
    repository.delete_purchase_order(db, db_order=db_order)
    db.commit()
    return {"detail": f"Ordem de compra {num} excluída com sucesso."}


def purge_purchase_orders(
    db: Session,
    organization_id: uuid.UUID,
    order_ids: list[uuid.UUID] | None = None,
    current_user: User | None = None,
) -> dict:
    """Rotina de limpeza de desenvolvimento: exclui ordens de compra de teste."""
    query = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.organization_id == organization_id)
    if order_ids:
        query = query.filter(models.PurchaseOrder.id.in_(order_ids))
    
    orders = query.all()
    count = len(orders)
    for o in orders:
        if o.document_id:
            transition_purchase_order_status(
                db,
                o,
                organization_id,
                "DELETED",
                current_user=current_user,
                event_type="DELETED",
            )
        db.delete(o)
    db.commit()
    return {"detail": f"{count} ordem(ns) de compra excluída(s) com sucesso.", "deleted_count": count}


def delete_quotation_record(
    db: Session,
    quotation_id: uuid.UUID,
    organization_id: uuid.UUID,
    current_user: User | None = None,
) -> dict:
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
    if quot.document_id:
        transition_quotation_process_status(
            db,
            quot,
            organization_id,
            "DELETED",
            current_user=current_user,
            event_type="DELETED",
        )
    repository.delete_quotation_process(db, quotation=quot)
    db.commit()
    return {"detail": f"Cotação {num} excluída com sucesso."}


def purge_quotations(
    db: Session,
    organization_id: uuid.UUID,
    quotation_ids: list[uuid.UUID] | None = None,
    current_user: User | None = None,
) -> dict:
    """Rotina de limpeza de desenvolvimento: exclui cotações de teste."""
    query = db.query(models.QuotationProcess).filter(models.QuotationProcess.organization_id == organization_id)
    if quotation_ids:
        query = query.filter(models.QuotationProcess.id.in_(quotation_ids))
    
    quots = query.all()
    count = len(quots)
    for quot in quots:
        if quot.document_id:
            transition_quotation_process_status(
                db,
                quot,
                organization_id,
                "DELETED",
                current_user=current_user,
                event_type="DELETED",
            )
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


def get_quotation_process_document(
    db: Session,
    quotation_process: models.QuotationProcess,
    organization_id: uuid.UUID,
):
    """Resolve o cabeçalho canônico e atualiza a projeção nativa da RFQ."""
    from controlb.modules.documents import service as documents_service

    if not quotation_process.document_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O Processo de Cotação não possui identidade documental.",
        )
    document = documents_service.get_document(
        db, quotation_process.document_id, organization_id
    )
    if (
        document.document_type != "PURCHASE_QUOTATION"
        or document.native_id != quotation_process.id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O cabeçalho documental do Processo de Cotação é inconsistente.",
        )

    quotation_process.quotation_number = document.document_number
    quotation_process.status = document.current_status.lower()
    quotation_process.notes = document.description
    return document


def transition_quotation_process_status(
    db: Session,
    quotation_process: models.QuotationProcess,
    organization_id: uuid.UUID,
    new_status: str,
    *,
    current_user: User | None = None,
    event_type: str = "STATUS_CHANGED",
    event_metadata: dict | None = None,
    idempotency_key: str | None = None,
    record_if_unchanged: bool = False,
) -> models.QuotationProcess:
    """Única porta para transições do processo de cotação."""
    normalized_status = new_status.strip().upper()
    document = None
    if quotation_process.document_id:
        document = get_quotation_process_document(
            db, quotation_process, organization_id
        )
        previous_status = document.current_status
    else:
        # Compatibilidade para objetos isolados de testes e bases pré-migração.
        previous_status = quotation_process.status.strip().upper()

    if normalized_status == previous_status and not record_if_unchanged:
        return quotation_process

    quotation_process.status = normalized_status.lower()
    repository.update_quotation_process_status(
        db,
        db_process=quotation_process,
        new_status=quotation_process.status,
    )

    if document is not None:
        from controlb.modules.documents import service as documents_service

        documents_service.record_event(
            db,
            organization_id=organization_id,
            document=document,
            event_type=event_type,
            previous_status=previous_status,
            new_status=normalized_status,
            event_metadata=event_metadata,
            idempotency_key=idempotency_key,
            created_by_id=current_user.id if current_user else None,
        )
        quotation_process.status = document.current_status.lower()

    db.commit()
    db.refresh(quotation_process)
    return quotation_process


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
        if existing_proc.document_id:
            get_quotation_process_document(
                db, existing_proc, current_user.organization_id
            )
        return existing_proc

    from controlb.modules.documents import schemas as document_schemas
    from controlb.modules.documents import service as documents_service

    request_document = None
    if db_request.document_id:
        request_document = get_purchase_request_document(
            db, db_request, current_user.organization_id
        )

    process_id = uuid.uuid4()
    process_document = documents_service.create_document(
        db,
        organization_id=current_user.organization_id,
        payload=document_schemas.DocumentCreate(
            category="purchase.quotation",
            document_type="PURCHASE_QUOTATION",
            native_id=process_id,
            title="Processo de Cotação",
            current_status="OPEN",
            description=notes,
            origin_module="PURCHASING",
            responsible_id=current_user.id,
        ),
        current_user=current_user,
    )
    process_document.title = f"Processo de Cotação {process_document.document_number}"

    created_process = repository.create_quotation_process(
        db=db,
        process_id=process_id,
        document_id=process_document.id,
        organization_id=current_user.organization_id,
        purchase_request_id=request_id,
        quotation_number=process_document.document_number,
        notes=notes
    )
    if request_document is not None:
        documents_service.relate_documents(
            db,
            organization_id=current_user.organization_id,
            parent_document=request_document,
            child_document=process_document,
            relation_type="generated",
            created_by_id=current_user.id,
        )

    db.commit()
    db.refresh(created_process)
    return created_process


def list_quotation_processes(
    db: Session,
    organization_id: uuid.UUID,
    status_filter: str | None = None
) -> list[models.QuotationProcess]:
    """Lista todos os processos de cotação abertos na organização."""
    processes = repository.get_all_quotation_processes(
        db, organization_id=organization_id, status=status_filter
    )
    for quotation_process in processes:
        get_quotation_process_document(db, quotation_process, organization_id)
    return processes


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
    get_quotation_process_document(db, db_process, organization_id)
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

    if db_process.document_id:
        get_quotation_process_document(
            db, db_process, current_user.organization_id
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

    transition_quotation_process_status(
        db,
        db_process,
        current_user.organization_id,
        "ANALYZING",
        current_user=current_user,
        event_type="SUPPLIER_QUOTE_ADDED",
        event_metadata={
            "supplier_quote_id": str(quote.id),
            "supplier_id": str(quote.supplier_id),
        },
        idempotency_key=f"quotation:{db_process.id}:supplier-quote:{quote.id}:added",
        record_if_unchanged=True,
    )

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

    if db_process.document_id:
        get_quotation_process_document(
            db, db_process, current_user.organization_id
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

    if db_process.document_id:
        get_quotation_process_document(
            db, db_process, current_user.organization_id
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

    # A transição da solicitação ocorre após a criação efetiva do pedido.
    db_request = db_process.purchase_request

    # Calcula data de entrega estimada com base no lead time prometido
    delivery_date = None
    if winning_quote.lead_time_days:
        from datetime import timedelta
        delivery_date = datetime.now(timezone.utc) + timedelta(days=winning_quote.lead_time_days)

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

    created_order = persist_purchase_order(
        db,
        current_user=current_user,
        total_amount=winning_quote.total_amount,
        order_data=po_data,
    )

    transition_quotation_process_status(
        db,
        db_process,
        current_user.organization_id,
        "COMPLETED",
        current_user=current_user,
        event_type="WINNER_SELECTED",
        event_metadata={
            "supplier_quote_id": str(winning_quote.id),
            "purchase_order_id": str(created_order.id),
        },
        idempotency_key=f"quotation:{db_process.id}:winner:{winning_quote.id}",
    )

    transition_purchase_request_status(
        db,
        db_request,
        current_user.organization_id,
        "ORDERED",
        current_user=current_user,
        event_type="QUOTATION_WINNER_SELECTED",
        event_metadata={
            "quotation_id": str(db_process.id),
            "purchase_order_id": str(created_order.id),
        },
        idempotency_key=(
            f"purchase-request:{db_request.id}:quotation:{db_process.id}:winner"
        ),
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

    if db_process.document_id:
        get_quotation_process_document(
            db, db_process, current_user.organization_id
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
            transition_purchase_order_status(
                db,
                o,
                current_user.organization_id,
                "CANCELLED",
                current_user=current_user,
                event_type="QUOTATION_CANCELLED",
                event_metadata={"quotation_id": str(db_process.id)},
            )

    # Atualiza status de todas as propostas para 'rejected'
    for q in db_process.quotes:
        repository.update_supplier_quote_status(db, db_quote=q, new_status="rejected")

    transition_quotation_process_status(
        db,
        db_process,
        current_user.organization_id,
        "CANCELLED",
        current_user=current_user,
        event_type="CANCELLED",
        event_metadata={"purchase_request_id": str(db_process.purchase_request_id)},
    )

    # Reverte solicitação para 'approved'
    db_request = db_process.purchase_request
    if db_request and db_request.status == "ordered":
        transition_purchase_request_status(
            db,
            db_request,
            current_user.organization_id,
            "APPROVED",
            current_user=current_user,
            event_type="QUOTATION_CANCELLED",
            event_metadata={"quotation_id": str(db_process.id)},
        )

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

    if db_process.document_id:
        get_quotation_process_document(
            db, db_process, current_user.organization_id
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
            transition_purchase_order_status(
                db,
                o,
                current_user.organization_id,
                "CANCELLED",
                current_user=current_user,
                event_type="QUOTATION_REOPENED",
                event_metadata={"quotation_id": str(db_process.id)},
            )

    # Retorna todas as propostas para 'pending'
    for q in db_process.quotes:
        repository.update_supplier_quote_status(db, db_quote=q, new_status="pending")

    # Define status da cotação
    new_status = "analyzing" if len(db_process.quotes) > 0 else "open"
    transition_quotation_process_status(
        db,
        db_process,
        current_user.organization_id,
        new_status,
        current_user=current_user,
        event_type="REOPENED",
        event_metadata={"purchase_request_id": str(db_process.purchase_request_id)},
    )

    # Reverte solicitação de compra para 'approved'
    db_request = db_process.purchase_request
    if db_request:
        transition_purchase_request_status(
            db,
            db_request,
            current_user.organization_id,
            "APPROVED",
            current_user=current_user,
            event_type="QUOTATION_REOPENED",
            event_metadata={"quotation_id": str(db_process.id)},
        )

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

    if db_process.document_id:
        get_quotation_process_document(
            db, db_process, current_user.organization_id
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
        transition_quotation_process_status(
            db,
            db_process,
            current_user.organization_id,
            "OPEN",
            current_user=current_user,
            event_type="LAST_SUPPLIER_QUOTE_REMOVED",
            event_metadata={"supplier_quote_id": str(quote_id)},
        )
    else:
        db.commit()

    return {"detail": "Proposta comercial removida com sucesso."}


# ==============================================================================
# 9. FLUXO ÁGIL: MOTOR DE SUGESTÕES DE COMPRA & CONTROLE DE INVENTÁRIO
# ==============================================================================

def list_inventory_replenishments(
    db: Session, organization_id: uuid.UUID
) -> list[models.InventoryReplenishment]:
    return repository.list_inventory_replenishments(db, organization_id)


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


def _persist_inventory_replenishment(
    db: Session,
    current_user: User,
    *,
    items: list[tuple[uuid.UUID, Decimal, Decimal]],
    notes: str | None,
    estimated_total_amount: Decimal | None = None,
    document_payload: dict | None = None,
) -> models.InventoryReplenishment:
    """Materializa a necessidade de estoque antes de escolher o rito de compra."""
    requested_by_product: dict[uuid.UUID, tuple[Decimal, Decimal]] = {}
    products_by_id: dict[uuid.UUID, models.Product] = {}
    for product_id, quantity, unit_price in items:
        product = repository.get_product_by_id(
            db, product_id, current_user.organization_id
        )
        if not product or not product.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Um dos produtos da reposição não existe ou está inativo.",
            )
        if quantity <= 0 or unit_price < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Quantidade e preço da reposição são inválidos.",
            )
        prior_quantity, prior_total = requested_by_product.get(
            product_id, (Decimal("0"), Decimal("0"))
        )
        requested_by_product[product_id] = (
            prior_quantity + quantity,
            prior_total + (quantity * unit_price),
        )
        products_by_id[product_id] = product

    if not requested_by_product:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A reposição precisa conter pelo menos um produto.",
        )

    items_total = sum(
        (total for _, total in requested_by_product.values()), Decimal("0")
    )
    from controlb.modules.documents import schemas as document_schemas
    from controlb.modules.documents import service as documents_service

    replenishment_id = uuid.uuid4()
    payload = {
        "product_count": len(requested_by_product),
        **(document_payload or {}),
    }
    replenishment_document = documents_service.create_document(
        db,
        organization_id=current_user.organization_id,
        payload=document_schemas.DocumentCreate(
            category="inventory.replenishment",
            document_type="REPLENISHMENT",
            native_id=replenishment_id,
            title="Reposição de Estoque",
            current_status="OPEN",
            description=notes,
            origin_module="INVENTORY",
            responsible_id=current_user.id,
            payload=payload,
            issued_at=utcnow(),
        ),
        current_user=current_user,
    )
    replenishment_document.title = (
        f"Reposição {replenishment_document.document_number}"
    )
    replenishment = models.InventoryReplenishment(
        id=replenishment_id,
        organization_id=current_user.organization_id,
        document_id=replenishment_document.id,
        replenishment_number=replenishment_document.document_number,
        status="OPEN",
        estimated_total_amount=(
            estimated_total_amount
            if estimated_total_amount is not None
            else items_total
        ),
        created_by_id=current_user.id,
        notes=notes,
    )
    for product_id, (quantity, estimated_total) in requested_by_product.items():
        product = products_by_id[product_id]
        current_stock = Decimal(str(product.current_stock or 0))
        replenishment.items.append(
            models.InventoryReplenishmentItem(
                organization_id=current_user.organization_id,
                product_id=product_id,
                current_stock=current_stock,
                min_stock=Decimal(str(product.min_stock or 0)),
                target_stock=current_stock + quantity,
                requested_quantity=quantity,
                estimated_unit_price=estimated_total / quantity,
            )
        )
    repository.create_inventory_replenishment(db, replenishment)
    return replenishment


def create_formal_replenishment_request(
    db: Session,
    current_user: User,
    data: schemas.PurchaseRequestCreate,
) -> models.PurchaseRequest:
    """Abre reposição e solicitação formal na mesma cadeia documental."""
    replenishment = _persist_inventory_replenishment(
        db,
        current_user,
        items=[
            (
                item.product_id,
                Decimal(str(item.quantity)),
                Decimal(str(item.estimated_unit_price)),
            )
            for item in data.items
        ],
        notes=data.justification,
        document_payload={"procurement_path": "FORMAL_REQUEST"},
    )
    request_data = data.model_copy(
        update={
            "organization_id": current_user.organization_id,
            "replenishment_id": replenishment.id,
        }
    )
    return create_purchase_request(db, current_user, request_data)


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

    items_total = sum(
        (
            Decimal(str(item.quantity)) * Decimal(str(item.unit_price))
            for item in data.items
        ),
        Decimal("0"),
    )
    freight = Decimal(str(data.freight_amount or 0))
    discount = Decimal(str(data.discount_amount or 0))
    total_order = items_total + freight - discount
    if total_order < Decimal("0.00"):
        total_order = Decimal("0.00")

    replenishment = _persist_inventory_replenishment(
        db,
        current_user,
        items=[
            (
                item.product_id,
                Decimal(str(item.quantity)),
                Decimal(str(item.unit_price)),
            )
            for item in data.items
        ],
        notes=data.notes,
        estimated_total_amount=total_order,
        document_payload={
            "procurement_path": "DIRECT_ORDER",
            "supplier_id": str(data.supplier_id),
        },
    )

    order_payload = schemas.PurchaseOrderCreate(
        organization_id=current_user.organization_id,
        buyer_id=current_user.id,
        purchase_request_id=None,  # Ordem direta de reposição
        replenishment_id=replenishment.id,
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

    db_order = persist_purchase_order(
        db,
        current_user=current_user,
        total_amount=total_order,
        order_data=order_payload,
    )

    return db_order
