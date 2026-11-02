# Backend CI failure follow-up

2026-11-02. **Local fix verified; hosted CI and live deployment remain UNVERIFIED.**
This continues the existing repairs rather than replacing their verification.

## Starting state and actual failure

The workspace was clean on `main` at `e9d88ab`, a merge of the existing repair
branch performed outside this investigation. Its source tree matched
`codex/warehouse-production-repair` at `6f8ffe5`. Work stayed on the checkout
as requested; the repair branch/ref and all prior commits were preserved.
No branch was created, history rewritten, merge performed, push made, workflow
triggered, or live service accessed by this follow-up.

Authenticated read-only inspection of
[run 41354117342](https://github.com/MoizAi8/wherehouse-os-/actions/runs/41354117342)
confirmed:

* Frontend job passed.
* Backend Ruff/mypy passed; Pytest failed with **1 failed, 1,179 passed**.
* The failed case was `test_public_health_is_rate_limited_with_retry_after`:
  the first request returned 429 instead of 200, with Retry-After 1 second.
* Image build and OCI deployment jobs were skipped because their prerequisite
  failed. This run did not reach container build or deployment verification.

The failure is separate from the historical Qdrant container-name incident.
The failed step logs were stored only in ignored `.tools`, not committed.

## Root cause, reproduction, and selected solution

The middleware sampled request time, then initialized a new bucket using a
second, slightly later clock sample. The subsequent take used the earlier
request time. Its negative elapsed time subtracted a tiny fraction from the
bucket's initial one token, making it less than one and rejecting a valid
first request. This is production logic, not an incorrect test expectation.
Coarser clock resolution can make both samples equal and hide the defect.

A deterministic advancing-clock regression reproduced the exact assertion
locally **before** the source fix: 1 failed, 6 passed in the focused security
file. It patches only the rate limiter's time binding, leaving asyncio and
other modules' clocks intact. No database, Redis, Qdrant, or model request is
needed to reproduce it.

Two valid approaches were considered:

1. Clamp negative elapsed time to zero. Small, but it compensates for two
   inconsistent timestamps rather than preventing them, and still permits
   timestamp state to move backwards.
2. Initialize the bucket from the same request timestamp used to consume it.
   Selected: one clock observation per request and consistent initialization,
   without special-casing health, changing quotas, or weakening throttling.

The stronger regression also exposed floating-point under-refill at an exact
hour boundary when a reciprocal rate was precomputed. Dividing elapsed time
by the window before multiplying by capacity preserves the tested boundary.
An epsilon allowance was considered but avoided because it would add an
arbitrary acceptance tolerance. The tests cover clock steps 0, 1 ms, and 100 ms.

Retry-After now uses mathematical ceiling. The former integer-plus-one formula
overstated an exact 3,600-second wait as 3,601 seconds. For every clock case,
the test requires initial success, then 429 with Retry-After 3,600, then success
at the full refill window. It does not skip, xfail, or mock away the limiter.

## Related CI findings

The same run repeatedly logged PostgreSQL `FATAL: role "root" does not exist`
from its unqualified `pg_isready` probe. The service itself started and this
was not the Pytest failure. The readiness command now explicitly uses the
configured test user/database: `pg_isready -U postgres -d fulfillment_test`.
Setting a global PGUSER was an alternative, but explicit probe arguments keep
the change local to health checking. Real PostgreSQL probe execution awaits CI.

The run also warned that `astral-sh/setup-uv@v5` uses the deprecated Node 20
action runtime. The action is updated to v7, whose
[published action definition](https://raw.githubusercontent.com/astral-sh/setup-uv/v7/action.yml)
uses Node 24 and supports the same version/cache inputs. Python 3.12 is now
passed explicitly through its documented python-version input, avoiding reliance
on an Ubuntu runner's default interpreter. The existing uv 0.12.3 pin, Node
24.22.2 application pin, frozen lockfiles, test jobs, and manual OCI gate remain.
Leaving v5 under GitHub's forced runtime was possible but would retain the
warning and implicit compatibility dependency. This update is not claimed as
the cause or fix of the Pytest assertion.

## Changed files

| File | Change / verification |
|---|---|
| `apps/api/src/fulfillment/rate_limit.py` | Shared request/bucket timestamp, stable refill arithmetic, exact retry ceiling; focused and full tests |
| `apps/api/tests/test_production_security.py` | Deterministic clock cases and refill/retry assertions; all cases pass |
| `.github/workflows/deploy.yml` (repository root) | Correct test PG probe, setup-uv v7, explicit Python version; Actionlint passes |
| `docs/ci-backend-followup.md` | Failure evidence, alternatives, verification and remaining actions |
| `docs/production-completion-report.md` | Link this current hosted-CI follow-up rather than silently overwriting historical results |

No frontend component, API contract, database schema, dependency lock, deployment
trigger, or production configuration was changed in this follow-up.

## Verification executed after the fix

| Check | Result |
|---|---|
| Focused security and advanced suite | **60 passed** |
| Frozen backend install | PASS: `uv sync --frozen --group dev --offline` |
| Full backend under CI test settings | **1,182 passed**, 0 failed/skipped; 30.82 s |
| Ruff | PASS |
| Mypy | PASS, 78 source files |
| Frontend tests, Node 24.22.2 | **52 passed**, 11 files |
| Frontend ESLint / TypeScript | PASS |
| Next.js production build | PASS |
| Built-app authentication fixture | **10 passed** |
| Actionlint | PASS; optional shellcheck/pyflakes integrations unavailable |
| Compose semantic validation | PASS with existing explicit validation fixture |
| Real loopback Caddy routing/header fixture | **8 passed** |
| Deployment/recovery Bash syntax | PASS |
| Real Linux Docker builds/container integration | UNVERIFIED: no Docker daemon available locally |
| Real PostgreSQL/Redis/Celery/Qdrant integration | UNVERIFIED: isolated services unavailable locally |
| Updated GitHub workflow run | UNVERIFIED: no push or workflow dispatch authorized |
| Live OCI/public TLS/data migrations/recovery | UNVERIFIED: no live access/change authorization |

The CI-settings local run uses the workflow's database/cache/JWT/rate/model
test configuration. The suite's application integration fixtures use isolated
temporary SQLite or explicit mocks; it does **not** establish service-container
connectivity. Existing Starlette httpx deprecation and refused localhost:3000
test requests remain warnings, not hidden successes or new failures.

Prior production npm/Python advisory evidence remains in the completion report;
no dependency changed here and those scans were not redundantly rerun. The
remaining moderate development advisories and operational limitations remain
as documented. No complete-security or exactly-once-processing claim is made.

## Next actions requiring authorization

1. Review the local follow-up commit on the existing main checkout. The preserved
   repair branch is unchanged. No new merge is needed to put this checkout's
   fix on main; it is already based on the user's merge commit.
2. After explicit push approval, verify clean status and that origin still
   targets **MoizAi8/wherehouse-os-**, fetch origin/main, check for divergence,
   and push the reviewed commit with a normal non-forced `git push origin main`.
   Stop if remote main changed incompatibly; never reset or force-push.
3. Inspect the resulting run. Require backend/frontend tests and actual Linux
   image builds to pass; do not report the old failed run as repaired remotely.
4. Main pushes still do **not** deploy OCI. Deployment remains a separate
   explicitly approved manual dispatch with deploy=true, after the existing
   data/backup/host-conflict/registry/reviewer/TLS prerequisites are satisfied.

Overall readiness remains **CONDITIONALLY READY**, with the newly observed
backend defect repaired locally and hosted verification outstanding. Use
[production-completion-report.md](production-completion-report.md) and
[merge-deployment-plan.md](merge-deployment-plan.md) for the unchanged external
checks and deployment safety boundaries; the merge instructions there are a
historical plan now that the user has already merged the original repair.
