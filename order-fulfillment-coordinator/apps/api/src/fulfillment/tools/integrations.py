from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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


async def check_odoo_connection(db: AsyncSession) -> dict[str, Any]:
    conn = await get_active_odoo_connection(db)
    if conn is None:
        return {"connected": False, "error": "No active Odoo connection"}
    client = OdooClient(
        url=conn.base_url,
        db=conn.db_name or "",
        username=conn.username or "",
        password=conn.api_key or "",
    )
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
    client = OdooClient(
        url=conn.base_url,
        db=conn.db_name or "",
        username=conn.username or "",
        password=conn.api_key or "",
    )
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
    client = OdooClient(
        url=conn.base_url,
        db=conn.db_name or "",
        username=conn.username or "",
        password=conn.api_key or "",
    )
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
    client = OdooClient(
        url=conn.base_url,
        db=conn.db_name or "",
        username=conn.username or "",
        password=conn.api_key or "",
    )
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
