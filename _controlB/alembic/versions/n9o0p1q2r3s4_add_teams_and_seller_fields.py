"""add teams and seller fields

Revision ID: n9o0p1q2r3s4
Revises: m8n9o0p1q2r3
Create Date: 2026-08-23 12:42:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "n9o0p1q2r3s4"
down_revision: str | Sequence[str] | None = "m8n9o0p1q2r3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Adiciona coluna is_seller na tabela user
    op.add_column(
        "user",
        sa.Column("is_seller", sa.Boolean(), server_default=sa.text("false"), nullable=False)
    )
    op.create_index("ix_user_is_seller", "user", ["is_seller"])

    # 2. Criação da tabela team
    op.create_table(
        "team",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=True),
        sa.Column("module_category", sa.String(length=50), server_default="SALES", nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("leader_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["leader_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_team_name", "team", ["name"])
    op.create_index("ix_team_module_category", "team", ["module_category"])
    op.create_index("ix_team_organization_id", "team", ["organization_id"])

    # 3. Criação da tabela associativa team_member
    op.create_table(
        "team_member",
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_in_team", sa.String(length=50), server_default="MEMBER", nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["team.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("team_id", "user_id")
    )


def downgrade() -> None:
    op.drop_table("team_member")
    op.drop_index("ix_team_organization_id", table_name="team")
    op.drop_index("ix_team_module_category", table_name="team")
    op.drop_index("ix_team_name", table_name="team")
    op.drop_table("team")
    op.drop_index("ix_user_is_seller", table_name="user")
    op.drop_column("user", "is_seller")
