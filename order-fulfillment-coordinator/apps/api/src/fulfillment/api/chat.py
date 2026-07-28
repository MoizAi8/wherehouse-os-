from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends
from openai import AsyncOpenAI
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func as sqlfunc

from fulfillment.api.deps import get_current_user, get_db
from fulfillment.agents.intent_analyzer import IntentAnalyzer
from fulfillment.config import settings
from fulfillment.models.order import Order, OrderStatus
from fulfillment.models.shipment import Shipment
from fulfillment.schemas.order import OrderCreate, OrderRead
from fulfillment.services.order_service import OrderService

logger = logging.getLogger("fulfillment.chat")

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessage(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    action: str | None = None
    data: dict | None = None


_openai_client: AsyncOpenAI | None = None
if settings.openai_api_key:
    kwargs = dict(api_key=settings.openai_api_key, timeout=8.0, max_retries=0)
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    _openai_client = AsyncOpenAI(**kwargs)

_intent_analyzer = IntentAnalyzer(_openai_client)


INTENT_MAP = {
    "ROUTE_ORDER": "proceed_delivery",
    "TRACK_SHIPMENT": "check_status",
    "PREDICT_RISK": "insight",
    "OPTIMIZE_COST": "cost_analysis",
    "REROUTE_SHIPMENT": "reroute_list",
    "SEND_NOTIFICATION": "help",
    "LIST_ORDERS": "list_orders",
    "CHECK_STATUS": "check_status",
    "AGENT_INFO": "agent_count",
    "GET_METRICS": "metrics",
    "GET_INSIGHT": "insight",
    "FILTER_ORDERS": "filter_orders",
    "FULFILLMENT_CENTERS": "fulfillment_centers",
    "CARRIER_USAGE": "carrier_usage",
    "ACTIVE_SHIPMENTS": "active_shipments",
    "DELAYED_SHIPMENTS": "delayed_shipments",
    "ON_TIME_SHIPMENTS": "on_time_shipments",
    "HIGH_RISK_SHIPMENTS": "high_risk_shipments",
    "COST_ANALYSIS": "cost_analysis",
    "REROUTE_LIST": "reroute_list",
    "NOTIFICATION_STATS": "notification_stats",
    "CYCLE_STATS": "cycle_stats",
    "OLDEST_PENDING": "oldest_pending",
    "HELP": "help",
    "GREETING": "greeting",
    "CREATE_ORDER": "create_order",
}

async def detect_intent(text: str) -> str:
    result = await _intent_analyzer.analyze(text)
    logger.info(
        "Intent analyzed | intent=%s agent=%s confidence=%.2f reason='%s' missing=%s",
        result.intent, result.required_agent, result.confidence, result.reason, result.missing_information,
    )
    return INTENT_MAP.get(result.intent, "help")


async def _generate_llm_reply(system_prompt: str, user_prompt: str, max_tokens: int = 500, fallback: str | None = None) -> str:
    if not _openai_client:
        return fallback or "AI service is not configured."
    logger.info("LLM response generation request sent")
    try:
        resp = await _openai_client.chat.completions.create(
            model=settings.openai_model or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=max_tokens,
        )
        reply = resp.choices[0].message.content.strip()
        logger.info("LLM response generation received | length=%d", len(reply))
        return reply
    except Exception as e:
        logger.error("LLM response generation failed | error='%s'", e)
        return fallback or "I'm having trouble processing your request right now. Please try again."


_CHAT_SYSTEM_PROMPT = (
    "# Enterprise AI Multi-Agent System Prompt\n\n"
    "You are an advanced enterprise-grade AI agent operating within a Multi-Agent AI System.\n\n"
    "Your primary objective is to provide accurate, context-aware, logical, and reliable responses. "
    "Never rely only on predefined prompts or hardcoded examples. Instead, understand the user's intent and reason step by step before producing an answer.\n\n"
    "## Core Responsibilities\n\n"
    "- Understand the real intent behind every user question.\n"
    "- Analyze all available context before answering.\n"
    "- If additional context is available from memory, knowledge base, vector database, APIs, tools, or previous conversation, use it.\n"
    "- If information is missing, clearly state what is missing instead of making assumptions.\n"
    "- Never hallucinate facts.\n"
    "- Always prefer factual, verifiable information.\n\n"
    "## Reasoning Process\n\n"
    "For every request:\n\n"
    "1. Understand the user's goal.\n"
    "2. Identify the domain.\n"
    "3. Gather relevant context.\n"
    "4. Decide whether tools or memory are required.\n"
    "5. Validate retrieved information.\n"
    "6. Produce a complete and well-structured response.\n"
    "7. Explain uncertainty when confidence is low.\n\n"
    "## Context Priority\n\n"
    "Always use information in the following order:\n\n"
    "1. User Input\n"
    "2. Conversation History\n"
    "3. Long-Term Memory\n"
    "4. Knowledge Base / RAG\n"
    "5. External Tools / APIs\n"
    "6. General LLM Knowledge\n\n"
    "Never ignore higher-priority context.\n\n"
    "## Response Quality\n\n"
    "Every answer should be:\n\n"
    "- Accurate\n"
    "- Context-aware\n"
    "- Logical\n"
    "- Complete\n"
    "- Consistent\n"
    "- Actionable\n"
    "- Professional\n\n"
    "Avoid vague or generic responses.\n\n"
    "## Handling Unknown Questions\n\n"
    "If the answer cannot be determined:\n\n"
    "- Say that the available information is insufficient.\n"
    "- Explain what additional information is needed.\n"
    "- Never invent data.\n\n"
    "## Multi-Agent Collaboration\n\n"
    "If another specialized agent is better suited for the task:\n\n"
    "- Route the task appropriately.\n"
    "- Share all required context.\n"
    "- Return the integrated final answer.\n\n"
    "## Error Prevention\n\n"
    "Never:\n\n"
    "- Guess missing information.\n"
    "- Contradict previous context.\n"
    "- Ignore user instructions.\n"
    "- Produce fabricated citations.\n"
    "- Repeat predefined template answers.\n\n"
    "## Output Style\n\n"
    "Always produce responses that are:\n\n"
    "- Structured\n"
    "- Easy to understand\n"
    "- Technically accurate\n"
    "- Relevant to the user's actual question\n\n"
    "Use headings and bullet points when appropriate.\n\n"
    "## Goal\n\n"
    "Your goal is not merely to answer prompts.\n\n"
    "Your goal is to understand problems, reason intelligently, use available knowledge, collaborate with other agents when necessary, and provide the most accurate response possible."
)


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatMessage,
    db: AsyncSession = Depends(get_db),
    _user: dict[str, str] = Depends(get_current_user),
) -> ChatResponse:
    message = body.message.strip()
    logger.info("User request received | message='%s'", message[:80])

    intent = await detect_intent(message)
    logger.info("Intent detected | intent='%s'", intent)

    service = OrderService(db)

    if intent == "greeting":
        logger.info("LLM request sent | intent=greeting")
        reply = "Hello! I'm your warehouse operations assistant. How can I help you today?"
        if _openai_client:
            r = await _generate_llm_reply(
                _CHAT_SYSTEM_PROMPT,
                f"The user said: \"{message}\"\n\nRespond with a friendly greeting and ask how you can help them with their warehouse.",
                max_tokens=100,
            )
            if "trouble" not in r and "not configured" not in r:
                reply = r
        return ChatResponse(reply=reply, action="greeting")

    if intent == "help":
        system_data = (
            "Available commands:\n"
            "- Create order: provide email, address, city, weight\n"
            "- List orders: show all orders\n"
            "- Check status: track order\n"
            "- Agent info: list agents, agent health, performance\n"
            "- Metrics: system summary, KPIs\n"
            "- Proceed delivery: route pending orders\n"
            "- Filter: pending/delayed orders\n"
            "- Fulfillment centers: FC assignments\n"
            "- Carriers: usage and costs\n"
            "- Shipments: active, delayed, on-time, high-risk\n"
            "- Analytics: cost analysis, reroute list, cycle stats\n"
            "- Notifications: stats\n"
        )
        logger.info("LLM request sent | intent=help")
        reply = await _generate_llm_reply(
            _CHAT_SYSTEM_PROMPT,
            f"The user needs help. Here is what the system can do:\n{system_data}\n\nUser said: \"{message}\"\n\nExplain how they can interact with the system.",
            max_tokens=300,
            fallback=f"I can help you with: creating orders, listing orders, checking shipment status, agent info, system metrics, and more. What would you like to do?",
        )
        return ChatResponse(reply=reply, action="help")

    if intent == "proceed_delivery":
        pending = await service.list_orders(skip=0, limit=50, status_filter="pending")
        if not pending:
            logger.info("No pending orders to process")
            reply = await _generate_llm_reply(
                _CHAT_SYSTEM_PROMPT,
                "The user wants to proceed with delivery but there are no pending orders. Let them know politely.",
                max_tokens=80,
            )
            return ChatResponse(reply=reply, action="proceed_delivery")
        routed = []
        failed = []
        for o in pending:
            try:
                svc = OrderService(db)
                result = await svc.route_order(o.id)
                routed.append(result)
            except ValueError as e:
                failed.append({"id": o.id[:8], "reason": str(e)[:80]})
        data_summary = (
            f"Routed {len(routed)} orders successfully, {len(failed)} failed."
        )
        if routed:
            data_summary += "\nRouted details:\n" + "\n".join(
                f"- #{r.order_id[:8]} -> {r.carrier_name} (tracking: {r.tracking_number})"
                for r in routed[:5]
            )
        if failed:
            data_summary += "\nFailed:\n" + "\n".join(
                f"- #{f['id']}: {f['reason']}" for f in failed[:3]
            )
        logger.info("LLM request sent | intent=proceed_delivery | routed=%d failed=%d", len(routed), len(failed))
        reply = await _generate_llm_reply(
            _CHAT_SYSTEM_PROMPT,
            f"The user requested to process all pending deliveries. Here are the results:\n{data_summary}\n\nSummarize the results for the user in a friendly way.",
            max_tokens=300,
        )
        return ChatResponse(
            reply=reply,
            action="proceed_delivery",
            data={"routed": len(routed), "failed": len(failed)},
        )

    if intent == "list_orders":
        orders = await service.list_orders(skip=0, limit=20)
        total = await service.count_orders()
        if not orders:
            logger.info("No orders found")
            reply = await _generate_llm_reply(
                _CHAT_SYSTEM_PROMPT,
                "The user wants to see orders but there are none. Suggest they create one.",
                max_tokens=80,
            )
            return ChatResponse(
                reply=reply,
                action="list_orders",
                data={"orders": [], "total": 0},
            )
        order_lines = "\n".join(
            f"- #{o.id[:8]} | {o.customer_email} | {o.shipping_city}, {o.shipping_state} | {o.status}"
            for o in orders[:15]
        )
        logger.info("LLM request sent | intent=list_orders | total=%d", total)
        reply = await _generate_llm_reply(
            _CHAT_SYSTEM_PROMPT,
            f"The user wants to see all orders. Total orders: {total}.\n\nOrders:\n{order_lines}\n\nPresent the orders in a clean readable format.",
            max_tokens=400,
        )
        return ChatResponse(
            reply=reply,
            action="list_orders",
            data={"total": total, "orders": [OrderRead.model_validate(o).model_dump(mode="json") for o in orders[:10]]},
        )

    if intent == "check_status":
        orders = await service.list_orders(skip=0, limit=10)
        if not orders:
            logger.info("No orders for status check")
            reply = await _generate_llm_reply(
                _CHAT_SYSTEM_PROMPT,
                "The user wants to check order status but there are no orders. Let them know.",
                max_tokens=80,
            )
            return ChatResponse(reply=reply, action="check_status")
        order_lines = "\n".join(
            f"- #{o.id[:8]} | {o.customer_email} -> {o.status}"
            for o in orders[:10]
        )
        logger.info("LLM request sent | intent=check_status")
        reply = await _generate_llm_reply(
            _CHAT_SYSTEM_PROMPT,
            f"The user wants to check order status. Recent orders:\n{order_lines}\n\nPresent the status information clearly.",
            max_tokens=300,
        )
        return ChatResponse(reply=reply, action="check_status")

    if intent == "agent_count":
        from fulfillment.agents.monitor import MonitorAgent
        from fulfillment.models.agent_event import AgentEvent

        agent = MonitorAgent(db)
        shipments = await agent.get_active_shipments()
        shipment_count = len(shipments)
        delayed_count = sum(1 for s in shipments if getattr(s, "is_delayed", False))

        ev_count_r = await db.execute(select(sqlfunc.count(AgentEvent.id)))
        total_events = ev_count_r.scalar() or 0

        context = (
            "Active agents:\n"
            "1. FulfillmentOrchestrator — coordinates all agents\n"
            "2. RoutingAgent — decides carrier and fulfillment center\n"
            "3. MonitorAgent — checks shipments every 15 minutes\n"
            "4. PredictionAgent — calculates risk scores\n"
            "5. CostOptimizer — analyzes shipping costs\n"
            "6. ReroutingAgent — evaluates alternative carriers\n"
            "7. CommunicationAgent — sends SMS and email alerts\n"
            f"\nActive shipments: {shipment_count}\n"
            f"Delayed: {delayed_count}\n"
            f"Total events logged: {total_events}"
        )
        logger.info("LLM request sent | intent=agent_count")
        reply = await _generate_llm_reply(
            _CHAT_SYSTEM_PROMPT,
            f"The user wants to know about agents and their status.\n\nCurrent system state:\n{context}\n\nPresent the agent information in a clear organized way.",
            max_tokens=400,
        )
        return ChatResponse(reply=reply, action="agent_count")

    if intent == "agent_perf":
        from fulfillment.agents.monitor import MonitorAgent
        from fulfillment.models.agent_event import AgentEvent

        agent = MonitorAgent(db)
        shipments = await agent.get_active_shipments()
        total_shipments = len(shipments)
        delayed_count = sum(1 for s in shipments if getattr(s, "is_delayed", False))

        svc = OrderService(db)
        total_orders = await svc.count_orders()
        pending = await svc.count_orders(status_filter="pending")
        processing = await svc.count_orders(status_filter="processing")

        total_cost_r = await db.execute(select(sqlfunc.sum(Shipment.shipping_cost)))
        total_cost = float(total_cost_r.scalar() or 0)

        ev_count = await db.execute(select(sqlfunc.count(AgentEvent.id)).where(AgentEvent.agent_name == "MonitorAgent"))
        monitor_events = ev_count.scalar() or 0

        context = (
            f"FulfillmentOrchestrator: {monitor_events} cycles completed\n"
            f"RoutingAgent: assigned carrier to {processing} orders\n"
            f"MonitorAgent: monitoring {total_shipments} shipments\n"
            f"PredictionAgent: scoring {total_shipments} shipments\n"
            f"CostOptimizer: analyzed ${total_cost:.2f} total cost\n"
            f"ReroutingAgent: evaluating alternatives\n"
            f"CommunicationAgent: sending alerts\n\n"
            f"Active: {total_shipments} | Delayed: {delayed_count}\n"
            f"Total orders: {total_orders} (Pending: {pending})"
        )
        logger.info("LLM request sent | intent=agent_perf")
        reply = await _generate_llm_reply(
            _CHAT_SYSTEM_PROMPT,
            f"The user wants agent performance data.\n\nCurrent performance:\n{context}\n\nPresent the performance data in a clear readable format.",
            max_tokens=400,
        )
        return ChatResponse(reply=reply, action="agent_perf")

    if intent == "metrics":
        total = await service.count_orders()
        pending = await service.count_orders(status_filter="pending")
        delayed = await service.count_orders(status_filter="delayed")
        processing = await service.count_orders(status_filter="processing")

        context = (
            f"Orders: {total} total\n"
            f"Pending: {pending}\n"
            f"Processing: {processing}\n"
            f"Delayed: {delayed}\n"
            f"Agents: 7 online"
        )
        logger.info("LLM request sent | intent=metrics")
        reply = await _generate_llm_reply(
            _CHAT_SYSTEM_PROMPT,
            f"The user wants system metrics and summary.\n\nData:\n{context}\n\nPresent the metrics clearly and suggest what they might want to check next.",
            max_tokens=300,
        )
        return ChatResponse(reply=reply, action="metrics")

    if intent == "insight":
        total_orders = await service.count_orders()
        pending = await service.count_orders(status_filter="pending")

        context = (
            f"Total system orders: {total_orders}\n"
            f"Pending orders needing delivery: {pending}\n"
            f"Available action: route pending orders with 'Proceed delivery'"
        )
        logger.info("LLM request sent | intent=insight")
        reply = await _generate_llm_reply(
            _CHAT_SYSTEM_PROMPT,
            f"The user wants insights and recommendations.\n\nSystem state:\n{context}\n\nProvide actionable insights and recommendations based on this data.",
            max_tokens=300,
        )
        return ChatResponse(reply=reply, action="insight")

    if intent == "filter_orders":
        lower = message.lower()
        filter_status = "delayed" if re.search(r"\b(?:delayed|delay)\b", lower) else "pending"
        orders = await service.list_orders(skip=0, limit=10, status_filter=filter_status)
        total = await service.count_orders(status_filter=filter_status)
        if not orders:
            logger.info("No %s orders found", filter_status)
            reply = await _generate_llm_reply(
                _CHAT_SYSTEM_PROMPT,
                f"The user wants to see {filter_status} orders but there are none. Let them know.",
                max_tokens=80,
            )
            return ChatResponse(
                reply=reply,
                action="filter_orders",
                data={"orders": [], "total": 0},
            )
        order_lines = "\n".join(
            f"- #{o.id[:8]} | {o.customer_email} | {o.shipping_city}, {o.shipping_state}"
            for o in orders[:8]
        )
        logger.info("LLM request sent | intent=filter_orders | status=%s count=%d", filter_status, total)
        reply = await _generate_llm_reply(
            _CHAT_SYSTEM_PROMPT,
            f"The user wants to see {filter_status} orders. Found {total} {filter_status} orders.\n\nOrders:\n{order_lines}\n\nPresent these {filter_status} orders clearly.",
            max_tokens=300,
        )
        return ChatResponse(
            reply=reply,
            action="filter_orders",
            data={"total": total, "orders": [OrderRead.model_validate(o).model_dump(mode="json") for o in orders[:8]]},
        )

    if intent == "create_order":
        email = _extract_email(message)
        if not email:
            name_patterns = [
                r"(?:customer name[:\s]+)(\w+(?:\s+\w+)?)",
                r"(?:name[:\s]+)(\w+(?:\s+\w+)?)",
                r"(?:for\s+)(\w+(?:\.?\s+\w+)?)",
            ]
            customer_name = "customer"
            for p in name_patterns:
                m = re.search(p, message, re.IGNORECASE)
                if m:
                    customer_name = m.group(1).strip()
                    break
            email = f"{customer_name.lower().replace(' ', '.')}@email.com"

        zip_code = _extract_zip(message)
        city = _extract_city(message)
        state = _extract_state(message)
        phone = _extract_phone(message)
        weight = _extract_weight(message)
        notes = _extract_notes(message)
        address = _extract_address(message) or f"Main Street, {city or 'Karachi'}, {state or 'Sindh'} {zip_code or '74000'}"

        if not city:
            city = "Karachi"
        if not state:
            state = "Sindh"
        if not zip_code:
            zip_code = "74000"
        if not address:
            address = f"Main Street, {city}, {state} {zip_code}"

        payload = OrderCreate(
            customer_email=email,
            customer_phone=phone,
            shipping_address=address,
            shipping_zip=zip_code,
            shipping_city=city,
            shipping_state=state,
            shipping_country="PK",
            total_weight_kg=weight or 1.0,
            notes=notes,
        )

        order = await service.create_order(payload)

        context = (
            f"Order created successfully:\n"
            f"Order ID: #{order.id[:8]}\n"
            f"Customer: {order.customer_email}\n"
            f"Address: {order.shipping_city}, {order.shipping_state}\n"
            f"Weight: {order.total_weight_kg} kg"
        )
        logger.info("LLM request sent | intent=create_order | order=%s", order.id[:8])
        reply = await _generate_llm_reply(
            _CHAT_SYSTEM_PROMPT,
            f"A new order was created. Details:\n{context}\n\nConfirm to the user that the order was created and will be routed.",
            max_tokens=200,
        )
        return ChatResponse(
            reply=reply,
            action="create_order_created",
            data=OrderRead.model_validate(order).model_dump(mode="json"),
        )

    if intent == "fulfillment_centers":
        svc = OrderService(db)
        total = await svc.count_orders()
        shipped = await svc.count_orders(status_filter="shipped")
        processing = await svc.count_orders(status_filter="processing")
        pending_count = total - processing - shipped
        from fulfillment.models.fulfillment_center import FulfillmentCenter
        fc_result = await db.execute(select(FulfillmentCenter))
        fcs = list(fc_result.scalars().all())
        fc_lines = [
            f"{fc.name} — {fc.city}, {fc.state} ({fc.current_daily_orders}/{fc.max_daily_orders} orders)"
            for fc in fcs
        ]
        from fulfillment.models import carrier_rate
        processing_orders = await svc.list_orders(status_filter="processing")
        carrier_lines = []
        for o in processing_orders[:8]:
            cr = None
            if o.carrier_id:
                cr_r = await db.execute(select(carrier_rate.CarrierRate).where(carrier_rate.CarrierRate.id == o.carrier_id))
                cr = cr_r.scalar_one_or_none()
            carrier_name = cr.carrier_name if cr else "N/A"
            carrier_lines.append(f"#{o.id[:8]} — {o.customer_email} -> {carrier_name}")

        context = (
            f"Orders total: {total} | Processing: {processing} | Pending: {pending_count}\n\n"
            f"Centers:\n" + "\n".join(fc_lines) + "\n\n"
            f"Orders with Carriers:\n" + "\n".join(carrier_lines)
        ) if fc_lines else f"Orders total: {total} | Processing: {processing} | Pending: {pending_count}\nNo fulfillment centers found."
        logger.info("LLM request sent | intent=fulfillment_centers")
        reply = await _generate_llm_reply(
            _CHAT_SYSTEM_PROMPT,
            f"The user wants fulfillment center and carrier info.\n\nData:\n{context}\n\nPresent the fulfillment center and carrier information clearly.",
            max_tokens=400,
        )
        return ChatResponse(reply=reply, action="fulfillment_centers")

    if intent == "oldest_pending":
        result = await db.execute(
            select(Order).where(Order.status == OrderStatus.PENDING).order_by(Order.created_at.asc()).limit(1)
        )
        oldest = result.scalar_one_or_none()
        if not oldest:
            logger.info("No pending orders for oldest query")
            reply = await _generate_llm_reply(
                _CHAT_SYSTEM_PROMPT,
                "The user wants the oldest pending order but there are none. Let them know.",
                max_tokens=80,
            )
            return ChatResponse(reply=reply, action="oldest_pending")
        created = oldest.created_at
        if created is not None and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        days_waiting = (datetime.now(timezone.utc) - created).days if created else 0
        context = (
            f"Oldest Pending Order:\n"
            f"Order: #{oldest.id[:8]}\n"
            f"Customer: {oldest.customer_email}\n"
            f"Location: {oldest.shipping_city}, {oldest.shipping_state}\n"
            f"Weight: {oldest.total_weight_kg} kg\n"
            f"Created: {oldest.created_at.strftime('%b %d, %Y') if oldest.created_at else 'N/A'}\n"
            f"Pending for: {days_waiting} days"
        )
        logger.info("LLM request sent | intent=oldest_pending")
        reply = await _generate_llm_reply(
            _CHAT_SYSTEM_PROMPT,
            f"The user wants the oldest pending order.\n\nDetails:\n{context}\n\nPresent this information to the user.",
            max_tokens=200,
        )
        return ChatResponse(reply=reply, action="oldest_pending")

    if intent == "carrier_usage":
        result = await db.execute(
            select(
                Shipment.carrier_name,
                sqlfunc.count(Shipment.id).label("count"),
                sqlfunc.sum(Shipment.shipping_cost).label("total_cost"),
            ).group_by(Shipment.carrier_name)
        )
        rows = result.all()
        if not rows:
            logger.info("No carrier usage data")
            reply = await _generate_llm_reply(
                _CHAT_SYSTEM_PROMPT,
                "The user wants carrier usage info but no carriers are being used. Let them know.",
                max_tokens=80,
            )
            return ChatResponse(reply=reply, action="carrier_usage")
        lines = "\n".join(
            f"{r.carrier_name}: {r.count} shipments, ${float(r.total_cost or 0):.2f} total"
            for r in rows
        )
        logger.info("LLM request sent | intent=carrier_usage")
        reply = await _generate_llm_reply(
            _CHAT_SYSTEM_PROMPT,
            f"The user wants carrier usage data.\n\nCarrier usage:\n{lines}\n\nPresent carrier usage info clearly.",
            max_tokens=300,
        )
        return ChatResponse(reply=reply, action="carrier_usage")

    if intent == "active_shipments":
        from fulfillment.agents.monitor import MonitorAgent
        agent = MonitorAgent(db)
        count = await agent.count_active_shipments()
        shipments = await agent.get_active_shipments()
        lines = "\n".join(
            f"{'⚠️' if getattr(s, 'is_delayed', False) else '✅'} #{s.id[:8]} — {s.carrier_name} ({s.tracking_number})"
            for s in shipments[:10]
        )
        more = f"\n... and {count - 10} more" if count > 10 else ""
        context = f"Active Shipments: {count}\n{lines}{more}"
        logger.info("LLM request sent | intent=active_shipments")
        reply = await _generate_llm_reply(
            _CHAT_SYSTEM_PROMPT,
            f"The user wants active shipments.\n\nData:\n{context}\n\nPresent the active shipments in a clear format.",
            max_tokens=300,
        )
        return ChatResponse(reply=reply, action="active_shipments")

    if intent == "delayed_shipments":
        from fulfillment.agents.monitor import MonitorAgent
        agent = MonitorAgent(db)
        shipments = await agent.get_active_shipments()
        delayed = [s for s in shipments if getattr(s, "is_delayed", False)]
        if not delayed:
            logger.info("No delayed shipments")
            reply = await _generate_llm_reply(
                _CHAT_SYSTEM_PROMPT,
                "The user wants delayed shipments but all are on time. Let them know the good news.",
                max_tokens=80,
            )
            return ChatResponse(reply=reply, action="delayed_shipments")
        lines = "\n".join(
            f"#{s.id[:8]} — {s.carrier_name}\n  Reason: {getattr(s, 'delay_reason', 'unknown') or 'unknown'}"
            for s in delayed[:8]
        )
        more = f"\n... and {len(delayed) - 8} more" if len(delayed) > 8 else ""
        context = f"Delayed Shipments: {len(delayed)}\n{lines}{more}"
        logger.info("LLM request sent | intent=delayed_shipments")
        reply = await _generate_llm_reply(
            _CHAT_SYSTEM_PROMPT,
            f"The user wants delayed shipments.\n\nData:\n{context}\n\nPresent the delayed shipments with reasons.",
            max_tokens=300,
        )
        return ChatResponse(reply=reply, action="delayed_shipments")

    if intent == "on_time_shipments":
        from fulfillment.agents.monitor import MonitorAgent
        agent = MonitorAgent(db)
        shipments = await agent.get_active_shipments()
        delayed = [s for s in shipments if getattr(s, "is_delayed", False)]
        on_time = len(shipments) - len(delayed)
        pct = round(on_time / len(shipments) * 100, 1) if shipments else 0
        context = f"On-Time: {on_time} | Delayed: {len(delayed)} | Rate: {pct}%"
        logger.info("LLM request sent | intent=on_time_shipments")
        reply = await _generate_llm_reply(
            _CHAT_SYSTEM_PROMPT,
            f"The user wants on-time shipment stats.\n\nData:\n{context}\n\nPresent the on-time shipment performance.",
            max_tokens=150,
        )
        return ChatResponse(reply=reply, action="on_time_shipments")

    if intent == "high_risk_shipments":
        from fulfillment.agents.monitor import MonitorAgent
        from fulfillment.agents.prediction import PredictionAgent
        monitor = MonitorAgent(db)
        predictor = PredictionAgent(db)
        shipments = await monitor.get_active_shipments()
        high_risk = []
        for s in shipments:
            pred = await predictor.predict_failure(s)
            if pred["risk_level"] == "high":
                high_risk.append(pred)
        if not high_risk:
            logger.info("No high-risk shipments")
            reply = await _generate_llm_reply(
                _CHAT_SYSTEM_PROMPT,
                "The user wants high-risk shipments but there are none. Let them know.",
                max_tokens=80,
            )
            return ChatResponse(reply=reply, action="high_risk_shipments")
        high_risk.sort(key=lambda x: x["failure_probability"], reverse=True)
        lines = "\n".join(
            f"#{p['shipment_id'][:8]} — Risk: {p['failure_probability']:.0%} ({p['tracking_number']})"
            f"\n  Factor: {p['factors'][0]['factor']}: {p['factors'][0]['detail'][:60]}"
            for p in high_risk[:5]
        )
        context = f"High-Risk Shipments: {len(high_risk)}\n{lines}"
        logger.info("LLM request sent | intent=high_risk_shipments")
        reply = await _generate_llm_reply(
            _CHAT_SYSTEM_PROMPT,
            f"The user wants high-risk shipments.\n\nData:\n{context}\n\nPresent the high-risk shipments with risk factors.",
            max_tokens=300,
        )
        return ChatResponse(reply=reply, action="high_risk_shipments")

    if intent == "reroute_list":
        from fulfillment.models.agent_event import AgentEvent
        events_r = await db.execute(
            select(AgentEvent).where(AgentEvent.event_type == "reroute_executed").order_by(AgentEvent.created_at.desc()).limit(20)
        )
        reroute_events = list(events_r.scalars().all())
        if not reroute_events:
            logger.info("No reroutes found")
            reply = await _generate_llm_reply(
                _CHAT_SYSTEM_PROMPT,
                "The user wants reroute history but none have happened. Let them know.",
                max_tokens=80,
            )
            return ChatResponse(reply=reply, action="reroute_list")
        from fulfillment.models.shipment import Shipment as Shp
        lines = []
        for ev in reroute_events[:8]:
            s_r = await db.execute(select(Shp).where(Shp.id == ev.entity_id))
            s = s_r.scalar_one_or_none()
            carrier = s.carrier_name if s else "N/A"
            lines.append(f"#{ev.entity_id[:8] if ev.entity_id else 'N/A'} -> Current carrier: {carrier}")
        context = f"Rerouted Shipments: {len(reroute_events)}\n" + "\n".join(lines)
        logger.info("LLM request sent | intent=reroute_list")
        reply = await _generate_llm_reply(
            _CHAT_SYSTEM_PROMPT,
            f"The user wants reroute history.\n\nData:\n{context}\n\nPresent the rerouted shipments information.",
            max_tokens=300,
        )
        return ChatResponse(reply=reply, action="reroute_list")

    if intent == "cost_analysis":
        from fulfillment.agents.cost_optimizer import CostOptimizer
        optimizer = CostOptimizer(db)
        analysis = await optimizer.analyze_cycle(str(uuid4()))
        if analysis.get("analysis") == "No shipments to analyze":
            logger.info("No cost analysis data available")
            reply = await _generate_llm_reply(
                _CHAT_SYSTEM_PROMPT,
                "The user wants cost analysis but no shipment data is available. Let them know.",
                max_tokens=80,
            )
            return ChatResponse(reply=reply, action="cost_analysis")
        a = analysis["analysis"]
        cheapest = await db.execute(select(Shipment).order_by(Shipment.shipping_cost.asc()).limit(1))
        cheapest_s = cheapest.scalar_one_or_none()
        costliest = await db.execute(select(Shipment).order_by(Shipment.shipping_cost.desc()).limit(1))
        costliest_s = costliest.scalar_one_or_none()
        context = (
            f"Total shipments: {a['total_shipments']}\n"
            f"Total cost: ${a['total_cost']}\n"
            f"Average per shipment: ${a['average_cost']}\n"
        )
        if cheapest_s:
            context += f"Cheapest: #{cheapest_s.id[:8]} ({cheapest_s.carrier_name}) — ${float(cheapest_s.shipping_cost or 0):.2f}\n"
        if costliest_s:
            context += f"Most expensive: #{costliest_s.id[:8]} ({costliest_s.carrier_name}) — ${float(costliest_s.shipping_cost or 0):.2f}\n"
        if analysis["recommendations"]:
            context += "\nRecommendations:\n" + "\n".join(f"- {r['suggestion']}" for r in analysis["recommendations"])
        logger.info("LLM request sent | intent=cost_analysis")
        reply = await _generate_llm_reply(
            _CHAT_SYSTEM_PROMPT,
            f"The user wants shipping cost analysis.\n\nData:\n{context}\n\nPresent the cost analysis with recommendations.",
            max_tokens=400,
        )
        return ChatResponse(reply=reply, action="cost_analysis")

    if intent == "notification_stats":
        from fulfillment.models.notification import Notification
        total_n = await db.execute(select(sqlfunc.count(Notification.id)))
        total = total_n.scalar() or 0
        sent_n = await db.execute(select(sqlfunc.count(Notification.id)).where(Notification.status == "sent"))
        sent = sent_n.scalar() or 0
        failed_n = await db.execute(select(sqlfunc.count(Notification.id)).where(Notification.status == "failed"))
        failed = failed_n.scalar() or 0
        customers_n = await db.execute(select(sqlfunc.count(Notification.recipient.distinct())))
        distinct_customers = customers_n.scalar() or 0
        context = (
            f"Total sent: {sent}\n"
            f"Failed: {failed}\n"
            f"Unique customers notified: {distinct_customers}\n"
            f"Success rate: {round(sent / total * 100, 1) if total else 0}%"
        )
        logger.info("LLM request sent | intent=notification_stats")
        reply = await _generate_llm_reply(
            _CHAT_SYSTEM_PROMPT,
            f"The user wants notification statistics.\n\nData:\n{context}\n\nPresent the notification stats clearly.",
            max_tokens=200,
        )
        return ChatResponse(reply=reply, action="notification_stats")

    if intent == "cycle_stats":
        from fulfillment.agents.monitor import MonitorAgent
        from fulfillment.models.agent_event import AgentEvent
        agent = MonitorAgent(db)
        shipments = await agent.get_active_shipments()
        delayed = sum(1 for s in shipments if getattr(s, "is_delayed", False))
        last_cycle = await db.execute(
            select(AgentEvent).where(AgentEvent.agent_name == "MonitorAgent").order_by(AgentEvent.created_at.desc()).limit(5)
        )
        last_events = list(last_cycle.scalars().all())
        now = datetime.now(timezone.utc)
        context = (
            f"Active shipments: {len(shipments)}\n"
            f"Delayed: {delayed}\n"
            f"On-time: {len(shipments) - delayed}\n"
            f"On-time rate: {round((len(shipments) - delayed) / len(shipments) * 100, 1) if shipments else 0}%\n\n"
        )
        if last_events:
            context += "Recent events:\n" + "\n".join(
                f"- {ev.event_type} at {ev.created_at.strftime('%H:%M')}" for ev in last_events[:3]
            )
        else:
            context += "No recent events"
        logger.info("LLM request sent | intent=cycle_stats")
        reply = await _generate_llm_reply(
            _CHAT_SYSTEM_PROMPT,
            f"The user wants monitor cycle stats.\n\nData ({now.strftime('%b %d, %H:%M')} UTC):\n{context}\n\nPresent the cycle status clearly.",
            max_tokens=300,
        )
        return ChatResponse(reply=reply, action="cycle_stats")

    logger.info("LLM request sent | intent=fallback (no intent matched)")
    reply = await _generate_llm_reply(
        _CHAT_SYSTEM_PROMPT,
        f"The user said: \"{message}\"\n\n"
        f"If they provided an email, create an order. Otherwise, help them understand what they can ask about. "
        f"Available topics: create order, list orders, check status, agents, metrics, "
        f"proceed delivery, filter orders, fulfillment centers, carriers, shipments, "
        f"cost analysis, notifications, cycle stats. Keep it helpful and concise.",
        max_tokens=300,
        fallback="I can help you with: creating orders, listing orders, checking shipment status, agent info, system metrics, delivery routing, and more. What would you like to do?",
    )
    return ChatResponse(reply=reply, action="help")


