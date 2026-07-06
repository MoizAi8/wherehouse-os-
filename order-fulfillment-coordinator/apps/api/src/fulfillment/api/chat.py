from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends
from openai import AsyncOpenAI
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from fulfillment.api.deps import get_current_user, get_db
from fulfillment.config import settings
from fulfillment.models.order import Order, OrderStatus
from fulfillment.models.shipment import Shipment
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


# ---------------------------------------------------------------------------
# Semantic Intent Classifier (TF-IDF + cosine similarity, no model download)
# ---------------------------------------------------------------------------
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

INTENT_EXAMPLES: dict[str, list[str]] = {
    "greeting": ["hy", "hi", "hello", "hey", "salam", "assalamoalikum", "good morning", "good evening"],
    "help": ["help", "what can you do", "kya kar sakte ho", "commands", "options", "mujhe samjhao", "kya kya kar sakte ho"],
    "create_order": [
        "create order for ahmed gmail com lahore 3kg",
        "place order", "new order", "order karo", "order banao",
        "ahmed ke liye ek order banao",
        "ek order create karo", "order place karo",
    ],
    "list_orders": [
        "list orders", "show all orders", "orders dikhao", "order list",
        "saare orders ki list do", "sab orders dikhao", "my orders",
    ],
    "check_status": ["status", "track order", "kahan hai", "tracking", "where is my order", "order ka status"],
    "agent_count": [
        "how many agents", "active agents", "agent health", "agent status",
        "kitne agents hain", "sab agents ka hal", "agents ki health",
        "kaunse agents active hain",
    ],
    "agent_perf": ["how are agents", "agent perform", "agents performing", "agents ka performance", "agents kaisa perform kar rahe"],
    "metrics": [
        "metrics", "current metrics", "summary", "kpi", "status breakdown",
        "kitne orders hain", "total orders", "system ka current snapshot",
        "numbers explain karo", "sab orders ka status",
    ],
    "insight": [
        "priority", "top priority", "suggest", "recommend", "optimization",
        "sabse zaroori kaam", "cost kam karne ka suggestion",
    ],
    "proceed_delivery": [
        "proceed delivery", "route orders", "process pending", "deliver all",
        "dispatch", "route karo", "sab pending orders ko route karo",
    ],
    "filter_orders": ["pending orders", "delayed orders", "sirf pending dikhao", "delayed ki list"],
    "fulfillment_centers": [
        "fulfillment center", "fc assign", "konsa carrier diya", "carrier kya hai",
        "consa carrier allocate hua", "fulfillment center assign",
    ],
    "carrier_usage": [
        "kaun se carrier use ho rahe", "carrier breakdown", "carrier ko kitne shipment",
        "carrier ka breakdown do", "carriers handle kar rahe",
    ],
    "active_shipments": [
        "active shipments", "shipments chal rahe", "kitne active shipments",
        "current shipments", "shipments ka status kya hai",
    ],
    "delayed_shipments": ["delayed shipments", "delayed hain", "kitne delayed", "delay ki wajah", "konse delayed hain"],
    "on_time_shipments": ["on time shipments", "time chal rahe", "time par shipments", "on time hai"],
    "high_risk_shipments": ["high risk", "failure probability", "risk wale", "zyada risk", "high risk shipments", "risk score"],
    "reroute_list": ["reroute kiye", "reroute huay", "naya carrier", "original carrier", "kitne reroute", "reroute ka record"],
    "cost_analysis": ["cost analysis", "shipping cost", "sasta shipment", "mehnga shipment", "cost kitna", "sabse sasta kaunsa"],
    "notification_stats": ["notifications bheje", "alerts bheje", "unique customers", "kitne notifications", "customers ko notify"],
    "cycle_stats": ["last cycle", "monitor cycle", "workflow cycle", "cycle kab chala", "cycle report", "kya actions hue last cycle"],
    "oldest_pending": ["sabse purana pending", "oldest pending", "jo abhi tak process nahi hua", "sabse pehle wala order", "sabse pehle kaunsa order aaya tha"],
}

INTENT_NAMES = list(INTENT_EXAMPLES.keys())
_all_examples: list[str] = []
_intent_for_example: list[str] = []
for intent, examples in INTENT_EXAMPLES.items():
    for ex in examples:
        _all_examples.append(ex)
        _intent_for_example.append(intent)

_vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), lowercase=True, max_features=2000)
_example_vectors = _vectorizer.fit_transform(_all_examples)

