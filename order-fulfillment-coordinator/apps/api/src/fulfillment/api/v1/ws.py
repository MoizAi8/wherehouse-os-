from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from fulfillment.config import settings
from fulfillment.security import decode_access_token

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, ws: WebSocket, channel: str = "shipments") -> None:
        await ws.accept()
        self._connections.setdefault(channel, set()).add(ws)

    def disconnect(self, ws: WebSocket, channel: str = "shipments") -> None:
        self._connections.get(channel, set()).discard(ws)

    async def broadcast(self, channel: str, message: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in self._connections.get(channel, set()):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.get(channel, set()).discard(ws)

    @property
    def active_connections(self) -> int:
        return sum(len(v) for v in self._connections.values())


manager = ConnectionManager()


async def _authenticate(ws: WebSocket) -> bool:
    """Validate JWT from query param and reject cross-origin requests."""
    origin = ws.headers.get("origin")
    if origin is None:
        # Browsers always send Origin; a missing header in production is
        # rejected (fail closed). Non-browser clients are only allowed in debug.
        if not settings.debug:
            await ws.close(code=4403, reason="origin_missing")
            return False
    else:
        allowed = settings.cors_origins
        if allowed and "*" not in allowed and origin.rstrip("/") not in {o.rstrip("/") for o in allowed}:
            await ws.close(code=4403, reason="origin_not_allowed")
            return False
    token = ws.query_params.get("token")
    payload = decode_access_token(token) if token else None
    if payload is None:
        await ws.close(code=4401, reason="unauthorized")
        return False
    return True


@router.websocket("/shipments")
async def websocket_shipments(ws: WebSocket) -> None:
    if not await _authenticate(ws):
        return
    await manager.connect(ws, channel="shipments")
    try:
        while True:
            data = await ws.receive_text()
            try:
                parsed = json.loads(data)
                if parsed.get("action") == "ping":
                    await ws.send_json({"action": "pong"})
            except json.JSONDecodeError:
                await ws.send_json({"error": "Invalid JSON"})
    except WebSocketDisconnect:
        manager.disconnect(ws, channel="shipments")
    except Exception:
        manager.disconnect(ws, channel="shipments")


@router.websocket("/shipments/stream")
async def websocket_shipment_stream(ws: WebSocket) -> None:
    if not await _authenticate(ws):
        return
    await manager.connect(ws, channel="shipments")
    try:
        while True:
            await asyncio.sleep(5)
            try:
                await ws.send_json({"type": "heartbeat", "timestamp": asyncio.get_event_loop().time()})
            except Exception:
                break
    except WebSocketDisconnect:
        manager.disconnect(ws, channel="shipments")
    except Exception:
        manager.disconnect(ws, channel="shipments")


async def broadcast_shipment_update(shipment_data: dict[str, Any]) -> None:
    await manager.broadcast("shipments", shipment_data)
