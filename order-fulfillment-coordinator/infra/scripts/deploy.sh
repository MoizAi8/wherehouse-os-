#!/usr/bin/env bash
# Deploy CI-built images. Single-stack replacement can cause brief downtime.
set -Eeuo pipefail
umask 077
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
RELEASE_DIR="$PWD"
STATE_DIR="${DEPLOY_STATE_DIR:-$HOME/fulfillment/deploy-state}"
mkdir -p "$STATE_DIR"
exec 9>"$STATE_DIR/deploy.lock"
flock -w 900 9 || { echo 'Another deployment holds the host lock'; exit 1; }
: "${TAG:?Set TAG to the tested commit SHA}"
: "${IMAGE_OWNER:?Set IMAGE_OWNER to the registry owner}"
[[ "$TAG" =~ ^[a-f0-9]{40}$ ]] || { echo 'TAG must be a full commit SHA'; exit 1; }
IMAGE_OWNER="${IMAGE_OWNER,,}"
[[ "$IMAGE_OWNER" =~ ^[a-z0-9][a-z0-9-]*$ ]] || exit 1
export TAG IMAGE_OWNER
unset API_IMAGE_REF FRONTEND_IMAGE_REF
if [[ -n "${CONFIG_B64:-}" ]]; then
    printf '%s' "$CONFIG_B64" | base64 --decode > .env.new
    mv .env.new .env
fi
[[ -s .env ]] || { echo 'Missing release .env'; exit 1; }
chmod 600 .env
unset CONFIG_B64
DOCKER=(docker)
if ! docker info >/dev/null 2>&1; then
    DOCKER=(sudo -n docker)
    "${DOCKER[@]}" info >/dev/null
fi
"${DOCKER[@]}" compose version >/dev/null
printf 'TAG=%s\nIMAGE_OWNER=%s\n' "$TAG" "$IMAGE_OWNER" > release.env
COMPOSE=("${DOCKER[@]}" compose --project-name order-fulfillment-coordinator --env-file .env --env-file release.env -f docker-compose.prod.yml)
diagnostics() {
    echo 'Deployment failed. Retained the release, images, and persistent volumes.'
    "${COMPOSE[@]}" ps -a || :
    echo 'Inspect service logs privately on the host; they may contain customer data.'
}
trap diagnostics ERR
"${COMPOSE[@]}" config --quiet
# Refuse name collisions with resources outside this project. Never delete them.
for service in postgres redis qdrant api celery-worker celery-beat frontend caddy; do
    name="order-fulfillment-coordinator-${service}-1"
    if "${DOCKER[@]}" container inspect "$name" >/dev/null 2>&1; then
        project=$("${DOCKER[@]}" inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$name")
        owner_service=$("${DOCKER[@]}" inspect -f '{{index .Config.Labels "com.docker.compose.service"}}' "$name")
        if [[ "$project" != order-fulfillment-coordinator || "$owner_service" != "$service" ]]; then
            echo "Conflicting container $name: inspect ownership and attached volumes before recovery."
            exit 1
        fi
    fi
done
if [[ -n "${REGISTRY_TOKEN:-}" ]]; then
    AUTH_DIR=$(mktemp -d "$STATE_DIR/registry.XXXXXX")
    DOCKER+=(--config "$AUTH_DIR")
    COMPOSE=("${DOCKER[@]}" compose --project-name order-fulfillment-coordinator --env-file .env --env-file release.env -f docker-compose.prod.yml)
    trap 'rm -f "$AUTH_DIR/config.json"; rmdir "$AUTH_DIR"' EXIT
    printf '%s' "$REGISTRY_TOKEN" | "${DOCKER[@]}" login ghcr.io --username "${REGISTRY_USER:?}" --password-stdin
    unset REGISTRY_TOKEN
fi
"${COMPOSE[@]}" pull
# Retain the exact pulled application digests even if a SHA tag is rebuilt.
for pair in API_IMAGE_REF:fulfillment-api FRONTEND_IMAGE_REF:fulfillment-ui; do
    variable="${pair%%:*}"
    repository="ghcr.io/$IMAGE_OWNER/${pair#*:}"
    digest=$("${DOCKER[@]}" image inspect --format '{{index .RepoDigests 0}}' "$repository:$TAG")
    [[ "$digest" =~ ^$repository@sha256:[a-f0-9]{64}$ ]] || { echo "Invalid retained image digest for ${pair#*:}"; exit 1; }
    printf '%s=%s\n' "$variable" "$digest" >> release.env
done
"${COMPOSE[@]}" run --rm --no-deps api python -c 'from fulfillment.config import settings; settings.validate_production()'
"${COMPOSE[@]}" run --rm --no-deps caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
"${COMPOSE[@]}" up -d --no-build --wait --wait-timeout 180 postgres redis qdrant
"${COMPOSE[@]}" run --rm --no-deps api alembic upgrade head
# Compose 2.40 rejects --wait for beat's explicitly disabled inherited API probe.
# Start the scheduler separately; retain real health gates on API and worker.
"${COMPOSE[@]}" up -d --no-build celery-beat
beat_id=$("${COMPOSE[@]}" ps -q celery-beat)
[[ -n "$beat_id" && "$("${DOCKER[@]}" inspect -f '{{.State.Running}}' "$beat_id")" == true ]] || { echo 'Celery scheduler is not running'; exit 1; }
"${COMPOSE[@]}" up -d --no-build --wait --wait-timeout 360 api celery-worker frontend caddy
"${COMPOSE[@]}" exec -T caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
ready=false
for ((attempt=1; attempt<=24; attempt++)); do
    if "${COMPOSE[@]}" exec -T api python - http://localhost:8000/health < infra/scripts/check_readiness.py; then
        ready=true
        break
    fi
    sleep 5
done
[[ "$ready" == true ]] || { echo 'Production dependency readiness timed out'; exit 1; }
DOMAIN=$("${COMPOSE[@]}" config --format json | "${COMPOSE[@]}" exec -T api python -c 'import json,sys; print(json.load(sys.stdin)["services"]["caddy"]["environment"]["DOMAIN"])')
[[ "$DOMAIN" =~ ^[a-zA-Z0-9.-]+$ && "$DOMAIN" != localhost ]] || { echo 'Production DOMAIN must be a DNS hostname'; exit 1; }
curl --fail --silent --show-error --connect-timeout 5 --max-time 15 --retry 8 --retry-delay 3 --retry-all-errors \
    --resolve "$DOMAIN:443:127.0.0.1" "https://$DOMAIN/health" > "$STATE_DIR/health.json"
"${COMPOSE[@]}" exec -T api python -c 'import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get("status")=="ok" and all(d.get("backends",{}).get(k) is True for k in ("postgres","celery","qdrant")) else 1)' < "$STATE_DIR/health.json"
curl --fail --silent --show-error --output /dev/null --connect-timeout 5 --max-time 15 \
    --resolve "$DOMAIN:443:127.0.0.1" "https://$DOMAIN/"
curl --fail --silent --show-error --output /dev/null --connect-timeout 5 --max-time 15 \
    --resolve "$DOMAIN:443:127.0.0.1" "https://$DOMAIN/api/auth/session"
if [[ -f "$STATE_DIR/current-release" && "$(cat "$STATE_DIR/current-release")" != "$RELEASE_DIR" ]]; then
    cp "$STATE_DIR/current-release" "$STATE_DIR/previous-release"
fi
printf '%s\n' "$RELEASE_DIR" > "$STATE_DIR/current-release.new"
mv "$STATE_DIR/current-release.new" "$STATE_DIR/current-release"
echo 'Deployment verified. Previous release and images retained; no pruning performed.'
