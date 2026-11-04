from __future__ import annotations

from datetime import date, datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fulfillment.database import Base

if TYPE_CHECKING:
    from fulfillment.models.order import Order


class FulfillmentCenter(Base):
    __tablename__ = "fulfillment_centers"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    zip_code: Mapped[str] = mapped_column(String(20), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(100), default="US")
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    capacity_pct: Mapped[float] = mapped_column(Float, default=0.0)
    max_daily_orders: Mapped[int] = mapped_column(default=1000)
    current_daily_orders: Mapped[int] = mapped_column(default=0)
    capacity_day: Mapped[date] = mapped_column(Date, default=lambda: datetime.now(timezone.utc).date(), server_default=func.current_date())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    orders: Mapped[list[Order]] = relationship("Order", back_populates="fulfillment_center")

    def __repr__(self) -> str:
        return f"<FulfillmentCenter {self.name}>"
