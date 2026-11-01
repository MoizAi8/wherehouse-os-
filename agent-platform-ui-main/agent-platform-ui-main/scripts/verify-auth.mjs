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
const accessToken = "isolated-backend-token"
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

  const rejected = await signIn("wrong-password")
  assert.match(rejected.result.url, /CredentialsSignin/)
  assert.equal((await (await request("/api/auth/session", rejected.jar)).json()).accessToken, undefined)
  checks.push("invalid credentials create no session")

  const accepted = await signIn("fixture-password")
  assert.equal(accepted.result.url, origin + "/dashboard")
  const session = await (await request("/api/auth/session", accepted.jar)).json()
  assert.equal(session.user.email, "operator@example.test")
  assert.equal(session.user.id, "fixture-user")
  assert.equal(session.accessToken, accessToken)
  checks.push("valid credentials persist JWT and session callbacks")

  const profile = await request("/api/auth/me", accepted.jar)
  assert.equal(profile.status, 200)
  assert.equal((await profile.json()).id, "fixture-user")
  checks.push("authenticated profile forwards backend bearer token")

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

  const malformed = await getToken({ secret, req: { cookies: {}, headers: { authorization: "Bearer %E0%A4%A" } } })
  assert.equal(malformed, null)
  checks.push("malformed Bearer token returns null without throwing")

  const csrf = await (await request("/api/auth/csrf", accepted.jar)).json()
  await request("/api/auth/signout", accepted.jar, { method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ csrfToken: csrf.csrfToken, callbackUrl: origin, json: "true" }) })
  assert.equal((await (await request("/api/auth/session", accepted.jar)).json()).accessToken, undefined)
  checks.push("signout clears the session")
  console.log(JSON.stringify({ status: "passed", checks }, null, 2))
} finally {
  app.kill()
  await new Promise(resolve => { if (app.exitCode !== null) resolve(); else app.once("exit", resolve) })
  await new Promise(resolve => fixture.close(resolve))
  output.end()
}
