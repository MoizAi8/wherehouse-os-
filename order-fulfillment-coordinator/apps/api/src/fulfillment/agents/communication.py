from __future__ import annotations

import asyncio
import logging
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from fulfillment.config import settings
from fulfillment.models.notification import Notification
from fulfillment.models.order import Order
from fulfillment.models.shipment import Shipment

logger = logging.getLogger(__name__)
PROVIDER_TIMEOUT_SECONDS = 10


class CommunicationAgent:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def send_delay_alert(self, shipment: Shipment, delay_reason: str) -> dict | None:
        try:
            order: Order | None = shipment.order
        except Exception:
            from sqlalchemy import select as sel

            result = await self.db.execute(sel(Order).where(Order.id == shipment.order_id))
            order = result.scalar_one_or_none()
            if order is None:
                logger.error("Order not found for shipment %s", shipment.id)
                return None

        if order is None:
            logger.error("Order not available for shipment %s", shipment.id)
            return None

        email_body = (
            f"Your shipment #{shipment.tracking_number} via {shipment.carrier_name} "
            f"has been delayed. Reason: {delay_reason}. "
            f"New status: {shipment.status.value}. "
            f"We are working to resolve this."
        )
        sms_body = f"Shipment {shipment.tracking_number} delayed: {delay_reason}"

        results = []

        if order.customer_email:
            email_result = await self._send_email(
                recipient=order.customer_email,
                subject=f"Shipment Delay - {shipment.tracking_number}",
                body=email_body,
                shipment=shipment,
            )
            if email_result:
                results.append(email_result)

        if order.customer_phone:
            sms_result = await self._send_sms(
                recipient=order.customer_phone,
                body=sms_body,
                shipment=shipment,
            )
            if sms_result:
                results.append(sms_result)

        if not results:
            return None

        return {
            "shipment_id": shipment.id,
            "notifications_sent": sum(result["status"] == "sent" for result in results),
            "channels": results,
        }

    async def _send_email(
        self,
        recipient: str,
        subject: str,
        body: str,
        shipment: Shipment,
    ) -> dict | None:
        if not settings.sendgrid_api_key:
            logger.info("SendGrid not configured for shipment %s", shipment.id)
            notif = self._create_notification(
                order_id=shipment.order_id,
                shipment_id=shipment.id,
                recipient=recipient,
                channel="email",
                subject=subject,
                body=body,
                status="skipped",
            )
            return {"channel": "email", "status": "skipped", "notification_id": notif.id}

        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail, Email, To, Content

            sg = sendgrid.SendGridAPIClient(api_key=settings.sendgrid_api_key)
            mail = Mail(
                from_email=Email(settings.sendgrid_from_email),
                to_emails=To(recipient),
                subject=subject,
                plain_text_content=Content("text/plain", body),
            )
            response = await asyncio.to_thread(
                sg.client.mail.send.post, request_body=mail.get(), timeout=PROVIDER_TIMEOUT_SECONDS,
            )
            if not 200 <= response.status_code < 300:
                raise RuntimeError("SendGrid rejected the notification")
            provider_id = str(response.status_code)
            notif = self._create_notification(
                order_id=shipment.order_id,
                shipment_id=shipment.id,
                recipient=recipient,
                channel="email",
                subject=subject,
                body=body,
                provider_id=provider_id,
            )
            return {"channel": "email", "status": "sent", "provider_id": provider_id, "notification_id": notif.id}
        except Exception as exc:
            logger.error("SendGrid failed for shipment %s (%s)", shipment.id, type(exc).__name__)
            notif = self._create_notification(
                order_id=shipment.order_id,
                shipment_id=shipment.id,
                recipient=recipient,
                channel="email",
                subject=subject,
                body=body,
                status="failed",
            )
            return {"channel": "email", "status": "failed", "notification_id": notif.id}

    async def _send_sms(
        self,
        recipient: str,
        body: str,
        shipment: Shipment,
    ) -> dict | None:
        if not settings.twilio_account_sid or not settings.twilio_auth_token:
            logger.info("Twilio not configured for shipment %s", shipment.id)
            notif = self._create_notification(
                order_id=shipment.order_id,
                shipment_id=shipment.id,
                recipient=recipient,
                channel="sms",
                body=body,
                status="skipped",
            )
            return {"channel": "sms", "status": "skipped", "notification_id": notif.id}

        try:
            from twilio.http.http_client import TwilioHttpClient
            from twilio.rest import Client

            client = Client(
                settings.twilio_account_sid, settings.twilio_auth_token,
                http_client=TwilioHttpClient(timeout=PROVIDER_TIMEOUT_SECONDS),
            )
            message = await asyncio.to_thread(
                client.messages.create,
                body=body,
                from_=settings.twilio_phone_number,
                to=recipient,
            )
            if message.status in {"failed", "undelivered", "canceled"} or not message.sid:
                raise RuntimeError("Twilio rejected the notification")
            notif = self._create_notification(
                order_id=shipment.order_id,
                shipment_id=shipment.id,
                recipient=recipient,
                channel="sms",
                body=body,
                provider_id=message.sid,
            )
            return {"channel": "sms", "status": "sent", "provider_id": message.sid, "notification_id": notif.id}
        except Exception as exc:
            logger.error("Twilio failed for shipment %s (%s)", shipment.id, type(exc).__name__)
            notif = self._create_notification(
                order_id=shipment.order_id,
                shipment_id=shipment.id,
                recipient=recipient,
                channel="sms",
                body=body,
                status="failed",
            )
            return {"channel": "sms", "status": "failed", "notification_id": notif.id}

    def _create_notification(
        self,
        order_id: str | None,
        shipment_id: str | None,
        recipient: str,
        channel: str,
        body: str,
        subject: str | None = None,
        status: str = "sent",
        provider_id: str | None = None,
    ) -> Notification:
        notif = Notification(
            id=str(uuid4()),
            order_id=order_id,
            shipment_id=shipment_id,
            recipient=recipient,
            channel=channel,
            subject=subject,
            body=body,
            status=status,
            provider_message_id=provider_id,
        )
        self.db.add(notif)
        return notif
