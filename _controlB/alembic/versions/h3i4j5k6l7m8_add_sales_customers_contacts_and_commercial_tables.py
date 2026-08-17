"""add_sales_customers_contacts_and_commercial_tables

Revision ID: h3i4j5k6l7m8
Revises: g2h3i4j5k6l7
Create Date: 2026-08-17 13:25:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'h3i4j5k6l7m8'
down_revision: Union[str, Sequence[str], None] = 'g2h3i4j5k6l7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Tabela CONTACT (Módulo Identity)
    op.create_table(
        'contact',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organization.id', ondelete='CASCADE'), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('mobile', sa.String(50), nullable=True),
        sa.Column('document', sa.String(30), nullable=True),
        sa.Column('position', sa.String(100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False)
    )
    op.create_index('ix_contact_organization_id', 'contact', ['organization_id'])
    op.create_index('ix_contact_full_name', 'contact', ['full_name'])
    op.create_index('ix_contact_email', 'contact', ['email'])

    # 2. Tabela CUSTOMER (Módulo Sales)
    op.create_table(
        'customer',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organization.id', ondelete='CASCADE'), nullable=False),
        sa.Column('contact_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('contact.id', ondelete='SET NULL'), nullable=True),
        sa.Column('person_type', sa.String(2), server_default='PJ', nullable=False),
        sa.Column('document', sa.String(30), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('trade_name', sa.String(255), nullable=True),
        sa.Column('state_registration', sa.String(50), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('address_street', sa.String(255), nullable=True),
        sa.Column('address_number', sa.String(50), nullable=True),
        sa.Column('address_neighborhood', sa.String(100), nullable=True),
        sa.Column('address_city', sa.String(100), nullable=True),
        sa.Column('address_state', sa.String(2), nullable=True),
        sa.Column('address_zip_code', sa.String(20), nullable=True),
        sa.Column('credit_limit', sa.Numeric(15, 2), server_default='0.00', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('organization_id', 'document', name='uq_customer_org_document')
    )
    op.create_index('ix_customer_organization_id', 'customer', ['organization_id'])
    op.create_index('ix_customer_document', 'customer', ['document'])
    op.create_index('ix_customer_name', 'customer', ['name'])

    # 3. Adiciona customer_id e payment_terms nas tabelas de vendas existentes
    op.add_column('sales_quote', sa.Column('customer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('customer.id', ondelete='SET NULL'), nullable=True))
    op.add_column('sales_quote', sa.Column('payment_terms', sa.String(100), nullable=True))

    op.add_column('sales_order', sa.Column('customer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('customer.id', ondelete='SET NULL'), nullable=True))
    op.add_column('sales_order', sa.Column('sales_quote_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sales_quote.id', ondelete='SET NULL'), nullable=True))

    op.add_column('pos_sale', sa.Column('customer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('customer.id', ondelete='SET NULL'), nullable=True))

    # 4. Tabela POS_CASH_MOVEMENT (Sangria e Suprimento)
    op.create_table(
        'pos_cash_movement',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organization.id', ondelete='CASCADE'), nullable=False),
        sa.Column('pos_session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pos_session.id', ondelete='CASCADE'), nullable=False),
        sa.Column('movement_type', sa.String(20), nullable=False),
        sa.Column('amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('reason', sa.String(255), nullable=False),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False)
    )
    op.create_index('ix_pos_cash_movement_session', 'pos_cash_movement', ['pos_session_id'])

    # 5. Tabela SALES_GOAL (Metas Comerciais)
    op.create_table(
        'sales_goal',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organization.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False),
        sa.Column('seller_name', sa.String(255), nullable=True),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('target_amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('commission_percent', sa.Numeric(5, 2), server_default='0.00', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('organization_id', 'user_id', 'month', 'year', name='uq_sales_goal_org_user_month_year')
    )

    # 6. Tabelas PRICE_TABLE & PRICE_TABLE_ITEM
    op.create_table(
        'price_table',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organization.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_default', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False)
    )

    op.create_table(
        'price_table_item',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('price_table_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('price_table.id', ondelete='CASCADE'), nullable=False),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('product.id', ondelete='CASCADE'), nullable=False),
        sa.Column('price', sa.Numeric(15, 2), nullable=False),
        sa.Column('discount_percent', sa.Numeric(5, 2), server_default='0.00', nullable=False)
    )

    # 7. Tabelas SALES_RETURN & SALES_RETURN_ITEM (Pós-venda)
    op.create_table(
        'sales_return',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organization.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sales_order_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sales_order.id', ondelete='SET NULL'), nullable=True),
        sa.Column('pos_sale_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pos_sale.id', ondelete='SET NULL'), nullable=True),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('customer.id', ondelete='SET NULL'), nullable=True),
        sa.Column('customer_name', sa.String(255), nullable=False),
        sa.Column('return_type', sa.String(30), server_default='DEVOLUCAO', nullable=False),
        sa.Column('status', sa.String(30), server_default='COMPLETED', nullable=False),
        sa.Column('total_amount', sa.Numeric(15, 2), server_default='0.00', nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('restock_items', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False)
    )

    op.create_table(
        'sales_return_item',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('sales_return_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sales_return.id', ondelete='CASCADE'), nullable=False),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('product.id', ondelete='CASCADE'), nullable=False),
        sa.Column('quantity', sa.Numeric(15, 4), nullable=False),
        sa.Column('unit_price', sa.Numeric(15, 2), nullable=False),
        sa.Column('total_price', sa.Numeric(15, 2), nullable=False),
        sa.Column('condition', sa.String(20), server_default='GOOD', nullable=False)
    )


def downgrade() -> None:
    op.drop_table('sales_return_item')
    op.drop_table('sales_return')
    op.drop_table('price_table_item')
    op.drop_table('price_table')
    op.drop_table('sales_goal')
    op.drop_table('pos_cash_movement')

    op.drop_column('pos_sale', 'customer_id')
    op.drop_column('sales_order', 'sales_quote_id')
    op.drop_column('sales_order', 'customer_id')
    op.drop_column('sales_quote', 'payment_terms')
    op.drop_column('sales_quote', 'customer_id')

    op.drop_table('customer')
    op.drop_table('contact')
