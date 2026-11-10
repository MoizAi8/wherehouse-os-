"use client"

import { useMemo } from "react"
import { AgentCard } from "./AgentCard"
import { SkeletonCard } from "@/components/ui/SkeletonCard"
import { ErrorDisplay } from "@/components/ui/ErrorDisplay"
import { type AgentRuntimeEvidence, type AgentRuntimeStatus, useAgentMonitor } from "@/hooks/use-agents"
import { useSearch } from "@/contexts/SearchContext"

export interface AgentInfo {
  id: string
  name: string
  role: string
  status: AgentRuntimeStatus
  evidence?: string
  execution?: AgentRuntimeEvidence
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
    const roster: AgentInfo[] = [
      {
        id: "routing",
        name: "RoutingAgent",
        role: "Order Router",
        status: "UNVERIFIED",
        uptime: "--",
        tasksCompleted: 0,
        workload: null,
        accuracy: null,
      },
      {
        id: "monitor",
        name: "MonitorAgent",
        role: "Shipment Monitor",
        status: "UNVERIFIED",
        uptime: "--",
        tasksCompleted: monitorData?.shipments_checked ?? 0,
        workload: null,
        accuracy: null,
      },
      {
        id: "prediction",
        name: "PredictionAgent",
        role: "Failure Predictor",
        status: "UNVERIFIED",
        uptime: "--",
        tasksCompleted: 0,
        workload: null,
        accuracy: null,
      },
      {
        id: "rerouting",
        name: "ReroutingAgent",
        role: "Reroute Handler",
        status: "UNVERIFIED",
        uptime: "--",
        tasksCompleted: monitorData?.reroutes_initiated ?? 0,
        workload: null,
        accuracy: null,
      },
      {
        id: "communication",
        name: "CommunicationAgent",
        role: "Notification Relay",
        status: "UNVERIFIED",
        uptime: "--",
        tasksCompleted: monitorData?.notifications_sent ?? 0,
        workload: null,
        accuracy: null,
      },
      { id: "cost", name: "CostOptimizer", role: "Cost Comparison", status: "UNVERIFIED", uptime: "--", tasksCompleted: 0, workload: null, accuracy: null },
      { id: "orchestrator", name: "FulfillmentOrchestrator", role: "Workflow Coordination", status: "UNVERIFIED", uptime: "--", tasksCompleted: 0, workload: null, accuracy: null },
    ]
    return roster.map(agent => {
      const evidence = monitorData?.agents?.find(item => item.name === agent.name)
      return { ...agent, status: evidence?.status ?? "UNVERIFIED", execution: evidence,
        evidence: evidence ? `${evidence.reason}${evidence.observed_at ? ` (${evidence.observed_at})` : ""}` : "No execution evidence" }
    })
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
      <p className="text-xs text-muted-foreground">Status reflects recorded execution evidence. Live workload and accuracy are not measured.</p>
      <button type="button" onClick={refetch} className="text-xs text-accent hover:underline">Refresh agent status</button>
      {filtered.map((agent, i) => (
        <AgentCard key={agent.id} agent={agent} index={i} onSelect={onAgentSelect} />
      ))}
      {filtered.length === 0 && (
        <p className="text-sm text-muted-foreground text-center py-8">No agents match your search</p>
      )}
    </div>
  )
}
