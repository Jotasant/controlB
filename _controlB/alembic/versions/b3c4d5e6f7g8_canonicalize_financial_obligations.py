"""canonicalize fiscal documents and payables

Revision ID: b3c4d5e6f7g8
Revises: a2b3c4d5e6f7
Create Date: 2026-08-24 13:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b3c4d5e6f7g8"
down_revision: str | Sequence[str] | None = "a2b3c4d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _canonicalize_numbers(document_type: str, prefix: str) -> None:
    op.execute(
        f"""
        WITH parsed AS (
            SELECT
                organization_id,
                substring(document_number FROM '^{prefix}-([0-9]{{4}})-[0-9]+$')::integer
                    AS sequence_year,
                max(substring(document_number FROM '^{prefix}-[0-9]{{4}}-([0-9]+)$')::integer)
                    AS sequence_value
            FROM business_document
            WHERE document_type = '{document_type}'
              AND document_number ~ '^{prefix}-[0-9]{{4}}-[0-9]+$'
            GROUP BY organization_id, sequence_year
        ), candidates AS (
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
                ) AS sequence_offset
            FROM business_document AS document
            WHERE document.document_type = '{document_type}'
              AND document.document_number !~ '^{prefix}-[0-9]{{4}}-[0-9]+$'
        ), numbered AS (
            SELECT
                candidates.document_id,
                candidates.sequence_year,
                coalesce(parsed.sequence_value, 0) + candidates.sequence_offset
                    AS sequence_value
            FROM candidates
            LEFT JOIN parsed
              ON parsed.organization_id = candidates.organization_id
             AND parsed.sequence_year = candidates.sequence_year
        )
        UPDATE business_document AS document
        SET document_number = '{prefix}-' || numbered.sequence_year::text || '-'
                || lpad(numbered.sequence_value::text, 4, '0'),
            updated_at = now()
        FROM numbered
        WHERE document.id = numbered.document_id;
        """
    )


def _sync_sequence(category: str, document_type: str, prefix: str) -> None:
    op.execute(
        f"""
        WITH maxima AS (
            SELECT
                organization_id,
                substring(document_number FROM '^{prefix}-([0-9]{{4}})-[0-9]+$')::integer
                    AS sequence_year,
                max(substring(document_number FROM '^{prefix}-[0-9]{{4}}-([0-9]+)$')::integer)
                    AS sequence_value
            FROM business_document
            WHERE document_type = '{document_type}'
              AND document_number ~ '^{prefix}-[0-9]{{4}}-[0-9]+$'
            GROUP BY organization_id, sequence_year
        )
        INSERT INTO document_sequence (
            id, organization_id, category, year,
            current_value, prefix, updated_at
        )
        SELECT
            gen_random_uuid(), organization_id, '{category}',
            sequence_year, sequence_value, '{prefix}', now()
        FROM maxima
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


