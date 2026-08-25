"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { cn } from "@/lib/utils"
import { Bell, Search, ChevronDown, Settings, X, CheckCircle2, AlertTriangle, Info } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useSearch } from "@/contexts/SearchContext"

interface NotificationItem {
  id: string
  type: "success" | "warning" | "info" | "error"
  agent: string
  message: string
  time: string
}

const notifications: NotificationItem[] = [
  { id: "1", type: "success", agent: "RoutingAgent", message: "Inventory reconciliation completed", time: "2m ago" },
  { id: "2", type: "warning", agent: "MonitorAgent", message: "Order routing delay detected", time: "15m ago" },
  { id: "3", type: "info", agent: "CommunicationAgent", message: "Customer notification sent", time: "1h ago" },
  { id: "4", type: "error", agent: "CostOptimizer", message: "Anomaly detected in Zone C", time: "2h ago" },
]

const notifStyles = {
  success: { icon: CheckCircle2, color: "text-success", bg: "bg-success/10" },
  warning: { icon: AlertTriangle, color: "text-warning", bg: "bg-warning/10" },
  info: { icon: Info, color: "text-info", bg: "bg-info/10" },
  error: { icon: AlertTriangle, color: "text-destructive", bg: "bg-destructive/10" },
}

export function TopBar() {
  const router = useRouter()
  const { query, setQuery } = useSearch()
  const [showNotifs, setShowNotifs] = useState(false)

  return (
    <motion.header
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5, ease: [0.25, 0.1, 0.25, 1] }}
      className="fixed top-0 right-0 left-0 z-40 flex h-14 items-center justify-end gap-3 px-6 glass-topbar"
    >
      <div className="relative flex-1 max-w-md">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground pointer-events-none" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search agents, workflows..."
          className="h-9 w-full rounded-xl glass-input pl-9 pr-8 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none transition-all"
          suppressHydrationWarning
        />
        {query && (
          <button
            onClick={() => setQuery("")}
            className="absolute right-2 top-1/2 -translate-y-1/2 flex h-5 w-5 items-center justify-center rounded-full text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
          >
            <X className="h-3 w-3" />
          </button>
        )}
      </div>

      <div className="relative">
        <Button variant="ghost" size="icon" className="relative" onClick={() => setShowNotifs(!showNotifs)}>
          <Bell className="h-4 w-4" />
          <motion.span
            animate={{ scale: [1, 1.4, 1] }}
            transition={{ duration: 2, repeat: Infinity }}
            className="absolute right-2 top-2 h-2 w-2 rounded-full bg-accent"
          />
        </Button>
        <AnimatePresence>
          {showNotifs && (
            <motion.div
              initial={{ opacity: 0, y: -8, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -8, scale: 0.95 }}
              transition={{ duration: 0.15 }}
              className="absolute right-0 top-full mt-2 w-80 rounded-xl glass-card-strong shadow-xl z-50 overflow-hidden"
            >
              <div className="flex items-center justify-between px-4 py-3 border-b border-border/30">
                <span className="text-sm font-semibold">Notifications</span>
                <span className="text-[10px] text-muted-foreground">{notifications.length} new</span>
              </div>
              <div className="max-h-72 overflow-y-auto">
                {notifications.map((n) => {
                  const ns = notifStyles[n.type]
                  const Icon = ns.icon
                  return (
                    <div key={n.id} onClick={() => { router.push("/dashboard/notifications"); setShowNotifs(false) }} className="flex items-start gap-3 px-4 py-3 hover:bg-muted/30 transition-colors cursor-pointer border-b border-border/20 last:border-0">
                      <div className={cn("flex h-7 w-7 shrink-0 items-center justify-center rounded-full", ns.bg)}>
                        <Icon className={cn("h-3.5 w-3.5", ns.color)} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="text-xs font-medium text-foreground">{n.agent}</span>
                          <span className="text-[10px] text-muted-foreground">· {n.time}</span>
                        </div>
                        <p className="text-[11px] text-muted-foreground truncate">{n.message}</p>
                      </div>
                    </div>
                  )
                })}
              </div>
              <div className="border-t border-border/30 px-4 py-2">
                <button onClick={() => { router.push("/dashboard/notifications"); setShowNotifs(false) }} className="text-[11px] text-accent hover:text-accent/80 transition-colors w-full text-center">
                  View all notifications
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" className="gap-2 px-2 rounded-xl">
            <Avatar className="h-7 w-7 ring-2 ring-accent/20">
              <AvatarImage src="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=64&h=64&fit=crop&crop=face" />
              <AvatarFallback>AD</AvatarFallback>
            </Avatar>
            <span className="text-sm font-medium">Admin</span>
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <div className="px-2.5 py-2">
            <p className="text-sm font-medium">Admin</p>
            <p className="text-xs text-muted-foreground">admin@warehouse.io</p>
          </div>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => router.push("/dashboard/settings")} className="cursor-pointer">
            <Settings className="h-3.5 w-3.5" />
            Settings
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </motion.header>
  )
}
