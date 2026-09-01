"""
tests/unit/test_purchasing_po_flow.py - Testes unitários para o fluxo de geração de PO e recebimento de mercadorias.
"""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch
import pytest
from fastapi import HTTPException

from controlb.modules.purchasing import models, schemas
from controlb.modules.purchasing.service import (
    generate_po_from_request,
    receive_purchase_order_shipment,
)
from controlb.modules.identity.models import User


def test_generate_po_from_approved_request_success():
    """Valida a conversão bem-sucedida de uma solicitação aprovada em Ordem de Compra com frete e desconto."""
    db_mock = MagicMock()
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    req_id = uuid.uuid4()
    sup_id = uuid.uuid4()
    prod_id = uuid.uuid4()

    mock_user = User(id=user_id, organization_id=org_id, email="comprador@controlb.com")
    
    mock_request = models.PurchaseRequest(
        id=req_id,
        organization_id=org_id,
        requester_id=user_id,
        request_number="SC-2026-0001",
        status="approved",
        total_estimated_amount=Decimal("500.00")
    )

    mock_supplier = models.Supplier(
        id=sup_id,
        organization_id=org_id,
        trade_name="Distribuidora Alfa",
        is_active=True
    )

    payload = schemas.GeneratePOFromRequest(
        supplier_id=sup_id,
        payment_terms="30 DDL",
        freight_type="FOB",
        freight_amount=Decimal("50.00"),
        discount_amount=Decimal("20.00"),
        items=[
            schemas.PurchaseOrderItemCreate(
                product_id=prod_id,
                quantity=Decimal("10.00"),
                unit_price=Decimal("45.00")  # Subtotal 450.00 + Frete 50.00 - Desc 20.00 = 480.00
            )
        ]
    )

    mock_created_po = models.PurchaseOrder(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        organization_id=org_id,
        buyer_id=user_id,
        purchase_request_id=req_id,
        supplier_id=sup_id,
        order_number="PC-2026-0001",
        status="issued",
        total_amount=Decimal("480.00")
    )

    with patch("controlb.modules.purchasing.repository.get_purchase_request_by_id", return_value=mock_request), \
         patch("controlb.modules.purchasing.repository.get_supplier_by_id", return_value=mock_supplier), \
         patch("controlb.modules.purchasing.repository.count_purchase_orders_in_year", return_value=0), \
         patch("controlb.modules.purchasing.repository.create_purchase_order", return_value=mock_created_po) as mock_create_repo, \
         patch("controlb.modules.purchasing.repository.update_purchase_request_status") as mock_update_req_status, \
         patch(
             "controlb.modules.documents.service.create_document",
             return_value=MagicMock(
                 id=mock_created_po.document_id,
                 document_number="PC-2026-0001",
             ),
         ):

        po = generate_po_from_request(
            db=db_mock,
            request_id=req_id,
            current_user=mock_user,
            data=payload
        )

        assert po.status == "issued"
        assert po.total_amount == Decimal("480.00")
        mock_create_repo.assert_called_once()
        # Verifica se o total calculado bate com os itens + frete - desconto
        _, kwargs = mock_create_repo.call_args
        assert kwargs["total_amount"] == Decimal("480.00")
        # Verifica se o status da solicitação foi atualizado para 'ordered'
        mock_update_req_status.assert_called_once_with(db_mock, db_request=mock_request, new_status="ordered")


def test_generate_po_from_non_approved_request_fails():
    """Garante que solicitações em rascunho ou pendentes NÃO possam gerar Ordem de Compra."""
    db_mock = MagicMock()
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    req_id = uuid.uuid4()

    mock_user = User(id=user_id, organization_id=org_id, email="comprador@controlb.com")
    
    mock_request = models.PurchaseRequest(
        id=req_id,
        organization_id=org_id,
        status="pending_approval"
    )

    payload = schemas.GeneratePOFromRequest(
        supplier_id=uuid.uuid4(),
        items=[
            schemas.PurchaseOrderItemCreate(
                product_id=uuid.uuid4(),
                quantity=Decimal("5.00"),
                unit_price=Decimal("10.00")
            )
        ]
    )

    with patch("controlb.modules.purchasing.repository.get_purchase_request_by_id", return_value=mock_request):
        with pytest.raises(HTTPException) as exc_info:
            generate_po_from_request(
                db=db_mock,
                request_id=req_id,
                current_user=mock_user,
                data=payload
            )
        assert exc_info.value.status_code == 400
        assert "Apenas solicitações com status 'Aprovada'" in exc_info.value.detail


