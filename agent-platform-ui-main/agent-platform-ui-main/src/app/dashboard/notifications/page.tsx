"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { cn } from "@/lib/utils"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Bell, X, Thermometer, CheckCircle2, AlertTriangle, Info, Bot } from "lucide-react"

interface NotificationItem {
  id: string
  type: "critical" | "warning" | "info" | "success"
  agent: string
  title: string
  message: string
  time: string
}

const allNotifications: NotificationItem[] = [
  { id: "1", type: "critical", agent: "MonitorAgent", title: "Shipment Delay Detected", message: "Order #1024 via FedEx is past estimated delivery by 15.2 hours", time: "2m ago" },
  { id: "2", type: "warning", agent: "MonitorAgent", title: "Order Routing Delay", message: "Shipment #d7ac53 to 90210 is delayed - evaluating alternatives", time: "15m ago" },
  { id: "3", type: "info", agent: "CommunicationAgent", title: "Customer Notification Sent", message: "Delay alert sent to customer ahmed@example.com via email", time: "1h ago" },
  { id: "4", type: "success", agent: "RoutingAgent", title: "Inventory Reconciliation", message: "Inventory reconciliation completed successfully across all zones", time: "2m ago" },
  { id: "5", type: "critical", agent: "CostOptimizer", title: "Anomaly Detected in Zone C", message: "Unusual cost pattern detected - 23% above average for Zone C shipments", time: "2h ago" },
  { id: "6", type: "warning", agent: "PredictionAgent", title: "High Failure Risk", message: "Shipment #1436a4 has 92% failure probability - immediate action needed", time: "30m ago" },
  { id: "7", type: "info", agent: "ReroutingAgent", title: "Shipment Rerouted", message: "Shipment #38a29f rerouted from UPS to DHL - new tracking generated", time: "45m ago" },
  { id: "8", type: "success", agent: "CommunicationAgent", title: "Bulk Notification Sent", message: "24 delay notifications sent to affected customers", time: "3h ago" },
]

const typeConfig = {
  critical: { icon: Thermometer, color: "text-destructive", bg: "bg-destructive/10", border: "border-destructive/20", label: "Critical" },
  warning: { icon: AlertTriangle, color: "text-warning", bg: "bg-warning/10", border: "border-warning/20", label: "Warning" },
  info: { icon: Info, color: "text-info", bg: "bg-info/10", border: "border-info/20", label: "Info" },
  success: { icon: CheckCircle2, color: "text-success", bg: "bg-success/10", border: "border-success/20", label: "Success" },
}

export default function NotificationsPage() {
  const [dismissed, setDismissed] = useState<string[]>([])

  const visible = allNotifications.filter((n) => !dismissed.includes(n.id))

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Notifications</h1>
        <p className="text-sm text-muted-foreground">Ask AI about alerts and notifications</p>
      </div>

      <div className="rounded-xl glass-card">
        <ScrollArea className="h-[520px]">
          <div className="space-y-1 p-3">
            <AnimatePresence>
              {visible.length === 0 && (
                <motion.p
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="text-sm text-muted-foreground text-center py-12"
                >
                  No notifications - all systems running smoothly
                </motion.p>
              )}
              {visible.map((n, i) => {
                const cfg = typeConfig[n.type]
                const Icon = cfg.icon
                return (
                  <motion.div
                    key={n.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, x: 100 }}
                    transition={{ delay: i * 0.04 }}
                    className={cn(
                      "group relative flex items-start gap-4 rounded-lg border px-4 py-3.5 transition-all",
                      cfg.border, cfg.bg
                    )}
                  >
                    <div className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-full", cfg.bg)}>
                      <Icon className={cn("h-4 w-4", cfg.color)} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-sm font-medium text-foreground">{n.title}</span>
                      </div>
                      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                        <Bot className="h-3 w-3" />
                        <span>{n.agent}</span>
                        <span>·</span>
                        <span>{n.time}</span>
                      </div>
                      <p className="text-xs text-muted-foreground/80 mt-1">{n.message}</p>
                    </div>
                  </motion.div>
                )
              })}
            </AnimatePresence>
          </div>
        </ScrollArea>
      </div>
    </div>
  )
}
