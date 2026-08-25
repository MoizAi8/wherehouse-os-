"use client"

import { useState, useRef, useEffect, useCallback } from "react"
import { Bot, Send, Loader2, Trash2, AlertTriangle, WifiOff } from "lucide-react"
import { cn } from "@/lib/utils"
import { ScrollArea } from "@/components/ui/scroll-area"
import type { Message } from "@/lib/ai/client"

const SESSION_KEY = "fulfillos_chat_session"
const MAX_RETRIES = 3
const RETRY_DELAY_MS = 1000

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
  const [input, setInput] = useState(() => {
    if (initialContext) {
      return `Show me details about ${initialContext.name} (${initialContext.role})`
    }
    return ""
  })
  const [sessionId, setSessionId] = useState<string>(loadSessionId)
  const [messages, setMessages] = useState<Message[]>([])
  const [streaming, setStreaming] = useState(false)
  const [streamContent, setStreamContent] = useState("")
  const [connectionStatus, setConnectionStatus] = useState<"connected" | "disconnected" | "checking">("checking")
  const [retryAttempt, setRetryAttempt] = useState(0)
  const scrollRef = useRef<HTMLDivElement>(null)
  const idCounter = useRef(0)

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

  const checkConnection = useCallback(async () => {
    try {
      const res = await fetch("/api/health", { method: "GET", cache: "no-store" })
      setConnectionStatus(res.ok ? "connected" : "disconnected")
    } catch {
      setConnectionStatus("disconnected")
    }
  }, [])

  useEffect(() => {
    // Perform initial connection check using async IIFE to avoid setState-in-effect warning
    const doInitialCheck = async () => {
      try {
        const res = await fetch("/api/health", { method: "GET", cache: "no-store" })
        setConnectionStatus(res.ok ? "connected" : "disconnected")
      } catch {
        setConnectionStatus("disconnected")
      }
    }
    doInitialCheck()

    const interval = setInterval(() => {
      checkConnection()
    }, 30000)

    return () => {
      clearInterval(interval)
    }
  }, [checkConnection])

  const clearChat = () => {
    const fresh = `s-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
    window.localStorage.setItem(SESSION_KEY, fresh)
    setSessionId(fresh)
    setMessages([{ id: "0", role: "assistant", content: "Chat cleared. Send a message to start a new conversation." }])
    idCounter.current = 1
    setRetryAttempt(0)
  }

  // Separate async function for retry logic (not a useCallback to avoid circular reference)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const sendWithRetry = async (text: string, retries = MAX_RETRIES): Promise<{ reply: string; sessionId?: string }> => {
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, sessionId }),
      })

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.error || `Request failed: ${res.status}`)
      }

      const data = await res.json()
      setRetryAttempt(0)
      return { reply: data.reply, sessionId: data.sessionId }
    } catch (err) {
      if (retries > 0) {
        const nextAttempt = MAX_RETRIES - retries + 1
        setRetryAttempt(nextAttempt)
        await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS * nextAttempt))
        return sendWithRetry(text, retries - 1)
      }
      setRetryAttempt(0)
      throw err
    }
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
      const { reply, sessionId: newSessionId } = await sendWithRetry(text)
      if (newSessionId) {
        window.localStorage.setItem(SESSION_KEY, newSessionId)
        setSessionId(newSessionId)
      }
      idCounter.current += 1
      setMessages((prev) => [...prev, { id: `msg-${idCounter.current}`, role: "assistant", content: reply }])
    } catch (err) {
      idCounter.current += 1
      const errMsg = err instanceof Error ? err.message : "AI service unavailable. Check your API key and backend connection."
      setMessages((prev) => [...prev, { id: `msg-${idCounter.current}`, role: "assistant", content: `Error: ${errMsg}` }])
    } finally {
      setStreaming(false)
      setStreamContent("")
      setRetryAttempt(0)
    }
  }, [streaming, sendWithRetry])

  return (
    <div className="flex flex-col h-full bg-card/95 backdrop-blur-2xl">
      <div className="flex items-center justify-between px-5 py-3 border-b border-border/30 bg-gradient-to-r from-accent/5 to-transparent">
        <div className="flex items-center gap-2.5">
          <div className={cn(
            "flex h-8 w-8 items-center justify-center rounded-xl shadow-lg",
            connectionStatus === "connected"
              ? "bg-gradient-to-br from-accent to-primary"
              : connectionStatus === "disconnected"
              ? "bg-gradient-to-br from-destructive to-red-600"
              : "bg-gradient-to-br from-warning to-amber-600"
          )}>
            {connectionStatus === "connected" ? (
              <Bot className="h-4 w-4 text-white" />
            ) : connectionStatus === "disconnected" ? (
              <WifiOff className="h-4 w-4 text-white" />
            ) : (
              <Loader2 className="h-4 w-4 text-white animate-spin" />
            )}
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground">Warehouse OS AI</p>
            <div className="flex items-center gap-1">
              <span className={cn(
                "h-1.5 w-1.5 rounded-full animate-pulse",
                connectionStatus === "connected" ? "bg-success" :
                connectionStatus === "disconnected" ? "bg-destructive" : "bg-warning"
              )} />
              <span className="text-[10px] text-muted-foreground capitalize">{connectionStatus}</span>
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
                Welcome to Warehouse OS! Send a message to get started.
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
          {retryAttempt > 0 && (
            <div className="flex justify-center">
              <div className="flex items-center gap-2 text-xs text-warning bg-warning/10 px-3 py-1.5 rounded-full border border-warning/20">
                <AlertTriangle className="h-3 w-3" />
                <span>Retrying... (attempt {retryAttempt}/{MAX_RETRIES})</span>
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
            disabled={streaming}
          />
          <button type="submit" disabled={!input.trim() || streaming}
            className={cn(
              "flex h-10 w-10 items-center justify-center rounded-xl text-white disabled:opacity-40 transition-all hover:opacity-90 active:scale-95",
              streaming ? "bg-muted" : "bg-accent"
            )}
          >
            {streaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </button>
        </form>
      </div>
    </div>
  )
}
