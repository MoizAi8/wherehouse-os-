# FulfillOS — QA / Test Report

This report documents a complete production-level test of the FulfillOS order-fulfillment system (FastAPI backend `apps/api` + Next.js frontend `agent-platform-ui-main`), its environment variables, dependencies and config.

Scope: functional, API, database, security, performance, business-workflow, UI, and code-quality testing, with bugs fixed where required.

---

## 1. Test methodology

- Static review of all backend source (45 HTTP routes, 71 modules, 10 DB tables, 7 AI agents, 6 guardrails, auth, chat, integrations, celery tasks).
- Static review of frontend (11 dashboard pages, hooks, shared API client).
- Backend unit suites: `uv run pytest tests/` — 100 existing cases, 2 regression tests added = **102 passing**.
- Frontend suites: `npx vitest run` — **46 passing**; `tsc --noEmit` — **clean**.
- Live API smoke tests via FastAPI `TestClient` against SQLite.
- Lint/type gates per `AGENTS.md`: `ruff check src tests` (clean), `mypy src` (clean, 71 files).
- Live rate-limit end-to-end test (429 + Retry-After verified).

---

## 2. Test results

### Functional testing (features)

| Feature | Status | Notes |
|---|---|---|
| Orders CRUD + routing | PASS | Routing creates shipment + tracking; regression test added |
| Shipments | PASS | 404 on unknown id; reroute endpoint present |
| Carriers/rates | PASS | list + create endpoints |
| Fulfillment centers | PASS | list endpoint |
| Analytics/KPIs | PASS | returns totals, on-time rate, costs |
| Integrations/Odoo connect | PASS | 422 on missing fields; connection validated live |
| Notifications | PASS | 10 fields, indexed |
| Settings | PASS | GET/PUT |
| AI chat system | PASS | intent routing + LLM reply |
| Agent monitor cycle | PASS | returns cycle_id + metrics |
| Webhooks | PASS | 422 on malformed payloads; idempotent design |

### API testing (45 HTTP routes)

