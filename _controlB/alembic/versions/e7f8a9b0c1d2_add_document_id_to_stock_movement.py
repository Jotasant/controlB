"""add document_id to stock_movement, pos_sale and sales_return

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-09-01 14:15:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e7f8a9b0c1d2"
down_revision: str | Sequence[str] | None = "d6e7f8a9b0c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. stock_movement: document_id
    op.add_column(
        "stock_movement",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_stock_movement_document",
        "stock_movement",
        ["organization_id", "document_id"],
    )

    # 2. pos_sale: document_id
    op.add_column(
        "pos_sale",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_pos_sale_document",
        "pos_sale",
        ["organization_id", "document_id"],
    )

    # 3. sales_return: document_id
    op.add_column(
        "sales_return",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_sales_return_document",
        "sales_return",
        ["organization_id", "document_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_sales_return_document", table_name="sales_return")
    op.drop_column("sales_return", "document_id")

    op.drop_index("ix_pos_sale_document", table_name="pos_sale")
    op.drop_column("pos_sale", "document_id")

    op.drop_index("ix_stock_movement_document", table_name="stock_movement")
    op.drop_column("stock_movement", "document_id")
