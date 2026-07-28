from __future__ import annotations

import json
import logging
import re
from typing import Any

from openai import AsyncOpenAI

from fulfillment.config import settings

logger = logging.getLogger("fulfillment.intent_analyzer")

INTENT_CONFIGS = {
    "ROUTE_ORDER": {
        "agent": "RoutingAgent",
        "description": "User wants to route an order, create a shipment, assign a warehouse, or make shipping decisions. Roman Urdu: 'order route karo', 'yeh parcel bhejo', 'Lahore bhejo', 'order dispatch karo'",
    },
    "TRACK_SHIPMENT": {
        "agent": "MonitorAgent",
        "description": "User wants to track a shipment, check delivery status, ETA, or delivery progress. Roman Urdu: 'order ka status batao', 'mera parcel kahan hai', 'track karo', 'shipment ka pata lagao', 'kahan pahuncha'",
    },
    "PREDICT_RISK": {
        "agent": "PredictionAgent",
        "description": "User wants delay prediction, failure prediction, risk analysis, or SLA prediction. Roman Urdu: 'kya yeh late hoga', 'risk batao', 'failure ka chance kya hai', 'delay to nahi hoga'",
    },
    "OPTIMIZE_COST": {
        "agent": "CostOptimizer",
        "description": "User wants to reduce shipping cost, find cheapest route, or optimize logistics budget. Roman Urdu: 'cost kam karo', 'sasta route batao', 'shipping me bachat karo', 'kharcha optimize karo'",
    },
    "REROUTE_SHIPMENT": {
        "agent": "ReroutingAgent",
        "description": "User wants to change shipment route, redirect, emergency rerouting, or alternative logistics. Roman Urdu: 'route change karo', 'redirect karo parcel', 'doosra raasta batao', 'reroute karo'",
    },
    "SEND_NOTIFICATION": {
        "agent": "CommunicationAgent",
        "description": "User wants to notify customer via email, SMS, push notification, or customer communication. Roman Urdu: 'customer ko batao', 'SMS karo', 'email bhejo', 'notification bhejo', 'inform karo'",
    },
    "LIST_ORDERS": {
        "agent": "RoutingAgent",
        "description": "User wants to see all orders or a list of orders. Roman Urdu: 'sare orders dikhao', 'list batao', 'order list', 'kitne orders hain'",
    },
    "CHECK_STATUS": {
        "agent": "MonitorAgent",
        "description": "User wants to check status of a specific order or shipment. Roman Urdu: 'order ka status kya hai', 'yeh order kahan hai', 'parcel ka pata lagao'",
    },
    "AGENT_INFO": {
        "agent": "MonitorAgent",
        "description": "User wants to know about agents — how many, their health, active status, or performance. Roman Urdu: 'agents ka haal batao', 'kitne agents hain', 'agent ki performance', 'agent health'",
    },
    "GET_METRICS": {
        "agent": "MonitorAgent",
        "description": "User wants system KPIs, metrics, order numbers, or summary. Roman Urdu: 'system metrics batao', 'KPI dikhao', 'summary do', 'total orders kitne hain'",
    },
    "GET_INSIGHT": {
        "agent": "PredictionAgent",
        "description": "User wants suggestions, priorities, recommendations, or optimizations. Roman Urdu: 'suggestion do', 'kya improve karein', 'recommendation batao', 'priority kya hai'",
    },
    "FILTER_ORDERS": {
        "agent": "MonitorAgent",
        "description": "User wants to filter or view orders by status — pending, delayed, or processing. Roman Urdu: 'pending orders dikhao', 'delayed wale batao', 'jo late hain wo dikhao'",
    },
    "FULFILLMENT_CENTERS": {
        "agent": "RoutingAgent",
        "description": "User wants info about fulfillment center assignments or carrier per order. Roman Urdu: 'fulfillment center ka status', 'kaunsa center hai', 'carrier assignment batao'",
    },
    "CARRIER_USAGE": {
        "agent": "CostOptimizer",
        "description": "User wants to know which carriers are used and cost per carrier. Roman Urdu: 'kaunsi carrier use ho rahi', 'carrier ka cost batao', 'har carrier ka kharcha'",
    },
    "ACTIVE_SHIPMENTS": {
        "agent": "MonitorAgent",
        "description": "User wants currently active or in-transit shipments. Roman Urdu: 'jo shipments chal rahe hain', 'active shipments dikhao', 'transit me kya hai'",
    },
    "DELAYED_SHIPMENTS": {
        "agent": "MonitorAgent",
        "description": "User wants list of delayed shipments and reasons. Roman Urdu: 'late shipments batao', 'delayed ka reason kya hai', 'jo late hain wo dikhao'",
    },
    "ON_TIME_SHIPMENTS": {
        "agent": "MonitorAgent",
        "description": "User wants on-time shipment statistics. Roman Urdu: 'jo time par hain wo batao', 'on-time stats', 'time par pahunchne wale'",
    },
    "HIGH_RISK_SHIPMENTS": {
        "agent": "PredictionAgent",
        "description": "User wants high-risk shipments or failure predictions. Roman Urdu: 'high risk shipments', 'jinme failure ho sakta hai', 'risk wale parcels'",
    },
    "COST_ANALYSIS": {
        "agent": "CostOptimizer",
        "description": "User wants shipping cost analysis details. Roman Urdu: 'cost analysis karo', 'kharche ka hisaab', 'shipping cost detail', 'kitna kharcha aaya'",
    },
    "REROUTE_LIST": {
        "agent": "ReroutingAgent",
        "description": "User wants rerouted shipment history. Roman Urdu: 'reroute ki history', 'jinhe redirect kiya wo batao', 'route change wale shipments'",
    },
    "NOTIFICATION_STATS": {
        "agent": "CommunicationAgent",
        "description": "User wants notification statistics. Roman Urdu: 'kitni notifications bheji', 'notification stats', 'SMS stats batao'",
    },
    "CYCLE_STATS": {
        "agent": "MonitorAgent",
        "description": "User wants monitor cycle information. Roman Urdu: 'monitor cycle ka status', 'cycle stats batao', 'kitni baar check hua'",
    },
    "OLDEST_PENDING": {
        "agent": "MonitorAgent",
        "description": "User wants the oldest pending order. Roman Urdu: 'sabse purana pending order', 'jo sabse pehle aaya wo pending hai'",
    },
    "HELP": {
        "agent": "MonitorAgent",
        "description": "User is asking what the system can do or requesting help. Roman Urdu: 'aap kya kar sakte ho', 'help karo', 'kaise use karein', 'options batao'",
    },
    "GREETING": {
        "agent": "MonitorAgent",
        "description": "User is greeting in any language. Examples: hello, hi, hey, salam, assalamoalaikum, namaste, adaab, kya haal hai, good morning, good evening",
    },
    "CREATE_ORDER": {
        "agent": "RoutingAgent",
        "description": "User wants to create a new order. Roman Urdu: 'naya order banao', 'order create karo', 'ek order lagao', 'new order'",
    },
}

