"""500 business scenarios; explicitly run against disposable PostgreSQL + Celery.

Five lifecycle outcomes x five quantities x five parcel weights x four basket
sizes. These are operational parameter cases, not 500 distinct features.
External carrier events are sandbox inputs; no real carrier booking is claimed.
"""
import asyncio
from datetime import datetime, timedelta, timezone
import os
from uuid import uuid4

import pytest
from sqlalchemy import select, func
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from fulfillment.models.agent_event import AgentEvent, MonitorTaskResult
from fulfillment.models.carrier_rate import CarrierRate
from fulfillment.models.fulfillment_center import FulfillmentCenter
from fulfillment.models.inventory import Product, Stock, StockMovement, Reservation
from fulfillment.models.order import Order
from fulfillment.models.shipment import Shipment
from fulfillment.schemas.inventory import StockChange
from fulfillment.schemas.order import OrderCreate, OrderLineCreate
from fulfillment.schemas.webhook import ShipmentEventWebhook
from fulfillment.services.inventory import InventoryService, InventoryConflict
from fulfillment.services.order_service import OrderService
from fulfillment.services.shipment_service import ShipmentService
from fulfillment.tasks import run_monitor_cycle


@pytest.mark.asyncio
@pytest.mark.parametrize('outcome', ['delivered', 'cancelled', 'shortage', 'replenished', 'delayed'])
@pytest.mark.parametrize('quantity', [1, 2, 10, 50, 100])
@pytest.mark.parametrize('weight', [0.1, 1, 5, 10, 25])
@pytest.mark.parametrize('line_count', [1, 2, 3, 4])
async def test_warehouse_matrix(outcome, quantity, weight, line_count, record_property):
    url = os.environ['DATABASE_URL']
    target = make_url(url)
    assert (target.host, target.port, target.database) == ('127.0.0.1', 55471, 'matrix_acceptance')
    assert os.environ['CELERY_BROKER_URL'] == 'redis://127.0.0.1:56379/11'
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    suffix = uuid4().hex[:12]
    stocks = []
    initial = quantity - 1 if outcome in {'shortage', 'replenished'} else quantity * 2
    try:
        async with sessions.begin() as db:
            center = FulfillmentCenter(name=suffix, address='Sandbox', city='Test', state='NY', zip_code=suffix)
            db.add(center)
            await db.flush()
            for i in range(line_count):
                sku = f'{suffix}-{i}'
                db.add(Product(sku=sku, name='Acceptance SKU'))
                await db.flush()
                stock = Stock(sku=sku, center_id=center.id)
                db.add(stock)
                await db.flush()
                stocks.append((stock.id, sku))
                if initial:
                    payload = StockChange(operation_id=uuid4(), kind='receipt', quantity_delta=initial, reason='Acceptance receipt')
                    await InventoryService(db).change_stock(stock.id, payload, 'acceptance')
                    await InventoryService(db).change_stock(stock.id, payload, 'acceptance')
            for carrier, base in [('Sandbox Primary', 10), ('Sandbox Alternative', 11)]:
                db.add(CarrierRate(carrier_name=carrier, service_name='Ground', origin_zip=suffix,
                                   destination_zip='10001', weight_kg_min=0, weight_kg_max=30,
                                   base_rate=base, rate_per_kg=1, estimated_days_min=2, estimated_days_max=3))
        async with sessions.begin() as db:
            order = await OrderService(db).create_order(OrderCreate(
                customer_email='matrix@example.com', shipping_address='Sandbox', shipping_city='Test',
                shipping_state='NY', shipping_zip='10001', total_weight_kg=weight,
                lines=[OrderLineCreate(sku=sku, quantity=quantity) for _, sku in stocks],
            ))
            order_id = order.id
            assert order.status == ('pending' if outcome in {'shortage', 'replenished'} else 'processing')
        record_property('order_id', order_id)
        record_property('external_provider', 'sandbox carrier events; no booking')
        if outcome in {'shortage', 'replenished'}:
            async with sessions() as db:
                assert await db.scalar(select(func.count()).select_from(Reservation).where(Reservation.order_id == order_id)) == 0
                assert await db.scalar(select(func.count()).select_from(Shipment).where(Shipment.order_id == order_id)) == 0
            if outcome == 'replenished':
                async with sessions.begin() as db:
                    for stock_id, _ in stocks:
                        await InventoryService(db).change_stock(stock_id, StockChange(
                            operation_id=uuid4(), kind='receipt', quantity_delta=1, reason='Replenish'), 'acceptance')
                    await OrderService(db).route_order(order_id)
        if outcome != 'shortage':
            async with sessions.begin() as db:
                service = OrderService(db)
                with pytest.raises(ValueError, match='already routed'):
                    await service.route_order(order_id)
                shipment = await db.scalar(select(Shipment).where(Shipment.order_id == order_id))
                assert shipment.shipping_cost == pytest.approx(10 + weight)
                shipment_id, tracking = shipment.id, shipment.tracking_number
                assert await db.scalar(select(func.count()).select_from(Shipment).where(Shipment.order_id == order_id)) == 1
                if outcome == 'cancelled':
                    await service.cancel_order(order_id, 'Acceptance cancellation', 'acceptance')
                    await service.cancel_order(order_id, 'Acceptance cancellation', 'acceptance')
                    with pytest.raises(InventoryConflict):
                        await service.dispatch_order(order_id, 'Rejected dispatch', 'acceptance')
                else:
                    await service.dispatch_order(order_id, 'Acceptance dispatch', 'acceptance')
                    await service.dispatch_order(order_id, 'Acceptance dispatch', 'acceptance')
            if outcome == 'delayed':
                async with sessions.begin() as db:
                    await ShipmentService(db).update_from_event(ShipmentEventWebhook(
                        tracking_number=tracking, carrier='Sandbox Primary', status='delayed',
                        status_detail='Sandbox weather', estimated_delivery=datetime.now(timezone.utc) - timedelta(days=1),
                    ))
                task = run_monitor_cycle.delay()
                result = await asyncio.to_thread(task.get, timeout=60)
                record_property('task_id', task.id)
                record_property('cycle_id', result['cycle_id'])
                assert result['delays_detected'] >= 1
                async with sessions() as db:
                    assert await db.get(MonitorTaskResult, task.id) is not None
                    events = list(await db.scalars(select(AgentEvent).where(AgentEvent.entity_id == shipment_id)))
                    assert {'MonitorAgent', 'PredictionAgent', 'ReroutingAgent'} <= {e.agent_name for e in events}
                    recommendation = next(e for e in events if e.event_type == 'reroute_recommended')
                    record_property('recommendation_event_id', recommendation.id)
                    current = await db.get(Shipment, shipment_id)
                    assert current.carrier_name == 'Sandbox Primary' and current.tracking_number == tracking
            if outcome != 'cancelled':
                async with sessions.begin() as db:
                    event = ShipmentEventWebhook(tracking_number=tracking, carrier='Sandbox Primary', status='delivered', timestamp=datetime.now(timezone.utc))
                    await ShipmentService(db).update_from_event(event)
                    await ShipmentService(db).update_from_event(event)
        async with sessions() as db:
            current_order = await db.get(Order, order_id)
            expected_status = 'pending' if outcome == 'shortage' else 'cancelled' if outcome == 'cancelled' else 'delivered'
            assert current_order.status == expected_status
            record_property('final_status', expected_status)
            for stock_id, _ in stocks:
                stock = await db.get(Stock, stock_id)
                expected_on_hand = initial if outcome in {'shortage', 'cancelled'} else 0 if outcome == 'replenished' else quantity
                assert (stock.on_hand, stock.reserved) == (expected_on_hand, 0)
                totals = (await db.execute(select(func.sum(StockMovement.on_hand_delta), func.sum(StockMovement.reserved_delta)).where(StockMovement.stock_id == stock_id))).one()
                assert (totals[0] or 0, totals[1] or 0) == (stock.on_hand, stock.reserved)
            record_property('verified_at', datetime.now(timezone.utc).isoformat())
    finally:
        await engine.dispose()
