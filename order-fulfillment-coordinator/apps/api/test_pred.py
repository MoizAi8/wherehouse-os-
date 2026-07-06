import asyncio, traceback
from fulfillment.database import async_session_factory
from fulfillment.agents.monitor import MonitorAgent
from fulfillment.agents.prediction import PredictionAgent

async def test():
    async with async_session_factory() as db:
        monitor = MonitorAgent(db)
        predictor = PredictionAgent(db)
        shipments = await monitor.get_active_shipments()
        print(f'Shipments count: {len(shipments)}', flush=True)
        for s in shipments[:2]:
            try:
                pred = await predictor.predict_failure(s)
                rl = pred['risk_level']
                fp = pred['failure_probability']
                print(f'  OK: {s.id[:8]}, Risk: {rl}, Prob: {fp}', flush=True)
            except Exception as e:
                traceback.print_exc()

asyncio.run(test())
