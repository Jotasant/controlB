"""add_crm_opportunity_and_sales_links

Revision ID: i4j5k6l7m8n9
Revises: h3i4j5k6l7m8
Create Date: 2026-08-17 14:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'i4j5k6l7m8n9'
down_revision: Union[str, Sequence[str], None] = 'h3i4j5k6l7m8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Adiciona customer_id e contact_id na tabela OPPORTUNITY (Módulo CRM)
    op.add_column(
        'opportunity',
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('customer.id', ondelete='SET NULL'), nullable=True)
    )
    op.add_column(
        'opportunity',
        sa.Column('contact_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('contact.id', ondelete='SET NULL'), nullable=True)
    )
    op.create_index('ix_opportunity_customer_id', 'opportunity', ['customer_id'])

    # 2. Adiciona opportunity_id na tabela SALES_QUOTE (Módulo Sales)
    op.add_column(
        'sales_quote',
        sa.Column('opportunity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('opportunity.id', ondelete='SET NULL'), nullable=True)
    )
    op.create_index('ix_sales_quote_opportunity_id', 'sales_quote', ['opportunity_id'])

    # 3. Adiciona opportunity_id na tabela SALES_ORDER (Módulo Sales)
    op.add_column(
        'sales_order',
        sa.Column('opportunity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('opportunity.id', ondelete='SET NULL'), nullable=True)
    )
    op.create_index('ix_sales_order_opportunity_id', 'sales_order', ['opportunity_id'])


def downgrade() -> None:
    op.drop_index('ix_sales_order_opportunity_id', table_name='sales_order')
    op.drop_column('sales_order', 'opportunity_id')

    op.drop_index('ix_sales_quote_opportunity_id', table_name='sales_quote')
    op.drop_column('sales_quote', 'opportunity_id')

    op.drop_index('ix_opportunity_customer_id', table_name='opportunity')
    op.drop_column('opportunity', 'contact_id')
    op.drop_column('opportunity', 'customer_id')
