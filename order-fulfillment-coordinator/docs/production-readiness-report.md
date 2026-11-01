# Production recovery verification report

> Historical snapshot. Current runtime, security, workflow gates and verification
> are documented in [production-completion-report.md](production-completion-report.md).

2026-11-02 — **NOT READY: unresolved critical blockers.**

**Dependency follow-up:** targeted security updates have since been installed
after compatibility checks. The final production npm audit has zero critical
and zero high records. The original advisory/declined-install section below
is the historical investigation snapshot. See the current
[security upgrade verification](security-upgrade-verification.md) for versions,
checkpoint, peer checks, authentication tests, and remaining CI engine limits.
The OCI/rollback/Docker verification blockers still apply.

Repairs are local on `codex/warehouse-production-repair`. The initial working
tree was clean. This is one Git repository rooted at `C:/Users/DC/wherehouse-os-`,
with `origin` pointing to `MoizAi8/wherehouse-os-` and an `upstream` remote to
`muhammadharis-web/wherehouse-os-`. No commit, push, merge, live SSH session,
deployment, restart, credential rotation, or infrastructure modification was
performed. Read-only GitHub Actions log retrieval was authorized.

## Confirmed OCI failure

[Run 34759400833](https://github.com/MoizAi8/wherehouse-os-/actions/runs/34759400833)
corresponds to commit `25c01c036fb94240c6111e21b0a169a92dda2152`, run title
`fix(ci): correct OCI health check target to use Caddy` (#63).

At **2026-09-13 13:26:22 UTC**, Docker reports:

```text
Conflict. The container name "/order-***-coordinator-qdrant-1" is already in use
```

The run then reports `Process exited with status 1`. These are GitHub-masked
log values. Image builds had finished; Compose was creating the network and
infrastructure containers. The failing command was:

```bash
sudo docker compose -f docker-compose.prod.yml up -d --build
```

It followed `down --remove-orphans` in the old SSH step. The health polling
was **not reached**, so the Caddy-target change did not cause this particular
exit. SSH authentication, file copy, Docker access, and remote builds worked
in that run. Current live health remains unknown.

The immediate cause is confirmed name ownership/existence conflict. Why the
container survived or reappeared is **not established**. Concurrent runs,
different ownership labels, or stale Compose state are hypotheses. Host
container labels, mounts, networks, and concurrent-operation history are the
remaining evidence required; see the runbook's read-only commands. Automatic
removal would be unsafe without that evidence.

The checkout Node 20 annotation is separate. Checkout was upgraded to v5,
which uses Node 24; this does not change the application's pinned Node runtime.
[Checkout release information](https://github.com/actions/checkout/releases).

## Architecture and operational scope

The active backend is `order-fulfillment-coordinator/apps/api/src/fulfillment`;
the active frontend is the doubly nested `agent-platform-ui-main` application.
The workflow, those Dockerfiles, production Compose, Caddyfile, and deployment
scripts are authoritative. Other deployment plans describe different systems
and were not used as operational instructions.

FastAPI registers auth/chat and versioned order, shipment, carrier, analytics,
agent, settings, fulfillment-center, integration, webhook, and WebSocket routes.
Bearer JWT authentication checks active users; role dependencies protect
operator/admin operations. Production boot refuses insecure default secrets.
Registration creates viewers. Global backend rate limiting returns 429 with
Retry-After. Webhooks use HMAC signatures. PostgreSQL models and Alembic
migrations hold durable state. Caddy is the only published service.

Celery Beat schedules monitor cycles on `monitoring`; health tasks use `health`.
The orchestrator composes monitoring, rerouting, communication, prediction,
and cost optimization, using DB sessions and append-style AgentEvent creation.
Routing and intent analysis support ingestion/chat workflows. Prediction is
heuristic code, not a trained predictive service. Fulfillment-center selection
currently orders by capacity, not geographic distance. Optional mail/SMS
providers simulate behavior without configuration. Qdrant collections and
OpenAI embeddings depend on real external/provider access.

Existing tests exercise many real methods with mocked persistence/providers;
some advanced cases explicitly use generic mock agents. Their counts are
not proof of live end-to-end fulfillment, provider delivery, or agent quality.
No paid model calls, real customer notifications, Odoo writes, or external
order operations were performed.

## Fixed issues and verification

| Issue | Severity | Cause and repair | Verification |
|---|---|---|---|
| Destructive host cleanup and full-stack teardown | High | Removed service disabling, port kills, global container removal, `down`, and pruning; serialize CI and host operations | Bash mocked command-flow/failure tests |
| Qdrant name conflict lacks ownership guard | High | Refuse unexpected project/service labels; retain resources and report conflict | Conflict and lock regression tests; host recovery still required |
| CI-built images were not deployed | High | Compose now selects GHCR SHA images; deploy pulls and uses `--no-build`; temporary scoped registry auth | YAML/model checks and command-flow tests; real pulls blocked |
| Secrets inserted as shell source and broad source upload | High | Selected settings encoded as literal dotenv; masked transfer; restrictive permissions; copy only deploy files; verify SSH fingerprint | Encoder tests, workflow review |
| Caddy strips API/health paths and mixes public/internal origins | High | Preserve paths; explicit frontend-owned NextAuth/chat/AI handlers; fixed internal upstreams; automatic TLS | Route/source review; real Caddy runtime blocked |
| Private host-port checks and weak health match | High | Remove host PostgreSQL probe; require exact JSON dependency readiness, HTTPS Host/SNI, frontend and session checks | JSON and command-flow regressions; live probes not run |
| Missing migration step and unsafe rollback claims | High | Run Alembic after infrastructure readiness, retain release metadata/images; broken rollback refuses safely | Migration-failure tests; real schema migration and traffic rollback unresolved |
| Celery queues and inconsistent service environment | High | Worker consumes `celery,monitoring,health`; shared API settings for worker/beat; cap concurrency; disable misleading Beat worker healthcheck | Compose environment inspection; real task execution blocked |
| AI endpoint could bypass backend auth/failure with direct model call | High | Require session token; preserve backend refusal; fail closed; validate input; use exact `/api/chat`; remove public-key/browser fallback | Five route regression tests; frontend suite/build |
| Expired sessions silently signed into a shared demo account | High | Production refresh no longer attempts shared demo credentials; users must authenticate again | Production session regression test |
| Integration encryption accepted invalid keys/plaintext in production | High | Validate Fernet key at boot; refuse missing/invalid key and decryption failures outside DEBUG | Production security tests; legacy data audit required |
| Rate-limit bucket leak and proxy client identity | Medium | Expire effectively refilled idle buckets; trust proxy headers on the private API network | Idle-client and 429/Retry-After tests; proxy spoofing boundary reviewed |
| Docker build contexts could include local secrets/dependencies | High | Add backend/frontend dockerignore files | Source review; Docker builds blocked |
| Test mock breaks TypeScript; build scans outside project | Medium | Declare bytes buffer/offset and construct compatible Buffer; pin Turbopack root | Frontend tests, lint, types, production build |
| Script line endings / wrong Qdrant example address | Low | Enforce LF shell files; document internal Qdrant URL and release settings | Bash syntax / example review |

`handle_path` stripping is documented by
[Caddy](https://caddyserver.com/docs/caddyfile/directives/handle_path).
Proxy header trust is configured according to
[Uvicorn settings](https://uvicorn.dev/settings/). Wildcard forwarding trust is
appropriate only while the API is unpublished and all Docker network members
are trusted. Do not expose its port with that setting.

## Security findings remaining

The executed `npm audit --omit=dev --json` reported **2 critical, 5 high,
2 moderate, 4 low** dependency records. These are package severity aggregates,
not 13 independently demonstrated exploits. The full audit is retained in
[npm-audit-production.json](npm-audit-production.json).

Critical aggregate records include Next.js and next-auth. High records include
nanoid, postcss, sharp, source-map-js, and zod. Advisory applicability varies;
for example an OAuth finding may not apply to the configured credentials
provider, while Next.js server vulnerabilities still require remediation.
[Next.js advisory](https://github.com/advisories/GHSA-2464-fhr4-w9xw) and
[Auth.js advisory](https://github.com/advisories/GHSA-x445-f3h2-j279).

Patched compatible candidates were queried: Next.js/eslint-config-next 16.4.3,
next-auth 4.24.15, zod 4.6.7. The dependency-installation request was declined,
so no package or lockfile changes were applied. Approve a targeted dependency
repair, regenerate the lock, rerun the audit, and verify all remaining transitive
records. Do not assume these three updates eliminate every finding. No Python
dependency advisory audit was executed; Python dependencies remain unaudited.

Other material remaining risks:

* **High:** live container conflict and actual resource ownership are unverified.
* **High:** traffic-only rollback and exactly-one-backend deployment invariants
  remain unsupported. No zero-downtime guarantee is made.
* **High:** existing schema/Alembic baseline, legacy plaintext integration rows,
  provider credentials, backups/restores, and external TLS/DNS need staging/host
  verification. Production encryption changes intentionally reject bad data.
* **Medium:** API boot with only OPENAI_API_KEY is still unsupported: defaults
  point to PostgreSQL and production guards require security settings. The old
  SQLite debug pool override is also suspect. Fixing this needs a clear secure
  local profile; no production auth guards were weakened to satisfy it.
* **Medium:** schema qualification is not consistently explicit across model/SQL
  code. Append-only events are an application convention, not a verified
  database privilege/trigger constraint.
* **Medium:** frontend manifest/lock drift and CI lock regeneration prevent
  reproducible builds; base/dependency images include mutable tags, notably
  Qdrant `latest`. Dependency/image pinning requires tested approved updates.
* **Medium:** task retries are configured, but duplicate side-effect protection,
  cross-loop async pool behavior, scheduler liveness, and real queue recovery
  were not fully demonstrated. Monitoring failure handling can report anomalies
  instead of raising for a task retry. Provider simulation is not delivery.
* **Medium:** frontend-owned handlers/NextAuth do not have a separately proven
  universal rate limiter; backend limiting is process-local and proxy wrappers
  can aggregate client identity. A distributed abuse/fairness test remains.
* **Low:** provider/application logging can include PII and detailed errors.
  Inspect logs privately; a comprehensive redaction audit was not completed.

No tracked dotenv/private-key files were found by the filename inventory.
This was a targeted source review, not a full historical secret scan or
penetration test. No secret values are included in this report.

## Verification results

See the final verification entry below for the last executed counts. Baseline:
1,129 backend and 46 frontend tests passed. Backend Ruff and mypy passed before
changes. Frontend lint passed; baseline TypeScript failed on BytesLike mock
members, now repaired. Existing UI components, public response contracts,
business logic, dependencies, and visual design were preserved.

| Category | Status and scope |
|---|---|
| Backend tests | PASS baseline and regression runs; includes mocked deployment and production security coverage |
| Backend Ruff / mypy | PASS, including 78 source files for mypy |
| Frontend tests | PASS, 52 tests across 11 files, including auth/failure and production-session regressions |
| Frontend ESLint / TypeScript | PASS after mock correction |
| Next.js production build | PASS with network access for existing Google Fonts; sandbox-only build was blocked fetching fonts |
| Shell syntax | PASS `bash -n` on deploy and rollback scripts |
| Workflow/Compose YAML | PASS parse, service inventory, private-port and inherited environment assertions |
| Docker Compose semantic config / image builds / Caddy adaptation | BLOCKED: Docker/Compose executable and daemon unavailable locally |
| Real PostgreSQL migrations / Redis-Celery / Qdrant / provider integrations | NOT RUN: isolated services and authorized external test credentials unavailable |
| Public health / real frontend-backend login / OCI firewall / TLS | NOT RUN: no live deployment authorized or accessed |
| Traffic rollback | BLOCKED: topology lacks retained serving slots |
| npm production advisory audit | EXECUTED, FAIL: critical/high records unresolved; installation declined |
| Python advisory audit | NOT RUN |

The frontend tests emit pre-existing refused localhost:3000 requests but pass;
no frontend dev server was running. Deployment tests mock Docker and curl:
they verify shell control flow, not container startup or live readiness.

Final backend execution: **1,157 passed in 8.22 seconds**, comprising the
1,129 existing tests, 22 deployment regressions, and six production-security
tests. Ruff passed; mypy reported no issues in 78 source files. Final frontend
tests: **52 passed**. No existing tests were removed or weakened.

## Changed files

Paths below are relative to the Git repository root; no files were deleted.

| File | Reason |
|---|---|
| `.gitattributes` | LF shell scripts |
| `.gitignore` | Exclude release metadata and test state |
| `.github/workflows/deploy.yml` | Serialized SHA-image deployment, safe config transfer, SSH fingerprint, checkout warning |
| `.github/scripts/prepare_deploy_env.py` | Literal settings encoding and validation |
| `agent-platform-ui-main/agent-platform-ui-main/next.config.ts` | Bound Turbopack root |
| `agent-platform-ui-main/agent-platform-ui-main/.dockerignore` | Exclude secrets/cache/dependencies |
| `agent-platform-ui-main/agent-platform-ui-main/src/__mocks__/@exodus-bytes.ts` | Correct TypeScript buffer contract |
| `agent-platform-ui-main/agent-platform-ui-main/src/app/api/ai/chat/route.ts` | Authenticated fail-closed backend proxy |
| `agent-platform-ui-main/agent-platform-ui-main/src/app/api/ai/insight/route.ts` | Require auth and correct backend path |
| `agent-platform-ui-main/agent-platform-ui-main/src/app/api/ai/suggest/route.ts` | Require auth and correct backend path |
| `agent-platform-ui-main/agent-platform-ui-main/src/lib/ai/client.ts` | Remove public API-key/browser mode |
| `agent-platform-ui-main/agent-platform-ui-main/src/lib/session.ts` | Disable production demo-account fallback |
| `agent-platform-ui-main/agent-platform-ui-main/src/__tests__/AIChatRoute.test.ts` | Auth and failure regressions |
| `agent-platform-ui-main/agent-platform-ui-main/src/__tests__/SessionSecurity.test.ts` | Production session regression |
| `order-fulfillment-coordinator/.env.example` | Container Qdrant address and image inputs |
| `order-fulfillment-coordinator/README.md` | Link authoritative recovery instructions |
| `order-fulfillment-coordinator/apps/api/.dockerignore` | Exclude secrets/venv/local state |
| `order-fulfillment-coordinator/apps/api/Dockerfile` | Trusted proxy identity on internal network |
| `order-fulfillment-coordinator/apps/api/src/fulfillment/config.py` | Validate production Fernet key |
| `order-fulfillment-coordinator/apps/api/src/fulfillment/encryption.py` | Production encryption fails closed |
| `order-fulfillment-coordinator/apps/api/src/fulfillment/rate_limit.py` | Reclaim idle client buckets |
| `order-fulfillment-coordinator/apps/api/tests/test_deployment.py` | Offline deployment regressions |
| `order-fulfillment-coordinator/apps/api/tests/test_production_security.py` | Encryption and rate-limit regressions |
| `order-fulfillment-coordinator/docker-compose.prod.yml` | SHA images, queues, shared settings, volumes, health semantics |
| `order-fulfillment-coordinator/infra/caddy/Caddyfile` | Preserve paths, frontend handlers, internal upstreams, TLS |
| `order-fulfillment-coordinator/infra/scripts/deploy.sh` | Locked staged deployment with migration and readiness |
| `order-fulfillment-coordinator/infra/scripts/check_readiness.py` | Strict dependency JSON validation |
| `order-fulfillment-coordinator/infra/scripts/rollback.sh` | Refuse unsafe unsupported rollback |
| `order-fulfillment-coordinator/docs/npm-audit-production.json` | Actual advisory evidence |
| `order-fulfillment-coordinator/docs/production-runbook.md` | Recovery, settings, approvals, deployment and rollback procedure |
| `order-fulfillment-coordinator/docs/production-readiness-report.md` | Findings, verification, limitations, changed files |

## Deployment decision

Follow [production-runbook.md](production-runbook.md) after security updates,
Docker/staging verification, live-conflict investigation, and explicit owner
approval. Current verdict is **NOT READY**. Local green tests do not establish
a successful deployment, a complete security audit, or real integration health.
