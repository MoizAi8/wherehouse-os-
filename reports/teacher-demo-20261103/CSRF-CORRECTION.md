# First-visit protected-login correction — tested locally, not deployed

Public demo, Gemini and trusted IP HTTPS are live on 78b98ea/run 80. Browser
verification found a separate first-visit private sign-in failure.

Opening `/dashboard` anonymously starts concurrent NextAuth session reads and
provider discovery. Installed NextAuth 4.24.15 initializes CSRF and callback-url
cookies on anonymous reads. A late response can overwrite the cookie matching
the already-rendered form. Live diagnostics confirmed
`csrf_form_matches_cookie=false`, followed by a 302 back to sign-in. CSRF
protection correctly blocks credential verification. Fresh direct sign-in works.

The installed `core/init.js` and official
[REST contract](https://next-auth.js.org/getting-started/rest-api) were reviewed.
The existing handler still processes every request. Only GET session/providers
responses are prevented from initializing form-specific CSRF/callback cookies.
Explicit csrf/signin/signout endpoints retain their behavior. Session-cookie
renewal/deletion and all POST/CSRF validation remain unchanged.

There are no backend, database, AI, infrastructure, secret or dependency changes.

Verification:

- 66 frontend tests, TypeScript, ESLint and production build passed.
- 19 checks against built NextAuth routes passed, including late anonymous
  responses applied after form rendering, correct callback, missing/mismatched
  CSRF rejection, credential checks, session renewal, expiry/tampering,
  protected forwarding and logout.
- Three actual Edge first-visit protected-page sign-ins passed against the
  built app and isolated auth fixture. Form/cookie pairing is checked before
  each submission. These are additional regressions, not AI inference claims.

Run 80 consumed the authorized deployment. This correction needs a renewed main
push and exactly one further OCI deployment, conditional on CI/image builds.
Then repeat real protected-page entry and public demo/Gemini/TLS verification.
