# mypy: disable-error-code="attr-defined,arg-type,assignment,index,union-attr"
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from fulfillment.agents.monitor import MonitorAgent
from fulfillment.agents.rerouting import ReroutingAgent
from fulfillment.agents.communication import CommunicationAgent
from fulfillment.agents.prediction import PredictionAgent
from fulfillment.agents.cost_optimizer import CostOptimizer
from fulfillment.schemas.agent import MonitorRequest, MonitorResponse
from fulfillment.guardrails.sla import sla_compliance
from fulfillment.guardrails.cost import cost_cap
from fulfillment.guardrails.notifications import notification_frequency
from fulfillment.guardrails.failed_delivery import failed_delivery_threshold
from fulfillment.models.agent_event import AgentEvent
from fulfillment.resilience import with_retry, get_circuit_breaker
from fulfillment.logging_config import log_agent_event

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

_monitor_breaker = get_circuit_breaker("monitor_agent", failure_threshold=5, timeout=60.0)
_rerouting_breaker = get_circuit_breaker("rerouting_agent", failure_threshold=5, timeout=60.0)
_communication_breaker = get_circuit_breaker("communication_agent", failure_threshold=5, timeout=60.0)
_prediction_breaker = get_circuit_breaker("prediction_agent", failure_threshold=5, timeout=60.0)
_cost_breaker = get_circuit_breaker("cost_optimizer", failure_threshold=5, timeout=60.0)