_openai_client: AsyncOpenAI | None = None
if settings.openai_api_key:
    kwargs = dict(api_key=settings.openai_api_key)
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    _openai_client = AsyncOpenAI(**kwargs)

INTENT_DESCRIPTIONS: dict[str, str] = {
    "greeting": "User is greeting or saying hello/hi/salam/assalamoalikum",
    "help": "User is asking what the system can do, needs command list, or requesting help/options",
    "create_order": "User wants to create a new order — mentions customer email, shipping address, city, weight. Keywords: create, place order, new order, order karo, banao, bhejo.",
    "list_orders": "User wants to see all orders or a list of orders. Keywords: list orders, show all orders, orders dikhao, order list, saare orders.",
    "check_status": "User wants to check status of a specific order or shipment. Keywords: status, track, kahan hai, tracking, where is my order.",
    "agent_count": "User wants to know about agents — how many, their health, active status, what each agent does. Keywords: how many agents, agent health, active agents, list agents, agent status, agents ka health.",
    "agent_perf": "User wants to know how agents are performing overall. Keywords: how are agents, agent perform, agents performing, performance.",
    "metrics": "User wants system KPIs, metrics, or order numbers. Keywords: metrics, summary, kpi, current metrics, kitne orders, total orders, sab orders, status breakdown, numbers explain karo.",
    "insight": "User wants suggestions, priorities, recommendations, or optimizations to reduce cost. Keywords: priority, top priority, suggest, recommend, optimize, cost kam karne ke liye suggestion.",
    "proceed_delivery": "User wants to route/process/dispatch all pending orders for delivery. Keywords: proceed delivery, route orders, process pending, deliver all, ship all, dispatch, fulfill, process karo, route karo.",
    "filter_orders": "User wants to filter/see orders by status — pending or delayed orders. Keywords: pending orders, delayed orders, pending list, sirf pending, delayed list.",
    "fulfillment_centers": "User wants to know about fulfillment center assignments, which FC is handling orders, or carrier per order. Keywords: fulfillment center, FC assign, assign kiya, carrier kya hai, konsa carrier.",
    "carrier_usage": "User wants to know which carriers are used, count of shipments per carrier, and total cost per carrier. Keywords: kaun se carrier, carrier use ho rahe, carriers use, carriers ho rahe, carrier ko kitne.",
    "active_shipments": "User wants to see currently active/in-transit shipments and their status (on-time/delayed). Keywords: active shipments, shipments hain, shipments chal rahe, kitne active, current shipments.",
    "delayed_shipments": "User wants to see list of delayed shipments and reasons for delay. Keywords: delayed hain, delayed shipment, kitne delayed, delayed ki list, delay ki wajah.",
    "on_time_shipments": "User wants to see on-time shipments. Keywords: on time shipments, on-time chal rahe, time par shipments.",
    "high_risk_shipments": "User wants to see high-risk shipments or failure predictions. Keywords: high risk, failure probability, risk wale shipments, sabse zyada risk, risk score.",
    "reroute_list": "User wants information about rerouted shipments — history, which ones were rerouted, original vs new carrier. Keywords: reroute kiye, reroute huay, naya carrier, original carrier, reroute ho chuke, kitne reroute.",
    "cost_analysis": "User wants shipping cost analysis details — average cost, min/max cost, cheapest/costliest shipment. Keywords: cost analysis, shipping cost, average cost, sasta shipment, mehnga shipment, cost kitna.",
    "notification_stats": "User wants notification statistics — total sent, how many unique customers received alerts, success/failure. Keywords: notifications bheje, alerts, customers ko notify, successfully send, fail huay.",
    "cycle_stats": "User wants monitor cycle information — last cycle time, workflow cycle status, actions taken in last cycle. Keywords: last cycle, monitor cycle, workflow cycle, cycle kab chala, kab cycle chala, cycle status.",
    "oldest_pending": "User wants to know the oldest/sabse purana pending order that hasn't been processed yet. Keywords: sabse purana, oldest pending, jo abhi tak process nahi hua, sabse pehle wala pending.",
}

INTENT_NAMES = list(INTENT_DESCRIPTIONS.keys())


def _tfidf_classify_intent(text: str) -> str | None:
    """Classify using TF-IDF char-ngram cosine similarity. Returns intent or None."""
    query_vec = _vectorizer.transform([text.lower()])
    from sklearn.metrics.pairwise import cosine_similarity
    scores = cosine_similarity(query_vec, _example_vectors).flatten()
    best_idx = int(scores.argmax())
    best_score = float(scores[best_idx])
    if best_score >= 0.15:
        return _intent_for_example[best_idx]
    return None


