"""canonicalize inventory receipts

Revision ID: a2b3c4d5e6f7
Revises: z1a2b3c4d5e6
Create Date: 2026-08-24 12:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a2b3c4d5e6f7"
down_revision: str | Sequence[str] | None = "z1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_purchase_order_id_org",
        "purchase_order",
        ["id", "organization_id"],
    )
    op.create_table(
        "inventory_receipt",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purchase_order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("receipt_number", sa.String(length=100), nullable=False),
        sa.Column("invoice_number", sa.String(length=100), nullable=False),
        sa.Column("invoice_attachment", sa.Text(), nullable=True),
        sa.Column("received_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name="fk_inventory_receipt_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["received_by_id"],
            ["user.id"],
            name="fk_inventory_receipt_received_by",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_order_id", "organization_id"],
            ["purchase_order.id", "purchase_order.organization_id"],
            name="fk_inventory_receipt_purchase_order_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["business_document.id", "business_document.organization_id"],
            name="fk_inventory_receipt_document_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_inventory_receipt"),
        sa.UniqueConstraint(
            "purchase_order_id", name="uq_inventory_receipt_purchase_order"
        ),
        sa.UniqueConstraint("document_id", name="uq_inventory_receipt_document"),
        sa.UniqueConstraint(
            "organization_id",
            "receipt_number",
            name="uq_inventory_receipt_org_number",
        ),
        sa.UniqueConstraint(
            "id", "organization_id", name="uq_inventory_receipt_id_org"
        ),
    )
    op.create_index(
        "ix_inventory_receipt_org_received",
        "inventory_receipt",
        ["organization_id", "received_at"],
        unique=False,
    )
    op.add_column(
        "stock_movement",
        sa.Column("receipt_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_stock_movement_receipt_org",
        "stock_movement",
        "inventory_receipt",
        ["receipt_id", "organization_id"],
        ["id", "organization_id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_stock_movement_receipt",
        "stock_movement",
        ["organization_id", "receipt_id"],
        unique=False,
    )

    op.execute(
        """
        INSERT INTO business_document (
            id, organization_id, category, document_type, native_id,
            document_number, title, current_status, priority, description,
            tags, origin_module, responsible_id, payload, issued_at,
            completed_at, created_by_id, created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            purchase_order.organization_id,
            'inventory.receipt',
            'INVENTORY_RECEIPT',
            gen_random_uuid(),
            'MIG-REC-' || purchase_order.id::text,
            'Recebimento da Ordem ' || purchase_order.order_number,
            'RECEIVED',
            'MEDIUM',
            purchase_order.notes,
            '[]'::json,
            'INVENTORY',
            purchase_order.received_by_id,
            json_build_object(
                'purchase_order_id', purchase_order.id,
                'purchase_order_number', purchase_order.order_number,
                'invoice_number', purchase_order.invoice_number
            ),
            coalesce(
                purchase_order.received_at,
                purchase_order.updated_at,
                purchase_order.created_at
            ),
            coalesce(
                purchase_order.received_at,
                purchase_order.updated_at,
                purchase_order.created_at
            ),
            purchase_order.received_by_id,
            coalesce(purchase_order.received_at, purchase_order.created_at),
            purchase_order.updated_at
        FROM purchase_order
        WHERE (
                lower(purchase_order.status) = 'received'
                OR purchase_order.received_at IS NOT NULL
              )
          AND purchase_order.invoice_number IS NOT NULL
          AND btrim(purchase_order.invoice_number) <> '';
        """
    )

    op.execute(
        """
        WITH candidates AS (
            SELECT
                document.id AS document_id,
                document.organization_id,
                extract(year FROM coalesce(document.issued_at, document.created_at))::integer
                    AS sequence_year,
                row_number() OVER (
                    PARTITION BY
                        document.organization_id,
                        extract(year FROM coalesce(document.issued_at, document.created_at))
                    ORDER BY coalesce(document.issued_at, document.created_at), document.id
                ) AS sequence_value
            FROM business_document AS document
            WHERE document.document_type = 'INVENTORY_RECEIPT'
              AND document.document_number !~ '^REC-[0-9]{4}-[0-9]+$'
        )
        UPDATE business_document AS document
        SET document_number = 'REC-' || candidates.sequence_year::text || '-'
                || lpad(candidates.sequence_value::text, 4, '0'),
            title = 'Recebimento REC-' || candidates.sequence_year::text || '-'
                || lpad(candidates.sequence_value::text, 4, '0'),
            updated_at = now()
        FROM candidates
        WHERE document.id = candidates.document_id;
        """
    )

    op.execute(
        """
        INSERT INTO inventory_receipt (
            id, organization_id, purchase_order_id, document_id,
            receipt_number, invoice_number, invoice_attachment,
            received_by_id, received_at, notes, created_at
        )
        SELECT
            document.native_id,
            purchase_order.organization_id,
            purchase_order.id,
            document.id,
            document.document_number,
            purchase_order.invoice_number,
            purchase_order.invoice_attachment,
            purchase_order.received_by_id,
            coalesce(
                purchase_order.received_at,
                purchase_order.updated_at,
                purchase_order.created_at
            ),
            purchase_order.notes,
            coalesce(purchase_order.received_at, purchase_order.created_at)
        FROM purchase_order
        JOIN business_document AS document
          ON document.organization_id = purchase_order.organization_id
         AND document.document_type = 'INVENTORY_RECEIPT'
         AND (document.payload ->> 'purchase_order_id')::uuid = purchase_order.id;
        """
    )

    op.execute(
        """
        WITH canonical_numbers AS (
            SELECT
                organization_id,
                substring(document_number FROM '^REC-([0-9]{4})-[0-9]+$')::integer
                    AS sequence_year,
                substring(document_number FROM '^REC-[0-9]{4}-([0-9]+)$')::integer
                    AS sequence_value
            FROM business_document
            WHERE document_type = 'INVENTORY_RECEIPT'
              AND document_number ~ '^REC-[0-9]{4}-[0-9]+$'
        ), sequence_maxima AS (
            SELECT organization_id, sequence_year, max(sequence_value) AS sequence_value
            FROM canonical_numbers
            GROUP BY organization_id, sequence_year
        )
        INSERT INTO document_sequence (
            id, organization_id, category, year,
            current_value, prefix, updated_at
        )
        SELECT
            gen_random_uuid(), organization_id, 'inventory.receipt',
            sequence_year, sequence_value, 'REC', now()
        FROM sequence_maxima
        ON CONFLICT (organization_id, category, year)
        DO UPDATE SET
            current_value = greatest(
                document_sequence.current_value,
                excluded.current_value
            ),
            prefix = excluded.prefix,
            updated_at = now();
        """
    )

    op.execute(
        """
        INSERT INTO document_relation (
            id, organization_id, parent_document_id, child_document_id,
            relation_type, relation_metadata, created_by_id, created_at
        )
        SELECT
            gen_random_uuid(),
            receipt.organization_id,
            purchase_order.document_id,
            receipt.document_id,
            'FULFILLED_BY',
            json_build_object(
                'migration_revision', 'a2b3c4d5e6f7',
                'invoice_number', receipt.invoice_number
            ),
            receipt.received_by_id,
            receipt.created_at
        FROM inventory_receipt AS receipt
        JOIN purchase_order
          ON purchase_order.id = receipt.purchase_order_id
         AND purchase_order.organization_id = receipt.organization_id
        ON CONFLICT ON CONSTRAINT uq_document_relation_edge DO NOTHING;
        """
    )

    op.execute(
        """
        INSERT INTO document_event (
            id, organization_id, document_id, event_type,
            previous_status, new_status, event_metadata,
            idempotency_key, created_by_id, created_at
        )
        SELECT
            gen_random_uuid(),
            receipt.organization_id,
            receipt.document_id,
            'CANONICAL_HEADER_MIGRATED',
            'RECEIVED',
            'RECEIVED',
            json_build_object(
                'migration_revision', 'a2b3c4d5e6f7',
                'source', 'purchase_order_receipt_projection'
            ),
            'migration:a2b3c4d5e6f7:' || receipt.document_id::text,
            receipt.received_by_id,
            now()
        FROM inventory_receipt AS receipt
        ON CONFLICT ON CONSTRAINT uq_document_event_idempotency DO NOTHING;
        """
    )

    op.execute(
        """
        WITH candidates AS (
            SELECT DISTINCT ON (movement.id)
                movement.id AS movement_id,
                receipt.id AS receipt_id
            FROM stock_movement AS movement
            JOIN inventory_receipt AS receipt
              ON receipt.organization_id = movement.organization_id
            JOIN purchase_order
              ON purchase_order.id = receipt.purchase_order_id
             AND purchase_order.organization_id = receipt.organization_id
            JOIN purchase_order_item
              ON purchase_order_item.purchase_order_id = purchase_order.id
             AND purchase_order_item.product_id = movement.product_id
            WHERE movement.movement_type = 'in_purchase'
              AND movement.receipt_id IS NULL
              AND right(
                    movement.reference_doc,
                    length(' / NF ' || receipt.invoice_number)
                  ) = ' / NF ' || receipt.invoice_number
              AND abs(extract(epoch FROM (
                    movement.created_at - receipt.received_at
                  ))) <= 86400
            ORDER BY
                movement.id,
                abs(extract(epoch FROM (
                    movement.created_at - receipt.received_at
                )))
        )
        UPDATE stock_movement AS movement
        SET receipt_id = candidates.receipt_id
        FROM candidates
        WHERE movement.id = candidates.movement_id;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM inventory_receipt AS receipt
                JOIN business_document AS document
                  ON document.id = receipt.document_id
                 AND document.organization_id = receipt.organization_id
                WHERE document.document_type <> 'INVENTORY_RECEIPT'
                   OR document.category <> 'inventory.receipt'
                   OR document.native_id <> receipt.id
                   OR document.document_number <> receipt.receipt_number
                   OR document.document_number !~ '^REC-[0-9]{4}-[0-9]+$'
                   OR document.current_status <> 'RECEIVED'
                   OR document.origin_module <> 'INVENTORY'
            ) THEN
                RAISE EXCEPTION 'Falha ao canonicalizar Recebimentos de Estoque.';
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.drop_index("ix_stock_movement_receipt", table_name="stock_movement")
    op.drop_constraint(
        "fk_stock_movement_receipt_org",
        "stock_movement",
        type_="foreignkey",
    )
    op.drop_column("stock_movement", "receipt_id")
    op.drop_index("ix_inventory_receipt_org_received", table_name="inventory_receipt")
    op.drop_table("inventory_receipt")

    op.execute(
        """
        DELETE FROM document_relation
        WHERE child_document_id IN (
            SELECT id FROM business_document
            WHERE document_type = 'INVENTORY_RECEIPT'
        )
          AND relation_metadata ->> 'migration_revision' = 'a2b3c4d5e6f7';

        DELETE FROM document_event
        WHERE idempotency_key LIKE 'migration:a2b3c4d5e6f7:%';

        DELETE FROM business_document
        WHERE document_type = 'INVENTORY_RECEIPT'
          AND payload ->> 'purchase_order_id' IS NOT NULL;

        DELETE FROM document_sequence AS sequence
        WHERE sequence.category = 'inventory.receipt'
          AND NOT EXISTS (
              SELECT 1 FROM business_document
              WHERE category = 'inventory.receipt'
          );
        """
    )
    op.drop_constraint(
        "uq_purchase_order_id_org",
        "purchase_order",
        type_="unique",
    )
