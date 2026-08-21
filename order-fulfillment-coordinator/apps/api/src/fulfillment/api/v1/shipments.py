from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from fulfillment.api.deps import get_current_user, get_db, require_operator_or_admin
from fulfillment.schemas.shipment import ShipmentRead, ShipmentRerouteRequest, ShipmentRerouteResponse
from fulfillment.services.shipment_service import ShipmentService

router = APIRouter()


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
    _user: dict[str, str] = Depends(require_operator_or_admin),
) -> ShipmentRerouteResponse:
    service = ShipmentService(db)
    return await service.reroute_shipment(shipment_id, payload)
