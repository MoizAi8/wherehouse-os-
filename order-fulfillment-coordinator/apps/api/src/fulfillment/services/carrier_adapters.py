"""Carrier boundary. Only the explicitly enabled sandbox has an implementation.

Live adapters must verify idempotency, error semantics, authentication and lookup
against official provider contracts before being registered here. No carrier
names imply API support. The warehouse workflow depends only on this protocol.
"""

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Protocol

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fulfillment.config import settings
from fulfillment.models.carrier_booking import SandboxCarrierReceipt


class CarrierUnavailable(Exception):
    pass


class CarrierRejected(Exception):
    pass


class CarrierRetryable(Exception):
    """Provider explicitly confirms that no booking was accepted."""


class CarrierAmbiguous(Exception):
    """Provider may have accepted the request; reconcile before resubmission."""


@dataclass(frozen=True)
class BookingReceipt:
    provider_reference: str
    tracking_number: str
    sandbox: bool


class CarrierAdapter(Protocol):
    sandbox: bool
    idempotent_submission: bool

    async def book(self, key: str, payload: dict, attempt: int) -> BookingReceipt: ...
    async def lookup(self, key: str, payload: dict) -> BookingReceipt | None: ...


def payload_hash(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class SandboxCarrier:
    sandbox = True
    idempotent_submission = True

    def __init__(self, sessions: async_sessionmaker[AsyncSession]):
        self.sessions = sessions

    async def lookup(self, key: str, payload: dict) -> BookingReceipt | None:
        async with self.sessions() as db:
            row = await db.get(SandboxCarrierReceipt, key)
            if row is None:
                return None
            if row.request_hash != payload_hash(payload):
                raise CarrierRejected("idempotency_conflict")
            return BookingReceipt(**row.receipt)

    async def book(self, key: str, payload: dict, attempt: int) -> BookingReceipt:
        previous = await self.lookup(key, payload)
        if previous:
            return previous
        scenario = payload["options"].get("sandbox_scenario", "accepted")
        if scenario == "rejected":
            raise CarrierRejected("sandbox_rejected")
        if scenario == "unavailable" or (scenario == "retry_once" and attempt == 1):
            raise CarrierRetryable("sandbox_unavailable")
        receipt = BookingReceipt("SANDBOX-BOOKING-" + key, "SANDBOX-" + key.replace("-", ""), True)
        async with self.sessions.begin() as db:
            insert = pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
            await db.execute(
                insert(SandboxCarrierReceipt)
                .values(
                    idempotency_key=key,
                    request_hash=payload_hash(payload),
                    receipt=asdict(receipt),
                )
                .on_conflict_do_nothing(index_elements=[SandboxCarrierReceipt.idempotency_key])
            )
        if scenario == "ambiguous":
            raise CarrierAmbiguous("sandbox_response_lost")
        persisted = await self.lookup(key, payload)
        assert persisted is not None
        return persisted


def get_carrier_adapter(
    provider: str, sessions: async_sessionmaker[AsyncSession]
) -> CarrierAdapter:
    if provider == "sandbox" and settings.carrier_sandbox_enabled:
        return SandboxCarrier(sessions)
    raise CarrierUnavailable("Carrier adapter is not activated")