async def detect_intent(text: str) -> str:
    """3-layer: TF-IDF semantic → LLM → keyword fallback."""
    # Layer 1: TF-IDF (fast, no API, no model download)
    tfidf_intent = _tfidf_classify_intent(text)
    if tfidf_intent:
        return tfidf_intent
    # Layer 2: LLM (if key available)
    if _openai_client:
        try:
            return await _llm_classify_intent(text)
        except Exception:
            pass
    # Layer 3: keyword fallback
    return _keyword_fallback_intent(text)


async def _llm_classify_intent(text: str) -> str:
    intent_list = "\n".join(f"- {name}: {ex[0]}..." for name, ex in INTENT_EXAMPLES.items())
    prompt = (
        "Classify this query into ONE of these intents. Reply with ONLY the intent name.\n\n"
        f"{intent_list}\n\n"
        f"Query: \"{text}\"\n"
        "Intent:"
    )
    resp = await _openai_client.chat.completions.create(
        model=settings.openai_model or "gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=30,
    )
    raw = resp.choices[0].message.content.strip().lower().rstrip(".")
    intent = raw.replace("-", "_").replace(" ", "_").strip("_")
    if intent in INTENT_NAMES:
        return intent
    for known in INTENT_NAMES:
        if known in raw:
            return known
    return _keyword_fallback_intent(text)


