"use client"

import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { Bot } from "lucide-react"

interface Agent {
  id: string; name: string; role: string; status: "active" | "idle" | "error" | "processing"
  uptime: string; tasksCompleted: number; workload: number; accuracy: number
}

interface AgentCardProps { agent: Agent; index: number }

export function AgentCard({ agent, index }: AgentCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.05, duration: 0.3, ease: [0.25, 0.1, 0.25, 1] }}
      className="flex items-center gap-3 rounded-lg glass-card cursor-pointer px-4 py-3"
    >
      <div className="flex h-7 w-7 items-center justify-center rounded-lg glass-card-strong">
        <Bot className="h-3.5 w-3.5 text-accent" />
      </div>
      <h3 className="text-sm font-semibold text-foreground">{agent.name}</h3>
      <span className="text-xs text-muted-foreground">— {agent.role}</span>
    </motion.div>
  )
}
