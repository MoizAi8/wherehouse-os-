import { NextRequest } from "next/server"

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

export async function POST(req: NextRequest) {
  try {
    const { message } = (await req.json()) as { message?: string }

    if (!message || !message.trim()) {
      return new Response(JSON.stringify({ error: "No message provided" }), { status: 400 })
    }

    const backendRes = await fetch(`${BACKEND_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
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