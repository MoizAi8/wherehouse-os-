from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from fulfillment.api.deps import get_current_user, get_db
from fulfillment.models.user import User
from fulfillment.schemas.order import (
    OrderCreate,
    OrderListResponse,
    OrderRead,
    OrderRouteRequest,
    OrderRouteResponse,
    OrderUpdate,
)
from fulfillment.services.order_service import OrderService

router = APIRouter()

DbDep = Annotated[AsyncSession, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_user)]


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
    _user: UserDep,
) -> OrderRead:
    service = OrderService(db)
    return await service.create_order(payload)


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


@router.patch("/{order_id}", response_model=OrderRead)
async def update_order(
    order_id: str,
    payload: OrderUpdate,
    db: DbDep,
    _user: UserDep,
) -> OrderRead:
    service = OrderService(db)
    order = await service.update_order(order_id, payload)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_order(
    order_id: str,
    db: DbDep,
    _user: UserDep,
) -> None:
    service = OrderService(db)
    deleted = await service.delete_order(order_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")


@router.post("/{order_id}/route", response_model=OrderRouteResponse)
async def route_order(
    order_id: str,
    db: DbDep,
    _user: UserDep,
    payload: OrderRouteRequest | None = None,
) -> OrderRouteResponse:
    service = OrderService(db)
    order = await service.get_order(order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    try:
        return await service.route_order(order_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))