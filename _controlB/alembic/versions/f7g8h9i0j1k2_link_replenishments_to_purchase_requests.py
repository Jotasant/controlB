"""link replenishments to formal purchase requests

Revision ID: f7g8h9i0j1k2
Revises: e6f7g8h9i0j1
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f7g8h9i0j1k2"
down_revision: str | Sequence[str] | None = "e6f7g8h9i0j1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_inventory_replenishment_status",
        "inventory_replenishment",
        type_="check",
    )
    op.create_check_constraint(
        "ck_inventory_replenishment_status",
        "inventory_replenishment",
        "status IN ('OPEN', 'REQUESTED', 'ORDERED', 'CANCELLED')",
    )
    op.add_column(
        "purchase_request",
        sa.Column(
            "replenishment_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_purchase_request_replenishment_org",
        "purchase_request",
        "inventory_replenishment",
        ["replenishment_id", "organization_id"],
        ["id", "organization_id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_purchase_request_replenishment",
        "purchase_request",
        ["replenishment_id"],
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE inventory_replenishment
        SET status = 'OPEN'
        WHERE status = 'REQUESTED';
        """
    )
    op.drop_constraint(
        "uq_purchase_request_replenishment",
        "purchase_request",
        type_="unique",
    )
    op.drop_constraint(
        "fk_purchase_request_replenishment_org",
        "purchase_request",
        type_="foreignkey",
    )
    op.drop_column("purchase_request", "replenishment_id")
    op.drop_constraint(
        "ck_inventory_replenishment_status",
        "inventory_replenishment",
        type_="check",
    )
    op.create_check_constraint(
        "ck_inventory_replenishment_status",
        "inventory_replenishment",
        "status IN ('OPEN', 'ORDERED', 'CANCELLED')",
    )
