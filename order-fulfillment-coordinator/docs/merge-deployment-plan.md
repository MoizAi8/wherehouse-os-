# Fork merge and authorized deployment plan

2026-11-02. These are **instructions, not actions already executed**. Source:
`codex/warehouse-production-repair`; target: `MoizAi8/wherehouse-os-:main`.
Never push to `upstream` (`muhammadharis-web/wherehouse-os-`).

## Deployment trigger behavior

The former workflow deployed after a successful main push. The repaired
workflow tests pushes to main and pull requests targeting main, and builds
Docker images. PR builds do not publish images. Main pushes publish SHA-tagged
images but **do not deploy OCI**. Deploy runs only for manual workflow_dispatch
on this fork's main with the boolean `deploy=true`.

The inspected GitHub production environment currently has **no protection
rules**. Set required reviewers and branch restrictions through an explicitly
approved repository-settings change before a live deployment. The manual input
gate prevents deployment on an ordinary merge even without those settings.
Tests are not bypassed; the deployment still depends on the image build job,
which depends on both test jobs.

## Review and push the repair branch — requires authorization

```powershell
Set-Location C:\Users\DC\wherehouse-os-
if ((git branch --show-current) -ne 'codex/warehouse-production-repair') { throw 'Wrong branch' }
if (git status --porcelain) { throw 'Working tree is not clean' }
if ((git remote get-url origin) -notmatch 'github.com[/:]MoizAi8/wherehouse-os-(\.git)?$') { throw 'Wrong origin' }
git log --oneline origin/main..HEAD
git diff --check origin/main...HEAD
git fetch origin main
git merge-tree --write-tree origin/main codex/warehouse-production-repair
if ($LASTEXITCODE -ne 0) { throw 'Resolve and retest conflicts on the repair branch first' }
git push origin codex/warehouse-production-repair
```

Current inspection fetched only origin/main and found it at
`25c01c036fb94240c6111e21b0a169a92dda2152`, an ancestor of the repair branch.
The local merge-tree check succeeded without checking out or merging main.
Remote state may change; fetch and recheck before acting.

Prefer a pull request for remote Linux Docker and test evidence before merging:

```powershell
gh pr create --repo MoizAi8/wherehouse-os- --base main --head codex/warehouse-production-repair --title 'Repair production deployment, runtime compatibility and security' --body 'Align Node LTS and strict lockfile installs, gate OCI deployment manually, harden authentication and chat access, and retain recoverable image digests. Local verification is documented in order-fulfillment-coordinator/docs/production-completion-report.md; real Docker/OCI checks remain required.'
gh pr checks <PR_NUMBER> --repo MoizAi8/wherehouse-os- --watch
```

Do not paste placeholder angle brackets literally; substitute the resulting
PR number. All PR checks, especially Linux image builds, must pass. If they
fail, repair and retest the branch rather than skipping CI.

## Direct local merge to the fork's main — separate authorization required

Use this only after review and green PR checks (or the owner's approved
alternative). These commands were **not** executed:

```powershell
git fetch origin main
if (git status --porcelain) { throw 'Working tree is not clean' }
git merge-tree --write-tree origin/main codex/warehouse-production-repair
if ($LASTEXITCODE -ne 0) { throw 'Merge conflict; stop' }
git switch main
git pull --ff-only origin main
if ($LASTEXITCODE -ne 0) { throw 'Local main diverged; stop without resetting' }
git merge --no-ff codex/warehouse-production-repair -m 'Merge verified production-readiness repairs'
if ($LASTEXITCODE -ne 0) { throw 'Merge failed; stop and resolve safely' }
git diff --check HEAD^1 HEAD
git log -3 --oneline
git push origin main
gh run list --repo MoizAi8/wherehouse-os- --workflow deploy.yml --branch main --limit 5
gh run watch <PUSH_RUN_ID> --repo MoizAi8/wherehouse-os- --exit-status
```

If branch protection requires PR merging, use its approved merge flow instead
of bypassing protections. An ordinary main push leaves the OCI deploy job
skipped under the new workflow.

## Production prerequisites — before approving any deployment

* Green hosted Linux Docker builds; validate the actual VM architecture, image
  compatibility, disk/memory capacity, Docker/Compose versions, and deployment
  account access. No Docker Engine/Desktop is available in the local environment.
