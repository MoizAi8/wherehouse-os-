"use client"

import { useMemo } from "react"
import { AgentCard } from "./AgentCard"
import { SkeletonCard } from "@/components/ui/SkeletonCard"
import { ErrorDisplay } from "@/components/ui/ErrorDisplay"
import { useAgentMonitor } from "@/hooks/use-agents"
import { useOrders } from "@/hooks/use-orders"
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
  const { data: ordersData } = useOrders({ limit: 100 })
  const { query } = useSearch()

  const agents: AgentInfo[] = loading
    ? []
    : [
        {
          id: "1",
          name: "RoutingAgent",
          role: "Order Router",
          status: "active",
          uptime: "--",
          tasksCompleted: monitorData?.shipments_checked ?? 0,
          workload: 72,
          accuracy: 98,
        },
        {
          id: "2",
          name: "MonitorAgent",
          role: "Shipment Monitor",
          status: "processing",
          uptime: "--",
          tasksCompleted: ordersData?.total ?? 0,
          workload: 88,
          accuracy: 96,
        },
        {
          id: "3",
          name: "PredictionAgent",
          role: "Failure Predictor",
          status: "active",
          uptime: "--",
          tasksCompleted: monitorData?.delays_detected ?? 0,
          workload: 45,
          accuracy: 94,
        },
        {
          id: "4",
          name: "CostOptimizer",
          role: "Cost Analyst",
          status: (monitorData?.anomalies_found ?? 0) > 0 ? "error" : "idle",
          uptime: "--",
          tasksCompleted: monitorData?.anomalies_found ?? 0,
          workload: 15,
          accuracy: 99,
        },
        {
          id: "5",
          name: "ReroutingAgent",
          role: "Reroute Handler",
          status: "active",
          uptime: "--",
          tasksCompleted: monitorData?.reroutes_initiated ?? 0,
          workload: 63,
          accuracy: 97,
        },
        {
          id: "6",
          name: "CommunicationAgent",
          role: "Notification Relay",
          status: "active",
          uptime: "--",
          tasksCompleted: monitorData?.notifications_sent ?? 0,
          workload: 30,
          accuracy: 88,
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
