// Exercise the built NextAuth routes with an isolated local backend fixture.
// No production services, credentials, or provider calls are used.
import assert from "node:assert/strict"
import { spawn } from "node:child_process"
import { createServer } from "node:http"
import { createWriteStream } from "node:fs"
import { createRequire } from "node:module"
import { setTimeout as delay } from "node:timers/promises"

const require = createRequire(import.meta.url)
const { encode, getToken } = require("next-auth/jwt")
const secret = "isolated-auth-regression-secret-not-for-production"
const backendToken = exp => `fixture.${Buffer.from(JSON.stringify({ exp })).toString("base64url")}.fixture-signature`
const accessToken = backendToken(Math.floor(Date.now() / 1000) + 3600)
let loginCalls = 0
const checks = []
const fixture = createServer(async (req, res) => {
  res.setHeader("Content-Type", "application/json")
  if (req.url === "/api/auth/login" && req.method === "POST") {
    loginCalls++
    let body = ""
    for await (const chunk of req) body += chunk
    const credentials = JSON.parse(body)
    if (credentials.email !== "operator@example.test" || credentials.password !== "fixture-password") {
      res.writeHead(401).end(JSON.stringify({ detail: "Invalid credentials" }))
      return
    }
    res.end(JSON.stringify({ access_token: accessToken, user: {
      id: "fixture-user", name: "Test Operator", email: "operator@example.test", role: "OPERATOR",
    } }))
    return
  }
  if (req.url === "/api/auth/me") {
    if (req.headers.authorization !== `Bearer ${accessToken}`) {
      res.writeHead(401).end(JSON.stringify({ detail: "Not authenticated" }))
      return
    }
    res.end(JSON.stringify({ id: "fixture-user", email: "operator@example.test", role: "OPERATOR" }))
    return
  }
  if (req.url === "/api/chat" || req.url?.startsWith("/api/chat/history?")) {
    if (req.headers.authorization !== `Bearer ${accessToken}`) {
      res.writeHead(401).end(JSON.stringify({ detail: "Not authenticated" }))
      return
    }
    res.end(JSON.stringify(req.method === "POST" ? { reply: "Authenticated warehouse reply" } : { messages: [] }))
    return
  }
  res.writeHead(404).end("{}")
})
await new Promise(resolve => fixture.listen(0, "127.0.0.1", resolve))
const portProbe = createServer()
await new Promise(resolve => portProbe.listen(0, "127.0.0.1", resolve))
const port = portProbe.address().port
await new Promise(resolve => portProbe.close(resolve))
const origin = `http://127.0.0.1:${port}`
const output = createWriteStream("verification-auth-server.log")
const app = spawn(process.execPath, [require.resolve("next/dist/bin/next"), "start", "-H", "127.0.0.1", "-p", String(port)], {
  windowsHide: true,
  env: { ...process.env, NODE_ENV: "production", NEXTAUTH_URL: origin, NEXTAUTH_SECRET: secret,
    BACKEND_URL: `http://127.0.0.1:${fixture.address().port}`, NEXT_TELEMETRY_DISABLED: "1" },
  stdio: ["ignore", "pipe", "pipe"],
})
app.stdout.pipe(output)
app.stderr.pipe(output)

async function request(path, jar = new Map(), options = {}) {
  const response = await fetch(origin + path, {
    ...options, redirect: "manual", signal: AbortSignal.timeout(10000),
    headers: { cookie: [...jar].map(([key, value]) => `${key}=${value}`).join("; "), ...options.headers },
  })
  for (const cookie of response.headers.getSetCookie()) {
    const pair = cookie.split(";")[0]
    const split = pair.indexOf("=")
    jar.set(pair.slice(0, split), pair.slice(split + 1))
  }
  return response
}
async function signIn(password) {
  const jar = new Map()
  const csrf = await (await request("/api/auth/csrf", jar)).json()
  assert.equal(typeof csrf.csrfToken, "string")
  const response = await request("/api/auth/callback/credentials", jar, {
    method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ csrfToken: csrf.csrfToken, email: "operator@example.test",
      password, callbackUrl: origin + "/dashboard", json: "true" }),
  })
  return { jar, result: await response.json() }
}

