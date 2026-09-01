"""consolidate document ownership for inventory imports and sales records

Revision ID: f8g9h0i1j2k3
Revises: e7f8a9b0c1d2
Create Date: 2026-09-01 15:10:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f8g9h0i1j2k3"
down_revision: str | Sequence[str] | None = "e7f8a9b0c1d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Movimentações produzidas por lotes já auditados pertencem ao documento do
    # lote. A janela de dois minutos cobre o processamento síncrono anterior.
    op.execute(
        """
        WITH matched AS (
            SELECT movement.id AS movement_id,
                   (
                       SELECT batch.document_id
                       FROM inventory_import_batch AS batch
                       WHERE batch.organization_id = movement.organization_id
                         AND abs(extract(epoch FROM (batch.created_at - movement.created_at))) <= 120
                       ORDER BY abs(extract(epoch FROM (batch.created_at - movement.created_at)))
                       LIMIT 1
                   ) AS batch_document_id
            FROM stock_movement AS movement
            WHERE movement.movement_type IN (
                'in_initial_inventory', 'in_purchase_sync', 'out_sale'
            )
              AND (
                  movement.movement_type <> 'out_sale'
                  OR movement.reference_doc LIKE 'Sync Invent%'
              )
        )
        UPDATE stock_movement AS movement
        SET document_id = matched.batch_document_id
        FROM matched
        WHERE movement.id = matched.movement_id
          AND matched.batch_document_id IS NOT NULL;
        """
    )

    # Reconstrói lotes legados somente quando não havia cabeçalho de importação.
    # Um intervalo superior a dez segundos identifica uma nova execução do
    # importador sem confundir as linhas processadas dentro do mesmo lote.
    op.execute(
        """
        CREATE TEMP TABLE legacy_import_movement_map ON COMMIT DROP AS
        WITH ordered AS (
            SELECT movement.id AS movement_id,
                   movement.organization_id,
                   movement.created_at,
                   CASE
                       WHEN lag(movement.created_at) OVER (
                           PARTITION BY movement.organization_id
                           ORDER BY movement.created_at, movement.id
                       ) IS NULL THEN 1
                       WHEN movement.created_at - lag(movement.created_at) OVER (
                           PARTITION BY movement.organization_id
                           ORDER BY movement.created_at, movement.id
                       ) > interval '10 seconds' THEN 1
                       ELSE 0
                   END AS starts_new_batch
            FROM stock_movement AS movement
            WHERE movement.document_id IS NULL
              AND movement.movement_type IN (
                  'in_initial_inventory', 'in_purchase_sync', 'out_sale'
              )
              AND (
                  movement.movement_type <> 'out_sale'
                  OR movement.reference_doc LIKE 'Sync Invent%'
              )
        ), grouped AS (
            SELECT ordered.*,
                   sum(starts_new_batch) OVER (
                       PARTITION BY organization_id
                       ORDER BY created_at, movement_id
                   ) AS batch_group
            FROM ordered
        )
        SELECT * FROM grouped;

        CREATE TEMP TABLE legacy_import_cluster ON COMMIT DROP AS
        SELECT gen_random_uuid() AS batch_id,
               gen_random_uuid() AS document_id,
               mapping.organization_id,
               mapping.batch_group,
               min(movement.created_at) AS started_at,
               max(movement.created_at) AS completed_at,
               count(DISTINCT movement.product_id)::integer AS total_products_read,
               count(*) FILTER (
                   WHERE movement.movement_type = 'in_initial_inventory'
               )::integer AS created_products_count,
               count(*) FILTER (
                   WHERE movement.movement_type <> 'in_initial_inventory'
               )::integer AS updated_products_count,
               count(*) FILTER (
                   WHERE movement.movement_type = 'out_sale'
               )::integer AS sales_identified_count,
               coalesce(sum(movement.quantity) FILTER (
                   WHERE movement.movement_type = 'out_sale'
               ), 0) AS total_sales_quantity,
               coalesce(sum(movement.quantity * product.sale_price) FILTER (
                   WHERE movement.movement_type = 'out_sale'
               ), 0) AS total_sales_estimated_revenue,
               count(*) FILTER (
                   WHERE movement.movement_type IN (
                       'in_initial_inventory', 'in_purchase_sync'
                   )
               )::integer AS entries_identified_count,
               coalesce(sum(movement.quantity) FILTER (
                   WHERE movement.movement_type IN (
                       'in_initial_inventory', 'in_purchase_sync'
                   )
               ), 0) AS total_entries_quantity,
               coalesce(sum(movement.quantity * movement.unit_cost) FILTER (
                   WHERE movement.movement_type IN (
                       'in_initial_inventory', 'in_purchase_sync'
                   )
               ), 0) AS total_entries_cost
        FROM legacy_import_movement_map AS mapping
        JOIN stock_movement AS movement ON movement.id = mapping.movement_id
        LEFT JOIN product ON product.id = movement.product_id
        GROUP BY mapping.organization_id, mapping.batch_group;

        INSERT INTO business_document (
            id, organization_id, category, document_type, native_id,
            document_number, title, current_status, priority, description,
            tags, origin_module, responsible_id, payload, issued_at,
            completed_at, created_by_id, created_at, updated_at
        )
        SELECT cluster.document_id, cluster.organization_id,
               'inventory.import_batch', 'INVENTORY_IMPORT_BATCH', cluster.batch_id,
               'IMPO-LEG-' || cluster.batch_id::text,
               'Lote legado de importação de estoque', 'PROCESSED', 'MEDIUM',
               'Cabeçalho reconstruído a partir das movimentações históricas do Kardex.',
               '[]'::json, 'INVENTORY', NULL,
               json_build_object(
                   'migration_revision', 'f8g9h0i1j2k3',
                   'legacy_reconstruction', true,
                   'total_products_read', cluster.total_products_read
               ), cluster.started_at, cluster.completed_at, NULL,
               cluster.started_at, cluster.completed_at
        FROM legacy_import_cluster AS cluster;

        INSERT INTO inventory_import_batch (
            id, organization_id, document_id, batch_number, filename,
            inventory_date, total_products_read, created_products_count,
            updated_products_count, created_categories_count,
            sales_identified_count, total_sales_quantity,
            total_sales_estimated_revenue, entries_identified_count,
            total_entries_quantity, total_entries_cost, cost_increases_count,
            cost_decreases_count, stagnant_products_count,
            total_stagnant_capital, total_inventory_cost,
            total_inventory_sale, imported_by_id, notes, created_at
        )
        SELECT cluster.batch_id, cluster.organization_id, cluster.document_id,
               'IMPO-LEG-' || cluster.batch_id::text, 'Histórico reconstruído',
               to_char(cluster.started_at, 'DD/MM/YY HH24:MI'),
               cluster.total_products_read, cluster.created_products_count,
               cluster.updated_products_count, 0,
               cluster.sales_identified_count, cluster.total_sales_quantity,
               cluster.total_sales_estimated_revenue,
               cluster.entries_identified_count, cluster.total_entries_quantity,
               cluster.total_entries_cost, 0, 0, 0, 0, 0, 0, NULL,
               'Lote reconstruído pela migração f8g9h0i1j2k3.',
               cluster.completed_at
        FROM legacy_import_cluster AS cluster;

        INSERT INTO inventory_import_item (
            id, organization_id, batch_id, product_id, code, barcode, sku,
            name, ncm, unit_of_measure, action_type, previous_stock, new_stock,
            delta_stock, previous_cost_price, new_cost_price,
            cost_variation_amount, cost_variation_percent,
            previous_sale_price, new_sale_price, sale_variation_amount,
            sale_variation_percent, stagnant_value,
            estimated_sales_revenue, created_at
        )
        SELECT gen_random_uuid(), movement.organization_id, cluster.batch_id,
               movement.product_id, coalesce(product.external_code, product.sku),
               product.barcode, product.sku, product.name, product.ncm,
               coalesce(product.unit_of_measure, 'UN'),
               CASE
                   WHEN movement.movement_type = 'in_initial_inventory' THEN 'created'
                   WHEN movement.movement_type = 'out_sale' THEN 'sale_detected'
                   ELSE 'entry_detected'
               END,
               CASE
                   WHEN movement.movement_type = 'out_sale'
                       THEN movement.balance_after + movement.quantity
                   ELSE movement.balance_after - movement.quantity
               END,
               movement.balance_after,
               CASE
                   WHEN movement.movement_type = 'out_sale' THEN -movement.quantity
                   ELSE movement.quantity
               END,
               movement.unit_cost, movement.unit_cost, 0, NULL,
               product.sale_price, product.sale_price, 0, NULL, 0,
               CASE WHEN movement.movement_type = 'out_sale'
                   THEN movement.quantity * product.sale_price ELSE 0 END,
               movement.created_at
        FROM legacy_import_movement_map AS mapping
        JOIN legacy_import_cluster AS cluster
          ON cluster.organization_id = mapping.organization_id
         AND cluster.batch_group = mapping.batch_group
        JOIN stock_movement AS movement ON movement.id = mapping.movement_id
        JOIN product ON product.id = movement.product_id;

        UPDATE stock_movement AS movement
        SET document_id = cluster.document_id
        FROM legacy_import_movement_map AS mapping
        JOIN legacy_import_cluster AS cluster
          ON cluster.organization_id = mapping.organization_id
         AND cluster.batch_group = mapping.batch_group
        WHERE movement.id = mapping.movement_id;
        """
    )

    # Lotes já existentes e registros de PDV/devolução também recebem vínculo
    # obrigatório caso venham de uma base anterior à centralização.
    op.execute(
        """
        INSERT INTO business_document (
            id, organization_id, category, document_type, native_id,
            document_number, title, current_status, priority, description,
            tags, origin_module, responsible_id, payload, issued_at,
            completed_at, created_by_id, created_at, updated_at
        )
        SELECT gen_random_uuid(), batch.organization_id,
               'inventory.import_batch', 'INVENTORY_IMPORT_BATCH', batch.id,
               coalesce(batch.batch_number, 'IMPO-LEG-' || batch.id::text),
               'Lote de importação de estoque', 'PROCESSED', 'MEDIUM',
               batch.notes, '[]'::json, 'INVENTORY', batch.imported_by_id,
               json_build_object(
                   'migration_revision', 'f8g9h0i1j2k3',
                   'filename', batch.filename,
                   'inventory_date', batch.inventory_date
               ), batch.created_at, batch.created_at, batch.imported_by_id,
               batch.created_at, batch.created_at
        FROM inventory_import_batch AS batch
        WHERE batch.document_id IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM business_document AS document
              WHERE document.organization_id = batch.organization_id
                AND document.document_type = 'INVENTORY_IMPORT_BATCH'
                AND document.native_id = batch.id
          );

        UPDATE inventory_import_batch AS batch
        SET document_id = document.id, batch_number = document.document_number
        FROM business_document AS document
        WHERE document.organization_id = batch.organization_id
          AND document.document_type = 'INVENTORY_IMPORT_BATCH'
          AND document.native_id = batch.id;

        INSERT INTO business_document (
            id, organization_id, category, document_type, native_id,
            document_number, title, current_status, priority, description,
            tags, origin_module, responsible_id, payload, issued_at,
            completed_at, created_by_id, created_at, updated_at
        )
        SELECT gen_random_uuid(), sale.organization_id,
               'sales.pos_sale', 'POS_SALE', sale.id,
               'PDV-LEG-' || sale.id::text,
               'Venda de PDV - ' || sale.customer_name,
               upper(sale.status), 'MEDIUM', 'Venda de balcão migrada.',
               '[]'::json, 'SALES', sale.created_by_id,
               json_build_object(
                   'migration_revision', 'f8g9h0i1j2k3',
                   'customer_id', sale.customer_id,
                   'customer_name', sale.customer_name,
                   'net_amount', sale.net_amount,
                   'payment_method', sale.payment_method
               ), sale.created_at,
               CASE WHEN upper(sale.status) IN ('COMPLETED', 'CANCELLED')
                   THEN sale.created_at ELSE NULL END,
               sale.created_by_id, sale.created_at, sale.created_at
        FROM pos_sale AS sale
        WHERE sale.document_id IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM business_document AS document
              WHERE document.organization_id = sale.organization_id
                AND document.document_type = 'POS_SALE'
                AND document.native_id = sale.id
          );

        UPDATE pos_sale AS sale
        SET document_id = document.id
        FROM business_document AS document
        WHERE document.organization_id = sale.organization_id
          AND document.document_type = 'POS_SALE'
          AND document.native_id = sale.id;

        INSERT INTO business_document (
            id, organization_id, category, document_type, native_id,
            document_number, title, current_status, priority, description,
            tags, origin_module, responsible_id, payload, issued_at,
            completed_at, created_by_id, created_at, updated_at
        )
        SELECT gen_random_uuid(), sales_return.organization_id,
               'sales.return', 'SALES_RETURN', sales_return.id,
               'DEV-LEG-' || sales_return.id::text,
               'Devolução - ' || sales_return.customer_name,
               upper(sales_return.status), 'MEDIUM', sales_return.reason,
               '[]'::json, 'SALES', sales_return.created_by_id,
               json_build_object(
                   'migration_revision', 'f8g9h0i1j2k3',
                   'customer_id', sales_return.customer_id,
                   'sales_order_id', sales_return.sales_order_id,
                   'pos_sale_id', sales_return.pos_sale_id,
                   'return_type', sales_return.return_type,
                   'total_amount', sales_return.total_amount
               ), sales_return.created_at,
               CASE WHEN upper(sales_return.status) IN ('COMPLETED', 'REJECTED')
                   THEN sales_return.created_at ELSE NULL END,
               sales_return.created_by_id, sales_return.created_at,
               sales_return.created_at
        FROM sales_return
        WHERE sales_return.document_id IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM business_document AS document
              WHERE document.organization_id = sales_return.organization_id
                AND document.document_type = 'SALES_RETURN'
                AND document.native_id = sales_return.id
          );

        UPDATE sales_return
        SET document_id = document.id
        FROM business_document AS document
        WHERE document.organization_id = sales_return.organization_id
          AND document.document_type = 'SALES_RETURN'
          AND document.native_id = sales_return.id;
        """
    )

    # Ajustes antigos que não pertencem a outro ciclo recebem um documento
    # próprio; isso é a exceção correta para lançamentos avulsos de Kardex.
    op.execute(
        """
        INSERT INTO business_document (
            id, organization_id, category, document_type, native_id,
            document_number, title, current_status, priority, description,
            tags, origin_module, responsible_id, payload, issued_at,
            completed_at, created_by_id, created_at, updated_at
        )
        SELECT gen_random_uuid(), movement.organization_id,
               'inventory.movement', 'STOCK_MOVEMENT', movement.id,
               'MOVE-LEG-' || movement.id::text,
               'Movimentação avulsa de estoque', 'POSTED', 'MEDIUM',
               movement.notes, '[]'::json, 'INVENTORY', movement.created_by_id,
               json_build_object(
                   'migration_revision', 'f8g9h0i1j2k3',
                   'product_id', movement.product_id,
                   'movement_type', movement.movement_type,
                   'quantity', movement.quantity,
                   'balance_after', movement.balance_after
               ), movement.created_at, movement.created_at,
               movement.created_by_id, movement.created_at, movement.created_at
        FROM stock_movement AS movement
        WHERE movement.document_id IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM business_document AS document
              WHERE document.organization_id = movement.organization_id
                AND document.document_type = 'STOCK_MOVEMENT'
                AND document.native_id = movement.id
          );

        UPDATE stock_movement AS movement
        SET document_id = document.id
        FROM business_document AS document
        WHERE movement.document_id IS NULL
          AND document.organization_id = movement.organization_id
          AND document.document_type = 'STOCK_MOVEMENT'
          AND document.native_id = movement.id;

        INSERT INTO document_relation (
            id, organization_id, parent_document_id, child_document_id,
            relation_type, relation_metadata, created_by_id, created_at
        )
        SELECT gen_random_uuid(), sales_return.organization_id,
               coalesce(sales_order.document_id, pos_sale.document_id),
               sales_return.document_id, 'RETURNED_BY',
               json_build_object('migration_revision', 'f8g9h0i1j2k3'),
               sales_return.created_by_id, sales_return.created_at
        FROM sales_return
        LEFT JOIN sales_order
          ON sales_order.id = sales_return.sales_order_id
         AND sales_order.organization_id = sales_return.organization_id
        LEFT JOIN pos_sale
          ON pos_sale.id = sales_return.pos_sale_id
         AND pos_sale.organization_id = sales_return.organization_id
        WHERE coalesce(sales_order.document_id, pos_sale.document_id) IS NOT NULL
        ON CONFLICT ON CONSTRAINT uq_document_relation_edge DO NOTHING;

        INSERT INTO document_event (
            id, organization_id, document_id, event_type, previous_status,
            new_status, event_metadata, idempotency_key, created_by_id,
            created_at
        )
        SELECT gen_random_uuid(), document.organization_id, document.id,
               'CANONICAL_HEADER_MIGRATED', document.current_status,
               document.current_status,
               json_build_object('migration_revision', 'f8g9h0i1j2k3'),
               'migration:f8g9h0i1j2k3:' || document.id::text,
               document.created_by_id, document.updated_at
        FROM business_document AS document
        WHERE document.payload ->> 'migration_revision' = 'f8g9h0i1j2k3'
        ON CONFLICT ON CONSTRAINT uq_document_event_idempotency DO NOTHING;
        """
    )

    # Remove apenas cabeçalhos redundantes de movimentação que ficaram sem
    # dono após a consolidação e que não participam de nenhuma cadeia.
    op.execute(
        """
        CREATE TEMP TABLE redundant_stock_document ON COMMIT DROP AS
        SELECT document.id
        FROM business_document AS document
        WHERE document.document_type = 'STOCK_MOVEMENT'
          AND NOT EXISTS (
              SELECT 1 FROM stock_movement AS movement
              WHERE movement.document_id = document.id
          )
          AND NOT EXISTS (
              SELECT 1 FROM document_relation AS relation
              WHERE relation.parent_document_id = document.id
                 OR relation.child_document_id = document.id
          );

        DELETE FROM document_event
        WHERE document_id IN (SELECT id FROM redundant_stock_document);

        DELETE FROM business_document
        WHERE id IN (SELECT id FROM redundant_stock_document);

        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM stock_movement WHERE document_id IS NULL)
               OR EXISTS (SELECT 1 FROM inventory_import_batch WHERE document_id IS NULL)
               OR EXISTS (SELECT 1 FROM pos_sale WHERE document_id IS NULL)
               OR EXISTS (SELECT 1 FROM sales_return WHERE document_id IS NULL)
            THEN
                RAISE EXCEPTION 'Existem registros de ciclo sem documento canônico.';
            END IF;
        END $$;
        """
    )

    op.alter_column("stock_movement", "document_id", nullable=False)
    op.alter_column("inventory_import_batch", "document_id", nullable=False)
    op.alter_column("pos_sale", "document_id", nullable=False)
    op.alter_column("sales_return", "document_id", nullable=False)

    op.create_foreign_key(
        "fk_stock_movement_document_org",
        "stock_movement",
        "business_document",
        ["document_id", "organization_id"],
        ["id", "organization_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_inventory_import_batch_document_org",
        "inventory_import_batch",
        "business_document",
        ["document_id", "organization_id"],
        ["id", "organization_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_pos_sale_document_org",
        "pos_sale",
        "business_document",
        ["document_id", "organization_id"],
        ["id", "organization_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_sales_return_document_org",
        "sales_return",
        "business_document",
        ["document_id", "organization_id"],
        ["id", "organization_id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_inventory_import_batch_document",
        "inventory_import_batch",
        ["document_id"],
    )
    op.create_unique_constraint("uq_pos_sale_document", "pos_sale", ["document_id"])
    op.create_unique_constraint(
        "uq_sales_return_document", "sales_return", ["document_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_sales_return_document", "sales_return", type_="unique")
    op.drop_constraint("uq_pos_sale_document", "pos_sale", type_="unique")
    op.drop_constraint(
        "uq_inventory_import_batch_document",
        "inventory_import_batch",
        type_="unique",
    )
    op.drop_constraint(
        "fk_sales_return_document_org", "sales_return", type_="foreignkey"
    )
    op.drop_constraint("fk_pos_sale_document_org", "pos_sale", type_="foreignkey")
    op.drop_constraint(
        "fk_inventory_import_batch_document_org",
        "inventory_import_batch",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_stock_movement_document_org", "stock_movement", type_="foreignkey"
    )
    op.alter_column("sales_return", "document_id", nullable=True)
    op.alter_column("pos_sale", "document_id", nullable=True)
    op.alter_column("inventory_import_batch", "document_id", nullable=True)
    op.alter_column("stock_movement", "document_id", nullable=True)
