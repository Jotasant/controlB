"""
tests/unit/test_purchasing_quotation_flow.py - Testes Unitários do Fluxo de Cotações (RFQ) e Mapa Comparativo
"""

import uuid
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest
from fastapi import HTTPException

from controlb.modules.purchasing import service, schemas, models


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = uuid.uuid4()
    user.organization_id = uuid.uuid4()
    return user


def test_open_quotation_process_from_approved_request(mock_db, mock_user):
    """Testa abertura de processo de cotação a partir de solicitação aprovada."""
    request_id = uuid.uuid4()
    
    mock_request = models.PurchaseRequest(
        id=request_id,
        organization_id=mock_user.organization_id,
        requester_id=mock_user.id,
        request_number="SC-2026-0001",
        status="approved",
        justification="Compra de servidores",
        total_estimated_amount=Decimal("15000.00")
    )
    
    service.repository.get_purchase_request_by_id = MagicMock(return_value=mock_request)
    service.repository.get_quotation_process_by_request_id = MagicMock(return_value=None)
    service.repository.count_quotation_processes_in_year = MagicMock(return_value=0)
    
    mock_process = models.QuotationProcess(
        id=uuid.uuid4(),
        organization_id=mock_user.organization_id,
        purchase_request_id=request_id,
        document_id=uuid.uuid4(),
        quotation_number="RFQ-2026-0001",
        status="open"
    )
    service.repository.create_quotation_process = MagicMock(return_value=mock_process)

    mock_document = MagicMock(
        id=mock_process.document_id,
        document_number="RFQ-2026-0001",
    )
    with patch(
        "controlb.modules.documents.service.create_document",
        return_value=mock_document,
    ):
        result = service.open_quotation_process(
            db=mock_db,
            current_user=mock_user,
            request_id=request_id,
            notes="Cotar com pelo menos 3 fornecedores"
        )

    assert result.quotation_number == "RFQ-2026-0001"
    assert result.status == "open"
    service.repository.create_quotation_process.assert_called_once()


def test_open_quotation_process_fails_if_request_not_approved(mock_db, mock_user):
    """Garante que solicitações não aprovadas não podem abrir cotação."""
    request_id = uuid.uuid4()
    
    mock_request = models.PurchaseRequest(
        id=request_id,
        organization_id=mock_user.organization_id,
        requester_id=mock_user.id,
        request_number="SC-2026-0002",
        status="pending_approval",
        justification="Pendente",
        total_estimated_amount=Decimal("5000.00")
    )
    
    service.repository.get_purchase_request_by_id = MagicMock(return_value=mock_request)
    
    with pytest.raises(HTTPException) as exc_info:
        service.open_quotation_process(
            db=mock_db,
            current_user=mock_user,
            request_id=request_id
        )
        
    assert exc_info.value.status_code == 400
    assert "approved" in exc_info.value.detail


