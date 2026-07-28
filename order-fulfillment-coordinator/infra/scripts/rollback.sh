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

# Get the previous image ID
PREV_IMAGE=$(docker images --format "{{.ID}}" "fulfillment-${SERVICE}" | sed -n '2p')
if [ -n "$PREV_IMAGE" ]; then
    docker tag "$PREV_IMAGE" "fulfillment-${SERVICE}:latest"
fi

docker compose -f docker-compose.prod.yml up -d "$SERVICE"
echo "✅ Rollback complete. Verify at /health"
