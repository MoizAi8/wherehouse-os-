"""Scoped guest sessions and original UI DTOs. Never access the production database."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import secrets
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError

from fulfillment.api.demo import DemoChatRequest, demo_chat
from fulfillment.config import settings
from fulfillment.services.demo_data import demo_data


def require_guest_mode() -> None:
    if not settings.demo_guest_enabled:
        raise HTTPException(404, "Guest access is disabled")


router = APIRouter(prefix="/api/demo/guest", tags=["restricted guest"],
                   dependencies=[Depends(require_guest_mode)])
bearer = HTTPBearer(auto_error=False)
PROFILE = {"id": "demo-guest", "name": "Demo Guest · read-only samples",
           "email": "guest@example.invalid", "role": "VIEWER", "must_change_password": False}


@router.get("/status")
def guest_status() -> dict:
    return {"enabled": True, "expires_at": None, "read_only": True}


@router.post("/session")
def guest_session() -> dict:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=1)
    token = jwt.encode({"sub": secrets.token_urlsafe(24), "typ": "demo_guest",
                        "aud": "isolated-demo", "iat": now, "exp": expires},
                       settings.jwt_secret, algorithm=settings.jwt_algorithm)
    # Token lifetime is renewable; the owner-controlled mode never expires.
    return {"user": PROFILE, "demoGuest": True, "accessToken": token,
            "expires": expires.isoformat()}


def require_guest(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> dict:
    if credentials is not None:
        try:
            payload = jwt.decode(credentials.credentials, settings.jwt_secret,
                                 algorithms=[settings.jwt_algorithm], audience="isolated-demo",
                                 options={"require": ["sub", "iat", "exp", "aud"]})
            if payload.get("typ") == "demo_guest":
                return payload
        except InvalidTokenError:
            pass
    raise HTTPException(401, "Restricted guest session required")


def original_ui_data(path: str, status: str | None = None, limit: int = 100) -> object:
    """Explicit allowlist of DTOs built exclusively from the isolated sample DB."""
    data = demo_data()
    metrics = data.metrics()
    stamp = "2026-11-01T10:00:00Z"
    orders = [{"id": row["id"], "external_order_id": row["id"],
               "customer_email": f"sample-{row['id'].lower()}@example.invalid",
               "customer_phone": None, "shipping_address": "Sample address",
               "shipping_zip": "00000", "shipping_city": row["city"], "shipping_state": "Sample",
               "shipping_country": "PK", "items_json": "[]", "total_weight_kg": row["weight_kg"],
               "status": row["status"], "fulfillment_center_id": None, "carrier_id": None,
               "tracking_number": None, "estimated_delivery": None, "shipping_cost": row["shipping_cost"],
               "notes": "Isolated read-only sample", "created_at": stamp, "updated_at": stamp}
              for row in data.orders(status=status)]
    if path == "/api/v1/orders":
        return {"orders": orders[:limit], "total": len(orders)}
    if path == "/api/auth/me":
        return PROFILE
    if path == "/api/v1/analytics/kpis":
        return {"total_orders": metrics["total_orders"], "orders_shipped": 2,
                "orders_delivered": metrics["delivered_orders"], "orders_delayed": metrics["delayed_shipments"],
                "on_time_delivery_rate": 100, "avg_delivery_time_days": 2,
                "total_shipping_cost": metrics["shipping_cost_pkr"],
                "avg_shipping_cost": round(metrics["shipping_cost_pkr"] / 8, 2),
                "failed_delivery_rate": 0, "period_start": stamp, "period_end": stamp}
    if path == "/api/v1/analytics/carriers":
        return [{"carrier_name": row["carrier"], "total_shipments": row["count"],
                 "on_time_shipments": row["count"] - row["delays"], "delayed_shipments": row["delays"],
                 "on_time_rate": round(100 * (row["count"] - row["delays"]) / row["count"], 1),
                 "avg_cost": row["cost"] / row["count"], "total_cost": row["cost"], "avg_delivery_days": 2}
                for row in data.query("SELECT carrier,count(*) AS count,sum(delayed) AS delays,"
                                      "sum(shipping_cost) AS cost FROM orders WHERE carrier!='Unassigned' GROUP BY carrier")]
    if path == "/api/v1/agents/status":
        return {"cycle_id": "sample-cycle", "shipments_checked": 2, "delays_detected": 1,
                "reroutes_initiated": 0, "notifications_sent": 0, "anomalies_found": 0,
                "events": [], "completed_at": stamp, "recorded": True}
    if path == "/api/v1/shipments":
        return [{"id": "SAMPLE-" + row["id"], "order_id": row["id"], "carrier_name": row["carrier"],
                 "tracking_number": "SAMPLE-" + row["id"], "status": row["status"],
                 "estimated_delivery": None, "actual_delivery": stamp if row["status"] == "delivered" else None,
                 "origin_zip": "00000", "destination_zip": "00000", "weight_kg": row["weight_kg"],
                 "shipping_cost": row["shipping_cost"], "carrier_status_detail": "Sample record",
                 "is_delayed": bool(row["delayed"]), "delay_reason": "Sample delay" if row["delayed"] else None,
                 "created_at": stamp, "updated_at": stamp}
                for row in data.orders(status=status) if row["carrier"] != "Unassigned"]
    if path == "/api/v1/fulfillment-centers":
        return [{"id": "sample-lahore", "name": "Sample Lahore Center", "address": "Sample address",
                 "zip_code": "00000", "city": "Lahore", "state": "Sample", "country": "PK",
                 "latitude": None, "longitude": None, "is_active": True, "capacity_pct": 25,
                 "max_daily_orders": 100, "current_daily_orders": 25}]
    if path == "/api/v1/integrations/connections":
        return []  # Never expose real connection URLs, usernames or credentials.
    if path == "/api/v1/settings":
        return {"appName": "Warehouse OS", "theme": "dark", "apiEndpoint": "", "webhookUrl": ""}
    raise HTTPException(403, "Guest access is read-only; this production operation requires owner login")


@router.get("/data", dependencies=[Depends(require_guest)])
def guest_data(path: str, status: str | None = None, limit: int = Query(100, ge=1, le=1000)) -> object:
    return original_ui_data(path, status, limit)


@router.post("/chat", dependencies=[Depends(require_guest)])
async def guest_chat(body: DemoChatRequest) -> dict:
    return await demo_chat(body)


@router.get("/history", dependencies=[Depends(require_guest)])
def guest_history() -> dict:
    # No public/shared chat history. A tab supplies bounded conversation turns.
    return {"messages": []}


@router.api_route("/data", methods=["POST", "PUT", "PATCH", "DELETE"], dependencies=[Depends(require_guest)])
def reject_guest_write() -> None:
    raise HTTPException(403, "Guest access is read-only; sign in as an owner for privileged operations")
