# Windows teacher demonstration

From `C:\Users\DC\wherehouse-os-`, double-click `start_teacher_demo.cmd`, or run:

```powershell
.\start_teacher_demo.cmd
```

Keep the terminal open. Open http://localhost:3000 and sign in with
`teacher@example.com` and the generated password printed by the launcher.
The backend documentation is http://127.0.0.1:8000/docs. Press Ctrl+C in the
launcher to stop its backend/frontend process trees. Ports 3000 and 8000 must
be free; the launcher refuses to kill unrelated applications.

This uses the already installed Python environment, Node 24.22.2, and locked
frontend dependencies in this checkout. It does not install packages, require
Docker, alter existing environment files, or connect to production data.

The launcher migrates a dedicated `.tools/teacher-demo/demo.db`, creates an
administrator account with a random password, and idempotently adds one clearly
labelled sample order plus the existing sample fulfillment centers/carrier rates.
These are real records in the demonstration database, not mock API responses.
The account password is retained in the ignored local credentials file so it
continues to work on restart; do not publish the `.tools` folder or its logs.

After startup it verifies real backend login/profile, unauthenticated access
denial, NextAuth login against that backend, order and KPI reads through the
frontend proxy, and an authenticated dashboard HTML response. Results are written
to `.tools/teacher-demo/verification.json`. Browser rendering and every dashboard
interaction are not established by these HTTP checks. Inspect the Orders page
for `TEACHER-DEMO-001` and the dashboard for backend-derived metrics.

To repeat the smoke checks and stop automatically:

```powershell
.\start_teacher_demo.cmd --verify
```

Backend authentication is enforced (`DEBUG=false`) with generated local JWT,
webhook, and valid Fernet secrets. Next.js runs in development mode on loopback.
This is a local demonstration, not an OCI deployment or a hardened public server.

SQLite replaces PostgreSQL locally. Redis, Celery workers, Qdrant/vector search,
external LLM/embeddings, Odoo, email/SMS and live shipping-provider integrations
are unavailable in this configuration. Built-in keyword intent handling can
still run; it must not be described as an LLM response. Scheduled/background
shipping operations are not demonstrated. `/health` honestly reports degraded
status with PostgreSQL/Celery/Qdrant false. No fake AI credentials, fabricated
provider responses, disabled authentication, or artificial green health are used.

Verified 2026-11-02: real NextAuth/backend login, protected access, persisted
sample order through frontend proxy, KPI response, dashboard HTTP response,
and startup/shutdown. Full backend regression after optional-AI deployment
configuration change: 1,183 passed; Ruff and mypy passed.
