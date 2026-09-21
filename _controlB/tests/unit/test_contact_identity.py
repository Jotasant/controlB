import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from controlb.db import SessionLocal
from controlb.modules.identity import schemas
from controlb.modules.identity import service as identity
from controlb.modules.identity.contact_identity import identifiers, normalize_phone
from controlb.modules.identity.contact_migration import migrate, rollback
from controlb.modules.identity.messaging import upsert_whatsapp_contact
from controlb.modules.identity.models import Contact, ContactIdentifier, Organization
from controlb.modules.purchasing import schemas as purchasing_schemas
from controlb.modules.purchasing import service as purchasing
from controlb.modules.purchasing.models import Supplier
from controlb.modules.sales import schemas as sales_schemas
from controlb.modules.sales import service as sales
from controlb.modules.sales.models import Customer


@pytest.fixture
def scope():
    with SessionLocal() as db:
        org = Organization(name="Contact identity tests")
        db.add(org)
        db.commit()
        yield db, org.id


def count_contacts(db, org):
    return db.scalar(
        select(func.count()).select_from(Contact).where(Contact.organization_id == org)
    )


def test_normalization_preserves_international_and_brazil_ddd55():
    assert normalize_phone("(55) 99999-1234") == "5555999991234"
    assert normalize_phone("+1 (202) 555-0123") == "12025550123"
    assert normalize_phone("0055 71 99999-1234") == "5571999991234"
    assert identifiers(email=" Test+one@Example.COM ") == {
        ("EMAIL", "test+one@example.com"): "Test+one@Example.COM"
    }
    with pytest.raises(ValueError):
        normalize_phone("99887766@lid")


def test_business_records_share_identity_without_overwriting_it(scope):
    db, org = scope
    contact = identity.create_contact(
        db,
        org,
        schemas.ContactCreate(name="Pessoa", phone="(71) 99999-1234", email="p@example.test"),
    )
    first = sales.create_customer(
        db,
        org,
        sales_schemas.CustomerCreate(
            name="Empresa A", document="11111111111", contact_id=contact.id
        ),
    )
    second = sales.create_customer(
        db,
        org,
        sales_schemas.CustomerCreate(
            name="Empresa B", document="22222222222", contact_id=contact.id
        ),
    )
    supplier = purchasing.create_new_supplier(
        db,
        purchasing_schemas.SupplierCreate(
            organization_id=org, name="Fornecedor", cnpj_cpf="33333333333", contact_id=contact.id
        ),
    )
    sales.update_customer(
        db, first.id, org, sales_schemas.CustomerUpdate(name="Outra razão social")
    )
    db.refresh(contact)
    assert contact.name == "Pessoa"
    assert {first.contact_id, second.contact_id, supplier.contact_id} == {contact.id}
    first.email = "legacy@example.test"
    supplier.email = "legacy@example.test"
    assert sales_schemas.CustomerResponse.model_validate(first).email == contact.email
    assert purchasing_schemas.SupplierResponse.model_validate(supplier).email == contact.email
    with pytest.raises(HTTPException, match="Identity"):
        sales.update_customer(
            db, first.id, org, sales_schemas.CustomerUpdate(phone="+5571888881234")
        )
    with pytest.raises(HTTPException, match="Identity"):
        purchasing.update_supplier_data(
            db, supplier.id, org, purchasing_schemas.SupplierUpdate(email="new@example.com")
        )
    unlinked = sales.create_customer(
        db, org, sales_schemas.CustomerCreate(name="Sem contato", document="44444444444")
    )
    assert unlinked.contact_id is None and count_contacts(db, org) == 1


def test_foreign_contact_and_duplicate_manual_identifiers_are_rejected(scope):
    db, org = scope
    other = Organization(name="Other")
    db.add(other)
    db.commit()
    contact = identity.create_contact(
        db, other.id, schemas.ContactCreate(name="Outro", phone="(71) 99999-1234")
    )
    with pytest.raises(HTTPException):
        sales.create_customer(
            db,
            org,
            sales_schemas.CustomerCreate(
                name="Empresa", document="11111111111", contact_id=contact.id
            ),
        )
    identity.create_contact(
        db,
        org,
        schemas.ContactCreate(name="Pessoa", mobile="(71) 99999-1234", email="Person@Example.test"),
    )
    for fields in ({"phone": "+5571999991234"}, {"email": " person@example.TEST "}):
        with pytest.raises(HTTPException) as exc:
            identity.create_contact(db, org, schemas.ContactCreate(name="Duplicado", **fields))
        assert exc.value.status_code == 409
    assert count_contacts(db, org) == 1


