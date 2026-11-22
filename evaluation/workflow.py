import asyncio
import hashlib
import hmac
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from uuid import uuid4

import httpx
from fulfillment.config import settings
from fulfillment.database import async_session_factory as sessions
from fulfillment.database import engine
from fulfillment.models.agent_event import AgentEvent, MonitorTaskResult
from fulfillment.models.carrier_booking import CarrierBooking
from fulfillment.models.carrier_rate import CarrierRate
from fulfillment.models.fulfillment_center import FulfillmentCenter
from fulfillment.models.inventory import Product, Stock
from fulfillment.models.notification import Notification
from fulfillment.models.order import Order
from fulfillment.models.shipment import Shipment
from fulfillment.schemas.carrier_booking import BookingRequest
from fulfillment.schemas.inventory import StockChange
from fulfillment.schemas.order import OrderCreate, OrderLineCreate
from fulfillment.schemas.webhook import ShipmentEventWebhook
from fulfillment.services.agent_runtime import agent_runtime_status
from fulfillment.services.carrier_booking import request_booking
from fulfillment.services.inventory import InventoryService
from fulfillment.services.order_service import OrderService
from fulfillment.tasks.monitor_cycle import (
    celery_app,
    drain_carrier_bookings,
    drain_notification_outbox,
    run_monitor_cycle,
)
from sqlalchemy import select
from sqlalchemy.engine import make_url

target = make_url(os.environ["DATABASE_URL"])
if (
    (target.host, target.port) != ("127.0.0.1", 55471)
    or target.database != target.username
    or not __import__("re").fullmatch("instructor_eval_[0-9a-f]{16}", target.database)
):
    raise RuntimeError("Unsafe workflow target")
assert os.environ["CELERY_BROKER_URL"] == "redis://127.0.0.1:56386/0"
assert not settings.twilio_auth_token and not settings.sendgrid_api_key
out = Path(os.environ["EVALUATION_STATE"])
if sys.argv[1:] == ["worker"]:
    from sendgrid import SendGridAPIClient

    url = os.environ["SEVEN_PROVIDER"]
    assert url.startswith("http://127.0.0.1:")
    init = SendGridAPIClient.__init__

    def sandbox(self, *, api_key):
        init(self, api_key=api_key, host=url)

    SendGridAPIClient.__init__ = sandbox
    settings.sendgrid_api_key = "sandbox-only"
    settings.sendgrid_from_email = "sender@example.com"
    celery_app.worker_main(
        [
            "worker",
            "--pool=solo",
            "--concurrency=1",
            "-Q",
            "visual-acceptance",
            "-l",
            "WARNING",
        ]
    )
    sys.exit()
posts = []


class Provider(BaseHTTPRequestHandler):
    def do_POST(self):
        assert self.path == "/v3/mail/send"
        posts.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
        self.send_response(202)
        self.send_header("X-Message-Id", "local-sandbox")
        self.end_headers()

    def log_message(self, *args):
        pass


async def tracking(payload):
    body = payload.model_dump_json().encode()
    key = os.environ["WEBHOOK_SECRET"]
    signature = hmac.new(key.encode(), body, hashlib.sha256).hexdigest()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://127.0.0.1:8386/api/v1/webhooks/shipment-event",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature,
            },
        )
        response.raise_for_status()


