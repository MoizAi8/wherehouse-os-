"use client"

import { AgentStatusGrid } from "@/components/dashboard/AgentStatusGrid"
import { EvaluationRun } from "@/components/dashboard/EvaluationRun"
import { ErrorBoundary } from "@/components/ui/ErrorBoundary"

export default function AgentsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Agents</h1>
        <p className="text-sm text-muted-foreground">Ask AI to monitor and control agents</p>
      </div>
      {process.env.NEXT_PUBLIC_INSTRUCTOR_WORKSPACE === "1" && <EvaluationRun />}
      <ErrorBoundary>
        <AgentStatusGrid />
      </ErrorBoundary>
    </div>
  )
}
