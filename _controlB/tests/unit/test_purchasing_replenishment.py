"""
tests/unit/test_purchasing_replenishment.py - Testes unitários para as sugestões de compra e fluxo ágil de PO direta.
"""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch
import pytest

from controlb.modules.inventory import models as inv_models
from controlb.modules.purchasing import models as pur_models, schemas as pur_schemas, service as pur_service
from controlb.modules.identity.models import User


def test_generate_replenishment_suggestions_calculation_and_urgency():
    """Valida o cálculo do ponto de pedido, quantidade sugerida e classificação de urgência crítica/alta/média."""
    db_mock = MagicMock()
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    mock_user = User(id=user_id, organization_id=org_id, email="comprador@farmacia.com")

    # Item 1: Estoque Zerado -> Urgência Crítica
    prod1 = inv_models.Product(
        id=uuid.uuid4(),
        organization_id=org_id,
        name="Dipirona 500mg",
        sku="MED-DIP-001",
        current_stock=Decimal("0.0000"),
        min_stock=Decimal("20.00"),
        max_stock=Decimal("50.00"),
        reference_price=Decimal("4.0000"),
        unit_of_measure="CX",
        is_active=True
    )

    # Item 2: Estoque Abaixo de 50% do mínimo -> Urgência Alta
    prod2 = inv_models.Product(
        id=uuid.uuid4(),
        organization_id=org_id,
        name="Losartana 50mg",
        sku="MED-LOS-001",
        current_stock=Decimal("5.0000"),
        min_stock=Decimal("20.00"),
        max_stock=Decimal("40.00"),
        reference_price=Decimal("8.0000"),
        unit_of_measure="CX",
        is_active=True
    )

    with patch("controlb.modules.inventory.service.get_replenishment_candidates", return_value=[prod1, prod2]):
        result = pur_service.generate_replenishment_suggestions(db_mock, organization_id=org_id)

        assert result.total_suggestions == 2
        assert result.critical_count == 1
        
        # Item 1: Suggested = 50 - 0 = 50. Total = 50 * 4 = 200.00. Urgência = critical
        item1 = next(i for i in result.items if i.sku == "MED-DIP-001")
        assert item1.suggested_quantity == Decimal("50.00")
        assert item1.estimated_total == Decimal("200.0000")
        assert item1.urgency_level == "critical"

        # Item 2: Suggested = 40 - 5 = 35. Total = 35 * 8 = 280.00. Urgência = high
        item2 = next(i for i in result.items if i.sku == "MED-LOS-001")
        assert item2.suggested_quantity == Decimal("35.00")
        assert item2.estimated_total == Decimal("280.0000")
        assert item2.urgency_level == "high"

        assert result.estimated_total_cost == Decimal("480.0000")


def test_create_quick_replenishment_order_success():
    """Valida a emissão ágil de PO direta para fornecedor a partir de múltiplos produtos selecionados."""
    db_mock = MagicMock()
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    sup_id = uuid.uuid4()
    prod_id = uuid.uuid4()

    mock_user = User(id=user_id, organization_id=org_id, email="farmaceutico@controlb.com")
    mock_supplier = pur_models.Supplier(id=sup_id, organization_id=org_id, trade_name="Distribuidora MedSul", is_active=True)

    payload = pur_schemas.QuickReplenishmentOrderCreate(
        supplier_id=sup_id,
        payment_terms="28 DDL",
        freight_type="CIF",
        freight_amount=Decimal("0.00"),
        discount_amount=Decimal("15.00"),
        items=[
            pur_schemas.PurchaseOrderItemCreate(
                product_id=prod_id,
                quantity=Decimal("42.00"),
                unit_price=Decimal("5.00")  # 210.00 - 15.00 = 195.00
            )
        ]
    )

    mock_po = pur_models.PurchaseOrder(
        id=uuid.uuid4(),
        organization_id=org_id,
        buyer_id=user_id,
        supplier_id=sup_id,
        purchase_request_id=None,
        order_number="OC-2026-0005",
        status="issued",
        total_amount=Decimal("195.00")
    )

    with patch("controlb.modules.purchasing.repository.get_supplier_by_id", return_value=mock_supplier), \
         patch("controlb.modules.purchasing.repository.count_purchase_orders_in_year", return_value=4), \
         patch("controlb.modules.purchasing.repository.create_purchase_order", return_value=mock_po) as mock_create_po:

        order = pur_service.create_quick_replenishment_order(
            db=db_mock,
            current_user=mock_user,
            data=payload
        )

        assert order.status == "issued"
        assert order.purchase_request_id is None
        mock_create_po.assert_called_once()
        _, kwargs = mock_create_po.call_args
        assert kwargs["total_amount"] == Decimal("195.00")
        assert kwargs["order_number"] == "OC-2026-0005"
