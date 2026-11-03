"use client"

import { useState, useRef, useEffect, useCallback, useLayoutEffect } from "react"
import { Bot, Send, Loader2, Trash2, AlertTriangle, WifiOff, History } from "lucide-react"
import { cn } from "@/lib/utils"
import { newConversationId, readChatStorage, readConversations, writeChatStorage, type Conversation } from "@/lib/chat-history"
import type { Message } from "@/lib/ai/client"
import { ApiError } from "@/lib/api"
import { useSessionIdentity } from "@/components/providers/SessionProvider"
import { refreshSession } from "@/lib/session"

const SESSION_KEY = "fulfillos_chat_session"
const MAX_RETRIES = 3
const RETRY_DELAY_MS = 1000

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
  const identity = useSessionIdentity()
  const guest = identity === "guest"
  const storageKey = `${SESSION_KEY}:${identity}`
  const historyKey = `${storageKey}:history`
  const [conversations, setConversations] = useState(() => readConversations(historyKey, guest))
  const indexRef = useRef(conversations)
  const [newChatNotice, setNewChatNotice] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [historyError, setHistoryError] = useState("")
  const [deleting, setDeleting] = useState(false)
  const [readySession, setReadySession] = useState("")
  const [input, setInput] = useState(() => {
    if (initialContext) {
      return `Show me details about ${initialContext.name} (${initialContext.role})`
    }
    return ""
  })
  const [sessionId, setSessionId] = useState(() => readChatStorage(storageKey) || (!guest ? readChatStorage(SESSION_KEY) : null) || newConversationId())
  const [messages, setMessages] = useState<Message[]>([])
  const [streaming, setStreaming] = useState(false)
  const [streamContent, setStreamContent] = useState("")
  const [connectionStatus, setConnectionStatus] = useState<"connected" | "disconnected" | "checking">("checking")
  const [retryAttempt, setRetryAttempt] = useState(0)
  const [pendingAction, setPendingAction] = useState<{ message: string; token: string } | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const idCounter = useRef(0)
  const followLatest = useRef(true)
  const [showLatest, setShowLatest] = useState(false)

  const scrollToLatest = useCallback(() => {
    followLatest.current = true
    setShowLatest(false)
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [])

  const saveIndex = (items: Conversation[]) => {
    const bounded = items.slice(0, 20)
    indexRef.current = bounded
    setConversations(bounded)
    if (!writeChatStorage(historyKey, JSON.stringify(bounded))) {
      setHistoryError("Browser storage is unavailable. Conversation shortcuts may be lost on reload.")
    }
  }

  const saveConversation = (id: string, turns: Message[]) => {
    const prior = conversations.find(item => item.id === id)
    const first = turns.find(turn => turn.role === "user")
    saveIndex([{
      id, title: prior?.title ?? first?.content.trim().slice(0, 64) ?? "Conversation",
      updated: Date.now(),
      ...(guest ? { messages: turns.slice(-30).map(turn => ({ ...turn, content: turn.content.slice(0, 4000) })) } : {}),
    }, ...conversations.filter(item => item.id !== id)])
  }

  useLayoutEffect(() => {
    if (followLatest.current && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, streamContent, streaming, retryAttempt])

  useEffect(() => {
    let cancelled = false
    async function loadHistory() {
      let loaded: Message[] = []
      try {
        if (guest) {
          loaded = indexRef.current.find(item => item.id === sessionId)?.messages ?? []
        } else {
          const res = await fetch(`/api/chat?sessionId=${encodeURIComponent(sessionId)}`, { cache: "no-store" })
          if (!res.ok && res.status !== 401) throw new Error("Could not load saved messages")
          const data = res.ok ? await res.json() : {}
          loaded = (data.messages ?? []).map((m: { id: number | string; role: "user" | "assistant"; content: string }) => ({
            id: String(m.id), role: m.role, content: m.content,
          }))
        }
        if (cancelled) return
        setMessages(loaded)
        setReadySession(sessionId)
        if (guest) writeChatStorage(historyKey, JSON.stringify(indexRef.current))
        if (!guest && loaded.length) {
          const index = readConversations(historyKey, false)
          if (!index.some(item => item.id === sessionId)) {
            const title = loaded.find(item => item.role === "user")?.content.trim().slice(0, 64) || "Conversation"
            const updated = [{ id: sessionId, title, updated: Date.now() }, ...index].slice(0, 20)
            indexRef.current = updated
            setConversations(updated)
            writeChatStorage(historyKey, JSON.stringify(updated))
          }
        }
      } catch {
        if (!cancelled) {
          setHistoryError("Could not load saved messages. Reopen the conversation to retry.")
          setShowHistory(true)
        }
      }
    }
    void Promise.resolve().then(loadHistory)
    return () => { cancelled = true }
  }, [sessionId, historyKey, guest])

  const checkConnection = useCallback(async () => {
    try {
      const res = await fetch("/health", { method: "GET", cache: "no-store" })
      setConnectionStatus(res.ok ? "connected" : "disconnected")
    } catch {
      setConnectionStatus("disconnected")
    }
  }, [])

  useEffect(() => {
    // Perform initial connection check using async IIFE to avoid setState-in-effect warning
    const doInitialCheck = async () => {
      try {
        const res = await fetch("/health", { method: "GET", cache: "no-store" })
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

  const openConversation = (id: string) => {
    if (id === sessionId && readySession === id) {
      setShowHistory(false)
      return
    }
    writeChatStorage(storageKey, id)
    setMessages([])
    setNewChatNotice(false)
    setPendingAction(null)
    setHistoryError("")
    setShowHistory(false)
    setSessionId(id)
    followLatest.current = true
    setShowLatest(false)
  }

  const clearChat = () => {
    openConversation(newConversationId())
    setNewChatNotice(true)
  }

  const deleteConversation = async (id: string) => {
    if (!window.confirm("Delete this conversation?")) return
    setDeleting(true)
    setHistoryError("")
    try {
      if (!guest) {
        const response = await fetch(`/api/chat?sessionId=${encodeURIComponent(id)}`, { method: "DELETE" })
        if (!response.ok) throw new Error("Delete failed")
      }
      saveIndex(conversations.filter(item => item.id !== id))
      if (id === sessionId) clearChat()
    } catch {
      setHistoryError("Could not delete the conversation. Try again.")
    } finally {
      setDeleting(false)
    }
  }

  // Separate async function for retry logic (not a useCallback to avoid circular reference)
  const sendWithRetry = async (text: string, retries = MAX_RETRIES, confirmationToken?: string): Promise<{ reply: string; confirmation?: { message: string; token: string } }> => {
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, sessionId, confirmationToken, history: messages.filter(m => m.role === "user" || m.role === "assistant").slice(-6).map(m => ({ role: m.role, content: m.content.slice(0, 500) })) }),
      })

      if (!res.ok) {
        if (res.status === 401) {
          await refreshSession()
          throw new ApiError(401, "Your session expired. Please sign in again.")
        }
        const errorData = await res.json().catch(() => ({}))
        throw new ApiError(res.status, errorData.error || `Request failed: ${res.status}`)
      }

      const data = await res.json()
      setRetryAttempt(0)
      return { reply: data.reply,
        confirmation: data.action === "confirmation_required" ? { message: data.data.message, token: data.data.confirmation_token } : undefined }
    } catch (err) {
      // An authenticated request may already have committed its history or action.
      if (!guest || confirmationToken) throw err
      if (err instanceof ApiError && (err.status === 401 || err.status === 403 || err.status === 429)) throw err
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

  const handleSend = async (text: string, confirmationToken?: string) => {
    if (!text.trim() || streaming || deleting || readySession !== sessionId) return
    scrollToLatest()

    idCounter.current += 1
    const userMsg: Message = { id: `msg-${idCounter.current}`, role: "user", content: text }
    setMessages((prev) => [...prev, userMsg])
    setInput("")
    setStreaming(true)
    setPendingAction(null)
    setStreamContent("")

    try {
      const { reply, confirmation } = await sendWithRetry(text, MAX_RETRIES, confirmationToken)
      setPendingAction(confirmation || null)
      idCounter.current += 1
      const answer: Message = { id: `msg-${idCounter.current}`, role: "assistant", content: reply }
      const turns = [...messages, userMsg, answer]
      setMessages(turns)
      saveConversation(sessionId, turns)
      writeChatStorage(storageKey, sessionId)
    } catch (err) {
      idCounter.current += 1
      const errMsg = err instanceof Error ? err.message : "AI service unavailable. Check your API key and backend connection."
      setMessages((prev) => [...prev, { id: `msg-${idCounter.current}`, role: "assistant", content: `Error: ${errMsg}` }])
    } finally {
      setStreaming(false)
      setStreamContent("")
      setRetryAttempt(0)
    }
  }

  return (
    <div className="relative flex min-h-0 min-w-0 w-full flex-1 flex-col h-full bg-card/95 backdrop-blur-2xl">
      <div className="flex items-center justify-between shrink-0 px-5 py-3 border-b border-border/30 bg-gradient-to-r from-accent/5 to-transparent">
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
        <div className="flex items-center gap-1">
        <button type="button" aria-label="Conversation history" aria-expanded={showHistory} onClick={() => setShowHistory(value => !value)}
          className="flex h-7 w-7 items-center justify-center rounded-lg text-muted-foreground hover:text-accent hover:bg-accent/10">
          <History className="h-3.5 w-3.5" />
        </button>
        <button onClick={clearChat} disabled={streaming || deleting} aria-label="New conversation"
          className="flex h-7 w-7 items-center justify-center rounded-lg text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-all"
          title="Clear chat"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
        </div>
      </div>

      {showHistory && <section aria-label="Saved conversations" className="absolute z-20 right-2 top-14 w-80 max-w-[calc(100%-1rem)] max-h-[calc(100%-4rem)] overflow-auto rounded-xl border border-border bg-card p-3 shadow-xl">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold">Conversations</h2>
          <button disabled={streaming || deleting} onClick={clearChat} className="text-xs text-accent">New chat</button>
        </div>
        <p className="my-2 text-xs text-muted-foreground">{guest ? "Saved on this browser for up to 30 days." : "Messages are saved to your account. Shortcuts are saved in this browser."}</p>
        {historyError && <p role="alert" className="text-xs text-destructive">{historyError}</p>}
        {conversations.length === 0 && <p className="my-2 text-xs text-muted-foreground">No saved conversations</p>}
        {conversations.map(item => <div key={item.id} className="flex items-center gap-1 rounded hover:bg-muted/60">
          <button aria-current={item.id === sessionId ? "true" : undefined} disabled={streaming || deleting} onClick={() => openConversation(item.id)} className="min-w-0 flex-1 truncate p-2 text-left text-sm">{item.title}</button>
          <button aria-label={`Delete ${item.title}`} disabled={streaming || deleting} onClick={() => void deleteConversation(item.id)} className="p-2 text-muted-foreground hover:text-destructive"><Trash2 className="h-3.5 w-3.5" /></button>
        </div>)}
        {guest && conversations.length > 0 && <button disabled={streaming || deleting} className="mt-3 text-xs text-destructive" onClick={() => {
          if (window.confirm("Clear all guest conversations from this browser?")) {
            saveIndex([])
            clearChat()
          }
        }}>Clear local history</button>}
      </section>}

      <div aria-label="Chat messages" className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-3 sm:p-5" ref={scrollRef}
        onScroll={event => {
          const node = event.currentTarget
          const nearBottom = node.scrollHeight - node.scrollTop - node.clientHeight <= 48
          followLatest.current = nearBottom
          setShowLatest(!nearBottom)
        }}>
        <div className="space-y-4">
          {messages.length === 0 && (
            <div className="flex justify-start">
              <div className="max-w-[85%] rounded-2xl rounded-bl-md bg-muted/50 px-4 py-2.5 text-sm text-foreground border border-border/20">
                {newChatNotice ? "Chat cleared. Send a message to start a new conversation." : "Welcome to Warehouse OS! Send a message to get started."}
              </div>
            </div>
          )}
          {messages.map((msg) => (
            <div key={msg.id} className={cn("flex", msg.role === "user" ? "justify-end" : "justify-start")}>
              <div className={cn(
                "max-w-[85%] whitespace-pre-wrap wrap-anywhere rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
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
      </div>
      {showLatest && <button onClick={scrollToLatest} className="mx-auto shrink-0 rounded-full border border-border bg-card px-3 py-1 text-xs text-accent">Scroll to latest</button>}

      {pendingAction && <div className="mx-4 max-h-[20%] shrink-0 overflow-auto rounded-lg border border-warning/40 bg-warning/5 p-3 text-sm">
        <p className="mb-2 break-words">Review action: {pendingAction.message}</p>
        <div className="flex gap-2"><button disabled={streaming} onClick={() => void handleSend(pendingAction.message, pendingAction.token)} className="rounded bg-accent px-3 py-2 text-white">Confirm warehouse action</button>
          <button onClick={() => setPendingAction(null)} className="rounded border border-border px-3 py-2">Cancel action</button></div>
      </div>}

      <div className="shrink-0 p-2 sm:p-4 border-t border-border/30">
        <div className="hidden md:flex flex-wrap gap-1.5 mb-3 max-h-20 overflow-auto">
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
            className="min-w-0 flex-1 h-10 rounded-xl border border-border/30 bg-muted/30 px-4 text-sm text-foreground placeholder:text-muted-foreground focus:border-accent/40 focus:outline-none focus:ring-1 focus:ring-accent/20 transition-all"
            disabled={streaming || deleting || readySession !== sessionId}
          />
          <button type="submit" disabled={!input.trim() || streaming || deleting || readySession !== sessionId}
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
