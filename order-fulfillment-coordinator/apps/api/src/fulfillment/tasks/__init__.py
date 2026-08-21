from __future__ import annotations

from fulfillment.tasks.monitor_cycle import celery_app, run_monitor_cycle
from fulfillment.tasks.health import celery_ping, celery_worker_health

__all__ = ["celery_app", "run_monitor_cycle", "celery_ping", "celery_worker_health"]


# Celery resolves `-A <module>` to `<module>.app` or `<module>.celery` by default.
# `-A fulfillment.tasks` is used in docker-compose, so expose the app under that name too.
app = celery_app
