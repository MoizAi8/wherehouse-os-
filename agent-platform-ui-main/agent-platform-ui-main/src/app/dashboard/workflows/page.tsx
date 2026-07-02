"use client"

import { WorkflowPanel } from "@/components/dashboard/WorkflowPanel"

export default function WorkflowsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Workflows</h1>
        <p className="text-sm text-muted-foreground">Ask AI to manage workflows</p>
      </div>
      <WorkflowPanel />
    </div>
  )
}