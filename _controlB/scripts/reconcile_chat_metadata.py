"""Repara apenas metadados locais de UMA conexão, sem consultar/enviar ao WhatsApp.

Padrão dry-run; --apply confirma status aceitos e nomes presentes em mensagens recebidas.
"""

import argparse
import logging
import uuid

logging.disable(logging.CRITICAL)

from sqlalchemy import select

from controlb.db import SessionLocal
from controlb.main import app  # noqa: F401 - registra todos os modelos
from controlb.modules.chat import service
from controlb.modules.chat.models import ChatConnection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connection-id", type=uuid.UUID)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as db:
        if args.list:
            for identifier in db.scalars(select(ChatConnection.id).order_by(ChatConnection.id)):
                print(identifier)
            return
        if not args.connection_id:
            parser.error("Informe --connection-id ou --list.")
        conn = db.get(ChatConnection, args.connection_id)
        if conn is None:
            parser.error("Conexão não encontrada.")
        counts = service.reconcile_local_metadata(db, conn)
        if args.apply:
            db.commit()
        else:
            db.rollback()
        print({"applied": args.apply, **counts})


if __name__ == "__main__":
    main()
