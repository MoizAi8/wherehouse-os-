import { NextRequest } from "next/server"

import { backendUrl, getAuthHeaders } from "@/lib/backend"

export async function POST(req: NextRequest) {
  const base = backendUrl()
  if (!base) {
    return Response.json({ error: "Backend not configured: BACKEND_URL is unset" }, { status: 503 })
  }

  try {
    const authHeaders = await getAuthHeaders()
    const backendRes = await fetch(`${base}/api/chat/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders },
      body: JSON.stringify({ message: "Give me current insights and recommendations for the warehouse system." }),
      signal: AbortSignal.timeout(10000),
    })
    if (!backendRes.ok) {
      return Response.json({ error: "Insight generation failed" }, { status: 500 })
    }
    const data = await backendRes.json()
    return Response.json({ insights: [{ metric: "AI Insight", insight: data.reply, severity: "info" }] })
  } catch {
    return Response.json({ error: "Insight generation failed" }, { status: 500 })
  }
}