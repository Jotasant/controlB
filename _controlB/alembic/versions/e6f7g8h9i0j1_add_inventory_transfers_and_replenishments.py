"""add inventory locations, transfers and replenishments

Revision ID: e6f7g8h9i0j1
Revises: d5e6f7g8h9i0
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e6f7g8h9i0j1"
down_revision: str | Sequence[str] | None = "d5e6f7g8h9i0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inventory_location",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_inventory_location_org_code"),
        sa.UniqueConstraint("id", "organization_id", name="uq_inventory_location_id_org"),
    )
    op.create_index(
        "ix_inventory_location_org_active",
        "inventory_location",
        ["organization_id", "is_active"],
    )
    op.create_index(
        "uq_inventory_location_default_org",
        "inventory_location",
        ["organization_id"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )
    op.execute(
        """
        INSERT INTO inventory_location (
            id, organization_id, code, name, description,
            is_default, is_active, created_at, updated_at
        )
        SELECT gen_random_uuid(), organization.id, 'PRINCIPAL', 'Estoque Principal',
               'Localização padrão criada durante a migração do saldo global.',
               true, true, now(), now()
        FROM organization;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM product WHERE current_stock < 0) THEN
                RAISE EXCEPTION 'Não é possível migrar saldos negativos para localizações de estoque.';
            END IF;
        END $$;
        """
    )
    op.create_table(
        "inventory_balance",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity >= 0", name="ck_inventory_balance_quantity_nonnegative"),
        sa.ForeignKeyConstraint(
            ["product_id", "organization_id"],
            ["product.id", "product.organization_id"],
            name="fk_inventory_balance_product_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["inventory_location.id", "inventory_location.organization_id"],
            name="fk_inventory_balance_location_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "location_id", name="uq_inventory_balance_product_location"),
    )
    op.create_index(
        "ix_inventory_balance_location",
        "inventory_balance",
        ["organization_id", "location_id"],
    )
    op.execute(
        """
        INSERT INTO inventory_balance (
            id, organization_id, product_id, location_id, quantity, updated_at
        )
        SELECT gen_random_uuid(), product.organization_id, product.id, location.id,
               coalesce(product.current_stock, 0), now()
        FROM product
        JOIN inventory_location AS location
          ON location.organization_id = product.organization_id
         AND location.is_default = true;
        """
    )

    op.create_table(
        "inventory_transfer",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transfer_number", sa.String(length=100), nullable=False),
        sa.Column("source_location_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("destination_location_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("completed_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("source_location_id <> destination_location_id", name="ck_inventory_transfer_distinct_locations"),
        sa.CheckConstraint("status IN ('COMPLETED', 'CANCELLED')", name="ck_inventory_transfer_status"),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["completed_by_id"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["business_document.id", "business_document.organization_id"],
            name="fk_inventory_transfer_document_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_location_id", "organization_id"],
            ["inventory_location.id", "inventory_location.organization_id"],
            name="fk_inventory_transfer_source_location_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["destination_location_id", "organization_id"],
            ["inventory_location.id", "inventory_location.organization_id"],
            name="fk_inventory_transfer_destination_location_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", name="uq_inventory_transfer_document"),
        sa.UniqueConstraint("id", "organization_id", name="uq_inventory_transfer_id_org"),
        sa.UniqueConstraint("organization_id", "transfer_number", name="uq_inventory_transfer_number_org"),
    )
    op.create_table(
        "inventory_transfer_item",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transfer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_inventory_transfer_item_quantity_positive"),
        sa.ForeignKeyConstraint(
            ["transfer_id", "organization_id"],
            ["inventory_transfer.id", "inventory_transfer.organization_id"],
            name="fk_inventory_transfer_item_transfer_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id", "organization_id"],
            ["product.id", "product.organization_id"],
            name="fk_inventory_transfer_item_product_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("transfer_id", "product_id", name="uq_inventory_transfer_item_product"),
    )

    op.add_column("stock_movement", sa.Column("transfer_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("stock_movement", sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("stock_movement", sa.Column("source_location_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("stock_movement", sa.Column("destination_location_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("stock_movement", sa.Column("location_balance_after", sa.Numeric(precision=12, scale=4), nullable=True))
    op.create_foreign_key(
        "fk_stock_movement_transfer_org", "stock_movement", "inventory_transfer",
        ["transfer_id", "organization_id"], ["id", "organization_id"], ondelete="RESTRICT",
    )
    for column, constraint in (
        ("location_id", "fk_stock_movement_location_org"),
        ("source_location_id", "fk_stock_movement_source_location_org"),
        ("destination_location_id", "fk_stock_movement_destination_location_org"),
    ):
        op.create_foreign_key(
            constraint, "stock_movement", "inventory_location",
            [column, "organization_id"], ["id", "organization_id"], ondelete="RESTRICT",
        )
    op.create_index("ix_stock_movement_transfer", "stock_movement", ["organization_id", "transfer_id"])
    op.execute(
        """
        UPDATE stock_movement AS movement
        SET location_id = location.id,
            location_balance_after = movement.balance_after
        FROM inventory_location AS location
        WHERE location.organization_id = movement.organization_id
          AND location.is_default = true;
        """
    )

    op.create_table(
        "inventory_replenishment",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("replenishment_number", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("estimated_total_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('OPEN', 'ORDERED', 'CANCELLED')", name="ck_inventory_replenishment_status"),
        sa.CheckConstraint("estimated_total_amount >= 0", name="ck_inventory_replenishment_total_nonnegative"),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["business_document.id", "business_document.organization_id"],
            name="fk_inventory_replenishment_document_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", name="uq_inventory_replenishment_document"),
        sa.UniqueConstraint("id", "organization_id", name="uq_inventory_replenishment_id_org"),
        sa.UniqueConstraint("organization_id", "replenishment_number", name="uq_inventory_replenishment_number_org"),
    )
    op.create_table(
        "inventory_replenishment_item",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("replenishment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("current_stock", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("min_stock", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("target_stock", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("requested_quantity", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("estimated_unit_price", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "current_stock >= 0 AND min_stock >= 0 AND target_stock >= 0",
            name="ck_inventory_replenishment_item_stock_nonnegative",
        ),
        sa.CheckConstraint(
            "requested_quantity > 0 AND estimated_unit_price >= 0",
            name="ck_inventory_replenishment_item_request_valid",
        ),
        sa.ForeignKeyConstraint(
            ["replenishment_id", "organization_id"],
            ["inventory_replenishment.id", "inventory_replenishment.organization_id"],
            name="fk_inventory_replenishment_item_header_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id", "organization_id"],
            ["product.id", "product.organization_id"],
            name="fk_inventory_replenishment_item_product_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("replenishment_id", "product_id", name="uq_inventory_replenishment_item_product"),
    )
    op.add_column("purchase_order", sa.Column("replenishment_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_purchase_order_replenishment_org", "purchase_order", "inventory_replenishment",
        ["replenishment_id", "organization_id"], ["id", "organization_id"], ondelete="RESTRICT",
    )
    op.create_unique_constraint("uq_purchase_order_replenishment", "purchase_order", ["replenishment_id"])


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM document_relation
        WHERE parent_document_id IN (
            SELECT document_id FROM inventory_transfer
            UNION SELECT document_id FROM inventory_replenishment
        ) OR child_document_id IN (
            SELECT document_id FROM inventory_transfer
            UNION SELECT document_id FROM inventory_replenishment
        );
        DELETE FROM document_event
        WHERE document_id IN (
            SELECT document_id FROM inventory_transfer
            UNION SELECT document_id FROM inventory_replenishment
        );
        """
    )
    op.drop_constraint("uq_purchase_order_replenishment", "purchase_order", type_="unique")
    op.drop_constraint("fk_purchase_order_replenishment_org", "purchase_order", type_="foreignkey")
    op.drop_column("purchase_order", "replenishment_id")
    op.drop_table("inventory_replenishment_item")
    op.drop_table("inventory_replenishment")

    op.drop_index("ix_stock_movement_transfer", table_name="stock_movement")
    op.drop_constraint("fk_stock_movement_destination_location_org", "stock_movement", type_="foreignkey")
    op.drop_constraint("fk_stock_movement_source_location_org", "stock_movement", type_="foreignkey")
    op.drop_constraint("fk_stock_movement_location_org", "stock_movement", type_="foreignkey")
    op.drop_constraint("fk_stock_movement_transfer_org", "stock_movement", type_="foreignkey")
    op.drop_column("stock_movement", "location_balance_after")
    op.drop_column("stock_movement", "destination_location_id")
    op.drop_column("stock_movement", "source_location_id")
    op.drop_column("stock_movement", "location_id")
    op.drop_column("stock_movement", "transfer_id")
    op.drop_table("inventory_transfer_item")
    op.drop_table("inventory_transfer")
    op.drop_index("ix_inventory_balance_location", table_name="inventory_balance")
    op.drop_table("inventory_balance")
    op.drop_index("uq_inventory_location_default_org", table_name="inventory_location")
    op.drop_index("ix_inventory_location_org_active", table_name="inventory_location")
    op.drop_table("inventory_location")
    op.execute(
        """
        DELETE FROM business_document
        WHERE document_type IN ('INVENTORY_TRANSFER', 'REPLENISHMENT');
        DELETE FROM document_sequence
        WHERE category IN ('inventory.transfer', 'inventory.replenishment');
        """
    )
