"""add stock reservations

Revision ID: l7m8n9o0p1q2
Revises: k6l7m8n9o0p1
Create Date: 2026-08-17 21:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "l7m8n9o0p1q2"
down_revision: str | Sequence[str] | None = "k6l7m8n9o0p1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # As unicidades compostas são criadas antes das FKs que também validam tenant.
    op.create_unique_constraint("uq_product_id_org", "product", ["id", "organization_id"])
    op.create_unique_constraint(
        "uq_sales_order_id_org", "sales_order", ["id", "organization_id"]
    )

    op.create_table(
        "stock_reservation",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sales_order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reservation_number", sa.String(length=100), nullable=False),
        sa.Column(
            "status", sa.String(length=20), server_default="RESERVED", nullable=False
        ),
        sa.Column("status_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("released_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('RESERVED', 'RELEASED')",
            name="ck_stock_reservation_status",
        ),
        sa.CheckConstraint(
            "status_version > 0", name="ck_stock_reservation_version_positive"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["user.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["released_by_id"], ["user.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["sales_order_id", "organization_id"],
            ["sales_order.id", "sales_order.organization_id"],
            name="fk_stock_reservation_sales_order_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["business_document.id", "business_document.organization_id"],
            name="fk_stock_reservation_document_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "sales_order_id", name="uq_stock_reservation_sales_order"
        ),
        sa.UniqueConstraint("document_id", name="uq_stock_reservation_document"),
        sa.UniqueConstraint(
            "organization_id",
            "reservation_number",
            name="uq_stock_reservation_number_org",
        ),
        sa.UniqueConstraint(
            "id", "organization_id", name="uq_stock_reservation_id_org"
        ),
    )
    op.create_index(
        "ix_stock_reservation_org_status",
        "stock_reservation",
        ["organization_id", "status"],
        unique=False,
    )

    op.create_table(
        "stock_reservation_item",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reservation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "quantity > 0", name="ck_stock_reservation_item_quantity_positive"
        ),
        sa.ForeignKeyConstraint(
            ["reservation_id", "organization_id"],
            ["stock_reservation.id", "stock_reservation.organization_id"],
            name="fk_stock_reservation_item_reservation_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id", "organization_id"],
            ["product.id", "product.organization_id"],
            name="fk_stock_reservation_item_product_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "reservation_id",
            "product_id",
            name="uq_stock_reservation_item_product",
        ),
    )
    op.create_index(
        "ix_stock_reservation_item_product",
        "stock_reservation_item",
        ["organization_id", "product_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_stock_reservation_item_product", table_name="stock_reservation_item"
    )
    op.drop_table("stock_reservation_item")
    op.drop_index("ix_stock_reservation_org_status", table_name="stock_reservation")
    op.drop_table("stock_reservation")
    op.drop_constraint("uq_sales_order_id_org", "sales_order", type_="unique")
    op.drop_constraint("uq_product_id_org", "product", type_="unique")
