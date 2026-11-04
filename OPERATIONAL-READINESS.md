# Warehouse OS operational readiness audit

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
