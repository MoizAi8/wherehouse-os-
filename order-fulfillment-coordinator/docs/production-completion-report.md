# Warehouse OS production completion report

2026-11-02 — **CONDITIONALLY READY**.

Local repairs, current security checks, and application regression gates pass.
Real Linux image builds/container integration and live OCI/data/operational
verification remain required before approving deployment. Nothing was pushed,
merged into main, deployed, restarted, or changed in the upstream repository.
This report supersedes earlier readiness snapshots; it does not claim live
production health or an exhaustive penetration test.

## Current architecture and Git state

One Git repository at `C:/Users/DC/wherehouse-os-`; active branch
`codex/warehouse-production-repair`. Active frontend:
`agent-platform-ui-main/agent-platform-ui-main`; active backend:
`order-fulfillment-coordinator/apps/api`. Caddy publishes 80/443; FastAPI,
Next.js, PostgreSQL, Redis, Qdrant, Celery worker and Beat use the private
Compose network. PostgreSQL/Qdrant/certificate state has named volumes.
Alembic applies schema changes. Auth uses HS256 bearer access tokens and
NextAuth credentials sessions; the API has role dependencies and rate limits.

Routing, monitoring, rerouting, communication, heuristic prediction and cost
optimization are implemented. The orchestrator persists append-style events
and Beat schedules the monitoring queue. The earlier missing queue
subscriptions are retained as fixed. Provider delivery/AI calls require
configured external services; simulation and mocks are not live fulfillment.
Archive/alternate deployment plans were not treated as active source.

The prior dependency changes were preserved in local commit `0498ff0`.
Runtime/CI/security work is in `a4d9eb3`; access/reliability/recovery work is in
`262bbd0`. Further Python security and documentation commits appear in the
final branch log. Baseline tag `codex/security-upgrades-baseline-20261102`
still points to `ba70fd7`. Only this repair branch was changed. Origin/main
was fetched at `25c01c036fb94240c6111e21b0a169a92dda2152`; it is an ancestor
and merge-tree completed without conflict. Recheck remote state before merging.

## Original OCI incident and prevention

