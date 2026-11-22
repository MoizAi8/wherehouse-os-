"""Run a single instructor workspace on this PC using a fresh DB and private broker."""

import asyncio
import hashlib
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

import asyncpg
from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".tools/instructor-workspace"
UI = ROOT / "agent-platform-ui-main/agent-platform-ui-main"
API = ROOT / "order-fulfillment-coordinator/apps/api"
NODE = ROOT / ".tools/node-v24.22.2-win-x64/node.exe"
ORIGIN = os.environ.get("EVALUATION_ORIGIN", "http://127.0.0.1:8387")


def rotate():
    token = secrets.token_urlsafe(40)
    STATE.mkdir(parents=True, exist_ok=True)
    (STATE / "generation").write_text(secrets.token_hex(32))
    tmp = STATE / "invitation.new"
    tmp.write_text(hashlib.sha256(token.encode()).hexdigest())
    tmp.replace(STATE / "invitation.sha256")
    return ORIGIN + "/invite#" + token


async def provision(password):
    admin = await asyncpg.connect(
        host="127.0.0.1",
        port=55471,
        user="inventory_test",
        database="watch_20261110185156",
        password=(ROOT / ".tools/inventory-pg-20261104/password").read_text().strip(),
    )
    try:
        # Never adopt an existing database or change an existing login.
        suffix = secrets.token_hex(8)
        name = "instructor_eval_" + suffix
        await admin.execute(
            f"CREATE ROLE {name} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD '{password}'"
        )
        await admin.execute(f"CREATE DATABASE {name} OWNER {name}")
        await admin.execute(f"REVOKE CONNECT ON DATABASE {name} FROM PUBLIC")
        return name
    finally:
        await admin.close()


def main():
    STATE.mkdir(parents=True, exist_ok=True)
    if sys.argv[1:] == ["invite"]:
        # Owner-only terminal output. Never run this command with stdout logging.
        print(rotate())
        return
    if sys.argv[1:] == ["revoke"]:
        (STATE / "generation").unlink(missing_ok=True)
        (STATE / "invitation.sha256").unlink(missing_ok=True)
        return
    if sys.argv[1:]:
        raise SystemExit("Use no arguments, invite, or revoke")
    for port in (3386, 8386, 8387, 56386):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))
    if not (UI / ".next-instructor/BUILD_ID").is_file():
        raise RuntimeError("Build the instructor UI first")
    for marker in ("invitation.sha256", "generation"):
        (STATE / marker).unlink(missing_ok=True)
    pw = secrets.token_hex(32)
    db = asyncio.run(provision(pw))
    env = {
        k: v
        for k, v in os.environ.items()
        if k.upper()
        in (
            "PATH",
            "SYSTEMROOT",
            "WINDIR",
            "COMSPEC",
            "TEMP",
            "TMP",
            "LOCALAPPDATA",
            "APPDATA",
            "USERPROFILE",
            "PROGRAMFILES",
            "PROGRAMFILES(X86)",
            "PATHEXT",
            "SYSTEMDRIVE",
            "NUMBER_OF_PROCESSORS",
        )
    }
    env.update(
        PYTHONPATH=str(API / "src") + os.pathsep + str(ROOT / "evaluation"),
        PYTHONUNBUFFERED="1",
        DATABASE_URL=f"postgresql+asyncpg://{db}:{pw}@127.0.0.1:55471/{db}",
        DEBUG="false",
        JWT_SECRET=secrets.token_hex(48),
        WEBHOOK_SECRET=secrets.token_hex(32),
        INTEGRATION_SECRET_KEY=Fernet.generate_key().decode(),
        REDIS_URL="redis://127.0.0.1:56386/0",
        CELERY_BROKER_URL="redis://127.0.0.1:56386/0",
        CELERY_RESULT_BACKEND="redis://127.0.0.1:56386/0",
        QDRANT_URL="http://127.0.0.1:56333",
        CARRIER_SANDBOX_ENABLED="true",
        CARRIER_BOOKING_PROVIDER="sandbox",
        EVALUATION_STATE=str(STATE),
        EVALUATION_ORIGIN=ORIGIN,
        EVALUATION_RELEASE_BUILD="1",
        EVALUATION_OPERATOR_SECRET=secrets.token_urlsafe(48),
        DEMO_GUEST_ENABLED="false",
        TEACHER_DEMO_MODE="false",
        ALLOW_AUTOMATIC_REROUTING="false",
    )
    if os.environ.get("EVALUATION_GEMINI_API_KEY") and os.environ.get(
        "EVALUATION_GEMINI_MODEL"
    ):
        env.update(
            CHAT_PROVIDER="gemini-free",
            CHAT_BASE_URL="https://generativelanguage.googleapis.com/v1beta/openai/",
            CHAT_API_KEY=os.environ["EVALUATION_GEMINI_API_KEY"],
            CHAT_MODEL=os.environ["EVALUATION_GEMINI_MODEL"],
        )
    tasks = []

    def start(name, args, cwd=STATE, custom=None):
        with (STATE / (name + ".log")).open("wb") as log:
            tasks.append(
                subprocess.Popen(
                    args,
                    env=custom or env,
                    cwd=cwd,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
            )

    try:
        start(
            "broker",
            [
                ROOT / ".tools/memurai-4.1.7/package/tools/memurai.exe",
                "--bind",
                "127.0.0.1",
                "--port",
                "56386",
                "--save",
                "",
                "--appendonly",
                "no",
                "--dbfilename",
                db + ".rdb",
            ],
        )
        start("api", [sys.executable, ROOT / "evaluation/backend.py"])
        start(
            "readiness",
            [
                sys.executable,
                "-m",
                "celery",
                "-A",
                "fulfillment.tasks.monitor_cycle:celery_app",
                "worker",
                "--pool=solo",
                "--concurrency=1",
                "-Q",
                "readiness",
                "-I",
                "fulfillment.tasks.health",
            ],
        )
        front = {
            k: v
            for k, v in env.items()
            if k.upper()
            in (
                "PATH",
                "SYSTEMROOT",
                "WINDIR",
                "COMSPEC",
                "TEMP",
                "TMP",
                "LOCALAPPDATA",
                "APPDATA",
                "USERPROFILE",
                "PATHEXT",
                "SYSTEMDRIVE",
            )
        }
        front.update(
            PATH=str(NODE.parent) + os.pathsep + front["PATH"],
            BACKEND_URL="http://127.0.0.1:8386",
            NEXTAUTH_URL="http://127.0.0.1:3386",
            NEXTAUTH_SECRET=secrets.token_hex(40),
            NEXT_PUBLIC_INSTRUCTOR_WORKSPACE="1",
            NEXT_TELEMETRY_DISABLED="1",
        )
        start(
            "ui",
            [
                NODE,
                UI / "node_modules/next/dist/bin/next",
                "start",
                "--hostname",
                "127.0.0.1",
                "-p",
                "3386",
            ],
            UI,
            front,
        )
        start(
            "gateway",
            [
                sys.executable,
                "-m",
                "uvicorn",
                "gateway:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8387",
                "--no-access-log",
            ],
        )
        while all(p.poll() is None for p in tasks):
            time.sleep(1)
        raise RuntimeError("Instructor service exited. See local service logs.")
    finally:
        for p in reversed(tasks):
            if p.poll() is None:
                p.terminate()


if __name__ == "__main__":
    main()
