"""Additive execution configuration; legacy records remain unversioned.

Before upgrade/downgrade take a pg_dump -Fc and verify pg_restore --list.
Downgrade removes ONLY this delivery's schema; restore backup to recover its data.
"""
from alembic import op
import sqlalchemy as sa

revision = "0415c6d7e8f9"
down_revision = "f304b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "execution_type_revision",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organization.id"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("type_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("workflow_snapshot", sa.JSON(), nullable=False),
        sa.Column("checklist_snapshot", sa.JSON(), nullable=False),
        sa.Column("published_by_id", sa.Uuid(), sa.ForeignKey("user.id", ondelete="SET NULL")),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "kind", "type_id", "version", name="uq_execution_type_version"),
    )
    for table in ("project_type", "work_order_type"):
        op.add_column(table, sa.Column("configuration", sa.JSON(), nullable=True))
        op.add_column(table, sa.Column("published_revision_id", sa.Uuid(), nullable=True))
        op.create_foreign_key(f"fk_{table}_revision", table, "execution_type_revision", ["published_revision_id"], ["id"], ondelete="RESTRICT")
    for table in ("project", "work_order"):
        op.add_column(table, sa.Column("type_revision_id", sa.Uuid(), nullable=True))
        op.create_foreign_key(f"fk_{table}_revision", table, "execution_type_revision", ["type_revision_id"], ["id"], ondelete="RESTRICT")
    op.add_column("checklist", sa.Column("project_id", sa.Uuid(), nullable=True))
    op.add_column("checklist", sa.Column("engine_key", sa.String(100), nullable=True))
    op.create_foreign_key("fk_checklist_project", "checklist", "project", ["project_id"], ["id"], ondelete="SET NULL")
    op.create_unique_constraint("uq_project_engine_checklist", "checklist", ["project_id", "engine_key"])
    op.create_unique_constraint("uq_order_engine_checklist", "checklist", ["work_order_id", "engine_key"])


def downgrade():
    op.drop_constraint("uq_order_engine_checklist", "checklist", type_="unique")
    op.drop_constraint("uq_project_engine_checklist", "checklist", type_="unique")
    op.drop_constraint("fk_checklist_project", "checklist", type_="foreignkey")
    op.drop_column("checklist", "engine_key")
    op.drop_column("checklist", "project_id")
    for table in ("project", "work_order"):
        op.drop_constraint(f"fk_{table}_revision", table, type_="foreignkey")
        op.drop_column(table, "type_revision_id")
    for table in ("project_type", "work_order_type"):
        op.drop_constraint(f"fk_{table}_revision", table, type_="foreignkey")
        op.drop_column(table, "published_revision_id")
        op.drop_column(table, "configuration")
    op.drop_table("execution_type_revision")
