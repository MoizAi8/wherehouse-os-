"""Bounded real Gemini integration probe. Synthetic accounts/data, never production.

The GitHub secret stays in the job environment and is never written to evidence.
Requires owner confirmation of a project with no linked billing account.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/teacher-demo-20261103/gemini-verification.json"


def main():
    if os.environ.get("GEMINI_FREE_TIER_CONFIRMED") != "true" or not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("Confirmed free-tier project and GitHub credential are required")
    (ROOT/".tools").mkdir(exist_ok=True)
    results = []
    server = None
    try:
        with (ROOT/".tools/gemini-synthetic-api.log").open("w", encoding="utf8") as log:
            server = subprocess.Popen([sys.executable, str(ROOT/"qa/server.py"), "--port", "8815", "--gemini-free"],
                cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            with httpx.Client(base_url="http://127.0.0.1:8815", timeout=75) as client:
                for _ in range(90):
                    try:
                        if client.get("/api/demo/status").status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    if server.poll() is not None:
                        raise RuntimeError("Disposable API did not start")
                    time.sleep(0.5)
                login = client.post("/api/auth/login", json={"email":"qa-admin@example.com", "password":"isolated-qa-password"})
                login.raise_for_status()
                headers = {"Authorization":"Bearer "+login.json()["access_token"]}
                cases = [
                    ("knowledge", "What is the capital of Pakistan? Reply in one sentence.", "knowledge", lambda x:"islamabad" in x.lower()),
                    ("arithmetic", "What is 19 plus 23? Reply with the number.", "arithmetic", lambda x:"42" in x),
                    ("roman-urdu", "Roman Urdu mein chhota sa salam karein.", "roman", lambda x:bool(re.search(r"salam|salaam|aap",x,re.I)) and not re.search(r"[\u0600-\u06ff\u0900-\u097f]",x)),
                    ("urdu", "اردو میں ایک مختصر سلام لکھیں۔", "urdu", lambda x:bool(re.search(r"[\u0600-\u06ff]",x))),
                    ("memory-store", "Remember my favourite fruit is mango. Acknowledge briefly.", "memory", lambda x:bool(x.strip())),
                    ("memory-recall", "What is my favourite fruit?", "memory", lambda x:"mango" in x.lower()),
                ]
                for name,prompt,session,assertion in cases:
                    response = client.post("/api/chat", headers=headers, json={"message":prompt,"session_id":"gemini-qa-"+session})
                    response.raise_for_status()
                    body = response.json()
                    passed = body.get("mode")=="llm" and body.get("model")=="gemini-3.5-flash-lite" and bool(body.get("usage",{}).get("output_tokens")) and bool(assertion(body["reply"]))
                    results.append({"case":name,"passed":passed,"http":response.status_code,"mode":body.get("mode"),"model":body.get("model"),"usage":body.get("usage"),"reply":body.get("reply")})
                    if not passed:
                        raise RuntimeError("Gemini conversation compatibility check failed")
                response = client.post("/api/demo/chat",json={"message":"Use read_demo_data to retrieve the factual summary of this sample environment."})
                response.raise_for_status();body=response.json()
                passed = body.get("mode")=="model_with_read_tool" and body.get("action_executed") is False and body.get("sample") is True
                results.append({"case":"isolated-read-tool","passed":passed,"http":response.status_code,"mode":body.get("mode"),"model":body.get("model")})
                if not passed:
                    raise RuntimeError("Gemini tool compatibility check failed")
                for path in ["/api/v1/orders","/api/v1/agents/status","/api/v1/analytics/kpis"]:
                    response=client.get(path)
                    results.append({"case":"unauthenticated-"+path,"passed":response.status_code==401,"http":response.status_code})
    except Exception as exc:
        # Do not serialize SDK/network exceptions: they may include request details.
        results.append({"case":"integration-execution","passed":False,"error_type":type(exc).__name__})
    finally:
        if server:
            server.terminate()
            try:server.wait(timeout=15)
            except subprocess.TimeoutExpired:server.kill();server.wait(timeout=5)
        REPORT.parent.mkdir(parents=True,exist_ok=True)
        REPORT.write_text(json.dumps({"synthetic_only":True,"billing_disabled_owner_confirmed":True,
            "maximum_logical_inference_requests":7,"no_deployment":True,"results":results},indent=2,ensure_ascii=False),encoding="utf8")
    print(json.dumps({"checks":len(results),"passed":sum(x["passed"] for x in results),"report":str(REPORT.relative_to(ROOT))}))
    return 0 if len(results)==10 and all(x["passed"] for x in results) else 1


if __name__=="__main__":
    raise SystemExit(main())
