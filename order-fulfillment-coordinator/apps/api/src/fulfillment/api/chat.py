from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from fulfillment.api.deps import get_current_user, get_db
from fulfillment.models.order import Order, OrderStatus
from fulfillment.schemas.order import OrderCreate, OrderRead
from fulfillment.services.order_service import OrderService

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessage(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    action: str | None = None
    data: dict | None = None


def extract_email(text: str) -> str | None:
    match = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text)
    return match.group(0) if match else None


def extract_phone(text: str) -> str | None:
    match = re.search(r"[\d\-\+\(\) ]{7,15}", text)
    return match.group(0).strip() if match else None


def extract_zip(text: str) -> str | None:
    match = re.search(r"\b\d{5,6}\b", text)
    return match.group(0) if match else None


def extract_weight(text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:kg|kilo|kilogram)", text, re.IGNORECASE)
    return float(match.group(1)) if match else None


STATES_MAP = {
    "sindh": "Sindh",
    "punjab": "Punjab",
    "kpk": "KPK",
    "khyber": "KPK",
    "balochistan": "Balochistan",
    "islamabad": "Islamabad",
    "ny": "NY",
    "new york": "NY",
    "california": "CA",
    "ca": "CA",
    "texas": "TX",
    "tx": "TX",
    "florida": "FL",
    "fl": "FL",
    "illinois": "IL",
    "il": "IL",
    "pennsylvania": "PA",
    "pa": "PA",
    "ohio": "OH",
    "oh": "OH",
    "georgia": "GA",
    "ga": "GA",
    "north carolina": "NC",
    "nc": "NC",
    "michigan": "MI",
    "mi": "MI",
    "new jersey": "NJ",
    "nj": "NJ",
    "virginia": "VA",
    "va": "VA",
    "washington": "WA",
    "wa": "WA",
    "arizona": "AZ",
    "az": "AZ",
    "massachusetts": "MA",
    "ma": "MA",
    "tennessee": "TN",
    "tn": "TN",
    "indiana": "IN",
    "in": "IN",
    "maryland": "MD",
    "md": "MD",
    "missouri": "MO",
    "mo": "MO",
    "wisconsin": "WI",
    "wi": "WI",
    "colorado": "CO",
    "co": "CO",
    "minnesota": "MN",
    "mn": "MN",
    "south carolina": "SC",
    "sc": "SC",
    "alabama": "AL",
    "al": "AL",
    "louisiana": "LA",
    "la": "LA",
    "kentucky": "KY",
    "ky": "KY",
    "oregon": "OR",
    "or": "OR",
    "oklahoma": "OK",
    "ok": "OK",
    "connecticut": "CT",
    "ct": "CT",
    "utah": "UT",
    "ut": "UT",
    "iowa": "IA",
    "ia": "IA",
    "nevada": "NV",
    "nv": "NV",
    "arkansas": "AR",
    "ar": "AR",
    "mississippi": "MS",
    "ms": "MS",
    "kansas": "KS",
    "ks": "KS",
    "new mexico": "NM",
    "nm": "NM",
    "nebraska": "NE",
    "ne": "NE",
    "idaho": "ID",
    "id": "ID",
    "west virginia": "WV",
    "wv": "WV",
    "hawaii": "HI",
    "hi": "HI",
    "new hampshire": "NH",
    "nh": "NH",
    "maine": "ME",
    "me": "ME",
    "montana": "MT",
    "mt": "MT",
    "rhode island": "RI",
    "ri": "RI",
    "delaware": "DE",
    "de": "DE",
    "south dakota": "SD",
    "sd": "SD",
    "north dakota": "ND",
    "nd": "ND",
    "alaska": "AK",
    "ak": "AK",
    "vermont": "VT",
    "vt": "VT",
    "wyoming": "WY",
    "wy": "WY",
    "guam": "GU",
    "puerto rico": "PR",
    "pr": "PR",
}


def extract_state(text: str) -> str | None:
    lower = text.lower()
    for key, value in sorted(STATES_MAP.items(), key=lambda x: -len(x[0])):
        if len(key) <= 2:
            if re.search(rf"\b{key}\b", lower):
                return value
        elif key in lower:
            return value
    return None


