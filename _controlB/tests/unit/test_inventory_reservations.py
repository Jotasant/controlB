"""Regressions for integral sales-order stock reservations."""

import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from controlb.db import Base
from controlb.modules.documents import service as documents_service
from controlb.modules.documents.models import (
    BusinessDocument,
    DocumentEvent,
    DocumentRelation,
)
from controlb.modules.identity.models import Organization
from controlb.modules.inventory import service as inventory_service
from controlb.modules.inventory.models import (
    Product,
    StockMovement,
    StockReservation,
    StockReservationItem,
)
from controlb.modules.sales import schemas as sales_schemas
from controlb.modules.sales import service as sales_service
from controlb.modules.sales.models import (
    POSSale,
    POSSaleItem,
    POSSession,
    SalesOrder,
    SalesOrderItem,
)


@pytest.fixture
def db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            Organization.__table__,
            BusinessDocument.__table__,
            DocumentRelation.__table__,
            DocumentEvent.__table__,
            Product.__table__,
            SalesOrder.__table__,
            SalesOrderItem.__table__,
            POSSession.__table__,
            POSSale.__table__,
            POSSaleItem.__table__,
            StockMovement.__table__,
            StockReservation.__table__,
            StockReservationItem.__table__,
        ],
    )
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        yield session
    engine.dispose()


def _organization(db: Session, suffix: str) -> Organization:
    organization = Organization(name=f"Reservation Org {suffix}-{uuid.uuid4().hex[:6]}")
    db.add(organization)
    db.commit()
    return organization


def _actor(organization: Organization):
    return SimpleNamespace(
        id=None,
        organization_id=organization.id,
        email="inventory.test@controlb.local",
    )


def _product(
    db: Session,
    organization: Organization,
    *,
    stock: str = "10.0000",
    suffix: str = "A",
) -> Product:
    product = Product(
        organization_id=organization.id,
        sku=f"RES-{suffix}-{uuid.uuid4().hex[:6]}",
        name=f"Reserved Product {suffix}",
        current_stock=Decimal(stock),
        min_stock=Decimal("0"),
        reference_price=Decimal("5"),
        cost_price=Decimal("3"),
        is_active=True,
    )
    db.add(product)
    db.commit()
    return product


def _order(
    db: Session,
    organization: Organization,
    lines: list[tuple[Product, str]],
) -> SalesOrder:
    order_id = uuid.uuid4()
    number = f"PED-TEST-{uuid.uuid4().hex[:8].upper()}"
    document = documents_service.ensure_document(
        db,
        organization_id=organization.id,
        document_type="SALES_ORDER",
        native_id=order_id,
        document_number=number,
        current_status="CONFIRMED",
    )
    order = SalesOrder(
        id=order_id,
        organization_id=organization.id,
        document_id=document.id,
        order_number=number,
        customer_name="Test Customer",
        total_amount=Decimal("10"),
        discount_amount=Decimal("0"),
        net_amount=Decimal("10"),
        delivery_status="PENDING",
        billing_status="PENDING",
        status="CONFIRMED",
    )
    for product, quantity in lines:
        order.items.append(
            SalesOrderItem(
                product_id=product.id,
                quantity=Decimal(quantity),
                unit_price=Decimal("5"),
                discount_amount=Decimal("0"),
                total_price=Decimal(quantity) * Decimal("5"),
            )
        )
    db.add(order)
    db.commit()
    return order


def test_reservation_is_integral_idempotent_and_does_not_change_physical_stock(
    db: Session,
):
    organization = _organization(db, "integral")
    product = _product(db, organization, stock="10")
    order = _order(db, organization, [(product, "3"), (product, "2")])

    reservation = inventory_service.reserve_sales_order(
        db, organization.id, None, order.id
    )
    db.commit()
    same_reservation = inventory_service.reserve_sales_order(
        db, organization.id, None, order.id
    )

    assert same_reservation.id == reservation.id
    assert reservation.status == "RESERVED"
    assert reservation.status_version == 1
    assert len(reservation.items) == 1
    assert reservation.items[0].quantity == Decimal("5")
    assert product.current_stock == Decimal("10")
    assert order.delivery_status == "RESERVED"

    availability = inventory_service.get_product_availability(
        db, organization.id, product.id
    )
    assert availability.current_stock == Decimal("10")
    assert availability.reserved_stock == Decimal("5")
    assert availability.available_stock == Decimal("5")

    chain = documents_service.get_document_chain(
        db,
        organization_id=organization.id,
        document_type="SALES_ORDER",
        native_id=order.id,
    )
    assert "STOCK_RESERVATION" in {item.document_type for item in chain.documents}
    assert "RESERVED_BY" in {item.relation_type for item in chain.relations}
    assert "RESERVED" in {item.event_type for item in chain.events}


