"""Single-instructor loopback gateway. Only this listener may be routed externally."""

import asyncio
import hashlib
import json
import os
import re
import secrets
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

STATE = Path(os.environ["EVALUATION_STATE"])
ORIGIN = os.environ.get("EVALUATION_ORIGIN", "http://127.0.0.1:8387")
REMOTE = ORIGIN != "http://127.0.0.1:8387"
if REMOTE and (
    not re.fullmatch(r"https://[a-z0-9.-]+", ORIGIN)
    or os.environ.get("EVALUATION_RELEASE_BUILD") != "1"
):
    raise RuntimeError("External origin requires HTTPS and a release frontend")
UI = "http://127.0.0.1:3386"
API = "http://127.0.0.1:8386"
COOKIE = "__Host-evaluation" if REMOTE else "evaluation-local"
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
sessions = {}
workflow = None
status = {}
lock = asyncio.Lock()
exchange_attempts = []


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def generation():
    try:
        return (STATE / "generation").read_text().strip()
    except FileNotFoundError:
        return None


def allowed(method, path):
    uid = r"[a-f0-9-]{36}"
    read = [
        r"/health",
        r"/api/auth/me",
        r"/api/v1/(orders|shipments|fulfillment-centers|carriers|agents/status)",
        rf"/api/v1/orders/{uid}(/lines)?",
        r"/api/v1/inventory/(products|stock)",
        rf"/api/v1/inventory/(stock/{uid}/movements|orders/{uid}/reservations)",
        r"/api/v1/analytics/(kpis|carriers)",
    ]
    write = [
        r"/api/v1/inventory/(products|stock)",
        rf"/api/v1/inventory/stock/{uid}/(movements|reservations)",
        rf"/api/v1/inventory/reservations/{uid}/(release|consume)",
        r"/api/v1/orders",
        rf"/api/v1/orders/{uid}/(route|dispatch|cancel)",
    ]
    return any(
        re.fullmatch(x, path)
        for x in (read if method == "GET" else write if method == "POST" else [])
    )


def event(stage):
    status.update(stage=stage, updated_at=time.time())
    with (STATE / "audit.jsonl").open("a") as f:
        f.write(
            json.dumps(dict(time=time.time(), event=stage, run=status.get("id"))) + "\n"
        )


async def run():
    import sys

    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        str(Path(__file__).with_name("workflow.py")),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        async with asyncio.timeout(240):
            async for line in proc.stdout:
                event(line.decode(errors="replace").strip()[:200])
            if await proc.wait():
                raise RuntimeError("Worker failed")
        status["result"] = json.loads((STATE / "eval-workflow.json").read_text())
        event("Completed")
    except Exception:
        event("Failed")
    finally:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()


@app.middleware("http")
async def protect(request, next_handler):
    if request.headers.get("host") != urlsplit(ORIGIN).netloc:
        return Response(status_code=403)
    if (
        request.method not in ("GET", "HEAD")
        and request.headers.get("origin") != ORIGIN
    ):
        return Response(status_code=403)
    if (
        request.headers.get("content-length", "0").isdigit()
        and int(request.headers.get("content-length", "0")) > 65536
    ):
        return Response(status_code=413)
    if request.headers.get("transfer-encoding"):
        return Response(status_code=413)
    response = await next_handler(request)
    response.headers.update(
        {
            "referrer-policy": "no-referrer",
            "cache-control": "no-store",
            "x-frame-options": "DENY",
            "x-content-type-options": "nosniff",
        }
    )
    return response


