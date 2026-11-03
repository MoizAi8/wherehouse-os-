import { guestFetch } from "@/lib/demo-guest"
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
    const body = (await req.json()) as { message?: string; sessionId?: string; confirmationToken?: string; history?: { role: string; content: string }[] }

    const message = body.message?.trim()
    if (!message) {
      return new Response(JSON.stringify({ error: "No message provided" }), { status: 400 })
    }

    const authHeaders = await getAuthHeaders()
    if (!authHeaders.Authorization) {
      return guestFetch("chat", { method: "POST", body: JSON.stringify({ message, history: body.history || [] }) })
    }

    const backendRes = await fetch(`${base}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders },
      body: JSON.stringify({ message, session_id: body.sessionId || null, confirmation_token: body.confirmationToken || null }),
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
    if (!authHeaders.Authorization) {
      return guestFetch("history")
    }

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

export async function DELETE(req: NextRequest) {
  const base = backendUrl()
  if (!base) return Response.json({ error: "Chat backend unavailable" }, { status: 503 })
  if (req.headers.get("sec-fetch-site") === "cross-site") {
    return Response.json({ error: "Cross-site request rejected" }, { status: 403 })
  }

  const id = req.nextUrl.searchParams.get("sessionId")
  if (!id || id.length > 64) return Response.json({ error: "Invalid conversation ID" }, { status: 400 })

  try {
    const headers = await getAuthHeaders()
    if (!headers.Authorization) return Response.json({ error: "Sign in to delete saved history" }, { status: 401 })
    const result = await fetch(`${base}/api/chat/history?session_id=${encodeURIComponent(id)}`, {
      method: "DELETE", headers, signal: AbortSignal.timeout(15000),
    })
    return result.ok ? new Response(null, { status: 204 })
      : Response.json({ error: "Could not delete conversation" }, { status: result.status })
  } catch {
    return Response.json({ error: "Chat backend unavailable" }, { status: 503 })
  }
}
