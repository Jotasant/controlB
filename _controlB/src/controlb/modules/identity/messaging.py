"""Contatos genéricos e origens; clientes/fornecedores continuam independentes."""

import re
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from controlb.db import get_db
from controlb.modules.chat import repository as chat_repo
from controlb.modules.chat.models import ChatConnection, ChatConversation
from controlb.modules.identity.models import Contact, ContactOrigin, User
from controlb.modules.identity.schemas import ContactResponse
from controlb.modules.identity.security import get_current_user
from controlb.modules.purchasing.models import Supplier
from controlb.modules.sales.models import Customer

router = APIRouter(prefix="/identity", tags=["Contatos"])
DB = Annotated[Session, Depends(get_db)]
Authenticated = Annotated[User, Depends(get_current_user)]


def upsert_whatsapp_contact(db, conn, incoming):
    # Only an actual inbound direct message may automatically create an Identity contact.
    if incoming.is_group or incoming.direction != "INBOUND":
        return None
    from .contact_identity import lock_contacts, find_contact, claim_identifiers
    lock_contacts(db, conn.organization_id)
    phone = incoming.remote_phone
    keys = {("PHONE", phone): phone}
    contact = find_contact(db, conn.organization_id, keys)
    inbound_name = incoming.contact_name or (
        incoming.sender_name.strip()
        if incoming.direction == "INBOUND" and incoming.sender_name
        else None
    )
    if contact is None:
        contact = Contact(
            organization_id=conn.organization_id,
            person_type="PF",
            name=inbound_name or phone,
            phone=phone,
            normalized_phone=phone,
            full_name=inbound_name[:150] if inbound_name else None,
            origin_module="CHAT",
        )
        db.add(contact)
    if not contact.normalized_phone:
        contact.normalized_phone = phone
    claim_identifiers(db, contact, keys)
    if inbound_name and (
        not contact.full_name
        or contact.last_contact_at is None
        or incoming.occurred_at >= contact.last_contact_at
    ):
        # Nome manual distinto do nome WhatsApp não é sobrescrito.
        update_whatsapp_name(contact, phone, inbound_name)
    contact.first_contact_at = min(
        contact.first_contact_at or incoming.occurred_at, incoming.occurred_at
    )
    contact.last_contact_at = max(
        contact.last_contact_at or incoming.occurred_at, incoming.occurred_at
    )
    db.flush()
    return contact


def update_whatsapp_name(contact, phone, name, *, force=False):
    numeric_name = re.sub(r"\D", "", contact.name or "") == phone and not re.search(
        r"[a-zA-Z]", contact.name or ""
    )
    if force or (
        not contact.name_manually_set
        and (
            numeric_name or (contact.origin_module == "CHAT" and contact.name[:150] == contact.full_name)
        )
    ):
        contact.name = name
    contact.full_name = name[:150]


class OriginCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    channel_type: str = Field(default="OTHER", max_length=50)
    is_active: bool = True


class OriginUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    channel_type: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None


class ContactLinks(BaseModel):
    customer_id: uuid.UUID | None = None
    supplier_id: uuid.UUID | None = None


DEFAULT_ORIGINS = [
    ("WhatsApp", "Atendimento via WhatsApp", "WHATSAPP"),
    ("Site / Formulário", "Formulário no site ou landing page", "WEBSITE"),
    ("Indicação", "Indicação de cliente ou parceiro", "REFERRAL"),
    ("Contato Telefônico / Ligação", "Contato ativo ou receptivo por telefone", "PHONE"),
    ("Instagram", "Direct ou post no Instagram", "SOCIAL"),
    ("Campanha", "Campanha de marketing ou anúncios", "CAMPAIGN"),
    ("Prospecção Ativa", "Outbound / prospecção ativa de vendas", "OUTBOUND"),
    ("Evento / Feira", "Evento presencial, feira ou congresso", "EVENT"),
    ("Outro", "Outro canal de entrada", "OTHER"),
]