def test_add_supplier_quotes_and_generate_comparison_matrix(mock_db, mock_user):
    """Testa adição de propostas e geração do mapa comparativo de preços."""
    quotation_id = uuid.uuid4()
    product_id = uuid.uuid4()
    supplier_a_id = uuid.uuid4()
    supplier_b_id = uuid.uuid4()
    quote_a_id = uuid.uuid4()
    quote_b_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    
    mock_product = models.Product(
        id=product_id,
        organization_id=mock_user.organization_id,
        name="Memória RAM 32GB",
        sku="RAM-32G",
        unit_of_measure="UN",
        is_active=True,
        created_at=now,
        updated_at=now
    )
    
    mock_req_item = models.PurchaseRequestItem(
        id=uuid.uuid4(),
        product_id=product_id,
        quantity=Decimal("10"),
        estimated_unit_price=Decimal("500.00"),
        total_estimated_price=Decimal("5000.00"),
        product=mock_product,
        created_at=now,
        updated_at=now
    )
    
    mock_request = models.PurchaseRequest(
        id=uuid.uuid4(),
        organization_id=mock_user.organization_id,
        requester_id=mock_user.id,
        request_number="SC-2026-0001",
        status="approved",
        justification="Upgrade",
        items=[mock_req_item],
        created_at=now,
        updated_at=now
    )
    
    quote_a = models.SupplierQuote(
        id=quote_a_id,
        organization_id=mock_user.organization_id,
        quotation_process_id=quotation_id,
        supplier_id=supplier_a_id,
        quote_reference="PROP-A-101",
        status="pending",
        freight_type="CIF",
        freight_amount=Decimal("50.00"),
        discount_amount=Decimal("0.00"),
        lead_time_days=5,
        total_amount=Decimal("4550.00"),  # 10 * 450 + 50
        is_active=True,
        created_at=now,
        updated_at=now,
        items=[
            models.SupplierQuoteItem(
                id=uuid.uuid4(),
                supplier_quote_id=quote_a_id,
                product_id=product_id,
                quantity=Decimal("10"),
                unit_price=Decimal("450.00"),
                total_price=Decimal("4500.00"),
                created_at=now,
                updated_at=now
            )
        ]
    )
    
    quote_b = models.SupplierQuote(
        id=quote_b_id,
        organization_id=mock_user.organization_id,
        quotation_process_id=quotation_id,
        supplier_id=supplier_b_id,
        quote_reference="PROP-B-202",
        status="pending",
        freight_type="CIF",
        freight_amount=Decimal("0.00"),
        discount_amount=Decimal("100.00"),
        lead_time_days=2,
        total_amount=Decimal("4100.00"),  # 10 * 420 - 100
        is_active=True,
        created_at=now,
        updated_at=now,
        items=[
            models.SupplierQuoteItem(
                id=uuid.uuid4(),
                supplier_quote_id=quote_b_id,
                product_id=product_id,
                quantity=Decimal("10"),
                unit_price=Decimal("420.00"),
                total_price=Decimal("4200.00"),
                created_at=now,
                updated_at=now
            )
        ]
    )
    
    mock_process = models.QuotationProcess(
        id=quotation_id,
        organization_id=mock_user.organization_id,
        purchase_request_id=mock_request.id,
        quotation_number="COT-2026-0001",
        status="analyzing",
        is_active=True,
        created_at=now,
        updated_at=now,
        purchase_request=mock_request,
        quotes=[quote_a, quote_b]
    )
    
    service.repository.get_quotation_process_by_id = MagicMock(return_value=mock_process)
    
    matrix = service.get_quotation_comparison_matrix(
        db=mock_db,
        current_user=mock_user,
        quotation_id=quotation_id
    )
    
    assert matrix.quotation_number == "COT-2026-0001"
    assert len(matrix.items_comparison) == 1
    assert matrix.items_comparison[0].lowest_unit_price == Decimal("420.00")
    assert matrix.items_comparison[0].lowest_supplier_id == str(supplier_b_id)
    assert matrix.best_total_quote_id == quote_b.id
    assert matrix.best_lead_time_quote_id == quote_b.id


