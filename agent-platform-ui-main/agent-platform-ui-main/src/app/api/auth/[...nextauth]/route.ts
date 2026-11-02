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
  if (!cookies.some(cookie => formCookie.test(cookie))) return response
  const headers = new Headers(response.headers)
  headers.delete("set-cookie")
  for (const cookie of cookies) if (!formCookie.test(cookie)) headers.append("set-cookie", cookie)
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers })
}

export { handler as POST }
