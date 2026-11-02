"use client"

import { useMemo } from "react"
import { AgentCard } from "./AgentCard"
import { SkeletonCard } from "@/components/ui/SkeletonCard"
import { ErrorDisplay } from "@/components/ui/ErrorDisplay"
import { useAgentMonitor } from "@/hooks/use-agents"
import { useSearch } from "@/contexts/SearchContext"

export interface AgentInfo {
  id: string
  name: string
  role: string
  status: "active" | "idle" | "error" | "processing" | "unknown"
  uptime: string
  tasksCompleted: number
  workload: number | null
  accuracy: number | null
}

export function AgentStatusGrid({ onAgentSelect }: { onAgentSelect?: (agent: { name: string; role: string }) => void }) {
  const { data: monitorData, loading, error, refetch } = useAgentMonitor()
  const { query } = useSearch()

  const agents = useMemo<AgentInfo[]>(() => {
    if (loading) return []
    return [
      {
        id: "routing",
        name: "RoutingAgent",
        role: "Order Router",
        status: "unknown",
        uptime: "--",
        tasksCompleted: 0,
        workload: null,
        accuracy: null,
      },
      {
        id: "monitor",
        name: "MonitorAgent",
        role: "Shipment Monitor",
        status: "unknown",
        uptime: "--",
        tasksCompleted: monitorData?.shipments_checked ?? 0,
        workload: null,
        accuracy: null,
      },
      {
        id: "prediction",
        name: "PredictionAgent",
        role: "Failure Predictor",
        status: "unknown",
        uptime: "--",
        tasksCompleted: 0,
        workload: null,
        accuracy: null,
      },
      {
        id: "rerouting",
        name: "ReroutingAgent",
        role: "Reroute Handler",
        status: "unknown",
        uptime: "--",
        tasksCompleted: monitorData?.reroutes_initiated ?? 0,
        workload: null,
        accuracy: null,
      },
      {
        id: "communication",
        name: "CommunicationAgent",
        role: "Notification Relay",
        status: "unknown",
        uptime: "--",
        tasksCompleted: monitorData?.notifications_sent ?? 0,
        workload: null,
        accuracy: null,
      },
      { id: "cost", name: "CostOptimizer", role: "Cost Comparison", status: "unknown", uptime: "--", tasksCompleted: 0, workload: null, accuracy: null },
      { id: "orchestrator", name: "FulfillmentOrchestrator", role: "Workflow Coordination", status: "unknown", uptime: "--", tasksCompleted: 0, workload: null, accuracy: null },
    ]
  }, [loading, monitorData])

  const filtered = useMemo(() => {
    if (!query.trim()) return agents
    const q = query.toLowerCase()
    return agents.filter((a) => a.name.toLowerCase().includes(q) || a.role.toLowerCase().includes(q))
  }, [agents, query])

  if (error) {
    return <ErrorDisplay message={error} onRetry={refetch} />
  }

  if (loading) {
    return (
      <div className="space-y-2" aria-busy="true" aria-label="Loading agents">
        <SkeletonCard count={6} />
      </div>
    )
  }

  return (
    <div className="space-y-2" role="list" aria-label="Agent status list">
      <p className="text-xs text-muted-foreground">Component roster. Runtime state, workload and accuracy are unverified.</p>
      {filtered.map((agent, i) => (
        <AgentCard key={agent.id} agent={agent} index={i} onSelect={onAgentSelect} />
      ))}
      {filtered.length === 0 && (
        <p className="text-sm text-muted-foreground text-center py-8">No agents match your search</p>
      )}
    </div>
  )
}