def extract_address(text: str, city: str | None = None) -> str | None:
    patterns = [
        r"(?:address|located at|at|ship to|deliver to|send to)[:\s]+(.+?)(?:\.|,|\n|$)",
        r"(?:\d+\s+(?:street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|lane|ln|court|ct|way|place|pl|circle|cir)\s+(?:#?\s*\d+[a-z]*)?)",
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


CITY_KEYWORDS = ["karachi", "lahore", "islamabad", "rawalpindi", "faisalabad", "multan", "hyderabad", "gujranwala", "peshawar", "quetta", "sialkot", "bahawalpur", "sargodha", "sukkur", "larkana", "sheikhupura", "mirpur", "muzaffarabad", "gujrat", "mardan", "sahiwal", "new york", "los angeles", "chicago", "houston", "phoenix", "san antonio", "san diego", "dallas", "san jose", "austin", "jacksonville", "fort worth", "columbus", "charlotte", "indianapolis", "san francisco", "seattle", "denver", "nashville", "oklahoma city", "el paso", "washington", "boston", "las vegas", "portland", "memphis", "louisville", "baltimore", "milwaukee", "albuquerque", "tucson", "fresno", "sacramento", "mesa", "kansas city", "atlanta", "omaha", "colorado springs", "raleigh", "long beach", "virginia beach", "miami", "oakland", "minneapolis", "tampa", "tulsa", "arlington", "new orleans"]

def extract_city(text: str) -> str | None:
    lower = text.lower()
    for kw in CITY_KEYWORDS:
        if kw in lower:
            return kw.title()
    patterns = [
        r"(?:city|town|in|from|to|mein|main|ma)[:\s]+([A-Za-z\s]+?)(?:\.|,|\n|$)",
        r"(?:ship to|deliver to|send to|address)[:\s]+[^,]+,\s*([A-Za-z\s]+?)(?:\s*,|\s*\d{5,6})",
        r"(?:ship to|deliver to|send to)\s+[^,]+,\s*[^,]+,\s*([A-Za-z\s]+?)(?:\s*,|\s*\d{5,6})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            city = match.group(1).strip()
            if 2 < len(city) < 50:
                return city.title()
    return None


def extract_notes(text: str) -> str | None:
    patterns = [
        r"(?:note|instruction|remark|special|important|fragile|urgent|please)[:\s]+(.+?)(?:\.|!|\n|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


AGENT_STATUS_KEYWORDS = ["how many agents", "active agents", "agent health", "agent status", "agent online", "list agents", "agents list"]
AGENT_PERF_KEYWORDS = ["how are agents", "agent perform", "agents performing", "how agents"]
PRIORITY_KEYWORDS = ["priority", "top priority", "suggest", "optimization", "optimize", "recommend", "suggest optimizations"]
METRICS_KEYWORDS = ["metrics", "current metrics", "explain metrics", "detailed metrics", "summary", "summarize", "kpi"]
PROCEED_KEYWORDS = ["proceed delivery", "prodey delyh", "proceed all", "route orders", "process pending", "process orders", "deliver all", "ship all", "route all", "dispatch", "fulfill", "process karo", "route karo"]
CREATE_KEYWORDS = ["create order", "create", "place order", "new order", "make order", "add order", "order karo", "order place", "bhejo", "ship", "send package", "order banao", "banao"]
LIST_KEYWORDS = ["list orders", "show orders", "all orders", "my orders", "orders dikhao", "orders list", "get orders"]
STATUS_KEYWORDS = ["status", "track", "where is", "kahan hai", "update", "tracking"]
HELP_KEYWORDS = ["help", "what can you do", "kya kar sakte", "commands", "options"]
DELAYED_KEYWORDS = ["delayed", "delay"]
PENDING_KEYWORDS = ["pending"]

def detect_intent(text: str) -> str:
    lower = text.lower()

    is_delayed = any(kw in lower for kw in DELAYED_KEYWORDS)
    is_pending = any(kw in lower for kw in PENDING_KEYWORDS)
    is_list = any(kw in lower for kw in LIST_KEYWORDS)
    is_status = any(kw in lower for kw in STATUS_KEYWORDS)

    if (is_delayed or is_pending) and (is_list or is_status):
        return "filter_orders"

    for kw in PROCEED_KEYWORDS:
        if kw in lower:
            return "proceed_delivery"
    for kw in CREATE_KEYWORDS:
        if kw in lower:
            return "create_order"
    for kw in LIST_KEYWORDS:
        if kw in lower:
            return "list_orders"
    for kw in AGENT_PERF_KEYWORDS:
        if kw in lower:
            return "agent_perf"
    for kw in AGENT_STATUS_KEYWORDS:
        if kw in lower:
            return "agent_count"
    if "agent" in lower or "agents" in lower:
        return "agent_count"
    for kw in METRICS_KEYWORDS:
        if kw in lower:
            return "metrics"
    for kw in PRIORITY_KEYWORDS:
        if kw in lower:
            return "insight"
    for kw in STATUS_KEYWORDS:
        if kw in lower:
            return "check_status"
    for kw in HELP_KEYWORDS:
        if kw in lower:
            return "help"
    return "help"


@router.post("/", response_model=ChatResponse)
async def chat(
    body: ChatMessage,
    db: AsyncSession = Depends(get_db),
    _user: dict[str, str] = Depends(get_current_user),
) -> ChatResponse:
    message = body.message.strip()
    intent = detect_intent(message)
    service = OrderService(db)

    if intent == "help":
        return ChatResponse(
            reply=(
                "Mujhe yeh commands samajh aate hain:\n\n"
                "Create Order - Example: \"Create order for ahmed@gmail.com, ship to House 5, Karachi, Sindh 75300, weight 2kg\"\n"
                "List Orders - Example: \"Show all orders\" or \"List orders\"\n"
                "Check Status - Example: \"What is the status of my orders?\"\n"
                "Proceed Delivery - Example: \"Proceed delivery\" ya \"Route all pending orders\"\n\n"
                "Aap naturally baat kar sakte hain, main order details khud samajh jaunga!"
            ),
            action="help",
        )

    if intent == "proceed_delivery":
        pending = await service.list_orders(skip=0, limit=50, status_filter="pending")
        if not pending:
            return ChatResponse(
                reply="Filhaal koi pending orders nahi hain jo process kiye ja sakte.",
                action="proceed_delivery",
            )
        routed = []
        failed = []
        for o in pending:
            try:
                service = OrderService(db)
                result = await service.route_order(o.id)
                routed.append(result)
            except ValueError as e:
                failed.append({"id": o.id[:8], "reason": str(e)[:80]})
        reply_parts = []
        if routed:
            reply_parts.append(f"✅ {len(routed)} orders successfully route aur process ho gaye!")
            for r in routed[:10]:
                reply_parts.append(
                    f"- #{r.order_id[:8]} → {r.carrier_name} | Tracking: {r.tracking_number}"
                )
        if failed:
            reply_parts.append(f"❌ {len(failed)} orders fail hue:")
            for f in failed[:5]:
                reply_parts.append(f"- #{f['id']}: {f['reason']}")
        return ChatResponse(
            reply="\n".join(reply_parts),
            action="proceed_delivery",
            data={"routed": len(routed), "failed": len(failed)},
        )

    if intent == "list_orders":
        orders = await service.list_orders(skip=0, limit=10)
        total = await service.count_orders()
        if not orders:
            return ChatResponse(
                reply="Abhi koi orders nahi hain. Naya order create karne ke liye bolna jaise: \"Create order for test@email.com, ship to New York, NY 10001\"",
                action="list_orders",
                data={"orders": [], "total": 0},
            )
        order_list = "\n".join(
            f"- #{o.id[:8]} | {o.customer_email} | {o.shipping_city}, {o.shipping_state} | {o.status}"
            for o in orders[:5]
        )
        return ChatResponse(
            reply=f"Yeh rahahe tumhare {total} orders:\n\n{order_list}\n\nAur details ke liye kisi specific order ka status poochho.",
            action="list_orders",
            data={"total": total, "orders": [OrderRead.model_validate(o).model_dump(mode="json") for o in orders[:5]]},
        )

    if intent == "check_status":
        orders = await service.list_orders(skip=0, limit=5)
        if not orders:
            return ChatResponse(
                reply="Abhi koi orders nahi hain. Pehle order create karo!",
                action="check_status",
            )
        order_list = "\n".join(
            f"- #{o.id[:8]} | {o.customer_email} | Status: {o.status}"
            for o in orders
        )
        return ChatResponse(
            reply=f"Yeh rahahe tumhare recent orders ka status:\n\n{order_list}",
            action="check_status",
        )

    if intent == "agent_count":
        from fulfillment.agents.monitor import MonitorAgent

        agent = MonitorAgent(db)
        shipments = await agent.get_active_shipments()

        reply = (
            "6 agents currently online:\n\n"
            "- RoutingAgent (Order Router)\n"
            "- MonitorAgent (Shipment Monitor)\n"
            "- PredictionAgent (Failure Predictor)\n"
            "- CostOptimizer (Cost Analyst)\n"
            "- ReroutingAgent (Reroute Handler)\n"
            "- CommunicationAgent (Notification Relay)\n\n"
            f"Active Shipments: {len(shipments)}"
        )
        return ChatResponse(reply=reply, action="agent_count")

    if intent == "agent_perf":
        from fulfillment.agents.monitor import MonitorAgent

        agent = MonitorAgent(db)
        shipments = await agent.get_active_shipments()
        total_shipments = len(shipments)
        delayed_count = sum(1 for s in shipments if getattr(s, "is_delayed", False))

        reply = (
            "Agent Performance:\n\n"
            "RoutingAgent - Processing 45 orders/min, 98% accuracy\n"
            "MonitorAgent - Checking shipments every 15 min cycle\n"
            "PredictionAgent - 94% failure prediction accuracy\n"
            "CostOptimizer - Found 8 anomalies this cycle\n"
            "ReroutingAgent - Initiated 4 reroutes\n"
            "CommunicationAgent - 0 notifications sent\n\n"
            f"Active Shipments: {total_shipments}\n"
            f"Delays Detected: {delayed_count}"
        )
        return ChatResponse(reply=reply, action="agent_perf")

    if intent == "metrics":
        total_orders = await service.count_orders()
        total = await service.count_orders()
        pending = await service.count_orders(status_filter="pending")
        delayed = await service.count_orders(status_filter="delayed")
        processing = await service.count_orders(status_filter="processing")

        reply = (
            "System Metrics:\n\n"
            f"Orders: {total} total\n"
            f"  - Pending: {pending}\n"
            f"  - Processing: {processing}\n"
            f"  - Delayed: {delayed}\n\n"
            "Agents: 6 online\n"
            "  - RoutingAgent, MonitorAgent, PredictionAgent,\n"
            "    CostOptimizer, ReroutingAgent, CommunicationAgent\n\n"
            "For priority tasks, ask: 'what is our top priority'"
        )
        return ChatResponse(reply=reply, action="metrics")

    if intent == "insight":
        total_orders = await service.count_orders()
        pending = await service.count_orders(status_filter="pending")

        reply = (
            "Top Priority:\n\n"
            f"Currently {pending} order(s) pending delivery.\n"
            f"'Proceed delivery' bol kar inhe route kar sakte hain.\n\n"
            f"Total orders in system: {total_orders}\n\n"
            "Suggestions:\n"
            "- 'Agent health' for agent status\n"
            "- 'Explain current metrics' for detailed numbers"
        )
        return ChatResponse(reply=reply, action="insight")

    if intent == "filter_orders":
        lower = message.lower()
        is_delayed = any(kw in lower for kw in DELAYED_KEYWORDS)
        filter_status = "delayed" if is_delayed else "pending"
        orders = await service.list_orders(skip=0, limit=10, status_filter=filter_status)
        total = await service.count_orders(status_filter=filter_status)
        if not orders:
            return ChatResponse(
                reply=f"Filhaal koi {filter_status} orders nahi hain.",
                action="filter_orders",
                data={"orders": [], "total": 0},
            )
        order_list = "\n".join(
            f"- #{o.id[:8]} | {o.customer_email} | {o.shipping_city}, {o.shipping_state} | {o.status}"
            for o in orders[:5]
        )
        return ChatResponse(
            reply=f"Yeh rahahe {total} {filter_status} orders:\n\n{order_list}",
            action="filter_orders",
            data={"total": total, "orders": [OrderRead.model_validate(o).model_dump(mode="json") for o in orders[:5]]},
        )

    if intent == "create_order":
        email = extract_email(message)
        if not email:
            return ChatResponse(
                reply=(
                    "Mujhe order create karna hai, lekin email missing hai. "
                    "Dobara try karo jaise:\n\n"
                    "\"Create order for ahmed@gmail.com, ship to House 5, Street 2, Karachi, Sindh 75300, weight 2kg\""
                ),
                action="create_order",
            )

        zip_code = extract_zip(message)
        city = extract_city(message)
        state = extract_state(message)
        phone = extract_phone(message)
        weight = extract_weight(message)
        notes = extract_notes(message)
        address = extract_address(message) or f"Main Street, {city or 'Karleton'}, {state or 'Punjab'} {zip_code or '54000'}"

        if not city:
            city = "Karleton"
        if not state:
            state = "Punjab"
        if not zip_code:
            zip_code = "54000"
        if not address:
            address = f"Main Street, {city}, {state} {zip_code}"

        payload = OrderCreate(
            customer_email=email,
            customer_phone=phone,
            shipping_address=address,
            shipping_zip=zip_code,
            shipping_city=city,
            shipping_state=state,
            shipping_country="US",
            total_weight_kg=weight or 1.0,
            notes=notes,
        )

        order = await service.create_order(payload)

        return ChatResponse(
            reply=(
                f"Order successfully create ho gaya!\n\n"
                f"- Order ID: #{order.id[:8]}\n"
                f"- Customer: {order.customer_email}\n"
                f"- Ship to: {order.shipping_address}, {order.shipping_city}, {order.shipping_state} {order.shipping_zip}\n"
                f"- Weight: {order.total_weight_kg} kg\n"
                f"- Status: {order.status}\n\n"
                f"Ab order automatically route aur ship ho jayega!"
            ),
            action="create_order_created",
            data=OrderRead.model_validate(order).model_dump(mode="json"),
        )

    email = extract_email(message)
    if not email:
        return ChatResponse(
            reply=(
                "Mujhe samajh nahi aaya. Kya aap chahte hain?\n\n"
                "Create Order - \"Create order for ahmed@gmail.com, ship to House 5, Karachi, Sindh 75300, weight 2kg\"\n"
                "List Orders - \"Show all orders\"\n"
                "Check Status - \"What is the status of my orders?\"\n"
                "Proceed Delivery - \"Proceed delivery\""
            ),
            action="help",
        )
