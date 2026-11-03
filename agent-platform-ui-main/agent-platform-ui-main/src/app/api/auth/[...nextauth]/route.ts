import { backendUrl } from "@/lib/backend"
import { guestCookieName } from "@/lib/demo-guest"
import NextAuth from "next-auth"
import type { NextRequest } from "next/server"
import { authOptions } from "@/lib/auth"

const handler = NextAuth(authOptions)

export async function GET(request: NextRequest, context: { params: Promise<{ nextauth: string[] }> }) {
  const response: Response = await handler(request, context)
  const action = (await context.params).nextauth[0]
  if (action !== "session" && action !== "providers") return response

  // Concurrent anonymous reads must not overwrite a rendered sign-in form's
  // CSRF/callback cookies. Explicit csrf/signin/signout endpoints own those.
  // Preserve session renewal/deletion cookies and all POST validation unchanged.
  const formCookie = /^(?:__Host-|__Secure-)?next-auth\.(?:csrf-token|callback-url)=/
  const cookies = response.headers.getSetCookie()
  const headers = new Headers(response.headers)
  headers.delete("set-cookie")
  for (const cookie of cookies) if (!formCookie.test(cookie)) headers.append("set-cookie", cookie)
  if (action === "session" && response.ok) {
    const current = await response.clone().json()
    if (!current.accessToken && backendUrl()) {
      try {
        const guest = await fetch(`${backendUrl()}/api/demo/guest/session`, {
          method: "POST", cache: "no-store", signal: AbortSignal.timeout(2000),
        })
        if (guest.ok) {
          const session = await guest.json()
          const secure = guestCookieName().startsWith("__Host-") ? "; Secure" : ""
          headers.append("Set-Cookie", `${guestCookieName()}=${encodeURIComponent(session.accessToken)}; Path=/; HttpOnly; SameSite=Lax; Max-Age=3600${secure}`)
          headers.set("Cache-Control", "no-store")
          return Response.json(session, { headers })
        }
      } catch { /* Guest mode fails closed; original authentication remains active. */ }
    }
  }
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers })
}

export { handler as POST }
