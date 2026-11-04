import asyncio
import hmac
import json
from datetime import datetime, timedelta, timezone
import os
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from fulfillment.agents.monitor import MonitorAgent
from fulfillment.config import settings
from fulfillment.database import Base, get_db
from fulfillment.main import app
from fulfillment.models.carrier_rate import CarrierRate
from fulfillment.models.fulfillment_center import FulfillmentCenter
from fulfillment.models.user import User, UserRole
from fulfillment.security import create_access_token
from fulfillment.services.inventory import InventoryConflict, InventoryService


@pytest.mark.asyncio
@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
async def test_inventory_order_lifecycle(database, tmp_path, monkeypatch):
    if database == "postgresql":
        url = os.environ.get("WAREHOUSE_INVENTORY_TEST_DATABASE")
        if not url:
            pytest.skip("Requires a migrated disposable PostgreSQL inventory_test database")
        target = make_url(url)
        assert target.host == "127.0.0.1" and target.database == "inventory_test"
        assert target.drivername == "postgresql+asyncpg"
    else:
        url = f"sqlite+aiosqlite:///{tmp_path / 'inventory.db'}"
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "webhook_secret", uuid4().hex)
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def test_db():
        async with sessions.begin() as session:
            yield session

    suffix = uuid4().hex[:10]
    sku = f"BOX-{suffix}"
    prior_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = test_db
    try:
        if database == "sqlite":
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
        async with sessions.begin() as db:
            operator = User(email=f"operator-{suffix}@example.com", password_hash="unused", role=UserRole.OPERATOR)
            viewer = User(email=f"viewer-{suffix}@example.com", password_hash="unused", role=UserRole.VIEWER)
            center = FulfillmentCenter(
                name=f"Stock Center {suffix}", address="1 Test Ave", zip_code="90210",
                city="Beverly Hills", state="CA", capacity_pct=10,
            )
            other_center = FulfillmentCenter(
                name=f"Other Center {suffix}", address="2 Test Ave", zip_code="90210",
                city="Beverly Hills", state="CA",
            )
            db.add_all([operator, viewer, center, other_center, CarrierRate(
                carrier_name=f"Sandbox {suffix}", service_name="Ground",
                origin_zip="90210", destination_zip="10001", weight_kg_min=0, weight_kg_max=50,
                base_rate=10, rate_per_kg=1, estimated_days_min=2, estimated_days_max=3,
            )])
            await db.flush()
            operator_headers = {"Authorization": f"Bearer {create_access_token(operator.id, 'operator')}"}
            viewer_headers = {"Authorization": f"Bearer {create_access_token(viewer.id, 'viewer')}"}
            center_id, other_center_id = center.id, other_center.id

        base = "/api/v1/inventory"
        client_address = ("192.0.2.20" if database == "sqlite" else "192.0.2.21", 12345)
        async with AsyncClient(
            transport=ASGITransport(app=app, client=client_address), base_url="http://testserver",
        ) as client:
            product = {"sku": sku, "name": "Packing boxes"}
            assert (await client.get(f"{base}/stock")).status_code == 401
            assert (await client.post(f"{base}/products", headers=viewer_headers, json=product)).status_code == 403
            client.headers.update(operator_headers)
            assert (await client.post(f"{base}/products", json=product)).status_code == 201
            assert (await client.post(f"{base}/products", json=product)).status_code == 409
            stocks = []
            for location in (center_id, other_center_id):
                result = await client.post(f"{base}/stock", json={
                    "sku": sku, "center_id": location, "low_stock_threshold": 2,
                })
                assert result.status_code == 201, result.text
                stocks.append(result.json()["id"])
            stock_id, other_stock_id = stocks
            path = f"{base}/stock/{stock_id}"
            receipt = {"operation_id": str(uuid4()), "kind": "receipt", "quantity_delta": 10, "reason": "Inbound PO"}
            for _ in range(2):
                response = await client.post(f"{path}/movements", json=receipt)
                assert response.status_code == 200, response.text
                assert response.json()["available"] == 10
            assert (await client.post(f"{path}/movements", json={**receipt, "quantity_delta": 11})).status_code == 409

            async def new_order():
                payload = {
                    "defer_routing": True, "external_order_id": str(uuid4()),
                    "customer_email": "stock-test@example.com",
                    "shipping_address": "10 Test St", "shipping_city": "New York",
                    "shipping_state": "NY", "shipping_zip": "10001", "total_weight_kg": 1,
                }
                result = await client.post("/api/v1/orders", json=payload)
                assert result.status_code == 201, result.text
                assert result.json()["status"] == "pending"
                assert (await client.post("/api/v1/orders", json=payload)).status_code == 409
                return result.json()["id"]

            order_ids = [await new_order() for _ in range(4)]
            unallocated_route = await client.post(f"/api/v1/orders/{order_ids[0]}/route")
            assert unallocated_route.status_code == 400
            assert unallocated_route.json()["detail"] == "Reserve inventory before routing this order"
            requests = [
                client.post(f"{path}/reservations", json={"order_id": order_id, "quantity": 4})
                for order_id in order_ids
            ]
            if database == "postgresql":
                results = await asyncio.gather(*requests)
            else:
                results = [await request for request in requests]
            assert sorted(result.status_code for result in results) == [200, 200, 409, 409]
            reservations = [result.json() for result in results if result.status_code == 200]
            first, second = reservations
            replay = await client.post(f"{path}/reservations", json={"order_id": first["order_id"], "quantity": 4})
            assert replay.json()["id"] == first["id"]
            assert (await client.post(f"{base}/stock/{other_stock_id}/reservations", json={
                "order_id": first["order_id"], "quantity": 1,
            })).status_code == 409
            low_stock = await client.get(f"{base}/stock?low_only=true", headers=viewer_headers)
            assert any(row["id"] == stock_id and row["available"] == 2 for row in low_stock.json())
            adjustment = {**receipt, "operation_id": str(uuid4()), "kind": "adjustment", "quantity_delta": -3}
            assert (await client.post(f"{path}/movements", json=adjustment)).status_code == 409

            order_path = f"/api/v1/orders/{first['order_id']}"
            assert (await client.patch(order_path, json={"status": "cancelled"})).status_code == 409
            assert (await client.delete(order_path)).status_code == 409
            route = await client.post(f"{order_path}/route")
            assert route.status_code == 200, route.text
            assert route.json()["fulfillment_center_id"] == center_id
            consume_path = f"{base}/reservations/{first['id']}/consume"
            release_path = f"{base}/reservations/{second['id']}/release"
            for _ in range(2):
                assert (await client.post(consume_path, json={"reason": "Picked and dispatched"})).status_code == 200
                assert (await client.post(release_path, json={"reason": "Customer cancellation"})).status_code == 200
            assert (await client.patch(f"/api/v1/orders/{second['order_id']}", json={"status": "cancelled"})).status_code == 200
            row = next(row for row in (await client.get(f"{base}/stock")).json() if row["id"] == stock_id)
            assert (row["on_hand"], row["reserved"], row["available"]) == (6, 0, 6)
            movement_rows = (await client.get(f"{path}/movements")).json()
            assert sorted(row["kind"] for row in movement_rows) == ["consume", "receipt", "release", "reserve", "reserve"]
            assert sum(row["on_hand_delta"] for row in movement_rows) == 6
            assert sum(row["reserved_delta"] for row in movement_rows) == 0

            second_sku = f"WRAP-{suffix}"
            assert (await client.post(f"{base}/products", json={"sku": second_sku, "name": "Packing wrap"})).status_code == 201
            result = await client.post(f"{base}/stock", json={"sku": second_sku, "center_id": center_id})
            second_stock = result.json()["id"]
            assert (await client.post(f"{base}/stock/{second_stock}/movements", json={
                **receipt, "operation_id": str(uuid4()), "quantity_delta": 6,
            })).status_code == 200

            lines = [{"sku": sku, "quantity": 3}, {"sku": second_sku, "quantity": 3}]
            typed = {
                "customer_email": "typed-test@example.com", "shipping_address": "10 Test St",
                "shipping_city": "New York", "shipping_state": "NY", "shipping_zip": "10001",
                "total_weight_kg": 1, "lines": lines,
            }
            assert (await client.post("/api/v1/orders", json={**typed, "lines": [lines[0], lines[0]]})).status_code == 422
            assert (await client.post("/api/v1/orders", json={
                **typed, "lines": [{"sku": "UNKNOWN", "quantity": 1}],
            })).status_code == 409

            # Fail on the second line after a real route and a real reservation were staged.
            reserve = InventoryService.reserve
            calls = 0

            async def fail_second(self, *args, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise InventoryConflict("Injected allocation failure")
                return await reserve(self, *args, **kwargs)

            with monkeypatch.context() as patch:
                patch.setattr(InventoryService, "reserve", fail_second)
                failed = await client.post("/api/v1/orders", json=typed)
            assert failed.status_code == 201, failed.text
            pending = failed.json()
            assert calls == 2 and pending["status"] == "pending" and pending["tracking_number"] is None
            assert (await client.get(f"{base}/orders/{pending['id']}/reservations")).json() == []
            assert len((await client.get(f"{path}/movements")).json()) == len(movement_rows)

            operations = [client.post("/api/v1/orders", json=typed) for _ in range(3)]
            outcomes = await asyncio.gather(*operations) if database == "postgresql" else [
                await request for request in operations
            ]
            assert all(outcome.status_code == 201 for outcome in outcomes), [item.text for item in outcomes]
            assert sorted(item.json()["status"] for item in outcomes) == ["pending", "processing", "processing"]
            for outcome in outcomes:
                item = outcome.json()
                response = await client.get(f"/api/v1/orders/{item['id']}/lines")
                persisted = response.json()
                assert [(line["sku"], line["quantity"]) for line in persisted] == [(sku, 3), (second_sku, 3)]
                allocated = item["status"] == "processing"
                assert all(line["center_id"] == (center_id if allocated else None) for line in persisted)
                assert all(line["reservation_status"] == ("reserved" if allocated else None) for line in persisted)
            typed_rows = {row["id"]: row for row in (await client.get(f"{base}/stock")).json()}
            for stock in (stock_id, second_stock):
                assert (typed_rows[stock]["on_hand"], typed_rows[stock]["reserved"], typed_rows[stock]["available"]) == (6, 6, 0)

            allocated_order = next(item.json() for item in outcomes if item.json()["status"] == "processing")
            typed_path = f"/api/v1/orders/{allocated_order['id']}"
            typed_reservations = (await client.get(f"{base}/orders/{allocated_order['id']}/reservations")).json()
            assert len(typed_reservations) == 2
            first_line = typed_reservations[0]["id"]
            for action in ("consume", "release"):
                assert (await client.post(f"{base}/reservations/{first_line}/{action}", json={
                    "reason": "Invalid partial transition",
                })).status_code == 409
            shipment = next(row for row in (await client.get("/api/v1/shipments")).json()
                            if row["order_id"] == allocated_order["id"])
            async with sessions() as db:
                assert await MonitorAgent(db).count_active_shipments([shipment["id"]]) == 0

            async def shipment_event(status, target=shipment, timestamp=None):
                event = {
                    "tracking_number": target["tracking_number"],
                    "carrier": target["carrier_name"], "status": status,
                }
                if timestamp is not None:
                    event["timestamp"] = timestamp.isoformat()
                body = json.dumps(event).encode()
                return await client.post("/api/v1/webhooks/shipment-event", content=body, headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Signature": hmac.digest(settings.webhook_secret.encode(), body, "sha256").hex(),
                })

            assert (await shipment_event("delivered")).status_code == 409
            dispatches = [
                client.post(f"{typed_path}/dispatch", json={"reason": "Operator recorded dispatch"})
                for _ in range(2)
            ]
            dispatched = await asyncio.gather(*dispatches) if database == "postgresql" else [
                await request for request in dispatches
            ]
            assert all(item.status_code == 200 and item.json()["status"] == "shipped" for item in dispatched)
            async with sessions() as db:
                assert await MonitorAgent(db).count_active_shipments([shipment["id"]]) == 1
            event_time = datetime.now(timezone.utc)
            assert (await shipment_event("in_transit", timestamp=event_time + timedelta(hours=1))).status_code == 409
            assert (await shipment_event("in_transit", timestamp=event_time)).status_code == 200
            assert (await shipment_event("picked_up", timestamp=event_time - timedelta(seconds=1))).status_code == 409
            assert (await shipment_event("picked_up", timestamp=event_time)).status_code == 409
            assert (await shipment_event("picked_up")).status_code == 409
            delivered_at = event_time + timedelta(seconds=1)
            assert (await shipment_event("delivered", timestamp=delivered_at)).status_code == 200
            assert (await shipment_event("delivered", timestamp=delivered_at)).status_code == 200
            assert (await shipment_event("in_transit", timestamp=delivered_at + timedelta(seconds=1))).status_code == 409
            assert (await client.get(typed_path)).json()["status"] == "delivered"
            final = {row["id"]: row for row in (await client.get(f"{base}/stock")).json()}
            for stock in (stock_id, second_stock):
                assert (final[stock]["on_hand"], final[stock]["reserved"], final[stock]["available"]) == (3, 3, 0)

            to_cancel = next(
                item.json() for item in outcomes
                if item.json()["status"] == "processing" and item.json()["id"] != allocated_order["id"]
            )
            cancellation_shipment = next(row for row in (await client.get("/api/v1/shipments")).json()
                                         if row["order_id"] == to_cancel["id"])
            reroute_payload = {"new_carrier_name": f"Missing-{suffix}", "reason": "No contract available"}
            assert (await client.post(f"/api/v1/shipments/{uuid4()}/reroute", json=reroute_payload)).status_code == 404
            assert (await client.post(
                f"/api/v1/shipments/{cancellation_shipment['id']}/reroute", json=reroute_payload,
            )).status_code == 409
            cancel_path = f"/api/v1/orders/{to_cancel['id']}"
            reason = {"reason": "Customer cancelled before dispatch"}
            assert (await client.post(f"{cancel_path}/cancel", headers=viewer_headers, json=reason)).status_code == 403
            assert (await client.post(f"{typed_path}/cancel", json=reason)).status_code == 409
            cancellations = [client.post(f"{cancel_path}/cancel", json=reason) for _ in range(2)]
            cancelled = await asyncio.gather(*cancellations) if database == "postgresql" else [
                await request for request in cancellations
            ]
            assert all(item.status_code == 200 and item.json()["status"] == "cancelled" for item in cancelled)
            cancelled_shipment = next(row for row in (await client.get("/api/v1/shipments?status=cancelled")).json()
                                      if row["order_id"] == to_cancel["id"])
            assert (await client.post(f"/api/v1/shipments/{cancelled_shipment['id']}/reroute", json={
                "new_carrier_name": "Sandbox", "reason": "Invalid cancelled reroute",
            })).status_code == 409
            assert (await shipment_event("picked_up", cancelled_shipment)).status_code == 409
            assert (await client.post(f"{cancel_path}/dispatch", json=reason)).status_code == 409
            cancelled_lines = (await client.get(f"{cancel_path}/lines")).json()
            assert [line["reservation_status"] for line in cancelled_lines] == ["released", "released"]
            async with sessions() as db:
                assert await MonitorAgent(db).count_active_shipments([cancelled_shipment["id"]]) == 0
            released = {row["id"]: row for row in (await client.get(f"{base}/stock")).json()}
            for stock in (stock_id, second_stock):
                assert (released[stock]["on_hand"], released[stock]["reserved"], released[stock]["available"]) == (3, 0, 3)

            if database == "postgresql":
                race_order = await client.post("/api/v1/orders", json=typed)
                assert race_order.status_code == 201 and race_order.json()["status"] == "processing"
                race_path = f"/api/v1/orders/{race_order.json()['id']}"
                cancel, dispatch = await asyncio.gather(
                    client.post(f"{race_path}/cancel", json=reason),
                    client.post(f"{race_path}/dispatch", json={"reason": "Concurrent dispatch"}),
                )
                assert sorted([cancel.status_code, dispatch.status_code]) == [200, 409]
                cancelled_first = cancel.status_code == 200
                assert (await client.get(race_path)).json()["status"] == ("cancelled" if cancelled_first else "shipped")
                race_lines = (await client.get(f"{race_path}/lines")).json()
                assert {row["reservation_status"] for row in race_lines} == {
                    "released" if cancelled_first else "consumed",
                }
    finally:
        if prior_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = prior_override
        await engine.dispose()
