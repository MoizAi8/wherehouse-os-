"use client"

import { AnalyticsCharts } from "@/components/dashboard/AnalyticsCharts"

export default function AnalyticsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Analytics</h1>
        <p className="text-sm text-muted-foreground">Ask AI for insights and metrics</p>
      </div>
      <AnalyticsCharts />
    </div>
  )
}