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

import logging
logger = logging.getLogger("fulfillment.vector_store")

qdrant: AsyncQdrantClient | None = None
if settings.qdrant_url:
    qdrant = AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key if settings.qdrant_api_key else None,
    )
else:
    logger.warning("QDRANT_URL not set. Vector search features will return empty results.")

openai_client: AsyncOpenAI | None = None
if settings.openai_api_key:
    openai_client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url or None,
    )
else:
    logger.warning("OPENAI_API_KEY not set. Vector search features will return empty results.")

COLLECTIONS: dict[str, int] = {
    "shipment_events": settings.embedding_dimensions,
    "product_catalog": settings.embedding_dimensions,
    "customer_order_history": settings.embedding_dimensions,
    "agent_decisions": settings.embedding_dimensions,
}


async def init_collections() -> None:
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
            print(f"[Qdrant] Collection created: {name}")
        else:
            print(f"[Qdrant] Collection exists: {name}")


async def embed(text: str) -> list[float]:
    if openai_client is None:
        raise RuntimeError("OPENAI_API_KEY not configured — embeddings unavailable")
    resp = await openai_client.embeddings.create(
        model=settings.embedding_model,
        input=text,
    )
    return resp.data[0].embedding


async def upsert_shipment_event(event: dict[str, Any]) -> None:
    if qdrant is None:
        return
    text = (
        f"carrier:{event['carrier']} "
        f"status:{event['status']} "
        f"reason:{event.get('reason', 'none')} "
        f"zip:{event.get('zip_code', 'unknown')}"
    )
    vector = await embed(text)
    await qdrant.upsert(
        collection_name="shipment_events",
        points=[
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
    if qdrant is None:
        return []
    vector = await embed(f"carrier:{carrier} status:{status}")
    result = await qdrant.query_points(
        collection_name="shipment_events",
        query=vector,
        limit=limit,
        query_filter=Filter(
            must=[
                FieldCondition(key="carrier", match=MatchValue(value=carrier))
            ]
        ),
    )
    return list(result.points)


async def upsert_product(product: dict[str, Any]) -> None:
    if qdrant is None:
        return
    text = (
        f"{product['name']} "
        f"{product['category']} "
        f"{' '.join(product.get('tags', []))}"
    )
    vector = await embed(text)
    await qdrant.upsert(
        collection_name="product_catalog",
        points=[
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
    if qdrant is None:
        return []
    vector = await embed(query)
    result = await qdrant.query_points(
        collection_name="product_catalog",
        query=vector,
        limit=limit,
    )
    return list(result.points)


async def upsert_customer_history(customer: dict[str, Any]) -> None:
    if qdrant is None:
        return
    text = (
        f"customer {customer['customer_id']} "
        f"sla:{customer['preferred_sla']} "
        f"value:{customer['avg_order_value']} "
        f"carrier:{customer.get('frequent_carrier', 'any')} "
        f"channel:{customer.get('preferred_channel', 'email')} "
        f"vip:{customer.get('vip', False)}"
    )
    vector = await embed(text)
    await qdrant.upsert(
        collection_name="customer_order_history",
        points=[
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
    if qdrant is None:
        return []
    vector = await embed(f"sla:{sla_tier} value:{avg_value}")
    result = await qdrant.query_points(
        collection_name="customer_order_history",
        query=vector,
        limit=limit,
    )
    return list(result.points)


async def upsert_agent_decision(decision: dict[str, Any]) -> None:
    if qdrant is None:
        return
    text = (
        f"agent:{decision['agent_name']} "
        f"event:{decision['event_type']} "
        f"decision:{decision['decision']} "
        f"outcome:{decision['outcome']}"
    )
    vector = await embed(text)
    await qdrant.upsert(
        collection_name="agent_decisions",
        points=[
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
    if qdrant is None:
        return []
    vector = await embed(f"agent:{agent_name} event:{event_type}")
    result = await qdrant.query_points(
        collection_name="agent_decisions",
        query=vector,
        limit=limit,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="agent_name", match=MatchValue(value=agent_name)
                )
            ]
        ),
    )
    return list(result.points)


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
