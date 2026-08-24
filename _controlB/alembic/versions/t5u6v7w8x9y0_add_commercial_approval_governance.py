"""add commercial approval governance

Revision ID: t5u6v7w8x9y0
Revises: s4t5u6v7w8x9
Create Date: 2026-08-24 04:10:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "t5u6v7w8x9y0"
down_revision: str | Sequence[str] | None = "s4t5u6v7w8x9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table_name in ("sales_quote", "sales_order"):
        op.add_column(
            table_name,
            sa.Column(
                "commercial_approval_status",
                sa.String(length=30),
                server_default="NOT_REQUIRED",
                nullable=False,
            ),
        )
        op.create_index(
            f"ix_{table_name}_commercial_approval_status",
            table_name,
            ["commercial_approval_status"],
            unique=False,
        )

    op.add_column(
        "commercial_settings",
        sa.Column(
            "automatic_discount_limit_percent",
            sa.Numeric(precision=5, scale=2),
            server_default="5.00",
            nullable=False,
        ),
    )
    op.add_column(
        "commercial_settings",
        sa.Column(
            "minimum_margin_percent",
            sa.Numeric(precision=5, scale=2),
            server_default="0.00",
            nullable=False,
        ),
    )
    op.add_column(
        "commercial_settings",
        sa.Column(
            "maximum_payment_term_days_without_approval",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )

    op.create_table(
        "commercial_approval_request",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sales_quote_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sales_order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approval_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="PENDING", nullable=False),
        sa.Column("metric_value", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("threshold_value", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("request_reason", sa.Text(), nullable=False),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("requested_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decided_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "(sales_quote_id IS NOT NULL AND sales_order_id IS NULL) OR "
            "(sales_quote_id IS NULL AND sales_order_id IS NOT NULL)",
            name="ck_commercial_approval_single_document",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sales_quote_id"], ["sales_quote.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sales_order_id"], ["sales_order.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_id"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["decided_by_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sales_quote_id", "approval_type", name="uq_commercial_approval_quote_type"),
        sa.UniqueConstraint("sales_order_id", "approval_type", name="uq_commercial_approval_order_type"),
    )
    for column in ("organization_id", "sales_quote_id", "sales_order_id", "approval_type", "status"):
        op.create_index(
            f"ix_commercial_approval_request_{column}",
            "commercial_approval_request",
            [column],
            unique=False,
        )


def downgrade() -> None:
    for column in ("status", "approval_type", "sales_order_id", "sales_quote_id", "organization_id"):
        op.drop_index(
            f"ix_commercial_approval_request_{column}",
            table_name="commercial_approval_request",
        )
    op.drop_table("commercial_approval_request")
    op.drop_column("commercial_settings", "maximum_payment_term_days_without_approval")
    op.drop_column("commercial_settings", "minimum_margin_percent")
    op.drop_column("commercial_settings", "automatic_discount_limit_percent")
    for table_name in ("sales_order", "sales_quote"):
        op.drop_index(
            f"ix_{table_name}_commercial_approval_status", table_name=table_name
        )
        op.drop_column(table_name, "commercial_approval_status")
