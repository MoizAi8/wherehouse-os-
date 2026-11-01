# Security dependency compatibility and verification

2026-11-02. Upgrades were installed only after source inspection, registry
metadata, release-note review, and strict-peer dry-run success. No
`--legacy-peer-deps`, `--force`, bulk audit fix, or application migration was used.

## Checkpoint

The repair baseline already existed as commit
`ba70fd7c1f140d88ea985f980d798ecf62f459a3`. Before installation, a local tag
`codex/security-upgrades-baseline-20261102` was created pointing to that commit.
No commits, tags, or code were pushed. Dependency upgrades remain reviewable
working-tree changes on `codex/warehouse-production-repair`.

## Confirmed compatibility

| Package | Declared/locked/installed before | Installed and pinned after |
|---|---|---|
| next | 16.2.7 | 16.4.3 |
| eslint-config-next | 16.2.7 | 16.4.3, remains a dev dependency |
| next-auth | ^4.24.14 / 4.24.14 / 4.24.14 | 4.24.15 |
| zod | ^4.4.3 / 4.4.3 / 4.4.3 | 4.6.7 |
| source-map-js (transitive) | 1.2.1 | 1.2.2 within the existing parent range |
| react / react-dom | 19.2.4 | unchanged |
| ai / @ai-sdk/openai | 6.0.198 / 3.0.68 | unchanged |

