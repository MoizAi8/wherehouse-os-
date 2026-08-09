from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fulfillment.database import Base

if TYPE_CHECKING:
    from fulfillment.models.fulfillment_center import FulfillmentCenter
    from fulfillment.models.shipment import Shipment


class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    external_order_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    customer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    shipping_address: Mapped[str] = mapped_column(Text, nullable=False)
    shipping_zip: Mapped[str] = mapped_column(String(20), nullable=False)
    shipping_city: Mapped[str] = mapped_column(String(100), nullable=False)
    shipping_state: Mapped[str] = mapped_column(String(100), nullable=False)
    shipping_country: Mapped[str] = mapped_column(String(100), default="US")
    items_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    total_weight_kg: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status", values_callable=lambda x: [e.value for e in x]),
        default=OrderStatus.PENDING,
        nullable=False,
    )
    fulfillment_center_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("fulfillment_centers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    carrier_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("carrier_rates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tracking_number: Mapped[str | None] = mapped_column(String(255), nullable=True)
    estimated_delivery: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    shipping_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    fulfillment_center: Mapped[FulfillmentCenter | None] = relationship(
        "FulfillmentCenter",
        back_populates="orders",
    )
    shipments: Mapped[list[Shipment]] = relationship(
        "Shipment",
        back_populates="order",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Order {self.id} status={self.status}>"
