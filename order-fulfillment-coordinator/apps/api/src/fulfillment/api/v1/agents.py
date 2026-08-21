from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from fulfillment.api.deps import get_db, require_operator_or_admin
from fulfillment.schemas.agent import MonitorRequest, MonitorResponse
from fulfillment.agents.orchestrator import FulfillmentOrchestrator

router = APIRouter()


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
