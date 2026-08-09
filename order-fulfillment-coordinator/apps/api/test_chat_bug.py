import asyncio
import traceback
import sys

async def test():
    from fulfillment.main import app
    from fastapi.testclient import TestClient
    
    client = TestClient(app)
    try:
        resp = client.post('/api/chat/', json={'message': 'help'})
        print(f'Status: {resp.status_code}', flush=True)
        if resp.status_code != 200:
            print(f'Body: {resp.text[:500]}', flush=True)
        else:
            data = resp.json()
            print(f'Reply: {data["reply"][:200]}', flush=True)
    except Exception:
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(test())
