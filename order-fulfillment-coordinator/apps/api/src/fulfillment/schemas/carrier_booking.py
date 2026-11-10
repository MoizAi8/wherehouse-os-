from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Phone = Annotated[str, StringConstraints(pattern=r"^\+[1-9][0-9]{6,14}$")]


class BookingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: UUID
    recipient_name: str = Field(min_length=1, max_length=100)
    recipient_phone: Phone
    sender_phone: Phone
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    payment_mode: Literal["prepaid", "cod"] = "prepaid"
    cod_amount: Decimal = Field(default=Decimal("0"), ge=0, le=10000000, decimal_places=2)
    sandbox_scenario: Literal["accepted", "retry_once", "rejected", "ambiguous", "unavailable"] = (
        "accepted"
    )

    @model_validator(mode="after")
    def validate_payment(self):
        if (self.payment_mode == "cod") != (self.cod_amount > 0):
            raise ValueError("COD requires a positive amount; prepaid requires zero COD")
        if not self.recipient_name.strip():
            raise ValueError("Recipient name cannot be blank")
        return self


class BookingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    shipment_id: str
    active: bool
    provider: str
    status: str
    sandbox: bool
    attempts: int
    provider_reference: str | None
    tracking_number: str | None
    error_code: str | None
    due_at: datetime | None
    created_at: datetime
    updated_at: datetime
