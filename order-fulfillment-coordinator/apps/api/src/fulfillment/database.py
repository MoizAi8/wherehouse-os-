from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from fulfillment.config import settings

engine = create_async_engine(
    settings.async_database_url(),
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Apply schema. In production migrations run via Alembic (see alembic/).

    For local/dev databases without an alembic_version table, fall back to
    create_all (idempotent — it only adds missing tables) so the app boots
    with only OPENAI_API_KEY set (rule #4).
    """
    from sqlalchemy import inspect, text

    async with engine.begin() as conn:
        tables = await conn.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))
        migrations_applied = False
        if "alembic_version" in tables:
            rows = await conn.execute(text("SELECT version_num FROM alembic_version"))
            migrations_applied = rows.scalar() is not None
        if not migrations_applied:
            await conn.run_sync(Base.metadata.create_all)
