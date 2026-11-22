"use client"

import { useEffect, useState } from "react"

type Run = { id?: string; stage?: string; updated_at?: number; result?: { monitor_task: string; booking_task: string; notification_task: string; events: {agent:string; type:string; id:string; time:string}[] } }
export function EvaluationRun() {
  const [run, setRun] = useState<Run>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  useEffect(() => {
    const controller = new AbortController()
    async function refresh() {
      try {
        const res = await fetch("/api/evaluation/workflow", {signal:controller.signal,cache:"no-store"})
        if (!res.ok) throw new Error("Evaluation access unavailable")
        setRun(await res.json())
      } catch { if (!controller.signal.aborted) setError("Evaluation status unavailable") }
    }
    void refresh()
    const timer = setInterval(refresh, 3000)
    return () => { controller.abort(); clearInterval(timer) }
  }, [])
  async function start() {
    setBusy(true)
    try {
      const res = await fetch("/api/evaluation/workflow", {method:"POST"})
      if (!res.ok) throw new Error()
      setRun(await res.json())
      setError("")
    } catch { setError("Could not start the evaluation. Check the current run before retrying.") }
    finally { setBusy(false) }
  }
  return <section className="space-y-2"><button className="rounded border px-3 py-2" onClick={start} disabled={busy || Boolean(run.id && !["Completed","Failed"].includes(run.stage ?? ""))}>Run Evaluation Workflow</button>
    <p aria-live="polite">{error || run.stage} {run.updated_at && new Date(run.updated_at * 1000).toLocaleTimeString()}</p>
    {run.id && <details><summary>Evaluation run details</summary><p>Run {run.id}</p>{run.result && <><p>Booking {run.result.booking_task} · Monitor {run.result.monitor_task} · Notification {run.result.notification_task}</p>
    {run.result.events.map(e=><p key={e.id}>{e.agent} · {e.type} · {e.time} · {e.id}</p>)}</>}</details>}
  </section>
}
