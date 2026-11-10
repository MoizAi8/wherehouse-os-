from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fulfillment.models.inventory import OrderLine
from fulfillment.models.order import Order, OrderStatus
from fulfillment.models.shipment import Shipment, ShipmentStatus
from fulfillment.models.carrier_booking import CarrierBooking

logger = logging.getLogger(__name__)

MAX_SHIPMENTS_PER_CYCLE = 200


def _active_shipment() -> ColumnElement[bool]:
    awaiting_dispatch = (
        select(Order.id).join(OrderLine, OrderLine.order_id == Order.id)
        .where(Order.id == Shipment.order_id, Order.status == OrderStatus.PROCESSING)
        .exists()
    )
    awaiting_booking = select(CarrierBooking.id).where(
        CarrierBooking.shipment_id == Shipment.id, CarrierBooking.active,
        CarrierBooking.status != "booked",
    ).exists()
    return Shipment.status.notin_([
        ShipmentStatus.DELIVERED, ShipmentStatus.RETURNED, ShipmentStatus.CANCELLED,
    ]) & ~awaiting_dispatch & ~awaiting_booking


def _ensure_aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class MonitorAgent:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_active_shipments(
        self, entity_ids: list[str] | None = None, offset: int = 0
    ) -> list[Shipment]:
        query = select(Order.id).join(Shipment, Shipment.order_id == Order.id).where(_active_shipment())
        if entity_ids:
            query = query.where(Shipment.id.in_(entity_ids))
        query = query.order_by(Shipment.last_monitored_at.asc().nullsfirst(), Shipment.id).offset(offset).limit(MAX_SHIPMENTS_PER_CYCLE)
        # Use the same order lock as dispatch, cancellation and carrier events.
        # Refresh the shipment in a second statement after waiting for that lock.
        order_ids = list((await self.db.execute(query.with_for_update(of=Order))).scalars().all())
        if not order_ids:
            return []
        refreshed = select(Shipment).where(Shipment.order_id.in_(order_ids), _active_shipment())
        if entity_ids:
            refreshed = refreshed.where(Shipment.id.in_(entity_ids))
        result = await self.db.execute(refreshed.order_by(
            Shipment.last_monitored_at.asc().nullsfirst(), Shipment.id,
        ).limit(MAX_SHIPMENTS_PER_CYCLE).execution_options(populate_existing=True))
        return list(result.scalars().all())

    async def count_active_shipments(self, entity_ids: list[str] | None = None) -> int:
        query = select(func.count(Shipment.id)).where(_active_shipment())
        if entity_ids:
            query = query.where(Shipment.id.in_(entity_ids))
        result = await self.db.execute(query)
        return result.scalar() or 0

    async def check_delay(self, shipment: Shipment) -> dict:
        now = datetime.now(timezone.utc)
        # Rotate bounded batches without pretending a carrier supplied a new event.
        shipment.last_monitored_at = now
        is_delayed = False
        reason = None
        risk_score = 0.0

        est_delivery = _ensure_aware(shipment.estimated_delivery)
        last_polled = _ensure_aware(shipment.last_polled_at)

        if shipment.status == ShipmentStatus.DELAYED:
            is_delayed = True
            reason = shipment.delay_reason or "Shipment status is delayed"

        if est_delivery and now > est_delivery:
            diff_hours = (now - est_delivery).total_seconds() / 3600
            is_delayed = True
            reason = reason or f"Past estimated delivery by {diff_hours:.1f} hours"
            risk_score = min(diff_hours / 24, 1.0)

        if not is_delayed and last_polled:
            hours_since_poll = (now - last_polled).total_seconds() / 3600
            if hours_since_poll > 24:
                is_delayed = True
                reason = f"No status update in {hours_since_poll:.1f} hours"
                risk_score = 0.3

        if is_delayed:
            shipment.is_delayed = True
            shipment.delay_reason = reason
            shipment.status = ShipmentStatus.DELAYED

        return {
            "is_delayed": is_delayed,
            "reason": reason,
            "risk_score": risk_score,
            "checked_at": now.isoformat(),
        }
