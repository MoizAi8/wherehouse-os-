# FulfillOS — Final System Audit

> Read-only audit of the existing FulfillOS implementation. No code was modified during this audit.
> All findings below are VERIFIED against the repository on disk with `file:line` references.
> Reference doc `docs/backend-audit.md` does NOT exist in the repository — this document replaces it.

Audit date: 2026-08-19
Repository root: `order-fulfillment-coordinator/` + `agent-platform-ui-main/agent-platform-ui-main/`

---

## 1. Backend core

### 1.1 Configuration (`apps/api/src/fulfillment/config.py`)

| Finding | Severity | Verified location |
|---|---|---|
| `jwt_secret` / `webhook_secret` have insecure defaults (`"change-me-in-production"`, `"change-webhook-secret"`) but `validate_production()` fails closed at boot in prod mode | OK (guarded) | config.py:25,41,77,84-91 |
| `INTEGRATION_SECRET_KEY` defaults to `""` and is **NOT** checked by `validate_production()` — production can boot with integration credentials stored in plaintext | HIGH | config.py:75,84; encryption.py:41-44 |
| No SQLite fallback when `DATABASE_URL` unset — default is PostgreSQL `postgresql+asyncpg://postgres:postgres@localhost:5432/fulfillment`; AGENTS.md rule #4 ("boot with only OPENAI_API_KEY") not implemented | MED | config.py:21; database.py:10-16 |
| `database_sync_url` defined but referenced nowhere | LOW | config.py:22 |
| Rate limit defaults: default 120/min, auth 10/min, chat 30/min | OK | config.py:37-39 |
| Production mode = `debug: bool = False` default; `DEBUG` env overrides | OK | config.py:19 |

### 1.2 Database (`database.py`)

- Async-only engine, `async_session_factory`, `get_db` commits/rolls back correctly. Single DB dependency — no duplicates. OK.
- `init_db()`: if `alembic_version` table absent → `Base.metadata.create_all` (idempotent). If present → does nothing (Alembic owns schema). OK for dev/fresh DB.

### 1.3 App wiring (`main.py`)

- Lifespan: `validate_production()` → `init_db()` → `init_collections()`. No try/except — DB or Qdrant outage at boot fails startup (fail-closed). | MED | main.py:36-40
- `/health`: `status` is `"ok"` whenever DB probe passes; Celery failure does not degrade status. Docker HEALTHCHECK treats `status=="ok"` as healthy, so Celery can be down while container is "healthy". | MED | main.py:100; Dockerfile:36-37
- All routers registered (auth, chat, orders, shipments, carriers, agents, analytics, settings, fulfillment-centers, webhooks, integrations, ws). | OK

### 1.4 Rate limiting (`rate_limit.py`)

| Finding | Severity | Location |
|---|---|---|
| In-memory token-bucket dict `self._buckets` is unbounded — no eviction, permanent bucket per unique client IP → memory-leak DoS on long-running instance | MED | rate_limit.py:79 |
| `Retry-After` returns the full window, not actual refill time | LOW | rate_limit.py:117 |
| `_CHAT_PATH = ^/api/chat$` does not match `GET /api/chat/history` → history bypasses the 30/min chat limit | LOW | rate_limit.py:36; chat.py:966 |
| WebSockets not rate-limited (only `scope["type"]=="http"`) | LOW | rate_limit.py:85 |
| 429 responses lack CORS headers (RateLimit middleware is outermost, short-circuits before CORS) | LOW | main.py:58 |

### 1.5 Auth (`api/auth.py`, `security.py`, `api/deps.py`)

| Finding | Severity | Location |
|---|---|---|
| JWT HS256, bcrypt, refresh tokens rotated on use, reset tokens hashed+expiring | OK | security.py:30-67; auth.py:161-188 |
| Refresh-token reuse detection MISSING — no token-family revocation | MED | auth.py:166-188 |
| Role authorization NOT enforced on business endpoints: orders create/update/delete/route, shipment reroute, carrier rates, integration connect/delete/sync, agent monitor all accept any authenticated user (incl. VIEWER) | HIGH | deps.py:57-72 vs orders.py:63,77,89; integrations.py:176,276; carriers.py:22; shipments.py:38 |
| Demo-mode ADMIN fallback active whenever `settings.debug` — dangerous if DEBUG ever exposed | MED | deps.py:46-49 |

