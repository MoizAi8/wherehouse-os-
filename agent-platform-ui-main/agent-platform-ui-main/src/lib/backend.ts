import { getServerSession } from "next-auth"

import { authOptions } from "@/lib/auth"

const DEV_BACKEND_URL = "http://localhost:8000"

/**
 * Resolve the backend API base URL.
 *
 * In production the proxy must fail closed rather than silently route to
 * localhost (which would 404/leak via Caddy) — so if BACKEND_URL is unset we
 * return "" and callers should respond 503.
 */
export function backendUrl(): string {
  const fromEnv = process.env.BACKEND_URL
  if (fromEnv) return fromEnv
  if (process.env.NODE_ENV !== "production") return DEV_BACKEND_URL
  return ""
}

/**
 * Server-side auth headers for proxied backend calls. Forwards the session's
 * JWT access token so the backend sees the authenticated user.
 */
export async function getAuthHeaders(): Promise<Record<string, string>> {
  const session = await getServerSession(authOptions)
  if (session?.accessToken) {
    return { Authorization: `Bearer ${session.accessToken}` }
  }
  return {}
}