"use client"

import { AgentStatusGrid } from "@/components/dashboard/AgentStatusGrid"
import { ErrorBoundary } from "@/components/ui/ErrorBoundary"

export default function AgentsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Agents</h1>
        <p className="text-sm text-muted-foreground">Ask AI to monitor and control agents</p>
      </div>
      <ErrorBoundary>
        <AgentStatusGrid />
      </ErrorBoundary>
    </div>
  )
}