class FulfillmentOrchestrator:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.monitor = MonitorAgent(db)
        self.rerouting = ReroutingAgent(db)
        self.communication = CommunicationAgent(db)
        self.prediction = PredictionAgent(db)
        self.cost_optimizer = CostOptimizer(db)

    async def run_monitor_cycle(self, request: MonitorRequest | None = None) -> MonitorResponse:
        cycle_id = str(uuid4())
        checked = 0
        delays = 0
        reroutes = 0
        notifications = 0
        anomalies = 0
        events: list[dict] = []

        log_agent_event("FulfillmentOrchestrator", "cycle_start", entity_id=cycle_id, details={})

        try:
            shipments = await with_retry(
                lambda: self.monitor.get_active_shipments(entity_ids=request.entity_ids if request else None),
                max_retries=2,
                retry_exceptions=(Exception,),
            )
        except Exception as exc:
            logger.error("Failed to fetch active shipments: %s", exc)
            log_agent_event(
                "FulfillmentOrchestrator",
                "cycle_error",
                entity_id=cycle_id,
                details={"error": str(exc)},
                level=logging.ERROR
            )
            return MonitorResponse(
                cycle_id=cycle_id,
                shipments_checked=0,
                delays_detected=0,
                reroutes_initiated=0,
                notifications_sent=0,
                anomalies_found=1,
                events=[{"type": "cycle_error", "detail": str(exc)}],
                completed_at=datetime.now(timezone.utc),
            )

        checked = len(shipments)  # type: ignore[arg-type]

        for shipment in shipments:  # type: ignore[union-attr]
            try:
                delay_result = await with_retry(
                    lambda: _monitor_breaker.call(self.monitor.check_delay, shipment),
                    max_retries=2,
                    retry_exceptions=(Exception,),
                )  # type: ignore[assignment]
            except Exception as exc:
                logger.error("Delay check failed for shipment %s: %s", shipment.id, exc)
                log_agent_event(
                    "MonitorAgent",
                    "delay_check_failed",
                    entity_id=shipment.id,
                    details={"error": str(exc)},
                    level=logging.ERROR
                )
                anomalies += 1
                continue

            if delay_result["is_delayed"]:
                delays += 1
                if not sla_compliance(shipment):
                    events.append({
                        "type": "sla_breach",
                        "shipment_id": shipment.id,
                        "detail": "SLA compliance check failed",
                    })
                    anomalies += 1

                if not failed_delivery_threshold(shipment):
                    events.append({
                        "type": "failed_delivery_risk",
                        "shipment_id": shipment.id,
                        "detail": "Failed delivery threshold exceeded",
                    })
                    anomalies += 1

                try:
                    reroute_result = await with_retry(
                        lambda: _rerouting_breaker.call(self.rerouting.evaluate_reroute, shipment),
                        max_retries=2,
                        retry_exceptions=(Exception,),
                    )  # type: ignore[assignment]
                except Exception as exc:
                    logger.error("Reroute evaluation failed for shipment %s: %s", shipment.id, exc)
                    log_agent_event(
                        "ReroutingAgent",
                        "evaluate_failed",
                        entity_id=shipment.id,
                        details={"error": str(exc)},
                        level=logging.ERROR
                    )
                    anomalies += 1
                    continue

                if reroute_result["should_reroute"]:
                    if cost_cap(shipment.shipping_cost or 0, reroute_result.get("new_cost", 0)):
                        try:
                            executed = await with_retry(
                                lambda: _rerouting_breaker.call(self.rerouting.execute_reroute, shipment, reroute_result),
                                max_retries=2,
                                retry_exceptions=(Exception,),
                            )  # type: ignore[assignment]
                            if executed:
                                reroutes += 1
                                events.append({
                                    "type": "reroute_executed",
                                    "shipment_id": shipment.id,
                                    "detail": executed,
                                })
                                if await notification_frequency(shipment.order_id, self.db):
                                    try:
                                        notif_result = await with_retry(
                                            lambda: _communication_breaker.call(self.communication.send_delay_alert, shipment=shipment, delay_reason=delay_result.get("reason", "Unknown")),
                                            max_retries=2,
                                            retry_exceptions=(Exception,),
                                        )  # type: ignore[assignment]
                                        if notif_result:
                                            notifications += 1
                                            events.append({
                                                "type": "notification_sent",
                                                "shipment_id": shipment.id,
                                                "detail": notif_result,
                                            })
                                    except Exception as exc:
                                        logger.error("Notification failed for shipment %s: %s", shipment.id, exc)
                                        anomalies += 1
                        except Exception as exc:
                            logger.error("Reroute execution failed for shipment %s: %s", shipment.id, exc)
                            log_agent_event(
                                "ReroutingAgent",
                                "execute_failed",
                                entity_id=shipment.id,
                                details={"error": str(exc)},
                                level=logging.ERROR
                            )
                            anomalies += 1

                try:
                    pred = await with_retry(
                        lambda: _prediction_breaker.call(self.prediction.predict_failure, shipment),
                        max_retries=2,
                        retry_exceptions=(Exception,),
                    )  # type: ignore[assignment]
                    if pred.get("failure_probability", 0) > 0.5:
                        anomalies += 1
                        events.append({
                            "type": "high_failure_risk",
                            "shipment_id": shipment.id,
                            "failure_probability": pred["failure_probability"],
                        })
                    await self._log_event("PredictionAgent", "failure_prediction", shipment.id, pred)
                except Exception as exc:
                    logger.error("Prediction failed for shipment %s: %s", shipment.id, exc)
                    log_agent_event(
                        "PredictionAgent",
                        "prediction_failed",
                        entity_id=shipment.id,
                        details={"error": str(exc)},
                        level=logging.ERROR
                    )

                await self._log_event("MonitorAgent", "delay_detected", shipment.id, delay_result)

        try:
            analysis = await with_retry(
                lambda: _cost_breaker.call(self.cost_optimizer.analyze_cycle, cycle_id),
                max_retries=2,
                retry_exceptions=(Exception,),
            )  # type: ignore[assignment]
            if analysis:
                events.append({"type": "cost_analysis", "detail": analysis})
        except Exception as exc:
            logger.error("Cost analysis failed for cycle %s: %s", cycle_id, exc)
            log_agent_event(
                "CostOptimizer",
                "analysis_failed",
                entity_id=cycle_id,
                details={"error": str(exc)},
                level=logging.ERROR
            )

        log_agent_event(
            "FulfillmentOrchestrator",
            "cycle_complete",
            entity_id=cycle_id,
            details={
                "shipments_checked": checked,
                "delays_detected": delays,
                "reroutes_initiated": reroutes,
                "notifications_sent": notifications,
                "anomalies_found": anomalies,
            }
        )

        return MonitorResponse(
            cycle_id=cycle_id,
            shipments_checked=checked,
            delays_detected=delays,
            reroutes_initiated=reroutes,
            notifications_sent=notifications,
            anomalies_found=anomalies,
            events=events,
            completed_at=datetime.now(timezone.utc),
        )

    async def _log_event(
        self,
        agent_name: str,
        event_type: str,
        entity_id: str | None,
        details: dict,
    ) -> None:
        event = AgentEvent(
            id=str(uuid4()),
            agent_name=agent_name,
            event_type=event_type,
            entity_id=entity_id,
            summary=f"{agent_name} - {event_type}",
            details_json=json.dumps(details, default=str),
            risk_score=details.get("risk_score"),
        )
        self.db.add(event)