### 1.6 Models

- 12 models, all registered in `models/__init__.py:3-13`, all reach Alembic metadata via `env.py:12`.
- **`chat_messages` table has NO Alembic migration** — baseline `afe1b0e38c11` and `b3a0c1e2f4a1` do not create it. On a migrated prod DB (`alembic_version` present) `init_db()` skips `create_all`, so `/api/chat` and `/api/chat/history` will fail at runtime. | **HIGH / P0** | models/chat_message.py:14 vs alembic/versions
- Stale orphaned compiled migrations in `alembic/versions/__pycache__` (no .py source). | LOW

---

## 2. Agents, orchestrator, tools, guardrails

### 2.1 Agent wiring

| Agent | Exists | Runtime calls | Verified location |
|---|---|---|---|
| RoutingAgent | Yes | **NO** — only unit tests. Production routing uses duplicated `OrderService.route_order` | agents/routing.py:57; order_service.py:118-197; tests/test_50_cases.py:125 |
| MonitorAgent | Yes | Yes — orchestrator + chat | agents/orchestrator.py:28,44,64; chat.py:412 |
| ReroutingAgent | Yes | Yes — orchestrator only | agents/orchestrator.py:29,88,92 |
| CommunicationAgent | Yes | Yes — orchestrator only. **Latent bug**: `Order` referenced at line 21 without module-level import | agents/orchestrator.py:30,101; agents/communication.py:21-24 |
| PredictionAgent | Yes | Yes — orchestrator + chat high-risk | agents/orchestrator.py:31,117; chat.py:805 |
| CostOptimizer | Yes | Yes — orchestrator + chat cost analysis | agents/orchestrator.py:32,132; chat.py:864 |
| FulfillmentOrchestrator | Yes | Celery beat (15 min) + `POST /api/v1/agents/monitor` | tasks/monitor_cycle.py:26-31; api/v1/agents.py:13-25 |
| IntentAnalyzer | Yes | chat.py:60,93; supports `history` param | intent_analyzer.py:234,248-256 |

### 2.2 Autonomous order flow — VERIFIED GAP

- **Nothing fires automatically on order creation.** No event bus, SQLAlchemy listener, BackgroundTask, or Celery enqueue after order create (all 3 paths: REST, webhook, chat). Order ends in `PENDING`.
- Routing (Order → FC → carrier → Shipment) happens **only on explicit manual action**: `POST /orders/{id}/route` or chat `proceed_delivery`.
- The orchestrator is a **monitor/reroute loop** (every 15 min), not an order-driven pipeline. The spec chain "order created → orchestrator → routing → FC → carrier → shipment" does not exist autonomously. | **HIGH / P0**

### 2.3 Tools (`tools/`)

- Only one production call site across the whole package: `send_email_notification` (auth.py:25,251). API v1 routes use services, not tools.
- **`qdrant_tools.py` is dead code** — its 8 `@function_tool` wrappers (OpenAI Agents SDK) have **zero importers**; no `Agent`/`Runner` exists anywhere; not in `tools/__init__.py`. | MED

### 2.4 Guardrails

| Guardrail | Wired | Location |
|---|---|---|
| `sla_compliance` | Yes (orchestrator) | orchestrator.py:72 |
| `cost_cap` | Yes (orchestrator) | orchestrator.py:90 |
| `notification_frequency` | Yes (orchestrator) | orchestrator.py:100 |
| `failed_delivery_threshold` | Yes (orchestrator) | orchestrator.py:80 |
| `carrier_diversity` | Yes (rerouting only) | rerouting.py:13,48 |
| `register_monopoly_carrier` | **NO** — dead | carrier_diversity.py:17 |
| `validate_address` | **NO** — dead | address.py:6 |

