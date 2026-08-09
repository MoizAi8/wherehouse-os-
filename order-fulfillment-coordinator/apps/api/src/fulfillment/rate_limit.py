"""Global rate limiting for public endpoints.

Implements an ASGI middleware with a simple per-client-IP token-bucket limiter.

Why middleware instead of per-route decorators?
- ``slowapi``'s ``@limiter.limit`` decorator requires each route to declare a
  ``request`` parameter, which would force signature changes on many existing
  endpoints and risk breaking FastAPI's auto-injection in our stack.
- A single middleware covers **every** public endpoint at once, satisfying the
  project rule that all public endpoints must return ``429`` with a
  ``Retry-After`` header on abuse.

Limits are configurable via settings:

- ``RATE_LIMIT_ENABLED`` -- master switch (default true in production).
- ``RATE_LIMIT_DEFAULT`` -- default limit string, e.g. ``"120/minute"``.
- ``RATE_LIMIT_AUTH`` -- tighter limit for auth endpoints, e.g. ``"10/minute"``.
- ``RATE_LIMIT_CHAT`` -- tighter limit for the chat endpoint, e.g. ``"30/minute"``.

When ``DEBUG`` or ``RATE_LIMIT_ENABLED`` is false, the middleware is a no-op so
local development and the demo login flow are not affected.
"""
from __future__ import annotations

import logging
import re
import time

from starlette.types import ASGIApp, Receive, Scope, Send

from fulfillment.config import settings

logger = logging.getLogger("fulfillment.rate_limit")

_AUTH_PATH = re.compile(r"^/api/auth/(login|register|forgot-password|reset-password|refresh)$")
_CHAT_PATH = re.compile(r"^/api/chat$")


def _parse_limit(value: str) -> tuple[int, int]:
    """Parse a ``"N/minute"`` / ``"N/second"`` / ``"N/hour"`` string into (count, window_seconds)."""
    match = re.match(r"^(\d+)/(\w+)$", value.strip())
    if not match:
        return 120, 60
    count = int(match.group(1))
    unit = match.group(2).lower()
    windows = {"second": 1, "minute": 60, "hour": 3600}
    window = windows.get(unit, 60)
    return count, window


class _Bucket:
    """Token bucket for a single client, allowing short bursts."""

    __slots__ = ("count", "window", "tokens", "timestamp")

    def __init__(self, count: int, window: int) -> None:
        self.count = count
        self.window = window
        self.tokens = float(count)
        self.timestamp = time.monotonic()

    def take(self, now: float) -> bool:
        elapsed = now - self.timestamp
        # refill proportionally to elapsed time
        self.tokens = min(self.count, self.tokens + elapsed * (self.count / self.window))
        self.timestamp = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class RateLimitMiddleware:
    """Per-IP rate limiter returning ``429`` with ``Retry-After`` on breach."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._enabled = settings.rate_limit_enabled and not settings.debug
        self._buckets: dict[str, _Bucket] = {}

    def _make_bucket(self, limit_str: str) -> _Bucket:
        return _Bucket(*_parse_limit(limit_str))

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self._enabled:
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        headers = scope.get("headers") or []
        client_ip = ""
        if scope.get("client"):
            client_ip = scope["client"][0]
        if not client_ip:
            client_ip = next(
                (v.decode() for k, v in headers if k == b"x-forwarded-for"), ""
            ).split(",")[0].strip() or "anonymous"

        now = time.monotonic()

        if _AUTH_PATH.match(path):
            key = f"auth:{client_ip}"
            limit_str = settings.rate_limit_auth
        elif _CHAT_PATH.match(path):
            key = f"chat:{client_ip}"
            limit_str = settings.rate_limit_chat
        else:
            key = f"ip:{client_ip}"
            limit_str = settings.rate_limit_default

        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = self._make_bucket(limit_str)
            self._buckets[key] = bucket

        if not bucket.take(now):
            retry_after = max(bucket.window, 1)
            logger.warning("Rate limit exceeded | ip=%s path=%s retry_after=%ds", client_ip, path, retry_after)
            await self._send_429(send, retry_after)
            return

        await self.app(scope, receive, send)

    @staticmethod
    async def _send_429(send: Send, retry_after: int) -> None:
        body = b'{"detail":"Rate limit exceeded"}'
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    (b"retry-after", str(retry_after).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
