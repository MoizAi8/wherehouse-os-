"use client"

import { useMemo } from "react"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { GitBranch, Play, Pause, CheckCircle2, Clock, Square } from "lucide-react"
import { useState } from "react"
import { useSearch } from "@/contexts/SearchContext"

type WorkflowStatus = "running" | "paused" | "completed" | "stopped"

interface Workflow { id: string; name: string; status: WorkflowStatus; progress: number; agents: number; lastRun: string }

const initialWorkflows: Workflow[] = [
  { id: "1", name: "Inventory Reconciliation", status: "running", progress: 72, agents: 3, lastRun: "2m ago" },
  { id: "2", name: "Order Fulfillment Pipeline", status: "running", progress: 45, agents: 5, lastRun: "1m ago" },
  { id: "3", name: "Demand Forecasting Cycle", status: "paused", progress: 88, agents: 2, lastRun: "15m ago" },
  { id: "4", name: "Quality Assurance Batch", status: "completed", progress: 100, agents: 2, lastRun: "32m ago" },
]

const statusIcons: Record<WorkflowStatus, typeof Play> = { running: Play, paused: Pause, completed: CheckCircle2, stopped: Square }

function nextStatus(current: WorkflowStatus): WorkflowStatus {
  if (current === "running") return "stopped"
  if (current === "stopped") return "running"
  if (current === "paused") return "running"
  return "stopped"
}

export function WorkflowPanel() {
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const [workflows, setWorkflows] = useState<Workflow[]>(initialWorkflows)
  const { query } = useSearch()

  const toggleWorkflow = (id: string) => {
    setWorkflows((prev) =>
      prev.map((wf) => (wf.id === id ? { ...wf, status: nextStatus(wf.status) } : wf))
    )
  }

  const filtered = useMemo(() => {
    if (!query.trim()) return workflows
    return workflows.filter((wf) => wf.name.toLowerCase().includes(query.toLowerCase()))
  }, [query, workflows])

  return (
    <div className="rounded-xl glass-card">
      <div className="flex items-center justify-between border-b border-border/30 px-5 py-3">
        <div className="flex items-center gap-2"><GitBranch className="h-4 w-4 text-muted-foreground" /><h3 className="text-sm font-semibold">Workflow simulations</h3></div>
        <Badge variant="secondary" className="text-[10px]">{filtered.length} workflows</Badge>
      </div>
      <p className="px-5 py-3 text-xs text-muted-foreground">Sample data. These controls change this view only; no production workflow is started, paused or completed.</p>
      <ScrollArea className="h-[320px]">
        <div className="divide-y divide-border/30">
          {filtered.map((wf, i) => {
            const StatusIcon = statusIcons[wf.status]
            return (
              <motion.div key={wf.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.08 }}
                onMouseEnter={() => setHoveredId(wf.id)} onMouseLeave={() => setHoveredId(null)}
                className={cn("relative px-5 py-4 transition-all duration-200", hoveredId === wf.id && "bg-muted/30")}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <StatusIcon className={cn("h-4 w-4", wf.status === "running" && "text-success", wf.status === "paused" && "text-warning", wf.status === "completed" && "text-info", wf.status === "stopped" && "text-muted-foreground")} />
                    <span className={cn("text-sm font-medium", wf.status === "stopped" ? "text-muted-foreground" : "text-foreground")}>{wf.name}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">{wf.agents} agents</span>
                    <Button aria-label={`Toggle simulation ${wf.name}`} variant="ghost" size="icon" className="h-7 w-7" onClick={() => toggleWorkflow(wf.id)}>
                      {wf.status === "running" ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
                    </Button>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Progress value={wf.progress} className={cn("h-1.5 flex-1", wf.status === "stopped" && "opacity-30")} />
                  <span className={cn("text-xs font-medium w-8 text-right", wf.status === "stopped" ? "text-muted-foreground/50" : "text-muted-foreground")}>{wf.progress}%</span>
                </div>
                <div className="mt-1.5 flex items-center gap-1">
                  <Clock className={cn("h-3 w-3", wf.status === "stopped" ? "text-muted-foreground/50" : "text-muted-foreground")} />
                  <span className={cn("text-[11px]", wf.status === "stopped" ? "text-muted-foreground/50" : "text-muted-foreground")}>{wf.status === "stopped" ? "Stopped" : wf.lastRun}</span>
                </div>
              </motion.div>
            )
          })}
          {filtered.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-8">No workflows match your search</p>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}
