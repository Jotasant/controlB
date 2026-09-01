"""canonicalize purchase quotation documents

Revision ID: y0z1a2b3c4d5
Revises: x9y0z1a2b3c4
Create Date: 2026-08-24 10:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "y0z1a2b3c4d5"
down_revision: str | Sequence[str] | None = "x9y0z1a2b3c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "quotation_process",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM quotation_process
                JOIN purchase_request
                  ON purchase_request.id = quotation_process.purchase_request_id
                WHERE quotation_process.organization_id
                    <> purchase_request.organization_id
            ) THEN
                RAISE EXCEPTION
                    'Existem Cotações vinculadas a Solicitações de outra organização.';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM purchase_order
                JOIN supplier_quote
                  ON supplier_quote.id = purchase_order.supplier_quote_id
                JOIN quotation_process
                  ON quotation_process.id = supplier_quote.quotation_process_id
                WHERE purchase_order.organization_id
                    <> quotation_process.organization_id
            ) THEN
                RAISE EXCEPTION
                    'Existem Pedidos vinculados a Cotações de outra organização.';
            END IF;
        END $$;
        """
    )

    # O sequencial é local ao tenant; o índice legado impunha unicidade global.
    op.drop_index(
        "ix_quotation_process_quotation_number",
        table_name="quotation_process",
    )
    op.create_index(
        "ix_quotation_process_quotation_number",
        "quotation_process",
        ["quotation_number"],
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
            quotation_process.organization_id,
            'purchase.quotation',
            'PURCHASE_QUOTATION',
            quotation_process.id,
            'MIG-RFQ-' || quotation_process.id::text,
            'Processo de Cotação ' || quotation_process.quotation_number,
            upper(quotation_process.status),
            'MEDIUM',
            quotation_process.notes,
            '[]'::json,
            'PURCHASING',
            purchase_request.requester_id,
            '{}'::json,
            quotation_process.created_at,
            CASE
                WHEN upper(quotation_process.status) IN (
                    'CANCELLED', 'COMPLETED'
                ) THEN coalesce(
                    quotation_process.updated_at,
                    quotation_process.created_at
                )
                ELSE NULL
            END,
            purchase_request.requester_id,
            quotation_process.created_at,
            quotation_process.updated_at
        FROM quotation_process
        JOIN purchase_request
          ON purchase_request.id = quotation_process.purchase_request_id
         AND purchase_request.organization_id = quotation_process.organization_id
        WHERE NOT EXISTS (
            SELECT 1
            FROM business_document AS document
            WHERE document.organization_id = quotation_process.organization_id
              AND document.document_type = 'PURCHASE_QUOTATION'
              AND document.native_id = quotation_process.id
        );
        """
    )

    op.execute(
        """
        UPDATE business_document AS document
        SET category = 'purchase.quotation',
            title = 'Processo de Cotação '
                || quotation_process.quotation_number,
            current_status = upper(quotation_process.status),
            description = quotation_process.notes,
            origin_module = 'PURCHASING',
            responsible_id = purchase_request.requester_id,
            issued_at = coalesce(
                document.issued_at,
                quotation_process.created_at
            ),
            completed_at = CASE
                WHEN upper(quotation_process.status) IN (
                    'CANCELLED', 'COMPLETED'
                ) THEN coalesce(
                    document.completed_at,
                    quotation_process.updated_at,
                    quotation_process.created_at
                )
                ELSE NULL
            END,
            created_by_id = coalesce(
                document.created_by_id,
                purchase_request.requester_id
            ),
            updated_at = now()
        FROM quotation_process
        JOIN purchase_request
          ON purchase_request.id = quotation_process.purchase_request_id
         AND purchase_request.organization_id = quotation_process.organization_id
        WHERE document.organization_id = quotation_process.organization_id
          AND document.document_type = 'PURCHASE_QUOTATION'
          AND document.native_id = quotation_process.id;
        """
    )

    # Prefixos legados COT são renumerados de forma determinística na série RFQ.
    op.execute(
        """
        WITH parsed_numbers AS (
            SELECT
                organization_id,
                substring(document_number FROM '^RFQ-([0-9]{4})-[0-9]+$')::integer
                    AS sequence_year,
                substring(document_number FROM '^RFQ-[0-9]{4}-([0-9]+)$')::integer
                    AS sequence_value
            FROM business_document
            WHERE document_type = 'PURCHASE_QUOTATION'
              AND document_number ~ '^RFQ-[0-9]{4}-[0-9]+$'
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
                extract(year FROM quotation_process.created_at)::integer
                    AS sequence_year,
                row_number() OVER (
                    PARTITION BY
                        document.organization_id,
                        extract(year FROM quotation_process.created_at)
                    ORDER BY quotation_process.created_at, quotation_process.id
                ) AS sequence_offset
            FROM quotation_process
            JOIN business_document AS document
              ON document.organization_id = quotation_process.organization_id
             AND document.document_type = 'PURCHASE_QUOTATION'
             AND document.native_id = quotation_process.id
            WHERE document.document_number !~ '^RFQ-[0-9]{4}-[0-9]+$'
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
        SET document_number = 'RFQ-' || numbered.sequence_year::text || '-'
                || lpad(numbered.sequence_value::text, 4, '0'),
            updated_at = now()
        FROM numbered
        WHERE document.id = numbered.document_id;
        """
    )

    op.execute(
        """
        UPDATE quotation_process
        SET document_id = document.id,
            quotation_number = document.document_number,
            notes = document.description
        FROM business_document AS document
        WHERE document.organization_id = quotation_process.organization_id
          AND document.document_type = 'PURCHASE_QUOTATION'
          AND document.native_id = quotation_process.id;
        """
    )

    op.execute(
        """
        UPDATE business_document AS document
        SET title = 'Processo de Cotação ' || document.document_number,
            updated_at = now()
        FROM quotation_process
        WHERE document.id = quotation_process.document_id
          AND document.organization_id = quotation_process.organization_id;
        """
    )

    op.execute(
        """
        WITH canonical_numbers AS (
            SELECT
                organization_id,
                substring(document_number FROM '^RFQ-([0-9]{4})-[0-9]+$')::integer
                    AS sequence_year,
                substring(document_number FROM '^RFQ-[0-9]{4}-([0-9]+)$')::integer
                    AS sequence_value
            FROM business_document
            WHERE document_type = 'PURCHASE_QUOTATION'
              AND document_number ~ '^RFQ-[0-9]{4}-[0-9]+$'
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
            gen_random_uuid(), organization_id, 'purchase.quotation',
            sequence_year, sequence_value, 'RFQ', now()
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
            quotation_process.organization_id,
            purchase_request.document_id,
            quotation_process.document_id,
            'GENERATED',
            json_build_object('migration_revision', 'y0z1a2b3c4d5'),
            quotation_document.created_by_id,
            now()
        FROM quotation_process
        JOIN purchase_request
          ON purchase_request.id = quotation_process.purchase_request_id
         AND purchase_request.organization_id = quotation_process.organization_id
        JOIN business_document AS quotation_document
          ON quotation_document.id = quotation_process.document_id
         AND quotation_document.organization_id = quotation_process.organization_id
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
            quotation_process.organization_id,
            quotation_process.document_id,
            order_document.id,
            'GENERATED',
            json_build_object('migration_revision', 'y0z1a2b3c4d5'),
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
          ON order_document.organization_id = purchase_order.organization_id
         AND order_document.document_type = 'PURCHASE_ORDER'
         AND order_document.native_id = purchase_order.id
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
                'migration_revision', 'y0z1a2b3c4d5',
                'source', 'quotation_process_legacy_projection'
            ),
            'migration:y0z1a2b3c4d5:' || document.id::text,
            document.created_by_id,
            now()
        FROM quotation_process
        JOIN business_document AS document
          ON document.id = quotation_process.document_id
         AND document.organization_id = quotation_process.organization_id
        ON CONFLICT ON CONSTRAINT uq_document_event_idempotency DO NOTHING;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM quotation_process WHERE document_id IS NULL
            ) THEN
                RAISE EXCEPTION
                    'Existem Processos de Cotação sem identidade documental.';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM quotation_process
                JOIN business_document AS document
                  ON document.id = quotation_process.document_id
                 AND document.organization_id = quotation_process.organization_id
                WHERE document.document_type <> 'PURCHASE_QUOTATION'
                   OR document.native_id <> quotation_process.id
                   OR document.category <> 'purchase.quotation'
                   OR document.document_number
                        !~ '^RFQ-[0-9]{4}-[0-9]+$'
                   OR document.document_number
                        <> quotation_process.quotation_number
                   OR document.title
                        <> 'Processo de Cotação '
                            || quotation_process.quotation_number
                   OR document.current_status
                        <> upper(quotation_process.status)
                   OR document.description
                        IS DISTINCT FROM quotation_process.notes
                   OR document.origin_module <> 'PURCHASING'
            ) THEN
                RAISE EXCEPTION
                    'Falha ao canonicalizar Processos de Cotação.';
            END IF;
        END $$;
        """
    )

    op.alter_column("quotation_process", "document_id", nullable=False)
    op.create_unique_constraint(
        "uq_quotation_process_document",
        "quotation_process",
        ["document_id"],
    )
    op.create_unique_constraint(
        "uq_quotation_process_org_number",
        "quotation_process",
        ["organization_id", "quotation_number"],
    )
    op.create_foreign_key(
        "fk_quotation_process_document_org",
        "quotation_process",
        "business_document",
        ["document_id", "organization_id"],
        ["id", "organization_id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_quotation_process_document_org",
        "quotation_process",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_quotation_process_org_number",
        "quotation_process",
        type_="unique",
    )
    op.drop_constraint(
        "uq_quotation_process_document",
        "quotation_process",
        type_="unique",
    )
    op.drop_column("quotation_process", "document_id")
    op.drop_index(
        "ix_quotation_process_quotation_number",
        table_name="quotation_process",
    )
    op.create_index(
        "ix_quotation_process_quotation_number",
        "quotation_process",
        ["quotation_number"],
        unique=True,
    )
    op.execute(
        """
        DELETE FROM document_event
        WHERE idempotency_key LIKE 'migration:y0z1a2b3c4d5:%';
        """
    )