INTENT_NAMES = list(INTENT_CONFIGS.keys())

SYSTEM_PROMPT = (
    "# Intent Analyzer Agent\n\n"
    "## Role\n\n"
    "You are the Intent Analyzer for an Enterprise Multi-Agent AI System.\n\n"
    "Your responsibility is NOT to answer the user's question.\n"
    "Your responsibility is to understand the user's intent regardless of wording "
    "and route the request to the correct specialist agent.\n"
    "Never rely on exact keywords or predefined example questions.\n"
    "Always understand the semantic meaning.\n\n"
    "## Language Support\n\n"
    "Users may write in English, Roman Urdu, or mixed. "
    "Understand the meaning regardless of language. "
    "Same intent in different languages must produce the same result.\n\n"
    "## Available Intents and Agents\n\n"
)
for name, cfg in INTENT_CONFIGS.items():
    SYSTEM_PROMPT += f"- {name} → Agent: {cfg['agent']} — {cfg['description']}\n"

SYSTEM_PROMPT += (
    "\n## Important Rules\n\n"
    "Understand meaning instead of wording. "
    "Different words with the same meaning must map to the same intent.\n\n"
    "Users may use:\n"
    "- Different wording\n"
    "- Broken English\n"
    "- Grammar mistakes\n"
    "- Roman Urdu\n"
    "- Short sentences\n"
    "- Long paragraphs\n\n"
    "Still identify the correct intent.\n\n"
    "If multiple intents exist, set primary in 'intent' and secondary in 'secondary_agents'.\n\n"
    "If information is missing (e.g. 'Track my shipment' without ID), "
    "list what is missing in 'missing_information'.\n\n"
    "## Output Format\n\n"
    "Return ONLY valid JSON. No markdown. No code fences.\n"
    '{\n'
    '  "intent": "INTENT_NAME",\n'
    '  "required_agent": "AgentName",\n'
    '  "confidence": 0.0,\n'
    '  "reason": "Brief reason for this classification",\n'
    '  "missing_information": [],\n'
    '  "secondary_agents": []\n'
    '}\n\n'
    "If unsure, set intent to HELP with low confidence."
)

