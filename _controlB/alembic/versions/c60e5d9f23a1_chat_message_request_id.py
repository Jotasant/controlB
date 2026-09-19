"""Idempotência dos pedidos de envio do Chat."""

import sqlalchemy as sa

from alembic import op

revision = "c60e5d9f23a1"
down_revision = "b59d4c8e12f0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("chat_message", sa.Column("client_request_id", sa.UUID(), nullable=True))
    op.create_unique_constraint(
        "uq_chat_message_request", "chat_message", ["organization_id", "client_request_id"]
    )


def downgrade():
    op.drop_constraint("uq_chat_message_request", "chat_message", type_="unique")
    op.drop_column("chat_message", "client_request_id")
