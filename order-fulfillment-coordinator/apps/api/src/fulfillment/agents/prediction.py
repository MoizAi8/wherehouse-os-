from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from fulfillment.models.shipment import Shipment

logger = logging.getLogger(__name__)


class PredictionAgent:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def predict_failure(self, shipment: Shipment) -> dict:
        probability = await self._calculate_failure_probability(shipment)
        risk_level = "low"
        if probability > 0.7:
            risk_level = "high"
        elif probability > 0.4:
            risk_level = "medium"

        return {
            "shipment_id": shipment.id,
            "tracking_number": shipment.tracking_number,
            "failure_probability": round(probability, 4),
            "risk_level": risk_level,
            "factors": await self._get_risk_factors(shipment),
            "predicted_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _calculate_failure_probability(self, shipment: Shipment) -> float:
        probability = 0.0

        if shipment.is_delayed:
            probability += 0.3

        if shipment.estimated_delivery:
            now = datetime.now(timezone.utc)
            if shipment.estimated_delivery.tzinfo is None:
                from datetime import timezone as tz
                est = shipment.estimated_delivery.replace(tzinfo=tz.utc)
            else:
                est = shipment.estimated_delivery
            hours_overdue = (now - est).total_seconds() / 3600
            if hours_overdue > 0:
                probability += min(hours_overdue / 48, 0.3)

        carrier_history = await self._get_carrier_failure_rate(shipment.carrier_name)
        probability += carrier_history * 0.2

        if shipment.status.value in ("exception", "delayed"):
            probability += 0.15

        return min(probability, 0.95)

    async def _get_carrier_failure_rate(self, carrier_name: str) -> float:
        from sqlalchemy.types import Integer
        result = await self.db.execute(
            select(
                func.avg(
                    func.cast(Shipment.is_delayed, Integer)  # type: ignore
                )
            ).where(Shipment.carrier_name == carrier_name)
        )
        rate = result.scalar()
        return float(rate) if rate is not None else 0.0

    async def _get_risk_factors(self, shipment: Shipment) -> list[dict]:
        factors: list[dict] = []

        if shipment.is_delayed:
            factors.append({
                "factor": "current_delay",
                "weight": 0.3,
                "detail": shipment.delay_reason or "Shipment is currently delayed",
            })

        if shipment.estimated_delivery:
            now = datetime.now(timezone.utc)
            est = shipment.estimated_delivery
            if est.tzinfo is None:
                est = est.replace(tzinfo=timezone.utc)
            hours_remaining = (est - now).total_seconds() / 3600
            if hours_remaining < 0:
                factors.append({
                    "factor": "overdue",
                    "weight": 0.3,
                    "detail": f"Shipment is {abs(hours_remaining):.1f} hours overdue",
                })
            elif hours_remaining < 24:
                factors.append({
                    "factor": "tight_schedule",
                    "weight": 0.1,
                    "detail": f"Only {hours_remaining:.1f} hours remaining until estimated delivery",
                })

        if shipment.status.value in ("exception",):
            factors.append({
                "factor": "carrier_exception",
                "weight": 0.15,
                "detail": "Carrier reported an exception",
            })

        carrier_rate = await self._get_carrier_failure_rate(shipment.carrier_name)
        if carrier_rate > 0.1:
            factors.append({
                "factor": "carrier_history",
                "weight": 0.2,
                "detail": f"Carrier historical delay rate: {carrier_rate:.1%}",
            })

        return factors
