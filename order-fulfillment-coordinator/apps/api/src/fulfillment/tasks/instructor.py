"""Run the fixed linked warehouse scenario on an existing Celery worker."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select, text

from fulfillment.agents.communication import deliver_due_notifications
from fulfillment.agents.orchestrator import FulfillmentOrchestrator
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
from fulfillment.services.carrier_booking import process_due_bookings, request_booking
from fulfillment.services.instructor_workspace import workspace
from fulfillment.services.inventory import InventoryService
from fulfillment.services.order_service import OrderService
from fulfillment.services.shipment_service import ShipmentService
from fulfillment.tasks.monitor_cycle import celery_app


async def execute(sessions, task_id: str, progress) -> dict:
    sku = uuid4().hex[:10]
    async with sessions.begin() as db:
        center = FulfillmentCenter(
            name=sku, address="Sandbox", city="Test", state="NY", zip_code=sku
        )
        db.add_all([center, Product(sku=sku, name="Evaluation product")])
        await db.flush()
        stock = Stock(center_id=center.id, sku=sku)
        db.add(stock)
        for carrier, price in [("Fixture A", 10), ("Fixture B", 11)]:
            db.add(
                CarrierRate(
                    carrier_name=carrier,
                    service_name="Ground",
                    origin_zip=sku,
                    destination_zip="10001",
                    weight_kg_min=0,
                    weight_kg_max=10,
                    base_rate=price,
                    rate_per_kg=1,
                    estimated_days_min=2,
                    estimated_days_max=3,
                )
            )
        await db.flush()
        await InventoryService(db).change_stock(
            stock.id,
            StockChange(
                operation_id=uuid4(), kind="receipt", quantity_delta=5, reason="Evaluation receipt"
            ),
            "instructor",
        )
        order = await OrderService(db).create_order(
            OrderCreate(
                customer_email=f"{sku}@example.com",
                shipping_address="Sandbox",
                shipping_zip="10001",
                shipping_city="Test",
                shipping_state="NY",
                total_weight_kg=1,
                lines=[OrderLineCreate(sku=sku, quantity=2)],
            )
        )
        shipment = await db.scalar(select(Shipment).where(Shipment.order_id == order.id))
        await db.refresh(stock)
        if (stock.on_hand, stock.reserved) != (5, 2) or shipment.carrier_name != "Fixture A":
            raise RuntimeError("Reservation or route did not match")
        booking = await request_booking(
            db,
            shipment.id,
            BookingRequest(
                idempotency_key=uuid4(),
                recipient_name="Evaluator",
                recipient_phone="+12025550100",
                sender_phone="+12025550101",
                currency="USD",
            ),
            "instructor",
        )
    await progress("Booking sandbox shipment")
    await process_due_bookings(sessions, task_id=task_id)
    async with sessions.begin() as db:
        booked = await db.get(CarrierBooking, booking.id)
        if not booked.sandbox or booked.status != "booked":
            raise RuntimeError("Sandbox booking not confirmed")
        shipment = await db.get(Shipment, shipment.id)
        await OrderService(db).dispatch_order(order.id, "Evaluation dispatch", "instructor")
        tracking = dict(tracking_number=shipment.tracking_number, carrier=shipment.carrier_name)
    async with sessions.begin() as db:
        await ShipmentService(db).update_from_event(
            ShipmentEventWebhook(
                **tracking,
                status="delayed",
                estimated_delivery=datetime.now(timezone.utc) - timedelta(days=2),
            )
        )
    await progress("Evaluating delay, rerouting and cost")
    async with sessions.begin() as db:
        cycle = (await FulfillmentOrchestrator(db).run_monitor_cycle()).model_dump(mode="json")
        db.add(MonitorTaskResult(task_id=task_id, result=cycle))
    await deliver_due_notifications(sessions)
    async with sessions.begin() as db:
        notice = await db.scalar(select(Notification).where(Notification.order_id == order.id))
        if (
            notice is None
            or notice.status != "sent"
            or not await db.scalar(
                text("SELECT 1 FROM instructor_mailbox WHERE notice_id=:id"), {"id": notice.id}
            )
        ):
            raise RuntimeError("Sandbox mailbox receipt missing")
        await ShipmentService(db).update_from_event(
            ShipmentEventWebhook(
                **tracking, status="delivered", timestamp=datetime.now(timezone.utc)
            )
        )
    async with sessions() as db:
        stock = await db.get(Stock, stock.id)
        delivered = await db.get(Order, order.id)
        events = list(
            await db.scalars(
                select(AgentEvent)
                .where(
                    AgentEvent.entity_id.in_([order.id, shipment.id, notice.id, cycle["cycle_id"]])
                )
                .order_by(AgentEvent.created_at)
            )
        )
        states = await agent_runtime_status(db)
        if (
            (stock.on_hand, stock.reserved) != (3, 0)
            or delivered.status != "delivered"
            or len(states) != 7
            or any(
                row["status"] != "IDLE" or row["event_id"] not in {e.id for e in events}
                for row in states
            )
        ):
            raise RuntimeError("Delivery or linked agent evidence missing")
        return dict(
            order=order.id,
            shipment=shipment.id,
            booking_id=booking.id,
            task_id=task_id,
            mailbox_receipt=notice.id,
            order_state="delivered",
            stock_after_delivery=[3, 0],
            events=[
                dict(
                    agent=e.agent_name,
                    type=e.event_type,
                    id=e.id,
                    time=e.created_at.isoformat(),
                    result=json.loads(e.details_json or "{}"),
                )
                for e in events
            ],
        )


async def perform(owner: str, task_id: str) -> None:
    async with workspace(owner, allocate=False) as (conn, sessions, slot):

        async def record(stage: str, result: dict | None = None) -> None:
            await conn.execute(
                text("""UPDATE public.instructor_slots SET stage=:stage, result=CAST(:result AS jsonb)
                WHERE slot=:slot AND owner=:owner AND run=CAST(:run AS uuid)"""),
                dict(slot=slot, owner=owner, run=task_id, stage=stage, result=json.dumps(result)),
            )
            await conn.commit()

        claimed = await conn.scalar(
            text("""UPDATE public.instructor_slots SET stage='Receiving stock'
            WHERE slot=:slot AND run=CAST(:run AS uuid) AND stage='Queued' RETURNING slot"""),
            dict(slot=slot, run=task_id),
        )
        await conn.commit()
        if claimed is None:
            return
        if not await conn.scalar(text("SELECT pg_try_advisory_lock(826412)")):
            await record("Failed")
            return
        try:
            result = await execute(sessions, task_id, record)
            await record("Completed", result)
        except Exception:
            await record("Failed")
            raise


@celery_app.task(bind=True, ignore_result=True, soft_time_limit=100, time_limit=120)
def instructor_run(self, owner):
    asyncio.run(perform(owner, self.request.id))
