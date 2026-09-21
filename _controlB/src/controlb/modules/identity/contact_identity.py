"""Organization-scoped contact identifiers shared by CRUD, imports and WhatsApp."""

import hashlib
import re
import uuid

from fastapi import HTTPException
from sqlalchemy import func, or_, select, text, tuple_

from .models import Contact, ContactIdentifier


def normalize_phone(value, country="BR"):
    if not value or not str(value).strip():
        return None
    raw = str(value).strip()
    if re.search(r"[a-zA-Z@]", raw):
        raise ValueError("Telefone inválido; identificadores do provedor não são telefones.")
    digits = re.sub(r"\D", "", raw)
    international = raw.startswith(("+", "00"))
    if raw.startswith("00"):
        digits = digits[2:]
    if not international and country == "BR" and len(digits) in (10, 11):
        digits = "55" + digits
    elif not international and not (
        country == "BR" and digits.startswith("55") and len(digits) in (12, 13)
    ):
        raise ValueError("Informe o telefone internacional com + e código do país.")
    if not re.fullmatch(r"[1-9][0-9]{7,14}", digits):
        raise ValueError("Telefone inválido; informe DDI e DDD.")
    return digits


def identifiers(phone=None, mobile=None, email=None, *, country="BR"):
    result = {}
    for value in (phone, mobile):
        normalized = normalize_phone(value, country)
        if normalized:
            result[("PHONE", normalized)] = str(value).strip()
    if email and str(email).strip():
        normalized = str(email).strip().casefold()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized):
            raise ValueError("E-mail inválido.")
        result[("EMAIL", normalized)] = str(email).strip()
    return result


def lock_contacts(db, organization_id):
    # Same transaction lock for every writer, not one lock per WhatsApp instance.
    key = int.from_bytes(
        hashlib.sha256(uuid.uuid5(organization_id, "whatsapp-contacts").bytes).digest()[:8],
        signed=True,
    )
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


def contact_keys(contact):
    result = {}
    for value in (contact.phone, contact.mobile):
        try:
            result.update(identifiers(phone=value))
        except ValueError:
            pass  # Legacy invalid values are reported by migration, never guessed.
    if contact.normalized_phone:
        result[("PHONE", contact.normalized_phone)] = contact.normalized_phone
    if contact.email:
        result[("EMAIL", contact.email.strip().casefold())] = contact.email
    return result


def find_contact(db, organization_id, keys):
    """Read-only lookup, also covering legacy contacts not yet indexed."""
    if not keys:
        return None
    candidates = {}
    phones = {value for kind, value in keys if kind == "PHONE"}
    emails = {value for kind, value in keys if kind == "EMAIL"}
    # SQL narrows the legacy fallback; Python validates national/international ambiguity.
    variants = phones | {"00" + phone for phone in phones} | {
        phone[2:] for phone in phones if phone.startswith("55") and len(phone) in (12, 13)
    }
    legacy = select(Contact).where(
        Contact.organization_id == organization_id,
        or_(
            Contact.normalized_phone.in_(phones),
            func.lower(func.trim(Contact.email)).in_(emails),
            func.regexp_replace(Contact.phone, r"\D", "", "g").in_(variants),
            func.regexp_replace(Contact.mobile, r"\D", "", "g").in_(variants),
        ),
    )
    for contact in db.scalars(legacy):
        if set(contact_keys(contact)) & set(keys):
            candidates[contact.id] = contact
    indexed = (
        select(Contact)
        .join(ContactIdentifier, ContactIdentifier.contact_id == Contact.id)
        .where(
            Contact.organization_id == organization_id,
            ContactIdentifier.organization_id == organization_id,
            tuple_(ContactIdentifier.kind, ContactIdentifier.value).in_(list(keys)),
        )
    )
    for contact in db.scalars(indexed):
        candidates[contact.id] = contact
    if len(candidates) > 1:
        raise HTTPException(
            409, "Telefone/e-mail apontam para contatos diferentes. Revise no Identity."
        )
    return next(iter(candidates.values()), None)


def claim_identifiers(db, contact, keys):
    lock_contacts(db, contact.organization_id)
    existing = find_contact(db, contact.organization_id, keys)
    if existing and existing.id != contact.id:
        raise HTTPException(409, f"Contato já cadastrado no Identity: {existing.id}.")
    db.flush()
    for (kind, value), original in keys.items():
        identifier = db.scalar(
            select(ContactIdentifier).where(
                ContactIdentifier.organization_id == contact.organization_id,
                ContactIdentifier.kind == kind,
                ContactIdentifier.value == value,
            )
        )
        if identifier is None:
            db.add(
                ContactIdentifier(
                    organization_id=contact.organization_id,
                    contact_id=contact.id,
                    kind=kind,
                    value=value,
                    original_value=original,
                )
            )
    db.flush()


def validate_link(db, organization_id, contact_id):
    if contact_id is None:
        return
    if not db.scalar(
        select(Contact.id).where(
            Contact.id == contact_id, Contact.organization_id == organization_id
        )
    ):
        raise HTTPException(
            422, "Contato não pertence à organização. Selecione um contato do Identity."
        )


def reject_legacy_fields(payload, fields):
    if any(getattr(payload, key, None) not in (None, "") for key in fields):
        raise HTTPException(
            422,
            "Edite os dados do contato no Identity e informe somente contact_id neste cadastro.",
        )


def contact_response(value, fields, mapping):
    """Keep response compatibility while never reading deprecated commercial columns."""
    if isinstance(value, dict):
        return value
    result = {field: getattr(value, field, None) for field in fields}
    contact = getattr(value, "identity_contact", None)
    if contact and contact.organization_id != value.organization_id:
        contact = None
    for field, source in mapping.items():
        result[field] = getattr(contact, source, None) if contact else None
    return result
