"""Protected contact names, media storage and local deletion markers."""

import sqlalchemy as sa

from alembic import op

revision = "b15da2e478f6"
down_revision = "a04c91d367e5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "contact",
        sa.Column("name_manually_set", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("chat_conversation", sa.Column("deleted_at", sa.DateTime(timezone=True)))
    op.add_column("chat_conversation", sa.Column("cleared_before", sa.DateTime(timezone=True)))
    op.add_column("chat_message", sa.Column("media_blob", sa.LargeBinary()))
    op.add_column("chat_message", sa.Column("media_sha256", sa.String(64)))
    op.add_column("chat_message", sa.Column("deleted_at", sa.DateTime(timezone=True)))
    op.add_column(
        "chat_message",
        sa.Column("deleted_by_id", sa.UUID(), sa.ForeignKey("user.id", ondelete="SET NULL")),
    )
    op.add_column("chat_message", sa.Column("revoke_status", sa.String(20)))


def downgrade():
    for field in ("revoke_status", "deleted_by_id", "deleted_at", "media_sha256", "media_blob"):
        op.drop_column("chat_message", field)
    op.drop_column("chat_conversation", "deleted_at")
    op.drop_column("chat_conversation", "cleared_before")
    op.drop_column("contact", "name_manually_set")
