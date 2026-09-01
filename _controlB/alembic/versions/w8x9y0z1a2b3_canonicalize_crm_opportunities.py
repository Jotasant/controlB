"""canonicalize crm opportunity documents

Revision ID: w8x9y0z1a2b3
Revises: v7w8x9y0z1a2
Create Date: 2026-08-24 07:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "w8x9y0z1a2b3"
down_revision: str | Sequence[str] | None = "v7w8x9y0z1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "opportunity",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM opportunity
                JOIN lead ON lead.id = opportunity.lead_id
                WHERE lead.organization_id <> opportunity.organization_id
            ) THEN
                RAISE EXCEPTION
                    'Existem Oportunidades vinculadas a Leads de outra organização.';
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
            gen_random_uuid(),
            opportunity.organization_id,
            'crm.opportunity',
            'OPPORTUNITY',
            opportunity.id,
            'MIG-OPP-' || opportunity.id::text,
            opportunity.title,
            upper(opportunity.stage),
            'MEDIUM',
            opportunity.loss_reason,
            '[]'::json,
            'CRM',
            opportunity.assigned_to_id,
            '{}'::json,
            opportunity.created_at,
            CASE
                WHEN upper(opportunity.stage) IN ('WON', 'LOST')
                    THEN coalesce(opportunity.updated_at, opportunity.created_at)
                ELSE NULL
            END,
            opportunity.assigned_to_id,
            opportunity.created_at,
            opportunity.updated_at
        FROM opportunity
        WHERE NOT EXISTS (
            SELECT 1
            FROM business_document AS document
            WHERE document.organization_id = opportunity.organization_id
              AND document.document_type = 'OPPORTUNITY'
              AND document.native_id = opportunity.id
        );
        """
    )

    op.execute(
        """
        UPDATE business_document AS document
        SET category = 'crm.opportunity',
            title = opportunity.title,
            current_status = upper(opportunity.stage),
            description = opportunity.loss_reason,
            origin_module = 'CRM',
            responsible_id = opportunity.assigned_to_id,
            issued_at = coalesce(document.issued_at, opportunity.created_at),
            completed_at = CASE
                WHEN upper(opportunity.stage) IN ('WON', 'LOST')
                    THEN coalesce(
                        document.completed_at,
                        opportunity.updated_at,
                        opportunity.created_at
                    )
                ELSE NULL
            END,
            created_by_id = coalesce(
                document.created_by_id,
                opportunity.assigned_to_id
            ),
            updated_at = now()
        FROM opportunity
        WHERE document.organization_id = opportunity.organization_id
          AND document.document_type = 'OPPORTUNITY'
          AND document.native_id = opportunity.id;
        """
    )

    op.execute(
        """
        WITH parsed_numbers AS (
            SELECT
                organization_id,
                substring(document_number FROM '^OPP-([0-9]{4})-[0-9]+$')::integer
                    AS sequence_year,
                substring(document_number FROM '^OPP-[0-9]{4}-([0-9]+)$')::integer
                    AS sequence_value
            FROM business_document
            WHERE document_type = 'OPPORTUNITY'
              AND document_number ~ '^OPP-[0-9]{4}-[0-9]+$'
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
                extract(year FROM opportunity.created_at)::integer AS sequence_year,
                row_number() OVER (
                    PARTITION BY
                        document.organization_id,
                        extract(year FROM opportunity.created_at)
                    ORDER BY opportunity.created_at, opportunity.id
                ) AS sequence_offset
            FROM opportunity
            JOIN business_document AS document
              ON document.organization_id = opportunity.organization_id
             AND document.document_type = 'OPPORTUNITY'
             AND document.native_id = opportunity.id
            WHERE document.document_number !~ '^OPP-[0-9]{4}-[0-9]+$'
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
        SET document_number = 'OPP-' || numbered.sequence_year::text || '-'
                || lpad(numbered.sequence_value::text, 4, '0'),
            updated_at = now()
        FROM numbered
        WHERE document.id = numbered.document_id;
        """
    )

    op.execute(
        """
        UPDATE opportunity
        SET document_id = document.id
        FROM business_document AS document
        WHERE document.organization_id = opportunity.organization_id
          AND document.document_type = 'OPPORTUNITY'
          AND document.native_id = opportunity.id;
        """
    )

    op.execute(
        """
        WITH canonical_numbers AS (
            SELECT
                organization_id,
                substring(document_number FROM '^OPP-([0-9]{4})-[0-9]+$')::integer
                    AS sequence_year,
                substring(document_number FROM '^OPP-[0-9]{4}-([0-9]+)$')::integer
                    AS sequence_value
            FROM business_document
            WHERE document_type = 'OPPORTUNITY'
              AND document_number ~ '^OPP-[0-9]{4}-[0-9]+$'
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
            gen_random_uuid(), organization_id, 'crm.opportunity', sequence_year,
            sequence_value, 'OPP', now()
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
            opportunity.organization_id,
            lead.document_id,
            opportunity.document_id,
            'ORIGINATED_FROM',
            json_build_object('migration_revision', 'w8x9y0z1a2b3'),
            opportunity_document.created_by_id,
            now()
        FROM opportunity
        JOIN lead
          ON lead.id = opportunity.lead_id
         AND lead.organization_id = opportunity.organization_id
        JOIN business_document AS opportunity_document
          ON opportunity_document.id = opportunity.document_id
         AND opportunity_document.organization_id = opportunity.organization_id
        WHERE opportunity.lead_id IS NOT NULL
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
                'migration_revision', 'w8x9y0z1a2b3',
                'source', 'crm_opportunity_legacy_projection'
            ),
            'migration:w8x9y0z1a2b3:' || document.id::text,
            document.created_by_id,
            now()
        FROM opportunity
        JOIN business_document AS document
          ON document.id = opportunity.document_id
         AND document.organization_id = opportunity.organization_id
        ON CONFLICT ON CONSTRAINT uq_document_event_idempotency DO NOTHING;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM opportunity WHERE document_id IS NULL) THEN
                RAISE EXCEPTION 'Existem Oportunidades sem identidade documental.';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM opportunity
                JOIN business_document AS document
                  ON document.id = opportunity.document_id
                 AND document.organization_id = opportunity.organization_id
                WHERE document.document_type <> 'OPPORTUNITY'
                   OR document.native_id <> opportunity.id
                   OR document.category <> 'crm.opportunity'
                   OR document.document_number !~ '^OPP-[0-9]{4}-[0-9]+$'
                   OR document.title <> opportunity.title
                   OR document.current_status <> upper(opportunity.stage)
                   OR document.origin_module <> 'CRM'
                   OR document.responsible_id
                        IS DISTINCT FROM opportunity.assigned_to_id
            ) THEN
                RAISE EXCEPTION
                    'Falha de integridade ao canonicalizar Oportunidades.';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM opportunity
                JOIN lead
                  ON lead.id = opportunity.lead_id
                 AND lead.organization_id = opportunity.organization_id
                WHERE opportunity.lead_id IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1
                      FROM document_relation
                      WHERE parent_document_id = lead.document_id
                        AND child_document_id = opportunity.document_id
                        AND relation_type = 'ORIGINATED_FROM'
                  )
            ) THEN
                RAISE EXCEPTION
                    'Falha ao migrar relações entre Leads e Oportunidades.';
            END IF;
        END $$;
        """
    )

    op.alter_column("opportunity", "document_id", nullable=False)
    op.create_unique_constraint(
        "uq_opportunity_document", "opportunity", ["document_id"]
    )
    op.create_foreign_key(
        "fk_opportunity_document_org",
        "opportunity",
        "business_document",
        ["document_id", "organization_id"],
        ["id", "organization_id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_opportunity_document_org", "opportunity", type_="foreignkey"
    )
    op.drop_constraint(
        "uq_opportunity_document", "opportunity", type_="unique"
    )
    op.drop_column("opportunity", "document_id")
    op.execute(
        """
        DELETE FROM document_event
        WHERE idempotency_key LIKE 'migration:w8x9y0z1a2b3:%';
        """
    )
