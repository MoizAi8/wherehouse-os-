"use client"

import { useOrders, type Order } from "@/hooks/use-orders"
import { motion } from "framer-motion"
import { ShoppingCart, RefreshCw, Package, Truck, CheckCircle2, Clock, XCircle } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { SkeletonCard } from "@/components/ui/SkeletonCard"

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

const rowVariants = {
  hidden: { opacity: 0, x: -12 },
  visible: (i: number) => ({
    opacity: 1,
    x: 0,
    transition: { delay: i * 0.04, duration: 0.35, ease: "easeOut" as const },
  }),
}

function OrderRow({ order, index }: { order: Order; index: number }) {
  return (
    <motion.tr
      custom={index}
      variants={rowVariants}
      initial="hidden"
      animate="visible"
      whileHover={{ backgroundColor: "rgba(255,255,255,0.03)", transition: { duration: 0.2 } }}
      className="border-b border-border/30 transition-colors cursor-pointer"
    >
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
    </motion.tr>
  )
}

export default function OrdersPage() {
  const { data, loading, error, refetch } = useOrders()

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.25, 0.1, 0.25, 1] }}
      className="space-y-6"
    >
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-accent to-primary shadow-lg">
            <ShoppingCart className="h-4 w-4 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-[22px] font-bold tracking-tight text-foreground">Orders</h1>
              {data && (
                <Badge variant="secondary" className="text-[10px] font-medium">
                  {data.total} total
                </Badge>
              )}
            </div>
            <p className="text-sm text-muted-foreground/80 mt-0.5">Manage and track all customer orders</p>
          </div>
        </div>
        <Button variant="outline" size="sm" className="h-8 gap-1.5 text-xs rounded-xl" onClick={refetch} disabled={loading}>
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          {loading ? "Loading..." : "Refresh"}
        </Button>
      </motion.div>

      {error && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive"
        >
          {error}
        </motion.div>
      )}

      {loading && !data && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <motion.div key={i} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.1 }}>
              <SkeletonCard className="h-14" />
            </motion.div>
          ))}
        </div>
      )}

      {data && data.orders.length === 0 && (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="flex flex-col items-center justify-center py-20 text-center"
        >
          <motion.div
            animate={{ rotate: [0, 10, -10, 0] }}
            transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
            className="flex h-12 w-12 items-center justify-center rounded-xl bg-muted mb-4"
          >
            <Package className="h-6 w-6 text-muted-foreground" />
          </motion.div>
          <h3 className="text-sm font-medium text-foreground">No orders yet</h3>
          <p className="text-xs text-muted-foreground mt-1">
            AI Chat se order banao: &ldquo;Create order for ahmed@gmail.com, ship to Lahore, weight 3kg&rdquo;
          </p>
        </motion.div>
      )}

      {data && data.orders.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="rounded-xl border border-border/40 bg-card/50 backdrop-blur-sm overflow-hidden"
        >
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border/30 bg-muted/20">
                  {["Order ID", "Customer", "Destination", "Weight", "Status", "Date"].map((h, i) => (
                    <th key={h} className="text-left py-3 px-4 text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                      <motion.span
                        initial={{ opacity: 0, y: -4 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.1 + i * 0.05 }}
                      >
                        {h}
                      </motion.span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.orders.map((order, i) => (
                  <OrderRow key={order.id} order={order} index={i} />
                ))}
              </tbody>
            </table>
          </div>
        </motion.div>
      )}
    </motion.div>
  )
}
