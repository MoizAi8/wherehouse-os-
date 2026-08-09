from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fulfillment.api import auth, chat
from fulfillment.api.v1 import (
    agents,
    analytics,
    carriers,
    fulfillment_centers,
    integrations,
    orders,
    settings as settings_router,
    shipments,
    webhooks,
    ws,
)
from fulfillment.config import settings
from fulfillment.database import init_db
from fulfillment.rate_limit import RateLimitMiddleware
from fulfillment.vector_store import init_collections

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("fulfillment")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    await init_collections()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RateLimitMiddleware)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(orders.router, prefix="/api/v1/orders", tags=["orders"])
app.include_router(shipments.router, prefix="/api/v1/shipments", tags=["shipments"])
app.include_router(carriers.router, prefix="/api/v1/carriers", tags=["carriers"])
app.include_router(agents.router, prefix="/api/v1/agents", tags=["agents"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["analytics"])
app.include_router(settings_router.router, prefix="/api/v1/settings", tags=["settings"])
app.include_router(fulfillment_centers.router, prefix="/api/v1/fulfillment-centers", tags=["fulfillment-centers"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["webhooks"])
app.include_router(integrations.router, prefix="/api/v1/integrations", tags=["integrations"])
app.include_router(ws.router, prefix="/api/v1/ws", tags=["websocket"])


@app.get("/health")
async def health() -> dict[str, str | bool]:
    db_ok = False
    try:
        from sqlalchemy import text

        from fulfillment.database import async_session_factory

        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:  # pragma: no cover
        logger.warning("Health check DB probe failed: %s", exc)
    return {"status": "ok", "version": settings.app_version, "postgres": db_ok}
