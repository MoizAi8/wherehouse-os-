from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from fulfillment.models.carrier_rate import CarrierRate
from fulfillment.models.fulfillment_center import FulfillmentCenter
from fulfillment.models.order import Order, OrderStatus
from fulfillment.models.shipment import Shipment, ShipmentStatus
from fulfillment.schemas.carrier import CarrierRateRequest, CarrierRateResponse
from fulfillment.schemas.order import (
    OrderCreate,
    OrderRead,
    OrderRouteRequest,
    OrderRouteResponse,
    OrderUpdate,
)
from fulfillment.schemas.webhook import OrderPlacedWebhook

logger = logging.getLogger(__name__)


def _coerce_order_status(raw: str) -> OrderStatus:
    """Convert a raw status string to an OrderStatus member.

    Prevents enum-vs-string comparison that silently works on SQLite but
    fails on PostgreSQL (critical rule #8).
    """
    try:
        return OrderStatus(raw)
    except ValueError:
        raise ValueError(
            f"Invalid order status '{raw}'. Valid: {[e.value for e in OrderStatus]}"
        )


class OrderService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_orders(
        self,
        skip: int = 0,
        limit: int = 100,
        status_filter: str | None = None,
    ) -> list[OrderRead]:
        query = select(Order).offset(skip).limit(limit).order_by(Order.created_at.desc())
        if status_filter:
            status_enum = _coerce_order_status(status_filter)
            query = query.where(Order.status == status_enum)
        result = await self.db.execute(query)
        orders = list(result.scalars().all())
        return [OrderRead.model_validate(o) for o in orders]

    async def count_orders(self, status_filter: str | None = None) -> int:
        query = select(func.count()).select_from(Order)
        if status_filter:
            status_enum = _coerce_order_status(status_filter)
            query = query.where(Order.status == status_enum)
        result = await self.db.execute(query)
        return result.scalar_one()

    async def create_order(self, payload: OrderCreate) -> OrderRead:
        order = Order(
            id=str(uuid4()),
            external_order_id=payload.external_order_id,
            customer_email=payload.customer_email,
            customer_phone=payload.customer_phone,
            shipping_address=payload.shipping_address,
            shipping_zip=payload.shipping_zip,
            shipping_city=payload.shipping_city,
            shipping_state=payload.shipping_state,
            shipping_country=payload.shipping_country,
            items_json=payload.items_json,
            total_weight_kg=payload.total_weight_kg,
            notes=payload.notes,
            status=OrderStatus.PENDING,
        )
        self.db.add(order)
        await self.db.flush()
        await self.db.refresh(order)
        return OrderRead.model_validate(order)

    async def get_order(self, order_id: str) -> OrderRead | None:
        result = await self.db.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if order is None:
            return None
        return OrderRead.model_validate(order)

    async def update_order(self, order_id: str, payload: OrderUpdate) -> OrderRead | None:
        result = await self.db.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if order is None:
            return None
        update_data = payload.model_dump(exclude_unset=True)
        if not update_data:
            return OrderRead.model_validate(order)
        for key, value in update_data.items():
            setattr(order, key, value)
        await self.db.flush()
        await self.db.refresh(order)
        return OrderRead.model_validate(order)

    async def delete_order(self, order_id: str) -> bool:
        result = await self.db.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if order is None:
            return False
        await self.db.delete(order)
        await self.db.flush()
        return True

    async def route_order(
        self,
        order_id: str,
        payload: OrderRouteRequest | None = None,
    ) -> OrderRouteResponse:
        result = await self.db.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if order is None:
            raise ValueError("Order not found")

        fc_result = await self.db.execute(
            select(FulfillmentCenter)
            .where(FulfillmentCenter.is_active)
            .where(FulfillmentCenter.current_daily_orders < FulfillmentCenter.max_daily_orders)
            .order_by(FulfillmentCenter.capacity_pct.asc())
            .limit(1)
        )
        fc = fc_result.scalar_one_or_none()
        if fc is None:
            raise ValueError("No available fulfillment center")

        rate_result = await self.db.execute(
            select(CarrierRate)
            .where(CarrierRate.is_active)
            .where(CarrierRate.origin_zip == fc.zip_code)
            .where(CarrierRate.destination_zip == order.shipping_zip)
            .where(CarrierRate.weight_kg_min <= order.total_weight_kg)
            .where(CarrierRate.weight_kg_max >= order.total_weight_kg)
            .order_by(CarrierRate.base_rate.asc())
            .limit(1)
        )
        carrier_rate = rate_result.scalar_one_or_none()
        if carrier_rate is None:
            raise ValueError("No suitable carrier rate found")

        shipping_cost = carrier_rate.base_rate + (carrier_rate.rate_per_kg * order.total_weight_kg)
        tracking_number = f"TRK-{uuid4().hex[:12].upper()}"
        estimated_delivery = datetime.now(timezone.utc)

        order.fulfillment_center_id = fc.id
        order.carrier_id = carrier_rate.id
        order.tracking_number = tracking_number
        order.shipping_cost = shipping_cost
        order.status = OrderStatus.PROCESSING
        order.estimated_delivery = estimated_delivery

        shipment = Shipment(
            id=str(uuid4()),
            order_id=order.id,
            carrier_name=carrier_rate.carrier_name,
            tracking_number=tracking_number,
            status=ShipmentStatus.LABEL_CREATED,
            estimated_delivery=estimated_delivery,
            origin_zip=fc.zip_code,
            destination_zip=order.shipping_zip,
            weight_kg=order.total_weight_kg,
            shipping_cost=shipping_cost,
        )
        self.db.add(shipment)

        fc.current_daily_orders += 1

        await self.db.flush()
        await self.db.refresh(order)

        return OrderRouteResponse(
            order_id=order.id,
            fulfillment_center_id=fc.id,
            carrier_id=carrier_rate.id,
            carrier_name=carrier_rate.carrier_name,
            tracking_number=tracking_number,
            estimated_delivery=estimated_delivery,
            shipping_cost=shipping_cost,
            route_details={
                "fulfillment_center": fc.name,
                "carrier": carrier_rate.carrier_name,
                "service": carrier_rate.service_name,
                "estimated_days": f"{carrier_rate.estimated_days_min}-{carrier_rate.estimated_days_max}",
            },
        )

    async def get_all_carrier_rates(self) -> list[CarrierRateResponse]:
        result = await self.db.execute(
            select(CarrierRate).where(CarrierRate.is_active).order_by(CarrierRate.carrier_name)
        )
        rates = list(result.scalars().all())
        return [CarrierRateResponse.model_validate(r) for r in rates]

    async def shop_rates(self, payload: CarrierRateRequest) -> list[CarrierRateResponse]:
        result = await self.db.execute(
            select(CarrierRate)
            .where(CarrierRate.is_active)
            .where(CarrierRate.origin_zip == payload.origin_zip)
            .where(CarrierRate.destination_zip == payload.destination_zip)
            .where(CarrierRate.weight_kg_min <= payload.weight_kg)
            .where(CarrierRate.weight_kg_max >= payload.weight_kg)
            .order_by(CarrierRate.base_rate.asc())
        )
        rates = list(result.scalars().all())
        return [CarrierRateResponse.model_validate(r) for r in rates]

    async def create_order_from_webhook(self, payload: OrderPlacedWebhook) -> Order:
        existing = await self.db.execute(
            select(Order).where(Order.external_order_id == payload.external_order_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise ValueError(f"Order with external_order_id {payload.external_order_id} already exists")
        order = Order(
            id=str(uuid4()),
            external_order_id=payload.external_order_id,
            customer_email=payload.customer_email,
            customer_phone=payload.customer_phone,
            shipping_address=payload.shipping_address,
            shipping_zip=payload.shipping_zip,
            shipping_city=payload.shipping_city,
            shipping_state=payload.shipping_state,
            shipping_country=payload.shipping_country,
            items_json=payload.items_json,
            total_weight_kg=payload.total_weight_kg,
            notes=payload.notes,
            status=OrderStatus.PENDING,
        )
        self.db.add(order)
        await self.db.flush()
        await self.db.refresh(order)
        return order
