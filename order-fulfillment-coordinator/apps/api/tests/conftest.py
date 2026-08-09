from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession


def _make_mock_result(scalar_one_or_none=None, scalars_list=None, one=None, scalar=None):
    """Create a properly chained SQLAlchemy Result mock."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar_one_or_none
    if scalars_list is not None:
        result.scalars.return_value.all.return_value = scalars_list
    if one is not None:
        result.one.return_value = one
    if scalar is not None:
        result.scalar.return_value = scalar
    return result


@pytest.fixture
def mock_db():
    db = MagicMock(spec=AsyncSession)
    db.add = MagicMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def mock_result():
    return MagicMock()


class MockShipment:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


@pytest.fixture
def mock_shipment():
    status_mock = MagicMock()
    status_mock.value = "in_transit"
    return MockShipment(
        id=str(uuid4()),
        order_id=str(uuid4()),
        carrier_name="FedEx",
        tracking_number="TRK-TEST123456",
        status=status_mock,
        estimated_delivery=datetime.now(timezone.utc),
        actual_delivery=None,
        origin_zip="90210",
        destination_zip="10001",
        weight_kg=2.5,
        shipping_cost=15.99,
        carrier_status_detail=None,
        is_delayed=False,
        delay_reason=None,
        last_polled_at=None,
    )


@pytest.fixture
def mock_order():
    status_mock = MagicMock()
    status_mock.value = "pending"
    return MockShipment(
        id=str(uuid4()),
        customer_email="test@example.com",
        customer_phone="+1234567890",
        shipping_address="123 Main St",
        shipping_zip="10001",
        shipping_city="New York",
        shipping_state="NY",
        shipping_country="US",
        total_weight_kg=2.5,
        status=status_mock,
    )


@pytest.fixture
def mock_carrier_rate():
    return MockShipment(
        id=str(uuid4()),
        carrier_name="UPS",
        service_name="Ground",
        origin_zip="90210",
        destination_zip="10001",
        weight_kg_min=0.0,
        weight_kg_max=50.0,
        base_rate=12.50,
        rate_per_kg=1.50,
        estimated_days_min=2,
        estimated_days_max=5,
        is_active=True,
    )