try {
  let started = false
  for (let attempt = 0; attempt < 60; attempt++) {
    if (app.exitCode !== null) throw new Error("Next.js exited; inspect verification-auth-server.log")
    try {
      if ((await request("/api/auth/providers")).status === 200) { started = true; break }
    } catch { /* Bounded startup retry for this isolated child. */ }
    await delay(500)
  }
  assert.ok(started, "Built application did not start")
  const providers = await (await request("/api/auth/providers")).json()
  assert.equal(providers.credentials.type, "credentials")
  checks.push("credentials provider discovery")

  const firstVisitSignIn = await request("/api/auth/signin?callbackUrl=%2Fdashboard")
  assert.equal(firstVisitSignIn.status, 200)
  assert.match(await firstVisitSignIn.text(), /Sign in with Credentials/)
  checks.push("first-visit sign-in form is reachable without a sign-out POST")

  // Reproduce late anonymous responses arriving after the form rendered.
  const lateReads = await Promise.all(["session", "session", "providers"].map(action =>
    request(`/api/auth/${action}`)))
  for (const response of lateReads) {
    assert.ok(!response.headers.getSetCookie().some(cookie => /next-auth\.(csrf-token|callback-url)=/.test(cookie)))
  }
  checks.push("anonymous session/provider reads do not initialize form cookies")
  const firstVisitJar = new Map()
  const form = await request("/api/auth/signin?callbackUrl=%2Fdashboard", firstVisitJar)
  const html = await form.text()
  const formToken = html.match(/name="csrfToken"[^>]*value="([^"]+)"/)?.[1]
  assert.ok(formToken)
  for (const response of lateReads) {
    for (const cookie of response.headers.getSetCookie()) {
      const pair = cookie.split(";")[0]; const split = pair.indexOf("=")
      firstVisitJar.set(pair.slice(0, split), pair.slice(split + 1))
    }
  }
  const firstVisit = await request("/api/auth/callback/credentials", firstVisitJar, {
    method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ csrfToken: formToken, email: "operator@example.test",
      password: "fixture-password", json: "true" }),
  })
  assert.equal((await firstVisit.json()).url, origin + "/dashboard")
  assert.equal((await (await request("/api/auth/session", firstVisitJar)).json()).accessToken, accessToken)
  checks.push("late anonymous responses preserve first-visit form CSRF and dashboard callback")

  const anonymous = await (await request("/api/auth/session")).json()
  assert.equal(anonymous.accessToken, undefined)
  checks.push("anonymous session has no backend token")

  const beforeCsrf = loginCalls
  await request("/api/auth/callback/credentials", new Map(), {
    method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ email: "operator@example.test", password: "fixture-password", json: "true" }),
  })
  assert.equal(loginCalls, beforeCsrf)
  checks.push("missing CSRF cannot reach credential verification")

  const mismatchJar = new Map()
  await request("/api/auth/csrf", mismatchJar)
  await request("/api/auth/callback/credentials", mismatchJar, {
    method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ csrfToken: "mismatched-fixture-token", email: "operator@example.test",
      password: "fixture-password", json: "true" }),
  })
  assert.equal(loginCalls, beforeCsrf)
  checks.push("mismatched CSRF remains rejected before credential verification")

  const rejected = await signIn("wrong-password")
  assert.match(rejected.result.url, /CredentialsSignin/)
  assert.equal((await (await request("/api/auth/session", rejected.jar)).json()).accessToken, undefined)
  checks.push("invalid credentials create no session")

  const accepted = await signIn("fixture-password")
  assert.equal(accepted.result.url, origin + "/dashboard")
  const renewed = await request("/api/auth/session", accepted.jar)
  assert.ok(renewed.headers.getSetCookie().some(cookie => cookie.includes("next-auth.session-token=")))
  checks.push("session reads preserve authenticated session-cookie renewal")
  const session = await renewed.json()
  assert.equal(session.user.email, "operator@example.test")
  assert.equal(session.user.id, "fixture-user")
  assert.equal(session.accessToken, accessToken)
  checks.push("valid credentials persist JWT and session callbacks")

  const profile = await request("/api/auth/me", accepted.jar)
  assert.equal(profile.status, 200)
  assert.equal((await profile.json()).id, "fixture-user")
  checks.push("authenticated profile forwards backend bearer token")

  assert.equal((await request("/api/chat?sessionId=fixture", accepted.jar)).status, 200)
  assert.equal((await request("/api/chat", accepted.jar, { method: "POST",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: "Show orders" }) })).status, 200)
  checks.push("cookie-authenticated chat and history forward backend bearer token")
  assert.equal((await request("/api/chat?sessionId=fixture")).status, 401)
  assert.equal((await request("/api/chat", new Map(), { method: "POST",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: "Show orders" }) })).status, 401)
  checks.push("anonymous chat and history fail closed")

  const cookieName = [...accepted.jar.keys()].find(name => name.includes("session-token"))
  assert.ok(cookieName)
  const tampered = new Map(accepted.jar)
  tampered.set(cookieName, "tampered." + tampered.get(cookieName))
  assert.equal((await (await request("/api/auth/session", tampered)).json()).accessToken, undefined)
  checks.push("tampered session rejected")

  const expired = await encode({ secret, token: { sub: "fixture-user", accessToken }, maxAge: -3600 })
  const expiredJar = new Map([[cookieName, expired]])
  assert.equal((await (await request("/api/auth/session", expiredJar)).json()).accessToken, undefined)
  checks.push("expired session rejected")

  // Real defect: a valid, long-lived NextAuth cookie carried an expired
  // backend JWT. Existing production cookies have no accessTokenExpires.
  const oldBackend = await encode({ secret, token: { sub: "fixture-user",
    accessToken: backendToken(Math.floor(Date.now() / 1000) - 60) }, maxAge: 3600 })
  const staleJar = new Map([[cookieName, oldBackend]])
  const staleSession = await (await request("/api/auth/session", staleJar)).json()
  assert.equal(staleSession.accessToken, undefined)
  assert.equal(staleSession.error, "SessionExpired")
  assert.equal((await request("/api/auth/me", staleJar)).status, 401)
  assert.equal((await request("/api/chat?sessionId=fixture", staleJar)).status, 401)
  checks.push("legacy NextAuth cookie cannot forward an expired backend JWT")

  const legacy = await encode({ secret, token: { sub: "fixture-user", accessToken }, maxAge: 3600 })
  assert.equal((await request("/api/chat?sessionId=fixture", new Map([[cookieName, legacy]]))).status, 200)
  checks.push("unexpired legacy cookie remains compatible")

  const malformed = await getToken({ secret, req: { cookies: {}, headers: { authorization: "Bearer %E0%A4%A" } } })
  assert.equal(malformed, null)
  checks.push("malformed Bearer token returns null without throwing")

  const csrf = await (await request("/api/auth/csrf", accepted.jar)).json()
  await request("/api/auth/signout", accepted.jar, { method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ csrfToken: csrf.csrfToken, callbackUrl: origin, json: "true" }) })
  assert.equal((await (await request("/api/auth/session", accepted.jar)).json()).accessToken, undefined)
  checks.push("signout clears the session")
  if (process.env.AUTH_BROWSER_QA === "true") {
    // Optional local tooling; no application dependency or CI browser install.
    const { chromium } = require("../../../.tools/qa-browser/node_modules/playwright")
    const browser = await chromium.launch({ channel: "msedge", headless: true })
    try {
      for (let attempt = 0; attempt < 3; attempt++) {
        const context = await browser.newContext()
        const page = await context.newPage()
        try {
          await page.goto(origin + "/dashboard", { waitUntil: "domcontentloaded" })
          await page.locator('input[name="email"]').waitFor()
          const formToken = await page.locator('input[name="csrfToken"]').inputValue()
          const cookie = (await context.cookies()).find(value => value.name.includes("csrf-token"))
          assert.ok(cookie)
          assert.equal(decodeURIComponent(cookie.value).split("|")[0], formToken)
          await page.locator('input[name="email"]').fill("operator@example.test")
          await page.locator('input[name="password"]').fill("fixture-password")
          await page.locator('button[type="submit"]').click()
          await page.waitForURL(origin + "/dashboard", { waitUntil: "domcontentloaded" })
          const response = await context.request.get(origin + "/api/auth/session")
          assert.equal((await response.json()).accessToken, accessToken)
          checks.push(`real browser first-visit protected-page sign-in ${attempt + 1}`)
        } finally { await context.close() }
      }
    } finally { await browser.close() }
  }
  console.log(JSON.stringify({ status: "passed", checks }, null, 2))
} finally {
  app.kill()
  await new Promise(resolve => { if (app.exitCode !== null) resolve(); else app.once("exit", resolve) })
  await new Promise(resolve => fixture.close(resolve))
  output.end()
}
