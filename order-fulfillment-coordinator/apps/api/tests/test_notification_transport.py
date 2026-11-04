import asyncio
import json
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from sendgrid import SendGridAPIClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from twilio.http.http_client import TwilioHttpClient

from fulfillment.agents.communication import CommunicationAgent, deliver_due_notifications
from fulfillment.agents import communication
from fulfillment.config import settings
from fulfillment.database import Base
from fulfillment.models.notification import Notification
from fulfillment.models.order import Order
from fulfillment.models.shipment import Shipment, ShipmentStatus


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_status", ["accepted", "rejected", "rate_limited", "ambiguous", "crash"])
async def test_notification_sdk_contract(tmp_path, monkeypatch, provider_status):
    requests = []

    class Provider(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = self.rfile.read(int(self.headers["Content-Length"])).decode()
            requests.append((self.path, self.headers["Authorization"], payload))
            email = self.path == "/v3/mail/send"
            if provider_status in {"accepted", "crash"}:
                status = 202 if email else 201
                body = {} if email else {"sid": "SM" + "1" * 32, "status": "queued"}
            elif provider_status == "rejected":
                status, body = 400, {"message": "Sandbox rejection", "code": 21614}
            else:
                status = 429 if provider_status == "rate_limited" else 503
                body = {"message": "Sandbox unavailable"}
            response = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
    server_thread = Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    endpoint = f"http://127.0.0.1:{server.server_port}"
    sendgrid_init = SendGridAPIClient.__init__
    twilio_request = TwilioHttpClient.request

    def use_local_sendgrid(self, *, api_key):
        sendgrid_init(self, api_key=api_key, host=endpoint)

    def use_local_twilio(self, method, url, *args, **kwargs):
        return twilio_request(self, method, endpoint + urlsplit(url).path, *args, **kwargs)

    monkeypatch.setattr(SendGridAPIClient, "__init__", use_local_sendgrid)
    monkeypatch.setattr(TwilioHttpClient, "request", use_local_twilio)
    monkeypatch.setattr(settings, "sendgrid_api_key", "sandbox-only")
    monkeypatch.setattr(settings, "sendgrid_from_email", "sender@example.com")
    monkeypatch.setattr(settings, "twilio_account_sid", "AC" + "1" * 32)
    monkeypatch.setattr(settings, "twilio_auth_token", "sandbox-only")
    monkeypatch.setattr(settings, "twilio_phone_number", "+12025550101")
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'notification.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions.begin() as db:
            order = Order(
                customer_email="receiver@example.com", customer_phone="+12025550102",
                shipping_address="2 Test St", shipping_zip="10001", shipping_city="New York", shipping_state="NY",
            )
            shipment = Shipment(
                id=str(uuid4()), order=order, carrier_name="Sandbox", tracking_number="TEST-100",
                status=ShipmentStatus.DELAYED, origin_zip="90210", destination_zip="10001",
            )
            db.add(shipment)
            await db.flush()
            result = await CommunicationAgent(db).send_delay_alert(shipment, "weather")
            assert result is not None
            assert result["notifications_queued"] == 2
            assert result["notifications_sent"] == 0
            assert await CommunicationAgent(db).send_delay_alert(shipment, "weather") is None
            assert requests == []
        if provider_status == "crash":
            submit = communication._submit_notice

            async def interrupt_after_provider(notice):
                await submit(notice)
                raise asyncio.CancelledError

            with monkeypatch.context() as patch:
                patch.setattr(communication, "_submit_notice", interrupt_after_provider)
                with pytest.raises(asyncio.CancelledError):
                    await deliver_due_notifications(sessions)
            async with sessions.begin() as db:
                await db.execute(update(Notification).where(Notification.status == "sending").values(
                    delivery_due_at=datetime.now(timezone.utc) - timedelta(seconds=1),
                ))
            assert await deliver_due_notifications(sessions) == 1
        else:
            assert await deliver_due_notifications(sessions) == 2
        assert await deliver_due_notifications(sessions) == 0
        async with sessions() as db:
            records = list(await db.scalars(select(Notification)))
            assert {record.channel for record in records} == {"email", "sms"}
            expected = {
                "accepted": {"sent"}, "rejected": {"failed"}, "rate_limited": {"retry"},
                "ambiguous": {"unknown"}, "crash": {"sent", "unknown"},
            }
            assert {record.status for record in records} == expected[provider_status]
        email = next(item for item in requests if item[0] == "/v3/mail/send")
        sms = next(item for item in requests if item[0].endswith("/Messages.json"))
        assert len(requests) == 2
        assert email[0] == "/v3/mail/send" and email[1] == "Bearer sandbox-only"
        assert json.loads(email[2])["personalizations"][0]["to"][0]["email"] == "receiver@example.com"
        assert sms[0].endswith("/Messages.json") and sms[1].startswith("Basic ")
        assert parse_qs(sms[2])["To"] == ["+12025550102"]
        if provider_status == "rate_limited":
            for _ in range(communication.MAX_ATTEMPTS - 1):
                async with sessions.begin() as db:
                    await db.execute(update(Notification).where(Notification.status == "retry").values(
                        delivery_due_at=datetime.now(timezone.utc) - timedelta(seconds=1),
                    ))
                assert await deliver_due_notifications(sessions) == 2
            assert await deliver_due_notifications(sessions) == 0
            async with sessions() as db:
                records = list(await db.scalars(select(Notification)))
                assert {(row.status, row.delivery_attempts) for row in records} == {("failed", communication.MAX_ATTEMPTS)}
            assert len(requests) == 2 * communication.MAX_ATTEMPTS
    finally:
        await engine.dispose()
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)