### 2.5 Prediction agent

- **Heuristic weighted scoring, NOT ML.** No model/training/sklearn. Additive weights (delayed +0.3, hours overdue/48 capped 0.3, carrier historical delay rate ×0.2, exception +0.15), capped 0.95, per-carrier SQL AVG delay ratio. | Documented as-is

---

## 3. API routes & chat

### 3.1 Route inventory

- All `/api/v1/*`, `/api/auth/*`, `/api/chat*`, `/api/v1/ws/*`, webhooks registered. Every v1 endpoint calls a real service/DB query — **no v1 endpoint returns mock data** (verified). | OK
- Auth enforcement: webhooks use HMAC (fail-closed in prod); WS uses JWT + origin validation (fail-closed); REST uses JWT via `get_current_user` (demo fallback only in DEBUG).

### 3.2 Chat system (`api/chat.py`) — per-command verdict

All commands resolve through real backend services/DB and LLM-composed replies:

| Command | Verdict |
|---|---|
| create order | REAL data (DB insert) — **BUT** fabricated default address at chat.py:600 |
| list orders / status | REAL (DB) |
| agents | REAL counts + static descriptive text |
| metrics | REAL counts, but `"Agents: 7 online"` hardcoded (chat.py:494) |
| proceed delivery | REAL (calls route_order, DB writes) |
| filter orders | REAL |
| fulfillment centers / carriers / shipments / cost analysis / notifications / cycle stats / reroute history | REAL (DB/agent) |
| help / greeting | Static text + LLM fallback (non-data) |

Intent-map caveats:
- `SEND_NOTIFICATION → "help"` — no notification is ever sent via chat. | MED
- `REROUTE_SHIPMENT → "reroute_list"` — lists history only; no reroute executed. | MED
- `PREDICT_RISK → "insight"` — returns order totals, not per-shipment risk. | MED
- `agent_perf` branch (chat.py:441-478) is unreachable — no INTENT_MAP value matches. | LOW

### 3.3 Chat data integrity — FABRICATION (P0)

- **chat.py:600** — fabricated default address `f"Main Street, {city}, {state} {zip_code}"` is written into a REAL DB order when the user's text yields no address. Violates "never invent address" rule. | **P0**
- No invented order IDs / tracking IDs / prices / customer info found (tracking = `TRK-{uuid4}`, costs from CarrierRate rows, customer fields from user input/DB).

### 3.4 Chat memory feature (added)

- `session_id` resolve/persist, `_load_chat_history` (last 12, oldest first), `_save_chat_message`, `_history_section`, `GET /api/chat/history` — all wired correctly and DB-backed. | OK
- `_sanitize_reply` strips "User Safety: safe" verdict lines from every LLM reply (chat.py:117,128-140). | OK
- chat.py does NOT import qdrant_tools or vector_store — Qdrant not used by chat. | Noted

### 3.5 Notifications bug

- `tools/notifications.py:90` — `status="sent" if provider_id or not provider_id else "failed"` is **always** `"sent"`; simulated sends without SendGrid/Twilio are recorded as sent, so chat "failed" count is always 0. | MED

---

## 4. Qdrant vector store & Odoo

### 4.1 Qdrant status — DEAD in the running system

| Finding | Severity | Location |
|---|---|---|
| 4 collections defined (shipment_events, product_catalog, customer_order_history, agent_decisions, 1536-dim Cosine) | OK | vector_store.py:38-43 |
| `QDRANT_URL` default is non-empty (`http://localhost:6333`) → client instantiated even when unset; empty in dev `.env` → client None, all vector fns no-op | Noted | config.py:49; vector_store.py:24-30 |
| **No Qdrant service in `docker-compose.yml` or `docker-compose.prod.yml`** | **HIGH** | compose files (grep = 0) |
| Prod container: `QDRANT_URL` not injected → default applies → `init_collections()` calls `get_collections()` against itself → **API crashes at boot** | **HIGH / P0** | vector_store.py:50; main.py:39; compose.prod:38-68 |
| On-disk Qdrant data EXISTS: `qdrant/` with 4 collections (2 segments each, populated vector+payload storage), `qdrant.exe`, `.qdrant-initialized`. Data is real and must be preserved. | OK | C:\Users\AC\Desktop\final project\qdrant |
| `qdrant_tools.py` (8 function_tools) — zero importers; dead code | MED | tools/qdrant_tools.py |
| `upsert_product`/`search_similar_products`/`upsert_customer_history` — zero callers anywhere | LOW | vector_store.py |
| No `get_client()` / `close()` for global client | LOW | vector_store.py |
| `/health` has no Qdrant probe despite AGENTS.md ladder "Step 3: Qdrant wired" | LOW | main.py:74-105 |

