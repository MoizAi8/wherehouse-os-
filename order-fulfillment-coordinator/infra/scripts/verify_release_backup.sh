# Sourced in a subshell by deploy.sh while it holds the deployment lock.
# COMPOSE and DOCKER address the same project and daemon as the migration.
set -Eeuo pipefail
umask 077
root=${RELEASE_BACKUP_DIR:-"$HOME/fulfillment/recovery"}
mkdir -p "$root"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
backup=$(mktemp -d "$root/pre-migration-$stamp.XXXXXX")

# An empty public schema is valid on first installation. On an existing
# database, a missing revision table or multiple revisions must fail closed.
revision_sql="SELECT NOT EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public') AS empty
\gset
\if :empty
\echo empty
\else
SELECT version_num FROM public.alembic_version;
\endif"
live_revision=$(printf '%s\n' "$revision_sql" | "${COMPOSE[@]}" exec -T postgres sh -ec '
    exec psql -XAtq -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"
')
[[ "$live_revision" == empty || "$live_revision" =~ ^[a-f0-9]{12}$ ]] || {
    echo 'Unexpected production Alembic revision; migration stopped.' >&2
    exit 1
}
pg_container=$("${COMPOSE[@]}" ps -q postgres)
pg_image=$("${DOCKER[@]}" inspect --format '{{.Image}}' "$pg_container")
[[ "$pg_image" =~ ^sha256:[a-f0-9]{64}$ ]]
if ! "${COMPOSE[@]}" exec -T postgres sh -ec '
    exec pg_dump --format=custom -U "$POSTGRES_USER" -d "$POSTGRES_DB"
' > "$backup/postgres.dump.partial" 2>"$backup/dump.log"; then
    echo 'Database backup failed; inspect the private dump log.' >&2
    exit 1
fi
test -s "$backup/postgres.dump.partial"
mv "$backup/postgres.dump.partial" "$backup/postgres.dump"
(
    cd "$backup"
    sha256sum postgres.dump > SHA256SUMS
    sha256sum --check --status SHA256SUMS
)

# No production mounts, network, published ports or credentials. Docker
# removes the disposable cluster with the container, including anonymous volumes.
if ! restored_revision=$("${DOCKER[@]}" run --rm -i --network none --user postgres \
    --entrypoint bash "$pg_image" -ceu '
        data=$(mktemp -d)
        initdb -D "$data" --auth-local=trust --auth-host=reject >/dev/null
        pg_ctl -D "$data" -l "$data/server.log" -o "-c listen_addresses= -k /tmp" -w start >/dev/null
        export PGHOST=/tmp PGDATABASE=postgres
        pg_restore --single-transaction --exit-on-error --no-owner --no-privileges --dbname=postgres
        printf "%s\n" "$1" | psql -XAtq -v ON_ERROR_STOP=1
    ' verify "$revision_sql" < "$backup/postgres.dump" 2>"$backup/restore.log"); then
    echo 'Isolated PostgreSQL restore failed; migration stopped.' >&2
    exit 1
fi
[[ "$restored_revision" == "$live_revision" ]] || {
    echo 'Restored revision differs from the source; migration stopped.' >&2
    exit 1
}
printf 'verified_at=%s\nsource_revision=%s\nrestore=passed\n' \
    "$(date -u +%FT%TZ)" "$live_revision" > "$backup/verified"
echo "Fresh PostgreSQL backup restored successfully: $stamp, revision $live_revision."
