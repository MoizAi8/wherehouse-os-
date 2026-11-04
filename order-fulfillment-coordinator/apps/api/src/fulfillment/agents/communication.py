from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fulfillment.config import settings
from fulfillment.models.notification import Notification
from fulfillment.models.order import Order
from fulfillment.models.shipment import Shipment

logger = logging.getLogger(__name__)
PROVIDER_TIMEOUT_SECONDS = 10
MAX_ATTEMPTS = 4


class CommunicationAgent:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def send_delay_alert(self, shipment: Shipment, delay_reason: str) -> dict | None:
        # Existing callers may supply a loaded relationship; workers load by ID.
        order = shipment.__dict__.get("order") or await self.db.get(Order, shipment.order_id)
        if order is None:
            return None
        subject = f"Shipment Delay - {shipment.tracking_number}"
        body = f"Shipment {shipment.tracking_number} via {shipment.carrier_name} is delayed: {delay_reason}"
        channels = []
        for channel, recipient, configured in (
            ("email", order.customer_email, bool(settings.sendgrid_api_key)),
            ("sms", order.customer_phone, bool(settings.twilio_account_sid and settings.twilio_auth_token)),
        ):
            if not recipient:
                continue
            key = hashlib.sha256(f"{shipment.id}:{shipment.tracking_number}:{channel}".encode()).hexdigest()
            notice_id = str(uuid4())
            status = "queued" if configured else "skipped"
            if not configured:
                self.db.add(Notification(
                    id=notice_id, order_id=order.id, shipment_id=shipment.id, channel=channel,
                    recipient=recipient, subject=subject, body=body, status=status,
                ))
            else:
                insert = pg_insert if self.db.get_bind().dialect.name == "postgresql" else sqlite_insert
                inserted = await self.db.scalar(insert(Notification).values(
                    id=notice_id, order_id=order.id, shipment_id=shipment.id, channel=channel,
                    recipient=recipient, subject=subject, body=body, status=status, delivery_key=key,
                    delivery_attempts=0, delivery_due_at=datetime.now(timezone.utc),
                ).on_conflict_do_nothing(index_elements=[Notification.delivery_key]).returning(Notification.id))
                if inserted is None:
                    continue
            channels.append({"channel": channel, "status": status, "notification_id": notice_id})
        if not channels:
            return None
        return {
            "shipment_id": shipment.id, "notifications_sent": 0,
            "notifications_queued": sum(item["status"] == "queued" for item in channels),
            "channels": channels,
        }


async def _submit_notice(notice: Notification) -> tuple[str, str | None]:
    try:
        if notice.channel == "email":
            import sendgrid
            from sendgrid.helpers.mail import Content, Email, Mail, To

            if not settings.sendgrid_api_key:
                return "failed", None
            client = sendgrid.SendGridAPIClient(api_key=settings.sendgrid_api_key)
            message = Mail(
                from_email=Email(settings.sendgrid_from_email), to_emails=To(notice.recipient),
                subject=notice.subject, plain_text_content=Content("text/plain", notice.body),
            )
            response = await asyncio.to_thread(
                client.client.mail.send.post, request_body=message.get(), timeout=PROVIDER_TIMEOUT_SECONDS,
            )
            if 200 <= response.status_code < 300:
                return "sent", response.headers.get("X-Message-Id")
            return "unknown", None

        from twilio.http.http_client import TwilioHttpClient
        from twilio.rest import Client

        if notice.channel != "sms" or not settings.twilio_account_sid or not settings.twilio_auth_token:
            return "failed", None
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token,
                        http_client=TwilioHttpClient(timeout=PROVIDER_TIMEOUT_SECONDS))
        sms = await asyncio.to_thread(
            client.messages.create, body=notice.body, from_=settings.twilio_phone_number, to=notice.recipient,
        )
        if sms.status in {"failed", "undelivered", "canceled"}:
            return "failed", sms.sid
        return ("sent", sms.sid) if sms.sid else ("unknown", None)
    except Exception as exc:
        code = getattr(exc, "status_code", None) or getattr(exc, "status", None)
        logger.warning("Provider submission for %s failed (%s, HTTP %s)", notice.id, type(exc).__name__, code)
        if code == 429:
            return "retry", None
        if isinstance(code, int) and 400 <= code < 500 and code != 408:
            return "failed", None
        return "unknown", None


async def deliver_due_notifications(sessions: async_sessionmaker[AsyncSession], limit: int = 20) -> int:
    processed = 0
    for _ in range(limit):
        now = datetime.now(timezone.utc)
        async with sessions.begin() as db:
            await db.execute(update(Notification).where(
                Notification.status == "sending", Notification.delivery_key.is_not(None),
                Notification.delivery_due_at <= now,
            ).values(status="unknown", delivery_due_at=None))
            due = select(Notification.id).where(
                Notification.status.in_(["queued", "retry"]), Notification.delivery_due_at <= now,
            ).order_by(Notification.delivery_due_at, Notification.id).limit(1)
            notice = (await db.execute(update(Notification).where(
                Notification.id == due.scalar_subquery(), Notification.status.in_(["queued", "retry"]),
            ).values(
                status="sending", delivery_due_at=now + timedelta(minutes=5),
                delivery_attempts=Notification.delivery_attempts + 1,
            ).returning(Notification))).scalar_one_or_none()
        if notice is None:
            break
        status, provider_id = await _submit_notice(notice)
        attempts = notice.delivery_attempts or 1
        if status == "retry" and attempts >= MAX_ATTEMPTS:
            status = "failed"
        next_due = datetime.now(timezone.utc) + timedelta(seconds=60 * 2 ** (attempts - 1)) if status == "retry" else None
        async with sessions.begin() as db:
            await db.execute(update(Notification).where(
                Notification.id == notice.id, Notification.status == "sending",
            ).values(status=status, provider_message_id=provider_id, delivery_due_at=next_due))
        processed += 1
    return processed
