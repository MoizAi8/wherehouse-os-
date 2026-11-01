export interface Message {
  id: string
  role: "user" | "assistant" | "system"
  content: string
}

export interface AIContext {
  page?: string
  agents?: number
  metrics?: Record<string, string>
}

export async function streamChat(messages: Message[], context?: AIContext) {
  const hasApiKey = process.env.OPENAI_API_KEY

  if (!hasApiKey) {
    throw new Error(
      "OpenAI API key is not configured on the server."
    )
  }

  const OpenAI = (await import("openai")).default
  const openai = new OpenAI({ apiKey: hasApiKey })

  const systemPrompt = `You are Warehouse OS AI — an intelligent assistant for a warehouse multi-agent system.
You help operators manage autonomous agents, interpret metrics, and optimize workflows.
Keep responses concise, data-driven, and actionable.
${context ? `Current context: Page=${context.page || "unknown"}, Agents=${context.agents || "—"}` : ""}`

  return openai.chat.completions.create({
    model: "gpt-4o-mini",
    messages: [
      { role: "system", content: systemPrompt },
      ...messages.map((m) => ({ role: m.role as "user" | "assistant" | "system", content: m.content })),
    ],
    stream: true,
    temperature: 0.7,
    max_tokens: 500,
  })
}
