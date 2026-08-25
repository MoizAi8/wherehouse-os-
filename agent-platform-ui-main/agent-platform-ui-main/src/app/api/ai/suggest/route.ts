import { NextRequest } from "next/server"

import { backendUrl, getAuthHeaders } from "@/lib/backend"

export async function POST(_req: NextRequest) {
  const base = backendUrl()
  if (!base) {
    return Response.json({ error: "Backend not configured: BACKEND_URL is unset" }, { status: 503 })
  }

  try {
    const authHeaders = await getAuthHeaders()
    const backendRes = await fetch(`${base}/api/chat/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders },
      body: JSON.stringify({ message: "Give me optimization suggestions and recommendations." }),
      signal: AbortSignal.timeout(10000),
    })
    if (!backendRes.ok) {
      return Response.json({ error: "Suggestion generation failed" }, { status: 500 })
    }
    const data = await backendRes.json()
    return Response.json({ suggestions: [{ agent: "AI", action: data.reply, priority: "medium" }] })
  } catch {
    return Response.json({ error: "Suggestion generation failed" }, { status: 500 })
  }
}