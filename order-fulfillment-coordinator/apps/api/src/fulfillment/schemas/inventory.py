from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, computed_field

Sku = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Quantity = Annotated[int, Field(strict=True, gt=0, le=1_000_000_000)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=250)]


class ProductCreate(BaseModel):
    sku: Sku
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class StockCreate(BaseModel):
    sku: Sku
    center_id: str = Field(min_length=1, max_length=36)
    low_stock_threshold: int = Field(default=0, ge=0, le=1_000_000_000)


class StockRead(StockCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    on_hand: int
    reserved: int

    @computed_field  # type: ignore[prop-decorator]
    @property
    def available(self) -> int:
        return self.on_hand - self.reserved

    @computed_field  # type: ignore[prop-decorator]
    @property
    def low_stock(self) -> bool:
        return self.available <= self.low_stock_threshold


class StockChange(BaseModel):
    operation_id: UUID
    kind: Literal["receipt", "adjustment"]
    quantity_delta: int = Field(strict=True, ge=-1_000_000_000, le=1_000_000_000)
    reason: Reason


class ReserveStock(BaseModel):
    order_id: str = Field(min_length=1, max_length=36)
    quantity: Quantity


class ReservationRead(ReserveStock):
    model_config = ConfigDict(from_attributes=True)

    id: str
    stock_id: str
    order_line_id: str | None
    status: Literal["reserved", "released", "consumed"]


class ReservationTransition(BaseModel):
    reason: Reason


class MovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    stock_id: str
    reservation_id: str | None
    actor_id: str
    kind: str
    on_hand_delta: int
    reserved_delta: int
    reason: str
    created_at: datetime
