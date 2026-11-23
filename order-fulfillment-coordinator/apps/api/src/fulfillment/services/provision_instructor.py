"""Provision only the reserved instructor database on the existing PostgreSQL cluster."""

import asyncio
import re
import sys

import asyncpg
from sqlalchemy import text
from sqlalchemy.engine import URL, make_url

from fulfillment.config import settings
from fulfillment.services.instructor_workspace import initialize_slot, sandbox_engine


async def provision() -> None:
    engine = sandbox_engine()  # shared fail-closed role/database and DSN validation
    admin_url = make_url(settings.async_database_url())
    url = make_url(settings.instructor_database_url)
    if (url.host, url.port) != (admin_url.host, admin_url.port) or not re.fullmatch(
        r"[a-fA-F0-9]{64}", url.password or ""
    ):
        raise RuntimeError(
            "Instructor database must use the same host and its own generated credential"
        )

    async def connect(address: URL) -> asyncpg.Connection:
        return await asyncpg.connect(
            address.set(drivername="postgresql").render_as_string(hide_password=False)
        )

    admin = await connect(admin_url)
    try:
        await admin.execute("SELECT pg_advisory_lock(826414)")
        existing = await admin.fetchval(
            "SELECT 1 FROM pg_roles WHERE rolname='warehouse_evaluator'"
        )
        if not existing:
            await admin.execute(
                f"CREATE ROLE warehouse_evaluator LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                f"NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 24 PASSWORD '{url.password}'"
            )
        # Authenticate before making a database for an existing identity. Never adopt or rotate another role.
        if existing:
            owner = await connect(url.set(database="postgres"))
            await owner.close()
        safe = await admin.fetchval("""SELECT NOT(rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)
            AND rolconnlimit=24 AND NOT EXISTS(SELECT 1 FROM pg_auth_members WHERE member=r.oid)
            FROM pg_roles r WHERE rolname='warehouse_evaluator'""")
        if not safe:
            raise RuntimeError("Unsafe evaluator role")
        business_access = await admin.fetchval("""
            SELECT EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m') AND
            has_table_privilege('warehouse_evaluator',c.oid,'SELECT, INSERT, UPDATE, DELETE, TRUNCATE'))
            OR has_schema_privilege('warehouse_evaluator','public','CREATE')
        """)
        if business_access:
            raise RuntimeError("Evaluator role has privileges in the business database")
        owned = await admin.fetchval(
            """SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='warehouse_evaluation'"""
        )
        if owned is None:
            await admin.execute("CREATE DATABASE warehouse_evaluation OWNER warehouse_evaluator")
        elif owned != "warehouse_evaluator":
            raise RuntimeError("Instructor database belongs to another owner")
        await admin.execute("REVOKE CONNECT ON DATABASE warehouse_evaluation FROM PUBLIC")
    finally:
        await admin.close()
    owner = await connect(url)
    try:
        await owner.execute(sys.stdin.read())
    finally:
        await owner.close()
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT pg_advisory_xact_lock(826410)"))
            if not await conn.scalar(text("SELECT to_regnamespace('workspace_8') IS NOT NULL")):
                await initialize_slot(conn, 8)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(provision())
