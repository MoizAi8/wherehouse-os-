from __future__ import annotations

import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fulfillment.api.deps import get_db, get_current_user
from fulfillment.models.app_settings import AppSettingsStore
from fulfillment.models.user import User
from fulfillment.models.user import UserRole
from fulfillment.schemas.settings import AppSettings

logger = logging.getLogger("fulfillment.settings")

router = APIRouter()

_SETTINGS_ID = "default"

UserDep = Annotated[User, Depends(get_current_user)]
DbDep = Annotated[AsyncSession, Depends(get_db)]


@router.get("", response_model=AppSettings)
async def get_settings(_user: UserDep, db: DbDep) -> AppSettings:
    row = await db.get(AppSettingsStore, _SETTINGS_ID)
    if row is None:
        return AppSettings()
    try:
        return AppSettings(**json.loads(row.payload_json))
    except Exception:
        return AppSettings()


@router.put("", response_model=AppSettings)
async def update_settings(
    payload: AppSettings,
    _user: UserDep,
    db: DbDep,
) -> AppSettings:
    if _user.role not in (UserRole.ADMIN, UserRole.OPERATOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or operator role required",
        )
    row = await db.get(AppSettingsStore, _SETTINGS_ID)
    if row is None:
        row = AppSettingsStore(id=_SETTINGS_ID, payload_json="{}")
        db.add(row)
    row.payload_json = payload.model_dump_json(indent=2)
    await db.flush()
    logger.info("Settings updated by %s", _user.email)
    return payload


async def load_settings(db: AsyncSession) -> AppSettings:
    row = (await db.execute(select(AppSettingsStore).where(AppSettingsStore.id == _SETTINGS_ID))).scalar_one_or_none()
    if row is None:
        return AppSettings()
    try:
        return AppSettings(**json.loads(row.payload_json))
    except Exception:
        return AppSettings()