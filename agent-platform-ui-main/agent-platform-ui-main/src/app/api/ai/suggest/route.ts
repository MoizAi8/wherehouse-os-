import { NextRequest } from "next/server"

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()
    const backendRes = await fetch(`${BACKEND_URL}/api/chat/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
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
