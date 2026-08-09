from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fulfillment.models.carrier_rate import CarrierRate
from fulfillment.models.order import Order, OrderStatus
from fulfillment.models.shipment import Shipment, ShipmentStatus
from fulfillment.schemas.shipment import ShipmentRead, ShipmentRerouteRequest, ShipmentRerouteResponse
from fulfillment.schemas.webhook import ShipmentEventWebhook

logger = logging.getLogger(__name__)


def _coerce_shipment_status(raw: str) -> ShipmentStatus:
    try:
        return ShipmentStatus(raw)
    except ValueError:
        raise ValueError(
            f"Invalid shipment status '{raw}'. Valid: {[e.value for e in ShipmentStatus]}"
        )


class ShipmentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_shipments(
        self,
        skip: int = 0,
        limit: int = 100,
        status_filter: str | None = None,
    ) -> list[ShipmentRead]:
        query = select(Shipment).offset(skip).limit(limit).order_by(Shipment.created_at.desc())
        if status_filter:
            query = query.where(Shipment.status == _coerce_shipment_status(status_filter))
        result = await self.db.execute(query)
        shipments = list(result.scalars().all())
        return [ShipmentRead.model_validate(s) for s in shipments]

    async def get_shipment(self, shipment_id: str) -> ShipmentRead | None:
        result = await self.db.execute(select(Shipment).where(Shipment.id == shipment_id))
        shipment = result.scalar_one_or_none()
        if shipment is None:
            return None
        return ShipmentRead.model_validate(shipment)

    async def reroute_shipment(
        self,
        shipment_id: str,
        payload: ShipmentRerouteRequest,
    ) -> ShipmentRerouteResponse:
        result = await self.db.execute(select(Shipment).where(Shipment.id == shipment_id))
        shipment = result.scalar_one_or_none()
        if shipment is None:
            raise ValueError("Shipment not found")

        previous_carrier = shipment.carrier_name

        rate_result = await self.db.execute(
            select(CarrierRate)
            .where(CarrierRate.is_active)
            .where(CarrierRate.carrier_name == payload.new_carrier_name)
            .where(CarrierRate.origin_zip == shipment.origin_zip)
            .where(CarrierRate.destination_zip == shipment.destination_zip)
            .where(CarrierRate.weight_kg_min <= shipment.weight_kg)
            .where(CarrierRate.weight_kg_max >= shipment.weight_kg)
            .order_by(CarrierRate.base_rate.asc())
            .limit(1)
        )
        new_rate = rate_result.scalar_one_or_none()
        if new_rate is None:
            raise ValueError(f"No rates available for carrier: {payload.new_carrier_name}")

        new_tracking = f"TRK-{uuid4().hex[:12].upper()}"
        additional_cost = (new_rate.base_rate + new_rate.rate_per_kg * shipment.weight_kg) - (shipment.shipping_cost or 0)

        shipment.carrier_name = payload.new_carrier_name
        shipment.tracking_number = new_tracking
        shipment.status = ShipmentStatus.LABEL_CREATED
        shipment.estimated_delivery = datetime.now(timezone.utc)
        shipment.shipping_cost = new_rate.base_rate + new_rate.rate_per_kg * shipment.weight_kg
        shipment.is_delayed = False
        shipment.delay_reason = None
        shipment.last_polled_at = datetime.now(timezone.utc)

        await self.db.flush()
        await self.db.refresh(shipment)

        return ShipmentRerouteResponse(
            shipment_id=shipment.id,
            previous_carrier=previous_carrier,
            new_carrier=payload.new_carrier_name,
            new_tracking_number=new_tracking,
            new_estimated_delivery=shipment.estimated_delivery,
            additional_cost=max(0.0, additional_cost),
            reroute_details={
                "reason": payload.reason,
                "service": new_rate.service_name,
                "estimated_days": f"{new_rate.estimated_days_min}-{new_rate.estimated_days_max}",
            },
        )

    async def update_from_event(self, payload: ShipmentEventWebhook) -> Shipment:
        result = await self.db.execute(
            select(Shipment).where(
                Shipment.tracking_number == payload.tracking_number,
                Shipment.carrier_name == payload.carrier,
            )
        )
        shipment = result.scalar_one_or_none()
        if shipment is None:
            raise ValueError(f"Shipment not found for tracking: {payload.tracking_number}")

        shipment.status = ShipmentStatus(payload.status)
        shipment.carrier_status_detail = payload.status_detail
        if payload.estimated_delivery:
            shipment.estimated_delivery = payload.estimated_delivery
        if payload.actual_delivery:
            shipment.actual_delivery = payload.actual_delivery

        if payload.status == "delayed":
            shipment.is_delayed = True
            shipment.delay_reason = payload.status_detail

        if payload.status == "delivered":
            order_result = await self.db.execute(select(Order).where(Order.id == shipment.order_id))
            order = order_result.scalar_one_or_none()
            if order is not None:
                order.status = OrderStatus.DELIVERED

        shipment.last_polled_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(shipment)
        return shipment

    async def get_shipments_by_order(self, order_id: str) -> list[ShipmentRead]:
        result = await self.db.execute(
            select(Shipment).where(Shipment.order_id == order_id).order_by(Shipment.created_at.desc())
        )
        shipments = list(result.scalars().all())
        return [ShipmentRead.model_validate(s) for s in shipments]
