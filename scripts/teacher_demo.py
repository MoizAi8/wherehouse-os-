"""Run an isolated Windows demonstration using real API, UI and SQLite data."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "order-fulfillment-coordinator/apps/api"
UI = ROOT / "agent-platform-ui-main/agent-platform-ui-main"
STATE = ROOT / ".tools/teacher-demo"
PYTHON = API / ".venv/Scripts/python.exe"
NODE = ROOT / ".tools/node-v24.22.2-win-x64/node.exe"

BOOTSTRAP = r'''
import asyncio, os
from sqlalchemy import select
import fulfillment.models
from fulfillment.database import async_session_factory, engine
from fulfillment.models.user import User, UserRole
from fulfillment.models.order import Order
from fulfillment.security import hash_password
from fulfillment.seed_data import seed_defaults
async def main():
    await seed_defaults()
    async with async_session_factory() as db:
        user = await db.scalar(select(User).where(User.email == 'teacher@example.com'))
        if user is None:
            db.add(User(email='teacher@example.com', name='Teacher demonstration',
                        password_hash=hash_password(os.environ['DEMO_PASSWORD']),
                        role=UserRole.ADMIN, is_active=True))
        order = await db.scalar(select(Order).where(Order.external_order_id == 'TEACHER-DEMO-001'))
        if order is None:
            db.add(Order(external_order_id='TEACHER-DEMO-001', customer_email='sample@example.com',
                         shipping_address='Demonstration address', shipping_zip='54000',
                         shipping_city='Lahore', shipping_state='Punjab', shipping_country='PK',
                         items_json='[{"sku":"DEMO-ITEM","quantity":1}]', total_weight_kg=1,
                         notes='Local demonstration sample; not a customer order.'))
        await db.commit()
    await engine.dispose()
asyncio.run(main())
'''


def wait_http(url: str, process: subprocess.Popen, timeout: int = 150) -> None:
    import httpx
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Service exited: see {STATE}")
        try:
            if httpx.get(url, timeout=5).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise RuntimeError(f"Startup timed out for {url}; see {STATE}")


def smoke(password: str) -> dict:
    import httpx
    results = {}
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=30) as api:
        health = api.get("/health")
        health.raise_for_status()
        results["backend_health"] = health.json()
        response = api.post("/api/auth/login", json={"email": "teacher@example.com", "password": password})
        response.raise_for_status()
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        assert api.get("/api/v1/orders").status_code in (401, 403)
        profile = api.get("/api/auth/me", headers=headers)
        profile.raise_for_status()
        results["authentication"] = "PASS: real backend login/profile; unauthenticated orders denied"
    with httpx.Client(base_url="http://localhost:3000", timeout=90) as ui:
        assert ui.get("/").status_code == 200
        csrf = ui.get("/api/auth/csrf").json()["csrfToken"]
        response = ui.post("/api/auth/callback/credentials", data={
            "csrfToken": csrf, "email": "teacher@example.com", "password": password,
            "callbackUrl": "http://localhost:3000/dashboard", "json": "true",
        })
        response.raise_for_status()
        session = ui.get("/api/auth/session").json()
        assert session.get("user", {}).get("email") == "teacher@example.com", "NextAuth login failed"
        results["frontend_authentication"] = "PASS: NextAuth credentials login against actual backend"
        orders = ui.get("/api/v1/orders", headers=headers)
        orders.raise_for_status()
        assert any(row["external_order_id"] == "TEACHER-DEMO-001" for row in orders.json()["orders"])
        results["frontend_backend_orders"] = "PASS: authenticated frontend proxy reads actual SQLite sample order"
        kpis = ui.get("/api/v1/analytics/kpis", headers=headers)
        kpis.raise_for_status()
        results["dashboard_api"] = "PASS: real backend KPI response through frontend proxy"
        assert ui.get("/dashboard").status_code == 200
        results["dashboard_page"] = "PASS: authenticated dashboard HTML responds"
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="Run real smoke tests, then stop both services")
    args = parser.parse_args()
    for required in (PYTHON, NODE, UI / "node_modules/next/dist/bin/next"):
        if not required.exists():
            raise RuntimeError(f"Missing installed prerequisite: {required}")
    for port in (8000, 3000):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError as exc:
                raise RuntimeError(f"Port {port} is occupied; stop its existing service first") from exc
    STATE.mkdir(parents=True, exist_ok=True)
    (STATE / "verification.json").unlink(missing_ok=True)
    config_path = STATE / "credentials.json"
    if config_path.exists():
        config = json.loads(config_path.read_text())
    else:
        from cryptography.fernet import Fernet
        config = {"password": secrets.token_urlsafe(18), "jwt": secrets.token_urlsafe(48),
                  "webhook": secrets.token_urlsafe(32), "integration": Fernet.generate_key().decode()}
        config_path.write_text(json.dumps(config), encoding="utf-8")
    env = os.environ.copy()
    env.update({
        "PYTHONPATH": str(API / "src"), "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1",
        "DEBUG": "false", "DATABASE_URL": f"sqlite+aiosqlite:///{(STATE / 'demo.db').as_posix()}",
        "DATABASE_SYNC_URL": f"sqlite:///{(STATE / 'demo.db').as_posix()}",
        "JWT_SECRET": config["jwt"], "WEBHOOK_SECRET": config["webhook"],
        "INTEGRATION_SECRET_KEY": config["integration"], "DEMO_PASSWORD": config["password"],
        "OPENAI_API_KEY": "", "OPENAI_BASE_URL": "", "QDRANT_URL": "", "QDRANT_API_KEY": "",
        "ODOO_URL": "", "ODOO_DB": "", "ODOO_USERNAME": "", "ODOO_PASSWORD": "",
        "TWILIO_ACCOUNT_SID": "", "TWILIO_AUTH_TOKEN": "", "SENDGRID_API_KEY": "",
        "REDIS_URL": "redis://127.0.0.1:6379/15", "CELERY_BROKER_URL": "redis://127.0.0.1:6379/15",
        "CELERY_RESULT_BACKEND": "redis://127.0.0.1:6379/15", "RATE_LIMIT_ENABLED": "true",
        "CORS_ORIGINS": "http://localhost:3000,http://127.0.0.1:3000",
        "NEXTAUTH_SECRET": config["jwt"], "NEXTAUTH_URL": "http://localhost:3000",
        "BACKEND_URL": "http://127.0.0.1:8000", "NEXT_PUBLIC_API_URL": "",
        "NEXT_PUBLIC_OPENAI_API_KEY": "", "NEXT_TELEMETRY_DISABLED": "1", "NODE_ENV": "development",
    })
    processes = []
    logs = []
    rules_path = UI / "AGENTS.md"
    rules_before = rules_path.read_text(encoding="utf-8")
    managed_pattern = r"<!-- BEGIN:nextjs-agent-rules -->.*?<!-- END:nextjs-agent-rules -->"
    managed_before = re.search(managed_pattern, rules_before, re.DOTALL)
    try:
        print("Preparing isolated demonstration database and starting the real backend/frontend...", flush=True)
        with (STATE / "bootstrap.log").open("w", encoding="utf-8") as log:
            subprocess.run([str(PYTHON), "-m", "alembic", "upgrade", "head"], cwd=API, env=env,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
            subprocess.run([str(PYTHON), "-c", BOOTSTRAP], cwd=API, env=env,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        commands = [
            ([str(PYTHON), "-m", "uvicorn", "fulfillment.main:app", "--host", "127.0.0.1", "--port", "8000"], API, "backend"),
            ([str(NODE), "node_modules/next/dist/bin/next", "dev", "--hostname", "127.0.0.1", "--port", "3000"], UI, "frontend"),
        ]
        for command, cwd, name in commands:
            log = (STATE / f"{name}.log").open("w", encoding="utf-8")
            logs.append(log)
            processes.append(subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT))
        wait_http("http://127.0.0.1:8000/docs", processes[0])
        wait_http("http://localhost:3000/api/auth/csrf", processes[1])
        results = smoke(config["password"])
        results["limitations"] = ["Local demonstration, not OCI", "SQLite, not PostgreSQL",
            "Redis/Celery/Qdrant unavailable unless independently running", "External AI, embeddings, Odoo, email/SMS unavailable",
            "Sample records are explicitly labelled demonstration data", "Backend health correctly remains degraded"]
        (STATE / "verification.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(json.dumps(results, indent=2), flush=True)
        print("\nFrontend: http://localhost:3000\nBackend: http://127.0.0.1:8000/docs", flush=True)
        if not args.verify:
            print(f"Login: teacher@example.com\nPassword: {config['password']}\nKeep this window open. Ctrl+C stops this demo.", flush=True)
            while all(process.poll() is None for process in processes):
                time.sleep(1)
            raise RuntimeError(f"A service stopped; see logs in {STATE}")
    except KeyboardInterrupt:
        print("Stopping demonstration.")
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
        for log in logs:
            log.close()
        # Next dev refreshes its managed instructions. Restore that block only,
        # preserving any unrelated edits made while the demonstration was open.
        if managed_before and rules_path.exists():
            current = rules_path.read_text(encoding="utf-8")
            restored = re.sub(managed_pattern, lambda _: managed_before.group(), current, flags=re.DOTALL)
            if restored != current:
                rules_path.write_text(restored, encoding="utf-8")


if __name__ == "__main__":
    main()
