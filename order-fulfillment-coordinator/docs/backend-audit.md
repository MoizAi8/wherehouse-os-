# FulfillOS Backend Audit — PHASE 1 (read-only)

> Status: audit complete, **no code modified**. Produced by the backend-dev
> workflow. This document is the source of truth for the follow-up phases
> (trace → deploy audit → fix → test → final report).

Audit date: 2026-08-15
Scope: `order-fulfillment-coordinator/apps/api` + `docker-compose*.yml`,
`infra/`, and the frontend↔backend connection surface
(`agent-platform-ui-main/agent-platform-ui-main`).

Gates run during audit: `ruff` clean, `mypy` 72 files clean, `pytest` **102 passed**
(1 warning). Live dev stack verified: API on `:8000` (health OK,
`{"status":"ok","version":"0.1.0","postgres":true}`), frontend on `:3000`.

---

## 1. What works

| Area | Evidence |
|---|---|
| App boots with only `OPENAI_API_KEY` set (rule #4) | SQLite fallback: dev `.env` sets `DATABASE_URL=sqlite+aiosqlite:///./fulfillment.db`, `DEBUG=true`. `init_db()` falls back to `create_all` when no `alembic_version` table. |
| Health check | `GET /health` probes DB with `SELECT 1`, returns `{"status","version","postgres"}` (main.py:73). |
| Auth flow | register / login / refresh / logout / me / change-password / forgot / reset (auth.py). JWT HS256, bcrypt passwords (truncated to 72 bytes), refresh tokens stored hashed (HMAC-SHA256), reset tokens hashed. |
| Rate limiting | Global `RateLimitMiddleware` token-bucket per IP; auth `10/min`, chat `30/min`, default `120/min`; returns 429 + `Retry-After`. Disabled only when `DEBUG` or `RATE_LIMIT_ENABLED=false`. |
| Webhook signature check | HMAC-SHA256 over raw body, constant-time compare (webhooks.py:22). |
| Order routing | Real DB queries: FC capacity + `carrier_rates` join by zip/weight → cost + tracking + shipment creation (order_service.py:118). |
| Shipment reroute | Re-selects cheapest rate, re-prices, new tracking (shipment_service.py:52). |
| Carrier rate shopping | `GET/POST /carriers/rates` from `carrier_rates` table (carriers.py). |
| Analytics KPIs / carrier performance | SQL aggregations, no mocks (analytics_service.py). |
| Multi-agent cycle | Orchestrator runs Monitor → SLA/failed-delivery guardrails → Rerouting (cost-cap guarded) → Communication → Prediction → CostOptimizer, all appending to `agent_events` (orchestrator.py). |
| Celery beat | `monitor-cycle-every-15-min` scheduled from `settings.shipment_poll_interval_seconds` (tasks/monitor_cycle.py). |
| Odoo integration | Real JSON-RPC via `OdooClient` (httpx, verify_ssl configurable); connect/test/sync/search endpoints. Secrets encrypted at rest via Fernet (`integration_secret_key`). |
| Notifications | SendGrid/Twilio when keys present; otherwise **simulated** (row persisted, no external send) — clear fallback, not silent failure. |
| Vector search | Qdrant + OpenAI embeddings behind feature-flag (`qdrant_url`/`openai_api_key`); returns empty results when unconfigured. |
| Websocket | JWT from query param + origin allowlist check; heartbeat + ping channels. |
| Migrations | Alembic baseline `afe1b0e38c11` matches models (includes FK fixes for notifications). |
| Schema-qualified SQL | Uses SQLAlchemy models; enum coercion fixes (`_coerce_order_status`) avoid SQLite-vs-PG enum string bugs. |

## 2. What is broken (correctness bugs)

1. **`sync_status` default drift** — `IntegrationConnection.sync_status` defaults to `"never"` in the model but the connect endpoint writes `"connected"`. Cosmetic only.
2. **`_demo_user` used for ANY unauthenticated request in DEBUG** (deps.py:59) — an intentionally-open door in DEBUG. In production `DEBUG=false` so requests with no/invalid token get 401. Acceptable by design (demo mode), but **must never leak to prod**. Confirmed `.env` has `DEBUG=false`.
3. **Duplicate `get_db`** — defined identically in both `database.py:29` and `api/deps.py:31`. Both `commit()` on success. Not a bug, but a maintainability trap (drift risk).
4. **Webhook endpoints commit even on success-path** — `get_db` commits automatically; `webhook_order_placed` catches `ValueError` → 409 but the `get_db` rollback path handles it. OK.
5. **`/odoo/search` does not decrypt stored secret** — integrations.py:312 passes `password=conn.api_key or ""` (ciphertext!) instead of `decrypt_secret(conn.api_key)`. Compare with `/test` (line 156) and `/sync` (line 195) which do decrypt. **This is a real bug**: after connect stores an encrypted `api_key`, `/odoo/search` would send the ciphertext as the Odoo password and fail auth.

## 3. What is incomplete

1. **No seed mechanism for production data** — `seed_all.py` is a raw-sqlite3 script hardcoding Karachi/Lahore/Islamabad FCs + carriers. **Nothing seeds PostgreSQL in prod.** Fresh prod DB has zero FCs and zero carrier rates → order routing raises `"No available fulfillment center"` / `"No suitable carrier rate found"`. This is a deployment blocker.
2. **`DATABASE_SYNC_URL` unused** — declared in config.py:22 and prod compose, referenced nowhere in code (no sync engine uses it).
3. **Guardrail usage** — `sla`+`cost` used by orchestrator; `failed_delivery`+`notifications` used by orchestrator; `carrier_diversity` used by `rerouting.py`; `address.py` present but no import found in `src/` — likely dead code, verify in PHASE 2.
4. **No auto-routing on order creation** — orders stay `pending` until explicitly routed (`/orders/{id}/route` or chat `proceed_delivery`). The webhook `order-placed` creates but does not route. If the design expects auto-route, it's missing.
5. **No tests for the Odoo search-decrypt bug** — coverage gap (tests are mock-heavy, 102 pass).

## 4. What is incorrectly connected

1. **Frontend prod rewrites are empty** — `next.config.ts` returns `{}` rewrites when `NODE_ENV === "production"`, but `src/lib/api.ts` uses **relative paths** (`/api/v1/...`). In dev the rewrite proxies to `localhost:8000`; in production, relative calls only work because **Caddy** reverse-proxies `/api/*`, `/health`, `/ws/*` → `api:8000`. If the frontend is ever served without Caddy (e.g. direct `frontend:3000`), all API calls 404. **Fragile coupling to Caddy** — acceptable only because Caddy is the sole public entry, but must be documented or replaced with `NEXT_PUBLIC_API_URL` absolute calls.
2. **Login uses `NEXT_PUBLIC_API_URL || "http://localhost:8000"`** (lib/auth.ts:18) — in the standalone Docker build the arg is baked at build time; if `NEXT_PUBLIC_API_URL` is unset it bakes `localhost:8000` which is wrong inside the container (backend is `api:8000`, not localhost). Compose passes it, but any other deploy path breaks.
3. **`schemas/settings.py` hardcodes `apiEndpoint: "http://localhost:8000"`** default, and the settings endpoint persists to a **JSON file** in `src/../data/` (filesystem), not the DB. On a container redeploy the file is lost; also `settings` is global ("default"), not per-user.
4. **`ws.py` origin default** — `origin = ws.headers.get("origin") or "http://localhost:3000"` (line 49): if the Origin header is absent the code *assumes* localhost:3000 is allowed. Minor CSWSH-ish gap; production behind Caddy has the header, but should fail closed.
5. **`CORS_ORIGINS` in prod compose defaults to `http://localhost:3000`** if `FRONTEND_URL` unset — silently wrong for a real domain. Same pattern as above.
6. **Health-check "postgres" flag** is actually "db reachable" — with the SQLite fallback it reports `postgres:true` even though no Postgres is used. Cosmetic but misleading in health ladders.

## 5. What will fail in production

1. **Empty FC / carrier tables** (see §3.1) → every routed order fails after deploy.
2. **`/odoo/search` ciphertext bug** (§2.5) → Odoo search always 401/400 after a successful connect.
3. **`integration_secret_key` / `webhook_secret` / `jwt_secret` defaults** — config.py ships `"change-me-in-production"` and `"change-webhook-secret"` and an empty `integration_secret_key`. The webhook guard explicitly **disables verification** when the secret is unset/insecure (webhooks.py:23) — a silent fail-open. Production MUST set all three; `.env.example` lists `JWT_SECRET` but **not** `WEBHOOK_SECRET` or `INTEGRATION_SECRET_KEY` → easy to miss.
4. **No migration step in deploy** — `deploy.sh` runs `docker compose build/up` but **never `alembic upgrade head`**. On a fresh volume `init_db()` falls back to `create_all`, so baseline tables appear, but any *future* Alembic migration is never applied on redeploys → schema drift. Rule: migrations must be explicit.
5. **`create_all` vs Alembic drift** — `init_db()` uses `create_all` only when `alembic_version` is absent. Once an Alembic migration exists, the fallback is skipped, so the app relies entirely on Alembic, which deploy never runs (see §5.4). Inconsistency.
6. **Single-API no workers** — Dockerfile runs `uvicorn ... ` single worker; acceptable for free-tier E2 micro but no horizontal scaling/graceful-drain story.
7. **Celery beat + worker in same image, no healthcheck for worker/beat** — worker unavailability is silent; only the API healthcheck exists in compose.
8. **`data/` settings JSON not in a volume** — lost on every `--force-recreate`; also container runs as non-root `appuser`, so `data/` must be writable (mkdir happens at import time with default perms).
9. **Chat `create_order` now requires explicit fields** — if the user omits required information (email, ZIP code, city, state), the chat prompts the user to provide them instead of fabricating default values. This prevents ghost orders with fake customer data. If any required field is missing, the response includes `action="create_order_missing_fields"` with a polite request for the missing information.

## 6. Deployment blockers (must fix before merge/deploy)

1. **Seed PostgreSQL with FCs + carrier rates** (or provide a documented SQL/JSON seed run via Alembic data migration).
2. **Run `alembic upgrade head` in deploy.sh** before starting API, and make `init_db()` not the only schema path.
3. **Fail closed on webhooks** — refuse to start (or 503) when `WEBHOOK_SECRET` unset/insecure, instead of silently disabling verification (rule: fail closed).
4. **Add `WEBHOOK_SECRET`, `INTEGRATION_SECRET_KEY`, `RESET_EMAIL_REDIRECT_URL`, `QDRANT_*` to `.env.example`** and validate at boot that prod secrets are not the defaults (boot guard).
5. **Fix `/odoo/search` to decrypt** stored secrets.
6. **Set `FRONTEND_URL`/`NEXT_PUBLIC_API_URL` explicitly** for prod; remove `localhost` fallbacks that can silently bake wrong URLs.
7. **Persist app settings in DB** (or a named volume) instead of the container filesystem.

## 7. Prioritized fixes (proposed for PHASE 4)

**P0 — correctness/security (blocks deploy):**
- `P0-1` Fix `/odoo/search` decryption (integrations.py:312).
- `P0-2` Boot guard: fail closed if `DEBUG=false` and `JWT_SECRET`/`WEBHOOK_SECRET` are defaults/empty (config or lifespan).
- `P0-3` Run `alembic upgrade head` in deploy + remove the create_all fallback ambiguity.
- `P0-4` Add a PG-compatible seed path for `fulfillment_centers` + `carrier_rates` (data migration or seed script used by deploy).
- `P0-5` Document/proxy guarantee: production relative `/api/*` relies on Caddy; add a compose-time check or switch `api.ts` to absolute `NEXT_PUBLIC_API_URL`.

**P1 — robustness:**
- `P1-1` `.env.example`: add `WEBHOOK_SECRET`, `INTEGRATION_SECRET_KEY`, `RESET_EMAIL_REDIRECT_URL`, Qdrant vars, and prod `DOMAIN`.
- `P1-2` Persist `AppSettings` to DB; drop filesystem JSON.
- `P1-3` `ws.py`: fail closed when Origin header missing (reject, don't default to localhost).
- `P1-4` Deduplicate `get_db` (single source in `database.py`).
- `P1-5` Add Celery worker/beat healthchecks; expose worker readiness in `/health` ladder.
- `P1-6` Rename health `postgres` → `db` or report backend flavor truthfully.

**P2 — hygiene / non-blocking:**
- `P2-1` Chat `create_order` now requires explicit fields — omitted email/ZIP/city/state prompt the user instead of fabricating defaults. No ghost orders with fake data.
- `P2-2` Remove unused `DATABASE_SYNC_URL` or wire a sync consumer.
- `P2-3` Remove or wire `guardrails/address.py` (no import found in `src/`).
- `P2-4` Replace `print()` in `vector_store.init_collections` with `logger`.
- `P2-5` Add tests covering `/odoo/search` decryption and prod-config boot guards.

---

## Notes for next phases
- PHASE 2 (trace): start from `POST /api/v1/orders` → `route_order` → shipment insert; and `POST /api/agents/monitor` → orchestrator → all agents. Verify no mock/hardcoded data at runtime (seed data IS real data, not mocks).
- PHASE 3 (deploy audit): covered largely here; remaining items are the compose healthcheck wiring, `api:8000` internal-only exposure, Caddy TLS, and CI (GitHub Actions) which was not present in the repo scan — confirm whether CI exists.
- PHASE 4 (fix): apply P0 + P1 in the order above, minimal diffs.
- PHASE 5 (test): re-run gates + live end-to-end (register→login→create order→route→shipment→analytics→webhook→chat→odoo search with encrypted secret).

---

# PHASE 4 — FIX (COMPLETE)

> Status: **all P0 + P1 fixes applied and verified.** This section supersedes the
> proposed P0/P1 items above. Verification date: 2026-08-16.

## 4A. What changed

| Item | Fix | Files |
|---|---|---|
| P0-1 `/odoo/search` decryption | Now passes `password=decrypt_secret(conn.api_key) or ""` instead of raw ciphertext. | `apps/api/src/fulfillment/api/v1/integrations.py:312` |
| P0-2 Boot guard | `Settings.validate_production()` refuses to start when `DEBUG=false` and `jwt_secret`/`webhook_secret` are empty or insecure defaults. Called first in the FastAPI lifespan. | `config.py` (`_INSECURE_SECRETS`, `validate_production`), `main.py:37` |
| P0-3 Alembic in deploy | `deploy.sh` runs `docker compose ... run --rm api alembic upgrade head` before `up -d`. | `infra/scripts/deploy.sh` |
| P0-4 PG seed | New async, ORM-based, idempotent `fulfillment/seed_data.py` (works on PG + SQLite; mirrors `seed_all.py` data). Deploy runs it after migrations. `seed_all.py` kept for local dev. | `apps/api/src/fulfillment/seed_data.py`, `deploy.sh` |
| P0-5 Frontend API connection | Prod rewrites proxy `/api/:path*` + `/health` to `BACKEND_URL` (baked at build); removed `|| "http://localhost:8000"` fallback in `lib/auth.ts` (fails closed when no base URL); removed hardcoded `localhost:8000` defaults in `SettingsContext.tsx` and `schemas/settings.py`. Dockerfile accepts `BACKEND_URL` build arg; prod compose passes it. | `next.config.ts`, `Dockerfile`, `docker-compose.prod.yml`, `src/lib/auth.ts:18`, `src/contexts/SettingsContext.tsx:36`, `apps/api/.../schemas/settings.py:18` |
| P1-6 (audit P1-1) `.env.example` | Added `WEBHOOK_SECRET`, `INTEGRATION_SECRET_KEY` (+ Fernet generation hint), `RESET_EMAIL_REDIRECT_URL`, `BACKEND_URL`, `JWT_REFRESH_EXPIRATION_DAYS`, `JWT_PASSWORD_RESET_EXPIRATION_MINUTES`; restored CORS/OpenAI/Qdrant/Shipping/Notifications sections. | `.env.example` |
| P1-7 (audit P1-2) Settings persistence | New `AppSettingsStore` model + alembic migration `b3a0c1e2f4a1`; settings API reads/writes the DB instead of a container-filesystem JSON. | `models/app_settings.py`, `models/__init__.py`, `api/v1/settings.py`, `alembic/versions/b3a0c1e2f4a1_add_app_settings_table.py` |
| P1-8 (audit P1-3) WS origin fail-closed | Missing `Origin` header now rejected in production (`4403 origin_missing`); only allowed in DEBUG. No `localhost:3000` default. | `api/v1/ws.py:47` |
| P1-9 (audit P1-4) Deduplicate `get_db` | Single canonical `get_db` in `database.py`; `api/deps.py` re-exports it (`import ... as get_db`). All callers unchanged. | `api/deps.py` |
| P1-10 (audit P1-5) Celery health | `tasks/health.py` adds `celery_ping` task + `celery_worker_health` probe (bounded, fail-soft). Healthcheck added to `celery-worker` and `celery-beat` in prod compose. | `tasks/health.py`, `tasks/__init__.py`, `docker-compose.prod.yml` |
| P1-11 (audit P1-6) Health DB type | `/health` reports `database` (real dialect from engine), keeps `postgres` truthful, adds `celery`, and returns `status: degraded` when DB is down. Probe is bounded so it never hangs. | `main.py` health route |
| Webhook fail-open (extra) | `verify_signature` no longer silently disables verification in production: insecure/missing `WEBHOOK_SECRET` → 500; DEBUG keeps the skip. | `api/v1/webhooks.py:22` |

## 4B. Verification executed

- **Gates (apps/api):** `ruff check src tests` clean; `mypy src` clean (75 files); `pytest tests/` **102 passed**.
- **Database migration:** `alembic upgrade head` applied cleanly against a real **PostgreSQL 15** instance (baseline `afe1b0e38c11` → `b3a0c1e2f4a1`). Verified new `app_settings` table exists.
- **Seed on PG:** `python -m fulfillment.seed_data` seeded 3 FCs + 10 carrier rates; **second run is a no-op** (idempotent).
- **Boot guard:** with `DEBUG=false` and insecure `JWT_SECRET`/`WEBHOOK_SECRET`, uvicorn refuses to start with `RuntimeError` listing the offending secrets.
- **Live boot + health (PG):** `{"status":"ok","version":"0.1.0","database":"postgresql","postgres":true,"celery":false}` (celery `false` is correct — no broker running; probe returned fast, fail-soft).
- **Live API battery (PG, via HTTP):**
  - login → OK (JWT + refresh token).
  - create order → 201.
  - `/orders/{id}/route` → Leopards, tracking `TRK-…`, cost 10.4, shipment row created.
  - shipments list → 1 shipment.
  - `/analytics/kpis` → aggregated KPIs.
  - settings PUT/GET → round-trips through the DB (viewer gets 403, admin succeeds — role guard intact).
  - webhook `order-placed`: no signature → **401**; correct HMAC-SHA256 → order created.
  - `/agents/monitor` → monitor cycle ran, detected the delay + cost analysis.
  - `/integrations/odoo/search` with no connection → clean 400 (endpoint wiring verified; full path needs a live Odoo).
  - Fernet round-trip: encrypt → decrypt == original; legacy plaintext still decrypts as-is.
- **Frontend:** `tsc --noEmit` clean; **`next build` succeeds** (standalone); `routes-manifest.json` shows the production rewrite baked as `http://api:8000/api/:path*` + `/health`; **`vitest run` 46 passed**; eslint clean on all changed files (pre-existing warnings/errors elsewhere untouched).
- **Compose:** both `docker-compose.yml` and `docker-compose.prod.yml` parse as valid YAML.

## 4C. Remaining deployment issues (not fixed — out of P0/P1 scope)

1. **Docker image build not executed locally** — Docker daemon is not running on this machine. `docker compose build` and the container runtime checks (healthcheck ladder, worker/beat healthchecks, Caddy TLS) must be validated on the OCI host with `./infra/scripts/deploy.sh`.
2. **Chat `create_order` now requires explicit fields** — omitted email/ZIP/city/state prompt the user instead of fabricating defaults (fixed in PHASE 4). No ghost orders.
3. **`DATABASE_SYNC_URL` unused**, **`guardrails/address.py` unused in `src/`**, **`print()` in `vector_store.init_collections`** — P2 hygiene items, deferred.
4. **No auto-routing on webhook order create** — orders stay `pending` until routed. Unchanged by design.
5. **`CORS_ORIGINS` still defaults to `http://localhost:3000`** in prod compose when `FRONTEND_URL` unset — set `FRONTEND_URL` explicitly (documented in `.env.example`).
6. **`/health` status when DB down** — now returns `degraded`; the Dockerfile HEALTHCHECK requires `status==ok`, so the container will be marked unhealthy (correct behavior — fail closed).
7. **GitHub Actions CI** was not present in the repo scan — confirm whether CI exists before merge.

## 4D. Required production environment variables

Set **all** of these in `.env` (see `.env.example`):

```
APP_NAME, APP_VERSION, DEBUG=false
DATABASE_URL, DATABASE_SYNC_URL
POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD   # compose
REDIS_URL, CELERY_BROKER_URL, CELERY_RESULT_BACKEND
JWT_SECRET, JWT_ALGORITHM=HS256, JWT_EXPIRATION_MINUTES
WEBHOOK_SECRET                                 # REQUIRED (boot guard + webhook fail-closed)
INTEGRATION_SECRET_KEY                         # REQUIRED (Fernet key for Odoo creds)
RESET_EMAIL_REDIRECT_URL
FRONTEND_URL, DOMAIN, SSL_EMAIL
BACKEND_URL=http://api:8000
CORS_ORIGINS, OPENAI_API_KEY, OPENAI_MODEL
QDRANT_URL, QDRANT_API_KEY
EASYPOST_API_KEY, SMARTYSTREETS_AUTH_ID, SMARTYSTREETS_AUTH_TOKEN
TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER
SENDGRID_API_KEY, SENDGRID_FROM_EMAIL
ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD, ODOO_VERIFY_SSL
```

## 4E. Exact deploy / start commands

```bash
# Local dev
cd apps/api && uv run fastapi dev src/fulfillment/main.py    # :8000
cd agent-platform-ui-main && npx next dev -p 3000           # :3000

# Production deploy (on OCI instance)
./infra/scripts/deploy.sh   # build → alembic upgrade head → seed → up → health wait

# Manual migration + seed if needed
cd apps/api
uv run alembic upgrade head
uv run python -m fulfillment.seed_data

# Rollback to previous image
./infra/scripts/rollback.sh api
```

---

# PHASE 5 — INTEGRATION & PRODUCTION TEST (COMPLETE)

> Status: **all PHASE 5 tests executed against a real PostgreSQL 15 database in
> production mode (`DEBUG=false`), no code changes required.** Verification
> date: 2026-08-16.

## 5A. Test environment

- Fresh PostgreSQL database `fulfillment_phase5` (trust auth, local PG 15 service).
- Migrations applied: `afe1b0e38c11` baseline → `b3a0c1e2f4a1` app_settings.
- Seeded via `python -m fulfillment.seed_data`: **3 FCs (Lahore 54000 / Karachi 74000 / Islamabad 44000) + 10 carrier rates**; re-run verified idempotent (0/0 on second run).
- API booted with `DEBUG=false`, strong `JWT_SECRET`/`WEBHOOK_SECRET`, real Fernet `INTEGRATION_SECRET_KEY` — boot guard passed (no insecure secrets).
- Fake Odoo JSON-RPC server (localhost:8899) mimicking `version`/`authenticate`/`execute_kw` and echoing the password it receives.

## 5B. Results matrix

| Test | Expected | Result |
|---|---|---|
| `/health` | ok, postgresql, postgres:true, celery:false | ✅ `{"status":"ok","version":"0.1.0","database":"postgresql","postgres":true,"celery":false}` |
| register | 201 with role=viewer | ✅ `ph5@test.com role=viewer` |
| duplicate register | 400 | ✅ `400 Email already registered` |
| login | access + refresh token | ✅ |
| `/auth/me` | viewer role | ✅ |
| create order (zip 44000) | 201 status=pending | ✅ order `bd88c308-…` |
| route order | FC + carrier + tracking + cost + ETA | ✅ Islamabad FC / Leopards / TRK-18514F1917FB / 11.0 / 2-5d |
| shipments list | 1 shipment | ✅ |
| analytics/kpis | aggregated KPIs | ✅ total_orders=1, total_shipping_cost=11.0 |
| analytics/carriers | Leopards 100% on-time | ✅ |
| fulfillment-centers | 3 FCs | ✅ |
| carriers/rates | 10 rates | ✅ |
| agents/monitor | cycle + delay detection + cost analysis | ✅ cycle `556781b7-…`, delays_detected=1, high_failure_risk 0.65, cost analysis |
| webhook order-placed unsigned | 401 | ✅ `Invalid webhook signature` |
| webhook order-placed wrong HMAC | 401 | ✅ |
| webhook order-placed correct HMAC | 201 order created | ✅ order `aa5135c3-…` |
| webhook shipment-event valid | processed | ✅ status → in_transit persisted |
| webhook shipment-event invalid status | 422 | ✅ |
| chat greeting | greeting reply + action | ✅ |
| chat list orders | list_orders + data | ✅ (2 orders) |
| chat create order (explicit) | order created | ✅ `buyer2@test.com` / Islamabad 44000 / 3kg |
| Odoo connect → encrypted at rest | connected, api_key = Fernet ciphertext | ✅ `gAAAAABqgaSU…` |
| Odoo /search → decrypted on wire | fake server receives **plaintext** password | ✅ `password=odoo-secret-plaintext`, DECRYPTED_CORRECTLY=True, 2 records |
| settings GET defaults | defaults, apiEndpoint="" | ✅ |
| settings PUT as viewer | 403 | ✅ `Admin or operator role required` |
| settings PUT as admin | persisted | ✅ theme=light, appName=FulfillOS Phase5, sessionTimeout=42, compactMode=true, autoBackup=false |
| settings GET round-trip | same values | ✅ |
| settings raw DB row | persisted in `app_settings.payload_json` | ✅ `light|42|FulfillOS Phase5` |
| settings **after server restart** | values survive (DB-backed, not filesystem) | ✅ theme=light / 42 / FulfillOS Phase5 / compactMode=true |
| shipment reroute | Leopards → TCS, new tracking, cost | ✅ TRK-09B7DA68BDF9, additional_cost 5.5, service Express |
| rate limiting (auth) | 10×401 then 429 + Retry-After | ✅ `…401,401,401,401,401,401,401,401,401,401,429,429`, Retry-After=60 |

## 5C. Gates re-run

| Gate | Result |
|---|---|
| `ruff check src tests` (backend) | ✅ clean |
| `mypy src` (backend) | ✅ 75 source files, no issues |
| `pytest tests/` (backend) | ✅ **102 passed**, 1 warning (starlette/httpx deprecation) |
| `tsc --noEmit` (frontend) | ✅ exit 0 |
| `vitest run` (frontend) | ✅ **46 passed / 9 files** |
| `next build` (frontend, production) | ✅ success; rewrites baked to `http://api:8000/api/:path*` + `/health` |

## 5D. Failures found

**None.** Every PHASE 5 test passed. Two transient test-harness mistakes (not app bugs) were corrected during the run:
1. Webhook signature format — the app verifies the **raw HMAC-SHA256 hex digest** in `X-Webhook-Signature` (not `sha256=<base64>`); re-tested with correct format → all pass.
2. Settings PUT field names are **camelCase** (`sessionTimeout`, `compactMode`, `appName`); snake_case keys are ignored by Pydantic — re-tested with correct names → persisted.

## 5E. Final DB state (fulfillment_phase5)

`orders=4, shipments=1, fulfillment_centers=3, carrier_rates=10, agent_events=2, integration_connections=1`

## 5F. Remaining (unchanged, out of PHASE 4/5 scope)

- Chat `create_order` now requires explicit fields — omitting email/city/zip prompts the user for missing information instead of producing ghost orders with fake data. (Fixed in PHASE 4)
- Docker compose build + healthcheck ladder still require the OCI host (Docker daemon absent locally).
- `DATABASE_SYNC_URL` unused; `guardrails/address.py` unused in `src/`; `print()` in `vector_store.init_collections` (P2 hygiene).