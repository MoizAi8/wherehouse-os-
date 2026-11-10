from datetime import datetime, timedelta, timezone
import asyncio
import json
import math
from uuid import uuid4
from typing import cast

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fulfillment.config import settings
from fulfillment.models.agent_event import AgentEvent
from fulfillment.models.carrier_booking import CarrierBooking
from fulfillment.models.fulfillment_center import FulfillmentCenter
from fulfillment.models.order import Order, OrderStatus
from fulfillment.models.shipment import Shipment, ShipmentStatus
from fulfillment.schemas.carrier_booking import BookingRequest
from fulfillment.services.carrier_adapters import (
    BookingReceipt,
    CarrierAmbiguous,
    CarrierRejected,
    CarrierRetryable,
    CarrierUnavailable,
    get_carrier_adapter,
    payload_hash,
)
from fulfillment.services.inventory import InventoryConflict, InventoryNotFound

MAX_BOOKING_ATTEMPTS = 4
CLAIM_SECONDS = 120
PROVIDER_TIMEOUT_SECONDS = 20


def booking_event(booking: CarrierBooking, action: str, actor_id: str = "worker") -> AgentEvent:
    return AgentEvent(
        agent_name="FulfillmentOrchestrator",
        event_type="carrier_booking_" + action,
        entity_id=booking.id,
        created_at=datetime.now(timezone.utc),
        summary="Sandbox carrier booking " + action
        if booking.sandbox
        else "Carrier booking " + action,
        details_json=json.dumps(
            {
                "shipment_id": booking.shipment_id,
                "provider": booking.provider,
                "sandbox": booking.sandbox,
                "attempt": booking.attempts,
                "actor_id": actor_id,
                "error_code": booking.error_code,
            }
        ),
    )


async def active_booking(db: AsyncSession, shipment_id: str) -> CarrierBooking | None:
    return cast(
        CarrierBooking | None,
        await db.scalar(
            select(CarrierBooking).where(
                CarrierBooking.shipment_id == shipment_id,
                CarrierBooking.active,
            )
        ),
    )


async def lock_shipment_order(db: AsyncSession, shipment_id: str) -> tuple[Shipment, Order]:
    shipment = await db.get(Shipment, shipment_id)
    if shipment is None:
        raise InventoryNotFound("Shipment not found")
    order = await db.scalar(select(Order).where(Order.id == shipment.order_id).with_for_update())
    if order is None:
        raise InventoryNotFound("Order not found")
    await db.refresh(shipment)
    return shipment, order


async def request_booking(
    db: AsyncSession, shipment_id: str, request: BookingRequest, actor_id: str
) -> CarrierBooking:
    shipment, order = await lock_shipment_order(db, shipment_id)
    key = str(request.idempotency_key)
    prior = await db.scalar(select(CarrierBooking).where(CarrierBooking.idempotency_key == key))
    options = request.model_dump(mode="json", exclude={"idempotency_key"})
    if prior:
        if prior.shipment_id != shipment_id or prior.request["options"] != options:
            raise InventoryConflict("Idempotency key already used for different booking details")
        return prior
    if await active_booking(db, shipment_id):
        raise InventoryConflict("Shipment already has an active booking intent")
    if (
        order.status != OrderStatus.PROCESSING
        or shipment.status != ShipmentStatus.LABEL_CREATED
        or shipment.last_polled_at is not None
    ):
        raise InventoryConflict("Only an unhanded routed shipment can be booked")
    provider = settings.carrier_booking_provider
    adapter = get_carrier_adapter(
        provider, async_sessionmaker(bind=db.bind, expire_on_commit=False)
    )
    if not adapter.sandbox and request.sandbox_scenario != "accepted":
        raise InventoryConflict("Sandbox scenarios cannot be used with a live carrier")
    center = await db.get(FulfillmentCenter, order.fulfillment_center_id)
    if center is None or not math.isfinite(shipment.weight_kg) or shipment.weight_kg <= 0:
        raise InventoryConflict("Booking requires a fulfillment center and positive parcel weight")
    if not all(
        (
            order.shipping_address.strip(),
            order.shipping_city.strip(),
            order.shipping_country.strip(),
            center.address.strip(),
            center.city.strip(),
            center.country.strip(),
        )
    ):
        raise InventoryConflict("Booking requires complete sender and recipient addresses")
    payload = {
        "shipment_id": shipment.id,
        "order_id": order.id,
        "internal_tracking": shipment.tracking_number,
        "carrier_name": shipment.carrier_name,
        "weight_kg": shipment.weight_kg,
        "sender": {
            "name": center.name,
            "address": center.address,
            "city": center.city,
            "region": center.state,
            "postal_code": center.zip_code,
            "country": center.country,
        },
        "recipient": {
            "address": order.shipping_address,
            "city": order.shipping_city,
            "region": order.shipping_state,
            "postal_code": order.shipping_zip,
            "country": order.shipping_country,
        },
        "options": options,
    }
    booking = CarrierBooking(
        shipment_id=shipment.id,
        provider=provider,
        idempotency_key=key,
        request_hash=payload_hash(payload),
        request=payload,
        sandbox=adapter.sandbox,
        attempts=0,
        status="queued",
        due_at=datetime.now(timezone.utc),
    )
    db.add(booking)
    await db.flush()
    db.add(booking_event(booking, "queued", actor_id))
    return booking


