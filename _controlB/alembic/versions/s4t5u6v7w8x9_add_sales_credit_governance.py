"""add sales credit governance

Revision ID: s4t5u6v7w8x9
Revises: r3s4t5u6v7w8
Create Date: 2026-08-24 03:10:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "s4t5u6v7w8x9"
down_revision: str | Sequence[str] | None = "r3s4t5u6v7w8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sales_order",
        sa.Column(
            "credit_status",
            sa.String(length=30),
            server_default="NOT_REQUIRED",
            nullable=False,
        ),
    )
    op.add_column(
        "sales_order",
        sa.Column(
            "credit_limit_snapshot",
            sa.Numeric(precision=14, scale=2),
            server_default="0.00",
            nullable=False,
        ),
    )
    op.add_column(
        "sales_order",
        sa.Column(
            "credit_exposure_snapshot",
            sa.Numeric(precision=14, scale=2),
            server_default="0.00",
            nullable=False,
        ),
    )
    op.add_column(
        "sales_order",
        sa.Column(
            "credit_excess_amount",
            sa.Numeric(precision=14, scale=2),
            server_default="0.00",
            nullable=False,
        ),
    )
    op.create_index(
        "ix_sales_order_credit_status",
        "sales_order",
        ["credit_status"],
        unique=False,
    )

    op.create_table(
        "credit_approval_request",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sales_order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="PENDING", nullable=False),
        sa.Column("request_reason", sa.Text(), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("credit_limit", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("exposure_before_order", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("order_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("excess_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("requested_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decided_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["sales_order_id"], ["sales_order.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customer.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_id"], ["user.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_id"], ["user.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sales_order_id", name="uq_credit_approval_sales_order"),
    )
    op.create_index(
        "ix_credit_approval_request_organization_id",
        "credit_approval_request",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_credit_approval_request_customer_id",
        "credit_approval_request",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        "ix_credit_approval_request_status",
        "credit_approval_request",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_credit_approval_request_status", table_name="credit_approval_request"
    )
    op.drop_index(
        "ix_credit_approval_request_customer_id", table_name="credit_approval_request"
    )
    op.drop_index(
        "ix_credit_approval_request_organization_id",
        table_name="credit_approval_request",
    )
    op.drop_table("credit_approval_request")
    op.drop_index("ix_sales_order_credit_status", table_name="sales_order")
    op.drop_column("sales_order", "credit_excess_amount")
    op.drop_column("sales_order", "credit_exposure_snapshot")
    op.drop_column("sales_order", "credit_limit_snapshot")
    op.drop_column("sales_order", "credit_status")
