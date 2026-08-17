"""fix_foreign_key_cascades_for_organization_and_product

Revision ID: e4f5g6h7i8j9
Revises: a91b827364ef
Create Date: 2026-08-17 10:55:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4f5g6h7i8j9'
down_revision: Union[str, Sequence[str], None] = 'a91b827364ef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Identity Cascades
    op.drop_constraint('user_organization_id_fkey', 'user', type_='foreignkey')
    op.create_foreign_key('user_organization_id_fkey', 'user', 'organization', ['organization_id'], ['id'], ondelete='CASCADE')

    op.drop_constraint('role_organization_id_fkey', 'role', type_='foreignkey')
    op.create_foreign_key('role_organization_id_fkey', 'role', 'organization', ['organization_id'], ['id'], ondelete='CASCADE')

    op.drop_constraint('user_role_id_fkey', 'user', type_='foreignkey')
    op.create_foreign_key('user_role_id_fkey', 'user', 'role', ['role_id'], ['id'], ondelete='SET NULL')

    # 2. Product Items Cascades
    op.drop_constraint('pos_sale_item_product_id_fkey', 'pos_sale_item', type_='foreignkey')
    op.create_foreign_key('pos_sale_item_product_id_fkey', 'pos_sale_item', 'product', ['product_id'], ['id'], ondelete='CASCADE')

    op.drop_constraint('sales_order_item_product_id_fkey', 'sales_order_item', type_='foreignkey')
    op.create_foreign_key('sales_order_item_product_id_fkey', 'sales_order_item', 'product', ['product_id'], ['id'], ondelete='CASCADE')

    op.drop_constraint('sales_quote_item_product_id_fkey', 'sales_quote_item', type_='foreignkey')
    op.create_foreign_key('sales_quote_item_product_id_fkey', 'sales_quote_item', 'product', ['product_id'], ['id'], ondelete='CASCADE')

    op.drop_constraint('purchase_request_item_product_id_fkey', 'purchase_request_item', type_='foreignkey')
    op.create_foreign_key('purchase_request_item_product_id_fkey', 'purchase_request_item', 'product', ['product_id'], ['id'], ondelete='CASCADE')

    op.drop_constraint('purchase_order_item_product_id_fkey', 'purchase_order_item', type_='foreignkey')
    op.create_foreign_key('purchase_order_item_product_id_fkey', 'purchase_order_item', 'product', ['product_id'], ['id'], ondelete='CASCADE')

    op.drop_constraint('supplier_quote_item_product_id_fkey', 'supplier_quote_item', type_='foreignkey')
    op.create_foreign_key('supplier_quote_item_product_id_fkey', 'supplier_quote_item', 'product', ['product_id'], ['id'], ondelete='CASCADE')

    # 3. User references in Purchasing
    op.alter_column('purchase_request', 'requester_id', nullable=True)
    op.drop_constraint('purchase_request_requester_id_fkey', 'purchase_request', type_='foreignkey')
    op.create_foreign_key('purchase_request_requester_id_fkey', 'purchase_request', 'user', ['requester_id'], ['id'], ondelete='SET NULL')

    op.alter_column('purchase_order', 'buyer_id', nullable=True)
    op.drop_constraint('purchase_order_buyer_id_fkey', 'purchase_order', type_='foreignkey')
    op.create_foreign_key('purchase_order_buyer_id_fkey', 'purchase_order', 'user', ['buyer_id'], ['id'], ondelete='SET NULL')

    op.alter_column('approval_event', 'approver_id', nullable=True)
    op.drop_constraint('approval_event_approver_id_fkey', 'approval_event', type_='foreignkey')
    op.create_foreign_key('approval_event_approver_id_fkey', 'approval_event', 'user', ['approver_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    pass
