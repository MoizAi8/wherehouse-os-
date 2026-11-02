"""Immutable, separately allocated sample database. Never imports production DB access."""
from __future__ import annotations

import sqlite3
from functools import lru_cache
from threading import Lock

AGENTS = [
    ("RoutingAgent", "Assigns carriers and fulfillment centers"),
    ("MonitorAgent", "Checks shipment progress and delivery estimates"),
    ("PredictionAgent", "Highlights potential SLA risks"),
    ("ReroutingAgent", "Evaluates alternative routes"),
    ("CommunicationAgent", "Prepares customer notifications"),
    ("CostOptimizer", "Compares shipping costs"),
    ("FulfillmentOrchestrator", "Coordinates the workflow"),
]


class DemoData:
    def __init__(self) -> None:
        self._lock = Lock()
        self._db = sqlite3.connect(":memory:", check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.executescript("""
            CREATE TABLE orders(id TEXT PRIMARY KEY, city TEXT, status TEXT,
                weight_kg REAL, shipping_cost REAL, carrier TEXT, delayed INTEGER);
            CREATE TABLE inventory(sku TEXT PRIMARY KEY, name TEXT, quantity INTEGER,
                reorder_level INTEGER, location TEXT);
            CREATE TABLE agents(name TEXT PRIMARY KEY, responsibility TEXT);
        """)
        self._db.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?)", [
            ("DEMO-001", "Lahore", "pending", 3, 0, "Unassigned", 0),
            ("DEMO-002", "Karachi", "shipped", 2, 350, "Sample Express", 0),
            ("DEMO-003", "Islamabad", "delivered", 1, 250, "Sample Standard", 0),
            ("DEMO-004", "Multan", "processing", 4, 420, "Sample Express", 0),
            ("DEMO-005", "Peshawar", "shipped", 5, 500, "Sample Standard", 1),
            ("DEMO-006", "Quetta", "delivered", 2, 300, "Sample Standard", 0),
            ("DEMO-007", "Faisalabad", "cancelled", 1, 0, "Unassigned", 0),
            ("DEMO-008", "Rawalpindi", "pending", 2.5, 0, "Unassigned", 0),
        ])
        self._db.executemany("INSERT INTO inventory VALUES (?,?,?,?,?)", [
            ("SKU-BOX", "Packing boxes", 120, 30, "Sample Lahore A1"),
            ("SKU-TAPE", "Packing tape", 18, 25, "Sample Lahore A2"),
            ("SKU-LABEL", "Shipping labels", 500, 100, "Sample Karachi B1"),
            ("SKU-WRAP", "Protective wrap", 42, 15, "Sample Islamabad C1"),
        ])
        self._db.executemany("INSERT INTO agents VALUES (?,?)", AGENTS)
        self._db.commit()
        self._db.execute("PRAGMA query_only=ON")

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        # Callers supply only fixed SELECT statements, never user/model SQL.
        with self._lock:
            return [dict(row) for row in self._db.execute(sql, params).fetchall()]

    def orders(self, status: str | None = None, city: str | None = None) -> list[dict]:
        return self.query(
            "SELECT * FROM orders WHERE (? IS NULL OR status=?) "
            "AND (? IS NULL OR lower(city)=lower(?)) ORDER BY id",
            (status, status, city, city),
        )

    def inventory(self, sku: str | None = None) -> list[dict]:
        return self.query("SELECT * FROM inventory WHERE (? IS NULL OR sku=?) ORDER BY sku", (sku, sku))

    def metrics(self) -> dict:
        return self.query("""SELECT count(*) AS total_orders,
            sum(status='pending') AS pending_orders, sum(status='delivered') AS delivered_orders,
            sum(delayed) AS delayed_shipments, round(sum(shipping_cost),2) AS shipping_cost_pkr
            FROM orders""")[0]

    def view(self, name: str, status: str | None = None) -> object:
        if name == "orders":
            return self.orders(status=status)
        if name == "inventory":
            return self.inventory()
        if name == "agents":
            return self.query("SELECT * FROM agents ORDER BY name")
        if name == "monitoring":
            return {"active": self.orders(status="shipped"), "delayed": self.query(
                "SELECT * FROM orders WHERE delayed=1 ORDER BY id"), "actions_executed": 0}
        if name == "workflows":
            return {"steps": ["Receive order", "Validate fields", "Request operator confirmation",
                "Evaluate carrier and center", "Route shipment", "Monitor progress", "Notify customer"],
                "execution": "Explanation only; public demo cannot dispatch or notify"}
        if name in ("dashboard", "analytics"):
            return {"metrics": self.metrics(), "inventory_alerts": self.query(
                "SELECT * FROM inventory WHERE quantity<reorder_level ORDER BY sku"),
                "by_status": self.query("SELECT status,count(*) AS count FROM orders GROUP BY status ORDER BY status")}
        raise ValueError("Unknown demo view")


@lru_cache(maxsize=1)
def demo_data() -> DemoData:
    return DemoData()
