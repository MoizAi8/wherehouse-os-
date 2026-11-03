import { cookies } from "next/headers"
import { backendUrl } from "@/lib/backend"

export function guestCookieName() {
  return process.env.NEXTAUTH_URL?.startsWith("https:") ? "__Host-warehouse-demo-guest" : "warehouse-demo-guest"
}

export async function guestModeEnabled(): Promise<boolean> {
  const base = backendUrl()
  if (!base) return false
  try {
    const res = await fetch(`${base}/api/demo/guest/status`, { cache: "no-store", signal: AbortSignal.timeout(2000) })
    return res.ok && (await res.json()).enabled === true
  } catch { return false }
}

/** Read only the separate guest cookie. Never substitute it for owner auth. */
export async function guestHeaders(): Promise<Record<string, string>> {
  const token = (await cookies()).get(guestCookieName())?.value
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function guestFetch(path: string, init?: RequestInit): Promise<Response> {
  const base = backendUrl()
  const headers = await guestHeaders()
  if (!base || !headers.Authorization) return Response.json({ error: "Not authenticated" }, { status: 401 })
  const res = await fetch(`${base}/api/demo/guest/${path}`, {
    ...init, headers: { "Content-Type": "application/json", ...headers },
    cache: "no-store", signal: AbortSignal.timeout(60000),
  })
  return new Response(res.body, { status: res.status, headers: {
    "Content-Type": "application/json", "Cache-Control": "no-store",
    ...(res.headers.has("retry-after") ? { "Retry-After": res.headers.get("retry-after")! } : {}),
  } })
}
