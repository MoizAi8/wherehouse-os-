"""Validate proposed Caddy route ownership locally, without requesting certificates.

Upstream fixtures identify routing only; separate real-API/browser checks verify
authentication. The actual production Caddy version is also adapted read-only.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import time

import httpx

ROOT=Path(__file__).resolve().parents[1]


def fixture(name):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200);self.end_headers();self.wfile.write(name.encode())
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
    Thread(target=server.serve_forever,daemon=True).start()
    return server


def main():
    caddy=ROOT/".tools/caddy/caddy.exe"
    env={**os.environ,"DOMAIN":"warehouse.example"}
    source=ROOT/"order-fulfillment-coordinator/infra/caddy/Caddyfile"
    adapted=subprocess.run([str(caddy),"adapt","--config",str(source),"--adapter","caddyfile"],
        env=env,capture_output=True,text=True,check=True)
    config=json.loads(adapted.stdout)
    api,frontend=fixture("backend"),fixture("frontend")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0));port=sock.getsockname()[1]
    servers=config["apps"]["http"]["servers"]
    # Keep the HTTPS server's actual routing tree; replace only transports.
    server=next(x for x in servers.values() if any(":443" in p for p in x["listen"]))
    server["listen"]=[f"127.0.0.1:{port}"]
    server["automatic_https"]={"disable":True}
    server.pop("tls_connection_policies",None)
    def replace(node):
        if isinstance(node,dict):
            if node.get("handler")=="reverse_proxy":
                for upstream in node["upstreams"]:
                    upstream["dial"]=f"127.0.0.1:{api.server_port if upstream['dial']=='api:8000' else frontend.server_port}"
            for value in node.values():replace(value)
        elif isinstance(node,list):
            for value in node:replace(value)
    replace(server)
    config={"admin":{"disabled":True},"apps":{"http":{"servers":{"fixture":server}}}}
    state=ROOT/".tools/proposed-caddy-routes";state.mkdir(parents=True,exist_ok=True)
    path=state/"config.json";path.write_text(json.dumps(config),encoding="utf8")
    results=[]
    with (state/"caddy.log").open("w",encoding="utf8") as log:
        process=subprocess.Popen([str(caddy),"run","--config",str(path)],stdout=log,stderr=subprocess.STDOUT)
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}",timeout=5,follow_redirects=False) as client:
                for _ in range(30):
                    try:
                        client.get("/",headers={"Host":"warehouse.example"});break
                    except httpx.ConnectError:time.sleep(.2)
                for route,expected,auth in [("/api/auth/session","frontend",False),("/api/chat","frontend",False),
                    ("/api/chat/history","backend",True),("/api/demo/status","backend",False),
                    ("/api/v1/agents/status","backend",True),("/api/auth/me","frontend",False),
                    ("/api/auth/me","backend",True),("/health","backend",False),("/demo","frontend",False)]:
                    headers={"Host":"warehouse.example"}
                    if auth:headers["Authorization"]="Bearer isolated-routing-fixture"
                    response=client.get(route,headers=headers)
                    assert response.status_code==200 and response.text==expected,route
                    results.append({"path":route,"bearer_present":auth,"owner":expected,"passed":True})
                response=client.get("/demo?teacher=1",headers={"Host":"140.245.218.97"})
                assert response.status_code==308 and response.headers["location"]=="https://warehouse.example/demo?teacher=1"
                results.append({"case":"IP canonical redirect preserves path and query","passed":True})
        finally:
            process.terminate();process.wait(timeout=10);api.shutdown();frontend.shutdown()
    report={"proposed_routing_only":True,"tls_issuance_tested":False,"production_config_applied":False,"results":results}
    target=ROOT/"reports/teacher-demo-20261103/caddy-routing.json"
    target.write_text(json.dumps(report,indent=2),encoding="utf8")
    print(f"{len(results)} proposed Caddy routing checks passed; no production reload or certificate issuance")


if __name__=="__main__":main()
