from __future__ import annotations

import logging
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from fulfillment.config import settings
from fulfillment.models.notification import Notification
from fulfillment.models.order import Order
from fulfillment.models.shipment import Shipment

logger = logging.getLogger(__name__)


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

        sent_count = 0
        results = []

        if order.customer_email:
            email_result = await self._send_email(
                recipient=order.customer_email,
                subject=f"Shipment Delay - {shipment.tracking_number}",
                body=email_body,
                shipment=shipment,
            )
            if email_result:
                sent_count += 1
                results.append(email_result)

        if order.customer_phone:
            sms_result = await self._send_sms(
                recipient=order.customer_phone,
                body=sms_body,
                shipment=shipment,
            )
            if sms_result:
                sent_count += 1
                results.append(sms_result)

        if sent_count == 0:
            logger.warning("No notifications sent for shipment %s", shipment.id)
            return None

        return {
            "shipment_id": shipment.id,
            "notifications_sent": sent_count,
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
            logger.info("SendGrid not configured. Email to %s: %s", recipient, subject)
            notif = self._create_notification(
                order_id=shipment.order_id,
                shipment_id=shipment.id,
                recipient=recipient,
                channel="email",
                subject=subject,
                body=body,
            )
            return {"channel": "email", "recipient": recipient, "notification_id": notif.id}

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
            response = sg.client.mail.send.post(request_body=mail.get())
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
            return {"channel": "email", "recipient": recipient, "provider_id": provider_id, "notification_id": notif.id}
        except Exception as exc:
            logger.error("SendGrid email failed to %s: %s", recipient, exc)
            notif = self._create_notification(
                order_id=shipment.order_id,
                shipment_id=shipment.id,
                recipient=recipient,
                channel="email",
                subject=subject,
                body=body,
                status="failed",
            )
            return {"channel": "email", "recipient": recipient, "error": str(exc), "notification_id": notif.id}

    async def _send_sms(
        self,
        recipient: str,
        body: str,
        shipment: Shipment,
    ) -> dict | None:
        if not settings.twilio_account_sid or not settings.twilio_auth_token:
            logger.info("Twilio not configured. SMS to %s: %s", recipient, body)
            notif = self._create_notification(
                order_id=shipment.order_id,
                shipment_id=shipment.id,
                recipient=recipient,
                channel="sms",
                body=body,
            )
            return {"channel": "sms", "recipient": recipient, "notification_id": notif.id}

        try:
            from twilio.rest import Client

            client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
            message = client.messages.create(
                body=body,
                from_=settings.twilio_phone_number,
                to=recipient,
            )
            notif = self._create_notification(
                order_id=shipment.order_id,
                shipment_id=shipment.id,
                recipient=recipient,
                channel="sms",
                body=body,
                provider_id=message.sid,
            )
            return {"channel": "sms", "recipient": recipient, "provider_id": message.sid, "notification_id": notif.id}
        except Exception as exc:
            logger.error("Twilio SMS failed to %s: %s", recipient, exc)
            notif = self._create_notification(
                order_id=shipment.order_id,
                shipment_id=shipment.id,
                recipient=recipient,
                channel="sms",
                body=body,
                status="failed",
            )
            return {"channel": "sms", "recipient": recipient, "error": str(exc), "notification_id": notif.id}

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
