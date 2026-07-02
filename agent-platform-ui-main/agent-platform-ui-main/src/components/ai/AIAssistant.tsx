"use client"

import { useState, useRef, useEffect, useCallback } from "react"
import { motion } from "framer-motion"
import { Bot, Send, Loader2, Package } from "lucide-react"
import { cn } from "@/lib/utils"
import { ScrollArea } from "@/components/ui/scroll-area"
import type { Message } from "@/lib/ai/client"

const suggestions = [
  "How many agents are active?",
  "Summarize agent health",
  "What's our top priority?",
  "Suggest optimizations",
  "Explain current metrics",
  "Create an order for ahmed@gmail.com, Lahore, 3kg",
  "Show me all orders",
  "How are the agents performing?",
]

export function AIAssistant() {
  const [input, setInput] = useState("")
  const [messages, setMessages] = useState<Message[]>([
    { id: "0", role: "assistant", content: "I'm Warehouse OS AI. Ask me about agents, orders, metrics, or anything about your warehouse." },
  ])
  const [streaming, setStreaming] = useState(false)
  const [streamContent, setStreamContent] = useState("")
  const scrollRef = useRef<HTMLDivElement>(null)
  const idCounter = useRef(0)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, streamContent])

  const handleSend = useCallback(async (text: string) => {
    if (!text.trim() || streaming) return

    idCounter.current += 1
    const userMsg: Message = { id: `msg-${idCounter.current}`, role: "user", content: text }
    setMessages((prev) => [...prev, userMsg])
    setInput("")
    setStreaming(true)
    setStreamContent("")

    try {
      const res = await fetch("/api/ai/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: [...messages, userMsg] }),
      })

      if (!res.ok) throw new Error("Failed")

      const reader = res.body?.getReader()
      const decoder = new TextDecoder()
      let content = ""

      if (reader) {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          content += decoder.decode(value, { stream: true })
          setStreamContent(content)
        }
      }

      idCounter.current += 1
      setMessages((prev) => [...prev, { id: `msg-${idCounter.current}`, role: "assistant", content }])
      setStreamContent("")
    } catch {
      idCounter.current += 1
      setMessages((prev) => [...prev, { id: `msg-${idCounter.current}`, role: "assistant", content: "AI service unavailable. Check your API key." }])
    } finally {
      setStreaming(false)
    }
  }, [messages, streaming])

  return (
    <div className="flex flex-col h-full bg-card/95 backdrop-blur-2xl">
      <div className="flex items-center justify-between px-5 py-3 border-b border-border/30 bg-gradient-to-r from-accent/5 to-transparent">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-accent to-primary shadow-lg">
            <Bot className="h-4 w-4 text-white" />
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground">Warehouse OS AI</p>
            <div className="flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full bg-success animate-pulse" />
              <span className="text-[10px] text-muted-foreground">Online</span>
            </div>
          </div>
        </div>
      </div>

      <ScrollArea className="flex-1 p-5" ref={scrollRef}>
        <div className="space-y-4">
          {messages.map((msg) => (
            <div key={msg.id} className={cn("flex", msg.role === "user" ? "justify-end" : "justify-start")}>
              <div className={cn(
                "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
                msg.role === "user"
                  ? "bg-accent text-white rounded-br-md"
                  : "bg-muted/50 text-foreground rounded-bl-md border border-border/20"
              )}>
                {msg.content}
              </div>
            </div>
          ))}
          {streaming && streamContent && (
            <div className="flex justify-start">
              <div className="max-w-[85%] rounded-2xl rounded-bl-md bg-muted/50 px-4 py-2.5 text-sm text-foreground border border-border/20">
                {streamContent}
                <span className="inline-block w-1.5 h-4 bg-accent ml-0.5 animate-pulse" />
              </div>
            </div>
          )}
          {streaming && !streamContent && (
            <div className="flex justify-start">
              <div className="rounded-2xl rounded-bl-md bg-muted/50 px-4 py-3 border border-border/20">
                <Loader2 className="h-4 w-4 text-accent animate-spin" />
              </div>
            </div>
          )}
        </div>
      </ScrollArea>

      <div className="p-4 border-t border-border/30">
        <div className="flex flex-wrap gap-1.5 mb-3">
          {suggestions.map((s) => (
            <button key={s} onClick={() => handleSend(s)}
              className="text-[11px] px-2.5 py-1 rounded-full border border-border/30 bg-muted/30 text-muted-foreground hover:text-foreground hover:border-accent/30 transition-all whitespace-nowrap"
            >
              {s}
            </button>
          ))}
        </div>
        <form onSubmit={(e) => { e.preventDefault(); handleSend(input) }} className="flex items-center gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask anything about your warehouse..."
            className="flex-1 h-10 rounded-xl border border-border/30 bg-muted/30 px-4 text-sm text-foreground placeholder:text-muted-foreground focus:border-accent/40 focus:outline-none focus:ring-1 focus:ring-accent/20 transition-all"
          />
          <button type="submit" disabled={!input.trim() || streaming}
            className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent text-white disabled:opacity-40 transition-all hover:opacity-90 active:scale-95"
          >
            <Send className="h-4 w-4" />
          </button>
        </form>
      </div>
    </div>
  )
}
