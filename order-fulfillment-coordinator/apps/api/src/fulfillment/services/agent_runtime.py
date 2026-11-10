"""Conservative runtime reporting from committed execution evidence.

IDLE means a recent completed invocation, not a worker heartbeat. No live
RUNNING or READY assertion is made without a corresponding runtime probe.
"""
from datetime import datetime, timedelta, timezone
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fulfillment.models.agent_event import AgentEvent


AGENT_OUTCOMES = {
    "RoutingAgent": {"route_selected"},
    "MonitorAgent": {"scan_complete", "delay_detected", "delay_check_failed"},
    "PredictionAgent": {"failure_prediction", "prediction_failed"},
    "ReroutingAgent": {"reroute_evaluated", "reroute_recommended", "reroute_executed", "evaluate_failed", "execute_failed"},
    "CommunicationAgent": {"provider_accepted", "delivery_failed", "delivery_unknown", "delivery_uncertain"},
    "CostOptimizer": {"cost_analysis", "analysis_failed"},
    "FulfillmentOrchestrator": {"cycle_complete", "cycle_failed"},
}
FAILURES = {"delay_check_failed", "prediction_failed", "evaluate_failed", "execute_failed",
            "delivery_failed", "delivery_unknown", "delivery_uncertain", "analysis_failed", "cycle_failed"}
EVIDENCE_MAX_AGE = timedelta(hours=24)


def _outcome(event: AgentEvent) -> dict:
    """Expose operational values without returning the raw event payload."""
    try:
        details = json.loads(event.details_json or "{}")
    except ValueError:
        return {}
    if not isinstance(details, dict):
        return {}
    keys = ("shipping_cost", "risk_level", "failure_probability", "is_delayed",
            "alternative_carrier", "current_cost", "new_cost", "approval_required",
            "shipments_checked", "delays_detected", "anomalies_found", "attempt")
    result = {k: details[k] for k in keys if isinstance(details.get(k), (str, int, float))}
    carrier = details.get("carrier")
    if isinstance(carrier, dict) and isinstance(carrier.get("name"), str):
        result["carrier"] = carrier["name"]
    analysis = details.get("analysis")
    if isinstance(analysis, dict):
        for k in ("total_shipments", "total_cost", "average_cost"):
            if isinstance(analysis.get(k), (int, float)):
                result[k] = analysis[k]
    return result


async def agent_runtime_status(db: AsyncSession) -> list[dict]:
    now = datetime.now(timezone.utc)
    agents = []
    for name, outcomes in AGENT_OUTCOMES.items():
        event = await db.scalar(select(AgentEvent).where(
            AgentEvent.agent_name == name, AgentEvent.event_type.in_(outcomes),
        ).order_by(AgentEvent.created_at.desc(), AgentEvent.id.desc()).limit(1))
        timestamp = event.created_at.replace(tzinfo=timezone.utc) if event and event.created_at.tzinfo is None else event.created_at if event else None
        state = "UNVERIFIED"
        reason = "No completed execution evidence"
        if event and event.event_type in FAILURES:
            state, reason = "FAILED", "Latest recorded execution failed or requires reconciliation"
        elif timestamp and timedelta(0) <= now - timestamp <= EVIDENCE_MAX_AGE:
            state, reason = "IDLE", "Recent completed execution; current worker activity is not measured"
        elif event:
            reason = "Execution evidence is stale or has an invalid timestamp"
        agents.append({
            "name": name, "status": state, "reason": reason,
            "event_id": event.id if event else None,
            "event_type": event.event_type if event else None,
            "entity_id": event.entity_id if event else None,
            "observed_at": timestamp,
            "outcome": _outcome(event) if event else {},
        })
    return agents
