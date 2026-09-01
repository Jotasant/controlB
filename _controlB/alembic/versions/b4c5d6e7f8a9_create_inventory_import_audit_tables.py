"""create inventory_import_batch and inventory_import_item tables

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-09-01 12:06:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b4c5d6e7f8a9"
down_revision: str | Sequence[str] | None = "a3b4c5d6e7f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. inventory_import_batch
    op.create_table(
        "inventory_import_batch",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organization.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("batch_number", sa.String(length=50), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column("inventory_date", sa.String(length=100), nullable=True),
        sa.Column("total_products_read", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_products_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_products_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_categories_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sales_identified_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_sales_quantity", sa.Numeric(14, 4), nullable=False, server_default="0.0000"),
        sa.Column("total_sales_estimated_revenue", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("entries_identified_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_entries_quantity", sa.Numeric(14, 4), nullable=False, server_default="0.0000"),
        sa.Column("total_entries_cost", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("cost_increases_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_decreases_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stagnant_products_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_stagnant_capital", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("total_inventory_cost", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("total_inventory_sale", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("imported_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("id", "organization_id", name="uq_inventory_import_batch_id_org"),
    )
    op.create_index("ix_inventory_import_batch_org_created", "inventory_import_batch", ["organization_id", "created_at"])

    # 2. inventory_import_item
    op.create_table(
        "inventory_import_item",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("product.id", ondelete="SET NULL"), nullable=True),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("barcode", sa.String(length=100), nullable=True),
        sa.Column("sku", sa.String(length=100), nullable=True),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("ncm", sa.String(length=20), nullable=True),
        sa.Column("unit_of_measure", sa.String(length=20), nullable=False, server_default="UN"),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("previous_stock", sa.Numeric(14, 4), nullable=False, server_default="0.0000"),
        sa.Column("new_stock", sa.Numeric(14, 4), nullable=False, server_default="0.0000"),
        sa.Column("delta_stock", sa.Numeric(14, 4), nullable=False, server_default="0.0000"),
        sa.Column("previous_cost_price", sa.Numeric(14, 4), nullable=True),
        sa.Column("new_cost_price", sa.Numeric(14, 4), nullable=False, server_default="0.0000"),
        sa.Column("cost_variation_amount", sa.Numeric(14, 4), nullable=False, server_default="0.0000"),
        sa.Column("cost_variation_percent", sa.Numeric(8, 2), nullable=True),
        sa.Column("previous_sale_price", sa.Numeric(14, 4), nullable=True),
        sa.Column("new_sale_price", sa.Numeric(14, 4), nullable=False, server_default="0.0000"),
        sa.Column("sale_variation_amount", sa.Numeric(14, 4), nullable=False, server_default="0.0000"),
        sa.Column("sale_variation_percent", sa.Numeric(8, 2), nullable=True),
        sa.Column("stagnant_value", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("estimated_sales_revenue", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["batch_id", "organization_id"], ["inventory_import_batch.id", "inventory_import_batch.organization_id"], name="fk_inventory_import_item_batch_org", ondelete="CASCADE"),
    )
    op.create_index("ix_inventory_import_item_batch", "inventory_import_item", ["batch_id"])
    op.create_index("ix_inventory_import_item_product", "inventory_import_item", ["organization_id", "product_id"])
    op.create_index("ix_inventory_import_item_action", "inventory_import_item", ["organization_id", "action_type"])


def downgrade() -> None:
    op.drop_index("ix_inventory_import_item_action", table_name="inventory_import_item")
    op.drop_index("ix_inventory_import_item_product", table_name="inventory_import_item")
    op.drop_index("ix_inventory_import_item_batch", table_name="inventory_import_item")
    op.drop_table("inventory_import_item")

    op.drop_index("ix_inventory_import_batch_org_created", table_name="inventory_import_batch")
    op.drop_table("inventory_import_batch")
