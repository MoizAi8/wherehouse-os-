"use client"

import { Activity, Server, Cpu, HardDrive, Wifi } from "lucide-react"

const metrics = [
  { icon: Server, label: "API Latency", value: "47ms", status: "good" },
  { icon: Cpu, label: "CPU Usage", value: "34%", status: "good" },
  { icon: HardDrive, label: "Memory", value: "62%", status: "warning" },
  { icon: Wifi, label: "Network I/O", value: "1.2 Gbps", status: "good" },
  { icon: Activity, label: "Error Rate", value: "0.03%", status: "good" },
]

const agents = [
  { name: "Order Router", status: "active", uptime: "99.98%", tasks: 1243 },
  { name: "Inventory Monitor", status: "active", uptime: "99.95%", tasks: 892 },
  { name: "Cost Optimizer", status: "active", uptime: "99.99%", tasks: 567 },
  { name: "Demand Predictor", status: "active", uptime: "99.87%", tasks: 345 },
  { name: "Rerouting Agent", status: "idle", uptime: "99.91%", tasks: 78 },
  { name: "Quality Checker", status: "active", uptime: "99.93%", tasks: 2101 },
]

export default function MonitoringPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Monitoring</h1>
        <p className="text-sm text-muted-foreground">Ask AI for system health and performance</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
        {metrics.map((m) => {
          const Icon = m.icon
          return (
            <div key={m.label} className="rounded-xl border border-border/50 bg-card p-4">
              <div className="flex items-center gap-2 mb-2">
                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-muted">
                  <Icon className="h-3.5 w-3.5 text-muted-foreground" />
                </div>
                <span className="text-xs font-medium text-muted-foreground">{m.label}</span>
              </div>
              <p className="text-xl font-bold text-foreground">{m.value}</p>
            </div>
          )
        })}
      </div>

      <div className="rounded-xl border border-border/50 bg-card overflow-hidden">
        <div className="border-b border-border/30 bg-muted/30 px-5 py-3">
          <h2 className="text-sm font-semibold text-foreground">Agent Status</h2>
        </div>
        <div className="divide-y divide-border/30">
          {agents.map((agent) => (
            <div key={agent.name} className="flex items-center justify-between px-5 py-3">
              <div>
                <span className="text-sm font-medium text-foreground">{agent.name}</span>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span className={`h-1.5 w-1.5 rounded-full ${agent.status === "active" ? "bg-emerald-500" : "bg-gray-400"}`} />
                  <span className="text-[10px] text-muted-foreground">{agent.status}</span>
                </div>
              </div>
              <div className="flex items-center gap-6 text-xs text-muted-foreground">
                <span>Uptime: <span className="text-foreground/80 font-medium">{agent.uptime}</span></span>
                <span>Tasks: <span className="text-foreground/80 font-medium">{agent.tasks.toLocaleString()}</span></span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
