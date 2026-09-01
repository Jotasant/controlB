"""canonicalize purchase order documents

Revision ID: z1a2b3c4d5e6
Revises: y0z1a2b3c4d5
Create Date: 2026-08-24 11:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "z1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "y0z1a2b3c4d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "purchase_order",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM purchase_order
                JOIN purchase_request
                  ON purchase_request.id = purchase_order.purchase_request_id
                WHERE purchase_order.organization_id
                    <> purchase_request.organization_id
            ) THEN
                RAISE EXCEPTION
                    'Existem Pedidos vinculados a Solicitações de outra organização.';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM purchase_order
                JOIN supplier_quote
                  ON supplier_quote.id = purchase_order.supplier_quote_id
                WHERE purchase_order.organization_id
                    <> supplier_quote.organization_id
            ) THEN
                RAISE EXCEPTION
                    'Existem Pedidos vinculados a Propostas de outra organização.';
            END IF;
        END $$;
        """
    )

    op.drop_index(
        "ix_purchase_order_order_number",
        table_name="purchase_order",
    )
    op.create_index(
        "ix_purchase_order_order_number",
        "purchase_order",
        ["order_number"],
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
            'purchase.order',
            'PURCHASE_ORDER',
            purchase_order.id,
            'MIG-PC-' || purchase_order.id::text,
            'Ordem de Compra ' || purchase_order.order_number,
            upper(purchase_order.status),
            'MEDIUM',
            purchase_order.notes,
            '[]'::json,
            'PURCHASING',
            purchase_order.buyer_id,
            json_build_object(
                'supplier_id', purchase_order.supplier_id,
                'purchase_request_id', purchase_order.purchase_request_id,
                'supplier_quote_id', purchase_order.supplier_quote_id
            ),
            purchase_order.created_at,
            CASE
                WHEN upper(purchase_order.status) IN (
                    'CANCELLED', 'CLOSED', 'RECEIVED'
                ) THEN coalesce(
                    purchase_order.received_at,
                    purchase_order.updated_at,
                    purchase_order.created_at
                )
                ELSE NULL
            END,
            purchase_order.buyer_id,
            purchase_order.created_at,
            purchase_order.updated_at
        FROM purchase_order
        WHERE NOT EXISTS (
            SELECT 1
            FROM business_document AS document
            WHERE document.organization_id = purchase_order.organization_id
              AND document.document_type = 'PURCHASE_ORDER'
              AND document.native_id = purchase_order.id
        );
        """
    )

    op.execute(
        """
        UPDATE business_document AS document
        SET category = 'purchase.order',
            title = 'Ordem de Compra ' || purchase_order.order_number,
            current_status = upper(purchase_order.status),
            description = purchase_order.notes,
            origin_module = 'PURCHASING',
            responsible_id = purchase_order.buyer_id,
            payload = (
                coalesce(document.payload, '{}'::json)::jsonb
                || jsonb_build_object(
                    'supplier_id', purchase_order.supplier_id,
                    'purchase_request_id', purchase_order.purchase_request_id,
                    'supplier_quote_id', purchase_order.supplier_quote_id
                )
            )::json,
            issued_at = coalesce(document.issued_at, purchase_order.created_at),
            completed_at = CASE
                WHEN upper(purchase_order.status) IN (
                    'CANCELLED', 'CLOSED', 'RECEIVED'
                ) THEN coalesce(
                    document.completed_at,
                    purchase_order.received_at,
                    purchase_order.updated_at,
                    purchase_order.created_at
                )
                ELSE NULL
            END,
            created_by_id = coalesce(
                document.created_by_id,
                purchase_order.buyer_id
            ),
            updated_at = now()
        FROM purchase_order
        WHERE document.organization_id = purchase_order.organization_id
          AND document.document_type = 'PURCHASE_ORDER'
          AND document.native_id = purchase_order.id;
        """
    )

    op.execute(
        """
        WITH parsed_numbers AS (
            SELECT
                organization_id,
                substring(document_number FROM '^PC-([0-9]{4})-[0-9]+$')::integer
                    AS sequence_year,
                substring(document_number FROM '^PC-[0-9]{4}-([0-9]+)$')::integer
                    AS sequence_value
            FROM business_document
            WHERE document_type = 'PURCHASE_ORDER'
              AND document_number ~ '^PC-[0-9]{4}-[0-9]+$'
        ), canonical_maxima AS (
            SELECT
                organization_id,
                sequence_year,
                max(sequence_value) AS sequence_value
            FROM parsed_numbers
            GROUP BY organization_id, sequence_year
        ), candidates AS (
            SELECT
                document.id AS document_id,
                document.organization_id,
                extract(year FROM purchase_order.created_at)::integer
                    AS sequence_year,
                row_number() OVER (
                    PARTITION BY
                        document.organization_id,
                        extract(year FROM purchase_order.created_at)
                    ORDER BY purchase_order.created_at, purchase_order.id
                ) AS sequence_offset
            FROM purchase_order
            JOIN business_document AS document
              ON document.organization_id = purchase_order.organization_id
             AND document.document_type = 'PURCHASE_ORDER'
             AND document.native_id = purchase_order.id
            WHERE document.document_number !~ '^PC-[0-9]{4}-[0-9]+$'
        ), numbered AS (
            SELECT
                candidates.document_id,
                candidates.sequence_year,
                coalesce(canonical_maxima.sequence_value, 0)
                    + candidates.sequence_offset AS sequence_value
            FROM candidates
            LEFT JOIN canonical_maxima
              ON canonical_maxima.organization_id = candidates.organization_id
             AND canonical_maxima.sequence_year = candidates.sequence_year
        )
        UPDATE business_document AS document
        SET document_number = 'PC-' || numbered.sequence_year::text || '-'
                || lpad(numbered.sequence_value::text, 4, '0'),
            updated_at = now()
        FROM numbered
        WHERE document.id = numbered.document_id;
        """
    )

    op.execute(
        """
        UPDATE purchase_order
        SET document_id = document.id,
            order_number = document.document_number,
            status = lower(document.current_status),
            buyer_id = document.responsible_id,
            notes = document.description
        FROM business_document AS document
        WHERE document.organization_id = purchase_order.organization_id
          AND document.document_type = 'PURCHASE_ORDER'
          AND document.native_id = purchase_order.id;
        """
    )

    op.execute(
        """
        UPDATE business_document AS document
        SET title = 'Ordem de Compra ' || document.document_number,
            updated_at = now()
        FROM purchase_order
        WHERE document.id = purchase_order.document_id
          AND document.organization_id = purchase_order.organization_id;
        """
    )

    op.execute(
        """
        WITH canonical_numbers AS (
            SELECT
                organization_id,
                substring(document_number FROM '^PC-([0-9]{4})-[0-9]+$')::integer
                    AS sequence_year,
                substring(document_number FROM '^PC-[0-9]{4}-([0-9]+)$')::integer
                    AS sequence_value
            FROM business_document
            WHERE document_type = 'PURCHASE_ORDER'
              AND document_number ~ '^PC-[0-9]{4}-[0-9]+$'
        ), sequence_maxima AS (
            SELECT
                organization_id,
                sequence_year,
                max(sequence_value) AS sequence_value
            FROM canonical_numbers
            GROUP BY organization_id, sequence_year
        )
        INSERT INTO document_sequence (
            id, organization_id, category, year,
            current_value, prefix, updated_at
        )
        SELECT
            gen_random_uuid(), organization_id, 'purchase.order',
            sequence_year, sequence_value, 'PC', now()
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
            purchase_order.organization_id,
            purchase_request.document_id,
            purchase_order.document_id,
            'GENERATED',
            json_build_object('migration_revision', 'z1a2b3c4d5e6'),
            order_document.created_by_id,
            now()
        FROM purchase_order
        JOIN purchase_request
          ON purchase_request.id = purchase_order.purchase_request_id
         AND purchase_request.organization_id = purchase_order.organization_id
        JOIN business_document AS order_document
          ON order_document.id = purchase_order.document_id
         AND order_document.organization_id = purchase_order.organization_id
        ON CONFLICT ON CONSTRAINT uq_document_relation_edge DO NOTHING;
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
            purchase_order.organization_id,
            quotation_process.document_id,
            purchase_order.document_id,
            'GENERATED',
            json_build_object('migration_revision', 'z1a2b3c4d5e6'),
            order_document.created_by_id,
            now()
        FROM purchase_order
        JOIN supplier_quote
          ON supplier_quote.id = purchase_order.supplier_quote_id
         AND supplier_quote.organization_id = purchase_order.organization_id
        JOIN quotation_process
          ON quotation_process.id = supplier_quote.quotation_process_id
         AND quotation_process.organization_id = supplier_quote.organization_id
        JOIN business_document AS order_document
          ON order_document.id = purchase_order.document_id
         AND order_document.organization_id = purchase_order.organization_id
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
            document.organization_id,
            document.id,
            'CANONICAL_HEADER_MIGRATED',
            document.current_status,
            document.current_status,
            json_build_object(
                'migration_revision', 'z1a2b3c4d5e6',
                'source', 'purchase_order_legacy_projection'
            ),
            'migration:z1a2b3c4d5e6:' || document.id::text,
            document.created_by_id,
            now()
        FROM purchase_order
        JOIN business_document AS document
          ON document.id = purchase_order.document_id
         AND document.organization_id = purchase_order.organization_id
        ON CONFLICT ON CONSTRAINT uq_document_event_idempotency DO NOTHING;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM purchase_order WHERE document_id IS NULL
            ) THEN
                RAISE EXCEPTION
                    'Existem Ordens de Compra sem identidade documental.';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM purchase_order
                JOIN business_document AS document
                  ON document.id = purchase_order.document_id
                 AND document.organization_id = purchase_order.organization_id
                WHERE document.document_type <> 'PURCHASE_ORDER'
                   OR document.native_id <> purchase_order.id
                   OR document.category <> 'purchase.order'
                   OR document.document_number
                        !~ '^PC-[0-9]{4}-[0-9]+$'
                   OR document.document_number <> purchase_order.order_number
                   OR document.title
                        <> 'Ordem de Compra ' || purchase_order.order_number
                   OR document.current_status <> upper(purchase_order.status)
                   OR document.description
                        IS DISTINCT FROM purchase_order.notes
                   OR document.origin_module <> 'PURCHASING'
                   OR document.responsible_id
                        IS DISTINCT FROM purchase_order.buyer_id
            ) THEN
                RAISE EXCEPTION
                    'Falha ao canonicalizar Ordens de Compra.';
            END IF;
        END $$;
        """
    )

    op.alter_column("purchase_order", "document_id", nullable=False)
    op.create_unique_constraint(
        "uq_purchase_order_document",
        "purchase_order",
        ["document_id"],
    )
    op.create_unique_constraint(
        "uq_purchase_order_org_number",
        "purchase_order",
        ["organization_id", "order_number"],
    )
    op.create_foreign_key(
        "fk_purchase_order_document_org",
        "purchase_order",
        "business_document",
        ["document_id", "organization_id"],
        ["id", "organization_id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_purchase_order_document_org",
        "purchase_order",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_purchase_order_org_number",
        "purchase_order",
        type_="unique",
    )
    op.drop_constraint(
        "uq_purchase_order_document",
        "purchase_order",
        type_="unique",
    )
    op.drop_column("purchase_order", "document_id")
    op.drop_index(
        "ix_purchase_order_order_number",
        table_name="purchase_order",
    )
    op.create_index(
        "ix_purchase_order_order_number",
        "purchase_order",
        ["order_number"],
        unique=True,
    )
    op.execute(
        """
        DELETE FROM document_event
        WHERE idempotency_key LIKE 'migration:z1a2b3c4d5e6:%';
        """
    )
