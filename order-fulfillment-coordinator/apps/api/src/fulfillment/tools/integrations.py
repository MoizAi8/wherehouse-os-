from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fulfillment.encryption import decrypt_secret
from fulfillment.models.integration import IntegrationConnection
from fulfillment.services.odoo_client import OdooClient

logger = logging.getLogger(__name__)


async def get_active_odoo_connection(db: AsyncSession) -> IntegrationConnection | None:
    result = await db.execute(
        select(IntegrationConnection).where(
            IntegrationConnection.provider == "odoo",
            IntegrationConnection.is_connected,
        ).order_by(IntegrationConnection.updated_at.desc())
    )
    return result.scalar_one_or_none()


def _odoo_client(conn: IntegrationConnection) -> OdooClient:
    """Build an OdooClient, decrypting the stored secret before use.

    ``IntegrationConnection.api_key`` holds a Fernet-encrypted ciphertext when
    ``INTEGRATION_SECRET_KEY`` is configured (see encryption.py). Passing the raw
    ciphertext as the Odoo password would always fail authentication, so the
    secret is decrypted here and never logged.
    """
    password = decrypt_secret(conn.api_key) or ""
    return OdooClient(
        url=conn.base_url,
        db=conn.db_name or "",
        username=conn.username or "",
        password=password,
    )


async def check_odoo_connection(db: AsyncSession) -> dict[str, Any]:
    conn = await get_active_odoo_connection(db)
    if conn is None:
        return {"connected": False, "error": "No active Odoo connection"}
    client = _odoo_client(conn)
    try:
        return await client.check_connection()
    finally:
        await client.close()


async def fetch_odoo_sale_orders(
    db: AsyncSession,
    limit: int = 50,
    state: str | None = None,
) -> list[dict[str, Any]]:
    conn = await get_active_odoo_connection(db)
    if conn is None:
        return []
    client = _odoo_client(conn)
    try:
        domain = [("state", "=", state)] if state else []
        return await client.get_sale_orders(domain=domain, limit=limit)
    finally:
        await client.close()


async def fetch_odoo_products(
    db: AsyncSession,
    limit: int = 50,
    category: str | None = None,
) -> list[dict[str, Any]]:
    conn = await get_active_odoo_connection(db)
    if conn is None:
        return []
    client = _odoo_client(conn)
    try:
        domain = [("categ_id.name", "=", category)] if category else []
        return await client.get_product_product(domain=domain, limit=limit)
    finally:
        await client.close()


async def create_odoo_sale_order(
    db: AsyncSession,
    partner_id: int,
    order_lines: list[dict[str, Any]],
) -> dict[str, Any]:
    conn = await get_active_odoo_connection(db)
    if conn is None:
        return {"success": False, "error": "No active Odoo connection"}
    client = _odoo_client(conn)
    try:
        order_vals = {
            "partner_id": partner_id,
            "order_line": [(0, 0, line) for line in order_lines],
        }
        order_id = await client.create("sale.order", order_vals)
        return {"success": True, "order_id": order_id}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
    finally:
        await client.close()
