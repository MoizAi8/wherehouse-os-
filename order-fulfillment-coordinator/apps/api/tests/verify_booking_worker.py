"""Real PostgreSQL/Redis worker booking and post-provider worker-loss acceptance."""

import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from uuid import uuid4

from sqlalchemy import select, func
from sqlalchemy.engine import make_url
from fulfillment.config import settings
from fulfillment.database import async_session_factory as sessions, engine
from fulfillment.models.carrier_booking import CarrierBooking, SandboxCarrierReceipt
from fulfillment.models.fulfillment_center import FulfillmentCenter
from fulfillment.models.order import Order, OrderStatus
from fulfillment.models.shipment import Shipment
from fulfillment.schemas.carrier_booking import BookingRequest
from fulfillment.services.carrier_booking import request_booking
from fulfillment.tasks.monitor_cycle import celery_app, drain_carrier_bookings

url = make_url(settings.database_url)
assert (url.host, url.port, url.database) == ("127.0.0.1", 55471, "booking_acceptance")
assert settings.celery_broker_url == "redis://127.0.0.1:56379/9"
assert settings.celery_result_backend == "redis://127.0.0.1:56379/10"
assert settings.carrier_booking_provider == "sandbox" and settings.carrier_sandbox_enabled
out = Path(os.environ["WAREHOUSE_ACCEPTANCE_OUTPUT"]).resolve()
out.mkdir(parents=True, exist_ok=True)
celery_app.conf.update(task_track_started=True, broker_transport_options={"visibility_timeout": 4})
if len(sys.argv) > 1 and sys.argv[1] == "worker":
    celery_app.worker_main(
        [
            "worker",
            "--pool=" + ("solo" if os.name == "nt" else "prefork"),
            "--concurrency=2",
            "-Q",
            "monitoring",
            "-n",
            "booking-acceptance@localhost",
            "-l",
            "INFO",
        ]
    )
    sys.exit()


async def seed():
    async with sessions.begin() as db:
        center = FulfillmentCenter(
            name="Sandbox booking",
            address="1 Test",
            city="Karachi",
            state="Sindh",
            zip_code="74000",
            country="PK",
        )
        db.add(center)
        await db.flush()
        order = Order(
            customer_email="booking@example.com",
            shipping_address="2 Test",
            shipping_city="Lahore",
            shipping_state="Punjab",
            shipping_zip="54000",
            shipping_country="PK",
            status=OrderStatus.PROCESSING,
            fulfillment_center_id=center.id,
            tracking_number="INTERNAL-" + uuid4().hex,
        )
        db.add(order)
        await db.flush()
        shipment = Shipment(
            order_id=order.id,
            carrier_name="Sandbox lane",
            tracking_number=order.tracking_number,
            origin_zip="74000",
            destination_zip="54000",
            weight_kg=1,
        )
        db.add(shipment)
        await db.flush()
        booking = await request_booking(
            db,
            shipment.id,
            BookingRequest(
                idempotency_key=uuid4(),
                recipient_name="Sandbox recipient",
                recipient_phone="+923001234567",
                sender_phone="+923001234568",
                currency="PKR",
            ),
            "acceptance",
        )
        return booking.id, booking.idempotency_key, order.id


async def wait_task(task):
    return await asyncio.to_thread(task.get, timeout=60)


async def main():
    evidence = {}
    worker = None

    def start(log):
        return subprocess.Popen(
            [sys.executable, __file__, "worker"],
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=os.name != "nt",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )

    def stop(process):
        if process.poll() is None:
            if os.name == "nt":
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)

    with (out / "booking-worker.log").open("w") as log:
        try:
            worker = start(log)
            booking_id, key, order_id = await seed()
            task = drain_carrier_bookings.delay()
            await wait_task(task)
            repeat = drain_carrier_bookings.delay()
            await wait_task(repeat)
            async with sessions() as db:
                row = await db.get(CarrierBooking, booking_id)
                assert row.status == "booked" and row.attempts == 1 and row.sandbox
                assert (
                    await db.scalar(
                        select(func.count())
                        .select_from(SandboxCarrierReceipt)
                        .where(SandboxCarrierReceipt.idempotency_key == key)
                    )
                    == 1
                )
                evidence["accepted"] = {
                    "booking_id": booking_id,
                    "task_id": task.id,
                    "duplicate_task_id": repeat.id,
                    "tracking_number": row.tracking_number,
                    "sandbox": True,
                }
            booking_id, key, order_id = await seed()
            async with sessions.begin() as locked:
                await locked.execute(select(Order).where(Order.id == order_id).with_for_update())
                interrupted = drain_carrier_bookings.delay()
                for _ in range(300):
                    async with sessions() as db:
                        receipt = await db.get(SandboxCarrierReceipt, key)
                    if receipt:
                        break
                    await asyncio.sleep(0.1)
                else:
                    raise TimeoutError("Provider acceptance not reached")
                stop(worker)
            async with sessions.begin() as db:
                row = await db.get(CarrierBooking, booking_id)
                assert row.status == "submitting" and row.attempts == 1
                row.due_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            worker = start(log)
            recovered = drain_carrier_bookings.delay()
            await wait_task(recovered)
            async with sessions() as db:
                row = await db.get(CarrierBooking, booking_id)
                assert row.status == "booked" and row.attempts == 1
                assert (await db.get(Order, order_id)).tracking_number == row.tracking_number
                assert (
                    await db.scalar(
                        select(func.count())
                        .select_from(SandboxCarrierReceipt)
                        .where(SandboxCarrierReceipt.idempotency_key == key)
                    )
                    == 1
                )
                evidence["worker_loss_after_acceptance"] = {
                    "booking_id": booking_id,
                    "interrupted_task_id": interrupted.id,
                    "recovery_task_id": recovered.id,
                    "status": row.status,
                    "attempts": row.attempts,
                    "sandbox": True,
                }
            evidence["status"] = "passed"
        finally:
            if worker:
                stop(worker)
            (out / "carrier-booking-worker.json").write_text(json.dumps(evidence, indent=2))
            await engine.dispose()
    print(json.dumps(evidence))


asyncio.run(main())