def ensure_default_origins(db: Session, organization_id: uuid.UUID) -> None:
    """Garante que as origens canônicas padrão existam para a organização de forma idempotente."""
    chat_repo.lock_connection(db, uuid.uuid5(organization_id, "contact-origins"))
    existing_rows = db.scalars(
        select(ContactOrigin).where(ContactOrigin.organization_id == organization_id)
    ).all()
    existing_map = {row.name.strip().casefold(): row for row in existing_rows}

    for def_name, def_desc, def_channel in DEFAULT_ORIGINS:
        key = def_name.strip().casefold()
        if key in existing_map:
            existing = existing_map[key]
            if existing.name == "whatsapp" and def_name == "WhatsApp":
                existing.name = "WhatsApp"
            if existing.channel_type == "OTHER" and def_channel != "OTHER":
                existing.channel_type = def_channel
            continue

        new_origin = ContactOrigin(
            organization_id=organization_id,
            name=def_name,
            description=def_desc,
            channel_type=def_channel,
            is_active=True,
        )
        db.add(new_origin)

    db.flush()


@router.get("/contact-origins")
def origins(db: DB, user: Authenticated):
    ensure_default_origins(db, user.organization_id)
    db.commit()
    return [
        dict(row._mapping)
        for row in db.execute(
            select(
                ContactOrigin.id,
                ContactOrigin.name,
                ContactOrigin.description,
                ContactOrigin.channel_type,
                ContactOrigin.is_active,
            )
            .where(ContactOrigin.organization_id == user.organization_id)
            .order_by(ContactOrigin.name)
        )
    ]


@router.post("/contact-origins")
def create_origin(data: OriginCreate, db: DB, user: Authenticated):
    obj = get_or_create_origin(
        db,
        user.organization_id,
        data.name,
        description=data.description,
        channel_type=data.channel_type,
        is_active=data.is_active,
    )
    return {
        "id": obj.id,
        "name": obj.name,
        "description": obj.description,
        "channel_type": obj.channel_type,
        "is_active": obj.is_active,
    }


@router.patch("/contact-origins/{origin_id}")
def update_origin(origin_id: uuid.UUID, data: OriginUpdate, db: DB, user: Authenticated):
    obj = db.scalar(
        select(ContactOrigin).where(
            ContactOrigin.id == origin_id,
            ContactOrigin.organization_id == user.organization_id,
        )
    )
    if obj is None:
        raise HTTPException(404, "Origem não encontrada.")
    if data.name is not None:
        name_clean = data.name.strip()
        if not name_clean or len(name_clean) > 100:
            raise HTTPException(422, "Informe um nome válido de até 100 caracteres.")
        existing = db.scalar(
            select(ContactOrigin).where(
                ContactOrigin.organization_id == user.organization_id,
                func.lower(ContactOrigin.name) == name_clean.casefold(),
                ContactOrigin.id != origin_id,
            )
        )
        if existing:
            raise HTTPException(409, "Já existe uma origem com este nome.")
        obj.name = name_clean
    if data.description is not None:
        obj.description = data.description.strip() or None
    if data.channel_type is not None:
        obj.channel_type = data.channel_type.strip().upper() or "OTHER"
    if data.is_active is not None:
        obj.is_active = data.is_active
    db.flush()
    return {
        "id": obj.id,
        "name": obj.name,
        "description": obj.description,
        "channel_type": obj.channel_type,
        "is_active": obj.is_active,
    }


def get_or_create_origin(db, organization_id, value, description=None, channel_type="OTHER", is_active=True):
    name_clean = value.strip()
    if not name_clean or len(name_clean) > 100:
        raise HTTPException(422, "Informe uma origem de até 100 caracteres.")
    chat_repo.lock_connection(db, uuid.uuid5(organization_id, "contact-origins"))
    obj = db.scalar(
        select(ContactOrigin).where(
            ContactOrigin.organization_id == organization_id,
            func.lower(ContactOrigin.name) == name_clean.casefold(),
        )
    )
    if obj is None:
        obj = ContactOrigin(
            organization_id=organization_id,
            name=name_clean,
            description=description.strip() if description else None,
            channel_type=(channel_type or "OTHER").strip().upper(),
            is_active=is_active,
        )
        db.add(obj)
        db.flush()
    return obj