async def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
    Thread(target=server.serve_forever, daemon=True).start()
    os.environ["SEVEN_PROVIDER"] = f"http://127.0.0.1:{server.server_port}"
    with (out / "linked-worker.log").open("w") as log:
        worker = subprocess.Popen(
            [sys.executable, __file__, "worker"],
            stdout=log,
            stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            suffix = uuid4().hex[:10]
            async with sessions.begin() as db:
                center = FulfillmentCenter(
                    name=suffix,
                    address="Sandbox",
                    city="Test",
                    state="NY",
                    zip_code=suffix,
                )
                db.add(center)
                db.add(Product(sku=suffix, name="QA product"))
                await db.flush()
                stock = Stock(center_id=center.id, sku=suffix)
                db.add(stock)
                for carrier, rate in [("Fixture A", 10), ("Fixture B", 11)]:
                    db.add(
                        CarrierRate(
                            carrier_name=carrier,
                            service_name="Ground",
                            origin_zip=suffix,
                            destination_zip="10001",
                            weight_kg_min=0,
                            weight_kg_max=10,
                            base_rate=rate,
                            rate_per_kg=1,
                            estimated_days_min=2,
                            estimated_days_max=3,
                        )
                    )
                await db.flush()
                await InventoryService(db).change_stock(
                    stock.id,
                    StockChange(
                        operation_id=uuid4(),
                        kind="receipt",
                        quantity_delta=5,
                        reason="QA receive",
                    ),
                    "QA",
                )
                order = await OrderService(db).create_order(
                    OrderCreate(
                        customer_email=f"{suffix}@example.com",
                        shipping_address="Test",
                        shipping_zip="10001",
                        shipping_city="Test",
                        shipping_state="NY",
                        total_weight_kg=1,
                        lines=[OrderLineCreate(sku=suffix, quantity=2)],
                    )
                )
                await db.refresh(stock)
                assert (stock.on_hand, stock.reserved) == (5, 2)
                shipment = await db.scalar(
                    select(Shipment).where(Shipment.order_id == order.id)
                )
                assert shipment.carrier_name == "Fixture A"
            print(
                "Received 5 units; reserved 2; RoutingAgent selected Fixture A.",
                flush=True,
            )
            async with sessions.begin() as db:
                options = BookingRequest(
                    idempotency_key=uuid4(),
                    recipient_name="Fixture",
                    recipient_phone="+12025550100",
                    sender_phone="+12025550101",
                    currency="USD",
                )
                booking = await request_booking(db, shipment.id, options, "QA")
                assert (
                    await request_booking(db, shipment.id, options, "QA")
                ).id == booking.id
            booking_task = drain_carrier_bookings.apply_async(queue="visual-acceptance")
            await asyncio.to_thread(booking_task.get, timeout=60)
            async with sessions() as db:
                booked = await db.get(CarrierBooking, booking.id)
                shipment = await db.get(Shipment, shipment.id)
                assert (
                    booked.sandbox
                    and booked.status == "booked"
                    and booked.tracking_number == shipment.tracking_number
                )
            await asyncio.sleep(1)
            async with sessions.begin() as db:
                await OrderService(db).dispatch_order(order.id, "QA dispatch", "QA")
            await tracking(
                ShipmentEventWebhook(
                    tracking_number=shipment.tracking_number,
                    carrier="Fixture A",
                    status="delayed",
                    estimated_delivery=datetime.now(timezone.utc) - timedelta(days=2),
                )
            )
            print(
                "Dispatched and ingested signed delay tracking; enqueueing monitor cycle.",
                flush=True,
            )
            await asyncio.sleep(1)
            cycle = run_monitor_cycle.apply_async(queue="visual-acceptance")
            result = await asyncio.to_thread(cycle.get, timeout=60)
            print("Monitor cycle completed: " + cycle.id, flush=True)
            await asyncio.sleep(1)
            delivery = drain_notification_outbox.apply_async(queue="visual-acceptance")
            await asyncio.to_thread(delivery.get, timeout=30)
            async with sessions.begin() as db:
                notice = await db.scalar(
                    select(Notification).where(Notification.order_id == order.id)
                )
                matched = sum(
                    any(
                        addr.get("email") == f"{suffix}@example.com"
                        for person in post.get("personalizations", [])
                        for addr in person.get("to", [])
                    )
                    for post in posts
                )
                assert (
                    notice.status == "sent"
                    and matched == 1
                    and notice.provider_message_id == "local-sandbox"
                )
                assert await db.get(MonitorTaskResult, cycle.id)
            print(
                "Sandbox notification accepted; recording signed delivery.", flush=True
            )
            await asyncio.sleep(1)
            await tracking(
                ShipmentEventWebhook(
                    tracking_number=shipment.tracking_number,
                    carrier="Fixture A",
                    status="delivered",
                    timestamp=datetime.now(timezone.utc),
                )
            )
            async with sessions() as db:
                stock = await db.get(Stock, stock.id)
                assert (stock.on_hand, stock.reserved) == (3, 0)
                assert (await db.get(Order, order.id)).status == "delivered"
                events = list(
                    await db.scalars(
                        select(AgentEvent).where(
                            AgentEvent.entity_id.in_(
                                [order.id, shipment.id, notice.id, result["cycle_id"]]
                            )
                        )
                    )
                )
                states = await agent_runtime_status(db)
                assert {s["name"] for s in states} <= {
                    event.agent_name for event in events
                } and len(states) == 7
                assert all(s["status"] == "IDLE" for s in states)
                evidence = dict(
                    booking_id=booking.id,
                    booking_task=booking_task.id,
                    booking_status=booked.status,
                    provider_reference=booked.provider_reference,
                    order=order.id,
                    shipment=shipment.id,
                    cycle=result["cycle_id"],
                    monitor_task=cycle.id,
                    notification_task=delivery.id,
                    provider_http_requests=matched,
                    all_workspace_provider_requests=len(posts),
                    stock_before_dispatch=[5, 2],
                    stock_after_delivery=[3, 0],
                    order_state="delivered",
                    events=[
                        dict(
                            agent=e.agent_name,
                            id=e.id,
                            time=e.created_at.isoformat(),
                            entity=e.entity_id,
                            type=e.event_type,
                            result=json.loads(e.details_json or "{}"),
                        )
                        for e in events
                    ],
                    dashboard_status=states,
                )
                (out / "eval-workflow.json").write_text(
                    json.dumps(evidence, default=str, indent=2)
                )
                print(
                    "Linked order delivered, seven agents verified, one sandbox provider request"
                )
        finally:
            worker.terminate()
            worker.wait(timeout=10)
            server.shutdown()
            server.server_close()
            await engine.dispose()


asyncio.run(main())
