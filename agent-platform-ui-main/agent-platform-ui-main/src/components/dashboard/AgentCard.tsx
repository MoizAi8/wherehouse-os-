"use client"

import React from "react"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { CheckCircle, AlertTriangle, PauseCircle, Loader2 } from "lucide-react"

import type { AgentRuntimeEvidence, AgentRuntimeStatus } from "@/hooks/use-agents"

interface Agent {
  id: string; name: string; role: string; status: AgentRuntimeStatus; evidence?: string
  execution?: AgentRuntimeEvidence
  uptime: string; tasksCompleted: number; workload: number | null; accuracy: number | null
}

interface AgentCardProps { agent: Agent; index: number; onSelect?: (agent: { name: string; role: string }) => void }

const statusConfig: Record<string, { icon: React.ElementType; color: string; bg: string; spin?: boolean }> = {
  READY: { icon: CheckCircle, color: "text-accent", bg: "bg-accent/8" },
  IDLE: { icon: PauseCircle, color: "text-muted-foreground", bg: "bg-muted/30" },
  FAILED: { icon: AlertTriangle, color: "text-destructive", bg: "bg-destructive/8" },
  RUNNING: { icon: Loader2, color: "text-info", bg: "bg-info/8", spin: true },
  UNAVAILABLE: { icon: AlertTriangle, color: "text-muted-foreground", bg: "bg-muted/30" },
  UNVERIFIED: { icon: PauseCircle, color: "text-muted-foreground", bg: "bg-muted/30" },
}

export function AgentCard({ agent, index, onSelect }: AgentCardProps) {
  const cfg = statusConfig[agent.status] ?? statusConfig.UNVERIFIED

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.05, duration: 0.3, ease: [0.25, 0.1, 0.25, 1] }}
      onClick={() => onSelect?.({ name: agent.name, role: agent.role })}
      className="flex items-center gap-3 rounded-lg glass-card cursor-pointer px-4 py-3 hover:border-accent/20 transition-all group"
    >
      <div className={cn("flex h-8 w-8 items-center justify-center rounded-lg shrink-0", cfg.bg)}>
        <cfg.icon className={cn("h-4 w-4", cfg.color, cfg.spin && "animate-spin")} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-foreground truncate">{agent.name}</h3>
          <span title={agent.evidence} className={cn("text-[10px] font-medium uppercase tracking-wider", cfg.color)}>{agent.status.toLowerCase()}</span>
        </div>
        <p className="text-xs text-muted-foreground truncate">{agent.role}</p>
        {agent.execution?.event_id && (
          <details className="mt-1 text-xs text-muted-foreground" onClick={event => event.stopPropagation()}>
            <summary className="cursor-pointer">Last execution</summary>
            <p>{agent.execution.event_type?.replaceAll("_", " ")} · <time dateTime={agent.execution.observed_at ?? undefined}>{agent.execution.observed_at}</time></p>
            <p className="break-all">Event {agent.execution.event_id}</p>
            {agent.execution.entity_id && <p className="break-all">Related record {agent.execution.entity_id}</p>}
            {Object.entries(agent.execution.outcome ?? {}).map(([key, value]) => (
              <p key={key}>{key.replaceAll("_", " ")}: {String(value)}</p>
            ))}
          </details>
        )}
      </div>
      <div className="flex items-center gap-3 text-[11px] text-muted-foreground shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
        <span title="Workload">{agent.workload === null ? "—" : `${agent.workload}%`}</span>
        <span title="Accuracy">{agent.accuracy === null ? "—" : `${agent.accuracy}%`}</span>
      </div>
    </motion.div>
  )
}
