# AGENTS.md — Order Fulfillment Coordinator

> Deployed as a multi-service Docker stack on **Oracle Cloud (OCI)**.
> FastAPI backend + Celery workers + Next.js frontend, wrapped in Caddy with auto SSL.

---

## Where things live

```
order-fulfillment-coordinator/
├── apps/api/                    # FastAPI backend (Python 3.12)
│   ├── src/fulfillment/
│   │   ├── agents/              # 7 AI agents (routing, monitor, rerouting, etc.)
│   │   ├── tools/               # Agent tool functions
│   │   ├── guardrails/          # Policy guardrails (SLA, cost, diversity, etc.)
│   │   ├── api/v1/              # REST endpoints (orders, shipments, integrations)
│   │   ├── services/            # Business logic (order_service, odoo_client)
│   │   ├── models/              # SQLAlchemy models
│   │   ├── schemas/             # Pydantic schemas
│   │   └── main.py              # FastAPI app entrypoint
│   └── Dockerfile               # Multi-stage: builder → production
├── infra/
│   ├── caddy/Caddyfile          # Reverse proxy + SSL
│   └── scripts/
│       ├── deploy.sh            # OCI deploy script
│       ├── rollback.sh          # Rollback to previous version
│       └── backup.sh            # Daily DB backup (30-day retention)
├── docker-compose.prod.yml      # Production stack (7 services)
├── docker-compose.yml           # Dev stack
└── .env.example                 # All environment variables

agent-platform-ui-main/
└── agent-platform-ui-main/
    ├── src/                     # Next.js 16 app router
    │   └── app/dashboard/       # 11 pages (orders, agents, integrations, etc.)
    └── Dockerfile               # Multi-stage: deps → builder → runner
```

---

## Commands

```bash
# Local dev
cd apps/api && uv run fastapi dev src/fulfillment/main.py   # Backend :8000
cd agent-platform-ui-main && npx next dev -p 3000           # Frontend :3000

# Docker dev
docker compose up -d postgres redis                          # Infra only
docker compose up -d                                         # Full stack

# Production deploy (on OCI instance)
./infra/scripts/deploy.sh

# Database backup
./infra/scripts/backup.sh

# Rollback
./infra/scripts/rollback.sh api

# Testing
cd apps/api && uv run pytest tests/ -v
cd agent-platform-ui-main && npx vitest run
```

---

## Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, uvicorn |
| Frontend | Next.js 16, React 19, Node 20 |
| Database | PostgreSQL 16 (primary), SQLite (dev fallback) |
| Cache/Queue | Redis 7 + Celery |
| Auth | JWT (python-jose) |
| AI | OpenAI Agents SDK / OpenRouter |
| Vectors | Qdrant |
| Integration | Odoo JSON-RPC API |
| Container | Docker, multi-stage builds |
| Proxy | Caddy 2 (auto SSL via LetsEncrypt) |
| Host | **Oracle Cloud (OCI)** VM.Standard.E2.1.Micro (free tier) or better |
| CI/CD | GitHub Actions → OCI instance via SSH |

## Critical Rules (from project architecture)

1. **Rate limit every public endpoint** — 429 with Retry-After
2. **Fail closed** — database down = tool refuses, does not improvise
3. **Schema-qualified SQL** — `public.orders`, `public.shipments` (PostgreSQL)
4. **The app must boot with only OPENAI_API_KEY set** — SQLite fallback when DATABASE_URL unset
5. **Append-only logging for agent events** — never mutate agent_event rows
6. **Rollback is a traffic change, not a redeploy** — keep the previous image tagged
7. **Each deploy flips exactly one backend** — health check ladder

## Deployment Topology (OCI)

| Surface | Component | Config |
|---|---|---|
| Public entry | Caddy (ports 80/443) | Auto SSL, reverse proxy |
| Control plane | FastAPI on `api:8000` | Internal, not exposed directly |
| UI | Next.js on `frontend:3000` | Internal, proxied via Caddy |
| Durable state | PostgreSQL `postgres:5432` | Persistent volume |
| Task queue | Redis `redis:6379` | Volatile |
| Background jobs | Celery worker + beat | Same image as API |
| Integration | Odoo (external) | Configured via env vars |

## Health Check Ladder

```
Step 1: API boots → {"status":"ok","backends":{"postgres":false}}
Step 2: PostgreSQL wired → postgres:true
Step 3: Qdrant wired → qdrant:true
Step 4: Odoo connection → integration configured
Step 5: Celery worker connected → celery:true
```

## Verification before merge

- [ ] `ruff check .` clean
- [ ] `mypy src/` clean (or known exemptions)
- [ ] `pytest tests/` green
- [ ] Docker build passes: `docker compose build`
- [ ] Health endpoint responds: `curl localhost:8000/health`
- [ ] Rate limiting active on public endpoints
