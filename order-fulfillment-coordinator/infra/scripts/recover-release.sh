#!/usr/bin/env bash
# Explicit recovery by service replacement; NOT traffic-only or zero downtime.
set -Eeuo pipefail
umask 077
MODE="${1:---check}"
[[ "$MODE" == --check || "$MODE" == --replace-services ]] || { echo 'Use --check or --replace-services --schema-compatible'; exit 1; }
if [[ "$MODE" == --replace-services && "${2:-}" != --schema-compatible ]]; then
    echo 'Refusing replacement until database compatibility has been reviewed (--schema-compatible).'
    exit 1
fi
STATE_DIR="${DEPLOY_STATE_DIR:-$HOME/fulfillment/deploy-state}"
[[ -d "$STATE_DIR" && -s "$STATE_DIR/previous-release" ]] || { echo 'No recorded previous release; nothing changed.'; exit 1; }
exec 9>"$STATE_DIR/deploy.lock"
flock -w 900 9 || { echo 'Deployment lock unavailable'; exit 1; }
RELEASE_ROOT=$(realpath "${DEPLOY_RELEASE_ROOT:-$HOME/fulfillment/releases}")
TARGET=$(realpath "$(cat "$STATE_DIR/previous-release")")
[[ "$TARGET" == "$RELEASE_ROOT/"* ]] || { echo 'Previous release is outside the retained release root'; exit 1; }
cd "$TARGET"
[[ -s .env && -s release.env && -f docker-compose.prod.yml ]] || { echo 'Previous release configuration is incomplete'; exit 1; }
TAG_VALUE=$(sed -n 's/^TAG=//p' release.env)
OWNER_VALUE=$(sed -n 's/^IMAGE_OWNER=//p' release.env)
[[ "$TAG_VALUE" =~ ^[a-f0-9]{40}$ && "$OWNER_VALUE" =~ ^[a-z0-9][a-z0-9-]*$ ]] || { echo 'Invalid retained image metadata'; exit 1; }
unset TAG IMAGE_OWNER API_IMAGE_REF FRONTEND_IMAGE_REF
DOCKER=(docker)
if ! docker info >/dev/null 2>&1; then DOCKER=(sudo -n docker); "${DOCKER[@]}" info >/dev/null; fi
COMPOSE=("${DOCKER[@]}" compose -p order-fulfillment-coordinator --env-file .env --env-file release.env -f docker-compose.prod.yml)
"${COMPOSE[@]}" config --quiet
for pair in API_IMAGE_REF:fulfillment-api FRONTEND_IMAGE_REF:fulfillment-ui; do
    image=$(sed -n "s/^${pair%%:*}=//p" release.env)
    expected="ghcr.io/$OWNER_VALUE/${pair#*:}"
    [[ "$image" =~ ^$expected@sha256:[a-f0-9]{64}$ ]] || { echo 'Retained digest metadata missing or invalid'; exit 1; }
    "${DOCKER[@]}" image inspect "$image" >/dev/null || { echo "Retained ${pair#*:} digest is unavailable; no services changed"; exit 1; }
done
if [[ "$MODE" == --check ]]; then
    echo "Retained release $TAG_VALUE configuration and application images exist. Database compatibility is not proven."
    exit 0
fi
trap 'echo "Recovery failed; volumes and release metadata retained. Inspect service logs privately."' ERR
"${COMPOSE[@]}" up -d --no-deps --no-build --pull never --wait --wait-timeout 240 api celery-worker celery-beat frontend caddy
"${COMPOSE[@]}" exec -T caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
ready=false
for ((attempt=1; attempt<=24; attempt++)); do
    if "${COMPOSE[@]}" exec -T api python - http://localhost:8000/health < infra/scripts/check_readiness.py; then ready=true; break; fi
    sleep 5
done
[[ "$ready" == true ]] || { echo 'Recovered services did not become ready'; exit 1; }
DOMAIN=$("${COMPOSE[@]}" config --format json | "${COMPOSE[@]}" exec -T api python -c 'import json,sys; print(json.load(sys.stdin)["services"]["caddy"]["environment"]["DOMAIN"])')
[[ "$DOMAIN" =~ ^[a-zA-Z0-9.-]+$ && "$DOMAIN" != localhost ]] || exit 1
curl --fail --silent --show-error --connect-timeout 5 --max-time 15 --retry 8 --retry-delay 3 --retry-all-errors --resolve "$DOMAIN:443:127.0.0.1" "https://$DOMAIN/health" > "$STATE_DIR/recovery-health.json"
"${COMPOSE[@]}" exec -T api python -c 'import json,sys;d=json.load(sys.stdin);sys.exit(0 if d.get("status")=="ok" and all(d.get("backends",{}).get(k) is True for k in ("postgres","celery","qdrant")) else 1)' < "$STATE_DIR/recovery-health.json"
for path in / /api/auth/session; do
    curl --fail --silent --show-error --output /dev/null --connect-timeout 5 --max-time 15 --resolve "$DOMAIN:443:127.0.0.1" "https://$DOMAIN$path"
done
if [[ -f "$STATE_DIR/current-release" ]]; then cp "$STATE_DIR/current-release" "$STATE_DIR/previous-release"; fi
printf '%s\n' "$TARGET" > "$STATE_DIR/current-release.new"
mv "$STATE_DIR/current-release.new" "$STATE_DIR/current-release"
echo 'Known-good application release restored by service replacement. No migration, pull, pruning, or volume deletion performed.'
