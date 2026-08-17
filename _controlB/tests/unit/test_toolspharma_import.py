"""
tests/unit/test_toolspharma_import.py - Teste de Compatibilidade para import_toolspharma_inventory
"""

from controlb.modules.inventory.service import import_toolspharma_inventory, import_inventory_spreadsheet
from controlb.modules.inventory.toolspharma_parser import parse_toolspharma_xlsx, parse_inventory_xlsx


def test_toolspharma_compatibility_aliases():
    assert import_toolspharma_inventory == import_inventory_spreadsheet
    assert parse_toolspharma_xlsx == parse_inventory_xlsx
