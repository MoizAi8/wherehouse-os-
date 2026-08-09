# FulfillOS

AI-powered multi-agent system that autonomously manages the complete post-purchase journey — from warehouse picking to doorstep delivery.

## System Architecture

```
fulfillos/
├── apps/
│   └── api/          # Python FastAPI backend
├── packages/
│   └── shared-types/ # Shared TypeScript type definitions
├── docker-compose.yml
└── docker-compose.prod.yml
```

### Backend (apps/api)
- **Framework:** FastAPI 0.115+ (async)
- **Runtime:** Python 3.12 managed via UV
- **ORM:** SQLAlchemy 2.0 (async) + Alembic
- **Database:** PostgreSQL 16 + Redis 7
- **Task Queue:** Celery + Redis
- **Auth:** JWT (python-jose)
- **Agents:** OpenAI Agents SDK pattern

## Quick Start

### Prerequisites
- Python >= 3.12
- UV (`pip install uv` or `winget install astral.uv`)
- Docker Desktop (optional, for PostgreSQL + Redis)

### 1. Clone and Install

```bash
cd apps/api
uv sync
cd ../..
```

### 2. Start Infrastructure (Docker)

```bash
docker compose up -d postgres redis
```

### 3. Apply Database Migrations

```bash
cd apps/api
uv run alembic upgrade head
```

### 4. Start Development Servers

```bash
cd apps/api
uv run fastapi dev src/fulfillment/main.py
```

### 5. Start Celery Worker (Background Tasks)

```bash
cd apps/api
uv run celery -A fulfillment.tasks worker --loglevel=info
uv run celery -A fulfillment.tasks beat --loglevel=info
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL async connection string |
| `REDIS_URL` | Redis connection string |
| `JWT_SECRET` | JWT signing secret |
| `OPENAI_API_KEY` | OpenAI API key for agent decisions |
| `EASYPOST_API_KEY` | EasyPost API key for rate shopping |
| `TWILIO_ACCOUNT_SID` | Twilio SMS integration |
| `SENDGRID_API_KEY` | SendGrid email integration |

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/v1/orders` | List orders |
| `POST /api/v1/orders` | Create order |
| `GET /api/v1/orders/{id}` | Get order detail |
| `PATCH /api/v1/orders/{id}` | Update order |
| `DELETE /api/v1/orders/{id}` | Delete order |
| `POST /api/v1/orders/{id}/route` | Trigger routing agent |
| `GET /api/v1/shipments` | List active shipments |
| `GET /api/v1/shipments/{id}` | Get shipment detail |
| `POST /api/v1/shipments/{id}/reroute` | Trigger rerouting agent |
| `GET /api/v1/carriers/rates` | List carrier rates |
| `POST /api/v1/carriers/rates` | Rate shopping |
| `POST /api/v1/agents/monitor` | Trigger monitor cycle |
| `GET /api/v1/analytics/kpis` | KPI dashboard data |
| `GET /api/v1/analytics/carriers` | Carrier performance |
| `GET /api/v1/fulfillment-centers` | List fulfillment centers |
| `WS /api/v1/ws/shipments` | Live shipment WebSocket |
| `POST /api/v1/webhooks/order-placed` | Order webhook |
| `POST /api/v1/webhooks/shipment-event` | Shipment event webhook |

## Agents

| Agent | Responsibility |
|---|---|
| **Routing** | FC selection, carrier rate optimization |
| **Monitor** | 15-min cycle polling, delay detection |
| **Re-routing** | Alternative carrier evaluation |
| **Communication** | Proactive SMS/email notifications |
| **Prediction** | Failed delivery probability scoring |
| **Cost Optimizer** | Post-hoc route cost analysis |
| **Orchestrator** | Event-driven agent dispatch |

## Guardrails

| Guardrail | Rule |
|---|---|
| SLA Compliance | New ETA must not exceed promised delivery |
| Cost Cap | Rerouting cost increase ≤ 40% |
| Notification Frequency | Max 4 notifications per order |
| Address Validation | Deliverability score ≥ 0.6 |
| Carrier Diversity | No carrier > 70% daily volume |
| Failed Delivery | Hold if predict_failure > 0.7 |

## KPI Targets

| Metric | Target |
|---|---|
| On-Time Delivery Rate | ≥ 96% |
| WISMO Ticket Rate | ≤ 5% |
| Proactive Delay Detection | ≥ 99% |
| Carrier Rate Savings | 8-15% |
| Rerouting Success Rate | ≥ 85% |
| Failed Delivery Rate | ≤ 1.5% |
| API p99 Latency | ≤ 200ms |

## Testing

```bash
cd apps/api
uv run pytest tests/
```

## License

MIT
