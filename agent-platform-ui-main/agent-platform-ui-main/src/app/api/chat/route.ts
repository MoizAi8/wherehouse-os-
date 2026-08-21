import { NextRequest } from "next/server"

import { backendUrl, getAuthHeaders } from "@/lib/backend"

export async function POST(req: NextRequest) {
  const base = backendUrl()
  if (!base) {
    return new Response(
      JSON.stringify({ error: "Backend not configured: BACKEND_URL is unset" }),
      { status: 503 }
    )
  }

  try {
    const body = (await req.json()) as { message?: string; sessionId?: string }

    const message = body.message?.trim()
    if (!message) {
      return new Response(JSON.stringify({ error: "No message provided" }), { status: 400 })
    }

    const authHeaders = await getAuthHeaders()

    const backendRes = await fetch(`${base}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders },
      body: JSON.stringify({ message, session_id: body.sessionId || null }),
      signal: AbortSignal.timeout(60000),
    })

    if (!backendRes.ok) {
      const text = await backendRes.text().catch(() => "")
      return new Response(
        JSON.stringify({ error: `Backend chat failed (${backendRes.status}): ${text}` }),
        { status: backendRes.status }
      )
    }

    const data = await backendRes.json()
    return new Response(JSON.stringify(data), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    })
  } catch (err) {
    const errMsg = err instanceof Error ? err.message : "AI service unavailable"
    return new Response(JSON.stringify({ error: errMsg }), { status: 500 })
  }
}

export async function GET(req: NextRequest) {
  const base = backendUrl()
  if (!base) {
    return new Response(
      JSON.stringify({ error: "Backend not configured: BACKEND_URL is unset" }),
      { status: 503 }
    )
  }

  try {
    const sessionId = req.nextUrl.searchParams.get("sessionId")
    if (!sessionId) {
      return new Response(JSON.stringify({ error: "sessionId is required" }), { status: 400 })
    }

    const authHeaders = await getAuthHeaders()

    const backendRes = await fetch(
      `${base}/api/chat/history?session_id=${encodeURIComponent(sessionId)}`,
      { headers: { ...authHeaders }, signal: AbortSignal.timeout(15000) }
    )

    if (!backendRes.ok) {
      const text = await backendRes.text().catch(() => "")
      return new Response(
        JSON.stringify({ error: `Backend history failed (${backendRes.status}): ${text}` }),
        { status: backendRes.status }
      )
    }

    const data = await backendRes.json()
    return new Response(JSON.stringify(data), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    })
  } catch (err) {
    const errMsg = err instanceof Error ? err.message : "AI service unavailable"
    return new Response(JSON.stringify({ error: errMsg }), { status: 500 })
  }
}