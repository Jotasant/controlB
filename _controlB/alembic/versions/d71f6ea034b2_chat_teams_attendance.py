"""Equipe, identidade do canal, atendimento e contatos WhatsApp."""
from alembic import op
import sqlalchemy as sa

revision = "d71f6ea034b2"
down_revision = "c60e5d9f23a1"
branch_labels = depends_on = None


def upgrade():
    op.create_table("contact_origin",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("organization_id", sa.UUID(), sa.ForeignKey("organization.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.UniqueConstraint("organization_id", "name", name="uq_contact_origin_name"))
    for column in [sa.Column("normalized_phone", sa.String(40)),
                   sa.Column("contact_origin_id", sa.UUID()),
                   sa.Column("first_contact_at", sa.DateTime(timezone=True)),
                   sa.Column("last_contact_at", sa.DateTime(timezone=True))]:
        op.add_column("contact", column)
    op.create_foreign_key("fk_contact_origin", "contact", "contact_origin", ["contact_origin_id"], ["id"], ondelete="SET NULL")
    op.create_unique_constraint("uq_contact_org_phone", "contact", ["organization_id", "normalized_phone"])
    for table in ("chat_connection", "chat_conversation", "chat_message"):
        op.add_column(table, sa.Column("team_id", sa.UUID()))
        op.add_column(table, sa.Column("instance_phone", sa.String(40)))
        op.create_foreign_key(f"fk_{table}_team", table, "team", ["team_id"], ["id"], ondelete="RESTRICT")
        op.create_index(f"ix_{table}_team_id", table, ["team_id"])
    for column in [sa.Column("provider_instance_id", sa.String(255)),
                   sa.Column("transcription_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
                   sa.Column("sync_checkpoint_at", sa.DateTime(timezone=True)),
                   sa.Column("sync_started_at", sa.DateTime(timezone=True)),
                   sa.Column("sync_page", sa.Integer(), nullable=False, server_default="1"),
                   sa.Column("recovery_pending", sa.Boolean(), nullable=False, server_default=sa.false())]:
        op.add_column("chat_connection", column)
    op.add_column("chat_conversation", sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("chat_conversation", sa.Column("closed_at", sa.DateTime(timezone=True)))
    op.add_column("chat_conversation", sa.Column("closed_by_id", sa.UUID()))
    op.create_foreign_key("fk_chat_closed_by", "chat_conversation", "user", ["closed_by_id"], ["id"], ondelete="SET NULL")
    op.execute("UPDATE chat_conversation SET is_archived = true, status = 'OPEN' WHERE status = 'ARCHIVED'")
    op.drop_constraint("ck_chat_conversation_status", "chat_conversation", type_="check")
    op.create_check_constraint("ck_chat_conversation_status", "chat_conversation", "status IN ('OPEN','CLOSED')")
    op.add_column("chat_message", sa.Column("transcription", sa.Text()))
    op.add_column("chat_message", sa.Column("transcription_status", sa.String(30), nullable=False, server_default="NOT_REQUESTED"))


def downgrade():
    op.drop_column("chat_message", "transcription_status")
    op.drop_column("chat_message", "transcription")
    op.drop_constraint("ck_chat_conversation_status", "chat_conversation", type_="check")
    op.create_check_constraint("ck_chat_conversation_status", "chat_conversation", "status IN ('OPEN','CLOSED','ARCHIVED')")
    op.execute("UPDATE chat_conversation SET status='ARCHIVED' WHERE is_archived")
    op.drop_constraint("fk_chat_closed_by", "chat_conversation", type_="foreignkey")
    for name in ("closed_by_id", "closed_at", "is_archived"):
        op.drop_column("chat_conversation", name)
    for name in ("provider_instance_id", "transcription_enabled", "sync_checkpoint_at", "sync_started_at", "sync_page", "recovery_pending"):
        op.drop_column("chat_connection", name)
    for table in ("chat_connection", "chat_conversation", "chat_message"):
        op.drop_index(f"ix_{table}_team_id", table_name=table)
        op.drop_constraint(f"fk_{table}_team", table, type_="foreignkey")
        op.drop_column(table, "team_id")
        op.drop_column(table, "instance_phone")
    op.drop_constraint("uq_contact_org_phone", "contact", type_="unique")
    op.drop_constraint("fk_contact_origin", "contact", type_="foreignkey")
    for name in ("normalized_phone", "contact_origin_id", "first_contact_at", "last_contact_at"):
        op.drop_column("contact", name)
    op.drop_table("contact_origin")
