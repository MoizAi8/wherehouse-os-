from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select, case, ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession

from fulfillment.models.order import Order, OrderStatus
from fulfillment.models.shipment import Shipment
from fulfillment.schemas.analytics import CarrierAnalyticsResponse, KPIsResponse

logger = logging.getLogger(__name__)


class AnalyticsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _delivery_days(self) -> ColumnElement[float | Decimal]:
        # Duration starts when the shipment was created, not at its ETA.
        # SQLite datetime subtraction is numeric string coercion, not an interval.
        if self.db.get_bind().dialect.name == "sqlite":
            return func.julianday(Shipment.actual_delivery) - func.julianday(Shipment.created_at)
        return func.extract("epoch", Shipment.actual_delivery - Shipment.created_at) / 86400

    async def compute_kpis(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> KPIsResponse:
        base = select(func.count(Order.id))
        total_orders = await self._scalar(base)

        shipped_count = await self._scalar(
            base.where(Order.status.in_([OrderStatus.SHIPPED, OrderStatus.DELIVERED]))
        )
        delivered_count = await self._scalar(
            base.where(Order.status == OrderStatus.DELIVERED)
        )

        delayed_count_q = select(func.count(Shipment.id)).where(Shipment.is_delayed)
        if start_date:
            delayed_count_q = delayed_count_q.where(Shipment.updated_at >= start_date)
        if end_date:
            delayed_count_q = delayed_count_q.where(Shipment.updated_at <= end_date)
        delayed_count = await self._scalar(delayed_count_q)

        on_time_rate = 0.0
        completed = await self._scalar(select(func.count(Shipment.id)).where(Shipment.actual_delivery.isnot(None)))
        if completed > 0:
            on_time = await self._scalar(select(func.count(Shipment.id)).where(
                Shipment.actual_delivery.isnot(None), Shipment.estimated_delivery.isnot(None),
                Shipment.actual_delivery <= Shipment.estimated_delivery))
            on_time_rate = round((on_time / completed) * 100, 2)

        avg_delivery = await self._scalar(
            select(
                func.avg(self._delivery_days())
            ).where(Shipment.actual_delivery.isnot(None))
        )

        cost_sum = await self._scalar(
            select(func.coalesce(func.sum(Shipment.shipping_cost), 0)).where(
                Shipment.shipping_cost.isnot(None)
            )
        )
        cost_count = await self._scalar(
            select(func.count(Shipment.id)).where(Shipment.shipping_cost.isnot(None))
        )
        avg_cost = round(cost_sum / cost_count, 2) if cost_count > 0 else 0.0

        failed_count = await self._scalar(
            base.where(Order.status == OrderStatus.CANCELLED)
        )
        failed_rate = round((failed_count / total_orders) * 100, 2) if total_orders > 0 else 0.0

        return KPIsResponse(
            total_orders=int(total_orders),
            orders_shipped=int(shipped_count),
            orders_delivered=int(delivered_count),
            orders_delayed=int(delayed_count),
            on_time_delivery_rate=on_time_rate,
            avg_delivery_time_days=round(abs(avg_delivery or 0.0), 2),
            total_shipping_cost=round(cost_sum, 2),
            avg_shipping_cost=avg_cost,
            failed_delivery_rate=failed_rate,
            period_start=start_date,
            period_end=end_date,
        )

    async def carrier_performance(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[CarrierAnalyticsResponse]:
        query = (
            select(
                Shipment.carrier_name,
                func.count(Shipment.id).label("total_shipments"),
                func.sum(
                    case((~Shipment.is_delayed, 1), else_=0)
                ).label("on_time_shipments"),
                func.sum(
                    case((Shipment.is_delayed.is_(True), 1), else_=0)
                ).label("delayed_shipments"),
                func.avg(Shipment.shipping_cost).label("avg_cost"),
                func.sum(Shipment.shipping_cost).label("total_cost"),
                func.avg(self._delivery_days()).label("avg_delivery_days"),
            )
            .group_by(Shipment.carrier_name)
        )

        if start_date:
            query = query.where(Shipment.created_at >= start_date)
        if end_date:
            query = query.where(Shipment.created_at <= end_date)

        result = await self.db.execute(query)
        rows = result.all()

        response: list[CarrierAnalyticsResponse] = []
        for row in rows:
            total = row.total_shipments or 0
            on_time = row.on_time_shipments or 0
            on_time_rate = round((on_time / total) * 100, 2) if total > 0 else 0.0
            response.append(
                CarrierAnalyticsResponse(
                    carrier_name=row.carrier_name,
                    total_shipments=total,
                    on_time_shipments=on_time,
                    delayed_shipments=row.delayed_shipments or 0,
                    on_time_rate=on_time_rate,
                    avg_cost=round(float(row.avg_cost or 0.0), 2),
                    total_cost=round(float(row.total_cost or 0.0), 2),
                    avg_delivery_days=round(abs(float(row.avg_delivery_days or 0.0)), 2),
                )
            )
        return response

    async def _scalar(self, query) -> int | float:
        result = await self.db.execute(query)
        return result.scalar() or 0
