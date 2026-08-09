"use client"

import { Bot, Package, TrendingUp, Zap } from "lucide-react"
import { MetricCard } from "./MetricCard"
import { useKPIs } from "@/hooks/use-analytics"

export function MetricsPanel() {
  const { data: kpis, loading: kpisLoading } = useKPIs()

  const loading = kpisLoading

  const metrics = loading
    ? [
        { title: "Active Agents", value: "--", change: "--", trend: "up" as const, icon: <Bot className="h-5 w-5" /> },
        { title: "Orders Processed", value: "--", change: "--", trend: "up" as const, icon: <Package className="h-5 w-5" /> },
        { title: "On-Time Delivery", value: "--", change: "--", trend: "up" as const, icon: <Zap className="h-5 w-5" /> },
        { title: "Avg Shipping Cost", value: "--", change: "--", trend: "down" as const, icon: <TrendingUp className="h-5 w-5" /> },
      ]
    : [
        {
          title: "Active Agents",
          value: String(kpis?.total_orders ?? 0),
          change: `${kpis?.orders_shipped ?? 0} shipped`,
          trend: "up" as const,
          icon: <Bot className="h-5 w-5" />,
        },
        {
          title: "Orders Processed",
          value: (kpis?.total_orders ?? 0).toLocaleString(),
          change: `${kpis?.orders_delivered ?? 0} delivered`,
          trend: "up" as const,
          icon: <Package className="h-5 w-5" />,
        },
        {
          title: "On-Time Delivery",
          value: `${(kpis?.on_time_delivery_rate ?? 0).toFixed(1)}%`,
          change: `${kpis?.orders_delayed ?? 0} delayed`,
          trend: ((kpis?.on_time_delivery_rate ?? 0) >= 90 ? "up" : "down") as "up" | "down",
          icon: <Zap className="h-5 w-5" />,
        },
        {
          title: "Avg Shipping Cost",
          value: `$${(kpis?.avg_shipping_cost ?? 0).toFixed(2)}`,
          change: `$${(kpis?.total_shipping_cost ?? 0).toFixed(2)} total`,
          trend: "down" as const,
          icon: <TrendingUp className="h-5 w-5" />,
        },
      ]

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {metrics.map((metric, i) => (
        <MetricCard key={metric.title} {...metric} index={i} />
      ))}
    </div>
  )
}
