import os
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select, func
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from fulfillment.database import Base
from fulfillment.config import settings
from fulfillment.models.carrier_booking import CarrierBooking, SandboxCarrierReceipt
from fulfillment.models.fulfillment_center import FulfillmentCenter
from fulfillment.models.order import Order, OrderStatus
from fulfillment.models.shipment import Shipment, ShipmentStatus
from fulfillment.schemas.carrier_booking import BookingRequest
from fulfillment.services.carrier_booking import (
    request_booking,
    process_due_bookings,
    cancel_booking,
    reconcile_booking,
)
from fulfillment.services.carrier_adapters import CarrierUnavailable, SandboxCarrier
from fulfillment.services.inventory import InventoryConflict


@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario,expected,attempts",
    [
        ("accepted", "booked", 1),
        ("retry_once", "booked", 2),
        ("rejected", "failed", 1),
        ("ambiguous", "booked", 1),
        ("unavailable", "failed", 4),
    ],
)
async def test_booking_persistence_and_recovery(
    tmp_path, monkeypatch, scenario, expected, attempts, database
):
    monkeypatch.setattr(settings, "carrier_booking_provider", "sandbox")
    monkeypatch.setattr(settings, "carrier_sandbox_enabled", True)
    url = f"sqlite+aiosqlite:///{tmp_path / 'booking.db'}"
    if database == "postgresql":
        url = os.environ.get("WAREHOUSE_BOOKING_TEST_DATABASE")
        if not url:
            pytest.skip("Requires disposable booking_acceptance PostgreSQL")
        target = make_url(url)
        assert target.host == "127.0.0.1" and target.database == "booking_acceptance"
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        if database == "sqlite":
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        async with sessions.begin() as db:
            center = FulfillmentCenter(
                name="Sandbox",
                address="1 Test",
                city="Karachi",
                state="Sindh",
                zip_code="74000",
                country="PK",
            )
            db.add(center)
            await db.flush()
            order = Order(
                customer_email="test@example.com",
                shipping_address="2 Test",
                shipping_city="Lahore",
                shipping_state="Punjab",
                shipping_zip="54000",
                shipping_country="PK",
                status=OrderStatus.PROCESSING,
                fulfillment_center_id=center.id,
                tracking_number="INTERNAL",
            )
            db.add(order)
            await db.flush()
            shipment = Shipment(
                order_id=order.id,
                carrier_name="Sandbox lane",
                tracking_number="INTERNAL",
                origin_zip="74000",
                destination_zip="54000",
                weight_kg=1,
                status=ShipmentStatus.LABEL_CREATED,
            )
            db.add(shipment)
            await db.flush()
            shipment_id, order_id = shipment.id, order.id
        payload = BookingRequest(
            idempotency_key=uuid4(),
            recipient_name="Test recipient",
            recipient_phone="+923001234567",
            sender_phone="+923001234568",
            currency="PKR",
            payment_mode="cod",
            cod_amount="1500.00",
            sandbox_scenario=scenario,
        )
        async with sessions.begin() as db:
            monkeypatch.setattr(settings, "carrier_sandbox_enabled", False)
            with pytest.raises(CarrierUnavailable):
                await request_booking(db, shipment_id, payload, "operator")
            monkeypatch.setattr(settings, "carrier_sandbox_enabled", True)
            row = await request_booking(db, shipment_id, payload, "operator")
            booking_id = row.id
            assert (await request_booking(db, shipment_id, payload, "operator")).id == booking_id
            with pytest.raises(InventoryConflict):
                await request_booking(
                    db,
                    shipment_id,
                    payload.model_copy(update={"recipient_name": "Changed"}),
                    "operator",
                )
            with pytest.raises(InventoryConflict):
                await request_booking(
                    db,
                    shipment_id,
                    payload.model_copy(update={"idempotency_key": uuid4()}),
                    "operator",
                )
        lookup_fault_tested = False
        for _ in range(6):
            if scenario == "accepted":
                await asyncio.gather(process_due_bookings(sessions), process_due_bookings(sessions))
            else:
                await process_due_bookings(sessions)
            async with sessions.begin() as db:
                row = await db.get(CarrierBooking, booking_id)
                if row.status in {"booked", "failed"}:
                    break
                assert row.status in {"retry", "unknown"}
                row.due_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            if scenario == "ambiguous" and not lookup_fault_tested:
                async def unavailable_lookup(*args):
                    raise TimeoutError("Sandbox provider lookup unavailable")
                with monkeypatch.context() as patch:
                    patch.setattr(SandboxCarrier, "lookup", unavailable_lookup)
                    await process_due_bookings(sessions)
                async with sessions.begin() as db:
                    row = await db.get(CarrierBooking, booking_id)
                    assert row.status == "unknown" and row.due_at is None
                    assert row.attempts == 1
                    await reconcile_booking(db, shipment_id, "operator")
                lookup_fault_tested = True
        async with sessions() as db:
            row = await db.get(CarrierBooking, booking_id)
            assert (row.status, row.attempts) == (expected, attempts)
            assert row.sandbox
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(CarrierBooking)
                    .where(CarrierBooking.id == booking_id)
                )
                == 1
            )
            assert await db.scalar(
                select(func.count())
                .select_from(SandboxCarrierReceipt)
                .where(SandboxCarrierReceipt.idempotency_key == str(payload.idempotency_key))
            ) == (1 if expected == "booked" else 0)
            if expected == "booked":
                assert (await db.get(Shipment, shipment_id)).tracking_number == row.tracking_number
                assert (await db.get(Order, order_id)).tracking_number == row.tracking_number
                assert row.tracking_number.startswith("SANDBOX-")
        assert await process_due_bookings(sessions) == 0
        if expected == "booked":
            async with sessions.begin() as db:
                with pytest.raises(InventoryConflict):
                    await cancel_booking(db, shipment_id, "operator")
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_authenticated_booking_to_dispatch_and_tracking(tmp_path, monkeypatch):
    import hmac
    import json
    from httpx import ASGITransport, AsyncClient
    from fulfillment.database import get_db
    from fulfillment.main import app
    from fulfillment.models.user import User, UserRole
    from fulfillment.models.carrier_rate import CarrierRate
    from fulfillment.models.inventory import Product, Stock
    from fulfillment.security import create_access_token
    from fulfillment.schemas.order import OrderCreate, OrderLineCreate
    from fulfillment.services.order_service import OrderService

    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "carrier_booking_provider", "sandbox")
    monkeypatch.setattr(settings, "carrier_sandbox_enabled", True)
    monkeypatch.setattr(settings, "carrier_require_booking_before_dispatch", True)
    monkeypatch.setattr(settings, "webhook_secret", "booking-acceptance-webhook-secret")
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'api.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def db_dependency():
        async with sessions.begin() as db:
            yield db

    original = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = db_dependency
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with sessions.begin() as db:
            operator = User(
                email="operator@booking.example", password_hash="unused", role=UserRole.OPERATOR
            )
            viewer = User(
                email="viewer@booking.example", password_hash="unused", role=UserRole.VIEWER
            )
            center = FulfillmentCenter(
                name="Sandbox",
                address="1 Test",
                city="Karachi",
                state="Sindh",
                zip_code="74000",
                country="PK",
            )
            db.add_all([operator, viewer, center, Product(sku="BOOK", name="Test product")])
            await db.flush()
            db.add_all(
                [
                    Stock(sku="BOOK", center_id=center.id, on_hand=5),
                    CarrierRate(
                        carrier_name="Sandbox lane",
                        service_name="Parcel",
                        origin_zip="74000",
                        destination_zip="54000",
                        weight_kg_min=0,
                        weight_kg_max=10,
                        base_rate=100,
                        rate_per_kg=10,
                        estimated_days_min=1,
                        estimated_days_max=2,
                    ),
                ]
            )
            await db.flush()
            order = await OrderService(db).create_order(
                OrderCreate(
                    customer_email="recipient@example.com",
                    shipping_address="2 Test",
                    shipping_city="Lahore",
                    shipping_state="Punjab",
                    shipping_zip="54000",
                    shipping_country="PK",
                    total_weight_kg=1,
                    lines=[OrderLineCreate(sku="BOOK", quantity=2)],
                )
            )
            shipment = await db.scalar(select(Shipment).where(Shipment.order_id == order.id))
            order_id, shipment_id = order.id, shipment.id
            operator_headers = {
                "Authorization": "Bearer " + create_access_token(operator.id, "operator")
            }
            viewer_headers = {"Authorization": "Bearer " + create_access_token(viewer.id, "viewer")}
        booking_path = f"/api/v1/shipments/{shipment_id}/booking"
        dispatch_path = f"/api/v1/orders/{order_id}/dispatch"
        payload = {
            "idempotency_key": str(uuid4()),
            "recipient_name": "Sandbox recipient",
            "recipient_phone": "+923001234567",
            "sender_phone": "+923001234568",
            "currency": "PKR",
        }
        async with AsyncClient(
            transport=ASGITransport(app=app, client=("192.0.2.44", 1234)), base_url="http://test"
        ) as client:
            assert (await client.get(booking_path)).status_code == 401
            assert (
                await client.post(booking_path, headers=viewer_headers, json=payload)
            ).status_code == 403
            client.headers.update(operator_headers)
            assert (
                await client.post(dispatch_path, json={"reason": "Too early"})
            ).status_code == 409
            assert (
                await client.post(booking_path, json={**payload, "recipient_phone": "invalid"})
            ).status_code == 422
            created = await client.post(booking_path, json=payload)
            assert created.status_code == 202, created.text
            assert created.json()["sandbox"] and created.json()["status"] == "queued"
            assert (await client.post(booking_path, json=payload)).json()["id"] == created.json()[
                "id"
            ]
            assert (
                await client.post(dispatch_path, json={"reason": "Still queued"})
            ).status_code == 409
            assert (
                await client.post(
                    f"/api/v1/orders/{order_id}/cancel",
                    json={"reason": "Must cancel booking first"},
                )
            ).status_code == 409
            assert (await client.post(booking_path + "/cancel")).status_code == 200
            payload["idempotency_key"] = str(uuid4())
            assert (await client.post(booking_path, json=payload)).status_code == 202
            assert await process_due_bookings(sessions) == 1
            read = await client.get(booking_path, headers=viewer_headers)
            assert read.status_code == 200 and read.json()["status"] == "booked"
            tracking = read.json()["tracking_number"]
            assert (await client.post(booking_path + "/cancel")).status_code == 409
            assert (
                await client.post(dispatch_path, json={"reason": "Sandbox dispatch exercise"})
            ).status_code == 200
            body = json.dumps(
                {
                    "tracking_number": tracking,
                    "carrier": "Sandbox lane",
                    "status": "delivered",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            signature = hmac.new(
                settings.webhook_secret.encode(), body.encode(), "sha256"
            ).hexdigest()
            event = await client.post(
                "/api/v1/webhooks/shipment-event",
                content=body,
                headers={"Content-Type": "application/json", "X-Webhook-Signature": signature},
            )
            assert event.status_code == 200, event.text
            assert (await client.get(f"/api/v1/orders/{order_id}")).json()["status"] == "delivered"
    finally:
        if original is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = original
        await engine.dispose()
