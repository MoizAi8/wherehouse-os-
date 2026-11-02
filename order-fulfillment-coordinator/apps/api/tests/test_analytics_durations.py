from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from fulfillment.database import Base
from fulfillment.models.order import Order, OrderStatus
from fulfillment.models.shipment import Shipment, ShipmentStatus
from fulfillment.services.analytics_service import AnalyticsService


@pytest.mark.asyncio
async def test_sqlite_delivery_duration_and_completed_on_time_denominator():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine)() as db:
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        db.add(Order(id="qa-order", customer_email="qa@example.com", shipping_address="QA",
            shipping_city="QA", shipping_zip="54000", shipping_state="QA", status=OrderStatus.DELIVERED))
        await db.flush()
        for identifier, actual, delayed in [("completed", start+timedelta(days=2), False), ("active", None, True)]:
            db.add(Shipment(id=identifier, order_id="qa-order", carrier_name="QA", tracking_number=identifier,
                status=ShipmentStatus.DELIVERED if actual else ShipmentStatus.IN_TRANSIT,
                origin_zip="54000", destination_zip="74000", created_at=start,
                estimated_delivery=start+timedelta(days=3), actual_delivery=actual, is_delayed=delayed))
        await db.commit()
        service = AnalyticsService(db)
        kpis = await service.compute_kpis()
        assert kpis.avg_delivery_time_days == 2.0
        assert kpis.on_time_delivery_rate == 100.0
        assert kpis.orders_delayed == 1
        carriers = await service.carrier_performance()
        assert carriers[0].avg_delivery_days == 2.0
    await engine.dispose()
