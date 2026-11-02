"use client"

import Link from "next/link"
import { useEffect, useState } from "react"

const views = ["dashboard", "orders", "inventory", "agents", "monitoring", "workflows", "analytics", "chat"] as const
type View = typeof views[number]
type Turn = { role: "user" | "assistant"; content: string; mode?: string }
type DemoStatus = { enabled: boolean; read_only: boolean; llm_configured: boolean; model: string | null }

function DataView({ data }: { data: unknown }) {
  if (Array.isArray(data)) {
    if (!data.length) return <p className="text-muted-foreground">No matching sample records.</p>
    if (typeof data[0] !== "object") return <ol className="space-y-3">{data.map((value, i) =>
      <li key={i} className="rounded-lg border border-border p-4">{i + 1}. {String(value)}</li>)}</ol>
    const columns = Object.keys(data[0])
    return <div className="overflow-x-auto"><table className="w-full text-left text-sm">
      <thead><tr>{columns.map(key => <th className="border-b border-border p-3 capitalize" key={key}>{key.replaceAll("_", " ")}</th>)}</tr></thead>
      <tbody>{data.map((row, i) => <tr key={i}>{columns.map(key =>
        <td key={key} className="border-b border-border/50 p-3">{String(row[key])}</td>)}</tr>)}</tbody>
    </table></div>
  }
  if (data !== null && typeof data === "object") return <div className="grid gap-5">{Object.entries(data).map(([key, value]) =>
    <section key={key} className="rounded-xl border border-border bg-card p-5">
      <h2 className="mb-3 text-lg font-semibold capitalize">{key.replaceAll("_", " ")}</h2>
      <DataView data={value} />
    </section>)}</div>
  return <p className="break-words">{String(data ?? "—")}</p>
}