def test_select_winner_and_generate_purchase_order(mock_db, mock_user):
    """Testa homologação da proposta vencedora e emissão da PO."""
    quotation_id = uuid.uuid4()
    quote_winner_id = uuid.uuid4()
    supplier_id = uuid.uuid4()
    product_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    
    winner_quote = models.SupplierQuote(
        id=quote_winner_id,
        organization_id=mock_user.organization_id,
        quotation_process_id=quotation_id,
        supplier_id=supplier_id,
        quote_reference="PROP-WINNER",
        payment_terms="30 DDL",
        freight_type="CIF",
        freight_amount=Decimal("0.00"),
        discount_amount=Decimal("50.00"),
        lead_time_days=3,
        total_amount=Decimal("4950.00"),
        is_active=True,
        created_at=now,
        updated_at=now,
        items=[
            models.SupplierQuoteItem(
                id=uuid.uuid4(),
                supplier_quote_id=quote_winner_id,
                product_id=product_id,
                quantity=Decimal("5"),
                unit_price=Decimal("1000.00"),
                total_price=Decimal("5000.00"),
                created_at=now,
                updated_at=now
            )
        ]
    )
    
    mock_request = models.PurchaseRequest(
        id=uuid.uuid4(),
        organization_id=mock_user.organization_id,
        requester_id=mock_user.id,
        cost_center_id=None,
        request_number="SC-2026-0001",
        status="approved",
        created_at=now,
        updated_at=now
    )
    
    mock_process = models.QuotationProcess(
        id=quotation_id,
        organization_id=mock_user.organization_id,
        purchase_request_id=mock_request.id,
        quotation_number="COT-2026-0001",
        status="analyzing",
        is_active=True,
        created_at=now,
        updated_at=now,
        purchase_request=mock_request,
        quotes=[winner_quote]
    )
    
    service.repository.get_quotation_process_by_id = MagicMock(return_value=mock_process)
    service.repository.get_purchase_request_by_id = MagicMock(return_value=mock_request)
    service.repository.get_supplier_quote_by_id = MagicMock(return_value=winner_quote)
    service.repository.update_supplier_quote_status = MagicMock()
    service.repository.update_quotation_process_status = MagicMock()
    service.repository.update_purchase_request_status = MagicMock()
    service.repository.count_purchase_orders_in_year = MagicMock(return_value=0)
    
    mock_created_order = models.PurchaseOrder(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        organization_id=mock_user.organization_id,
        purchase_request_id=mock_request.id,
        supplier_id=supplier_id,
        buyer_id=mock_user.id,
        order_number="PC-2026-0001",
        status="issued",
        payment_terms="30 DDL",
        total_amount=Decimal("4950.00"),
        is_active=True,
        created_at=now,
        updated_at=now
    )
    service.repository.create_purchase_order = MagicMock(return_value=mock_created_order)
    
    with patch(
        "controlb.modules.documents.service.create_document",
        return_value=MagicMock(
            id=mock_created_order.document_id,
            document_number="PC-2026-0001",
        ),
    ):
        po = service.select_winner_and_generate_order(
            db=mock_db,
            current_user=mock_user,
            quotation_id=quotation_id,
            quote_id=quote_winner_id,
            notes="Fornecedor selecionado por melhor prazo e preço"
        )
    
    assert po.order_number == "PC-2026-0001"
    assert po.total_amount == Decimal("4950.00")
    service.repository.update_quotation_process_status.assert_called_with(mock_db, db_process=mock_process, new_status="completed")
    service.repository.update_purchase_request_status.assert_called_with(mock_db, db_request=mock_request, new_status="ordered")
    
    # Valida argumentos passados para create_purchase_order
    service.repository.create_purchase_order.assert_called_once()
    _, kwargs = service.repository.create_purchase_order.call_args
    assert kwargs["order_number"] == "PC-2026-0001"
    assert kwargs["total_amount"] == Decimal("4950.00")
    assert kwargs["order_data"].supplier_quote_id == quote_winner_id


def test_select_winner_self_healing_if_completed_with_existing_po(mock_db, mock_user):
    """Testa idempotência: se o processo já estiver completed e a PO existir, retorna a PO."""
    quotation_id = uuid.uuid4()
    quote_id = uuid.uuid4()
    req_id = uuid.uuid4()
    
    mock_process = models.QuotationProcess(
        id=quotation_id,
        organization_id=mock_user.organization_id,
        purchase_request_id=req_id,
        quotation_number="COT-2026-0001",
        status="completed",
        quotes=[]
    )
    mock_quote = models.SupplierQuote(
        id=quote_id,
        organization_id=mock_user.organization_id,
        quotation_process_id=quotation_id,
        supplier_id=uuid.uuid4(),
        total_amount=Decimal("1000.00")
    )
    existing_po = models.PurchaseOrder(
        id=uuid.uuid4(),
        organization_id=mock_user.organization_id,
        order_number="OC-2026-0001",
        total_amount=Decimal("1000.00")
    )
    
    service.repository.get_quotation_process_by_id = MagicMock(return_value=mock_process)
    service.repository.get_supplier_quote_by_id = MagicMock(return_value=mock_quote)
    service.repository.get_purchase_orders_by_request_id = MagicMock(return_value=[existing_po])
    
    result = service.select_winner_and_generate_order(
        db=mock_db,
        current_user=mock_user,
        quotation_id=quotation_id,
        quote_id=quote_id
    )
    
    assert result.order_number == "OC-2026-0001"


