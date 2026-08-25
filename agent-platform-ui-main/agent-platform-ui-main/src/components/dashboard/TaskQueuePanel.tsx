"use client"

import { useMemo } from "react"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { ListTodo, ArrowRight, Package, ClipboardCheck, Truck, ScanLine } from "lucide-react"
import { useShipments } from "@/hooks/use-shipments"
import { useSearch } from "@/contexts/SearchContext"

interface Task {
  id: string
  title: string
  agent: string
  priority: "high" | "medium" | "low"
  status: "pending" | "in-progress" | "completed"
  type: "pick" | "pack" | "ship" | "audit"
  time: string
}

const priorityColors = {
  high: "text-destructive border-destructive/30 bg-destructive/10",
  medium: "text-warning border-warning/30 bg-warning/10",
  low: "text-info border-info/30 bg-info/10",
}

const typeIcons = { pick: ScanLine, pack: Package, ship: Truck, audit: ClipboardCheck }

function getTaskFromShipment(shipment: {
  id: string
  status: string
  carrier_name: string
  is_delayed: boolean
  created_at: string
}): Task {
  const statusMap: Record<string, Task["status"]> = {
    created: "pending",
    picked: "in-progress",
    packed: "in-progress",
    shipped: "in-progress",
    delivered: "completed",
    delayed: "pending",
  }

  const typeMap: Record<string, Task["type"]> = {
    created: "pick",
    picked: "pack",
    packed: "ship",
    shipped: "ship",
    delivered: "audit",
    delayed: "pick",
  }

  const priority: Task["priority"] = shipment.is_delayed ? "high" : shipment.status === "shipped" ? "medium" : "low"

  const diff = Date.now() - new Date(shipment.created_at).getTime()
  const minutes = Math.floor(diff / 60000)
  const timeAgo = minutes < 60 ? `${minutes}m ago` : `${Math.floor(minutes / 60)}h ago`

  return {
    id: shipment.id.slice(0, 8),
    title: `Shipment via ${shipment.carrier_name}`,
    agent: shipment.is_delayed ? "ReroutingAgent" : "MonitorAgent",
    priority,
    status: statusMap[shipment.status] ?? "pending",
    type: typeMap[shipment.status] ?? "ship",
    time: timeAgo,
  }
}

export function TaskQueuePanel() {
  const { data: shipments, loading } = useShipments()
  const { query } = useSearch()

  const tasks = useMemo<Task[]>(() => {
    if (loading) return []
    return (shipments ?? []).slice(0, 6).map(getTaskFromShipment)
  }, [loading, shipments])

  const filtered = useMemo(() => {
    if (!query.trim()) return tasks
    const q = query.toLowerCase()
    return tasks.filter((t) => t.title.toLowerCase().includes(q) || t.agent.toLowerCase().includes(q) || t.id.toLowerCase().includes(q))
  }, [tasks, query])

  return (
    <div className="rounded-xl glass-card">
      <div className="flex items-center justify-between border-b border-border/30 px-5 py-3">
        <div className="flex items-center gap-2">
          <ListTodo className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold">Task Queue</h3>
          <Badge variant="secondary" className="text-[10px] ml-1">{filtered.length}</Badge>
        </div>
        <Button variant="ghost" size="sm" className="h-7 text-xs gap-1">
          View All <ArrowRight className="h-3 w-3" />
        </Button>
      </div>
      <ScrollArea className="h-[320px]">
        <div className="space-y-1 p-2">
          {filtered.map((task, i) => {
            const TypeIcon = typeIcons[task.type]
            return (
              <motion.div
                key={task.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.04 }}
                className="group flex items-start gap-3 rounded-lg px-3 py-2.5 transition-colors hover:bg-muted/50"
              >
                <div
                  className={cn(
                    "flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border",
                    task.status === "completed"
                      ? "border-success/30 bg-success/10 text-success"
                      : "border-border/50 bg-muted/50 text-muted-foreground"
                  )}
                >
                  <TypeIcon className="h-3.5 w-3.5" />
                </div>
                <div className="flex-1 min-w-0">
                  <span
                    className={cn(
                      "text-xs font-medium",
                      task.status === "completed" ? "text-muted-foreground line-through" : "text-foreground"
                    )}
                  >
                    {task.title}
                  </span>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-[11px] text-muted-foreground">{task.id}</span>
                    <span className="text-[11px] text-muted-foreground">·</span>
                    <span className="text-[11px] text-muted-foreground">{task.agent}</span>
                    <span className="text-[11px] text-muted-foreground">·</span>
                    <span className={cn("text-[10px] font-medium px-1.5 py-0.5 rounded-full border", priorityColors[task.priority])}>
                      {task.priority}
                    </span>
                  </div>
                </div>
                <span className="shrink-0 text-[11px] text-muted-foreground">{task.time}</span>
              </motion.div>
            )
          })}
          {!loading && filtered.length === 0 && (
            <p className="text-xs text-muted-foreground text-center py-8">{query ? "No tasks match your search" : "No shipments yet"}</p>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}
