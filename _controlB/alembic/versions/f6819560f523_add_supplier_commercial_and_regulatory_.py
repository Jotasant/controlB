"""add_supplier_commercial_and_regulatory_fields

Revision ID: f6819560f523
Revises: f54882fa6455
Create Date: 2026-08-15 23:34:23.746694

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6819560f523'
down_revision: Union[str, Sequence[str], None] = 'f54882fa6455'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('supplier', sa.Column('state_registration', sa.String(length=100), nullable=True))
    op.add_column('supplier', sa.Column('contact_name', sa.String(length=200), nullable=True))
    op.add_column('supplier', sa.Column('segments', sa.String(length=500), nullable=True))
    op.add_column('supplier', sa.Column('payment_terms', sa.String(length=200), nullable=True))
    op.add_column('supplier', sa.Column('min_order_amount', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False))
    op.add_column('supplier', sa.Column('anvisa_license', sa.String(length=200), nullable=True))
    op.add_column('supplier', sa.Column('notes', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('supplier', 'notes')
    op.drop_column('supplier', 'anvisa_license')
    op.drop_column('supplier', 'min_order_amount')
    op.drop_column('supplier', 'payment_terms')
    op.drop_column('supplier', 'segments')
    op.drop_column('supplier', 'contact_name')
    op.drop_column('supplier', 'state_registration')