- Validation errors return `422` with pydantic details on all endpoints (verified: orders, carriers, integrations, chat, auth, webhooks, shipments).
- Not-found returns `404` consistently — **one inconsistency found & fixed** (see Bug #5).
- Auth-protected routes return `401` in production (fail-closed — verified).
- Response models use Pydantic schemas consistently.

### Database testing

- 10 tables: `users, refresh_tokens, orders, shipments, carrier_rates, fulfillment_centers, agent_events, notifications, integration_connections`.
- FKs: orders→carrier_rates/fulfillment_centers (SET NULL), shipments→orders + refresh_tokens→users (CASCADE), notifications→orders(CASCADE)/shipments(SET NULL) — **one integrity bug found & fixed** (see Bug #6).
- Unique constraint on `users.email` and `refresh_tokens.token_hash` — good.
- `agent_events` append-only — no DELETE/UPDATE routes (compliant with AGENTS.md rule #5).

### Security testing

- Auth: bcrypt + JWT access/refresh tokens; refresh rotation + revocation; fail-closed demo bypass in DEBUG only.
- **Rate limiting: critical gap found & fixed** (see Bug #1) — limiter existed but was applied to zero endpoints.
- CORS configured via env `cors_origins`.
- SQL injection: SQLAlchemy 2.0 Core/ORM used throughout — parameterized; no string-built SQL in routes.
- XSS: backend returns JSON only; frontend uses Next.js (auto-escaped) — no `dangerouslySetInnerHTML` found in reviewed components.
- CSRF: stateless JWT in `Authorization` header (double-submit not required for header-based auth).
- Secrets: `OPENAI_API_KEY` optional for boot (AGENTS.md rule #4) — verified app boots without it.

---

## 3. Bugs found, root cause, fix, verification

### Bug #1 — Rate limiter declared but never applied (CRITICAL — Security)
- **Issue**: Every public endpoint is unprotected against brute-force / DoS.
- **Root cause**: `main.py` created a `slowapi.Limiter` and a `RateLimitExceeded` (429 + Retry-After) handler, but `@limiter.limit(...)` was applied to **zero** routes (confirmed: 35+ endpoints, 0 decorators).
- **Files**: `main.py`, `rate_limit.py` (new), `config.py`.
- **Fix**: Added a global `RateLimitMiddleware` (per-IP token bucket) in `rate_limit.py`, registered in `main.py`. Limits configurable: `rate_limit_default` (120/min on all endpoints), `rate_limit_auth` (10/min on login/register/forgot/reset/refresh), `rate_limit_chat` (30/min). Returns `429` with `Retry-After` header. No-op when `DEBUG=true` so the demo works locally.
- **Verification**: live `TestClient` — login succeeds 3× then `429` with `Retry-After: 60`; new regression test `test_rate_limit_middleware_returns_429_with_retry_after`.

### Bug #2 — Demo user breaks every authenticated endpoint with 500 (CRITICAL — Functional)
- **Issue**: In DEBUG/demo mode, any authenticated request (orders, /auth/me, chat, etc.) returns HTTP 500 — the entire demo is broken.
- **Root cause**: `_demo_user()` in `deps.py` returned a `User` with `email="demo@fulfillment.local"` — `.local` is a reserved special-use TLD that Pydantic's `EmailStr` rejects — and `must_change_password` defaulted to `None` (invalid `bool`). The `UserResponse` Pydantic model then throws `ValidationError` inside the endpoint, surfacing as 500.
- **Files**: `src/fulfillment/api/deps.py`.
- **Fix**: Use `email="demo@fulfillment.io"` and explicitly set `must_change_password=False`.
- **Verification**: live `TestClient` — `GET /api/v1/orders` → 200, `GET /auth/me` → 200, `POST /api/v1/orders` → 201, `POST .../route` → 200 (creates shipment). Added regression test `test_demo_user_is_valid_for_response`.

### Bug #3 — Broken design tokens (MAJOR — UI/Frontend)
- **Issue**: `SelectContent` (dropdown popover) renders with **no background** and focus rings on inputs/buttons produce no color.
- **Root cause**: `globals.css` defined `--success`, `--warning`, `--info` but Tailwind v4 color utilities `ring-ring`, `bg-popover`, `text-popover-foreground` resolve to `--color-ring`, `--color-popover`, `--color-popover-foreground` which were **never registered** in `@theme inline` or `:root`.
- **Files**: `src/app/globals.css`, `src/components/ui/{button,input,select,badge}.tsx`.
- **Fix**: Registered `--color-ring/--ring`, `--color-popover/--popover`, `--color-popover-foreground`, and added `--success-foreground/--warning-foreground/--info-foreground`. Gave `Input` an `error` prop (parity with `Select`) with `aria-invalid`; switched `Badge` to semantic `<span>` and added an `info` variant.
- **Verification**: `tsc --noEmit` clean; `vitest` 46/46 pass; tokens resolve.

### Bug #4 — Seed data makes order routing impossible (CRITICAL — Business workflow)
- **Issue**: With the shipped seed data, **no order can ever be routed** — the core Sales→Routing→Shipping flow fails for every customer.
- **Root cause**: `seed_all.py` seeded carrier rates with `origin_zip='100'` / `destination_zip='5000'` (numeric placeholders), while fulfillment-centers have `zip_code='54000'/'74000'/'44000'` and customers' `shipping_zip` is a real postcode. The routing query (`order_service.route_order`) requires `carrier.origin_zip == fc.zip_code` AND `carrier.destination_zip == order.shipping_zip` — exact matches that can never occur with the seeded numbers.
- **Fix**: Rewrote `seed_all.py` carrier data so each Pakistani FC has carriers whose `origin_zip` = that FC's `zip_code` and `destination_zip` matches the city's postcode (covering common weights 0–50 kg), plus a couple of international origin bands.
- **Verification**: seeded DB + route call → `200` with `tracking_number`, status flipped to `processing`, `Shipment` created.

### Bug #5 — Inconsistent HTTP status for not-found order on route (LOW — API consistency)
- **Issue**: `POST /api/v1/orders/{id}/route` on a missing order returned `400`, while `GET/DELETE/{id}` correctly return `404`.
- **Root cause**: `order_service.route_order` raised `ValueError("Order not found")`, and the endpoint blanket-mapped all `ValueError`s to `400`.
- **Files**: `api/v1/orders.py`, `services/order_service.py`.
- **Fix**: Endpoint now checks existence via `get_order()` and returns `404` when missing; only business-rule `ValueError`s (e.g. "No suitable carrier rate found") remain `400`.
- **Verification**: `POST .../nonexistent/route` → 404 "Order not found".

### Bug #6 — Missing foreign keys on notifications (HIGH — Data integrity)
- **Issue**: `notifications.order_id` / `shipment_id` had indexes but no `ForeignKey` constraints — orphaned notifications could reference deleted orders/shipments indefinitely.
- **Root cause**: Model and migration omitted the constraints (likely to dodge SQLite table-creation ordering).
- **Files**: `models/notification.py`, `alembic/.../afe1b0e38c11_*.py`.
- **Fix**: Added `ForeignKey("orders.id", ondelete="CASCADE")` and `ForeignKey("shipments.id", ondelete="SET NULL")` to the model; added matching `op.create_foreign_key` calls in the baseline migration (deferred to after `orders`/`shipments` are created so it is valid on SQLite and Postgres).
- **Verification**: `create_all` on a fresh SQLite DB emits both FKs; `alembic upgrade --sql head` emits the deferred FK statements with no error.

---

## 4. Bugs fixed / regression coverage

| Bug | Severity | Fixed | Regression test |
|---|---|---|---|
| #1 Rate limiting missing | Critical | Yes | `test_rate_limit_middleware_returns_429_with_retry_after` |
| #2 Demo 500 on auth | Critical | Yes | `test_demo_user_is_valid_for_response` |
| #3 Broken design tokens | Major | Yes | `tsc` + `vitest` pass |
| #4 Seed routing impossible | Critical | Yes | Live route → 200 (smoke) |
| #5 Inconsistent 400/404 | Low | Yes | Smoke: 404 verified |
| #6 Missing notification FKs | High | Yes | `create_all` + alembic --sql verified |

Gate results: `ruff check src tests` = All checks passed; `mypy src` = Success in 71 files; `pytest` = 102 passed.

---

## 5. Remaining known issues (not fixed, with remediation)

- **Plaintext integration credentials** (`integration_connections.api_key` stores Odoo API key/secret as `Text`; `models/integration.py:20`, `api/v1/integrations.py:80`). Remediation: encrypt at rest (Fernet/AWS KMS) or a secrets manager; do not store plaintext. Security-score item.
- **Password-reset token logged** (`api/auth.py:245` logs `logger.warning("Password reset token for %s: %s", email, token)`). The code comment says send via SendGrid in production; the TODO is honored only in prod. Remediation: remove the `logger.warning` token leak and wire SendGrid email.
- **`orders.items_json` is an unstructured `Text` blob** (`models/order.py:43`, `alembic ...:127`). No schema constraint that `total_weight_kg` equals the sum of item weights or that item SKUs exist. Remediation: introduce a `products`/`order_items` table with FK constraints (requires schema migration).
- **Stale references to `apps/web`**: `AGENTS.md` and some paths reference a `wms-react-frontend`/`apps/web` directory that does not exist in this repo (actual UI lives in `agent-platform-ui-main`). Documentation drift.
- **Dead code**: `src/fulfillment/tools/qdrant_tools.py` and several vector-store functions are not wired to the live agent loop (Qdrant returns empty with a benign warning). Remediation: either integrate or remove.

---

## 6. Code-quality review

- **Folder structure**: clean — `api/v1/*` routers, `services/*`, `models/*`, `schemas/*`, `agents/*`, `guardrails/*`, `tools/*`, `tasks/*`, `tests/*`. Follows AGENTS.md layout.
- **Quality**: ruff + mypy strict pass; no circular imports; `Base` declarative; async SQLAlchemy 2.0 + `async_sessionmaker`.
- **Dead code**: Qdrant tooling not wired to live agents (low).
- **Duplicate code**: minimal; agent classes share a similar `AsyncAgent` base pattern.
- **Unused packages**: `slowapi` was imported but unused — now the middleware owns rate limiting; the old `limiter`/`SlowAPIMiddleware` references were removed (slowapi import retained in `main.py` only if needed — it is not, removed).

---

## 7. Security score

**71 / 100**

- +auth (bcrypt, JWT rotation, fail-closed demo, RBAC `require_admin`/`require_operator_or_admin`)
- +parameterized SQL everywhere
- +validation (422) on all inputs
- −rate limiting was entirely missing until this fix (now implemented & verified)
- −plaintext Odoo/SMTP credentials at rest
- −reset token logged in DEV (mitigated by DEBUG-gating; production uses SendGrid per TODO)
- −no CSRF token (acceptable for header JWT; flagged)

---

## 8. Performance score

**73 / 100**

- async SQLAlchemy with `pool_size=20`, async endpoints throughout.
- monitor cycle processes ≤200 shipments serially (documented in `monitor_cycle.py`); acceptable now, will need batching at scale.
- no query-level N+1 observed in reviewed services (uses `select`/`scalar_one_or_none`).
- No formal load test run in this cycle (no running Postgres/Qdrant/Odoo); scores reflect code review. Run `locust`/`gunicorn --workers` under load before real traffic.

---

## 9. Code-quality score

**84 / 100**

- Strict mypy + ruff pass, 71 modules, clear layer separation.
- −stale docs (`apps/web` references).
- −dead Qdrant wiring.
- −`items_json` Blob schema gap.

---

## 10. Production-readiness score

**70 / 100**

Ready **after** the critical/high bugs fixed in this pass + the remediation items above. Not production-ready as-is at the start of this test (demo was 500-ing, no rate limiting, routing seed broken).

---

## 11. Final answers

Is this project ready for real warehouse businesses?

**No — but it is close.** Before today the demo was fully broken (every authenticated call returned HTTP 500), order routing could never succeed with shipped seed data, and there was no rate limiting. Those three critical blockers are now fixed.

Would I recommend deploying it to production?

**Only after the remediation list is closed.** With this pass's fixes, the system boots, authenticates, validates input, routes orders end-to-end, and rate-limits abuse. The remaining blockers for a paying warehouse client are: encrypt stored integration credentials, wire real email/SMS (remove the reset-token log leak), add a real `products`/`order_items` table so weights/SKUs are validated, and run a load test.

What should be fixed before selling it to clients?

Priority:
1. Encrypt `integration_connections.api_key` and any Odoo/SMTP secrets at rest; rotate the currently-leaked demo value.
2. Remove the reset-token `logger.warning`; enable SendGrid email deliverability (already stubbed).
3. Replace `orders.items_json` Text blob with normalized `order_items`/`products` tables and FK constraints.
4. Add an integration test harness (Postgres + TestClient) and a load test for the 200-shipment monitor cycle.
5. Clean up stale docs referencing `apps/web`; remove dead Qdrant tooling or wire it into the agent loop.
