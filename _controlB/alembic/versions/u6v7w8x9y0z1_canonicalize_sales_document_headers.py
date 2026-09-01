"""canonicalize sales document headers

Revision ID: u6v7w8x9y0z1
Revises: t5u6v7w8x9y0
Create Date: 2026-08-24 05:30:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "u6v7w8x9y0z1"
down_revision: str | Sequence[str] | None = "t5u6v7w8x9y0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # O corte de autoridade só é seguro quando cada extensão nativa aponta para
    # o cabeçalho correto, no mesmo tenant e com a identidade nativa esperada.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM sales_quote AS quote
                LEFT JOIN business_document AS document
                  ON document.id = quote.document_id
                 AND document.organization_id = quote.organization_id
                WHERE document.id IS NULL
                   OR document.document_type <> 'SALES_QUOTE'
                   OR document.native_id <> quote.id
            ) THEN
                RAISE EXCEPTION 'Vínculo documental inválido em sales_quote.';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM sales_order AS sales_order
                LEFT JOIN business_document AS document
                  ON document.id = sales_order.document_id
                 AND document.organization_id = sales_order.organization_id
                WHERE document.id IS NULL
                   OR document.document_type <> 'SALES_ORDER'
                   OR document.native_id <> sales_order.id
            ) THEN
                RAISE EXCEPTION 'Vínculo documental inválido em sales_order.';
            END IF;
        END $$;
        """
    )

    # Última importação do estado legado. Após esta revisão, BusinessDocument é
    # a fonte de verdade e sales_quote/sales_order são projeções de compatibilidade.
    op.execute(
        """
        UPDATE business_document AS document
        SET category = 'sales.quotation',
            document_type = 'SALES_QUOTE',
            document_number = quote.quote_number,
            title = 'Cotação ' || quote.quote_number || ' - ' || quote.customer_name,
            current_status = upper(quote.status),
            origin_module = 'SALES',
            responsible_id = coalesce(document.responsible_id, quote.created_by_id),
            issued_at = coalesce(document.issued_at, quote.created_at),
            completed_at = CASE
                WHEN upper(quote.status) IN (
                    'CANCELLED', 'CLOSED', 'COMPLETED', 'CONVERTED',
                    'DELIVERED', 'EXPIRED', 'REJECTED'
                ) THEN coalesce(document.completed_at, quote.updated_at, quote.created_at)
                ELSE NULL
            END,
            updated_at = now()
        FROM sales_quote AS quote
        WHERE document.id = quote.document_id
          AND document.organization_id = quote.organization_id;
        """
    )
    op.execute(
        """
        UPDATE business_document AS document
        SET category = 'sales.order',
            document_type = 'SALES_ORDER',
            document_number = sales_order.order_number,
            title = 'Pedido de Venda ' || sales_order.order_number || ' - '
                    || sales_order.customer_name,
            current_status = upper(sales_order.status),
            origin_module = 'SALES',
            responsible_id = coalesce(document.responsible_id, sales_order.created_by_id),
            issued_at = coalesce(document.issued_at, sales_order.created_at),
            completed_at = CASE
                WHEN upper(sales_order.status) IN (
                    'CANCELLED', 'CLOSED', 'COMPLETED', 'CONVERTED',
                    'DELIVERED', 'EXPIRED', 'REJECTED'
                ) THEN coalesce(
                    document.completed_at,
                    sales_order.updated_at,
                    sales_order.created_at
                )
                ELSE NULL
            END,
            updated_at = now()
        FROM sales_order AS sales_order
        WHERE document.id = sales_order.document_id
          AND document.organization_id = sales_order.organization_id;
        """
    )

    # Um evento idempotente torna o corte histórico auditável sem duplicar a
    # timeline caso a operação seja retomada durante uma recuperação controlada.
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
                'migration_revision', 'u6v7w8x9y0z1',
                'source', 'sales_legacy_projection'
            ),
            'migration:u6v7w8x9y0z1:' || document.id::text,
            document.created_by_id,
            now()
        FROM business_document AS document
        WHERE document.document_type IN ('SALES_QUOTE', 'SALES_ORDER')
        ON CONFLICT ON CONSTRAINT uq_document_event_idempotency DO NOTHING;
        """
    )

    # Avança a sequência até o maior número no formato canônico já utilizado.
    # Números legados (ORC-AAAAMMDD-XXXX/PED-...) permanecem válidos, mas não
    # interferem na nova série ORC-AAAA-NNNN / PV-AAAA-NNNN.
    op.execute(
        """
        WITH canonical_numbers AS (
            SELECT
                organization_id,
                category,
                CASE category
                    WHEN 'sales.quotation' THEN 'ORC'
                    WHEN 'sales.order' THEN 'PV'
                END AS prefix,
                (
                    CASE category
                        WHEN 'sales.quotation' THEN substring(
                            document_number FROM '^ORC-([0-9]{4})-[0-9]+$'
                        )
                        WHEN 'sales.order' THEN substring(
                            document_number FROM '^PV-([0-9]{4})-[0-9]+$'
                        )
                    END
                )::integer AS sequence_year,
                (
                    CASE category
                        WHEN 'sales.quotation' THEN substring(
                            document_number FROM '^ORC-[0-9]{4}-([0-9]+)$'
                        )
                        WHEN 'sales.order' THEN substring(
                            document_number FROM '^PV-[0-9]{4}-([0-9]+)$'
                        )
                    END
                )::integer AS sequence_value
            FROM business_document
            WHERE (
                category = 'sales.quotation'
                AND document_number ~ '^ORC-[0-9]{4}-[0-9]+$'
            ) OR (
                category = 'sales.order'
                AND document_number ~ '^PV-[0-9]{4}-[0-9]+$'
            )
        ), sequence_maxima AS (
            SELECT
                organization_id,
                category,
                prefix,
                sequence_year,
                max(sequence_value) AS sequence_value
            FROM canonical_numbers
            GROUP BY organization_id, category, prefix, sequence_year
        )
        INSERT INTO document_sequence (
            id, organization_id, category, year,
            current_value, prefix, updated_at
        )
        SELECT
            gen_random_uuid(), organization_id, category, sequence_year,
            sequence_value, prefix, now()
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
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM sales_quote AS quote
                JOIN business_document AS document
                  ON document.id = quote.document_id
                 AND document.organization_id = quote.organization_id
                WHERE document.category <> 'sales.quotation'
                   OR document.document_number <> quote.quote_number
                   OR document.current_status <> upper(quote.status)
                   OR document.origin_module <> 'SALES'
            ) THEN
                RAISE EXCEPTION
                    'Falha de integridade após canonicalizar cabeçalhos de cotação.';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM sales_order AS sales_order
                JOIN business_document AS document
                  ON document.id = sales_order.document_id
                 AND document.organization_id = sales_order.organization_id
                WHERE document.category <> 'sales.order'
                   OR document.document_number <> sales_order.order_number
                   OR document.current_status <> upper(sales_order.status)
                   OR document.origin_module <> 'SALES'
            ) THEN
                RAISE EXCEPTION
                    'Falha de integridade após canonicalizar cabeçalhos de pedido.';
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # Reverter cabeçalhos após o corte poderia descartar alterações canônicas
    # legítimas. Apenas o marcador de auditoria é removido; os dados saneados e
    # os cursores de sequência são preservados deliberadamente.
    op.execute(
        """
        DELETE FROM document_event
        WHERE idempotency_key LIKE 'migration:u6v7w8x9y0z1:%';
        """
    )
