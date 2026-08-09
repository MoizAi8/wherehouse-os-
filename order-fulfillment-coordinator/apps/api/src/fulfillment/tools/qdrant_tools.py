from __future__ import annotations

from typing import Any

from agents import function_tool

from fulfillment.vector_store import (
    search_past_decisions,
    upsert_agent_decision,
    search_similar_customers,
    search_similar_delays,
    upsert_shipment_event,
    format_decisions_for_agent,
)


@function_tool
async def get_routing_context(order_sla: str, order_value: float) -> str:
    """
    Routing Agent ke liye past context nikalo.
    Batao ke pehle is type ke orders ke liye kya decide kiya gaya tha.
    """
    decisions = await search_past_decisions(
        agent_name="RoutingAgent",
        event_type="ORDER_PLACED",
        limit=3,
    )
    customers = await search_similar_customers(
        sla_tier=order_sla,
        avg_value=order_value,
        limit=2,
    )
    context = format_decisions_for_agent(decisions)
    if customers:
        freq_carrier = customers[0].payload.get("frequent_carrier", "N/A")
        context += f"\nSimilar customers prefer carrier: {freq_carrier}"
    return context


@function_tool
async def log_routing_decision(
    fc_id: str,
    carrier: str,
    cost: float,
    order_id: str,
) -> str:
    """Routing decision Qdrant mein save karo. Hamesha call karo routing ke baad."""
    await upsert_agent_decision(
        {
            "agent_name": "RoutingAgent",
            "event_type": "ORDER_PLACED",
            "decision": f"fc:{fc_id} carrier:{carrier}",
            "outcome": "pending",
            "order_id": order_id,
            "cost": cost,
        }
    )
    return f"Decision logged: fc:{fc_id} carrier:{carrier} cost:{cost}"


@function_tool
async def get_delay_pattern(carrier: str, status: str) -> str:
    """
    Monitor Agent ke liye: is carrier ne pehle is status mein kitna delay kiya?
    Risk score calculate karne ke liye use karo.
    """
    results = await search_similar_delays(
        carrier=carrier,
        status=status,
        limit=20,
    )
    if not results:
        return f"No historical data for {carrier} with status {status}"

    total = len(results)
    delayed = sum(1 for r in results if r.payload.get("risk_score", 0) > 0.5)
    delay_rate = delayed / total

    return (
        f"Carrier: {carrier} | Status: {status}\n"
        f"Historical events: {total}\n"
        f"Delay rate: {delay_rate:.0%}\n"
        f"Risk level: {'HIGH' if delay_rate > 0.6 else 'MEDIUM' if delay_rate > 0.3 else 'LOW'}"
    )


@function_tool
async def log_shipment_event(
    order_id: str,
    carrier: str,
    status: str,
    risk_score: float,
    reason: str = "",
) -> str:
    """Monitor cycle mein har at-risk shipment ka event save karo."""
    await upsert_shipment_event(
        {
            "order_id": order_id,
            "carrier": carrier,
            "status": status,
            "risk_score": risk_score,
            "reason": reason,
        }
    )
    return f"Event logged: {order_id} risk={risk_score}"


@function_tool
async def get_rerouting_context(disrupted_carrier: str) -> str:
    """
    Re-routing Agent ke liye: jab X carrier ne fail kiya,
    pehle kaunsa alternative carrier use kiya gaya tha aur outcome kya tha?
    """
    results = await search_past_decisions(
        agent_name="ReroutingAgent",
        event_type="SHIPMENT_DISRUPTION",
        limit=5,
    )
    successful = [
        r
        for r in results
        if "success" in r.payload.get("outcome", "").lower()
        or "on_time" in r.payload.get("outcome", "").lower()
    ]
    return (
        format_decisions_for_agent(successful)
        if successful
        else "No successful rerouting history found. Use carrier rates API."
    )


@function_tool
async def log_rerouting_decision(
    order_id: str,
    old_carrier: str,
    new_carrier: str,
    outcome: str,
) -> str:
    """Rerouting decision save karo - outcome baad mein update hoga."""
    await upsert_agent_decision(
        {
            "agent_name": "ReroutingAgent",
            "event_type": "SHIPMENT_DISRUPTION",
            "decision": f"switched from {old_carrier} to {new_carrier}",
            "outcome": outcome,
            "order_id": order_id,
        }
    )
    return f"Rerouting logged: {old_carrier} -> {new_carrier}"


@function_tool
async def get_customer_notification_preference(
    customer_sla: str,
    order_value: float,
) -> str:
    """
    Communication Agent ke liye: is type ke customer ka
    preferred notification channel kya hai?
    """
    results = await search_similar_customers(
        sla_tier=customer_sla,
        avg_value=order_value,
        limit=3,
    )
    if not results:
        return "channel:email  (default - no history found)"

    channels = [r.payload.get("preferred_channel", "email") for r in results]
    preferred = max(set(channels), key=channels.count)
    vip = any(r.payload.get("vip") for r in results)
    return (
        f"preferred_channel:{preferred}\n"
        f"vip_customer:{vip}\n"
        f"Based on {len(results)} similar customers"
    )


@function_tool
async def get_carrier_cost_analysis() -> str:
    """
    Cost Optimizer ke liye: pichle 100 routing decisions mein
    kaunsa carrier sasta aur reliable raha?
    """
    results = await search_past_decisions(
        agent_name="RoutingAgent",
        event_type="ORDER_PLACED",
        limit=100,
    )
    if not results:
        return "Insufficient data for cost analysis"

    carrier_data: dict[str, dict[str, Any]] = {}
    for r in results:
        p = r.payload
        decision = p.get("decision", "")
        carrier = decision.split("carrier:")[-1].split()[0] if "carrier:" in decision else "unknown"
        cost = float(p.get("cost", 0))
        outcome = p.get("outcome", "unknown")
        if carrier not in carrier_data:
            carrier_data[carrier] = {"costs": [], "success": 0, "total": 0}
        carrier_data[carrier]["costs"].append(cost)
        carrier_data[carrier]["total"] += 1
        if "on_time" in outcome or "success" in outcome:
            carrier_data[carrier]["success"] += 1

    lines = ["Carrier cost analysis (last 100 decisions):"]
    for carrier, data in carrier_data.items():
        avg_cost = sum(data["costs"]) / len(data["costs"])
        success_rate = data["success"] / data["total"]
        lines.append(
            f"  {carrier}: avg_cost=${avg_cost:.2f} "
            f"success_rate={success_rate:.0%} "
            f"total_orders={data['total']}"
        )
    return "\n".join(lines)