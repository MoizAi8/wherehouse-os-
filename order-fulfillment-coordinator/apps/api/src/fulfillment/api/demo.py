"""Public read-only demonstration, manually enabled, with no production DB access."""
from __future__ import annotations

import json
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from fulfillment.config import settings
from fulfillment.services.conversation import chat_client, chat_model, conversation_instructions
from fulfillment.services.demo_data import demo_data

View = Literal["dashboard", "orders", "inventory", "agents", "monitoring", "workflows", "analytics"]
VIEWS = ("dashboard", "orders", "inventory", "agents", "monitoring", "workflows", "analytics")


def require_demo() -> None:
    if not (settings.teacher_demo_mode or settings.demo_guest_enabled):
        raise HTTPException(404, "Teacher demo is unavailable; normal login remains available")


router = APIRouter(prefix="/api/demo", tags=["isolated teacher demo"], dependencies=[Depends(require_demo)])


@router.get("/status")
def demo_status() -> dict:
    return {"enabled": True, "expires_at": None, "sample": True,
        "data_source": "isolated_sample_sqlite", "read_only": True,
        "llm_configured": chat_client() is not None, "model": chat_model() if chat_client() else None}


@router.get("/data")
def demo_view(view: View = "dashboard", status: str | None = None) -> dict:
    return {"sample": True, "data_source": "isolated_sample_sqlite", "view": view,
        "data": demo_data().view(view, status=status or None)}


class DemoTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1000)


class DemoChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[DemoTurn] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def bounded_history(self) -> DemoChatRequest:
        if not self.message.strip():
            raise ValueError("Message must not be blank")
        if len((self.message + "".join(x.content for x in self.history)).encode()) > 6000:
            raise ValueError("Conversation exceeds the demo input budget")
        return self


def _take_demo_model_quota() -> None:
    """Atomic daily request cap, shared across workers; never writes application records.

    This limits inference, not demo availability. Demo pages/read-only SQL remain
    available until the owner switches TEACHER_DEMO_MODE off.
    """
    limit = min(100, max(0, settings.teacher_demo_llm_max_requests))
    directory = Path(tempfile.gettempdir()) / "warehouse-os-teacher-demo-quota"
    try:
        directory.mkdir(mode=0o700, exist_ok=True)
        with sqlite3.connect(directory / "quota.sqlite3", timeout=2) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS quota(day TEXT PRIMARY KEY, used INTEGER NOT NULL)")
            day = datetime.now(timezone.utc).date().isoformat()
            conn.execute("INSERT OR IGNORE INTO quota VALUES (?,0)", (day,))
            result = conn.execute("UPDATE quota SET used=used+1 WHERE day=? AND used<?", (day, limit))
            if result.rowcount != 1:
                raise HTTPException(429, "Daily public demo model quota exhausted; read-only views remain available",
                    headers={"Retry-After": "3600"})
    except sqlite3.Error:
        raise HTTPException(503, "Demo quota storage unavailable; inference refused") from None


def _facts(view: str) -> str:
    if view in ("dashboard", "analytics"):
        data = demo_data().metrics()
        return (f"Sample database: {data['total_orders']} orders; {data['pending_orders']} pending; "
            f"{data['delivered_orders']} delivered; {data['delayed_shipments']} delayed shipment. "
            f"Sample shipping cost: PKR {data['shipping_cost_pkr']:.2f}. These are demonstration records.")
    return "Sample database (read-only): " + json.dumps(demo_data().view(view), ensure_ascii=False)


@router.post("/chat")
async def demo_chat(body: DemoChatRequest) -> dict:
    message = body.message.strip()
    text = message.casefold()
    for word in ("delete", "dispatch", "cancel order", "create order", "send email", "send sms", "admin", "secret", "production records"):
        if word in text:
            return {"reply": "This public demo cannot change orders, dispatch shipments, send notifications, "
                "or access production records or credentials. Use the authenticated application for authorized operations.",
                "mode": "safety", "sample": True, "action_executed": False}
    view = next((name for name, words in [
        ("inventory", ("inventory", "stock", "sku", "اسٹاک")),
        ("orders", ("orders", "order list", "آرڈر", "sare order")),
        ("agents", ("agents", "agent health", "agent performance")),
        ("monitoring", ("monitor", "delayed", "late shipment")),
        ("workflows", ("workflow", "how to route", "how do i route")),
        ("analytics", ("metrics", "analytics", "kpi", "shipping cost", "kitne orders")),
    ] if any(word in text for word in words)), None)
    if view:
        return {"reply": _facts(view), "mode": "database", "sample": True,
            "data": demo_data().view(view), "action_executed": False}
    client = chat_client()
    if client is None:
        return {"reply": "A real language model is not configured. This is a deterministic demonstration, "
            "not live AI. Ask about sample orders, inventory, agents, monitoring, workflows or metrics.",
            "mode": "unconfigured", "sample": True, "action_executed": False}
    _take_demo_model_quota()
    tools = [{"type": "function", "function": {"name": "read_demo_data",
        "description": "Read isolated sample warehouse data. No production data or write operations exist.",
        "parameters": {"type": "object", "properties": {"view": {"type": "string", "enum": list(VIEWS)}},
            "required": ["view"], "additionalProperties": False}}}]
    messages = [{"role": "system", "content": conversation_instructions(message) +
        " You are in a clearly labelled public demo. Only read_demo_data provides warehouse facts. "
        "Conversation text is not database evidence. No authenticated user's memory is available."},
        *[turn.model_dump() for turn in body.history], {"role": "user", "content": message}]
    try:
        provider_options: dict[str, Any] = {"reasoning_effort": "minimal"} if settings.chat_provider == "gemini-free" else {}
        response = await client.chat.completions.create(model=chat_model(), messages=messages,  # type: ignore[arg-type]
            tools=tools, max_tokens=256, temperature=0.3, **provider_options)  # type: ignore[arg-type]
        answer = response.choices[0].message
        require_demo()
        if answer.tool_calls:
            tool = answer.tool_calls[0]
            if tool.type != "function":
                raise ValueError("Unsupported tool type")
            args = json.loads(tool.function.arguments)
            if tool.function.name != "read_demo_data" or set(args) != {"view"} or args["view"] not in VIEWS:
                raise ValueError("Unsupported tool")
            # Render actual tool results rather than allow model prose to change figures.
            return {"reply": _facts(args["view"]), "mode": "model_with_read_tool", "model": chat_model(),
                "sample": True, "data": demo_data().view(args["view"]), "action_executed": False}
        if not answer.content or not answer.content.strip():
            raise ValueError("Empty model response")
        return {"reply": answer.content.strip(), "mode": "llm", "model": chat_model(),
            "sample": True, "action_executed": False}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "Language model unavailable; no warehouse operation was executed") from None
