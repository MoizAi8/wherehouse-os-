from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class OdooClient:
    def __init__(
        self,
        url: str,
        db: str,
        username: str,
        password: str,
        verify_ssl: bool = True,
        timeout: int = 30,
    ) -> None:
        self.url = url.rstrip("/")
        self.db = db
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self._uid: int | None = None
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                verify=self.verify_ssl,
                timeout=self.timeout,
            )
        return self._client

    async def _json_rpc(
        self,
        service: str,
        method: str,
        args: list[Any] | None = None,
    ) -> Any:
        client = await self._get_client()
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "service": service,
                "method": method,
                "args": args or [],
            },
            "id": 1,
        }
        response = await client.post(
            f"{self.url}/jsonrpc",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and data.get("error"):
            raise OdooError(data["error"]["data"]["message"])
        if isinstance(data, dict):
            return data["result"]
        return data

    async def authenticate(self) -> int:
        result = await self._json_rpc("common", "authenticate", [
            self.db,
            self.username,
            self.password,
            {},
        ])
        if not isinstance(result, int) or result == 0:
            raise OdooError("Authentication failed — check credentials")
        self._uid = result
        logger.info("Odoo authenticated as uid=%d", self._uid)
        return self._uid

    async def _execute_kw(
        self,
        model: str,
        method: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        if self._uid is None:
            await self.authenticate()
        params: list[Any] = [self.db, self._uid, self.password, model, method, args or []]
        if kwargs:
            params.append(kwargs)
        return await self._json_rpc("object", "execute_kw", params)

    async def search_read(
        self,
        model: str,
        domain: list[Any] | None = None,
        fields: list[str] | None = None,
        limit: int | None = None,
        offset: int = 0,
        order: str | None = None,
    ) -> list[dict[str, Any]]:
        kwargs: dict[str, Any] = {}
        if fields:
            kwargs["fields"] = fields
        if limit:
            kwargs["limit"] = limit
        if offset:
            kwargs["offset"] = offset
        if order:
            kwargs["order"] = order
        result = await self._execute_kw(model, "search_read", [domain or []], kwargs)
        return result if isinstance(result, list) else []

    async def create(self, model: str, values: dict[str, Any]) -> int:
        result = await self._execute_kw(model, "create", [values])
        return result if isinstance(result, int) else 0

    async def write(self, model: str, ids: list[int], values: dict[str, Any]) -> bool:
        result = await self._execute_kw(model, "write", [ids, values])
        return bool(result)

    async def unlink(self, model: str, ids: list[int]) -> bool:
        result = await self._execute_kw(model, "unlink", [ids])
        return bool(result)

    async def read(self, model: str, ids: list[int], fields: list[str] | None = None) -> list[dict[str, Any]]:
        kwargs = {}
        if fields:
            kwargs["fields"] = fields
        result = await self._execute_kw(model, "read", [ids], kwargs)
        return result if isinstance(result, list) else []

    async def get_sale_orders(
        self,
        domain: list[Any] | None = None,
        limit: int = 100,
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        default_fields = [
            "id", "name", "partner_id", "date_order", "amount_total",
            "state", "commitment_date", "note",
        ]
        return await self.search_read(
            "sale.order",
            domain=domain or [("state", "=", "sale")],
            fields=fields or default_fields,
            limit=limit,
            order="date_order desc",
        )

    async def get_stock_picking(
        self,
        domain: list[Any] | None = None,
        limit: int = 100,
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        default_fields = [
            "id", "name", "origin", "partner_id", "scheduled_date",
            "state", "location_id", "location_dest_id",
        ]
        return await self.search_read(
            "stock.picking",
            domain=domain or [("state", "=", "assigned")],
            fields=fields or default_fields,
            limit=limit,
            order="scheduled_date desc",
        )

    async def get_product_product(
        self,
        domain: list[Any] | None = None,
        limit: int = 100,
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        default_fields = [
            "id", "name", "default_code", "list_price",
            "standard_price", "qty_available", "uom_id",
        ]
        return await self.search_read(
            "product.product",
            domain=domain or [],
            fields=fields or default_fields,
            limit=limit,
        )

    async def get_partner(
        self,
        domain: list[Any] | None = None,
        limit: int = 100,
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        default_fields = [
            "id", "name", "email", "phone", "street",
            "city", "state_id", "zip", "country_id",
        ]
        return await self.search_read(
            "res.partner",
            domain=domain or [],
            fields=fields or default_fields,
            limit=limit,
        )

    async def check_connection(self) -> dict[str, Any]:
        try:
            version = await self._json_rpc("common", "version")
            await self.authenticate()
            return {
                "connected": True,
                "version": version.get("server_version", "unknown"),
                "uid": self._uid,
                "db": self.db,
                "server": self.url,
            }
        except Exception as exc:
            return {
                "connected": False,
                "error": str(exc),
            }

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
        self._uid = None


class OdooError(Exception):
    pass
