# ── Base Stage ──────────────────────────────────────────
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

RUN groupadd -r appuser && useradd -r -g appuser appuser

# ── Builder Stage ───────────────────────────────────────
FROM base AS builder
ARG UV_VERSION=0.12.3

ENV PIP_NO_CACHE_DIR=1 \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

# Phase 1: Install ONLY dependencies leveraging BuildKit cache mounts
COPY pyproject.toml uv.lock* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    pip install --no-cache-dir "uv==${UV_VERSION}" && \
    uv sync --frozen --no-dev --no-install-project

# Phase 2: Copy the actual application code
COPY . .

# Phase 3: Sync the local project package now that the source is present
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ── Production Stage ────────────────────────────────────
FROM base AS production

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application source and config
COPY --from=builder /app/src ./src
COPY --from=builder /app/alembic.ini ./
COPY --from=builder /app/alembic ./alembic/

# Expose venv binaries to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Set ownership and switch to non-root user
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=15s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request, json; r=urllib.request.urlopen('http://localhost:8000/health'); data=json.loads(r.read()); exit(0 if data.get('status') in ('ok','degraded') else 1)"

CMD ["uvicorn", "fulfillment.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
