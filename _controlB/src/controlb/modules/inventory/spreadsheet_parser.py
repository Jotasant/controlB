"""
modules/inventory/spreadsheet_parser.py - Motor de Parsing e Classificação de Planilhas de Estoque

Responsabilidades:
1. Extrair de forma robusta e otimizada os dados brutos da planilha .xlsx de inventário e estoque.
2. Tratar quebras de página, cabeçalhos repetidos e dados numéricos com casas decimais.
3. Classificar inteligentemente a categoria farmacêutica / comercial do item com base no NCM e descrição.
"""

import io
import zipfile
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from typing import TypedDict


class ParsedInventoryProduct(TypedDict):
    code: str
    barcode: str | None
    name: str
    ncm: str | None
    quantity: Decimal
    unit_of_measure: str
    cost_price: Decimal
    total_cost: Decimal
    sale_price: Decimal
    total_sale: Decimal
    suggested_category_name: str


class ParsedInventoryReport(TypedDict):
    company_name: str | None
    company_cnpj: str | None
    inventory_date: str | None
    total_cost: Decimal
    total_sale: Decimal
    products: list[ParsedInventoryProduct]


# Aliases para compatibilidade
ParsedToolsPharmaProduct = ParsedInventoryProduct
ParsedToolsPharmaReport = ParsedInventoryReport


def classify_category_by_ncm(ncm: str | None, product_name: str | None) -> str:
    """
    Classifica a categoria do produto com base no código fiscal NCM e na taxonomia farmacêutica / comercial.
    
    Regras da Nomenclatura Comum do Mercosul (NCM) e Farmácia:
    - 3003, 3004: Medicamentos e especialidades farmacêuticas
    - 3303, 3304, 3305, 3307 ou prefixo '#': Cosméticos, Higiene e Perfumaria
    - 2106, 2202, 1517: Suplementos alimentares, Vitaminas e Nutrição
    - 3005, 3006, 3808, 3926, 9018: Materiais Médicos, Curativos e Correlatos
    - Demais: Diversos & Cuidados Pessoais
    """
    clean_ncm = (ncm or "").replace(".", "").strip()
    name = (product_name or "").upper()

    if clean_ncm.startswith(("3003", "3004")):
        if name.startswith("+") or "/ GEN" in name or "GENERICO" in name:
            return "Medicamentos Genéricos"
        return "Medicamentos"
    elif clean_ncm.startswith(("3303", "3304", "3305", "3307")) or name.startswith("#") or "SHAMP" in name or "DES DOVE" in name:
        return "Cosméticos & Perfumaria"
    elif clean_ncm.startswith(("2106", "2202", "1517")) or "VITAMINA" in name or "QUELATO" in name or "SUPLEM" in name:
        return "Suplementos & Vitaminas"
    elif clean_ncm.startswith(("3005", "3006", "3808", "3926", "9018")) or "SERINGA" in name or "AGULHA" in name or "ALCOOL" in name:
        return "Materiais Médicos & Antissépticos"
    else:
        return "Diversos & Cuidados Pessoais"


def parse_decimal(val: str | None, default: Decimal = Decimal("0.0000")) -> Decimal:
    """Converte valores numéricos em string para Decimal com tolerância a falhas."""
    if not val:
        return default
    try:
        cleaned = str(val).strip().replace(",", ".")
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return default


def parse_inventory_xlsx(file_content: bytes) -> ParsedInventoryReport:
    """
    Realiza o parsing direto do arquivo .xlsx na memória através do container ZIP e XMLs nativos.
    Garante máxima velocidade e zero dependências de bibliotecas C/pesadas.
    """
    with zipfile.ZipFile(io.BytesIO(file_content), "r") as z:
        # 1. Carrega tabela de strings compartilhadas (sharedStrings.xml)
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            tree = ET.fromstring(z.read("xl/sharedStrings.xml"))
            ns = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            for si in tree.findall("main:si", ns):
                t = si.find("main:t", ns)
                if t is not None and t.text:
                    shared_strings.append(t.text)
                else:
                    text_parts = [elem.text for elem in si.findall(".//main:t", ns) if elem.text]
                    shared_strings.append("".join(text_parts))

        # 2. Carrega a primeira planilha da pasta de trabalho (sheet1.xml)
        sheet_xml = z.read("xl/worksheets/sheet1.xml")
        sheet_tree = ET.fromstring(sheet_xml)
        ns = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

        company_name: str | None = None
        company_cnpj: str | None = None
        inventory_date: str | None = None
        total_cost = Decimal("0.00")
        total_sale = Decimal("0.00")
        products: list[ParsedInventoryProduct] = []

        for row in sheet_tree.findall(".//main:row", ns):
            cells: dict[str, str | None] = {}
            for c in row.findall("main:c", ns):
                cell_ref = c.attrib.get("r", "")
                col_letter = "".join([ch for ch in cell_ref if ch.isalpha()])
                cell_type = c.attrib.get("t")
                v = c.find("main:v", ns)
                val = None
                if v is not None and v.text is not None:
                    val = v.text
                    if cell_type == "s":
                        idx = int(val)
                        val = shared_strings[idx] if idx < len(shared_strings) else val
                cells[col_letter] = val

            # Captura metadados do cabeçalho
            if "B" in cells and cells["B"] and len(str(cells["B"]).strip()) > 3:
                company_name = str(cells["B"]).strip()
            if "C" in cells and cells["C"] and "/" in str(cells["C"]):
                company_cnpj = str(cells["C"]).strip()
            if "X" in cells and "Estoque do dia" in str(cells.get("X", "")):
                # Data informada no cabeçalho
                inventory_date = str(cells.get("AB") or cells.get("AA") or "").strip()
            elif "A" in cells and "/" in str(cells.get("A", "")) and ":" in str(cells.get("A", "")):
                # Rodapé com data (ex: '16/08/26 10:30')
                inventory_date = str(cells["A"]).strip()

            # Captura produto
            code = cells.get("A")
            barcode = cells.get("E")
            name = cells.get("I")
            ncm = cells.get("O")
            qty = cells.get("S")
            un = cells.get("U")
            cost = cells.get("V")
            tot_cost = cells.get("W")
            price = cells.get("Z")
            tot_price = cells.get("AA")

            # Valida se é linha de produto legítimo (código numérico e não cabeçalho)
            if code and name and code.strip().isdigit() and name.strip() != "Produto":
                q_dec = parse_decimal(qty)
                c_dec = parse_decimal(cost)
                p_dec = parse_decimal(price)
                tc_dec = parse_decimal(tot_cost, q_dec * c_dec)
                tp_dec = parse_decimal(tot_price, q_dec * p_dec)

                total_cost += tc_dec
                total_sale += tp_dec

                prod_name = name.strip()
                ncm_clean = ncm.strip() if ncm else None

                products.append({
                    "code": code.strip(),
                    "barcode": barcode.strip() if barcode else None,
                    "name": prod_name,
                    "ncm": ncm_clean,
                    "quantity": q_dec,
                    "unit_of_measure": un.strip() if un else "UN",
                    "cost_price": c_dec,
                    "total_cost": tc_dec,
                    "sale_price": p_dec,
                    "total_sale": tp_dec,
                    "suggested_category_name": classify_category_by_ncm(ncm_clean, prod_name)
                })

        return {
            "company_name": company_name,
            "company_cnpj": company_cnpj,
            "inventory_date": inventory_date,
            "total_cost": total_cost,
            "total_sale": total_sale,
            "products": products
        }


# Alias para retrocompatibilidade
parse_toolspharma_xlsx = parse_inventory_xlsx
