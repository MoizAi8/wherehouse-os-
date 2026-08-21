import { NextRequest } from "next/server"

import { backendUrl } from "@/lib/backend"

export async function POST(req: NextRequest) {
  const base = backendUrl()
  if (!base) {
    return new Response(
      JSON.stringify({ error: "Backend not configured: BACKEND_URL is unset" }),
      { status: 503 }
    )
  }

  try {
    const body = (await req.json()) as { name?: string; email?: string; password?: string }

    const backendRes = await fetch(`${base}/api/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(15000),
    })

    const data = await backendRes.json().catch(() => null)
    const status = backendRes.ok ? 200 : backendRes.status
    const error = !backendRes.ok && typeof data?.detail === "string" ? data.detail : undefined
    return new Response(JSON.stringify({ ok: backendRes.ok, user: data, error }), {
      status,
      headers: { "Content-Type": "application/json" },
    })
  } catch (err) {
    const errMsg = err instanceof Error ? err.message : "Registration service unavailable"
    return new Response(JSON.stringify({ ok: false, error: errMsg }), { status: 500 })
  }
}