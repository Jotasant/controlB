"""add document relationship foundation

Revision ID: k6l7m8n9o0p1
Revises: j5k6l7m8n9o0
Create Date: 2026-08-17 18:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "k6l7m8n9o0p1"
down_revision: str | Sequence[str] | None = "j5k6l7m8n9o0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "business_document",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_type", sa.String(length=50), nullable=False),
        sa.Column("native_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_number", sa.String(length=100), nullable=False),
        sa.Column("current_status", sa.String(length=50), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["user.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "document_type",
            "native_id",
            name="uq_business_document_native",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "document_type",
            "document_number",
            name="uq_business_document_number",
        ),
        sa.UniqueConstraint("id", "organization_id", name="uq_business_document_id_org"),
    )
    op.create_index(
        "ix_business_document_org_type",
        "business_document",
        ["organization_id", "document_type"],
        unique=False,
    )

    op.create_table(
        "document_relation",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("child_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relation_type", sa.String(length=50), nullable=False),
        sa.Column(
            "relation_metadata",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "parent_document_id <> child_document_id",
            name="ck_document_relation_not_self",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["user.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["parent_document_id", "organization_id"],
            ["business_document.id", "business_document.organization_id"],
            name="fk_document_relation_parent_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["child_document_id", "organization_id"],
            ["business_document.id", "business_document.organization_id"],
            name="fk_document_relation_child_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "parent_document_id",
            "child_document_id",
            "relation_type",
            name="uq_document_relation_edge",
        ),
    )
    op.create_index(
        "ix_document_relation_org", "document_relation", ["organization_id"], unique=False
    )
    op.create_index(
        "ix_document_relation_parent_document_id",
        "document_relation",
        ["parent_document_id"],
        unique=False,
    )
    op.create_index(
        "ix_document_relation_child_document_id",
        "document_relation",
        ["child_document_id"],
        unique=False,
    )

    op.create_table(
        "document_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("previous_status", sa.String(length=50), nullable=True),
        sa.Column("new_status", sa.String(length=50), nullable=True),
        sa.Column(
            "event_metadata",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=200), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["user.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organization.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["business_document.id", "business_document.organization_id"],
            name="fk_document_event_document_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_document_event_idempotency",
        ),
    )
    op.create_index(
        "ix_document_event_document_created",
        "document_event",
        ["document_id", "created_at"],
        unique=False,
    )

    op.add_column(
        "sales_quote",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "sales_order",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # Registra os documentos legados antes de tornar as novas FKs obrigatórias.
    op.execute(
        """
        INSERT INTO business_document (
            id, organization_id, document_type, native_id, document_number,
            current_status, issued_at, created_by_id, created_at, updated_at
        )
        SELECT
            gen_random_uuid(), organization_id, 'SALES_QUOTE', id, quote_number,
            status, NULL, created_by_id, created_at, updated_at
        FROM sales_quote
        ON CONFLICT ON CONSTRAINT uq_business_document_native DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO business_document (
            id, organization_id, document_type, native_id, document_number,
            current_status, issued_at, created_by_id, created_at, updated_at
        )
        SELECT
            gen_random_uuid(), organization_id, 'SALES_ORDER', id, order_number,
            status, created_at, created_by_id, created_at, updated_at
        FROM sales_order
        ON CONFLICT ON CONSTRAINT uq_business_document_native DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE sales_quote AS quote
        SET document_id = document.id
        FROM business_document AS document
        WHERE document.organization_id = quote.organization_id
          AND document.document_type = 'SALES_QUOTE'
          AND document.native_id = quote.id
        """
    )
    op.execute(
        """
        UPDATE sales_order AS sales_order
        SET document_id = document.id
        FROM business_document AS document
        WHERE document.organization_id = sales_order.organization_id
          AND document.document_type = 'SALES_ORDER'
          AND document.native_id = sales_order.id
        """
    )
    op.execute(
        """
        INSERT INTO document_relation (
            id, organization_id, parent_document_id, child_document_id,
            relation_type, relation_metadata, created_by_id, created_at
        )
        SELECT
            gen_random_uuid(), sales_order.organization_id,
            quote_document.id, order_document.id, 'CONVERTED_TO', '{}'::json,
            sales_order.created_by_id, sales_order.created_at
        FROM sales_order
        JOIN business_document AS order_document
          ON order_document.id = sales_order.document_id
        JOIN business_document AS quote_document
          ON quote_document.organization_id = sales_order.organization_id
         AND quote_document.document_type = 'SALES_QUOTE'
         AND quote_document.native_id = sales_order.sales_quote_id
        WHERE sales_order.sales_quote_id IS NOT NULL
        ON CONFLICT ON CONSTRAINT uq_document_relation_edge DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO document_event (
            id, organization_id, document_id, event_type, previous_status,
            new_status, event_metadata, idempotency_key, created_by_id, created_at
        )
        SELECT
            gen_random_uuid(), organization_id, id, 'REGISTERED_FROM_LEGACY', NULL,
            current_status, '{}'::json, 'legacy-registration:' || id::text,
            created_by_id, created_at
        FROM business_document
        WHERE document_type IN ('SALES_QUOTE', 'SALES_ORDER')
        ON CONFLICT ON CONSTRAINT uq_document_event_idempotency DO NOTHING
        """
    )

    op.alter_column("sales_quote", "document_id", nullable=False)
    op.alter_column("sales_order", "document_id", nullable=False)
    op.create_unique_constraint(
        "uq_sales_quote_document_id", "sales_quote", ["document_id"]
    )
    op.create_unique_constraint(
        "uq_sales_order_document_id", "sales_order", ["document_id"]
    )
    op.create_foreign_key(
        "fk_sales_quote_document_org",
        "sales_quote",
        "business_document",
        ["document_id", "organization_id"],
        ["id", "organization_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_sales_order_document_org",
        "sales_order",
        "business_document",
        ["document_id", "organization_id"],
        ["id", "organization_id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_sales_order_sales_quote", "sales_order", ["sales_quote_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_sales_order_sales_quote", "sales_order", type_="unique")
    op.drop_constraint("fk_sales_order_document_org", "sales_order", type_="foreignkey")
    op.drop_constraint("fk_sales_quote_document_org", "sales_quote", type_="foreignkey")
    op.drop_constraint("uq_sales_order_document_id", "sales_order", type_="unique")
    op.drop_constraint("uq_sales_quote_document_id", "sales_quote", type_="unique")
    op.drop_column("sales_order", "document_id")
    op.drop_column("sales_quote", "document_id")

    op.drop_index("ix_document_event_document_created", table_name="document_event")
    op.drop_table("document_event")
    op.drop_index(
        "ix_document_relation_child_document_id", table_name="document_relation"
    )
    op.drop_index(
        "ix_document_relation_parent_document_id", table_name="document_relation"
    )
    op.drop_index("ix_document_relation_org", table_name="document_relation")
    op.drop_table("document_relation")
    op.drop_index("ix_business_document_org_type", table_name="business_document")
    op.drop_table("business_document")
