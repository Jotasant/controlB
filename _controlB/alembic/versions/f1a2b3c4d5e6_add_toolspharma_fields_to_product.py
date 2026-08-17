"""add_toolspharma_fields_to_product

Revision ID: f1a2b3c4d5e6
Revises: e4f5g6h7i8j9
Create Date: 2026-08-17 11:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e4f5g6h7i8j9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('product', sa.Column('cost_price', sa.Numeric(12, 4), server_default='0.0000', nullable=False))
    op.add_column('product', sa.Column('sale_price', sa.Numeric(12, 4), server_default='0.0000', nullable=False))
    op.add_column('product', sa.Column('toolspharma_code', sa.String(100), nullable=True))
    op.create_index(op.f('ix_product_toolspharma_code'), 'product', ['toolspharma_code'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_product_toolspharma_code'), table_name='product')
    op.drop_column('product', 'toolspharma_code')
    op.drop_column('product', 'sale_price')
    op.drop_column('product', 'cost_price')
