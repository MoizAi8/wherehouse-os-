# Live release — November 3, 2026 (Asia/Karachi)

**The public teacher demo is deployed and working.**

- [Public teacher demo](https://140-245-218-97.sslip.io/demo)
- [Direct OCI HTTPS IP](https://140.245.218.97/) — trusted TLS, then canonical redirect.
- [Explicit protected sign-in](https://140-245-218-97.sslip.io/api/auth/signin?callbackUrl=%2Fdashboard)

Release **78b98ea89e8de530690bbec0f0fb931668d9f382** deployed successfully through
[run #80](https://github.com/MoizAi8/wherehouse-os-/actions/runs/41534406364), after
[main CI #79](https://github.com/MoizAi8/wherehouse-os-/actions/runs/41533545040)
and both Docker builds passed. Exactly one authorized OCI deployment was used.
No second deployment or manual service restart was performed.

Live settings: TEACHER_DEMO_MODE=true, no demo expiration, DEBUG=false,
Gemini Free-tier chat configured, no legacy OpenAI/embedding key. All eight
containers run. API, worker, PostgreSQL and Redis are healthy; dependency
readiness confirms PostgreSQL, Celery and Qdrant. Migration d5e8f1a2b3c4 is
applied and the previous release is retained. `live-host-state.json` records
exact release paths and immutable image digests.

All **33 live HTTP checks passed** (`live-smoke.json`): anonymous root/demo,
all seven isolated sample views, real Gemini arithmetic/Roman Urdu/history,
sample inventory, refusal of public destructive requests, actual teacher login,
cookie forwarding, authenticated Chat/Agents/Orders/Dashboard APIs, anonymous
and malformed-token rejection, logout, dependency readiness and trusted TLS.
The IP certificate has IP SAN 140.245.218.97 and expires November 9, 2026 at
13:18:50 UTC. Caddy's shortlived ACME policy manages renewal; future renewal has
not yet occurred. The working hostname certificate remains valid.

Real Edge verified public navigation, sample filtering/chat, trusted IP TLS,
expired-cookie public access and the private sign-in form. Its longer sequence
then exposed a reproducible **first-visit private login CSRF-cookie race**.
A fresh direct browser sign-in succeeded. Initial browser failures remain in
`live-browser-initial.json` and `live-browser.json`; a complete browser pass is
not claimed. The tested local correction is in `CSRF-CORRECTION.md` and needs
renewed release authorization.

Controlled 500-case results remain **498 passed, two local-Qwen quality failures,
none blocked**. Deployed Gemini separately passed ten CI checks and three live
conversational checks. No paid inference, billing or infrastructure purchases
were performed. See `REPORT.md` for detailed evaluation and quota limitations.

To restore the normal landing/login flow, change one repository variable and
redeploy through the existing pipeline:

```powershell
gh variable set TEACHER_DEMO_MODE --repo MoizAi8/wherehouse-os- --body false
```

The variable applies on redeployment; it does not itself restart the app. There
is no automatic demo time limit. Public inference quotas do not expire the demo.
The private PostgreSQL backup has a validated archive manifest and SHA-256.
No dump, credentials, JWTs or private response bodies were committed. Smoke
tests performed no customer-record mutations.