async def cancel_booking(db: AsyncSession, shipment_id: str, actor_id: str) -> CarrierBooking:
    await lock_shipment_order(db, shipment_id)
    booking = await active_booking(db, shipment_id)
    if booking is None:
        raise InventoryNotFound("No active booking intent")
    # Lock after the order, consistently with the worker's result transaction.
    await db.refresh(booking, with_for_update=True)
    if booking.status not in {"queued", "retry", "failed"}:
        raise InventoryConflict(
            "Provider acceptance or uncertainty requires carrier reconciliation"
        )
    booking.status, booking.active, booking.due_at = "cancelled", False, None
    db.add(booking_event(booking, "cancelled", actor_id))
    return booking


async def reconcile_booking(db: AsyncSession, shipment_id: str, actor_id: str) -> CarrierBooking:
    await lock_shipment_order(db, shipment_id)
    booking = await active_booking(db, shipment_id)
    if booking is None:
        raise InventoryNotFound("No active booking intent")
    await db.refresh(booking, with_for_update=True)
    if booking.status != "unknown":
        raise InventoryConflict("Only an uncertain booking can be reconciled")
    booking.due_at = datetime.now(timezone.utc)
    db.add(booking_event(booking, "reconciliation_requested", actor_id))
    return booking


async def process_due_bookings(
    sessions: async_sessionmaker[AsyncSession], limit: int = 20, task_id: str | None = None
) -> int:
    processed = 0
    for _ in range(limit):
        now = datetime.now(timezone.utc)
        claim = str(uuid4())
        async with sessions.begin() as db:
            # A lost worker may have called the carrier. Never blindly rebook.
            expired = list(
                await db.scalars(
                    update(CarrierBooking)
                    .where(
                        CarrierBooking.active,
                        CarrierBooking.status == "submitting",
                        CarrierBooking.due_at <= now,
                    )
                    .values(status="unknown", claim_token=None, error_code="worker_claim_expired")
                    .returning(CarrierBooking)
                )
            )
            for row in expired:
                row.status, row.claim_token = "unknown", None
                row.error_code = "worker_claim_expired"
                db.add(booking_event(row, "unknown"))
            due = (
                select(CarrierBooking.id)
                .where(
                    CarrierBooking.active,
                    CarrierBooking.status.in_(["queued", "retry", "unknown"]),
                    CarrierBooking.due_at <= now,
                )
                .order_by(CarrierBooking.due_at, CarrierBooking.id)
                .limit(1)
            )
            booking = await db.scalar(
                select(CarrierBooking)
                .where(CarrierBooking.id == due.scalar_subquery())
                .with_for_update(skip_locked=True)
            )
            if booking is None:
                break
            reconcile = booking.status == "unknown"
            claimed = await db.scalar(
                update(CarrierBooking)
                .where(
                    CarrierBooking.id == booking.id,
                    CarrierBooking.status == booking.status,
                    CarrierBooking.active,
                )
                .values(
                    status="submitting",
                    claim_token=claim,
                    due_at=now + timedelta(seconds=CLAIM_SECONDS),
                    attempts=CarrierBooking.attempts + (0 if reconcile else 1),
                )
                .returning(CarrierBooking.id)
            )
            if claimed is None:
                continue
            await db.refresh(booking)
            db.add(booking_event(booking, "claimed", task_id or "worker"))
        receipt = None
        state, error_code = "booked", None
        try:
            adapter = get_carrier_adapter(booking.provider, sessions)
            if reconcile:
                receipt = await asyncio.wait_for(
                    adapter.lookup(booking.idempotency_key, booking.request),
                    PROVIDER_TIMEOUT_SECONDS,
                )
                if receipt is None:
                    if adapter.idempotent_submission and booking.attempts < MAX_BOOKING_ATTEMPTS:
                        state, error_code = "retry", "provider_lookup_empty"
                    else:
                        state, error_code = "unknown", "manual_reconciliation_required"
            else:
                receipt = await asyncio.wait_for(
                    adapter.book(booking.idempotency_key, booking.request, booking.attempts),
                    PROVIDER_TIMEOUT_SECONDS,
                )
            if receipt and (
                not receipt.provider_reference
                or not receipt.tracking_number
                or len(receipt.provider_reference) > 100
                or len(receipt.tracking_number) > 255
                or receipt.sandbox != booking.sandbox
            ):
                raise CarrierAmbiguous("invalid_provider_receipt")
        except CarrierRetryable:
            state, error_code = (
                ("retry" if booking.attempts < MAX_BOOKING_ATTEMPTS else "failed"),
                "provider_temporarily_unavailable",
            )
        except CarrierRejected:
            state, error_code = ("unknown" if reconcile else "failed"), "provider_rejected"
        except CarrierUnavailable:
            # Configuration removal does not prove a previous submission failed.
            state, error_code = ("unknown" if reconcile else "failed"), "provider_not_activated"
        except Exception:
            state, error_code = (
                "unknown",
                "manual_reconciliation_required" if reconcile else "provider_outcome_uncertain",
            )
            receipt = None
        await finalize_booking(sessions, booking.id, claim, state, error_code, receipt)
        processed += 1
    return processed


