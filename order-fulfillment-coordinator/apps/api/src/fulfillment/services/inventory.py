from typing import Literal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from fulfillment.models.inventory import OrderLine, Reservation, Stock, StockMovement
from fulfillment.models.order import Order, OrderStatus
from fulfillment.schemas.inventory import ReserveStock, StockChange


class InventoryConflict(Exception):
    pass


class InventoryNotFound(Exception):
    pass


class InventoryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _lock_stock(self, stock_id: str) -> Stock:
        stock = await self.db.scalar(select(Stock).where(Stock.id == stock_id).with_for_update())
        if stock is None:
            raise InventoryNotFound("Stock location not found")
        return stock

    async def _update_balance(self, stock_id: str, on_hand_delta: int, reserved_delta: int) -> None:
        on_hand = Stock.on_hand + on_hand_delta
        reserved = Stock.reserved + reserved_delta
        changed = await self.db.scalar(
            update(Stock)
            .where(Stock.id == stock_id, on_hand >= reserved, reserved >= 0, on_hand <= 1_000_000_000)
            .values(on_hand=on_hand, reserved=reserved)
            .returning(Stock.id)
        )
        if changed is None:
            raise InventoryConflict("Stock change would exceed available inventory or balance limits")

    async def _move(self, movement: StockMovement) -> None:
        await self._update_balance(movement.stock_id, movement.on_hand_delta, movement.reserved_delta)
        self.db.add(movement)
        await self.db.flush()

    async def active_center(self, order_id: str) -> str | None:
        result = await self.db.execute(
            select(Stock.center_id).join(Reservation, Reservation.stock_id == Stock.id)
            .where(Reservation.order_id == order_id, Reservation.status == "reserved")
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def change_stock(self, stock_id: str, payload: StockChange, actor_id: str) -> Stock:
        stock = await self._lock_stock(stock_id)
        movement_id = str(payload.operation_id)
        existing = await self.db.get(StockMovement, movement_id)
        if existing is not None:
            if (
                existing.stock_id != stock_id or existing.kind != payload.kind
                or existing.on_hand_delta != payload.quantity_delta or existing.reason != payload.reason
                or existing.actor_id != actor_id
            ):
                raise InventoryConflict("Operation ID already used with different details")
            return stock
        if payload.quantity_delta == 0 or (payload.kind == "receipt" and payload.quantity_delta < 0):
            raise InventoryConflict("A receipt must be positive and an adjustment must be nonzero")
        await self._move(StockMovement(
            id=movement_id, stock_id=stock_id, actor_id=actor_id, kind=payload.kind,
            on_hand_delta=payload.quantity_delta, reserved_delta=0, reason=payload.reason,
        ))
        await self.db.refresh(stock)
        return stock

    async def reserve(
        self, stock_id: str, payload: ReserveStock, actor_id: str, *, line: OrderLine | None = None,
    ) -> Reservation:
        order = await self.db.scalar(select(Order).where(Order.id == payload.order_id).with_for_update())
        if order is None:
            raise InventoryNotFound("Order not found")
        if line is None and await self.db.scalar(
            select(OrderLine.id).where(OrderLine.order_id == order.id).limit(1)
        ):
            raise InventoryConflict("Use automatic allocation for orders with typed lines")
        stock = await self._lock_stock(stock_id)
        if line is not None and (line.order_id, line.sku, line.quantity) != (
            order.id, stock.sku, payload.quantity,
        ):
            raise InventoryConflict("Reservation does not match its order line")
        existing = await self.db.scalar(select(Reservation).where(
            Reservation.stock_id == stock_id, Reservation.order_id == order.id,
        ))
        if existing is not None:
            if existing.quantity != payload.quantity or existing.status != "reserved":
                raise InventoryConflict("Order already has a reservation history at this stock location")
            return existing
        if order.status not in (OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.PROCESSING):
            raise InventoryConflict("Order status does not permit reservation")
        center_id = order.fulfillment_center_id or await self.active_center(order.id)
        if center_id and center_id != stock.center_id:
            raise InventoryConflict("Stock location differs from the assigned fulfillment center")
        reservation = Reservation(
            stock_id=stock_id, order_id=order.id, quantity=payload.quantity,
            order_line_id=line.id if line is not None else None,
        )
        await self._update_balance(stock_id, 0, payload.quantity)
        self.db.add(reservation)
        await self.db.flush()
        self.db.add(StockMovement(
            stock_id=stock_id, reservation_id=reservation.id, actor_id=actor_id, kind="reserve",
            on_hand_delta=0, reserved_delta=payload.quantity, reason="Order allocation",
        ))
        await self.db.flush()
        return reservation

    async def transition(
        self, reservation_id: str, target: Literal["released", "consumed"], reason: str, actor_id: str,
        *, order_dispatch: bool = False,
    ) -> Reservation:
        reservation = await self.db.get(Reservation, reservation_id)
        if reservation is None:
            raise InventoryNotFound("Reservation not found")
        order = await self.db.scalar(select(Order).where(Order.id == reservation.order_id).with_for_update())
        if order is None:
            raise InventoryNotFound("Order not found")
        stock = await self._lock_stock(reservation.stock_id)
        await self.db.refresh(reservation)
        if reservation.status == target:
            return reservation
        if reservation.order_line_id is not None and not (order_dispatch and target == "consumed"):
            raise InventoryConflict("Use order-level dispatch for typed reservations")
        if target == "consumed" and order.status not in (
            OrderStatus.PROCESSING, OrderStatus.SHIPPED, OrderStatus.DELIVERED,
        ):
            raise InventoryConflict("Order must be routed before consuming stock")
        changed = await self.db.scalar(
            update(Reservation)
            .where(Reservation.id == reservation_id, Reservation.status == "reserved")
            .values(status=target)
            .returning(Reservation.id)
        )
        if changed is None:
            raise InventoryConflict("Reservation has already been finalized")
        await self._move(StockMovement(
            stock_id=stock.id, reservation_id=reservation.id, actor_id=actor_id,
            kind="release" if target == "released" else "consume",
            on_hand_delta=0 if target == "released" else -reservation.quantity,
            reserved_delta=-reservation.quantity, reason=reason,
        ))
        await self.db.refresh(reservation)
        return reservation
