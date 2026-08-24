"""add commercial settings

Revision ID: r3s4t5u6v7w8
Revises: q2r3s4t5u6v7
Create Date: 2026-08-24 01:05:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "r3s4t5u6v7w8"
down_revision: str | Sequence[str] | None = "q2r3s4t5u6v7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "commercial_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "default_payment_terms",
            sa.String(length=100),
            server_default="30 DDL",
            nullable=False,
        ),
        sa.Column(
            "quote_validity_days",
            sa.Integer(),
            server_default="15",
            nullable=False,
        ),
        sa.Column(
            "maximum_discount_percent",
            sa.Numeric(precision=5, scale=2),
            server_default="100.00",
            nullable=False,
        ),
        sa.Column(
            "default_commission_percent",
            sa.Numeric(precision=5, scale=2),
            server_default="2.00",
            nullable=False,
        ),
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
            ["organization_id"],
            ["organization.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_commercial_settings_organization_id",
        "commercial_settings",
        ["organization_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_commercial_settings_organization_id",
        table_name="commercial_settings",
    )
    op.drop_table("commercial_settings")
