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
    schema = f"chat_migration_{uuid.uuid4().hex}"
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
            with Operations.context(MigrationContext.configure(connection)):
                foundation.upgrade()
                requests.upgrade()
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
                assert inspect(connection).get_table_names(schema=schema) == []
        finally:
            transaction.rollback()
