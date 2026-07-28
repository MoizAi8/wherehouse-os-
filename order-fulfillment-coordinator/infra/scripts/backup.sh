#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════
# Database Backup Script — runs via cron
# ═══════════════════════════════════════════════════════
#
# Install in crontab:
#   0 3 * * * /opt/fulfillment/infra/scripts/backup.sh
#
# ═══════════════════════════════════════════════════════

BACKUP_DIR="/opt/backups/fulfillment"
RETENTION_DAYS=30
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_FILE="fulfillment_${TIMESTAMP}.sql"
LOG_FILE="${BACKUP_DIR}/backup.log"

mkdir -p "$BACKUP_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# ── PostgreSQL backup ────────────────────────────────
if docker ps --format '{{.Names}}' | grep -q 'fulfillment-postgres'; then
    log "Starting PostgreSQL backup..."
    if docker exec fulfillment-postgres-1 pg_dump \
        -U "${POSTGRES_USER:-fulfillment}" \
        -d "${POSTGRES_DB:-fulfillment}" \
        --clean --if-exists > "${BACKUP_DIR}/${DB_FILE}" 2>> "$LOG_FILE"; then
        gzip "${BACKUP_DIR}/${DB_FILE}"
        log "✅ PostgreSQL backup: ${DB_FILE}.gz ($(du -h "${BACKUP_DIR}/${DB_FILE}.gz" | cut -f1))"
    else
        log "❌ PostgreSQL backup failed"
        rm -f "${BACKUP_DIR}/${DB_FILE}"
    fi
else
    log "⚠️  PostgreSQL container not running, skipping"
fi

# ── SQLite fallback backup ───────────────────────────
if [ -f "/opt/fulfillment/apps/api/fulfillment.db" ]; then
    log "Starting SQLite backup..."
    cp "/opt/fulfillment/apps/api/fulfillment.db" "${BACKUP_DIR}/fulfillment_${TIMESTAMP}.db"
    gzip "${BACKUP_DIR}/fulfillment_${TIMESTAMP}.db"
    log "✅ SQLite backup: fulfillment_${TIMESTAMP}.db.gz"
fi

# ── Rotate old backups ──────────────────────────────
log "Rotating backups older than ${RETENTION_DAYS} days..."
find "$BACKUP_DIR" -name "fulfillment_*.sql.gz" -type f -mtime "+${RETENTION_DAYS}" -delete
find "$BACKUP_DIR" -name "fulfillment_*.db.gz" -type f -mtime "+${RETENTION_DAYS}" -delete
log "Cleanup complete"
