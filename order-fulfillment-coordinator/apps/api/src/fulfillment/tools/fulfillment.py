from __future__ import annotations

import logging
from typing import Any
from datetime import date, datetime, timezone

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from fulfillment.models.fulfillment_center import FulfillmentCenter

logger = logging.getLogger(__name__)


def daily_count(center: FulfillmentCenter) -> int:
    if isinstance(center.capacity_day, date) and center.capacity_day != datetime.now(timezone.utc).date():
        return 0
    return center.current_daily_orders


async def list_fulfillment_centers(db: AsyncSession) -> list[dict[str, Any]]:
    result = await db.execute(
        select(FulfillmentCenter).where(FulfillmentCenter.is_active)
    )
    centers = list(result.scalars().all())
    return [
        {
            "id": c.id,
            "name": c.name,
            "address": c.address,
            "zip_code": c.zip_code,
            "city": c.city,
            "state": c.state,
            "capacity_pct": c.capacity_pct,
            "current_daily_orders": daily_count(c),
            "max_daily_orders": c.max_daily_orders,
        }
        for c in centers
    ]


async def find_nearest_fc(
    db: AsyncSession,
    zip_code: str,
) -> dict[str, Any] | None:
    result = await db.execute(
        select(FulfillmentCenter)
        .where(FulfillmentCenter.is_active)
        .where(FulfillmentCenter.max_daily_orders > 0)
        .where(or_(FulfillmentCenter.current_daily_orders < FulfillmentCenter.max_daily_orders,
                   FulfillmentCenter.capacity_day < datetime.now(timezone.utc).date()))
        .order_by(FulfillmentCenter.capacity_pct.asc())
        .limit(1)
    )
    fc = result.scalar_one_or_none()
    if fc is None:
        return None
    return {
        "id": fc.id,
        "name": fc.name,
        "zip_code": fc.zip_code,
        "city": fc.city,
        "state": fc.state,
        "capacity_pct": fc.capacity_pct,
        "current_daily_orders": daily_count(fc),
        "max_daily_orders": fc.max_daily_orders,
    }


async def get_fc_capacity(db: AsyncSession, fc_id: str) -> dict[str, Any] | None:
    result = await db.execute(
        select(FulfillmentCenter).where(FulfillmentCenter.id == fc_id)
    )
    fc = result.scalar_one_or_none()
    if fc is None:
        return None
    return {
        "id": fc.id,
        "name": fc.name,
        "capacity_pct": fc.capacity_pct,
        "current_daily_orders": daily_count(fc),
        "max_daily_orders": fc.max_daily_orders,
        "available_capacity": fc.max_daily_orders - daily_count(fc),
    }
