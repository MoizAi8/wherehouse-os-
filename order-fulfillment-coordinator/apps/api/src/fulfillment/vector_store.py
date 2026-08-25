from __future__ import annotations

import time
import uuid
from typing import Any

from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from fulfillment.config import settings
from fulfillment.resilience import with_retry, get_circuit_breaker, CircuitBreakerError

import logging
logger = logging.getLogger("fulfillment.vector_store")

_qdrant_client: AsyncQdrantClient | None = None
_openai_client: AsyncOpenAI | None = None
_qdrant_breaker = get_circuit_breaker("qdrant", failure_threshold=3, timeout=30.0)
_openai_breaker = get_circuit_breaker("openai_embeddings", failure_threshold=3, timeout=30.0)


def get_qdrant() -> AsyncQdrantClient | None:
    global _qdrant_client
    if _qdrant_client is None and settings.qdrant_url:
        _qdrant_client = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key if settings.qdrant_api_key else None,
            timeout=10.0,
        )
    return _qdrant_client


def get_openai() -> AsyncOpenAI | None:
    global _openai_client
    if _openai_client is None and settings.openai_api_key:
        _openai_client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
            timeout=15.0,
            max_retries=0,
        )
    return _openai_client


COLLECTIONS: dict[str, int] = {
    "shipment_events": settings.embedding_dimensions,
    "product_catalog": settings.embedding_dimensions,
    "customer_order_history": settings.embedding_dimensions,
    "agent_decisions": settings.embedding_dimensions,
}


async def init_collections() -> None:
    qdrant = get_qdrant()
    if qdrant is None:
        logger.warning("Qdrant not available — skipping collection initialization.")
        return
    try:
        existing = {c.name for c in (await qdrant.get_collections()).collections}
    except Exception as exc:
        logger.warning("Qdrant unreachable — skipping collection initialization. error='%s'", exc)
        return
    for name, size in COLLECTIONS.items():
        if name not in existing:
            await qdrant.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=size, distance=Distance.COSINE),
            )
            logger.info("Qdrant collection created: %s", name)
        else:
            logger.debug("Qdrant collection exists: %s", name)


async def _embed_with_retry(text: str) -> list[float]:
    openai = get_openai()
    if openai is None:
        raise RuntimeError("OPENAI_API_KEY not configured — embeddings unavailable")

    async def _call():
        return await _openai_breaker.call(
            openai.embeddings.create,
            model=settings.embedding_model,
            input=text,
        )

    resp = await with_retry(
        _call,
        max_retries=2,
        base_delay=0.5,
        retry_exceptions=(Exception,),
    )
    return resp.data[0].embedding


async def _qdrant_upsert(collection_name: str, points: list[PointStruct]) -> None:
    qdrant = get_qdrant()
    if qdrant is None:
        logger.debug("Qdrant unavailable, skipping upsert to %s", collection_name)
        return

    async def _call():
        return await _qdrant_breaker.call(
            qdrant.upsert,
            collection_name=collection_name,
            points=points,
        )

    await with_retry(
        _call,
        max_retries=2,
        base_delay=0.5,
        retry_exceptions=(Exception,),
    )


async def _qdrant_query(collection_name: str, vector: list[float], limit: int = 10, query_filter: Filter | None = None) -> list[Any]:
    qdrant = get_qdrant()
    if qdrant is None:
        return []

    async def _call():
        return await _qdrant_breaker.call(
            qdrant.query_points,
            collection_name=collection_name,
            query=vector,
            limit=limit,
            query_filter=query_filter,
        )

    try:
        result = await with_retry(
            _call,
            max_retries=2,
            base_delay=0.5,
            retry_exceptions=(Exception,),
        )
        return list(result.points)
    except CircuitBreakerError:
        logger.warning("Qdrant circuit breaker open, returning empty results")
        return []


async def embed(text: str) -> list[float]:
    return await _embed_with_retry(text)


