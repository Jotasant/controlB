"""add item-level and partial billing support

Revision ID: a1b2c3d4e5f7
Revises: g8h9i0j1k2l3
Create Date: 2026-09-01 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a1b2c3d4e5f7"
down_revision: str | Sequence[str] | None = "g8h9i0j1k2l3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invoice_item",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sales_order_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("product_sku", sa.String(length=100), nullable=True),
        sa.Column("quantity", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("discount_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_invoice_item_quantity_positive"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["invoice_id", "organization_id"],
            ["invoice.id", "invoice.organization_id"],
            name="fk_invoice_item_invoice_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sales_order_item_id"],
            ["sales_order_item.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id", "organization_id"],
            ["product.id", "product.organization_id"],
            name="fk_invoice_item_product_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "invoice_id", "sales_order_item_id", name="uq_invoice_item_order_item"
        ),
    )
    op.create_index(
        "ix_invoice_item_org_invoice",
        "invoice_item",
        ["organization_id", "invoice_id"],
    )
    op.create_index(
        "ix_invoice_item_order_item",
        "invoice_item",
        ["sales_order_item_id"],
    )

    # Faturas históricas geradas pelo fluxo antigo eram sempre integrais. O
    # backfill é deliberadamente conservador: somente a primeira fatura ativa
    # cujo total coincide com o pedido recebe snapshots de itens.
    op.execute(
        """
        WITH ranked_invoice AS (
            SELECT invoice.*,
                   row_number() OVER (
                       PARTITION BY invoice.sales_order_id
                       ORDER BY invoice.created_at, invoice.id
                   ) AS position
            FROM invoice
            JOIN sales_order
              ON sales_order.id = invoice.sales_order_id
             AND sales_order.organization_id = invoice.organization_id
            WHERE invoice.status <> 'CANCELLED'
              AND abs(invoice.total_amount - sales_order.net_amount) <= 0.01
        )
        INSERT INTO invoice_item (
            id, organization_id, invoice_id, sales_order_item_id, product_id,
            description, product_sku, quantity, unit_price, discount_amount,
            total_amount, created_at
        )
        SELECT
            gen_random_uuid(), ranked_invoice.organization_id,
            ranked_invoice.id, sales_order_item.id, sales_order_item.product_id,
            product.name, product.sku, sales_order_item.quantity,
            sales_order_item.unit_price, sales_order_item.discount_amount,
            sales_order_item.total_price, ranked_invoice.created_at
        FROM ranked_invoice
        JOIN sales_order_item
          ON sales_order_item.sales_order_id = ranked_invoice.sales_order_id
        JOIN product
          ON product.id = sales_order_item.product_id
         AND product.organization_id = ranked_invoice.organization_id
        WHERE ranked_invoice.position = 1;
        """
    )


def downgrade() -> None:
    op.drop_index("ix_invoice_item_order_item", table_name="invoice_item")
    op.drop_index("ix_invoice_item_org_invoice", table_name="invoice_item")
    op.drop_table("invoice_item")
