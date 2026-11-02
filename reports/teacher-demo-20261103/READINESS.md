# Teacher demo and AI upgrade — verification in progress

Production remains on `00ecaa9` / successful OCI run 77. This branch has not been
pushed or deployed. Production records and settings have not been migrated.
Direct-IP trusted HTTPS certificate issuance remains unverified and unapplied.

The proposed demo uses a separately allocated, read-only sample SQLite database.
`TEACHER_DEMO_MODE=true/false` is the sole availability switch; there is no expiry.
Normal JWT authentication, stored roles and per-user history remain enforced.
Public inference has per-client rate limits and a shared daily request quota;
the quota never disables database views or automatically turns demo mode off.

Verified locally so far:

- 1,197 backend regression tests passed; Ruff clean; mypy clean for 83 files.
- 66 frontend tests passed; ESLint clean; production build passed.
- 15 checks against built NextAuth routes passed.
- 30 real Edge/Playwright scenarios passed after fixing a stale-view rendering
  race and correcting invalid test expectations. All attempts remain in JSONL.
- Actual installed production Caddy 2.11.4 accepted the proposed configuration
  in read-only adaptation. No reload, certificate request or deployment occurred.
- Genuine localhost Qwen conversations and read-tool selection work at $0.
  The 220-case conversation/memory evaluation is still running. Model errors
  remain failures; no deterministic fallback is counted as real inference.

Confirmed defects fixed include a circuit breaker returning an unawaited SDK
coroutine, database history commits racing immediate follow-up requests,
unsupported inventory answers, missing plural intent matches, fabricated agent
activity, and SQLite datetime subtraction producing nonsensical duration KPIs.
Chat mutations now require user/session/message-bound, expiring one-use approval
tokens and recheck authorization. The additive migration creates only the new
approval table; it does not change customer tables.

The owner confirmed the Gemini key's project is Free tier with no linked billing
account. GitHub secret metadata confirms `GEMINI_API_KEY` exists; its value was
not retrieved or exposed. The credential is available only inside GitHub Actions.
Prepared Gemini verification is synthetic, bounded, and cannot deploy. Live
Gemini compatibility and credential validity are not yet verified. Do not treat
local Qwen results as Gemini results.

Release gates still outstanding: finish the 500-case evidence, run real Gemini
verification, build Docker images in CI (Docker is unavailable on this Windows
host), obtain explicit production authorization, take a fresh database backup,
deploy once through the existing pipeline, verify public demo, protected login
and trusted direct-IP TLS, and preserve the working canonical hostname.

Official references reviewed November 3, 2026:

- [Gemini pricing](https://aistudio.google.com/docs/pricing#gemini-3.5-flash-lite)
- [Gemini SDK compatibility](https://aistudio.google.com/docs/openai)
- [Gemini billing tiers](https://aistudio.google.com/docs/billing)
- [Let's Encrypt IP certificates](https://letsencrypt.org/2026/01/15/6day-and-ip-general-availability)
- [Caddy TLS configuration](https://caddyserver.com/docs/caddyfile/directives/tls)

Free-tier prompts may be used by Google to improve products. The verification
uses synthetic data only. The public demo never sends private production records.
