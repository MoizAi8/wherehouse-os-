"""Loopback API fixture; cloud AI requires the explicit --gemini-free switch."""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "order-fulfillment-coordinator/apps/api/src"))
RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
STATE = ROOT / ".tools/teacher-qa" / RUN_ID
STATE.mkdir(parents=True, exist_ok=True)
DATABASE = STATE / "private-fixture.sqlite3"
(STATE.parent / "active.json").write_text(json.dumps({"run_id": RUN_ID, "database": str(DATABASE)}))
os.environ.update({
    "DATABASE_URL": "sqlite+aiosqlite:///" + DATABASE.as_posix(),
    "DATABASE_SYNC_URL": "sqlite:///" + DATABASE.as_posix(),
    "JWT_SECRET": "isolated-qa-key-never-valid-in-production",
    "WEBHOOK_SECRET": "isolated-qa-webhook-key", "DEBUG": "false",
    "OPENAI_API_KEY": "", "OPENAI_BASE_URL": "",
    "CHAT_API_KEY": "ollama" if "--no-llm" not in sys.argv else "",
    "CHAT_BASE_URL": "http://127.0.0.1:11434/v1", "CHAT_MODEL": "warehouse-os-qa-qwen",
    "CHAT_PROVIDER": "ollama-local", "CHAT_TIMEOUT_SECONDS": "90", "CHAT_MAX_OUTPUT_TOKENS": "80",
    "TEACHER_DEMO_MODE": "false" if "--no-demo" in sys.argv else "true", "QDRANT_URL": "http://127.0.0.1:9",
    "REDIS_URL": "redis://127.0.0.1:9/0", "CELERY_BROKER_URL": "redis://127.0.0.1:9/0",
    "CELERY_RESULT_BACKEND": "redis://127.0.0.1:9/0",
    "CORS_ORIGINS": "http://127.0.0.1:3318", "RATE_LIMIT_ENABLED": "false" if "--disable-global-rate-limit" in sys.argv else "true",
})
if "--gemini-free" in sys.argv:
    if os.environ.get("GEMINI_FREE_TIER_CONFIRMED") != "true" or not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("A confirmed free-tier Gemini credential is required")
    os.environ.update(CHAT_API_KEY=os.environ["GEMINI_API_KEY"],
        CHAT_BASE_URL="https://generativelanguage.googleapis.com/v1beta/openai/",
        CHAT_MODEL="gemini-3.5-flash-lite", CHAT_PROVIDER="gemini-free",
        CHAT_TIMEOUT_SECONDS="30", CHAT_MAX_OUTPUT_TOKENS="500")
from cryptography.fernet import Fernet
os.environ["INTEGRATION_SECRET_KEY"] = Fernet.generate_key().decode()

from sqlalchemy import select
from fulfillment.database import Base, async_session_factory, engine
from fulfillment.models import AgentEvent, Order, Shipment, User, UserRole
from fulfillment.models.order import OrderStatus
from fulfillment.models.shipment import ShipmentStatus
from fulfillment.security import hash_password
from fulfillment.main import app


async def seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session_factory() as db:
        for role in UserRole:
            email = f"qa-{role.value}@example.com"
            if not await db.scalar(select(User).where(User.email == email)):
                db.add(User(id=f"qa-{role.value}", email=email, name=f"Isolated QA {role.value}",
                    password_hash=hash_password("isolated-qa-password"), role=role, is_active=True))
        for index, status in enumerate([OrderStatus.PENDING, OrderStatus.SHIPPED, OrderStatus.DELIVERED], 1):
            identifier = f"11111111-1111-4111-8111-{index:012d}"
            if await db.get(Order, identifier):
                continue
            order = Order(id=identifier, customer_email=f"private-qa-{index}@example.com",
                shipping_address="PRIVATE-QA-ONLY FIXTURE ADDRESS", shipping_zip="54000",
                shipping_city=["Lahore", "Karachi", "Islamabad"][index-1], shipping_state="QA",
                shipping_country="PK", total_weight_kg=float(index), status=status,
                tracking_number=f"QA-TRACK-{index:03d}")
            db.add(order)
            await db.flush()
            if index > 1:
                db.add(Shipment(id=f"22222222-2222-4222-8222-{index:012d}", order_id=identifier,
                    carrier_name="QA Sample Courier", tracking_number=f"QA-TRACK-{index:03d}",
                    status=ShipmentStatus.DELIVERED if index==3 else ShipmentStatus.IN_TRANSIT,
                    origin_zip="54000", destination_zip="74000", weight_kg=float(index),
                    shipping_cost=250.0*index, is_delayed=index==2,
                    estimated_delivery=datetime.now(timezone.utc)+timedelta(days=1),
                    actual_delivery=datetime.now(timezone.utc) if index==3 else None))
        if not await db.get(AgentEvent, "qa-recorded-cycle"):
            db.add(AgentEvent(id="qa-recorded-cycle", agent_name="FulfillmentOrchestrator",
                event_type="cycle_complete", entity_id="qa-cycle", summary="Isolated QA fixture",
                details_json=json.dumps({"shipments_checked": 2, "delays_detected": 1,
                    "reroutes_initiated": 0, "notifications_sent": 0, "anomalies_found": 0})))
        await db.commit()


if __name__ == "__main__":
    import uvicorn
    asyncio.run(seed())
    port = int(sys.argv[sys.argv.index("--port")+1]) if "--port" in sys.argv else 8808
    uvicorn.run(app, host="127.0.0.1", port=port, proxy_headers=True, forwarded_allow_ips="127.0.0.1")
