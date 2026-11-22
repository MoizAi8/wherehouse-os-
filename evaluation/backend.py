import asyncio
import os
import re

import uvicorn
from fulfillment.config import settings
from fulfillment.database import async_session_factory, engine, init_db
from fulfillment.main import app
from fulfillment.models.carrier_rate import CarrierRate
from fulfillment.models.fulfillment_center import FulfillmentCenter
from fulfillment.models.user import User, UserRole
from fulfillment.security import hash_password
from gateway import allowed
from starlette.responses import Response


async def seed():
    url = engine.url
    if (
        (url.host, url.port) != ("127.0.0.1", 55471)
        or not re.fullmatch("instructor_eval_[0-9a-f]{16}", url.database)
        or url.username != url.database
        or settings.debug
    ):
        raise RuntimeError("Instructor database isolation check failed")
    await init_db()
    async with async_session_factory.begin() as db:
        db.add(
            User(
                email="warehouse-instructor@example.com",
                name="Instructor",
                role=UserRole.OPERATOR,
                password_hash=hash_password(os.environ["EVALUATION_OPERATOR_SECRET"]),
            )
        )
        db.add(
            FulfillmentCenter(
                name="Evaluation Center",
                address="Test Street",
                city="Test",
                state="NY",
                zip_code="90211",
            )
        )
        db.add(
            CarrierRate(
                carrier_name="Sandbox Ground",
                service_name="Ground",
                origin_zip="90211",
                destination_zip="10001",
                weight_kg_min=0,
                weight_kg_max=50,
                base_rate=10,
                rate_per_kg=1,
                estimated_days_min=2,
                estimated_days_max=3,
            )
        )
    await engine.dispose()


@app.middleware("http")
async def limit(request, next_handler):
    path = request.url.path
    internal = {
        ("POST", "/api/auth/login"),
        ("POST", "/api/v1/webhooks/shipment-event"),
        ("POST", "/api/chat"),
        ("GET", "/api/chat/history"),
        ("DELETE", "/api/chat/history"),
    }
    if not allowed(request.method, path) and (request.method, path) not in internal:
        return Response(status_code=403)
    return await next_handler(request)


if __name__ == "__main__":
    asyncio.run(seed())
    uvicorn.run(app, host="127.0.0.1", port=8386, access_log=False)
