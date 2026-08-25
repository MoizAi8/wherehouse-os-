from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func as sqlfunc

from fulfillment.api.deps import get_current_user, get_db
from fulfillment.agents.intent_analyzer import IntentAnalyzer
from fulfillment.config import settings
from fulfillment.models.chat_message import ChatMessageRecord
from fulfillment.models.order import Order, OrderStatus
from fulfillment.models.shipment import Shipment
from fulfillment.schemas.order import OrderCreate, OrderRead
from fulfillment.services.order_service import OrderService
from fulfillment.resilience import with_retry, get_circuit_breaker
from fulfillment.logging_config import log_agent_event, get_correlation_id

logger = logging.getLogger("fulfillment.chat")

_openai_breaker = get_circuit_breaker("openai_chat", failure_threshold=3, timeout=30.0)

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessage(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    session_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    action: str | None = None
    data: dict | None = None
    session_id: str | None = None


class ChatHistoryMessage(BaseModel):
    id: int
    role: str
    content: str


class ChatHistoryResponse(BaseModel):
    session_id: str
    messages: list[ChatHistoryMessage]


_openai_client: AsyncOpenAI | None = None
if settings.openai_api_key:
    _openai_client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url or None,
        timeout=25.0,
        max_retries=0,
    )

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

async def detect_intent(text: str, history: list[tuple[str, str]] | None = None) -> str:
    result = await _intent_analyzer.analyze(text, history=history)
    logger.info(
        "Intent analyzed | intent=%s agent=%s confidence=%.2f reason='%s' missing=%s",
        result.intent, result.required_agent, result.confidence, result.reason, result.missing_information,
    )
    return INTENT_MAP.get(result.intent, "help")


async def _handle_create_order(
    db: AsyncSession, message: str, system_prompt: str
) -> tuple[str, str, dict | None]:
    """Extract order fields, execute the Create Order tool, and build the reply."""
    email = _extract_email(message)
    zip_code = _extract_zip(message)
    city = _extract_city(message)
    state = _extract_state(message) or _infer_state_from_city(city)
    phone = _extract_phone(message)
    weight = _extract_weight(message)
    notes = _extract_notes(message)
    address = _extract_address(message) or (city or "")

    missing = []
    if not email:
        missing.append("email")
    if not city:
        missing.append("city")

    if missing:
        logger.info("create_order missing fields: %s", missing)
        reply = await _generate_llm_reply(
            system_prompt,
            f"The user wants to create an order but is missing required information: {', '.join(missing)}. "
            f"Please provide the {', '.join(missing)} so the order can be created. "
            f"Never use markdown or ** bold formatting.",
            max_tokens=150,
            fallback=f"I need the following information to create an order: {', '.join(missing)}. Please provide them.",
        )
        return reply, "create_order_missing_fields", None

    assert email is not None

    payload = OrderCreate(
        customer_email=email,
        customer_phone=phone,
        shipping_address=address,
        shipping_zip=zip_code or "",
        shipping_city=city or "",
        shipping_state=state or "",
        shipping_country="PK",
        total_weight_kg=weight or 1.0,
        notes=notes,
    )

    service = OrderService(db)
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
        system_prompt,
        f"A new order was created. Details:\n{context}\n\n"
        f"The order was already created. Confirm to the user that their order was created and will be routed. "
        f"Report the real Order ID and details above. Never explain how to create an order, "
        f"never use markdown or ** bold formatting.",
        max_tokens=200,
        fallback=(
            f"Your order was created successfully. Order ID: #{order.id[:8]}, "
            f"customer {order.customer_email}, destination {order.shipping_city}, {order.shipping_state}. "
            f"It will be routed shortly."
        ),
    )
    return reply, "create_order_created", OrderRead.model_validate(order).model_dump(mode="json")


async def _generate_llm_reply(system_prompt: str, user_prompt: str, max_tokens: int = 500, fallback: str | None = None) -> str:
    if not _openai_client:
        return fallback or "AI service is not configured."

    async def _call_openai():
        base_kwargs = {
            "model": settings.openai_model or "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
            "max_tokens": max_tokens,
        }
        return await _openai_breaker.call(
            _openai_client.chat.completions.create,
            **base_kwargs
        )

    try:
        resp = await with_retry(
            _call_openai,
            max_retries=2,
            base_delay=0.5,
            retry_exceptions=(Exception,),
        )
        content = resp.choices[0].message.content
        reply = content.strip() if content else ""
        reply = _sanitize_reply(reply)
        if not reply and fallback:
            logger.info("LLM response empty, using fallback")
            return fallback
        if not reply:
            logger.info("LLM response empty, no fallback available")
            return "I found the information you asked about but couldn't summarize it. Please try rephrasing your question."
        logger.info("LLM response generation received | length=%d", len(reply))
        return reply
    except Exception as e:
        logger.error("LLM response generation failed | error='%s'", e)
        return fallback or "I'm having trouble processing your request right now. Please try again."


