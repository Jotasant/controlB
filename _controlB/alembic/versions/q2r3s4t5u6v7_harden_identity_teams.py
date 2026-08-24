"""harden identity teams

Revision ID: q2r3s4t5u6v7
Revises: p1q2r3s4t5u6
Create Date: 2026-08-24 00:15:00.000000

"""
from collections.abc import Sequence

from alembic import op

revision: str = "q2r3s4t5u6v7"
down_revision: str | Sequence[str] | None = "p1q2r3s4t5u6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_team_organization_category_name",
        "team",
        ["organization_id", "module_category", "name"],
    )
    op.create_unique_constraint(
        "uq_team_organization_category_code",
        "team",
        ["organization_id", "module_category", "code"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_team_organization_category_code",
        "team",
        type_="unique",
    )
    op.drop_constraint(
        "uq_team_organization_category_name",
        "team",
        type_="unique",
    )
