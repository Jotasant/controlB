"""CRM, Sales and Chat unified origins, customer contacts and enrichment.

Revision ID: d1e2f3a4b5c6
Revises: c26eb3f589a7
Create Date: 2026-09-20 13:48:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "d1e2f3a4b5c6"
down_revision = "c26eb3f589a7"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Enriquecimento da tabela contact_origin
    op.add_column("contact_origin", sa.Column("description", sa.String(255), nullable=True))
    op.add_column("contact_origin", sa.Column("channel_type", sa.String(50), nullable=False, server_default="OTHER"))
    op.add_column("contact_origin", sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("contact_origin", sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("contact_origin", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))

    # 2. Enriquecimento da tabela lead e chave estrangeira para contact_origin
    op.add_column("lead", sa.Column("contact_origin_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_lead_contact_origin_id",
        "lead",
        "contact_origin",
        ["contact_origin_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_lead_contact_origin_id", "lead", ["contact_origin_id"])
    op.add_column("lead", sa.Column("position", sa.String(100), nullable=True))
    op.add_column("lead", sa.Column("segment", sa.String(100), nullable=True))
    op.add_column("lead", sa.Column("address_city", sa.String(100), nullable=True))
    op.add_column("lead", sa.Column("address_state", sa.String(10), nullable=True))
    op.add_column("lead", sa.Column("annual_revenue", sa.Numeric(15, 2), nullable=True))
    op.add_column("lead", sa.Column("secondary_phone", sa.String(50), nullable=True))

    # 3. Enriquecimento da tabela customer
    op.add_column("customer", sa.Column("segment", sa.String(100), nullable=True))
    op.add_column("customer", sa.Column("website", sa.String(255), nullable=True))
    op.add_column("customer", sa.Column("secondary_phone", sa.String(50), nullable=True))
    op.add_column("customer", sa.Column("contact_role", sa.String(100), nullable=True))


def downgrade():
    # 3. Reverter customer
    op.drop_column("customer", "contact_role")
    op.drop_column("customer", "secondary_phone")
    op.drop_column("customer", "website")
    op.drop_column("customer", "segment")

    # 2. Reverter lead
    op.drop_column("lead", "secondary_phone")
    op.drop_column("lead", "annual_revenue")
    op.drop_column("lead", "address_state")
    op.drop_column("lead", "address_city")
    op.drop_column("lead", "segment")
    op.drop_column("lead", "position")
    op.drop_index("ix_lead_contact_origin_id", table_name="lead")
    op.drop_constraint("fk_lead_contact_origin_id", "lead", type_="foreignkey")
    op.drop_column("lead", "contact_origin_id")

    # 1. Reverter contact_origin
    op.drop_column("contact_origin", "updated_at")
    op.drop_column("contact_origin", "created_at")
    op.drop_column("contact_origin", "is_active")
    op.drop_column("contact_origin", "channel_type")
    op.drop_column("contact_origin", "description")
