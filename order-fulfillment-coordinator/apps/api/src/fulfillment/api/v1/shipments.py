from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from fulfillment.api.deps import get_current_user, get_db, require_operator_or_admin
from fulfillment.schemas.shipment import ShipmentRead, ShipmentRerouteRequest, ShipmentRerouteResponse
from fulfillment.services.shipment_service import ShipmentService
from fulfillment.services.inventory import InventoryConflict
from fulfillment.models.user import User
from fulfillment.models.carrier_booking import CarrierBooking
from fulfillment.schemas.carrier_booking import BookingRequest, BookingRead
from fulfillment.services.carrier_booking import request_booking, cancel_booking, reconcile_booking
from fulfillment.services.carrier_adapters import CarrierUnavailable
from fulfillment.services.inventory import InventoryNotFound
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

router = APIRouter()


@router.post("/{shipment_id}/booking", response_model=BookingRead, status_code=202)
async def book_shipment(shipment_id: str, payload: BookingRequest,
                        db: AsyncSession = Depends(get_db), user: User = Depends(require_operator_or_admin)):
    try:
        return await request_booking(db, shipment_id, payload, user.id)
    except InventoryNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except (InventoryConflict, IntegrityError) as exc:
        raise HTTPException(409, "Booking request conflicts with existing fulfillment state" if isinstance(exc, IntegrityError) else str(exc)) from exc
    except CarrierUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


@router.get("/{shipment_id}/booking", response_model=BookingRead)
async def get_booking(shipment_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    booking = await db.scalar(select(CarrierBooking).where(CarrierBooking.shipment_id == shipment_id)
                              .order_by(CarrierBooking.active.desc(), CarrierBooking.created_at.desc(), CarrierBooking.id.desc()).limit(1))
    if booking is None:
        raise HTTPException(404, "No booking recorded")
    return booking


@router.post("/{shipment_id}/booking/cancel", response_model=BookingRead)
async def cancel_shipment_booking(shipment_id: str, db: AsyncSession = Depends(get_db),
                                  user: User = Depends(require_operator_or_admin)):
    try:
        booking = await cancel_booking(db, shipment_id, user.id)
        await db.flush()
        await db.refresh(booking)
        return booking
    except InventoryNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except InventoryConflict as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/{shipment_id}/booking/reconcile", response_model=BookingRead, status_code=202)
async def reconcile_shipment_booking(shipment_id: str, db: AsyncSession = Depends(get_db),
                                     user: User = Depends(require_operator_or_admin)):
    try:
        booking = await reconcile_booking(db, shipment_id, user.id)
        await db.flush()
        await db.refresh(booking)
        return booking
    except InventoryNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except InventoryConflict as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("", response_model=list[ShipmentRead])
async def list_shipments(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    _user: dict[str, str] = Depends(get_current_user),
) -> list[ShipmentRead]:
    service = ShipmentService(db)
    return await service.list_shipments(skip=skip, limit=limit, status_filter=status_filter)


@router.get("/{shipment_id}", response_model=ShipmentRead)
async def get_shipment(
    shipment_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict[str, str] = Depends(get_current_user),
) -> ShipmentRead:
    service = ShipmentService(db)
    shipment = await service.get_shipment(shipment_id)
    if shipment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found")
    return shipment


@router.post("/{shipment_id}/reroute", response_model=ShipmentRerouteResponse)
async def reroute_shipment(
    shipment_id: str,
    payload: ShipmentRerouteRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_operator_or_admin),
) -> ShipmentRerouteResponse:
    service = ShipmentService(db)
    try:
        return await service.reroute_shipment(shipment_id, payload, actor_id=_user.id)
    except InventoryConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
