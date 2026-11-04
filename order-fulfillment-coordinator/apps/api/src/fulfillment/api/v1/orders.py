from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from fulfillment.api.deps import get_current_user, get_db, require_operator_or_admin
from fulfillment.models.user import User
from fulfillment.schemas.inventory import ReservationTransition
from fulfillment.schemas.order import (
    OrderCreate,
    OrderLineRead,
    OrderListResponse,
    OrderRead,
    OrderRouteRequest,
    OrderRouteResponse,
    OrderUpdate,
)
from fulfillment.services.order_service import OrderService
from fulfillment.services.inventory import InventoryConflict

router = APIRouter()

DbDep = Annotated[AsyncSession, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_user)]
MutateDep = Annotated[User, Depends(require_operator_or_admin)]


@router.get("", response_model=OrderListResponse)
async def list_orders(
    db: DbDep,
    _user: UserDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status_filter: str | None = Query(None, alias="status"),
) -> OrderListResponse:
    service = OrderService(db)
    orders = await service.list_orders(skip=skip, limit=limit, status_filter=status_filter)
    total = await service.count_orders(status_filter=status_filter)
    return OrderListResponse(orders=orders, total=total)


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreate,
    db: DbDep,
    user: MutateDep,
) -> OrderRead:
    service = OrderService(db)
    try:
        return await service.create_order(payload, actor_id=user.id)
    except InventoryConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        original = exc.orig
        postgres = getattr(original, "__cause__", None)
        if (
            getattr(postgres, "constraint_name", None) == "orders_external_order_id_key"
            or str(original) == "UNIQUE constraint failed: orders.external_order_id"
        ):
            raise HTTPException(409, "Order reference already exists") from exc
        raise


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(
    order_id: str,
    db: DbDep,
    _user: UserDep,
) -> OrderRead:
    service = OrderService(db)
    order = await service.get_order(order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


@router.get("/{order_id}/lines", response_model=list[OrderLineRead])
async def list_order_lines(order_id: str, db: DbDep, _user: UserDep) -> list[OrderLineRead]:
    service = OrderService(db)
    if await service.get_order(order_id) is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return await service.list_lines(order_id)


@router.patch("/{order_id}", response_model=OrderRead)
async def update_order(
    order_id: str,
    payload: OrderUpdate,
    db: DbDep,
    _user: MutateDep,
) -> OrderRead:
    service = OrderService(db)
    try:
        order = await service.update_order(order_id, payload)
    except InventoryConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_order(
    order_id: str,
    db: DbDep,
    _user: MutateDep,
) -> None:
    service = OrderService(db)
    try:
        deleted = await service.delete_order(order_id)
    except InventoryConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")


@router.post("/{order_id}/route", response_model=OrderRouteResponse)
async def route_order(
    order_id: str,
    db: DbDep,
    user: MutateDep,
    payload: OrderRouteRequest | None = None,
) -> OrderRouteResponse:
    service = OrderService(db)
    order = await service.get_order(order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    try:
        return await service.route_order(order_id, payload, actor_id=user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{order_id}/dispatch", response_model=OrderRead)
async def dispatch_order(order_id: str, payload: ReservationTransition, db: DbDep, user: MutateDep) -> OrderRead:
    try:
        order = await OrderService(db).dispatch_order(order_id, payload.reason, user.id)
    except InventoryConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
