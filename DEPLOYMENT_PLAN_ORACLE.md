# Deployment Plan — support_worker on Oracle Cloud (OCI)

> Source of truth: `AGENTS (1).md`. That file was written for **Azure Container Apps +
> Neon + Cloudflare R2 + E2B**. This plan maps every component to its **OCI equivalent**
> while keeping the one non-negotiable architectural invariant:
>
> **The harness is the control plane you own and keep running.**
> **The sandbox is the execution plane you create, use once, and throw away.**

---

## Architecture Overview (OCI)

```
                        ┌─────────────────────────┐
                        │   Domain + DNS (OCI DNS)│
                        └───────────┬─────────────┘
                                    │ 443
                       ┌────────────┴────────────┐
                       │  Caddy (port 80/443)    │  ← public entry, auto SSL
                       └────────────┬────────────┘
                                    │
              ┌─────────────────────┼──────────────────────┐
              │                     │                      │
   ┌──────────┴─────────┐  ┌────────┴─────────┐  ┌─────────┴──────────┐
   │ FastAPI harness    │  │  Inngest dev     │  │  Sandbox           │
   │ (control plane)    │  │  server (local)  │  │  (execution plane) │
   │ :8000              │  │  :8288           │  │  throwaway, per-run│
   └──────────┬─────────┘  └──────────────────┘  └────────────────────┘
              │
   ┌──────────┴─────────┐
   │ PostgreSQL 16      │  ← OCI Database for PostgreSQL (or container)
   │ pgvector + HNSW    │     sessions, runs, traces, artifacts, audit_log
   └────────────────────┘
```

All services run on **one OCI Compute instance** behind Caddy. The envelope is either
**Inngest Cloud** (recommended) or the Inngest dev server colocated on the box.

---

## Component Mapping — Azure → OCI

