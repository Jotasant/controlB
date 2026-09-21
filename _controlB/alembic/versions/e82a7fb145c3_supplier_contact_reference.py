"""Vínculo opcional do fornecedor ao contato, sem unificar os cadastros."""

import sqlalchemy as sa

from alembic import op

revision = "e82a7fb145c3"
down_revision = "d71f6ea034b2"
branch_labels = depends_on = None


def upgrade():
    op.add_column("supplier", sa.Column("contact_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_supplier_contact", "supplier", "contact", ["contact_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_supplier_contact_id", "supplier", ["contact_id"])


def downgrade():
    op.drop_index("ix_supplier_contact_id", table_name="supplier")
    op.drop_constraint("fk_supplier_contact", "supplier", type_="foreignkey")
    op.drop_column("supplier", "contact_id")
