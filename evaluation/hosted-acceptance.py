"""Exercise two visitors on an already-running, disposable hosted-evaluator fixture."""
import time
import uuid

import httpx


def main():
    # Fixed loopback origin reserved for this fixture. Never send test writes to OCI.
    origin = "http://127.0.0.1:8397"
    path = "/api/demo/guest/workspace"
    with httpx.Client(base_url=origin, timeout=30, trust_env=False) as c:
        def visitor():
            res = c.post("/api/demo/guest/session")
            res.raise_for_status()
            assert res.json()["instructorWorkspace"]
            return {"Authorization": "Bearer " + res.json()["accessToken"]}

        a, b = visitor(), visitor()
        products = path + "/api/v1/inventory/products"
        assert c.get(products).status_code == 401
        sku = uuid.uuid4().hex
        created = c.post(products, headers=a, json={"sku": sku, "name": "Evaluator boxes"})
        assert created.status_code == 201, created.status_code
        assert sku in [p["sku"] for p in c.get(products,headers=a).json()]
        assert sku not in [p["sku"] for p in c.get(products,headers=b).json()]
        for url in ("/api/v1/orders","/api/v1/inventory/products","/api/auth/users"):
            assert c.get(url, headers=a).status_code in (401,403)
        assert c.post(path+"/api/v1/integrations", headers=a,json={}).status_code == 404
        run_path=path+"/api/evaluation/workflow"
        run=c.post(run_path,headers=a,json={})
        assert run.status_code==202, run.status_code
        assert c.post(run_path,headers=a,json={}).status_code==409
        assert not c.get(run_path,headers=b).json()
        for _ in range(100):
            status=c.get(run_path,headers=a).json()
            if status["stage"] in ("Completed","Failed"):
                break
            time.sleep(1)
        assert status["stage"]=="Completed",status["stage"]
        result=status["result"]
        assert result["task_id"]==run.json()["id"] and result["stock_after_delivery"]==[3,0]
        cards=c.get(path+"/api/v1/agents/status",headers=a).json()["agents"]
        events={event["id"] for event in result["events"]}
        assert len(cards)==7 and all(card["status"]=="IDLE" and card["event_id"] in events for card in cards)
        assert c.get(path+"/api/v1/orders/"+result["order"],headers=b).status_code==404
        print("PASS two-visitor isolation, inventory, linked order, seven cards, Celery task",result["task_id"])


if __name__ == "__main__":
    main()
