"""
tests/unit/test_procurement_inventory_invoice_cycle.py - Testes unitários para o ciclo integrado:
Compra -> Nota Fiscal -> Recebimento Físico -> Kardex -> Fatura a Pagar -> Boleto -> Baixa.
"""

import uuid
from decimal import Decimal
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch
import pytest

from controlb.modules.purchasing import models as purchasing_models
from controlb.modules.purchasing import schemas as purchasing_schemas
from controlb.modules.purchasing.service import receive_purchase_order_shipment
from controlb.modules.inventory import models as inventory_models
from controlb.modules.inventory import schemas as inventory_schemas
from controlb.modules.inventory.service import adjust_stock
from controlb.modules.finance import models as finance_models
from controlb.modules.finance import schemas as finance_schemas
from controlb.modules.finance.service import create_payable_expense
from controlb.modules.identity.models import User


def test_receive_purchase_order_creates_nfe_receipt_kardex_and_payable_with_boleto():
    """Valida o ciclo completo de recebimento de OC gerando NF-e, Kardex, Fatura e Boleto."""
    db_mock = MagicMock()
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    order_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    sup_id = uuid.uuid4()
    prod_id = uuid.uuid4()
    receipt_id = uuid.uuid4()
    fiscal_doc_id = uuid.uuid4()
    payable_id = uuid.uuid4()

    mock_org = MagicMock()
    mock_org.name = "ControlB Farma"
    mock_user = User(
        id=user_id,
        organization_id=org_id,
        email="comprador@controlb.com",
    )
    mock_user.organization = mock_org

    mock_supplier = purchasing_models.Supplier(
        id=sup_id,
        organization_id=org_id,
        name="Distribuidora Farmacêutica Beta Ltda",
        cnpj_cpf="12.345.678/0001-90",
        is_active=True,
    )

    mock_order = purchasing_models.PurchaseOrder(
        id=order_id,
        document_id=doc_id,
        organization_id=org_id,
        buyer_id=user_id,
        supplier_id=sup_id,
        supplier=mock_supplier,
        order_number="PO-2026-0099",
        status="issued",
        total_amount=Decimal("1500.00"),
        cost_center_id=uuid.uuid4(),
        items=[
            purchasing_models.PurchaseOrderItem(
                id=uuid.uuid4(),
                purchase_order_id=order_id,
                product_id=prod_id,
                quantity=Decimal("100.00"),
                unit_price=Decimal("15.00"),
                total_price=Decimal("1500.00"),
            )
        ],
    )

    mock_order_doc = MagicMock(
        id=doc_id,
        document_number="PO-2026-0099",
        current_status="ISSUED",
        organization_id=org_id,
    )

    mock_fiscal_doc = finance_models.FiscalDocument(
        id=fiscal_doc_id,
        organization_id=org_id,
        document_id=uuid.uuid4(),
        document_number="987654",
        series="1",
        access_key="35260912345678000190550010009876541234567890",
        direction="INBOUND",
        total_amount=Decimal("1500.00"),
        status="authorized",
    )

    mock_movement = inventory_models.StockMovement(
        id=uuid.uuid4(),
        organization_id=org_id,
        product_id=prod_id,
        receipt_id=receipt_id,
        fiscal_document_id=fiscal_doc_id,
        movement_type="in_purchase",
        quantity=Decimal("100.00"),
        unit_cost=Decimal("15.00"),
        balance_after=Decimal("150.00"),
    )

    mock_receipt = inventory_models.InventoryReceipt(
        id=receipt_id,
        organization_id=org_id,
        purchase_order_id=order_id,
        document_id=uuid.uuid4(),
        receipt_number="REC-2026-0001",
        invoice_number="987654",
        fiscal_document_id=fiscal_doc_id,
        received_at=datetime.now(timezone.utc),
        movements=[mock_movement],
    )

    mock_payable = finance_models.Payable(
        id=payable_id,
        organization_id=org_id,
        document_id=uuid.uuid4(),
        payable_number="PAG-2026-0001",
        supplier_id=sup_id,
        purchase_order_id=order_id,
        fiscal_document_id=fiscal_doc_id,
        inventory_receipt_id=receipt_id,
        original_amount=Decimal("1500.00"),
        outstanding_amount=Decimal("1500.00"),
        issue_date=date.today(),
        due_date=date.today(),
        status="APPROVED",
    )

    payload = purchasing_schemas.PurchaseOrderReceive(
        invoice_number="987654",
        invoice_type="NFE",
        invoice_series="1",
        invoice_access_key="35260912345678000190550010009876541234567890",
        invoice_tax_amount=Decimal("180.00"),
        generate_payable=True,
        payable_due_date=date.today(),
        payment_method_expected="BOLETO",
        digitable_line="34191.79001 01043.510047 91020.150008 5 99990000150000",
        barcode="34195999900001500001790001043510049102015000",
        notes="Recebido e conferido com sucesso",
    )

    with patch("controlb.modules.purchasing.repository.get_purchase_order_by_id", return_value=mock_order), \
         patch("controlb.modules.purchasing.service.get_purchase_order_document", return_value=mock_order_doc), \
         patch("controlb.modules.purchasing.repository.receive_purchase_order", return_value=mock_order), \
         patch("controlb.modules.finance.service.persist_fiscal_document", return_value=mock_fiscal_doc) as mock_persist_fiscal, \
         patch("controlb.modules.inventory.service.record_purchase_order_receipt", return_value=mock_receipt) as mock_record_receipt, \
         patch("controlb.modules.documents.service.get_document", return_value=mock_order_doc), \
         patch("controlb.modules.documents.service.relate_documents") as mock_relate_docs, \
         patch("controlb.modules.finance.service.create_payable_expense", return_value=[mock_payable]) as mock_create_payable, \
         patch("controlb.modules.purchasing.service.transition_purchase_order_status", return_value=mock_order):

        result = receive_purchase_order_shipment(
            db=db_mock,
            order_id=order_id,
            current_user=mock_user,
            data=payload,
        )

        assert result.id == order_id
        mock_record_receipt.assert_called_once()

        mock_persist_fiscal.assert_called_once()
        fiscal_payload = mock_persist_fiscal.call_args.args[3]
        assert fiscal_payload.document_number == "987654"
        assert fiscal_payload.access_key == "35260912345678000190550010009876541234567890"

        mock_create_payable.assert_called_once()
        payable_payload = mock_create_payable.call_args.args[3]
        assert payable_payload.fiscal_document_id == fiscal_doc_id
        assert payable_payload.inventory_receipt_id == receipt_id
        assert payable_payload.instrument is not None
        assert payable_payload.instrument.digitable_line == "34191.79001 01043.510047 91020.150008 5 99990000150000"

        # Confirma que o StockMovement recebeu o fiscal_document_id e o payable_id
        assert mock_movement.fiscal_document_id == fiscal_doc_id
        assert mock_movement.payable_id == payable_id


