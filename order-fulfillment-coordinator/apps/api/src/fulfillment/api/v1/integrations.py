from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from fulfillment.api.deps import get_db, get_current_user, require_operator_or_admin
from fulfillment.encryption import encrypt_secret
from fulfillment.models.integration import IntegrationConnection
from fulfillment.models.order import Order, OrderStatus
from fulfillment.schemas.integration import (
    IntegrationConnectRequest,
    IntegrationConnectionRead,
    IntegrationConnectionStatus,
    OdooSearchRequest,
    OdooSearchResult,
    SyncResult,
)
from fulfillment.services.odoo_client import OdooClient, OdooError
from fulfillment.tools.integrations import _odoo_client

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/connect", response_model=IntegrationConnectionRead)
async def connect_integration(
    payload: IntegrationConnectRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict[str, str] = Depends(require_operator_or_admin),
) -> IntegrationConnectionRead:
    existing = await db.execute(
        select(IntegrationConnection).where(
            IntegrationConnection.provider == payload.provider,
            IntegrationConnection.base_url == payload.base_url,
        )
    )
    conn = existing.scalar_one_or_none()

    if payload.provider == "odoo":
        if not payload.password and not payload.api_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="password or api_key required for Odoo",
            )
        secret = payload.password or payload.api_key
        client = OdooClient(
            url=payload.base_url,
            db=payload.db,
            username=payload.username,
            password=secret,
            verify_ssl=payload.verify_ssl,
        )
        try:
            status_result = await client.check_connection()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Connection failed: {exc}",
            )
        finally:
            await client.close()

        if not status_result["connected"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=status_result.get("error", "Unknown connection error"),
            )

        if conn is None:
            conn = IntegrationConnection(
                id=str(uuid4()),
                provider="odoo",
                label=payload.label or f"Odoo — {payload.base_url}",
                base_url=payload.base_url,
                db_name=payload.db,
                username=payload.username,
                api_key=encrypt_secret(secret),
                is_connected=True,
                sync_status="connected",
                version=status_result.get("version"),
                error_message=None,
            )
            db.add(conn)
        else:
            conn.is_connected = True
            conn.sync_status = "connected"
            conn.version = status_result.get("version")
            conn.error_message = None
            if payload.label:
                conn.label = payload.label
            conn.api_key = encrypt_secret(secret)
            conn.db_name = payload.db
            conn.username = payload.username
            conn.base_url = payload.base_url
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider: {payload.provider}",
        )

    await db.flush()
    await db.refresh(conn)
    return IntegrationConnectionRead.model_validate(conn)


@router.get("/connections", response_model=list[IntegrationConnectionRead])
async def list_connections(
    db: AsyncSession = Depends(get_db),
    _user: dict[str, str] = Depends(get_current_user),
) -> list[IntegrationConnectionRead]:
    result = await db.execute(
        select(IntegrationConnection).order_by(IntegrationConnection.created_at.desc())
    )
    return [IntegrationConnectionRead.model_validate(c) for c in result.scalars().all()]


@router.get("/connections/{connection_id}", response_model=IntegrationConnectionRead)
async def get_connection(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict[str, str] = Depends(get_current_user),
) -> IntegrationConnectionRead:
    result = await db.execute(
        select(IntegrationConnection).where(IntegrationConnection.id == connection_id)
    )
    conn = result.scalar_one_or_none()
    if conn is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    return IntegrationConnectionRead.model_validate(conn)


@router.post("/connections/{connection_id}/test", response_model=IntegrationConnectionStatus)
async def test_connection(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict[str, str] = Depends(require_operator_or_admin),
) -> IntegrationConnectionStatus:
    result = await db.execute(
        select(IntegrationConnection).where(IntegrationConnection.id == connection_id)
    )
    conn = result.scalar_one_or_none()
    if conn is None:
        raise HTTPException(status_code=404, detail="Connection not found")

    if conn.provider != "odoo":
        raise HTTPException(status_code=400, detail="Only Odoo connections supported for now")

    client = _odoo_client(conn)
    try:
        status_result = await client.check_connection()
        conn.is_connected = status_result["connected"]
        conn.version = status_result.get("version")
        conn.sync_status = "connected" if status_result["connected"] else "error"
        conn.error_message = status_result.get("error") if not status_result["connected"] else None
        await db.flush()
        return IntegrationConnectionStatus(**status_result)
    except Exception as exc:
        conn.is_connected = False
        conn.sync_status = "error"
        conn.error_message = str(exc)
        await db.flush()
        return IntegrationConnectionStatus(connected=False, error=str(exc))
    finally:
        await client.close()


