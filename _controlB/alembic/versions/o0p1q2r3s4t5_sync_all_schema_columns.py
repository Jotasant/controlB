"""sync all schema columns for customers, contacts, sales and documents

Revision ID: o0p1q2r3s4t5
Revises: n9o0p1q2r3s4
Create Date: 2026-08-23 12:46:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "o0p1q2r3s4t5"
down_revision: str | Sequence[str] | None = "n9o0p1q2r3s4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Atualizações na tabela CUSTOMER (Módulo Sales)
    op.add_column(
        "customer",
        sa.Column("origin_module", sa.String(length=50), server_default="SALES", nullable=False)
    )

    # 2. Atualizações nas tabelas SALES_QUOTE e SALES_ORDER
    op.add_column(
        "sales_quote",
        sa.Column("cancellation_reason", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "sales_order",
        sa.Column("cancellation_reason", sa.String(length=255), nullable=True)
    )

    # 3. Atualizações na tabela CONTACT (Módulo Identity - Padrão Odoo res.partner)
    op.add_column(
        "contact",
        sa.Column("name", sa.String(length=255), nullable=True)
    )
    # Copia dados existentes de full_name para name
    op.execute("UPDATE contact SET name = full_name WHERE name IS NULL AND full_name IS NOT NULL")
    op.execute("UPDATE contact SET name = 'Contato Sem Nome' WHERE name IS NULL")
    op.alter_column("contact", "name", nullable=False)
    op.create_index("ix_contact_name", "contact", ["name"])

    op.add_column(
        "contact",
        sa.Column("person_type", sa.String(length=10), server_default="PJ", nullable=False)
    )
    op.create_index("ix_contact_person_type", "contact", ["person_type"])

    op.add_column("contact", sa.Column("trade_name", sa.String(length=255), nullable=True))
    op.add_column("contact", sa.Column("state_registration", sa.String(length=50), nullable=True))
    op.add_column("contact", sa.Column("address_street", sa.String(length=255), nullable=True))
    op.add_column("contact", sa.Column("address_number", sa.String(length=50), nullable=True))
    op.add_column("contact", sa.Column("address_neighborhood", sa.String(length=100), nullable=True))
    op.add_column("contact", sa.Column("address_city", sa.String(length=100), nullable=True))
    op.add_column("contact", sa.Column("address_state", sa.String(length=10), nullable=True))
    op.add_column("contact", sa.Column("address_zip_code", sa.String(length=20), nullable=True))

    op.add_column(
        "contact",
        sa.Column("is_customer", sa.Boolean(), server_default=sa.text("false"), nullable=False)
    )
    op.create_index("ix_contact_is_customer", "contact", ["is_customer"])

    op.add_column(
        "contact",
        sa.Column("is_supplier", sa.Boolean(), server_default=sa.text("false"), nullable=False)
    )
    op.create_index("ix_contact_is_supplier", "contact", ["is_supplier"])

    op.add_column(
        "contact",
        sa.Column("is_carrier", sa.Boolean(), server_default=sa.text("false"), nullable=False)
    )
    op.create_index("ix_contact_is_carrier", "contact", ["is_carrier"])

    op.add_column(
        "contact",
        sa.Column("credit_limit", sa.Numeric(precision=14, scale=2), server_default="0.00", nullable=False)
    )
    op.add_column(
        "contact",
        sa.Column("origin_module", sa.String(length=50), server_default="IDENTITY", nullable=False)
    )
    op.create_index("ix_contact_origin_module", "contact", ["origin_module"])

    # 4. Atualizações na tabela BUSINESS_DOCUMENT (Módulo Documents)
    op.add_column(
        "business_document",
        sa.Column("category", sa.String(length=100), server_default="generic", nullable=False)
    )
    op.create_index("ix_business_document_org_cat", "business_document", ["organization_id", "category"])

    op.add_column(
        "business_document",
        sa.Column("title", sa.String(length=255), server_default="", nullable=False)
    )
    op.add_column(
        "business_document",
        sa.Column("priority", sa.String(length=20), server_default="MEDIUM", nullable=False)
    )
    op.add_column("business_document", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "business_document",
        sa.Column("tags", postgresql.JSON(astext_type=sa.Text()), server_default=sa.text("'[]'::json"), nullable=False)
    )
    op.add_column(
        "business_document",
        sa.Column("origin_module", sa.String(length=50), server_default="DOCUMENTS", nullable=False)
    )
    op.add_column(
        "business_document",
        sa.Column("responsible_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_business_document_responsible",
        "business_document",
        "user",
        ["responsible_id"],
        ["id"],
        ondelete="SET NULL"
    )
    op.add_column(
        "business_document",
        sa.Column("payload", postgresql.JSON(astext_type=sa.Text()), server_default=sa.text("'{}'::json"), nullable=False)
    )
    op.add_column("business_document", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))

    # 5. Criação da tabela DOCUMENT_SEQUENCE (Módulo Documents)
    op.create_table(
        "document_sequence",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("current_value", sa.Integer(), server_default="0", nullable=False),
        sa.Column("prefix", sa.String(length=20), server_default="DOC", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "category", "year", name="uq_document_sequence_org_cat_year")
    )
    op.create_index("ix_document_sequence_lookup", "document_sequence", ["organization_id", "category", "year"])


def downgrade() -> None:
    op.drop_index("ix_document_sequence_lookup", table_name="document_sequence")
    op.drop_table("document_sequence")

    op.drop_constraint("fk_business_document_responsible", "business_document", type_="foreignkey")
    op.drop_column("business_document", "completed_at")
    op.drop_column("business_document", "payload")
    op.drop_column("business_document", "responsible_id")
    op.drop_column("business_document", "origin_module")
    op.drop_column("business_document", "tags")
    op.drop_column("business_document", "description")
    op.drop_column("business_document", "priority")
    op.drop_column("business_document", "title")
    op.drop_index("ix_business_document_org_cat", table_name="business_document")
    op.drop_column("business_document", "category")

    op.drop_index("ix_contact_origin_module", table_name="contact")
    op.drop_column("contact", "origin_module")
    op.drop_column("contact", "credit_limit")
    op.drop_index("ix_contact_is_carrier", table_name="contact")
    op.drop_column("contact", "is_carrier")
    op.drop_index("ix_contact_is_supplier", table_name="contact")
    op.drop_column("contact", "is_supplier")
    op.drop_index("ix_contact_is_customer", table_name="contact")
    op.drop_column("contact", "is_customer")
    op.drop_column("contact", "address_zip_code")
    op.drop_column("contact", "address_state")
    op.drop_column("contact", "address_city")
    op.drop_column("contact", "address_neighborhood")
    op.drop_column("contact", "address_number")
    op.drop_column("contact", "address_street")
    op.drop_column("contact", "state_registration")
    op.drop_column("contact", "trade_name")
    op.drop_index("ix_contact_person_type", table_name="contact")
    op.drop_column("contact", "person_type")
    op.drop_index("ix_contact_name", table_name="contact")
    op.drop_column("contact", "name")

    op.drop_column("sales_order", "cancellation_reason")
    op.drop_column("sales_quote", "cancellation_reason")
    op.drop_column("customer", "origin_module")
