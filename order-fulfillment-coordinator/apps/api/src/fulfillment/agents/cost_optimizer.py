from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from fulfillment.models.shipment import Shipment, ShipmentStatus

logger = logging.getLogger(__name__)


class CostOptimizer:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def analyze_cycle(self, cycle_id: str) -> dict:
        result = await self.db.execute(
            select(
                func.avg(Shipment.shipping_cost).label("avg_cost"),
                func.min(Shipment.shipping_cost).label("min_cost"),
                func.max(Shipment.shipping_cost).label("max_cost"),
                func.sum(Shipment.shipping_cost).label("total_cost"),
                func.count(Shipment.id).label("total_shipments"),
            ).where(Shipment.status != ShipmentStatus.CANCELLED)
        )
        stats = result.one()

        total = stats.total_shipments or 0
        if total == 0:
            return {
                "cycle_id": cycle_id,
                "analysis": "No shipments to analyze",
                "recommendations": [],
            }

        avg_cost = float(stats.avg_cost or 0)
        total_cost = float(stats.total_cost or 0)

        recommendations: list[dict] = []

        if avg_cost > 50:
            recommendations.append({
                "type": "cost_reduction",
                "priority": "medium",
                "suggestion": "Consider negotiating bulk rates with carriers to reduce average shipping cost",
                "current_avg": round(avg_cost, 2),
            })

        carrier_costs = await self.db.execute(
            select(
                Shipment.carrier_name,
                func.avg(Shipment.shipping_cost).label("avg_carrier_cost"),
                func.count(Shipment.id).label("carrier_count"),
            )
            .where(Shipment.status != ShipmentStatus.CANCELLED)
            .group_by(Shipment.carrier_name)
            .order_by(func.avg(Shipment.shipping_cost).desc())
        )

        for row in carrier_costs.all():
            if float(row.avg_carrier_cost or 0) > avg_cost * 1.2:
                recommendations.append({
                    "type": "carrier_cost_alert",
                    "priority": "low",
                    "carrier": row.carrier_name,
                    "suggestion": f"Carrier {row.carrier_name} has above-average costs",
                    "avg_cost": round(float(row.avg_carrier_cost or 0), 2),
                })

        return {
            "cycle_id": cycle_id,
            "analysis": {
                "total_shipments": total,
                "total_cost": round(total_cost, 2),
                "average_cost": round(avg_cost, 2),
                "min_cost": round(float(stats.min_cost or 0), 2),
                "max_cost": round(float(stats.max_cost or 0), 2),
            },
            "recommendations": recommendations,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }
