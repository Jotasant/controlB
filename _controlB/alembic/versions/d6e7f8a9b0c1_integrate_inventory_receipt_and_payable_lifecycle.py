"""integrate inventory receipt, stock movement and payable lifecycle

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-09-01 13:12:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d6e7f8a9b0c1"
down_revision: str | Sequence[str] | None = "c5d6e7f8a9b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. inventory_receipt: fiscal_document_id
    op.add_column(
        "inventory_receipt",
        sa.Column("fiscal_document_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_inventory_receipt_fiscal_document_org",
        "inventory_receipt",
        "fiscal_document",
        ["fiscal_document_id", "organization_id"],
        ["id", "organization_id"],
        ondelete="RESTRICT",
    )

    # 2. stock_movement: fiscal_document_id, payable_id
    op.add_column(
        "stock_movement",
        sa.Column("fiscal_document_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "stock_movement",
        sa.Column("payable_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # 3. payable: inventory_receipt_id
    op.add_column(
        "payable",
        sa.Column("inventory_receipt_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_payable_inventory_receipt_org",
        "payable",
        "inventory_receipt",
        ["inventory_receipt_id", "organization_id"],
        ["id", "organization_id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_payable_inventory_receipt_org", "payable", type_="foreignkey")
    op.drop_column("payable", "inventory_receipt_id")
    op.drop_column("stock_movement", "payable_id")
    op.drop_column("stock_movement", "fiscal_document_id")
    op.drop_constraint("fk_inventory_receipt_fiscal_document_org", "inventory_receipt", type_="foreignkey")
    op.drop_column("inventory_receipt", "fiscal_document_id")
