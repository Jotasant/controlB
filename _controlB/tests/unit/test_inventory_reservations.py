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
    InventoryBalance,
    InventoryTransfer,
    Product,
    StockMovement,
    StockReservation,
    StockReservationItem,
)
from controlb.modules.inventory.schemas import (
    InventoryLocationCreate,
    InventoryTransferCreate,
    InventoryTransferItemCreate,
)
from controlb.modules.purchasing import schemas as purchasing_schemas
from controlb.modules.purchasing import service as purchasing_service
from controlb.modules.purchasing.models import InventoryReplenishment, Supplier
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
    Base.metadata.create_all(engine)
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


def test_transfer_preserves_global_stock_and_moves_local_balances(db: Session):
    organization = _organization(db, "transfer")
    product = _product(db, organization, stock="10")
    actor = _actor(organization)
    source = inventory_service.ensure_default_location(db, organization.id)
    inventory_service.sync_default_location_balance(db, organization.id, product)
    destination = inventory_service.create_inventory_location(
        db,
        organization.id,
        InventoryLocationCreate(code="LOJA", name="Loja"),
    )
    db.commit()

    transfer = inventory_service.create_inventory_transfer(
        db,
        organization.id,
        actor,
        InventoryTransferCreate(
            source_location_id=source.id,
            destination_location_id=destination.id,
            items=[
                InventoryTransferItemCreate(
                    product_id=product.id, quantity=Decimal("4")
                )
            ],
            notes="Abastecimento da loja",
        ),
    )
    db.commit()

    db.refresh(product)
    balances = list(
        db.scalars(
            select(InventoryBalance).where(
                InventoryBalance.product_id == product.id
            )
        ).all()
    )
    balances_by_location = {item.location_id: item.quantity for item in balances}
    movements = list(
        db.scalars(
            select(StockMovement).where(
                StockMovement.transfer_id == transfer.id
            )
        ).all()
    )
    document = db.get(BusinessDocument, transfer.document_id)

    assert product.current_stock == Decimal("10")
    assert balances_by_location[source.id] == Decimal("6")
    assert balances_by_location[destination.id] == Decimal("4")
    assert {movement.movement_type for movement in movements} == {
        "transfer_out",
        "transfer_in",
    }
    assert all(movement.balance_after == Decimal("10") for movement in movements)
    assert transfer.status == "COMPLETED"
    assert document is not None
    assert document.document_type == "INVENTORY_TRANSFER"
    assert document.document_number.startswith("TRF-")


def test_transfer_with_insufficient_local_stock_is_atomic(db: Session):
    organization = _organization(db, "transfer-insufficient")
    product = _product(db, organization, stock="3")
    actor = _actor(organization)
    source = inventory_service.ensure_default_location(db, organization.id)
    inventory_service.sync_default_location_balance(db, organization.id, product)
    destination = inventory_service.create_inventory_location(
        db,
        organization.id,
        InventoryLocationCreate(code="EXPEDICAO", name="Expedição"),
    )
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        inventory_service.create_inventory_transfer(
            db,
            organization.id,
            actor,
            InventoryTransferCreate(
                source_location_id=source.id,
                destination_location_id=destination.id,
                items=[
                    InventoryTransferItemCreate(
                        product_id=product.id, quantity=Decimal("4")
                    )
                ],
            ),
        )
    db.rollback()

    source_balance = db.scalar(
        select(InventoryBalance).where(
            InventoryBalance.product_id == product.id,
            InventoryBalance.location_id == source.id,
        )
    )
    transfer_count = db.scalar(select(func.count(InventoryTransfer.id)))
    assert exc_info.value.status_code == 409
    assert source_balance is not None
    assert source_balance.quantity == Decimal("3")
    assert transfer_count == 0