### 4.2 Odoo (`services/odoo_client.py`, `api/v1/integrations.py`)

| Finding | Severity | Location |
|---|---|---|
| API layer encrypts/decrypts correctly (Fernet) on write/read | OK | integrations.py:81,95,156,195,312; encryption.py:36-44 |
| **`INTEGRATION_SECRET_KEY` not set in any deployed config** → secrets stored **plaintext**; `.env.example` marks it REQUIRED but nothing enforces | **HIGH / P0** | encryption.py:42-43; compose.prod:50 |
| **Latent bug**: `tools/integrations.py:33,53,74,95` pass the **encrypted ciphertext** as the Odoo password without decrypting — would fail auth once the key is set (currently masked by plaintext fallback; tools also uncalled at runtime) | MED | tools/integrations.py |
| Logging is clean — no secret material in any log statement; GET schemas omit api_key | OK | odoo_client.py:77 |
| `close()` leaves `self.password` on instance (minor in-memory retention) | LOW | odoo_client.py:221-225 |

---

## 5. Frontend (`agent-platform-ui-main/agent-platform-ui-main`)

### 5.1 Routes

- Pages exist for landing, dashboard, chat, agents, workflows, orders, monitoring, integrations, analytics, team, notifications, settings.
- **Static/hardcoded pages (no backend call):** `/dashboard/monitoring` (monitoring/page.tsx:5-20), `/dashboard/notifications` (notifications/page.tsx:18-27), `/dashboard/workflows` (WorkflowPanel.tsx:18-23). | MED
- **No login/register page exists** — no signIn() call anywhere. | HIGH

### 5.2 Chat proxy routes — P0 connection bug

| Finding | Severity | Location |
|---|---|---|
| 4 server-side proxy routes use `process.env.BACKEND_URL || "http://localhost:8000"` — **dangerous localhost fallback in production** (inside frontend container, no API there) | **HIGH / P0** | api/chat/route.ts:3; api/ai/chat/route.ts:4; api/ai/suggest/route.ts:3; api/ai/insight/route.ts:3 |
| Chat proxies forward **zero auth headers** → backend `get_current_user` returns 401 in any non-debug deployment. `AIAssistant` and history load will fail with 401 | **HIGH / P0** | api/chat/route.ts:16,47-50; api/ai/chat/route.ts:19 |
| Trailing-slash mismatch: `/api/ai/*` fetch `${BACKEND_URL}/api/chat/` but backend route is `/api/chat` → 307 every call | LOW | api/ai/chat/route.ts |
| `/api/ai/chat` + `/api/ai/suggest` unused (no consumer); `/api/ai/insight` consumed only by AIInsights (never rendered) | LOW | |
| `next.config.ts` production rewrites fail closed (`{}` if BACKEND_URL unset) — inconsistent with the routes above | Noted | next.config.ts:8-21 |
| `.env.local:3` — `NEXTAUTH_SECRET=super-secret-key-change-in-production-123456` hardcoded | MED | .env.local |

### 5.3 Auth / token

- NextAuth v4 CredentialsProvider, JWT session, `session.accessToken`. Data hooks (`lib/api.ts`) attach `Authorization: Bearer` to `/api/v1/*`. | OK
- **Token refresh MISSING** — backend `POST /api/auth/refresh` never called by frontend. | MED
- Logout does not call `signOut()` — session cookie survives. | MED

