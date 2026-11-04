from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fulfillment.models.carrier_rate import CarrierRate
from fulfillment.models.agent_event import AgentEvent
from fulfillment.models.inventory import OrderLine
from fulfillment.models.order import Order, OrderStatus
from fulfillment.models.shipment import Shipment, ShipmentStatus
from fulfillment.schemas.shipment import ShipmentRead, ShipmentRerouteRequest, ShipmentRerouteResponse
from fulfillment.schemas.webhook import ShipmentEventWebhook
from fulfillment.services.inventory import InventoryConflict

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
        *, actor_id: str = "system",
    ) -> ShipmentRerouteResponse:
        result = await self.db.execute(select(Shipment).where(Shipment.id == shipment_id))
        shipment = result.scalar_one_or_none()
        if shipment is None:
            raise ValueError("Shipment not found")
        order = await self.db.scalar(select(Order).where(Order.id == shipment.order_id).with_for_update())
        await self.db.refresh(shipment)
        if shipment.status == ShipmentStatus.CANCELLED or (order and order.status == OrderStatus.CANCELLED):
            raise InventoryConflict("Cancelled shipments cannot be rerouted")
        if shipment.status in (ShipmentStatus.DELIVERED, ShipmentStatus.RETURNED):
            raise InventoryConflict("A terminal shipment cannot be rerouted")
        if shipment.last_polled_at is not None or shipment.status not in (
            ShipmentStatus.LABEL_CREATED, ShipmentStatus.DELAYED,
        ) or (order is not None and order.status in (OrderStatus.SHIPPED, OrderStatus.DELIVERED)):
            raise InventoryConflict("Carrier handoff requires reconciliation before rerouting")
        if order is not None and await self.db.scalar(
            select(OrderLine.id).where(OrderLine.order_id == order.id).limit(1)
        ):
            if (
                order.status != OrderStatus.PROCESSING or shipment.status != ShipmentStatus.LABEL_CREATED
                or shipment.last_polled_at is not None
            ):
                raise InventoryConflict("Carrier handoff requires reconciliation before rerouting")

        previous_carrier = shipment.carrier_name
        previous_tracking = shipment.tracking_number
        if previous_carrier == payload.new_carrier_name:
            raise InventoryConflict("Shipment already uses the requested carrier")

        rate_result = await self.db.execute(
            select(CarrierRate)
            .where(CarrierRate.is_active)
            .where(CarrierRate.carrier_name == payload.new_carrier_name)
            .where(CarrierRate.origin_zip == shipment.origin_zip)
            .where(CarrierRate.destination_zip == shipment.destination_zip)
            .where(CarrierRate.weight_kg_min <= shipment.weight_kg)
            .where(CarrierRate.weight_kg_max >= shipment.weight_kg)
            .order_by(
                CarrierRate.base_rate + CarrierRate.rate_per_kg * shipment.weight_kg,
                CarrierRate.estimated_days_max, CarrierRate.id,
            )
            .limit(1)
        )
        new_rate = rate_result.scalar_one_or_none()
        if new_rate is None:
            raise InventoryConflict("No configured rate matches the requested carrier and shipment")

        new_tracking = f"TRK-{uuid4().hex[:12].upper()}"
        additional_cost = (new_rate.base_rate + new_rate.rate_per_kg * shipment.weight_kg) - (shipment.shipping_cost or 0)

        shipment.carrier_name = payload.new_carrier_name
        shipment.tracking_number = new_tracking
        shipment.status = ShipmentStatus.LABEL_CREATED
        shipment.estimated_delivery = datetime.now(timezone.utc) + timedelta(days=new_rate.estimated_days_max)
        shipment.shipping_cost = new_rate.base_rate + new_rate.rate_per_kg * shipment.weight_kg
        shipment.is_delayed = False
        shipment.delay_reason = None
        shipment.last_polled_at = None
        shipment.carrier_event_at = None
        shipment.carrier_event_hash = None
        if order is not None:
            order.carrier_id = new_rate.id
            order.tracking_number = shipment.tracking_number
            order.shipping_cost = shipment.shipping_cost
            order.estimated_delivery = shipment.estimated_delivery

        self.db.add(AgentEvent(
            agent_name="ReroutingAgent", event_type="reroute_executed", entity_id=shipment.id,
            summary="Changed an internal shipment route before carrier handoff",
            created_at=datetime.now(timezone.utc),
            details_json=json.dumps({
                "actor_id": actor_id, "reason": payload.reason,
                "previous_carrier": previous_carrier, "previous_tracking": previous_tracking,
                "new_carrier": shipment.carrier_name, "new_tracking": shipment.tracking_number,
                "rate_id": new_rate.id, "shipping_cost": shipment.shipping_cost,
                "provider_booking_verified": False,
            }),
        ))

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

        order = await self.db.scalar(select(Order).where(Order.id == shipment.order_id).with_for_update())
        await self.db.refresh(shipment)
        if shipment.tracking_number != payload.tracking_number or shipment.carrier_name != payload.carrier:
            raise InventoryConflict("Shipment route changed before applying the event")
        if shipment.status == ShipmentStatus.CANCELLED or (order and order.status == OrderStatus.CANCELLED):
            raise InventoryConflict("Cancelled shipments cannot accept carrier events")
        event_at = payload.timestamp
        event_hash = None
        if event_at is not None:
            if event_at.tzinfo is None:
                event_at = event_at.replace(tzinfo=timezone.utc)
            if event_at > datetime.now(timezone.utc) + timedelta(minutes=5):
                raise InventoryConflict("Carrier event timestamp is too far in the future")
            event_hash = hashlib.sha256(payload.model_dump_json().encode()).hexdigest()
            previous_at = shipment.carrier_event_at
            if previous_at is not None:
                if previous_at.tzinfo is None:
                    previous_at = previous_at.replace(tzinfo=timezone.utc)
                if event_at == previous_at and event_hash == shipment.carrier_event_hash:
                    return shipment
                if event_at <= previous_at:
                    raise InventoryConflict("Carrier event is older than or conflicts with the last event")
        elif shipment.carrier_event_at is not None:
            raise InventoryConflict("Carrier event timestamp is required after a timestamped event")
        if order is not None:
            if payload.status == "delivered" or order.status == OrderStatus.DELIVERED:
                typed = await self.db.scalar(select(OrderLine.id).where(OrderLine.order_id == order.id).limit(1))
                if typed and order.status == OrderStatus.DELIVERED:
                    if payload.status == "delivered":
                        return shipment
                    raise InventoryConflict("Delivered typed shipments cannot return to an earlier state")
                if payload.status == "delivered":
                    if typed and order.status != OrderStatus.SHIPPED:
                        raise InventoryConflict("Record order dispatch before accepting delivery")
                    order.status = OrderStatus.DELIVERED

        shipment.status = ShipmentStatus(payload.status)
        shipment.carrier_status_detail = payload.status_detail
        if payload.estimated_delivery:
            shipment.estimated_delivery = payload.estimated_delivery
        if payload.actual_delivery:
            shipment.actual_delivery = payload.actual_delivery

        if payload.status == "delayed":
            shipment.is_delayed = True
            shipment.delay_reason = payload.status_detail
        elif payload.status != "exception":
            shipment.is_delayed = False
            shipment.delay_reason = None

        shipment.last_polled_at = datetime.now(timezone.utc)
        shipment.carrier_event_at = event_at
        shipment.carrier_event_hash = event_hash
        await self.db.flush()
        await self.db.refresh(shipment)
        return shipment

    async def get_shipments_by_order(self, order_id: str) -> list[ShipmentRead]:
        result = await self.db.execute(
            select(Shipment).where(Shipment.order_id == order_id).order_by(Shipment.created_at.desc())
        )
        shipments = list(result.scalars().all())
        return [ShipmentRead.model_validate(s) for s in shipments]