_SAFETY_VERDICT_RE = re.compile(
    r"^\s*(?:user|assistant|system)\s*safety\s*:\s*\S+",
    re.IGNORECASE,
)


_MARKDOWN_RE = re.compile(r"(\*\*|__|`|~~)")


def _strip_markdown(reply: str) -> str:
    """Remove markdown artifacts so user-facing replies are always plain text."""
    if not reply:
        return reply
    reply = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", reply)
    reply = _MARKDOWN_RE.sub("", reply)
    reply = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", reply)
    reply = re.sub(r"\n{3,}", "\n\n", reply)
    return reply.strip()


def _sanitize_reply(reply: str) -> str:
    """Strip model-injected safety-verdict lines (e.g. "User Safety: safe")."""
    if not reply:
        return reply
    kept = [line for line in reply.splitlines() if not _SAFETY_VERDICT_RE.match(line.strip())]
    cleaned = _strip_markdown("\n".join(kept))
    if not cleaned:
        logger.info("LLM reply contained only safety verdicts, returning empty")
    return cleaned


async def _load_chat_history(db: AsyncSession, session_id: str, limit: int = 12) -> list[tuple[str, str]]:
    """Return recent (role, content) turns for a session, oldest first."""
    result = await db.execute(
        select(ChatMessageRecord)
        .where(ChatMessageRecord.session_id == session_id)
        .order_by(ChatMessageRecord.id.desc())
        .limit(limit)
    )
    rows = list(result.scalars().all())
    rows.reverse()
    return [(r.role, r.content) for r in rows]


async def _save_chat_message(db: AsyncSession, session_id: str, role: str, content: str) -> None:
    db.add(ChatMessageRecord(session_id=session_id, role=role, content=content))


def _history_section(history: list[tuple[str, str]]) -> str:
    if not history:
        return ""
    lines = "\n".join(f"{role}: {content}" for role, content in history)
    return (
        "\n\n## Conversation Memory\n"
        "The following is the conversation history with this user. Use it to stay "
        "consistent, refer back to earlier facts (like an order they already created), "
        "and never contradict it.\n"
        f"{lines}"
    )


_BASE_SYSTEM_PROMPT = (
    "You are the Warehouse OS AI — an intelligent, professional, and helpful warehouse management assistant.\n\n"
    "You help operators manage autonomous agents, interpret metrics, and optimize fulfillment workflows. "
    "You can engage in natural conversation, answer questions about system status, and assist with order fulfillment tasks.\n\n"
    "## Core Behaviors\n\n"
    "- Always respond in clear, professional English.\n"
    "- Be conversational and solution-oriented — never robotic or template-driven.\n"
    "- Understand the user's real intent before responding.\n"
    "- Use available context (conversation history, system data, tools) to give accurate, specific answers.\n"
    "- If information is missing, ask clarifying questions rather than guessing.\n"
    "- Never hallucinate facts or invent data.\n\n"
    "## Response Style\n\n"
    "- Plain text only — no markdown, bold, italics, code formatting, or decorative symbols.\n"
    "- No emojis, ASCII art, or fancy ornaments.\n"
    "- Keep sentences short and direct. Answer exactly what was asked.\n"
    "- When the system has already performed an action, report the actual result directly.\n"
    "- Never expose internal command syntax, tool names, or raw API details to the user.\n\n"
    "## Available Capabilities (Internal Knowledge)\n\n"
    "You have access to real-time warehouse data through backend functions:\n"
    "- Order management: create, list, check status, filter orders\n"
    "- Shipment tracking: active, delayed, on-time, high-risk shipments\n"
    "- Agent monitoring: 7 specialized agents (Routing, Monitor, Prediction, CostOptimizer, Rerouting, Communication, Orchestrator)\n"
    "- Metrics & analytics: system KPIs, carrier usage, cost analysis, cycle stats\n"
    "- Notifications: SMS/email alerts and statistics\n"
    "- Fulfillment centers: capacity and carrier assignments\n\n"
    "When users ask about these topics, the system automatically fetches relevant data and provides it to you. "
    "Simply report the data naturally in your response.\n\n"
    "## Goal\n\n"
    "Help users operate their warehouse efficiently through natural conversation. "
    "Be the knowledgeable colleague they can rely on for insights, actions, and answers."
)


