'''bootstrap_billing_and_finance_tables

Revision ID: j5k6l7m8n9o0
Revises: i4j5k6l7m8n9
Create Date: 2026-08-17 15:30:00.000000

Billing and Finance ORM tables existed in legacy databases without an Alembic
creation revision. This compatibility revision creates each missing table while
adopting any pre-existing table unchanged. An ownership marker makes downgrade
non-destructive for legacy data.
'''

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.schema import SchemaItem

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'j5k6l7m8n9o0'
down_revision: str | Sequence[str] | None = 'i4j5k6l7m8n9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_OWNER_MARKER = 'controlb.alembic.owner=j5k6l7m8n9o0'


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _mark_created(table_name: str) -> None:
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
    _create_table(
        'financial_category',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'organization_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('organization.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('code', sa.String(50), nullable=True),
        sa.Column('category_type', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    _create_table(
        'bank_account',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'organization_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('organization.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('bank_name', sa.String(150), nullable=False),
        sa.Column('bank_code', sa.String(20), nullable=True),
        sa.Column('agency', sa.String(50), nullable=True),
        sa.Column('account_number', sa.String(50), nullable=True),
        sa.Column('account_type', sa.String(50), nullable=False),
        sa.Column('opening_balance', sa.Numeric(14, 2), nullable=False),
        sa.Column('current_balance', sa.Numeric(14, 2), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    if _create_table(
        'fiscal_document',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'organization_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('organization.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('direction', sa.String(20), nullable=False),
        sa.Column('document_type', sa.String(50), nullable=False),
        sa.Column('document_number', sa.String(100), nullable=False),
        sa.Column('series', sa.String(20), nullable=True),
        sa.Column('access_key', sa.String(100), nullable=True),
        sa.Column('issuer_name', sa.String(255), nullable=False),
        sa.Column('issuer_cnpj_cpf', sa.String(30), nullable=True),
        sa.Column('recipient_name', sa.String(255), nullable=True),
        sa.Column('recipient_cnpj_cpf', sa.String(30), nullable=True),
        sa.Column('issue_date', sa.Date(), nullable=False),
        sa.Column('total_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('tax_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column(
            'purchase_order_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('purchase_order.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column(
            'supplier_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('supplier.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('file_attachment', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    ):
        op.create_index(
            'ix_fiscal_document_access_key', 'fiscal_document', ['access_key']
        )

    if _create_table(
        'payable',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'organization_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('organization.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'supplier_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('supplier.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column(
            'purchase_order_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('purchase_order.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column(
            'fiscal_document_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('fiscal_document.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column(
            'cost_center_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('cost_center.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column(
            'financial_category_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('financial_category.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('description', sa.String(500), nullable=False),
        sa.Column('favored_name', sa.String(255), nullable=False),
        sa.Column('original_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('outstanding_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('issue_date', sa.Date(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=False),
        sa.Column('expense_nature', sa.String(20), nullable=False),
        sa.Column('payment_method_expected', sa.String(50), nullable=True),
        sa.Column('installment_number', sa.Integer(), nullable=False),
        sa.Column('total_installments', sa.Integer(), nullable=False),
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
        op.create_index('ix_payable_due_date', 'payable', ['due_date'])
        op.create_index('ix_payable_status', 'payable', ['status'])

    _create_table(
        'payment_instrument',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'payable_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('payable.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('instrument_type', sa.String(50), nullable=False),
        sa.Column('barcode', sa.String(100), nullable=True),
        sa.Column('digitable_line', sa.String(150), nullable=True),
        sa.Column('pix_code', sa.Text(), nullable=True),
        sa.Column('document_number', sa.String(100), nullable=True),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('amount', sa.Numeric(14, 2), nullable=True),
        sa.Column('file_attachment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    _create_table(
        'payment',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'organization_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('organization.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'payable_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('payable.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'bank_account_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('bank_account.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('discount_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('interest_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('payment_date', sa.Date(), nullable=False),
        sa.Column('payment_method', sa.String(50), nullable=False),
        sa.Column('reference', sa.String(200), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column(
            'created_by_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('user.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    _create_table(
        'payment_attachment',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'payment_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('payment.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('file_name', sa.String(255), nullable=False),
        sa.Column('file_url', sa.Text(), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=True),
        sa.Column(
            'uploaded_by_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('user.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    if _create_table(
        'bank_transaction',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'organization_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('organization.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'bank_account_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('bank_account.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('transaction_date', sa.Date(), nullable=False),
        sa.Column('description', sa.String(500), nullable=False),
        sa.Column('amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('transaction_type', sa.String(20), nullable=False),
        sa.Column('external_id', sa.String(100), nullable=True),
        sa.Column('document_number', sa.String(100), nullable=True),
        sa.Column('balance_after', sa.Numeric(14, 2), nullable=True),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    ):
        op.create_index(
            'ix_bank_transaction_transaction_date',
            'bank_transaction',
            ['transaction_date'],
        )

    if _create_table(
        'receivable',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'organization_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('organization.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('customer_name', sa.String(255), nullable=False),
        sa.Column('customer_document', sa.String(30), nullable=True),
        sa.Column(
            'fiscal_document_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('fiscal_document.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column(
            'cost_center_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('cost_center.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column(
            'financial_category_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('financial_category.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('description', sa.String(500), nullable=False),
        sa.Column('original_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('outstanding_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('issue_date', sa.Date(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=False),
        sa.Column('payment_method_expected', sa.String(50), nullable=True),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    ):
        op.create_index('ix_receivable_due_date', 'receivable', ['due_date'])
        op.create_index('ix_receivable_status', 'receivable', ['status'])

    _create_table(
        'receipt',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'organization_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('organization.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'receivable_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('receivable.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'bank_account_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('bank_account.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('receipt_date', sa.Date(), nullable=False),
        sa.Column('payment_method', sa.String(50), nullable=False),
        sa.Column('reference', sa.String(200), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column(
            'received_by_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('user.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    _create_table(
        'reconciliation',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'organization_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('organization.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'bank_transaction_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('bank_transaction.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'payment_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('payment.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column(
            'receipt_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('receipt.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('reconciled_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            'reconciled_by_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('user.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.UniqueConstraint('bank_transaction_id'),
    )

    if _create_table(
        'sales_report',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'organization_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('organization.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('report_date', sa.Date(), nullable=False),
        sa.Column('gross_sales', sa.Numeric(14, 2), nullable=False),
        sa.Column('discounts', sa.Numeric(14, 2), nullable=False),
        sa.Column('returns', sa.Numeric(14, 2), nullable=False),
        sa.Column('net_sales', sa.Numeric(14, 2), nullable=False),
        sa.Column('cash_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('pix_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('debit_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('credit_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('other_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('source', sa.String(100), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column(
            'created_by_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('user.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    ):
        op.create_index('ix_sales_report_report_date', 'sales_report', ['report_date'])

    if _create_table(
        'invoice',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'organization_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('organization.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'sales_order_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('sales_order.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('invoice_number', sa.String(50), nullable=False),
        sa.Column('customer_name', sa.String(255), nullable=False),
        sa.Column('customer_document', sa.String(30), nullable=True),
        sa.Column('total_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('tax_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('net_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('issue_date', sa.Date(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=False),
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
        op.create_index('ix_invoice_status', 'invoice', ['status'])

    _create_table(
        'invoice_installment',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'invoice_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('invoice.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('installment_number', sa.Integer(), nullable=False),
        sa.Column('total_installments', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False),
    )


def downgrade() -> None:
    # Reverse dependency order; adopted legacy tables are deliberately retained.
    for table_name in (
        'invoice_installment',
        'invoice',
        'sales_report',
        'reconciliation',
        'receipt',
        'receivable',
        'bank_transaction',
        'payment_attachment',
        'payment',
        'payment_instrument',
        'payable',
        'fiscal_document',
        'bank_account',
        'financial_category',
    ):
        _drop_if_created_here(table_name)
