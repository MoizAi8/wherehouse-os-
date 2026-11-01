import { NextRequest } from "next/server"
import { backendUrl, getAuthHeaders } from "@/lib/backend"

export async function POST(req: NextRequest) {
  const base = backendUrl()
  if (!base) return Response.json({ error: "Backend unavailable" }, { status: 503 })

  try {
    const authHeaders = await getAuthHeaders()
    if (!authHeaders.Authorization) {
      return Response.json({ error: "Not authenticated" }, { status: 401 })
    }
    const { messages } = await req.json()
    if (!Array.isArray(messages) || messages.length > 100) {
      return Response.json({ error: "Invalid messages" }, { status: 400 })
    }
    const lastUserMsg = [...messages].reverse().find(m => m?.role === "user")
    if (typeof lastUserMsg?.content !== "string" || !lastUserMsg.content.trim() || lastUserMsg.content.length > 5000) {
      return Response.json({ error: "Invalid user message" }, { status: 400 })
    }
    const backendRes = await fetch(`${base}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders },
      body: JSON.stringify({ message: lastUserMsg.content }),
      signal: AbortSignal.timeout(60000),
    })
    if (!backendRes.ok) {
      return Response.json({ error: "Backend chat unavailable" }, { status: backendRes.status })
    }
    const data = await backendRes.json()
    if (typeof data.reply !== "string") {
      return Response.json({ error: "Invalid backend response" }, { status: 502 })
    }
    return new Response(data.reply, {
      headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-cache" },
    })
  } catch {
    return Response.json({ error: "Chat service unavailable" }, { status: 503 })
  }
}
