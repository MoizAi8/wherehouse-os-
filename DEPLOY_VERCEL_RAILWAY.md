# Vercel Frontend + Railway Backend Demo Deployment

## Architecture
```
┌─────────────┐     ┌─────────────┐
│   Vercel    │────▶│   Railway   │
│  (Next.js)  │     │  (FastAPI)  │
└─────────────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    ▼           ▼
               PostgreSQL    Redis
               (Railway)     (Railway)
```

---

## 1. Deploy Backend to Railway

### Step 1: Create Railway Project
1. Go to [railway.app](https://railway.app) → New Project
2. Add **PostgreSQL** plugin
3. Add **Redis** plugin
4. Connect your GitHub repo → select `order-fulfillment-coordinator/apps/api`

### Step 2: Configure Environment Variables (Railway Dashboard)
Copy from `.env.example` and set in Railway:

```bash
# Required
DEBUG=false
DATABASE_URL=${{Postgres.DATABASE_URL}}  # Auto-filled by Railway
REDIS_URL=${{Redis.REDIS_URL}}            # Auto-filled by Railway

JWT_SECRET=your-64-char-random-string
WEBHOOK_SECRET=your-64-char-random-string

OPENAI_API_KEY=your-gemini-or-openai-key
OPENAI_MODEL=gemini-3.6-flash

# CORS - replace with your Vercel URL after frontend deploy
CORS_ORIGINS=https://your-app.vercel.app

# Optional for demo (can leave empty)
QDRANT_URL=
ODOO_URL=
TWILIO_ACCOUNT_SID=
SENDGRID_API_KEY=
INTEGRATION_SECRET_KEY=your-44-char-base64-key
```

### Step 3: Add Start Command
In Railway service settings:
```
Start Command: uv run python -m src.fulfillment.main
```
Or use the Dockerfile (Railway auto-detects).

### Step 4: Get Backend URL
After deploy, copy your Railway URL (e.g., `https://fulfillos-api.up.railway.app`)

---

## 2. Deploy Frontend to Vercel

### Step 1: Import to Vercel
1. Go to [vercel.com](https://vercel.com) → Add New Project
2. Import `agent-platform-ui-main/agent-platform-ui-main` folder
3. Framework: Next.js (auto-detected)

### Step 2: Environment Variables (Vercel Dashboard)
```
NEXTAUTH_URL=https://your-app.vercel.app
NEXTAUTH_SECRET=your-64-char-random-string (same as JWT_SECRET or different)
BACKEND_URL=https://your-railway-url.up.railway.app
```

### Step 3: Deploy
Vercel builds automatically. Your demo will be live at `https://your-app.vercel.app`

---

## 3. Update CORS (After Both Deployed)

Go back to Railway → add your Vercel URL to `CORS_ORIGINS`:
```
CORS_ORIGINS=https://your-app.vercel.app
```
Redeploy backend.

---

## Quick Commands

### Local Test Before Deploy
```bash
# Frontend
cd agent-platform-ui-main/agent-platform-ui-main
pnpm run build  # Should succeed

# Backend
cd order-fulfillment-coordinator/apps/api
uv run python -m src.fulfillment.main  # Should start on :8000
```

### Generate Secrets
```bash
# JWT_SECRET / WEBHOOK_SECRET (64 chars)
openssl rand -base64 48

# INTEGRATION_SECRET_KEY (44 chars base64)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## Notes
- **Qdrant**: Optional for demo (vector search disabled)
- **Odoo/Twilio/SendGrid**: Optional for demo
- **SQLite fallback**: Backend works with SQLite if `DATABASE_URL` not set, but Railway provides Postgres
- **Celery**: Railway runs workers separately — add a second service with `uv run celery -A src.fulfillment.celery_app worker -l info`

---

## Alternative: All-in-One on Render
If you prefer one platform, [Render](https://render.com) supports:
- Web Service (FastAPI)
- Background Worker (Celery)
- PostgreSQL
- Redis
All in one project. Similar env vars.

---

## Need Help?
Run locally first to verify:
```bash
# Terminal 1: Backend
cd order-fulfillment-coordinator/apps/api && uv run python -m src.fulfillment.main

# Terminal 2: Frontend
cd agent-platform-ui-main/agent-platform-ui-main && pnpm run dev
```
Then visit `http://localhost:3000`