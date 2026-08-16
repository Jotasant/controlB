"""
tests/unit/test_inventory_service.py - Testes unitários para o domínio de Estoque e Inventário Físico (Inventory).
"""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch
import pytest
from fastapi import HTTPException

from controlb.modules.inventory import models, schemas, service


def test_adjust_stock_set_balance_success():
    """Valida o balanço de inventário com contagem física direta (set_balance)."""
    db_mock = MagicMock()
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    prod_id = uuid.uuid4()

    mock_product = models.Product(
        id=prod_id,
        organization_id=org_id,
        name="Dipirona 500mg",
        sku="MED-DIP-0001",
        current_stock=Decimal("8.0000"),
        min_stock=Decimal("20.00"),
        max_stock=Decimal("50.00"),
        reference_price=Decimal("4.5000"),
        is_active=True
    )

    payload = schemas.StockAdjustmentCreate(
        product_id=prod_id,
        adjustment_type="set_balance",
        quantity=Decimal("50.00"),
        reason="Inventário Físico Mensal",
        notes="Ajuste após contagem na prateleira A3"
    )

    mock_movement = models.StockMovement(
        id=uuid.uuid4(),
        organization_id=org_id,
        product_id=prod_id,
        movement_type="in_reconciliation",
        quantity=Decimal("42.0000"),
        balance_after=Decimal("50.0000"),
        reference_doc="Inventário Físico Mensal",
        notes="Ajuste após contagem na prateleira A3",
        created_by_id=user_id
    )

    with patch("controlb.modules.inventory.repository.get_product_by_id", return_value=mock_product), \
         patch("controlb.modules.inventory.repository.update_product") as mock_update_prod, \
         patch("controlb.modules.inventory.repository.create_stock_movement", return_value=mock_movement) as mock_create_mov:

        result = service.adjust_stock(
            db=db_mock,
            organization_id=org_id,
            user_id=user_id,
            payload=payload
        )

        assert result.balance_after == Decimal("50.0000")
        assert result.movement_type == "in_reconciliation"
        assert mock_product.current_stock == Decimal("50.00")
        mock_update_prod.assert_called_once_with(db_mock, mock_product)
        mock_create_mov.assert_called_once()
        _, kwargs = mock_create_mov.call_args
        mov_arg = kwargs.get("movement") or _[1]
        assert mov_arg.quantity == Decimal("42.0000")
        assert mov_arg.movement_type == "in_reconciliation"



def test_adjust_stock_remove_stock_loss_success():
    """Valida a saída manual de estoque por avaria/perda (remove_stock)."""
    db_mock = MagicMock()
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    prod_id = uuid.uuid4()

    mock_product = models.Product(
        id=prod_id,
        organization_id=org_id,
        name="Omeprazol 20mg",
        sku="MED-OME-0001",
        current_stock=Decimal("15.0000"),
        min_stock=Decimal("10.00"),
        reference_price=Decimal("12.0000"),
        is_active=True
    )

    payload = schemas.StockAdjustmentCreate(
        product_id=prod_id,
        adjustment_type="remove_stock",
        quantity=Decimal("3.00"),
        reason="Avaria de Embalagem",
        notes="Caixa amassada com frascos quebrados"
    )

    mock_movement = models.StockMovement(
        id=uuid.uuid4(),
        organization_id=org_id,
        product_id=prod_id,
        movement_type="out_loss",
        quantity=Decimal("3.0000"),
        balance_after=Decimal("12.0000"),
        reference_doc="Avaria de Embalagem",
        created_by_id=user_id
    )

    with patch("controlb.modules.inventory.repository.get_product_by_id", return_value=mock_product), \
         patch("controlb.modules.inventory.repository.update_product") as mock_update_prod, \
         patch("controlb.modules.inventory.repository.create_stock_movement", return_value=mock_movement) as mock_create_mov:

        result = service.adjust_stock(
            db=db_mock,
            organization_id=org_id,
            user_id=user_id,
            payload=payload
        )

        assert result.balance_after == Decimal("12.0000")
        assert mock_product.current_stock == Decimal("12.0000")
        mock_update_prod.assert_called_once_with(db_mock, mock_product)
        _, kwargs = mock_create_mov.call_args
        mov_arg = kwargs.get("movement") or _[1]
        assert mov_arg.movement_type == "out_loss"
        assert mov_arg.quantity == Decimal("3.00")