def upgrade() -> None:
    op.add_column(
        "fiscal_document",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "payable",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "payable", sa.Column("payable_number", sa.String(length=100), nullable=True)
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM fiscal_document
                JOIN purchase_order
                  ON purchase_order.id = fiscal_document.purchase_order_id
                WHERE purchase_order.organization_id <> fiscal_document.organization_id
            ) OR EXISTS (
                SELECT 1
                FROM payable
                JOIN purchase_order ON purchase_order.id = payable.purchase_order_id
                WHERE purchase_order.organization_id <> payable.organization_id
            ) OR EXISTS (
                SELECT 1
                FROM payable
                JOIN fiscal_document
                  ON fiscal_document.id = payable.fiscal_document_id
                WHERE fiscal_document.organization_id <> payable.organization_id
            ) THEN
                RAISE EXCEPTION 'Existem vínculos financeiros entre organizações distintas.';
            END IF;
        END $$;
        """
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
            gen_random_uuid(), fiscal.organization_id,
            'finance.fiscal_document', 'FISCAL_DOCUMENT', fiscal.id,
            'MIG-DFE-' || fiscal.id::text,
            'Documento Fiscal ' || fiscal.document_number,
            upper(fiscal.status), 'MEDIUM', fiscal.notes, '[]'::json,
            'FINANCE', NULL,
            json_build_object(
                'direction', fiscal.direction,
                'fiscal_type', fiscal.document_type,
                'external_number', fiscal.document_number,
                'series', fiscal.series,
                'access_key', fiscal.access_key,
                'purchase_order_id', fiscal.purchase_order_id,
                'supplier_id', fiscal.supplier_id,
                'total_amount', fiscal.total_amount
            ),
            fiscal.issue_date::timestamp AT TIME ZONE 'UTC',
            CASE WHEN upper(fiscal.status) = 'CANCELLED'
                THEN fiscal.updated_at ELSE NULL END,
            NULL, fiscal.created_at, fiscal.updated_at
        FROM fiscal_document AS fiscal
        WHERE NOT EXISTS (
            SELECT 1 FROM business_document AS document
            WHERE document.organization_id = fiscal.organization_id
              AND document.document_type = 'FISCAL_DOCUMENT'
              AND document.native_id = fiscal.id
        );
        """
    )
    _canonicalize_numbers("FISCAL_DOCUMENT", "DFE")
    op.execute(
        """
        UPDATE fiscal_document AS fiscal
        SET document_id = document.id,
            status = lower(document.current_status)
        FROM business_document AS document
        WHERE document.organization_id = fiscal.organization_id
          AND document.document_type = 'FISCAL_DOCUMENT'
          AND document.native_id = fiscal.id;

        UPDATE business_document AS document
        SET title = 'Documento Fiscal ' || document.document_number || ' • '
                || fiscal.document_number,
            updated_at = now()
        FROM fiscal_document AS fiscal
        WHERE document.id = fiscal.document_id;
        """
    )
    _sync_sequence("finance.fiscal_document", "FISCAL_DOCUMENT", "DFE")

    op.execute(
        """
        INSERT INTO business_document (
            id, organization_id, category, document_type, native_id,
            document_number, title, current_status, priority, description,
            tags, origin_module, responsible_id, payload, issued_at,
            completed_at, created_by_id, created_at, updated_at
        )
        SELECT
            gen_random_uuid(), payable.organization_id,
            'finance.payable', 'PAYABLE', payable.id,
            'MIG-PAG-' || payable.id::text,
            'Conta a Pagar', upper(payable.status), 'MEDIUM',
            payable.description, '[]'::json, 'FINANCE', payable.created_by_id,
            json_build_object(
                'supplier_id', payable.supplier_id,
                'purchase_order_id', payable.purchase_order_id,
                'fiscal_document_id', payable.fiscal_document_id,
                'installment_number', payable.installment_number,
                'total_installments', payable.total_installments,
                'due_date', payable.due_date,
                'amount', payable.original_amount
            ),
            payable.issue_date::timestamp AT TIME ZONE 'UTC',
            CASE WHEN upper(payable.status) IN ('PAID', 'CANCELLED', 'RECONCILED')
                THEN payable.updated_at ELSE NULL END,
            payable.created_by_id, payable.created_at, payable.updated_at
        FROM payable
        WHERE NOT EXISTS (
            SELECT 1 FROM business_document AS document
            WHERE document.organization_id = payable.organization_id
              AND document.document_type = 'PAYABLE'
              AND document.native_id = payable.id
        );
        """
    )
    _canonicalize_numbers("PAYABLE", "PAG")
    op.execute(
        """
        UPDATE payable
        SET document_id = document.id,
            payable_number = document.document_number,
            status = document.current_status
        FROM business_document AS document
        WHERE document.organization_id = payable.organization_id
          AND document.document_type = 'PAYABLE'
          AND document.native_id = payable.id;

        UPDATE business_document AS document
        SET title = 'Conta a Pagar ' || document.document_number,
            updated_at = now()
        FROM payable
        WHERE document.id = payable.document_id;
        """
    )
    _sync_sequence("finance.payable", "PAYABLE", "PAG")

    op.execute(
        """
        INSERT INTO document_relation (
            id, organization_id, parent_document_id, child_document_id,
            relation_type, relation_metadata, created_by_id, created_at
        )
        SELECT
            gen_random_uuid(), fiscal.organization_id,
            coalesce(receipt.document_id, purchase_order.document_id),
            fiscal.document_id, 'DOCUMENTED_BY',
            json_build_object(
                'migration_revision', 'b3c4d5e6f7g8',
                'external_number', fiscal.document_number
            ), NULL, now()
        FROM fiscal_document AS fiscal
        JOIN purchase_order
          ON purchase_order.id = fiscal.purchase_order_id
         AND purchase_order.organization_id = fiscal.organization_id
        LEFT JOIN inventory_receipt AS receipt
          ON receipt.purchase_order_id = purchase_order.id
         AND receipt.organization_id = purchase_order.organization_id
        ON CONFLICT ON CONSTRAINT uq_document_relation_edge DO NOTHING;

        INSERT INTO document_relation (
            id, organization_id, parent_document_id, child_document_id,
            relation_type, relation_metadata, created_by_id, created_at
        )
        SELECT
            gen_random_uuid(), payable.organization_id,
            coalesce(fiscal.document_id, purchase_order.document_id),
            payable.document_id, 'GENERATED',
            json_build_object(
                'migration_revision', 'b3c4d5e6f7g8',
                'installment_number', payable.installment_number,
                'total_installments', payable.total_installments
            ), payable.created_by_id, now()
        FROM payable
        LEFT JOIN fiscal_document AS fiscal
          ON fiscal.id = payable.fiscal_document_id
         AND fiscal.organization_id = payable.organization_id
        LEFT JOIN purchase_order
          ON purchase_order.id = payable.purchase_order_id
         AND purchase_order.organization_id = payable.organization_id
        WHERE coalesce(fiscal.document_id, purchase_order.document_id) IS NOT NULL
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
            gen_random_uuid(), document.organization_id, document.id,
            'CANONICAL_HEADER_MIGRATED', document.current_status,
            document.current_status,
            json_build_object('migration_revision', 'b3c4d5e6f7g8'),
            'migration:b3c4d5e6f7g8:' || document.id::text,
            document.created_by_id, now()
        FROM business_document AS document
        WHERE document.document_type IN ('FISCAL_DOCUMENT', 'PAYABLE')
        ON CONFLICT ON CONSTRAINT uq_document_event_idempotency DO NOTHING;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM fiscal_document WHERE document_id IS NULL)
               OR EXISTS (
                    SELECT 1 FROM payable
                    WHERE document_id IS NULL OR payable_number IS NULL
               ) THEN
                RAISE EXCEPTION 'Existem registros financeiros sem identidade documental.';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM fiscal_document AS fiscal
                JOIN business_document AS document
                  ON document.id = fiscal.document_id
                 AND document.organization_id = fiscal.organization_id
                WHERE document.document_type <> 'FISCAL_DOCUMENT'
                   OR document.category <> 'finance.fiscal_document'
                   OR document.native_id <> fiscal.id
                   OR document.document_number !~ '^DFE-[0-9]{4}-[0-9]+$'
                   OR document.current_status <> upper(fiscal.status)
            ) OR EXISTS (
                SELECT 1
                FROM payable
                JOIN business_document AS document
                  ON document.id = payable.document_id
                 AND document.organization_id = payable.organization_id
                WHERE document.document_type <> 'PAYABLE'
                   OR document.category <> 'finance.payable'
                   OR document.native_id <> payable.id
                   OR document.document_number !~ '^PAG-[0-9]{4}-[0-9]+$'
                   OR document.document_number <> payable.payable_number
                   OR document.current_status <> upper(payable.status)
            ) THEN
                RAISE EXCEPTION 'Falha ao canonicalizar registros financeiros.';
            END IF;
        END $$;
        """
    )

    op.drop_constraint(
        "fiscal_document_purchase_order_id_fkey",
        "fiscal_document",
        type_="foreignkey",
    )
    op.drop_constraint(
        "payable_purchase_order_id_fkey", "payable", type_="foreignkey"
    )
    op.drop_constraint(
        "payable_fiscal_document_id_fkey", "payable", type_="foreignkey"
    )

    op.alter_column("fiscal_document", "document_id", nullable=False)
    op.alter_column("payable", "document_id", nullable=False)
    op.alter_column("payable", "payable_number", nullable=False)

    op.create_unique_constraint(
        "uq_fiscal_document_document", "fiscal_document", ["document_id"]
    )
    op.create_unique_constraint(
        "uq_fiscal_document_id_org",
        "fiscal_document",
        ["id", "organization_id"],
    )
    op.create_unique_constraint("uq_payable_document", "payable", ["document_id"])
    op.create_unique_constraint(
        "uq_payable_org_number",
        "payable",
        ["organization_id", "payable_number"],
    )
    op.create_unique_constraint(
        "uq_payable_id_org", "payable", ["id", "organization_id"]
    )

    op.create_foreign_key(
        "fk_fiscal_document_document_org",
        "fiscal_document",
        "business_document",
        ["document_id", "organization_id"],
        ["id", "organization_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_fiscal_document_purchase_order_org",
        "fiscal_document",
        "purchase_order",
        ["purchase_order_id", "organization_id"],
        ["id", "organization_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_payable_document_org",
        "payable",
        "business_document",
        ["document_id", "organization_id"],
        ["id", "organization_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_payable_purchase_order_org",
        "payable",
        "purchase_order",
        ["purchase_order_id", "organization_id"],
        ["id", "organization_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_payable_fiscal_document_org",
        "payable",
        "fiscal_document",
        ["fiscal_document_id", "organization_id"],
        ["id", "organization_id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_payable_fiscal_document_org", "payable", type_="foreignkey")
    op.drop_constraint("fk_payable_purchase_order_org", "payable", type_="foreignkey")
    op.drop_constraint("fk_payable_document_org", "payable", type_="foreignkey")
    op.drop_constraint(
        "fk_fiscal_document_purchase_order_org",
        "fiscal_document",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_fiscal_document_document_org", "fiscal_document", type_="foreignkey"
    )
    op.drop_constraint("uq_payable_id_org", "payable", type_="unique")
    op.drop_constraint("uq_payable_org_number", "payable", type_="unique")
    op.drop_constraint("uq_payable_document", "payable", type_="unique")
    op.drop_constraint(
        "uq_fiscal_document_id_org", "fiscal_document", type_="unique"
    )
    op.drop_constraint(
        "uq_fiscal_document_document", "fiscal_document", type_="unique"
    )

    op.create_foreign_key(
        "payable_fiscal_document_id_fkey",
        "payable",
        "fiscal_document",
        ["fiscal_document_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "payable_purchase_order_id_fkey",
        "payable",
        "purchase_order",
        ["purchase_order_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fiscal_document_purchase_order_id_fkey",
        "fiscal_document",
        "purchase_order",
        ["purchase_order_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_column("payable", "payable_number")
    op.drop_column("payable", "document_id")
    op.drop_column("fiscal_document", "document_id")

    op.execute(
        """
        DELETE FROM document_relation
        WHERE parent_document_id IN (
            SELECT id FROM business_document
            WHERE document_type IN ('FISCAL_DOCUMENT', 'PAYABLE')
        ) OR child_document_id IN (
            SELECT id FROM business_document
            WHERE document_type IN ('FISCAL_DOCUMENT', 'PAYABLE')
        );
        DELETE FROM document_event
        WHERE document_id IN (
            SELECT id FROM business_document
            WHERE document_type IN ('FISCAL_DOCUMENT', 'PAYABLE')
        );
        DELETE FROM business_document
        WHERE document_type IN ('FISCAL_DOCUMENT', 'PAYABLE');
        DELETE FROM document_sequence
        WHERE category IN ('finance.fiscal_document', 'finance.payable');
        """
    )
