from __future__ import annotations

import asyncio
import logging

from celery import Celery
from celery.signals import worker_ready, worker_shutdown, task_failure, task_retry

from fulfillment.config import settings
from fulfillment.database import async_session_factory
from fulfillment.agents.orchestrator import FulfillmentOrchestrator
from fulfillment.logging_config import log_agent_event, setup_logging

logger = logging.getLogger(__name__)

# Configure Celery for production reliability
celery_app = Celery(
    "fulfillment",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["fulfillment.tasks.monitor_cycle", "fulfillment.tasks.health"],
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    result_compression="gzip",

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Task execution
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_acks_on_failure_or_timeout=True,

    # Retry policy
    task_autoretry_for=(Exception,),
    task_retry_backoff=True,
    task_retry_backoff_max=600,
    task_retry_jitter=True,

    # Result backend
    result_expires=3600,
    result_extended=True,

    # Worker
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=False,

    # Beat schedule
    beat_schedule={
        "monitor-cycle-every-15-min": {
            "task": "fulfillment.tasks.monitor_cycle.run_monitor_cycle",
            "schedule": settings.shipment_poll_interval_seconds,
            "options": {"queue": "monitoring"},
        },
    },

    # Task routing
    task_routes={
        "fulfillment.tasks.monitor_cycle.*": {"queue": "monitoring"},
        "fulfillment.tasks.health.*": {"queue": "health"},
    },

    # Monitoring
    task_send_sent_event=True,
    worker_send_task_events=True,
)

# Set up structured logging in workers
@worker_ready.connect
def on_worker_ready(**kwargs):
    setup_logging()
    logger.info("Celery worker ready: %s", kwargs.get("sender"))

@worker_shutdown.connect
def on_worker_shutdown(**kwargs):
    logger.info("Celery worker shutting down: %s", kwargs.get("sender"))

@task_failure.connect
def on_task_failure(sender=None, exception=None, **kwargs):
    logger.error("Task %s failed: %s", sender.name if sender else "unknown", exception)

@task_retry.connect
def on_task_retry(sender=None, reason=None, **kwargs):
    logger.warning("Task %s retry: %s", sender.name if sender else "unknown", reason)


async def _run_monitor_cycle_async() -> dict:
    """Async implementation of monitor cycle with proper error handling."""
    async with async_session_factory() as db:
        orchestrator = FulfillmentOrchestrator(db)
        result = await orchestrator.run_monitor_cycle()
        await db.commit()
        return result.model_dump()


@celery_app.task(
    bind=True,
    max_retries=5,
    acks_late=True,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    name="fulfillment.tasks.monitor_cycle.run_monitor_cycle",
)
def run_monitor_cycle(self) -> dict:
    """
    Run the monitor cycle with automatic retries and proper error handling.
    Uses asyncio in a thread-safe manner for production reliability.
    """
    log_agent_event("FulfillmentOrchestrator", "cycle_start", entity_id=None, details={})
    logger.info("Starting monitor cycle task (attempt %d)", self.request.retries + 1)

    try:
        # Create new event loop for this task execution
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_run_monitor_cycle_async())
        finally:
            # Clean up pending tasks
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()

        log_agent_event(
            "FulfillmentOrchestrator",
            "cycle_complete",
            entity_id=result.get("cycle_id"),
            details={
                "shipments_checked": result.get("shipments_checked", 0),
                "delays_detected": result.get("delays_detected", 0),
                "reroutes_initiated": result.get("reroutes_initiated", 0),
            }
        )

        logger.info(
            "Monitor cycle complete: %d shipments checked, %d delays detected, %d reroutes",
            result.get("shipments_checked", 0),
            result.get("delays_detected", 0),
            result.get("reroutes_initiated", 0),
        )
        return result

    except Exception as exc:
        logger.error("Monitor cycle failed: %s", exc, exc_info=True)
        log_agent_event(
            "FulfillmentOrchestrator",
            "cycle_failed",
            entity_id=None,
            details={"error": str(exc), "attempt": self.request.retries + 1},
            level=logging.ERROR
        )
        # Re-raise to trigger Celery's automatic retry
        raise