### 5.4 WebSocket

- **No WebSocket client exists in the frontend.** Backend exposes `/api/v1/ws/*` but nothing consumes them. Monitoring page is static. | MED

### 5.5 AIAssistant

- Uses real backend via proxy (no mock). session_id persisted in localStorage (`fulfillos_chat_session`), history loaded on mount, clear chat rotates session. Streaming state set but never populated (non-streaming response). | OK

---

## 6. Infrastructure, deployment, migrations, tests

### 6.1 Dockerfiles

- API: multi-stage (base/builder/production), non-root, HEALTHCHECK `/health`. **`alembic.ini` and `alembic/` NOT copied into image** (only `src/`) → `alembic upgrade` inside container fails. | **HIGH / P0** | Dockerfile:28
- Frontend: multi-stage standalone, non-root. OK.

### 6.2 docker-compose

- Dev: postgres, redis, api, celery-worker, celery-beat. Prod: + frontend, caddy. **Qdrant absent from both.** Prod api is `expose: 8000` only (no host port). | Noted
- `INTEGRATION_SECRET_KEY` default `""` in prod compose. | HIGH

### 6.3 infra/scripts

| Bug | Severity | Location |
|---|---|---|
| `deploy.sh:37` runs `alembic upgrade head` inside image that lacks `alembic.ini`/`alembic/` → fails, `set -euo pipefail` aborts deploy | **HIGH / P0** | deploy.sh:37; Dockerfile:28 |
| `deploy.sh:47` health-check curls `localhost:8000` but api is not host-published → never succeeds | **HIGH / P0** | deploy.sh:47; compose.prod:36-37 |
| `rollback.sh` tags image `fulfillment-${SERVICE}` which matches nothing (actual name `order-fulfillment-coordinator-api`) → rollback is a no-op | MED | rollback.sh:22-25 |
| `backup.sh` container name `fulfillment-postgres-1` doesn't match `order-fulfillment-coordinator-postgres-1` → backup skipped | MED | backup.sh:26,28 |
| `POSTGRES_PASSWORD` read from env, never from `.env` in backup.sh | MED | backup.sh |

### 6.4 Alembic

- 2 migration files: `afe1b0e38c11` (baseline) + `b3a0c1e2f4a1` (app_settings). **`b3a0c1e2f4a1` is untracked in git.** Stale orphaned pyc in versions/__pycache__. | MED
- **`chat_messages` has NO migration** → chat persistence breaks on migrated prod DB. | **HIGH / P0**
- `alembic upgrade` is deploy-script-only; not run on app startup (by design). | Noted

### 6.5 Seed data

- `seed_data.py` exists (untracked): 3 centers (Lahore/Karachi/Islamabad), 10 carrier rates (TCS/Leopards/DHL/FedEx), idempotent. `deploy.sh:40` runs it **after** the failing migration step → **production never gets seeded**. | **HIGH / P0**

### 6.6 Celery

| Bug | Severity | Location |
|---|---|---|
| Worker/beat command `-A fulfillment.tasks` resolves to `.app`/`.celery` attr — module exposes neither; app is `celery_app` in `tasks.monitor_cycle` → **worker, beat, and `inspect ping` healthchecks all fail to start** | **HIGH / P0** | tasks/__init__.py:1-6; compose.prod:80,106,90,115 |
| Otherwise schedule/config (15-min beat, acks_late, retries) correct | OK | tasks/monitor_cycle.py:14-31 |

### 6.7 Settings persistence (P1)

- **DB-backed** (`AppSettingsStore` → `app_settings`), not ephemeral filesystem. GET/PUT via `api/v1/settings.py`. Migration exists (`b3a0c1e2f4a1`). File-based implementation already deleted from code (tracked deletion). | RESOLVED

### 6.8 WebSocket security (P1)

- Origin validation present and fail-closed (missing Origin → close 4403, mismatch → 4403, JWT via `?token=` → close 4401; `*` disables origin check). | OK

### 6.9 Health endpoint (P1)

