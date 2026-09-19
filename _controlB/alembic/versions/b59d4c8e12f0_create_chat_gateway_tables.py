"""create chat gateway tables

Revision ID: b59d4c8e12f0
Revises: a4927d31e6c4
Create Date: 2026-09-19 10:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b59d4c8e12f0"
down_revision: str | Sequence[str] | None = "a4927d31e6c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_connection",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=False),
        sa.Column("external_instance_id", sa.String(length=200), nullable=False),
        sa.Column("credentials_ciphertext", sa.Text(), nullable=False),
        sa.Column("credentials_hint", sa.String(length=50), nullable=True),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('DISCONNECTED', 'CONNECTING', 'CONNECTED', 'ERROR')",
            name="ck_chat_connection_status",
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", name="uq_chat_connection_id_org"),
        sa.UniqueConstraint(
            "organization_id",
            "provider",
            "external_instance_id",
            name="uq_chat_connection_org_provider_instance",
        ),
    )
    op.create_index(
        "ix_chat_connection_org_active",
        "chat_connection",
        ["organization_id", "is_active"],
        unique=False,
    )

    op.create_table(
        "chat_conversation",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("connection_id", sa.UUID(), nullable=False),
        sa.Column("external_chat_id", sa.String(length=255), nullable=False),
        sa.Column("remote_phone", sa.String(length=40), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.String(length=1000), nullable=True),
        sa.Column("contact_id", sa.UUID(), nullable=True),
        sa.Column("customer_id", sa.UUID(), nullable=True),
        sa.Column("assigned_user_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("unread_count", sa.Integer(), nullable=False),
        sa.Column("last_message_preview", sa.String(length=500), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('OPEN', 'CLOSED', 'ARCHIVED')",
            name="ck_chat_conversation_status",
        ),
        sa.CheckConstraint("unread_count >= 0", name="ck_chat_conversation_unread"),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["contact_id"], ["contact.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["customer_id"], ["customer.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["connection_id", "organization_id"],
            ["chat_connection.id", "chat_connection.organization_id"],
            ondelete="CASCADE",
            name="fk_chat_conversation_connection_org",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", name="uq_chat_conversation_id_org"),
        sa.UniqueConstraint(
            "connection_id", "external_chat_id", name="uq_chat_conversation_external"
        ),
    )
    op.create_index(
        "ix_chat_conversation_org_phone",
        "chat_conversation",
        ["organization_id", "remote_phone"],
        unique=False,
    )
    op.create_index(
        "ix_chat_conversation_org_status_last",
        "chat_conversation",
        ["organization_id", "status", "last_message_at"],
        unique=False,
    )

    op.create_table(
        "chat_conversation_link",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("business_document_id", sa.UUID(), nullable=False),
        sa.Column("link_type", sa.String(length=20), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("created_by_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("link_type IN ('ORIGIN', 'RELATED')", name="ck_chat_link_type"),
        sa.ForeignKeyConstraint(
            ["business_document_id", "organization_id"],
            ["business_document.id", "business_document.organization_id"],
            ondelete="CASCADE",
            name="fk_chat_link_document_org",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id", "organization_id"],
            ["chat_conversation.id", "chat_conversation.organization_id"],
            ondelete="CASCADE",
            name="fk_chat_link_conversation_org",
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id",
            "business_document_id",
            name="uq_chat_link_conversation_document",
        ),
    )
    op.create_index(
        "ix_chat_link_document",
        "chat_conversation_link",
        ["business_document_id"],
        unique=False,
    )

    op.create_table(
        "chat_message",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("external_message_id", sa.String(length=255), nullable=True),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.Column("message_type", sa.String(length=30), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("media_url", sa.String(length=2000), nullable=True),
        sa.Column("media_mime_type", sa.String(length=150), nullable=True),
        sa.Column("media_filename", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("sender_name", sa.String(length=255), nullable=True),
        sa.Column("sender_phone", sa.String(length=40), nullable=True),
        sa.Column("reply_to_message_id", sa.UUID(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("provider_payload", sa.JSON(), nullable=False),
        sa.Column("created_by_id", sa.UUID(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "direction IN ('INBOUND', 'OUTBOUND')", name="ck_chat_message_direction"
        ),
        sa.CheckConstraint(
            "status IN ('RECEIVED', 'PENDING', 'SENT', 'DELIVERED', 'READ', 'FAILED')",
            name="ck_chat_message_status",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id", "organization_id"],
            ["chat_conversation.id", "chat_conversation.organization_id"],
            ondelete="CASCADE",
            name="fk_chat_message_conversation_org",
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reply_to_message_id"], ["chat_message.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id", "external_message_id", name="uq_chat_message_external"
        ),
    )
    op.create_index(
        "ix_chat_message_conversation_time",
        "chat_message",
        ["conversation_id", "occurred_at"],
        unique=False,
    )

    op.create_table(
        "chat_webhook_event",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("connection_id", sa.UUID(), nullable=False),
        sa.Column("event_key", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PROCESSED', 'IGNORED', 'FAILED')",
            name="ck_chat_webhook_status",
        ),
        sa.ForeignKeyConstraint(
            ["connection_id", "organization_id"],
            ["chat_connection.id", "chat_connection.organization_id"],
            ondelete="CASCADE",
            name="fk_chat_webhook_connection_org",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("connection_id", "event_key", name="uq_chat_webhook_event_key"),
    )
    op.create_index(
        "ix_chat_webhook_status_created",
        "chat_webhook_event",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_chat_webhook_status_created", table_name="chat_webhook_event")
    op.drop_table("chat_webhook_event")
    op.drop_index("ix_chat_message_conversation_time", table_name="chat_message")
    op.drop_table("chat_message")
    op.drop_index("ix_chat_link_document", table_name="chat_conversation_link")
    op.drop_table("chat_conversation_link")
    op.drop_index("ix_chat_conversation_org_status_last", table_name="chat_conversation")
    op.drop_index("ix_chat_conversation_org_phone", table_name="chat_conversation")
    op.drop_table("chat_conversation")
    op.drop_index("ix_chat_connection_org_active", table_name="chat_connection")
    op.drop_table("chat_connection")
