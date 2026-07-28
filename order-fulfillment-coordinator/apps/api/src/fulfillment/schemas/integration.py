from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class IntegrationConnectRequest(BaseModel):
    provider: str = "odoo"
    label: str = ""
    base_url: str
    db: str = ""
    username: str = ""
    password: str = ""
    api_key: str = ""
    verify_ssl: bool = True


class IntegrationConnectionRead(BaseModel):
    id: str
    provider: str
    label: str
    base_url: str
    db_name: str | None = None
    username: str | None = None
    is_connected: bool
    last_sync_at: datetime | None = None
    sync_status: str
    error_message: str | None = None
    version: str | None = None
    total_orders_synced: int = 0
    total_products_synced: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class IntegrationConnectionStatus(BaseModel):
    connected: bool
    version: str | None = None
    uid: int | None = None
    db: str | None = None
    server: str | None = None
    error: str | None = None


class SyncResult(BaseModel):
    success: bool
    message: str
    orders_created: int = 0
    orders_updated: int = 0
    products_synced: int = 0
    partners_synced: int = 0


class OdooSearchRequest(BaseModel):
    model: str
    domain: list[Any] = []
    fields: list[str] | None = None
    limit: int = 50
    offset: int = 0
    order: str | None = None


class OdooSearchResult(BaseModel):
    records: list[dict[str, Any]]
    total: int
