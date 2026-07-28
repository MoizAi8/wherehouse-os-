# Deployment Plan — Order Fulfillment Coordinator

## Architecture Overview

```
                    ┌──────────────────────┐
                    │   Cloudflare / DNS    │
                    └──────┬───────────────┘
                           │
              ┌────────────┴────────────┐
              │  Reverse Proxy (Caddy)  │
              │   → /api/*  :8000       │
              │   → /*      :3000       │
              └────────────┬────────────┘
                           │
              ┌────────────┴────────────┐
              │      Docker Host         │
              │  (VPS / Azure VM / ACA)  │
              │                          │
              │  ┌──────┐ ┌──────┐       │
              │  │ API  │ │Next.js│       │
              │  │:8000 │ │:3000  │       │
              │  └──┬───┘ └──────┘       │
              │     │                     │
              │  ┌──┴───┐ ┌──────┐        │
              │  │Post- │ │Redis │        │
              │  │greSQL│ │:6379 │        │
              │  │:5432 │ └──────┘        │
              │  └──────┘                 │
              │  ┌──────────────────────┐ │
              │  │ Celery Worker + Beat │ │
              │  └──────────────────────┘ │
              └───────────────────────────┘
```

## Project Components

| Component | Tech | Port | Docker | CI Needed |
|-----------|------|------|--------|-----------|
| **Backend API** | Python 3.12, FastAPI, uvicorn | 8000 | ✅ Dockerfile | ✅ Build + push |
| **Frontend** | Next.js 16, Node 20 | 3000 | ❌ No Dockerfile | ✅ Static export / container |
| **PostgreSQL** | Postgres 16 | 5432 | ✅ Official image | ❌ |
| **Redis** | Redis 7 | 6379 | ✅ Official image | ❌ |
| **Celery Worker** | Python Celery | — | ✅ Same Dockerfile | Same as API |
| **Celery Beat** | Python Celery | — | ✅ Same Dockerfile | Same as API |

---

## Phase 1 — Pre-Deployment Setup

### 1.1 CI/CD Pipeline (GitHub Actions)

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy
on:
  push:
    branches: [main]

jobs:
  test-api:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: fulfillment_test
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --frozen
        working-directory: apps/api
      - run: uv run pytest tests/
        working-directory: apps/api
      - run: uv run ruff check .
        working-directory: apps/api
      - run: uv run mypy src/
        working-directory: apps/api

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: npm ci
        working-directory: agent-platform-ui-main/agent-platform-ui-main
      - run: npm run lint
        working-directory: agent-platform-ui-main/agent-platform-ui-main

  build-api:
    needs: [test-api]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker build -t ${{ secrets.REGISTRY }}/fulfillment-api:latest ./apps/api
      - run: docker push ${{ secrets.REGISTRY }}/fulfillment-api:latest

  build-frontend:
    needs: [test-frontend]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: npm ci
        working-directory: agent-platform-ui-main/agent-platform-ui-main
      - run: npm run build
        working-directory: agent-platform-ui-main/agent-platform-ui-main
        env:
          NEXT_PUBLIC_API_URL: ${{ secrets.API_URL }}
      - uses: docker/setup-buildx-action@v3
      - run: docker build -t ${{ secrets.REGISTRY }}/fulfillment-ui:latest -f Dockerfile.frontend .
      - run: docker push ${{ secrets.REGISTRY }}/fulfillment-ui:latest

  deploy:
    needs: [build-api, build-frontend]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: |
          docker compose -f docker-compose.prod.yml pull
          docker compose -f docker-compose.prod.yml up -d --force-recreate
```

### 1.2 Frontend Dockerfile

Create `agent-platform-ui-main/agent-platform-ui-main/Dockerfile`:

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/next.config.ts ./
EXPOSE 3000
CMD ["npm", "start"]
```

### 1.3 Docker Hub / Registry Setup

| Registry | Variable |
|----------|----------|
| Docker Hub | `REGISTRY=docker.io/yourorg` |
| GitHub Container | `REGISTRY=ghcr.io/yourorg` |
| Azure ACR | `REGISTRY=youracr.azurecr.io` |

### 1.4 Environment Variables — Production

File `.env.production` (DO NOT commit — store in GitHub Secrets):

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/fulfillment
DATABASE_SYNC_URL=postgresql://user:pass@host:5432/fulfillment

# Redis
REDIS_URL=redis://host:6379/0

# Auth
JWT_SECRET=<generate-random-64-chars>
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=60

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=
OPENAI_MODEL=gpt-4o

# Shipping
EASYPOST_API_KEY=EZ...
SMARTYSTREETS_AUTH_ID=...
SMARTYSTREETS_AUTH_TOKEN=...

# Notifications
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
SENDGRID_API_KEY=SG...

# Odoo Integration
ODOO_URL=
ODOO_DB=
ODOO_USERNAME=
ODOO_PASSWORD=

# Frontend
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
FRONTEND_URL=https://app.yourdomain.com

