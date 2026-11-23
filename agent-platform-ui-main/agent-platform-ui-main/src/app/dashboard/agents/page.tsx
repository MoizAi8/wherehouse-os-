"use client"

import { AgentStatusGrid } from "@/components/dashboard/AgentStatusGrid"
import { useSession } from "next-auth/react"
import { EvaluationRun } from "@/components/dashboard/EvaluationRun"
import { ErrorBoundary } from "@/components/ui/ErrorBoundary"

export default function AgentsPage() {
  const {data: session} = useSession()
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Agents</h1>
        <p className="text-sm text-muted-foreground">Ask AI to monitor and control agents</p>
      </div>
      {(session?.instructorWorkspace || process.env.NEXT_PUBLIC_INSTRUCTOR_WORKSPACE === "1") && <EvaluationRun hosted={!!session?.instructorWorkspace} />}
      <ErrorBoundary>
        <AgentStatusGrid />
      </ErrorBoundary>
    </div>
  )
}
