"""separate payable accounting nature, obligation type and business origin

Revision ID: g8h9i0j1k2l3
Revises: f7g8h9i0j1k2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "g8h9i0j1k2l3"
down_revision: str | Sequence[str] | None = "f7g8h9i0j1k2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "payable",
        "expense_nature",
        existing_type=sa.String(length=20),
        type_=sa.String(length=30),
        existing_nullable=False,
    )
    op.add_column(
        "payable",
        sa.Column("obligation_type", sa.String(length=40), nullable=False, server_default="OTHER"),
    )
    op.add_column(
        "payable",
        sa.Column("business_origin", sa.String(length=40), nullable=False, server_default="MANUAL"),
    )

    op.execute(
        """
        UPDATE payable
        SET expense_nature = CASE
            WHEN upper(expense_nature) IN (
                'OPEX', 'CAPEX', 'FINANCIAL', 'TAX', 'PAYROLL', 'TRANSFER', 'NOT_APPLICABLE'
            ) THEN upper(expense_nature)
            ELSE 'NOT_APPLICABLE'
        END,
        obligation_type = CASE
            WHEN supplier_id IS NOT NULL OR purchase_order_id IS NOT NULL
                THEN 'GOODS_SUPPLIER'
            ELSE 'OTHER'
        END,
        business_origin = CASE
            WHEN purchase_order_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM purchase_order
                WHERE purchase_order.id = payable.purchase_order_id
                  AND purchase_order.organization_id = payable.organization_id
                  AND purchase_order.replenishment_id IS NOT NULL
            ) THEN 'REPLENISHMENT'
            WHEN purchase_order_id IS NOT NULL THEN 'PURCHASE'
            WHEN fiscal_document_id IS NOT NULL THEN 'FISCAL_DOCUMENT'
            ELSE 'MANUAL'
        END
        """
    )

    op.alter_column("payable", "obligation_type", server_default=None)
    op.alter_column("payable", "business_origin", server_default=None)
    op.create_check_constraint(
        "ck_payable_expense_nature",
        "payable",
        "expense_nature IN ('OPEX', 'CAPEX', 'FINANCIAL', 'TAX', 'PAYROLL', 'TRANSFER', 'NOT_APPLICABLE')",
    )
    op.create_check_constraint(
        "ck_payable_obligation_type",
        "payable",
        "obligation_type IN ('GOODS_SUPPLIER', 'SERVICE_PROVIDER', 'TAX', 'PAYROLL', 'RENT_LEASE', 'FINANCING', 'REIMBURSEMENT', 'INVESTMENT', 'OTHER')",
    )
    op.create_check_constraint(
        "ck_payable_business_origin",
        "payable",
        "business_origin IN ('PURCHASE', 'REPLENISHMENT', 'INVESTMENT', 'CONTRACT', 'FISCAL_DOCUMENT', 'MANUAL', 'OTHER')",
    )
    op.create_index(
        "ix_payable_org_classification",
        "payable",
        ["organization_id", "obligation_type", "business_origin"],
    )


def downgrade() -> None:
    op.drop_index("ix_payable_org_classification", table_name="payable")
    op.drop_constraint("ck_payable_business_origin", "payable", type_="check")
    op.drop_constraint("ck_payable_obligation_type", "payable", type_="check")
    op.drop_constraint("ck_payable_expense_nature", "payable", type_="check")
    op.drop_column("payable", "business_origin")
    op.drop_column("payable", "obligation_type")
    op.alter_column(
        "payable",
        "expense_nature",
        existing_type=sa.String(length=30),
        type_=sa.String(length=20),
        existing_nullable=False,
    )
