import asyncio, sys, os, signal
from fulfillment.main import app
from fastapi.testclient import TestClient

questions = [
    "Aaj kitne orders ke liye fulfillment center assign kiya gaya hai?",
    "Kaun se carriers is waqt use ho rahe hain?",
    "Is waqt kitne active shipments hain?",
    "In active shipments mein se kitne delayed hain? Unki list do.",
    "Kitne shipments on-time chal rahe hain?",
    "Kitne shipments high-risk mark huay hain?",
    "Aaj kitne shipments reroute kiye gaye hain?",
    "Is hafte ka average shipping cost kitna raha?",
    "Aaj kitne customers ko delay alerts bheje gaye hain?",
    "Aaj total kitne cycles complete huay hain?",
]

passed = 0
failed = 0

client = TestClient(app)
for q in questions:
    try:
        resp = client.post('/api/chat/', json={'message': q})
        status = resp.status_code
        if status == 200:
            data = resp.json()
            reply_preview = data["reply"][:100].replace('\n', ' | ')
            print(f'OK [{status}] {reply_preview}')
            passed += 1
        else:
            print(f'FAIL [{status}] {q[:60]}')
            failed += 1
    except Exception as e:
        print(f'ERROR {q[:60]}: {e}')
        failed += 1
    sys.stdout.flush()

print(f'\nResults: {passed} passed, {failed} failed out of {len(questions)}')
sys.exit(0 if failed == 0 else 1)
