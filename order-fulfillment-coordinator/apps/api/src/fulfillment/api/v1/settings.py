from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from fulfillment.schemas.settings import AppSettings

router = APIRouter()

_SETTINGS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)


def _file_path(user: str) -> Path:
    return _SETTINGS_DIR / f"settings_{user}.json"


@router.get("", response_model=AppSettings)
async def get_settings() -> AppSettings:
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
) -> AppSettings:
    fpath = _file_path("default")
    fpath.write_text(payload.model_dump_json(indent=2), "utf-8")
    return payload