[Run 34759400833](https://github.com/MoizAi8/wherehouse-os-/actions/runs/34759400833)
failed at Compose creation with an existing Qdrant container-name conflict on
2026-09-13, before health polling. Historical evidence is retained in
[production-readiness-report.md](production-readiness-report.md). The Node
annotation was not the incident cause. Why that live container survived or
reappeared remains unknown without host ownership/network/mount evidence.

Deployment now uses GitHub and host locking, fixed project identity, ownership
checks, unique attempt directories, exact captured application registry digests,
bounded readiness, failure propagation, and retained release pointers/config.
It neither indiscriminately removes containers nor deletes volumes. Regression
tests cover foreign ownership, existing owned resources, lock contention, failed
registry login/pull/migration/Caddy validation/TLS/readiness and successful flow.
These repairs prevent the previously unsafe local command sequence; they cannot
stop an unrelated old host script or prove the live conflict has disappeared.

## Node, installs, workflow and deployment control

Node 20.18.0 was below existing Vite/rolldown/lint engine requirements and Node
20 is EOL. The selected supported LTS is **24.22.2** (official release listing
and Docker official-image metadata checked). It is pinned in workflow env,
frontend Docker ARG and .nvmrc; package engines constrain Node 24 and npm 11.
Actual clean install, tests/build/auth used the isolated official Windows x64
Node 24.22.2 archive after SHA256 verification, with npm **11.19.1**. The system
runtime was not replaced. [Node release status](https://nodejs.org/en/about/previous-releases),
[official release index](https://nodejs.org/dist/index.json).

CI and Docker now use frozen `npm ci` with strict peers; lock deletion and
legacy peer overrides were removed. Setup-node v6 and cache v5 use Node 24;
hosted runners satisfy their documented minimum runner requirements.
Python remains 3.12; uv tooling is pinned to the tested **0.12.3** in CI and
the backend builder so the committed lockfile is used consistently.

The workflow now tests pull requests and main pushes, builds Linux images on
PRs without publishing them, and publishes images on non-PR runs. OCI deploy
requires manual dispatch, main, the correct fork, and `deploy=true`. An ordinary
merge/main push does **not** change OCI. The read-only environment API check
showed no configured production protection rules; require reviewers before a
live run. Job timeouts bound test/build/deployment runs. Actionlint passes.

## Dependency security and compatibility

Previous Next.js 16.4.3, Auth.js 4.24.15, Zod 4.6.7, matching lint config,
source-map-js 1.2.2, and React 19.2.4 were preserved. Zod remains v4; no v3
migration or UI redesign was introduced.

The current full audit exposed test-only Happy DOM and development transitive
findings missing from the prior production-only audit. After strict dry runs,
Happy DOM moved 14.12.3 to **21.0.4** (test environment only), AI SDK packages
received compatible same-major patches (`ai` 6.0.320, `@ai-sdk/openai` 3.0.135),
and vulnerable brace-expansion/js-yaml/Vite transitives received updates within
their parent ranges. The entire existing frontend suite passes on the updated
DOM. No bulk audit fix, forced dependency resolution, or test weakening occurred.

Current npm results:

* Production: **0 findings**, audit exit 0.
* Full graph: **18 moderate development-only records**, no critical/high/low;
  audit exit 1 is reported honestly. These aggregate records inherit minimatch
  findings in lint/test tools; they are not 18 demonstrated production exploits.
  npm's proposed downgrade of eslint/Next lint config is not a safe compatible
  remediation. No major override was forced. Do not expose test/dev servers or
  feed untrusted patterns into these tools. CI timeouts limit runaway jobs.

Evidence: [production npm audit](completion-npm-production-audit.json),
[full npm audit](completion-npm-all-audit.json).

The added Python audit distinguished installed/development state from the
production lock. The initial locked production scan reported 73 advisory
records across 17 packages (including duplicate aliases). Targeted updates
addressed affected aiohttp, anyio, certifi, cryptography, dnspython, h2/hpack,
MCP, multidict, settings, JWT, Starlette, urllib3 and Werkzeug versions. MCP
stays on compatible 1.x (1.30.0), respecting the Agents SDK's `<2` constraint.
Fernet's API/format is preserved and tested on cryptography 50.0.0.

Unpatched python-jose and its ecdsa dependency were removed instead of ignored.
The small JWT utility now uses **PyJWT 2.15.0**, retaining standard HS256 token
format and requiring exp/iat/sub. Seven tests cover standard prior wire-format
compatibility, expired/missing claims, wrong token type/key/algorithm. Existing
issued application tokens contain these claims; third-party legacy issuance
must be reviewed before rollout. The frozen sync also removed stale packages
that were installed but absent from the lock. `uv pip check` passes.

Final locked production **and synchronized installed** Python audits both have
**no known vulnerabilities**, exit 0. See
[Python audit evidence](completion-python-audit.json). This is advisory-database
coverage, not proof of no exploitable defects.

## Important code fixes and evidence

| Files | Problem / repair | Verification |
|---|---|---|
| workflow, frontend Dockerfile/.nvmrc/package files | Incompatible/variable Node installs; aligned LTS and strict frozen installs, manual deploy gate | Actual npm ci, build/lint/types/tests, Actionlint |
| backend pyproject/uv.lock, Dockerfile, security.py | Audited dependencies, unpatched JWT chain; targeted fixes and standard JWT codec | Frozen uv sync, package check, audits, seven codec tests, full suite |
| api/chat.py | Viewer could mutate through chat; session ID alone exposed other-user history | Operator/admin checks on explicit and email-fallback mutations; HMAC user/session storage scope; five endpoint regressions |
| database.py | SQLite debug pool returned a synchronous Connection lacking cursor | Keep the async adapter; file and memory SQLite avoid PostgreSQL pool options; real migration/API test |
| initial baseline migration | SQLite cannot add notification FKs with direct ALTER | Alembic batch mode; PostgreSQL operations remain equivalent; fresh SQLite head migration passes |
| tasks/monitor_cycle.py | Initial input failure was reported as success; pooled connections reused across task event loops | Raise on cycle_error for Celery retry; dispose before loop close; success/failure tests |
| deploy.sh, Compose, workflow | Same-SHA retries could overwrite configuration/tag state | Unique attempt directory and persisted registry digests; deployment failure regressions and semantic Compose validation |
| recover-release.sh, rollback.sh | No reviewable known-good recovery path | Non-mutating preflight; explicit schema-attested service replacement from retained digests/config; safe refusal regressions |
| verify_caddy_routes.py | Static routing validation alone did not prove dispatch/path preservation | Real loopback Caddy with explicit HTTP fixtures; eight successful routing/header checks |
| frontend README, reports/runbook | Old runtime/install commands and conflict-marker text | Updated exact commands and current evidence; diff review |

Chat's public session IDs/response shapes remain unchanged. Old rows had no
authenticated owner and remain stored but hidden; no ownership is guessed and
no records are deleted. Because scoped storage keys depend on JWT signing key,
plan key rotation and continuity explicitly. Review this behavior before live
rollout. Production auth/default-secret guards were not relaxed.

## Final executed quality gates

| Category | Result |
|---|---|
| Backend pytest | **1,180 passed**, 0 failed/skipped, 17.42 s |
| Backend Ruff / mypy | PASS; mypy 78 source files |
| Frontend Vitest | **52 passed / 11 files**, 0 failed/skipped |
| ESLint / TypeScript | PASS on Node 24.22.2 |
| Production Next.js build | PASS; existing Google Fonts require network access |
| Built-app auth | **10 passed**, real NextAuth routes against isolated backend fixture |
| Real temporary SQLite | Head migrations, registration/login/profile/bad password/health PASS |
| Chat role/isolation regressions | **5 passed**, real endpoint/SQLite fixture |
| JWT compatibility/security | **7 passed** |
| Deployment/recovery regressions | PASS within backend suite; Docker/curl mocked, no live services |
| Frozen installs / package consistency | Actual npm ci, uv sync --frozen, npm ls --all, uv pip check PASS |
| Audits | npm production PASS; npm full 18 moderate dev records; both Python scans PASS |
| Workflow | Actionlint 1.7.12 PASS; optional shellcheck/pyflakes integrations disabled because not installed |
| Shell syntax | bash -n PASS for deploy/recovery/rollback |
| Compose | Real Compose 5.6.1 semantic config/model checks PASS with explicit fake env |
| Caddy | Real 2.11.7 adapt/validate PASS; **8** real loopback dispatch/path/header checks PASS |
| Git diff / merge-tree | PASS; no merge executed |
| Docker image builds / full service startup | BLOCKED: no local Docker Engine/Desktop/daemon |
| PostgreSQL / Redis-Celery / Qdrant real integration | BLOCKED: isolated services unavailable locally |
| External AI, carrier, mail/SMS, Odoo delivery | NOT RUN: no live operations authorized |
| OCI/public TLS/DNS/firewall/VM sizing / real replacement recovery | NOT RUN: live access/change authorization withheld |

Test warnings: Starlette's test client warns that httpx support is deprecated
in favor of httpx2; tests pass and the replacement was not added merely to hide
a warning. Frontend baseline tests still emit refused localhost:3000 requests
while passing; they do not prove a running external frontend. npm noted an
unapproved optional unrs-resolver postinstall script under npm 11's policy;
no approval bypass was applied and lint/build/tests resolved their bindings.
Validator binaries were downloaded into ignored .tools and checked against
official SHA256 (Actionlint/Compose) or SHA512 (Caddy) release checksums.
No validator started a public listener; the Caddy fixture used loopback only.

## Remaining risks and release prerequisites

* **Production verification pending / high impact if misconfigured:** resolve
  the original host collision with label/mount evidence; prove correct persistent
  volumes, staging PostgreSQL migrations and encryption data, backup/restore,
  private registry access, host capacity and native Linux images. No automatic
  cleanup or schema downgrade is permitted.
* **Environment-only:** Docker image/service tests require Docker Engine or a
  hosted green PR run. Compose/Caddy semantic and loopback tests are real but
  are not equivalent to the full container stack. Linux/musl/VM architecture
  remains unverified here.
* **Operational:** production environment reviewers are not configured. Add
  them before live deployment. Manual gating protects ordinary main pushes.
* **Medium:** remaining development minimatch advisories; process-local rate
  limiting and frontend-proxy fairness; no distributed abuse test. Event append
  semantics are not verified as DB privilege/trigger enforcement. SQL schema
  qualification is not consistent everywhere. Task duplicate side effects still
  need a provider-aware staging/outbox review; no exactly-once claim is made.
* **Medium / functional limitation:** boot with only OPENAI_API_KEY is not proven
  or supported by current secure production defaults. Explicit DEBUG/SQLite
  configuration now works; no production secret/auth guard was weakened.
* **Low:** some application/provider logs can contain customer data; inspect
  them privately. Full historical-secret scanning and penetration testing were
  not completed. Prediction is heuristic; mock tests do not establish quality.
* **Topology limitation:** one stack means possible service-replacement downtime.
  True traffic-only rollback requires retained serving slots; it is not claimed.

No known unremediated critical/high dependency finding remains in the checked
production graphs. External prerequisites are explicit conditions for release,
not locally verified facts. The exact approved push/merge/deploy/recovery
commands are in [merge-deployment-plan.md](merge-deployment-plan.md); the
[runbook](production-runbook.md) covers secret names and host diagnostics.
