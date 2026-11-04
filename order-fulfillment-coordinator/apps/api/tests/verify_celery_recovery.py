import asyncio
import json
import os
import signal
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from fulfillment.models.agent_event import AgentEvent, MonitorTaskResult
from fulfillment.models.carrier_rate import CarrierRate
from fulfillment.models.fulfillment_center import FulfillmentCenter
from fulfillment.models.shipment import Shipment
from fulfillment.database import async_session_factory, engine
from fulfillment.schemas.order import OrderCreate
from fulfillment.services.order_service import OrderService
from fulfillment.tasks import celery_app, run_monitor_cycle

database = make_url(os.environ["DATABASE_URL"])
assert (database.drivername, database.host, database.port, database.database) == (
    "postgresql+asyncpg", "127.0.0.1", 55471, "worker_acceptance",
)
assert os.environ["CELERY_BROKER_URL"] == "redis://127.0.0.1:56379/13"
assert os.environ["CELERY_RESULT_BACKEND"] == "redis://127.0.0.1:56379/14"
celery_app.conf.update(
    task_track_started=True, visibility_timeout=4,
    broker_transport_options={"visibility_timeout": 4},
    result_backend_transport_options={"visibility_timeout": 4},
)
artifact = Path(os.environ["WAREHOUSE_ACCEPTANCE_OUTPUT"]).resolve()
artifact.mkdir(parents=True, exist_ok=True)

if len(sys.argv) > 1 and sys.argv[1] == "worker":
    pool = "solo" if os.name == "nt" else "prefork"
    celery_app.worker_main(["worker", f"--pool={pool}", "--concurrency=2", "-Q", "monitoring", "-l", "INFO", "-n", "warehouse-recovery@localhost"])
    sys.exit()
if len(sys.argv) > 1 and sys.argv[1] == "beat":
    celery_app.conf.beat_schedule["monitor-cycle-every-15-min"]["schedule"] = 2
    celery_app.start(["beat", "-l", "INFO", "-s", str(artifact / "warehouse-beat-schedule")])
    sys.exit()


async def wait_for(result, states, seconds):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        state = await asyncio.to_thread(lambda: result.state)
        if state in states:
            return state
        if state == "FAILURE":
            raise RuntimeError(f"Task failed: {type(result.result).__name__}")
        await asyncio.sleep(0.15)
    raise TimeoutError(f"{result.id} failed to reach {states}; last state {state}")


async def seed():
    async with async_session_factory.begin() as db:
        db.add(FulfillmentCenter(name="Worker fixture", address="1 Test", zip_code="11010", city="Test", state="NY"))
        for name, cost in (("Sandbox A", 11), ("Sandbox B", 12)):
            db.add(CarrierRate(
                carrier_name=name, service_name="Ground", origin_zip="11010", destination_zip="10001",
                weight_kg_min=0, weight_kg_max=10, base_rate=cost, rate_per_kg=1,
                estimated_days_min=2, estimated_days_max=3,
            ))
        await db.flush()
        await OrderService(db).create_order(OrderCreate(
            customer_email="isolated-worker@example.com", shipping_address="2 Test", shipping_zip="10001",
            shipping_city="New York", shipping_state="NY", total_weight_kg=1,
        ))
        shipment = await db.scalar(select(Shipment).order_by(Shipment.created_at.desc()).limit(1))
        shipment.estimated_delivery = datetime.now(timezone.utc) - timedelta(days=2)


def start(log, mode="worker"):
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    return subprocess.Popen(
        [sys.executable, __file__, mode], stdout=log, stderr=subprocess.STDOUT,
        creationflags=flags, start_new_session=os.name != "nt",
    )