@app.get("/invite")
def invite():
    nonce = secrets.token_urlsafe(18)
    page = """<!doctype html><title>Warehouse OS</title><p id="msg">Opening Warehouse OS…</p><script nonce="NONCE">
    const credential=location.hash.slice(1);history.replaceState(null,'','/invite');
    fetch('/exchange',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({credential})}).then(r=>{if(r.ok)location.replace('/dashboard');else document.getElementById('msg').textContent='Invitation unavailable. Contact the owner.'});</script>"""
    return HTMLResponse(
        page.replace("NONCE", nonce),
        headers={
            "Content-Security-Policy": f"default-src 'none'; script-src 'nonce-{nonce}'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        },
    )


@app.post("/exchange")
async def exchange(request: Request):
    global sessions
    async with lock:
        now = time.monotonic()
        exchange_attempts[:] = [t for t in exchange_attempts if now - t < 60]
        if len(exchange_attempts) >= 30:
            return Response(status_code=429, headers={"Retry-After": "60"})
        exchange_attempts.append(now)
        try:
            value = (await request.json())["credential"]
            if not isinstance(value, str) or not re.fullmatch(
                r"[A-Za-z0-9_-]{54}", value
            ):
                return Response(status_code=403)
            token_file = STATE / "invitation.sha256"
            gen = generation()
            if (
                not gen
                or time.time() - token_file.stat().st_mtime > 3600
                or not secrets.compare_digest(
                    digest(value), token_file.read_text().strip()
                )
            ):
                return Response(status_code=403)
        except (TypeError, ValueError, KeyError, FileNotFoundError, AttributeError):
            return Response(status_code=403)
        # Only the owner-issued, single-use capability can start this isolated operator session.
        token_file.unlink()
        client = httpx.AsyncClient(base_url=UI, trust_env=False, timeout=45)
        try:
            csrf = (await client.get("/api/auth/csrf")).json()["csrfToken"]
            await client.post(
                "/api/auth/callback/credentials",
                data={
                    "csrfToken": csrf,
                    "email": "warehouse-instructor@example.com",
                    "password": os.environ["EVALUATION_OPERATOR_SECRET"],
                    "callbackUrl": UI + "/dashboard",
                },
            )
            profile = (await client.get("/api/auth/session")).json()
            bearer = profile["accessToken"]
            if generation() != gen:
                raise ValueError()
        except Exception:
            await client.aclose()
            return Response(status_code=503)
        for old in sessions.values():
            await old[1].aclose()
        sid = secrets.token_urlsafe(32)
        sessions = {
            digest(sid): (gen, client, bearer, profile, time.monotonic() + 3600)
        }
        response = Response(status_code=204)
        response.set_cookie(
            COOKIE,
            sid,
            httponly=True,
            secure=REMOTE,
            samesite="strict",
            max_age=3600,
            path="/",
        )
        event("Invitation redeemed")
        return response


@app.api_route("/{rest:path}", methods=["GET", "POST", "PATCH", "PUT", "DELETE"])
async def gateway(rest: str, request: Request):
    global workflow, status
    s = sessions.get(digest(request.cookies.get(COOKIE, "")))
    if not s or not s[0] or s[0] != generation() or time.monotonic() >= s[4]:
        return Response(status_code=401)
    path = "/" + rest
    method = request.method
    if path == "/api/auth/session" and method == "GET":
        return {"user": s[3]["user"], "expires": s[3]["expires"]}
    if path == "/api/evaluation/workflow":
        if method == "GET":
            return status
        if method != "POST":
            return Response(status_code=405)
        if workflow and not workflow.done():
            return Response(status_code=409)
        status = {"id": secrets.token_hex(12)}
        event("Started")
        workflow = asyncio.create_task(run())
        return JSONResponse(status.copy(), status_code=202)
    if allowed(method, path):
        url = API + path
        headers = {"Authorization": "Bearer " + s[2]}
    elif (
        method == "GET"
        and (
            re.fullmatch(
                r"/dashboard(/(agents|orders|inventory|monitoring|analytics|chat|workflows))?",
                path,
            )
            or re.fullmatch(r"/_next/static/[a-zA-Z0-9_./%\[\]-]+", path)
            and ".." not in path
            or path in ["/favicon.ico", "/api/auth/csrf"]
        )
    ) or (path == "/api/chat" and method in ["GET", "POST", "DELETE"]):
        url = UI + path
        headers = {
            k: request.headers[k]
            for k in ("rsc", "next-router-state-tree", "next-router-prefetch", "accept")
            if k in request.headers
        }
    else:
        return Response(status_code=403)
    body = await request.body()
    if len(body) > 65536:
        return Response(status_code=413)
    if path.startswith("/_next/static/") and (
        "%" in path
        or "\\" in path
        or any(part in (".", "..") for part in rest.split("/"))
    ):
        return Response(status_code=403)
    if path == "/api/chat" and method == "POST":
        try:
            if json.loads(body).get("confirmationToken"):
                return Response(status_code=403)
        except (ValueError, AttributeError):
            return Response(status_code=400)
    if method in ("POST", "PATCH", "DELETE", "PUT") and path != "/api/chat":
        event("warehouse " + method + " " + path)
    if body:
        headers["Content-Type"] = "application/json"
    # No client-supplied authorization, cookies, forwarding headers or upstream destinations.
    async with httpx.AsyncClient(trust_env=False, timeout=60) as direct:
        client = direct if url.startswith(API + "/") else s[1]
        r = await client.request(
            method, url, params=request.query_params, content=body, headers=headers
        )
    return Response(
        r.content,
        status_code=r.status_code,
        headers={
            "Content-Type": r.headers.get("content-type", "application/octet-stream")
        },
    )
