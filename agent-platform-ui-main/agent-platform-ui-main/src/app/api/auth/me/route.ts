import { backendUrl, getAuthHeaders } from "@/lib/backend"

export async function GET() {
  const base = backendUrl()
  if (!base) {
    return new Response(
      JSON.stringify({ error: "Backend not configured: BACKEND_URL is unset" }),
      { status: 503 }
    )
  }

  try {
    const authHeaders = await getAuthHeaders()

    const backendRes = await fetch(`${base}/api/auth/me`, {
      headers: { ...authHeaders },
      signal: AbortSignal.timeout(15000),
    })

    if (!backendRes.ok) {
      const text = await backendRes.text().catch(() => "")
      return new Response(
        JSON.stringify({ error: `Backend /api/auth/me failed (${backendRes.status}): ${text}` }),
        { status: backendRes.status }
      )
    }

    const data = await backendRes.json()
    return new Response(JSON.stringify(data), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    })
  } catch (err) {
    const errMsg = err instanceof Error ? err.message : "Profile service unavailable"
    return new Response(JSON.stringify({ error: errMsg }), { status: 500 })
  }
}