# Warehouse OS — Final commercial verification

## Instructor invitation and original dashboard

**Local browser acceptance passed. External HTTPS acceptance awaits authorization.** The single-use instructor invitation opened the original dashboard in fresh Edge. The restricted session received stock, ran the linked warehouse workflow, refreshed the dashboard and matched seven idle agent cards to their persisted event IDs. Order `f22840dc-3ea3-4bd6-9621-4b0b5b0b044b` was delivered, with three units on hand and zero reserved. The browser verified replay rejection, denied administration and integrations, origin enforcement, revocation and Chat History. Chat used fallback. The instructor frontend release build and 87 frontend regression tests passed.

[Instructor walkthrough and owner controls](evaluation/README.md) · [Persisted execution results](evaluation/evidence/eval-workflow.json) · [Original Agents dashboard](evaluation/evidence/verified-cards.png)

## November 22 practical instructor acceptance

**NO-GO for a writable instructor HTTPS link.** Local isolated warehouse execution PASS. Production Guest Mode PASS for read-only evaluation. Cloud isolated writable evaluation BLOCKED. Real customer fulfillment BLOCKED for live carrier and notification activation. Historical production administrator recovery is closed for this assignment. Administrator login remains NOT TESTED.

Local development HEAD, remote main and the OCI release directory matched d6a876296064434ba2015f1f73dd804490269504 during testing. OCI had 956 MiB total RAM, 336 MiB available, 895 MiB swap in use, and 13 GiB available disk. The API, PostgreSQL, Redis and Celery worker reported healthy. Beat was running. Another full stack has no demonstrated safe memory headroom there. Public browser acceptance passed the HTTPS redirect, landing, Launch Dashboard, seven guest cards and 401 rejection at the private status endpoint.

The credentials provider exchanges email/password for a backend JWT. The UI session exposes that bearer to frontend code. Operator authorization spans inventory, shipments and integration configuration. Stock/order selectors and monitoring tasks operate across the configured database. A link to an ordinary operator session cannot enforce evaluator-only scope. An independently routed evaluation origin needs its own database, signing secrets, broker/workers, sandbox dependencies, and a revocable invitation/session boundary that enforces permitted operations at the API. Redemption, revocation, CSRF, replay and cross-environment rejection are BLOCKED for instructor acceptance. No invitation or deployment candidate was issued.

**Linked operational test.** A real PostgreSQL reservation, sandbox booking with idempotent replay, signed delay/delivery events and Celery tasks produced a delivered order. Stock went from 5 on hand / 2 reserved to 3 / 0. One provider request matched the order's unique sandbox recipient. An earlier fixture run omitted explicit sandbox activation; another used a workspace-wide request count. Corrected the acceptance runner locally. Full records, input entity IDs, UTC timestamps, outcomes, booking receipt, task IDs and original dashboard screenshots are in [the evidence bundle](reports/practical-evaluation-20261122/).

| Agent | Trigger / persisted result | Event ID | UTC | Backend |
|---|---|---|---|---|
| RoutingAgent | route_selected | 2e6504c1-f97a-4d6a-9849-1ae5149c5f78 | 2026-11-22T07:29:05.204201+00:00 | PASS |
| MonitorAgent | delay_detected | 1886ac47-daf0-451d-bf16-75607b99c301 | 2026-11-22T07:29:30.519612+00:00 | PASS |
| PredictionAgent | failure_prediction | f5440d17-9d7e-4909-b602-b55f7f2687a3 | 2026-11-22T07:29:30.519612+00:00 | PASS |
| ReroutingAgent | reroute_recommended | 05268ad5-82d5-49d2-8cd5-4fba0d9b946c | 2026-11-22T07:29:30.508644+00:00 | PASS |
| CommunicationAgent | provider_accepted | 885c0e28-7878-4fd1-bc3c-6dd34858ed57 | 2026-11-22T07:29:42.819798+00:00 | PASS |
| CostOptimizer | cost_analysis | e8233f6d-d662-4835-953c-90e22fc40f4f | 2026-11-22T07:29:30.560819+00:00 | PASS |
| FulfillmentOrchestrator | cycle_complete | a4581fb6-c1cf-4311-8ee9-c202e5c18512 | 2026-11-22T07:29:30.560819+00:00 | PASS |