async def upsert_shipment_event(event: dict[str, Any]) -> None:
    text = (
        f"carrier:{event['carrier']} "
        f"status:{event['status']} "
        f"reason:{event.get('reason', 'none')} "
        f"zip:{event.get('zip_code', 'unknown')}"
    )
    vector = await embed(text)
    await _qdrant_upsert(
        "shipment_events",
        [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "order_id": event["order_id"],
                    "carrier": event["carrier"],
                    "status": event["status"],
                    "risk_score": event.get("risk_score", 0.0),
                    "reason": event.get("reason", ""),
                    "zip_code": event.get("zip_code", ""),
                    "timestamp": event.get("timestamp", str(time.time())),
                },
            )
        ],
    )


async def search_similar_delays(
    carrier: str,
    status: str,
    limit: int = 10,
) -> list[Any]:
    vector = await embed(f"carrier:{carrier} status:{status}")
    return await _qdrant_query(
        "shipment_events",
        vector,
        limit=limit,
        query_filter=Filter(
            must=[FieldCondition(key="carrier", match=MatchValue(value=carrier))]
        ),
    )


async def upsert_product(product: dict[str, Any]) -> None:
    text = (
        f"{product['name']} "
        f"{product['category']} "
        f"{' '.join(product.get('tags', []))}"
    )
    vector = await embed(text)
    await _qdrant_upsert(
        "product_catalog",
        [
            PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"product:{product['sku']}")),
                vector=vector,
                payload={
                    "sku": product["sku"],
                    "name": product["name"],
                    "category": product["category"],
                    "weight_kg": product.get("weight_kg"),
                    "fragile": product.get("fragile", False),
                    "tags": product.get("tags", []),
                },
            )
        ],
    )


async def search_similar_products(query: str, limit: int = 5) -> list[Any]:
    vector = await embed(query)
    return await _qdrant_query("product_catalog", vector, limit=limit)


async def upsert_customer_history(customer: dict[str, Any]) -> None:
    text = (
        f"customer {customer['customer_id']} "
        f"sla:{customer['preferred_sla']} "
        f"value:{customer['avg_order_value']} "
        f"carrier:{customer.get('frequent_carrier', 'any')} "
        f"channel:{customer.get('preferred_channel', 'email')} "
        f"vip:{customer.get('vip', False)}"
    )
    vector = await embed(text)
    await _qdrant_upsert(
        "customer_order_history",
        [
            PointStruct(
                id=customer["customer_id"],
                vector=vector,
                payload=customer,
            )
        ],
    )


async def search_similar_customers(
    sla_tier: str,
    avg_value: float,
    limit: int = 3,
) -> list[Any]:
    vector = await embed(f"sla:{sla_tier} value:{avg_value}")
    return await _qdrant_query("customer_order_history", vector, limit=limit)


async def upsert_agent_decision(decision: dict[str, Any]) -> None:
    text = (
        f"agent:{decision['agent_name']} "
        f"event:{decision['event_type']} "
        f"decision:{decision['decision']} "
        f"outcome:{decision['outcome']}"
    )
    vector = await embed(text)
    await _qdrant_upsert(
        "agent_decisions",
        [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={**decision, "timestamp": str(time.time())},
            )
        ],
    )


async def search_past_decisions(
    agent_name: str,
    event_type: str,
    limit: int = 3,
) -> list[Any]:
    vector = await embed(f"agent:{agent_name} event:{event_type}")
    return await _qdrant_query(
        "agent_decisions",
        vector,
        limit=limit,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="agent_name", match=MatchValue(value=agent_name)
                )
            ]
        ),
    )


def format_decisions_for_agent(results: list[Any]) -> str:
    if not results:
        return "No past decisions found for this scenario."
    lines = ["Past similar decisions:"]
    for r in results:
        p = r.payload
        lines.append(
            f"  - Agent: {p['agent_name']} | "
            f"Decision: {p['decision']} | "
            f"Outcome: {p['outcome']} | "
            f"Similarity: {r.score:.2f}"
        )
    return "\n".join(lines)


async def check_qdrant_connection() -> bool:
    qdrant = get_qdrant()
    if qdrant is None:
        return False
    try:
        await qdrant.get_collections()
        return True
    except Exception:
        return False