# ---------------------------------------------------------------------------
# Extraction helpers (data parsing, not response generation)
# ---------------------------------------------------------------------------

def _extract_email(text: str) -> str | None:
    match = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text)
    return match.group(0) if match else None


def _extract_phone(text: str) -> str | None:
    match = re.search(r"[\d\-\+\(\) ]{7,15}", text)
    return match.group(0).strip() if match else None


def _extract_zip(text: str) -> str | None:
    match = re.search(r"\b\d{5,6}\b", text)
    return match.group(0) if match else None


def _extract_weight(text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:kg|kilo|kilogram)", text, re.IGNORECASE)
    return float(match.group(1)) if match else None


def _extract_state(text: str) -> str | None:
    STATES_MAP = {
        "sindh": "Sindh", "punjab": "Punjab", "kpk": "KPK", "khyber": "KPK",
        "balochistan": "Balochistan", "islamabad": "Islamabad",
        "ny": "NY", "new york": "NY", "california": "CA", "ca": "CA",
        "texas": "TX", "tx": "TX", "florida": "FL", "fl": "FL",
        "illinois": "IL", "il": "IL", "pennsylvania": "PA", "pa": "PA",
        "ohio": "OH", "oh": "OH", "georgia": "GA", "ga": "GA",
        "north carolina": "NC", "nc": "NC", "michigan": "MI", "mi": "MI",
        "new jersey": "NJ", "nj": "NJ", "virginia": "VA", "va": "VA",
        "washington": "WA", "wa": "WA", "arizona": "AZ", "az": "AZ",
        "massachusetts": "MA", "ma": "MA", "tennessee": "TN", "tn": "TN",
        "indiana": "IN", "in": "IN", "maryland": "MD", "md": "MD",
        "missouri": "MO", "mo": "MO", "wisconsin": "WI", "wi": "WI",
        "colorado": "CO", "co": "CO", "minnesota": "MN", "mn": "MN",
        "south carolina": "SC", "sc": "SC", "alabama": "AL", "al": "AL",
        "louisiana": "LA", "la": "LA", "kentucky": "KY", "ky": "KY",
        "oregon": "OR", "or": "OR", "oklahoma": "OK", "ok": "OK",
        "connecticut": "CT", "ct": "CT", "utah": "UT", "ut": "UT",
        "iowa": "IA", "ia": "IA", "nevada": "NV", "nv": "NV",
        "arkansas": "AR", "ar": "AR", "mississippi": "MS", "ms": "MS",
        "kansas": "KS", "ks": "KS", "new mexico": "NM", "nm": "NM",
        "nebraska": "NE", "ne": "NE", "idaho": "ID", "id": "ID",
        "west virginia": "WV", "wv": "WV", "hawaii": "HI", "hi": "HI",
        "new hampshire": "NH", "nh": "NH", "maine": "ME", "me": "ME",
        "montana": "MT", "mt": "MT", "rhode island": "RI", "ri": "RI",
        "delaware": "DE", "de": "DE", "south dakota": "SD", "sd": "SD",
        "north dakota": "ND", "nd": "ND", "alaska": "AK", "ak": "AK",
        "vermont": "VT", "vt": "VT", "wyoming": "WY", "wy": "WY",
        "guam": "GU", "puerto rico": "PR", "pr": "PR",
    }
    lower = text.lower()
    for key, value in sorted(STATES_MAP.items(), key=lambda x: -len(x[0])):
        if len(key) <= 2:
            if re.search(rf"\b{key}\b", lower):
                return value
        elif key in lower:
            return value
    return None


