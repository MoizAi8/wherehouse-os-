# Warehouse OS — teacher demo and AI verification

## Release status

Implementation checkpoint **a56c7bc** is on `codex/teacher-demo-qa`.
[CI and real Gemini verification succeeded](https://github.com/MoizAi8/wherehouse-os-/actions/runs/41531599185).
Image publishing and OCI deployment were explicitly skipped. No main push,
merge, production configuration reload, production migration, or deployment was
authorized or performed for this upgrade.

Live production remains **00ecaa93c31d5cea8eab7c86ef27a84c9dee9b06**, from run 77.
The fresh live smoke test verified teacher NextAuth login, the cookie profile
bridge, authenticated Chat, Orders and Dashboard KPIs, logout, and rejection of
anonymous/malformed-token requests. Dependency health is green. Evidence:
`production-smoke-before-release.json` and `production-baseline.json`.

Current working public application: https://140-245-218-97.sslip.io
Planned public teacher entry after an approved deployment: the same root URL,
which redirects to `/demo` when the manual switch is enabled. The new teacher
page is currently verified locally, not live.

## 500 distinct, actually exercised scenarios

The latest result per scenario is **498 passed, 2 failed,
0 blocked, 0 unexecuted**: **99.6%** of all 500.
The retained append-only JSONL files contain **1195 attempts**,
including earlier failures, unavailable-model fallbacks and rechecks. Automated
unit tests are additional checks and are not included in the 500.

| Category | Planned | Passed | Failed | Blocked |
|---|---:|---:|---:|---:|
| Natural | 150 | 148 | 2 | 0 |
| Memory | 70 | 70 | 0 | 0 |
| Warehouse | 100 | 100 | 0 | 0 |
| Tools | 50 | 50 | 0 | 0 |
| Security | 50 | 50 | 0 | 0 |
| Reliability | 50 | 50 | 0 | 0 |
| Browser | 30 | 30 | 0 | 0 |

The `B*-failure.png` files are historical browser-attempt screenshots, retained
for traceability. `local-demo-preview.png` shows the current verified sample UI.

`results.json` contains each final scenario, purpose, status, reason, duration and
response evidence. Category JSONL files retain every attempt. All requests used
real local HTTP services; browser scenarios used actual Microsoft Edge through
Playwright, without intercepted APIs. No provider was mocked in this evaluation.
Natural/memory passes require an actual model response and nonzero token usage.
Fallbacks and unconfigured AI were never counted as successful model inference.

The 500-case model is **local CPU Ollama `warehouse-os-qa-qwen`**, reusing installed
Qwen2.5 weights, not Gemini. Local inference cost is $0. The test fixture's
80-token output cap bounds CPU runtime and can truncate otherwise relevant
answers. Passing keyword/fact assertions are not a guarantee of unrestricted
factual accuracy or polished prose.

Remaining genuine local-model failures:

- **N027**: Which star is nearest to Earth? Answer in one short sentence. Actual response: The nearest star to Earth is Proxima Centauri.
- **N092**: Aap kaise hain? Roman Urdu mein chhota jawab dein, Latin letters only. Actual response: I am fine, thank you. How can I assist you today?

The nearest-star answer is factually wrong: the Sun is nearest to Earth. The
Roman Urdu failure is a language-following error. Neither has been hidden,
hardcoded around or relabelled as a successful model response.

Two evaluator corrections were evidence based: a correct caching explanation
using “keeping a copy” was accepted, and recognizable Latin-script salam greeting
variants were accepted instead of requiring an isolated exact spelling. Original
failures remain in JSONL. Browser harness corrections fixed an incorrect sample
order expectation and waiting for a visibly nonempty log when an empty log was
the intended result.

## Real Gemini verification and zero-budget configuration

The repository secret **GEMINI_API_KEY** exists. Only its name/metadata was read;
the value was consumed inside GitHub Actions and was never retrieved, printed,
committed or put in frontend code. The owner confirmed its AI Studio project is
Free tier with no linked billing account. No billing account, purchase, paid plan
or paid infrastructure was created.

**Gemini 3.5 Flash-Lite** passed all **10 additional integration checks**: six
genuine conversational calls covering knowledge, arithmetic, Roman Urdu, Urdu
and two-turn memory; one genuine isolated read-tool call; three unauthenticated
API rejection checks. That is **seven successful cloud inference requests**, at
$0 under the owner-confirmed Free tier. These checks are separate from the 500
local scenarios. See `gemini-verification.json` for actual replies and usage.

The official endpoint is
`https://generativelanguage.googleapis.com/v1beta/openai/`. Existing SDKs and
application lockfiles are unchanged. The workflow maps the GitHub secret into
the existing masked deployment configuration as CHAT_API_KEY, with a fixed
reviewed model and official origin. It refuses Gemini deployment without
GEMINI_FREE_TIER_CONFIRMED=true. Both nonsecret repository switches are prepared:
GEMINI_FREE_TIER_CONFIRMED=true and TEACHER_DEMO_MODE=true. They have not changed
the running release.

Chat settings are independent of OPENAI_API_KEY and embedding settings. No
embedding provider, vector dimensions, Qdrant collections or existing production
data were changed. Semantic vector memory remains unconfigured; protected chat
uses persisted per-user/per-session SQL history with bounded recent context.
The public demo keeps conversation history only in its current tab.

[Current Gemini pricing](https://aistudio.google.com/docs/pricing#gemini-3.5-flash-lite)
lists free input/output for the Free tier; [billing documentation](https://aistudio.google.com/docs/billing)
describes the separate paid upgrade. Free-tier prompts may be used by Google to
improve products. Verification used synthetic data, and the public demo has no
private production records available to send. Free quotas can reject requests;
the application will not enable billing or switch to a paid provider.

No OpenCode Zen credential exists in the authorized store. The supplied
`C:\Users\DC.local\share\opencode\auth.json` path does not exist; the actual
store is under `C:\Users\DC\.local\share\opencode\auth.json` and lists only
Ollama. To configure Zen later, run `opencode auth login` locally and enter any
credential privately through its provider flow. Do not put keys in this report,
source, command arguments or chat. Current Zen free-model access is restricted
to the OpenCode client, so it was not used as a free direct API for this web app.

## Fixes and security boundaries

- Await synchronous SDK wrappers that return coroutines before recording circuit
  success/failure. Previously valid model calls fell back after receiving an
  unawaited coroutine. Regressions cover wrapped success, failure and sync calls.
- Commit chat history and issued approvals before returning success. The older
  dependency teardown raced immediate follow-up requests, losing conversational
  context. All 70 real memory cases were rerun against the corrected server.
- Keep untrusted user/assistant history in their own message roles, scoped by
  authenticated identity and session, with bounded context. General questions
  no longer accidentally trigger warehouse count/action keyword handlers.
- Return warehouse numbers from actual SQL/tool evidence, refuse unsupported
  production inventory quantities, and distinguish seven defined components
  from verified runtime availability. Viewing agent status no longer starts a
  monitoring/rerouting cycle. Workflow animations are labelled simulations.
- Require explicit one-use, five-minute, identity/session/message/action-bound
  approvals before protected chat creates orders or routes approved pending
  orders. Tokens are stored hashed; replay, changed messages, other identities
  and viewer mutations are rejected. Creation does not automatically dispatch.
- Keep all private JWT/role/CSRF controls intact. Demo mode never sets DEBUG or
  makes a transient administrator. Public demo data is a separate in-memory,
  query-only SQLite database: eight sample orders, four inventory SKUs and seven
  component definitions. No production database dependency or write tool is
  reachable from demo handlers.
- Rate-limit public demo reads and chat even when the general development rate
  switch is disabled. A shared atomic daily model-request quota bounds abuse;
  database views remain available after inference quota exhaustion.
- Fix SQLite datetime subtraction in duration KPIs and distinguish completed
  on-time deliveries from currently delayed active shipments. A real SQLite
  regression verifies a two-day delivery and correct completed denominator.
- Prevent stale demo data from briefly appearing beneath a newly selected view.
  Keep public demo access available even with an expired protected-session cookie.

The additive migration `d5e8f1a2b3c4` creates only `chat_approvals`. A rehearsal
upgraded a synthetic database from the current production revision and verified
all **11 existing table schemas and row hashes remained identical**. This is
not a production migration. Evidence: `migration-rehearsal.json`.

A fresh private PostgreSQL custom-format backup was created on the existing
server at `/home/ubuntu/fulfillment/recovery/pre-teacher-demo-20261102T215815Z/postgres.dump`.
It is 27,286 bytes; the archive manifest was validated and its SHA-256 is saved
in `database-backup.json`. The dump was not downloaded, committed or restored.
This validates the archive format, not a full restore rehearsal of production.

## Regression and quality review

- **1,197 backend tests passed**, locally and in CI; Ruff clean and mypy clean
  across 83 source files.
- **66 frontend tests passed**, locally and in CI; TypeScript, ESLint and the
  production Next.js build passed. **15 built NextAuth checks passed**.
- **30 actual browser scenarios passed**. Four additional browser checks verify
  unconfirmed/cancelled actions preserve record counts, confirmation forwards
  through real NextAuth exactly once, and creation leaves the order pending.
- **10 proposed Caddy route-ownership checks passed** with local upstream
  fixtures. Actual installed production Caddy **2.11.4** accepted the proposed
  configuration in read-only adaptation. Neither test issued a certificate.

Representative review, alongside the explicit automated rubrics:

| Criterion | Evidence and practical limits |
|---|---|
| Conversational naturalness | N061/N064 are brief, relevant greeting/farewell responses. N067 identifies itself as AI. Some local explanations are verbose or truncated by the QA cap. |
| Relevance | N076 gives the requested antonym; N079 uses the requested queue analogy; N105 explains communication clearly. N101 starts a useful comparison procedure but is truncated. |
| Context retention | 70 actual multi-turn cases, including ten topic-switch cases, plus real Gemini memory store/recall. History is bounded, not unlimited long-term semantic memory. |
| Factual accuracy | Stable fact and arithmetic assertions are explicit. N027 remains a genuine wrong answer. No model can be described as universally accurate. |
| Warehouse accuracy | 100 database assertions verify sample isolation, real private fixture reads, filters, metrics, inventory and recorded agent status. |
| Tool correctness | 50 tool scenarios plus four real confirmation UI checks. Public tools are read-only; external production dispatch/email/SMS were not invoked. |
| Authorization | 50 security scenarios verify JWT signature/expiry/type/stored role, cross-user history isolation, anonymous rejection and demo-off behavior. This is not an exhaustive security audit. |
| Error handling | 50 reliability scenarios cover invalid schemas, routes, limits, fallback disclosure, rate limits and degraded local dependencies. |
| Reliability | Failures and blocked attempts remain visible. Gemini's seven requests passed; this small sample does not establish unlimited free quota or long-term service availability. |
| User experience | All eight sample views, filters, chat, clear/history isolation, mobile layout, keyboard use and ordinary protected login were exercised in a real browser. |

## OCI and direct-IP HTTPS

Existing server: **140.245.218.97**, x86_64, approximately **956 MB RAM plus 2 GB
swap**. The existing 4.7 GB local model cannot safely run there alongside the
production stack. No model was installed on OCI and no Windows AI port was
exposed publicly. Caddy owns ports 80/443; frontend:3000 and api:8000 remain
internal, with PostgreSQL, Redis, Qdrant, Celery worker and beat in the existing
Compose stack. Frontend/backend images are the existing GHCR deployment units.

Actual current release directory:
`/home/ubuntu/fulfillment/releases/00ecaa93c31d5cea8eab7c86ef27a84c9dee9b06-41515031459-1/order-fulfillment-coordinator`.
The sslip hostname resolves to the same public IP and has a trusted DNS-name
certificate expiring January 31, 2027. Direct-IP HTTPS currently fails trusted
TLS validation because a suitable IP certificate has not been deployed.

Prepared Caddy configuration requests a publicly trusted Let's Encrypt IP
certificate using its shortlived ACME profile and handles IP clients that omit
SNI. After trusted TLS terminates, it redirects to the canonical hostname while
preserving the path/query. This maintains one NextAuth cookie/CSRF origin.
HTTP-IP access also redirects. A redirect alone does not fix an invalid HTTPS
certificate; actual issuance and renewal must be verified after authorization.
The canonical hostname must remain operational if IP issuance is unavailable.
No self-signed bypass, domain purchase, server replacement or new paid service
is part of the change.

See [Let's Encrypt IP-certificate availability](https://letsencrypt.org/2026/01/15/6day-and-ip-general-availability)
and [Caddy's explicit ACME profile configuration](https://caddyserver.com/docs/caddyfile/directives/tls).

## Owner control and remaining release gates

There is **no automatic demo expiration**. The owner can restore the normal
landing/login flow by changing **TEACHER_DEMO_MODE=false** and redeploying through
the existing pipeline. No authentication code rewrite or data deletion is needed.
The daily inference quota is not an expiry and does not turn demo mode off.

Before release: obtain explicit authorization for the final main push and one
OCI deployment; require normal CI and Docker image builds to pass; confirm the
fresh backup is still current; deploy once through the existing immutable-image
pipeline; then test live anonymous demo, real Gemini conversation, protected
teacher login, API rejection boundaries, dependency readiness and trusted IP TLS.
Docker is unavailable on this Windows host, so new images have **not** yet been
built here. The authorized Gemini-only CI run deliberately skipped publishing
and deployment. No production success is claimed for this unreleased upgrade.

Reproduction commands and fixture boundaries are in `qa/README.md`.
