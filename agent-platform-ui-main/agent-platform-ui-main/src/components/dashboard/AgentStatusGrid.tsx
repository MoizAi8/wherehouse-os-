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
  status: "active" | "idle" | "error" | "processing"
  uptime: string
  tasksCompleted: number
  workload: number
  accuracy: number
}

export function AgentStatusGrid({ onAgentSelect }: { onAgentSelect?: (agent: { name: string; role: string }) => void }) {
  const { data: monitorData, loading, error, refetch } = useAgentMonitor()
  const { query } = useSearch()

  const delaysDetected = monitorData?.delays_detected ?? 0
  const agents: AgentInfo[] = loading
    ? []
    : [
        {
          id: "routing",
          name: "RoutingAgent",
          role: "Order Router",
          status: "active",
          uptime: "--",
          tasksCompleted: 0,
          workload: 0,
          accuracy: 0,
        },
        {
          id: "monitor",
          name: "MonitorAgent",
          role: "Shipment Monitor",
          status: "processing",
          uptime: "--",
          tasksCompleted: monitorData?.shipments_checked ?? 0,
          workload: 0,
          accuracy: 0,
        },
        {
          id: "prediction",
          name: "PredictionAgent",
          role: "Failure Predictor",
          status: "processing",
          uptime: "--",
          tasksCompleted: delaysDetected,
          workload: 0,
          accuracy: 0,
        },
        {
          id: "rerouting",
          name: "ReroutingAgent",
          role: "Reroute Handler",
          status: delaysDetected > 0 ? "active" : "idle",
          uptime: "--",
          tasksCompleted: monitorData?.reroutes_initiated ?? 0,
          workload: 0,
          accuracy: 0,
        },
        {
          id: "communication",
          name: "CommunicationAgent",
          role: "Notification Relay",
          status: "active",
          uptime: "--",
          tasksCompleted: monitorData?.notifications_sent ?? 0,
          workload: 0,
          accuracy: 0,
        },
      ]

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
      {filtered.map((agent, i) => (
        <AgentCard key={agent.id} agent={agent} index={i} onSelect={onAgentSelect} />
      ))}
      {filtered.length === 0 && (
        <p className="text-sm text-muted-foreground text-center py-8">No agents match your search</p>
      )}
    </div>
  )
}
