from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, field_validator


class OrderCreate(BaseModel):
    external_order_id: str | None = None
    customer_email: EmailStr
    customer_phone: str | None = None
    shipping_address: str
    shipping_zip: str = ""
    shipping_city: str
    shipping_state: str
    shipping_country: str = "US"
    items_json: str = "[]"
    total_weight_kg: float = 0.0
    notes: str | None = None

    @field_validator("shipping_zip")
    @classmethod
    def validate_zip(cls, v: str) -> str:
        stripped = v.strip()
        if stripped and len(stripped) < 5:
            raise ValueError("shipping_zip must be at least 5 characters")
        return stripped

    @field_validator("total_weight_kg")
    @classmethod
    def validate_weight(cls, v: float) -> float:
        if v < 0:
            raise ValueError("total_weight_kg must be non-negative")
        return v


class OrderUpdate(BaseModel):
    customer_email: EmailStr | None = None
    customer_phone: str | None = None
    shipping_address: str | None = None
    shipping_zip: str | None = None
    shipping_city: str | None = None
    shipping_state: str | None = None
    shipping_country: str | None = None
    items_json: str | None = None
    total_weight_kg: float | None = None
    notes: str | None = None
    status: str | None = None


class OrderRead(BaseModel):
    id: str
    external_order_id: str | None = None
    customer_email: str
    customer_phone: str | None = None
    shipping_address: str
    shipping_zip: str
    shipping_city: str
    shipping_state: str
    shipping_country: str
    items_json: str
    total_weight_kg: float
    status: str
    fulfillment_center_id: str | None = None
    carrier_id: str | None = None
    tracking_number: str | None = None
    estimated_delivery: datetime | None = None
    shipping_cost: float | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrderListResponse(BaseModel):
    orders: list[OrderRead]
    total: int


class OrderRouteRequest(BaseModel):
    preferred_carrier: str | None = None
    max_cost: float | None = None
    max_days: int | None = None


class OrderRouteResponse(BaseModel):
    order_id: str
    fulfillment_center_id: str
    carrier_id: str
    carrier_name: str
    tracking_number: str
    estimated_delivery: datetime | None = None
    shipping_cost: float
    route_details: dict[str, Any] = {}
