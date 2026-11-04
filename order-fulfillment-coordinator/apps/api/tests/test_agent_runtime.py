from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from fulfillment.database import Base
from fulfillment.models.agent_event import AgentEvent
from fulfillment.services.agent_runtime import agent_runtime_status
from fulfillment.agents.monitor import MonitorAgent
from fulfillment.models.order import Order
from fulfillment.models.shipment import Shipment
from fulfillment.models.carrier_rate import CarrierRate
from fulfillment.agents.cost_optimizer import CostOptimizer


@pytest.mark.asyncio
async def test_runtime_requires_recent_committed_outcomes(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'runtime.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            assert {a['status'] for a in await agent_runtime_status(db)} == {'UNVERIFIED'}
        now = datetime.now(timezone.utc)
        async with sessions.begin() as db:
            for name, event, age in (
                ('RoutingAgent', 'route_selected', 0),
                ('PredictionAgent', 'failure_prediction', 48),
                ('CostOptimizer', 'analysis_failed', 0),
                ('CommunicationAgent', 'delivery_claimed', 0),
                ('MonitorAgent', 'scan_complete', -2),
            ):
                db.add(AgentEvent(agent_name=name, event_type=event, summary='test',
                                  created_at=now - timedelta(hours=age)))
        async with sessions() as db:
            states = {a['name']: a for a in await agent_runtime_status(db)}
            assert states['RoutingAgent']['status'] == 'IDLE'
            assert states['RoutingAgent']['event_id']
            assert states['PredictionAgent']['status'] == 'UNVERIFIED'
            assert states['CostOptimizer']['status'] == 'FAILED'
            assert states['CommunicationAgent']['status'] == 'UNVERIFIED'
            assert states['MonitorAgent']['status'] == 'UNVERIFIED'
        async with sessions.begin() as db:
            db.add(AgentEvent(agent_name='CostOptimizer', event_type='cost_analysis',
                              summary='recovered', created_at=datetime.now(timezone.utc)))
        async with sessions() as db:
            assert next(a for a in await agent_runtime_status(db) if a['name'] == 'CostOptimizer')['status'] == 'IDLE'
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_cost_recommendations_preserve_transit_and_do_not_execute(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'cost.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions.begin() as db:
            order = Order(customer_email='test@example.com', shipping_address='Sandbox',
                          shipping_city='Test', shipping_state='NY', shipping_zip='10001')
            db.add(order)
            await db.flush()
            shipment = Shipment(order_id=order.id, carrier_name='Original', tracking_number='KEEP',
                                origin_zip='10001', destination_zip='10002', weight_kg=5, shipping_cost=30,
                                estimated_delivery=datetime.now(timezone.utc) + timedelta(days=4))
            db.add(shipment)
            for name, base, per_kg, days in [('Eligible', 10, 2, 3), ('Slow', 1, 1, 5), ('Heavy', 1, 10, 2)]:
                db.add(CarrierRate(carrier_name=name, service_name='Ground', origin_zip='10001',
                                   destination_zip='10002', weight_kg_min=0, weight_kg_max=10,
                                   base_rate=base, rate_per_kg=per_kg, estimated_days_min=1, estimated_days_max=days))
            await db.flush()
            result = await CostOptimizer(db).analyze_cycle('acceptance')
            quotes = [r for r in result['recommendations'] if r['type'] == 'configured_rate_saving']
            assert len(quotes) == 1
            assert (quotes[0]['carrier'], quotes[0]['quoted_cost'], quotes[0]['potential_saving']) == ('Eligible', 20, 10)
            assert quotes[0]['approval_required']
            assert shipment.tracking_number == 'KEEP' and shipment.shipping_cost == 30
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_bounded_monitor_rotates_unchanged_shipments(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'rotation.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions.begin() as db:
            order = Order(customer_email='test@example.com', shipping_address='Sandbox',
                          shipping_city='Test', shipping_state='NY', shipping_zip='10001')
            db.add(order)
            await db.flush()
            for i in range(201):
                db.add(Shipment(order_id=order.id, carrier_name='Sandbox', tracking_number=str(i),
                                origin_zip='10001', destination_zip='10002',
                                estimated_delivery=datetime.now(timezone.utc) + timedelta(days=2)))
        async with sessions.begin() as db:
            monitor = MonitorAgent(db)
            first = await monitor.get_active_shipments()
            assert len(first) == 200
            first_ids = {s.id for s in first}
            for shipment in first:
                assert not (await monitor.check_delay(shipment))['is_delayed']
        async with sessions.begin() as db:
            monitor = MonitorAgent(db)
            second = await monitor.get_active_shipments()
            assert second[0].id not in first_ids
            for shipment in second:
                await monitor.check_delay(shipment)
        async with sessions() as db:
            assert not list(await db.scalars(select(Shipment).where(Shipment.last_monitored_at.is_(None))))
            assert all(s.last_polled_at is None for s in await db.scalars(select(Shipment)))
    finally:
        await engine.dispose()
