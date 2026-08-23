"""add crm stages and lead customer id

Revision ID: m8n9o0p1q2r3
Revises: l7m8n9o0p1q2
Create Date: 2026-08-22 21:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "m8n9o0p1q2r3"
down_revision: str | Sequence[str] | None = "l7m8n9o0p1q2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Criação da tabela crm_stage
    op.create_table(
        "crm_stage",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("color", sa.String(length=20), server_default="#10b981", nullable=False),
        sa.Column("order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_won", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_lost", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_crm_stage_org_code")
    )
    op.create_index("ix_crm_stage_org_order", "crm_stage", ["organization_id", "order"])

    # 2. Adição de customer_id na tabela lead
    op.add_column("lead", sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_lead_customer_id",
        "lead",
        "customer",
        ["customer_id"],
        ["id"],
        ondelete="SET NULL"
    )
    op.create_index("ix_lead_customer_id", "lead", ["customer_id"])


def downgrade() -> None:
    op.drop_index("ix_lead_customer_id", table_name="lead")
    op.drop_constraint("fk_lead_customer_id", "lead", type_="foreignkey")
    op.drop_column("lead", "customer_id")
    op.drop_index("ix_crm_stage_org_order", table_name="crm_stage")
    op.drop_table("crm_stage")
