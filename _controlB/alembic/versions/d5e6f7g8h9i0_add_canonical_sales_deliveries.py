"""add canonical sales deliveries

Revision ID: d5e6f7g8h9i0
Revises: c4d5e6f7g8h9
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d5e6f7g8h9i0"
down_revision: str | Sequence[str] | None = "c4d5e6f7g8h9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _canonicalize_numbers(document_type: str, prefix: str) -> None:
    op.execute(
        f"""
        WITH parsed AS (
            SELECT organization_id,
                   substring(document_number FROM '^{prefix}-([0-9]{{4}})-[0-9]+$')::integer AS sequence_year,
                   max(substring(document_number FROM '^{prefix}-[0-9]{{4}}-([0-9]+)$')::integer) AS sequence_value
            FROM business_document
            WHERE document_type = '{document_type}'
              AND document_number ~ '^{prefix}-[0-9]{{4}}-[0-9]+$'
            GROUP BY organization_id, sequence_year
        ), candidates AS (
            SELECT document.id AS document_id, document.organization_id,
                   extract(year FROM coalesce(document.issued_at, document.created_at))::integer AS sequence_year,
                   row_number() OVER (
                       PARTITION BY document.organization_id,
                           extract(year FROM coalesce(document.issued_at, document.created_at))
                       ORDER BY coalesce(document.issued_at, document.created_at), document.id
                   ) AS sequence_offset
            FROM business_document AS document
            WHERE document.document_type = '{document_type}'
              AND document.document_number !~ '^{prefix}-[0-9]{{4}}-[0-9]+$'
        ), numbered AS (
            SELECT candidates.document_id, candidates.sequence_year,
                   coalesce(parsed.sequence_value, 0) + candidates.sequence_offset AS sequence_value
            FROM candidates
            LEFT JOIN parsed
              ON parsed.organization_id = candidates.organization_id
             AND parsed.sequence_year = candidates.sequence_year
        )
        UPDATE business_document AS document
        SET document_number = '{prefix}-' || numbered.sequence_year::text || '-'
                || lpad(numbered.sequence_value::text, 4, '0'), updated_at = now()
        FROM numbered WHERE document.id = numbered.document_id;
        """
    )


def _sync_sequence(category: str, document_type: str, prefix: str) -> None:
    op.execute(
        f"""
        WITH maxima AS (
            SELECT organization_id,
                   substring(document_number FROM '^{prefix}-([0-9]{{4}})-[0-9]+$')::integer AS sequence_year,
                   max(substring(document_number FROM '^{prefix}-[0-9]{{4}}-([0-9]+)$')::integer) AS sequence_value
            FROM business_document
            WHERE document_type = '{document_type}'
              AND document_number ~ '^{prefix}-[0-9]{{4}}-[0-9]+$'
            GROUP BY organization_id, sequence_year
        )
        INSERT INTO document_sequence (id, organization_id, category, year, current_value, prefix, updated_at)
        SELECT gen_random_uuid(), organization_id, '{category}', sequence_year,
               sequence_value, '{prefix}', now() FROM maxima
        ON CONFLICT (organization_id, category, year)
        DO UPDATE SET current_value = greatest(document_sequence.current_value, excluded.current_value),
                      prefix = excluded.prefix, updated_at = now();
        """
    )


def upgrade() -> None:
    op.add_column(
        "stock_reservation",
        sa.Column("consumed_by_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "stock_reservation",
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "stock_reservation_consumed_by_id_fkey",
        "stock_reservation",
        "user",
        ["consumed_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_constraint("ck_stock_reservation_status", "stock_reservation", type_="check")
    op.create_check_constraint(
        "ck_stock_reservation_status",
        "stock_reservation",
        "status IN ('RESERVED', 'RELEASED', 'CONSUMED')",
    )

    op.create_table(
        "inventory_delivery",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sales_order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reservation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fiscal_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("delivery_number", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("stock_posted", sa.Boolean(), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("delivered_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('DISPATCHED', 'DELIVERED', 'CANCELLED')",
            name="ck_inventory_delivery_status",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["delivered_by_id"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["sales_order_id", "organization_id"],
            ["sales_order.id", "sales_order.organization_id"],
            name="fk_inventory_delivery_sales_order_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reservation_id", "organization_id"],
            ["stock_reservation.id", "stock_reservation.organization_id"],
            name="fk_inventory_delivery_reservation_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["business_document.id", "business_document.organization_id"],
            name="fk_inventory_delivery_document_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["fiscal_document_id", "organization_id"],
            ["fiscal_document.id", "fiscal_document.organization_id"],
            name="fk_inventory_delivery_fiscal_document_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sales_order_id", name="uq_inventory_delivery_sales_order"),
        sa.UniqueConstraint("reservation_id", name="uq_inventory_delivery_reservation"),
        sa.UniqueConstraint("document_id", name="uq_inventory_delivery_document"),
        sa.UniqueConstraint("id", "organization_id", name="uq_inventory_delivery_id_org"),
        sa.UniqueConstraint("organization_id", "delivery_number", name="uq_inventory_delivery_number_org"),
    )
    op.create_index(
        "ix_inventory_delivery_org_status",
        "inventory_delivery",
        ["organization_id", "status"],
    )
    op.create_table(
        "inventory_delivery_item",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delivery_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_inventory_delivery_item_quantity_positive"),
        sa.ForeignKeyConstraint(
            ["delivery_id", "organization_id"],
            ["inventory_delivery.id", "inventory_delivery.organization_id"],
            name="fk_inventory_delivery_item_delivery_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id", "organization_id"],
            ["product.id", "product.organization_id"],
            name="fk_inventory_delivery_item_product_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("delivery_id", "product_id", name="uq_inventory_delivery_item_product"),
    )
    op.add_column(
        "stock_movement",
        sa.Column("delivery_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_stock_movement_delivery_org",
        "stock_movement",
        "inventory_delivery",
        ["delivery_id", "organization_id"],
        ["id", "organization_id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_stock_movement_delivery",
        "stock_movement",
        ["organization_id", "delivery_id"],
    )

    op.execute(
        """
        UPDATE business_document AS document
        SET category = 'inventory.reservation', origin_module = 'INVENTORY',
            title = 'Reserva de Estoque ' || document.document_number,
            current_status = upper(reservation.status),
            responsible_id = coalesce(document.responsible_id, reservation.created_by_id),
            payload = json_build_object(
                'sales_order_id', reservation.sales_order_id,
                'status_version', reservation.status_version
            ), updated_at = now()
        FROM stock_reservation AS reservation
        WHERE document.id = reservation.document_id
          AND document.organization_id = reservation.organization_id;
        """
    )
    _canonicalize_numbers("STOCK_RESERVATION", "RSV")
    op.execute(
        """
        UPDATE stock_reservation AS reservation
        SET reservation_number = document.document_number
        FROM business_document AS document
        WHERE document.id = reservation.document_id
          AND document.organization_id = reservation.organization_id;
        UPDATE business_document AS document
        SET title = 'Reserva de Estoque ' || document.document_number, updated_at = now()
        WHERE document.document_type = 'STOCK_RESERVATION';
        """
    )
    _sync_sequence("inventory.reservation", "STOCK_RESERVATION", "RSV")

    op.execute(
        """
        INSERT INTO business_document (
            id, organization_id, category, document_type, native_id, document_number,
            title, current_status, priority, description, tags, origin_module,
            responsible_id, payload, issued_at, completed_at, created_by_id, created_at, updated_at
        )
        SELECT gen_random_uuid(), orders.organization_id, 'inventory.delivery', 'DELIVERY', gen_random_uuid(),
               'MIG-ENT-' || orders.id::text, 'Entrega de Venda', upper(orders.delivery_status),
               'MEDIUM', orders.notes, '[]'::json, 'INVENTORY', orders.created_by_id,
               json_build_object('sales_order_id', orders.id, 'legacy_stock_posted_unknown', true),
               orders.updated_at,
               CASE WHEN orders.delivery_status = 'DELIVERED' THEN orders.updated_at ELSE NULL END,
               orders.created_by_id, orders.updated_at, orders.updated_at
        FROM sales_order AS orders
        WHERE orders.delivery_status IN ('DISPATCHED', 'DELIVERED')
          AND NOT EXISTS (
              SELECT 1 FROM inventory_delivery AS delivery
              WHERE delivery.sales_order_id = orders.id
          );
        """
    )
    _canonicalize_numbers("DELIVERY", "ENT")
    op.execute(
        """
        INSERT INTO inventory_delivery (
            id, organization_id, sales_order_id, reservation_id, document_id,
            fiscal_document_id, delivery_number, status, stock_posted,
            dispatched_at, delivered_at, created_by_id, delivered_by_id,
            notes, created_at, updated_at
        )
        SELECT document.native_id, orders.organization_id, orders.id, reservation.id,
               document.id, fiscal.id, document.document_number, orders.delivery_status,
               false, orders.updated_at,
               CASE WHEN orders.delivery_status = 'DELIVERED' THEN orders.updated_at ELSE NULL END,
               orders.created_by_id, NULL, orders.notes, orders.updated_at, orders.updated_at
        FROM sales_order AS orders
        JOIN business_document AS document
          ON document.organization_id = orders.organization_id
         AND document.document_type = 'DELIVERY'
         AND document.payload ->> 'sales_order_id' = orders.id::text
        LEFT JOIN stock_reservation AS reservation
          ON reservation.sales_order_id = orders.id
         AND reservation.organization_id = orders.organization_id
        LEFT JOIN LATERAL (
            SELECT fiscal_document.*
            FROM invoice
            JOIN fiscal_document ON fiscal_document.id = invoice.fiscal_document_id
            WHERE invoice.sales_order_id = orders.id
              AND invoice.organization_id = orders.organization_id
            ORDER BY invoice.created_at DESC LIMIT 1
        ) AS fiscal ON true;

        INSERT INTO inventory_delivery_item (
            id, organization_id, delivery_id, product_id, quantity, created_at
        )
        SELECT gen_random_uuid(), delivery.organization_id, delivery.id,
               order_item.product_id, sum(order_item.quantity), delivery.created_at
        FROM inventory_delivery AS delivery
        JOIN sales_order_item AS order_item ON order_item.sales_order_id = delivery.sales_order_id
        GROUP BY delivery.id, delivery.organization_id, order_item.product_id, delivery.created_at;
        """
    )
    _sync_sequence("inventory.delivery", "DELIVERY", "ENT")

    op.execute(
        """
        INSERT INTO document_relation (
            id, organization_id, parent_document_id, child_document_id,
            relation_type, relation_metadata, created_by_id, created_at
        )
        SELECT gen_random_uuid(), delivery.organization_id, orders.document_id,
               delivery.document_id, 'FULFILLED_BY',
               json_build_object('migration_revision', 'd5e6f7g8h9i0', 'stock_posted', false),
               delivery.created_by_id, now()
        FROM inventory_delivery AS delivery
        JOIN sales_order AS orders ON orders.id = delivery.sales_order_id
        ON CONFLICT ON CONSTRAINT uq_document_relation_edge DO NOTHING;

        INSERT INTO document_relation (
            id, organization_id, parent_document_id, child_document_id,
            relation_type, relation_metadata, created_by_id, created_at
        )
        SELECT gen_random_uuid(), delivery.organization_id, reservation.document_id,
               delivery.document_id, 'FULFILLED_BY',
               json_build_object('migration_revision', 'd5e6f7g8h9i0'),
               delivery.created_by_id, now()
        FROM inventory_delivery AS delivery
        JOIN stock_reservation AS reservation ON reservation.id = delivery.reservation_id
        ON CONFLICT ON CONSTRAINT uq_document_relation_edge DO NOTHING;

        INSERT INTO document_relation (
            id, organization_id, parent_document_id, child_document_id,
            relation_type, relation_metadata, created_by_id, created_at
        )
        SELECT gen_random_uuid(), delivery.organization_id, delivery.document_id,
               fiscal.document_id, 'DOCUMENTED_BY',
               json_build_object('migration_revision', 'd5e6f7g8h9i0'),
               delivery.created_by_id, now()
        FROM inventory_delivery AS delivery
        JOIN fiscal_document AS fiscal ON fiscal.id = delivery.fiscal_document_id
        ON CONFLICT ON CONSTRAINT uq_document_relation_edge DO NOTHING;

        INSERT INTO document_event (
            id, organization_id, document_id, event_type, previous_status, new_status,
            event_metadata, idempotency_key, created_by_id, created_at
        )
        SELECT gen_random_uuid(), document.organization_id, document.id,
               'CANONICAL_HEADER_MIGRATED', document.current_status, document.current_status,
               json_build_object('migration_revision', 'd5e6f7g8h9i0'),
               'migration:d5e6f7g8h9i0:' || document.id::text,
               document.created_by_id, now()
        FROM business_document AS document
        WHERE document.document_type IN ('STOCK_RESERVATION', 'DELIVERY')
        ON CONFLICT ON CONSTRAINT uq_document_event_idempotency DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM document_relation
        WHERE parent_document_id IN (SELECT document_id FROM inventory_delivery)
           OR child_document_id IN (SELECT document_id FROM inventory_delivery);
        DELETE FROM document_event WHERE document_id IN (SELECT document_id FROM inventory_delivery);
        """
    )
    op.drop_index("ix_stock_movement_delivery", table_name="stock_movement")
    op.drop_constraint("fk_stock_movement_delivery_org", "stock_movement", type_="foreignkey")
    op.drop_column("stock_movement", "delivery_id")
    op.drop_table("inventory_delivery_item")
    op.drop_index("ix_inventory_delivery_org_status", table_name="inventory_delivery")
    op.drop_table("inventory_delivery")
    op.execute(
        """
        DELETE FROM business_document WHERE document_type = 'DELIVERY';
        DELETE FROM document_sequence WHERE category = 'inventory.delivery';
        """
    )
    op.execute(
        """
        UPDATE stock_reservation SET status = 'RELEASED', consumed_at = NULL, consumed_by_id = NULL
        WHERE status = 'CONSUMED';
        UPDATE business_document SET current_status = 'RELEASED'
        WHERE document_type = 'STOCK_RESERVATION' AND current_status = 'CONSUMED';
        """
    )
    op.drop_constraint("ck_stock_reservation_status", "stock_reservation", type_="check")
    op.create_check_constraint(
        "ck_stock_reservation_status",
        "stock_reservation",
        "status IN ('RESERVED', 'RELEASED')",
    )
    op.drop_constraint(
        "stock_reservation_consumed_by_id_fkey", "stock_reservation", type_="foreignkey"
    )
    op.drop_column("stock_reservation", "consumed_at")
    op.drop_column("stock_reservation", "consumed_by_id")
