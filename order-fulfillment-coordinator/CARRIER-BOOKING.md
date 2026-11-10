# Carrier booking operations and activation contract

Booking is an opt-in API workflow. The original dashboard and chat are unchanged.
No live carrier integration is implemented or implied. TCS, Leopards, Trax and
PostEx require official API contracts, credentials and acceptance before an
adapter can be registered. The sandbox never purchases a label or moves a parcel.

## Configuration

Set CARRIER_BOOKING_PROVIDER=sandbox and CARRIER_SANDBOX_ENABLED=true only in an
isolated sandbox deployment. CARRIER_REQUIRE_BOOKING_BEFORE_DISPATCH=true makes
booking mandatory; its default false preserves existing operator-recorded
fulfillment. An active pending/uncertain booking always blocks dispatch, even
when the global requirement is false. A sandbox booking cannot authorize dispatch
when sandbox mode is disabled. Production Compose passes all three settings to
API, worker and Beat. Never enable sandbox mode to claim live carrier readiness.

## Authenticated API workflow

1. Route and allocate the order through the existing order/inventory APIs.
2. GET /api/v1/carriers/booking-adapters returns actual activation state.
3. POST /api/v1/shipments/{id}/booking with a UUID idempotency_key,
   recipient_name, recipient_phone, sender_phone (E.164), currency (e.g. PKR),
   payment_mode (prepaid or cod), and cod_amount (positive for COD, zero otherwise).
   Sender/recipient addresses and weight are snapshotted from the routed order.
   The 202 response is a durable intent, NOT provider acceptance.
4. Beat schedules drain_carrier_bookings. The worker claims and commits before
   calling the adapter, then atomically persists receipt/tracking on booking,
   shipment and order. GET the same booking URL to inspect status and sandbox flag.
5. Dispatch only after booked. Signed shipment-event webhooks use the returned
   tracking number and the configured lane's carrier name. A booking receipt is
   not proof of pickup or delivery. Existing dispatch and event-order guards apply.

Reads require a business account. Booking, cancellation, reconciliation and
warehouse writes require operator/admin. Existing global rate limits apply.
Request snapshots include delivery PII; they are not included in read responses
or agent-event log details. Evidence records include booking IDs and worker task
IDs (claim actor_id). No credentials are stored in booking payloads.

## Retry and recovery

Same key and same input returns the same intent; conflicting key reuse returns
409. Only one active intent can exist per shipment. A second drain cannot create a
second provider receipt. Explicit nonacceptance retries with bounded exponential
backoff, at most four submissions. A timeout, invalid receipt or expired worker
claim is UNKNOWN, not a fabricated failure or success. Lookup runs before any
resubmission. Rebooking after an empty lookup is permitted only for an adapter
whose idempotent submission contract has been verified. Failed lookup leaves an
unscheduled UNKNOWN record. POST .../booking/reconcile explicitly requests another
lookup. It does not mark success or blindly resubmit.

POST .../booking/cancel cancels only queued/retry/failed intents locally, retains
history, and permits a corrected new intent with a new key. Submitting, unknown or
booked records require provider reconciliation; this release does not pretend to
cancel a live label. Active booking intents prevent changes to fulfillment data,
order cancellation/deletion and internal rerouting. Carrier events are rejected
until the booking is confirmed.

The explicit sandbox_scenario field supports accepted, retry_once, rejected,
ambiguous and unavailable simulations. Sandbox receipts are durable records in a
separate transaction, so worker-death tests can prove recovery after simulated
provider acceptance. All sandbox tracking starts SANDBOX-.

## Adapter activation requirements

Implement CarrierAdapter.book and lookup, map provider statuses to the explicit
accepted/rejected/retryable/ambiguous contract, enforce timeouts and response
validation, and verify idempotency before declaring idempotent_submission=true.
Keep credentials in existing secured configuration, never in user payloads.
Verify address/service/COD/currency mapping against official documentation and
account capability. Add signed event normalization for the provider's documented
webhook contract; the current normalized HMAC webhook is the internal boundary.
Register the adapter only after sandbox and failure/reconciliation tests pass.
Provider selection is persisted on each intent; changing the configured default
never switches an in-flight booking to another provider.

## Migrations and rollback

Apply e217f65c9843 (UTC capacity day) then f328a76da954 (booking tables) before
starting the candidate. Back up first. The booking downgrade refuses populated
history. Preserve schema and records during application rollback. After booking
activation, never roll back to an image that ignores active booking guards.
Pause dispatch and reconcile pending/unknown submissions before changing images.

## Evidence

Tests: tests/test_carrier_booking.py (SQLite and disposable PostgreSQL API/service
cases); tests/verify_booking_worker.py (real Redis/Celery, provider acceptance,
duplicate drain, forced worker loss before local success commit and reconciliation).
The existing Ubuntu operational acceptance workflow includes these tests and
retains the seven-agent recovery and 500 warehouse lifecycle matrix gates.
