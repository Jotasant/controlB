'''bootstrap_crm_and_sales_core_tables

Revision ID: h2i3j4k5l6m7
Revises: g2h3i4j5k6l7
Create Date: 2026-08-17 15:00:00.000000

This compatibility bootstrap closes a historical gap in the Alembic chain:
CRM, Sales and POS core tables already existed in legacy databases, but had no
revision that created them for a clean installation. Every table is therefore
created only when absent. Tables created here receive an ownership marker so a
downgrade never removes a table adopted from a legacy installation.
'''

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.schema import SchemaItem

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'h2i3j4k5l6m7'
down_revision: str | Sequence[str] | None = 'g2h3i4j5k6l7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_OWNER_MARKER = 'controlb.alembic.owner=h2i3j4k5l6m7'


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _mark_created(table_name: str) -> None:
    # All identifiers and the marker are migration-owned constants.
    op.execute(
        f'COMMENT ON TABLE {chr(34)}{table_name}{chr(34)} '
        f'IS {chr(39)}{_OWNER_MARKER}{chr(39)}'
    )


def _create_table(table_name: str, *columns: SchemaItem) -> bool:
    if _has_table(table_name):
        return False
    op.create_table(table_name, *columns)
    _mark_created(table_name)
    return True


def _was_created_here(table_name: str) -> bool:
    if not _has_table(table_name):
        return False
    comment = op.get_bind().execute(
        sa.text('SELECT obj_description(to_regclass(:table_name), '
                f'{chr(39)}pg_class{chr(39)})'),
        {'table_name': table_name},
    ).scalar_one_or_none()
    return comment == _OWNER_MARKER


def _drop_if_created_here(table_name: str) -> None:
    if _was_created_here(table_name):
        op.drop_table(table_name)


def upgrade() -> None:
    # Base CRM: later revisions add Customer/Contact links to opportunity.
    if _create_table(
        'lead',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'organization_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('organization.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('company_name', sa.String(255), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('source', sa.String(100), nullable=False),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column(
            'assigned_to_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('user.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    ):
        op.create_index('ix_lead_status', 'lead', ['status'])

    if _create_table(
        'opportunity',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'organization_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('organization.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'lead_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('lead.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('customer_name', sa.String(255), nullable=False),
        sa.Column('estimated_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('probability_percent', sa.Integer(), nullable=False),
        sa.Column('expected_closing_date', sa.Date(), nullable=True),
        sa.Column('stage', sa.String(50), nullable=False),
        sa.Column('loss_reason', sa.String(255), nullable=True),
        sa.Column(
            'assigned_to_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('user.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    ):
        op.create_index('ix_opportunity_stage', 'opportunity', ['stage'])

    _create_table(
        'customer_interaction',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'organization_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('organization.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'lead_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('lead.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column(
            'opportunity_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('opportunity.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('interaction_type', sa.String(50), nullable=False),
        sa.Column('summary', sa.String(255), nullable=False),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('interaction_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            'created_by_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('user.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Base Sales: h3/i4 add Customer, Quote and Opportunity links. The generic
    # BusinessDocument links intentionally belong to the later Documents
    # foundation revision and are not duplicated here.
    if _create_table(
        'sales_quote',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'organization_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('organization.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('quote_number', sa.String(50), nullable=False),
        sa.Column('customer_name', sa.String(255), nullable=False),
        sa.Column('customer_document', sa.String(30), nullable=True),
        sa.Column('customer_email', sa.String(255), nullable=True),
        sa.Column('customer_phone', sa.String(50), nullable=True),
        sa.Column('total_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('discount_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('net_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('valid_until', sa.Date(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column(
            'created_by_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('user.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    ):
        op.create_index('ix_sales_quote_status', 'sales_quote', ['status'])

    if _create_table(
        'sales_order',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'organization_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('organization.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('order_number', sa.String(50), nullable=False),
        sa.Column('customer_name', sa.String(255), nullable=False),
        sa.Column('customer_document', sa.String(30), nullable=True),
        sa.Column('total_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('discount_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('net_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('payment_terms', sa.String(100), nullable=True),
        sa.Column('delivery_status', sa.String(50), nullable=False),
        sa.Column('billing_status', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column(
            'created_by_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('user.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    ):
        op.create_index(
            'ix_sales_order_billing_status', 'sales_order', ['billing_status']
        )
        op.create_index('ix_sales_order_status', 'sales_order', ['status'])

    _create_table(
        'sales_quote_item',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'quote_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('sales_quote.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'product_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('product.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('quantity', sa.Numeric(12, 4), nullable=False),
        sa.Column('unit_price', sa.Numeric(12, 4), nullable=False),
        sa.Column('discount_amount', sa.Numeric(12, 4), nullable=False),
        sa.Column('total_price', sa.Numeric(14, 2), nullable=False),
        sa.Column('notes', sa.String(255), nullable=True),
    )

    _create_table(
        'sales_order_item',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'sales_order_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('sales_order.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'product_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('product.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('quantity', sa.Numeric(12, 4), nullable=False),
        sa.Column('unit_price', sa.Numeric(12, 4), nullable=False),
        sa.Column('discount_amount', sa.Numeric(12, 4), nullable=False),
        sa.Column('total_price', sa.Numeric(14, 2), nullable=False),
        sa.Column('notes', sa.String(255), nullable=True),
    )

    if _create_table(
        'pos_session',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'organization_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('organization.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('pos_terminal', sa.String(50), nullable=False),
        sa.Column(
            'opened_by_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('user.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('opening_cash', sa.Numeric(14, 2), nullable=False),
        sa.Column('closing_cash', sa.Numeric(14, 2), nullable=True),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('opened_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
    ):
        op.create_index('ix_pos_session_status', 'pos_session', ['status'])

    _create_table(
        'pos_sale',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'organization_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('organization.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'pos_session_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('pos_session.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('customer_name', sa.String(255), nullable=False),
        sa.Column('customer_document', sa.String(30), nullable=True),
        sa.Column('total_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('discount_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('net_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('payment_method', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column(
            'created_by_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('user.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    _create_table(
        'pos_sale_item',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'pos_sale_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('pos_sale.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'product_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('product.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('quantity', sa.Numeric(12, 4), nullable=False),
        sa.Column('unit_price', sa.Numeric(12, 4), nullable=False),
        sa.Column('total_price', sa.Numeric(14, 2), nullable=False),
    )


def downgrade() -> None:
    # Reverse dependency order. Legacy/adopted tables have no marker and are
    # deliberately retained; a mixed-state downgrade fails safely on an FK
    # instead of cascading into data owned outside this revision.
    for table_name in (
        'pos_sale_item',
        'pos_sale',
        'pos_session',
        'sales_order_item',
        'sales_quote_item',
        'sales_order',
        'sales_quote',
        'customer_interaction',
        'opportunity',
        'lead',
    ):
        _drop_if_created_here(table_name)
