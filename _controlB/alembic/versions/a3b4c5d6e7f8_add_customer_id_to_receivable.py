"""add customer_id to receivable

Revision ID: a3b4c5d6e7f8
Revises: z1a2b3c4d5e6
Create Date: 2026-09-01 11:30:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a3b4c5d6e7f8"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "receivable",
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customer.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_receivable_customer_id", "receivable", ["customer_id"])


def downgrade() -> None:
    op.drop_index("ix_receivable_customer_id", table_name="receivable")
    op.drop_column("receivable", "customer_id")
