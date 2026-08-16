"""
tests/unit/test_purchasing_request_deletion.py - Testes unitários para exclusão e purga de solicitações de compra.
"""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch
import pytest
from fastapi import HTTPException

from controlb.modules.purchasing import models
from controlb.modules.purchasing.service import (
    delete_purchase_request_record,
    purge_purchase_requests,
)


def test_delete_purchase_request_unlinks_orders_and_deletes_successfully():
    """Valida que a exclusão de uma solicitação de compra desvincula POs associadas e a remove com sucesso."""
    db_mock = MagicMock()
    org_id = uuid.uuid4()
    req_id = uuid.uuid4()
    order_id = uuid.uuid4()

    mock_request = models.PurchaseRequest(
        id=req_id,
        organization_id=org_id,
        request_number="PR-2026-0001",
        status="approved",
        total_estimated_amount=Decimal("150.00")
    )

    mock_order = models.PurchaseOrder(
        id=order_id,
        organization_id=org_id,
        purchase_request_id=req_id,
        supplier_quote_id=uuid.uuid4(),
        order_number="PO-2026-0001",
        status="issued"
    )

    with patch("controlb.modules.purchasing.service.repository.get_purchase_request_by_id", return_value=mock_request), \
         patch("controlb.modules.purchasing.service.repository.get_purchase_orders_by_request_id", return_value=[mock_order]), \
         patch("controlb.modules.purchasing.service.repository.delete_purchase_request") as mock_delete:
        
        result = delete_purchase_request_record(db_mock, request_id=req_id, organization_id=org_id)

        # Verifica se a ordem foi desvinculada
        assert mock_order.purchase_request_id is None
        assert mock_order.supplier_quote_id is None

        # Verifica se a deleção no repositório foi invocada
        mock_delete.assert_called_once_with(db_mock, db_request=mock_request)
        assert "PR-2026-0001" in result["detail"]


def test_delete_purchase_request_not_found():
    """Valida que tentar excluir uma solicitação inexistente gera 404."""
    db_mock = MagicMock()
    org_id = uuid.uuid4()
    req_id = uuid.uuid4()

    with patch("controlb.modules.purchasing.service.repository.get_purchase_request_by_id", return_value=None):
        with pytest.raises(HTTPException) as exc:
            delete_purchase_request_record(db_mock, request_id=req_id, organization_id=org_id)
        assert exc.value.status_code == 404


def test_purge_purchase_requests_success():
    """Valida a rotina de purga em lote de solicitações de compra."""
    db_mock = MagicMock()
    org_id = uuid.uuid4()

    req1 = models.PurchaseRequest(id=uuid.uuid4(), organization_id=org_id, request_number="PR-01")
    req2 = models.PurchaseRequest(id=uuid.uuid4(), organization_id=org_id, request_number="PR-02")

    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = [req1, req2]
    db_mock.query.return_value = mock_query

    with patch("controlb.modules.purchasing.service.repository.get_purchase_orders_by_request_id", return_value=[]):
        result = purge_purchase_requests(db_mock, organization_id=org_id)

        assert result["deleted_count"] == 2
        assert db_mock.delete.call_count == 2
        assert db_mock.commit.called