@router.get("/contact-directory")
def directory(
    db: DB,
    user: Authenticated,
    search: str = "",
    team_id: uuid.UUID | None = None,
    connection_id: uuid.UUID | None = None,
    contact_id: uuid.UUID | None = None,
    origin_module: str | None = None,
    is_active: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    query = select(Contact).where(Contact.organization_id == user.organization_id)
    if contact_id:
        query = query.where(Contact.id == contact_id)
    if origin_module:
        query = query.where(Contact.origin_module == origin_module)
    if is_active is not None:
        query = query.where(Contact.is_active.is_(is_active))
    if search:
        query = query.where(
            or_(
                Contact.name.icontains(search, autoescape=True),
                Contact.phone.icontains(search, autoescape=True),
            )
        )
    if team_id or connection_id:
        related = select(ChatConversation.contact_id).where(
            ChatConversation.organization_id == user.organization_id,
            ChatConversation.team_id.in_(chat_repo.member_teams(user.organization_id, user.id)),
        )
        if team_id:
            related = related.where(ChatConversation.team_id == team_id)
        if connection_id:
            related = related.where(ChatConversation.connection_id == connection_id)
        query = query.where(Contact.id.in_(related))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = []
    for contact in db.scalars(
        query.order_by(Contact.name, Contact.id).offset((page - 1) * page_size).limit(page_size)
    ):
        item = ContactResponse.model_validate(contact).model_dump()
        item["origin_name"] = db.scalar(
            select(ContactOrigin.name).where(
                ContactOrigin.id == contact.contact_origin_id,
                ContactOrigin.organization_id == user.organization_id,
            )
        )
        item["customers"] = [
            dict(r._mapping)
            for r in db.execute(
                select(Customer.id, Customer.name).where(
                    Customer.contact_id == contact.id,
                    Customer.organization_id == user.organization_id,
                )
            )
        ]
        item["suppliers"] = [
            dict(r._mapping)
            for r in db.execute(
                select(Supplier.id, Supplier.name).where(
                    Supplier.contact_id == contact.id,
                    Supplier.organization_id == user.organization_id,
                )
            )
        ]
        item["channels"] = [
            dict(r._mapping)
            for r in db.execute(
                select(
                    ChatConversation.id,
                    ChatConversation.connection_id,
                    ChatConnection.name,
                    ChatConversation.instance_phone,
                    ChatConversation.team_id,
                )
                .join(ChatConnection, ChatConnection.id == ChatConversation.connection_id)
                .where(
                    ChatConversation.contact_id == contact.id,
                    ChatConversation.organization_id == user.organization_id,
                    ChatConversation.team_id.in_(
                        chat_repo.member_teams(user.organization_id, user.id)
                    ),
                )
            )
        ]
        items.append(item)
    return {"items": items, "total": total, "page": page}


@router.post("/contact-directory/{contact_id}/links")
def link_business(contact_id: uuid.UUID, data: ContactLinks, db: DB, user: Authenticated):
    from controlb.modules.chat.service import permissions

    perms = permissions(user)
    contact = db.scalar(
        select(Contact).where(
            Contact.id == contact_id, Contact.organization_id == user.organization_id
        )
    )
    if contact is None:
        raise HTTPException(404, "Contato não encontrado.")
    for identifier, model, permission in (
        (data.customer_id, Customer, "sales:manage"),
        (data.supplier_id, Supplier, "purchasing:order"),
    ):
        if identifier is None:
            continue
        if not {permission, "*:*"}.intersection(perms):
            raise HTTPException(403, "Sem permissão para alterar esse cadastro.")
        obj = db.scalar(
            select(model).where(
                model.id == identifier, model.organization_id == user.organization_id
            )
        )
        if obj is None:
            raise HTTPException(404, "Cadastro não encontrado.")
        if obj.contact_id and obj.contact_id != contact.id:
            raise HTTPException(409, "Cadastro já vinculado a outro contato.")
        obj.contact_id = contact.id
    db.flush()
    return {"linked": True}
