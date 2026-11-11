# Local seven-agent visual acceptance — 11 November 2026

Production is unchanged. This local verification continues application commit e4739e0 on codex/operational-readiness.

## Local failures and fixes

- Development API rewrites ignored BACKEND_URL and forwarded to localhost:8000, causing HTTP 500/ECONNREFUSED while FastAPI was on 8385. next.config.ts now respects BACKEND_URL in both environments; production still refuses an unset backend.
- Login succeeded (session HTTP 200 with a valid access token), but Turbopack repeatedly performed full Fast Refresh reloads before hydration completed. The same application runs successfully using the supported Webpack dev mode. `npm run dev:webpack -- --hostname 127.0.0.1 -p 3385` is the reproducible local workaround; production build behavior is unchanged. This establishes the runtime-specific cause, not an upstream Turbopack patch.
- The isolated worker originally listened only on monitoring. The local worker now also consumes readiness and imports fulfillment.tasks.health; actual health tasks return pong.

## Actual workflow and evidence

The local PostgreSQL database watch_20261110185156 on 127.0.0.1:55471 is separate from production. Redis-compatible Memurai listens on 127.0.0.1:56385, database 7. Celery uses its actual solo worker on Windows. The FastAPI backend is 8385; Next.js is 3385. No production credentials are used.

The driver receives 5 units, creates an order for 2, verifies reservation, routes with stored carrier rates, dispatches, sends signed delay tracking through HTTP, executes a real Celery monitor cycle and notification outbox, sends signed delivery tracking, and verifies delivered status plus stock 3 on hand/0 reserved.

All seven agents have persisted outcomes: route_selected, delay_detected, failure_prediction, reroute_evaluated/recommended, provider_accepted, cost_analysis, cycle_complete. Notification delivery uses the actual SendGrid SDK directed exclusively at a loopback HTTP sink, not a live provider. Rerouting is evaluated/recommended; no fabricated carrier handoff occurs.

Evidence directory: `.tools/watch-20261110185156/` (local, ignored by Git).
- linked-workflow.json: latest order, shipment, task IDs, complete event results and timestamps, inventory reconciliation.
- watched-workflow.json: the run observed with four live dashboard stages.
- live-transitions.json and live-stage-*.png: actual API event changes shown in the original UI.
- browser-regression.json: authenticated API responses and browser checks.
- seven-agents-after.png, dashboard.png, orders.png: captured original interface.
- linked-worker.log and ready-worker-final.out/log: actual worker logs.

The browser checks compare all seven event IDs and timestamps with PostgreSQL, click Refresh and verify its HTTP 200 request, expand Last execution, reload, and navigate through the original dashboard and back. IDLE means recent completed evidence; the UI explicitly says current workload is not measured. This is not a RUNNING/heartbeat implementation and must not be presented as one. Failed/missing/stale evidence retains existing conservative behavior.

## Repeat on this workstation

1. Open http://127.0.0.1:3385/dashboard/agents. Sign in interactively using the local disposable operator details in `.tools/watch-20261110185156/operator-login.txt`; never commit that file or paste its contents into chat.
2. From repository root run `powershell -NoProfile -File .tools/watch-20261110185156/run-workflow.ps1`.
3. Click Refresh agent status during the run and expand Last execution. Routing updates first, then the monitoring/prediction/rerouting/cost/orchestration cycle, then communication. The command creates a new disposable order; existing events remain append-only. The sandbox worker uses its own visual-acceptance queue so the general worker cannot steal notification tasks.
4. Open Orders or Inventory to inspect persisted order and stock changes. Signed carrier events are supplied by the local driver because they represent an external webhook, not a dashboard action.
5. The current services remain running. If restarting the frontend, set BACKEND_URL=http://127.0.0.1:8385 and NEXTAUTH_URL=http://127.0.0.1:3385, supply a local NEXTAUTH_SECRET, and use dev:webpack. Rotating that local secret requires another sign-in.

Validation: previous full frontend run 76 passed; affected routing/status regression 12 passed; TypeScript noEmit and targeted ESLint passed; backend runtime/security 13 passed. Existing 500-case and Docker evidence is preserved and was not rerun for this local routing change.

Limitations: Memurai is Redis-compatible, not a newly verified Linux Redis run. Qdrant is not running locally; health correctly remains degraded despite PostgreSQL/Celery passing. Backend chat connectivity is available; no local Gemini model key or paid inference was used. Live carrier and external notification delivery remain provider activation dependencies. No OCI capacity, production deployment, or production business operations were attempted.
