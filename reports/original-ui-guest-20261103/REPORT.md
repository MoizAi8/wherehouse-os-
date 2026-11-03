# Original Warehouse OS UI with restricted public guests

**Prepared and tested locally; not pushed or deployed. Current production remains b726603/run 82 and still uses the unwanted separate public demo landing.**

## What changes

Root now checks DEMO_GUEST_ENABLED at runtime and redirects directly to /dashboard. /demo also redirects to /dashboard; its separate interface is removed. All 16 original dashboard/layout/sidebar/style source files checked against b726603 are unchanged. Original Chat gets bounded per-request history without changing its markup or styles. The topbar keeps its original design and shows Demo Guest instead of Admin, with an owner sign-in item in the existing dropdown.

NextAuth's session response can issue a separate restricted guest session when no valid owner token exists. It uses a separate HTTP-only, SameSite=Lax, host-only cookie (Secure and __Host- prefixed on HTTPS). Its signed token uses a distinct demo_guest type and isolated-demo audience. Production authentication rejects it before looking up a user. Valid owner sessions always take precedence. Normal credentials, CSRF validation, expiry handling and session renewal stay intact.

Guest requests use an explicit allowlist of original UI response shapes built exclusively from the separately allocated read-only sample SQLite database. No production database access is imported by the guest router. Orders, shipments, analytics, centers, agent status and safe settings are sample-only. Integrations expose no private connections. Writes and privileged routes return 403 rather than fake success. Team and other original static views remain as originally implemented. Workflows remain the original labelled simulations. Owner-to-guest identity transitions remount page/query/chat state. Guest browser preferences and chat identifiers use separate storage, so cached owner settings/history do not become guest content. Guest chat uses the existing bounded, rate-limited Gemini implementation with only read-only sample tools; guests have no shared server chat history.

DEMO_GUEST_ENABLED=true enables this indefinitely; false disables guest session issuance and revokes existing guest requests. One-hour guest tokens renew automatically while mode remains enabled; they do not impose a one-hour demo limit. Owner login remains at /api/auth/signin?callbackUrl=%2Fdashboard. No credentials are embedded or automatically submitted.

## Verification

- 1,221 backend tests passed, including 24 new guest contract/security tests.
- Backend ruff clean and mypy clean across 84 files.
- 75 frontend tests passed; ESLint, TypeScript and production build passed.
- 26 built authentication checks passed, including owner precedence while guest mode is enabled and mode-off revocation, plus three fresh-browser normal owner sign-ins.
- 25 fresh Edge browser checks passed: original dashboard entry without credentials, every sidebar page, original sample order table, read-only chat, rejected write, production token rejection, old-demo redirect, navigation history and mobile navigation.
- One real Gemini Free-tier response (19+23 → 42) passed in the original built chat interface. Because the key exists only in GitHub, this synthetic QA test used a local test-only relay to the existing public production demo endpoint. No key was retrieved. The new guest release itself has not been tested live or deployed yet.
- Both current public HTTPS addresses still pass trusted TLS and existing redirects. Caddy, hostname and IP TLS configuration are unchanged.

The first backend run hit Windows sandbox restrictions in five deployment-shell tests; the full permitted rerun passed all 1,221. An initial browser run caught a static root build, fixed by forcing runtime rendering. Test harness selectors/history navigation were corrected to match the existing DOM. Final evidence records passing checks.

## Visual review

Playwright captured the existing original production /dashboard with API reads intercepted using isolated sample DTOs, and the proposed guest dashboard at the same 1440×1000 viewport. Both screenshots were inspected: sidebar, dark theme, metrics, agent panel and original chat design match. See original-production-ui-sample-baseline.png and dashboard-desktop.png. Chat, Agents, Orders, Analytics and Integrations screenshots are included.

No exact pixel-equality claim is made. The guest identity differs intentionally. At 390px, the original fixed 240px sidebar and wide content clip the main area; that pre-existing behavior is preserved and documented in orders-mobile-original-layout.png. Desktop is the verified presentation layout. No responsive redesign was introduced.

## Proposed authorized release

After explicit user approval only: push the tested candidate to main; set repository variables DEMO_GUEST_ENABLED=true and TEACHER_DEMO_MODE=false; run normal CI and Docker image builds; perform exactly one OCI deployment only if they pass. The existing Gemini secret and limits stay unchanged. The workflow passes the new flag through the existing environment generator and API Compose setting. No migrations, database/volume changes, Caddy changes, new dependencies or paid services are involved.

Then verify the actual live root and direct-IP redirect enter the original dashboard without credentials, browse all pages, test real Gemini in original Chat, verify owner login and rejected production access, and capture live screenshots. A further deployment would need renewed authorization. No push or deployment was performed while preparing this correction.