def test_release_and_reactivation_reuse_header_and_create_distinct_cycle_events(
    db: Session,
):
    organization = _organization(db, "cycle")
    product = _product(db, organization)
    order = _order(db, organization, [(product, "4")])
    reservation = inventory_service.reserve_sales_order(
        db, organization.id, None, order.id
    )
    db.commit()

    released = inventory_service.release_stock_reservation(
        db, organization.id, None, reservation.id
    )
    db.commit()
    assert released.status == "RELEASED"
    assert released.status_version == 2
    assert order.delivery_status == "PENDING"
    assert inventory_service.get_product_availability(
        db, organization.id, product.id
    ).available_stock == Decimal("10")

    reactivated = inventory_service.reserve_sales_order(
        db, organization.id, None, order.id
    )
    db.commit()
    assert reactivated.id == reservation.id
    assert reactivated.status == "RESERVED"
    assert reactivated.status_version == 3
    assert order.delivery_status == "RESERVED"

    events = list(
        db.scalars(
            select(DocumentEvent).where(
                DocumentEvent.document_id == reservation.document_id
            )
        ).all()
    )
    assert [event.event_type for event in events].count("RESERVED") == 2
    assert [event.event_type for event in events].count("RELEASED") == 1
    assert len({event.idempotency_key for event in events}) == 3


def test_competing_orders_cannot_overbook_and_tenant_is_hidden(db: Session):
    organization = _organization(db, "owner")
    other_organization = _organization(db, "other")
    product = _product(db, organization, stock="10")
    first = _order(db, organization, [(product, "7")])
    second = _order(db, organization, [(product, "7")])

    inventory_service.reserve_sales_order(db, organization.id, None, first.id)
    db.commit()
    with pytest.raises(HTTPException) as shortage:
        inventory_service.reserve_sales_order(db, organization.id, None, second.id)
    assert shortage.value.status_code == 409
    assert db.scalar(select(func.count(StockReservation.id))) == 1
    assert product.current_stock == Decimal("10")
    assert inventory_service.get_product_availability(
        db, organization.id, product.id
    ).available_stock == Decimal("3")

    with pytest.raises(HTTPException) as hidden:
        inventory_service.reserve_sales_order(
            db, other_organization.id, None, first.id
        )
    assert hidden.value.status_code == 404


def test_manual_release_cannot_regress_dispatched_order(db: Session):
    organization = _organization(db, "dispatch")
    product = _product(db, organization)
    order = _order(db, organization, [(product, "2")])
    reservation = inventory_service.reserve_sales_order(
        db, organization.id, None, order.id
    )
    db.commit()
    order.delivery_status = "DISPATCHED"
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        inventory_service.release_stock_reservation(
            db, organization.id, None, reservation.id
        )
    assert exc_info.value.status_code == 409
    assert reservation.status == "RESERVED"
    assert order.delivery_status == "DISPATCHED"


def test_cancelling_order_releases_reservation_and_retry_heals_delivery(db: Session):
    organization = _organization(db, "cancel")
    actor = _actor(organization)
    product = _product(db, organization)
    order = _order(db, organization, [(product, "6")])
    reservation = inventory_service.reserve_sales_order(
        db, organization.id, actor.id, order.id
    )
    db.commit()

    sales_service.delete_sales_order(db, order.id, organization.id, actor)
    db.commit()
    assert order.status == "CANCELLED"
    assert order.delivery_status == "CANCELLED"
    assert reservation.status == "RELEASED"
    assert reservation.status_version == 2
    assert inventory_service.get_product_availability(
        db, organization.id, product.id
    ).available_stock == Decimal("10")

    order.delivery_status = "PENDING"
    db.commit()
    sales_service.delete_sales_order(db, order.id, organization.id, actor)
    assert order.delivery_status == "CANCELLED"
    assert reservation.status_version == 2


def test_pos_uses_available_stock_is_all_or_nothing_and_does_not_commit(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    organization = _organization(db, "pos")
    actor = _actor(organization)
    reserved_product = _product(db, organization, stock="10", suffix="reserved")
    free_product = _product(db, organization, stock="4", suffix="free")
    order = _order(db, organization, [(reserved_product, "8")])
    inventory_service.reserve_sales_order(db, organization.id, actor.id, order.id)
    db.commit()

    failing_payload = sales_schemas.POSSaleCreate(
        payment_method="PIX",
        items=[
            sales_schemas.POSSaleItemCreate(
                product_id=reserved_product.id,
                quantity=Decimal("2"),
                unit_price=Decimal("5"),
            ),
            sales_schemas.POSSaleItemCreate(
                product_id=free_product.id,
                quantity=Decimal("5"),
                unit_price=Decimal("5"),
            ),
        ],
    )
    with pytest.raises(HTTPException) as exc_info:
        sales_service.process_pos_sale(db, organization.id, actor, failing_payload)
    assert exc_info.value.status_code == 409
    assert reserved_product.current_stock == Decimal("10")
    assert free_product.current_stock == Decimal("4")
    assert db.scalar(select(func.count(POSSale.id))) == 0
    assert db.scalar(select(func.count(StockMovement.id))) == 0

    def fail_if_committed() -> None:
        raise AssertionError("process_pos_sale must not commit internally")

    monkeypatch.setattr(db, "commit", fail_if_committed)
    sale = sales_service.process_pos_sale(
        db,
        organization.id,
        actor,
        sales_schemas.POSSaleCreate(
            payment_method="PIX",
            items=[
                sales_schemas.POSSaleItemCreate(
                    product_id=reserved_product.id,
                    quantity=Decimal("2"),
                    unit_price=Decimal("5"),
                )
            ],
        ),
    )
    assert sale.id is not None
    assert reserved_product.current_stock == Decimal("8")
    assert inventory_service.get_product_availability(
        db, organization.id, reserved_product.id
    ).available_stock == Decimal("0")
