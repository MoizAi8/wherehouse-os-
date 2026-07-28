#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════
# OCI Oracle Cloud Deployment Script
# ═══════════════════════════════════════════════════════
#
# Prerequisites:
#   1. OCI CLI installed (https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/cliinstall.htm)
#   2. Docker + Docker Compose on the instance
#   3. GitHub Secrets configured (see .env.example)
#
# Usage:
#   export DOMAIN=fulfillment.yourdomain.com
#   export SSL_EMAIL=admin@yourdomain.com
#   ./infra/scripts/deploy.sh
#
# ═══════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$SCRIPT_DIR"

echo "→ Pulling latest code..."
git pull origin main

echo "→ Loading environment..."
if [ ! -f .env ]; then
    echo "❌ .env file not found! Copy .env.example to .env and fill values."
    exit 1
fi
set -a; source .env; set +a

echo "→ Building and starting services..."
docker compose -f docker-compose.prod.yml build --pull
docker compose -f docker-compose.prod.yml up -d --force-recreate

echo "→ Waiting for health checks..."
sleep 10
for i in $(seq 1 12); do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ API is healthy"
        break
    fi
    echo "   Waiting... ($i/12)"
    sleep 5
done

echo "→ Cleaning up old images..."
docker image prune -f

echo "✅ Deployment complete!"
echo "   API:  https://${DOMAIN}/health"
echo "   App:  https://${DOMAIN}"
