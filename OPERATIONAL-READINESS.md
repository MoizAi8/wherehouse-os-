# Warehouse OS operational readiness audit

## Isolated Linux and notification acceptance

The development-only workflow builds both production Dockerfiles locally on an Ubuntu runner, boots the production Compose services with disposable configuration, checks strict backend readiness and frontend-to-backend connectivity, and exercises the pinned PostgreSQL and Redis images with Celery prefork. It does not log into a registry or use production secrets. Run 41845863352 verified image builds, container startup and seven worker scenarios. Its later PostgreSQL regression command failed due to the Compose working directory. The workflow now runs Compose commands from the coordinator directory.

Notification intents are persisted with the warehouse transaction and deduplicated per shipment, tracking number and channel. The scheduled outbox worker commits its claim before contacting the provider. Explicit throttling retries with bounded backoff. A permanent rejection is terminal. A timeout, ambiguous provider response or expired worker claim is recorded as unknown for reconciliation and is never automatically resent. Provider acceptance is recorded separately from physical delivery in the audit trail. No live communications are used in acceptance.

Timestamped signed carrier events use the existing order lock to enforce event order. Exact replay of the last event is idempotent. Older, conflicting, implausibly future and subsequent untimestamped updates are rejected. Legacy integrations can submit untimestamped events until they opt into timestamped updates. A route change clears its old event cursor.

The Linux workflow uploads an operational evidence ledger from actual worker artifacts and selected warehouse regression cases. The 500-scenario gate remains open. External carrier booking and live delivery need authorized provider access, and ambiguous notification outcomes still need provider-side reconciliation.

## Cancellation and worker recovery checkpoint

Routed typed orders can be cancelled before dispatch or carrier activity. Cancellation locks the order, releases its reservations, restores center capacity, records the shipment as cancelled, and preserves the route and ledger history. Viewer writes, later carrier events, and dispatch of a cancelled order are rejected. Cancelled shipments are excluded from monitoring and cost totals. The shipment enum migration blocks database downgrade when cancelled shipments exist. Any application rollback after recording a cancellation must use an image that understands the new shipment status.

The PostgreSQL monitor worker now serializes repeat deliveries of the same task ID and stores the result in the same transaction as cycle evidence. A replay returns the original cycle even after its broker result was removed. This protects database effects for the same task ID. External notification delivery still needs a separate durable outbox and provider-side reconciliation before automatic sending can be treated as safe across a worker crash.

On a disposable PostgreSQL 17 database and the loopback Memurai Developer 4.1.7 Redis-compatible server, a real Windows Celery solo worker passed queued monitoring, duplicate replay, retry after a simulated database fault, forced worker termination and recovery of the same queued job, and periodic dispatch from Celery Beat. The run persisted RoutingAgent, MonitorAgent, PredictionAgent, ReroutingAgent, CostOptimizer and FulfillmentOrchestrator records. CommunicationAgent separately passed both accepted and rejected loopback HTTP scenarios using the actual SendGrid and Twilio SDKs. These checks establish the internal behavior and SDK contracts. Provider acceptance, carrier booking, and Linux prefork remain separate gates.

The recovery harness is `order-fulfillment-coordinator/apps/api/tests/verify_celery_recovery.py`. Create and migrate a fresh disposable PostgreSQL database named `worker_acceptance` at loopback port 55471. Use an isolated broker on loopback port 56379 with `CELERY_BROKER_URL=redis://127.0.0.1:56379/13` and `CELERY_RESULT_BACKEND=redis://127.0.0.1:56379/14`. Set `DATABASE_URL` to the disposable database, `ALLOW_AUTOMATIC_REROUTING=false`, and `WAREHOUSE_ACCEPTANCE_OUTPUT` to a fresh artifact directory. Run `python tests/verify_celery_recovery.py` from the API checkout. The harness temporarily renames the fixture shipment table and kills only the worker it started.