@router.post("", response_model=ChatResponse)
async def chat(
    request: Request,
    body: ChatMessage,
    db: AsyncSession = Depends(get_db),
    _user: dict[str, str] = Depends(get_current_user),
) -> ChatResponse:
    message = body.message.strip()
    correlation_id = get_correlation_id()
    user_id = _user.get("sub") if _user else None

    log_agent_event("ChatAPI", "request_received", entity_id=correlation_id, details={
        "message_length": len(message),
        "user_id": user_id,
        "session_id": body.session_id,
    })

    session_id = body.session_id or str(uuid4())
    history = await _load_chat_history(db, session_id)
    system_prompt = _BASE_SYSTEM_PROMPT + _history_section(history)
    await _save_chat_message(db, session_id, "user", message)

    async def _respond(reply: str, action: str | None = None, data: dict | None = None) -> ChatResponse:
        await _save_chat_message(db, session_id, "assistant", reply)
        return ChatResponse(reply=reply, action=action, data=data, session_id=session_id)

    intent = await detect_intent(message, history)
    log_agent_event("ChatAPI", "intent_detected", entity_id=session_id, details={
        "intent": intent,
        "message_preview": message[:80],
    })

    service = OrderService(db)

    if intent == "greeting":
        logger.info("LLM request sent | intent=greeting")
        if _openai_client:
            r = await _generate_llm_reply(
                system_prompt,
                f"The user said: \"{message}\"\n\nRespond with a warm, professional greeting. Ask how you can help with their warehouse operations today.",
                max_tokens=100,
            )
            if "trouble" not in r and "not configured" not in r:
                return await _respond(reply=r, action="greeting")
        return await _respond(
            reply="Hello! I'm your Warehouse OS assistant. How can I help you with your warehouse operations today?",
            action="greeting"
        )

    if intent == "help":
        logger.info("LLM request sent | intent=help")
        reply = await _generate_llm_reply(
            system_prompt,
            f"The user is asking for help or guidance. They said: \"{message}\"\n\n"
            f"Give a helpful, conversational overview of what you can assist with — orders, shipments, agents, metrics, analytics. "
            f"Keep it natural and inviting. Don't list commands or syntax. Just explain capabilities in plain language.",
            max_tokens=250,
            fallback=(
                "I can help you with your warehouse operations — creating and tracking orders, checking shipment status, "
                "viewing agent performance, system metrics, cost analysis, and more. Just ask me naturally, like "
                "'Show me pending orders' or 'What's our on-time delivery rate?' What would you like to know?"
            ),
        )
        return await _respond(reply=reply, action="help")

    if intent == "proceed_delivery":
        pending = await service.list_orders(skip=0, limit=50, status_filter="pending")
        if not pending:
            logger.info("No pending orders to process")
            reply = await _generate_llm_reply(
                system_prompt,
                "The user wants to proceed with delivery but there are no pending orders. Let them know politely.",
                max_tokens=80,
            )
            return await _respond(reply=reply, action="proceed_delivery")
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
            system_prompt,
            f"The user requested to process all pending deliveries. Here are the results:\n{data_summary}\n\nSummarize the results for the user in a friendly way.",
            max_tokens=300,
        )
        return await _respond(
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
                system_prompt,
                "The user wants to see orders but there are none. Suggest they create one.",
                max_tokens=80,
            )
            return await _respond(
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
            system_prompt,
            f"The user wants to see all orders. Total orders: {total}.\n\nOrders:\n{order_lines}\n\nPresent the orders in a clean readable format. Never use markdown or ** bold formatting.",
            max_tokens=400,
            fallback=f"You have {total} orders total:\n{order_lines}",
        )
        return await _respond(
            reply=reply,
            action="list_orders",
            data={"total": total, "orders": [OrderRead.model_validate(o).model_dump(mode="json") for o in orders[:10]]},
        )

    if intent == "check_status":
        ref = _extract_order_ref(message)
        if ref:
            looked = await service.get_order(ref)
            if looked is None:
                order_result = await db.execute(
                    select(Order).where(Order.tracking_number == ref).limit(1)
                )
                looked_row = order_result.scalar_one_or_none()
                if looked_row:
                    looked = OrderRead.model_validate(looked_row)
            if looked is None and re.fullmatch(r"[0-9a-f]{8}", ref):
                prefix_result = await db.execute(
                    select(Order).where(Order.id.startswith(ref)).limit(1)
                )
                prefix_row = prefix_result.scalar_one_or_none()
                if prefix_row:
                    looked = OrderRead.model_validate(prefix_row)
            if looked:
                order_lines = (
                    f"# {looked.id}\n"
                    f"Status: {looked.status}\n"
                    f"Customer: {looked.customer_email}\n"
                    f"Tracking: {looked.tracking_number or 'not assigned yet'}\n"
                    f"Destination: {looked.shipping_city}, {looked.shipping_state}"
                )
                logger.info("LLM request sent | intent=check_status | ref=%s found", ref)
                reply = await _generate_llm_reply(
                    system_prompt,
                    f"The user wants the status of order {ref}. The actual order data is:\n{order_lines}\n\n"
                    f"Report the real status of this order from the data above. "
                    f"Never use markdown or ** bold formatting, never invent additional details.",
                    max_tokens=200,
                    fallback=(
                        f"Order status:\n"
                        f"Status: {looked.status}\n"
                        f"Tracking: {looked.tracking_number or 'not assigned yet'}"
                    ),
                )
                return await _respond(
                    reply=reply,
                    action="check_status",
                    data=OrderRead.model_validate(looked).model_dump(mode="json"),
                )
            logger.info("check_status | ref=%s not found", ref)
            reply = await _generate_llm_reply(
                system_prompt,
                f"The user asked for the status of '{ref}' but no order or tracking number matched. "
                f"Tell them honestly that no order was found for that reference. "
                f"Never invent an order, never use markdown or ** bold formatting.",
                max_tokens=120,
                fallback=f"I couldn't find any order matching '{ref}'. Please double-check the order ID or tracking number.",
            )
            return await _respond(reply=reply, action="check_status_not_found", data={"ref": ref})

        orders = await service.list_orders(skip=0, limit=10)
        if not orders:
            logger.info("No orders for status check")
            reply = await _generate_llm_reply(
                system_prompt,
                "The user wants to check order status but there are no orders. Let them know.",
                max_tokens=80,
            )
            return await _respond(reply=reply, action="check_status")
        order_lines = "\n".join(
            f"- #{o.id[:8]} | {o.customer_email} -> {o.status}"
            for o in orders[:10]
        )
        logger.info("LLM request sent | intent=check_status")
        reply = await _generate_llm_reply(
            system_prompt,
            f"The user wants to check order status. Recent orders:\n{order_lines}\n\nPresent the status information clearly. Never use markdown or ** bold formatting.",
            max_tokens=300,
            fallback=f"Recent orders:\n{order_lines}",
        )
        return await _respond(reply=reply, action="check_status")

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
            system_prompt,
            f"The user wants to know about agents and their status.\n\nCurrent system state:\n{context}\n\nPresent the agent information in a clear organized way.",
            max_tokens=400,
        )
        return await _respond(reply=reply, action="agent_count")

    if intent == "agent_perf":
        from fulfillment.agents.monitor import MonitorAgent
        from fulfillment.models.agent_event import AgentEvent

        agent = MonitorAgent(db)
        shipments = await agent.get_active_shipments()
        total_shipments = len(shipments)
        delayed_count = sum(1 for s in shipments if getattr(s, "is_delayed", False))

        svc = OrderService(db)
        total_orders = await svc.count_orders()
        pending_count = await svc.count_orders(status_filter="pending")
        processing_count = await svc.count_orders(status_filter="processing")

        total_cost_r = await db.execute(select(sqlfunc.sum(Shipment.shipping_cost)))
        total_cost = float(total_cost_r.scalar() or 0)

        ev_count = await db.execute(select(sqlfunc.count(AgentEvent.id)).where(AgentEvent.agent_name == "MonitorAgent"))
        monitor_events = ev_count.scalar() or 0

        context = (
            f"FulfillmentOrchestrator: {monitor_events} cycles completed\n"
            f"RoutingAgent: assigned carrier to {processing_count} orders\n"
            f"MonitorAgent: monitoring {total_shipments} shipments\n"
            f"PredictionAgent: scoring {total_shipments} shipments\n"
            f"CostOptimizer: analyzed ${total_cost:.2f} total cost\n"
            f"ReroutingAgent: evaluating alternatives\n"
            f"CommunicationAgent: sending alerts\n\n"
            f"Active: {total_shipments} | Delayed: {delayed_count}\n"
            f"Total orders: {total_orders} (Pending: {pending_count})"
        )
        logger.info("LLM request sent | intent=agent_perf")
        reply = await _generate_llm_reply(
            system_prompt,
            f"The user wants agent performance data.\n\nCurrent performance:\n{context}\n\nPresent the performance data in a clear readable format.",
            max_tokens=400,
        )
        return await _respond(reply=reply, action="agent_perf")

    if intent == "metrics":
        total = await service.count_orders()
        pending_count = await service.count_orders(status_filter="pending")
        delayed_count_result = await db.execute(
            select(sqlfunc.count()).select_from(Shipment).where(Shipment.is_delayed.is_(True))
        )
        delayed_count = delayed_count_result.scalar_one()
        processing_count = await service.count_orders(status_filter="processing")

        context = (
            f"Orders: {total} total\n"
            f"Pending: {pending_count}\n"
            f"Processing: {processing_count}\n"
            f"Delayed: {delayed_count}\n"
            f"Agents: 7 online"
        )
        logger.info("LLM request sent | intent=metrics")
        reply = await _generate_llm_reply(
            system_prompt,
            f"The user wants system metrics and summary.\n\nData:\n{context}\n\nPresent the metrics clearly and suggest what they might want to check next. Never use markdown or ** bold formatting.",
            max_tokens=300,
            fallback=f"Current system metrics: {total} orders total, {pending_count} pending, {processing_count} processing, {delayed_count} delayed, 7 agents online.",
        )
        return await _respond(reply=reply, action="metrics")

    if intent == "insight":
        total_orders = await service.count_orders()
        pending_count = await service.count_orders(status_filter="pending")

        context = (
            f"Total system orders: {total_orders}\n"
            f"Pending orders needing delivery: {pending_count}\n"
            f"Available action: route pending orders with 'Proceed delivery'"
        )
        logger.info("LLM request sent | intent=insight")
        reply = await _generate_llm_reply(
            system_prompt,
            f"The user wants insights and recommendations.\n\nSystem state:\n{context}\n\nProvide actionable insights and recommendations based on this data.",
            max_tokens=300,
        )
        return await _respond(reply=reply, action="insight")

    if intent == "filter_orders":
        lower = message.lower()
        if re.search(r"\b(?:delayed|delay)\b", lower):
            filter_status = "delayed"
            delayed_ids_result = await db.execute(
                select(Shipment.order_id).where(Shipment.is_delayed.is_(True)).limit(10)
            )
            delayed_ids = list(delayed_ids_result.scalars().all())
            orders = []
            total = len(delayed_ids)
            if delayed_ids:
                orders_result = await db.execute(
                    select(Order).where(Order.id.in_(delayed_ids)).order_by(Order.created_at.desc())
                )
                orders = [
                    OrderRead.model_validate(o) for o in orders_result.scalars().all()
                ]
        else:
            filter_status = "pending"
            orders = await service.list_orders(skip=0, limit=10, status_filter=filter_status)
            total = await service.count_orders(status_filter=filter_status)
        if not orders:
            logger.info("No %s orders found", filter_status)
            reply = await _generate_llm_reply(
                system_prompt,
                f"The user wants to see {filter_status} orders but there are none. Let them know.",
                max_tokens=80,
            )
            return await _respond(
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
            system_prompt,
            f"The user wants to see {filter_status} orders. Found {total} {filter_status} orders.\n\nOrders:\n{order_lines}\n\nPresent these {filter_status} orders clearly.",
            max_tokens=300,
        )
        return await _respond(
            reply=reply,
            action="filter_orders",
            data={"total": total, "orders": [OrderRead.model_validate(o).model_dump(mode="json") for o in orders[:8]]},
        )

    if intent == "create_order":
        reply, action, data = await _handle_create_order(db, message, system_prompt)
        return await _respond(reply=reply, action=action, data=data)

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
            "Orders with Carriers:\n" + "\n".join(carrier_lines)
        ) if fc_lines else f"Orders total: {total} | Processing: {processing} | Pending: {pending_count}\nNo fulfillment centers found."
        logger.info("LLM request sent | intent=fulfillment_centers")
        reply = await _generate_llm_reply(
            system_prompt,
            f"The user wants fulfillment center and carrier info.\n\nData:\n{context}\n\nPresent the fulfillment center and carrier information clearly.",
            max_tokens=400,
        )
        return await _respond(reply=reply, action="fulfillment_centers")

    if intent == "oldest_pending":
        oldest_result = await db.execute(
            select(Order).where(Order.status == OrderStatus.PENDING).order_by(Order.created_at.asc()).limit(1)
        )
        oldest = oldest_result.scalar_one_or_none()
        if not oldest:
            logger.info("No pending orders for oldest query")
            reply = await _generate_llm_reply(
                system_prompt,
                "The user wants the oldest pending order but there are none. Let them know.",
                max_tokens=80,
            )
            return await _respond(reply=reply, action="oldest_pending")
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
            system_prompt,
            f"The user wants the oldest pending order.\n\nDetails:\n{context}\n\nPresent this information to the user.",
            max_tokens=200,
        )
        return await _respond(reply=reply, action="oldest_pending")

    if intent == "carrier_usage":
        usage_result = await db.execute(
            select(
                Shipment.carrier_name,
                sqlfunc.count(Shipment.id).label("count"),
                sqlfunc.sum(Shipment.shipping_cost).label("total_cost"),
            ).group_by(Shipment.carrier_name)
        )
        rows = usage_result.all()
        if not rows:
            logger.info("No carrier usage data")
            reply = await _generate_llm_reply(
                system_prompt,
                "The user wants carrier usage info but no carriers are being used. Let them know.",
                max_tokens=80,
            )
            return await _respond(reply=reply, action="carrier_usage")
        lines = "\n".join(
            f"{r.carrier_name}: {r.count} shipments, ${float(r.total_cost or 0):.2f} total"
            for r in rows
        )
        logger.info("LLM request sent | intent=carrier_usage")
        reply = await _generate_llm_reply(
            system_prompt,
            f"The user wants carrier usage data.\n\nCarrier usage:\n{lines}\n\nPresent carrier usage info clearly.",
            max_tokens=300,
        )
        return await _respond(reply=reply, action="carrier_usage")

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
            system_prompt,
            f"The user wants active shipments.\n\nData:\n{context}\n\nPresent the active shipments in a clear format.",
            max_tokens=300,
        )
        return await _respond(reply=reply, action="active_shipments")

    if intent == "delayed_shipments":
        from fulfillment.agents.monitor import MonitorAgent
        agent = MonitorAgent(db)
        active = await agent.get_active_shipments()
        delayed = [s for s in active if getattr(s, "is_delayed", False)]
        if not delayed:
            logger.info("No delayed shipments")
            reply = await _generate_llm_reply(
                system_prompt,
                "The user wants delayed shipments but all are on time. Let them know the good news.",
                max_tokens=80,
            )
            return await _respond(reply=reply, action="delayed_shipments")
        lines = "\n".join(
            f"#{s.id[:8]} — {s.carrier_name}\n  Reason: {getattr(s, 'delay_reason', 'unknown') or 'unknown'}"
            for s in delayed[:8]
        )
        more = f"\n... and {len(delayed) - 8} more" if len(delayed) > 8 else ""
        context = f"Delayed Shipments: {len(delayed)}\n{lines}{more}"
        logger.info("LLM request sent | intent=delayed_shipments")
        reply = await _generate_llm_reply(
            system_prompt,
            f"The user wants delayed shipments.\n\nData:\n{context}\n\nPresent the delayed shipments with reasons.",
            max_tokens=300,
        )
        return await _respond(reply=reply, action="delayed_shipments")

    if intent == "on_time_shipments":
        from fulfillment.agents.monitor import MonitorAgent
        agent = MonitorAgent(db)
        active = await agent.get_active_shipments()
        delayed_ships = [s for s in active if getattr(s, "is_delayed", False)]
        on_time = len(active) - len(delayed_ships)
        pct = round(on_time / len(active) * 100, 1) if active else 0
        context = f"On-Time: {on_time} | Delayed: {len(delayed_ships)} | Rate: {pct}%"
        logger.info("LLM request sent | intent=on_time_shipments")
        reply = await _generate_llm_reply(
            system_prompt,
            f"The user wants on-time shipment stats.\n\nData:\n{context}\n\nPresent the on-time shipment performance.",
            max_tokens=150,
        )
        return await _respond(reply=reply, action="on_time_shipments")

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
                system_prompt,
                "The user wants high-risk shipments but there are none. Let them know.",
                max_tokens=80,
            )
            return await _respond(reply=reply, action="high_risk_shipments")
        high_risk.sort(key=lambda x: x["failure_probability"], reverse=True)
        lines = "\n".join(
            f"#{p['shipment_id'][:8]} — Risk: {p['failure_probability']:.0%} ({p['tracking_number']})"
            f"\n  Factor: {p['factors'][0]['factor']}: {p['factors'][0]['detail'][:60]}"
            for p in high_risk[:5]
        )
        context = f"High-Risk Shipments: {len(high_risk)}\n{lines}"
        logger.info("LLM request sent | intent=high_risk_shipments")
        reply = await _generate_llm_reply(
            system_prompt,
            f"The user wants high-risk shipments.\n\nData:\n{context}\n\nPresent the high-risk shipments with risk factors.",
            max_tokens=300,
        )
        return await _respond(reply=reply, action="high_risk_shipments")

    if intent == "reroute_list":
        from fulfillment.models.agent_event import AgentEvent
        events_r = await db.execute(
            select(AgentEvent).where(AgentEvent.event_type == "reroute_executed").order_by(AgentEvent.created_at.desc()).limit(20)
        )
        reroute_events = list(events_r.scalars().all())
        if not reroute_events:
            logger.info("No reroutes found")
            reply = await _generate_llm_reply(
                system_prompt,
                "The user wants reroute history but none have happened. Let them know.",
                max_tokens=80,
            )
            return await _respond(reply=reply, action="reroute_list")
        from fulfillment.models.shipment import Shipment as Shp
        reroute_lines: list[str] = []
        for ev in reroute_events[:8]:
            s_r = await db.execute(select(Shp).where(Shp.id == ev.entity_id))
            found_shipment = s_r.scalar_one_or_none()
            carrier = found_shipment.carrier_name if found_shipment else "N/A"
            reroute_lines.append(f"#{ev.entity_id[:8] if ev.entity_id else 'N/A'} -> Current carrier: {carrier}")
        context = f"Rerouted Shipments: {len(reroute_events)}\n" + "\n".join(reroute_lines)
        logger.info("LLM request sent | intent=reroute_list")
        reply = await _generate_llm_reply(
            system_prompt,
            f"The user wants reroute history.\n\nData:\n{context}\n\nPresent the rerouted shipments information.",
            max_tokens=300,
        )
        return await _respond(reply=reply, action="reroute_list")

    if intent == "cost_analysis":
        from fulfillment.agents.cost_optimizer import CostOptimizer
        optimizer = CostOptimizer(db)
        analysis = await optimizer.analyze_cycle(str(uuid4()))
        if analysis.get("analysis") == "No shipments to analyze":
            logger.info("No cost analysis data available")
            reply = await _generate_llm_reply(
                system_prompt,
                "The user wants cost analysis but no shipment data is available. Let them know.",
                max_tokens=80,
            )
            return await _respond(reply=reply, action="cost_analysis")
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
            system_prompt,
            f"The user wants shipping cost analysis.\n\nData:\n{context}\n\nPresent the cost analysis with recommendations.",
            max_tokens=400,
        )
        return await _respond(reply=reply, action="cost_analysis")

    if intent == "notification_stats":
        from fulfillment.models.notification import Notification
        total_n = await db.execute(select(sqlfunc.count(Notification.id)))
        total = total_n.scalar() or 0
        sent_n = await db.execute(select(sqlfunc.count(Notification.id)).where(Notification.status == "sent"))
        sent = sent_n.scalar() or 0
        failed_n = await db.execute(select(sqlfunc.count(Notification.id)).where(Notification.status == "failed"))
        failed_count = failed_n.scalar() or 0
        customers_n = await db.execute(select(sqlfunc.count(Notification.recipient.distinct())))
        distinct_customers = customers_n.scalar() or 0
        context = (
            f"Total sent: {sent}\n"
            f"Failed: {failed_count}\n"
            f"Unique customers notified: {distinct_customers}\n"
            f"Success rate: {round(sent / total * 100, 1) if total else 0}%"
        )
        logger.info("LLM request sent | intent=notification_stats")
        reply = await _generate_llm_reply(
            system_prompt,
            f"The user wants notification statistics.\n\nData:\n{context}\n\nPresent the notification stats clearly.",
            max_tokens=200,
        )
        return await _respond(reply=reply, action="notification_stats")

    if intent == "cycle_stats":
        from fulfillment.agents.monitor import MonitorAgent
        from fulfillment.models.agent_event import AgentEvent
        agent = MonitorAgent(db)
        shipments = await agent.get_active_shipments()
        delayed_count = sum(1 for s in shipments if getattr(s, "is_delayed", False))
        last_cycle = await db.execute(
            select(AgentEvent).where(AgentEvent.agent_name == "MonitorAgent").order_by(AgentEvent.created_at.desc()).limit(5)
        )
        last_events = list(last_cycle.scalars().all())
        now = datetime.now(timezone.utc)
        context = (
            f"Active shipments: {len(shipments)}\n"
            f"Delayed: {delayed_count}\n"
            f"On-time: {len(shipments) - delayed_count}\n"
            f"On-time rate: {round((len(shipments) - delayed_count) / len(shipments) * 100, 1) if shipments else 0}%\n\n"
        )
        if last_events:
            context += "Recent events:\n" + "\n".join(
                f"- {ev.event_type} at {ev.created_at.strftime('%H:%M')}" for ev in last_events[:3]
            )
        else:
            context += "No recent events"
        logger.info("LLM request sent | intent=cycle_stats")
        reply = await _generate_llm_reply(
            system_prompt,
            f"The user wants monitor cycle stats.\n\nData ({now.strftime('%b %d, %H:%M')} UTC):\n{context}\n\nPresent the cycle status clearly.",
            max_tokens=300,
        )
        return await _respond(reply=reply, action="cycle_stats")

    email = _extract_email(message)
    if email:
        logger.info("LLM request sent | intent=fallback (create_order via email) | email='%s'", email)
        return await _handle_create_order(db, message, system_prompt)

    logger.info("LLM request sent | intent=fallback (no intent matched)")
    reply = await _generate_llm_reply(
        system_prompt,
        f"The user said: \"{message}\"\n\n"
        f"They may be asking something outside the predefined intents, or just chatting naturally. "
        f"Respond helpfully and conversationally. If it seems like a warehouse-related question, "
        f"guide them toward what you can help with (orders, shipments, agents, metrics, analytics). "
        f"Keep it natural and concise. Never use markdown or ** bold formatting.",
        max_tokens=250,
        fallback=(
            "I'm here to help with your warehouse operations. You can ask me about orders, "
            "shipments, agent performance, metrics, or anything else fulfillment-related. "
            "What would you like to know?"
        ),
    )
    return await _respond(reply=reply, action="help")


