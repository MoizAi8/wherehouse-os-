"use client"

import { useState, useRef, useEffect, useCallback } from "react"
import { motion } from "framer-motion"
import { Bot, Send, Loader2, Package, Trash2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { ScrollArea } from "@/components/ui/scroll-area"
import type { Message } from "@/lib/ai/client"

const SESSION_KEY = "fulfillos_chat_session"

function loadSessionId(): string {
  if (typeof window === "undefined") return ""
  let sid = window.localStorage.getItem(SESSION_KEY)
  if (!sid) {
    sid = `s-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
    window.localStorage.setItem(SESSION_KEY, sid)
  }
  return sid
}

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

export function AIAssistant({ initialContext }: { initialContext?: { name: string; role: string } | null }) {
  const [input, setInput] = useState("")
  const [sessionId, setSessionId] = useState<string>(loadSessionId)
  const [messages, setMessages] = useState<Message[]>([])
  const [streaming, setStreaming] = useState(false)
  const [streamContent, setStreamContent] = useState("")
  const scrollRef = useRef<HTMLDivElement>(null)
  const idCounter = useRef(0)

  useEffect(() => {
    if (initialContext) {
      setInput(`Show me details about ${initialContext.name} (${initialContext.role})`)
    }
  }, [initialContext])

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, streamContent])

  useEffect(() => {
    let cancelled = false
    async function loadHistory() {
      try {
        const res = await fetch(`/api/chat/history?sessionId=${encodeURIComponent(sessionId)}`)
        if (!res.ok) return
        const data = await res.json()
        if (cancelled || !data?.messages?.length) return
        const loaded: Message[] = data.messages.map((m: { id: number | string; role: string; content: string }) => ({
          id: String(m.id),
          role: (m.role === "user" || m.role === "assistant" ? m.role : "assistant") as "user" | "assistant",
          content: m.content,
        }))
        idCounter.current = loaded.length
        setMessages(loaded)
      } catch {
        // history is best-effort; the chat still works without it
      }
    }
    loadHistory()
    return () => {
      cancelled = true
    }
  }, [sessionId])

  const clearChat = () => {
    const fresh = `s-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
    window.localStorage.setItem(SESSION_KEY, fresh)
    setSessionId(fresh)
    setMessages([{ id: "0", role: "assistant", content: "👋 Chat cleared. Send a message to start a new conversation." }])
    idCounter.current = 1
  }

  const handleSend = useCallback(async (text: string) => {
    if (!text.trim() || streaming) return

    idCounter.current += 1
    const userMsg: Message = { id: `msg-${idCounter.current}`, role: "user", content: text }
    setMessages((prev) => [...prev, userMsg])
    setInput("")
    setStreaming(true)
    setStreamContent("")

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, sessionId }),
      })

      if (!res.ok) throw new Error("Failed")

      const data = await res.json()
      if (data.sessionId) {
        window.localStorage.setItem(SESSION_KEY, data.sessionId)
        setSessionId(data.sessionId)
      }
      idCounter.current += 1
      setMessages((prev) => [...prev, { id: `msg-${idCounter.current}`, role: "assistant", content: data.reply }])
    } catch (err) {
      idCounter.current += 1
      const errMsg = err instanceof Error ? err.message : "AI service unavailable. Check your API key and backend connection."
      setMessages((prev) => [...prev, { id: `msg-${idCounter.current}`, role: "assistant", content: `Error: ${errMsg}` }])
    } finally {
      setStreaming(false)
    }
  }, [messages, streaming, sessionId])

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
        <button onClick={clearChat}
          className="flex h-7 w-7 items-center justify-center rounded-lg text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-all"
          title="Clear chat"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>

      <ScrollArea className="flex-1 p-5" ref={scrollRef}>
        <div className="space-y-4">
          {messages.length === 0 && (
            <div className="flex justify-start">
              <div className="max-w-[85%] rounded-2xl rounded-bl-md bg-muted/50 px-4 py-2.5 text-sm text-foreground border border-border/20">
                👋 Welcome to Warehouse OS! Send a message to get started.
              </div>
            </div>
          )}
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
