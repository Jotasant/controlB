"""add CRM interaction lifecycle and audit fields

Revision ID: p1q2r3s4t5u6
Revises: o0p1q2r3s4t5
Create Date: 2026-08-23 23:10:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "p1q2r3s4t5u6"
down_revision: str | Sequence[str] | None = "o0p1q2r3s4t5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "customer_interaction",
        sa.Column("status", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "customer_interaction",
        sa.Column("responsible_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "customer_interaction",
        sa.Column("updated_by_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "customer_interaction",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_foreign_key(
        "fk_customer_interaction_responsible_id_user",
        "customer_interaction",
        "user",
        ["responsible_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_customer_interaction_updated_by_id_user",
        "customer_interaction",
        "user",
        ["updated_by_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.execute(
        """
        UPDATE customer_interaction
        SET status = CASE
            WHEN interaction_type = 'NOTE' THEN NULL
            WHEN interaction_date > now() THEN 'SCHEDULED'
            ELSE 'COMPLETED'
        END
        """
    )
    op.create_check_constraint(
        "ck_customer_interaction_lifecycle",
        "customer_interaction",
        "(interaction_type = 'NOTE' AND status IS NULL) OR "
        "(interaction_type <> 'NOTE' AND status IN ('SCHEDULED', 'COMPLETED', 'CANCELLED'))",
    )
    op.create_index(
        "ix_customer_interaction_org_status",
        "customer_interaction",
        ["organization_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_customer_interaction_org_status",
        table_name="customer_interaction",
    )
    op.drop_constraint(
        "ck_customer_interaction_lifecycle",
        "customer_interaction",
        type_="check",
    )
    op.drop_constraint(
        "fk_customer_interaction_updated_by_id_user",
        "customer_interaction",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_customer_interaction_responsible_id_user",
        "customer_interaction",
        type_="foreignkey",
    )
    op.drop_column("customer_interaction", "updated_at")
    op.drop_column("customer_interaction", "updated_by_id")
    op.drop_column("customer_interaction", "responsible_id")
    op.drop_column("customer_interaction", "status")