def test_register_purchase_receipt_integration():
    """Valida a função de integração chamada quando Compras recebe uma remessa de PO."""
    db_mock = MagicMock()
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    prod_id = uuid.uuid4()

    mock_product = models.Product(
        id=prod_id,
        organization_id=org_id,
        name="Paracetamol 750mg",
        sku="MED-PAR-0001",
        current_stock=Decimal("10.0000"),
        min_stock=Decimal("30.00"),
        reference_price=Decimal("3.0000"),
        is_active=True
    )

    with patch("controlb.modules.inventory.repository.get_product_by_id", return_value=mock_product), \
         patch("controlb.modules.inventory.repository.update_product") as mock_update_prod, \
         patch("controlb.modules.inventory.repository.create_stock_movement") as mock_create_mov:

        service.register_purchase_receipt(
            db=db_mock,
            organization_id=org_id,
            user_id=user_id,
            product_id=prod_id,
            quantity=Decimal("50.00"),
            unit_cost=Decimal("2.80"),
            reference_doc="OC-2026-0001 / NF 9876",
            notes="Recebimento aprovado pelo almoxarifado"
        )

        assert mock_product.current_stock == Decimal("60.0000")
        mock_update_prod.assert_called_once_with(db_mock, mock_product)
        mock_create_mov.assert_called_once()
        _, kwargs = mock_create_mov.call_args
        mov_arg = kwargs.get("movement") or _[1]
        assert mov_arg.movement_type == "in_purchase"
        assert mov_arg.quantity == Decimal("50.00")
        assert mov_arg.unit_cost == Decimal("2.80")
        assert mov_arg.balance_after == Decimal("60.0000")


def test_adjust_stock_invoice_entry_success():
    """Valida a entrada física por Nota Fiscal com registro de fornecedor e lote."""
    db_mock = MagicMock()
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    prod_id = uuid.uuid4()

    mock_product = models.Product(
        id=prod_id,
        organization_id=org_id,
        name="Amoxicilina 500mg",
        sku="MED-AMX-0001",
        current_stock=Decimal("20.0000"),
        min_stock=Decimal("15.00"),
        reference_price=Decimal("8.5000"),
        is_active=True
    )

    payload = schemas.StockAdjustmentCreate(
        product_id=prod_id,
        adjustment_type="invoice_entry",
        quantity=Decimal("100.00"),
        unit_cost=Decimal("7.90"),
        invoice_number="004.892 - Série 1",
        supplier_name="EMS Farmacêutica",
        batch_number="LT-2026-904",
        expiry_date="2027-12-31",
        notes="Recebimento e conferência na doca de entrada"
    )

    with patch("controlb.modules.inventory.repository.get_product_by_id", return_value=mock_product), \
         patch("controlb.modules.inventory.repository.update_product") as mock_update_prod, \
         patch("controlb.modules.inventory.repository.create_stock_movement") as mock_create_mov:

        service.adjust_stock(
            db=db_mock,
            organization_id=org_id,
            user_id=user_id,
            payload=payload
        )

        assert mock_product.current_stock == Decimal("120.0000")
        assert mock_product.reference_price == Decimal("7.9000")
        mock_update_prod.assert_called_once_with(db_mock, mock_product)
        mock_create_mov.assert_called_once()
        _, kwargs = mock_create_mov.call_args
        mov_arg = kwargs.get("movement") or _[1]
        assert mov_arg.movement_type == "in_invoice"
        assert mov_arg.quantity == Decimal("100.00")
        assert "NF: 004.892 - Série 1" in mov_arg.reference_doc
        assert "Forn: EMS Farmacêutica" in mov_arg.reference_doc
        assert "Lote: LT-2026-904" in mov_arg.reference_doc
        assert mov_arg.balance_after == Decimal("120.0000")

