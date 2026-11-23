"""PostgreSQL-only instructor workspaces, isolated from operator sessions and data."""

from contextlib import asynccontextmanager
from hashlib import sha256

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from fulfillment.config import settings
from fulfillment.database import Base
from fulfillment.models.carrier_rate import CarrierRate
from fulfillment.models.fulfillment_center import FulfillmentCenter

COOLDOWN = {"Retry-After": "60"}


def identity(subject: str) -> str:
    return sha256(subject.encode()).hexdigest()


def sandbox_engine(schema: str | None = None) -> AsyncEngine:
    if not settings.instructor_database_url:
        raise HTTPException(404, "Hosted evaluation is disabled")
    url = make_url(settings.instructor_database_url)
    production = make_url(settings.async_database_url())
    if (
        url.drivername != "postgresql+asyncpg"
        or url.database != "warehouse_evaluation"
        or url.username != "warehouse_evaluator"
        or url.database == production.database
        or url.username == production.username
        or url.query
        or (url.host, url.port) != (production.host, production.port)
        or not url.host
    ):
        raise RuntimeError("Refusing an invalid instructor database configuration")
    if schema is not None and schema not in {f"workspace_{n}" for n in range(9)}:
        raise RuntimeError("Unknown evaluation slot")
    return create_async_engine(
        url,
        poolclass=NullPool,
        connect_args={
            "server_settings": {
                "search_path": schema or "public",
                "statement_timeout": "15000",
                "default_transaction_read_only": "on" if schema == "workspace_8" else "off",
            }
        },
    )


async def initialize_slot(conn: AsyncConnection, slot: int) -> None:
    if slot not in range(9):
        raise RuntimeError("Unknown instructor schema")
    schema = f"workspace_{slot}"
    # Only fixed, server-generated schema names in the dedicated database.
    await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    await conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
    await conn.run_sync(Base.metadata.create_all)
    await conn.execute(
        text(
            "CREATE TABLE instructor_mailbox(notice_id text PRIMARY KEY, received_at timestamptz DEFAULT now())"
        )
    )
    async with async_sessionmaker(conn).begin() as db:
        db.add(
            FulfillmentCenter(
                id="8d124467-baa8-49ae-a1fd-efa6868f5969",
                name="Evaluation Center",
                address="Sandbox",
                city="Test",
                state="NY",
                zip_code="90211",
            )
        )
        db.add(
            CarrierRate(
                carrier_name="Sandbox Ground",
                service_name="Ground",
                origin_zip="90211",
                destination_zip="10001",
                weight_kg_min=0,
                weight_kg_max=50,
                base_rate=10,
                rate_per_kg=1,
                estimated_days_min=2,
                estimated_days_max=3,
            )
        )


@asynccontextmanager
async def workspace(owner: str, *, write=False, allocate=True):
    """Hold a shared slot lock until the HTTP operation or Celery job finishes."""
    control = sandbox_engine()
    data = None
    try:
        async with control.connect() as conn:
            async with conn.begin():
                valid = await conn.scalar(
                    text("""
                    SELECT current_database()='warehouse_evaluation' AND current_user='warehouse_evaluator'
                    AND NOT (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)
                    AND NOT EXISTS (SELECT 1 FROM pg_auth_members WHERE member=r.oid)
                    FROM pg_roles r WHERE rolname=current_user
                """)
                )
                if not valid:
                    raise RuntimeError("Instructor database identity check failed")
                # The provisioning step owns this registry. Serialize allocation across API workers.
                await conn.execute(text("SELECT pg_advisory_xact_lock(826410)"))
                slot = await conn.scalar(
                    text("SELECT slot FROM public.instructor_slots WHERE owner=:owner"),
                    {"owner": owner},
                )
                # Empty reads use the read-only seed schema without occupying a visitor slot.
                if slot is None and (write or not allocate):
                    if not allocate:
                        raise RuntimeError("Workspace no longer assigned")
                    candidates = await conn.scalars(
                        text("""
                        SELECT slot FROM public.instructor_slots
                        WHERE owner IS NULL OR touched < now()-interval '2 hours'
                        ORDER BY touched NULLS FIRST, slot
                    """)
                    )
                    for n in candidates:
                        if await conn.scalar(
                            text("SELECT pg_try_advisory_xact_lock(826411,:n)"), {"n": n}
                        ):
                            slot = n
                            break
                    if slot is None:
                        raise HTTPException(
                            429, "All isolated workspaces are in use", headers=COOLDOWN
                        )
                    await initialize_slot(conn, slot)
                    await conn.execute(
                        text("""UPDATE public.instructor_slots SET owner=:owner, writes=0,
                        run=NULL, stage=NULL, result=NULL, started=NULL WHERE slot=:slot"""),
                        {"slot": slot, "owner": owner},
                    )
                # A session-level lock spans the separately committed warehouse transactions.
                if slot is not None:
                    await conn.execute(
                        text("SELECT pg_advisory_lock_shared(826411,:n)"), {"n": slot}
                    )
                    changed = await conn.execute(
                        text("""UPDATE public.instructor_slots SET touched=now(),
                        writes=writes+:inc WHERE slot=:slot AND (writes<300 OR :inc=0)"""),
                        {"inc": int(write), "slot": slot},
                    )
                    if not changed.rowcount:
                        raise HTTPException(429, "Workspace write limit reached", headers=COOLDOWN)
            data = sandbox_engine(f"workspace_{slot}" if slot is not None else "workspace_8")
            yield (
                conn,
                async_sessionmaker(data, expire_on_commit=False, info={"instructor_sandbox": True}),
                slot,
            )
    finally:
        if data is not None:
            await data.dispose()
        await control.dispose()
