from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from fulfillment.api.deps import get_current_user, get_db, require_operator_or_admin
from fulfillment.models.fulfillment_center import FulfillmentCenter
from fulfillment.models.inventory import Product, Reservation, Stock, StockMovement
from fulfillment.models.user import User
from fulfillment.schemas.inventory import (
    MovementRead, ProductCreate, ReservationRead, ReservationTransition, ReserveStock,
    StockChange, StockCreate, StockRead,
)
from fulfillment.services.inventory import InventoryConflict, InventoryNotFound, InventoryService

router = APIRouter()
Db = Annotated[AsyncSession, Depends(get_db)]
Reader = Annotated[User, Depends(get_current_user)]
Operator = Annotated[User, Depends(require_operator_or_admin)]
Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0)]


@asynccontextmanager
async def inventory_write() -> AsyncIterator[None]:
    try:
        yield
    except InventoryConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except InventoryNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except IntegrityError as exc:
        raise HTTPException(409, "Inventory write conflicts with an existing record") from exc


@router.get("/products", response_model=list[ProductCreate])
async def list_products(db: Db, _user: Reader, limit: Limit = 100, offset: Offset = 0):
    return (await db.scalars(select(Product).order_by(Product.sku).offset(offset).limit(limit))).all()


@router.post("/products", response_model=ProductCreate, status_code=201)
async def create_product(payload: ProductCreate, db: Db, _user: Operator):
    async with inventory_write():
        db.add(Product(**payload.model_dump()))
        await db.flush()
    return payload


@router.get("/stock", response_model=list[StockRead])
async def list_stock(
    db: Db, _user: Reader, limit: Limit = 100, offset: Offset = 0, low_only: bool = False,
):
    query = select(Stock)
    if low_only:
        query = query.where(Stock.on_hand - Stock.reserved <= Stock.low_stock_threshold)
    return (await db.scalars(query.order_by(Stock.sku, Stock.center_id).offset(offset).limit(limit))).all()


@router.post("/stock", response_model=StockRead, status_code=201)
async def create_stock(payload: StockCreate, db: Db, _user: Operator):
    if await db.get(Product, payload.sku) is None or await db.get(FulfillmentCenter, payload.center_id) is None:
        raise HTTPException(404, "Product or fulfillment center not found")
    stock = Stock(**payload.model_dump())
    async with inventory_write():
        db.add(stock)
        await db.flush()
    return stock


@router.get("/stock/{stock_id}/movements", response_model=list[MovementRead])
async def list_movements(stock_id: str, db: Db, _user: Reader, limit: Limit = 100, offset: Offset = 0):
    return (await db.scalars(
        select(StockMovement).where(StockMovement.stock_id == stock_id)
        .order_by(StockMovement.created_at.desc(), StockMovement.id).offset(offset).limit(limit)
    )).all()


@router.post("/stock/{stock_id}/movements", response_model=StockRead)
async def change_stock(stock_id: str, payload: StockChange, db: Db, user: Operator):
    async with inventory_write():
        return await InventoryService(db).change_stock(stock_id, payload, user.id)


@router.get("/orders/{order_id}/reservations", response_model=list[ReservationRead])
async def list_reservations(order_id: str, db: Db, _user: Reader, limit: Limit = 100, offset: Offset = 0):
    return (await db.scalars(
        select(Reservation).where(Reservation.order_id == order_id)
        .order_by(Reservation.id).offset(offset).limit(limit)
    )).all()


@router.post("/stock/{stock_id}/reservations", response_model=ReservationRead)
async def reserve_stock(stock_id: str, payload: ReserveStock, db: Db, user: Operator):
    async with inventory_write():
        return await InventoryService(db).reserve(stock_id, payload, user.id)


@router.post("/reservations/{reservation_id}/release", response_model=ReservationRead)
async def release_stock(reservation_id: str, payload: ReservationTransition, db: Db, user: Operator):
    async with inventory_write():
        return await InventoryService(db).transition(reservation_id, "released", payload.reason, user.id)


@router.post("/reservations/{reservation_id}/consume", response_model=ReservationRead)
async def consume_stock(reservation_id: str, payload: ReservationTransition, db: Db, user: Operator):
    async with inventory_write():
        return await InventoryService(db).transition(reservation_id, "consumed", payload.reason, user.id)
