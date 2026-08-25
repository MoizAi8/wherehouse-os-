"use client"

import { useOrders } from "@/hooks/use-orders"
import { motion } from "framer-motion"
import { Package, Truck, CheckCircle2, Clock, XCircle } from "lucide-react"

const statusConfig: Record<string, { icon: typeof Clock; style: string }> = {
  pending: { icon: Clock, style: "bg-amber-500/10 text-amber-500 border-amber-500/20" },
  confirmed: { icon: CheckCircle2, style: "bg-blue-500/10 text-blue-500 border-blue-500/20" },
  processing: { icon: Truck, style: "bg-blue-500/10 text-blue-500 border-blue-500/20" },
  shipped: { icon: Truck, style: "bg-accent/10 text-accent border-accent/20" },
  delivered: { icon: CheckCircle2, style: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20" },
  cancelled: { icon: XCircle, style: "bg-red-500/10 text-red-500 border-red-500/20" },
}

function StatusBadge({ status }: { status: string }) {
  const config = statusConfig[status]
  if (!config) return <span className="text-xs text-muted-foreground">{status}</span>
  const Icon = config.icon
  return (
    <motion.span
      initial={{ scale: 0.8, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${config.style}`}
    >
      <Icon className="h-3 w-3" />
      {status}
    </motion.span>
  )
}

export default function OrdersPage() {
  const { data, loading, error } = useOrders()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">
          Orders {data ? `(${data.total})` : ""}
        </h1>
        <p className="text-sm text-muted-foreground">Browse orders or ask the AI to create and manage them</p>
      </div>

      {error && (
        <div className="rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {loading && !data && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-14 rounded-xl bg-muted/20 animate-pulse" />
          ))}
        </div>
      )}

      {data && data.orders.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-muted mb-4">
            <Package className="h-6 w-6 text-muted-foreground" />
          </div>
          <h3 className="text-sm font-medium text-foreground">No orders yet</h3>
          <p className="text-xs text-muted-foreground mt-1">Ask the AI to create one, or create it here.</p>
        </div>
      )}

      {data && data.orders.length > 0 && (
        <div className="rounded-xl border border-border/40 bg-card/50 backdrop-blur-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border/30 bg-muted/20">
                  {["Order ID", "Customer", "Destination", "Weight", "Status", "Date"].map((h) => (
                    <th key={h} className="text-left py-3 px-4 text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.orders.map((order) => (
                  <tr key={order.id} className="border-b border-border/30 transition-colors">
                    <td className="py-3 px-4">
                      <span className="text-xs font-mono text-muted-foreground">#{order.id.slice(0, 8)}</span>
                    </td>
                    <td className="py-3 px-4 text-sm text-foreground">{order.customer_email}</td>
                    <td className="py-3 px-4 text-sm text-muted-foreground">
                      {order.shipping_city}, {order.shipping_state}
                    </td>
                    <td className="py-3 px-4 text-sm text-muted-foreground">{order.total_weight_kg} kg</td>
                    <td className="py-3 px-4"><StatusBadge status={order.status} /></td>
                    <td className="py-3 px-4 text-xs text-muted-foreground">
                      {new Date(order.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}