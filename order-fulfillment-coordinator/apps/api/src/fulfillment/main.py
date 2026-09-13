from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from fulfillment.api import auth, chat
from fulfillment.api.v1 import (
    agents,
    analytics,
    carriers,
    fulfillment_centers,
    integrations,
    orders,
    shipments,
    webhooks,
    ws,
)
from fulfillment.api.v1 import settings as settings_router
from fulfillment.config import settings
from fulfillment.database import check_db_connection, engine, init_db
from fulfillment.logging_config import (
    get_correlation_id,
    log_api_request,
    set_correlation_id,
    setup_logging,
)
from fulfillment.rate_limit import RateLimitMiddleware
from fulfillment.tasks.health import async_celery_worker_health
from fulfillment.vector_store import check_qdrant_connection, init_collections

setup_logging()

logger = logging.getLogger("fulfillment")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("x-correlation-id") or get_correlation_id()
        set_correlation_id(correlation_id)

        start_time = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000

        log_api_request(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        response.headers["x-correlation-id"] = correlation_id
        return response


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings.validate_production()
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
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestLoggingMiddleware)

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
async def health() -> dict[str, object]:
    db_ok = False
    db_type = "unknown"
    try:
        db_ok = await check_db_connection()
        if db_ok:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            db_type = engine.dialect.name
    except Exception as exc:
        logger.warning("Health check DB probe failed: %s", exc)

    celery_task = asyncio.create_task(_safe_celery_health())
    qdrant_task = asyncio.create_task(_safe_qdrant_health())

    celery_health, qdrant_ok = await asyncio.gather(celery_task, qdrant_task)

    celery_connected = bool(celery_health.get("connected", False))

    status = "ok" if db_ok else "degraded"
    if db_ok and not (celery_connected and qdrant_ok):
        status = "degraded"

    return {
        "status": status,
        "version": settings.app_version,
        "database": db_type,
        "postgres": db_ok if db_type == "postgresql" else False,
        "celery": celery_connected,
        "qdrant": qdrant_ok,
        "degraded": status == "degraded",
        "backends": {
            "postgres": db_ok if db_type == "postgresql" else False,
            "celery": celery_connected,
            "qdrant": qdrant_ok,
        },
    }


async def _safe_celery_health() -> dict:
    try:
        return await async_celery_worker_health(timeout=1.0)
    except Exception as exc:
        logger.warning("Health check Celery probe failed: %s", exc)
        return {"connected": False, "detail": f"{type(exc).__name__}: {exc}"}


async def _safe_qdrant_health() -> bool:
    try:
        return await asyncio.wait_for(check_qdrant_connection(), timeout=2.0)
    except TimeoutError:
        logger.warning("Health check Qdrant probe timed out")
        return False
    except Exception as exc:
        logger.warning("Health check Qdrant probe failed: %s", exc)
        return False
