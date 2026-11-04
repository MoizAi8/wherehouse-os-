from __future__ import annotations

from datetime import timezone

import json
import logging
from uuid import uuid4

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from fulfillment.agents.routing import RoutingAgent, RoutingError
from fulfillment.models.agent_event import AgentEvent
from fulfillment.models.carrier_rate import CarrierRate
from fulfillment.models.fulfillment_center import FulfillmentCenter
from fulfillment.models.inventory import OrderLine, Product, Reservation, Stock
from fulfillment.models.order import Order, OrderStatus
from fulfillment.models.shipment import Shipment, ShipmentStatus
from fulfillment.schemas.carrier import CarrierRateRequest, CarrierRateResponse
from fulfillment.schemas.order import (
    OrderCreate,
    OrderLineRead,
    OrderRead,
    OrderRouteRequest,
    OrderRouteResponse,
    OrderUpdate,
)
from fulfillment.schemas.webhook import OrderPlacedWebhook
from fulfillment.schemas.inventory import ReserveStock
from fulfillment.services.inventory import InventoryConflict, InventoryService

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

    async def create_order(self, payload: OrderCreate, *, actor_id: str = "system") -> OrderRead:
        skus = {line.sku for line in payload.lines}
        if skus:
            found = set(await self.db.scalars(select(Product.sku).where(Product.sku.in_(skus))))
            if missing := skus - found:
                raise InventoryConflict(f"Unknown inventory SKU: {', '.join(sorted(missing))}")
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
            requires_stock=payload.defer_routing or bool(payload.lines),
            total_weight_kg=payload.total_weight_kg,
            notes=payload.notes,
            status=OrderStatus.PENDING,
        )
        self.db.add(order)
        await self.db.flush()
        self.db.add_all(
            OrderLine(order_id=order.id, sku=line.sku, quantity=line.quantity) for line in payload.lines
        )
        await self.db.flush()
        await self.db.refresh(order)
        if not payload.defer_routing:
            await self._try_autonomous_routing(order.id, actor_id=actor_id)
        return OrderRead.model_validate(order)

    async def list_lines(self, order_id: str) -> list[OrderLineRead]:
        rows = await self.db.execute(
            select(OrderLine, Stock.center_id, Reservation.status)
            .outerjoin(Reservation, Reservation.order_line_id == OrderLine.id)
            .outerjoin(Stock, Stock.id == Reservation.stock_id)
            .where(OrderLine.order_id == order_id).order_by(OrderLine.sku)
        )
        return [
            OrderLineRead(id=line.id, sku=line.sku, quantity=line.quantity,
                          center_id=center, reservation_status=status)
            for line, center, status in rows
        ]

    async def get_order(self, order_id: str) -> OrderRead | None:
        result = await self.db.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if order is None:
            return None
        return OrderRead.model_validate(order)

    async def update_order(self, order_id: str, payload: OrderUpdate) -> OrderRead | None:
        result = await self.db.execute(select(Order).where(Order.id == order_id).with_for_update())
        order = result.scalar_one_or_none()
        if order is None:
            return None
        update_data = payload.model_dump(exclude_unset=True)
        if not update_data:
            return OrderRead.model_validate(order)
        if await self.db.scalar(select(OrderLine.id).where(OrderLine.order_id == order_id).limit(1)):
            if "items_json" in update_data:
                raise InventoryConflict("Typed order lines are immutable")
            route_fields = {
                "shipping_address", "shipping_zip", "shipping_city", "shipping_state",
                "shipping_country", "total_weight_kg",
            }
            if order.status != OrderStatus.PENDING and route_fields.intersection(update_data):
                raise InventoryConflict("Routed order shipping details require reconciliation")
            if "status" in update_data and payload.status != order.status and not (
                order.status == OrderStatus.PENDING and payload.status == OrderStatus.CANCELLED
            ):
                raise InventoryConflict("Use a fulfillment operation to change this order status")
        if payload.status == OrderStatus.CANCELLED and await self.db.scalar(
            select(Reservation.id).where(
                Reservation.order_id == order.id, Reservation.status != "released",
            ).limit(1)
        ):
            raise InventoryConflict("Release active reservations before cancelling. Consumed stock requires reconciliation.")
        for key, value in update_data.items():
            setattr(order, key, value)
        await self.db.flush()
        await self.db.refresh(order)
        return OrderRead.model_validate(order)

    async def delete_order(self, order_id: str) -> bool:
        result = await self.db.execute(select(Order).where(Order.id == order_id).with_for_update())
        order = result.scalar_one_or_none()
        if order is None:
            return False
        if await self.db.scalar(select(OrderLine.id).where(OrderLine.order_id == order_id).limit(1)):
            raise InventoryConflict("Cancel typed orders to retain their line history")
        if await self.db.scalar(select(Reservation.id).where(Reservation.order_id == order_id).limit(1)):
            raise InventoryConflict("Orders with inventory history cannot be deleted")
        await self.db.delete(order)
        await self.db.flush()
        return True

    async def route_order(
        self,
        order_id: str,
        payload: OrderRouteRequest | None = None,
        *,
        actor_id: str = "system",
    ) -> OrderRouteResponse:
        result = await self.db.execute(select(Order).where(Order.id == order_id).with_for_update())
        order = result.scalar_one_or_none()
        if order is None:
            raise ValueError("Order not found")
        if order.tracking_number or await self.db.scalar(
            select(Shipment.id).where(Shipment.order_id == order_id).limit(1)
        ):
            raise ValueError("Order is already routed")
        if order.status != OrderStatus.PENDING:
            raise ValueError("Only pending orders can be routed")
        lines = list(await self.db.scalars(select(OrderLine).where(OrderLine.order_id == order_id)))
        if lines:
            decision = await self._allocate_and_route(order, lines, payload, actor_id)
        else:
            center_id = await InventoryService(self.db).active_center(order.id)
            if order.requires_stock and center_id is None:
                raise ValueError("Reserve inventory before routing this order")
            try:
                decision = await RoutingAgent(self.db).route_order(order, payload, center_id=center_id)
            except RoutingError as exc:
                raise ValueError(str(exc)) from exc

        await self.db.flush()
        await self.db.refresh(order)
        return OrderRouteResponse(
            order_id=order.id,
            fulfillment_center_id=decision["fulfillment_center"]["id"],
            carrier_id=decision["carrier"]["id"],
            carrier_name=decision["carrier"]["name"],
            tracking_number=decision["tracking_number"],
            estimated_delivery=order.estimated_delivery,
            shipping_cost=decision["shipping_cost"],
            route_details={
                "fulfillment_center": decision["fulfillment_center"]["name"],
                "carrier": decision["carrier"]["name"],
                "service": decision["carrier"]["service"],
                "estimated_days": decision["estimated_days"],
            },
        )

    async def _allocate_and_route(
        self, order: Order, lines: list[OrderLine], payload: OrderRouteRequest | None, actor_id: str,
    ) -> dict:
        order_id = order.id
        candidates = await self.db.execute(
            select(Stock.center_id, Stock.id, OrderLine)
            .join(OrderLine, OrderLine.sku == Stock.sku)
            .join(FulfillmentCenter, FulfillmentCenter.id == Stock.center_id)
            .where(OrderLine.order_id == order_id, FulfillmentCenter.is_active,
                   Stock.on_hand - Stock.reserved >= OrderLine.quantity)
            .order_by(FulfillmentCenter.capacity_pct, Stock.center_id, Stock.id)
        )
        by_center: dict[str, list[tuple[str, OrderLine]]] = {}
        for center_id, stock_id, line in candidates:
            by_center.setdefault(center_id, []).append((stock_id, line))

        # The SQLite legacy driver does not begin a transaction for a SELECT.
        # Establish the outer write transaction before opening any savepoint.
        if self.db.get_bind().dialect.name == "sqlite":
            await self.db.execute(update(Order).where(Order.id == order_id).values(updated_at=Order.updated_at))

        inventory = InventoryService(self.db)
        for center_id, allocation in by_center.items():
            if len(allocation) != len(lines):
                continue
            try:
                async with self.db.begin_nested():
                    decision = await RoutingAgent(self.db).route_order(order, payload, center_id=center_id)
                    for stock_id, line in allocation:
                        await inventory.reserve(
                            stock_id, ReserveStock(order_id=order_id, quantity=line.quantity), actor_id, line=line,
                        )
                return decision
            except (RoutingError, InventoryConflict):
                await self.db.refresh(order)
        raise ValueError("No single fulfillment center has both sufficient inventory and a suitable route")

    async def _lock_order_for_transition(self, order_id: str) -> Order | None:
        if self.db.get_bind().dialect.name == "sqlite":
            await self.db.execute(update(Order).where(Order.id == order_id).values(updated_at=Order.updated_at))
        result = await self.db.execute(select(Order).where(Order.id == order_id).with_for_update())
        return result.scalar_one_or_none()

    async def dispatch_order(self, order_id: str, reason: str, actor_id: str) -> OrderRead | None:
        order = await self._lock_order_for_transition(order_id)
        if order is None:
            return None
        records = (await self.db.execute(
            select(OrderLine, Reservation, Stock)
            .outerjoin(Reservation, Reservation.order_line_id == OrderLine.id)
            .outerjoin(Stock, Stock.id == Reservation.stock_id)
            .where(OrderLine.order_id == order_id)
            .order_by(Stock.id)
        )).all()
        if not records:
            raise InventoryConflict("Order-level dispatch requires typed order lines")
        if order.status in (OrderStatus.SHIPPED, OrderStatus.DELIVERED) and all(
            reservation is not None and reservation.status == "consumed" for _, reservation, _ in records
        ):
            return OrderRead.model_validate(order)
        if order.status != OrderStatus.PROCESSING or not order.fulfillment_center_id:
            raise InventoryConflict("Only a routed order can be dispatched")
        if not all(
            reservation is not None and stock is not None
            and reservation.order_id == order_id and reservation.quantity == line.quantity
            and stock.sku == line.sku and stock.center_id == order.fulfillment_center_id
            and reservation.status == "reserved"
            for line, reservation, stock in records
        ):
            raise InventoryConflict("The order does not have a complete allocation")
        inventory = InventoryService(self.db)
        for _, reservation, _ in records:
            await inventory.transition(reservation.id, "consumed", reason, actor_id, whole_order=True)
        order.status = OrderStatus.SHIPPED
        self.db.add(AgentEvent(
            agent_name="WarehouseOperator", event_type="order_dispatch_recorded", entity_id=order_id,
            summary="Operator recorded dispatch of all allocated order lines",
            details_json=json.dumps({"actor_id": actor_id, "line_count": len(records), "reason": reason}),
        ))
        await self.db.flush()
        await self.db.refresh(order)
        return OrderRead.model_validate(order)

    async def cancel_order(self, order_id: str, reason: str, actor_id: str) -> OrderRead | None:
        order = await self._lock_order_for_transition(order_id)
        if order is None:
            return None
        if not await self.db.scalar(select(OrderLine.id).where(OrderLine.order_id == order_id).limit(1)):
            raise InventoryConflict("Use order-level cancellation only for typed orders")
        if order.status == OrderStatus.CANCELLED:
            return OrderRead.model_validate(order)
        if order.status not in (OrderStatus.PENDING, OrderStatus.PROCESSING):
            raise InventoryConflict("An order cannot be cancelled after dispatch")
        shipments = list(await self.db.scalars(
            select(Shipment).where(Shipment.order_id == order_id).with_for_update()
        ))
        if any(
            shipment.status != ShipmentStatus.LABEL_CREATED or shipment.last_polled_at is not None
            for shipment in shipments
        ):
            raise InventoryConflict("Reconcile carrier activity before cancelling this order")
        reservations = list(await self.db.scalars(
            select(Reservation).where(Reservation.order_id == order_id).order_by(Reservation.stock_id)
        ))
        if any(reservation.status == "consumed" for reservation in reservations):
            raise InventoryConflict("Consumed inventory requires reconciliation before cancellation")
        inventory = InventoryService(self.db)
        for reservation in reservations:
            if reservation.status == "reserved":
                await inventory.transition(reservation.id, "released", reason, actor_id, whole_order=True)
        if order.fulfillment_center_id and shipments:
            routed_at = shipments[0].created_at
            routed_day = (routed_at.replace(tzinfo=timezone.utc) if routed_at.tzinfo is None else routed_at).astimezone(timezone.utc).date()
            await self.db.execute(update(FulfillmentCenter).where(
                FulfillmentCenter.id == order.fulfillment_center_id,
                FulfillmentCenter.current_daily_orders > 0,
                FulfillmentCenter.capacity_day == routed_day,
            ).values(current_daily_orders=FulfillmentCenter.current_daily_orders - 1))
        for shipment in shipments:
            shipment.status = ShipmentStatus.CANCELLED
        order.status = OrderStatus.CANCELLED
        self.db.add(AgentEvent(
            agent_name="WarehouseOperator", event_type="order_cancelled", entity_id=order_id,
            summary="Operator cancelled the order before dispatch",
            details_json=json.dumps({"actor_id": actor_id, "reason": reason}),
        ))
        await self.db.flush()
        await self.db.refresh(order)
        return OrderRead.model_validate(order)

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

    async def _try_autonomous_routing(self, order_id: str, *, actor_id: str = "system") -> None:
        """Best-effort autonomous routing for a freshly created order.

        The order pipeline (order → FC → carrier → shipment) should progress
        without a manual kick. If no eligible fulfillment center or carrier
        rate exists yet the order is left PENDING so order creation can succeed.
        """
        try:
            await self.route_order(order_id, actor_id=actor_id)
            logger.info("Autonomous routing completed for order %s", order_id)
        except ValueError as exc:
            logger.info("Autonomous routing deferred for order %s: %s", order_id, exc)

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
        await self._try_autonomous_routing(order.id)
        return order