async def main():
    await seed()
    evidence = {}
    with (artifact / "warehouse-celery-first.log").open("w") as first, (artifact / "warehouse-celery-restarted.log").open("w") as second:
        worker = start(first)
        try:
            normal = run_monitor_cycle.delay()
            await wait_for(normal, {"SUCCESS"}, 45)
            assert normal.result["delays_detected"] >= 1
            assert any(event["type"] == "reroute_recommended" for event in normal.result["events"])
            evidence["normal"] = {"task_id": normal.id, "cycle_id": normal.result["cycle_id"]}
            normal.forget()
            duplicate = run_monitor_cycle.apply_async(task_id=normal.id)
            await wait_for(duplicate, {"SUCCESS"}, 30)
            assert duplicate.result["cycle_id"] == evidence["normal"]["cycle_id"]
            evidence["duplicate"] = {"task_id": duplicate.id, "cycle_id": duplicate.result["cycle_id"]}

            async with engine.begin() as connection:
                await connection.execute(text("ALTER TABLE public.shipments RENAME TO shipments_test_unavailable"))
            try:
                retry = run_monitor_cycle.delay()
                await wait_for(retry, {"RETRY"}, 30)
            finally:
                async with engine.begin() as connection:
                    await connection.execute(text("ALTER TABLE public.shipments_test_unavailable RENAME TO shipments"))
            await wait_for(retry, {"SUCCESS"}, 45)
            evidence["retry"] = {"task_id": retry.id, "cycle_id": retry.result["cycle_id"]}

            async with engine.begin() as connection:
                await connection.execute(text("LOCK TABLE public.agent_events IN ACCESS EXCLUSIVE MODE"))
                recovery = run_monitor_cycle.delay()
                await wait_for(recovery, {"STARTED"}, 30)
                if os.name == "nt":
                    worker.kill()
                else:
                    os.killpg(worker.pid, signal.SIGKILL)
                worker.wait(timeout=10)
            await asyncio.sleep(6)
            worker = start(second)
            await wait_for(recovery, {"SUCCESS"}, 60)
            evidence["recovery"] = {"task_id": recovery.id, "cycle_id": recovery.result["cycle_id"]}

            beat_start = datetime.now(timezone.utc)
            with (artifact / "warehouse-celery-beat.log").open("w") as beat_log:
                beat = start(beat_log, "beat")
                try:
                    for _ in range(60):
                        async with async_session_factory() as db:
                            scheduled = await db.scalar(select(MonitorTaskResult).where(
                                MonitorTaskResult.completed_at >= beat_start
                            ).order_by(MonitorTaskResult.completed_at).limit(1))
                        if scheduled is not None:
                            evidence["scheduled"] = {
                                "task_id": scheduled.task_id, "cycle_id": scheduled.result["cycle_id"],
                            }
                            break
                        await asyncio.sleep(0.25)
                    else:
                        raise TimeoutError("Beat did not produce a persisted monitor result")
                finally:
                    beat.terminate()
                    beat.wait(timeout=10)

            async with engine.begin() as connection:
                await connection.execute(text("ALTER TABLE public.shipments RENAME TO shipments_test_unavailable"))
            try:
                exhausted = run_monitor_cycle.delay()
                await wait_for(exhausted, {"RETRY"}, 30)
                await wait_for(exhausted, {"FAILURE"}, 100)
                async with async_session_factory() as db:
                    assert await db.get(MonitorTaskResult, exhausted.id) is None
                evidence["exhausted"] = {"task_id": exhausted.id, "state": exhausted.state}
            finally:
                async with engine.begin() as connection:
                    await connection.execute(text("ALTER TABLE public.shipments_test_unavailable RENAME TO shipments"))
            restored = run_monitor_cycle.delay()
            await wait_for(restored, {"SUCCESS"}, 30)
            evidence["after_exhaustion"] = {"task_id": restored.id, "cycle_id": restored.result["cycle_id"]}

            async with async_session_factory() as db:
                for result in (duplicate, retry, recovery):
                    rows = list(await db.scalars(select(AgentEvent).where(AgentEvent.entity_id == result.result["cycle_id"])))
                    assert {row.agent_name for row in rows} == {"CostOptimizer", "FulfillmentOrchestrator"}
                    assert len(rows) == 2
                evidence["persisted_agents"] = sorted(set(await db.scalars(select(AgentEvent.agent_name))))
        finally:
            if worker.poll() is None:
                worker.terminate()
                worker.wait(timeout=10)
    await engine.dispose()
    (artifact / "warehouse-celery-evidence.json").write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence))


asyncio.run(main())
