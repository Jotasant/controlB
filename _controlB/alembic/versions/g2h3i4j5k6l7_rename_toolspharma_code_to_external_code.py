"""rename_toolspharma_code_to_external_code

Revision ID: g2h3i4j5k6l7
Revises: f1a2b3c4d5e6
Create Date: 2026-08-17 11:42:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g2h3i4j5k6l7'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('product', 'toolspharma_code', new_column_name='external_code')
    op.drop_index('ix_product_toolspharma_code', table_name='product')
    op.create_index(op.f('ix_product_external_code'), 'product', ['external_code'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_product_external_code'), table_name='product')
    op.alter_column('product', 'external_code', new_column_name='toolspharma_code')
    op.create_index('ix_product_toolspharma_code', 'product', ['toolspharma_code'], unique=False)
