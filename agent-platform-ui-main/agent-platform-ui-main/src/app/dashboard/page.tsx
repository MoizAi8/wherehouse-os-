"use client"

import { Suspense, useState } from "react"
import { motion } from "framer-motion"
import { AgentStatusGrid } from "@/components/dashboard/AgentStatusGrid"
import { AgentCard } from "@/components/dashboard/AgentCard"
import { SkeletonCard } from "@/components/ui/SkeletonCard"
import { ErrorBoundary } from "@/components/ui/ErrorBoundary"
import { AIAssistant } from "@/components/ai/AIAssistant"
import { Bot, Sparkles, Package, Activity, TrendingUp, Clock, CheckCircle, AlertTriangle, PauseCircle } from "lucide-react"
import { cn } from "@/lib/utils"

const metrics = [
  { icon: Bot, label: "Active Agents", value: "8", change: "+2", positive: true },
  { icon: Activity, label: "Tasks Today", value: "147", change: "+12.5%", positive: true },
  { icon: TrendingUp, label: "Success Rate", value: "98.2%", change: "+0.3%", positive: true },
  { icon: Clock, label: "Avg Response", value: "1.2s", change: "-0.1s", positive: true },
]

const agentSummary = [
  { icon: CheckCircle, label: "Active", count: 5, color: "text-accent" },
  { icon: AlertTriangle, label: "Error", count: 1, color: "text-destructive" },
  { icon: PauseCircle, label: "Idle", count: 1, color: "text-muted-foreground" },
  { icon: Activity, label: "Processing", count: 1, color: "text-info" },
]

function PanelSkeleton() {
  return <SkeletonCard className="h-64" />
}

function MetricsGrid() {
  return (
    <>
      <div className="grid grid-cols-4 gap-4 mb-4">
        {metrics.map((metric, i) => (
          <motion.div
            key={metric.label}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 + i * 0.05, duration: 0.4 }}
            className="glass-card rounded-xl p-4"
          >
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent/8">
                <metric.icon className="h-4 w-4 text-accent" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs text-muted-foreground">{metric.label}</p>
                <div className="flex items-center gap-2">
                  <span className="text-lg font-bold tracking-tight text-foreground">{metric.value}</span>
                  <span className={`text-[11px] font-medium ${metric.positive ? "text-accent" : "text-destructive"}`}>
                    {metric.change}
                  </span>
                </div>
              </div>
            </div>
          </motion.div>
        ))}
      </div>

      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3, duration: 0.4 }}
        className="flex items-center gap-3 mb-6 px-4 py-2.5 rounded-xl glass-card-strong"
      >
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Agent Session</span>
        <div className="h-4 w-px bg-border/40" />
        {agentSummary.map((s) => (
          <div key={s.label} className="flex items-center gap-1.5">
            <s.icon className={cn("h-3 w-3", s.color)} />
            <span className="text-xs text-foreground font-medium">{s.count}</span>
            <span className="text-[10px] text-muted-foreground">{s.label}</span>
          </div>
        ))}
      </motion.div>
    </>
  )
}

export default function DashboardPage() {
  const [selectedAgent, setSelectedAgent] = useState<{ name: string; role: string } | null>(null)

  return (
    <div className="flex flex-1 flex-col p-6 h-full overflow-hidden">
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="flex items-center gap-3 mb-6"
      >
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-accent to-primary shadow-lg shadow-accent/20">
          <Package className="h-5 w-5 text-background" />
        </div>
        <div>
          <h1 className="text-base font-semibold tracking-tight text-foreground">Warehouse OS</h1>
          <p className="text-xs text-muted-foreground">Monitor agents and manage operations</p>
        </div>
      </motion.div>

      <MetricsGrid />

      <div className="flex-1 flex overflow-hidden min-h-0 rounded-xl border border-border/30 glass-card">
        <div className="w-[380px] border-r border-border/20 flex flex-col min-h-0 shrink-0">
          <div className="flex items-center gap-2 px-5 pt-5 pb-3 shrink-0">
            <Sparkles className="h-3.5 w-3.5 text-accent" />
            <h2 className="text-xs font-semibold text-foreground uppercase tracking-wider">Agent Status</h2>
          </div>
          <div className="flex-1 overflow-y-auto px-5 pb-5 min-h-0">
            <ErrorBoundary>
              <Suspense fallback={<PanelSkeleton />}>
                <AgentStatusGrid onAgentSelect={setSelectedAgent} />
              </Suspense>
            </ErrorBoundary>
          </div>
        </div>
        <div className="flex-1 flex flex-col min-h-0">
          <AIAssistant initialContext={selectedAgent} />
        </div>
      </div>
    </div>
  )
}
