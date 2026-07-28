"use client"

import React from "react"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { Bot, CheckCircle, AlertTriangle, PauseCircle, Loader2 } from "lucide-react"

interface Agent {
  id: string; name: string; role: string; status: "active" | "idle" | "error" | "processing"
  uptime: string; tasksCompleted: number; workload: number; accuracy: number
}

interface AgentCardProps { agent: Agent; index: number; onSelect?: (agent: { name: string; role: string }) => void }

const statusConfig: Record<string, { icon: React.ElementType; color: string; bg: string; spin?: boolean }> = {
  active: { icon: CheckCircle, color: "text-accent", bg: "bg-accent/8" },
  idle: { icon: PauseCircle, color: "text-muted-foreground", bg: "bg-muted/30" },
  error: { icon: AlertTriangle, color: "text-destructive", bg: "bg-destructive/8" },
  processing: { icon: Loader2, color: "text-info", bg: "bg-info/8", spin: true },
}

export function AgentCard({ agent, index, onSelect }: AgentCardProps) {
  const cfg = statusConfig[agent.status]

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
          <span className={cn("text-[10px] font-medium uppercase tracking-wider", cfg.color)}>{agent.status}</span>
        </div>
        <p className="text-xs text-muted-foreground truncate">{agent.role}</p>
      </div>
      <div className="flex items-center gap-3 text-[11px] text-muted-foreground shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
        <span title="Workload">{agent.workload}%</span>
        <span title="Accuracy">{agent.accuracy}%</span>
      </div>
    </motion.div>
  )
}
