# Production recovery and deployment runbook

Updated 2026-11-02. The current [completion report](production-completion-report.md)
and [merge/deployment plan](merge-deployment-plan.md) supersede earlier status
snapshots. Local runtime, clean-install, audit, schema/auth, proxy-routing, and
workflow checks are verified. Docker image/service integration and live OCI
checks remain external prerequisites. Nothing has been pushed or deployed.

**Merging/pushing main no longer deploys OCI.** Tests and image builds run on
main pushes and pull requests. Deployment requires manual `workflow_dispatch`
on this fork's main with `deploy=true`. Configure production reviewers before
using that gate; the inspected environment currently has no protection rules.

## Authoritative execution path

GitHub `.github/workflows/deploy.yml` tests the API in `apps/api` and the frontend
in `../agent-platform-ui-main/agent-platform-ui-main`. It builds GHCR images
`fulfillment-api:<commit SHA>` and `fulfillment-ui:<commit SHA>`. The deploy job
copies only Compose and infrastructure files into
`~/fulfillment/releases/<SHA>-<run-id>-<attempt>/order-fulfillment-coordinator`, then calls
`infra/scripts/deploy.sh`. It does not rebuild images on the VM.

Caddy owns public ports 80/443. FastAPI, Next.js, PostgreSQL, Redis, and Qdrant
remain private to the Docker network. PostgreSQL and Qdrant have named volumes;
Caddy certificate state persists. The project name remains
`order-fulfillment-coordinator` to reuse the existing volumes. **Confirm this
name against the live container labels before first use.** Never substitute a
new project name to evade a name collision: that can attach empty volumes.

The deployment is a single-stack service replacement, with possible downtime.
It is not blue/green, and it does not satisfy the architecture's traffic-only
rollback or one-backend-flip requirements. That needs a separate reviewed
serving-slot design and capacity verification before claiming those guarantees.

## Required approvals and preparation

1. Review the committed repair diff and current audit reports. Node 24.22.2 LTS
   is pinned in CI, Docker, and .nvmrc. Use npm 11 and strict npm ci with the
   verified lockfile; do not regenerate or delete it during deployment.
2. Configure the GitHub `production` environment with required reviewers and
   restrict it to `main`. Pushes run checks and image builds; production deployment is manual. Protect
   this environment before approving a live run. Publishing, merging, pushing, and deployment
   each require the owner's authorization.
3. Provision Docker Engine and Compose v2 on OCI separately. Confirm that the
   deployment account can run `docker info` or `sudo -n docker info`, and that
   Bash, `flock`, `base64`, and curl are installed. Compose must support
   multiple `--env-file` options, `--wait`, and `config --format json`. The
   deploy script deliberately does not install packages or stop host services.
