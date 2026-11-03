# Live release — November 3, 2026 (Asia/Karachi)

**The public teacher demo and corrected private login are deployed and verified.**

- [Public teacher demo](https://140-245-218-97.sslip.io/demo)
- [Direct OCI HTTPS IP](https://140.245.218.97/) — trusted TLS, then canonical redirect.
- [Protected sign-in](https://140-245-218-97.sslip.io/api/auth/signin?callbackUrl=%2Fdashboard)

Production release **b7266035270efbca545bf028aa64814c9e42e6ce** was already deployed successfully through [run #82](https://github.com/MoizAi8/wherehouse-os-/actions/runs/41539083186), after [CI #81](https://github.com/MoizAi8/wherehouse-os-/actions/runs/41538210260) and both Docker image builds passed. It supersedes run #80. The user's one further deployment authorization was consumed by run #82. Final acceptance triggered no deployment, restart or application changes.

## Final live acceptance

All **33 HTTP checks**, **13 Edge browser checks** and **nine CSRF checks** passed. Three additional independent fresh-browser visits to the private dashboard successfully signed in with matching form/cookie CSRF tokens. Desktop and mobile public screenshots were inspected.

Verified: no-login demo entry; all seven sample data views and chat; filtering; backend readiness; real Gemini arithmetic, Roman Urdu and supplied conversational memory; sample inventory facts; public destructive-operation refusal; private dashboard, Orders and Chat browser access; authenticated Chat, Agents, Orders and Dashboard API reads; logout; rejection of anonymous/malformed bearer requests and missing/mismatched CSRF tokens; trusted hostname and direct-IP TLS; preservation of path/query during the canonical IP redirect.

The prior cookie race affected first-visit **private login**, while the public demo remained accessible. Late anonymous NextAuth session/provider responses could overwrite the form cookie. The deployed correction suppresses only those form-cookie initializations; session cookies and all POST CSRF validation remain active. See CSRF-CORRECTION.md.

All eight services are running. PostgreSQL, Celery and Qdrant readiness is green. Runtime remains TEACHER_DEMO_MODE=true, DEBUG=false, Gemini Free-tier provider, with no legacy OpenAI embedding key. Migration d5e8f1a2b3c4 is unchanged by this correction. The prior release remains available. Exact immutable images and release paths are recorded in live-host-state.json. No production customer records were created, modified or deleted by acceptance checks; warehouse write paths were tested with isolated fixtures in the earlier suite.

CI passed 1,197 backend tests, 66 frontend tests, 19 built authentication checks, lint/types and production image builds. Earlier controlled evaluation remains **498/500 passed**, with two local-Qwen quality failures and no blocked scenarios. That evaluation is distinct from bounded real Gemini CI/live calls. Free-tier quotas may limit AI responses; no paid inference, billing or infrastructure purchases were performed.

The public demo is intentionally isolated and read-only: sample workflows are simulations, and private production operations remain protected. It does not expire automatically. To restore the normal landing/login flow, set the existing repository variable and obtain authorization for a normal redeployment:

```powershell
gh variable set TEACHER_DEMO_MODE --repo MoizAi8/wherehouse-os- --body false
```

Changing the variable alone does not restart production. IP TLS uses Caddy's configured short-lived ACME renewal policy; future certificate renewal was not tested by advancing time. Validated pre-release and pre-correction database backups remain on the server. No dump, credentials, JWTs or private response bodies were committed.

Evidence: live-smoke.json, live-browser.json, live-csrf-regression.json, live-first-visit-{1,2,3}.json, live-host-state.json and csrf-correction-backup.json. Historical run-80 state and initial race diagnostics remain preserved separately.