async def finalize_booking(
    sessions: async_sessionmaker[AsyncSession],
    booking_id: str,
    claim: str,
    state: str,
    error_code: str | None,
    receipt: BookingReceipt | None,
) -> None:
    async with sessions.begin() as db:
        booking = await db.get(CarrierBooking, booking_id)
        if booking is None:
            return
        shipment, order = await lock_shipment_order(db, booking.shipment_id)
        await db.refresh(booking, with_for_update=True)
        if booking.claim_token != claim or booking.status != "submitting":
            return
        if receipt:
            if (
                order.status != OrderStatus.PROCESSING
                or shipment.tracking_number != booking.request["internal_tracking"]
            ):
                state, error_code = "unknown", "warehouse_state_changed"
            else:
                shipment.tracking_number = order.tracking_number = receipt.tracking_number
                booking.provider_reference = receipt.provider_reference
                booking.tracking_number = receipt.tracking_number
        booking.status, booking.error_code, booking.claim_token = state, error_code, None
        # Unknown results are looked up once. Unresolvable uncertainty requires
        # explicit operator reconciliation, not an endless or duplicate send.
        if state == "retry":
            booking.due_at = datetime.now(timezone.utc) + timedelta(
                seconds=30 * 2 ** min(booking.attempts, 4)
            )
        elif state == "unknown" and error_code == "provider_outcome_uncertain":
            booking.due_at = datetime.now(timezone.utc) + timedelta(seconds=30)
        else:
            booking.due_at = None
        db.add(booking_event(booking, state))


async def ensure_no_active_booking(db: AsyncSession, order_id: str) -> None:
    booking = await db.scalar(
        select(CarrierBooking.id)
        .join(Shipment)
        .where(
            Shipment.order_id == order_id,
            CarrierBooking.active,
        )
        .limit(1)
    )
    if booking:
        raise InventoryConflict(
            "Cancel or reconcile the active carrier booking before changing fulfillment"
        )


async def require_booking_safe_to_dispatch(db: AsyncSession, order_id: str) -> None:
    shipments = list(await db.scalars(select(Shipment).where(Shipment.order_id == order_id)))
    for shipment in shipments:
        booking = await active_booking(db, shipment.id)
        if booking and booking.status != "booked":
            raise InventoryConflict("Carrier booking must complete before dispatch")
        if settings.carrier_require_booking_before_dispatch and booking is None:
            raise InventoryConflict("A confirmed carrier booking is required before dispatch")
        if booking and booking.sandbox and not settings.carrier_sandbox_enabled:
            raise InventoryConflict("Sandbox bookings cannot authorize live dispatch")
