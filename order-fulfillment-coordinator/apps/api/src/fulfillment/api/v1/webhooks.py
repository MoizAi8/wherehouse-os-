from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from fulfillment.api.deps import get_db
from fulfillment.config import settings
from fulfillment.schemas.webhook import OrderPlacedWebhook, ShipmentEventWebhook, WebhookResponse
from fulfillment.services.order_service import OrderService
from fulfillment.services.shipment_service import ShipmentService

logger = logging.getLogger("fulfillment.webhooks")

router = APIRouter()


async def verify_signature(request: Request, x_webhook_signature: Annotated[str | None, Header()] = None) -> None:
    if not settings.webhook_secret or settings.webhook_secret == "change-webhook-secret":
        if settings.debug:
            logger.warning("Webhook signature verification skipped (DEBUG mode, WEBHOOK_SECRET unset/insecure)")
            return
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook verification is not configured (WEBHOOK_SECRET missing)",
        )
    body = await request.body()
    expected = hmac.new(
        settings.webhook_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    if not x_webhook_signature or not hmac.compare_digest(x_webhook_signature, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )


@router.post("/order-placed", response_model=WebhookResponse, dependencies=[Depends(verify_signature)])
async def webhook_order_placed(
    payload: OrderPlacedWebhook,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WebhookResponse:
    service = OrderService(db)
    try:
        order = await service.create_order_from_webhook(payload)
        return WebhookResponse(success=True, message="Order created", order_id=str(order.id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except Exception as exc:  # pragma: no cover
        logger.exception("Failed to process order webhook: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook",
        )


@router.post("/shipment-event", response_model=WebhookResponse, dependencies=[Depends(verify_signature)])
async def webhook_shipment_event(
    payload: ShipmentEventWebhook,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WebhookResponse:
    service = ShipmentService(db)
    try:
        shipment = await service.update_from_event(payload)
        return WebhookResponse(
            success=True,
            message="Shipment event processed",
            order_id=str(shipment.id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:  # pragma: no cover
        logger.exception("Failed to process shipment webhook: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process shipment event",
        )