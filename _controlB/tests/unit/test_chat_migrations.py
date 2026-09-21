"""Valida as migrations reais num schema transacional do banco efêmero do pytest."""

import importlib.util
import uuid
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text

from controlb.db import engine


def migration(filename):
    path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_chat_migrations_upgrade_and_downgrade():
    foundation = migration("b59d4c8e12f0_create_chat_gateway_tables.py")
    requests = migration("c60e5d9f23a1_chat_message_request_id.py")
    attendance = migration("d71f6ea034b2_chat_teams_attendance.py")
    instance_members = migration("f93b80c256d4_chat_instance_members.py")
    groups = migration("a04c91d367e5_chat_groups_notifications.py")
    media = migration("b15da2e478f6_chat_media_deletion_names.py")
    schema = f"chat_migration_{uuid.uuid4().hex}"
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
            connection.execute(
                text("CREATE TABLE contact (id uuid PRIMARY KEY, organization_id uuid)")
            )
            with Operations.context(MigrationContext.configure(connection)):
                foundation.upgrade()
                requests.upgrade()
                attendance.upgrade()
                instance_members.upgrade()
                groups.upgrade()
                media.upgrade()
                assert "media_blob" in {
                    c["name"]
                    for c in inspect(connection).get_columns("chat_message", schema=schema)
                }
                media.downgrade()
                assert "notify_at" in {
                    c["name"]
                    for c in inspect(connection).get_columns("chat_message", schema=schema)
                }
                groups.downgrade()
                fk = next(
                    item
                    for item in inspect(connection).get_foreign_keys(
                        "chat_connection", schema=schema
                    )
                    if item["constrained_columns"] == ["team_id"]
                )
                assert fk["referred_table"] == "chat_team"
                assert "chat_team_member" in inspect(connection).get_table_names(schema=schema)
                instance_members.downgrade()
                assert "team_id" in {
                    c["name"]
                    for c in inspect(connection).get_columns("chat_message", schema=schema)
                }
                attendance.downgrade()
                columns = inspect(connection).get_columns("chat_message", schema=schema)
                assert "client_request_id" in {column["name"] for column in columns}
                constraints = inspect(connection).get_unique_constraints(
                    "chat_message", schema=schema
                )
                assert any(
                    item["column_names"] == ["organization_id", "client_request_id"]
                    for item in constraints
                )
                requests.downgrade()
                columns = inspect(connection).get_columns("chat_message", schema=schema)
                assert "client_request_id" not in {column["name"] for column in columns}
                foundation.downgrade()
                assert inspect(connection).get_table_names(schema=schema) == ["contact"]
        finally:
            transaction.rollback()


def test_supplier_contact_reference_migration_is_optional_and_reversible():
    reference = migration("e82a7fb145c3_supplier_contact_reference.py")
    schema = f"contact_migration_{uuid.uuid4().hex}"
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
            connection.execute(text("CREATE TABLE contact (id uuid PRIMARY KEY)"))
            connection.execute(text("CREATE TABLE supplier (id uuid PRIMARY KEY)"))
            supplier_id = uuid.uuid4()
            connection.execute(text("INSERT INTO supplier (id) VALUES (:id)"), {"id": supplier_id})
            with Operations.context(MigrationContext.configure(connection)):
                reference.upgrade()
                columns = {
                    column["name"]: column
                    for column in inspect(connection).get_columns("supplier", schema=schema)
                }
                assert columns["contact_id"]["nullable"] is True
                assert connection.scalar(text("SELECT contact_id FROM supplier")) is None
                reference.downgrade()
                assert connection.scalar(text("SELECT id FROM supplier")) == supplier_id
                assert "contact_id" not in {
                    column["name"]
                    for column in inspect(connection).get_columns("supplier", schema=schema)
                }
        finally:
            transaction.rollback()


def test_identity_identifiers_migration_is_additive_and_preserves_audit():
    revision = migration("f304b5c6d7e8_identity_contact_identifiers.py")
    schema = f"identity_migration_{uuid.uuid4().hex}"
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
            connection.execute(text("CREATE TABLE organization (id uuid PRIMARY KEY)"))
            connection.execute(text("CREATE TABLE contact (id uuid PRIMARY KEY)"))
            connection.execute(text("CREATE TABLE customer (id uuid PRIMARY KEY, phone varchar(50))"))
            with Operations.context(MigrationContext.configure(connection)):
                revision.upgrade()
                tables = inspect(connection).get_table_names(schema=schema)
                assert "contact_identifier" in tables and "contact_migration_run" in tables
                assert "phone" in {column["name"] for column in inspect(connection).get_columns("customer", schema=schema)}
                revision.downgrade()
                assert inspect(connection).get_table_names(schema=schema) == tables
        finally:
            transaction.rollback()
