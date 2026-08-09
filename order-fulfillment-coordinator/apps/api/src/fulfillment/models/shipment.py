from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fulfillment.database import Base

if TYPE_CHECKING:
    from fulfillment.models.order import Order


class ShipmentStatus(str, enum.Enum):
    LABEL_CREATED = "label_created"
    PICKED_UP = "picked_up"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    EXCEPTION = "exception"
    DELAYED = "delayed"
    RETURNED = "returned"


class Shipment(Base):
    __tablename__ = "shipments"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    order_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    carrier_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tracking_number: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ShipmentStatus] = mapped_column(
        Enum(ShipmentStatus, name="shipment_status", values_callable=lambda x: [e.value for e in x]),
        default=ShipmentStatus.LABEL_CREATED,
        nullable=False,
    )
    estimated_delivery: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_delivery: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    origin_zip: Mapped[str] = mapped_column(String(20), nullable=False)
    destination_zip: Mapped[str] = mapped_column(String(20), nullable=False)
    weight_kg: Mapped[float] = mapped_column(Float, default=0.0)
    shipping_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    carrier_status_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_delayed: Mapped[bool] = mapped_column(default=False)
    delay_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    order: Mapped[Order] = relationship("Order", back_populates="shipments")

    def __repr__(self) -> str:
        return f"<Shipment {self.id} carrier={self.carrier_name} status={self.status}>"
