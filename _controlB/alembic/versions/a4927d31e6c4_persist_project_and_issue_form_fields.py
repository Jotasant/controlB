"""persist project and issue form fields

Revision ID: a4927d31e6c4
Revises: 8c1f4b72d9a0
Create Date: 2026-09-18 13:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a4927d31e6c4"
down_revision: str | Sequence[str] | None = "8c1f4b72d9a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("project", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column(
        "project",
        sa.Column("is_billable", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "issue",
        sa.Column("impact_cost", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
    )
    op.add_column(
        "issue",
        sa.Column("impact_days", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("issue", "impact_days")
    op.drop_column("issue", "impact_cost")
    op.drop_column("project", "is_billable")
    op.drop_column("project", "notes")
