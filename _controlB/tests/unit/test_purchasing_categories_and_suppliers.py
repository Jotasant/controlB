"""
tests/unit/test_purchasing_categories_and_suppliers.py - Testes unitários para Categorias e Fornecedores Avançados.
"""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch
import pytest
from fastapi import HTTPException

from controlb.modules.purchasing.service import (
    update_category_data,
    delete_category_record
)
from controlb.modules.purchasing import models, schemas


def test_update_category_success():
    """Valida a atualização dos dados cadastrais de uma categoria de produto."""
    db_mock = MagicMock()
    org_id = uuid.uuid4()
    cat_id = uuid.uuid4()

    mock_category = models.ProductCategory(
        id=cat_id,
        organization_id=org_id,
        name="Medicamentos",
        code="MED",
        description="Descrição antiga"
    )

    update_payload = schemas.ProductCategoryUpdate(
        name="Medicamentos Controlados",
        code="MED-CTRL",
        description="Portaria 344/98"
    )

    with patch("controlb.modules.purchasing.repository.get_product_category_by_id", return_value=mock_category), \
         patch("controlb.modules.purchasing.repository.update_product_category") as mock_update:
        
        mock_update.return_value = mock_category
        result = update_category_data(db_mock, category_id=cat_id, organization_id=org_id, category_data=update_payload)
        
        assert result is not None
        mock_update.assert_called_once()


def test_delete_category_fails_if_has_products():
    """Valida que uma categoria com produtos vinculados não pode ser excluída."""
    db_mock = MagicMock()
    org_id = uuid.uuid4()
    cat_id = uuid.uuid4()

    mock_product = models.Product(
        id=uuid.uuid4(),
        organization_id=org_id,
        sku="MED-001",
        name="Dipirona 500mg"
    )

    mock_category = models.ProductCategory(
        id=cat_id,
        organization_id=org_id,
        name="Medicamentos",
        code="MED"
    )
    mock_category.products = [mock_product]

    with patch("controlb.modules.purchasing.repository.get_product_category_by_id", return_value=mock_category):
        with pytest.raises(HTTPException) as exc_info:
            delete_category_record(db_mock, category_id=cat_id, organization_id=org_id)
        
        assert exc_info.value.status_code == 400
        assert "produto(s) vinculado(s)" in exc_info.value.detail


def test_delete_category_success_if_no_products():
    """Valida que uma categoria sem produtos vinculados é excluída com sucesso."""
    db_mock = MagicMock()
    org_id = uuid.uuid4()
    cat_id = uuid.uuid4()

    mock_category = models.ProductCategory(
        id=cat_id,
        organization_id=org_id,
        name="Categoria Vazia",
        code="VAZ"
    )
    mock_category.products = []

    with patch("controlb.modules.purchasing.repository.get_product_category_by_id", return_value=mock_category), \
         patch("controlb.modules.purchasing.repository.delete_product_category") as mock_del:
        
        res = delete_category_record(db_mock, category_id=cat_id, organization_id=org_id)
        
        assert res["detail"] == "Categoria de produto excluída com sucesso."
        mock_del.assert_called_once_with(db_mock, db_category=mock_category)