def test_migration_preview_apply_repeat_and_non_destructive_rollback(scope):
    db, org = scope
    customer = Customer(
        organization_id=org,
        name="Empresa",
        document="11111111111",
        phone="(71) 99999-1234",
        email="Person@Example.test",
    )
    supplier = Supplier(
        organization_id=org,
        name="Fornecedor",
        contact_name="Pessoa",
        cnpj_cpf="22222222222",
        phone="+5571999991234",
        email="person@example.TEST",
    )
    db.add_all([customer, supplier])
    db.commit()
    preview = migrate(db, org, "", preview=True)
    assert preview["created"] == 1 and preview["linked"] == 2
    assert count_contacts(db, org) == 0
    result = migrate(db, org, "a" * 64, preview=False)
    db.commit()
    assert customer.contact_id == supplier.contact_id
    assert customer.phone == "(71) 99999-1234" and supplier.email == "person@example.TEST"
    repeated = migrate(db, org, "a" * 64, preview=False)
    assert repeated["run_id"] is None and repeated["created"] == 0
    contact_id = customer.contact_id
    rollback(db, uuid.UUID(result["run_id"]), preview=True)
    assert customer.contact_id == contact_id
    rollback(db, uuid.UUID(result["run_id"]), preview=False)
    db.commit()
    assert customer.contact_id is None and supplier.contact_id is None
    assert db.get(Contact, contact_id).is_active is False
    assert customer.phone == "(71) 99999-1234"


def test_migration_conflicts_abort_without_partial_contacts(scope):
    db, org = scope
    one = Contact(organization_id=org, name="Um", phone="+5571999991234")
    two = Contact(organization_id=org, name="Dois", email="person@example.test")
    db.add_all([one, two])
    db.add(
        Customer(
            organization_id=org,
            name="Empresa",
            document="11111111111",
            phone="(71) 99999-1234",
            email="person@example.test",
        )
    )
    db.commit()
    with pytest.raises(HTTPException):
        migrate(db, org, "a" * 64, preview=False)
    assert count_contacts(db, org) == 2
    assert (
        db.scalar(
            select(func.count())
            .select_from(ContactIdentifier)
            .where(ContactIdentifier.organization_id == org)
        )
        == 0
    )


def test_rollback_refuses_later_edits(scope):
    db, org = scope
    db.add(
        Customer(
            organization_id=org, name="Empresa", document="11111111111", phone="(71) 99999-1234"
        )
    )
    db.commit()
    result = migrate(db, org, "a" * 64, preview=False)
    db.commit()
    contact = db.scalar(select(Contact).where(Contact.organization_id == org))
    contact.name = "Edição posterior"
    db.commit()
    with pytest.raises(ValueError, match="alterado"):
        rollback(db, uuid.UUID(result["run_id"]), preview=False)
    assert contact.name == "Edição posterior"


def test_parallel_inbound_direct_messages_create_one_contact(scope):
    db, org = scope
    barrier = Barrier(2)

    def receive():
        with SessionLocal() as worker:
            barrier.wait()
            message = SimpleNamespace(
                is_group=False,
                direction="INBOUND",
                remote_phone="5571999991234",
                contact_name=None,
                sender_name="Pessoa",
                occurred_at=datetime.now(UTC),
            )
            contact = upsert_whatsapp_contact(worker, SimpleNamespace(organization_id=org), message)
            worker.commit()
            return contact.id

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: receive(), range(2)))
    assert len(set(results)) == 1
    assert count_contacts(db, org) == 1


@pytest.mark.parametrize(
    "group,direction", [(True, "INBOUND"), (True, "OUTBOUND"), (False, "OUTBOUND")]
)
def test_non_direct_inbound_events_never_create_contacts(scope, group, direction):
    db, org = scope
    assert (
        upsert_whatsapp_contact(
            db,
            SimpleNamespace(organization_id=org),
            SimpleNamespace(is_group=group, direction=direction),
        )
        is None
    )
    assert count_contacts(db, org) == 0