- Reports real DB (SELECT 1) and real Celery probe; no fake health. Improvement needed: Celery-down should degrade `status` (currently stays "ok"). | MED

### 6.10 CI (`github/workflows/ci.yml`)

| Bug | Severity | Location |
|---|---|---|
| Frontend jobs use `working-directory: apps/web` which **does not exist** (frontend is sibling dir) → lint/typecheck/test/build fail | **HIGH** | ci.yml:75-141 |
| `typecheck-frontend` runs `pnpm typecheck`; frontend package.json has no `typecheck` script | HIGH | ci.yml:105 |
| `build` job runs compose with no `.env`; `POSTGRES_PASSWORD` has no default → empty interpolation | MED | ci.yml:141 |
| No CD/deploy workflow exists (AGENTS.md claims SSH deploy via GitHub Actions) | MED | .github/workflows/ |

### 6.11 Tests

- Backend: 102 test functions (`test_50_cases.py` 50 + `test_advanced_50.py` 52). Mostly MagicMock/AsyncMock — no real-DB integration tests. `test_50_cases.py:61` references pytest-rerunfailures attribute (plugin absent) — inert but harmless.
- Frontend: vitest configured; tests exist under `src/__tests__/`.
- Command: `uv run pytest tests/`.

---

## 7. Verified P0/P1/P2 issue summary

### P0 — blocking for production
1. **`chat_messages` has no Alembic migration** → chat persistence 500s on migrated prod DB.
2. **Deploy broken at migration step** — image lacks `alembic.ini`/`alembic/`; deploy.sh aborts before anything runs.
3. **Celery `-A fulfillment.tasks` unresolvable** → worker/beat/healthchecks fail to start.
4. **Chat fabricates a default address** into real DB orders (chat.py:600).
5. **Chat frontend proxies forward no auth + localhost fallback** → 401 / guaranteed failure in prod.
6. **Production secrets**: `INTEGRATION_SECRET_KEY` unguarded → Odoo secrets stored plaintext.
7. **Qdrant prod-boot hazard** — no compose service + non-empty default URL → API crashes at startup unless `QDRANT_URL=` injected.
8. **Autonomous order flow absent** — order creation triggers no orchestrator/routing.

### P1
9. Role authorization not enforced on business endpoints (any authenticated user can mutate).
10. Rate-limit bucket dict unbounded (memory DoS).
11. Health stays "ok" when Celery down.
12. Refresh-token reuse detection missing.
13. Frontend has no login UI / no token refresh / logout doesn't signOut.
14. Frontend WebSocket client missing; monitoring page static.
15. CI frontend jobs point at non-existent `apps/web`.
16. backup.sh / rollback.sh container-name mismatches.
17. deploy.sh health check curls un-published port.

### P2
18. Address validation guardrail (`validate_address`) not connected.
19. `SEND_NOTIFICATION`, `REROUTE_SHIPMENT`, `PREDICT_RISK` intents degraded (help/list/insight).
20. Notifications `status` always "sent" (simulated sends mislabeled).
21. Dead code: `qdrant_tools.py`, `agent_perf` branch, orphaned upsert/search functions.
22. `CommunicationAgent` latent missing-import bug.
23. Static pages (monitoring, notifications, workflows).

---

## 8. Things that are healthy (verified)

- No duplicate DB dependency implementation; single `get_db`.
- Auth primitives solid (bcrypt, JWT typ check, rotated refresh tokens, hashed reset tokens).
- Rate limiting active on public endpoints with 429 + Retry-After.
- Webhook HMAC fail-closed in prod; WS origin + JWT fail-closed.
- Settings persistence DB-backed.
- All 12 models registered; chat memory feature DB-backed and wired.
- Chat uses real backend results for all data commands; no mock/static data in v1 endpoints or chat data branches.
- Logging does not expose secrets anywhere (Odoo and otherwise).
- Frontend data hooks attach auth tokens for `/api/v1/*`.
- Qdrant on-disk data (4 collections, 1536-dim Cosine) intact and preserved.