"""Non-destructive, per-organization migration. Default mode is a rolled-back preview.

Run with python -m controlb.modules.identity.contact_migration --help.
Keep the application in maintenance mode during apply/rollback.
"""

import argparse
import hashlib
import json
import uuid
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select

from .contact_identity import claim_identifiers, find_contact, identifiers, lock_contacts
from .models import Contact, ContactIdentifier, ContactMigrationRun, Organization


def snapshot(row):
    def encode(value):
        return str(value) if isinstance(value, (uuid.UUID, datetime, date, Decimal)) else value

    return {column.key: encode(getattr(row, column.key)) for column in row.__table__.columns}


def migrate(db, organization_id, backup_sha256, *, preview=True):
    from controlb.modules.purchasing.models import Supplier
    from controlb.modules.sales.models import Customer

    if db.get(Organization, organization_id) is None:
        raise ValueError("Organização não encontrada.")
    lock_contacts(db, organization_id)
    # SAVEPOINT ensures a failed migration or preview never leaves partial changes.
    with db.begin_nested() as transaction:
        contacts_before = {
            str(c.id): snapshot(c)
            for c in db.scalars(
                select(Contact).where(Contact.organization_id == organization_id).with_for_update()
            )
        }
        identifiers_before = {
            str(i.id)
            for i in db.scalars(
                select(ContactIdentifier).where(
                    ContactIdentifier.organization_id == organization_id
                )
            )
        }
        for contact_id in contacts_before:
            contact = db.get(Contact, uuid.UUID(contact_id))
            keys = identifiers(contact.phone, contact.mobile, contact.email)
            if contact.normalized_phone:
                keys[("PHONE", contact.normalized_phone)] = contact.normalized_phone
            claim_identifiers(db, contact, keys)
        links = []
        for model in (Customer, Supplier):
            for row in db.scalars(
                select(model).where(model.organization_id == organization_id).with_for_update()
            ):
                values = {
                    "phone": row.phone,
                    "email": row.email,
                    "mobile": getattr(row, "secondary_phone", None),
                    "position": getattr(row, "contact_role", None),
                }
                keys = identifiers(
                    values["phone"],
                    values["mobile"],
                    values["email"],
                    country=getattr(row, "country", None) or "BR",
                )
                matched = find_contact(db, organization_id, keys)
                linked = db.get(Contact, row.contact_id) if row.contact_id else None
                if linked and linked.organization_id != organization_id:
                    raise ValueError(
                        f"{model.__tablename__}/{row.id}: vínculo fora da organização."
                    )
                if linked and matched and linked.id != matched.id:
                    raise ValueError(
                        f"{model.__tablename__}/{row.id}: vínculo e telefone/e-mail conflitantes."
                    )
                contact = linked or matched
                representative = getattr(row, "contact_name", None)
                if contact is None and not keys and not representative and not values["position"]:
                    continue
                before = snapshot(row)
                if contact is None:
                    name = representative or row.name
                    if len(name) > 255:
                        raise ValueError(
                            f"{row.id}: nome excede o limite do Identity; resolver antes de migrar."
                        )
                    contact = Contact(
                        organization_id=organization_id,
                        name=name,
                        person_type="PF" if representative else getattr(row, "person_type", "PJ"),
                        name_manually_set=True,
                        origin_module="IDENTITY_MIGRATION",
                    )
                    db.add(contact)
                    db.flush()
                for field, value in values.items():
                    if value and not getattr(contact, field):
                        limit = {"phone": 50, "mobile": 50, "email": 255, "position": 100}[field]
                        if len(value) > limit:
                            raise ValueError(
                                f"{row.id}: {field} excede o limite do Identity; nenhum valor foi truncado."
                            )
                        setattr(contact, field, value)
                if not contact.normalized_phone:
                    contact.normalized_phone = next(
                        (value for kind, value in keys if kind == "PHONE"), None
                    )
                claim_identifiers(db, contact, keys)
                row.contact_id = contact.id
                db.flush()
                links.append(
                    {
                        "table": model.__tablename__,
                        "id": str(row.id),
                        "before": before,
                        "after": snapshot(row),
                    }
                )
        contacts_after = {
            str(c.id): snapshot(c)
            for c in db.scalars(select(Contact).where(Contact.organization_id == organization_id))
        }
        new_identifiers = [
            str(i.id)
            for i in db.scalars(
                select(ContactIdentifier).where(
                    ContactIdentifier.organization_id == organization_id
                )
            )
            if str(i.id) not in identifiers_before
        ]
        changed = {
            key: value for key, value in contacts_after.items() if contacts_before.get(key) != value
        }
        journal = {
            "links": [item for item in links if item["before"] != item["after"]],
            "contacts_before": {
                key: contacts_before[key] for key in changed if key in contacts_before
            },
            "contacts_after": changed,
            "new_identifiers": new_identifiers,
            # Preserve source values even when an existing canonical name/email differs.
            "sources": links,
        }
        changed_any = bool(journal["links"] or changed or new_identifiers)
        run = None
        if changed_any and not preview:
            if len(backup_sha256) != 64:
                raise ValueError("Backup verificado é obrigatório.")
            run = ContactMigrationRun(
                organization_id=organization_id,
                backup_sha256=backup_sha256,
                journal=journal,
                status="APPLIED",
            )
            db.add(run)
            db.flush()
        result = {
            "run_id": str(run.id) if run else None,
            "preview": preview,
            "linked": len(journal["links"]),
            "created": len(set(changed) - set(contacts_before)),
            "updated": len(set(changed) & set(contacts_before)),
            "identifiers": len(new_identifiers),
        }
        if preview:
            transaction.rollback()
        return result


