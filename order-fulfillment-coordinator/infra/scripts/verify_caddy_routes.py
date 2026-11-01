"""Run real Caddy on loopback with explicit HTTP backend fixtures (no live services)."""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
import urllib.request


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--caddy", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    work = root / ".tools/caddy-route-fixture"
    work.mkdir(parents=True, exist_ok=True)
    servers = []
    for service in ("api", "frontend"):
        class Handler(BaseHTTPRequestHandler):
            label = service

            def do_GET(self):
                body = json.dumps({"service": self.label, "path": self.path}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    env = {**os.environ, "DOMAIN": f"http://127.0.0.1:{port}",
           "XDG_DATA_HOME": str(work), "XDG_CONFIG_HOME": str(work)}
    adapted = subprocess.check_output([args.caddy, "adapt", "--config",
        str(root / "order-fulfillment-coordinator/infra/caddy/Caddyfile"), "--adapter", "caddyfile"], env=env)
    model = json.loads(adapted)
    model["admin"] = {"disabled": True}
    for server in model["apps"]["http"]["servers"].values():
        server["listen"] = [f"127.0.0.1:{port}"]
    encoded = json.dumps(model).replace('"api:8000"', f'"127.0.0.1:{servers[0].server_port}"')
    encoded = encoded.replace('"frontend:3000"', f'"127.0.0.1:{servers[1].server_port}"')
    config = work / "fixture.json"
    config.write_text(encoded)
    with (work / "server.log").open("w") as log:
        child = subprocess.Popen([args.caddy, "run", "--config", str(config)], env=env,
            stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        try:
            for attempt in range(50):
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1):
                        break
                except OSError:
                    if child.poll() is not None or attempt == 49:
                        raise RuntimeError("Caddy fixture did not start; inspect .tools/caddy-route-fixture/server.log")
                    time.sleep(0.1)
            cases = [("/", "frontend", {}), ("/health", "api", {}),
                     ("/api/v1/orders?limit=1", "api", {}), ("/api/auth/session", "frontend", {}),
                     ("/api/chat", "frontend", {}), ("/api/auth/me", "frontend", {}),
                     ("/api/auth/me", "api", {"Authorization": "Bearer isolated-fixture"}),
                     ("/api/v1/ws/shipments", "api", {})]
            for path, expected, headers in cases:
                request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", headers=headers)
                with urllib.request.urlopen(request, timeout=3) as response:
                    actual = json.load(response)
                    assert actual == {"service": expected, "path": path}, actual
                    assert response.headers["X-Content-Type-Options"] == "nosniff"
            print(f"PASS: {len(cases)} real Caddy route/path/header checks; backend services are explicit fixtures")
        finally:
            child.terminate()
            child.wait(timeout=10)
            for server in servers:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    main()