**There was no Zod 3 to 4 migration.** The lockfile contained one actual Zod
package, version 4.4.3. The application source has no direct Zod schema imports
or Zod 3-only APIs to migrate. The installed AI SDK packages accept
`^3.25.76 || ^4.1.8`, which includes 4.6.7. No schemas, validation behavior,
form components, or business logic were rewritten. If introducing a future
Zod 3 consumer, use the actual
[Zod migration guide](https://zod.dev/v4/changelog); error maps, issue shapes,
defaults/coercion, and other major-version changes must not be assumed compatible.

Next.js accepts the existing React 19.2.4 pair and requires Node >=20.9.0.
Auth.js v4.24.15 accepts Next.js 16 and React 19, so migrating to Auth.js v5
is unnecessary. The AI SDK's and form resolver's existing peer requirements
remain satisfied. All strict npm resolution checks completed without peer
conflicts; `npm ls --all` also exited successfully after installation.

The [Next.js 16.4 release notes](https://nextjs.org/blog/next-16-4) describe
an opt-in caching model for existing applications; this project does not enable
the new flags. No caching migration or React update was applied. Matching
Next.js/eslint-config-next versions were selected.
[16.4.3 patch notes](https://github.com/vercel/next.js/releases/tag/v16.4.3)
were also reviewed.

The [Auth.js v4.24.15 security release](https://github.com/nextauthjs/next-auth/releases/tag/next-auth%404.24.15)
changes malformed Bearer handling, provider binding of OAuth check cookies,
email normalization, and configured NEXTAUTH_URL precedence. This application
uses the credentials provider. OAuth/email-provider behavior was not claimed
as tested. In-flight OAuth attempts can fail once after an upgrade according
to the release notes; users retry rather than bypassing checks. The release
also moves its uuid dependency to a CommonJS-compatible 11.x range; the app
does not import uuid directly. Configured origin, successful credentials,
rejection behavior, JWT/session callbacks, and malformed-token handling were
verified against the real updated NextAuth runtime.

The install also repaired pre-existing manifest/lock drift for declared
autoprefixer/postcss development dependencies. No new top-level dependency
was introduced. Normal dependency resolution updated the required Next.js
runtime/native packages and compatible transitive dependencies. Exact changes
and peer metadata are in [security-upgrade-evidence.json](security-upgrade-evidence.json).

## Commands used

From `agent-platform-ui-main/agent-platform-ui-main`:

```powershell
npm install --dry-run --ignore-scripts --strict-peer-deps --save-exact next@16.4.3 next-auth@4.24.15 zod@4.6.7 eslint-config-next@16.4.3 --no-audit --no-fund
npm install --save-exact --strict-peer-deps next@16.4.3 next-auth@4.24.15 zod@4.6.7 --no-audit --no-fund
npm install --save-dev --save-exact --strict-peer-deps eslint-config-next@16.4.3 --no-audit --no-fund
npm update source-map-js --dry-run --ignore-scripts --strict-peer-deps --no-audit --no-fund
npm update source-map-js --strict-peer-deps --no-audit --no-fund
```

For a fresh approved checkout of the resulting lockfile, prefer:

```powershell
npm ci --include=dev --strict-peer-deps --no-audit --no-fund
```

The `npm ci` command was verified with `--dry-run --ignore-scripts`; a second
clean install was not performed. Package installation itself completed with
strict peers and normal package lifecycle behavior. The manifest and lock root
dependency maps now agree. The historical CI/Docker commands still use legacy
install/lock-regeneration behavior; changing those paths and proving Linux
image builds is a separate deployment-readiness item, not evidence from this
Windows dependency verification.

## Executed checks

| Check | Result |
|---|---|
| Pre-install dry-run, scripts disabled and strict peers | PASS |
| Targeted installs and source-map-js patch | PASS, no peer overrides |
| Post-install full dependency tree | PASS, `npm ls --all` exit 0 |
| Final lockfile strict `npm ci` dry run | PASS, up to date |
| Frontend regression suite | PASS, 52 tests / 11 files |
| ESLint | PASS |
| TypeScript `tsc --noEmit` | PASS |
| Next.js production build | PASS on the upgraded packages |
| Backend regression suite | PASS, 1,157 tests |
| Built-app authentication integration | PASS, 10 checks with isolated local backend |
| Real OCI/Docker/Linux build and production credentials | NOT RUN |

The repeatable authentication command is `npm run test:auth`, after `npm run
build`. It starts the actual built Next.js application and a temporary local
HTTP backend fixture, and shuts both down. It verifies provider discovery,
anonymous sessions, missing CSRF rejection, bad credentials, accepted login,
JWT/session propagation, authenticated profile forwarding, tampered and expired
sessions, malformed Bearer tokens, and signout. The backend fixture is explicit:
this does not claim a real PostgreSQL login or production identity-provider test.
No real accounts, provider requests, or customer data were used.

## Advisory outcome and remaining compatibility limits

The initial production npm audit had 2 critical, 5 high, 2 moderate, and 4 low
package records. The final production audit has **0 critical, 0 high,
0 moderate, and 4 low** records. npm audit still exits 1 because those low
AI SDK records remain. They were not suppressed or removed by broad updates.
See [npm-audit-production-after.json](npm-audit-production-after.json).
This audit covers production npm dependencies, not the Python graph or every
development dependency.

Local runtime verification used Node **24.15.0** and npm **11.14.1** on Windows
x64. A pre-existing engine mismatch remains: the workflow pins Node 20.18.0,
while Vite/rolldown and an eslint-visitor-keys dependency already required
20.19.0 or a supported newer major before these upgrades. These requirements
were not introduced by this change. The only locked Node-24-incompatible
optional binary found is sharp's **Windows ia32** package, which is not selected
on this x64 host. Linux native binaries and musl behavior need real Docker CI.

Do not equate local success with validation on pinned CI Node 20.18.0. Align
the CI/runtime version in a separately verified change; Node 24.15.0 is the
runtime actually exercised here, not a claim about the newest secure release.
No runtime-major or Docker-base-image change was silently bundled into these
dependency updates.

Operational OCI blockers and unsupported traffic rollback remain as documented
in the [production report](production-readiness-report.md). This dependency
repair does not authorize a push, merge, deployment, or service restart.

## Files changed in this follow-up

* Frontend `package.json` / `package-lock.json`: targeted pins, transitive patch,
  reconciled lockfile, and repeatable authentication verification command.
* Frontend `scripts/verify-auth.mjs`: built-app authentication regression harness.
* `docs/security-upgrade-evidence.json`: before/after versions and peer metadata.
* `docs/npm-audit-production-after.json`: actual final audit result.
* This report and links in the production report/runbook: distinguish the new
  verified dependency state from the earlier historical advisory snapshot.

The checkpoint supports review and recovery without deleting team work. Inspect
`git diff codex/security-upgrades-baseline-20261102` to review changes. To undo
an upgrade later, prepare a reviewed inverse change from that checkpoint and
reinstall its lockfile; do not use `git reset --hard` or discard unrelated work.