Both production image builds were attempted with `docker compose -f docker-compose.prod.yml build api frontend`. The local Docker named pipe did not exist and there was no installed Linux runtime. The next infrastructure gate needs an isolated Linux Docker host for both image builds and recovery under the production PostgreSQL/Redis versions and Celery prefork pool. Do not use the live OCI database or broker for failure injection. Remaining product gates include provider-side booking and delivery, notification outbox recovery, and broader operational acceptance toward the 500-scenario target.

Final local evidence for this checkpoint includes 1,230 passing backend cases with zero skips, 74 frontend tests, 23 authentication checks, nine browser checks, and seven real worker scenarios. The PostgreSQL cancellation-versus-dispatch race returned one success and one conflict with consistent final reservations. Alembic upgraded and rolled back both migrations on an empty disposable database and refused to remove cancellation support from a populated one. The worker reached terminal failure when the database fault outlasted its retry budget, wrote no completion receipt, and processed a new task after repair. Worker task IDs and cycle IDs were captured in `.tools/celery-exhaustion-final/warehouse-celery-evidence.json`. The regression suite count is separate from the 500-scenario operational target.

## Typed fulfillment checkpoint

**Commercial status remains NOT READY.** Orders with typed SKU lines now attempt automatic allocation and routing when created. Every requested SKU must be stocked in the required quantity at a single eligible center with a configured route. The reservation rows reference the order lines. Allocation, route evidence, shipment, and center capacity change together. Shortages or routing failures leave a pending order with no partial reservations. Operators can retry allocation from Inventory after replenishment. Existing orders without typed lines retain their original behavior.

- Dispatch for a typed order verifies every line against its reservation and consumes all reservations in one transaction. An accepted retry returns the existing dispatched state. Typed reservations cannot be consumed or released individually. The operator's dispatch record advances the order to shipped and records an audit event. Carrier delivery still requires an authenticated shipment event, and that event cannot complete an order before dispatch.
- A routed typed shipment enters monitoring only after operator dispatch. Manual status patches on typed orders are restricted to cancelling a pending order. Routed cancellation, return-to-stock reconciliation, external shipment booking and full carrier event ordering remain open.
- Migration `c8e2401a52df` adds order lines and an optional reservation link. Existing orders require no backfill. The migration guards against destructive downgrade when typed lines exist.
- Development Compose now starts the Celery binary included in the runtime image, consumes the monitoring queue, uses the project Redis service explicitly, and gives worker and Beat appropriate container health settings. Runtime and restart verification still require a Linux container host.

### Verification sequence

On a disposable Docker host, prepare a local `.env` from `.env.example` with test-only secrets. From `order-fulfillment-coordinator`, run `docker compose -p warehouse-acceptance up -d postgres redis qdrant`, then `docker compose -p warehouse-acceptance run --rm api alembic upgrade head`, and `docker compose -p warehouse-acceptance up -d api celery-worker celery-beat`. Keep this stack separate from business deployments. Connect the existing frontend to the isolated backend. A production-equivalent worker test must capture task IDs, persisted outcomes, and database state across worker interruption and duplicate delivery. A running container alone does not meet that gate.

For the typed workflow, create at least two SKUs with stock and a configured lane at the same center. Use **Add order line** in Inventory and submit exact quantities. Verify that the order shows its persisted lines, reserved quantities, assigned center and internal tracking. Record whole-order dispatch and check the movement ledger. Create an order that exceeds available stock and confirm it stays pending and no stock is reserved.

### Checkpoint evidence

- PostgreSQL 17 and SQLite API workflows passed. On PostgreSQL, three concurrent orders each requested three units of both SKUs, with six of each available. Two allocated and routed, and the third remained pending. A forced failure after the first reservation left no partial reservation or tracking number. Two concurrent dispatch requests consumed each allocated line once. Signed test events could not deliver before dispatch or regress a delivered order.
- Eight browser checks passed against the real Next.js application, FastAPI, and disposable PostgreSQL. The two added checks covered a typed shortage and automatic allocation through whole-order dispatch. Backend regression passed all 1,228 tests with zero skips. Frontend regression passed 74 tests and 23 built authentication checks. Ruff, mypy, ESLint, TypeScript, and the frontend production build passed.
- PostgreSQL upgraded and rolled back the typed-line migration on an empty test database. The populated downgrade guard stopped the rollback and left the database at `c8e2401a52df`. Both Compose manifests passed official Compose CLI configuration validation. Configuration validation does not build images or run containers.
- The next gate is an isolated Linux Docker environment for both builds, real Redis/Celery/Beat execution with populated data, and worker interruption and recovery. Then complete routed cancellation, carrier event ordering, approval and delivery integrations, and representative performance and operational acceptance coverage. The 500-scenario target remains open.