def rollback(db, run_id, *, preview=True):
    from controlb.modules.chat.models import ChatConversation
    from controlb.modules.crm.models import Lead
    from controlb.modules.purchasing.models import Supplier
    from controlb.modules.sales.models import Customer

    run = db.get(ContactMigrationRun, run_id)
    if not run:
        raise ValueError("Execução não encontrada.")
    lock_contacts(db, run.organization_id)
    db.refresh(run, with_for_update=True)
    if run.status == "REVERTED":
        return {"run_id": str(run.id), "status": "REVERTED"}
    models = {"customer": Customer, "supplier": Supplier}
    with db.begin_nested() as transaction:
        for item in run.journal["links"]:
            row = db.get(models[item["table"]], uuid.UUID(item["id"]))
            if row is None or snapshot(row) != item["after"]:
                raise ValueError(
                    "Cadastro comercial alterado após a migração; reversão automática bloqueada."
                )
        for contact_id, after in run.journal["contacts_after"].items():
            contact = db.get(Contact, uuid.UUID(contact_id))
            if contact is None or snapshot(contact) != after:
                raise ValueError("Contato alterado após a migração; reversão automática bloqueada.")
        for item in run.journal["links"]:
            row = db.get(models[item["table"]], uuid.UUID(item["id"]))
            old = item["before"]["contact_id"]
            row.contact_id = uuid.UUID(old) if old else None
        db.flush()
        for contact_id, after in run.journal["contacts_after"].items():
            contact = db.get(Contact, uuid.UUID(contact_id))
            before = run.journal["contacts_before"].get(contact_id)
            if before:
                for key in ("phone", "email", "mobile", "position", "normalized_phone"):
                    setattr(contact, key, before[key])
            else:
                for model in (Customer, Supplier, ChatConversation, Lead):
                    if db.scalar(select(model.id).where(model.contact_id == contact.id).limit(1)):
                        raise ValueError(
                            "Contato criado já está em uso; reversão automática bloqueada."
                        )
                contact.is_active = False  # Preserve identifiers and provenance; never DELETE.
        run.status = "REVERTED"
        db.flush()
        if preview:
            transaction.rollback()
        return {"run_id": str(run_id), "status": "PREVIEW" if preview else "REVERTED"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--organization", type=uuid.UUID)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path, help="Existing pg_dump custom-format backup")
    parser.add_argument(
        "--restore-verified",
        action="store_true",
        help="Confirm backup was restored in an isolated database",
    )
    parser.add_argument(
        "--rollback", type=uuid.UUID, help="Migration run ID; preview unless --apply"
    )
    args = parser.parse_args()
    if not args.organization and not args.rollback:
        parser.error("--organization ou --rollback é obrigatório.")
    digest = ""
    if args.apply:
        if not args.backup or not args.backup.is_file() or not args.restore_verified:
            parser.error("--apply exige --backup e --restore-verified.")
        with args.backup.open("rb") as backup:
            if backup.read(5) != b"PGDMP":
                parser.error("Backup deve ser pg_dump em formato custom (-Fc).")
            backup.seek(0)
            digest = hashlib.file_digest(backup, "sha256").hexdigest()
    # Register all ORM relationship targets without starting workers or touching data.
    from controlb import main as application  # noqa: F401
    from controlb.db import SessionLocal

    try:
        with SessionLocal() as db:
            result = (
                rollback(db, args.rollback, preview=not args.apply)
                if args.rollback
                else migrate(db, args.organization, digest, preview=not args.apply)
            )
            if args.apply:
                db.commit()
            print(json.dumps(result, ensure_ascii=False))
    except (ValueError, HTTPException) as exc:
        parser.exit(1, f"Migração bloqueada, sem alterações: {getattr(exc, 'detail', str(exc))}\n")


if __name__ == "__main__":
    main()