def test_outbound_stock_movement_categorization():
    """Valida a categorização precisa dos motivos de saída de estoque no Kardex."""
    db_mock = MagicMock()
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    prod_id = uuid.uuid4()

    mock_product = inventory_models.Product(
        id=prod_id,
        organization_id=org_id,
        name="Amoxicilina 500mg",
        sku="MED-AMX-001",
        current_stock=Decimal("100.00"),
        unit_of_measure="UN",
        reference_price=Decimal("20.00"),
    )

    mock_loc_balance = MagicMock(location_id=uuid.uuid4(), quantity=Decimal("90.00"))

    with patch("controlb.modules.inventory.repository.get_product_by_id", return_value=mock_product), \
         patch("controlb.modules.inventory.repository.update_product", return_value=mock_product), \
         patch("controlb.modules.inventory.service.sync_default_location_balance", return_value=mock_loc_balance), \
         patch("controlb.modules.inventory.service.documents_service.create_document", return_value=MagicMock(id=uuid.uuid4(), document_number="MOVE-2026-0001")), \
         patch("controlb.modules.inventory.repository.create_stock_movement") as mock_create_movement:

        # 1. Perda / Avaria (loss_damage)
        payload_loss = inventory_schemas.StockAdjustmentCreate(
            product_id=prod_id,
            adjustment_type="remove_stock",
            outbound_reason="loss_damage",
            quantity=Decimal("5.00"),
            reason="Frasco quebrado durante manuseio",
        )
        adjust_stock(db_mock, org_id, user_id, payload_loss)
        movement_loss = mock_create_movement.call_args[0][1]
        assert movement_loss.movement_type == "out_loss"

        # 2. Consumo Interno (internal_consumption)
        payload_consump = inventory_schemas.StockAdjustmentCreate(
            product_id=prod_id,
            adjustment_type="remove_stock",
            outbound_reason="internal_consumption",
            quantity=Decimal("2.00"),
            reason="Uso no ambulatório interno da empresa",
        )
        adjust_stock(db_mock, org_id, user_id, payload_consump)
        movement_consump = mock_create_movement.call_args[0][1]
        assert movement_consump.movement_type == "out_internal_consumption"

        # 3. Devolução ao Fornecedor (supplier_return)
        payload_return = inventory_schemas.StockAdjustmentCreate(
            product_id=prod_id,
            adjustment_type="remove_stock",
            outbound_reason="supplier_return",
            quantity=Decimal("10.00"),
            reason="Lote com defeito devolvido ao fabricante",
        )
        adjust_stock(db_mock, org_id, user_id, payload_return)
        movement_return = mock_create_movement.call_args[0][1]
        assert movement_return.movement_type == "out_return_supplier"

        # 4. Ajuste Técnico / Inventário (inventory_adjustment)
        payload_adj = inventory_schemas.StockAdjustmentCreate(
            product_id=prod_id,
            adjustment_type="remove_stock",
            outbound_reason="inventory_adjustment",
            quantity=Decimal("1.00"),
            reason="Ajuste de contagem periódica",
        )
        adjust_stock(db_mock, org_id, user_id, payload_adj)
        movement_adj = mock_create_movement.call_args[0][1]
        assert movement_adj.movement_type == "out_adjustment"
