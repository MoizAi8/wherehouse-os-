from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from fulfillment.api.deps import get_current_user
from fulfillment.models.user import User
from fulfillment.models.user import UserRole
from fulfillment.schemas.settings import AppSettings

logger = logging.getLogger("fulfillment.settings")

router = APIRouter()

_SETTINGS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)


def _file_path(user: str) -> Path:
    if not user or "/" in user or "\\" in user or ".." in user:
        raise HTTPException(status_code=400, detail="Invalid user identifier")
    return _SETTINGS_DIR / f"settings_{user}.json"


UserDep = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=AppSettings)
async def get_settings(_user: UserDep) -> AppSettings:
    fpath = _file_path("default")
    if not fpath.exists():
        return AppSettings()
    try:
        data = json.loads(fpath.read_text("utf-8"))
        return AppSettings(**data)
    except Exception:
        return AppSettings()


@router.put("", response_model=AppSettings)
async def update_settings(
    payload: AppSettings,
    _user: UserDep,
) -> AppSettings:
    if _user.role not in (UserRole.ADMIN, UserRole.OPERATOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or operator role required",
        )
    fpath = _file_path("default")
    fpath.write_text(payload.model_dump_json(indent=2), "utf-8")
    logger.info("Settings updated by %s", _user.email)
    return payload