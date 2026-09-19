"""allow standalone work orders

Revision ID: 8c1f4b72d9a0
Revises: 617db08d30b7
Create Date: 2026-09-18 12:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "8c1f4b72d9a0"
down_revision: str | Sequence[str] | None = "617db08d30b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "work_order",
        "project_id",
        existing_type=sa.UUID(),
        nullable=True,
    )


def downgrade() -> None:
    connection = op.get_bind()
    orphan_count = connection.execute(
        sa.text("SELECT COUNT(*) FROM work_order WHERE project_id IS NULL")
    ).scalar_one()
    if orphan_count:
        raise RuntimeError(
            "Não é possível tornar work_order.project_id obrigatório enquanto existirem ordens sem projeto."
        )

    op.alter_column(
        "work_order",
        "project_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
