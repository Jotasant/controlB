"""canonicalize crm lead documents

Revision ID: v7w8x9y0z1a2
Revises: u6v7w8x9y0z1
Create Date: 2026-08-24 06:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "v7w8x9y0z1a2"
down_revision: str | Sequence[str] | None = "u6v7w8x9y0z1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "lead",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # Reaproveita os documentos já criados pela compatibilidade e cria somente
    # os cabeçalhos ausentes, inicialmente com um número técnico sem colisão.
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
            lead.organization_id,
            'crm.lead',
            'LEAD',
            lead.id,
            'MIG-LEAD-' || lead.id::text,
            lead.name,
            upper(lead.status),
            'MEDIUM',
            lead.notes,
            '[]'::json,
            'CRM',
            lead.assigned_to_id,
            '{}'::json,
            lead.created_at,
            CASE
                WHEN upper(lead.status) IN ('CONVERTED', 'DISQUALIFIED')
                    THEN coalesce(lead.updated_at, lead.created_at)
                ELSE NULL
            END,
            lead.assigned_to_id,
            lead.created_at,
            lead.updated_at
        FROM lead
        WHERE NOT EXISTS (
            SELECT 1
            FROM business_document AS document
            WHERE document.organization_id = lead.organization_id
              AND document.document_type = 'LEAD'
              AND document.native_id = lead.id
        );
        """
    )

    # Última importação dos campos comuns mantidos pelo CRM legado.
    op.execute(
        """
        UPDATE business_document AS document
        SET category = 'crm.lead',
            title = lead.name,
            current_status = upper(lead.status),
            description = lead.notes,
            origin_module = 'CRM',
            responsible_id = lead.assigned_to_id,
            issued_at = coalesce(document.issued_at, lead.created_at),
            completed_at = CASE
                WHEN upper(lead.status) IN ('CONVERTED', 'DISQUALIFIED')
                    THEN coalesce(
                        document.completed_at,
                        lead.updated_at,
                        lead.created_at
                    )
                ELSE NULL
            END,
            created_by_id = coalesce(document.created_by_id, lead.assigned_to_id),
            updated_at = now()
        FROM lead
        WHERE document.organization_id = lead.organization_id
          AND document.document_type = 'LEAD'
          AND document.native_id = lead.id;
        """
    )

    # Preserva números canônicos já usados e numera apenas documentos legados.
    op.execute(
        """
        WITH parsed_numbers AS (
            SELECT
                organization_id,
                substring(document_number FROM '^LEAD-([0-9]{4})-[0-9]+$')::integer
                    AS sequence_year,
                substring(document_number FROM '^LEAD-[0-9]{4}-([0-9]+)$')::integer
                    AS sequence_value
            FROM business_document
            WHERE document_type = 'LEAD'
              AND document_number ~ '^LEAD-[0-9]{4}-[0-9]+$'
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
                extract(year FROM lead.created_at)::integer AS sequence_year,
                row_number() OVER (
                    PARTITION BY document.organization_id, extract(year FROM lead.created_at)
                    ORDER BY lead.created_at, lead.id
                ) AS sequence_offset
            FROM lead
            JOIN business_document AS document
              ON document.organization_id = lead.organization_id
             AND document.document_type = 'LEAD'
             AND document.native_id = lead.id
            WHERE document.document_number !~ '^LEAD-[0-9]{4}-[0-9]+$'
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
        SET document_number = 'LEAD-' || numbered.sequence_year::text || '-'
                || lpad(numbered.sequence_value::text, 4, '0'),
            updated_at = now()
        FROM numbered
        WHERE document.id = numbered.document_id;
        """
    )

    op.execute(
        """
        UPDATE lead
        SET document_id = document.id
        FROM business_document AS document
        WHERE document.organization_id = lead.organization_id
          AND document.document_type = 'LEAD'
          AND document.native_id = lead.id;
        """
    )

    # O cursor passa a refletir o maior número histórico, impedindo reutilização.
    op.execute(
        """
        WITH canonical_numbers AS (
            SELECT
                organization_id,
                substring(document_number FROM '^LEAD-([0-9]{4})-[0-9]+$')::integer
                    AS sequence_year,
                substring(document_number FROM '^LEAD-[0-9]{4}-([0-9]+)$')::integer
                    AS sequence_value
            FROM business_document
            WHERE document_type = 'LEAD'
              AND document_number ~ '^LEAD-[0-9]{4}-[0-9]+$'
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
            gen_random_uuid(), organization_id, 'crm.lead', sequence_year,
            sequence_value, 'LEAD', now()
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
                'migration_revision', 'v7w8x9y0z1a2',
                'source', 'crm_lead_legacy_projection'
            ),
            'migration:v7w8x9y0z1a2:' || document.id::text,
            document.created_by_id,
            now()
        FROM lead
        JOIN business_document AS document
          ON document.id = lead.document_id
         AND document.organization_id = lead.organization_id
        ON CONFLICT ON CONSTRAINT uq_document_event_idempotency DO NOTHING;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM lead WHERE document_id IS NULL) THEN
                RAISE EXCEPTION 'Existem Leads sem identidade documental.';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM lead
                JOIN business_document AS document
                  ON document.id = lead.document_id
                 AND document.organization_id = lead.organization_id
                WHERE document.document_type <> 'LEAD'
                   OR document.native_id <> lead.id
                   OR document.category <> 'crm.lead'
                   OR document.document_number !~ '^LEAD-[0-9]{4}-[0-9]+$'
                   OR document.title <> lead.name
                   OR document.current_status <> upper(lead.status)
                   OR document.origin_module <> 'CRM'
                   OR document.responsible_id IS DISTINCT FROM lead.assigned_to_id
            ) THEN
                RAISE EXCEPTION 'Falha de integridade ao canonicalizar Leads.';
            END IF;
        END $$;
        """
    )

    op.alter_column("lead", "document_id", nullable=False)
    op.create_unique_constraint("uq_lead_document", "lead", ["document_id"])
    op.create_foreign_key(
        "fk_lead_document_org",
        "lead",
        "business_document",
        ["document_id", "organization_id"],
        ["id", "organization_id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_lead_document_org", "lead", type_="foreignkey")
    op.drop_constraint("uq_lead_document", "lead", type_="unique")
    op.drop_column("lead", "document_id")
    op.execute(
        """
        DELETE FROM document_event
        WHERE idempotency_key LIKE 'migration:v7w8x9y0z1a2:%';
        """
    )
