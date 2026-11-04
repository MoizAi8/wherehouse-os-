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
from fulfillment.agents.rerouting import ReroutingAgent
from fulfillment.models.inventory import Product, OrderLine
from fulfillment.models.order import OrderStatus
from fulfillment.services.inventory import InventoryConflict
from fulfillment.services.order_service import OrderService
from fulfillment.schemas.order import OrderCreate
from fulfillment.models.fulfillment_center import FulfillmentCenter


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
async def test_daily_capacity_rolls_over_without_overbooking(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'capacity.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions.begin() as db:
            center = FulfillmentCenter(name='Daily', address='Sandbox', city='Test', state='NY', zip_code='10001',
                                       max_daily_orders=1, current_daily_orders=1,
                                       capacity_day=datetime.now(timezone.utc).date() - timedelta(days=1))
            db.add_all([center, CarrierRate(carrier_name='Sandbox', service_name='Ground', origin_zip='10001',
                                          destination_zip='10002', weight_kg_min=0, weight_kg_max=10,
                                          base_rate=10, rate_per_kg=1, estimated_days_min=1, estimated_days_max=2)])
        payload = OrderCreate(customer_email='test@example.com', shipping_address='Sandbox',
                              shipping_city='Test', shipping_state='NY', shipping_zip='10002', total_weight_kg=1)
        async with sessions.begin() as db:
            routed = await OrderService(db).create_order(payload)
            assert routed.status == 'processing'
        async with sessions.begin() as db:
            assert (await OrderService(db).create_order(payload)).status == 'pending'
            persisted = await db.get(FulfillmentCenter, center.id)
            assert persisted.current_daily_orders == 1
            assert persisted.capacity_day == datetime.now(timezone.utc).date()
        async with sessions.begin() as db:
            # A cancellation from yesterday must not free today's occupied slot.
            db.add(Product(sku='YESTERDAY', name='Older order'))
            await db.flush()
            db.add(OrderLine(order_id=routed.id, sku='YESTERDAY', quantity=1))
            shipment = await db.scalar(select(Shipment).where(Shipment.order_id == routed.id))
            shipment.created_at = datetime.now(timezone.utc) - timedelta(days=1)
            await db.flush()
            await OrderService(db).cancel_order(routed.id, 'Old order cancellation', 'acceptance')
            persisted = await db.get(FulfillmentCenter, center.id)
            assert persisted.current_daily_orders == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_automatic_reroute_synchronizes_order_and_rejects_dispatched_typed_order(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'reroute.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions.begin() as db:
            order = Order(customer_email='test@example.com', shipping_address='Sandbox',
                          shipping_city='Test', shipping_state='NY', shipping_zip='10002',
                          status=OrderStatus.PROCESSING, tracking_number='OLD')
            db.add(order)
            await db.flush()
            shipment = Shipment(order_id=order.id, carrier_name='Original', tracking_number='OLD',
                                origin_zip='10001', destination_zip='10002', weight_kg=5, shipping_cost=30)
            db.add(shipment)
            db.add(CarrierRate(carrier_name='Alternative', service_name='Ground', origin_zip='10001',
                               destination_zip='10002', weight_kg_min=0, weight_kg_max=10,
                               base_rate=10, rate_per_kg=2, estimated_days_min=2, estimated_days_max=3))
            await db.flush()
            result = await ReroutingAgent(db).execute_reroute(shipment, {
                'should_reroute': True, 'alternative_carrier': 'Alternative',
            })
            assert result and order.tracking_number == shipment.tracking_number != 'OLD'
            assert order.shipping_cost == shipment.shipping_cost == 20
            db.add(Product(sku='TEST', name='Test'))
            await db.flush()
            db.add(OrderLine(order_id=order.id, sku='TEST', quantity=1))
            order.status = OrderStatus.SHIPPED
            await db.flush()
            tracking = shipment.tracking_number
            with pytest.raises(InventoryConflict, match='handoff requires reconciliation'):
                await ReroutingAgent(db).execute_reroute(shipment, {
                    'should_reroute': True, 'alternative_carrier': 'Alternative',
                })
            assert shipment.tracking_number == order.tracking_number == tracking
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
