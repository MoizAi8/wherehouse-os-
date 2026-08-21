"""Idempotent default seed for fulfillment centers and carrier rates.

Runs against whatever DATABASE_URL the app uses (PostgreSQL or SQLite) via the
same async engine as the app — unlike the legacy raw-sqlite3 ``seed_all.py``.

Usage:
    uv run python -m fulfillment.seed_data            # seed if empty
    uv run python -m fulfillment.seed_data --force   # upsert by (name/zip) keys

Deployment (deploy.sh) runs this after ``alembic upgrade head``.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from uuid import uuid4

from sqlalchemy import select

from fulfillment.database import async_session_factory
from fulfillment.models.carrier_rate import CarrierRate
from fulfillment.models.fulfillment_center import FulfillmentCenter

logger = logging.getLogger("fulfillment.seed_data")

# (name, address, zip_code, city, state, country, lat, lng, capacity_pct, max_daily, current_daily)
FULFILLMENT_CENTERS: list[tuple] = [
    ("Lahore FC", "1 KM Defense Rd, Lahore", "54000", "Lahore", "Punjab", "PK", 31.5204, 74.3587, 0.75, 500, 187),
    ("Karachi FC", "Port Qasim Authority, Karachi", "74000", "Karachi", "Sindh", "PK", 24.8607, 67.0011, 0.60, 400, 120),
    ("Islamabad FC", "Sector I-9, Islamabad", "44000", "Islamabad", "Islamabad", "PK", 33.6844, 73.0479, 0.45, 300, 68),
]

# (carrier_name, service_name, origin_zip, destination_zip, min_kg, max_kg, base, per_kg, min_days, max_days)
CARRIER_RATES: list[tuple] = [
    ("TCS", "Express", "54000", "54000", 0, 50, 12.0, 1.8, 1, 3),
    ("TCS", "Express", "74000", "74000", 0, 50, 12.0, 1.8, 1, 3),
    ("TCS", "Express", "44000", "44000", 0, 50, 12.0, 1.8, 1, 3),
    ("Leopards", "Standard", "54000", "54000", 0, 20, 8.0, 1.2, 2, 5),
    ("Leopards", "Standard", "74000", "74000", 0, 20, 8.0, 1.2, 2, 5),
    ("Leopards", "Standard", "44000", "44000", 0, 20, 8.0, 1.2, 2, 5),
    ("DHL", "Express", "54000", "54000", 0, 30, 18.0, 2.5, 1, 4),
    ("FedEx", "Economy", "54000", "54000", 0, 30, 14.0, 2.0, 2, 5),
    ("DHL", "Express", "10001", "10001", 0, 30, 25.0, 3.5, 2, 6),
    ("FedEx", "Economy", "10001", "10001", 0, 30, 19.0, 2.2, 3, 7),
]


async def seed_defaults(force: bool = False) -> dict[str, int]:
    async with async_session_factory() as db:
        fc_count = (await db.execute(select(FulfillmentCenter.id))).all()
        rates_count = (await db.execute(select(CarrierRate.id))).all()

        if fc_count and not force:
            logger.info("Fulfillment centers already seeded (%d) — skipping", len(fc_count))
            centers_created = 0
        else:
            centers_created = len(FULFILLMENT_CENTERS)
            if force and fc_count:
                logger.info("--force: deleting %d existing fulfillment centers", len(fc_count))
                for (fid,) in fc_count:
                    fc = await db.get(FulfillmentCenter, fid)
                    if fc:
                        await db.delete(fc)
            for row in FULFILLMENT_CENTERS:
                db.add(
                    FulfillmentCenter(
                        id=str(uuid4()),
                        name=row[0],
                        address=row[1],
                        zip_code=row[2],
                        city=row[3],
                        state=row[4],
                        country=row[5],
                        latitude=row[6],
                        longitude=row[7],
                        capacity_pct=row[8],
                        max_daily_orders=row[9],
                        current_daily_orders=row[10],
                        is_active=True,
                    )
                )
            logger.info("Seeded %d fulfillment centers", centers_created)

        if rates_count and not force:
            logger.info("Carrier rates already seeded (%d) — skipping", len(rates_count))
            rates_created = 0
        else:
            rates_created = len(CARRIER_RATES)
            if force and rates_count:
                logger.info("--force: deleting %d existing carrier rates", len(rates_count))
                for (rid,) in rates_count:
                    rate = await db.get(CarrierRate, rid)
                    if rate:
                        await db.delete(rate)
            for row in CARRIER_RATES:
                db.add(
                    CarrierRate(
                        id=str(uuid4()),
                        carrier_name=row[0],
                        service_name=row[1],
                        origin_zip=row[2],
                        destination_zip=row[3],
                        weight_kg_min=row[4],
                        weight_kg_max=row[5],
                        base_rate=row[6],
                        rate_per_kg=row[7],
                        estimated_days_min=row[8],
                        estimated_days_max=row[9],
                        is_active=True,
                    )
                )
            logger.info("Seeded %d carrier rates", rates_created)

        await db.commit()
        return {"fulfillment_centers": centers_created, "carrier_rates": rates_created}


def _main() -> None:
    parser = argparse.ArgumentParser(description="Seed default fulfillment data")
    parser.add_argument("--force", action="store_true", help="Delete and re-insert seed rows")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    result = asyncio.run(seed_defaults(force=args.force))
    print(f"Seed complete: {result}")


if __name__ == "__main__":
    _main()