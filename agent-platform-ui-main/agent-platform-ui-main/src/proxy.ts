import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

const SESSION_COOKIE = "__Secure-next-auth.session-token"
const SESSION_COOKIE_DEV = "next-auth.session-token"

function hasSession(request: NextRequest): boolean {
  return request.cookies.has(SESSION_COOKIE) || request.cookies.has(SESSION_COOKIE_DEV)
}

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl
  const isAuthPage =
    pathname === "/login" ||
    pathname === "/register" ||
    pathname === "/forgot-password" ||
    pathname === "/reset-password"
  const isProtected = pathname.startsWith("/dashboard")

  if (isProtected && !hasSession(request)) {
    const loginUrl = new URL("/login", request.url)
    loginUrl.searchParams.set("callbackUrl", pathname)
    return NextResponse.redirect(loginUrl)
  }

  if (isAuthPage && hasSession(request)) {
    return NextResponse.redirect(new URL("/dashboard", request.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: ["/dashboard/:path*", "/login", "/register", "/forgot-password", "/reset-password"],
}