def _extract_address(text: str, city: str | None = None) -> str | None:
    patterns = [
        r"(?:address|located at|at|ship to|deliver to|send to)[:\s]+(.+?)(?:\.|,|\n|$)",
        r"\d+\s+(?:street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|lane|ln|court|ct|way|place|pl|circle|cir)\s*(?:#?\s*\d+[a-z]*)?",
        r"(?:house\s*\d+|h\s*#\s*\d+|plot\s*\d+|house\s*no\.?\s*\d+)[^.!?\n]*",
        r"(?:ship to|deliver to|send to)\s+(.+?)(?:,|\n|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            addr = match.group(0).strip()
            addr = re.sub(r"^(?:address|located at|at|ship to|deliver to|send to)[:\s]+", "", addr, flags=re.IGNORECASE)
            return addr.strip()
    return None


def _extract_city(text: str) -> str | None:
    CITY_KEYWORDS = ["karachi", "lahore", "islamabad", "rawalpindi", "faisalabad", "multan", "hyderabad", "gujranwala", "peshawar", "quetta", "sialkot", "bahawalpur", "sargodha", "sukkur", "larkana", "sheikhupura", "mirpur", "muzaffarabad", "gujrat", "mardan", "sahiwal", "new york", "los angeles", "chicago", "houston", "phoenix", "san antonio", "san diego", "dallas", "san jose", "austin", "jacksonville", "fort worth", "columbus", "charlotte", "indianapolis", "san francisco", "seattle", "denver", "nashville", "oklahoma city", "el paso", "washington", "boston", "las vegas", "portland", "memphis", "louisville", "baltimore", "milwaukee", "albuquerque", "tucson", "fresno", "sacramento", "mesa", "kansas city", "atlanta", "omaha", "colorado springs", "raleigh", "long beach", "virginia beach", "miami", "oakland", "minneapolis", "tampa", "tulsa", "arlington", "new orleans"]
    lower = text.lower()
    for kw in CITY_KEYWORDS:
        if kw in lower:
            return kw.title()
    return None


def _extract_notes(text: str) -> str | None:
    patterns = [
        r"(?:note|instruction|remark|special|important|fragile|urgent|please)[:\s]+(.+?)(?:\.|!|\n|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None
