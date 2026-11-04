from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from fulfillment.agents.communication import CommunicationAgent
from fulfillment.agents.orchestrator import FulfillmentOrchestrator
from fulfillment.config import settings
from fulfillment.database import Base
from fulfillment.models.agent_event import AgentEvent
from fulfillment.models.carrier_rate import CarrierRate
from fulfillment.models.fulfillment_center import FulfillmentCenter
from fulfillment.models.notification import Notification
from fulfillment.models.shipment import Shipment, ShipmentStatus
from fulfillment.schemas.order import OrderCreate, OrderRouteRequest, OrderUpdate
from fulfillment.schemas.webhook import ShipmentEventWebhook
from fulfillment.services.order_service import OrderService
from fulfillment.services.shipment_service import ShipmentService


@pytest.mark.asyncio
@pytest.mark.parametrize("reported_delay", [False, True], ids=["overdue", "carrier-reported"])
async def test_configured_route_survives_monitor_and_duplicate_dispatch(tmp_path, reported_delay, monkeypatch):
    monkeypatch.setattr(settings, "allow_automatic_rerouting", False)
    monkeypatch.setattr(settings, "sendgrid_api_key", "")
    monkeypatch.setattr(settings, "twilio_account_sid", "")
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'orders.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions.begin() as db:
            center = FulfillmentCenter(
                name="Sandbox West", address="1 Test Ave", zip_code="90210",
                city="Beverly Hills", state="CA",
            )
            center.capacity_pct = 10
            db.add_all([center, FulfillmentCenter(
                name="Sandbox Without Rates", address="2 Test Ave", zip_code="60601",
                city="Chicago", state="IL", capacity_pct=1,
            )])
            db.add(CarrierRate(
                carrier_name="Sandbox Carrier", service_name="Ground",
                origin_zip="90210", destination_zip="10001",
                weight_kg_min=0, weight_kg_max=20, base_rate=10, rate_per_kg=2,
                estimated_days_min=2, estimated_days_max=3,
            ))
            await db.flush()
            center_id = center.id
            service = OrderService(db)
            order = await service.create_order(OrderCreate(
                customer_email="warehouse-test@example.com", shipping_address="10 Test St",
                shipping_city="New York", shipping_state="NY", shipping_zip="10001",
                total_weight_kg=5,
            ))
            assert order.status == "processing"
            assert order.shipping_cost == 20
            assert order.estimated_delivery is not None
            assert order.estimated_delivery.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)
            with pytest.raises(ValueError, match="already routed"):
                await service.route_order(order.id)

        async with sessions.begin() as db:
            cycle = await FulfillmentOrchestrator(db).run_monitor_cycle()
            assert cycle.shipments_checked == 1
            assert cycle.delays_detected == 0
            assert await db.scalar(select(func.count()).select_from(Shipment)) == 1
            center = await db.get(FulfillmentCenter, center_id)
            assert center is not None and center.current_daily_orders == 1
            event = await db.scalar(select(AgentEvent).where(
                AgentEvent.agent_name == "RoutingAgent", AgentEvent.entity_id == order.id,
            ))
            assert event is not None and event.event_type == "route_selected"

        async with sessions.begin() as db:
            shipment = await db.scalar(select(Shipment))
            assert shipment is not None
            await ShipmentService(db).update_from_event(ShipmentEventWebhook(
                tracking_number=shipment.tracking_number,
                carrier=shipment.carrier_name,
                status="delayed" if reported_delay else "in_transit",
                status_detail="Sandbox carrier reported a delay" if reported_delay else None,
                estimated_delivery=datetime.now(timezone.utc) + timedelta(days=1 if reported_delay else -1),
            ))
            if reported_delay:
                db.add(CarrierRate(
                    carrier_name="Sandbox Alternative", service_name="Express",
                    origin_zip="90210", destination_zip="10001",
                    weight_kg_min=0, weight_kg_max=20, base_rate=11, rate_per_kg=2,
                    estimated_days_min=2, estimated_days_max=3,
                ))

        async with sessions.begin() as db:
            delayed = await FulfillmentOrchestrator(db).run_monitor_cycle()
            assert delayed.shipments_checked == delayed.delays_detected == 1
            assert delayed.reroutes_initiated == delayed.notifications_sent == 0
            assert any(event["type"] == "cost_analysis" for event in delayed.events)
            assert any(event["type"] == "reroute_recommended" for event in delayed.events) == reported_delay

        async with sessions.begin() as db:
            shipment = await db.scalar(select(Shipment))
            assert shipment is not None and shipment.status == ShipmentStatus.DELAYED
            agents = set(await db.scalars(select(AgentEvent.agent_name).where(
                AgentEvent.entity_id == shipment.id,
            )))
            assert {"MonitorAgent", "PredictionAgent"} <= agents
            assert ("ReroutingAgent" in agents) == reported_delay
            assert shipment.carrier_name == "Sandbox Carrier"
            alert = await CommunicationAgent(db).send_delay_alert(shipment, "Sandbox delay")
            assert alert is not None and alert["notifications_sent"] == 0
            await db.flush()
            notification = await db.scalar(select(Notification).where(Notification.shipment_id == shipment.id))
            assert notification is not None and notification.status == "skipped"
            service = OrderService(db)
            pending = await service.create_order(OrderCreate(
                customer_email="warehouse-test@example.com", shipping_address="20 Test St",
                shipping_city="Chicago", shipping_state="IL", shipping_zip="60601",
                total_weight_kg=5,
            ))
            assert pending.status == "pending"
            assert pending.tracking_number is None
            with pytest.raises(ValueError, match="No suitable"):
                await service.route_order(pending.id)
            await db.flush()
            await service.update_order(pending.id, OrderUpdate(shipping_zip="10001"))
            with pytest.raises(ValueError, match="No suitable"):
                await service.route_order(pending.id, OrderRouteRequest(max_cost=15))
            with pytest.raises(ValueError, match="No suitable"):
                await service.route_order(pending.id, OrderRouteRequest(max_days=2))
            assert await db.scalar(select(func.count()).select_from(Shipment)) == 1
    finally:
        await engine.dispose()
