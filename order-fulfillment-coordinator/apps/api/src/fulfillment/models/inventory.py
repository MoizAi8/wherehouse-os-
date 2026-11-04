from datetime import datetime
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from fulfillment.database import Base


class Product(Base):
    __tablename__ = "inventory_products"

    sku: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))


class Stock(Base):
    __tablename__ = "inventory_stock"
    __table_args__ = (
        UniqueConstraint("sku", "center_id", name="uq_inventory_stock_location"),
        CheckConstraint("reserved >= 0 AND on_hand >= reserved", name="ck_inventory_stock_balance"),
        CheckConstraint("low_stock_threshold >= 0", name="ck_inventory_stock_threshold"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    sku: Mapped[str] = mapped_column(ForeignKey("inventory_products.sku"))
    center_id: Mapped[str] = mapped_column(ForeignKey("fulfillment_centers.id"))
    on_hand: Mapped[int] = mapped_column(default=0)
    reserved: Mapped[int] = mapped_column(default=0)
    low_stock_threshold: Mapped[int] = mapped_column(default=0)


class OrderLine(Base):
    __tablename__ = "order_lines"
    __table_args__ = (
        UniqueConstraint("order_id", "sku", name="uq_order_lines_sku"),
        CheckConstraint("quantity > 0", name="ck_order_lines_quantity"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    sku: Mapped[str] = mapped_column(ForeignKey("inventory_products.sku"))
    quantity: Mapped[int]


class Reservation(Base):
    __tablename__ = "inventory_reservations"
    __table_args__ = (
        UniqueConstraint("stock_id", "order_id", name="uq_inventory_reservation_order_stock"),
        CheckConstraint("quantity > 0", name="ck_inventory_reservation_quantity"),
        CheckConstraint("status IN ('reserved', 'released', 'consumed')", name="ck_inventory_reservation_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    stock_id: Mapped[str] = mapped_column(ForeignKey("inventory_stock.id"))
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    order_line_id: Mapped[str | None] = mapped_column(ForeignKey("order_lines.id"), unique=True)
    quantity: Mapped[int]
    status: Mapped[str] = mapped_column(String(12), default="reserved")


class StockMovement(Base):
    __tablename__ = "inventory_movements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    stock_id: Mapped[str] = mapped_column(ForeignKey("inventory_stock.id"), index=True)
    reservation_id: Mapped[str | None] = mapped_column(ForeignKey("inventory_reservations.id"))
    actor_id: Mapped[str] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(12))
    on_hand_delta: Mapped[int]
    reserved_delta: Mapped[int]
    reason: Mapped[str] = mapped_column(String(250))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
