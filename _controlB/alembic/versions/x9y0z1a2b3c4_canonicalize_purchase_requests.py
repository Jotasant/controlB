"""canonicalize purchase request documents

Revision ID: x9y0z1a2b3c4
Revises: w8x9y0z1a2b3
Create Date: 2026-08-24 08:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "x9y0z1a2b3c4"
down_revision: str | Sequence[str] | None = "w8x9y0z1a2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "purchase_request",
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
                FROM quotation_process
                JOIN purchase_request
                  ON purchase_request.id = quotation_process.purchase_request_id
                WHERE quotation_process.organization_id
                    <> purchase_request.organization_id
            ) THEN
                RAISE EXCEPTION
                    'Existem Cotações vinculadas a Solicitações de outra organização.';
            END IF;
        END $$;
        """
    )

    # A numeração sempre foi calculada por organização; o índice legado global
    # contradizia essa regra e impediria o mesmo número em tenants diferentes.
    op.drop_index(
        "ix_purchase_request_request_number",
        table_name="purchase_request",
    )
    op.create_index(
        "ix_purchase_request_request_number",
        "purchase_request",
        ["request_number"],
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
            purchase_request.organization_id,
            'purchase.request',
            'PURCHASE_REQUEST',
            purchase_request.id,
            'MIG-SC-' || purchase_request.id::text,
            'Solicitação de Compra ' || purchase_request.request_number,
            upper(purchase_request.status),
            'MEDIUM',
            purchase_request.justification,
            '[]'::json,
            'PURCHASING',
            purchase_request.requester_id,
            '{}'::json,
            purchase_request.created_at,
            CASE
                WHEN upper(purchase_request.status) IN (
                    'CANCELLED', 'ORDERED', 'REJECTED'
                ) THEN coalesce(
                    purchase_request.updated_at,
                    purchase_request.created_at
                )
                ELSE NULL
            END,
            purchase_request.requester_id,
            purchase_request.created_at,
            purchase_request.updated_at
        FROM purchase_request
        WHERE NOT EXISTS (
            SELECT 1
            FROM business_document AS document
            WHERE document.organization_id = purchase_request.organization_id
              AND document.document_type = 'PURCHASE_REQUEST'
              AND document.native_id = purchase_request.id
        );
        """
    )

    op.execute(
        """
        UPDATE business_document AS document
        SET category = 'purchase.request',
            title = 'Solicitação de Compra ' || purchase_request.request_number,
            current_status = upper(purchase_request.status),
            description = purchase_request.justification,
            origin_module = 'PURCHASING',
            responsible_id = purchase_request.requester_id,
            issued_at = coalesce(document.issued_at, purchase_request.created_at),
            completed_at = CASE
                WHEN upper(purchase_request.status) IN (
                    'CANCELLED', 'ORDERED', 'REJECTED'
                ) THEN coalesce(
                    document.completed_at,
                    purchase_request.updated_at,
                    purchase_request.created_at
                )
                ELSE NULL
            END,
            created_by_id = coalesce(
                document.created_by_id,
                purchase_request.requester_id
            ),
            updated_at = now()
        FROM purchase_request
        WHERE document.organization_id = purchase_request.organization_id
          AND document.document_type = 'PURCHASE_REQUEST'
          AND document.native_id = purchase_request.id;
        """
    )

    op.execute(
        """
        WITH parsed_numbers AS (
            SELECT
                organization_id,
                substring(document_number FROM '^SC-([0-9]{4})-[0-9]+$')::integer
                    AS sequence_year,
                substring(document_number FROM '^SC-[0-9]{4}-([0-9]+)$')::integer
                    AS sequence_value
            FROM business_document
            WHERE document_type = 'PURCHASE_REQUEST'
              AND document_number ~ '^SC-[0-9]{4}-[0-9]+$'
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
                extract(year FROM purchase_request.created_at)::integer
                    AS sequence_year,
                row_number() OVER (
                    PARTITION BY
                        document.organization_id,
                        extract(year FROM purchase_request.created_at)
                    ORDER BY purchase_request.created_at, purchase_request.id
                ) AS sequence_offset
            FROM purchase_request
            JOIN business_document AS document
              ON document.organization_id = purchase_request.organization_id
             AND document.document_type = 'PURCHASE_REQUEST'
             AND document.native_id = purchase_request.id
            WHERE document.document_number !~ '^SC-[0-9]{4}-[0-9]+$'
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
        SET document_number = 'SC-' || numbered.sequence_year::text || '-'
                || lpad(numbered.sequence_value::text, 4, '0'),
            updated_at = now()
        FROM numbered
        WHERE document.id = numbered.document_id;
        """
    )

    op.execute(
        """
        UPDATE purchase_request
        SET document_id = document.id,
            request_number = document.document_number
        FROM business_document AS document
        WHERE document.organization_id = purchase_request.organization_id
          AND document.document_type = 'PURCHASE_REQUEST'
          AND document.native_id = purchase_request.id;
        """
    )

    op.execute(
        """
        UPDATE business_document AS document
        SET title = 'Solicitação de Compra ' || document.document_number,
            updated_at = now()
        FROM purchase_request
        WHERE document.id = purchase_request.document_id
          AND document.organization_id = purchase_request.organization_id;
        """
    )

    op.execute(
        """
        WITH canonical_numbers AS (
            SELECT
                organization_id,
                substring(document_number FROM '^SC-([0-9]{4})-[0-9]+$')::integer
                    AS sequence_year,
                substring(document_number FROM '^SC-[0-9]{4}-([0-9]+)$')::integer
                    AS sequence_value
            FROM business_document
            WHERE document_type = 'PURCHASE_REQUEST'
              AND document_number ~ '^SC-[0-9]{4}-[0-9]+$'
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
            gen_random_uuid(), organization_id, 'purchase.request', sequence_year,
            sequence_value, 'SC', now()
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

    # Cria as arestas possíveis agora; pedidos sem cabeçalho serão tratados no
    # recorte canônico de PurchaseOrder.
    op.execute(
        """
        INSERT INTO document_relation (
            id, organization_id, parent_document_id, child_document_id,
            relation_type, relation_metadata, created_by_id, created_at
        )
        SELECT
            gen_random_uuid(),
            purchase_request.organization_id,
            purchase_request.document_id,
            order_document.id,
            'GENERATED',
            json_build_object('migration_revision', 'x9y0z1a2b3c4'),
            order_document.created_by_id,
            now()
        FROM purchase_order
        JOIN purchase_request
          ON purchase_request.id = purchase_order.purchase_request_id
         AND purchase_request.organization_id = purchase_order.organization_id
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
                'migration_revision', 'x9y0z1a2b3c4',
                'source', 'purchase_request_legacy_projection'
            ),
            'migration:x9y0z1a2b3c4:' || document.id::text,
            document.created_by_id,
            now()
        FROM purchase_request
        JOIN business_document AS document
          ON document.id = purchase_request.document_id
         AND document.organization_id = purchase_request.organization_id
        ON CONFLICT ON CONSTRAINT uq_document_event_idempotency DO NOTHING;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM purchase_request WHERE document_id IS NULL
            ) THEN
                RAISE EXCEPTION
                    'Existem Solicitações de Compra sem identidade documental.';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM purchase_request
                JOIN business_document AS document
                  ON document.id = purchase_request.document_id
                 AND document.organization_id = purchase_request.organization_id
                WHERE document.document_type <> 'PURCHASE_REQUEST'
                   OR document.native_id <> purchase_request.id
                   OR document.category <> 'purchase.request'
                   OR document.document_number
                        !~ '^SC-[0-9]{4}-[0-9]+$'
                   OR document.document_number
                        <> purchase_request.request_number
                   OR document.title
                        <> 'Solicitação de Compra '
                            || purchase_request.request_number
                   OR document.current_status
                        <> upper(purchase_request.status)
                   OR document.description
                        IS DISTINCT FROM purchase_request.justification
                   OR document.origin_module <> 'PURCHASING'
                   OR document.responsible_id
                        IS DISTINCT FROM purchase_request.requester_id
            ) THEN
                RAISE EXCEPTION
                    'Falha ao canonicalizar Solicitações de Compra.';
            END IF;
        END $$;
        """
    )

    op.alter_column("purchase_request", "document_id", nullable=False)
    op.create_unique_constraint(
        "uq_purchase_request_document",
        "purchase_request",
        ["document_id"],
    )
    op.create_unique_constraint(
        "uq_purchase_request_org_number",
        "purchase_request",
        ["organization_id", "request_number"],
    )
    op.create_foreign_key(
        "fk_purchase_request_document_org",
        "purchase_request",
        "business_document",
        ["document_id", "organization_id"],
        ["id", "organization_id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_purchase_request_document_org",
        "purchase_request",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_purchase_request_org_number",
        "purchase_request",
        type_="unique",
    )
    op.drop_constraint(
        "uq_purchase_request_document",
        "purchase_request",
        type_="unique",
    )
    op.drop_column("purchase_request", "document_id")
    op.drop_index(
        "ix_purchase_request_request_number",
        table_name="purchase_request",
    )
    op.create_index(
        "ix_purchase_request_request_number",
        "purchase_request",
        ["request_number"],
        unique=True,
    )
    op.execute(
        """
        DELETE FROM document_event
        WHERE idempotency_key LIKE 'migration:x9y0z1a2b3c4:%';
        """
    )
