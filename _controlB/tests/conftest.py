"""Configuração comum e isolada da suíte de testes.

Cada processo do pytest recebe um banco PostgreSQL efêmero. Isso é
intencionalmente configurado antes de importar ``controlb.db``: vários testes
legados abrem ``SessionLocal`` diretamente e fazem ``commit()``, portanto uma
transação externa não seria suficiente para proteger o banco de desenvolvimento.
"""

from __future__ import annotations

import atexit
import os
import re
import uuid

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

from controlb.config import Settings


def _postgres_driver_url(url: URL, database: str) -> URL:
    """Mantém credenciais/host e seleciona um banco PostgreSQL específico."""

    driver = "postgresql+psycopg" if url.drivername.startswith("postgresql") else url.drivername
    return url.set(drivername=driver, database=database)


_source_url = make_url(Settings().database_url)
if not _source_url.drivername.startswith("postgresql"):
    raise RuntimeError("A suíte exige PostgreSQL para criar um banco de testes isolado.")

_test_database = f"controlb_pytest_{os.getpid()}_{uuid.uuid4().hex[:8]}"
if not re.fullmatch(r"[a-z0-9_]+", _test_database):
    raise RuntimeError("Nome de banco de testes inválido.")

_maintenance_url = _postgres_driver_url(_source_url, "postgres")
_maintenance_engine = create_engine(_maintenance_url, isolation_level="AUTOCOMMIT")

with _maintenance_engine.connect() as connection:
    connection.execute(text(f'CREATE DATABASE "{_test_database}"'))

_test_url = _postgres_driver_url(_source_url, _test_database)
os.environ["DATABASE_URL"] = _test_url.render_as_string(hide_password=False)

# As importações abaixo precisam acontecer somente depois de DATABASE_URL apontar
# para o banco efêmero. Elas também registram o catálogo ORM completo, tornando cada
# arquivo de teste independente da ordem de coleta.
from controlb.db import Base, engine  # noqa: E402
from controlb.modules.billing import models as billing_models  # noqa: E402
from controlb.modules.crm import models as crm_models  # noqa: E402
from controlb.modules.documents import models as document_models  # noqa: E402
from controlb.modules.finance import models as finance_models  # noqa: E402
from controlb.modules.identity import models as identity_models  # noqa: E402
from controlb.modules.inventory import models as inventory_models  # noqa: E402
from controlb.modules.purchasing import models as purchasing_models  # noqa: E402
from controlb.modules.sales import models as sales_models  # noqa: E402

_MODEL_MODULES = (
    identity_models,
    document_models,
    inventory_models,
    purchasing_models,
    finance_models,
    crm_models,
    sales_models,
    billing_models,
)

Base.metadata.create_all(engine)

_cleaned_up = False


def _drop_test_database() -> None:
    global _cleaned_up
    if _cleaned_up:
        return
    _cleaned_up = True

    engine.dispose()
    with _maintenance_engine.connect() as connection:
        connection.execute(
            text(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = :database_name
                  AND pid <> pg_backend_pid()
                """
            ),
            {"database_name": _test_database},
        )
        connection.execute(text(f'DROP DATABASE IF EXISTS "{_test_database}"'))
    _maintenance_engine.dispose()


def pytest_sessionfinish(session, exitstatus) -> None:  # noqa: ARG001
    _drop_test_database()


atexit.register(_drop_test_database)
