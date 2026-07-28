from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from uuid import uuid4

from sqlalchemy import select

from fulfillment.config import settings
from fulfillment.database import init_db, async_session_factory
from fulfillment.models.integration import IntegrationConnection
from fulfillment.vector_store import init_collections
from fulfillment.api import auth, chat

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("fulfillment")
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


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    await init_collections()

    if settings.odoo_url:
        async with async_session_factory() as session:
            result = await session.execute(
                select(IntegrationConnection).where(
                    IntegrationConnection.provider == "odoo",
                    IntegrationConnection.base_url == settings.odoo_url.rstrip("/"),
                )
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                conn = IntegrationConnection(
                    id=str(uuid4()),
                    provider="odoo",
                    label=f"Odoo — {settings.odoo_url}",
                    base_url=settings.odoo_url.rstrip("/"),
                    db_name=settings.odoo_db or "",
                    username=settings.odoo_username or "",
                    api_key=settings.odoo_password or "",
                    is_connected=False,
                    sync_status="configured",
                )
                session.add(conn)
                await session.flush()
                logger.info("Odoo connection created from env vars: %s", settings.odoo_url)
            else:
                existing.base_url = settings.odoo_url.rstrip("/")
                existing.db_name = settings.odoo_db or existing.db_name or ""
                existing.username = settings.odoo_username or existing.username or ""
                existing.api_key = settings.odoo_password or existing.api_key or ""
                await session.flush()

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
async def health() -> dict[str, str]:
    return {"status": "ok", "version": settings.app_version}
