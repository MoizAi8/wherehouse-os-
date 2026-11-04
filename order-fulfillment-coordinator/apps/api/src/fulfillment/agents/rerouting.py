from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fulfillment.config import settings
from fulfillment.models.carrier_rate import CarrierRate
from fulfillment.models.shipment import Shipment, ShipmentStatus
from fulfillment.guardrails.carrier_diversity import carrier_diversity

logger = logging.getLogger(__name__)

COST_INCREASE_LIMIT_PCT = 40.0


def _ensure_aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class ReroutingAgent:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def evaluate_reroute(self, shipment: Shipment) -> dict:
        rates_result = await self.db.execute(
            select(CarrierRate)
            .where(CarrierRate.is_active)
            .where(CarrierRate.origin_zip == shipment.origin_zip)
            .where(CarrierRate.destination_zip == shipment.destination_zip)
            .where(CarrierRate.weight_kg_min <= shipment.weight_kg)
            .where(CarrierRate.weight_kg_max >= shipment.weight_kg)
            .where(CarrierRate.carrier_name != shipment.carrier_name)
            .order_by(
                CarrierRate.base_rate + CarrierRate.rate_per_kg * shipment.weight_kg,
                CarrierRate.estimated_days_max, CarrierRate.id,
            )
        )
        alternatives = list(rates_result.scalars().all())

        if not alternatives:
            return {"should_reroute": False, "reason": "No alternative carriers available"}

        best_alternative = next(
            (rate for rate in alternatives if carrier_diversity(shipment.carrier_name, rate.carrier_name)),
            None,
        )
        if best_alternative is None:
            return {"should_reroute": False, "reason": "Carrier diversity constraint"}

        current_cost = shipment.shipping_cost or 0
        new_cost = best_alternative.base_rate + (best_alternative.rate_per_kg * shipment.weight_kg)

        cost_increase_pct = ((new_cost - current_cost) / current_cost) * 100 if current_cost > 0 else 0
        max_allowed = settings.max_allowed_cost_increase_pct

        if cost_increase_pct > max_allowed:
            return {
                "should_reroute": False,
                "reason": f"Alternative cost increase ({cost_increase_pct:.1f}%) exceeds limit ({max_allowed}%)",
            }

        est = _ensure_aware(shipment.estimated_delivery)
        delta_days = abs(
            (est - datetime.now(timezone.utc)).total_seconds() / 86400
        ) if est else 0

        return {
            "should_reroute": True,
            "alternative_carrier": best_alternative.carrier_name,
            "alternative_service": best_alternative.service_name,
            "alternative_rate_id": best_alternative.id,
            "new_cost": new_cost,
            "current_cost": current_cost,
            "cost_increase_pct": round(((new_cost - current_cost) / current_cost) * 100, 2) if current_cost > 0 else 0,
            "estimated_days_min": best_alternative.estimated_days_min,
            "estimated_days_max": best_alternative.estimated_days_max,
            "urgency": "high" if delta_days < 1 else "medium",
        }

    async def execute_reroute(self, shipment: Shipment, reroute_data: dict) -> dict | None:
        if not reroute_data.get("should_reroute"):
            return None

        new_tracking = f"TRK-{uuid4().hex[:12].upper()}"
        previous_carrier = shipment.carrier_name

        shipment.carrier_name = reroute_data["alternative_carrier"]
        shipment.tracking_number = new_tracking
        shipment.status = ShipmentStatus.LABEL_CREATED
        shipment.is_delayed = False
        shipment.delay_reason = None
        shipment.shipping_cost = reroute_data["new_cost"]
        shipment.estimated_delivery = datetime.now(timezone.utc) + timedelta(days=reroute_data["estimated_days_max"])
        shipment.last_polled_at = None
        shipment.carrier_event_at = None
        shipment.carrier_event_hash = None

        return {
            "previous_carrier": previous_carrier,
            "new_carrier": reroute_data["alternative_carrier"],
            "new_tracking": new_tracking,
            "new_cost": reroute_data["new_cost"],
            "previous_cost": reroute_data["current_cost"],
        }
