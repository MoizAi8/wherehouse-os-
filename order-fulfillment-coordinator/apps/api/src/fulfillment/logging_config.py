from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

from fulfillment.config import settings

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_request_context: ContextVar[dict[str, Any]] = ContextVar("request_context", default={})


def get_correlation_id() -> str:
    cid = _correlation_id.get()
    if cid is None:
        cid = str(uuid.uuid4())[:8]
        _correlation_id.set(cid)
    return cid


def set_correlation_id(cid: str | None) -> None:
    _correlation_id.set(cid)


def set_request_context(ctx: dict[str, Any]) -> None:
    _request_context.set(ctx)


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": get_correlation_id(),
        }

        if record.exc_info:
            base["exception"] = self.formatException(record.exc_info)

        extra = {k: v for k, v in record.__dict__.items() if k not in {
            "name", "msg", "args", "created", "filename", "funcName",
            "levelname", "levelno", "lineno", "module", "msecs",
            "message", "msg", "pathname", "process", "processName",
            "relativeCreated", "thread", "threadName", "exc_info",
            "exc_text", "stack_info", "asctime"
        }}
        if extra:
            base["extra"] = json.dumps(extra, default=str)

        request_ctx = _request_context.get()
        if request_ctx:
            base["request"] = json.dumps(request_ctx, default=str)

        return json.dumps(base, default=str)


class HumanReadableFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        corr = get_correlation_id()
        prefix = f"[{corr}] " if corr else ""
        msg = super().format(record)
        return f"{prefix}{msg}"


def setup_logging() -> None:
    log_level = logging.DEBUG if settings.debug else logging.INFO
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    if settings.debug:
        handler.setFormatter(HumanReadableFormatter(
            fmt="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            datefmt="%H:%M:%S",
        ))
    else:
        handler.setFormatter(StructuredFormatter())

    root_logger.addHandler(handler)

    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def log_agent_event(
    agent_name: str,
    event_type: str,
    entity_id: str | None = None,
    details: dict | None = None,
    level: int = logging.INFO,
    risk_score: float | None = None,
) -> None:
    logger = logging.getLogger(f"fulfillment.agents.{agent_name.lower()}")
    extra = {
        "agent_name": agent_name,
        "event_type": event_type,
        "entity_id": entity_id,
        "details": details or {},
    }
    if risk_score is not None:
        extra["risk_score"] = str(risk_score)
    logger.log(level, f"{agent_name} | {event_type} | entity={entity_id}", extra=extra)


def log_api_request(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    user_id: str | None = None,
) -> None:
    logger = logging.getLogger("fulfillment.api")
    extra = {
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
    }
    if user_id:
        extra["user_id"] = user_id
    level = logging.WARNING if status_code >= 400 else logging.INFO
    logger.log(level, f"{method} {path} -> {status_code} ({duration_ms:.1f}ms)", extra=extra)


def log_db_query(query: str, duration_ms: float, rows_affected: int | None = None) -> None:
    logger = logging.getLogger("fulfillment.db")
    extra = {
        "query": query[:200],
        "duration_ms": round(duration_ms, 2),
    }
    if rows_affected is not None:
        extra["rows_affected"] = rows_affected
    level = logging.WARNING if duration_ms > 1000 else logging.DEBUG
    logger.log(level, f"DB query ({duration_ms:.1f}ms)", extra=extra)


def log_external_call(service: str, operation: str, success: bool, duration_ms: float, error: str | None = None) -> None:
    logger = logging.getLogger(f"fulfillment.external.{service}")
    extra = {
        "service": service,
        "operation": operation,
        "success": success,
        "duration_ms": round(duration_ms, 2),
    }
    if error:
        extra["error"] = error
    level = logging.ERROR if not success else logging.INFO
    logger.log(level, f"{service}.{operation} -> {'OK' if success else 'FAILED'} ({duration_ms:.1f}ms)", extra=extra)


class Timer:
    def __init__(self, name: str):
        self.name = name
        self.start = time.perf_counter()

    def __enter__(self) -> "Timer":
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self.start) * 1000