def test_quick_order_persists_replenishment_and_document_chain(db: Session):
    organization = _organization(db, "replenishment")
    product = _product(db, organization, stock="2")
    supplier = Supplier(
        organization_id=organization.id,
        name="Fornecedor de teste",
        trade_name="Fornecedor",
        cnpj_cpf=f"CNPJ-{uuid.uuid4().hex[:12]}",
        payment_terms="30 DDL",
        is_active=True,
    )
    db.add(supplier)
    db.commit()

    order = purchasing_service.create_quick_replenishment_order(
        db,
        _actor(organization),
        purchasing_schemas.QuickReplenishmentOrderCreate(
            supplier_id=supplier.id,
            items=[
                purchasing_schemas.PurchaseOrderItemCreate(
                    product_id=product.id,
                    quantity=Decimal("8"),
                    unit_price=Decimal("4"),
                )
            ],
        ),
    )

    replenishment = db.get(InventoryReplenishment, order.replenishment_id)
    assert replenishment is not None
    assert replenishment.status == "ORDERED"
    assert replenishment.items[0].current_stock == Decimal("2")
    assert replenishment.items[0].target_stock == Decimal("10")
    assert replenishment.items[0].requested_quantity == Decimal("8")

    replenishment_document = db.get(BusinessDocument, replenishment.document_id)
    order_document = db.get(BusinessDocument, order.document_id)
    relation = db.scalar(
        select(DocumentRelation).where(
            DocumentRelation.parent_document_id == replenishment.document_id,
            DocumentRelation.child_document_id == order.document_id,
        )
    )
    events = list(
        db.scalars(
            select(DocumentEvent).where(
                DocumentEvent.document_id == replenishment.document_id
            )
        ).all()
    )

    assert replenishment_document is not None
    assert replenishment_document.document_type == "REPLENISHMENT"
    assert replenishment_document.document_number.startswith("REP-")
    assert replenishment_document.current_status == "ORDERED"
    assert order_document is not None
    assert order_document.document_type == "PURCHASE_ORDER"
    assert relation is not None
    assert relation.relation_type == "GENERATED"
    assert {event.event_type for event in events} == {"CREATED", "ORDER_CREATED"}

    purchasing_service.cancel_purchase_order(
        db, order.id, organization.id, current_user=_actor(organization)
    )
    db.refresh(replenishment)
    db.refresh(replenishment_document)
    assert replenishment.status == "CANCELLED"
    assert replenishment_document.current_status == "CANCELLED"
    assert db.scalar(
        select(func.count(DocumentEvent.id)).where(
            DocumentEvent.document_id == replenishment.document_id,
            DocumentEvent.event_type == "ORDER_CANCELLED",
        )
    ) == 1


def test_formal_replenishment_tracks_request_until_order(db: Session):
    organization = _organization(db, "formal-replenishment")
    product = _product(db, organization, stock="2")
    actor = _actor(organization)

    purchase_request = purchasing_service.create_formal_replenishment_request(
        db,
        actor,
        purchasing_schemas.PurchaseRequestCreate(
            justification="Reposição formal de estoque crítico",
            items=[
                purchasing_schemas.PurchaseRequestItemCreate(
                    product_id=product.id,
                    quantity=Decimal("8"),
                    estimated_unit_price=Decimal("4"),
                )
            ],
        ),
    )

    replenishment = db.get(
        InventoryReplenishment, purchase_request.replenishment_id
    )
    assert replenishment is not None
    assert replenishment.status == "REQUESTED"
    request_relation = db.scalar(
        select(DocumentRelation).where(
            DocumentRelation.parent_document_id == replenishment.document_id,
            DocumentRelation.child_document_id == purchase_request.document_id,
        )
    )
    assert request_relation is not None
    assert request_relation.relation_type == "GENERATED"

    supplier = Supplier(
        organization_id=organization.id,
        name="Fornecedor formal",
        trade_name="Fornecedor formal",
        cnpj_cpf=f"CNPJ-{uuid.uuid4().hex[:12]}",
        is_active=True,
    )
    db.add(supplier)
    db.commit()
    purchasing_service.transition_purchase_request_status(
        db,
        purchase_request,
        organization.id,
        "APPROVED",
        current_user=actor,
    )
    quotation = purchasing_service.open_quotation_process(
        db,
        current_user=actor,
        request_id=purchase_request.id,
        notes="Cotação formal da reposição",
    )
    supplier_quote = purchasing_service.add_supplier_quote_to_process(
        db,
        current_user=actor,
        quotation_id=quotation.id,
        quote_data=purchasing_schemas.SupplierQuoteCreate(
            supplier_id=supplier.id,
            quote_reference="PROP-REPOSICAO-1",
            lead_time_days=3,
            items=[
                purchasing_schemas.SupplierQuoteItemCreate(
                    product_id=product.id,
                    quantity=Decimal("8"),
                    unit_price=Decimal("4"),
                )
            ],
        ),
    )
    order = purchasing_service.select_winner_and_generate_order(
        db,
        current_user=actor,
        quotation_id=quotation.id,
        quote_id=supplier_quote.id,
        notes="Melhor proposta da reposição",
    )

    db.refresh(replenishment)
    assert order.replenishment_id == replenishment.id
    assert replenishment.status == "ORDERED"
    chain_relations = list(
        db.scalars(
            select(DocumentRelation).where(
                DocumentRelation.organization_id == organization.id
            )
        ).all()
    )
    relation_edges = {
        (relation.parent_document_id, relation.child_document_id)
        for relation in chain_relations
    }
    assert (
        replenishment.document_id,
        purchase_request.document_id,
    ) in relation_edges
    assert (
        purchase_request.document_id,
        quotation.document_id,
    ) in relation_edges
    assert (
        quotation.document_id,
        order.document_id,
    ) in relation_edges

    purchasing_service.cancel_purchase_request(
        db,
        purchase_request.id,
        organization.id,
        current_user=actor,
    )
    db.refresh(replenishment)
    assert replenishment.status == "CANCELLED"
    assert db.scalar(
        select(func.count(DocumentEvent.id)).where(
            DocumentEvent.document_id == replenishment.document_id,
            DocumentEvent.event_type == "ORDER_CANCELLED",
        )
    ) == 1


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