def test_receive_purchase_order_shipment_success():
    """Valida o registro de recebimento de mercadoria com nota fiscal e alteração de status."""
    db_mock = MagicMock()
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    order_id = uuid.uuid4()

    mock_user = User(id=user_id, organization_id=org_id, email="almoxarife@controlb.com")
    
    mock_order = models.PurchaseOrder(
        id=order_id,
        organization_id=org_id,
        order_number="OC-2026-0001",
        status="issued"
    )

    payload = schemas.PurchaseOrderReceive(
        invoice_number="NF-e 123456",
        notes="Itens conferidos sem avarias no almoxarifado central"
    )

    with patch("controlb.modules.purchasing.repository.get_purchase_order_by_id", return_value=mock_order), \
         patch("controlb.modules.purchasing.repository.receive_purchase_order", return_value=mock_order) as mock_receive_repo:

        receive_purchase_order_shipment(
            db=db_mock,
            order_id=order_id,
            current_user=mock_user,
            data=payload
        )

        mock_receive_repo.assert_called_once_with(
            db=db_mock,
            db_order=mock_order,
            invoice_number="NF-e 123456",
            received_by_id=user_id,
            invoice_attachment=None,
            received_at=None,
            notes="Itens conferidos sem avarias no almoxarifado central"
        )


def test_receive_purchase_order_requires_due_date_for_payable():
    with pytest.raises(ValueError, match="primeiro vencimento"):
        schemas.PurchaseOrderReceive(
            invoice_number="NF-e 123456",
            generate_payable=True,
        )


def test_create_purchase_request_success():
    """Valida a emissão de solicitação de compra sem necessidade de organization_id no body."""
    from controlb.modules.purchasing.service import create_purchase_request
    db_mock = MagicMock()
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    prod_id = uuid.uuid4()

    mock_user = User(id=user_id, organization_id=org_id, email="solicitante@controlb.com")

    mock_prod = models.Product(
        id=prod_id,
        organization_id=org_id,
        name="Dipirona 500mg",
        sku="MED-DIP-0001",
        current_stock=Decimal("5.00"),
        min_stock=Decimal("10.00"),
        reference_price=Decimal("4.50"),
        is_active=True
    )

    payload = schemas.PurchaseRequestCreate(
        justification="Reposição urgente de estoque da farmácia",
        items=[
            schemas.PurchaseRequestItemCreate(
                product_id=prod_id,
                quantity=Decimal("20.00"),
                estimated_unit_price=Decimal("4.50"),
                notes="Frascos de 20ml"
            )
        ]
    )
    # Atribuído pelo endpoint a partir do usuário autenticado
    payload.organization_id = org_id

    mock_created_pr = models.PurchaseRequest(
        id=uuid.uuid4(),
        organization_id=org_id,
        requester_id=user_id,
        request_number="SC-2026-0001",
        status="pending_approval",
        total_estimated_amount=Decimal("90.00"),
        justification=payload.justification
    )
    mock_document = MagicMock(
        id=uuid.uuid4(),
        document_number="SC-2026-0001",
        current_status="PENDING_APPROVAL",
    )

    with patch("controlb.modules.purchasing.service.repository.get_product_by_id", return_value=mock_prod), \
         patch("controlb.modules.documents.service.create_document", return_value=mock_document) as mock_create_document, \
         patch("controlb.modules.documents.service.update_document", return_value=mock_document), \
         patch("controlb.modules.purchasing.service.repository.create_purchase_request", return_value=mock_created_pr) as mock_create_repo:

        result = create_purchase_request(
            db=db_mock,
            current_user=mock_user,
            request_data=payload
        )

        assert result.status == "pending_approval"
        assert result.request_number == "SC-2026-0001"
        assert result.total_estimated_amount == Decimal("90.00")
        assert mock_create_document.call_count == 1
        mock_create_repo.assert_called_once()
        assert mock_create_repo.call_args.kwargs["document_id"] == mock_document.id
