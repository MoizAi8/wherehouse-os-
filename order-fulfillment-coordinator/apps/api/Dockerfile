# ── Base Stage ──────────────────────────────────────────
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

RUN groupadd -r appuser && useradd -r -g appuser appuser

# ── Builder Stage ───────────────────────────────────────
FROM base AS builder

ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN pip install --no-cache-dir uv && \
    uv sync --frozen --no-dev

# ── Production Stage ────────────────────────────────────
FROM base AS production

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY src/ ./src/

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request, json; r=urllib.request.urlopen('http://localhost:8000/health'); data=json.loads(r.read()); exit(0 if data.get('status')=='ok' else 1)"

CMD ["uvicorn", "fulfillment.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
