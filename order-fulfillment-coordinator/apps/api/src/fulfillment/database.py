from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text, event
from sqlalchemy.pool import NullPool

from fulfillment.config import settings
from fulfillment.logging_config import log_db_query, Timer

engine = create_async_engine(
    settings.async_database_url(),
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_timeout=30,
    # For SQLite fallback in dev
    connect_args={"check_same_thread": False} if "sqlite" in settings.async_database_url() else {},
)

# Use NullPool for serverless environments
if settings.debug:
    engine.pool = NullPool()

@event.listens_for(engine.sync_engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._query_start_time = Timer("db_query")

@event.listens_for(engine.sync_engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    if hasattr(context, "_query_start_time"):
        duration = context._query_start_time.elapsed_ms()
        log_db_query(statement, duration)


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


async def get_db_with_retry(max_retries: int = 3, base_delay: float = 0.5) -> AsyncGenerator[AsyncSession, None]:
    """Get DB session with automatic retry on transient failures."""
    from fulfillment.resilience import with_retry
    from sqlalchemy.exc import OperationalError, DisconnectionError

    async def _get_session():
        async with async_session_factory() as session:
            return session

    session = await with_retry(
        _get_session,
        max_retries=max_retries,
        base_delay=base_delay,
        retry_exceptions=(OperationalError, DisconnectionError, ConnectionError),
    )

    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


@asynccontextmanager
async def db_transaction() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for explicit transaction handling."""
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
    from sqlalchemy import inspect

    async with engine.begin() as conn:
        tables = await conn.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))
        migrations_applied = False
        if "alembic_version" in tables:
            rows = await conn.execute(text("SELECT version_num FROM alembic_version"))
            migrations_applied = rows.scalar() is not None
        if not migrations_applied:
            await conn.run_sync(Base.metadata.create_all)


async def check_db_connection() -> bool:
    """Check if database is reachable."""
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
