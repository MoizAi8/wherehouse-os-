# Production authentication

Credentials are submitted to NextAuth's credentials callback with its CSRF token.
The Next.js server calls FastAPI `/api/auth/login` using the internal
`BACKEND_URL`. FastAPI signs a one-hour access JWT. NextAuth stores that JWT in
its encrypted, HTTP-only session cookie and exposes the access token through
the authenticated session endpoint for browser API requests.

Browser calls through `src/lib/api.ts` obtain that session and send a Bearer
token. Caddy forwards `/api/v1/*` to FastAPI without changing the path or
Authorization header. A NextAuth cookie alone does not authenticate FastAPI.
FastAPI verifies the signature, expiration, active user and required role.

Chat uses the frontend `/api/chat` handler. Its server-side session bridge
forwards the same backend Bearer token. History must use
`GET /api/chat?sessionId=...`; the frontend translates the query to FastAPI's
`/api/chat/history?session_id=...`. Calling the backend history URL directly
with only a browser cookie skips this bridge and is correctly rejected.

The connectivity indicator uses the public `/health` endpoint. It reports
backend connectivity, not whether an external LLM provider is configured.
An OpenAI key is not needed to authenticate or use deterministic warehouse
chat operations.

## Session expiration

Previously, NextAuth kept its session for 30 days while the embedded FastAPI
token expired after one hour. No production renewal existed, leaving the UI
apparently logged in while protected APIs correctly rejected the expired JWT.

NextAuth now caps its cookie lifetime at one hour and checks the embedded JWT's
absolute expiration on each session read, including cookies from older releases.
Expired/malformed backend tokens are withheld and marked `SessionExpired`.
The client checks its session every minute and on focus; protected pages return
to the normal sign-in page when either the backend token or browser cookie
expires. This opens the normal sign-in form directly, without first posting
sign-out: simultaneous first-visit CSRF-cookie initialization can otherwise
send an anonymous visitor to a sign-out confirmation page. Expired backend
tokens are already withheld, and successful credential verification replaces
the session cookie. A 401 also requires sign-in. Chat does not retry unauthorized writes.
Valid legacy cookies continue to work until their actual backend expiration.

This deliberately requires a new login after one hour. Extending the backend
JWT lifetime would widen credential exposure. Automatic refresh would need to
retain rotating refresh tokens securely and coordinate concurrent requests,
tabs and cookie persistence; it is not introduced by this urgent repair.
No refresh token is exposed in the NextAuth browser session, no shared account
substitution occurs in production, and backend authorization remains mandatory.

## Regression checks

Run frontend lint, types, Vitest, production build, then `npm run test:auth`.
The built-route fixture checks real NextAuth CSRF/sign-in/session/sign-out,
cookie-to-Bearer bridging, chat/history, tampering, expired cookies, expired
backend JWTs inside valid cookies, and valid legacy cookies. Backend tests
retain signature, role, ownership and unauthenticated access checks.

After an approved deployment, verify with an actual account through public
HTTPS: NextAuth login, profile, chat, history, Orders, Dashboard KPIs and Agents.
Verify anonymous and expired-token calls still return 401. Never record live
passwords, JWTs, cookies or signing secrets in reports or test logs.