def test_reopen_quotation_process(mock_db, mock_user):
    """Testa a reabertura de uma cotação homologada, desfazendo a homologação."""
    quotation_id = uuid.uuid4()
    req_id = uuid.uuid4()
    
    mock_request = models.PurchaseRequest(
        id=req_id,
        organization_id=mock_user.organization_id,
        status="ordered"
    )
    mock_quote = models.SupplierQuote(
        id=uuid.uuid4(),
        organization_id=mock_user.organization_id,
        quotation_process_id=quotation_id,
        status="selected"
    )
    mock_process = models.QuotationProcess(
        id=quotation_id,
        organization_id=mock_user.organization_id,
        purchase_request_id=req_id,
        status="completed",
        purchase_request=mock_request,
        quotes=[mock_quote]
    )
    
    service.repository.get_quotation_process_by_id = MagicMock(return_value=mock_process)
    service.repository.get_purchase_orders_by_request_id = MagicMock(return_value=[])
    service.repository.update_supplier_quote_status = MagicMock()
    service.repository.update_quotation_process_status = MagicMock()
    service.repository.update_purchase_request_status = MagicMock()
    
    reopened = service.reopen_quotation_process(
        db=mock_db,
        current_user=mock_user,
        quotation_id=quotation_id
    )
    
    service.repository.update_quotation_process_status.assert_called_with(mock_db, db_process=mock_process, new_status="analyzing")
    service.repository.update_purchase_request_status.assert_called_with(mock_db, db_request=mock_request, new_status="approved")
    service.repository.update_supplier_quote_status.assert_called_with(mock_db, db_quote=mock_quote, new_status="pending")


def test_cancel_quotation_process(mock_db, mock_user):
    """Testa o cancelamento de uma cotação e reversão da solicitação para approved."""
    quotation_id = uuid.uuid4()
    req_id = uuid.uuid4()
    
    mock_request = models.PurchaseRequest(
        id=req_id,
        organization_id=mock_user.organization_id,
        status="ordered"
    )
    mock_quote = models.SupplierQuote(
        id=uuid.uuid4(),
        organization_id=mock_user.organization_id,
        quotation_process_id=quotation_id,
        status="pending"
    )
    mock_process = models.QuotationProcess(
        id=quotation_id,
        organization_id=mock_user.organization_id,
        purchase_request_id=req_id,
        status="analyzing",
        purchase_request=mock_request,
        quotes=[mock_quote]
    )
    
    service.repository.get_quotation_process_by_id = MagicMock(return_value=mock_process)
    service.repository.get_purchase_orders_by_request_id = MagicMock(return_value=[])
    service.repository.update_supplier_quote_status = MagicMock()
    service.repository.update_quotation_process_status = MagicMock()
    service.repository.update_purchase_request_status = MagicMock()
    
    cancelled = service.cancel_quotation_process(
        db=mock_db,
        current_user=mock_user,
        quotation_id=quotation_id
    )
    
    service.repository.update_quotation_process_status.assert_called_with(mock_db, db_process=mock_process, new_status="cancelled")
    service.repository.update_purchase_request_status.assert_called_with(mock_db, db_request=mock_request, new_status="approved")