4. Verify the VM architecture matches the built images (current workflow uses
   the GitHub hosted runner's architecture). Verify disk, RAM, swap policy,
   persistent-volume ownership, and workload capacity on staging. A free-tier
   label is not evidence that this eight-service stack fits the instance.
5. Verify DNS A/AAAA records, OCI security lists/NSGs, host firewall, and ingress
   TCP 80/443. Restrict SSH appropriately. No database/cache/vector port needs
   public exposure. The local TLS probe does not verify external connectivity.
6. Record and test a PostgreSQL backup and Qdrant recovery procedure. Do not
   rely on the legacy backup script's first-container-name match. Confirm the
   selected database and volume explicitly. No backup or restore was executed
   in this investigation.

The repaired Compose file separates Qdrant snapshots from its storage volume.
The original storage volume is retained. Inventory any existing snapshots
before rollout and arrange an approved copy if needed; the new snapshot volume
starts empty. Do not remove the old storage volume.

## GitHub secrets and settings

Required SSH secrets: `OCI_HOST`, `OCI_USERNAME`, `OCI_SSH_KEY`, and
`OCI_SSH_FINGERPRINT`. Obtain the SHA256 host fingerprint through the OCI console
or another trusted channel, for example on the host:

```bash
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub -E sha256
```

Do not trust an unverified network scan as the fingerprint source.

Required application secrets: `POSTGRES_PASSWORD`, `JWT_SECRET`, `WEBHOOK_SECRET`,
`INTEGRATION_SECRET_KEY`, `OPENAI_API_KEY`, `DOMAIN`, and `FRONTEND_URL`.
`POSTGRES_USER`/`POSTGRES_DB` default to `fulfillment`; existing volumes must use
their original values. Changing PostgreSQL initialization variables does not
rotate credentials inside an existing database. Use strong random secrets;
the integration key must be a valid Fernet key. Never rotate that key without
an approved data re-encryption plan and a backup of the old key.

`DOMAIN` is a bare DNS hostname; `FRONTEND_URL` is its public HTTPS origin.
Optional provider, Qdrant, Odoo, mail/SMS, model, rate, and monitoring settings
are listed under `CFG_*` in the workflow and in `.env.example`. Missing optional
values use application/Compose defaults. Internal addresses are `api:8000`,
`postgres:5432`, `redis:6379`, `qdrant:6333`, and `frontend:3000`.
An external Qdrant URL is supported but must be independently verified.

The CI dotenv encoder preserves dollar signs, hashes, and spaces as literal
values. It refuses newlines, NULs, single quotes, and backslashes rather than
evaluating shell input. PostgreSQL passwords must use URL-safe characters
(`A-Z`, `a-z`, digits, `.`, `_`, `~`, `-`) because Compose interpolates a URL.
Do not change a live password merely to satisfy this constraint; coordinate
an approved rotation or implement encoded URL construction first.

Production enforces `DEBUG=false`, rate limiting, and Odoo TLS verification.
`API_URL`/public `FRONTEND_URL` no longer control Caddy's internal upstreams.
No `NEXT_PUBLIC_OPENAI_API_KEY` is supported. If one was ever published, rotate
it through the provider and purge/rebuild affected assets with approval.

GHCR login uses the job's scoped `GITHUB_TOKEN`; grant this repository Actions
read access to both packages if private. OCI API-key secrets/OCI CLI are no
longer needed for this SSH-only workflow.

## Recover the original Qdrant name conflict safely

The failed run stopped at container creation, before health polling. On the
authorized OCI host, gather only labels, status, networks, and mount metadata:

```bash
sudo docker ps -a --filter name=order-fulfillment-coordinator-qdrant-1
sudo docker inspect -f '{{json .Config.Labels}}' order-fulfillment-coordinator-qdrant-1
sudo docker inspect -f '{{json .Mounts}}' order-fulfillment-coordinator-qdrant-1
sudo docker inspect -f '{{json .NetworkSettings.Networks}}' order-fulfillment-coordinator-qdrant-1
sudo docker compose ls -a
```

Do not publish full `docker inspect` output: environment values may be secret.
Determine whether another Compose invocation owns this container, whether a
previous operation is running, and which storage volume contains live data.
The new script refuses containers owned by a different project/service and
serializes deployments with a host lock. It does not remove existing conflicts.
An operator must approve any rename/removal or ownership repair after checking
data and service impact. Never run `down -v`, broad `docker rm -f`, `fuser -k`,
or a global prune as a recovery shortcut.

## Migrations and credentials

The script starts/waits for infrastructure, then executes
`alembic upgrade head` before replacing the application. Test migrations on a
copy of the production database first. The old workflow omitted migrations;
databases created by `create_all` can contain tables without an Alembic version.
If an initial migration reports existing tables, stop and compare the schema
against migration history. Do not blindly stamp or drop tables.

Production now refuses plaintext/undecryptable integration credentials. Check
stored integrations in a private staging copy using the existing Fernet key.
For legacy plaintext, plan an approved, backed-up encryption migration;
do not enable DEBUG or replace a key to bypass the guard. Registering a user
still creates a viewer; verify an authorized administrator account exists.
Demo seed data is not automatically inserted by the deployment.

## Deployment, after blockers and approvals

1. Run backend lint, types, tests, frontend lint, types, tests, and builds.
   Run real Docker/Compose/Caddy/migration integration checks on staging.
2. Review, authorize, and push/merge the approved commit to protected `main`.
   Inspect the resulting GitHub Actions run. Build jobs publish the tested SHA.
3. Approve the `production` environment deployment only after confirming the
   backup, migration compatibility, package access, host conflict resolution,
   required secrets, and a maintenance window for service replacement.
4. The script locks the host, validates config and ownership, authenticates to
   GHCR temporarily, pulls images, checks production settings and Caddy config,
   waits for infrastructure, migrates, and replaces services without `down`.
5. Readiness requires exact JSON `status=ok` and boolean `postgres`, `celery`,
   and `qdrant` backend flags. It then verifies TLS/SNI/Host routing through
   local Caddy using the configured hostname, probes the frontend and NextAuth
   session endpoint, and records the successful release. Certificate checking
   remains enabled. Retries and request timeouts are bounded.
6. Independently verify from outside OCI: public HTTPS `/health`, login/session,
   an authenticated read-only order request, dashboard, WebSocket handshake,
   and the scheduled monitor job on the intended queue. Confirm Odoo/provider
   operations only in an authorized test environment. Do not equate a passing
   container healthcheck with successful order fulfillment.

## Failure handling and rollback

Failed critical commands return nonzero. Images, release files, and volumes
are retained. CI prints container status; inspect service logs privately on
the host because application logs may contain customer data. No automatic
rollback, image pruning, or database downgrade occurs.

`~/fulfillment/deploy-state/current-release` records the latest successful
release directory; `previous-release` records its predecessor. Each release.env retains the exact
application registry digests; reruns use distinct directories and cannot replace
the previous configuration merely by rebuilding the same commit tag. The first
deployment using this workflow has no automatically captured old release.
Record the original image IDs/digests and configuration privately before it.

`rollback.sh` now refuses safely: the current topology cannot switch traffic
to an already-running previous slot. This is an explicit readiness blocker,
not a successful rollback implementation. A true traffic-only rollback needs
reviewed parallel serving slots and a verified Caddy switch.

The new `infra/scripts/recover-release.sh --check` validates the recorded
previous path, configuration, and local digest availability without changing
services. It refuses missing metadata or resources outside the release root.
After explicit owner approval and schema review, invoke:

```bash
bash infra/scripts/recover-release.sh --replace-services --schema-compatible
```

This holds the deployment lock, uses retained digests/configuration without
pulling/building/migrating, replaces application services, verifies backend and
HTTPS/frontend/session health, and updates release pointers only on success.
It leaves infrastructure and volumes intact. No live replacement has been tested
here. Compatibility acknowledgement is an operator attestation, not an automatic
proof; do not bypass schema review. Records from deployments predating digest
capture require an approved inventory before this command can work.

If the owner explicitly approves service replacement as an interim recovery,
validate that the previous release's schema expectations remain compatible
with the current database. From its retained directory, run these commands
only after a reviewed backup/recovery plan:

```bash
exec 9>"$HOME/fulfillment/deploy-state/deploy.lock"
flock -w 900 9
unset TAG IMAGE_OWNER CONFIG_B64
cd /absolute/path/to/the/verified/previous/order-fulfillment-coordinator
sudo docker compose -p order-fulfillment-coordinator --env-file .env --env-file release.env -f docker-compose.prod.yml config --quiet
sudo docker compose -p order-fulfillment-coordinator --env-file .env --env-file release.env -f docker-compose.prod.yml up -d --no-build --pull never api celery-worker celery-beat frontend caddy
```

Hold the same deployment lock (`flock` on
`~/fulfillment/deploy-state/deploy.lock`) for this entire manual operation.
Use already-retained images and restore that release's Caddy configuration.
Recheck backend JSON, Caddy HTTPS, frontend, login, and the worker. Keep the
deployment marked failed until all checks pass. This causes possible downtime
and is **not** the architecture-required traffic rollback. Do not automatically
reverse migrations or restore a production database over newer orders.
