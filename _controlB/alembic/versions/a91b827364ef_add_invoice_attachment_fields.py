"""add_invoice_attachment_fields

Revision ID: a91b827364ef
Revises: f6819560f523
Create Date: 2026-08-16 11:18:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a91b827364ef'
down_revision: Union[str, Sequence[str], None] = 'e892c57a9110'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('stock_movement', sa.Column('invoice_attachment', sa.Text(), nullable=True))
    op.add_column('purchase_order', sa.Column('invoice_attachment', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('purchase_order', 'invoice_attachment')
    op.drop_column('stock_movement', 'invoice_attachment')
