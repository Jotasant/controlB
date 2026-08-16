"""add_current_stock_and_stock_movement_table

Revision ID: e892c57a9110
Revises: f6819560f523
Create Date: 2026-08-16 00:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e892c57a9110'
down_revision: Union[str, Sequence[str], None] = 'f6819560f523'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('product', sa.Column('current_stock', sa.Numeric(precision=12, scale=4), server_default='0.0000', nullable=False))
    
    op.create_table(
        'stock_movement',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organization.id', ondelete='CASCADE'), nullable=False),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('product.id', ondelete='CASCADE'), nullable=False),
        sa.Column('movement_type', sa.String(length=50), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('unit_cost', sa.Numeric(precision=12, scale=4), server_default='0.0000', nullable=False),
        sa.Column('balance_after', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('reference_doc', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False)
    )
    op.create_index('ix_stock_movement_movement_type', 'stock_movement', ['movement_type'], unique=False)
    op.create_index('ix_stock_movement_product_id', 'stock_movement', ['product_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_stock_movement_product_id', table_name='stock_movement')
    op.drop_index('ix_stock_movement_movement_type', table_name='stock_movement')
    op.drop_table('stock_movement')
    op.drop_column('product', 'current_stock')