* Inspect the original conflicting Qdrant container's labels, mounts and networks
  using the read-only commands in [production-runbook.md](production-runbook.md).
  Identify the correct existing project/volumes and any competing automation.
  Container removal/renaming is a separate live operation requiring approval.
* Verify trusted SSH fingerprint, GitHub production reviewers, GHCR package-read
  permissions, SSH reachability, and required secrets. No values belong in logs.
* Test backup and restore, production PostgreSQL migration compatibility, and
  legacy integration encryption data on staging. Do not stamp/drop existing
  tables to evade a migration failure. New SQLite tests do not prove PostgreSQL.
* Keep original JWT/Fernet keys stable. Existing valid HS256 tokens with the
  application's standard exp/iat/sub claims remain compatible. Review any
  separately issued legacy tokens before rollout. Legacy chat rows had no
  trusted owner; they remain stored but are intentionally not exposed by the
  new user-scoped history. Do not guess ownership or silently reassign records.
* Verify public DNS, OCI NSGs/security lists, host firewall, HTTPS certificates,
  Caddy ports, and all provider configurations. Do not publish backend/state ports.
* Before the first new deployment, privately inventory the existing release,
  configuration, image digests, and volume bindings; there may be no recorded
  previous-release pointer yet. Inventory old Qdrant snapshots before changing
  its snapshot-volume binding. Do not delete the storage volume.

## Explicitly authorized OCI deployment

Only after the owner approves this live operation:

```powershell
gh workflow run deploy.yml --repo MoizAi8/wherehouse-os- --ref main -f deploy=true
gh run list --repo MoizAi8/wherehouse-os- --workflow deploy.yml --branch main --event workflow_dispatch --limit 5
gh run watch <DEPLOY_RUN_ID> --repo MoizAi8/wherehouse-os- --exit-status
```

The workflow rebuilds/tests the selected main commit, then deploys its SHA
images. Each attempt has a unique directory:
`~/fulfillment/releases/<SHA>-<run-id>-<attempt>/order-fulfillment-coordinator`.
The host lock serializes service operations. The script verifies ownership,
pulls images, records exact application registry digests in release.env,
validates production settings/Caddy, waits for infrastructure, runs migrations,
replaces services, and requires exact dependency health plus local HTTPS,
frontend and session checks. It does not kill ports, bring the stack down,
delete volumes, or prune images.

From outside OCI, independently verify the actual public hostname:

```powershell
$health = Invoke-RestMethod 'https://YOUR_CONFIGURED_DOMAIN/health' -TimeoutSec 15
if ($health.status -ne 'ok' -or !$health.backends.postgres -or !$health.backends.celery -or !$health.backends.qdrant) { throw 'Dependency readiness failed' }
Invoke-WebRequest 'https://YOUR_CONFIGURED_DOMAIN/' -TimeoutSec 15
Invoke-RestMethod 'https://YOUR_CONFIGURED_DOMAIN/api/auth/session' -TimeoutSec 15
```

Also verify an authorized real login, read-only order request, viewer denial of
chat mutations, per-user chat isolation, profile, WebSocket handshake, scheduled
monitoring execution, and provider integrations in an authorized test context.
Do not publish access tokens or use real customer orders as a smoke test.

## Recovery, with separate approval

This single-stack deployment may have downtime. It cannot offer a traffic-only
rollback to an already-running slot; `rollback.sh` still refuses that claim.
No database downgrade or automatic restore occurs.

On the approved host, from a retained repair release directory:

```bash
bash infra/scripts/recover-release.sh --check
# Only after owner approval, a tested backup, and schema-compatibility review:
bash infra/scripts/recover-release.sh --replace-services --schema-compatible
```

The check refuses invalid paths, missing configuration/digest metadata, or
unavailable local application images. The replacement path holds the host
lock and uses the exact previous application digests/configuration, without
pulling, building or migrating. It replaces API/worker/beat/frontend/Caddy,
checks dependency and HTTPS/frontend/session health, and changes release
pointers only after success. Infrastructure volumes are preserved. A failed
recovery exits nonzero and retains evidence/resources. Container execution of
this recovery is still unverified locally; do a staging rehearsal before relying
on it. Schema compatibility is an operator attestation, not something the flag
proves. Never restore over newer orders or reverse migrations automatically.