@router.get("/history", response_model=ChatHistoryResponse)
async def chat_history(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict[str, str] = Depends(get_current_user),
) -> ChatHistoryResponse:
    result = await db.execute(
        select(ChatMessageRecord)
        .where(ChatMessageRecord.session_id == session_id)
        .order_by(ChatMessageRecord.id.asc())
        .limit(200)
    )
    rows = list(result.scalars().all())
    messages = [
        ChatHistoryMessage(id=r.id, role=r.role, content=r.content)
        for r in rows
    ]
    return ChatHistoryResponse(session_id=session_id, messages=messages)


# ---------------------------------------------------------------------------
# Extraction helpers (data parsing, not response generation)
# ---------------------------------------------------------------------------

def _extract_email(text: str) -> str | None:
    match = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text)
    return match.group(0) if match else None


def _infer_state_from_city(city: str | None) -> str | None:
    """Map a known city to its state/province. Falls back to the state extractor's map."""
    if not city:
        return None
    lower = city.lower()
    city_state = {
        "karachi": "Sindh", "hyderabad": "Sindh", "sukkur": "Sindh", "larkana": "Sindh",
        "lahore": "Punjab", "faisalabad": "Punjab", "multan": "Punjab", "gujranwala": "Punjab",
        "rawalpindi": "Punjab", "sialkot": "Punjab", "bahawalpur": "Punjab", "sargodha": "Punjab",
        "sheikhupura": "Punjab", "gujrat": "Punjab", "sahiwal": "Punjab", "mardan": "KPK",
        "peshawar": "KPK", "quetta": "Balochistan", "islamabad": "Islamabad",
        "mirpur": "AJK", "muzaffarabad": "AJK",
        "new york": "NY", "los angeles": "CA", "chicago": "IL", "houston": "TX",
        "phoenix": "AZ", "san antonio": "TX", "san diego": "CA", "dallas": "TX",
        "san jose": "CA", "austin": "TX", "jacksonville": "FL", "fort worth": "TX",
        "columbus": "OH", "charlotte": "NC", "indianapolis": "IN", "san francisco": "CA",
        "seattle": "WA", "denver": "CO", "nashville": "TN", "oklahoma city": "OK",
        "el paso": "TX", "washington": "DC", "boston": "MA", "las vegas": "NV",
        "portland": "OR", "memphis": "TN", "louisville": "KY", "baltimore": "MD",
        "milwaukee": "WI", "albuquerque": "NM", "tucson": "AZ", "fresno": "CA",
        "sacramento": "CA", "mesa": "AZ", "kansas city": "MO", "atlanta": "GA",
        "omaha": "NE", "colorado springs": "CO", "raleigh": "NC", "long beach": "CA",
        "virginia beach": "VA", "miami": "FL", "oakland": "CA", "minneapolis": "MN",
        "tampa": "FL", "tulsa": "OK", "arlington": "TX", "new orleans": "LA",
    }
    return city_state.get(lower)


def _extract_order_ref(text: str) -> str | None:
    """Extract an order ID or tracking number reference from the message."""
    match = re.search(r"\bTRK-[A-Z0-9]+\b", text, re.IGNORECASE)
    if match:
        return match.group(0).upper()
    match = re.search(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        text,
        re.IGNORECASE,
    )
    if match:
        return match.group(0)
    match = re.search(r"\bORD[-_][A-Za-z0-9]+\b", text, re.IGNORECASE)
    if match:
        return match.group(0)
    match = re.search(r"\border\s+(?:id|no\.?|#)?\s*([0-9a-f]{8})\b", text, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


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
        r"\b\d{1,5}\s+[A-Za-z0-9.\-]+(?:\s+[A-Za-z0-9.\-]+)*?\s+(?:street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|lane|ln|court|ct|way|place|pl|circle|cir|highway|hwy)\b",
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
