"""Limpeza explícita de histórico descartável de UMA conexão ainda sem equipe.

Por padrão apenas conta os registros. --execute aplica a exclusão irreversível
localmente; não remove a conexão nem acessa o provedor WhatsApp.
"""

import argparse
import hashlib
import json
import uuid

from sqlalchemy import text

from controlb.db import engine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connection-id", required=True, type=uuid.UUID)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    engine.echo = False
    params = {"id": args.connection_id}
    with engine.begin() as db:
        key = int.from_bytes(hashlib.sha256(args.connection_id.bytes).digest()[:8], signed=True)
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
        connection = (
            db.execute(
                text("SELECT id, team_id FROM chat_connection WHERE id=:id FOR UPDATE"), params
            )
            .mappings()
            .one_or_none()
        )
        if connection is None or connection["team_id"] is not None:
            raise SystemExit("Limpeza recusada: a conexão deve existir e ainda não ter equipe.")
        assigned = db.scalar(
            text("""
            SELECT count(*) FROM chat_conversation v
            LEFT JOIN chat_message m ON m.conversation_id=v.id
            WHERE v.connection_id=:id AND (v.team_id IS NOT NULL OR m.team_id IS NOT NULL)
        """),
            params,
        )
        if assigned:
            raise SystemExit("Limpeza recusada: existe histórico já atribuído a uma equipe.")
        counts = dict(
            db.execute(
                text("""
            SELECT
              (SELECT count(*) FROM chat_conversation WHERE connection_id=:id) AS conversations,
              (SELECT count(*) FROM chat_message m JOIN chat_conversation v ON v.id=m.conversation_id
                 WHERE v.connection_id=:id) AS messages,
              (SELECT count(*) FROM chat_webhook_event WHERE connection_id=:id) AS webhook_events,
              (SELECT count(*) FROM chat_conversation_link l JOIN chat_conversation v ON v.id=l.conversation_id
                 WHERE v.connection_id=:id) AS document_links
        """),
                params,
            )
            .mappings()
            .one()
        )
        if args.execute:
            db.execute(text("DELETE FROM chat_webhook_event WHERE connection_id=:id"), params)
            # Mensagens e vínculos são removidos pelo FK ON DELETE CASCADE.
            db.execute(text("DELETE FROM chat_conversation WHERE connection_id=:id"), params)
            db.execute(
                text("""
                UPDATE chat_connection SET sync_checkpoint_at=now(), sync_started_at=NULL,
                  sync_page=1, recovery_pending=false WHERE id=:id
            """),
                params,
            )
    print(json.dumps({"connection_id": str(args.connection_id), "deleted": args.execute, **counts}))


if __name__ == "__main__":
    main()
