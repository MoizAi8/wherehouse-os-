from __future__ import annotations

import asyncio
import logging

from fulfillment.tasks.monitor_cycle import celery_app

logger = logging.getLogger(__name__)

_PING_TASK = "fulfillment.tasks.health.celery_ping"


@celery_app.task(name=_PING_TASK, acks_late=True)
def celery_ping() -> str:
    """Health probe task: returns 'pong' when a worker executes it."""
    return "pong"


def celery_worker_health(timeout: float = 2.0) -> dict:
    """Check whether any Celery worker is reachable and executes tasks.

    Returns ``{"connected": bool, "detail": str}``. Never raises — the API
    health endpoint uses this to report broker/worker status (fail soft).
    """
    try:
        result = celery_app.send_task(_PING_TASK)
        raw = result.get(timeout=timeout)
        return {"connected": raw == "pong", "detail": str(raw)}
    except Exception as exc:
        logger.warning("Celery worker health probe failed: %s", exc)
        return {"connected": False, "detail": f"{type(exc).__name__}: {exc}"}


async def async_celery_worker_health(timeout: float = 2.0) -> dict:
    loop = asyncio.get_running_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, celery_worker_health, timeout),
            timeout=timeout + 1.0,
        )
    except asyncio.TimeoutError:
        return {"connected": False, "detail": "timeout"}