def _keyword_fallback_intent(text: str) -> str:
    """Improved keyword-based fallback with word-boundary regex & token overlap."""
    lower = text.lower().strip()
    if not lower:
        return "help"

    # Token-level matching: collect words
    tokens = set(lower.split())

    # Helper: word-boundary phrase match
    def has_phrase(phrase: str) -> bool:
        return bool(re.search(r'\b' + re.escape(phrase) + r'\b', lower))

    # Helper: any word in a set is present
    def has_any_word(words: set[str]) -> bool:
        return bool(tokens & words)

    # ============= Intent checks ordered by specificity =============

    # High-specificity phrase checks
    if any(has_phrase(p) for p in ["fulfillment center", "fulfillment centre", "fc assign", "assign kiya", "konsa carrier", "carrier kya hai"]):
        return "fulfillment_centers"
    if any(has_phrase(p) for p in ["kaun se carrier", "carrier use ho rahe", "carrier ko kitne", "carriers use ho", "carriers ho rahe"]):
        return "carrier_usage"
    if any(has_phrase(p) for p in ["active shipment", "shipments hain", "shipments chal rahe", "current shipment"]):
        return "active_shipments"
    if any(has_phrase(p) for p in ["delayed shipment", "delayed hain", "kitne delayed", "delayed ki list", "delay ki wajah"]):
        return "delayed_shipments"
    if any(has_phrase(p) for p in ["on time shipment", "on-time chal", "time chal rahe", "time par shipment"]):
        return "on_time_shipments"
    if any(has_phrase(p) for p in ["high risk", "failure probability", "risk wale", "zyada risk", "risk score", "risk mark"]):
        return "high_risk_shipments"
    if any(has_phrase(p) for p in ["reroute kiye", "reroute huay", "reroute ho chuke", "reroute hua", "naya carrier", "original carrier", "kitne reroute", "reroute list"]):
        return "reroute_list"
    if any(has_phrase(p) for p in ["cost analysis", "shipping cost", "average cost", "sasta shipment", "mehnga shipment", "cost kitna", "min cost", "max cost"]):
        return "cost_analysis"
    if any(has_phrase(p) for p in ["notifications bheje", "delay alert", "alerts bheje", "customers ko notify", "successfully send", "fail huay", "unique customer"]):
        return "notification_stats"
    if any(has_phrase(p) for p in ["last cycle", "workflow cycle", "kitne cycle", "cycle kab", "kab chala", "monitor cycle", "cycle status"]):
        return "cycle_stats"
    if any(has_phrase(p) for p in ["sabse purana", "oldest pending", "oldest order", "sabse pehle wala", "jo abhi tak process nahi hua"]):
        return "oldest_pending"

    # Proceed delivery
    if any(has_phrase(p) for p in ["proceed delivery", "route orders", "process pending", "process orders", "deliver all", "ship all", "route all", "dispatch", "fulfill", "process karo", "route karo"]):
        return "proceed_delivery"

    # Create order — careful with bare "create" and "bhejo" (generic)
    if (has_phrase("create order") or has_phrase("place order") or has_phrase("new order") or
        has_phrase("order karo") or has_phrase("order banao") or has_phrase("banao") or
        has_phrase("add order") or has_phrase("order create") or has_phrase("make order")):
        return "create_order"
    # Also catch "create for customer@..." patterns
    if re.search(r'\bcreate\b', lower) and re.search(r'\bfor\b', lower) and ('@' in lower or 'weight' in lower or 'kg' in lower):
        return "create_order"

    # Greeting — only if it's a short greeting
    greeting_tokens = {"hy", "hi", "hello", "hey", "salam", "assalam", "assalamoalikum", "good"}
    if has_any_word(greeting_tokens) and len(tokens) <= 4:
        return "greeting"

    # Agent performance
    if any(has_phrase(p) for p in ["how are agents", "agent perform", "agents performing", "agents ka performance"]):
        return "agent_perf"

    # Agent count/status
    if any(has_phrase(p) for p in ["how many agents", "active agents", "agent health", "agent status",
                                     "agent online", "list agents", "agents list", "health status",
                                     "agents ka health", "sab agents ka", "agents active"]):
        return "agent_count"
    if "agent" in tokens or "agents" in tokens:
        return "agent_count"

    # Metrics / summary
    if any(has_phrase(p) for p in ["metrics", "current metrics", "detailed metrics", "status breakdown",
                                     "kitne orders", "total orders", "sab orders", "numbers explain",
                                     "explain metrics", "stats explain", "kpi", "summary", "summarize"]):
        return "metrics"

    # Priority / insight
    if any(has_phrase(p) for p in ["priority", "top priority", "suggest", "recommend", "optimization",
                                     "optimize", "cost kam", "suggestion", "sabse zaroori",
                                     "zaroori kaam", "kaam kya hai"]):
        return "insight"

    # Filter by status
    is_delayed = has_phrase("delayed")
    is_pending = has_phrase("pending")
    is_list = any(has_phrase(p) for p in ["list orders", "show orders", "all orders", "my orders",
                                            "orders dikhao", "orders list", "order list", "list order"])
    is_status = any(has_phrase(p) for p in ["status", "track", "kahan hai", "tracking"])
    if (is_delayed or is_pending) and (is_list or is_status):
        return "filter_orders"

    # List orders
    if is_list or any(has_phrase(p) for p in ["sare orders", "orders ki list", "saare order", "sab orders dikhao", "sab orders"]):
        return "list_orders"

    # Status check
    if is_status:
        return "check_status"

    # Help
    if any(has_phrase(p) for p in ["help", "what can you do", "kya kar sakte", "commands", "options"]):
        return "help"

    return "help"


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatMessage,
    db: AsyncSession = Depends(get_db),
    _user: dict[str, str] = Depends(get_current_user),
) -> ChatResponse:
    message = body.message.strip()
    intent = await detect_intent(message)
    service = OrderService(db)

    if intent == "greeting":
        return ChatResponse(
            reply=("WalikumSalam! 👋 Main order fulfillment system hoon. Aap kya chahte hain?\n\n"
                   "Order create karne hain, status check karna hai, ya kuch aur?"),
            action="greeting",
        )

    if intent == "help":
        return ChatResponse(
            reply=(
                "🤖 Main yeh kar sakta hoon:\n\n"
                "📦 Order banayein:\n"
                "\"Create order for ahmed@gmail.com, ship to Karachi, weight 2kg\"\n\n"
                "📋 Orders dekhein:\n"
                "\"Show all orders\" ya \"Orders dikhao\"\n\n"
                "🔍 Status check:\n"
                "\"What is the status of my orders?\"\n\n"
                "🚚 Delivery process karo:\n"
                "\"Proceed delivery\" ya \"Route all pending orders\"\n\n"
                "🤖 Agents ke baare mein poochhein:\n"
                "\"Kitne active shipments hain?\" ya \"Agents ka health kya hai?\""
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
            reply_parts.append(f"✅ {len(routed)} orders process ho gaye!")
            for r in routed[:5]:
                reply_parts.append(f"• #{r.order_id[:8]} → {r.carrier_name} (Tracking: {r.tracking_number})")
        if failed:
            reply_parts.append(f"❌ {len(failed)} orders mein issue aaya")
            for f in failed[:3]:
                reply_parts.append(f"• #{f['id']}: {f['reason']}")
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
            f"• #{o.id[:8]} — {o.customer_email} ({o.shipping_city}, {o.shipping_state}) — {o.status}"
            for o in orders[:5]
        )
        extra = f"\n\n(+{total - 5} aur orders hain)" if total > 5 else ""
        return ChatResponse(
            reply=f"📦 {total} Orders\n\n{order_list}{extra}",
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
            f"• #{o.id[:8]} — {o.customer_email} → {o.status}"
            for o in orders
        )
        return ChatResponse(
            reply=f"📋 Recent Orders Status\n\n{order_list}",
            action="check_status",
        )

    if intent == "agent_count":
        from fulfillment.agents.monitor import MonitorAgent
        from fulfillment.models.agent_event import AgentEvent
        from sqlalchemy import func as sqlfunc

        agent = MonitorAgent(db)
        shipments = await agent.get_active_shipments()
        shipment_count = len(shipments)
        delayed_count = sum(1 for s in shipments if getattr(s, "is_delayed", False))

        ev_count_r = await db.execute(select(sqlfunc.count(AgentEvent.id)))
        total_events = ev_count_r.scalar() or 0

        reply = (
            "🤖 7 Agents Active\n\n"
            "1. FulfillmentOrchestrator — sab agents ko coordinate karta hai\n"
            "2. RoutingAgent — order ko konsa carrier aur FC de, yeh decide karta hai\n"
            "3. MonitorAgent — har 15 min mein shipments check karta hai\n"
            "4. PredictionAgent — risk score calculate karta hai\n"
            "5. CostOptimizer — shipping cost analyze karta hai\n"
            "6. ReroutingAgent — alternative carriers evaluate karta hai\n"
            "7. CommunicationAgent — SMS aur email alerts bhejta hai\n\n"
            f"📦 Active shipments: {shipment_count}\n"
            f"⚠️ Delayed: {delayed_count}\n"
            f"📊 Total events logged: {total_events}"
        )
        return ChatResponse(reply=reply, action="agent_count")

    if intent == "agent_perf":
        from fulfillment.agents.monitor import MonitorAgent
        from fulfillment.models.agent_event import AgentEvent
        from sqlalchemy import func as sqlfunc

        agent = MonitorAgent(db)
        shipments = await agent.get_active_shipments()
        total_shipments = len(shipments)
        delayed_count = sum(1 for s in shipments if getattr(s, "is_delayed", False))

        svc = OrderService(db)
        total_orders = await svc.count_orders()
        pending = await svc.count_orders(status_filter="pending")
        processing = await svc.count_orders(status_filter="processing")

        total_shipments_cost_r = await db.execute(select(sqlfunc.sum(Shipment.shipping_cost)))
        total_cost = float(total_shipments_cost_r.scalar() or 0)

        ev_count = await db.execute(select(sqlfunc.count(AgentEvent.id)).where(AgentEvent.agent_name == "MonitorAgent"))
        monitor_events = ev_count.scalar() or 0

        reply = (
            "📊 Agent Performance\n\n"
            f"• FulfillmentOrchestrator — {monitor_events} cycles chal chuke hain\n"
            f"• RoutingAgent — {processing} orders ko carrier assign kiya\n"
            f"• MonitorAgent — {total_shipments} shipments monitor kar raha hai\n"
            f"• PredictionAgent — {total_shipments} shipments ka risk score de raha hai\n"
            f"• CostOptimizer — ${total_cost:.2f} total cost analyze ki\n"
            f"• ReroutingAgent — alternative carriers dekh raha hai\n"
            f"• CommunicationAgent — delay alerts bhej raha hai\n\n"
            f"📦 Active: {total_shipments} | ⚠️ Delayed: {delayed_count}\n"
            f"📋 Total orders: {total_orders} (Pending: {pending})"
        )
        return ChatResponse(reply=reply, action="agent_perf")

    if intent == "metrics":
        total = await service.count_orders()
        pending = await service.count_orders(status_filter="pending")
        delayed = await service.count_orders(status_filter="delayed")
        processing = await service.count_orders(status_filter="processing")

        reply = (
            "📊 System Summary\n\n"
            f"Orders: {total} total\n"
            f"• Pending: {pending}\n"
            f"• Processing: {processing}\n"
            f"• Delayed: {delayed}\n\n"
            "Agents: 7 online — sab active hain\n\n"
            "💡 Top priority dekhni hai? Poochhein 'what is our top priority'"
        )
        return ChatResponse(reply=reply, action="metrics")

    if intent == "insight":
        total_orders = await service.count_orders()
        pending = await service.count_orders(status_filter="pending")

        reply = (
            "🎯 Top Priority\n\n"
            f"{pending} orders abhi pending hain jinhe deliver karna hai.\n"
            "Inhe route karne ke liye 'Proceed delivery' bolein.\n\n"
            f"Total system mein {total_orders} orders hain.\n\n"
            "💡 Chahein to agents ka health dekh sakte hain, ya metrics ka detailed breakdown."
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
            f"• #{o.id[:8]} — {o.customer_email} ({o.shipping_city}, {o.shipping_state})"
            for o in orders[:5]
        )
        label = "⏳ Pending" if filter_status == "pending" else "⚠️ Delayed"
        extra = f"\n\n(+{total - 5} aur hain)" if total > 5 else ""
        return ChatResponse(
            reply=f"{label} Orders: {total}\n\n{order_list}{extra}",
            action="filter_orders",
            data={"total": total, "orders": [OrderRead.model_validate(o).model_dump(mode="json") for o in orders[:5]]},
        )

    if intent == "create_order":
        email = extract_email(message)
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

        zip_code = extract_zip(message)
        city = extract_city(message)
        state = extract_state(message)
        phone = extract_phone(message)
        weight = extract_weight(message)
        notes = extract_notes(message)
        address = extract_address(message) or f"Main Street, {city or 'Karachi'}, {state or 'Sindh'} {zip_code or '74000'}"

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

        return ChatResponse(
            reply=(
                f"✅ Order Created!\n\n"
                f"• Order ID: #{order.id[:8]}\n"
                f"• Customer: {order.customer_email}\n"
                f"• Address: {order.shipping_city}, {order.shipping_state}\n"
                f"• Weight: {order.total_weight_kg} kg\n\n"
                f"Ab yeh order automatically route hoga aur ship ho jayega."
            ),
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
        fc_lines = []
        for fc in fcs:
            fc_lines.append(f"• {fc.name} — {fc.city}, {fc.state} ({fc.current_daily_orders}/{fc.max_daily_orders} orders today)")
        from fulfillment.models import carrier_rate
        processing_orders = await svc.list_orders(status_filter="processing")
        carrier_lines = []
        for o in processing_orders[:8]:
            cr = None
            if o.carrier_id:
                cr_r = await db.execute(select(carrier_rate.CarrierRate).where(carrier_rate.CarrierRate.id == o.carrier_id))
                cr = cr_r.scalar_one_or_none()
            carrier_name = cr.carrier_name if cr else "N/A"
            carrier_lines.append(f"• #{o.id[:8]} — {o.customer_email} → {carrier_name} (Tracking: {o.tracking_number or 'N/A'})")
        parts = [
            f"🏭 Fulfillment Centers\n\n",
            f"Orders: {total} total | Processing: {processing} | Pending: {pending_count}\n",
        ]
        if fc_lines:
            parts.append("\nCenters:\n")
            parts.extend(fc_lines)
        if carrier_lines:
            parts.append("\n\nOrders with Carriers:\n")
            parts.extend(carrier_lines)
        return ChatResponse(
            reply="".join(parts),
            action="fulfillment_centers",
        )

    if intent == "oldest_pending":
        result = await db.execute(
            select(Order).where(Order.status == OrderStatus.PENDING).order_by(Order.created_at.asc()).limit(1)
        )
        oldest = result.scalar_one_or_none()
        if not oldest:
            return ChatResponse(reply="Filhaal koi pending orders nahi hain.", action="oldest_pending")
        created = oldest.created_at
        if created is not None and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        days_waiting = (datetime.now(timezone.utc) - created).days if created else 0
        return ChatResponse(
            reply=(
                f"⏰ Sabse Purana Pending Order\n\n"
                f"• Order: #{oldest.id[:8]}\n"
                f"• Customer: {oldest.customer_email}\n"
                f"• Location: {oldest.shipping_city}, {oldest.shipping_state}\n"
                f"• Weight: {oldest.total_weight_kg} kg\n"
                f"• Created: {oldest.created_at.strftime('%b %d, %Y') if oldest.created_at else 'N/A'}\n"
                f"• ⏳ {days_waiting} din se pending hai!"
            ),
            action="oldest_pending",
        )

    if intent == "carrier_usage":
        from sqlalchemy import func as sqlfunc
        result = await db.execute(
            select(
                Shipment.carrier_name,
                sqlfunc.count(Shipment.id).label("count"),
                sqlfunc.sum(Shipment.shipping_cost).label("total_cost"),
            ).group_by(Shipment.carrier_name)
        )
        rows = result.all()
        if not rows:
            return ChatResponse(reply="Abhi koi carrier use nahi ho raha.", action="carrier_usage")
        parts = ["🚚 Carrier Usage\n"]
        for r in rows:
            parts.append(f"• {r.carrier_name} — {r.count} shipments, ${float(r.total_cost or 0):.2f} total")
        return ChatResponse(reply="\n".join(parts), action="carrier_usage")

    if intent == "active_shipments":
        from fulfillment.agents.monitor import MonitorAgent
        agent = MonitorAgent(db)
        count = await agent.count_active_shipments()
        shipments = await agent.get_active_shipments()
        parts = [f"🚚 Active Shipments: {count}\n"]
        for s in shipments[:8]:
            status = "⚠️" if getattr(s, "is_delayed", False) else "✅"
            parts.append(f"{status} #{s.id[:8]} — {s.carrier_name} ({s.tracking_number})")
        if count > 8:
            parts.append(f"\n... aur {count - 8} shipments")
        return ChatResponse(reply="\n".join(parts), action="active_shipments")

    if intent == "delayed_shipments":
        from fulfillment.agents.monitor import MonitorAgent
        agent = MonitorAgent(db)
        shipments = await agent.get_active_shipments()
        delayed = [s for s in shipments if getattr(s, "is_delayed", False)]
        if not delayed:
            return ChatResponse(reply="✅ Koi delayed shipments nahi hain. Sab on-time hain!", action="delayed_shipments")
        parts = [f"⚠️ Delayed Shipments: {len(delayed)}\n"]
        for s in delayed[:8]:
            reason = getattr(s, "delay_reason", "unknown") or "unknown"
            parts.append(f"• #{s.id[:8]} — {s.carrier_name}\n  Reason: {reason}")
        if len(delayed) > 8:
            parts.append(f"\n... aur {len(delayed) - 8} delayed shipments")
        return ChatResponse(reply="\n".join(parts), action="delayed_shipments")

    if intent == "on_time_shipments":
        from fulfillment.agents.monitor import MonitorAgent
        agent = MonitorAgent(db)
        shipments = await agent.get_active_shipments()
        delayed = [s for s in shipments if getattr(s, "is_delayed", False)]
        on_time = len(shipments) - len(delayed)
        pct = round(on_time / len(shipments) * 100, 1) if shipments else 0
        reply = (
            f"✅ On-Time Shipments: {on_time}\n"
            f"⚠️ Delayed: {len(delayed)}\n"
            f"📊 On-Time Rate: {pct}%"
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
            return ChatResponse(reply="✅ Koi high-risk shipments nahi hain.", action="high_risk_shipments")
        high_risk.sort(key=lambda x: x["failure_probability"], reverse=True)
        parts = [f"🔴 High-Risk Shipments: {len(high_risk)}\n"]
        for p in high_risk[:5]:
            parts.append(f"• #{p['shipment_id'][:8]} — Risk: {p['failure_probability']:.0%} ({p['tracking_number']})")
            for f in p["factors"][:1]:
                parts.append(f"  → {f['factor']}: {f['detail'][:50]}")
        return ChatResponse(reply="\n".join(parts), action="high_risk_shipments")

    if intent == "reroute_list":
        from fulfillment.models.agent_event import AgentEvent
        events_r = await db.execute(
            select(AgentEvent).where(AgentEvent.event_type == "reroute_executed").order_by(AgentEvent.created_at.desc()).limit(20)
        )
        reroute_events = list(events_r.scalars().all())
        if reroute_events:
            parts = [f"🔄 Rerouted Shipments: {len(reroute_events)}\n"]
            for ev in reroute_events[:8]:
                from fulfillment.models.shipment import Shipment as Shp
                s_r = await db.execute(select(Shp).where(Shp.id == ev.entity_id))
                s = s_r.scalar_one_or_none()
                carrier = s.carrier_name if s else "N/A"
                parts.append(f"• #{ev.entity_id[:8] if ev.entity_id else 'N/A'} → Current carrier: {carrier}")
            return ChatResponse(reply="\n".join(parts), action="reroute_list")
        return ChatResponse(reply="🔄 Abhi tak koi reroute nahi hua hai.", action="reroute_list")

    if intent == "cost_analysis":
        from fulfillment.agents.cost_optimizer import CostOptimizer
        optimizer = CostOptimizer(db)
        from uuid import uuid4
        analysis = await optimizer.analyze_cycle(str(uuid4()))
        if analysis.get("analysis") == "No shipments to analyze":
            return ChatResponse(reply="Cost analysis: No shipments available.", action="cost_analysis")
        a = analysis["analysis"]
        cheapest = await db.execute(
            select(Shipment).order_by(Shipment.shipping_cost.asc()).limit(1)
        )
        cheapest_s = cheapest.scalar_one_or_none()
        costliest = await db.execute(
            select(Shipment).order_by(Shipment.shipping_cost.desc()).limit(1)
        )
        costliest_s = costliest.scalar_one_or_none()
        reply = (
            f"💰 Cost Analysis\n\n"
            f"• Total shipments: {a['total_shipments']}\n"
            f"• Total cost: ${a['total_cost']}\n"
            f"• Average per shipment: ${a['average_cost']}\n"
        )
        if cheapest_s:
            reply += f"• ✅ Cheapest: #{cheapest_s.id[:8]} ({cheapest_s.carrier_name}) — ${float(cheapest_s.shipping_cost or 0):.2f}\n"
        if costliest_s:
            reply += f"• 🔴 Most expensive: #{costliest_s.id[:8]} ({costliest_s.carrier_name}) — ${float(costliest_s.shipping_cost or 0):.2f}\n"
        if analysis["recommendations"]:
            reply += "\nSuggestions:\n"
            for rec in analysis["recommendations"]:
                reply += f"• {rec['suggestion']}\n"
        return ChatResponse(reply=reply, action="cost_analysis")

    if intent == "notification_stats":
        from fulfillment.models.notification import Notification
        from sqlalchemy import func as sqlfunc
        total_n = await db.execute(select(sqlfunc.count(Notification.id)))
        total = total_n.scalar() or 0
        sent_n = await db.execute(select(sqlfunc.count(Notification.id)).where(Notification.status == "sent"))
        sent = sent_n.scalar() or 0
        failed_n = await db.execute(select(sqlfunc.count(Notification.id)).where(Notification.status == "failed"))
        failed = failed_n.scalar() or 0
        customers_n = await db.execute(select(sqlfunc.count(Notification.recipient.distinct())))
        distinct_customers = customers_n.scalar() or 0
        reply = (
            f"🔔 Notification Stats\n\n"
            f"• Total sent: {sent}\n"
            f"• Failed: {failed}\n"
            f"• Unique customers notified: {distinct_customers}\n"
            f"• Success rate: {round(sent / total * 100, 1) if total else 0}%"
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
        reply = (
            f"🔄 Last Monitor Cycle ({now.strftime('%b %d, %H:%M')} UTC)\n\n"
            f"• Active shipments: {len(shipments)}\n"
            f"• Delayed: {delayed}\n"
            f"• On-time: {len(shipments) - delayed}\n"
            f"• On-time rate: {round((len(shipments) - delayed) / len(shipments) * 100, 1) if shipments else 0}%\n\n"
            "Recent events:\n"
        )
        if last_events:
            for ev in last_events[:3]:
                reply += f"• {ev.event_type} at {ev.created_at.strftime('%H:%M')}\n"
        else:
            reply += "No recent cycles\n"
        return ChatResponse(reply=reply, action="cycle_stats")

    email = extract_email(message)
    if not email:
        return ChatResponse(
            reply=(
                "🤔 Samajh nahi aaya. Yeh batao kya karna hai:\n\n"
                "📦 Order: \"Create order for ahmed@gmail.com, Lahore, 3kg\"\n"
                "📋 List: \"Show all orders\"\n"
                "🔍 Status: \"What is the status of my orders?\"\n"
                "🚚 Delivery: \"Proceed delivery\"\n\n"
                "🤖 Agents se poochhein:\n"
                "• \"Kitne active shipments hain?\"\n"
                "• \"Delayed shipments ki list do\"\n"
                "• \"Shipping cost analysis do\"\n"
                "• \"High risk shipments konse hain?\"\n"
                "• \"Kaun se carriers use ho rahe hain?\"\n"
                "• \"Sab agents ka health kya hai?\"\n"
                "• \"Sabse purana pending order konsa hai?\"\n"
                "• \"Kitne customers ko alerts bheje?\"\n"
                "• \"Last cycle kab chala tha?\"\n"
                "• \"Reroute kiye gaye shipments ka list do\""
            ),
            action="help",
        )