export default function TeacherDemo() {
  const [view, setView] = useState<View>("dashboard")
  const [status, setStatus] = useState<DemoStatus | null>(null)
  const [data, setData] = useState<unknown>(null)
  const [loadedKey, setLoadedKey] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState("")
  const [health, setHealth] = useState("Checking backend")
  const [turns, setTurns] = useState<Turn[]>([])
  const [input, setInput] = useState("")
  const [sending, setSending] = useState(false)

  useEffect(() => {
    let stopped = false
    async function load() {
      setLoading(true)
      setError("")
      try {
        const state = await fetch("/api/demo/status", { cache: "no-store" })
        if (!state.ok) throw new Error("Teacher demo is disabled. The protected application remains available through normal login.")
        const info = await state.json()
        const response = await fetch(`/api/demo/data?view=${view === "chat" ? "dashboard" : view}&status=${encodeURIComponent(filter)}`, { cache: "no-store" })
        if (!response.ok) throw new Error("Demo data is unavailable. Please try again.")
        const result = await response.json()
        if (!stopped) { setStatus(info); setData(result.data); setLoadedKey(`${view}:${filter}`) }
      } catch (cause) {
        if (!stopped) { setStatus(null); setData(null); setError(cause instanceof Error ? cause.message : "Demo unavailable") }
      } finally { if (!stopped) setLoading(false) }
    }
    void load()
    return () => { stopped = true }
  }, [view, filter])

  useEffect(() => {
    void fetch("/health", { cache: "no-store" }).then(async response => {
      if (!response.ok) throw new Error("Backend unavailable")
      const body = await response.json()
      setHealth(body.degraded ? "Backend reachable · some dependencies unavailable" : "Backend connected · dependencies healthy")
    }).catch(() => setHealth("Backend unavailable"))
  }, [])

  async function send(message: string) {
    if (!message.trim() || sending) return
    setSending(true)
    setInput("")
    const history = turns.slice(-6).map(({ role, content }) => ({ role, content: content.slice(0, 500) }))
    setTurns(previous => [...previous, { role: "user", content: message }])
    try {
      const response = await fetch("/api/demo/chat", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, history }) })
      const result = await response.json()
      if (!response.ok) throw new Error(result.detail || "Demo chat unavailable")
      setTurns(previous => [...previous, { role: "assistant", content: result.reply, mode: result.mode }])
    } catch (cause) {
      setTurns(previous => [...previous, { role: "assistant", content: cause instanceof Error ? cause.message : "Chat unavailable", mode: "error" }])
    } finally { setSending(false) }
  }

  return <div className="min-h-screen bg-background text-foreground">
    <header className="border-b border-border px-5 py-6 sm:px-10">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4">
        <div><p className="text-sm font-medium text-accent">Warehouse OS</p><h1 className="text-2xl font-semibold">Teacher demonstration</h1></div>
        <Link className="rounded-lg border border-border px-4 py-2 text-sm" href="/dashboard">Protected application · sign in</Link>
      </div>
    </header>
    <main className="mx-auto max-w-6xl space-y-6 p-5 sm:p-10">
      <aside aria-label="Demo isolation notice" className="rounded-xl border border-accent/40 bg-accent/5 p-4 text-sm">
        <strong>Read-only sample environment.</strong> All displayed warehouse records are labelled samples in a separate SQLite database.
        No private production records, administrator access, dispatch or notifications are exposed. Demo mode stays enabled until the owner disables it.
      </aside>
      <p role="status" className="text-sm text-muted-foreground">{health}</p>
      <nav aria-label="Demo navigation" className="flex flex-wrap gap-2">{views.map(name =>
        <button key={name} aria-pressed={view === name} onClick={() => { setView(name); setFilter("") }}
          className={`rounded-lg border px-4 py-2 capitalize ${view === name ? "border-accent bg-accent text-white" : "border-border bg-card"}`}>{name}</button>)}</nav>
      {loading && <p>Loading sample data…</p>}
      {error && <p role="alert" className="rounded-lg border border-destructive p-4">{error}</p>}
      {!loading && status && loadedKey === `${view}:${filter}` && <section aria-label="Demo workspace" className="space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-xl font-semibold capitalize">Sample {view}</h2>
          <span className="text-xs text-muted-foreground">Data source: isolated sample SQLite · no production access</span>
        </div>
        {view === "orders" && <label className="flex items-center gap-3 text-sm">Filter sample orders
          <select aria-label="Order status" value={filter} onChange={event => setFilter(event.target.value)} className="rounded-md border border-border bg-card p-2">
            <option value="">All statuses</option>{["pending", "processing", "shipped", "delivered", "cancelled"].map(value => <option key={value}>{value}</option>)}
          </select></label>}
        {view !== "chat" ? <DataView data={data} /> : <div className="rounded-xl border border-border bg-card p-5">
          <p className="mb-4 text-sm text-muted-foreground">{status.llm_configured
            ? `Language model configured: ${status.model}. Warehouse facts come from the sample database.`
            : "No real language model is configured on this server. Database commands work; general AI conversation is unavailable."}</p>
          <div role="log" aria-label="Demo conversation" className="max-h-[500px] space-y-3 overflow-auto">{turns.map((turn, i) =>
            <article key={i} className="rounded-lg border border-border p-3"><p className="mb-1 text-xs font-medium capitalize">{turn.role}{turn.mode ? ` · ${turn.mode}` : ""}</p><p className="whitespace-pre-wrap break-words text-sm">{turn.content}</p></article>)}</div>
          <div className="my-4 flex flex-wrap gap-2">{["Show sample orders", "Check inventory", "Explain the workflow", "Show metrics"].map(message =>
            <button key={message} disabled={sending} onClick={() => void send(message)} className="rounded-md border border-border px-3 py-2 text-xs">{message}</button>)}</div>
          <form onSubmit={event => { event.preventDefault(); void send(input) }} className="flex gap-2">
            <input aria-label="Demo message" maxLength={2000} value={input} onChange={event => setInput(event.target.value)} disabled={sending}
              placeholder="Ask about the sample warehouse…" className="min-w-0 flex-1 rounded-lg border border-border bg-background px-3 py-2" />
            <button disabled={sending || !input.trim()} className="rounded-lg bg-accent px-5 py-2 text-white">{sending ? "Sending…" : "Send"}</button>
          </form>
          <button onClick={() => setTurns([])} className="mt-3 text-xs text-muted-foreground">Clear this tab&apos;s conversation</button>
        </div>}
      </section>}
    </main>
  </div>
}
