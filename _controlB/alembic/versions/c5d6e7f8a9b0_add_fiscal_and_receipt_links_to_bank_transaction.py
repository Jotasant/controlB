"""add fiscal and receipt links to bank transaction

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-09-01 12:50:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c5d6e7f8a9b0"
down_revision: str | Sequence[str] | None = "b4c5d6e7f8a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "bank_transaction",
        sa.Column("fiscal_document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fiscal_document.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column(
        "bank_transaction",
        sa.Column("payment_attachment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("payment_attachment.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column(
        "bank_transaction",
        sa.Column("receipt_url", sa.Text(), nullable=True),
    )
    op.add_column(
        "bank_transaction",
        sa.Column("receipt_filename", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("bank_transaction", "receipt_filename")
    op.drop_column("bank_transaction", "receipt_url")
    op.drop_column("bank_transaction", "payment_attachment_id")
    op.drop_column("bank_transaction", "fiscal_document_id")
