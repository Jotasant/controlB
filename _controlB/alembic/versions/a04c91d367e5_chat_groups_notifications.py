"""Group channels, participant identifiers and live notification timestamps."""

import sqlalchemy as sa

from alembic import op

revision = "a04c91d367e5"
down_revision = "f93b80c256d4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "chat_connection",
        sa.Column("groups_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "chat_conversation",
        sa.Column("is_group", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("chat_message", sa.Column("sender_external_id", sa.String(255), nullable=True))
    op.add_column("chat_message", sa.Column("notify_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_chat_message_notify_at", "chat_message", ["notify_at"])


def downgrade():
    op.drop_index("ix_chat_message_notify_at", table_name="chat_message")
    op.drop_column("chat_message", "notify_at")
    op.drop_column("chat_message", "sender_external_id")
    op.drop_column("chat_conversation", "is_group")
    op.drop_column("chat_connection", "groups_enabled")
