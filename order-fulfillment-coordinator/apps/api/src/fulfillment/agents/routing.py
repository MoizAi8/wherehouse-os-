from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from fulfillment.models.agent_event import AgentEvent
from fulfillment.models.carrier_rate import CarrierRate
from fulfillment.models.fulfillment_center import FulfillmentCenter
from fulfillment.models.order import Order, OrderStatus
from fulfillment.models.shipment import Shipment, ShipmentStatus
from fulfillment.schemas.order import OrderRouteRequest


class RoutingError(Exception):
    pass


class RoutingAgent:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def select_fulfillment_center(
        self, order: Order, request: OrderRouteRequest, center_id: str | None = None
    ) -> FulfillmentCenter | None:
        eligible_rates = self._eligible_rates(
            order.shipping_zip, order.total_weight_kg, request.max_cost, request.max_days,
        ).where(CarrierRate.origin_zip == FulfillmentCenter.zip_code)
        query = (
            select(FulfillmentCenter)
            .where(FulfillmentCenter.is_active)
            .where(FulfillmentCenter.current_daily_orders < FulfillmentCenter.max_daily_orders)
            .where(eligible_rates.exists())
            .order_by(FulfillmentCenter.capacity_pct.asc(), FulfillmentCenter.id)
            .limit(1)
            .with_for_update()
        )
        if center_id is not None:
            query = query.where(FulfillmentCenter.id == center_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    def _eligible_rates(
        destination_zip: str,
        weight_kg: float,
        max_cost: float | None,
        max_days: int | None,
    ) -> Select[tuple[CarrierRate]]:
        total_cost = CarrierRate.base_rate + CarrierRate.rate_per_kg * weight_kg
        query = (
            select(CarrierRate)
            .where(CarrierRate.is_active)
            .where(CarrierRate.destination_zip == destination_zip)
            .where(CarrierRate.weight_kg_min <= weight_kg)
            .where(CarrierRate.weight_kg_max >= weight_kg)
        )
        if max_cost is not None:
            query = query.where(total_cost <= max_cost)
        if max_days is not None:
            query = query.where(CarrierRate.estimated_days_max <= max_days)
        return query

    async def get_best_rates(
        self,
        origin_zip: str,
        destination_zip: str,
        weight_kg: float,
        max_cost: float | None = None,
        max_days: int | None = None,
        preferred_carrier: str | None = None,
    ) -> list[CarrierRate]:
        query = self._eligible_rates(destination_zip, weight_kg, max_cost, max_days)
        query = query.where(CarrierRate.origin_zip == origin_zip)
        if preferred_carrier:
            query = query.order_by((CarrierRate.carrier_name == preferred_carrier).desc())
        total_cost = CarrierRate.base_rate + CarrierRate.rate_per_kg * weight_kg
        query = query.order_by(total_cost.asc(), CarrierRate.estimated_days_max, CarrierRate.id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def route_order(
        self, order: Order, request: OrderRouteRequest | None = None, *, center_id: str | None = None
    ) -> dict:
        request = request or OrderRouteRequest()
        fc = await self.select_fulfillment_center(order, request, center_id)
        if fc is None:
            raise RoutingError("No suitable route from an available fulfillment center")

        rates = await self.get_best_rates(
            origin_zip=fc.zip_code,
            destination_zip=order.shipping_zip,
            weight_kg=order.total_weight_kg,
            max_cost=request.max_cost,
            max_days=request.max_days,
            preferred_carrier=request.preferred_carrier,
        )
        if not rates:
            raise RoutingError("No suitable carrier rates found for route")

        best_rate = rates[0]
        shipping_cost = best_rate.base_rate + (best_rate.rate_per_kg * order.total_weight_kg)

        tracking_number = f"TRK-{uuid4().hex[:12].upper()}"

        order.fulfillment_center_id = fc.id
        order.carrier_id = best_rate.id
        order.tracking_number = tracking_number
        order.shipping_cost = shipping_cost
        order.status = OrderStatus.PROCESSING
        order.estimated_delivery = datetime.now(timezone.utc) + timedelta(days=best_rate.estimated_days_max)

        shipment = Shipment(
            id=str(uuid4()),
            order_id=order.id,
            carrier_name=best_rate.carrier_name,
            tracking_number=tracking_number,
            status=ShipmentStatus.LABEL_CREATED,
            estimated_delivery=order.estimated_delivery,
            origin_zip=fc.zip_code,
            destination_zip=order.shipping_zip,
            weight_kg=order.total_weight_kg,
            shipping_cost=shipping_cost,
        )
        self.db.add(shipment)

        fc.current_daily_orders += 1

        decision = {
            "fulfillment_center": {"id": fc.id, "name": fc.name},
            "carrier": {"id": best_rate.id, "name": best_rate.carrier_name, "service": best_rate.service_name},
            "tracking_number": tracking_number,
            "shipping_cost": shipping_cost,
            "estimated_delivery": order.estimated_delivery.isoformat(),
            "estimated_days": f"{best_rate.estimated_days_min}-{best_rate.estimated_days_max}",
        }
        self.db.add(AgentEvent(
            agent_name="RoutingAgent", event_type="route_selected", entity_id=order.id,
            summary="Selected a configured fulfillment center and carrier rate",
            details_json=json.dumps(decision),
        ))
        return decision