KEYWORD_FALLBACKS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"\b(track|where|kahan|status|pata\s*laga|pahunch|arrived|delivery\s*progress|consignment)\b", re.IGNORECASE), "TRACK_SHIPMENT", "MonitorAgent"),
    (re.compile(r"\b(cost|price|cheap|sasta|kharacha|kharche|kharcha|budget|expensive|mahanga|save|bache|bchat)\b", re.IGNORECASE), "OPTIMIZE_COST", "CostOptimizer"),
    (re.compile(r"\b(route|ship|deliver|bhej|dispatch|forward|transfer|send)\b", re.IGNORECASE), "ROUTE_ORDER", "RoutingAgent"),
    (re.compile(r"\b(notify|notification|sms|email|inform|alert|bata|intimate)\b", re.IGNORECASE), "SEND_NOTIFICATION", "CommunicationAgent"),
    (re.compile(r"\b(risk|delay|late|predict|failure|fail|chance|probability|hoga|chance)\b", re.IGNORECASE), "PREDICT_RISK", "PredictionAgent"),
    (re.compile(r"\b(reroute|redirect|change\s*route|alter|alternative|doosra\s*raasta)\b", re.IGNORECASE), "REROUTE_SHIPMENT", "ReroutingAgent"),
    (re.compile(r"\b(agent|worker|monitor|health|perform)\b", re.IGNORECASE), "AGENT_INFO", "MonitorAgent"),
    (re.compile(r"\b(metric|kpi|summary|total\s*order|count|kitne)\b", re.IGNORECASE), "GET_METRICS", "MonitorAgent"),
    (re.compile(r"\b(create|new\s*order|naya|order\s*laga|order\s*ban|place)\b", re.IGNORECASE), "CREATE_ORDER", "RoutingAgent"),
    (re.compile(r"\b(list|all\s*order|show|dikha|dikhao|dikhay|sab|sare|sarii|tamam|saare)\b", re.IGNORECASE), "LIST_ORDERS", "RoutingAgent"),
    (re.compile(r"\b(help|can you|kya\s*kar|options|commands|kya\s*ho|guide)\b", re.IGNORECASE), "HELP", "MonitorAgent"),
    (re.compile(r"\b(hello|hi|hey|salam|assalam|namaste|adaab|good\s*morning|good\s*evening|good\s*day|kya\s*haal|howdy|wasup|greeting)\b", re.IGNORECASE), "GREETING", "MonitorAgent"),
    (re.compile(r"\b(pending|delayed|processing|filter)\b", re.IGNORECASE), "FILTER_ORDERS", "MonitorAgent"),
    (re.compile(r"\b(fulfillment|center|warehouse|fc)\b", re.IGNORECASE), "FULFILLMENT_CENTERS", "RoutingAgent"),
    (re.compile(r"\b(carrier|shipping\s*company|courier)\b", re.IGNORECASE), "CARRIER_USAGE", "CostOptimizer"),
    (re.compile(r"\b(active|in.transit|ongoing|current\s*ship)\b", re.IGNORECASE), "ACTIVE_SHIPMENTS", "MonitorAgent"),
    (re.compile(r"\b(delayed|late|overdue|der)\b", re.IGNORECASE), "DELAYED_SHIPMENTS", "MonitorAgent"),
    (re.compile(r"\b(on.time|ontime|timely|schedule)\b", re.IGNORECASE), "ON_TIME_SHIPMENTS", "MonitorAgent"),
    (re.compile(r"\b(high.risk|risk\s*sco|failure\s*pred|vulnerable)\b", re.IGNORECASE), "HIGH_RISK_SHIPMENTS", "PredictionAgent"),
    (re.compile(r"\b(cost.analys|expense.analys|kharche\s*ka\s*hisaab)\b", re.IGNORECASE), "COST_ANALYSIS", "CostOptimizer"),
    (re.compile(r"\b(reroute\s*list|reroute\s*history|redirect\s*history)\b", re.IGNORECASE), "REROUTE_LIST", "ReroutingAgent"),
    (re.compile(r"\b(notification\s*stat|notif\s*count|kitni\s*notification)\b", re.IGNORECASE), "NOTIFICATION_STATS", "CommunicationAgent"),
    (re.compile(r"\b(cycle\s*stat|monitor\s*cycle|last\s*cycle)\b", re.IGNORECASE), "CYCLE_STATS", "MonitorAgent"),
    (re.compile(r"\b(oldest\s*pending|sabse\s*purana|pehla\s*order|first\s*pending)\b", re.IGNORECASE), "OLDEST_PENDING", "MonitorAgent"),
    (re.compile(r"\b(order\s*|insight|suggest|recommend|improve|optimize|priority|suggestion)\b", re.IGNORECASE), "GET_INSIGHT", "PredictionAgent"),
]


