"use client"

import { useMemo } from "react"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { Bot, CheckCircle2, AlertTriangle, Info, ArrowRight } from "lucide-react"
import { useAgentMonitor } from "@/hooks/use-agents"
import { useSearch } from "@/contexts/SearchContext"

interface LogEntry {
  id: string
  type: "success" | "warning" | "info" | "error"
  agent: string
  message: string
  time: string
}

const typeConfig = {
  success: { icon: CheckCircle2, color: "text-success", bg: "bg-success/10" },
  warning: { icon: AlertTriangle, color: "text-warning", bg: "bg-warning/10" },
  info: { icon: Info, color: "text-info", bg: "bg-info/10" },
  error: { icon: AlertTriangle, color: "text-destructive", bg: "bg-destructive/10" },
}

export function ActivityLog() {
  const { data: monitorData, loading } = useAgentMonitor()
  const { query } = useSearch()

  const logs = useMemo<LogEntry[]>(() => {
    if (loading || !monitorData) return []
    return [
      {
        id: "1",
        type: "success" as const,
        agent: "System",
        message: `Monitor cycle completed — ${monitorData.shipments_checked} shipments checked`,
        time: new Date(monitorData.completed_at).toLocaleTimeString(),
      },
      ...(monitorData.delays_detected > 0
        ? [
            {
              id: "2",
              type: "warning" as const,
              agent: "MonitorAgent",
              message: `${monitorData.delays_detected} delays detected — rerouting initiated`,
              time: new Date(monitorData.completed_at).toLocaleTimeString(),
            },
          ]
        : []),
      ...(monitorData.reroutes_initiated > 0
        ? [
            {
              id: "3",
              type: "info" as const,
              agent: "ReroutingAgent",
              message: `${monitorData.reroutes_initiated} reroutes initiated`,
              time: new Date(monitorData.completed_at).toLocaleTimeString(),
            },
          ]
        : []),
      ...(monitorData.notifications_sent > 0
        ? [
            {
              id: "4",
              type: "info" as const,
              agent: "CommunicationAgent",
              message: `${monitorData.notifications_sent} notifications sent`,
              time: new Date(monitorData.completed_at).toLocaleTimeString(),
            },
          ]
        : []),
      ...(monitorData.anomalies_found > 0
        ? [
            {
              id: "5",
              type: "error" as const,
              agent: "CostOptimizer",
              message: `${monitorData.anomalies_found} anomalies found in current cycle`,
              time: new Date(monitorData.completed_at).toLocaleTimeString(),
            },
          ]
        : []),
    ]
  }, [loading, monitorData])

  const filtered = useMemo(() => {
    if (!query.trim()) return logs
    const q = query.toLowerCase()
    return logs.filter((l) => l.agent.toLowerCase().includes(q) || l.message.toLowerCase().includes(q))
  }, [logs, query])

  return (
    <div className="rounded-xl glass-card">
      <div className="flex items-center justify-between border-b border-border/30 px-5 py-3">
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold">Activity Log</h3>
        </div>
        <Badge variant="secondary" className="text-[10px]">Live</Badge>
      </div>
      <ScrollArea className="h-[320px]">
        <div className="space-y-1 p-2">
          {filtered.map((log, i) => {
            const config = typeConfig[log.type]
            const Icon = config.icon
            return (
              <motion.div
                key={log.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.05 }}
                className="group flex items-start gap-3 rounded-lg px-3 py-2.5 transition-colors hover:bg-muted/50"
              >
                <div className={cn("flex h-7 w-7 shrink-0 items-center justify-center rounded-full", config.bg)}>
                  <Icon className={cn("h-3.5 w-3.5", config.color)} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-foreground">{log.agent}</span>
                    <ArrowRight className="h-2.5 w-2.5 text-muted-foreground" />
                    <span className="text-xs text-muted-foreground truncate">{log.message}</span>
                  </div>
                </div>
                <span className="shrink-0 text-[11px] text-muted-foreground">{log.time}</span>
              </motion.div>
            )
          })}
          {!loading && filtered.length === 0 && (
            <p className="text-xs text-muted-foreground text-center py-8">{query ? "No activity matches your search" : "Run a monitor cycle to see activity"}</p>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}
