import { NextRequest } from "next/server"
import { streamChat } from "@/lib/ai/client"

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

export async function POST(req: NextRequest) {
  try {
    const { messages } = (await req.json()) as { messages: Array<{ role: string; content: string }> }

    const lastUserMsg = [...messages].reverse().find(m => m.role === "user")
    if (!lastUserMsg) {
      return new Response(JSON.stringify({ error: "No user message" }), { status: 400 })
    }

    let reply: string | null = null
    try {
      const backendRes = await fetch(`${BACKEND_URL}/api/chat/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: lastUserMsg.content }),
        signal: AbortSignal.timeout(10000),
      })
      if (backendRes.ok) {
        const data = await backendRes.json()
        reply = data.reply || null
      }
    } catch {
      // Backend unavailable, fall through to direct AI stream
    }

    if (reply) {
      const encoder = new TextEncoder()
      const readable = new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode(reply))
          controller.close()
        },
      })
      return new Response(readable, {
        headers: {
          "Content-Type": "text/plain; charset=utf-8",
          "Cache-Control": "no-cache",
        },
      })
    }

    const stream = await streamChat(messages)
    const encoder = new TextEncoder()
    const readable = new ReadableStream({
      async start(controller) {
        try {
          for await (const chunk of stream) {
            const content = chunk.choices?.[0]?.delta?.content || ""
            if (content) {
              controller.enqueue(encoder.encode(content))
            }
          }
        } catch (err) {
          const errMsg = err instanceof Error ? err.message : "Failed to generate response"
          controller.enqueue(encoder.encode(`Error: ${errMsg}`))
        } finally {
          controller.close()
        }
      },
    })

    return new Response(readable, {
      headers: {
        "Content-Type": "text/plain; charset=utf-8",
        "Cache-Control": "no-cache",
      },
    })
  } catch (err) {
    const errMsg = err instanceof Error ? err.message : "AI service unavailable"
    return new Response(
      JSON.stringify({ error: errMsg }),
      { status: 500 }
    )
  }
}