## Inventory and order allocation milestone

**Commercial status remains NOT READY.** This branch now supports a single-business inventory workflow. The existing admin and operator roles may write inventory. Viewers may read it, and public guest tokens cannot access business inventory.

- The Inventory page uses the existing dashboard and supports SKU creation, stocking at a fulfillment center, receipts, adjustments, low-stock display, order reservations, and stock movement history. Operators can create a pending order for allocation, route it from its reserved center, and explicitly record dispatch of reserved units. The existing order workflow still accepts orders without an inventory allocation requirement.
- The balance and append-only movement record change in one database transaction. The database enforces nonnegative balances with reservations bounded by on-hand stock. PostgreSQL order and stock row locks serialize order allocation and balance changes. Repeating a stock movement with the same operation ID or retrying an existing reservation does not add stock or reserve it twice. Orders with reservation history are retained for audit.
- A pending order created for allocation cannot route without an active reservation. An order cannot reserve inventory from a different center after assignment. Cancellation requires active reservations to be released first. Consumed stock requires reconciliation. The operator still specifies SKUs and quantities during allocation. The application does not yet reconcile reservations against typed order line items.
- Migration `e4f71ab892cd` adds inventory tables. Migration `f3a84d6720b1` adds a false-by-default stock requirement to existing orders. Downgrade guards stop removal when inventory or allocation-dependent orders exist. Use the repository's image rollback mechanism and preserve the database schema and inventory data for investigation. If rolling back to software that predates allocation, suspend inventory operations until a compatible release is restored.

### Priority for the remaining release

1. Add typed order lines and reconcile required quantities before routing. Complete dispatch, cancellation, replenishment, and shipment-event transitions with durable business keys.
2. Verify populated PostgreSQL, Redis, Celery, and Beat together in an isolated environment. Exercise retries, worker loss, event replay, and per-agent evidence.
3. Verify sandbox carrier and notification adapters, then require provider confirmation before recording an external handoff or delivery. Complete cost alternatives and validate prediction behavior with representative data.
4. Keep deployments single-business until tenant isolation is implemented across queries, workers, and AI tools. Verify role provisioning, business workflows at representative volume, both Docker images, and the full operational release gates.

### Repeat the inventory exercise

Use a disposable deployment with the current migrations and an operator and viewer account. Configure a synthetic fulfillment center and a matching carrier rate. Sign in as the operator, open **Inventory**, add a product and location, and receive ten units. Create a pending order for allocation. Reserving eleven units should fail, and reserving four should display six available. Route the order, then record dispatch of the four reserved units. The page should show six on hand and zero reserved. Reload and inspect the movement history. Sign in as a viewer to confirm read access and absence of write controls. In a fresh guest session, the Inventory page should require a business account.

The repository API test `tests/test_inventory_operations.py` runs with SQLite by default. Set `WAREHOUSE_INVENTORY_TEST_DATABASE` to a migrated, disposable loopback PostgreSQL database named `inventory_test` to enable the PostgreSQL case. It inserts synthetic records and must run in a dedicated test database.

### Verification results

- The backend regression suite ran 1,228 tests, all passing with zero skips. Ruff and mypy passed. The two inventory cases exercised the authenticated FastAPI routes on SQLite and PostgreSQL 17. In PostgreSQL, four simultaneous four-unit reservations against ten units returned two successes and two conflicts. The final balance and movement deltas reconciled to six on hand and zero reserved.
- Six browser checks passed against built Next.js, the actual FastAPI application and local PostgreSQL. They covered operator sign-in, product and location creation, receipts, insufficient stock, order allocation, routing and dispatch persistence across reload, viewer write rejection, and guest read rejection. The frontend suite passed 74 tests and 23 built authentication checks. Lint, TypeScript and the production frontend build passed.
- PostgreSQL upgraded from an empty database, downgraded to the live schema revision while empty, and upgraded again. Downgrade stopped on the populated test database and retained the current revision.
- The 500 operational-scenario target remains open. This milestone adds two API workflow cases and the six browser checks. Redis and Celery recovery, both Docker image builds, production external adapters and representative throughput remain unverified. No live inference was needed.