def test_reservation_uses_canonical_sales_order_status(db: Session):
    organization = _organization(db, "canonical-status")
    product = _product(db, organization, stock="10")
    order = _order(db, organization, [(product, "1")])
    document = db.get(BusinessDocument, order.document_id)
    assert document is not None

    order.status = "CONFIRMED"
    document.current_status = "CANCELLED"
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        inventory_service.reserve_sales_order(db, organization.id, None, order.id)

    assert exc_info.value.status_code == 409
    assert order.status == "CANCELLED"


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
    cycle_events = [
        event for event in events if event.event_type in {"RESERVED", "RELEASED"}
    ]
    assert len({event.idempotency_key for event in cycle_events}) == 3


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


def test_dispatch_consumes_reservation_posts_stock_once_and_delivery_completes(
    db: Session,
):
    organization = _organization(db, "delivery")
    actor = _actor(organization)
    product = _product(db, organization, stock="10", suffix="delivery")
    order = _order(db, organization, [(product, "3")])
    reservation = inventory_service.reserve_sales_order(
        db, organization.id, actor.id, order.id
    )

    delivery = inventory_service.dispatch_sales_order(
        db, organization.id, actor, order.id
    )
    assert delivery.status == "DISPATCHED"
    assert delivery.stock_posted is True
    assert delivery.reservation_id == reservation.id
    assert reservation.status == "CONSUMED"
    assert order.delivery_status == "DISPATCHED"
    assert product.current_stock == Decimal("7")
    assert len(delivery.items) == 1
    assert delivery.items[0].quantity == Decimal("3")
    assert db.scalar(
        select(func.count(StockMovement.id)).where(
            StockMovement.delivery_id == delivery.id
        )
    ) == 1

    same_delivery = inventory_service.dispatch_sales_order(
        db, organization.id, actor, order.id
    )
    assert same_delivery.id == delivery.id
    assert product.current_stock == Decimal("7")
    assert db.scalar(
        select(func.count(StockMovement.id)).where(
            StockMovement.delivery_id == delivery.id
        )
    ) == 1

    completed = inventory_service.confirm_sales_order_delivery(
        db, organization.id, actor, order.id
    )
    assert completed.status == "DELIVERED"
    assert completed.delivered_at is not None
    assert order.delivery_status == "DELIVERED"
    assert product.current_stock == Decimal("7")
    delivery_header = db.get(BusinessDocument, delivery.document_id)
    assert delivery_header.current_status == "DELIVERED"
    assert delivery_header.completed_at is not None

    with pytest.raises(HTTPException) as cancellation:
        sales_service.delete_sales_order(
            db, order.id, organization.id, actor, reason="cancelamento tardio"
        )
    assert cancellation.value.status_code == 409
    assert product.current_stock == Decimal("7")

    chain = documents_service.get_document_chain(
        db,
        organization_id=organization.id,
        document_type="SALES_ORDER",
        native_id=order.id,
    )
    assert "DELIVERY" in {document.document_type for document in chain.documents}
    assert "FULFILLED_BY" in {relation.relation_type for relation in chain.relations}


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
