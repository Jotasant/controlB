"""
tests/unit/test_purchasing_sku.py - Testes unitários para o gerador de SKU automático.
"""

import uuid
from unittest.mock import MagicMock
from controlb.modules.purchasing.service import generate_product_sku
from controlb.modules.purchasing import models


def test_generate_product_sku_with_category_code():
    """Valida a geração de SKU com código de categoria explícito."""
    db_mock = MagicMock()
    org_id = uuid.uuid4()
    cat_id = uuid.uuid4()

    mock_category = models.ProductCategory(
        id=cat_id,
        organization_id=org_id,
        name="Medicamentos Hospitalares",
        code="MED"
    )

    # Mock do repository para retornar a categoria e nenhum produto prévio com o SKU
    from unittest.mock import patch
    with patch("controlb.modules.purchasing.repository.get_product_category_by_id", return_value=mock_category), \
         patch("controlb.modules.purchasing.repository.get_product_by_sku", return_value=None):
        
        sku = generate_product_sku(
            db=db_mock,
            organization_id=org_id,
            name="Paracetamol 500mg",
            category_id=cat_id,
            unit_of_measure="CX"
        )

        assert sku == "MED-PARACETAMOL-500MG-CX-0001"


def test_generate_product_sku_without_category():
    """Valida a geração de SKU com prefixo genérico GEN quando não há categoria."""
    db_mock = MagicMock()
    org_id = uuid.uuid4()

    from unittest.mock import patch
    with patch("controlb.modules.purchasing.repository.get_product_category_by_id", return_value=None), \
         patch("controlb.modules.purchasing.repository.get_product_by_sku", return_value=None):
        
        sku = generate_product_sku(
            db=db_mock,
            organization_id=org_id,
            name="Luva de Procedimento Látex P",
            category_id=None,
            unit_of_measure="UN"
        )

        assert sku == "GEN-LUVA-PROCEDIMENTO-LATEX-UN-0001"


def test_generate_product_sku_collision_resolution():
    """Valida o incremento sequencial (-0002) quando já existe um item com o mesmo SKU base."""
    db_mock = MagicMock()
    org_id = uuid.uuid4()

    # Simula que o primeiro SKU (-0001) já existe no banco, mas o segundo (-0002) está livre
    existing_product = models.Product(id=uuid.uuid4(), sku="GEN-ALCOOL-GEL-70-L-0001")

    from unittest.mock import patch
    with patch("controlb.modules.purchasing.repository.get_product_category_by_id", return_value=None), \
         patch("controlb.modules.purchasing.repository.get_product_by_sku", side_effect=[existing_product, None]):
        
        sku = generate_product_sku(
            db=db_mock,
            organization_id=org_id,
            name="Álcool em Gel 70% 1L",
            category_id=None,
            unit_of_measure="L"
        )

        assert sku == "GEN-ALCOOL-GEL-70-L-0002"
