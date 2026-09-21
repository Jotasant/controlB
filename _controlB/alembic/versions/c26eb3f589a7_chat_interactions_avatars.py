"""Profile pictures, quoted replies and idempotent reactions."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c26eb3f589a7"
down_revision = "b15da2e478f6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("chat_conversation", sa.Column("avatar_blob", sa.LargeBinary()))
    op.add_column("chat_conversation", sa.Column("avatar_mime", sa.String(100)))
    op.add_column("chat_conversation", sa.Column("avatar_checked_at", sa.DateTime(timezone=True)))
    op.add_column("chat_message", sa.Column("reply_snapshot", sa.JSON()))
    op.add_column("chat_message", sa.Column("reaction_data", sa.JSON(), nullable=False, server_default="{}"))
    op.create_table(
        "chat_reaction_request",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organization.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chat_message.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id", ondelete="SET NULL")),
        sa.Column("emoji", sa.String(32), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_chat_reaction_request_message_id", "chat_reaction_request", ["message_id"])


def downgrade():
    op.drop_table("chat_reaction_request")
    op.drop_column("chat_message", "reaction_data")
    op.drop_column("chat_message", "reply_snapshot")
    for column in ("avatar_checked_at", "avatar_mime", "avatar_blob"):
        op.drop_column("chat_conversation", column)