| `AGENTS (1).md` surface | Azure-era choice | **OCI equivalent** |
|---|---|---|
| Harness host | Azure Container Apps | **OCI Compute** (Ampere A1 ARM free tier, 4 OCPU / 24 GB) + Docker Compose, or **OCI Container Instances** |
| Envelope | Inngest Cloud | **Inngest Cloud** (external, no change) *or* Inngest dev server on the VM |
| Durable state | Neon Postgres | **OCI Database for PostgreSQL** (managed, pgvector) *or* `postgres:16-pgvector` container on the VM |
| Files / artifacts | Cloudflare R2 (`boto3`) | **OCI Object Storage** (S3-compatible, `boto3`) |
| Execution plane | E2B sandbox | **Docker sandbox container** on the same host (provision per run, destroy on finish) — see Sandbox section |
| Secrets | ACA named secrets (`secretref:`) | **OCI Vault** secrets *or* `.env` file on host (0600) |
| Observability | App Insights + Phoenix + OTel | **OCI Logging + OCI Monitoring + self-hosted Phoenix** (same OTel/pyroscope story, tied by `run_id`) |
| Reverse proxy / TLS | ACA managed ingress | **Caddy** on the VM (auto Let's Encrypt) |
| CI/CD | `az acr build` + `az containerapp update` | **GitHub Actions → SSH/SCP to OCI** or OCI DevOps, pushing to **OCI Container Registry (OCIR)** |
| Backup | R2 lifecycle (30-day) | **OCI Object Storage lifecycle policy** (30-day, then archive/delete) |
| Rollback | ACA traffic split (revision) | **Tag flip in `docker-compose.prod.yml`** — rollback is a traffic change, not a redeploy |

---

## Phase 0 — Decisions (answer before provisioning)

| # | Decision | Pick |
|---|---|---|
| D1 | Inngest Cloud vs self-hosted | **Inngest Cloud** (durable execution is the envelope we ship; do not hand-roll) |
| D2 | Postgres managed vs container | **OCI Database for PostgreSQL** if budget allows; **`pgvector/pgvector:pg16` container** for free-tier demo |
| D3 | Sandbox | **Docker sandbox container** on the same host (free path, mirrors E2B semantics: create → use once → destroy) |
| D4 | Registry | **OCI Container Registry (OCIR)** or plain **Docker Hub** (simplest for 1 VM) |
| D5 | Compute shape | **VM.Standard.A1.Flex (Ampere, 4 OCPU/24GB)** — free tier, enough for harness + postgres + sandbox |

Model strings and API keys are placeholders. The swap mechanism is unchanged: base-URL
swap for OpenAI-compatible providers, `LitellmModel` for everything else.

---

## Phase 1 — OCI Tenancy Setup

1. **Create tenancy/compartment** (e.g. `support-worker`).
2. **VCN** with a public subnet + Internet Gateway. Record the **security list** rules:

   | Direction | Source/Dest | Port | Purpose |
   |---|---|---|---|
   | Ingress | 0.0.0.0/0 | 80, 443 | Caddy public entry |
   | Ingress | your-IP | 22 | SSH (restrict, don't leave open) |
   | Ingress | your-IP | 3000* | *optional* dev dashboard, keep locked |
   | Egress | 0.0.0.0/0 | all | outbound |

3. **Launch instance** `VM.Standard.A1.Flex`, Ubuntu 24.04, attach the free-tier block
   volume. Keep the SSH keypair in a password manager + GitHub secret.
4. **SSH in and baseline:**
   ```bash
   sudo apt update && sudo apt upgrade -y
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker ubuntu
   sudo docker compose version   # verify plugin
   ```

---

## Phase 2 — Durable State (PostgreSQL)

### Option A: OCI Database for PostgreSQL (managed, recommended for production)

- Provision via Console/CLI: shape, version 16, storage, auto-backup (7–30 days).
- Enable **pgvector** (included). Create the `runs`, `sessions`, `traces`,
  `artifacts`, `audit_log`, and `routing_decisions` (multi-agent day-one) tables.
- Two endpoints, per AGENTS rule #4:
  - `DIRECT_BRANCH_URL` → migrations
  - pooled/primary URL → the app
- Schema-qualify everything: `public.runs`, `public.sessions`. (OCI poolers can drop
  `search_path`, same gotcha as Neon.)

### Option B: Container on the VM (free-tier demo)

```yaml
# compose fragment — postgres:
  postgres:
    image: pgvector/pgvector:pg16
    restart: unless-stopped
    environment:
      POSTGRES_DB: support_worker
      POSTGRES_USER: support
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U support"]
      interval: 5s
      timeout: 5s
      retries: 10
```

Migrate with `psql "$DIRECT_BRANCH_URL" -f migrations/schema.sql` — **never** through the
app's pooled connection.

---

## Phase 3 — Artifacts (OCI Object Storage ≈ R2)

R2 was S3-compatible via `boto3`, `region_name="auto"`. OCI Object Storage is also
S3-compatible — point `boto3` at the compat endpoint:

```python
import boto3

s3 = boto3.client(
    "s3",
    endpoint_url=f"https://{NAMESPACE}.compat.objectstorage.{REGION}.oraclecloud.com",
    region_name=REGION,                      # e.g. "us-ashburn-1"
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
)
```

| Bucket / prefix | Purpose | Lifecycle |
|---|---|---|
| `inputs/` | never-grow scratch | none |
| `outputs/` | generated artifacts | **30-day** lifecycle, then archive/delete |
| `knowledge/` | KB / golden files | none |

**Critical rule #2:** only **presigned URLs and short-lived tokens** cross into the sandbox
Manifest. DB strings and API keys never leave the harness. In OCI use the S3-compat
`generate_presigned_url` for the same effect.

Lifecycle policy (OCI Console → bucket → lifecycle): rule on `outputs/` prefix,
`tier-archive` at 30 days.

---

## Phase 4 — Sandbox (execution plane)

Free-tier substitute for E2B, same semantics: **provision → use once → destroy**.

- A Docker image `sandbox-base` built from `python:3.12-slim` with the project's agent
  deps but **no credentials baked in**.
- On each run the harness does:
  1. Build `Manifest` from **presigned URLs only** (inputs + knowledge).
  2. `docker run --rm --network none --memory 512m` with the manifest mounted read-only.
  3. Collect output, write to Object Storage under `outputs/`, `docker rm -f` the container.
- `--network none` is your isolation boundary — the sandbox cannot phone home with anything.
- Sandbox API shape (AGENTS gotchas to respect): `Manifest(entries={...})` is entries-only;
  capabilities additive (`default() + [Memory()]`); attach via `RunConfig(sandbox=...)`,
  never `Runner.run(..., sandbox=...)`.

> If you later want a managed sandbox, keep the E2B code path — swap only the driver. The
> Manifest contract does not change.

---

## Phase 5 — Harness + Envelope (FastAPI + Inngest)

### Harness container

`Dockerfile` (multi-stage, `uv`):

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.12-bookworm AS builder
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"
COPY --from=builder /app/.venv ./.venv
COPY src ./src
COPY migrations ./migrations
EXPOSE 8000
CMD ["uvicorn", "support_worker.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
```

### docker-compose.prod.yml

```yaml
services:
  caddy:
    image: caddy:2
    ports: ["80:80", "443:443"]
    volumes:
      - ./infra/caddy/Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    restart: unless-stopped
    depends_on: [api]

  api:
    image: ${REGISTRY}/support-worker-api:${TAG:-latest}
    restart: unless-stopped
    env_file: .env
    expose: ["8000"]
    depends_on:
      postgres:
        condition: service_healthy

  postgres:
    image: pgvector/pgvector:pg16
    ...
```

### Envelope wiring (one `step.run` per agent loop — rule #8)

- **Inngest Cloud:** set `INNGEST_SIGNING_KEY`, event `support/run`. Each function wraps
  `Runner.run()` in a single `step.run`. Idempotency keys from a **stable business key**
  (run/order id), never a timestamp (rule #9).
- **Self-hosted fallback:** run `inngest dev` as a sidecar on the VM (port 8288, locked to
  your IP) and point the SDK's event API at it.

---

## Phase 6 — Public Entry (Caddy)

`infra/caddy/Caddyfile`:

```
support.example.com {
    reverse_proxy api:8000
    encode gzip
}
```

Auto TLS via Let's Encrypt once DNS A record points at the instance's public IP.
`--proxy-headers` on uvicorn so Caddy's `X-Forwarded-For` is honoured by the rate limiter.

---

## Phase 7 — Secrets

Prefer **OCI Vault**; for a 1-VM free-tier setup `.env` (0600) is acceptable.

```bash
OPENAI_API_KEY=sk-...          # the only var required to boot (rule #11)
DATABASE_URL=postgresql+asyncpg://...   # pooled
DIRECT_BRANCH_URL=postgresql://...      # migrations only
R2_* / OCI_NAMESPACE=... / OCI_ACCESS_KEY=... / OCI_SECRET_KEY=...
INNGEST_SIGNING_KEY=...
JWT_SECRET=$(openssl rand -hex 32)
```

**Rotation (AGENTS):** add new credential beside old → redeploy → verify → revoke old.
Never bake secrets into images.

---

## Phase 8 — CI/CD (GitHub Actions → OCI)

`.github/workflows/deploy.yml` — same gates as the AGENTS file, target OCI:

1. **test** — `make check` (ruff + pyright), `make test` (pytest), DeepEval gate on
   `evals/golden.jsonl`. No test may be edited to turn green (rule #14).
2. **build** — `docker build` api + sandbox-base, push to `ghcr.io/you/support-worker-api:${GITHUB_SHA}`.
3. **deploy** — SSH to the OCI host:
   ```bash
   ssh -o StrictHostKeyChecking=accept-new $OCI_HOST <<'EOF'
     cd /opt/support-worker
     docker compose -f docker-compose.prod.yml pull
     TAG=${{ github.sha }} docker compose -f docker-compose.prod.yml up -d --no-deps api
   EOF
   ```
4. **health** — `curl -f https://support.example.com/health` before marking green.

Store `OCI_HOST`, `OCI_SSH_KEY`, registry creds in **GitHub secrets**.

---

## Phase 9 — Observability

Four surfaces, tied by shared `run_id` (AGENTS):

| Surface | OCI equivalent | Purpose |
|---|---|---|
| Logs | **OCI Logging** (or `docker compose logs` + journald) | harness + envelope errors |
| Metrics | **OCI Monitoring** | p95 latency, error rate, tokens/run |
| Traces | OTel → self-hosted **Phoenix** (sidecar) | per-run trace tree, model calls |
| Evals | DeepEval CI gate + nightly Ragas | quality trend |

`GET /health` is the build ladder — it must reflect reality:

```json
{"status":"ok","model":"<model>","backends":{"postgres":false,"sandbox":false,"r2":false}}
```

---

## Phase 10 — Rollout Ladder (one flag per step)

```
Step 1: api boots, SQLite fallback, OPENAI_API_KEY only → /health ok, postgres:false
Step 2: wire PostgreSQL (migrate via DIRECT URL)        → postgres:true
Step 3: wire Object Storage (presigned URLs)            → r2:true
Step 4: wire sandbox (docker run/rm smoke test)         → sandbox:true
Step 5: wire Inngest (event fires, function completes)   → envelope verified
Step 6: rate limiting on public endpoints               → 429 + Retry-After on abuse
```

Never flip two flags at once.

---

## Rollback = traffic change, not redeploy

Keep the previous image tagged:

```bash
TAG=previous-sha docker compose -f docker-compose.prod.yml up -d --no-deps api
```

No rebuild, no migration. If a migration was applied, roll that back first via the direct
endpoint.

---

## Backup (30-day retention)

| Asset | How |
|---|---|
| PostgreSQL | `pg_dump` daily at 03:00 → OCI Object Storage, lifecycle 30 days |
| `.env` / secrets | GitHub Secrets / OCI Vault (never in backup bucket) |
| Artifacts | Object Storage lifecycle (30 days on `outputs/` only) |

Cron on the VM:

```bash
0 3 * * * docker exec postgres pg_dump -U support support_worker | \
  aws --endpoint-url https://...s3.<region>.oraclecloud.com s3 cp - s3://backups/db_$(date +%F).sql
```

---

## Security checklist (AGENTS critical rules)

- [ ] **Never run agent-generated code in the harness** — sandbox only (rule #1)
- [ ] Manifest carries **presigned URLs only** (rule #2)
- [ ] **Schema-qualified SQL** everywhere (rule #3)
- [ ] Migrations via `DIRECT_BRANCH_URL`, app uses pooled (rule #4)
- [ ] Explicit `max_turns` on every `Runner.run()` (rule #5)
- [ ] Guardrails on irreversible actions: `run_in_parallel=False` (rule #6)
- [ ] Identity from verified claims, never a tool arg (rule #7)
- [ ] One `step.run` per agent loop (rule #8)
- [ ] Idempotency keys from stable business keys (rule #9)
- [ ] **Rate limit every public endpoint** — 429 + `Retry-After` (rule #10)
- [ ] Boots with only `OPENAI_API_KEY` set (rule #11)
- [ ] **Fail closed** — DB down = tool refuses (rule #16)

---

## Cost

| Item | Free tier | Paid |
|---|---|---|
| Compute (Ampere A1) | 4 OCPU / 24 GB free | ~$0/VM or ~$30/mo beyond quota |
| Block volume | 200 GB free | storage rate |
| Object Storage | 10 GB free, 10K GET/mo | $0.025/GB/mo + requests |
| Managed Postgres | ❌ | hourly + storage |
| Inngest Cloud | 1k events/mo free | per-event |
| **Total (all-free)** | **$0/mo** | — |

---

## Files to create

| File | Purpose |
|---|---|
| `infra/caddy/Caddyfile` | reverse proxy + auto SSL |
| `docker-compose.prod.yml` | full OCI stack |
| `Dockerfile` | harness image (multi-stage, `uv`) |
| `Dockerfile.sandbox` | throwaway sandbox image |
| `.github/workflows/deploy.yml` | test → build → push → SSH deploy |
| `infra/backup.sh` | pg_dump → Object Storage |
| `.env.example` | all vars incl. OCI S3-compat creds |
| `infra/deploy.sh` | one-command deploy + health check |
