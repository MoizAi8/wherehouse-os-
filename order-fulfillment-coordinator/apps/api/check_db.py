import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check():
    engine = create_async_engine('sqlite+aiosqlite:///fulfillment.db')
    async with engine.connect() as conn:
        r = await conn.execute(text('SELECT DISTINCT event_type FROM agent_events'))
        types = [row[0] for row in r]
        print('Event types:', types)
        for t in types:
            r2 = await conn.execute(text('SELECT COUNT(*) FROM agent_events WHERE event_type = :t'), dict(t=t))
            cnt = r2.scalar()
            print(f'  {t}: {cnt}')
        r3 = await conn.execute(text('SELECT COUNT(*) FROM shipments WHERE is_delayed = 1'))
        print(f'Delayed shipments: {r3.scalar()}')
    await engine.dispose()

asyncio.run(check())
