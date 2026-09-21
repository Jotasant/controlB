"""Resolve nomes de grupos já cadastrados. Sem criar grupos ou enviar mensagens."""

import argparse
import asyncio
import logging
import uuid

logging.disable(logging.CRITICAL)

from sqlalchemy import select

from controlb.db import SessionLocal
from controlb.main import app  # noqa: F401 - registra modelos
from controlb.modules.chat import repository as repo
from controlb.modules.chat import service
from controlb.modules.chat.connectors.base import ConnectorError
from controlb.modules.chat.models import ChatConnection, ChatConversation


async def run(identifier, apply):
    with SessionLocal() as db:
        conn = db.get(ChatConnection, identifier)
        if not conn or not conn.is_active:
            raise SystemExit("Conexão não encontrada ou inativa.")
        adapter = service.connector_for(conn, network=True)
        routing = (conn.base_url, conn.external_instance_id, conn.instance_phone)
        groups = list(
            db.scalars(
                select(ChatConversation).where(
                    ChatConversation.connection_id == conn.id,
                    ChatConversation.organization_id == conn.organization_id,
                    ChatConversation.is_group.is_(True),
                    ChatConversation.deleted_at.is_(None),
                )
            )
        )
        changed, unavailable = 0, 0
        names = {}
        try:
            for group in groups:
                try:
                    name = await asyncio.wait_for(
                        adapter.fetch_group_name(group.external_chat_id), timeout=8
                    )
                except (ConnectorError, TimeoutError):
                    name = None
                if name:
                    names[group.id] = name
                else:
                    unavailable += 1
        finally:
            await adapter.aclose()
        repo.lock_connection(db, conn.id)
        db.refresh(conn)
        if routing != (conn.base_url, conn.external_instance_id, conn.instance_phone):
            raise SystemExit("A conexão mudou durante a consulta. Nada foi alterado.")
        for group in groups:
            db.refresh(group)
            name = names.get(group.id)
            if name and not group.deleted_at and name != group.display_name:
                group.display_name = name
                changed += 1
        if apply:
            db.commit()
        else:
            db.rollback()
        print(
            {
                "applied": apply,
                "updated": changed,
                "unavailable": unavailable,
                "checked": len(groups),
            }
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connection-id", type=uuid.UUID, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.connection_id, args.apply))
