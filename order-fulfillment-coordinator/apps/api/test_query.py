import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import select
from fulfillment.models.order import Order

async def t():
    engine = create_async_engine('sqlite+aiosqlite:///./fulfillment.db')
    async with engine.connect() as conn:
        await conn.execute(select(Order).limit(1))
        print('OK')
    await engine.dispose()

asyncio.run(t())
