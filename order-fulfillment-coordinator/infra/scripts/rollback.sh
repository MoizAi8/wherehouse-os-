#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════
# Rollback Script — reverts to previous Docker image
# ═══════════════════════════════════════════════════════
# Rollback is a traffic change, not a redeploy (AGENTS.md rule)
# Usage: ./infra/scripts/rollback.sh [service-name]

SERVICE="${1:-api}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$SCRIPT_DIR"

echo "⚠️  Rolling back ${SERVICE} to previous version..."

# Stop current, remove, then restart with previous image
docker compose -f docker-compose.prod.yml stop "$SERVICE"
docker compose -f docker-compose.prod.yml rm -f "$SERVICE"
docker compose -f docker-compose.prod.yml create "$SERVICE"

# Get the previous image ID (compose project name may be the dir name, e.g.
# order-fulfillment-coordinator-api). Match any image for this service.
PREV_IMAGE=$(docker images --format "{{.Repository}}:{{.Tag}} {{.ID}}" | awk -v svc="$SERVICE" '$1 ~ ("-"svc"$") {print $2}' | sed -n '2p')
if [ -n "$PREV_IMAGE" ]; then
    docker tag "$PREV_IMAGE" "order-fulfillment-coordinator-${SERVICE}:rollback"
    docker compose -f docker-compose.prod.yml up -d "$SERVICE"
    echo "✅ Rollback complete using image ${PREV_IMAGE}. Verify at /health"
else
    echo "⚠️  No previous image found for ${SERVICE}; restarting current image only."
    docker compose -f docker-compose.prod.yml up -d "$SERVICE"
fi
