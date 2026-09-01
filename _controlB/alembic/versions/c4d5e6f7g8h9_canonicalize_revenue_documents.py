"""canonicalize revenue documents

Revision ID: c4d5e6f7g8h9
Revises: b3c4d5e6f7g8
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c4d5e6f7g8h9"
down_revision: str | Sequence[str] | None = "b3c4d5e6f7g8"
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
            SELECT organization_id,
                   substring(document_number FROM '^{prefix}-([0-9]{{4}})-[0-9]+$')::integer AS sequence_year,
                   max(substring(document_number FROM '^{prefix}-[0-9]{{4}}-([0-9]+)$')::integer) AS sequence_value
            FROM business_document
            WHERE document_type = '{document_type}'
              AND document_number ~ '^{prefix}-[0-9]{{4}}-[0-9]+$'
            GROUP BY organization_id, sequence_year
        )
        INSERT INTO document_sequence (
            id, organization_id, category, year, current_value, prefix, updated_at
        )
        SELECT gen_random_uuid(), organization_id, '{category}', sequence_year,
               sequence_value, '{prefix}', now()
        FROM maxima
        ON CONFLICT (organization_id, category, year)
        DO UPDATE SET current_value = greatest(document_sequence.current_value, excluded.current_value),
                      prefix = excluded.prefix, updated_at = now();
        """
    )


