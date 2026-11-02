from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from fulfillment.api.deps import get_current_user, get_db, require_operator_or_admin
from fulfillment.models.agent_event import AgentEvent
from sqlalchemy import select
from fulfillment.schemas.agent import MonitorRequest, MonitorResponse
from fulfillment.agents.orchestrator import FulfillmentOrchestrator

router = APIRouter()


@router.get("/status")
async def agent_status(db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)) -> dict:
    """Read persisted evidence only; never run a cycle by opening a page."""
    event = await db.scalar(select(AgentEvent).where(
        AgentEvent.agent_name == "FulfillmentOrchestrator", AgentEvent.event_type == "cycle_complete"
    ).order_by(AgentEvent.created_at.desc()).limit(1))
    details = json.loads(event.details_json or "{}") if event else {}
    return {"recorded": event is not None, "cycle_id": event.entity_id if event else "",
        "completed_at": event.created_at if event else None, "events": [],
        **{key: int(details.get(key, 0)) for key in ("shipments_checked", "delays_detected",
            "reroutes_initiated", "notifications_sent", "anomalies_found")}}


@router.post("/monitor", response_model=MonitorResponse)
async def run_agent_monitor(
    payload: MonitorRequest | None = None,
    db: AsyncSession = Depends(get_db),
    _user: dict[str, str] = Depends(require_operator_or_admin),
) -> MonitorResponse:
    orchestrator = FulfillmentOrchestrator(db)
    try:
        return await orchestrator.run_monitor_cycle(payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Monitor cycle failed: {exc}",
        )
