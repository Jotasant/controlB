"""
tests/unit/test_inventory_import.py - Testes de Importação e Sincronização de Planilha de Estoque
"""

import os
import uuid
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from controlb.db import Base
from controlb.modules.identity.models import Organization, User
from controlb.modules.inventory.models import Product, ProductCategory, StockMovement
from controlb.modules.inventory.service import import_inventory_spreadsheet
from controlb.modules.inventory.spreadsheet_parser import parse_inventory_xlsx, classify_category_by_ncm


@pytest.fixture
def db_session():
    """Cria banco SQLite em memória isolado para os testes de inventário."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            Organization.__table__,
            User.__table__,
            ProductCategory.__table__,
            Product.__table__,
            StockMovement.__table__,
        ],
    )
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_classify_category_by_ncm():
    assert classify_category_by_ncm("3004.90.69", "DIPIRONA 500MG") == "Medicamentos"
    assert classify_category_by_ncm("3004.90.69", "+ IVERMECTINA 6 MG 4 CPS / GEN") == "Medicamentos Genéricos"
    assert classify_category_by_ncm("3305.90.00", "SHAMPOO ELSEVE 200ML") == "Cosméticos & Perfumaria"
    assert classify_category_by_ncm("2106.90.30", "VITAMINA C 1000MG") == "Suplementos & Vitaminas"
    assert classify_category_by_ncm("3005.10.10", "ESPARADRAPO 10X4,5") == "Materiais Médicos & Antissépticos"
    assert classify_category_by_ncm("9999.99.99", "PRODUTO DIVERSO") == "Diversos & Cuidados Pessoais"


def test_inventory_full_spreadsheet_import(db_session):
    # 1. Cria organização e usuário de teste
    org = Organization(name="FarmaNutri Teste")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)

    user = User(
        organization_id=org.id,
        email="farmaceutico@farmanutri.com.br",
        full_name="Farmacêutico Responsável",
        hashed_password="hash"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    xlsx_path = os.path.join(os.path.dirname(__file__), "..", "..", "Arquivos", "relatorio.xlsx")
    assert os.path.exists(xlsx_path), f"Arquivo não encontrado em {xlsx_path}"

    with open(xlsx_path, "rb") as f:
        file_bytes = f.read()

    # 2. Primeira Importação (Carga Inicial)
    result = import_inventory_spreadsheet(
        db=db_session,
        organization_id=org.id,
        user_id=user.id,
        file_bytes=file_bytes
    )

    assert result["total_products_read"] == 1598
    assert result["created_products_count"] + result["updated_products_count"] == 1598
    assert result["created_products_count"] == 1588  # 1588 produtos únicos
    assert result["created_categories_count"] > 0
    assert result["total_cost_value"] > Decimal("50000.00")

    # Verifica produtos únicos cadastrados no banco
    db_products = db_session.query(Product).filter(Product.organization_id == org.id).all()
    assert len(db_products) == 1588

    # Verifica se categorias foram associadas
    prods_with_cat = [p for p in db_products if p.category_id is not None]
    assert len(prods_with_cat) == 1588

    # 3. Segunda Importação: Simulando Venda e Reposição no dia seguinte
    test_prod = db_products[0]
    # Simulamos que antes da 2ª importação o produto tinha saldo 10
    test_prod.current_stock = Decimal("10.0000")
    db_session.commit()

    # Rodamos a importação de novo (o relatório tem saldo original 5, logo deve detectar venda de 5)
    result_day2 = import_inventory_spreadsheet(
        db=db_session,
        organization_id=org.id,
        user_id=user.id,
        file_bytes=file_bytes
    )

    assert result_day2["created_products_count"] == 0
    assert result_day2["updated_products_count"] == 1598
    assert result_day2["sales_identified_count"] >= 1

    # Verifica se a movimentação de out_sale foi criada
    sales_mov = db_session.query(StockMovement).filter(
        StockMovement.product_id == test_prod.id,
        StockMovement.movement_type == "out_sale"
    ).first()
    assert sales_mov is not None
    assert sales_mov.quantity == Decimal("5.0000")