@router.post("/connections/{connection_id}/sync", response_model=SyncResult)
async def sync_from_odoo(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict[str, str] = Depends(require_operator_or_admin),
) -> SyncResult:
    result = await db.execute(
        select(IntegrationConnection).where(IntegrationConnection.id == connection_id)
    )
    conn = result.scalar_one_or_none()
    if conn is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    if conn.provider != "odoo":
        raise HTTPException(status_code=400, detail="Only Odoo sync supported")

    client = _odoo_client(conn)
    orders_created = 0
    orders_updated = 0
    products_synced = 0
    partners_synced = 0

    try:
        existing = await db.execute(select(Order.external_order_id).where(Order.external_order_id.isnot(None)))
        existing_ids = {row[0] for row in existing.all()}

        odoo_orders = await client.get_sale_orders(limit=200)
        for odoo_order in odoo_orders:
            partner_data = None
            pid = odoo_order.get("partner_id")
            if isinstance(pid, (list, tuple)) and len(pid) > 0:
                partner_result = await client.read("res.partner", [pid[0]])
                if partner_result:
                    partner_data = partner_result[0]
            partner_email = partner_data.get("email", "") if partner_data else ""
            partner_street = partner_data.get("street", "") if partner_data else ""
            partner_city = partner_data.get("city", "") if partner_data else ""
            partner_zip = partner_data.get("zip", "") if partner_data else ""
            partner_state_id = partner_data.get("state_id") if partner_data else None
            partner_state = partner_state_id[1] if isinstance(partner_state_id, (list, tuple)) and len(partner_state_id) > 1 else ""

            if str(odoo_order["id"]) in existing_ids:
                continue

            order = Order(
                id=str(uuid4()),
                external_order_id=str(odoo_order["id"]),
                customer_email=partner_email or f"partner_{odoo_order['partner_id'][0]}@odoo.local",
                shipping_address=partner_street or "Imported from Odoo",
                shipping_zip=partner_zip or "00000",
                shipping_city=partner_city or "Imported",
                shipping_state=partner_state or "N/A",
                shipping_country="PK",
                items_json="[]",
                status=OrderStatus.PENDING,
                notes=f"Imported from Odoo order: {odoo_order.get('name', '')}",
            )
            db.add(order)
            orders_created += 1
            existing_ids.add(str(odoo_order["id"]))

        products = await client.get_product_product(limit=200)
        products_synced = len(products)

        partners = await client.get_partner(limit=200)
        partners_synced = len(partners)

        conn.total_orders_synced = (conn.total_orders_synced or 0) + orders_created
        conn.total_products_synced = products_synced
        conn.last_sync_at = func.now()
        conn.sync_status = "success"
        conn.error_message = None
        await db.flush()

        return SyncResult(
            success=True,
            message=f"Synced {orders_created} new orders, {products_synced} products, {partners_synced} partners",
            orders_created=orders_created,
            orders_updated=orders_updated,
            products_synced=products_synced,
            partners_synced=partners_synced,
        )
    except OdooError as exc:
        conn.sync_status = "error"
        conn.error_message = str(exc)
        await db.flush()
        return SyncResult(success=False, message=f"Odoo error: {exc}")
    except Exception as exc:
        conn.sync_status = "error"
        conn.error_message = str(exc)
        await db.flush()
        return SyncResult(success=False, message=f"Sync failed: {exc}")
    finally:
        await client.close()


@router.delete("/connections/{connection_id}", status_code=204)
async def delete_connection(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict[str, str] = Depends(require_operator_or_admin),
) -> None:
    result = await db.execute(
        select(IntegrationConnection).where(IntegrationConnection.id == connection_id)
    )
    conn = result.scalar_one_or_none()
    if conn is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    await db.delete(conn)
    await db.flush()


@router.post("/odoo/search", response_model=OdooSearchResult)
async def odoo_search(
    payload: OdooSearchRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict[str, str] = Depends(require_operator_or_admin),
) -> OdooSearchResult:
    conn_result = await db.execute(
        select(IntegrationConnection).where(
            IntegrationConnection.provider == "odoo",
            IntegrationConnection.is_connected,
        ).order_by(IntegrationConnection.updated_at.desc()).limit(1)
    )
    conn = conn_result.scalar_one_or_none()
    if conn is None:
        raise HTTPException(status_code=400, detail="No active Odoo connection found")

    client = _odoo_client(conn)
    try:
        records = await client.search_read(
            model=payload.model,
            domain=payload.domain,
            fields=payload.fields,
            limit=payload.limit,
            offset=payload.offset,
            order=payload.order,
        )
        return OdooSearchResult(records=records, total=len(records))
    except OdooError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        await client.close()