Booking task dd9e4c36-7be4-42f7-9c5b-6ec651a53690, monitor/orchestration task 5eabfb66-2a1f-4453-b4be-fbc8152ef9c1, outbox task 25071010-085c-4cd6-b5e7-b92d29c7ab35. Browser refresh and all seven expanded card IDs/times matched the latest database evidence. The monitoring cycle evaluated multiple fixture shipments, so some cards displayed a different shipment from the same scan. See dashboard_status versus events in the JSON.

**Instructor questions and guide**

1. Open https://140-245-218-97.sslip.io/ and click **Launch Dashboard** for login-free read-only guest access. A writable instructor invitation is unavailable.
2. Creating stock-backed orders works with an isolated operator. Guest order creation is unavailable.
3. Isolated receiving and reservation passed. On this PC an authorized local operator can open http://127.0.0.1:3385/dashboard/inventory and follow section 19 below using a new SKU such as EVAL-BOX-01.
4. All seven implementations executed. To repeat this machine's isolated linked run, use PowerShell from the repository root and run `powershell -NoProfile -File .tools/watch-20261110185156/run-evaluation.ps1`. Keep the local API, PostgreSQL and broker running. Each invocation creates a fresh SKU and order. The runner drives signed events and worker tasks. It requires local access.
5. Visit Agents, click **Refresh agent status**, expand **Execution details**, and compare event IDs and timestamps with the runner output. All seven were Idle after completion. Orders displays the delivered order.
6. Current live Gemini inference BLOCKED pending confirmed no-cost quota. Earlier live greeting and bounded tool checks are historical. English/Roman Urdu multi-turn inference, inventory accuracy and model error behavior were NOT TESTED this run.
7. Authenticated local Chat PASS for fallback response and history reload, reopen and deletion. Scroll container used overflow auto. Long-transcript scrolling and evaluator isolation NOT TESTED.
8. Local test records used the dedicated loopback database and broker. Messages went to a loopback sink. The browser fixture used ordinary sign-in and deactivated its disposable tester afterward.
9. No new P0/P1 application defect confirmed in the exercised paths. npm reports moderate advisories affecting Next 16.4.3, including GHSA-f3mh-rxg3-f5g2. App-specific exposure NOT TESTED.
10. Evaluation release deployment BLOCKED. Existing app and CI evidence: [main CI and images](https://github.com/MoizAi8/wherehouse-os-/actions/runs/43105879858), [deployment](https://github.com/MoizAi8/wherehouse-os-/actions/runs/43106874143). Local Docker executable unavailable. No new image builds or production migrations. Historical 500-scenario, worker recovery, over-allocation and duplicate-prevention results apply to the unchanged application code.
11. The instructor cannot independently complete the workflow from one HTTPS link today.
12. Remaining gates: safely hosted independent evaluation origin, restricted evaluator identity with revocable invitation exchange, safe linked workflow controls, verified inference quota, and browser acceptance against that origin. Until provisioned there is no invitation to use, reset, or revoke.

Verification date: 11 November 2026 (Asia/Karachi). Evidence timestamps retain UTC offsets. Decision: **CONDITIONALLY READY**.

## 1. Executive summary

The declared core scope—stock-backed orders, reservation, routing, dispatch, signed tracking, delay monitoring, prediction, reroute evaluation, cost analysis, durable sandbox booking and sandbox notifications—passed isolated operational acceptance. No known critical/high defect remains unresolved in that tested scope. This is not a claim that future defects are impossible, that predictions have field-validated accuracy, or that real couriers/recipients received anything.

The original dashboard is preserved. Internal UNVERIFIED remains audit data, but normal customer-facing presentation maps it to **Not yet run**. Failure maps to **Error**. Ready/Running are displayed only if supplied by the backend; this release does not invent live runtime evidence. Recent recorded successes display Idle; qualifying execution records display Completed. Diagnostics remain available in Execution details.

## 2. Release and deployment status

- Verified application candidate: `dceb5f22c8744c975eb4154da43b6f0fe4affb3b`, branch `codex/operational-readiness`.
- Previous local commits: `19df775b2e304d7c0d0ec9c57933501a89fef06e` (local routing/preview), `e4739e0` (execution outcomes and refresh).
- Main and last confirmed production release: `447b84e472ebaca73e0766c895faa48c102b2cc9`.
- Earlier application candidate: `df86fdaef23f4089032c0e04618ad31a595e5afc`.
- The report/evidence commit containing this document preserves the tested application tree. Its exact approval SHA and final CI run are supplied with the release handoff; use `git rev-parse HEAD` to identify it locally.
- **No new main push or OCI deployment has occurred. Explicit approval of the final SHA is required.**

[Application acceptance CI](https://github.com/MoizAi8/wherehouse-os-/actions/runs/43041661053) passed both jobs. [Previous authorized production deployment](https://github.com/MoizAi8/wherehouse-os-/actions/runs/42874560588) completed once for 447b84e. Main CI for that release: [42873577877](https://github.com/MoizAi8/wherehouse-os-/actions/runs/42873577877).

## 3. Architecture and execution boundaries

Next.js/React original UI → NextAuth session and same-origin API forwarding → FastAPI authorization/services → PostgreSQL durable orders, inventory ledger/reservations, shipments, booking intents/receipts, notifications, chat history and append-only agent events. Redis brokers Celery tasks; workers and Beat execute durable monitoring/outbox workflows. Qdrant is the configured vector service. Caddy terminates production HTTPS. Gemini and external Odoo/carrier/message providers sit outside the core transaction boundary.

Production uses the existing OCI Docker Compose stack and persistent volumes. The acceptance runner uses disposable PostgreSQL 16, Redis 7, Qdrant, API/frontend images, Celery prefork workers and Beat. The visible Windows stack uses separate PostgreSQL 17 at 127.0.0.1:55471/database watch_20261110185156, Redis-compatible Memurai at 56385/database 7, Celery solo, API 8385 and original frontend 3385. No production database, account, credentials, volumes or records were copied into local tests.

## 4. Seven-agent verification

The final local order was received, allocated, routed, dispatched, delayed through a signed HTTP event, processed by an actual queued monitoring cycle, notified through a loopback provider and delivered through a signed event. These are persisted records, not injected dashboard responses.

| Agent | Latest qualifying result | Event ID | Timestamp | UI state |
|---|---|---|---|---|
| RoutingAgent | route_selected | `ebe09951-4c74-4c9c-beb1-d71fa83f0c81` | 2026-11-11 14:53:45.440759+00:00 | Idle |
| MonitorAgent | delay_detected | `96538692-3615-4f39-9246-06744432feac` | 2026-11-11 14:54:08.135477+00:00 | Idle |
| PredictionAgent | failure_prediction | `c2b01431-9d23-4b73-94da-4742b721a36a` | 2026-11-11 14:54:08.135477+00:00 | Idle |
| ReroutingAgent | reroute_evaluated | `6ff5a967-fc87-41bf-845d-510f591d2301` | 2026-11-11 14:54:08.121518+00:00 | Idle |
| CommunicationAgent | provider_accepted | `27a9ba62-af18-4e13-9719-cc0d7b9a9f2d` | 2026-11-11 14:54:20.300985+00:00 | Idle |
| CostOptimizer | cost_analysis | `76ed837a-9be2-4095-b04c-c85d0679dab8` | 2026-11-11 14:54:08.144475+00:00 | Idle |
| FulfillmentOrchestrator | cycle_complete | `b8e26310-af91-4d67-9d74-1bae11f30178` | 2026-11-11 14:54:08.144475+00:00 | Idle |

Routing runs during order processing; monitoring, prediction, rerouting, cost analysis and orchestration run within the actual Celery monitor cycle. Communication runs via the actual durable outbox task and SendGrid SDK configured solely for a loopback HTTP sink. Reroute evaluation/recommendation does not imply a real carrier transfer. Cost analysis records actual configured-rate totals; it is not a claim of achieved market savings.

Failure behavior is covered by backend runtime tests (missing/stale/future evidence, failed results and recovery), worker retry/exhaustion tests, notification failure handling and booking rejection/ambiguity tests. No fabricated Active/Running state is shown. Current per-agent work-in-progress/heartbeat measurement remains unimplemented and is explicitly not claimed by the UI.

## 5. Warehouse feature verification matrix

| Feature | Verification and boundary |
|---|---|
| SKU/stock receipt and adjustment | Backend inventory suite; original UI creates SKU/location and posts receipt; ledger checked |
| Allocation/reservation/release | PostgreSQL lifecycle and concurrency tests; UI shortage rejection and cancellation release |
| Typed orders/routing | Real stock-backed order creation and stored-rate selection; insufficient stock remains pending |
| Dispatch/cancel/transitions | UI whole-order dispatch consumes reservation; pre-handoff cancellation releases it; backend transition guards |
| Shipment/delay/delivery | Real shipments and signed HTTP tracking; final delivered state and inventory reconciliation |
| Booking | Provider-agnostic sandbox intent/receipt persistence, idempotency, retry, rejection, ambiguity and worker-loss recovery |
| Monitoring/prediction/rerouting/cost | Persisted seven-agent records, configured rates, overdue shipment; approval-safe recommendations |
| Notification | Real outbox and SDK to loopback HTTP provider; accepted once; failure/duplicate/recovery coverage |
| Queue/Beat | Linux prefork retry, process death, exhaustion/recovery, duplicate task ID, Redis restart and scheduled cycle |
| Security | Backend roles/access tests; 23 built NextAuth checks; live local guest cannot read inventory |
| Chat/history | Backend intent/access/history persistence tests, built authenticated forwarding, original UI connectivity; separate bounded real Gemini probe |
| Existing pages | 13 original pages loaded with HTTP 200, no failed API calls, no customer audit label; page load is not proof of every possible mutation |

## 6. Actual business workflow

Final local order: `dbb1aa3a-e21a-45cb-a8d4-bb8287323485`; shipment: `ddc8198a-d3d3-46b5-851e-4d1285b6b658`; cycle: `164292f8-2b86-410d-9518-40a311797cc8`.

Monitor task: `4880a298-a5e7-4614-b3d2-a0287cc264b3`. Notification task: `425291d3-e241-4d93-a6a9-f192f59a3a5e`.

Received 5 units, reserved 2 (on hand 5/reserved 2), dispatched and delivered, ending on hand 3/reserved 0. One sandbox notification HTTP request was accepted. All seven qualifying outcomes were compared by event ID and timestamp between PostgreSQL, authenticated API and original cards. Complete outcomes are in [linked-workflow.json](reports/commercial-final-20261111/linked-workflow.json).

The separate original-UI inventory sequence also passed ten checks: SKU/location creation, receipt, insufficient reservation rejection, routing/dispatch persistence after reload, typed shortage, automatic typed allocation/dispatch, cancellation release, Launch Dashboard, restricted guest inventory and guest Not yet run roster. See [UI inventory results](reports/commercial-final-20261111/release-inventory-browser.json).

## 7. PostgreSQL, Redis, Celery and migrations

The exact application candidate passed 1,252 backend tests with zero failures/errors/skips and 500 PostgreSQL parameter scenarios with zero failures/errors/skips. The 500 cases are five lifecycle outcomes × five quantities × five weights × four basket sizes, not 500 independent features. The operational ledger records 519 passes including those 500; do not add these as independent counts.

Linux evidence includes normal execution, duplicate suppression, retry, killed-worker recovery, Beat scheduling, exhausted retry then recovery, notification acceptance with a single HTTP request, and Redis restart. Booking worker loss after provider acceptance recovered the same durable booking with one submission attempt. See [worker evidence](reports/commercial-final-20261111/warehouse-celery-evidence.json) and [booking recovery](reports/commercial-final-20261111/carrier-booking-worker.json).

Alembic upgraded disposable databases to `f328a76da954`. There are no migration changes between current production 447b84e and this candidate. Backup restore independently matched that source revision. Local health reports PostgreSQL/Celery true; local Qdrant is unavailable, so degraded health is accurate. Linux and current production health include Qdrant true.

## 8. Docker, OCI, backup and recovery

Both production Dockerfiles built and the full disposable Compose stack started in CI. [Release evidence](reports/commercial-final-20261111/release-evidence.json) records isolated manifest/config digests; these are not production image readbacks or published GHCR release digests.

The existing deployment preflight is unchanged: under deployment lock, create a fresh protected custom-format PostgreSQL archive, check its SHA-256, restore in a disposable container with no production mounts/network/credentials, compare Alembic revision, and stop before migrations on failure. The latest isolated backup check passed at 2026-11-11T14:51:55Z, source revision f328a76da954. This does **not** replace the mandatory fresh production backup during an approved deployment.

Current public read-only checks: HTTPS sslip.io landing 200, health 200/status ok with PostgreSQL/Celery/Qdrant true; HTTPS IP returns 308 to sslip.io. [Read-only evidence](reports/commercial-final-20261111/final-production-readonly.json).

The single-stack topology has no retained serving slot for traffic-only rollback. rollback.sh refuses to pretend otherwise. recover-release.sh --check inspects retained image/config availability; approved service replacement requires database compatibility review. No retained-host inspection or recovery was performed this turn. Independent live container digest readback remains a post-approval verification requirement; previous deployment build manifests are not presented as that readback.

## 9. Authentication and security

NextAuth and backend authorization remain enabled. The 23 built checks cover CSRF, invalid credentials, persisted sessions, bearer forwarding, tampered/expired/legacy tokens, signout, restricted guest sessions, operator precedence and guest revocation. Backend tests cover viewer write rejection and chat/history ownership. Original local UI tests confirm guest inventory isolation, API 401, and no private execution evidence in guest cards. The user entered the disposable password interactively; no password/token is included in this report/evidence.

## 10. Gemini Chat and history

[No-deployment Gemini run 43041422103](https://github.com/MoizAi8/wherehouse-os-/actions/runs/43041422103) passed ten checks, including seven bounded inference/tool cases: knowledge, arithmetic, Roman Urdu, Urdu, memory store/recall and an isolated read tool. The owner-configured free-tier flag was true; no paid service was enabled. See [Gemini evidence](reports/commercial-final-20261111/gemini-verification.json).

This existing synthetic probe runs on the unchanged production-base commit 447b84e, not against customer data or the live dashboard. The original authenticated chat/history path is separately covered by backend and built-auth regressions. Current local original Chat connects to the backend; no local Gemini key is installed. Original-production chat generation after the new deployment is still a post-approval gate; it is not claimed complete.

## 11. Test counts and evidence

| Gate | Result |
|---|---|
| Backend regression | 1,252 passed; zero skipped/failed/errors |
| Warehouse matrix | 500 passed; zero skipped/failed/errors |
| Operational ledger | 519 PASS entries, includes matrix |
| Frontend | 87 passed across 18 files |
| Built authentication | 23 checks passed |
| Local inventory/guest UI | 10 checks passed |
| Original page traversal | 13 pages, no failed API requests or audit label |
| Seven-agent browser | Exact DB/API/card IDs and timestamps, refresh, expansion, reload/navigation passed |
| Lint/types | Ruff, mypy, ESLint, TypeScript passed |
| Docker/Compose | API and frontend builds, migration/startup/readiness passed |
| Recovery and backup | Redis/prefork/Beat/notification/booking and isolated restore passed |
| Gemini synthetic | 10 checks passed; seven bounded inference/tool cases |

Full JUnit/worker/Compose artifacts are available in acceptance CI and locally at `.tools/commercial-linux-dceb5f2`. Count overlap is disclosed; these totals do not represent independent product features. Fixture-based frontend auth tests are distinguished from actual PostgreSQL/Celery operational tests.

## 12. Defects and test-harness issues resolved

1. Development rewrites incorrectly targeted port 8000 despite BACKEND_URL=8385. Fixed with regression coverage and authenticated browser verification.
2. Turbopack repeatedly reloaded the successfully authenticated page, leaving it blank. Supported dev:webpack restores stable local rendering; this is a verified development workaround, not an upstream Turbopack patch.
3. Local worker omitted the readiness queue; configured that queue and task import. Actual readiness task now succeeds.
4. Customer audit terminology exposed normal missing evidence as UNVERIFIED. Presentation now uses Not yet run, without changing internal evidence or suppressing failures. Last action/time/result are visible and technical details expand.
5. Local webhook test key read normalized Windows newlines; driver now signs the exact configured bytes. Invalid signatures were rejected before correction.
6. Competing Playwright dialog handlers caused a harness race; disposable dispatch/cancellation confirmations are accepted deterministically in that test context. No application authentication or production protection changed.

## 13. Technical limitations

- No live per-agent heartbeat/active-task instrumentation: Ready/Running are not fabricated; Idle means recent successful recorded execution, as explained on the page.
- Prediction results are tested algorithm outputs, not demonstrated real-world accuracy guarantees.
- Local Memurai/solo tests supplement, not replace, successful Linux Redis/prefork/Beat acceptance.
- Local Qdrant and Gemini inference are unavailable; Linux Qdrant and separate real Gemini probe passed.
- Single-stack recovery is service replacement, not zero-downtime traffic switching.
- Page traversal does not certify every third-party integration. External Odoo access and real provider endpoints were not exercised.

## 14. External carrier and notification activation

Only the explicitly labelled sandbox carrier adapter is activated in acceptance. TCS, Leopards, Trax and PostEx are potential future adapters; no undocumented live integration or account access is claimed. Live activation needs official documentation, credentials through an approved secret mechanism, verified idempotency/reconciliation and provider-specific acceptance.

Notifications use loopback sandbox acceptance in operational tests. Real SendGrid/Twilio recipient delivery remains an external activation dependency. No real shipment or message was sent. Gemini secret-name availability is confirmed without reading secret values into chat.

## 15. Git reconciliation

The remote development branch includes all prior commits through 447b84e plus e4739e0, 19df775 and dceb5f2. Main remains 447b84e. Application changes since production are conservative runtime outcome exposure, status refresh/details, development backend rewrites/Webpack command, professional status mapping/tests, and frontend gates in isolated CI. No database migrations, production deployment script changes, original UI redesign or new demonstration page were added.

The auto-generated Next.js AGENTS.md update was preserved and committed. Historical COMMERCIAL-EXECUTION-CHECKPOINT.md remains preserved outside this release to avoid treating stale open tasks as current instructions. No reset, force-push or discarded work occurred.

## 16. Release authorization and post-deployment gate

Approve the exact final SHA from the handoff only after its required CI is successful. Approval is not inferred from older releases. Then promote to main, wait for required CI/image manifests, and perform one controlled deployment through the existing workflow. The fresh production backup/restore must succeed before migrations.

After deployment: record workflow URL/attempt, exact release SHA, running API/frontend image identities versus the approved manifest, both HTTPS URLs, strict backend health, landing/navigation, authenticated status labels/events, guest isolation, Chat and Chat History. These checks remain **pending approval and deployment**, not passed. Do not run customer bookings, notifications or destructive warehouse operations for verification. If no safe authorized image readback mechanism exists, report that limitation rather than trigger another deployment.

## 17. Screenshots and live visual evidence

- [Original seven-agent dashboard with professional labels](reports/commercial-final-20261111/seven-agents-after.png)
- [Original dashboard](reports/commercial-final-20261111/release-dashboard.png)
- [Actual inventory operations](reports/commercial-final-20261111/release-inventory-operations.png)
- [Authenticated browser checks](reports/commercial-final-20261111/browser-regression.json)
- [All original page results](reports/commercial-final-20261111/release-pages.json)

## 18. Readiness decision

**CONDITIONALLY READY** for declared core warehouse operations with explicitly sandboxed external booking/notification integrations. All listed application acceptance gates passed for the candidate. Public rollout of the new UI is pending exact-SHA approval and controlled deployment verification. Real courier handoff, real recipient delivery, live prediction accuracy and full external ERP activation are not part of the demonstrated acceptance. These boundaries must be stated in commercial onboarding; do not market sandbox outcomes as live provider fulfillment.

## 19. Manual testing guide — original application only

### Sign in and inspect

1. Open http://127.0.0.1:3385/dashboard/agents on this workstation. Use the disposable **operator** account; admin also has write permissions. Viewer/guest cannot perform the write workflow.
2. Use `.tools/watch-20261110185156/operator-login.txt` in Notepad for interactive login. Do not paste its password into chat or commit the file. Production URL https://140-245-218-97.sslip.io/ is a different environment: do not use it for these disposable writes.
3. The frontend uses BACKEND_URL=http://127.0.0.1:8385. If restarted, use `npm run dev:webpack -- --hostname 127.0.0.1 -p 3385` with the local NextAuth configuration. The current services remain running; rotating the local session secret requires signing in again.

### Inventory, orders and dispatch

4. Open `/dashboard/inventory`. Under **New product**, enter a unique SKU and product name; click **Add product**.
5. Under **New stock location**, choose that product and **Inventory Browser Center**, set a threshold, then **Add stock location**. This existing fixture center has a configured rate to postal code 10001.
6. Select the stock location. Under **Record stock movement**, choose **Receipt**, quantity 10 and a reason; click **Record movement**. Confirm on hand 10/reserved 0 and the receipt ledger entry. Adjustment is another supported movement type and requires a reason; negative availability is rejected.
7. Under **Create order for allocation**, enter a unique reference, synthetic email, address/city/state, postal code **10001**, country US and weight 1. Click **Add order line**, choose the SKU, quantity 2, then **Create and allocate order**. Confirm processing status and reserved quantity 2. Routing is automatic for a stock-backed order. If a pending order needs retry after replenishment, the actual button is **Retry allocation and routing**; manually reserved pending orders use **Route allocated order**.
8. For the processing typed order, enter **Order dispatch reason**, click **Record order dispatch**, and confirm. Verify shipped status, consumed reservation, on hand 8/reserved 0. To test cancellation instead, create a second order and use **Cancellation reason** / **Cancel order** before dispatch; its reservation must release.
9. To test shortage, create a typed order larger than available stock. It must remain pending without holding unavailable stock. Receive more and use the retry button; do not edit balances directly.

### Controlled delay, all agents and sandbox communication

10. The UI has no fabricated carrier-event button. From repository root run:

```powershell
powershell -NoProfile -File .tools/watch-20261110185156/run-workflow.ps1
```

This guarded runner creates its own disposable SKU/order, uses the actual inventory/order services, dispatches, signs POST `/api/v1/webhooks/shipment-event` with the local-only key, enqueues actual Celery tasks on `visual-acceptance`, runs a loopback notification sink, posts delivery and reconciles stock. It refuses a non-local/different database or broker. It does not delay your manually created order; it creates a separate controlled case.

11. To reproduce carrier-event mechanics for a different isolated shipment, the supported JSON fields are `tracking_number`, `carrier`, `status`, and optional `estimated_delivery`/`timestamp`. The header is `X-Webhook-Signature`, the hexadecimal HMAC-SHA256 of the exact JSON bytes using that environment's WEBHOOK_SECRET. See the existing runner's `tracking` function for the exact implementation. Never expose the signing key or use a production key in local tests.
12. Monitoring runs through `run_monitor_cycle` in Celery. The authenticated operator endpoint POST `/api/v1/agents/monitor` also exists, but executes a synchronous cycle and is not proof of worker delivery. GET `/api/v1/agents/status` is read-only and never triggers a cycle. Do not confuse clicking Refresh with running agents.
13. On `/dashboard/agents`, click **Refresh agent status** during/after the runner. Inspect updated action/time/result and expand **Execution details** for event ID, related record and operational values. Monitoring/prediction/rerouting/cost/orchestration update after the queued cycle; communication updates after outbox acceptance. Expected labels are Not yet run, Ready, Running, Idle, Error or Unavailable according to actual backend evidence; execution results show Completed only for qualifying completed events.
14. Inspect `.tools/watch-20261110185156/linked-workflow.json` for order/shipment IDs, both task IDs, timestamps, results and stock reconciliation; `linked-worker.log` contains the real worker output. The recorded provider request count must be one. Check Orders, Inventory and Notifications in the original UI. Sandbox acceptance does not prove an external recipient received a message.
15. Booking tests use POST `/api/v1/shipments/{shipment_id}/booking` with operator authentication and a UUID idempotency key, recipient name/phone, sender phone, currency, payment mode/COD amount and explicit sandbox scenario. Sandbox must be enabled in that isolated environment; the normal local viewer is not silently reconfigured to enable booking. The exact automated recovery procedure is `tests/verify_booking_worker.py` in the isolated CI setup; use its dedicated guarded database/broker rather than production. GET the same booking route to inspect durable state. Real providers remain disabled.
16. Repeat with unique references/SKUs. Preserve prior audit events and never reset production data. The helper creates new disposable data each time; retain each evidence JSON under a new filename before repeating if comparing runs. Its separate queue prevents the general readiness worker from stealing sandbox deliveries.