# PostgreSQL for Docker Compose
POSTGRES_DB=fulfillment
POSTGRES_USER=fulfillment
POSTGRES_PASSWORD=<random>
```

---

## Phase 2 — Deployment Options (Choose One)

### Option A: VPS with Docker Compose (Recommended for Start)

**Pros:** Simple, cheap ($10–20/mo), full control  
**Cons:** Manual scaling, you manage SSL + backups  

**Steps:**

1. **Provision VPS** (DigitalOcean / Hetzner / Linode — 4GB RAM, 2 CPU)
2. **Install Docker + Docker Compose**
3. **Copy files to server:**
   ```bash
   rsync -avz --exclude node_modules --exclude .git ./ root@yourserver:/opt/fulfillment/
   ```
4. **Create `.env` on server** with production values
5. **Start with docker compose:**
   ```bash
   cd /opt/fulfillment
   docker compose -f docker-compose.prod.yml --env-file .env up -d
   ```
6. **Set up reverse proxy** (Caddy — auto SSL):
   ```bash
   # Caddyfile
   api.yourdomain.com {
       reverse_proxy localhost:8000
   }
   app.yourdomain.com {
       reverse_proxy localhost:3000
   }
   ```
7. **Set up backups:**
   ```bash
   0 3 * * * docker exec postgres pg_dump -U fulfillment fulfillment > /backups/db_$(date +\%Y\%m\%d).sql
   ```

### Option B: Azure Container Apps (AGENTS.md Recommended)

**Pros:** Scale-to-zero, managed SSL, managed Postgres (Neon)  
**Cons:** Higher cost, more complex setup  

**Steps:**

1. **Create Azure Container Apps environment**
2. **Deploy API app:**
   ```bash
   az containerapp create \
     --name fulfillment-api \
     --image $REGISTRY/fulfillment-api:latest \
     --target-port 8000 \
     --ingress external \
     --min-replicas 0 \
     --max-replicas 3 \
     --env-vars DATABASE_URL=... JWT_SECRET=... \
     --secrets openai-key=...
   ```
3. **Deploy Frontend app:**
   ```bash
   az containerapp create \
     --name fulfillment-ui \
     --image $REGISTRY/fulfillment-ui:latest \
     --target-port 3000 \
     --ingress external \
     --env-vars NEXT_PUBLIC_API_URL=https://fulfillment-api.azurecontainerapps.io
   ```
4. **Set up Neon Postgres** — create branch, get pooled URL
5. **Wire secrets** — use `secretref:` in ACA config
6. **Health check ladder:**
   - [ ] API boots with SQLite → `{"status":"ok","backends":{"postgres":false}}`
   - [ ] Wire Neon Postgres → `{"postgres":true}`
   - [ ] Wire Qdrant → `{"postgres":true,"qdrant":true}`
   - [ ] Wire Odoo connection

### Option C: Single Server (Simplest — Current Local Setup)

If this is for demo/personal use, just:

1. Run backend: `python -m uvicorn fulfillment.main:app --host 0.0.0.0 --port 8000`
2. Run frontend: `npx next start -p 3000` (after `npm run build`)
3. Set up Nginx/Caddy as reverse proxy
4. Use SQLite / managed Postgres

---

## Phase 3 — Production Checklist

### Pre-Launch

- [ ] **API health endpoint** returns correct status
- [ ] **CORS** restricted to frontend domain (not `*`)
- [ ] **JWT_SECRET** = strong random value
- [ ] **Rate limiting** enabled (AGENTS.md rule #10)
- [ ] **Database** — PostgreSQL in production (not SQLite)
- [ ] **SSL/TLS** — Caddy/LetsEncrypt or ACA managed
- [ ] **Frontend** — `NEXT_PUBLIC_API_URL` = production API URL
- [ ] **Next.js rewrites** removed or pointed to prod API
- [ ] **Odoo** — API credentials configured

### Monitoring

| Tool | Purpose |
|------|---------|
| Health endpoint | `GET /health` — uptime check |
| Docker logs | `docker compose logs -f` |
| Uptime Robot / Better Uptime | External ping every 5 min |
| Celery Flower (optional) | Task queue monitoring |

### Security (AGENTS.md Critical Rules)

- [ ] **Never run agent code in harness** — rule #1
- [ ] **Presigned URLs only in sandbox** — rule #2
- [ ] **Schema-qualified SQL** — rule #3 (if PostgreSQL)
- [ ] **max_turns on every Runner.run()** — rule #5
- [ ] **fail closed** — database down = tool refuses — rule #16

### Backup Strategy

```
PostgreSQL:  pg_dump daily → S3/R2 (30-day retention)
SQLite:      .backup daily → S3/R2 (30-day retention)
.env:        stored in GitHub Secrets / Azure KV
```

---

## Phase 4 — Rollout Strategy

Following AGENTS.md release pattern:

```
Step 1:   Deploy API with SQLite → verify /health
Step 2:   Wire PostgreSQL → verify /health shows postgres:true
Step 3:   Deploy Frontend → verify login + dashboard loads
Step 4:   Wire Odoo → verify integration page connects
Step 5:   Wire Celery → verify monitor cycles run
Step 6:   Add rate limiting → verify 429 on abuse
```

**Rollback:** `docker compose -f docker-compose.prod.yml down && docker compose -f docker-compose.prod.yml up -d` with previous image tag.

---

## Files to Create

| File | Purpose |
|------|---------|
| `.github/workflows/deploy.yml` | CI/CD pipeline |
| `agent-platform-ui-main/agent-platform-ui-main/Dockerfile` | Frontend container |
| `infra/caddy/Caddyfile` | Reverse proxy config |
| `infra/backup.sh` | Database backup script |
| `scripts/deploy.sh` | One-command deploy script |
| `.env.example` | Update with all new vars |

## Estimated Timeline

| Phase | Time |
|-------|------|
| CI/CD pipeline | 2–3 hours |
| Docker setup | 1–2 hours |
| VPS/Cloud provisioning | 30 min |
| SSL + Domain | 30 min |
| Production testing | 2–3 hours |
| **Total** | **6–9 hours** |
