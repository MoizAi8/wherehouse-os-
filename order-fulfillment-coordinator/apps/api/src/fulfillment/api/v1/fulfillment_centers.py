from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fulfillment.api.deps import get_current_user, get_db
from fulfillment.models.fulfillment_center import FulfillmentCenter
from fulfillment.schemas.carrier import FulfillmentCenterRead
from fulfillment.tools.fulfillment import daily_count

router = APIRouter()


@router.get("", response_model=list[FulfillmentCenterRead])
async def list_fulfillment_centers(
    db: AsyncSession = Depends(get_db),
    _user: dict[str, str] = Depends(get_current_user),
) -> list[FulfillmentCenterRead]:
    result = await db.execute(select(FulfillmentCenter).order_by(FulfillmentCenter.name))
    centers = result.scalars().all()
    return [FulfillmentCenterRead.model_validate(c).model_copy(update={"current_daily_orders": daily_count(c)}) for c in centers]
