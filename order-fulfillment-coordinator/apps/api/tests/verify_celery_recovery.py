import asyncio
import json
import os
import signal
from pathlib import Path
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlsplit
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from fulfillment.agents.communication import CommunicationAgent
from fulfillment.config import settings
from fulfillment.models.agent_event import AgentEvent, MonitorTaskResult
from fulfillment.models.carrier_rate import CarrierRate
from fulfillment.models.fulfillment_center import FulfillmentCenter
from fulfillment.models.notification import Notification
from fulfillment.models.shipment import Shipment
from fulfillment.database import async_session_factory, engine
from fulfillment.schemas.order import OrderCreate
from fulfillment.services.order_service import OrderService
from fulfillment.tasks import celery_app, run_monitor_cycle
from fulfillment.tasks.monitor_cycle import drain_notification_outbox

database = make_url(os.environ["DATABASE_URL"])
assert (database.drivername, database.host, database.port) == (
    "postgresql+asyncpg", "127.0.0.1", 55471,
)
assert database.database in {"worker_acceptance", "worker_release_acceptance"}
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
    sandbox_url = os.environ.get("WAREHOUSE_NOTIFICATION_SANDBOX")
    if sandbox_url:
        assert urlsplit(sandbox_url).hostname == "127.0.0.1"
        from sendgrid import SendGridAPIClient
        original_init = SendGridAPIClient.__init__

        def local_sendgrid(self, *, api_key):
            original_init(self, api_key=api_key, host=sandbox_url)

        SendGridAPIClient.__init__ = local_sendgrid
        settings.sendgrid_api_key = "sandbox-only"
        settings.sendgrid_from_email = "sender@example.com"
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
    assert not settings.sendgrid_api_key and not settings.twilio_auth_token
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

            async with async_session_factory.begin() as db:
                shipment = await db.scalar(select(Shipment).order_by(Shipment.created_at.desc()).limit(1))
                settings.sendgrid_api_key = "queue-only-test-placeholder"
                try:
                    notice = await CommunicationAgent(db).send_delay_alert(shipment, "Sandbox carrier delay")
                finally:
                    settings.sendgrid_api_key = ""
                assert notice is not None and notice["notifications_queued"] == 1
                notification_id = notice["channels"][0]["notification_id"]
            delivery = drain_notification_outbox.delay()
            await wait_for(delivery, {"SUCCESS"}, 30)
            async with async_session_factory() as db:
                stored = await db.get(Notification, notification_id)
                assert stored.status == "failed" and stored.delivery_attempts == 1
                assert stored.provider_message_id is None
            evidence["notification_worker"] = {
                "task_id": delivery.id, "notification_id": notification_id, "status": "failed",
            }

            # An external HTTP sandbox replaces only the provider, not the agent,
            # outbox transaction, SDK, Redis broker or worker execution.
            requests = []

            class SandboxProvider(BaseHTTPRequestHandler):
                def do_POST(self):
                    assert self.path == "/v3/mail/send"
                    requests.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                    self.send_response(202)
                    self.send_header("X-Message-Id", "sandbox-accepted")
                    self.send_header("Content-Length", "0")
                    self.end_headers()

                def log_message(self, *_args):
                    pass

            server = ThreadingHTTPServer(("127.0.0.1", 0), SandboxProvider)
            server_thread = Thread(target=server.serve_forever, daemon=True)
            server_thread.start()
            worker.terminate()
            worker.wait(timeout=10)
            os.environ["WAREHOUSE_NOTIFICATION_SANDBOX"] = f"http://127.0.0.1:{server.server_port}"
            worker = start(second)
            try:
                await seed()
                async with async_session_factory.begin() as db:
                    shipment = await db.scalar(select(Shipment).order_by(Shipment.created_at.desc()).limit(1))
                    settings.sendgrid_api_key = "sandbox-only"
                    try:
                        notice = await CommunicationAgent(db).send_delay_alert(shipment, "Sandbox weather")
                    finally:
                        settings.sendgrid_api_key = ""
                    assert notice and notice["notifications_queued"] == 1
                    accepted_id = notice["channels"][0]["notification_id"]
                accepted = drain_notification_outbox.delay()
                await wait_for(accepted, {"SUCCESS"}, 45)
                duplicate_delivery = drain_notification_outbox.delay()
                await wait_for(duplicate_delivery, {"SUCCESS"}, 30)
                async with async_session_factory() as db:
                    stored = await db.get(Notification, accepted_id)
                    assert stored.status == "sent" and stored.delivery_attempts == 1
                    assert stored.provider_message_id == "sandbox-accepted"
                assert len(requests) == 1
                evidence["notification_accepted"] = {
                    "task_id": accepted.id, "notification_id": accepted_id,
                    "status": "provider_accepted", "external_provider": "loopback sandbox",
                    "duplicate_task_id": duplicate_delivery.id, "http_requests": len(requests),
                }
            finally:
                server.shutdown()
                server.server_close()
                server_thread.join(timeout=5)

            redis_container = os.environ.get("WAREHOUSE_ACCEPTANCE_REDIS_CONTAINER")
            if redis_container:
                labels = subprocess.check_output([
                    "docker", "inspect", "--format", "{{json .Config.Labels}}", redis_container,
                ], text=True, timeout=10)
                assert json.loads(labels)["com.docker.compose.project"] == "warehouse-acceptance"
                assert json.loads(labels)["com.docker.compose.service"] == "redis"
                subprocess.run(["docker", "restart", "--timeout", "2", redis_container], check=True, timeout=20)
                reconnected = run_monitor_cycle.delay()
                await wait_for(reconnected, {"SUCCESS"}, 45)
                evidence["redis_restart"] = {
                    "task_id": reconnected.id, "cycle_id": reconnected.result["cycle_id"],
                }

            async with async_session_factory() as db:
                for result in (duplicate, retry, recovery):
                    rows = list(await db.scalars(select(AgentEvent).where(AgentEvent.entity_id == result.result["cycle_id"])))
                    assert {row.agent_name for row in rows} == {"MonitorAgent", "CostOptimizer", "FulfillmentOrchestrator"}
                    assert len(rows) == 3
                evidence["persisted_agents"] = sorted(set(await db.scalars(select(AgentEvent.agent_name))))
                evidence["agent_executions"] = []
                for name in evidence["persisted_agents"]:
                    event = await db.scalar(select(AgentEvent).where(AgentEvent.agent_name == name).order_by(AgentEvent.created_at.desc()).limit(1))
                    evidence["agent_executions"].append({
                        "agent": name, "event_id": event.id, "entity_id": event.entity_id,
                        "event_type": event.event_type, "timestamp": event.created_at.isoformat(),
                        "result": json.loads(event.details_json or "{}"),
                    })
        finally:
            (artifact / "warehouse-celery-evidence.json").write_text(json.dumps(evidence, indent=2))
            if worker.poll() is None:
                worker.terminate()
                worker.wait(timeout=10)
    await engine.dispose()
    print(json.dumps(evidence))


asyncio.run(main())
