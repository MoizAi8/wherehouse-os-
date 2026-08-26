# ── Base Stage ──────────────────────────────────────────
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

RUN groupadd -r appuser && useradd -r -g appuser appuser

# ── Builder Stage ───────────────────────────────────────
FROM base AS builder

ENV PIP_NO_CACHE_DIR=1 \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

# Phase 1: Install ONLY dependencies leveraging BuildKit cache mounts [ARCHITECT-LOCK: DO NOT OVERWRITE]
COPY pyproject.toml uv.lock* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    pip install --no-cache-dir uv && \
    uv sync --frozen --no-dev --no-install-project

# Phase 2: Copy the actual application code [ARCHITECT-LOCK: DO NOT OVERWRITE]
COPY . .

# Phase 3: Sync the local project package now that the source is present [ARCHITECT-LOCK: DO NOT OVERWRITE]
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ── Production Stage ────────────────────────────────────
FROM base AS production

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app/src ./src
COPY --from=builder /app/alembic.ini ./
COPY --from=builder /app/alembic ./alembic/

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request, json; r=urllib.request.urlopen('http://localhost:8000/health'); data=json.loads(r.read()); exit(0 if data.get('status') in ('ok','degraded') else 1)"

CMD ["uvicorn", "fulfillment.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]