## Baseline routing and agent audit at b57a250

## Release decision

**NOT READY for commercial release or a public writable instructor exercise.**

Read-only OCI inspection confirmed release `d91dc2718c971d9c0e0f3006041bbeefeb93c9b3` from [deployment #88](https://github.com/MoizAi8/wherehouse-os-/actions/runs/41704609945). All eight containers were running. API, PostgreSQL, Redis and worker had healthy container checks. The API and frontend digests matched the release manifest. PostgreSQL was at revision `d5e8f1a2b3c4` with zero orders at inspection. A healthy worker and an empty shipment cycle cannot establish shipment processing. OCI was inspected read-only. The candidate changes require no schema migration.

## Execution paths

```text
Caddy HTTPS → original Next.js landing and dashboard
             ├─ guest session → isolated read-only sample endpoints
             └─ owner session → NextAuth bearer bridge → FastAPI role checks
                  ├─ order create / route → OrderService → RoutingAgent (candidate)
                  │    → configured rates + capacity → order, shipment, audit → dashboard reads
                  ├─ signed shipment webhook → ShipmentService → stored status
                  ├─ manual monitoring → FulfillmentOrchestrator → DB state and cycle records
                  └─ Chat → authorized SQL reads / server confirmation → supported operation

Celery Beat → Redis monitoring queue → Celery worker → FulfillmentOrchestrator
            → Monitor → Reroute evaluation / Prediction → Cost analysis → persisted cycle
            → dashboard status API
```

Orders route synchronously. The broker drives monitoring; order submission does not enqueue a durable per-order workflow. PostgreSQL stores the business state and events. Qdrant has startup/health and tool helpers. Vector retrieval is outside the verified order/monitor path, and the production legacy embedding key is absent. Gemini Free Tier is configured in production and was verified in the previous release. This audit did not spend additional inference quota. The candidate does not change the original UI, HTTPS routing, guest session or Chat code.

## Seven-agent evidence

These checks exercised real agent code with a disposable SQLite file and configured sandbox rate rows. The test calls the orchestrator directly and opens new database transactions to inspect committed results. It does not use a broker, delivery provider, or physical warehouse.

| Agent | Trigger and contract | Outcome and boundary |
|---|---|---|
| RoutingAgent | New eligible order or explicit route request. Uses postal codes, weight, center capacity, configured rates and request limits. | **PASS, local DB.** API service now delegates to the agent. It selects a center with an eligible lane, sorts by full weight-adjusted rate, uses configured transit days, and saves one shipment plus a route event. No eligible lane leaves the order pending. Tracking is generated internally. Courier acceptance is unverified. |
| MonitorAgent | Scheduled or manual scan of active shipment records. | **PASS, local DB.** Fresh shipment stayed on schedule. An overdue record and a carrier-reported delay with future ETA each produced a persisted delay record. Monitoring reads local shipment state. Direct carrier polling and a populated scheduled worker cycle remain unverified. |
| PredictionAgent | A delay reaches the orchestrator. | **PASS, local DB.** Stored `failure_prediction` event. Scores are heuristics derived from delay, lateness, status and observed carrier data. Calibration and predictive accuracy are unverified. |
| ReroutingAgent | Monitor detects a delay and evaluates configured alternatives. | **PASS for evaluation.** No eligible alternative produced zero reroutes. An eligible alternative produced a persisted recommendation, kept the original carrier and sent no notification. The default requires review. The existing explicit operator reroute endpoint is separate from the recommendation. A recommendation-to-approval workflow and real dispatch remain unverified. |
| CommunicationAgent | Existing delay-alert method or opt-in automatic rerouting path. | **PASS for unconfigured provider handling.** The real method stored a `skipped` attempt and returned zero sends. The candidate distinguishes failed and accepted attempts; acceptance means provider handoff. External delivery, preferences, retries and deduplication remain unverified. |
| CostOptimizer | At the end of a monitor cycle. | **PASS for aggregation.** Returned actual stored cost statistics in the cycle output. Service-constrained quote comparison and durable cost recommendation evidence remain incomplete. |
| FulfillmentOrchestrator | Manual API or Celery scheduled task. | **PASS for local monitor coordination.** Checked committed shipment records, ran applicable agents and appended a cycle summary. Durable per-order orchestration and worker restart recovery are unverified. |

The candidate defaults `ALLOW_AUTOMATIC_REROUTING` to false. The existing automatic execution branch can be enabled only with explicit backend configuration. Its carrier mutation and notification paths still need idempotency, approval-policy and recovery validation before use.

## Workflow evidence and remaining gates

| Scenario | Status |
|---|---|
| A. Normal fulfillment | **PASS for local routing and monitoring.** A 5 kg order selected a configured lane costing 20, wrote one shipment and a routing audit record, and completed monitoring with zero delays. Carrier booking and dashboard write acceptance are unverified. |
| B. Delayed shipment | **PASS for local webhook service, detection, prediction and recommendation.** The prior monitor ignored delayed carrier status when the ETA was still in the future. The regression covers this case and an overdue shipment with no alternative. Delivery is unverified. |
| C. Unavailable route | **PASS for local DB.** No compatible rate, exceeded cost cap or exceeded transit cap leaves the order pending and adds no shipment. |
| D. Insufficient inventory | **NOT IMPLEMENTED in the verified order path.** Center order capacity and shipping rates do not represent stock reservations. |
| E. Duplicate operation | **PASS for sequential repeat routing of the same order.** One shipment and one capacity increment remained. Order-create replay, event replay and database concurrency require separate verification. |
| F. External dependency failure | **PARTIAL.** Missing communication provider recorded as skipped. Provider failure injection, timed retries and delivery outcomes remain unverified. |
| G. Concurrent orders | **NOT VERIFIED.** Candidate uses PostgreSQL row locks for order and center. SQLite cannot validate their semantics. |
| H. Interrupted worker | **NOT VERIFIED.** Celery config has late acknowledgement and retry policies. Redelivery and exactly-once business effects are unproven. |

Release blockers include durable replay and worker recovery, safe carrier execution and approval, notification idempotency, and a writable staging environment separated from production. Shipment webhooks can overwrite status without an event identity or transition guard. Protected warehouse records use shared application queries, so an operator account in production is unsuitable for instructor isolation. The inspected machine had no usable Docker CLI or Linux runtime. No throughput or recovery target was measured. Guest access and owner authentication remain separate, and the candidate deliberately makes no new agent availability claims in the dashboard.

## Repeatable instructor evidence

The available exercise is a local, disposable database regression. It needs the development checkout and its Python environment and does not require production access or provider credentials.

```powershell
Set-Location order-fulfillment-coordinator/apps/api
.venv/Scripts/python.exe -m pytest tests/test_operational_routing.py -v
```

The two labeled cases run a normal order and repeat-routing check, then submit a synthetic carrier event through the shipment service. Inspect the assertions for the persisted route, one shipment, prediction, alternate-route recommendation, skipped communication and cost limits. The fixture creates and manages its own data. The original public landing and Launch Dashboard remain available for read-only browsing. A browser-based writable evaluation needs a separate API, database, Redis namespace, worker, synthetic carrier adapter and staging-only operator, followed by the same order and event sequence with task IDs and database results recorded.

The final local backend regression ran 1,226 cases with 1,226 passes, zero failures and zero skips. Ruff and mypy passed. The frontend had 74 passing tests, a clean lint run, a successful production build, and 23 passing built authentication checks. The backend total includes unit, API, security and integration tests. Only two new database-backed operational cases were executed, both passed. The 500-scenario operational target remains open. Docker builds, migration verification on PostgreSQL, staged worker failure injection and the remaining acceptance scenarios are release gates.