def upgrade() -> None:
    op.add_column("invoice", sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("invoice", sa.Column("fiscal_document_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("receivable", sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("receivable", sa.Column("receivable_number", sa.String(length=100), nullable=True))
    op.add_column("receivable", sa.Column("invoice_installment_id", postgresql.UUID(as_uuid=True), nullable=True))

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM invoice JOIN sales_order ON sales_order.id = invoice.sales_order_id
                WHERE invoice.organization_id <> sales_order.organization_id
            ) OR EXISTS (
                SELECT 1 FROM receivable JOIN fiscal_document ON fiscal_document.id = receivable.fiscal_document_id
                WHERE receivable.organization_id <> fiscal_document.organization_id
            ) THEN
                RAISE EXCEPTION 'Existem vínculos de receita entre organizações distintas.';
            END IF;
        END $$;

        UPDATE receivable AS receivable
        SET invoice_installment_id = installment.id
        FROM invoice
        JOIN invoice_installment AS installment ON installment.invoice_id = invoice.id
        WHERE invoice.organization_id = receivable.organization_id
          AND receivable.description = 'Fatura ' || invoice.invoice_number || ' (Parcela '
              || installment.installment_number::text || '/' || installment.total_installments::text || ')'
          AND NOT EXISTS (
              SELECT 1 FROM receivable AS duplicate
              WHERE duplicate.id <> receivable.id
                AND duplicate.organization_id = receivable.organization_id
                AND duplicate.description = receivable.description
          );

        UPDATE invoice
        SET fiscal_document_id = fiscal.id
        FROM fiscal_document AS fiscal
        WHERE fiscal.organization_id = invoice.organization_id
          AND fiscal.direction = 'OUTBOUND'
          AND fiscal.document_number = invoice.invoice_number
          AND NOT EXISTS (
              SELECT 1 FROM fiscal_document AS duplicate
              WHERE duplicate.id <> fiscal.id
                AND duplicate.organization_id = fiscal.organization_id
                AND duplicate.direction = 'OUTBOUND'
                AND duplicate.document_number = fiscal.document_number
          )
          AND NOT EXISTS (
              SELECT 1 FROM invoice AS duplicate
              WHERE duplicate.id <> invoice.id
                AND duplicate.organization_id = invoice.organization_id
                AND duplicate.invoice_number = invoice.invoice_number
          );
        """
    )

    op.execute(
        """
        UPDATE business_document AS document
        SET category = 'billing.invoice', origin_module = 'BILLING',
            title = 'Fatura Comercial ' || document.document_number,
            current_status = upper(invoice.status),
            description = invoice.notes,
            responsible_id = invoice.created_by_id,
            created_by_id = coalesce(document.created_by_id, invoice.created_by_id),
            payload = json_build_object(
                'sales_order_id', invoice.sales_order_id,
                'customer_name', invoice.customer_name,
                'customer_document', invoice.customer_document,
                'total_amount', invoice.total_amount,
                'tax_amount', invoice.tax_amount,
                'net_amount', invoice.net_amount,
                'due_date', invoice.due_date
            ),
            issued_at = invoice.issue_date::timestamp AT TIME ZONE 'UTC', updated_at = now()
        FROM invoice
        WHERE document.organization_id = invoice.organization_id
          AND document.document_type = 'INVOICE' AND document.native_id = invoice.id;

        INSERT INTO business_document (
            id, organization_id, category, document_type, native_id, document_number,
            title, current_status, priority, description, tags, origin_module,
            responsible_id, payload, issued_at, completed_at, created_by_id, created_at, updated_at
        )
        SELECT gen_random_uuid(), invoice.organization_id, 'billing.invoice', 'INVOICE', invoice.id,
               'MIG-FAT-' || invoice.id::text, 'Fatura Comercial', upper(invoice.status), 'MEDIUM',
               invoice.notes, '[]'::json, 'BILLING', invoice.created_by_id,
               json_build_object(
                   'sales_order_id', invoice.sales_order_id, 'customer_name', invoice.customer_name,
                   'customer_document', invoice.customer_document, 'total_amount', invoice.total_amount,
                   'tax_amount', invoice.tax_amount, 'net_amount', invoice.net_amount, 'due_date', invoice.due_date
               ), invoice.issue_date::timestamp AT TIME ZONE 'UTC',
               CASE WHEN upper(invoice.status) = 'CANCELLED' THEN invoice.updated_at ELSE NULL END,
               invoice.created_by_id, invoice.created_at, invoice.updated_at
        FROM invoice
        WHERE NOT EXISTS (
            SELECT 1 FROM business_document AS document
            WHERE document.organization_id = invoice.organization_id
              AND document.document_type = 'INVOICE' AND document.native_id = invoice.id
        );
        """
    )
    _canonicalize_numbers("INVOICE", "FAT")
    op.execute(
        """
        UPDATE invoice
        SET document_id = document.id, invoice_number = document.document_number,
            status = document.current_status
        FROM business_document AS document
        WHERE document.organization_id = invoice.organization_id
          AND document.document_type = 'INVOICE' AND document.native_id = invoice.id;

        UPDATE business_document AS document
        SET title = 'Fatura Comercial ' || document.document_number, updated_at = now()
        FROM invoice WHERE document.id = invoice.document_id;
        """
    )
    _sync_sequence("billing.invoice", "INVOICE", "FAT")

    op.execute(
        """
        INSERT INTO business_document (
            id, organization_id, category, document_type, native_id, document_number,
            title, current_status, priority, description, tags, origin_module,
            responsible_id, payload, issued_at, completed_at, created_by_id, created_at, updated_at
        )
        SELECT gen_random_uuid(), receivable.organization_id, 'finance.receivable', 'RECEIVABLE', receivable.id,
               'MIG-REC-' || receivable.id::text, 'Conta a Receber', upper(receivable.status), 'MEDIUM',
               receivable.description, '[]'::json, 'FINANCE', NULL,
               json_build_object(
                   'fiscal_document_id', receivable.fiscal_document_id,
                   'invoice_installment_id', receivable.invoice_installment_id,
                   'customer_name', receivable.customer_name,
                   'customer_document', receivable.customer_document,
                   'due_date', receivable.due_date, 'amount', receivable.original_amount
               ), receivable.issue_date::timestamp AT TIME ZONE 'UTC',
               CASE WHEN upper(receivable.status) IN ('RECEIVED', 'CANCELLED') THEN receivable.updated_at ELSE NULL END,
               NULL, receivable.created_at, receivable.updated_at
        FROM receivable
        WHERE NOT EXISTS (
            SELECT 1 FROM business_document AS document
            WHERE document.organization_id = receivable.organization_id
              AND document.document_type = 'RECEIVABLE' AND document.native_id = receivable.id
        );
        """
    )
    _canonicalize_numbers("RECEIVABLE", "REC")
    op.execute(
        """
        UPDATE receivable
        SET document_id = document.id, receivable_number = document.document_number,
            status = document.current_status
        FROM business_document AS document
        WHERE document.organization_id = receivable.organization_id
          AND document.document_type = 'RECEIVABLE' AND document.native_id = receivable.id;

        UPDATE business_document AS document
        SET title = 'Conta a Receber ' || document.document_number, updated_at = now()
        FROM receivable WHERE document.id = receivable.document_id;
        """
    )
    _sync_sequence("finance.receivable", "RECEIVABLE", "REC")

    op.execute(
        """
        INSERT INTO document_relation (
            id, organization_id, parent_document_id, child_document_id, relation_type,
            relation_metadata, created_by_id, created_at
        )
        SELECT gen_random_uuid(), invoice.organization_id, sales_order.document_id,
               invoice.document_id, 'INVOICED_BY',
               json_build_object('migration_revision', 'c4d5e6f7g8h9'), invoice.created_by_id, now()
        FROM invoice JOIN sales_order
          ON sales_order.id = invoice.sales_order_id
         AND sales_order.organization_id = invoice.organization_id
        ON CONFLICT ON CONSTRAINT uq_document_relation_edge DO NOTHING;

        INSERT INTO document_relation (
            id, organization_id, parent_document_id, child_document_id, relation_type,
            relation_metadata, created_by_id, created_at
        )
        SELECT gen_random_uuid(), invoice.organization_id, invoice.document_id,
               fiscal.document_id, 'DOCUMENTED_BY',
               json_build_object('migration_revision', 'c4d5e6f7g8h9'), invoice.created_by_id, now()
        FROM invoice JOIN fiscal_document AS fiscal
          ON fiscal.id = invoice.fiscal_document_id
         AND fiscal.organization_id = invoice.organization_id
        ON CONFLICT ON CONSTRAINT uq_document_relation_edge DO NOTHING;

        INSERT INTO document_relation (
            id, organization_id, parent_document_id, child_document_id, relation_type,
            relation_metadata, created_by_id, created_at
        )
        SELECT gen_random_uuid(), receivable.organization_id,
               coalesce(fiscal.document_id, invoice.document_id), receivable.document_id,
               'GENERATED', json_build_object(
                   'migration_revision', 'c4d5e6f7g8h9',
                   'invoice_installment_id', receivable.invoice_installment_id
               ), invoice.created_by_id, now()
        FROM receivable
        LEFT JOIN fiscal_document AS fiscal
          ON fiscal.id = receivable.fiscal_document_id
         AND fiscal.organization_id = receivable.organization_id
        LEFT JOIN invoice_installment AS installment
          ON installment.id = receivable.invoice_installment_id
        LEFT JOIN invoice
          ON invoice.id = installment.invoice_id
         AND invoice.organization_id = receivable.organization_id
        WHERE coalesce(fiscal.document_id, invoice.document_id) IS NOT NULL
        ON CONFLICT ON CONSTRAINT uq_document_relation_edge DO NOTHING;

        INSERT INTO document_event (
            id, organization_id, document_id, event_type, previous_status, new_status,
            event_metadata, idempotency_key, created_by_id, created_at
        )
        SELECT gen_random_uuid(), document.organization_id, document.id,
               'CANONICAL_HEADER_MIGRATED', document.current_status, document.current_status,
               json_build_object('migration_revision', 'c4d5e6f7g8h9'),
               'migration:c4d5e6f7g8h9:' || document.id::text,
               document.created_by_id, now()
        FROM business_document AS document
        WHERE document.document_type IN ('INVOICE', 'RECEIVABLE')
        ON CONFLICT ON CONSTRAINT uq_document_event_idempotency DO NOTHING;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM invoice WHERE document_id IS NULL)
               OR EXISTS (SELECT 1 FROM receivable WHERE document_id IS NULL OR receivable_number IS NULL)
            THEN RAISE EXCEPTION 'Existem registros de receita sem identidade documental.';
            END IF;

            IF EXISTS (
                SELECT 1 FROM invoice JOIN business_document AS document
                  ON document.id = invoice.document_id AND document.organization_id = invoice.organization_id
                WHERE document.document_type <> 'INVOICE' OR document.category <> 'billing.invoice'
                   OR document.native_id <> invoice.id OR document.document_number <> invoice.invoice_number
                   OR document.document_number !~ '^FAT-[0-9]{4}-[0-9]+$'
                   OR document.current_status <> upper(invoice.status)
            ) OR EXISTS (
                SELECT 1 FROM receivable JOIN business_document AS document
                  ON document.id = receivable.document_id AND document.organization_id = receivable.organization_id
                WHERE document.document_type <> 'RECEIVABLE' OR document.category <> 'finance.receivable'
                   OR document.native_id <> receivable.id OR document.document_number <> receivable.receivable_number
                   OR document.document_number !~ '^REC-[0-9]{4}-[0-9]+$'
                   OR document.current_status <> upper(receivable.status)
            ) THEN RAISE EXCEPTION 'Falha ao canonicalizar os registros de receita.';
            END IF;
        END $$;
        """
    )

    op.drop_constraint("invoice_sales_order_id_fkey", "invoice", type_="foreignkey")
    op.drop_constraint("receivable_fiscal_document_id_fkey", "receivable", type_="foreignkey")
    op.alter_column("invoice", "document_id", nullable=False)
    op.alter_column("receivable", "document_id", nullable=False)
    op.alter_column("receivable", "receivable_number", nullable=False)

    op.create_unique_constraint("uq_invoice_document", "invoice", ["document_id"])
    op.create_unique_constraint("uq_invoice_id_org", "invoice", ["id", "organization_id"])
    op.create_unique_constraint("uq_invoice_org_number", "invoice", ["organization_id", "invoice_number"])
    op.create_unique_constraint("uq_invoice_installment_number", "invoice_installment", ["invoice_id", "installment_number"])
    op.create_unique_constraint("uq_receivable_document", "receivable", ["document_id"])
    op.create_unique_constraint("uq_receivable_org_number", "receivable", ["organization_id", "receivable_number"])
    op.create_unique_constraint("uq_receivable_id_org", "receivable", ["id", "organization_id"])
    op.create_unique_constraint("uq_receivable_invoice_installment", "receivable", ["invoice_installment_id"])

    op.create_foreign_key("fk_invoice_document_org", "invoice", "business_document", ["document_id", "organization_id"], ["id", "organization_id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_invoice_sales_order_org", "invoice", "sales_order", ["sales_order_id", "organization_id"], ["id", "organization_id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_invoice_fiscal_document_org", "invoice", "fiscal_document", ["fiscal_document_id", "organization_id"], ["id", "organization_id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_receivable_document_org", "receivable", "business_document", ["document_id", "organization_id"], ["id", "organization_id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_receivable_fiscal_document_org", "receivable", "fiscal_document", ["fiscal_document_id", "organization_id"], ["id", "organization_id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_receivable_invoice_installment", "receivable", "invoice_installment", ["invoice_installment_id"], ["id"], ondelete="RESTRICT")


def downgrade() -> None:
    op.drop_constraint("fk_receivable_invoice_installment", "receivable", type_="foreignkey")
    op.drop_constraint("fk_receivable_fiscal_document_org", "receivable", type_="foreignkey")
    op.drop_constraint("fk_receivable_document_org", "receivable", type_="foreignkey")
    op.drop_constraint("fk_invoice_fiscal_document_org", "invoice", type_="foreignkey")
    op.drop_constraint("fk_invoice_sales_order_org", "invoice", type_="foreignkey")
    op.drop_constraint("fk_invoice_document_org", "invoice", type_="foreignkey")
    op.drop_constraint("uq_receivable_invoice_installment", "receivable", type_="unique")
    op.drop_constraint("uq_receivable_id_org", "receivable", type_="unique")
    op.drop_constraint("uq_receivable_org_number", "receivable", type_="unique")
    op.drop_constraint("uq_receivable_document", "receivable", type_="unique")
    op.drop_constraint("uq_invoice_installment_number", "invoice_installment", type_="unique")
    op.drop_constraint("uq_invoice_org_number", "invoice", type_="unique")
    op.drop_constraint("uq_invoice_id_org", "invoice", type_="unique")
    op.drop_constraint("uq_invoice_document", "invoice", type_="unique")
    op.create_foreign_key("receivable_fiscal_document_id_fkey", "receivable", "fiscal_document", ["fiscal_document_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("invoice_sales_order_id_fkey", "invoice", "sales_order", ["sales_order_id"], ["id"], ondelete="SET NULL")
    op.drop_column("receivable", "invoice_installment_id")
    op.drop_column("receivable", "receivable_number")
    op.drop_column("receivable", "document_id")
    op.drop_column("invoice", "fiscal_document_id")
    op.drop_column("invoice", "document_id")
    op.execute(
        """
        DELETE FROM document_relation
        WHERE parent_document_id IN (SELECT id FROM business_document WHERE document_type IN ('INVOICE', 'RECEIVABLE'))
           OR child_document_id IN (SELECT id FROM business_document WHERE document_type IN ('INVOICE', 'RECEIVABLE'));
        DELETE FROM document_event
        WHERE document_id IN (SELECT id FROM business_document WHERE document_type IN ('INVOICE', 'RECEIVABLE'));
        DELETE FROM business_document WHERE document_type IN ('INVOICE', 'RECEIVABLE');
        DELETE FROM document_sequence WHERE category IN ('billing.invoice', 'finance.receivable');
        """
    )