class IntentResult:
    def __init__(self, data: dict[str, Any]):
        self.intent: str = data.get("intent", "HELP")
        self.required_agent: str = data.get("required_agent", "MonitorAgent")
        self.confidence: float = data.get("confidence", 0.0)
        self.reason: str = data.get("reason", "")
        self.missing_information: list[str] = data.get("missing_information", [])
        self.secondary_agents: list[str] = data.get("secondary_agents", [])


class IntentAnalyzer:
    def __init__(self, openai_client: AsyncOpenAI | None = None):
        self.client = openai_client
        self.model = settings.openai_model or "gpt-4o-mini"

    def _keyword_fallback(self, text: str) -> IntentResult | None:
        matched: list[tuple[str, str, int]] = []
        for pattern, intent, agent in KEYWORD_FALLBACKS:
            matches = pattern.findall(text)
            if matches:
                matched.append((intent, agent, len(matches)))

        if not matched:
            return None

        matched.sort(key=lambda x: -x[2])
        best = matched[0]
        return IntentResult({
            "intent": best[0],
            "required_agent": best[1],
            "confidence": 0.6,
            "reason": f"Keyword fallback matched pattern for {best[0]}",
            "missing_information": [],
            "secondary_agents": [],
        })

    async def analyze(self, text: str) -> IntentResult:
        if not self.client:
            fallback = self._keyword_fallback(text)
            if fallback:
                return fallback
            return IntentResult({
                "intent": "HELP",
                "required_agent": "MonitorAgent",
                "confidence": 0.3,
                "reason": "AI client not available, using default",
                "missing_information": [],
                "secondary_agents": [],
            })

        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                temperature=0,
                max_tokens=300,
                timeout=6,
            )
            raw = resp.choices[0].message.content.strip()
            raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            data = json.loads(raw)

            if data.get("intent") not in INTENT_NAMES:
                closest = self._find_closest_intent(data.get("intent", ""))
                if closest:
                    data["intent"] = closest
                    data["required_agent"] = INTENT_CONFIGS[closest]["agent"]
                    data["confidence"] = max(data.get("confidence", 0.0) * 0.7, 0.2)
                    data["reason"] = f"Normalized to closest intent: {closest}"

            return IntentResult(data)

        except Exception as e:
            logger.warning("LLM intent analysis failed | error='%s'", e)
            fallback = self._keyword_fallback(text)
            if fallback:
                fallback.reason = f"LLM failed ({e}), used keyword fallback"
                return fallback
            return IntentResult({
                "intent": "HELP",
                "required_agent": "MonitorAgent",
                "confidence": 0.2,
                "reason": f"LLM analysis failed and no keyword match: {e}",
                "missing_information": [],
                "secondary_agents": [],
            })

    def _find_closest_intent(self, name: str) -> str | None:
        clean = name.upper().strip().replace(" ", "_").replace("-", "_")
        if clean in INTENT_NAMES:
            return clean
        for known in INTENT_NAMES:
            if clean in known or known in clean:
                return known
        return None
